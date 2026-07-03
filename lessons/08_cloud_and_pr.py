"""Lesson 8 - cloud runtime: fire-and-forget agents that open real PRs.

Local agents (lessons 1-7) run on YOUR machine against a folder. Cloud agents
run on a Cursor-hosted VM against a freshly CLONED copy of a real repo. That's
the shape of true unattended automation: a schedule or webhook kicks off an
agent, it works on a VM, and it can open a pull request when it's done - no
human machine involved.

Runtime is chosen by which option you pass to Agent.create:
    local=LocalAgentOptions(...)   -> your machine
    cloud=CloudAgentOptions(...)   -> Cursor VM against cloned repo(s)

SAFETY: this lesson defaults to a READ-ONLY cloud run (clone, read, summarize -
no commits, no branch, no PR). Only when you pass `--pr` does it make a tiny
one-file change and open a REAL pull request on your GitHub repo (with
`auto_create_pr=True`). The PR is gated behind an extra confirmation.

The repo is auto-detected from `git remote origin`. It must be connected to
your Cursor account (see `Cursor.repositories.list()`); this repo already is.

Run:  python lessons/08_cloud_and_pr.py           (safe: read-only cloud run)
      python lessons/08_cloud_and_pr.py --pr       (opens a REAL PR - confirmed)
      add --demo for the offline, no-cost walkthrough
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (  # noqa: E402
    MODEL,
    PROJECT_ROOT,
    approve,
    banner,
    demo_enabled,
    require_api_key,
    stream_text,
)

from cursor_sdk import (  # noqa: E402
    Agent,
    AgentOptions,
    CloudAgentOptions,
    CloudRepository,
    CursorAgentError,
)

FALLBACK_REPO = "https://github.com/stephenvowell/cursor-agent-lab"

READ_ONLY_TASK = (
    "Read this repository and summarize what it does in 3 short bullet points. "
    "This is a read-only task: do NOT modify, create, or delete any files, and "
    "do not commit anything."
)

PR_TASK = (
    "Create a new file at `docs/cloud-hello.md` containing exactly one line: a "
    f"friendly one-sentence greeting from a Cursor cloud agent that includes "
    f"today's date ({date.today().isoformat()}). Make ONLY this single-file "
    "change - do not touch anything else."
)


def detect_repo_url() -> str:
    """Repo URL from `git remote origin`, normalized to match connected repos."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=str(PROJECT_ROOT), text=True,
        ).strip()
        return url[:-4] if url.endswith(".git") else url
    except Exception:  # noqa: BLE001
        return FALLBACK_REPO


def report_branches(result) -> None:
    """Print branch + PR info the cloud run produced, if any."""
    git = getattr(result, "git", None)
    branches = getattr(git, "branches", None) or []
    # Keep only entries that actually carry a branch name or PR link; a
    # read-only run reports a placeholder entry with both empty.
    meaningful = [
        b for b in branches
        if (getattr(b, "branch", "") or "").strip()
        or (getattr(b, "pr_url", "") or "").strip()
    ]
    if not meaningful:
        print("\n(no branch/PR was created - expected for a read-only run.)")
        return
    for b in meaningful:
        print(f"\n  branch:  {getattr(b, 'branch', '?')}")
        pr = getattr(b, "pr_url", None)
        print(f"  PR:      {pr}" if pr else "  PR:      (none opened)")


def demo_run(want_pr: bool) -> None:
    task = PR_TASK if want_pr else READ_ONLY_TASK
    print(f"\nWould create a CLOUD agent against {FALLBACK_REPO}")
    print(f"auto_create_pr={want_pr}\n\nTask:\n   {task}\n")
    print("--- streamed run (simulated) ---")
    if want_pr:
        print("Created docs/cloud-hello.md and committed it.")
        print("\n  branch:  cursor/cloud-hello-1234")
        print("  PR:      https://github.com/stephenvowell/cursor-agent-lab/pull/42")
    else:
        print("- A hands-on lab of Cursor SDK lessons (local + cloud agents)\n"
              "- A Gmail job-email automation\n"
              "- Job-application drafts and resume tooling")
        print("\n(no branch/PR - read-only run.)")
    print("\n(demo note: a real run clones the repo on a Cursor VM and executes there.)")


def main() -> None:
    demo = demo_enabled()
    want_pr = "--pr" in sys.argv
    banner("Lesson 8: cloud runtime + PR" + ("  [PR MODE]" if want_pr else "")
           + ("  [DEMO]" if demo else ""))

    if demo:
        demo_run(want_pr)
        return

    api_key = require_api_key()
    repo_url = detect_repo_url()
    task = PR_TASK if want_pr else READ_ONLY_TASK

    print(f"\nRepo:  {repo_url}")
    print(f"Mode:  {'OPEN A REAL PR' if want_pr else 'read-only (no changes)'}")

    if want_pr:
        print("\n!! --pr will run a cloud agent that COMMITS a file and opens a")
        print("!! real pull request on the repo above.")
        if not approve("Really open a real PR?", default_yes=False):
            print("Cancelled. (Run without --pr for the safe read-only version.)")
            return
    else:
        if not approve(
            f"Start a read-only CLOUD agent against {repo_url}?", default_yes=True
        ):
            print("Cancelled.")
            return

    options = AgentOptions(
        api_key=api_key,
        model=MODEL,
        cloud=CloudAgentOptions(
            repos=[CloudRepository(url=repo_url, starting_ref="main")],
            auto_create_pr=want_pr,
            # Don't page yourself as reviewer on an automated PR.
            skip_reviewer_request=True if want_pr else None,
        ),
    )

    print("\nLaunching cloud agent (clones the repo on a Cursor VM; this can "
          "take a few minutes)...")
    try:
        with Agent.create(options) as agent:
            # A cloud id starts with 'bc-' - that's how resume/get auto-route it.
            print(f"(agent={agent.agent_id})\n--- streamed run ---")
            run = agent.send(task)
            stream_text(run)
            result = run.wait()
            print(f"\nstatus: {result.status}")
            report_branches(result)
            print(f"\nView it later: Agent.resume(\"{agent.agent_id}\") "
                  "or client.agents.list(runtime=\"cloud\").")
    except CursorAgentError as err:
        print(
            f"\nCloud agent failed to start: {err.message} "
            f"(retryable={err.is_retryable})\n"
            "Common causes: repo not connected to your Cursor account, or the "
            "starting_ref doesn't exist.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nInterrupted. The cloud agent may still be running - check "
              "client.agents.list(runtime=\"cloud\").")


if __name__ == "__main__":
    main()
