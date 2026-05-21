---
name: agent-chain
description: Use the installed agent-chain binary to orchestrate Codex, Kimi, and Antigravity CLI agents in a code-review-revise loop.
---

# AgentChain

Use this skill when the user wants two CLI agents to alternate:

1. coder CLI implements or edits code.
2. reviewer CLI reviews and returns feedback.
3. AgentChain repeats until the review is approved or max iterations are reached.

The `agc` executable must be available on `PATH`. `agent-chain` remains a long-form alias.

## Host-Session Review

When the current CLI session has already edited files, call only the reviewer:

```powershell
agc review "USER REQUEST" -R codex -t src/generated.py -w . --json .agent-chain-review.json
```

Read `.agent-chain-review.json`; apply `changes_requested` feedback and repeat until `approved`.

## Commands

Kimi as coder, Codex as reviewer:

```powershell
agc p "USER REQUEST" -C kimi -R codex -t src/generated.py -w .
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
