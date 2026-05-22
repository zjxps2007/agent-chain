"""Run AgentChain from a plugin/skill-style wrapper.

The script can be invoked from any workspace. It locates the AgentChain repo
relative to this plugin, adds it to PYTHONPATH, and executes AgentChain with
the requested workspace as the working directory. The default mode is reviewer
only so the host CLI session can do the coding itself.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SUPPORTED_CLIS = ("codex", "kimi", "antigravity")
SUPPORTED_PROFILES = (
    "codex-antigravity",
    "codex-kimi",
    "kimi-codex",
    "kimi-antigravity",
    "antigravity-codex",
    "antigravity-kimi",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_python(repo_root: Path) -> str:
    if os.name == "nt":
        candidate = repo_root / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = repo_root / ".venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def _default_config(workspace: Path, repo_root: Path) -> Path:
    for name in (".agent-chain.yaml", "agent-chain.yaml", "config.yaml"):
        candidate = workspace / name
        if candidate.exists():
            return candidate
    return repo_root / "config.yaml"


def _profile_config(profile: str) -> Path:
    return _plugin_root() / "configs" / f"{profile}.yaml"


def _env_with_repo(repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    current = env.get("PYTHONPATH")
    repo_path = str(repo_root)
    env["PYTHONPATH"] = repo_path if not current else os.pathsep.join([repo_path, current])
    return env


def _agent_name(cli_name: str, role: str) -> str:
    if cli_name not in SUPPORTED_CLIS:
        raise ValueError(f"unsupported CLI: {cli_name}")
    if role not in {"coder", "reviewer"}:
        raise ValueError(f"unsupported role: {role}")
    return f"{cli_name}_{role}"


def _write_generated_config(args: argparse.Namespace) -> Path:
    coder_cli = args.coder_cli or "codex"
    reviewer_cli = args.reviewer_cli or "kimi"
    coder_agent = _agent_name(coder_cli, "coder")
    reviewer_agent = _agent_name(reviewer_cli, "reviewer")

    config: dict[str, object] = {
        "max_iterations": args.max_iterations or 3,
        "steps": [
            {"role": "coder", "agent": coder_agent, "output": "code"},
            {"role": "reviewer", "agent": reviewer_agent, "output": "review"},
        ],
        "agent_configs": {
            coder_agent: {},
            reviewer_agent: {},
        },
    }
    agent_configs = config["agent_configs"]  # type: ignore[index]
    assert isinstance(agent_configs, dict)
    coder_config = agent_configs[coder_agent]
    reviewer_config = agent_configs[reviewer_agent]
    assert isinstance(coder_config, dict)
    assert isinstance(reviewer_config, dict)

    if args.target_file:
        coder_config["target_file"] = args.target_file
        reviewer_config["target_file"] = args.target_file
    if args.coder_model:
        coder_config["model"] = args.coder_model
    if args.reviewer_model:
        reviewer_config["model"] = args.reviewer_model
    if args.coder_command:
        coder_config["cli_command"] = args.coder_command
    if args.reviewer_command:
        reviewer_config["cli_command"] = args.reviewer_command

    handle = tempfile.NamedTemporaryFile(
        "w",
        suffix=".agent-chain.json",
        prefix="agent-chain-",
        delete=False,
        encoding="utf-8",
    )
    with handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")
    return Path(handle.name)


def _select_config(args: argparse.Namespace, workspace: Path, repo_root: Path) -> tuple[Path, list[Path]]:
    if args.config:
        return Path(args.config).resolve(), []

    if args.pair or args.coder_cli or args.reviewer_cli:
        generated = _write_generated_config(args)
        return generated, [generated]

    if args.profile:
        config = _profile_config(args.profile)
        if not config.exists():
            raise FileNotFoundError(f"profile config not found: {config}")
        return config, []

    return _default_config(workspace, repo_root), []


def _uses_review_mode(args: argparse.Namespace) -> bool:
    if args.pair or args.config or args.profile or args.coder_cli:
        return False
    return True


def build_command(args: argparse.Namespace) -> tuple[list[str], Path, dict[str, str], list[Path]]:
    repo_root = _repo_root()
    workspace = Path(args.workspace).resolve()

    if _uses_review_mode(args):
        command = [
            _default_python(repo_root),
            "-m",
            "agent_chain",
            "challenge" if args.challenge else "review",
            args.request,
            "--reviewer-cli",
            args.reviewer_cli or "kimi",
            "--workspace",
            str(workspace),
            "--language",
            args.language,
        ]
        if args.target_file:
            command.extend(["--target-file", args.target_file])
        if args.reviewer_model:
            command.extend(["--reviewer-model", args.reviewer_model])
        if args.reviewer_command:
            command.extend(["--reviewer-command", args.reviewer_command])
        if args.json:
            command.extend(["--json", args.json])
        if args.focus:
            command.extend(["--focus", args.focus])
        if args.background:
            command.append("--background")
        if args.plugins_dir:
            command.extend(["--plugins-dir", str(Path(args.plugins_dir).resolve())])
        return command, workspace, _env_with_repo(repo_root), []

    config, cleanup_paths = _select_config(args, workspace, repo_root)

    command = [
        _default_python(repo_root),
        "-m",
        "agent_chain",
        "run",
        args.request,
        "--config",
        str(config),
        "--workspace",
        str(workspace),
        "--language",
        args.language,
    ]

    if args.max_iterations is not None and not (args.coder_cli or args.reviewer_cli):
        command.extend(["--max-iterations", str(args.max_iterations)])
    if args.output:
        command.extend(["--output", args.output])
    if args.json:
        command.extend(["--json", args.json])
    if args.plugins_dir:
        command.extend(["--plugins-dir", str(Path(args.plugins_dir).resolve())])

    return command, workspace, _env_with_repo(repo_root), cleanup_paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agent-chain-wrapper",
        description="Run AgentChain from a CLI plugin/skill wrapper.",
    )
    parser.add_argument("request", help="User request to pass to AgentChain.")
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="AgentChain YAML config. Defaults to workspace config or repo config.yaml.",
    )
    parser.add_argument(
        "--profile",
        choices=SUPPORTED_PROFILES,
        default=None,
        help="Built-in CLI pair profile to use when --config is omitted. Implies delegated pair mode.",
    )
    parser.add_argument("--pair", action="store_true", help="Run a delegated coder/reviewer pair.")
    parser.add_argument(
        "--coder-cli",
        choices=SUPPORTED_CLIS,
        default=None,
        help="Generate a delegated config using this CLI as coder. Implies pair mode.",
    )
    parser.add_argument(
        "--reviewer-cli",
        choices=SUPPORTED_CLIS,
        default=None,
        help="Use this CLI as reviewer. Defaults to reviewer-only mode unless --pair/--coder-cli is set.",
    )
    parser.add_argument("--target-file", default=None, help="Target file for generated code/review.")
    parser.add_argument("--coder-model", default=None, help="Model name for the coder CLI, when supported.")
    parser.add_argument("--reviewer-model", default=None, help="Model name for the reviewer CLI, when supported.")
    parser.add_argument("--coder-command", default=None, help="Executable path/name for the coder CLI.")
    parser.add_argument("--reviewer-command", default=None, help="Executable path/name for the reviewer CLI.")
    parser.add_argument("--challenge", action="store_true", help="Use adversarial challenge review mode.")
    parser.add_argument("--focus", default=None, help="Extra review focus for challenge/review mode.")
    parser.add_argument("--background", action="store_true", help="Run review mode as a background job.")
    parser.add_argument(
        "--workspace",
        default=".",
        help="Target workspace for file operations. Defaults to current directory.",
    )
    parser.add_argument(
        "-l",
        "--language",
        default="python",
        help="Target language metadata passed to AgentChain.",
    )
    parser.add_argument(
        "-m",
        "--max-iterations",
        type=int,
        default=None,
        help="Override max_iterations in the config.",
    )
    parser.add_argument("-o", "--output", default=None, help="Write final code to this path.")
    parser.add_argument("--json", default=None, metavar="PATH", help="Write final result JSON.")
    parser.add_argument("--plugins-dir", default=None, help="Additional AgentChain Python plugin directory.")
    parser.add_argument("--dry-run", action="store_true", help="Print the resolved command without running it.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    command, workspace, env, cleanup_paths = build_command(args)

    try:
        if args.dry_run:
            print("cwd:", workspace)
            print("command:", subprocess.list2cmdline(command))
            return 0

        workspace.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(command, cwd=workspace, env=env)
        return completed.returncode
    finally:
        for path in cleanup_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
