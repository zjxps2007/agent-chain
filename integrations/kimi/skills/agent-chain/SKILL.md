---
name: agent-chain
description: Use the installed agent-chain binary to review code produced by the current Kimi session, or explicitly run delegated Codex/Kimi/Antigravity pairs.
---

# AgentChain

Use this skill when the current Kimi session should implement code and an external reviewer CLI should review it.

The `agc` executable must be available on `PATH`. `agent-chain` remains a long-form alias.

## Preferred Host-Session Review

When running inside Kimi, do not spawn another Kimi coder by default. First edit the files yourself, then call only the reviewer:

```powershell
agc review "USER REQUEST" -R codex -t src/generated.py -w . --json .agent-chain-review.json
```

Read `.agent-chain-review.json`; apply `changes_requested` feedback and repeat until `approved`.

Use challenge mode for adversarial design or risk review:

```powershell
agc challenge "USER REQUEST" -R codex -t src/generated.py -w . --focus "security and race conditions"
```

For long reviews, use background job commands:

```powershell
agc review "USER REQUEST" -R codex -t src/generated.py -w . --background
agc status
agc result <job-id>
agc cancel <job-id>
```

## Delegated Pair Commands

Use these only when the user explicitly asks AgentChain to spawn both CLIs.

Kimi as coder, Codex as reviewer:

```powershell
agc delegate "USER REQUEST" -C kimi -R codex -t src/generated.py -w .
```

Codex as coder, Kimi as reviewer:

```powershell
agc p "USER REQUEST" -C codex -R kimi -t src/generated.py -w .
```

Antigravity as reviewer:

```powershell
agc p "USER REQUEST" -C kimi -R antigravity -t src/generated.py -w .
```

## Profiles

```powershell
agc p "USER REQUEST" -P kimi-codex -t src/generated.py -w .
```

Supported profiles:

- `codex-antigravity`
- `codex-kimi`
- `kimi-codex`
- `kimi-antigravity`
- `antigravity-codex`
- `antigravity-kimi`

## Host Setup

Launch Kimi with this directory:

```powershell
kimi --skills-dir <AGENT_CHAIN_ROOT>\integrations\kimi\skills --prompt "Use agent-chain for this request."
```
