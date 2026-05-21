"""내장 코딩 에이전트 예시."""

from typing import Any, Dict

from .base import BaseCoderAgent, _LLMConfigMixin
from ..core import Context
from ..llm import create_text_response, load_openai_client


class SimpleCoderAgent(BaseCoderAgent):
    """요청을 받아 간단한 파이썬 함수 스텁을 생성하는 예시 코더.

    실제 환경에서는 LLM API 호출, RAG, 내부 규칙 엔진 등으로 교체하면 됩니다.
    설정에 target_file이 있으면 해당 파일에 직접 쓰고, 없으면 ctx.code에 저장합니다.
    """

    def generate_code(self, context: Context) -> str:
        req = context.request
        review = context.review
        target_file = self.config.get("target_file")

        # 이전 검토 피드백이 있으면 반영 메시지 추가
        feedback_note = ""
        if review and review.status == "changes_requested":
            feedback_note = f"\n# NOTE: 이전 리뷰 피드백 반영 - {review.message}"

        code = (
            f"# 요청: {req}{feedback_note}\n"
            f"def generated_function():\n"
            f'    """{req}"""\n'
            f"    # TODO: 구현 필요\n"
            f"    pass\n"
        )

        if target_file and context.env is not None:
            try:
                context.env.write_file(target_file, code)
                print(f"[Coder '{self.name}'] {target_file}에 코드 작성 완료")
            except Exception as e:
                print(f"[Coder '{self.name}'] 파일 쓰기 실패: {e}")
        else:
            print(f"[Coder '{self.name}'] 코드 생성 완료 (in-memory)")

        return code


class LLMCoderAgent(_LLMConfigMixin, BaseCoderAgent):
    """OpenAI Responses API 기반 코더 에이전트."""

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self._init_llm_config()

    def generate_code(self, context: Context) -> str:
        print(f"[LLM Coder '{self.name}'] model={self.model} 로 코드 생성 중...")

        client = load_openai_client(self._client)
        code = create_text_response(
            client,
            model=self.model,
            instructions=self.config.get("instructions", _DEFAULT_CODER_INSTRUCTIONS),
            input_text=self._build_prompt(context),
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            reasoning_effort=self.reasoning_effort,
            verbosity=self.verbosity,
            store=bool(self.config.get("store", False)),
        )

        if self.target_file and context.env is not None:
            try:
                context.env.write_file(self.target_file, code)
            except Exception as e:
                print(f"[LLM Coder] 파일 쓰기 실패: {e}")

        return code

    def _build_prompt(self, context: Context) -> str:
        language = context.language or self.config.get("language") or "unspecified"
        parts = [
            f"요청:\n{context.request}",
            f"대상 언어: {language}",
        ]

        if context.code:
            parts.append(f"현재 코드:\n```{language}\n{context.code}\n```")

        if context.review and context.review.status == "changes_requested":
            feedback = [context.review.message]
            if context.review.suggestions:
                feedback.extend(f"- {item}" for item in context.review.suggestions)
            parts.append("이전 리뷰 피드백:\n" + "\n".join(feedback))

        if self.target_file:
            parts.append(f"결과 파일 경로: {self.target_file}")

        parts.append("코드만 출력하세요. 설명, 마크다운 코드펜스, 후속 안내 문장은 출력하지 마세요.")
        return "\n\n".join(parts)


_DEFAULT_CODER_INSTRUCTIONS = (
    "You are a senior software engineer writing production-ready code. "
    "Follow the user's request, preserve existing behavior when revising code, "
    "and return only the final code content."
)
