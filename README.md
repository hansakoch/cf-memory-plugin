# CF Memory Plugin

Persistent memory for AI agents, backed by
[Cloudflare Agent Memory](https://developers.cloudflare.com/agent-memory/).

This plugin is a thin client. Cloudflare stores, classifies, and recalls
memories. You do not run a vector DB, embeddings pipeline, or Worker.

**Want a batteries-included version?** [Alfred](https://alfred.report) ships
cf-memory-plugin pre-configured with a full agent stack — just bring your keys.

**Private beta.** Expect 2-4 weeks for access after signing up. Paid Workers is required. Paid Workers alone is not enough —
you still need Agent Memory entitlement.

| Need | Link |
|---|---|
| Join the beta (2-4 week wait) | [Waitlist form](https://forms.gle/RAXbK6gN9Yy89ECw8) |
| Product docs | [developers.cloudflare.com/agent-memory](https://developers.cloudflare.com/agent-memory/) |
| HTTP API | [HTTP API](https://developers.cloudflare.com/agent-memory/api/http-api/) |
| Pricing | [Agent Memory pricing](https://developers.cloudflare.com/agent-memory/platform/pricing/) |
| Limits | [Platform limits](https://developers.cloudflare.com/agent-memory/platform/limits/) |
| Create a token | [API Tokens](https://dash.cloudflare.com/profile/api-tokens) |
| Create a token (docs) | [Create API token](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/) |
| Workers Paid | [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/) |
| Design notes | [Introducing Agent Memory](https://blog.cloudflare.com/introducing-agent-memory/) |

---

## One-Minute Setup

```bash
# 1. Install
pip install git+https://github.com/hansakoch/cf-memory-plugin.git

# 2. Set credentials (get these from Cloudflare dashboard)
export MCP_CLOUDFLARE_API_KEY="cf-api-token-with-agent-memory"
export CF_ACCOUNT_ID="your-32-char-account-id"

# 3. Test connectivity
cf-memory test
```

`CF_ACCOUNT_ID` is required. There is no default account. Find it in the
[Cloudflare dashboard](https://dash.cloudflare.com/) sidebar.

Create the token at
[dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens)
with **Agent Memory** permission only. Do not reuse a Global API Key.

### Verify it works

```bash
$ cf-memory test
✓ Account: abc123...
✓ Token: valid
✓ Agent Memory: enabled
✓ Namespace "hermes" exists
```

If any step fails, see [Troubleshooting](#troubleshooting) below.

---

## What's Stored

Memories live in **namespaces** (isolated buckets) and **profiles** (per-user
or per-session views within a namespace).

```
Account
└── Namespace: "my-app"          ← one per project
    ├── Profile: "default"       ← general memories
    │   ├── Entry: "User prefers concise answers"
    │   ├── Entry: "Project uses PostgreSQL 16"
    │   └── Entry: "Deploy target is Fly.io"
    ├── Profile: "user:alice"    ← per-user context
    │   └── Entry: "Alice is in UTC+9"
    └── Profile: "session:xyz"   ← per-session scratch space
        └── Entry: "Currently refactoring auth module"
```

| Concept | Default | Override |
|---|---|---|
| Namespace | `hermes` | `CF_MEMORY_NAMESPACE` env or `--namespace` flag |
| Profile | `default` | `CF_MEMORY_PROFILE` env or `--profile` flag |

Each entry has:
- **content** — the raw text you stored
- **summary** — Cloudflare-generated one-liner
- **type** — classified category (fact, instruction, event, etc.)
- **timestamps** — `createdAt`, `updatedAt`

Use one namespace per app and one profile per user/tenant. Don't store
secrets, passwords, or customer PII you aren't allowed to store.

---

## What this is

| You call | Cloudflare does | Default MCP |
|---|---|---|
| `remember` | Store one fact / instruction / event | yes |
| `recall` | Search + synthesize an answer (~5s) | yes |
| `ingest` | Extract memories from a conversation (writes land 3–8s later) | CLI / `--full` only |
| `summary` | Markdown profile of what is stored | CLI / `--full` only |
| `list` / `get` / `delete` | Inspect or remove entries | CLI / `--full` only |

---

## MCP surface (token cost)

Harnesses (Grok CLI, Grok Bot, Claude, Codex, Cursor) inject **every** MCP
tool schema into **every** turn, even if unused. Tool count and description
size are the cost.

`cf-memory serve` and `python -m cloudflare_memory` advertise **two** tools:

| Tool | Schema | Returns |
|---|---|---|
| `remember` | `content: str` | compact `{"id","type"}` |
| `recall` | `query: str` | short synthesized answer only |

`thinking_level` and `response_length` are hardcoded to `low` / `short`. They
are not MCP parameters.

**Not registered on the default MCP server:** `list_memories`, `get_memory`,
`delete_memory`, `ingest`, `summary`, `list_namespaces`, `create_namespace`,
`delete_namespace`. Use the Python client or CLI. `ingest` and `summary` are
CLI-only because those schemas blow context.

Debug with `cf-memory serve --full` (old admin tool set).

Hermes does **not** use this MCP server. It uses the native memory provider
(background ingest, non-blocking prefetch, **zero MCP tools**).

## HTTP latency (client / CLI)

Each client call hits Cloudflare. Here's what to expect:

| Call | Latency | What happens |
|---|---|---|
| `remember` | ~2s (1.3–3.8s) | Classify + store one memory |
| `recall` | ~5s | Semantic search + LLM synthesis of answer |
| `ingest` | ~3s + async | Accept messages, return immediately. Cloudflare extracts memories in the background (3–8s) |
| `summary` | ~1s | Fetch the generated markdown profile |
| `list` | ~0.4s | Fast pagination, no content |
| `get` | ~1.4s | Single entry with content |
| `delete` | ~1s | Remove by ID |

**Cost:** Agent Memory is **free during private beta** with 30-day notice
before billing. You pay only for Workers Paid ($5/mo minimum). See
[Agent Memory pricing](https://developers.cloudflare.com/agent-memory/platform/pricing/)
for post-beta rates.

**Tip for Hermes users:** Hermes prefetches memory in the background, so
`recall`'s ~5s latency doesn't block your turn.

---

## MCP Config Examples

Same MCP block everywhere. Only the config file path changes.
`args: ["serve"]` is the slim default (two tools). Use `["serve", "--full"]`
only when debugging.

### Generic MCP block

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

### Grok CLI

Add to `~/.config/grok/mcp.json`:

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

### Grok Bot

Set via environment variables before launch:

```bash
export MCP_CLOUDFLARE_API_KEY="your-token"
export CF_ACCOUNT_ID="your-account-id"
```

Or configure in your Grok Bot deployment's MCP server list using the generic
block above.

### Hermes

Hermes is the only native provider — **zero MCP tools**, so it does not pay
the MCP schema tax. It prefetches in the background so recall does not add
~5s to every turn, and it ingests turns without blocking.

**Single profile:**

```bash
pip install git+https://github.com/hansakoch/cf-memory-plugin.git

# Add to ~/.hermes/.env
echo 'MCP_CLOUDFLARE_API_KEY=cfut_your_token' >> ~/.hermes/.env
echo 'CF_ACCOUNT_ID=your_account_id' >> ~/.hermes/.env

hermes config set memory.provider cloudflare-memory
hermes cloudflare-memory test
```

**Multi-profile (hub + specialists):**

Each profile has its own `.env` — the root `.env` does NOT propagate automatically.

```bash
# For EACH profile that needs memory access:
echo 'MCP_CLOUDFLARE_API_KEY=cfut_your_token' >> ~/.hermes/profiles/<name>/.env
echo 'CF_ACCOUNT_ID=your_account_id' >> ~/.hermes/profiles/<name>/.env
hermes --profile <name> config set memory.provider cloudflare-memory
```

**Migrating old sessions:** See [docs/hermes-migration-guide.md](docs/hermes-migration-guide.md) for bulk ingest of existing session data.

### Claude Code

```bash
claude mcp add cf-memory -- cf-memory serve
```

Or add to `.claude/mcp.json`:

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

### Codex

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.cf-memory]
command = "cf-memory"
args = ["serve"]

[mcp_servers.cf-memory.env]
MCP_CLOUDFLARE_API_KEY = "your-token"
CF_ACCOUNT_ID = "your-account-id"
```

### Cursor

Add to `.cursor/mcp.json`:

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

### Other clients

| Agent | Where to put it | Docs |
|---|---|---|
| [OpenClaw](https://github.com/openclaw) | host MCP config | OpenClaw |
| [TRAE](https://www.trae.ai) | `.trae/mcp.json` | TRAE |
| [OpenCode](https://opencode.ai) | `~/.opencode/config.json` | OpenCode |
| [pi](https://pi.dev) | host MCP config | pi |
| Any MCP client | stdio `cf-memory serve` | [MCP spec](https://modelcontextprotocol.io) |
| [LangChain](https://www.langchain.com) / [LangGraph](https://www.langchain.com/langgraph) | Python `CloudflareMemoryClient` | LangChain |
| A2A peers | `cf-memory a2a --port 9120` | Agent card at `/.well-known/agent.json` |

---

## Use it from Python

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
        await client.remember("User prefers concise answers.")
        result = await client.recall("How should I answer?")
        print(result.answer)

asyncio.run(main())
```

---

## CLI

```bash
cf-memory test                          # connectivity
cf-memory serve                         # MCP (stdio): remember + recall only
cf-memory serve --full                  # MCP with admin tools (debug)
cf-memory list                          # list memories (CLI-only)
cf-memory get MEMORY_ID                 # get one memory (CLI-only)
cf-memory delete MEMORY_ID              # delete one memory (CLI-only)
cf-memory summary                       # markdown summary (CLI-only)
cf-memory ingest messages.json          # extract from a conversation (CLI-only)
cf-memory namespaces                    # list namespaces (CLI-only)
cf-memory create-ns NAME                # create a namespace (CLI-only)
cf-memory delete-ns NAME                # delete a namespace (CLI-only)
cf-memory a2a --port 9120               # A2A on localhost
cf-memory card                          # print agent card

hermes cloudflare-memory status
hermes cloudflare-memory namespaces
```

`ingest` and `summary` stay on the CLI because registering them as MCP tools
blows context on every turn.

---

## Cost

| Item | Today | Source |
|---|---|---|
| Agent Memory | **$0 during private beta.** 30-day notice before billing. | [Pricing](https://developers.cloudflare.com/agent-memory/platform/pricing/) |
| Workers Paid (required to apply) | **$5/month** minimum | [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/) |
| This plugin | Free (MIT). Your own HTTP calls only. | — |

Recommended: Workers Paid on the account that will hold memory. Do not put
production memory on a free account. Do not assume every paid Workers account
has Agent Memory — we verified paid ≠ entitlement.

After beta, treat Agent Memory as a separate bill. Cloudflare has not published
GA rates yet.

---

## Dependencies

Runtime:

| Package | Why |
|---|---|
| [httpx](https://www.python-httpx.org/) | HTTPS client to `api.cloudflare.com` |
| [mcp](https://github.com/modelcontextprotocol/python-sdk) | MCP server (`cf-memory serve`) |

Optional:

| Extra | Packages | When |
|---|---|---|
| `pip install 'cf-memory-plugin[a2a]'` | starlette, uvicorn | A2A peer server |
| `pip install 'cf-memory-plugin[dev]'` | pytest, pytest-asyncio, respx | Tests |

No Cloudflare Worker, Wrangler, D1, Vectorize, or Workers AI binding is
required for this plugin. Those are Cloudflare products this client does **not**
use.

---

## Security

Follow Cloudflare's token rules:
[API token best practices](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/).

- Store `MCP_CLOUDFLARE_API_KEY` in the environment or a secret store. Never
  commit it.
- Scope the token to **Agent Memory** on one account.
- Set `CF_ACCOUNT_ID` yourself. This plugin will not fall back to another
  account.
- `cf-memory a2a` binds to `127.0.0.1` by default. Do not expose it to the
  public internet without auth.
- `ingest` and `sync_turn` send conversation text to Cloudflare. Do not ingest
  secrets, passwords, or customer PII you are not allowed to store.
- Use one namespace per app and one profile per user/tenant.
- Rotate the token from the
  [API Tokens](https://dash.cloudflare.com/profile/api-tokens) page if it leaks.

See [SECURITY.md](SECURITY.md).

---

## Troubleshooting

### `cf-memory test` fails with "Agent Memory not enabled"

Your account has Workers Paid but not the Agent Memory entitlement. This is a
private beta — you need to join the
[waitlist](https://forms.gle/RAXbK6gN9Yy89ECw8) and wait 2-4 weeks.

### `401 Unauthorized` or `403 Forbidden`

Your API token is missing the **Agent Memory** permission, or it's scoped to
the wrong account. Create a new token at
[dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens)
with only **Agent Memory** selected.

### `CF_ACCOUNT_ID` not set

```
Error: CF_ACCOUNT_ID is required
```

Find your 32-character account ID in the
[Cloudflare dashboard](https://dash.cloudflare.com/) sidebar. Export it:

```bash
export CF_ACCOUNT_ID="abc123..."
```

### `cf-memory: command not found`

The package isn't on your `PATH`. Try:

```bash
pip install --force-reinstall git+https://github.com/hansakoch/cf-memory-plugin.git
```

Or run it as a module: `python -m cloudflare_memory` (slim MCP) or
`python -m cloudflare_memory serve --full`.

### MCP client can't connect

- Ensure `cf-memory` is on `PATH` in the environment where the client runs.
  Some editors (Cursor, VS Code) use a different shell profile.
- Check the env block in your MCP config — typos in `MCP_CLOUDFLARE_API_KEY`
  or `CF_ACCOUNT_ID` are the most common issue.
- Test standalone first: `cf-memory test`.

### `recall` is slow (~5s)

This is expected. `recall` does a semantic search then an LLM synthesis pass
on Cloudflare's side. Hermes users get prefetching that hides this latency.
For other clients, consider caching or calling `recall` asynchronously.

### Ingested memories don't appear immediately

`ingest` returns immediately but Cloudflare extracts memories asynchronously.
Wait 3–8 seconds, then call `list` or `recall` to verify.

### Namespace already exists / doesn't exist

```
Error: namespace 'my-app' already exists
```

This is informational. Existing namespaces are fine — the plugin reuses them.
If a namespace doesn't exist, create it:

```bash
# Via CLI (not an MCP tool — namespaces are not on the default server)
cf-memory create-ns my-app

# Or set it and it will be created on first write
export CF_MEMORY_NAMESPACE="my-app"
```

### Rate limits

Cloudflare enforces API rate limits. If you see `429 Too Many Requests`, back
off and retry. Avoid tight loops calling `recall` or `remember` in scripts.

---

## Deploy the landing page (optional)

The plugin itself is not a Worker. The public page at
[cloudflare-memory.pages.dev](https://cloudflare-memory.pages.dev) is a static
[Cloudflare Pages](https://developers.cloudflare.com/pages/) site.

```bash
# token needs Pages:Edit on the same account
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
npx wrangler pages deploy ./public --project-name cf-memory-plugin
```

[Pages docs](https://developers.cloudflare.com/pages/get-started/guide/) ·
[Wrangler](https://developers.cloudflare.com/workers/wrangler/)

---

## Credits

- Memory backend: [Cloudflare Agent Memory](https://developers.cloudflare.com/agent-memory/)
  ([blog](https://blog.cloudflare.com/introducing-agent-memory/),
  [Discord](https://discord.cloudflare.com),
  [Community](https://community.cloudflare.com))
- Protocol: [Model Context Protocol](https://modelcontextprotocol.io)
- Hermes provider contract: [Nous Research Hermes Agent](https://hermes-agent.nousresearch.com)
- HTTP client: [httpx](https://www.python-httpx.org/)
- Batteries-included agent: [Alfred](https://alfred.report)

- Design inspiration: [Open Brain (OB1)](https://github.com/NateBJones-Projects/OB1) — "One database, one AI gateway, one chat channel — any AI plugs in."

This repo is not affiliated with Cloudflare or Nous Research.

## License

[MIT](LICENSE)
