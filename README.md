# CF Memory Plugin

Persistent memory for AI agents, backed by
[Cloudflare Agent Memory](https://developers.cloudflare.com/agent-memory/).

This plugin is a thin client. Cloudflare stores, classifies, and recalls
memories. You do not run a vector DB, embeddings pipeline, or Worker.

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

## 60-second setup

```bash
pip install git+https://github.com/hansakoch/cf-memory-plugin.git

export MCP_CLOUDFLARE_API_KEY="cf-api-token-with-agent-memory"
export CF_ACCOUNT_ID="your-32-char-account-id"

cf-memory test
```

`CF_ACCOUNT_ID` is required. There is no default account. Find it in the
[Cloudflare dashboard](https://dash.cloudflare.com/) sidebar.

Create the token at
[dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens)
with **Agent Memory** permission only. Do not reuse a Global API Key.

## What this is

| You call | Cloudflare does |
|---|---|
| `remember` | Store one fact / instruction / event |
| `recall` | Search + synthesize an answer (~5s) |
| `ingest` | Extract memories from a conversation (writes land 3–8s later) |
| `summary` | Markdown profile of what is stored |
| `list` / `get` / `delete` | Inspect or remove entries |

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

## Use it from an agent

Same MCP block everywhere. Only the config file path changes.

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

| Agent | Where to put it | Docs |
|---|---|---|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `.claude/mcp.json` or `claude mcp add cf-memory -- cf-memory serve` | [MCP](https://modelcontextprotocol.io) |
| [Codex](https://github.com/openai/codex) | `~/.codex/config.toml` → `[mcp_servers.cf-memory]` | OpenAI Codex |
| [Cursor](https://cursor.com) | `.cursor/mcp.json` | Cursor MCP |
| [Hermes](https://hermes-agent.nousresearch.com) | See [Hermes setup](#hermes-setup) below | [Migration guide](docs/hermes-migration-guide.md) |
| [OpenClaw](https://github.com/openclaw) | host MCP config | OpenClaw |
| [TRAE](https://www.trae.ai) | `.trae/mcp.json` | TRAE |
| [OpenCode](https://opencode.ai) | `~/.opencode/config.json` | OpenCode |
| [pi](https://pi.dev) | host MCP config | pi |
| Any MCP client | stdio `cf-memory serve` | [MCP spec](https://modelcontextprotocol.io) |
| [LangChain](https://www.langchain.com) / [LangGraph](https://www.langchain.com/langgraph) | Python `CloudflareMemoryClient` | LangChain |
| A2A peers | `cf-memory a2a --port 9120` | Agent card at `/.well-known/agent.json` |

Hermes is the only native provider. It prefetches in the background so recall
does not add ~5s to every turn.

### Hermes setup

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

Python:

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

## CLI

```bash
cf-memory test                          # connectivity
cf-memory serve                         # MCP (stdio)
cf-memory a2a --port 9120               # A2A on localhost
cf-memory card                          # print agent card

hermes cloudflare-memory status
hermes cloudflare-memory namespaces
```

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

## Credits

- Memory backend: [Cloudflare Agent Memory](https://developers.cloudflare.com/agent-memory/)
  ([blog](https://blog.cloudflare.com/introducing-agent-memory/),
  [Discord](https://discord.cloudflare.com),
  [Community](https://community.cloudflare.com))
- Protocol: [Model Context Protocol](https://modelcontextprotocol.io)
- Hermes provider contract: [Nous Research Hermes Agent](https://hermes-agent.nousresearch.com)
- HTTP client: [httpx](https://www.python-httpx.org/)

- Design inspiration: [Open Brain (OB1)](https://github.com/NateBJones-Projects/OB1) — "One database, one AI gateway, one chat channel — any AI plugs in."
This repo is not affiliated with Cloudflare or Nous Research.

## License

[MIT](LICENSE)
