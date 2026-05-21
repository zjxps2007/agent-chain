---
name: agent-chain
description: Use the installed agent-chain binary to run paired CLI agents such as Codex, Kimi, and Antigravity in a code-review-revise loop.
---

# AgentChain

Use this skill when the user wants a coder CLI and reviewer CLI to work together.

The `ac` executable must be available on `PATH`. `agent-chain` remains a long-form alias.

## Preferred Commands

Codex as coder, Kimi as reviewer:

```powershell
ac p "USER REQUEST" -C codex -R kimi -t src/generated.py -w .
```

Kimi as coder, Codex as reviewer:

```powershell
ac p "USER REQUEST" -C kimi -R codex -t src/generated.py -w .
```

Antigravity as reviewer:

```powershell
ac p "USER REQUEST" -C codex -R antigravity -t src/generated.py -w .
```

Profiles are available when the user does not need custom options:

```powershell
ac p "USER REQUEST" -P codex-kimi -t src/generated.py -w .
```

Supported profile names:

- `codex-antigravity`
- `codex-kimi`
- `kimi-codex`
- `kimi-antigravity`
- `antigravity-codex`
- `antigravity-kimi`

## Notes

If a CLI executable is not named `codex`, `kimi`, or `antigravity`, pass its path:

```powershell
ac p "USER REQUEST" -C codex -R antigravity --reviewer-command <ANTIGRAVITY_EXE>
```

The reviewer should return JSON with `status`, `message`, and `suggestions`.
