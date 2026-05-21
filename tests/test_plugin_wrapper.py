from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _yaml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _load_wrapper_module():
    script = Path("plugins/agent-chain-wrapper/scripts/agent_chain_wrapper.py").resolve()
    spec = importlib.util.spec_from_file_location("agent_chain_wrapper", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_agent_chain_wrapper_runs_from_target_workspace(tmp_path: Path) -> None:
    config = tmp_path / ".agent-chain.yaml"
    python_exe = _yaml_string(sys.executable)
    config.write_text(
        f"""
max_iterations: 1

steps:
  - role: coder
    agent: generic_cli_coder
    output: code
  - role: reviewer
    agent: generic_cli_reviewer
    output: review

agent_configs:
  generic_cli_coder:
    command:
      - {python_exe}
      - "-c"
      - "print('def ok():\\\\n    return 1')"
  generic_cli_reviewer:
    command:
      - {python_exe}
      - "-c"
      - "print('{{\\"status\\":\\"approved\\",\\"message\\":\\"ok\\",\\"suggestions\\":[]}}')"
""".lstrip(),
        encoding="utf-8",
    )

    script = Path("plugins/agent-chain-wrapper/scripts/agent_chain_wrapper.py").resolve()
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "create a tiny function",
            "--workspace",
            str(tmp_path),
            "--config",
            str(config),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr
    assert "def ok()" in result.stdout
    assert "approved" in result.stdout


def test_agent_chain_wrapper_dry_run_resolves_repo_config(tmp_path: Path) -> None:
    script = Path("plugins/agent-chain-wrapper/scripts/agent_chain_wrapper.py").resolve()
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "dry run",
            "--workspace",
            str(tmp_path),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0
    assert "agent_chain" in result.stdout
    assert "config.yaml" in result.stdout


def test_agent_chain_wrapper_generates_cli_pair_config(tmp_path: Path) -> None:
    wrapper = _load_wrapper_module()
    args = wrapper.parse_args(
        [
            "work on this",
            "--workspace",
            str(tmp_path),
            "--coder-cli",
            "kimi",
            "--reviewer-cli",
            "codex",
            "--target-file",
            "src/generated.py",
            "--coder-model",
            "kimi-model",
            "--reviewer-model",
            "codex-model",
        ]
    )

    command, _workspace, _env, cleanup_paths = wrapper.build_command(args)
    try:
        config_path = Path(command[command.index("--config") + 1])
        config = json.loads(config_path.read_text(encoding="utf-8"))
    finally:
        for path in cleanup_paths:
            Path(path).unlink(missing_ok=True)

    assert config["steps"] == [
        {"role": "coder", "agent": "kimi_coder", "output": "code"},
        {"role": "reviewer", "agent": "codex_reviewer", "output": "review"},
    ]
    assert config["agent_configs"]["kimi_coder"]["target_file"] == "src/generated.py"
    assert config["agent_configs"]["kimi_coder"]["model"] == "kimi-model"
    assert config["agent_configs"]["codex_reviewer"]["model"] == "codex-model"


def test_agent_chain_wrapper_profile_selects_config(tmp_path: Path) -> None:
    wrapper = _load_wrapper_module()
    args = wrapper.parse_args(
        [
            "work on this",
            "--workspace",
            str(tmp_path),
            "--profile",
            "antigravity-kimi",
            "--dry-run",
        ]
    )

    command, _workspace, _env, cleanup_paths = wrapper.build_command(args)

    assert not cleanup_paths
    assert command[command.index("--config") + 1].endswith("antigravity-kimi.yaml")
