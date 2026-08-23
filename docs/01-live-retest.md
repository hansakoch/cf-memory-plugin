# Live retest log (2026-08-23)

Token: existing `MCP_CLOUDFLARE_API_KEY` (not stored here).
Caller: Vultr Singapore. `api.cloudflare.com` CF-Ray suffix **SIN**.

## A. Entitlement sweep

| Account | ID prefix | Agent Memory list NS | Workers sub |
|---|---|---|---|
| Iceberg Media | 0870b0bd | 200 success | prod_workers:workers_paid |
| OpenRoyleAl | 89fe3b61 | 401 Not allowed | prod_workers:workers_paid |
| Globe IFA | c9f98ed0 | 401 Authentication error | none visible |
| Karl woolton | 571d0eb6 | 401 Not allowed | none visible |
| Nandersk | b5e78b5d | 401 Not allowed | none visible |
| Webuyyourcar | f0a0cebe | 401 Authentication error | none visible |

Conclusion: **Workers Paid ≠ Agent Memory access.**

## B. Namespace `grok-recheck` / profile `recheck`

Create NS: HTTP **201**.

### remember (POST, HTTP 201)

| Label | curl s | type | summary (truncated) |
|---|---|---|---|
| short "Dark mode preferred." | 3.755 | fact | Prefers dark mode |
| instruction text | 3.051 | **fact** | Prefers communication that leads with the result... |
| event text (dated) | 3.478 | event | Retested Cloudflare Agent Memory from Hermes on August 23, 2026 |
| complex Iceberg fact | 1.346 | fact | Hans runs Iceberg Media... |

Response keys always: `id, type, summary, content, sessionId, createdAt, updatedAt`.

### list (GET)

curl 0.388s, HTTP 200, count 4.
Keys: `id, type, summary, sessionId, createdAt, updatedAt`. **No `content`.**

### get (GET by id)

curl 1.366s. Keys include **`content`**.

### recall (POST, thinkingLevel=low, responseLength=short)

curl 5.350s. `answer="Iceberg Media, an SEO agency"` candidates=1.

### ingest (POST)

curl 2.180s. `success=true`, `result=null`. List immediately after still 4 rows (ingest session not present).

## C. Namespace `grok-recheck2` — ingest delay + summary

`POST /summary` empty body: HTTP 200, curl 0.830s. Body is markdown with Key Facts + Last Session.

Ingest "client reports live at reports.icebergmedia.co.uk":

| Seconds after ingest HTTP return | list count | new row? |
|---|---|---|
| 0 | 1 | no |
| 3 | 1 | no |
| 8 | 2 | yes — `[fact] sess=s2 Client reports hosted at reports.icebergmedia.co.uk` |
| 15 | 2 | same |

`GET /summary`: 404 Endpoint is unknown.

Both namespaces deleted after tests.

## D. Official HTTP API quotes that match the live shape

- Remember: stores one memory; example result includes `type`, `summary`, `content`.
- Ingest: example `result: null`.
- List: "List entries omit `content`."
- Recall: synthesized `answer` + `candidates`.
