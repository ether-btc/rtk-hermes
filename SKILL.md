# RTK Hermes Plugin

## Skill Identity

**Name:** rtk-hermes  
**Type:** Hermes Agent Plugin  
**Language:** Python 3.9+  
**License:** MIT  

## What It Does

A transparent **RTK token optimization plugin** for Hermes that intercepts shell commands via the `terminal` tool and rewrites them to RTK equivalents, achieving **60–90% LLM token savings** on command output.

## Core Mechanism

```
Agent runs: terminal(command="cargo test --nocapture")
  → Plugin intercepts pre_tool_call hook
  → Calls rtk rewrite "cargo test --nocapture"
  → Mutates args["command"] = "rtk cargo test --nocapture"
  → Agent executes the rewritten command
  → Filtered output reaches LLM (~90% fewer tokens)
```

## Key Features

- **Zero-config integration** — auto-registers when RTK is in `$PATH`
- **Graceful degradation** — never blocks execution; passes commands through unchanged if RTK is unavailable
- **30+ commands supported** — git, grep, find, ls, cargo, pytest, npm, docker, kubectl, and more
- **Automatic updates** — all rewrite logic lives in RTK; new filters picked up without plugin changes

## Measured Token Savings

| Command | Savings |
|---------|---------|
| `cargo test` | 90–99% |
| `git log --stat` | 87% |
| `ls -la` | 78% |
| `git status` | 66% |
| `grep` (single file) | 52% |

## Installation

```bash
# Install RTK
brew install rtk
# or: curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh

# Install the plugin
pip install rtk-hermes

# Restart Hermes — plugin auto-registers
```

## Configuration

```yaml
# ~/.hermes/config.yaml
plugins:
  disabled:
    - rtk-rewrite
```

## Requirements

- Python 3.9+
- RTK binary in `$PATH`
- Hermes Agent

## Links

- **Plugin Repo:** https://github.com/ether-btc/rtk-hermes
- **RTK Repo:** https://github.com/rtk-ai/rtk
- **Hermes Repo:** https://github.com/NousResearch/hermes-agent
