"""Job hunter — Job Scout + skills matchers + ranker + cover letters.

Flow (every step gated by `approve()` — you only say yes/no in Career Copilot):

  1. JOB SCOUT  -> live web search (Interrupt, Arc, Wellfound, …) + fit table
  2. MATCHER    -> one per opportunity, scores fit against your résumé
  3. RANKER     -> ranks matches, recommends top picks
  4. COVER      -> tailored letters for top roles (optional)

Profile: workspace/output/resume-and-cover-letter.md (fallback if missing).
Scout report: workspace/output/jobs-YYYY-MM-DD.md

Run:  python app/job_hunter.py
      python app/job_hunter.py --demo
      python app/job_hunter.py --unattended
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from job_scout import (  # noqa: E402
    DEFAULT_FOCUS,
    DEFAULT_TYPES,
    build_scout_prompt,
    demo_scout_markdown,
    parse_opportunities,
    send_with_progress,
)
from shared import (  # noqa: E402
    MODEL,
    OUTPUT_DIR,
    WORKSPACE,
    FakeAgent,
    approve,
    ask_text,
    banner,
    configure_utf8_stdio,
    demo_enabled,
    notify_desktop,
    require_api_key,
    save_output,
    unattended_enabled,
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


def scout_stage(api_key: str, profile: str, types: str, focus: str) -> list[str]:
    """Job Scout — live web search; you approve before it runs."""
    if not approve(
        "Send Job Scout to search live job boards (Interrupt, Arc, Wellfound, …)?",
        default_yes=True,
    ):
        print("Cancelled.")
        return []
    prompt = build_scout_prompt(profile, types, focus)
    if DEMO:
        result = demo_scout_markdown()
    else:
        with new_agent(api_key) as scout:
            result = send_with_progress(scout, prompt)
    scout_path = OUTPUT_DIR / f"jobs-{date.today().isoformat()}.md"
    scout_path.write_text(result, encoding="utf-8")
    print(f"\nSaved scout report -> {scout_path}")
    print("\n--- Job Scout: opportunities found ---")
    print(result)
    print("--------------------------------------")
    opps = parse_opportunities(result)
    if not opps:
        print("(No parseable rows in scout output — review report above.)")
    return opps


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
    configure_utf8_stdio()
    unattended = unattended_enabled()
    banner(
        "Job Hunter: Job Scout -> matchers -> ranker -> cover letters"
        + ("  [DEMO]" if DEMO else "")
        + ("  [UNATTENDED]" if unattended else "")
    )
    print(
        "Job Scout -> Matchers -> Ranker."
        + (" Auto-approving every step.\n" if unattended else " You approve every step (yes/no).\n")
    )
    api_key = "demo" if DEMO else require_api_key()

    profile = load_profile()

    types = ask_text(
        "Employment types to target?\n"
        f"(default: {DEFAULT_TYPES})\n> "
    ) or DEFAULT_TYPES
    focus = ask_text(
        "Role focus / keywords?\n"
        f"(default: {DEFAULT_FOCUS})\n> "
    ) or DEFAULT_FOCUS

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

        report_path = None
        if unattended or approve("Save the full report?", default_yes=True):
            report = build_report(types, focus, scored, ranking)
            report_path = save_output(
                f"job-opportunities-{date.today().isoformat()}.md", report
            )
            print(f"\nSaved -> {report_path}")
        print(f"\nDone. Reports live in {WORKSPACE / 'output'}.")

        if unattended and report_path:
            ranked = sorted(scored, key=lambda pair: parse_score(pair[1]), reverse=True)
            top = ranked[:3]
            lines = [
                f"Job Hunter finished — {len(scored)} role(s) scored.",
                "",
                "Top picks:",
            ]
            for i, (opp, verdict) in enumerate(top, start=1):
                score = parse_score(verdict)
                lines.append(f"  {i}. {short_label(opp)} ({score}/100)")
            lines.append("")
            lines.append("Full report opened in your editor.")
            notify_desktop("Job Hunter — morning run", "\n".join(lines), open_path=report_path)

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
