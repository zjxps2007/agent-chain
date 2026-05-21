# AgentChain Kimi Integration

This directory is a prebuilt Kimi skills pack.

Usage:

```powershell
kimi --skills-dir <AGENT_CHAIN_ROOT>\integrations\kimi\skills --prompt "Use agent-chain for this request."
```

The `ac` executable must be on `PATH`. `agent-chain` remains available as the long-form command.

Direct run:

```powershell
ac p "USER REQUEST" -C kimi -R codex -t src/generated.py -w .
```
