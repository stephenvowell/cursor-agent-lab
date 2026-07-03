"""Lesson 2 - a durable agent: streaming output + follow-ups.

`Agent.create(...)` gives you an agent you can talk to more than once. Each
`agent.send(...)` returns a `run` you can stream, and the agent remembers the
whole conversation, so follow-ups have context.

Key habits shown here:
  - stream with `run.messages()` to watch tokens arrive
  - ALWAYS call `run.wait()` to get the terminal result
  - dispose cleanly with `with Agent.create(...) as agent:`

Run:  python lessons/02_streaming_followup.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (  # noqa: E402
    MODEL,
    WORKSPACE,
    approve,
    banner,
    require_api_key,
    stream_text,
)

from cursor_sdk import Agent, CursorAgentError, LocalAgentOptions  # noqa: E402


def main() -> None:
    banner("Lesson 2: durable agent, streaming + follow-up")
    api_key = require_api_key()

    first = "Draft a 2-sentence morning stand-up update for a solo developer."
    followup = "Now rewrite it to be one sentence and more upbeat."

    if not approve(f'Start a conversation with:\n   "{first}"'):
        print("Cancelled.")
        return

    try:
        # `with` guarantees the agent (and its local executor) is disposed.
        with Agent.create(
            model=MODEL,
            api_key=api_key,
            local=LocalAgentOptions(cwd=str(WORKSPACE)),
        ) as agent:
            print("\n--- agent, first reply ---")
            run = agent.send(first)
            # Log the ids first - if a stream ever hangs, these are your handle.
            print(f"(agent={getattr(agent, 'agent_id', '?')}  run={run.run_id})\n")
            stream_text(run)

            # Follow-up: the agent still has the full conversation in context.
            if approve(f'Send follow-up:\n   "{followup}"'):
                print("\n--- agent, follow-up reply ---")
                run2 = agent.send(followup)
                stream_text(run2)
            else:
                print("Skipped the follow-up.")

    except CursorAgentError as err:
        print(
            f"\nAgent failed to start: {err.message} "
            f"(retryable={err.is_retryable})",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
