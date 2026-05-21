---
name: agent-chain
description: Use the installed agent-chain binary to orchestrate Codex, Kimi, and Antigravity CLI agents in a code-review-revise loop.
---

# AgentChain

Use this skill when the user wants two CLI agents to alternate:

1. coder CLI implements or edits code.
2. reviewer CLI reviews and returns feedback.
3. AgentChain repeats until the review is approved or max iterations are reached.

The `ac` executable must be available on `PATH`. `agent-chain` remains a long-form alias.

## Commands

Kimi as coder, Codex as reviewer:

```powershell
ac p "USER REQUEST" -C kimi -R codex -t src/generated.py -w .
```

Codex as coder, Kimi as reviewer:

```powershell
ac p "USER REQUEST" -C codex -R kimi -t src/generated.py -w .
```

Antigravity as reviewer:

```powershell
ac p "USER REQUEST" -C kimi -R antigravity -t src/generated.py -w .
```

## Profiles

```powershell
ac p "USER REQUEST" -P kimi-codex -t src/generated.py -w .
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
