from __future__ import annotations

import subprocess
from pathlib import Path

from agent_chain import cli as cli_module
from agent_chain.cli import _apply_setups, _load_run_config, build_parser
from agent_chain.integrations import build_integration_setup


def test_short_agc_entrypoint_is_registered() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'agent-chain = "agent_chain.cli:main"' in text
    assert 'agc = "agent_chain.cli:main"' in text


def test_pair_alias_defaults_to_codex_kimi_config() -> None:
    parser = build_parser(prog="agc")
    args = parser.parse_args(["p", "implement a parser"])

    assert args.command == "p"
    assert args.coder_cli == "codex"
    assert args.reviewer_cli == "kimi"
    assert args.max_iterations == 3

    config, label = _load_run_config(args)

    assert label == "generated:codex-kimi"
    assert config["max_iterations"] == 3
    assert [step["agent"] for step in config["steps"]] == ["codex_coder", "kimi_reviewer"]


def test_delegate_alias_defaults_to_codex_kimi_config() -> None:
    parser = build_parser(prog="agc")
    args = parser.parse_args(["delegate", "implement a parser"])

    assert args.command == "delegate"
    assert args.coder_cli == "codex"
    assert args.reviewer_cli == "kimi"


def test_run_alias_accepts_short_cli_options() -> None:
    parser = build_parser(prog="agc")
    args = parser.parse_args(
        [
            "r",
            "implement a parser",
            "-P",
            "kimi-codex",
            "-t",
            "src/generated.py",
            "-w",
            "work",
            "-m",
            "2",
        ]
    )

    assert args.command == "r"
    assert args.profile == "kimi-codex"
    assert args.target_file == "src/generated.py"
    assert args.workspace == "work"
    assert args.max_iterations == 2

    config, label = _load_run_config(args)

    assert label == "generated:kimi-codex"
    assert config["max_iterations"] == 2
    assert config["agent_configs"]["kimi_coder"]["target_file"] == "src/generated.py"


def test_init_alias_parses() -> None:
    parser = build_parser(prog="agc")
    args = parser.parse_args(["i", "--path", "demo"])

    assert args.command == "i"
    assert args.path == "demo"


def test_ui_alias_parses() -> None:
    parser = build_parser(prog="agc")
    args = parser.parse_args(["ui", "--host", "0.0.0.0", "--port", "9000"])

    assert args.command == "ui"
    assert args.host == "0.0.0.0"
    assert args.port == 9000


def test_install_alias_parses_for_cli_hosts() -> None:
    parser = build_parser(prog="agc")
    args = parser.parse_args(["install", "codex", "--copy-to", "dist", "--force", "--apply", "--json"])

    assert args.command == "install"
    assert args.target == "codex"
    assert args.copy_to == "dist"
    assert args.force is True
    assert args.apply is True
    assert args.json is True


def test_apply_setups_runs_codex_commands(monkeypatch, tmp_path: Path) -> None:
    setup = build_integration_setup("codex", tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(cli_module.shutil, "which", lambda executable: f"/bin/{executable}")
    monkeypatch.setattr(cli_module, "_run_setup_command", fake_run)

    results, exit_code = _apply_setups([setup])

    assert exit_code == 0
    assert calls == setup["apply_commands"]
    assert [result["status"] for result in results] == ["applied", "applied"]


def test_apply_setups_skips_hosts_without_persistent_setup() -> None:
    setup = {
        "host": "custom",
        "commands": ["custom setup"],
        "apply_commands": [],
    }

    results, exit_code = _apply_setups([setup])

    assert exit_code == 0
    assert results[0]["host"] == "custom"
    assert results[0]["status"] == "skipped"
    assert "manual_commands" in results[0]


def test_apply_setups_reports_missing_executable(monkeypatch, tmp_path: Path) -> None:
    setup = build_integration_setup("codex", tmp_path)
    monkeypatch.setattr(cli_module.shutil, "which", lambda executable: None)

    results, exit_code = _apply_setups([setup])

    assert exit_code == 1
    assert results[0]["status"] == "failed"
    assert results[0]["returncode"] == 127
    assert "Executable not found" in results[0]["stderr"]


def test_review_alias_parses_for_host_session_flow() -> None:
    parser = build_parser(prog="agc")
    args = parser.parse_args(
        [
            "review",
            "implement a parser",
            "-R",
            "kimi",
            "-t",
            "src/generated.py",
            "-w",
            "work",
            "--json",
            ".agent-chain-review.json",
            "--fail-on-changes",
        ]
    )

    assert args.command == "review"
    assert args.request == "implement a parser"
    assert args.reviewer_cli == "kimi"
    assert args.target_file == "src/generated.py"
    assert args.workspace == "work"
    assert args.json == ".agent-chain-review.json"
    assert args.fail_on_changes is True


def test_challenge_alias_parses_review_options() -> None:
    parser = build_parser(prog="agc")
    args = parser.parse_args(
        [
            "challenge",
            "implement a parser",
            "-R",
            "codex",
            "-t",
            "src/generated.py",
            "--focus",
            "race conditions",
            "--background",
            "--jobs-dir",
            ".jobs",
        ]
    )

    assert args.command == "challenge"
    assert args.reviewer_cli == "codex"
    assert args.focus == "race conditions"
    assert args.background is True
    assert args.jobs_dir == ".jobs"


def test_job_commands_parse() -> None:
    parser = build_parser(prog="agc")

    status = parser.parse_args(["status", "job123", "--jobs-dir", ".jobs"])
    result = parser.parse_args(["result", "job123", "--json"])
    cancel = parser.parse_args(["cancel", "job123"])

    assert status.command == "status"
    assert status.job_id == "job123"
    assert result.command == "result"
    assert result.json is True
    assert cancel.command == "cancel"
