# Agent workspace

Agents run against this folder. **Approved output** lands in `output/` (gitignored).

| Path | Purpose |
|------|---------|
| `output/` | Job reports, cover letters, email summaries, resume copies |
| `output/archive/` | Older runs — safe to delete if you need space |
| `output/NEXT-STEPS.md` | **Start here** — today's apply list |
| `output/jobs-YYYY-MM-DD.md` | Job Scout report (live search + fit table) |
| `output/job-opportunities-YYYY-MM-DD.md` | Full Job Hunter report (matches + rank) |
| `output/job-email-summary-YYYY-MM-DD.md` | Latest morning Gmail scan |
| `fetch_dice_job.py` | Pull a Dice job description to stdout: `python fetch_dice_job.py <url>` |
| `plan.md` | Cursor Agent Lab lesson checklist (not job hunt) |

Morning automation (if registered): **JobEmailChecker 8:00**, **JobHunter 8:15** → see `scripts/register-morning-tasks.ps1`.
