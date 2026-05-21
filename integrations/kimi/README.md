# AgentChain Kimi Integration

This directory is a prebuilt Kimi skills pack.

Usage:

```powershell
kimi --skills-dir <AGENT_CHAIN_ROOT>\integrations\kimi\skills --prompt "Use agent-chain for this request."
```

The `agc` executable must be on `PATH`. `agent-chain` remains available as the long-form command.

Direct run:

```powershell
agc review "USER REQUEST" -R codex -t src/generated.py -w . --json .agent-chain-review.json
```

Use `agc p "USER REQUEST" -C kimi -R codex ...` only when AgentChain should spawn both the Kimi coder and the reviewer.
