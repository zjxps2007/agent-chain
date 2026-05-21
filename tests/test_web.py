from __future__ import annotations

from agent_chain.web import RunStore, _build_config


def test_web_builds_default_pair_config() -> None:
    config, label = _build_config({})

    assert label == "generated:codex-kimi"
    assert [step["agent"] for step in config["steps"]] == ["codex_coder", "kimi_reviewer"]


def test_web_run_record_replays_events_to_subscribers() -> None:
    record = RunStore().create()
    record.emit("server_status", {"status": "queued"})

    subscriber, replay = record.subscribe()

    assert replay[0]["type"] == "server_status"

    record.emit("server_status", {"status": "running"})

    assert subscriber.get(timeout=1)["data"]["status"] == "running"
    record.unsubscribe(subscriber)
