from __future__ import annotations

from pathlib import Path

from agent_chain.cli import _load_run_config, build_parser


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
