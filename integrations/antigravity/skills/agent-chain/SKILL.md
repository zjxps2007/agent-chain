---
name: agent-chain
description: Use the installed agent-chain binary to run Codex, Kimi, and Antigravity CLI agents as coder/reviewer pairs.
---

# AgentChain

Use this skill when the user wants AgentChain to coordinate CLI agents.

The `agent-chain` executable must be available on `PATH`.

## Commands

Antigravity as coder, Kimi as reviewer:

```powershell
agent-chain run "USER REQUEST" --coder-cli antigravity --reviewer-cli kimi --target-file src/generated.py --workspace .
```

Codex as coder, Antigravity as reviewer:

```powershell
agent-chain run "USER REQUEST" --coder-cli codex --reviewer-cli antigravity --target-file src/generated.py --workspace .
```

Kimi as coder, Antigravity as reviewer:

```powershell
agent-chain run "USER REQUEST" --coder-cli kimi --reviewer-cli antigravity --target-file src/generated.py --workspace .
```

If the Antigravity executable has a different name or path:

```powershell
agent-chain run "USER REQUEST" --coder-cli codex --reviewer-cli antigravity --reviewer-command C:\Tools\antigravity.exe --target-file src/generated.py
```

## Review Contract

Reviewer CLIs should print JSON:

```json
{"status":"approved","message":"ok","suggestions":[]}
```

or:

```json
{"status":"changes_requested","message":"fix this","suggestions":["specific change"]}
```
