# AgentChain Kimi Integration

This directory is a prebuilt Kimi Code CLI plugin.

Kimi Code CLI uses `kimi plugin install` for persistent plugin registration:

```powershell
kimi plugin install <AGENT_CHAIN_ROOT>\integrations\kimi
```

The plugin bundles a root `SKILL.md`. The legacy `skills/agent-chain/SKILL.md`
copy remains for one-session `--skills-dir` workflows.

The `agc` executable must be on `PATH`. `agent-chain` remains available as the long-form command.

Direct run:

```powershell
agc review "USER REQUEST" -R codex -t src/generated.py -w . --json .agent-chain-review.json
```

Use `agc p "USER REQUEST" -C kimi -R codex ...` only when AgentChain should spawn both the Kimi coder and the reviewer.
