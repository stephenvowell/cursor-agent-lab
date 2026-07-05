# Career Copilot — product overview

![Career Copilot — roles table, Job Scout + Hunter, yes/no workflow](../assets/career-copilot-demo.png)

**Human-in-the-loop job search desk.** Scout live boards, score fit against *your* résumé, rank picks, draft cover letters — you only say **Yes** or **No**.

Built by [Stephen Vowell](https://stephenv.net) · [GitHub](https://github.com/stephenvowell/cursor-agent-lab)

---

## Who it’s for

- **Senior contractors** (embedded, firmware, IoT, health tech) who want speed without spam-applying
- **Career coaches** white-labeling a research + drafting pipeline for clients
- **Anyone** who wants agents to *propose* and a human to *decide*

## What you get

| Feature | Detail |
|---------|--------|
| **Job Scout + Hunter** | LinkedIn/Indeed seeds → live search → fit table → matchers → ranker → cover letters |
| **Roles table** | Fit, company, role, URL — open postings in one click |
| **Email Check** | Gmail scan for interview/rejection/recruiter mail (read-only OAuth) |
| **Task Assistant** | Daily planning with the same yes/no approval model |
| **Local artifacts** | Markdown reports in `workspace/output/` — your data stays on your machine |
| **Demo mode** | Try the full pipeline offline before spending API credits |

## Pricing (suggested launch)

| Tier | Price | Includes |
|------|-------|----------|
| **Trial** | Free 14 days | Key: `CCOP-TRIAL` — full features, local only |
| **Personal** | **$79** one-time | Lifetime license for one user / one machine |
| **Coach / Agency** | **$299** | 5 license keys + setup call (1 hr) |
| **Cursor API** | Pass-through | Customer brings their own [Cursor API key](https://cursor.com/dashboard/integrations) |

*Adjust on Gumroad/Lemon Squeezy when you list it.*

## How to sell it

1. **List** on Gumroad or Lemon Squeezy — deliver `CareerCopilot.zip` (contents of `bin/` after build).
2. **Email** the license key from `python scripts/generate-license.py`.
3. **Point** buyers to [docs/PRIVACY.md](PRIVACY.md) and setup steps below.

## Customer setup (3 steps)

1. Unzip → run **CareerCopilot.exe**
2. **Setup** wizard: license key → Cursor API key → import résumé (`.md`)
3. Click **Job Scout + Hunter** → Yes/No through the pipeline

## Build the retail package (you)

```powershell
cd cursor-agent-lab
.\scripts\build-career-copilot.ps1
```

Output:

- `bin/CareerCopilot.exe` — GUI launcher
- `bin/pack/` — toolkit + venv (job hunter, fetchers, config)
- Desktop **myApps** shortcut

Generate license keys:

```powershell
python scripts/generate-license.py --count 5
```

## Positioning (one line)

> **Not auto-apply spam.** A scout, matcher, and writer on retainer — you’re the hiring manager.

## Roadmap (paid updates)

- One-click LinkedIn/Indeed apply prep (still human submits)
- Profile wizard (no YAML)
- Optional cloud sync (encrypted) for multi-device coaches

---

Questions: [stephenv.net](https://stephenv.net) · GitHub issues for bugs in the open-source lab repo.
