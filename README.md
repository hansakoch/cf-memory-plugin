# cloudflare-memory

Cloudflare Agent Memory client, MCP server, and Hermes memory provider plugin.

Standalone MIT Python package — no Cloudflare Worker needed. Calls the [Agent Memory HTTP API](https://developers.cloudflare.com/agent-memory/api/http-api/) directly from any Python environment.

## Features

- **HTTP client** — async client for all CF Agent Memory endpoints (remember, recall, list, get, delete, ingest, summary, namespace management)
- **MCP server** — `cloudflare-memory serve` exposes 10 tools via Model Context Protocol
- **Hermes provider** — plug-in memory provider for [Hermes Agent](https://hermes-agent.nousresearch.com) with background prefetch, non-blocking sync, and TTL cache
- **CLI** — `cloudflare-memory test` for connectivity checks, `hermes cloudflare-memory` for management

## Install

```bash
pip install git+https://github.com/hansakoch/cloudflare-memory.git
```

Or editable:

```bash
git clone https://github.com/hansakoch/cloudflare-memory.git
cd cloudflare-memory
pip install -e .
```

## Quick start

```bash
# Set credentials
export MCP_CLOUDFLARE_API_KEY="your-cf-api-token"
export CF_ACCOUNT_ID="your-account-id"

# Test connectivity
cloudflare-memory test

# Start MCP server
cloudflare-memory serve --namespace hermes --profile default
```

## Hermes Agent integration

The package auto-registers as a Hermes memory provider via pip entry point.

```bash
# Activate
hermes config set memory.provider cloudflare-memory

# Verify
hermes memory status

# Management commands
hermes cloudflare-memory status
hermes cloudflare-memory test
hermes cloudflare-memory namespaces
hermes cloudflare-memory create-ns my-namespace
hermes cloudflare-memory delete-ns my-namespace
```

### Configuration

Via `hermes memory setup` (interactive), or manually:

**~/.hermes/.env** (secrets):
```bash
MCP_CLOUDFLARE_API_KEY=your-cf-api-token
CF_ACCOUNT_ID=your-account-id
```

**~/.hermes/cloudflare-memory.json** (optional):
```json
{
  "namespace": "hermes",
  "profile": "default"
}
```

### Performance design

The provider is designed to never add latency to Hermes turns:

| Operation | Latency | How provider handles it |
|-----------|---------|------------------------|
| `prefetch()` | **0ms** | Returns cached result; fires background recall on cache miss |
| `queue_prefetch()` | **0ms** | Warms cache for next turn (daemon thread) |
| `sync_turn()` | **0ms** | Daemon thread → `ingest()` (writes appear 3–8s later) |
| `cf_remember` tool | 1.3–3.8s | User-initiated, blocking OK |
| `cf_recall` tool | ~5s | User-initiated, blocking OK |
| `cf_list` tool | ~0.4s | User-initiated |
| `cf_summary` tool | ~0.8s | User-initiated |

### Tools exposed to the agent

| Tool | Description |
|------|-------------|
| `cf_remember` | Store a single memory (returns type + summary) |
| `cf_recall` | Semantic search (returns synthesized answer + candidates) |
| `cf_list` | List memories (omits content) |
| `cf_get` | Get one memory by ID (includes content) |
| `cf_summary` | Markdown profile summary |
| `cf_delete` | Delete a memory by ID |

### Hooks

| Hook | Behavior |
|------|----------|
| `on_session_end` | Ingests full session for fact extraction |
| `system_prompt_block` | Injects provider status into system prompt |

## MCP Server

Exposes 10 tools via stdio or SSE transport:

```bash
# stdio (default)
cloudflare-memory serve

# SSE
cloudflare-memory serve --transport sse
```

Tools: `remember`, `recall`, `list_memories`, `get_memory`, `delete_memory`, `ingest`, `summary`, `list_namespaces`, `create_namespace`, `delete_namespace`

### MCP config for other clients

```json
{
  "mcpServers": {
    "cloudflare-memory": {
      "command": "cloudflare-memory",
      "args": ["serve"],
      "env": {
        "MCP_CLOUDFLARE_API_KEY": "your-token",
        "CF_ACCOUNT_ID": "your-account-id"
      }
    }
  }
}
```

## HTTP Client API

```python
import asyncio
from cloudflare_memory import CloudflareMemoryClient

async def main():
    async with CloudflareMemoryClient(
        account_id="your-account-id",
        api_token="your-token",
        namespace="my-app",
        profile="user-123",
    ) as client:
        # Store a memory
        entry = await client.remember("User prefers dark mode.")
        print(f"[{entry.type}] {entry.summary}")

        # Semantic recall
        result = await client.recall("What UI preferences?")
        print(f"Answer: {result.answer}")

        # List (no content)
        entries = await client.list_memories()

        # Get (with content)
        full = await client.get_memory(entry.id)

        # Ingest conversation (async, writes 3-8s later)
        await client.ingest([
            {"role": "user", "content": "I prefer concise answers."},
            {"role": "assistant", "content": "Noted!"},
        ])

        # Summary
        summary = await client.get_summary()

asyncio.run(main())
```

## API reference

Based on [Cloudflare Agent Memory HTTP API](https://developers.cloudflare.com/agent-memory/api/http-api/).

### Verified behavior (2026-08-23)

| Fact | Source |
|------|--------|
| `remember` returns `type` + `summary` assigned server-side | Live test |
| `list` omits `content`; `get` includes it | Live test + docs |
| `ingest` returns `result: null`, writes appear 3–8s later | Live test |
| `POST /summary` works; `GET /summary` returns 404 | Live test |
| Paid Workers ≠ beta access (separate entitlement) | Live test |
| `remember` latency: 1.3–3.8s | Live test |
| `recall` latency: ~5s | Live test |

### Limits (official)

| Feature | Limit |
|---------|-------|
| Messages per ingest() | 500 |
| Message content | 32 KB UTF-8 |
| Recall query | 1 KB UTF-8 |
| Session ID | 64 chars |
| Profile name | 100 chars |
| Namespace name | 32 chars |
| List page size | 1–1000 (default 20) |

## Development

```bash
git clone https://github.com/hansakoch/cloudflare-memory.git
cd cloudflare-memory
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT
