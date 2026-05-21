---
name: agent-chain
description: Use the installed agent-chain binary to run Codex, Kimi, and Antigravity CLI agents as coder/reviewer pairs.
---

# AgentChain

Use this skill when the user wants AgentChain to coordinate CLI agents.

The `ac` executable must be available on `PATH`. `agent-chain` remains a long-form alias.

## Commands

Antigravity as coder, Kimi as reviewer:

```powershell
ac p "USER REQUEST" -C antigravity -R kimi -t src/generated.py -w .
```

Codex as coder, Antigravity as reviewer:

```powershell
ac p "USER REQUEST" -C codex -R antigravity -t src/generated.py -w .
```

Kimi as coder, Antigravity as reviewer:

```powershell
ac p "USER REQUEST" -C kimi -R antigravity -t src/generated.py -w .
```

If the Antigravity executable has a different name or path:

```powershell
ac p "USER REQUEST" -C codex -R antigravity --reviewer-command <ANTIGRAVITY_EXE> -t src/generated.py
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
