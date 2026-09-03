# cf-memory — Agent Memory via Cloudflare

Persistent semantic memory across sessions. [GitHub](https://github.com/hansakoch/cf-memory-plugin)

## Install

```bash
pip install git+https://github.com/hansakoch/cf-memory-plugin.git
cf-memory doctor  # verify
```

## Credentials

```bash
export MCP_CLOUDFLARE_API_KEY="token-with-agent-memory-permission"
export CF_ACCOUNT_ID="your-account-id"
export CF_MEMORY_NAMESPACE="hermes"
export CF_MEMORY_PROFILE="alfred"
```

## MCP Server (any harness)

```bash
cf-memory serve        # 10 tools
cf-memory serve --slim # remember + recall only
```

Tools: `remember`, `recall`, `list_memories(type, session_id)`, `get_memory`, `delete_memory`, `ingest`, `summary`, `list_namespaces`, `create_namespace`, `delete_namespace`

## CLI

```bash
cf-memory remember "fact"
cf-memory recall "query"
cf-memory list --type fact --session my-session --limit 20
cf-memory export --format json -o backup.json
cf-memory export --format markdown --type fact -o facts.md
cf-memory get <id>
cf-memory delete <id>
cf-memory ingest messages.json --session-id my-session
cf-memory summary
```

## Harness Configs

**Grok CLI** (`~/.grok/config.toml`):
```toml
[mcp_servers.cf-memory]
command = "cf-memory"
args = ["serve"]
[mcp_servers.cf-memory.env]
MCP_CLOUDFLARE_API_KEY = "token"
CF_ACCOUNT_ID = "account"
CF_MEMORY_NAMESPACE = "hermes"
CF_MEMORY_PROFILE = "alfred"
```

**Hermes** (profile `config.yaml`):
```yaml
mcp:
  cf-memory:
    url: http://127.0.0.1:9120
    auth: { type: none }
    timeout: 30
    capabilities: [remember, recall, ingest, summary]
```
Start: `cf-memory a2a --port 9120`

**Claude Code**: `claude mcp add cf-memory -- cf-memory serve`

**Cursor/OpenClaw**: Add to `.cursor/mcp.json` or `openclaw.json`:
```json
{"mcpServers": {"cf-memory": {"command": "cf-memory", "args": ["serve"],
  "env": {"MCP_CLOUDFLARE_API_KEY": "...", "CF_ACCOUNT_ID": "...", "CF_MEMORY_NAMESPACE": "...", "CF_MEMORY_PROFILE": "..."}}}}
```

## Auto-Ingest (add to your system prompt)

```
Store facts to cf-memory proactively. After any work that discovers
information (clients, credentials, decisions, outcomes), call remember().
If you looked it up from local files or APIs, it should also be in cf-memory.
```

## Limits

Content: 32KB/msg. Ingest: 500 msgs. Recall query: 1KB. Namespace: 32 chars.

## Latency

remember ~2s, recall ~5s, list ~0.4s, get ~1.4s, ingest return ~2s (write 3-8s later).
