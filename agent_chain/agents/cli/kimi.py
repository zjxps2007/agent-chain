"""Kimi Code CLI 기반 에이전트."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .base import CLICoderBase, CLIReviewerBase
from ...core import Context, ReviewResult


class KimiCLICoder(CLICoderBase):
    """Kimi Code CLI를 subprocess로 호출하는 코더.

    config:
      - target_file: 코드를 작성할 파일 경로 (선택)
      - max_steps: 최대 tool call 횟수 (기본 10)
      - extra_args: 추가 CLI 인자 (리스트)
      - model: 사용 모델 (선택)
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.cli_command = self.config.get("cli_command", "kimi")

    def build_command(self, context: Context) -> List[str]:
        parts: List[str] = [self.cli_command, "--quiet"]

        if self.config.get("model"):
            parts += ["--model", self.config["model"]]

        # 프롬프트 조립
        prompt = context.request
        prompt += self._build_feedback_suffix(context)

        if self.target_file:
            prompt += (
                f"\n\n결과를 {self.target_file} 파일에 작성해주세요. "
                f"기존 내용이 있다면 피드백을 반영하여 수정해주세요."
            )
        else:
            prompt += "\n\n생성한 코드만 출력해주세요."

        parts += ["--prompt", prompt]
        parts += ["--work-dir", str(context.workspace)]
        parts += ["-y"]
        parts += ["--max-steps-per-turn", str(self.max_steps)]

        if self.extra_args:
            parts += [str(a) for a in self.extra_args]

        return parts


class KimiCLIReviewer(CLIReviewerBase):
    """Kimi Code CLI를 subprocess로 호출하는 리뷰어.

    config:
      - target_file: 검토할 파일 경로 (기본: ctx.code 사용)
      - max_steps: 최대 tool call 횟수 (기본 10)
      - extra_args: 추가 CLI 인자 (리스트)
      - model: 사용 모델 (선택)
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.cli_command = self.config.get("cli_command", "kimi")

    def build_command(self, context: Context) -> List[str]:
        parts: List[str] = [self.cli_command, "--quiet"]

        if self.config.get("model"):
            parts += ["--model", self.config["model"]]

        # 검토 대상 결정
        target = self.target_file or "생성된 코드"
        code_snippet = ""
        if not self.target_file and context.code:
            code_snippet = context.code[:4000]  # 너무 길면 잘라냄

        prompt = (
            f"당신은 코드 리뷰어입니다. "
            f"{target}를 읽고 검토한 뒤, "
            f"반드시 다음 JSON 형식으로만 결과를 반환하세요:\n"
            f'{{"status": "approved" 또는 "changes_requested", '
            f'"message": "검토 요약 (한 문장)", '
            f'"suggestions": ["구체적 제안1", "제안2"]}}\n\n'
            f"규칙:\n"
            f"- approved: 코드가 양호함\n"
            f"- changes_requested: 수정이 필요함\n"
            f"- suggestions는 반드시 한국어로 작성\n"
        )

        if code_snippet:
            prompt += f"\n[코드]\n{code_snippet}"
        else:
            prompt += f"\n파일 경로: {target}"

        parts += ["--prompt", prompt]
        parts += ["--work-dir", str(context.workspace)]
        parts += ["-y"]
        parts += ["--max-steps-per-turn", str(self.max_steps)]

        if self.extra_args:
            parts += [str(a) for a in self.extra_args]

        return parts

    def parse_review(self, stdout: str) -> ReviewResult:
        """Kimi의 stdout에서 JSON을 추출하여 ReviewResult로 변환."""
        text = stdout.strip()

        # ```json ... ``` 블록이 있으면 추출
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()

        return super().parse_review(text)
