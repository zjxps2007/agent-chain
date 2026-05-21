"""에이전트 베이스 클래스."""

from abc import abstractmethod
from typing import Any, Dict, Optional

from ..core import Agent, Context, ReviewResult
from ..llm import DEFAULT_OPENAI_MODEL


class BaseCoderAgent(Agent):
    """코딩 에이전트를 위한 추상 베이스.

    구현체는 `generate_code` 만 오버라이드하면 됩니다.
    """

    def run(self, context: Context) -> Context:
        context.code = self.generate_code(context)
        return context

    @abstractmethod
    def generate_code(self, context: Context) -> str:
        """현재 컨텍스트를 바탕으로 코드를 생성하여 문자열로 반환."""
        ...


class BaseReviewerAgent(Agent):
    """검토 에이전트를 위한 추상 베이스.

    구현체는 `review_code` 만 오버라이드하면 됩니다.
    """

    def run(self, context: Context) -> Context:
        context.review = self.review_code(context)
        return context

    @abstractmethod
    def review_code(self, context: Context) -> ReviewResult:
        """코드를 검토하여 ReviewResult를 반환."""
        ...


class _LLMConfigMixin:
    """LLM 에이전트(Coder/Reviewer)의 공통 설정 초기화 헬퍼.

    사용하는 클래스는 반드시 Agent를 상속해야 합니다 (self.config 필요).
    """

    def _init_llm_config(self) -> None:
        self.model = self.config.get("model", DEFAULT_OPENAI_MODEL)
        self.temperature = self.config.get("temperature")
        self.max_output_tokens = self.config.get("max_output_tokens")
        self.reasoning_effort = self.config.get("reasoning_effort", "medium")
        self.verbosity = self.config.get("verbosity", "low")
        self.target_file = self.config.get("target_file")
        self._client = self.config.get("client")
