"""Lesson 3 - the human-in-the-loop pattern.

This is the core idea of the whole lab: an agent *proposes*, and you *decide*.
The agent first drafts a plan. You read it, then approve, deny, or hand it
revised instructions. The agent only "commits" (here: saves the plan to a
file) once you say yes.

No autonomy - the agent never takes the final step on its own.

Run:  python lessons/03_human_in_the_loop.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (  # noqa: E402
    MODEL,
    WORKSPACE,
    approve,
    ask_text,
    banner,
    require_api_key,
    save_output,
)

from cursor_sdk import Agent, CursorAgentError, LocalAgentOptions  # noqa: E402


def main() -> None:
    banner("Lesson 3: human-in-the-loop  (propose -> you decide)")
    api_key = require_api_key()

    goal = ask_text("What should we plan? (e.g. 'tidy my desk and inbox')\n> ")
    if not goal:
        goal = "spend 30 focused minutes learning the Cursor SDK"
        print(f"(using default goal: {goal})")

    try:
        with Agent.create(
            model=MODEL,
            api_key=api_key,
            local=LocalAgentOptions(cwd=str(WORKSPACE)),
        ) as agent:
            plan = ""
            # Loop: propose -> review -> (approve | revise | quit)
            while True:
                prompt = (
                    f"Propose a short, checkbox-style plan to: {goal}. "
                    "Keep it to 3-5 concrete steps. Return only the plan."
                )
                if plan:  # a revision round
                    hint = ask_text("How should the agent change it? > ")
                    prompt = (
                        f"Here is the previous plan:\n{plan}\n\n"
                        f"Revise it: {hint or 'make it simpler'}. Return only the plan."
                    )

                run = agent.send(prompt)
                plan = run.text()  # blocks on wait(), returns final text
                print("\n--- proposed plan ---")
                print(plan)
                print("---------------------")

                if approve("Accept this plan and save it?", default_yes=True):
                    path = save_output("plan.md", plan + "\n")
                    print(f"\nSaved to {path}")
                    break
                if not approve("Ask the agent to revise it?", default_yes=True):
                    print("Discarded. Nothing was saved.")
                    break

    except CursorAgentError as err:
        print(
            f"\nAgent failed to start: {err.message} "
            f"(retryable={err.is_retryable})",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
