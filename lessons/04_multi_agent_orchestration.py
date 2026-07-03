"""Lesson 4 - multiple agents working together.

Here we coordinate THREE separate agents, each with a role, and gate the
hand-offs so you approve every stage:

    planner  ->  worker(s)  ->  reviewer

- planner:  breaks a goal into a few concrete tasks
- worker:   drafts the output for one task (a fresh agent per task)
- reviewer: reads the drafts and gives combined feedback

This is the essence of multi-agent orchestration: your Python code is the
"conductor", the agents are the "players", and you approve each cue.

Run:  python lessons/04_multi_agent_orchestration.py
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (  # noqa: E402
    MODEL,
    WORKSPACE,
    approve,
    ask_text,
    banner,
    require_api_key,
)

from cursor_sdk import Agent, CursorAgentError, LocalAgentOptions  # noqa: E402


def new_agent(api_key: str):
    """Spin up a fresh, disposable local agent."""
    return Agent.create(
        model=MODEL,
        api_key=api_key,
        local=LocalAgentOptions(cwd=str(WORKSPACE)),
    )


def parse_tasks(text: str) -> list[str]:
    """Pull '1. ...' / '- ...' style lines out of the planner's answer."""
    tasks: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(?:\d+[.)]|[-*])\s+(.*)", line)
        if m and m.group(1):
            tasks.append(m.group(1).strip())
    return tasks


def main() -> None:
    banner("Lesson 4: multi-agent orchestration  (planner -> workers -> reviewer)")
    api_key = require_api_key()

    goal = ask_text("Goal for the agents to tackle?\n> ")
    if not goal:
        goal = "write a friendly launch announcement for a small side project"
        print(f"(using default goal: {goal})")

    try:
        # --- Stage 1: the PLANNER proposes tasks ---
        if not approve("Ask the PLANNER agent to break this into tasks?", default_yes=True):
            print("Cancelled.")
            return
        with new_agent(api_key) as planner:
            plan_text = planner.send(
                f"Break this goal into 2-3 small, independent writing tasks: {goal}. "
                "Return ONLY a numbered list, one task per line."
            ).text()
        print("\n--- planner proposed ---")
        print(plan_text)

        tasks = parse_tasks(plan_text) or [goal]

        # --- Stage 2: a WORKER drafts each approved task ---
        drafts: list[tuple[str, str]] = []
        for i, task in enumerate(tasks, start=1):
            if not approve(f"Task {i}/{len(tasks)}: have a WORKER agent draft:\n   \"{task}\""):
                print("   skipped.")
                continue
            with new_agent(api_key) as worker:
                draft = worker.send(
                    f"You are a focused worker. Produce a concise draft for this task: {task}. "
                    "Return only the deliverable."
                ).text()
            print(f"\n--- draft for task {i} ---")
            print(draft)
            drafts.append((task, draft))

        if not drafts:
            print("\nNo drafts produced. Done.")
            return

        # --- Stage 3: the REVIEWER critiques the combined work ---
        if approve("Send all drafts to a REVIEWER agent for feedback?", default_yes=True):
            combined = "\n\n".join(f"## {t}\n{d}" for t, d in drafts)
            with new_agent(api_key) as reviewer:
                feedback = reviewer.send(
                    "You are a kind but sharp reviewer. Give 3 bullet points of "
                    "feedback across these drafts, then one overall verdict:\n\n"
                    + combined
                ).text()
            print("\n--- reviewer feedback ---")
            print(feedback)

        print("\nDone. Three roles, three agents, you approved every hand-off.")

    except CursorAgentError as err:
        print(
            f"\nAn agent failed to start: {err.message} "
            f"(retryable={err.is_retryable})",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
