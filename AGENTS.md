# cf-memory-plugin — Agent Integration Guide

Persistent memory for AI agents, backed by [Cloudflare Agent Memory](https://developers.cloudflare.com/agent-memory/).

You are an agent reading this because you need durable memory across sessions. This plugin gives you that.

## What This Gives You

- `remember` — store a fact (returns immediately, indexed async)
- `recall` — semantic search over all stored facts (~5s)
- `ingest` — extract facts from conversation messages
- `list` — list memories with filtering by type/session
- `export` — dump all memories as JSON/JSONL/Markdown
- `summary` — markdown profile of what's stored

## Install

```bash
pip install git+https://github.com/hansakoch/cf-memory-plugin.git
```

## Credentials

```bash
export MCP_CLOUDFLARE_API_KEY="cf-api-token-with-agent-memory-permission"
export CF_ACCOUNT_ID="your-32-char-account-id"
export CF_MEMORY_NAMESPACE="hermes"    # or your namespace
export CF_MEMORY_PROFILE="alfred"      # or your profile
```

Create token at [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens) with **Agent Memory** permission only.

## Verify

```bash
cf-memory doctor
```

Checks credentials, connectivity, namespace, write/read round-trip, latency.

## Usage Modes

### 1. MCP Server (any agent harness)

```bash
cf-memory serve
```

Exposes 10 tools via stdio MCP:
- `remember(content)` — store a fact
- `recall(query)` — semantic search
- `list_memories(page, per_page, type, session_id)` — list with filtering
- `get_memory(memory_id)` — get one memory with content
- `delete_memory(memory_id)` — delete
- `ingest(messages, session_id)` — extract facts from conversation
- `summary()` — markdown profile
- `list_namespaces()` / `create_namespace(name)` / `delete_namespace(name)`

Slim mode (remember + recall only):
```bash
cf-memory serve --slim
```

### 2. Standalone CLI

```bash
cf-memory remember "User prefers dark mode"
cf-memory recall "what theme does the user prefer"
cf-memory list --type fact --limit 20
cf-memory list --session vultr/alfred/session-123
cf-memory export --format markdown -o memories.md
cf-memory export --format json --type fact -o facts.json
cf-memory export --format jsonl --session vultr/alfred/session-123
cf-memory get <memory-id>
cf-memory delete <memory-id>
cf-memory ingest messages.json --session-id my-session
cf-memory summary
cf-memory doctor
```

### 3. Hermes Native Provider (zero MCP tax)

Add to profile config.yaml:
```yaml
mcp:
  cf-memory:
    url: http://127.0.0.1:9120
    auth:
      type: none
    timeout: 30
    capabilities:
      - remember
      - recall
      - ingest
      - summary
```

Start A2A server:
```bash
cf-memory a2a --port 9120
```

Or install as systemd service:
```bash
# See scripts/ for service files
```

### 4. A2A Agent (OpenClaw, other A2A clients)

```bash
cf-memory a2a --port 9120 --host 0.0.0.0
```

Agent card at `/.well-known/agent.json`. Supports:
- `SendMessage`
- `message/send`
- `tasks/send`

## Harness Configs

### Grok CLI (`~/.grok/config.toml`)

```toml
[mcp_servers.cf-memory]
command = "cf-memory"
args = ["serve"]
enabled = true

[mcp_servers.cf-memory.env]
MCP_CLOUDFLARE_API_KEY = "your-token"
CF_ACCOUNT_ID = "your-account-id"
CF_MEMORY_NAMESPACE = "hermes"
CF_MEMORY_PROFILE = "alfred"
```

### Claude Code

```bash
claude mcp add cf-memory -- cf-memory serve
```

### Cursor (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "cf-memory": {
      "command": "cf-memory",
      "args": ["serve"],
      "env": {
        "MCP_CLOUDFLARE_API_KEY": "your-token",
        "CF_ACCOUNT_ID": "your-account-id",
        "CF_MEMORY_NAMESPACE": "hermes",
        "CF_MEMORY_PROFILE": "alfred"
      }
    }
  }
}
```

### OpenClaw (`~/.openclaw/openclaw.json`)

```json
{
  "mcpServers": {
    "cf-memory": {
      "command": "cf-memory",
      "args": ["serve"],
      "env": {
        "MCP_CLOUDFLARE_API_KEY": "your-token",
        "CF_ACCOUNT_ID": "your-account-id",
        "CF_MEMORY_NAMESPACE": "hermes",
        "CF_MEMORY_PROFILE": "alfred"
      }
    }
  }
}
```

## Auto-Ingest Pattern

Add this to your AGENTS.md or system prompt:

```
Every session MUST proactively store facts to cf-memory using remember().
Do NOT wait for the user to ask.

Always remember:
- User preferences and context
- Credentials and API details discovered during work
- Task outcomes and decisions
- Any information that took more than 2 tool calls to discover

After completing work, audit what you learned and push it to cf-memory.
```

## Bulk Migration

```bash
# Ingest from Hermes sessions
python scripts/ingest_all.py --source hermes --profile alfred

# Ingest from Grok CLI JSONL sessions
python scripts/ingest_all.py --source grok --session-id vultr/session-123

# Dry run first
python scripts/ingest_all.py --source hermes --dry-run
```

## Architecture

```
┌─────────────────────────────────────────────┐
│  Your Agent                                  │
│  (Grok / Hermes / OpenClaw / Claude / etc)  │
└──────────┬──────────────────────────────────┘
           │ MCP (stdio) or A2A (HTTP)
           ▼
┌─────────────────────────────────────────────┐
│  cf-memory-plugin                            │
│  client.py → server.py → a2a_server.py       │
│  provider.py (Hermes native, zero MCP tax)   │
└──────────┬──────────────────────────────────┘
           │ HTTPS
           ▼
┌─────────────────────────────────────────────┐
│  Cloudflare Agent Memory                     │
│  Namespace: hermes  Profile: alfred          │
│  (vector index, semantic recall, storage)    │
└─────────────────────────────────────────────┘
```

## Limits

| Limit | Value |
|-------|-------|
| Namespace name | ≤32 chars |
| Profile name | ≤100 chars |
| Session ID | ≤64 chars |
| Recall query | ≤1KB UTF-8 |
| Content per message | ≤32KB UTF-8 |
| Messages per ingest | ≤500 |
| List page size | ≤1000 |

## Latency

| Operation | Typical |
|-----------|---------|
| remember | 1.3–3.8s |
| recall | ~5s |
| list | ~0.4s |
| get (with content) | ~1.4s |
| ingest (return) | ~2s (write 3–8s later) |

## License

MIT
