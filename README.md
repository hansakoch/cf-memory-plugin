# CF Memory Plugin

**Cloudflare Agent Memory for every AI coding agent and LLM framework.**

Gives your agent persistent, cross-session memory powered by [Cloudflare Agent Memory](https://developers.cloudflare.com/agent-memory/) — a managed service that handles recall, fact extraction, and profile summaries. No vector DB to run, no embeddings to manage, no Worker to deploy.

## Who this is for

- **AI coding agents** (Claude Code, Codex, Cursor, Hermes, OpenClaw, TRAE, OpenCode, pi) that need to remember context across sessions
- **LLM frameworks** (LangChain, LangGraph) building agents with persistent memory
- **MCP clients** (any tool supporting Model Context Protocol)
- **Agent-to-agent systems** using the A2A protocol
- **Anyone** who wants a simple, hosted memory backend for their AI agent

## What it does

| Capability | Description |
|------------|-------------|
| **Remember** | Store facts, instructions, events — CF classifies them automatically |
| **Recall** | Semantic search with synthesized answers (not just raw matches) |
| **Ingest** | Feed conversation turns — CF extracts facts/events/instructions/tasks |
| **Summary** | Markdown profile of everything stored, auto-generated |
| **Namespaces** | Isolate memory per app, user, or environment |

## Quick start (any agent)

```bash
pip install git+https://github.com/hansakoch/cloudflare-memory.git

# Set credentials
export MCP_CLOUDFLARE_API_KEY="your-cf-api-token"
export CF_ACCOUNT_ID="your-account-id"

# Test it works
cf-memory test
```

---

## Agent integrations

### MCP clients (universal)

Works with any MCP-compatible client: Claude Desktop, Cursor, Windsurf, Continue, Zed, and more.

```json
{
  "mcpServers": {
    "cf-memory": {
      "command": "cf-memory",
      "args": ["serve"],
      "env": {
        "MCP_CLOUDFLARE_API_KEY": "your-token",
        "CF_ACCOUNT_ID": "your-account-id"
      }
    }
  }
}
```

**Tools exposed:** `remember`, `recall`, `list_memories`, `get_memory`, `delete_memory`, `ingest`, `summary`, `list_namespaces`, `create_namespace`, `delete_namespace`

### Hermes

Auto-discovered via pip entry point. No files to copy.

```bash
# Install
pip install git+https://github.com/hansakoch/cloudflare-memory.git

# Activate
hermes config set memory.provider cloudflare-memory

# Verify
hermes memory status

# Management
hermes cloudflare-memory status
hermes cloudflare-memory test
hermes cloudflare-memory namespaces
hermes cloudflare-memory card
```

**What Hermes gets:**
- `prefetch()` — 0ms (cached + background recall)
- `sync_turn()` — 0ms (daemon thread ingest)
- 6 agent tools: `cf_remember`, `cf_recall`, `cf_list`, `cf_get`, `cf_summary`, `cf_delete`
- `on_session_end` — auto-ingests full session for fact extraction
- System prompt injection with provider status

### Claude Code

Add to `.claude/mcp.json` in your project:

```json
{
  "mcpServers": {
    "cf-memory": {
      "command": "cf-memory",
      "args": ["serve"],
      "env": {
        "MCP_CLOUDFLARE_API_KEY": "your-token",
        "CF_ACCOUNT_ID": "your-account-id"
      }
    }
  }
}
```

Or add globally: `claude mcp add cf-memory -- cf-memory serve`

### Codex (OpenAI)

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.cf-memory]
command = "cf-memory"
args = ["serve"]
env = { MCP_CLOUDFLARE_API_KEY = "your-token", CF_ACCOUNT_ID = "your-account-id" }
```

### Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "cf-memory": {
      "command": "cf-memory",
      "args": ["serve"],
      "env": {
        "MCP_CLOUDFLARE_API_KEY": "your-token",
        "CF_ACCOUNT_ID": "your-account-id"
      }
    }
  }
}
```

### OpenClaw

Add to your OpenClaw config:

```json
{
  "mcpServers": {
    "cf-memory": {
      "command": "cf-memory",
      "args": ["serve"],
      "env": {
        "MCP_CLOUDFLARE_API_KEY": "your-token",
        "CF_ACCOUNT_ID": "your-account-id"
      }
    }
  }
}
```

### TRAE / TRAE CN / TraeCode CLI 2.0

Add MCP server in TRAE settings or `.trae/mcp.json`:

```json
{
  "mcpServers": {
    "cf-memory": {
      "command": "cf-memory",
      "args": ["serve"],
      "env": {
        "MCP_CLOUDFLARE_API_KEY": "your-token",
        "CF_ACCOUNT_ID": "your-account-id"
      }
    }
  }
}
```

### OpenCode

Add to `~/.opencode/config.json`:

