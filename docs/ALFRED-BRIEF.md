# Brief for Alfred — Cloudflare Memory plugin

Read `/home/fansfollow/projects/cloudflare-memory/docs/00-verified-facts.md` and `01-live-retest.md` before writing code. Those were rechecked 2026-08-23 with live curl + official CF/Hermes docs.

## Build

Standalone MIT Python package at `/home/fansfollow/projects/cloudflare-memory`.

- HTTP client for Cloudflare **Agent Memory** REST API (no Worker).
- MCP server: `cloudflare-memory serve`.
- Hermes `MemoryProvider` via pip entry point / `~/.hermes/plugins/` — **not** a PR under `plugins/memory/` (CONTRIBUTING: in-tree providers closed).
- D1 backend later; do not claim it works until live-tested.

Iceberg Media account `0870b0bdbc14bcd31f43fe5e82c3ee8e` already has Agent Memory. Token is `MCP_CLOUDFLARE_API_KEY` in env — do not write it to files.

## Hard rules from evidence

- `remember` takes 1.3–3.8s and returns `type`+`summary`. Not 50ms.
- `recall` ~5s. Never block `prefetch()` on it. Cache + `queue_prefetch`.
- `list` has no `content`; `get` does.
- `ingest` returns `result: null` then writes ~3–8s later. `sync_turn` must be async.
- `POST /summary` works; `GET /summary` 404.
- Paid Workers ≠ beta access (OpenRoyleAl is paid and 401).

## Done

Live namespace create/delete test, MCP tools, Hermes provider that does not add 5s per turn. Then install on this box and fix from a real session.

Use grok-4.6 for the client/hooks. Use mimo-v2.5-pro for tests and setup UX.
