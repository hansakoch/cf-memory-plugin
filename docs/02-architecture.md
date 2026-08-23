# Architecture (locked where evidence exists)

## Goal

One MIT Python package:

1. HTTP client for Cloudflare Agent Memory
2. MCP server (`cloudflare-memory serve`) so any MCP client can use it
3. Hermes `MemoryProvider` adapter (standalone plugin / pip entry point)
4. Later: D1 backend for people without Agent Memory beta

Not a Worker. Not in the Hermes git tree.

## Why HTTP API, not a Worker

Verified: the HTTP API works from this VPS with a Bearer token. A Worker adds deploy/maintenance and does not remove the 1–5s server-side work on `remember`/`recall`.

## Why MCP + Hermes provider

- MCP: Claude Code, Cursor, OpenCode, etc. Tools are request/response. Keep them synchronous.
- Hermes provider: `prefetch` / `queue_prefetch` / `sync_turn` are lifecycle hooks MCP cannot replace. Required for automatic memory.

## Backends

```
MemoryBackend ABC
├── AgentMemoryBackend   # LIVE on Iceberg Media
└── D1Backend            # designed, NOT live-tested
```

Same tool names. D1 `recall` returns `answer: null` + FTS5 `candidates`. Do not put an LLM in the D1 path until someone measures it.

## Hermes mapping (must follow ABC)

| Hook | Call | Why |
|---|---|---|
| `is_available()` | env vars present only | ABC: no network |
| `initialize()` | ensure namespace (network ok here) | |
| `prefetch()` | return **cached** text only | ABC: "should be fast" |
| `queue_prefetch()` | background `list` and/or `recall` low/short | next turn |
| `sync_turn()` | background `ingest` | ABC: non-blocking; ingest is async anyway |
| tools | `memory_recall`, `memory_remember`, `memory_forget`, `memory_list`, `memory_get` | list has no content → get is required |

**Do not** block `prefetch()` on a 5s `recall`. That was a CF Ask AI suggestion; it fights the Hermes ABC.

## MCP tools (v1)

`memory_remember`, `memory_recall` (+ optional `reference_date`), `memory_list`, `memory_get`, `memory_forget`, `memory_ingest`, `memory_summary`.

Namespace/profile: env/config at process start. Auto-create namespace. No management tools in v1.

## Config (env)

```
CF_API_TOKEN
CF_ACCOUNT_ID
CF_MEMORY_NAMESPACE     # default: hermes
CF_MEMORY_PROFILE       # default: default
CF_MEMORY_BACKEND       # agent-memory | d1
CF_D1_DATABASE_ID       # d1 only
```

Secrets only in env. No tokens in this repo.

## License / contribution

- Package: MIT
- Hermes: MIT (adapter implements ABC; do not vendor Hermes)
- Cloudflare APIs: call only, do not copy SDK source
- Contribution: docs PR to list the provider, **not** a `plugins/memory/` directory

## Name

Package / CLI: `cloudflare-memory` (check PyPI before publish).
Hermes provider name: `cloudflare-memory`.
