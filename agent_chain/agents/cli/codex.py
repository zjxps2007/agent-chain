"""OpenAI Codex CLI 기반 에이전트."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import CLICoderBase, CLIReviewerBase
from ...core import Context


class CodexCLICoder(CLICoderBase):
    """OpenAI Codex CLI를 subprocess로 호출하는 코더.

    config:
      - target_file: 코드를 작성할 파일 경로 (선택)
      - model: 사용 모델 (예: gpt-5.4)
      - max_steps: codex exec에는 직접 해당 없음 (stub)
      - extra_args: 추가 CLI 인자 (리스트)
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.cli_command = self.config.get("cli_command", "codex")
        self.model = self.config.get("model", "gpt-5.4")

    def build_command(self, context: Context) -> List[str]:
        parts: List[str] = [self.cli_command, "exec"]

        if self.model:
            parts += ["--model", self.model]

        prompt = context.request
        prompt += self._build_feedback_suffix(context)

        if self.target_file:
            prompt += (
                f"\n\nWrite the result to {self.target_file}. "
                f"If the file exists, modify it based on the feedback."
            )

        parts += [prompt]

        if self.extra_args:
            parts += [str(a) for a in self.extra_args]

        return parts


class CodexCLIReviewer(CLIReviewerBase):
    """OpenAI Codex CLI를 subprocess로 호출하는 리뷰어.

    config:
      - target_file: 검토할 파일 경로
      - model: 사용 모델 (예: gpt-5.4)
      - extra_args: 추가 CLI 인자 (리스트)
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.cli_command = self.config.get("cli_command", "codex")
        self.model = self.config.get("model", "gpt-5.4")

    def build_command(self, context: Context) -> List[str]:
        parts: List[str] = [self.cli_command, "exec"]

        if self.model:
            parts += ["--model", self.model]

        # 리뷰어는 read-only sandbox 권장
        parts += ["--sandbox", "read-only"]

        target = self.target_file or "the current code"
        prompt = (
            f"Original request:\n{context.request}\n\n"
            f"Review {target} for code quality, bugs, and security issues. "
            f"Return the result as JSON:\n"
            f'{{"status": "approved" or "changes_requested", '
            f'"message": "summary", '
            f'"suggestions": ["specific suggestion 1", "suggestion 2"]}}'
        )

        code_snippet = ""
        if not self.target_file and context.code:
            code_snippet = context.code[:4000]

        if code_snippet:
            prompt += f"\n\nCode:\n{code_snippet}"

        parts += [prompt]

        if self.extra_args:
            parts += [str(a) for a in self.extra_args]

        return parts
