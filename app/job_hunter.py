"""Job hunter - a web-search scout that feeds a skills-matching agent team.

Flow (every step gated by `approve()` - nothing autonomous):

  1. SCOUT   agent  -> searches the web for CURRENT openings that match your
                       criteria (full-time / part-time / remote)
  2. MATCHER agents -> one per opportunity, scores fit against YOUR skill set
                       (matched skills, gaps, APPLY / MAYBE / SKIP)
  3. RANKER  agent  -> ranks the matches, recommends the top picks

Your skill profile is read from workspace/output/resume-and-cover-letter.md
when present; otherwise a built-in fallback is used.

Run:  python app/job_hunter.py
      python app/job_hunter.py --demo     (offline, no key, no cost)
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (  # noqa: E402
    MODEL,
    OUTPUT_DIR,
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

# Used only if resume-and-cover-letter.md isn't found in workspace/output/.
FALLBACK_PROFILE = (
    "Software engineer, 29 years in product development. Strong in C/C++ "
    "(embedded), Python, and JavaScript/Node.js. Embedded & IoT: ESP32, "
    "PlatformIO, Wi-Fi, sensors, mmWave radar. Linux & gateways: embedded "
    "Linux gateway development, device-to-cloud connectivity, edge gateway "
    "integration. Software & APIs: REST, OAuth 2.0, Express, production web "
    "services. Mission-critical experience (NASA contractor); 6 granted U.S. "
    "patents. Based in Sierra Vista, AZ; U.S. work authorized; open to remote."
)


def new_agent(api_key: str):
    """Fresh, disposable local agent (or a fake one in demo mode)."""
    if DEMO:
        return FakeAgent()
    return Agent.create(
        model=MODEL,
        api_key=api_key,
        local=LocalAgentOptions(cwd=str(WORKSPACE)),
    )


def load_profile() -> str:
    """Pull a skill profile from the saved resume, or fall back.

    Prefers the high-signal Summary + Technical Skills + Experience sections so
    the matchers see your real skills (not a mid-bullet truncation). Falls back
    to the whole file, then to FALLBACK_PROFILE.
    """
    resume = OUTPUT_DIR / "resume-and-cover-letter.md"
    try:
        text = resume.read_text(encoding="utf-8").strip()
    except OSError:
        return FALLBACK_PROFILE
    if not text:
        return FALLBACK_PROFILE
    # Cut off the cover-letter boilerplate so skills/experience dominate; the
    # cover letter is regenerated per-role anyway.
    for marker in ("\n## Cover Letter", "\n## Portal", "\n## Pre-export"):
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    return text.strip()


def parse_opportunities(text: str) -> list[str]:
    """Pull '1. ...' / '- ...' style lines out of the scout's answer."""
    found: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(?:\d+[.)]|[-*])\s+(.*)", line)
        if m and m.group(1).strip():
            found.append(m.group(1).strip())
    return found


def short_label(opp: str) -> str:
    """A compact 'Company | Role' label for prompts, from a pipe-delimited row."""
    parts = [p.strip() for p in opp.split("|") if p.strip()]
    label = " | ".join(parts[:2]) if parts else opp
    return label[:80]


def parse_score(verdict: str) -> int:
    """Pull the 'Fit score: N/100' number out of a matcher verdict (0 if none)."""
    m = re.search(r"fit score[^0-9]*(\d{1,3})\s*/\s*100", verdict, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def slugify(text: str, limit: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:limit] or "role").rstrip("-")


def scout_stage(api_key: str, profile: str, types: str, focus: str) -> list[str]:
    """SCOUT searches the web for openings; you approve before it runs."""
    if not approve("Send the SCOUT agent to search the web for openings?", default_yes=True):
        print("Cancelled.")
        return []
    prompt = (
        "You are a job-search scout WITH LIVE WEB ACCESS. Use web search now to "
        "find CURRENT, real, active job openings for this candidate.\n\n"
        f"Candidate profile:\n{profile}\n\n"
        f"Preferred employment types: {types}\n"
        f"Preferred roles / focus: {focus}\n"
        "Location: candidate is in Sierra Vista, AZ, USA and is open to REMOTE.\n\n"
        "Return 5-8 openings, ONE per line, numbered, in EXACTLY this format:\n"
        "N. Company | Role title | Type (full-time/part-time/remote) | "
        "Location or Remote | URL | one-line why it fits\n\n"
        "Only include real postings you can find via web search. If you cannot "
        "verify a posting's link, omit that row rather than inventing one."
    )
    with new_agent(api_key) as scout:
        result = scout.send(prompt).text()
    print("\n--- scout: opportunities found ---")
    print(result)
    print("----------------------------------")
    return parse_opportunities(result)


def match_stage(api_key: str, profile: str, opportunities: list[str]) -> list[tuple[str, str]]:
    """A MATCHER agent scores each opportunity against the skill set.

    Each opportunity is gated individually - press Enter to score it (default
    yes) or answer 'n' to skip that one.
    """
    scored: list[tuple[str, str]] = []
    for i, opp in enumerate(opportunities, start=1):
        if not approve(
            f"Score match {i}/{len(opportunities)}: {short_label(opp)}?",
            default_yes=True,
        ):
            print("   skipped.")
            continue
        prompt = (
            "You are a rigorous skills-match evaluator. Score how well this "
            "candidate fits the opportunity.\n\n"
            f"Candidate profile:\n{profile}\n\n"
            f"Opportunity:\n{opp}\n\n"
            "Return exactly:\n"
            "Fit score: N/100\n"
            "Matched skills: ...\n"
            "Gaps / missing: ...\n"
            "Verdict: APPLY | MAYBE | SKIP - one-line reason\n"
            "Be honest; do not inflate the score."
        )
        with new_agent(api_key) as matcher:
            verdict = matcher.send(prompt).text()
        print(f"\n--- match {i}/{len(opportunities)} ---")
        print(f"{opp}\n")
        print(verdict)
        print("-" * 30)
        scored.append((opp, verdict))
    return scored


