"""Job Scout — scout prompt, parsing, validation, and progress (used by Job Hunter)."""

from __future__ import annotations

import json
import re
import threading
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yaml"
SCOUT_JSON_NAME = "scout-latest.json"
MIN_ROLES = 3
MAX_SCOUT_RETRIES = 2

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


def _format_fetched_postings(postings: list[dict]) -> str:
    if not postings:
        return ""
    blocks: list[str] = [
        "## Verified seed postings (full descriptions fetched — score these first)\n"
    ]
    for i, post in enumerate(postings, start=1):
        company = post.get("company") or "Unknown"
        note = post.get("note") or ""
        url = post.get("url") or ""
        desc = post.get("description") or ""
        blocks.append(f"### Seed {i}: {company} {note}".strip())
        blocks.append(f"URL: {url}\n")
        blocks.append(desc)
        blocks.append("")
    return "\n".join(blocks)


def build_scout_prompt(
    profile: str,
    types: str,
    focus: str,
    *,
    fetched_postings: list[dict] | None = None,
) -> str:
    today = date.today().isoformat()
    config = load_sources_config()
    seeds_block = _format_fetched_postings(fetched_postings or [])
    seeds_instruction = (
        "Include every seed posting above in your table (LinkedIn/Indeed seeds are search "
        "pages — follow to individual job URLs). "
        "Then add more roles from live web search if needed.\n"
        if seeds_block
        else "Prioritize LinkedIn Jobs and Indeed for US remote embedded/firmware roles.\n"
    )
    return f"""You are Job Scout with LIVE WEB ACCESS. Use web search now.

Today's date: {today}

## Candidate profile
{profile}

## Search parameters
Employment types: {types}
Role focus / keywords: {focus}
Location: Sierra Vista, AZ, USA — open to REMOTE US roles.

{seeds_block}

## Sources and keywords (prioritize priority 1–3 boards)
{config}

## Task
1. Search the live web for current job postings matching the profile.
2. {seeds_instruction}Score each role 0–100 (honest gaps, do not inflate).
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


def build_scout_retry_prompt(previous: str) -> str:
    return (
        "Your previous reply was NOT a parseable markdown table with at least "
        f"{MIN_ROLES} data rows.\n\n"
        f"Previous reply:\n{previous[:2000]}\n\n"
        "Try again. Return ONLY the markdown document. The table MUST have header:\n"
        "| Rank | Fit | Company | Role | Type | Remote | URL | Matched | Gaps |\n"
        "with numbered rank rows (1, 2, 3…) and real URLs."
    )


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
        matched = cols[7] if len(cols) > 7 else ""
        gaps = cols[8] if len(cols) > 8 else ""
        rows.append(
            f"{company} | {role} | {typ} | {remote} | {url} | fit {fit}/100"
            + (f" | matched: {matched}" if matched else "")
            + (f" | gaps: {gaps}" if gaps else "")
        )
    return rows


def parse_table_to_roles(text: str) -> list[dict]:
    roles: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 7 or cols[0].lower() in ("rank", "#") or not cols[0].isdigit():
            continue
        roles.append(
            {
                "rank": int(cols[0]),
                "fit": int(cols[1]) if cols[1].isdigit() else cols[1],
                "company": cols[2],
                "role": cols[3],
                "type": cols[4],
                "remote": cols[5],
                "url": cols[6],
                "matched": cols[7] if len(cols) > 7 else "",
                "gaps": cols[8] if len(cols) > 8 else "",
            }
        )
    return roles


def parse_opportunities(text: str) -> list[str]:
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


def extract_url_from_opp(opp: str) -> str | None:
    for part in opp.split("|"):
        p = part.strip()
        if p.lower().startswith("http://") or p.lower().startswith("https://"):
            return p
    m = re.search(r"https?://\S+", opp)
    return m.group(0).rstrip(").,") if m else None


def write_scout_json(text: str, output_dir: Path) -> Path:
    """Write scout-latest.json and print GUI bridge line."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / SCOUT_JSON_NAME
    payload = {
        "date": date.today().isoformat(),
        "roles": parse_table_to_roles(text),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"@@SCOUT_JSON {path}", flush=True)
    return path


def send_with_progress(agent, prompt: str) -> str:
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


def run_scout_agent(agent, prompt: str) -> str:
    """Run scout with validate/retry until table parses or retries exhausted."""
    result = send_with_progress(agent, prompt)
    for attempt in range(MAX_SCOUT_RETRIES):
        opps = parse_opportunities(result)
        if len(opps) >= MIN_ROLES:
            return result
        print(
            f"\n   Scout output had {len(opps)} parseable role(s); "
            f"retrying ({attempt + 1}/{MAX_SCOUT_RETRIES})…",
            flush=True,
        )
        result = send_with_progress(agent, build_scout_retry_prompt(result))
    return result


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
