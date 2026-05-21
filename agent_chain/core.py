"""AgentChain 핵심 타입 및 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import json


PipelineEventHandler = Callable[[str, Dict[str, Any]], None]


@dataclass
class ReviewResult:
    """검토 결과를 표현하는 데이터 클래스."""
    status: str  # "approved", "changes_requested", "comment"
    message: str
    suggestions: List[str] = field(default_factory=list)
    line_comments: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """직렬화 가능한 dict로 변환."""
        return {
            "status": self.status,
            "message": self.message,
            "suggestions": self.suggestions,
            "line_comments": self.line_comments,
        }


@dataclass
class Context:
    """파이프라인 전체에서 공유되는 실행 컨텍스트."""
    request: str  # 사용자 원본 요청
    workspace: Path  # 작업 디렉토리
    env: Optional[Any] = None  # Tool Environment (tools.env.Environment)
    code: Optional[str] = None  # 현재까지 생성된 코드
    language: Optional[str] = None  # 코드 언어
    review: Optional[ReviewResult] = None  # 마지막 검토 결과
    reviews: List[ReviewResult] = field(default_factory=list)  # 다중 리뷰 결과
    history: List[Dict[str, Any]] = field(default_factory=list)  # 전체 히스토리
    metadata: Dict[str, Any] = field(default_factory=dict)  # 임의 메타데이터
    iteration: int = 0  # 현재 반복 횟수

    def log_step(self, agent_name: str, role: str, output: Any) -> None:
        """실행 단계를 히스토리에 기록."""
        self.history.append({
            "iteration": self.iteration,
            "agent": agent_name,
            "role": role,
            "output": output,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request": self.request,
            "workspace": str(self.workspace),
            "code": self.code,
            "language": self.language,
            "review": self.review.to_dict() if self.review else None,
            "reviews": [r.to_dict() for r in self.reviews],
            "history": self.history,
            "iteration": self.iteration,
            "metadata": self.metadata,
        }


class Agent(ABC):
    """모든 에이전트가 구현해야 하는 기본 인터페이스."""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.config = config or {}

    @abstractmethod
    def run(self, context: Context) -> Context:
        """컨텍스트를 받아 처리 후 갱신된 컨텍스트를 반환."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"


def _step_output_key(step: Dict[str, Any]) -> Optional[str]:
    """Return the context field or metadata key a step is expected to produce."""
    if "output" in step:
        return step["output"]
    if "output_key" in step:
        return step["output_key"]

    role = step.get("role")
    if role == "coder":
        return "code"
    if role == "reviewer":
        return "review"
    return role


def _context_output(context: Context, output_key: Optional[str]) -> Any:
    if not output_key:
        return None
    if hasattr(context, output_key):
        return getattr(context, output_key)
    return context.metadata.get(output_key)


def _list_of_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _list_of_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _coerce_review(value: Any) -> ReviewResult:
    if isinstance(value, ReviewResult):
        return value
    if isinstance(value, dict):
        status = str(value.get("status", "comment"))
        if status not in {"approved", "changes_requested", "comment"}:
            status = "comment"
        return ReviewResult(
            status=status,
            message=str(value.get("message", "")).strip(),
            suggestions=_list_of_strings(value.get("suggestions", [])),
            line_comments=_list_of_dicts(value.get("line_comments", [])),
        )
    return ReviewResult(status="comment", message=str(value))


def _apply_agent_result(
    context: Context,
    result: Any,
    output_key: Optional[str],
) -> tuple[Context, bool]:
    """Merge common agent return shapes into Context.

    Native AgentChain agents mutate and return Context. Looser adapters may return
    a string, dict, ReviewResult, or None after mutating context in place.
    """
    if result is None:
        return context, False
    if isinstance(result, Context):
        return result, False
    if isinstance(result, ReviewResult):
        context.review = result
        return context, True

    if isinstance(result, dict):
        produced_review = False
        if "code" in result:
            context.code = None if result["code"] is None else str(result["code"])
        if "language" in result:
            context.language = None if result["language"] is None else str(result["language"])
        if "review" in result:
            context.review = _coerce_review(result["review"])
            produced_review = True
        elif "status" in result and "message" in result:
            context.review = _coerce_review(result)
            produced_review = True

        reserved = {"code", "language", "review", "status", "message", "suggestions", "line_comments"}
        for key, value in result.items():
            if key not in reserved:
                context.metadata[key] = value
        if output_key and output_key not in reserved and output_key not in result:
            context.metadata[output_key] = result
        return context, produced_review

    if output_key == "review":
        context.review = _coerce_review(result)
        return context, True
    if output_key and hasattr(context, output_key):
        setattr(context, output_key, result)
    elif output_key:
        context.metadata[output_key] = result
    return context, False


def _is_review_gate(step: Dict[str, Any], output_key: Optional[str], produced_review: bool) -> bool:
    if "review_gate" in step:
        return bool(step["review_gate"])
    if "gate" in step:
        return bool(step["gate"])
    return step.get("role") == "reviewer" or output_key == "review" or produced_review


def _retry_statuses(step: Dict[str, Any]) -> set[str]:
    value = step.get("retry_on", step.get("retry_on_status", ["changes_requested"]))
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value}
    return {"changes_requested"}


