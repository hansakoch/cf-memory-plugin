# Hermes Migration Guide: Centralized Cloudflare Agent Memory

Complete guide for migrating Hermes Agent profiles to shared Cloudflare Agent Memory.

## Problem

By default, each Hermes profile has isolated local memory (`~/.hermes/profiles/<name>/memories/`). When you run multiple bots/profiles, they can't share context. Old sessions stay trapped in SQLite.

## Solution

Cloudflare Agent Memory provides one shared brain for all profiles.

## Prerequisites

- Hermes Agent installed
- Cloudflare account with **Paid Workers** ($5/mo minimum)
- Agent Memory entitlement (private beta — [join waitlist](https://forms.gle/RAXbK6gN9Yy89ECw8))
- API token with **Agent Memory** permission ([create token](https://dash.cloudflare.com/profile/api-tokens))

## Step 1: Install the plugin

```bash
# From source (recommended until community index is updated)
pip install git+https://github.com/hansakoch/cf-memory-plugin.git

# Or clone and install locally
git clone https://github.com/hansakoch/cf-memory-plugin.git
cd cf-memory-plugin
pip install -e .
```

**Note:** Hermes security scan may block community plugins. Use `--force` if you trust the source:

```bash
hermes plugins install hansakoch/cf-memory-plugin --force
```

## Step 2: Set environment variables

Add to `~/.hermes/.env` (and each profile's `.env` if running multi-profile):

```bash
MCP_CLOUDFLARE_API_KEY=cfut_your_token_here
CF_ACCOUNT_ID=your_32_char_account_id
```

**Important:** Each profile has its own `.env` file at `~/.hermes/profiles/<name>/env`. The root `~/.hermes/.env` does NOT automatically propagate to profiles. You must copy these keys to every profile that needs memory access.

## Step 3: Configure memory provider

For each profile:

```bash
hermes config set memory.provider cloudflare-memory
hermes --profile <name> config set memory.provider cloudflare-memory
```

Or edit `config.yaml` directly:

```yaml
memory_provider: cloudflare-memory
```

## Step 4: Test connectivity

```bash
hermes cloudflare-memory test
```

Expected output:
```
✓ Namespaces: 1 found
✓ Remember: OK
✓ List: OK
✓ Recall: OK
✓ Summary: OK
✓ Cleaned up test memory
```

## Step 5: Ingest old sessions (bulk migration)

Hermes stores sessions in SQLite at `~/.hermes/profiles/<name>/state.db`. There is no built-in bulk ingest command. Use this Python script:

```python
#!/usr/bin/env python3
"""Bulk ingest Hermes sessions into Cloudflare Agent Memory."""
import asyncio
import sqlite3
from cloudflare_memory import CloudflareMemoryClient

ACCOUNT_ID = "your_account_id"
API_TOKEN = "your_token"
DB_PATH = "~/.hermes/profiles/alfred/state.db  # example path"  # adjust path

def get_sessions(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, display_name, started_at, last_activity_at, model
        FROM sessions WHERE archived IS NOT 1
        ORDER BY last_activity_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_messages(db_path, session_id, limit=60):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT role, content FROM messages
        WHERE session_id = ? AND role IN ('user','assistant')
        AND content IS NOT NULL AND content != ''
        ORDER BY timestamp ASC LIMIT ?
    """, (session_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

async def main():
    async with CloudflareMemoryClient(
        account_id=ACCOUNT_ID, api_token=API_TOKEN,
        namespace="hermes", profile="default"
    ) as client:
        sessions = get_sessions(DB_PATH)
        for i, s in enumerate(sessions):
            msgs = get_messages(DB_PATH, s["id"])
            if not msgs:
                continue
            user = [m["content"][:200] for m in msgs if m["role"]=="user"][:4]
            asst = [m["content"][:200] for m in msgs if m["role"]=="assistant"][:3]
            memory = f"[session:{s['id']}] {s.get('title','?')}. Asks: {' | '.join(user)}. Results: {' | '.join(asst)}"
            await client.remember(memory[:2000])
            print(f"[{i+1}/{len(sessions)}] {s.get('title','?')[:60]}")
            await asyncio.sleep(0.3)

asyncio.run(main())
```

## Multi-profile setup

For hub-and-spoke architectures (one main bot + specialists):

1. Create profiles: `hermes profile create <name>`
2. For each profile, add `MCP_CLOUDFLARE_API_KEY` and `CF_ACCOUNT_ID` to `~/.hermes/profiles/<name>/.env`
3. Set `memory_provider: cloudflare-memory` in each profile's `config.yaml`
4. All profiles share the same namespace and can read/write each other's memories

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `server 'cloudflare-memory' not found` | Plugin not installed as MCP server | Run `hermes config set memory.provider cloudflare-memory` |
| `OAuthNonInteractiveError` | Missing API key, falling back to OAuth | Add `MCP_CLOUDFLARE_API_KEY` to profile's `.env` |
| `Plugin not installed or bundled` | Plugin not in community index | Install from source: `pip install git+https://github.com/...` |
| `403 Forbidden` on MCP endpoint | Wrong token or missing Agent Memory permission | Verify token at dash.cloudflare.com/profile/api-tokens |
| `FileNotFoundError: config.yaml` | New profile has no config yet | Create it manually or run `hermes config set` for that profile |

## What gets ingested

- Session titles + key user/assistant messages
- SOUL.md, MEMORY.md, USER.md from each profile
- Skills metadata (name + description)
- Project associations

## What does NOT get ingested automatically

- Full message history (only key messages per session)
- Binary files, images, or attachments
- Cron job definitions (recreate these manually)
- Plugin configurations

## Cost

- Agent Memory: **$0 during private beta** (30-day notice before billing)
- Workers Paid: **$5/month** minimum
- This plugin: Free (MIT)
