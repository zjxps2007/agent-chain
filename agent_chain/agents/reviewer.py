"""내장 검토 에이전트 예시."""

from typing import Any, Dict, List

from .base import BaseReviewerAgent, _LLMConfigMixin
from ..core import Context, ReviewResult
from ..llm import (
    create_text_response,
    load_openai_client,
    parse_json_object,
)


class SimpleReviewerAgent(BaseReviewerAgent):
    """간단한 규칙 기반 검토 에이전트 예시.

    실제 환경에서는 정적 분석기, LLM 기반 리뷰어, 보안 스캐너 등으로 교체 가능.
    설정에 target_file이 있으면 해당 파일을 읽어 검토합니다.
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.rules = self.config.get("rules", [])
        self.require_docstring = self.config.get("require_docstring", True)
        self.max_line_length = self.config.get("max_line_length", 100)
        self.target_file = self.config.get("target_file")

    def review_code(self, context: Context) -> ReviewResult:
        # 설정에 target_file이 있으면 파일에서 읽고, 없으면 ctx.code 사용
        code = context.code or ""
        if self.target_file and context.env is not None:
            try:
                code = context.env.read_file(self.target_file)
                print(f"[Reviewer '{self.name}'] {self.target_file} 읽어서 검토 중")
            except Exception as e:
                print(f"[Reviewer '{self.name}'] 파일 읽기 실패: {e}")

        issues: List[str] = []

        if "TODO" in code:
            issues.append("TODO 주석이 남아있습니다. 구현을 완료하세요.")

        if self.require_docstring and '"""' not in code:
            issues.append("함수에 docstring이 없습니다.")

        for i, line in enumerate(code.splitlines(), 1):
            if len(line) > self.max_line_length:
                issues.append(f"Line {i}: 라인 길이 {len(line)} > {self.max_line_length}")

        # 반복 횟수가 2회 이상이면 승인 (데모 목적)
        if context.iteration >= 2:
            return ReviewResult(
                status="approved",
                message=f"{context.iteration}회 반복 후 승인됨.",
                suggestions=issues,
            )

        if issues:
            return ReviewResult(
                status="changes_requested",
                message="코드 수정이 필요합니다.",
                suggestions=issues,
            )

        return ReviewResult(
            status="approved",
            message="검토 통과.",
        )


class LLMReviewerAgent(_LLMConfigMixin, BaseReviewerAgent):
    """OpenAI Responses API 기반 검토 에이전트."""

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self._init_llm_config()
        self.max_code_chars = self.config.get("max_code_chars", 12000)

    def review_code(self, context: Context) -> ReviewResult:
        print(f"[LLM Reviewer '{self.name}'] model={self.model} 로 리뷰 중...")

        client = load_openai_client(self._client)
        code = self._load_code(context)
        raw = create_text_response(
            client,
            model=self.model,
            instructions=self.config.get("instructions", _DEFAULT_REVIEWER_INSTRUCTIONS),
            input_text=self._build_prompt(context, code),
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            reasoning_effort=self.reasoning_effort,
            verbosity=self.verbosity,
            text_format=_review_json_schema(),
            store=bool(self.config.get("store", False)),
        )

        try:
            data = parse_json_object(raw)
        except Exception:
            return ReviewResult(
                status="changes_requested",
                message="LLM 리뷰 응답을 JSON으로 해석하지 못했습니다.",
                suggestions=[raw[:500]],
            )

        status = str(data.get("status", "comment"))
        if status not in {"approved", "changes_requested", "comment"}:
            status = "changes_requested"

        return ReviewResult(
            status=status,
            message=str(data.get("message", "")).strip() or "리뷰 메시지가 비어 있습니다.",
            suggestions=_string_list(data.get("suggestions", [])),
            line_comments=_dict_list(data.get("line_comments", [])),
        )

    def _load_code(self, context: Context) -> str:
        code = context.code or ""
        if self.target_file and context.env is not None:
            try:
                code = context.env.read_file(self.target_file)
                print(f"[LLM Reviewer '{self.name}'] {self.target_file} 읽어서 검토 중")
            except Exception as e:
                print(f"[LLM Reviewer '{self.name}'] 파일 읽기 실패: {e}")
        return code[: self.max_code_chars]

    def _build_prompt(self, context: Context, code: str) -> str:
        language = context.language or self.config.get("language") or "unspecified"
        target = self.target_file or "in-memory context.code"
        return (
            f"요청:\n{context.request}\n\n"
            f"검토 대상: {target}\n"
            f"대상 언어: {language}\n\n"
            f"코드:\n```{language}\n{code}\n```\n\n"
            "버그, 보안 리스크, 요구사항 누락, 유지보수성 문제를 우선순위대로 검토하세요."
        )


def _review_json_schema() -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "agent_chain_review",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["approved", "changes_requested", "comment"],
                },
                "message": {"type": "string"},
                "suggestions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "line_comments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line": {"type": "integer"},
                            "message": {"type": "string"},
                        },
                        "required": ["line", "message"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["status", "message", "suggestions", "line_comments"],
            "additionalProperties": False,
        },
    }


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _dict_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


_DEFAULT_REVIEWER_INSTRUCTIONS = (
    "You are a strict code reviewer. Return only JSON matching the provided schema. "
    "Use changes_requested for correctness, security, or requirement issues; "
    "use approved only when the code is ready to ship."
)