def _event_output(value: Any, max_chars: int = 4000) -> Dict[str, Any]:
    """Return a compact, JSON-safe representation for live UI events."""
    if isinstance(value, ReviewResult):
        return {"kind": "review", "value": value.to_dict()}
    if isinstance(value, str):
        return {
            "kind": "text",
            "length": len(value),
            "preview": value[:max_chars],
            "truncated": len(value) > max_chars,
        }
    try:
        json.dumps(value, ensure_ascii=False)
    except TypeError:
        return {"kind": "repr", "preview": repr(value)[:max_chars]}
    return {"kind": "json", "value": value}


def _emit(
    event_callback: Optional[PipelineEventHandler],
    event_type: str,
    **data: Any,
) -> None:
    if event_callback is not None:
        event_callback(event_type, data)


class Pipeline:
    """선언적 설정으로부터 N-step 워크플로우를 구성하고 실행."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.max_iterations = config.get("max_iterations", 3)
        self.steps: List[Dict[str, Any]] = list(config.get("steps", []))

    def execute(
        self,
        agents: Dict[str, Agent],
        request: str,
        workspace: Path,
        env: Optional[Any] = None,
        language: Optional[str] = None,
        event_callback: Optional[PipelineEventHandler] = None,
    ) -> Context:
        """등록된 에이전트 맵을 사용하여 multi-step 파이프라인을 실행."""
        ctx = Context(request=request, workspace=workspace, env=env, language=language)
        _emit(
            event_callback,
            "run_started",
            request=request,
            workspace=str(workspace),
            language=language,
            max_iterations=self.max_iterations,
            steps=[
                {
                    "role": step.get("role", step["agent"]),
                    "agent": step["agent"],
                    "output": _step_output_key(step),
                }
                for step in self.steps
            ],
        )

        for i in range(self.max_iterations):
            ctx.iteration = i + 1
            print(f"\n=== Iteration {ctx.iteration}/{self.max_iterations} ===")
            _emit(
                event_callback,
                "iteration_started",
                iteration=ctx.iteration,
                max_iterations=self.max_iterations,
            )

            should_retry = False

            for step in self.steps:
                role = step.get("role", step["agent"])
                agent_name = step["agent"]
                agent = agents.get(agent_name)
                if not agent:
                    raise ValueError(f"에이전트 '{agent_name}' 를 찾을 수 없습니다.")

                output_key = _step_output_key(step)
                agent_display_name = getattr(agent, "name", agent_name)
                _emit(
                    event_callback,
                    "step_started",
                    iteration=ctx.iteration,
                    role=role,
                    agent=agent_display_name,
                    agent_key=agent_name,
                    output=output_key,
                )
                result = agent.run(ctx)
                ctx, produced_review = _apply_agent_result(ctx, result, output_key)
                output_value = _context_output(ctx, output_key)
                ctx.log_step(agent_display_name, role, output_value)
                _emit(
                    event_callback,
                    "step_completed",
                    iteration=ctx.iteration,
                    role=role,
                    agent=agent_display_name,
                    agent_key=agent_name,
                    output=output_key,
                    result=_event_output(output_value),
                    code_length=len(ctx.code or ""),
                    review=ctx.review.to_dict() if ctx.review else None,
                )

                if _is_review_gate(step, output_key, produced_review) and ctx.review:
                    ctx.reviews.append(ctx.review)
                    print(f"[ReviewGate '{agent_display_name}'] {ctx.review.status}: {ctx.review.message}")
                    retry_requested = ctx.review.status in _retry_statuses(step)
                    _emit(
                        event_callback,
                        "review_gate",
                        iteration=ctx.iteration,
                        agent=agent_display_name,
                        status=ctx.review.status,
                        message=ctx.review.message,
                        suggestions=ctx.review.suggestions,
                        line_comments=ctx.review.line_comments,
                        retry=retry_requested,
                    )

                    if retry_requested:
                        should_retry = True
                        # 남은 steps를 skip하고 다음 iteration에서 다시 처음부터
                        break
                    elif ctx.review.status == "approved":
                        # 계속 진행 (다음 reviewer가 있을 수 있음)
                        pass
                    else:
                        # comment는 승인으로 간주, 계속 진행
                        pass

            if not should_retry:
                print("[OK] 모든 단계 통과. 파이프라인 종료.")
                _emit(
                    event_callback,
                    "iteration_completed",
                    iteration=ctx.iteration,
                    retry=False,
                )
                break

            if ctx.iteration >= self.max_iterations:
                print("[WARN] 최대 반복 횟수 도달. 종료.")
                _emit(
                    event_callback,
                    "iteration_completed",
                    iteration=ctx.iteration,
                    retry=False,
                    max_iterations_reached=True,
                )
                break

            print("[RETRY] 수정 요청이 있어 다음 반복을 재시도합니다...")
            _emit(
                event_callback,
                "iteration_completed",
                iteration=ctx.iteration,
                retry=True,
            )
            _emit(
                event_callback,
                "retry_scheduled",
                iteration=ctx.iteration + 1,
                reason=ctx.review.message if ctx.review else "",
            )

        _emit(
            event_callback,
            "run_completed",
            iteration=ctx.iteration,
            review=ctx.review.to_dict() if ctx.review else None,
            reviews=len(ctx.reviews),
            code_length=len(ctx.code or ""),
            result=ctx.to_dict(),
        )
        return ctx
