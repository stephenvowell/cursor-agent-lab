"""Multi-agent daily task assistant (capstone).

Give it a goal for the day. Then:

  1. a PLANNER agent proposes a task list   -> you approve or re-plan
  2. for each task, a WORKER agent drafts it -> you approve, optionally save
  3. a REVIEWER agent wraps up the day       -> you approve

Every agent step is gated by `approve()`. The assistant drafts; you decide.
Approved drafts are saved under workspace/output/.

Run:  python app/task_assistant.py
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (  # noqa: E402
    MODEL,
    WORKSPACE,
    FakeAgent,
    approve,
    ask_text,
    banner,
    demo_enabled,
    require_api_key,
    save_output,
)

from cursor_sdk import Agent, CursorAgentError, LocalAgentOptions  # noqa: E402

DEMO = demo_enabled()


def new_agent(api_key: str):
    if DEMO:
        return FakeAgent()
    return Agent.create(
        model=MODEL,
        api_key=api_key,
        local=LocalAgentOptions(cwd=str(WORKSPACE)),
    )


def parse_tasks(text: str) -> list[str]:
    tasks: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(?:\d+[.)]|[-*])\s+(.*)", line)
        if m and m.group(1):
            tasks.append(m.group(1).strip())
    return tasks


def slugify(text: str, limit: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:limit] or "task").rstrip("-")


def plan_stage(api_key: str, goal: str) -> list[str]:
    """PLANNER proposes tasks; you accept or ask for a re-plan."""
    with new_agent(api_key) as planner:
        hint = ""
        while True:
            prompt = (
                f"You are a planning assistant. Turn this daily goal into a short, "
                f"realistic task list (2-5 items): {goal}. "
                "Return ONLY a numbered list, one task per line."
            )
            if hint:
                prompt += f" Adjust the plan: {hint}."
            plan_text = planner.send(prompt).text()
            print("\n--- proposed tasks ---")
            print(plan_text)
            print("----------------------")

            if approve("Accept this task list?", default_yes=True):
                return parse_tasks(plan_text) or [goal]
            if not approve("Ask the planner to try again?", default_yes=True):
                return []
            hint = ask_text("What should change? > ")


def work_stage(api_key: str, tasks: list[str]) -> list[tuple[str, str]]:
    """A WORKER drafts each approved task; you can save the draft."""
    done: list[tuple[str, str]] = []
    for i, task in enumerate(tasks, start=1):
        if not approve(f"Task {i}/{len(tasks)}: draft \"{task}\"?"):
            print("   skipped.")
            continue
        with new_agent(api_key) as worker:
            draft = worker.send(
                f"You are a focused worker. Produce a concise, ready-to-use draft "
                f"for this task: {task}. Return only the deliverable."
            ).text()
        print(f"\n--- draft: {task} ---")
        print(draft)
        print("-" * 30)

        if approve("Save this draft?", default_yes=True):
            path = save_output(f"{i:02d}-{slugify(task)}.md", f"# {task}\n\n{draft}\n")
            print(f"   saved -> {path}")
        done.append((task, draft))
    return done


def review_stage(api_key: str, done: list[tuple[str, str]]) -> None:
    """REVIEWER summarizes the day's work."""
    if not done or not approve("Have the reviewer summarize the day?", default_yes=True):
        return
    combined = "\n\n".join(f"## {t}\n{d}" for t, d in done)
    with new_agent(api_key) as reviewer:
        summary = reviewer.send(
            "You are an encouraging end-of-day reviewer. In 3-4 bullets, summarize "
            "what got done and suggest one thing to pick up tomorrow:\n\n" + combined
        ).text()
    print("\n--- end-of-day summary ---")
    print(summary)
    if approve("Save the summary?", default_yes=True):
        path = save_output("00-summary.md", summary + "\n")
        print(f"   saved -> {path}")


def main() -> None:
    banner("Multi-agent Daily Task Assistant" + ("  [DEMO]" if DEMO else ""))
    print("Planner -> Workers -> Reviewer. You approve every step.\n")
    api_key = "demo" if DEMO else require_api_key()

    goal = ask_text("What do you want to get done today?\n> ")
    if not goal:
        print("No goal given - nothing to do. Bye!")
        return

    try:
        tasks = plan_stage(api_key, goal)
        if not tasks:
            print("No plan accepted. Stopping.")
            return
        done = work_stage(api_key, tasks)
        if not done:
            print("\nNo drafts produced.")
            return
        review_stage(api_key, done)
        print(f"\nAll set. Drafts are in {WORKSPACE / 'output'}.")
    except CursorAgentError as err:
        print(
            f"\nAn agent failed to start: {err.message} "
            f"(retryable={err.is_retryable})",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nInterrupted. Nothing further was sent.")


if __name__ == "__main__":
    main()
