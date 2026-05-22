# AgentChain Antigravity Integration

This directory contains an Antigravity CLI plugin for AgentChain.

Antigravity CLI uses the `agy` executable. Verify it first:

```powershell
agy --version
```

Install the plugin:

```powershell
agy plugin validate <AGENT_CHAIN_ROOT>\integrations\antigravity
agy plugin install <AGENT_CHAIN_ROOT>\integrations\antigravity
```

The plugin contains:

- `skills/agent-chain/SKILL.md`
- `commands/agent-chain.md`
- `plugin.json`

The `agc` executable must be on `PATH`. `agent-chain` remains available as the long-form command.

Direct run:

```powershell
agc review "USER REQUEST" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
```

Use `agc p "USER REQUEST" -C antigravity -R kimi ...` only when AgentChain should spawn both the Antigravity coder and the reviewer.
