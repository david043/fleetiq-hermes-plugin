# fleetiq-hermes-plugin

A read-only [Hermes](https://github.com/NousResearch/hermes-agent) observer
plugin that reports session/turn/tool activity to a
[FleetIQ](https://github.com/david043/fleetiq) dashboard.

It uses Hermes' documented observer-hook contract (`docs/observability/`) —
the same mechanism as Hermes' bundled Langfuse/NeMo Relay plugins — so it
never changes what the agent does. Every hook callback is fail-open: a
misconfigured or unreachable FleetIQ instance is logged and ignored, never
raised into the agent loop.

One Hermes session = one FleetIQ dashboard agent, matching how FleetIQ tracks
Claude Code sessions.

| Hermes hook | FleetIQ event |
|---|---|
| `on_session_start` | `session_started` |
| `pre_llm_call` | `user_prompt` |
| `pre_tool_call` | `tool_call` |
| `post_tool_call` | `tool_result` |
| `post_llm_call` | `turn_ended` |
| `on_session_end` | `turn_ended` (session closed) |

## Install

You need a FleetIQ URL and API key (from your FleetIQ operator/dashboard).

**macOS / Linux / WSL / Git Bash:**

```bash
curl -fsSL https://raw.githubusercontent.com/david043/fleetiq-hermes-plugin/main/install.sh | \
  FLEETIQ_URL=https://your-fleetiq-host FLEETIQ_API_KEY=fliq_sk_... bash
```

Omit the env vars to be prompted interactively instead.

**Windows (native PowerShell):**

```powershell
$env:FLEETIQ_URL="https://your-fleetiq-host"
$env:FLEETIQ_API_KEY="fliq_sk_..."
irm https://raw.githubusercontent.com/david043/fleetiq-hermes-plugin/main/install.ps1 | iex
```

Both installers:

1. Fetch `plugin.yaml` + `__init__.py` into Hermes' plugin directory
   (`~/.hermes/plugins/fleetiq`, or `%LOCALAPPDATA%\hermes\plugins\fleetiq`
   on native Windows)
2. Upsert `FLEETIQ_URL` / `FLEETIQ_API_KEY` / `FLEETIQ_PROJECT_ID` into
   Hermes' `.env`
3. Run `hermes plugins enable fleetiq` if the `hermes` CLI is on `PATH`

Start (or resume) a Hermes session afterward — it appears automatically on
your FleetIQ dashboard.

## Config

| Env var | Required | Default | Meaning |
|---|---|---|---|
| `FLEETIQ_API_KEY` | yes | — | Bearer key for your FleetIQ tenant |
| `FLEETIQ_URL` | no | `http://localhost:8000` | FleetIQ API base |
| `FLEETIQ_PROJECT_ID` | no | `hermes` | Groups these agents on the dashboard |

## Manual install

Copy `plugin.yaml` and `__init__.py` into
`$HERMES_HOME/plugins/fleetiq/` (default `~/.hermes/plugins/fleetiq`, or
`%LOCALAPPDATA%\hermes\plugins\fleetiq` on native Windows), set the env vars
above in Hermes' `.env`, then run `hermes plugins enable fleetiq`.
