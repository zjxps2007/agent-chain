"""Configurable CLI agents for tools without a dedicated adapter."""

from __future__ import annotations

import shlex
import re
from typing import Any, Dict, List, Union

from .base import CLICoderBase, CLIReviewerBase
from ...core import Context, ReviewResult


def _format_template(template: str, values: Dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            return match.group(0)
        return str(values[key])

    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, template)


def _review_feedback(context: Context) -> str:
    if not context.review:
        return ""
    parts = [context.review.message]
    if context.review.suggestions:
        parts.extend(f"- {item}" for item in context.review.suggestions)
    return "\n".join(parts)


class _ConfigurableCLICommandMixin:
    def _template_values(self, context: Context, prompt: str) -> Dict[str, Any]:
        code = context.code or ""
        return {
            "request": context.request,
            "workspace": str(context.workspace),
            "language": context.language or self.config.get("language") or "",
            "code": code,
            "code_snippet": code[: int(self.config.get("max_code_chars", 4000))],
            "target_file": self.target_file or "",
            "review_feedback": _review_feedback(context),
            "review_mode_instruction": (
                self._review_mode_instruction() if hasattr(self, "_review_mode_instruction") else ""
            ),
            "prompt": prompt,
        }

    def _build_prompt_from_template(self, context: Context, default_prompt: str) -> str:
        template = self.config.get("prompt", default_prompt)
        return _format_template(template, self._template_values(context, ""))

    def _command_from_config(self, context: Context, prompt: str) -> Union[str, List[str]]:
        command = self.config.get("command")
        values = self._template_values(context, prompt)

        if command is None:
            args = [str(item) for item in self.extra_args]
            return [self.cli_command, *args, prompt]

        if isinstance(command, list):
            return [_format_template(str(item), values) for item in command]

        if isinstance(command, str):
            formatted = _format_template(command, values)
            return shlex.split(formatted)

        raise TypeError("command must be a string or list of strings")


class ConfigurableCLICoder(_ConfigurableCLICommandMixin, CLICoderBase):
    """CLI coder driven entirely by config.

    Config:
      - cli_command: executable used when command is omitted
      - command: optional full command, e.g. ["tool", "--prompt", "{prompt}"]
      - prompt: optional prompt template
      - target_file: read generated code from this file when present
    """

    def build_command(self, context: Context) -> Union[str, List[str]]:
        prompt = self._build_prompt_from_template(context, _DEFAULT_CODER_PROMPT)
        return self._command_from_config(context, prompt)


class ConfigurableCLIReviewer(_ConfigurableCLICommandMixin, CLIReviewerBase):
    """CLI reviewer driven entirely by config.

    The CLI should ideally print JSON with status/message/suggestions. Plain text
    output is still accepted and becomes a comment review.
    """

    def build_command(self, context: Context) -> Union[str, List[str]]:
        prompt = self._build_prompt_from_template(context, _DEFAULT_REVIEWER_PROMPT)
        return self._command_from_config(context, prompt)

    def parse_review(self, stdout: str) -> ReviewResult:
        text = stdout.strip()
        if "```json" in text:
            start = text.find("```json") + len("```json")
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + len("```")
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()

        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                text = text[start : end + 1]

        return super().parse_review(text)


_DEFAULT_CODER_PROMPT = """\
Implement the requested change.

Request:
{request}

Language: {language}
Previous review feedback:
{review_feedback}

Return only the generated code unless instructed to write a file.
"""


_DEFAULT_REVIEWER_PROMPT = """\
Review the code for correctness, security, and maintainability.

{review_mode_instruction}

Request:
{request}

Language: {language}
Target file: {target_file}

Code:
{code_snippet}

Return JSON only:
{"status":"approved" or "changes_requested","message":"summary","suggestions":["specific item"]}
"""
