"""Google Gemini CLI 호환 에이전트.

Google은 공식 Gemini CLI(google-gemini/gemini-cli)를 제공합니다.
다만 Google I/O 2026 개발자 발표에서는 Gemini CLI 사용자에게
Antigravity CLI로의 마이그레이션을 권장하고 있습니다.

이 모듈은 기존 Gemini CLI 인터페이스와 호환하기 위한 어댑터입니다.
신규 설정에서는 가능하면 antigravity_coder/antigravity_reviewer를 우선 사용하세요.
사용 시 config의 cli_command로 실제 바이너리 경로를 지정할 수 있습니다.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import CLICoderBase, CLIReviewerBase
from ...core import Context


class GeminiCLICoder(CLICoderBase):
    """Gemini CLI 호환 코더.

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
    """Gemini CLI 호환 리뷰어.

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
