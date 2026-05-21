"""Shared helpers for CLI-worker integration profiles."""

from __future__ import annotations

from typing import Any, Dict, Optional


SUPPORTED_CLIS = ("codex", "kimi", "antigravity")
PROFILE_PAIRS = {
    "codex-antigravity": ("codex", "antigravity"),
    "codex-kimi": ("codex", "kimi"),
    "kimi-codex": ("kimi", "codex"),
    "kimi-antigravity": ("kimi", "antigravity"),
    "antigravity-codex": ("antigravity", "codex"),
    "antigravity-kimi": ("antigravity", "kimi"),
}
SUPPORTED_PROFILES = tuple(PROFILE_PAIRS)


def agent_name(cli_name: str, role: str) -> str:
    if cli_name not in SUPPORTED_CLIS:
        raise ValueError(f"unsupported CLI: {cli_name}")
    if role not in {"coder", "reviewer"}:
        raise ValueError(f"unsupported role: {role}")
    return f"{cli_name}_{role}"


def build_cli_pair_config(
    *,
    coder_cli: Optional[str] = None,
    reviewer_cli: Optional[str] = None,
    profile: Optional[str] = None,
    max_iterations: Optional[int] = None,
    target_file: Optional[str] = None,
    coder_model: Optional[str] = None,
    reviewer_model: Optional[str] = None,
    coder_command: Optional[str] = None,
    reviewer_command: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an AgentChain config for a pair of supported CLI agents."""
    if profile:
        if profile not in PROFILE_PAIRS:
            raise ValueError(f"unsupported profile: {profile}")
        profile_coder, profile_reviewer = PROFILE_PAIRS[profile]
        coder_cli = coder_cli or profile_coder
        reviewer_cli = reviewer_cli or profile_reviewer

    coder_cli = coder_cli or "codex"
    reviewer_cli = reviewer_cli or "antigravity"

    coder_agent = agent_name(coder_cli, "coder")
    reviewer_agent = agent_name(reviewer_cli, "reviewer")

    config: Dict[str, Any] = {
        "max_iterations": max_iterations or 3,
        "steps": [
            {"role": "coder", "agent": coder_agent, "output": "code"},
            {"role": "reviewer", "agent": reviewer_agent, "output": "review"},
        ],
        "agent_configs": {
            coder_agent: {},
            reviewer_agent: {},
        },
    }

    coder_config = config["agent_configs"][coder_agent]
    reviewer_config = config["agent_configs"][reviewer_agent]

    if target_file:
        coder_config["target_file"] = target_file
        reviewer_config["target_file"] = target_file
    if coder_model:
        coder_config["model"] = coder_model
    if reviewer_model:
        reviewer_config["model"] = reviewer_model
    if coder_command:
        coder_config["cli_command"] = coder_command
    if reviewer_command:
        reviewer_config["cli_command"] = reviewer_command

    return config


def build_cli_review_config(
    *,
    reviewer_cli: Optional[str] = None,
    max_iterations: Optional[int] = None,
    target_file: Optional[str] = None,
    reviewer_model: Optional[str] = None,
    reviewer_command: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an AgentChain config for a reviewer-only host-session flow."""
    reviewer_cli = reviewer_cli or "kimi"
    reviewer_agent = agent_name(reviewer_cli, "reviewer")

    config: Dict[str, Any] = {
        "max_iterations": max_iterations or 1,
        "steps": [
            {
                "role": "reviewer",
                "agent": reviewer_agent,
                "output": "review",
                "retry_on": [],
            },
        ],
        "agent_configs": {
            reviewer_agent: {},
        },
    }

    reviewer_config = config["agent_configs"][reviewer_agent]
    if target_file:
        reviewer_config["target_file"] = target_file
    if reviewer_model:
        reviewer_config["model"] = reviewer_model
    if reviewer_command:
        reviewer_config["cli_command"] = reviewer_command

    return config


def uses_generated_cli_config(
    *,
    profile: Optional[str] = None,
    coder_cli: Optional[str] = None,
    reviewer_cli: Optional[str] = None,
) -> bool:
    return bool(profile or coder_cli or reviewer_cli)
