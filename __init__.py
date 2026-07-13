"""fleetiq — Hermes plugin that reports agent activity to a FleetIQ dashboard.

Read-only observability, same contract as the bundled langfuse/nemo_relay
plugins: maps Hermes' observer hooks onto FleetIQ's generic event vocabulary
(session_started, user_prompt, tool_call, tool_result, turn_ended) and posts
them to FleetIQ's /event API with agent_runtime="hermes". Never changes what
the agent does — hook callbacks are fail-open and never raise.

One Hermes session = one FleetIQ dashboard agent (matches Claude Code's model),
so `session_id` is used as both `agent_id` and `run_id`.

Required env var (~/.hermes/.env or `hermes tools`):
  FLEETIQ_API_KEY    - Bearer key for your FleetIQ tenant

Optional:
  FLEETIQ_URL        - FleetIQ API base (default: http://localhost:8000)
  FLEETIQ_PROJECT_ID - groups these agents on the dashboard (default: "hermes")
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)

# Fire-and-forget so a slow/unreachable FleetIQ instance never blocks the
# agent loop. A couple of workers is plenty for one session's worth of hooks.
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fleetiq-report")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _post(event_type: str, session_id: str, metadata: dict[str, Any]) -> None:
    key = _env("FLEETIQ_API_KEY")
    if not key or not session_id:
        return

    url = _env("FLEETIQ_URL", "http://localhost:8000").rstrip("/") + "/event"
    project_id = _env("FLEETIQ_PROJECT_ID", "hermes")
    payload = {
        "agent_id": session_id,
        "run_id": session_id,
        "project_id": project_id,
        "event_type": event_type,
        "agent_runtime": "hermes",
        "metadata": metadata,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, default=str).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as exc:  # fail-open: telemetry must never break the agent
        logger.warning("FleetIQ report failed (%s): %s", event_type, exc)


def _report(event_type: str, session_id: str, metadata: dict[str, Any]) -> None:
    _EXECUTOR.submit(_post, event_type, session_id, metadata)


def on_session_start(*, session_id: str = "", **_: Any) -> None:
    _report("session_started", session_id, {})


def on_session_end(
    *, session_id: str = "", completed: bool = False, interrupted: bool = False,
    reason: str = "", **_: Any,
) -> None:
    # Fires after EVERY turn (once per run_conversation() call), not just when
    # the conversation actually closes — so this must never carry
    # session_end=True, or FleetIQ marks the agent offline after every
    # message. The real close signal is on_session_finalize, below.
    _report("turn_ended", session_id, {
        "completed": completed, "interrupted": interrupted, "reason": reason,
    })


def on_session_finalize(
    *, session_id: str | None = None, platform: str = "", **_: Any,
) -> None:
    # Fires once when the CLI/gateway actually tears down a session (/new,
    # /reset, idle GC) — this is the correct place to signal session_end.
    if not session_id:
        return
    _report("turn_ended", session_id, {"session_end": True, "platform": platform})


def on_pre_llm_call(
    *, session_id: str = "", user_message: Any = None, is_first_turn: bool = False,
    model: str = "", platform: str = "", **_: Any,
) -> None:
    if user_message is None:
        return
    _report("user_prompt", session_id, {
        "prompt": str(user_message), "is_first_turn": is_first_turn,
        "model": model, "platform": platform,
    })


def on_post_llm_call(
    *, session_id: str = "", assistant_response: Any = None, model: str = "", **_: Any,
) -> None:
    _report("turn_ended", session_id, {"assistant_response": assistant_response, "model": model})


def on_pre_tool_call(
    *, session_id: str = "", tool_name: str = "", args: Any = None,
    tool_call_id: str = "", **_: Any,
) -> None:
    _report("tool_call", session_id, {"tool": tool_name, "args": args, "tool_call_id": tool_call_id})


def on_post_tool_call(
    *, session_id: str = "", tool_name: str = "", args: Any = None, result: Any = None,
    status: str = "", duration_ms: Any = None, tool_call_id: str = "", **_: Any,
) -> None:
    _report("tool_result", session_id, {
        "tool": tool_name, "args": args, "result": result,
        "success": status == "ok", "status": status,
        "duration_ms": duration_ms, "tool_call_id": tool_call_id,
    })


def on_subagent_start(
    *, parent_session_id: str = "", child_session_id: str = "", child_subagent_id: str = "",
    child_role: str = "", child_goal: str = "", **_: Any,
) -> None:
    # A delegate_task call spins up its own AIAgent with a fresh session_id
    # (see hermes-agent's tools/delegate_tool.py) that never touches
    # on_session_start/pre_llm_call in a way this plugin previously reported
    # reliably (short-lived, fire-and-forget). Report it explicitly here so
    # e.g. a "scraping" delegate shows up as its own FleetIQ agent instead of
    # only being narrated in the chat.
    if not child_session_id:
        return
    _report("session_started", child_session_id, {
        "parent_session_id": parent_session_id, "child_subagent_id": child_subagent_id,
        "role": child_role, "delegated": True,
    })
    _report("user_prompt", child_session_id, {
        "prompt": child_goal, "is_first_turn": True, "delegated": True,
    })


def on_subagent_stop(
    *, child_session_id: str = "", child_role: str = "", child_summary: Any = None,
    child_status: Any = None, duration_ms: Any = None, **_: Any,
) -> None:
    if not child_session_id:
        return
    _report("turn_ended", child_session_id, {
        "session_end": True, "role": child_role, "summary": child_summary,
        "status": child_status, "duration_ms": duration_ms, "delegated": True,
    })


def register(ctx) -> None:
    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("on_session_end", on_session_end)
    ctx.register_hook("on_session_finalize", on_session_finalize)
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("post_llm_call", on_post_llm_call)
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
    ctx.register_hook("subagent_start", on_subagent_start)
    ctx.register_hook("subagent_stop", on_subagent_stop)
