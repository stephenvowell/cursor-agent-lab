"""Realistic demo output for matcher, ranker, and cover-letter stages."""

from __future__ import annotations

import re


def _company_from_opp(opp: str) -> str:
    parts = [p.strip() for p in opp.split("|") if p.strip()]
    return parts[0] if parts else "the company"


def _fit_from_opp(opp: str) -> int:
    m = re.search(r"fit\s+(\d{1,3})\s*/\s*100", opp, re.I)
    if m:
        return int(m.group(1))
    defaults = {
        "Example Health IoT Inc.": 76,
        "Demo Wearables Co.": 71,
        "Sample MedTech Startup": 68,
    }
    company = _company_from_opp(opp)
    return defaults.get(company, 65)


def demo_matcher_verdict(opp: str) -> str:
    company = _company_from_opp(opp)
    score = _fit_from_opp(opp)
    if score >= 72:
        verdict = "APPLY"
        reason = "Strong embedded/IoT overlap with your ESP32 and firmware background."
        gaps = "Minor: verify any Rust or Matter requirements against your résumé."
        matched = "ESP32, C/C++, IoT, Wi-Fi/BLE, PlatformIO, sensor integration, contract remote"
    elif score >= 65:
        verdict = "MAYBE"
        reason = "Solid fit but one or two gaps worth addressing in the cover letter."
        gaps = "Production-scale team process; domain-specific compliance if med-device."
        matched = "Embedded Linux, Python tooling, cloud connectivity, prototype-to-ship experience"
    else:
        verdict = "SKIP"
        reason = "Stack or seniority mismatch for this search focus."
        gaps = "Role emphasizes stacks outside your primary embedded firmware lane."
        matched = "General software engineering, remote US"

    return (
        f"Fit score: {score}/100\n"
        f"Matched skills: {matched}\n"
        f"Gaps / missing: {gaps}\n"
        f"Verdict: {verdict} — {reason}\n"
        f"[DEMO] Tailored analysis for {company}."
    )


def demo_ranking(scored: list[tuple[str, str]]) -> str:
    lines = ["## Ranked shortlist [DEMO]", ""]
    ranked = sorted(
        scored,
        key=lambda p: int(re.search(r"(\d{1,3})\s*/\s*100", p[1]).group(1))
        if re.search(r"(\d{1,3})\s*/\s*100", p[1])
        else 0,
        reverse=True,
    )
    for i, (opp, verdict) in enumerate(ranked, start=1):
        company = _company_from_opp(opp)
        m = re.search(r"Verdict:\s*(\w+)", verdict)
        v = m.group(1) if m else "?"
        lines.append(f"{i}. **{company}** — {v}")
    lines.extend(
        [
            "",
            "### Apply first",
            "1. Highest fit score with contract/embedded alignment.",
            "2. Second pick — good IoT overlap, honest gaps in letter.",
            "3. Third — MAYBE unless timeline is urgent.",
            "",
            "**Red flags:** Verify each URL is still live before applying.",
        ]
    )
    return "\n".join(lines)


def demo_cover_letter(opp: str) -> str:
    company = _company_from_opp(opp)
    parts = [p.strip() for p in opp.split("|") if p.strip()]
    role = parts[1] if len(parts) > 1 else "Embedded Engineer"
    return (
        f"Dear Hiring Team at {company},\n\n"
        f"I am writing regarding the {role} opportunity. I bring 29 years of "
        f"product development with deep hands-on work in embedded firmware, ESP32, "
        f"IoT connectivity, and shipping prototype hardware to production. Recent "
        f"work includes MedAlert (mmWave + ESP32 health monitoring) and mission-"
        f"critical systems experience as a NASA contractor.\n\n"
        f"Your role aligns with my strengths in C/C++, sensor integration, Wi-Fi/BLE, "
        f"and device-to-cloud pipelines. Where your team uses tools I have less "
        f"production time in, I learn quickly and document clearly — as shown in my "
        f"open firmware and portfolio at stephenv.net.\n\n"
        f"I am based in Sierra Vista, AZ, authorized to work in the US, and available "
        f"for remote contract engagement. I would welcome a conversation about how I "
        f"can contribute to {company}'s next shipping milestone.\n\n"
        f"Sincerely,\nStephen Vowell\n\n"
        f"[DEMO draft — edit before sending]"
    )
