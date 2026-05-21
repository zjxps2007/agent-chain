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
agc review "USER REQUEST" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
```

Use `agc p "USER REQUEST" -C antigravity -R kimi ...` only when AgentChain should spawn both the Antigravity coder and the reviewer.