```json
{
  "mcp": {
    "cf-memory": {
      "command": "cf-memory",
      "args": ["serve"],
      "env": {
        "MCP_CLOUDFLARE_API_KEY": "your-token",
        "CF_ACCOUNT_ID": "your-account-id"
      }
    }
  }
}
```

### pi

Add MCP server to pi config:

```json
{
  "mcpServers": {
    "cf-memory": {
      "command": "cf-memory",
      "args": ["serve"],
      "env": {
        "MCP_CLOUDFLARE_API_KEY": "your-token",
        "CF_ACCOUNT_ID = "your-account-id"
      }
    }
  }
}
```

### Agent Plugins 1.0

Install as a plugin:

```bash
pip install git+https://github.com/hansakoch/cloudflare-memory.git
```

The package registers via `hermes_agent.memory_providers` entry point. Any Agent Plugins 1.0 compatible host discovers it automatically.

### LangChain / LangGraph

```python
import asyncio
from cloudflare_memory import CloudflareMemoryClient

# Use as a memory backend in your LangChain/LangGraph agent
client = CloudflareMemoryClient(
    account_id="your-account-id",
    api_token="your-token",
    namespace="my-agent",
    profile="user-123",
)

# Store a fact
entry = asyncio.run(client.remember("User prefers Python over JavaScript."))

# Recall
result = asyncio.run(client.recall("What programming language does the user prefer?"))
print(result.answer)  # "Python"

# Ingest a conversation
asyncio.run(client.ingest([
    {"role": "user", "content": "I'm building a RAG pipeline."},
    {"role": "assistant", "content": "Great! Let me help with that."},
]))

# Get summary
summary = asyncio.run(client.get_summary())
```

### A2A (Agent-to-Agent)

Start the A2A server for peer agents to discover and call:

```bash
cf-memory a2a --port 9120
```

Agent card at `http://localhost:9120/.well-known/agent.json`

Skills: `remember`, `recall`, `ingest`, `list`, `get`, `summary`

### Python (standalone)

```python
import asyncio
from cloudflare_memory import CloudflareMemoryClient

async def main():
    async with CloudflareMemoryClient(
        account_id="your-account-id",
        api_token="your-token",
        namespace="my-app",
        profile="default",
    ) as client:
        # Remember
        entry = await client.remember("User is based in London.")
        print(f"[{entry.type}] {entry.summary}")

        # Recall
        result = await client.recall("Where is the user based?")
        print(result.answer)

        # Ingest conversation (async — memories appear 3-8s later)
        await client.ingest([
            {"role": "user", "content": "I prefer dark mode."},
            {"role": "assistant", "content": "Noted!"},
        ])

        # Summary
        print(await client.get_summary())

asyncio.run(main())
```

---

## Configuration

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MCP_CLOUDFLARE_API_KEY` | Yes | Cloudflare API token with Agent Memory permission |
| `CF_ACCOUNT_ID` | No | Cloudflare Account ID (defaults to Iceberg Media) |
| `CF_MEMORY_NAMESPACE` | No | Namespace name (default: `hermes`) |
| `CF_MEMORY_PROFILE` | No | Profile name (default: `default`) |

### Getting a Cloudflare API token

1. Go to [Cloudflare Dashboard → API Tokens](https://dash.cloudflare.com/profile/api-tokens)
2. Create a token with **Agent Memory** permission
3. You need a **paid Workers subscription** and **beta access** to Agent Memory

### Limits (official)

| Feature | Limit |
|---------|-------|
| Messages per ingest() | 500 |
| Message content | 32 KB UTF-8 |
| Recall query | 1 KB UTF-8 |
| Session ID | 64 chars |
| Profile name | 100 chars |
| Namespace name | 32 chars |

---

## Performance

Designed to never add latency to your agent's turns:

| Operation | Latency | Blocking? |
|-----------|---------|-----------|
| `prefetch()` | **0ms** | No — cached + background |
| `sync_turn()` | **0ms** | No — daemon thread |
| `remember` | 1.3–3.8s | User-initiated |
| `recall` | ~5s | User-initiated |
| `list` | ~0.4s | User-initiated |
| `summary` | ~0.8s | User-initiated |

---

## CLI reference

```bash
# Standalone
cf-memory test                          # Connectivity check
cf-memory serve [--transport stdio|sse] # MCP server
cf-memory a2a [--port 9120]             # A2A agent server
cf-memory card                          # Print agent card JSON

# Hermes plugin
hermes cloudflare-memory status         # Provider status
hermes cloudflare-memory test           # Full connectivity test
hermes cloudflare-memory namespaces     # List namespaces
hermes cloudflare-memory create-ns NAME # Create namespace
hermes cloudflare-memory delete-ns NAME # Delete namespace
hermes cloudflare-memory card           # Print agent card
```

---

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
