"""Lesson 6 - observe agents & runs you didn't launch.

Lesson 5 RESUMED one agent by id. But real operations need the other half:
seeing what's out there without knowing ids in advance - a dashboard, a "what
did last night's jobs do?" report, a health check before firing another run.

That's the read-only side of the SDK, driven by an explicit `CursorClient`
instead of the convenience `Agent.*` classmethods:

  client.agents.list(...)      -> every agent (SDKAgentInfo rows)
  client.agents.get(id, ...)   -> one agent's metadata
  client.agents.list_runs(id)  -> that agent's runs (status, timing, result)
  client.agents.get_run(rid)   -> a single run by id

Two things that trip people up (both echo lesson 5):
  - Local listing is workspace-scoped: launch the bridge with the SAME
    `workspace` and pass the SAME `cwd` you created the agents under, or the
    list comes back empty.
  - It's all read-only here - no model needed, nothing is sent, no cost.

This lesson lists the local agents created under workspace/ (run lesson 5 a
couple of times first so there's something to see), then drills into the most
recent one's runs.

Run:  python lessons/06_observe_agents.py
      add --demo for the offline, no-key walkthrough
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (  # noqa: E402
    WORKSPACE,
    approve,
    banner,
    demo_enabled,
    require_api_key,
)

from cursor_sdk import CursorClient, CursorAgentError  # noqa: E402


def short(value: str | None, width: int = 20) -> str:
    """Trim long ids/text to keep the table readable."""
    text = (value or "").strip().replace("\n", " ")
    return (text[: width - 1] + "\u2026") if len(text) > width else text


def print_agent_table(agents) -> None:
    print(f"\n{'agent id':22}  {'status':9}  {'created':20}  name")
    print("-" * 74)
    for a in agents:
        print(
            f"{short(a.agent_id, 22):22}  "
            f"{short(getattr(a, 'status', None), 9):9}  "
            f"{short(getattr(a, 'created_at', None), 20):20}  "
            f"{short(getattr(a, 'name', None) or getattr(a, 'summary', None), 28)}"
        )


def print_runs(runs) -> None:
    if not runs:
        print("   (no runs recorded for this agent)")
        return
    print(f"\n   {'run id':22}  {'status':10}  {'duration':>9}  created")
    print("   " + "-" * 66)
    for r in runs:
        rid = getattr(r, "id", None) or getattr(r, "run_id", "?")
        dur = getattr(r, "duration_ms", None)
        dur_s = f"{dur/1000:.1f}s" if isinstance(dur, (int, float)) else "-"
        print(
            f"   {short(rid, 22):22}  "
            f"{short(getattr(r, 'status', None), 10):10}  "
            f"{dur_s:>9}  "
            f"{short(getattr(r, 'created_at', None), 20)}"
        )


def demo_run() -> None:
    """Offline stand-in: fabricate a couple of rows so the shape is clear."""
    agents = [
        SimpleNamespace(agent_id="agent-1069ccff-4489", status="finished",
                        created_at="2026-07-03T11:52", name="Nightjar recall demo"),
        SimpleNamespace(agent_id="agent-6acd01d9-7c9d", status="finished",
                        created_at="2026-07-03T11:47", name="first resume demo"),
    ]
    print_agent_table(agents)
    print(f"\nMost recent agent: {agents[0].agent_id}")
    print_runs([
        SimpleNamespace(id="run-abc123", status="finished", duration_ms=9922,
                        created_at="2026-07-03T11:52"),
        SimpleNamespace(id="run-def456", status="finished", duration_ms=17239,
                        created_at="2026-07-03T11:52"),
    ])
    print("\n(demo note: real listing reads your on-disk local store via the bridge.)")


def main() -> None:
    demo = demo_enabled()
    banner("Lesson 6: observe agents & runs" + ("  [DEMO]" if demo else ""))

    if demo:
        demo_run()
        return

    api_key = require_api_key()
    if not approve(
        f"List local agents stored under {WORKSPACE} (read-only, no cost)?",
        default_yes=True,
    ):
        print("Cancelled.")
        return

    try:
        # Same workspace + cwd the lessons created their agents under - local
        # persistence is workspace-scoped, so this is what makes them visible.
        with CursorClient.launch_bridge(
            workspace=str(WORKSPACE),
            allow_api_key_env_fallback=True,
        ) as client:
            result = client.agents.list(
                runtime="local", cwd=str(WORKSPACE), api_key=api_key, limit=20
            )
            agents = list(result.items)
            if not agents:
                print(
                    "\nNo local agents found under this workspace yet.\n"
                    "Run lesson 5 first (it creates one), then come back."
                )
                return

            print(f"\nFound {len(agents)} local agent(s):")
            print_agent_table(agents)

            # Drill into the first row and show its run history.
            target = agents[0]
            print(f"\nMost recent agent: {target.agent_id}")
            info = client.agents.get(target.agent_id, cwd=str(WORKSPACE), api_key=api_key)
            print(f"  name:    {info.name}")
            print(f"  summary: {short(info.summary, 60)}")
            print(f"  runtime: {info.runtime}    cwd: {info.cwd}")

            runs = client.agents.list_runs(
                info.agent_id, runtime="local", cwd=str(WORKSPACE),
                api_key=api_key, limit=10,
            )
            print_runs(list(runs.items))

    except CursorAgentError as err:
        print(
            f"\nCouldn't reach the bridge/list agents: {err.message} "
            f"(retryable={err.is_retryable})",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")


if __name__ == "__main__":
    main()
