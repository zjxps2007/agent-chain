# AgentChain Command

Use this command definition if Antigravity supports custom Markdown commands.

Run AgentChain with the current request:

```powershell
agent-chain run "$ARGUMENTS" --coder-cli codex --reviewer-cli antigravity --target-file src/generated.py --workspace .
```

Alternative pairs:

```powershell
agent-chain run "$ARGUMENTS" --coder-cli antigravity --reviewer-cli kimi --target-file src/generated.py --workspace .
agent-chain run "$ARGUMENTS" --coder-cli kimi --reviewer-cli antigravity --target-file src/generated.py --workspace .
```

The `agent-chain` executable must be on `PATH`.
