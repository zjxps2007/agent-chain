from __future__ import annotations

import json
from pathlib import Path

import yaml

from agent_chain.integrations import (
    build_cli_pair_config,
    build_cli_review_config,
    build_integration_setup,
    copy_integration_pack,
)


def test_build_cli_pair_config_from_profile() -> None:
    config = build_cli_pair_config(
        profile="kimi-codex",
        target_file="src/generated.py",
        coder_model="kimi-model",
        reviewer_model="codex-model",
    )

    assert config["steps"] == [
        {"role": "coder", "agent": "kimi_coder", "output": "code"},
        {"role": "reviewer", "agent": "codex_reviewer", "output": "review"},
    ]
    assert config["agent_configs"]["kimi_coder"] == {
        "target_file": "src/generated.py",
        "model": "kimi-model",
    }
    assert config["agent_configs"]["codex_reviewer"] == {
        "target_file": "src/generated.py",
        "model": "codex-model",
    }


def test_build_cli_review_config_defaults_to_kimi_reviewer() -> None:
    config = build_cli_review_config(
        target_file="src/generated.py",
        reviewer_model="kimi-review",
    )

    assert config["max_iterations"] == 1
    assert config["steps"] == [
        {
            "role": "reviewer",
            "agent": "kimi_reviewer",
            "output": "review",
            "retry_on": [],
        }
    ]
    assert config["agent_configs"]["kimi_reviewer"] == {
        "target_file": "src/generated.py",
        "model": "kimi-review",
    }


def test_build_cli_review_config_can_set_challenge_mode() -> None:
    config = build_cli_review_config(
        reviewer_cli="codex",
        target_file="src/generated.py",
        review_mode="challenge",
        review_focus="race conditions",
    )

    assert config["steps"][0]["agent"] == "codex_reviewer"
    assert config["agent_configs"]["codex_reviewer"]["review_mode"] == "challenge"
    assert config["agent_configs"]["codex_reviewer"]["review_focus"] == "race conditions"


def test_prebuilt_codex_marketplace_points_to_plugin() -> None:
    marketplace_path = Path("integrations/codex/.agents/plugins/marketplace.json")
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

    plugin_entry = marketplace["plugins"][0]

    assert marketplace["name"] == "agent-chain-local"
    assert plugin_entry["name"] == "agent-chain-wrapper"
    assert plugin_entry["source"]["path"] == "./plugins/agent-chain-wrapper"
    assert (Path("integrations/codex") / plugin_entry["source"]["path"]).resolve().exists()


def test_prebuilt_common_configs_are_valid_profiles() -> None:
    expected = {
        "codex-antigravity": ("codex_coder", "antigravity_reviewer"),
        "codex-kimi": ("codex_coder", "kimi_reviewer"),
        "kimi-codex": ("kimi_coder", "codex_reviewer"),
        "kimi-antigravity": ("kimi_coder", "antigravity_reviewer"),
        "antigravity-codex": ("antigravity_coder", "codex_reviewer"),
        "antigravity-kimi": ("antigravity_coder", "kimi_reviewer"),
    }

    for profile, agents in expected.items():
        config_path = Path("integrations/common/configs") / f"{profile}.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert [step["agent"] for step in config["steps"]] == list(agents)
        assert set(config["agent_configs"]) == set(agents)


def test_prebuilt_skill_files_call_agent_chain_binary() -> None:
    skill_paths = [
        Path("integrations/codex/plugins/agent-chain-wrapper/skills/agent-chain/SKILL.md"),
        Path("integrations/kimi/skills/agent-chain/SKILL.md"),
        Path("integrations/antigravity/skills/agent-chain/SKILL.md"),
    ]

    for path in skill_paths:
        text = path.read_text(encoding="utf-8")
        assert "agc review" in text
        assert "agc p" in text
        assert "uv run python" not in text


def test_integration_setup_defaults_to_host_session_review() -> None:
    setup = build_integration_setup("codex", Path("integrations/codex").resolve())

    assert setup["mode"] == "host-session-review"
    assert setup["commands"] == [
        f"codex plugin marketplace add {Path('integrations/codex').resolve()}",
        "codex plugin add agent-chain-wrapper@agent-chain-local",
    ]
    assert any("agc review" in note for note in setup["notes"])


def test_copy_integration_pack_copies_skill_files(tmp_path: Path) -> None:
    copied = copy_integration_pack("kimi", tmp_path)

    assert copied == tmp_path / "kimi"
    skill = copied / "skills" / "agent-chain" / "SKILL.md"
    assert skill.exists()
    assert "agc review" in skill.read_text(encoding="utf-8")
