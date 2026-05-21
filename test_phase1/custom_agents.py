"""커스텀 에이전트 예시 템플릿."""

from agent_chain.agents.base import BaseCoderAgent, BaseReviewerAgent
from agent_chain.core import Context, ReviewResult


class MyCoderAgent(BaseCoderAgent):
    """나만의 코딩 에이전트."""

    def generate_code(self, context: Context) -> str:
        # TODO: LLM API 호출 또는 자체 로직 구현
        return f"# {context.request}\ndef solution():\n    pass\n"


class MyReviewerAgent(BaseReviewerAgent):
    """나만의 검토 에이전트."""

    def review_code(self, context: Context) -> ReviewResult:
        # TODO: 실제 검토 로직 구현
        return ReviewResult(
            status="approved",
            message="검토 통과 (stub).",
        )
