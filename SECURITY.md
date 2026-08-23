# Security

## Report a vulnerability

Email hans@icebergmedia.co.uk. Do not open a public issue for token leaks or
remote-code bugs.

## What this plugin stores

Nothing locally except optional non-secret config:

```json
{ "namespace": "hermes", "profile": "default" }
```

Memories live in Cloudflare Agent Memory on **your** account. This plugin never
defaults to another account.

## Token rules

Follow Cloudflare:
https://developers.cloudflare.com/fundamentals/api/get-started/create-token/

1. Create a **user API token**, not a Global API Key.
2. Grant only **Agent Memory** on the target account.
3. Put it in `MCP_CLOUDFLARE_API_KEY`. Never commit it.
4. Rotate it from https://dash.cloudflare.com/profile/api-tokens if leaked.

## What we send to Cloudflare

| Call | Payload |
|---|---|
| remember | the text you pass |
| ingest / Hermes `sync_turn` | user + assistant messages (and optional tool messages if the host supplies them) |
| recall | the query string |

Do not ingest secrets, passwords, payment data, or customer PII you are not
allowed to store with a processor.

## Network

- All API calls go to `https://api.cloudflare.com` over TLS.
- The A2A helper binds to `127.0.0.1` by default. Binding to `0.0.0.0` exposes
  an unauthenticated JSON-RPC surface — do not do that on a public host.

## Cloudflare resources

- [API token best practices](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
- [Agent Memory HTTP API](https://developers.cloudflare.com/agent-memory/api/http-api/)
- [Cloudflare security disclosures](https://www.cloudflare.com/disclosure/)
