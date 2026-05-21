---
name: agent-chain
description: Use the installed agent-chain binary to run Codex, Kimi, and Antigravity CLI agents as coder/reviewer pairs.
---

# AgentChain

Use this skill when the user wants AgentChain to coordinate CLI agents.

The `agc` executable must be available on `PATH`. `agent-chain` remains a long-form alias.

## Host-Session Review

When the current CLI session has already edited files, call only the reviewer:

```powershell
agc review "USER REQUEST" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
```

Read `.agent-chain-review.json`; apply `changes_requested` feedback and repeat until `approved`.

## Commands

Antigravity as coder, Kimi as reviewer:

```powershell
agc p "USER REQUEST" -C antigravity -R kimi -t src/generated.py -w .
```

Codex as coder, Antigravity as reviewer:

```powershell
agc p "USER REQUEST" -C codex -R antigravity -t src/generated.py -w .
```

Kimi as coder, Antigravity as reviewer:

```powershell
agc p "USER REQUEST" -C kimi -R antigravity -t src/generated.py -w .
```

If the Antigravity executable has a different name or path:

```powershell
agc p "USER REQUEST" -C codex -R antigravity --reviewer-command <ANTIGRAVITY_EXE> -t src/generated.py
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
