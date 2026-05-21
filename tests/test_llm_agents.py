from pathlib import Path
from types import SimpleNamespace

from agent_chain.agents import LLMCoderAgent, LLMReviewerAgent
from agent_chain.core import Context, ReviewResult
from agent_chain.tools import Environment


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict] = []

    def create(self, **payload):
        self.calls.append(payload)
        return SimpleNamespace(output_text=self.output_text)


class FakeOpenAIClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)


def test_llm_coder_uses_responses_api_and_writes_target_file(tmp_path: Path) -> None:
    client = FakeOpenAIClient("def solution():\n    return 42\n")
    env = Environment(tmp_path)
    agent = LLMCoderAgent(
        "llm_coder",
        {
            "client": client,
            "model": "test-model",
            "reasoning_effort": "low",
            "target_file": "generated.py",
        },
    )
    context = Context(
        request="정답 함수를 작성",
        workspace=tmp_path,
        env=env,
        language="python",
        review=ReviewResult(
            status="changes_requested",
            message="반환값이 틀립니다.",
            suggestions=["42를 반환하세요."],
        ),
    )

    code = agent.generate_code(context)

    assert code == "def solution():\n    return 42"
    assert (tmp_path / "generated.py").read_text(encoding="utf-8") == code

    payload = client.responses.calls[0]
    assert payload["model"] == "test-model"
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["text"]["verbosity"] == "low"
    assert "이전 리뷰 피드백" in payload["input"]


def test_llm_reviewer_parses_structured_review_json(tmp_path: Path) -> None:
    client = FakeOpenAIClient(
        """
{
  "status": "changes_requested",
  "message": "예외 처리가 필요합니다.",
  "suggestions": ["빈 입력을 처리하세요."],
  "line_comments": [{"line": 2, "message": "검증 로직 추가"}]
}
""".strip()
    )
    agent = LLMReviewerAgent(
        "llm_reviewer",
        {
            "client": client,
            "model": "test-reviewer",
            "reasoning_effort": "medium",
        },
    )
    context = Context(
        request="입력 검증 함수 작성",
        workspace=tmp_path,
        code="def validate(value):\n    return bool(value)\n",
        language="python",
    )

    review = agent.review_code(context)

    assert review.status == "changes_requested"
    assert review.message == "예외 처리가 필요합니다."
    assert review.suggestions == ["빈 입력을 처리하세요."]
    assert review.line_comments == [{"line": 2, "message": "검증 로직 추가"}]

    payload = client.responses.calls[0]
    assert payload["model"] == "test-reviewer"
    assert payload["text"]["format"]["name"] == "agent_chain_review"
    assert "입력 검증 함수 작성" in payload["input"]


def test_llm_reviewer_marks_unparseable_output_as_changes_requested(tmp_path: Path) -> None:
    client = FakeOpenAIClient("not json")
    agent = LLMReviewerAgent("llm_reviewer", {"client": client})
    context = Context(
        request="검토",
        workspace=tmp_path,
        code="print('hello')",
        language="python",
    )

    review = agent.review_code(context)

    assert review.status == "changes_requested"
    assert "JSON" in review.message
