---
name: reachy-mini
description: Reference guide for Reachy Mini robot troubleshooting, known issues, and workaround procedures.
version: 1.1.0
---

# Reachy Mini Troubleshooting Reference

## Architecture: Voice App vs Jerry

The Reachy Mini system has two separate components that often get confused:

1. **`reachy_mini_conversation_app`** (standalone voice app): Located at `~/Documents/reachy_mini_conversation_app/`. Runs its own LLM (usually HuggingFace), its own STT, its own TTS. Talks to a WebSocket endpoint directly. **Completely independent of Jerry** — has no access to Spotify, Gmail, or any Hermes skills.

2. **`hermes_reachy_mini`** (Hermes plugin): Located at `~/.hermes/plugins/reachy-mini-hermes-agent/hermes-reachy-mini/`. Embeds a Hermes AIAgent that routes through Jerry. Can use all of Jerry's tools (Spotify, Google, etc.).

**The bridge is the problem**: If the voice app's `.env` has `BACKEND_PROVIDER="huggingface"`, it bypasses Jerry entirely. To route through Jerry:
- Set `BACKEND_PROVIDER` in the voice app's `.env` to connect to Jerry's WebSocket gateway (usually `ws://127.0.0.1:8765`)
- Or use the `hermes_reachy_mini` package's embedded agent instead of the voice app's native LLM
- The embedded agent needs `HERMES_HOME=/home/yanyi/.hermes` to load skills and tools

**User frequently expects Reachy to use Jerry's tools (Spotify, Google, etc.)** but the voice app talks to HuggingFace directly. Check the voice app's `.env` `BACKEND_PROVIDER` setting before assuming the integration is broken — it's usually just misconfigured to talk to the wrong LLM.

## Dance Routine Timeouts

`reachy_dance` times out on the user's Reachy Mini for all tested dance names. This is reproducible and persistent.

**Tested names (all timed out):** `default`, `happy`, `wave`, `disco`, `shuffle`

**Workaround:** Use `reachy_play_emotion` or basic movements (`reachy_move_head`, `reachy_move_antennas`) for physical expression instead.

## Emotion Playouts May Also Timeout

`reachy_play_emotion` has been observed to timeout (tested with `happy`). Try a different emotion name if one times out.

**Emotions that may work:** `sad`, `surprised`, `angry`, `thinking`, `cheerful`, `curious`, `laughing`, `thoughtful`, `welcoming`, `scared`, `proud`, `confused`, `shy`, `enthusiastic`, `grateful`

## Connection Must Be Established First

The first dance attempt in a session can fail with "Not connected to robot" even though `reachy_status` reports connected.

**Fix:** Call `reachy_connect(connection_mode="auto")` before attempting dance routines.

## Verified Working Actions

- `reachy_connect` — works
- `reachy_move_head` — works
- `reachy_move_antennas` — works
- `reachy_status` — works
- `reachy_dance` — times out
- `reachy_play_emotion` — may timeout

## Connection Modes

- `auto` — works reliably
- `network` — confirmed working
- `localhost_only` — untested

## References

See `references/troubleshooting.md` for the full troubleshooting table and version history.