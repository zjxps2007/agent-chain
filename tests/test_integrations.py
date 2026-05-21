from __future__ import annotations

import json
from pathlib import Path

import yaml

from agent_chain.integrations import build_cli_pair_config


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
        assert "ac p" in text
        assert "uv run python" not in text
