"""Google Gemini CLI 기반 에이전트 (Stub).

Google은 공식 Gemini CLI를 별도로 제공하지 않습니다.
gemini-cli (https://github.com/reugn/gemini-cli) 같은 서드파티 도구나
gcloud CLI의 gemini 명령어를 사용한다고 가정하고 stub을 작성합니다.

사용 시 config의 cli_command를 실제 바이너리 경로로 설정하세요.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import CLICoderBase, CLIReviewerBase
from ...core import Context


class GeminiCLICoder(CLICoderBase):
    """Gemini CLI 코더 (stub).

    config:
      - cli_command: 실제 Gemini CLI 바이너리 (기본: "gemini")
      - target_file: 코드를 작성할 파일 경로
      - model: 사용 모델 (선택)
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.cli_command = self.config.get("cli_command", "gemini")

    def build_command(self, context: Context) -> List[str]:
        parts: List[str] = [self.cli_command]

        if self.config.get("model"):
            parts += ["--model", self.config["model"]]

        prompt = context.request
        prompt += self._build_feedback_suffix(context)

        if self.target_file:
            prompt += f"\n\nWrite result to {self.target_file}"

        parts += ["--prompt", prompt]

        if self.extra_args:
            parts += [str(a) for a in self.extra_args]

        return parts


class GeminiCLIReviewer(CLIReviewerBase):
    """Gemini CLI 리뷰어 (stub).

    config:
      - cli_command: 실제 Gemini CLI 바이너리 (기본: "gemini")
      - target_file: 검토할 파일 경로
      - model: 사용 모델 (선택)
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.cli_command = self.config.get("cli_command", "gemini")

    def build_command(self, context: Context) -> List[str]:
        parts: List[str] = [self.cli_command]

        if self.config.get("model"):
            parts += ["--model", self.config["model"]]

        target = self.target_file or "the code"
        prompt = (
            f"Review {target}. Return JSON: "
            f'{{"status": "approved" or "changes_requested", '
            f'"message": "summary", "suggestions": []}}'
        )

        code_snippet = ""
        if not self.target_file and context.code:
            code_snippet = context.code[:4000]
        if code_snippet:
            prompt += f"\n\nCode:\n{code_snippet}"

        parts += ["--prompt", prompt]

        if self.extra_args:
            parts += [str(a) for a in self.extra_args]

        return parts
