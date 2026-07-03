"""Lesson 1 - one agent, one shot.

`Agent.prompt(...)` is the simplest pattern: send a prompt, wait for the
result, and it disposes itself. Use it for fire-and-forget tasks.

Run:  python lessons/01_one_shot.py
"""

from __future__ import annotations

import os
import sys

# Make the sibling `shared` package importable when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (  # noqa: E402
    MODEL,
    WORKSPACE,
    approve,
    banner,
    demo_enabled,
    demo_prompt,
    require_api_key,
)

from cursor_sdk import (  # noqa: E402
    Agent,
    AgentOptions,
    CursorAgentError,
    LocalAgentOptions,
)


def main() -> None:
    demo = demo_enabled()
    banner("Lesson 1: one agent, one shot  (Agent.prompt)" + ("  [DEMO]" if demo else ""))
    api_key = "demo" if demo else require_api_key()

    task = (
        "Write a short, friendly 3-item to-do list for someone whose goal "
        "today is 'learn the Cursor SDK'. Return only the list."
    )

    # Even a one-shot goes through the gate - you stay in control.
    if not approve(f'Send this to a Cursor agent:\n   "{task}"'):
        print("Cancelled. Nothing was sent.")
        return

    if demo:
        result = demo_prompt(task)
    else:
        try:
            result = Agent.prompt(
                task,
                AgentOptions(
                    api_key=api_key,
                    model=MODEL,
                    # Explicit local runtime against the sandbox folder.
                    local=LocalAgentOptions(cwd=str(WORKSPACE)),
                ),
            )
        except CursorAgentError as err:
            # Thrown = the run never started (auth/config/network).
            print(
                f"\nAgent failed to start: {err.message} "
                f"(retryable={err.is_retryable})",
                file=sys.stderr,
            )
            raise SystemExit(1)

    print(f"\nstatus: {result.status}\n")
    print(result.result)


if __name__ == "__main__":
    main()
