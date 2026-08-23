# Verified facts

Checked again on 2026-08-23 by grok-4.6 against **live API calls** and **official docs**. Earlier chat numbers are not treated as truth unless this retest or a primary source matches them.

Legend: **LIVE** = this session's curl. **DOC** = Cloudflare / Hermes source. **FORM** = beta Google Form text. **UNCONFIRMED** = do not build on this.

## Cloudflare Agent Memory product

| Claim | Verdict | Source |
|---|---|---|
| Private beta | **DOC** | https://developers.cloudflare.com/agent-memory/ — "Agent Memory is in private beta." |
| Not billed during beta; 30-day notice before charging | **DOC** | https://developers.cloudflare.com/agent-memory/platform/pricing/ |
| HTTP API exists for non-Worker callers | **DOC** + **LIVE** | https://developers.cloudflare.com/agent-memory/api/http-api/ |
| Worker binding also exists | **DOC** | Workers API page. Optional. Not needed for Hermes-on-Vultr. |
| Auth is `Authorization: Bearer <API token>` | **DOC** + **LIVE** | HTTP API docs; Iceberg token works |
| Profiles created on first write | **DOC** | HTTP API intro |
| `ingest` extracts facts/events/instructions/tasks | **DOC** | How it works + ingest docs |
| `ingest` HTTP response `result` is `null` | **DOC** + **LIVE** | Docs sample; live 200 + `result: null` |
| `ingest` is async — memories appear later | **LIVE** | New fact not listed at 0s/3s; present at 8s |
| `remember` stores one memory; response includes `type`, `summary`, `content` | **DOC** + **LIVE** | Docs sample includes type+summary; live 201 with those fields |
| `remember` is not a raw dump — type is assigned server-side | **LIVE** | Request has only `content` + `sessionId`; response has `type` |
| Type classification is inconsistent | **LIVE** | Same "Always lead with the result..." was `instruction` in an earlier test, `fact` in this retest |
| `list` omits `content` | **DOC** + **LIVE** | Docs: "List entries omit content." Live keys: id, type, summary, sessionId, createdAt, updatedAt |
| `get` includes `content` | **DOC** + **LIVE** | |
| `recall` returns synthesized `answer` + `candidates` | **DOC** + **LIVE** | |
| `recall` runs query analysis + parallel retrieval + synthesis | **DOC** | How it works |
| `GET .../summary` | **LIVE fail** | HTTP 404, code 10003 "Endpoint is unknown" |
| `POST .../summary` | **LIVE** | 200, `{ summary: markdown }` in ~0.4–0.8s on a 1-memory profile |
| Models used (Llama 4 Scout / Nemotron 3) | **UNCONFIRMED for this API** | Mentioned in a Cloudflare blog / InfoQ about Agent Memory internals. **Not** in the HTTP API docs. Do not document a model name as a contract. |
| Uses caller's Workers AI 10k neurons | **UNCONFIRMED / likely false** | Pricing page bills Agent Memory separately (currently $0). No neuron meter on these calls. Do not assume neuron drain. |
| Skip-classification flag on `remember` | **UNCONFIRMED** | Not in HTTP API docs. Not tested as a request field. |

## Limits (official)

From https://developers.cloudflare.com/agent-memory/platform/limits/ :

| Feature | Limit |
|---|---|
| Messages per ingest() | 500 |
| Message content | 32 KB UTF-8 |
| Recall query | 1 KB UTF-8 |
| Session ID | 64 chars |
| Profile name | 100 chars |
| Namespace name | 32 chars |
| List page size | 1–1000 (default 20) |

These are fine for Hermes turns. Not a blocker.

## Beta / plans

| Claim | Verdict | Source |
|---|---|---|
| Signup form says paid Workers is required | **FORM** | User pasted: "Do you have a paid Workers subscription? Yes! / No (a paid Workers sub is required)" |
| Wait 2–4 weeks after form | **FORM** | Same form |
| Iceberg Media has Agent Memory | **LIVE** | `GET .../agent-memory/namespaces` → 200 success |
| Iceberg Media has `prod_workers:workers_paid` | **LIVE** | subscriptions API |
| OpenRoyleAl has `workers_paid` but Agent Memory 401 "Not allowed" | **LIVE** | Paid is not sufficient; beta entitlement is separate |
| Free accounts on this token cannot use Agent Memory | **LIVE** | 401 Authentication error / Not allowed |
| Free accounts can never get beta | **UNCONFIRMED** | Form says paid is required. Do not sign up free accounts. |

Account IDs (not secrets):

- Iceberg Media: `0870b0bdbc14bcd31f43fe5e82c3ee8e` — **has** Agent Memory
- OpenRoyleAl: `89fe3b617242b040ec3936d43caa2011` — Workers Paid, **no** Agent Memory (form submitted)

## Latency (this session only — ranges, not SLAs)

From Vultr Singapore to `api.cloudflare.com` (CF-Ray **SIN**):

| Op | This retest (curl) | Notes |
|---|---|---|
| Account list / TLS | ~0.85s TTFB | Network + API |
| `remember` | **1.35–3.75s** | 4 writes; type+summary returned |
| `list` | **0.39s** | 4 rows |
| `get` | **1.37s** | 1 row + content |
| `recall` low/short | **5.35s** | answer + 1 candidate |
| `ingest` HTTP return | **1.60–2.18s** | `result: null`; extraction continues after |
| `ingest` visible in list | **between 3s and 8s** after HTTP return | Polled 0 / 3 / 8 / 15s |
| `POST summary` (1 memory) | **0.38–0.83s** | Fast on tiny profile; do not assume this stays fast at scale |

Earlier chat said remember 6–8s and list ~1s. **Those were older runs.** Use the range, not a single number. `remember` is still seconds, not 50–150ms (that CF Ask AI claim is **false** against live data).

## What we will not use

| Primitive | Why |
|---|---|
| Session API / Durable Object SQLite | **DOC**: Agents Session API is in-Worker. Not an external HTTP memory API. |
| Custom Worker proxy | Extra ops. HTTP API already works from this VPS. |
| OpenViking copy | Different product, AGPL server. Hermes already ships OpenViking. |

## Hermes integration rules

| Claim | Verdict | Source |
|---|---|---|
| New memory providers must be standalone | **DOC** | `hermes-agent/CONTRIBUTING.md` — in-tree `plugins/memory/` is closed |
| One external provider at a time | **DOC** | `agent/memory_provider.py` |
| `prefetch()` must be fast; use cache + background | **DOC** | ABC docstring |
| `sync_turn()` must be non-blocking | **DOC** | ABC + plugin guide |
| `message_agent` only in Bot Chat | **DOC** | `website/docs/user-guide/bot-mode.md` + `tools/bot_mode_dm.py` |
| This desktop chat can grow `message_agent` | **FALSE** | Regular profile session, not canonical Bot Chat |

## D1 fallback

| Claim | Verdict | Source |
|---|---|---|
| D1 has a REST query API | **DOC** | Cloudflare API: Query D1 Database |
| Free: 5M reads/day, 100k writes/day, 5GB | **DOC** | https://developers.cloudflare.com/d1/platform/pricing/ |
| D1 FTS5 schema designed in chat | **UNCONFIRMED in prod** | Designed, not created, not queried |

Do not ship D1 as "tested" until someone creates a DB and runs the same tests.
