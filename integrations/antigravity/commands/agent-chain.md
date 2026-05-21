# AgentChain Command

Use this command definition if Antigravity supports custom Markdown commands.

Run AgentChain with the current request:

```powershell
agc p "$ARGUMENTS" -C codex -R antigravity -t src/generated.py -w .
```

Alternative pairs:

```powershell
agc p "$ARGUMENTS" -C antigravity -R kimi -t src/generated.py -w .
agc p "$ARGUMENTS" -C kimi -R antigravity -t src/generated.py -w .
```

The `agc` executable must be on `PATH`. `agent-chain` remains a long-form alias.