def rank_stage(api_key: str, profile: str, scored: list[tuple[str, str]]) -> str:
    """RANKER ranks the matches and recommends the top picks."""
    if not scored or not approve(
        "Send all matches to the RANKER agent for a final shortlist?",
        default_yes=True,
    ):
        return ""
    combined = "\n\n".join(f"### {opp}\n{verdict}" for opp, verdict in scored)
    prompt = (
        "You are a hiring strategist for this candidate.\n\n"
        f"Candidate profile:\n{profile}\n\n"
        f"Evaluated opportunities:\n{combined}\n\n"
        "Rank them best-to-worst fit. Then recommend the TOP 3 to apply to "
        "first, each with a one-line reason. End with any red flags to watch."
    )
    with new_agent(api_key) as ranker:
        ranking = ranker.send(prompt).text()
    print("\n--- ranker: final shortlist ---")
    print(ranking)
    return ranking


def cover_letter_stage(
    api_key: str, profile: str, scored: list[tuple[str, str]], top_n: int = 3
) -> list[tuple[str, str]]:
    """Draft a tailored cover letter for the top-scoring picks; you gate each."""
    letters: list[tuple[str, str]] = []
    ranked = sorted(scored, key=lambda pair: parse_score(pair[1]), reverse=True)
    picks = [pair for pair in ranked if parse_score(pair[1]) > 0][:top_n]
    if not picks:
        return letters
    labels = ", ".join(short_label(opp) for opp, _ in picks)
    if not approve(
        f"Draft tailored cover letters for the top {len(picks)} picks "
        f"({labels})?",
        default_yes=True,
    ):
        return letters
    for i, (opp, verdict) in enumerate(picks, start=1):
        if not approve(
            f"Cover letter {i}/{len(picks)}: {short_label(opp)}?",
            default_yes=True,
        ):
            print("   skipped.")
            continue
        prompt = (
            "You are an expert cover-letter writer. Using ONLY the candidate's "
            "real background, write a concise, specific cover letter (about 200-"
            "250 words) tailored to this opportunity. Lead with the strongest "
            "matched skills and address the biggest gap honestly but positively. "
            "No invented experience. Return only the letter text.\n\n"
            f"Candidate profile:\n{profile}\n\n"
            f"Opportunity:\n{opp}\n\n"
            f"Match analysis (matched skills + gaps):\n{verdict}"
        )
        with new_agent(api_key) as writer:
            letter = writer.send(prompt).text()
        print(f"\n--- cover letter {i}/{len(picks)}: {short_label(opp)} ---")
        print(letter)
        print("-" * 30)
        letters.append((opp, letter))
        if approve("Save this cover letter?", default_yes=True):
            company = (opp.split("|")[0].strip() or "role")
            path = save_output(f"cover-letter-{slugify(company)}.md",
                               f"# Cover letter - {opp}\n\n{letter}\n")
            print(f"   saved -> {path}")
    return letters


def build_report(types: str, focus: str, scored: list[tuple[str, str]], ranking: str) -> str:
    parts = [
        f"# Job opportunities - {date.today().isoformat()}",
        "",
        f"**Employment types:** {types}",
        f"**Focus:** {focus}",
        "",
        "> Scout results come from live web search and can go stale - "
        "verify each posting and link before applying.",
        "",
        "## Evaluated opportunities",
        "",
    ]
    for i, (opp, verdict) in enumerate(scored, start=1):
        parts.append(f"### {i}. {opp}")
        parts.append("")
        parts.append(verdict)
        parts.append("")
    if ranking:
        parts.append("## Ranked shortlist")
        parts.append("")
        parts.append(ranking)
        parts.append("")
    return "\n".join(parts)


def main() -> None:
    banner("Job Hunter: web-search scout -> skills matchers -> ranker"
           + ("  [DEMO]" if DEMO else ""))
    print("Scout -> Matchers -> Ranker. You approve every step.\n")
    api_key = "demo" if DEMO else require_api_key()

    profile = load_profile()

    types = ask_text(
        "Employment types to target?\n"
        "(default: full-time, part-time, or remote)\n> "
    ) or "full-time, part-time, or remote"
    focus = ask_text(
        "Role focus / keywords?\n"
        "(default: software / embedded / firmware / IoT / backend)\n> "
    ) or "software engineer, embedded/firmware, IoT, Python/C++, backend/Node.js"

    try:
        opportunities = scout_stage(api_key, profile, types, focus)
        if not opportunities:
            print("\nNo opportunities found. Done.")
            return
        scored = match_stage(api_key, profile, opportunities)
        if not scored:
            print("\nNo matches scored. Done.")
            return
        ranking = rank_stage(api_key, profile, scored)
        cover_letter_stage(api_key, profile, scored)

        if approve("Save the full report?", default_yes=True):
            report = build_report(types, focus, scored, ranking)
            path = save_output(f"job-opportunities-{date.today().isoformat()}.md", report)
            print(f"\nSaved -> {path}")
        print(f"\nDone. Reports live in {WORKSPACE / 'output'}.")

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
