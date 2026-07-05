"""Job Scout — scout prompt, parsing, and progress (used by Job Hunter).

Merged from the standalone job-scout project: live web search using
config/sources.yaml, markdown table output, heartbeat while the agent runs.
"""

from __future__ import annotations

import re
import threading
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yaml"

DEFAULT_TYPES = "contract preferred; full-time, part-time, remote US"
DEFAULT_FOCUS = (
    "embedded, firmware, IoT, ESP32, health tech, wearable, "
    "connectivity, contract, remote US"
)


def load_sources_config() -> str:
    try:
        return CONFIG_PATH.read_text(encoding="utf-8")
    except OSError:
        return "# sources.yaml not found — search broadly for remote embedded/IoT roles\n"


def build_scout_prompt(profile: str, types: str, focus: str) -> str:
    today = date.today().isoformat()
    config = load_sources_config()
    return f"""You are Job Scout with LIVE WEB ACCESS. Use web search now.

Today's date: {today}

## Candidate profile
{profile}

## Search parameters
Employment types: {types}
Role focus / keywords: {focus}
Location: Sierra Vista, AZ, USA — open to REMOTE US roles.

## Sources and keywords (prioritize priority 1–3 boards)
{config}

## Task
1. Search the live web for current job postings matching the profile.
2. Score each role 0–100 (honest gaps, do not inflate).
3. Return ONLY a markdown document with:

# Job scout — {today}

**Search focus:** (one line)

| Rank | Fit | Company | Role | Type | Remote | URL | Matched | Gaps |
|------|-----|---------|------|------|--------|-----|---------|------|
(one row per role, 5–10 roles, fit >= 50 only)

## Apply first
(top 3 with one sentence each)

## Skipped (why)
(brief list)

## Next step
(one line for the human)

Use REAL postings with verifiable URLs. Do not invent companies or links.
Also include a numbered list after the table, ONE line per role:
N. Company | Role title | Type | Remote | URL | fit N/100
"""


def parse_table_rows(text: str) -> list[str]:
    rows: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 7:
            continue
        if cols[0].lower() in ("rank", "#"):
            continue
        if not cols[0].isdigit():
            continue
        company = cols[2]
        role = cols[3]
        typ = cols[4]
        remote = cols[5]
        url = cols[6]
        fit = cols[1]
        rows.append(
            f"{company} | {role} | {typ} | {remote} | {url} | fit {fit}/100"
        )
    return rows


def parse_opportunities(text: str) -> list[str]:
    """Parse scout output: markdown table first, then numbered lines."""
    from_table = parse_table_rows(text)
    if from_table:
        return from_table

    found: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(?:\d+[.)]|[-*])\s+(.*)", line)
        if m and m.group(1).strip():
            found.append(m.group(1).strip())
    return found


def send_with_progress(agent, prompt: str) -> str:
    """Call agent.send and print heartbeat lines while waiting (1–3 min typical)."""
    stop = threading.Event()

    def heartbeat() -> None:
        elapsed = 0
        while not stop.wait(15):
            elapsed += 15
            print(
                f"   … still searching ({elapsed}s) — live web search can take 1–3 min",
                flush=True,
            )

    print("Calling Cursor agent (live web search)…", flush=True)
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        return agent.send(prompt).text()
    finally:
        stop.set()


def demo_scout_markdown() -> str:
    today = date.today().isoformat()
    return f"""# Job scout — {today}

**Search focus:** [DEMO] embedded IoT contract remote US

| Rank | Fit | Company | Role | Type | Remote | URL | Matched | Gaps |
|------|-----|---------|------|------|--------|-----|---------|------|
| 1 | 76 | Example Health IoT Inc. | Senior Embedded Engineer | Contract | Yes | https://example.com/jobs/1 | ESP32, IoT, C/C++ | No production Matter |
| 2 | 71 | Demo Wearables Co. | Firmware Engineer | Contract | Yes | https://example.com/jobs/2 | UART, Wi-Fi, sensors | Rust in JD |
| 3 | 68 | Sample MedTech Startup | Founding Embedded Engineer | FTE | Yes | https://example.com/jobs/3 | Prototype shipping | Equity-stage startup |

## Apply first
1. Example Health IoT Inc. — strongest firmware overlap.
2. Demo Wearables Co. — connectivity-focused contract.
3. Sample MedTech Startup — health-adjacent founding role.

## Skipped (why)
- Generic full-stack-only roles below threshold.

## Next step
Review top 3; matchers will score each against your résumé next.

1. Example Health IoT Inc. | Senior Embedded Engineer | Contract | Yes | https://example.com/jobs/1 | fit 76/100
2. Demo Wearables Co. | Firmware Engineer | Contract | Yes | https://example.com/jobs/2 | fit 71/100
3. Sample MedTech Startup | Founding Embedded Engineer | FTE | Yes | https://example.com/jobs/3 | fit 68/100
"""
