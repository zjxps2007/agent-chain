from pathlib import Path

import pytest

from agent_chain.agents.base import BaseCoderAgent, BaseReviewerAgent
from agent_chain.core import Context, Pipeline, ReviewResult


class IterationCoder(BaseCoderAgent):
    def generate_code(self, context: Context) -> str:
        return f"def solution():\n    return {context.iteration}\n"


class RejectOnceReviewer(BaseReviewerAgent):
    def review_code(self, context: Context) -> ReviewResult:
        if context.iteration == 1:
            return ReviewResult(
                status="changes_requested",
                message="한 번 더 생성해야 합니다.",
                suggestions=["retry"],
            )
        return ReviewResult(status="approved", message="통과")


def test_pipeline_retries_from_first_step_after_changes_requested(tmp_path: Path) -> None:
    pipeline = Pipeline(
        {
            "max_iterations": 3,
            "steps": [
                {"role": "coder", "agent": "coder"},
                {"role": "reviewer", "agent": "reviewer"},
            ],
        }
    )
    agents = {
        "coder": IterationCoder("coder"),
        "reviewer": RejectOnceReviewer("reviewer"),
    }

    context = pipeline.execute(
        agents=agents,
        request="반복 테스트",
        workspace=tmp_path,
        language="python",
    )

    assert context.iteration == 2
    assert context.code == "def solution():\n    return 2\n"
    assert context.review is not None
    assert context.review.status == "approved"
    assert [review.status for review in context.reviews] == ["changes_requested", "approved"]
    assert [entry["role"] for entry in context.history] == [
        "coder",
        "reviewer",
        "coder",
        "reviewer",
    ]


def test_pipeline_emits_live_events(tmp_path: Path) -> None:
    pipeline = Pipeline(
        {
            "max_iterations": 3,
            "steps": [
                {"role": "coder", "agent": "coder"},
                {"role": "reviewer", "agent": "reviewer"},
            ],
        }
    )
    agents = {
        "coder": IterationCoder("coder"),
        "reviewer": RejectOnceReviewer("reviewer"),
    }
    events = []

    pipeline.execute(
        agents=agents,
        request="이벤트 테스트",
        workspace=tmp_path,
        language="python",
        event_callback=lambda event_type, data: events.append((event_type, data)),
    )

    event_types = [event_type for event_type, _ in events]

    assert event_types[0] == "run_started"
    assert event_types.count("iteration_started") == 2
    assert event_types.count("step_started") == 4
    assert event_types.count("step_completed") == 4
    assert "review_gate" in event_types
    assert "retry_scheduled" in event_types
    assert event_types[-1] == "run_completed"
    assert events[-1][1]["review"]["status"] == "approved"


def test_pipeline_raises_for_missing_agent(tmp_path: Path) -> None:
    pipeline = Pipeline(
        {
            "steps": [
                {"role": "coder", "agent": "missing"},
            ],
        }
    )

    with pytest.raises(ValueError, match="missing"):
        pipeline.execute(
            agents={},
            request="없는 에이전트",
            workspace=tmp_path,
        )


def test_context_to_dict_serializes_review_state(tmp_path: Path) -> None:
    context = Context(request="요청", workspace=tmp_path, language="python")
    context.review = ReviewResult(
        status="comment",
        message="참고",
        suggestions=["제안"],
    )
    context.reviews.append(context.review)
    context.metadata["key"] = "value"

    data = context.to_dict()

    assert data["workspace"] == str(tmp_path)
    assert data["review"] == {
        "status": "comment",
        "message": "참고",
        "suggestions": ["제안"],
        "line_comments": [],
    }
    assert data["reviews"] == [
        {"status": "comment", "message": "참고", "suggestions": ["제안"], "line_comments": []}
    ]
    assert data["history"] == []
    assert data["metadata"] == {"key": "value"}
