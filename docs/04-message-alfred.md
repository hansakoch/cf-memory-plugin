# How to reach Alfred (`message_agent`)

## What is true

`message_agent` is injected **only** into a Bot Mode **canonical Bot Chat**. Source: Hermes `tools/bot_mode_dm.py` and `website/docs/user-guide/bot-mode.md`.

This session is a normal Desktop chat on profile `default`. It **cannot** grow that tool. Do not build a custom DM layer.

Alfred exists as profile `alfred` (`~/.hermes/profiles/alfred/`). Gateway currently listed as **stopped**. Default model there: `mimo-v2.5-pro`. Alias `grok` → `xai/grok-4.6` is already in Alfred's config.

## What to do (operator)

1. Settings → Plugins → Bots: Bot Mode on.
2. Open **Alfred's Bot Chat** (not this thread).
3. If the gateway is stopped, start it / open that Bot Chat so it is running.
4. Paste the brief in `ALFRED-BRIEF.md` (or `@alfred` from another Bot Chat — that Bot will call `message_agent`).

Future Bot Chats get `message_agent` automatically. Regular chats never will.

## CLI equivalent (not message_agent)

```bash
hermes -p alfred chat --create-if-missing -c "Bot Chat"
```

That is a different session. Use it only if Bot Mode UI is down.
