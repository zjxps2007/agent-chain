# AgentChain Antigravity Integration

This directory contains prebuilt skill and command files for Antigravity-style
integrations.

Because Antigravity CLI was not available in the development environment, this
pack is intentionally file-based:

- `skills/agent-chain/SKILL.md`
- `commands/agent-chain.md`

Copy or register these files according to the Antigravity CLI's custom skill or
command mechanism. The `agc` executable must be on `PATH`.
`agent-chain` remains available as the long-form command.

Direct run:

```powershell
agc p "USER REQUEST" -C codex -R antigravity -t src/generated.py -w .
```
