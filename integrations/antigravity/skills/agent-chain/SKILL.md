---
name: agent-chain
description: Use the installed agent-chain binary to review code produced by the current Antigravity session, or explicitly run delegated Codex/Kimi/Antigravity pairs.
---

# AgentChain

Use this skill when the current Antigravity session should implement code and an external reviewer CLI should review it.

The `agc` executable must be available on `PATH`. `agent-chain` remains a long-form alias.

## Preferred Host-Session Review

When running inside Antigravity, do not spawn another Antigravity coder by default. First edit the files yourself, then call only the reviewer:

```powershell
agc review "USER REQUEST" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
```

Read `.agent-chain-review.json`; apply `changes_requested` feedback and repeat until `approved`.

Use challenge mode for adversarial design or risk review:

```powershell
agc challenge "USER REQUEST" -R kimi -t src/generated.py -w . --focus "security and rollback risk"
```

For long reviews, use background job commands:

```powershell
agc review "USER REQUEST" -R kimi -t src/generated.py -w . --background
agc status
agc result <job-id>
agc cancel <job-id>
```

## Delegated Pair Commands

Use these only when the user explicitly asks AgentChain to spawn both CLIs.

Antigravity as coder, Kimi as reviewer:

```powershell
agc delegate "USER REQUEST" -C antigravity -R kimi -t src/generated.py -w .
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
