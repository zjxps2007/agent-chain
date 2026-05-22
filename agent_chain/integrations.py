"""Shared helpers for CLI-worker integration profiles."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Optional


SUPPORTED_CLIS = ("codex", "kimi", "antigravity")
SUPPORTED_INSTALL_TARGETS = (*SUPPORTED_CLIS, "all")
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


def integration_assets_root(repo_root: Optional[Path] = None) -> Path:
    """Return the checked-in integration pack directory."""
    root = repo_root or Path(__file__).resolve().parents[1]
    assets = root / "integrations"
    if not assets.exists():
        raise FileNotFoundError(f"integration assets not found: {assets}")
    return assets


def copy_integration_pack(
    host: str,
    destination: Path,
    *,
    repo_root: Optional[Path] = None,
    force: bool = False,
) -> Path:
    """Copy one prebuilt host integration pack into a destination directory."""
    if host not in SUPPORTED_CLIS:
        raise ValueError(f"unsupported install host: {host}")

    source = integration_assets_root(repo_root) / host
    target = destination / host
    if target.exists() and not force:
        raise FileExistsError(f"integration target already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=force)
    return target


def build_integration_setup(host: str, host_root: Path) -> Dict[str, Any]:
    """Return setup instructions for one CLI host integration pack."""
    if host == "codex":
        return {
            "host": host,
            "mode": "host-session-review",
            "path": str(host_root),
            "commands": [
                f"codex plugin marketplace add {host_root}",
                "codex plugin add agent-chain-wrapper@agent-chain-local",
            ],
            "notes": [
                "Codex remains the coder. The plugin skill calls `agc review` for external review by default.",
                "`agc p` is only for explicitly delegated coder/reviewer pairs.",
            ],
        }
    if host == "kimi":
        skills_dir = host_root / "skills"
        return {
            "host": host,
            "mode": "host-session-review",
            "path": str(host_root),
            "commands": [
                f'kimi --skills-dir {skills_dir} --prompt "Use agent-chain for this request."',
            ],
            "notes": [
                "Kimi remains the coder. The skill calls `agc review -R codex` by default.",
                "`agc p` is only for explicitly delegated coder/reviewer pairs.",
            ],
        }
    if host == "antigravity":
        return {
            "host": host,
            "mode": "host-session-review",
            "path": str(host_root),
            "commands": [],
            "notes": [
                f"Register skills from: {host_root / 'skills'}",
                f"Register custom commands from: {host_root / 'commands'}",
                "Antigravity remains the coder. The skill/command calls `agc review` by default.",
                "`agc p` is only for explicitly delegated coder/reviewer pairs.",
            ],
        }
    raise ValueError(f"unsupported install host: {host}")
