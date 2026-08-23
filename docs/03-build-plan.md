# Build plan (for Alfred)

Do not start until the operator says go. Build against facts in `00-verified-facts.md`.

## Constraints

- Python only for v1. No TypeScript monorepo. No Worker.
- Iceberg Media account can hit Agent Memory **now**.
- D1 path is fallback; write schema + client, but mark untested until a live D1 query passes.
- `sync_turn` / `ingest` = background. `prefetch` = cache only.
- Never print or commit API tokens.

## Suggested order

1. `AgentMemoryBackend` HTTP client (stdlib `urllib` or `httpx`). Cover remember, list, get, recall, ingest, forget, summary POST, namespace create.
2. Unit tests with recorded JSON fixtures from `01-live-retest.md` (no live token in CI).
3. One live integration test gated on env (`CF_LIVE=1`), creates `cfmem-test-*` namespace, deletes it.
4. MCP stdio server + `uvx`/`cloudflare-memory serve`.
5. Hermes provider in `cloudflare_memory.providers.hermes` + `plugin.yaml` + pip entry point `hermes_agent.memory_providers`.
6. CLI: `serve`, `setup`, `status`.
7. D1 backend second (schema + FTS5). Live test on Iceberg D1 before calling it done.
8. Install into this Hermes profile, run `hermes memory setup`, one real session, fix what breaks.

## QA split

- grok-4.6: architecture, client correctness, latency-sensitive hooks.
- mimo-v2.5-pro: tests, fixtures, setup wizard, docs.

## Done when

- `CF_LIVE=1 pytest` creates and deletes a namespace on Iceberg Media.
- MCP `memory_list` / `memory_remember` / `memory_get` work from a local stdio session.
- Hermes with `memory.provider: cloudflare-memory` prefetches without adding ~5s to every turn.
- Built-in MEMORY.md still works (provider is additive).
