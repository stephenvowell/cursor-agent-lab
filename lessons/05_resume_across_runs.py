"""Lesson 5 - resume an agent across separate runs (Agent.resume).

Lessons 1-2 lived inside a single process. Real automations don't: a cron job
picks up last night's work, a webhook extends a conversation an hour later, a
CLI reloads where you left off. That's `Agent.resume(agent_id, ...)` - hand it
an agent ID you saved earlier and the whole conversation comes back with it.

This lesson proves it by splitting the work across TWO separate runs of this
same script:

  Run #1 (no saved id yet)  -> CREATE an agent, tell it something to remember,
                               save its id to workspace/output/.agent_resume_id
  Run #2 (saved id found)   -> RESUME that agent and ask it to recall - if it
                               answers correctly, memory survived the process exit

Because it's a fresh Python process each time, this is the genuine
cron/webhook pattern, not an in-memory trick.

Local resume has two easy-to-miss requirements (both learned the hard way,
see resume_and_recall below): you must resume with the SAME `cwd` the agent
was created with (local persistence is workspace-scoped) and re-pass `model`
(`agent.model` is None after resume). Cloud "bc-" agents need neither.

Run:  python lessons/05_resume_across_runs.py           (1st: creates + saves)
      python lessons/05_resume_across_runs.py           (2nd: resumes + recalls)
      python lessons/05_resume_across_runs.py --new     (force a fresh start)
      add --demo to any of the above for the offline, no-key, no-cost walkthrough
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (  # noqa: E402
    MODEL,
    OUTPUT_DIR,
    WORKSPACE,
    FakeAgent,
    approve,
    banner,
    demo_enabled,
    require_api_key,
    stream_text,
)

from cursor_sdk import (  # noqa: E402
    Agent,
    AgentOptions,
    CursorAgentError,
    LocalAgentOptions,
)

# A tiny, non-secret breadcrumb. Lives under workspace/output/ (gitignored).
ID_FILE = OUTPUT_DIR / ".agent_resume_id"

# The "memory" we plant on run #1 and quiz on run #2.
SECRET = "the project codename is Nightjar and the lucky number is 7"
PLANT = (
    f"Please remember this for later: {SECRET}. "
    "Reply with a single short sentence confirming you've got it."
)
RECALL = (
    "Without me repeating it, what is the project codename and the lucky "
    "number I asked you to remember earlier? Answer in one short sentence."
)


def read_saved_id() -> str:
    try:
        return ID_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def create_and_save(api_key: str, demo: bool) -> None:
    """Run #1: create a fresh agent, plant a memory, persist its id."""
    if not approve(f'Create an agent and tell it:\n   "{PLANT}"', default_yes=True):
        print("Cancelled. Nothing was sent.")
        return

    agent_cm = FakeAgent() if demo else Agent.create(
        model=MODEL,
        api_key=api_key,
        local=LocalAgentOptions(cwd=str(WORKSPACE)),
    )

    with agent_cm as agent:
        agent_id = getattr(agent, "agent_id", "?")
        print(f"\n--- new agent {agent_id} ---")
        run = agent.send(PLANT)
        stream_text(run)
        # Save the id BEFORE the `with` block disposes the live handle. Local
        # agents persist on disk under a per-workspace state root, so the record
        # outlives disposal - but that store is scoped to this agent's `cwd`
        # (here: WORKSPACE). Resume MUST point at the same cwd to find it again.
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ID_FILE.write_text(agent_id, encoding="utf-8")

    print(f"\nSaved agent id -> {ID_FILE}")
    print("Now run this lesson again (no flags) to RESUME and test its memory.")
    if demo:
        print("(demo note: FakeAgent can't truly remember - run for real to see recall work.)")


def resume_and_recall(api_key: str, saved_id: str, demo: bool) -> None:
    """Run #2: resume the saved agent in a brand-new process and quiz it."""
    runtime = "cloud" if saved_id.startswith("bc-") else "local"
    print(f"Found saved agent id: {saved_id}  (runtime auto-detected: {runtime})")
    if not approve(f'Resume it and ask:\n   "{RECALL}"', default_yes=True):
        print("Cancelled.")
        return

    # Resume gotchas learned the hard way (all three matter for LOCAL agents):
    #   1. cwd - local persistence is workspace-scoped; pass the SAME cwd the
    #      agent was created with or the bridge reports "Agent not found".
    #   2. model - `agent.model` is None after resume; re-pass it or a local
    #      send fails with "Local SDK agents require an explicit model".
    #   3. inline MCP servers are NOT persisted - pass them again here if used.
    # (Cloud "bc-" agents persist server-side and don't need cwd.)
    agent_cm = FakeAgent() if demo else Agent.resume(
        saved_id,
        AgentOptions(
            api_key=api_key,
            model=MODEL,
            local=LocalAgentOptions(cwd=str(WORKSPACE)),
        ),
    )

    with agent_cm as agent:
        print(f"\n--- resumed agent {getattr(agent, 'agent_id', '?')} ---")
        run = agent.send(RECALL)
        answer = stream_text(run)

    if not demo:
        ok = "nightjar" in answer.lower() and "7" in answer
        print(
            "\n[check] Memory survived the process boundary."
            if ok
            else "\n[check] Hmm - recall wasn't clearly correct; the id may be stale "
            "(try --new)."
        )
    else:
        print("\n(demo note: real recall requires a real agent + CURSOR_API_KEY.)")


def main() -> None:
    demo = demo_enabled()
    force_new = "--new" in sys.argv
    banner("Lesson 5: resume across runs  (Agent.resume)" + ("  [DEMO]" if demo else ""))
    api_key = "demo" if demo else require_api_key()

    saved_id = "" if force_new else read_saved_id()

    try:
        if saved_id:
            resume_and_recall(api_key, saved_id, demo)
        else:
            if force_new and ID_FILE.exists():
                ID_FILE.unlink()
            create_and_save(api_key, demo)
    except CursorAgentError as err:
        # Thrown = the run never started (auth/config/network, or a stale/invalid
        # id on resume). Different from a run that starts and then fails.
        print(
            f"\nAgent failed to start: {err.message} "
            f"(retryable={err.is_retryable}).\n"
            "If you were resuming, the saved id may be stale - rerun with --new.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nInterrupted. Nothing further was sent.")


if __name__ == "__main__":
    main()
