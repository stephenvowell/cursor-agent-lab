# Case study: a human-in-the-loop, multi-agent job-search pipeline

**One evening, one operator, one API key.** This is a worked example of the
pattern I build for clients: a chain of AI agents that does the tedious research
and drafting, while a human approves every consequential step. It ran against a
real job search and produced real, submitted applications.

- **Repo:** [cursor-agent-lab](https://github.com/stephenvowell/cursor-agent-lab) · `app/job_hunter.py`, `app/career_copilot.py`
- **Stack:** Python, [Cursor SDK](https://cursor.com/docs/sdk/python) (multi-agent orchestration), live web search, Tkinter desktop UI
- **Design rule:** the agents draft; the human decides. Nothing is sent or saved without a `y`.

---

## The problem

Applying to engineering roles is a repetitive research-and-writing loop: find
live postings, read each one, honestly judge fit against a specific background,
rank them, and write a tailored cover letter for the best ones. Done well it
takes hours per sitting; done fast it gets sloppy and generic.

The goal was **not** "auto-apply to everything" — that produces spam and burns
reputation. The goal was to compress the *research and drafting* while keeping a
person in control of every judgment call and every submission.

## The approach — four agent roles, one operator

The pipeline (`app/job_hunter.py`) coordinates several specialized agents, each
gated by an approval prompt:

1. **Scout** — searches the live web for current openings (full-time, part-time,
   remote) in the target domains.
2. **Matchers** — score each posting against a real skill profile, producing a
   fit score plus an honest, itemized list of *matched skills* and *gaps*.
3. **Ranker** — turns the scored set into a shortlist with a clear "apply first"
   recommendation.
4. **Writer** — drafts a tailored cover letter for each top pick, referencing the
   specific role and stating gaps truthfully.

The operator reviews each stage in an embedded console (`app/career_copilot.py`)
and answers `y`/`n` — accept the plan, redo it, draft this one, save that one.

## What was automated vs. what stayed human

| Automated (agents) | Kept human (on purpose) |
|---|---|
| Live posting discovery | Final decision to apply |
| Fit scoring + gap analysis | Editing any claim before it's sent |
| Ranking + shortlist | Résumé/file uploads |
| Cover-letter drafts | reCAPTCHA and account creation |
| Summaries saved to disk | Clicking "submit" |

This split is the whole point. The un-automatable, high-stakes, or trust-sensitive
steps (uploads, CAPTCHAs, the actual submit) are left to the human — by design,
not by limitation.

## Results (single real run)

- **8** live roles discovered and evaluated end-to-end.
- Fit scored **43–74/100** with itemized matched-skills / gaps for each — e.g. a
  senior firmware role scored **74** for near-direct domain overlap, correctly
  flagging radar-DSP and OTA as the interview risks.
- Ranked shortlist with a defensible **top 3**.
- Tailored cover letters drafted for the picks, each stating real gaps honestly.
- **5 applications submitted** the same day (with the human doing uploads and
  final submit); 1 role had closed, 1 required manual account creation behind a
  cross-domain iframe.

The agents turned "an evening of research and writing" into a **reviewed queue**
the operator could clear quickly — without sending anything they hadn't read.

## Honest limitations

- **Web results go stale** — every posting and link is verified before applying.
- **Some steps can't (and shouldn't) be automated** — file uploads, CAPTCHAs, and
  account creation stay manual.
- **The model can be wrong** — which is exactly why a human approves each step and
  edits drafts before they're used.

## Why this transfers to your business

Swap "job postings" for **the repetitive research-and-drafting loop in any
business** and the same architecture applies:

- **Sales** — research leads, score fit, draft tailored outreach → you approve/send.
- **Ops** — triage inbound tickets/emails, draft responses → a person confirms.
- **Reporting** — gather inputs, draft the weekly/board report → an owner signs off.

The reusable spine for this is published as
[workflow-app-starter](https://github.com/stephenvowell/workflow-app-starter):
define the steps, wire in the client's systems (Gmail, a CRM, a database) as tool
integrations, and ship a desktop app a non-coder can run — with the approval gate
kept firmly on.

---

*Built by [Stephen Vowell](https://stephenv.net). Interested in automating a
workflow like this? [Get in touch](https://stephenv.net/#contact).*
