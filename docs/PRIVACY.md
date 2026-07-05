# Career Copilot — privacy & data

## Summary

**Your job search data stays on your computer.** Career Copilot is a local desktop app. We (the seller) do not operate a server that stores your résumé, applications, or email.

## What runs locally

- Résumé and reports: `workspace/output/` on your machine
- License file: `license.json` (license key + trial expiry only)
- API key: `.env` file (your Cursor API key — **never share this**)
- Gmail OAuth: `credentials.json` + `token.json` (if you use Email Check)

## What leaves your machine

| Service | Data sent | Why |
|---------|-----------|-----|
| **Cursor API** | Prompts containing résumé excerpts, job text, your yes/no workflow | Agent scout/match/rank/cover stages |
| **Google Gmail API** | Read-only inbox search for job-related mail | Email Check feature only |
| **Job boards** | HTTP requests when fetchers load posting URLs | Real job description text |

Career Copilot does **not** auto-submit applications. You click Apply on LinkedIn, Indeed, or company sites yourself.

## What we don’t collect

- No telemetry bundled in the open-source lab repo by default
- No account on stephenv.net required to use the app
- License keys are validated **offline** (checksum format only)

## Your responsibilities

- Keep `.env`, `credentials.json`, and `token.json` private
- Use your own Cursor API key and monitor usage on Cursor’s dashboard
- Verify job URLs before applying — scout results can go stale

## Open source

The underlying patterns are published in [cursor-agent-lab](https://github.com/stephenvowell/cursor-agent-lab) for transparency. The retail **CareerCopilot.exe** pack is the supported product build.

---

Last updated: 2026-07-05
