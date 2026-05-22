"""Antigravity CLI based agents."""

from __future__ import annotations

from typing import Any, Dict, List, Union

from .generic import ConfigurableCLICoder, ConfigurableCLIReviewer
from ...core import Context, ReviewResult


class _AntigravityCommandMixin:
    """Default Antigravity command shape with config override support."""

    def _init_antigravity_config(self) -> None:
        self.cli_command = self.config.get("cli_command", "agy")

    def _antigravity_command(self, context: Context, prompt: str) -> Union[str, List[str]]:
        if self.config.get("command") is not None:
            return self._command_from_config(context, prompt)

        parts = [self.cli_command, "--prompt", prompt]
        if self.extra_args:
            parts.extend(str(item) for item in self.extra_args)
        return parts


class AntigravityCLICoder(_AntigravityCommandMixin, ConfigurableCLICoder):
    """Antigravity CLI coder.

    The default command is `agy --prompt {prompt}`. If the installed
    CLI uses a different syntax, set `command` explicitly in agent_configs.
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self._init_antigravity_config()

    def build_command(self, context: Context) -> Union[str, List[str]]:
        prompt = self._build_prompt_from_template(context, _DEFAULT_ANTIGRAVITY_CODER_PROMPT)
        return self._antigravity_command(context, prompt)


class AntigravityCLIReviewer(_AntigravityCommandMixin, ConfigurableCLIReviewer):
    """Antigravity CLI reviewer.

    Review output should include JSON with status/message/suggestions. Fenced or
    embedded JSON is accepted by the inherited parser.
    """

    def __init__(self, name: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self._init_antigravity_config()

    def build_command(self, context: Context) -> Union[str, List[str]]:
        prompt = self._build_prompt_from_template(context, _DEFAULT_ANTIGRAVITY_REVIEWER_PROMPT)
        return self._antigravity_command(context, prompt)

    def parse_review(self, stdout: str) -> ReviewResult:
        return super().parse_review(stdout)


_DEFAULT_ANTIGRAVITY_CODER_PROMPT = """\
Implement the requested change.

Request:
{request}

Language: {language}
Previous review feedback:
{review_feedback}

Write the result to {target_file} when a target file is provided. Otherwise return only code.
"""


_DEFAULT_ANTIGRAVITY_REVIEWER_PROMPT = """\
Review the code for correctness, security, and maintainability.

Request:
{request}

Review mode:
{review_mode_instruction}

Language: {language}
Target file: {target_file}

Code:
{code_snippet}

Return JSON only:
{"status":"approved" or "changes_requested","message":"summary","suggestions":["specific item"]}
"""
