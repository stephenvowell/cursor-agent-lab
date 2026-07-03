# Cursor Agent Lab

A hands-on, **you-stay-in-control** playground for learning the [Cursor SDK](https://cursor.com/docs/sdk/python) —
how to run and coordinate **multiple Cursor agents** from your own Python code.

Nothing here runs autonomously. Every agent action passes through an
approval gate (`approve()` in `shared/`), so *you* decide what happens and
when. That's the whole point: learn the machinery while keeping your hands
on the wheel.

## What you'll learn

| Lesson | File | Concept |
|--------|------|---------|
| 1 | `lessons/01_one_shot.py` | One agent, one shot — `Agent.prompt(...)` |
| 2 | `lessons/02_streaming_followup.py` | A durable agent, streaming output + follow-ups — `Agent.create` / `agent.send` |
| 3 | `lessons/03_human_in_the_loop.py` | The approval-gate pattern: agent proposes, you approve/deny/edit |
| 4 | `lessons/04_multi_agent_orchestration.py` | **Multiple agents** working together: planner → workers → reviewer |

Then the capstone:

- `app/task_assistant.py` — an interactive **multi-agent daily-task assistant**.
  You give it a goal; a *planner* agent proposes tasks (you approve/edit),
  *worker* agents draft each one (you approve, optionally save), and a
  *reviewer* agent wraps up. Multiple agents, human-in-the-loop throughout.

## Prerequisites

- **Python 3.9+**
- A **Cursor API key** — create one at
  [cursor.com/dashboard/integrations](https://cursor.com/dashboard/integrations).

## Setup

```powershell
# from the project folder
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # PowerShell
pip install -r requirements.txt

# add your key
copy .env.example .env              # then edit .env and paste your key
# ...or set it for the session:
$env:CURSOR_API_KEY = "cursor_your_key_here"
```

## Run

```powershell
python lessons/01_one_shot.py
python lessons/02_streaming_followup.py
python lessons/03_human_in_the_loop.py
python lessons/04_multi_agent_orchestration.py

python app/task_assistant.py
```

Each script prints what it's *about* to do and waits for your `y`/`n`.
Answer `n` and nothing is sent.

## The "not autonomous" design

- **`approve()` gates every send.** The agents never act until you say yes.
- **Local runtime, sandboxed `cwd`.** Agents run against the `workspace/`
  folder, not your real projects, so experiments stay contained.
- **Drafts, not actions.** The task assistant produces text you review;
  saving output is a separate, explicit approval.

## Key SDK concepts (cheat sheet)

- `Agent.prompt(prompt, options)` — one-shot; sends, waits, disposes itself.
- `Agent.create(...)` + `agent.send(...)` — durable agent with streaming and
  multi-turn follow-ups. Always `run.wait()`; dispose with `with ... as agent:`.
- `Agent.resume(id, ...)` — pick an existing agent back up later.
- Two failure modes: a thrown `CursorAgentError` = the run never started
  (auth/config/network); a returned `result.status == "error"` = it ran and
  failed. Handle them differently.

See the [Python SDK docs](https://cursor.com/docs/sdk/python) for the full reference.

## Layout

```
cursor-agent-lab/
├─ README.md
├─ requirements.txt
├─ .env.example
├─ shared/__init__.py        # api-key check, approval gate, streaming helper
├─ lessons/                  # progressive, runnable examples
│  ├─ 01_one_shot.py
│  ├─ 02_streaming_followup.py
│  ├─ 03_human_in_the_loop.py
│  └─ 04_multi_agent_orchestration.py
├─ app/task_assistant.py     # multi-agent capstone
└─ workspace/                # sandbox the agents run against (gitignored output)
```
