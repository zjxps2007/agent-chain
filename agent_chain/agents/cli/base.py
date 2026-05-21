"""CLI 기반 에이전트 베이스 클래스.

외부 CLI 도구(kimi, codex, gemini 등)를 subprocess로 호출하고,
stdout을 파싱하여 AgentChain 파이프라인에 통합합니다.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Union

from ..base import BaseCoderAgent, BaseReviewerAgent
from ...core import Context, ReviewResult
from ...tools.env import ShellResult


class _CLIMixin:
    """CLI 에이전트 공통 초기화 및 셸 실행 헬퍼.

    CLICoderBase와 CLIReviewerBase에서 중복되는 로직을 공유합니다.
    사용하는 클래스는 반드시 Agent를 상속해야 합니다 (self.config, self.name 필요).
    """

    def _init_cli_config(self) -> None:
        """공통 CLI 설정 필드를 초기화."""
        self.cli_command = self.config.get("cli_command", "echo")
        self.max_steps = self.config.get("max_steps", 10)
        self.extra_args = self.config.get("extra_args", [])
        self.target_file = self.config.get("target_file")

    def _execute_command(self, context: Context, label: str) -> ShellResult:
        """build_command() → 셸 실행 → 에러 처리까지의 공통 흐름."""
        cmd = self.build_command(context)
        cmd_display = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else cmd
        print(f"[{label} '{self.name}'] 실행: {cmd_display[:120]}...")

        if context.env is None:
            raise RuntimeError("CLI 에이전트는 Environment가 필요합니다.")

        result = context.env.run_shell(cmd)

        if result.returncode != 0:
            err = (result.stderr or "").strip() or "(no stderr)"
            raise RuntimeError(f"CLI 실행 실패 (rc={result.returncode}): {err}")

        return result

    @staticmethod
    def _build_feedback_suffix(context: Context) -> str:
        """리뷰 피드백이 있으면 프롬프트 접미사를 생성."""
        if not (context.review and context.review.status == "changes_requested"):
            return ""
        parts = [f"\n\n[이전 검토 피드백]\n{context.review.message}"]
        if context.review.suggestions:
            parts.append(f"제안: {context.review.suggestions}")
        return "\n".join(parts)


class CLICoderBase(_CLIMixin, BaseCoderAgent):
    """CLI를 subprocess로 호출하는 코더 베이스.

    구현체는 `build_command()`만 오버라이드하면 됩니다.
    문자열 또는 문자열 리스트를 반환할 수 있습니다.
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self._init_cli_config()

    def build_command(self, context: Context) -> Union[str, List[str]]:
        """실행할 셸 명령어를 조립. 자식 클래스에서 구현."""
        raise NotImplementedError

    def parse_output(self, stdout: str) -> str:
        """CLI stdout을 파싱하여 코드 문자열로 변환. 기본: 그대로 반환."""
        return stdout

    def generate_code(self, context: Context) -> str:
        result = self._execute_command(context, "CLICoder")

        # CLI가 직접 파일을 썼다면 파일에서 읽고, 아니면 stdout 파싱
        if self.target_file and context.env.exists(self.target_file):
            code = context.env.read_file(self.target_file)
            print(f"[CLICoder '{self.name}'] {self.target_file} 읽기 완료")
            return code

        code = self.parse_output(result.stdout)
        print(f"[CLICoder '{self.name}'] stdout 파싱 완료 ({len(code)} chars)")
        return code


class CLIReviewerBase(_CLIMixin, BaseReviewerAgent):
    """CLI를 subprocess로 호출하는 리뷰어 베이스.

    구현체는 `build_command()`만 오버라이드하면 됩니다.
    문자열 또는 문자열 리스트를 반환할 수 있습니다.
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self._init_cli_config()

    def build_command(self, context: Context) -> Union[str, List[str]]:
        """실행할 셸 명령어를 조립. 자식 클래스에서 구현."""
        raise NotImplementedError

    def parse_review(self, stdout: str) -> ReviewResult:
        """CLI stdout을 파싱하여 ReviewResult로 변환.

        기본 구현:
        1. JSON 파싱 시도
        2. 실패하면 전체 텍스트를 message로 사용
        """
        # 1. JSON 파싱 시도
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                return ReviewResult(
                    status=data.get("status", "comment"),
                    message=data.get("message", ""),
                    suggestions=data.get("suggestions", []),
                )
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. Fallback: 텍스트 전체를 message로
        return ReviewResult(
            status="comment",
            message=stdout.strip()[:2000],
            suggestions=[],
        )

    def review_code(self, context: Context) -> ReviewResult:
        result = self._execute_command(context, "CLIReviewer")
        review = self.parse_review(result.stdout)
        print(f"[CLIReviewer '{self.name}'] 결과: {review.status}")
        return review
