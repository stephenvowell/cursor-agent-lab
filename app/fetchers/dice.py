"""Fetch a Dice.com job description as plain text."""

from __future__ import annotations

import json
import re
import urllib.request


def fetch_dice_job(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CareerCopilot/1.0 (job research; +https://stephenv.net)"},
    )
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    match = re.search(r'"description": "(.*?)"\s*,\s*"', html, re.S)
    if not match:
        raise ValueError(f"Dice description not found in page: {url}")

    desc = json.loads('"' + match.group(1) + '"')
    return (
        desc.replace("<br />", "\n")
        .replace("<br/>", "\n")
        .replace("<strong>", "**")
        .replace("</strong>", "**")
        .replace("<b>", "**")
        .replace("</b>", "**")
        .replace("<li>", "- ")
        .replace("</li>", "")
        .replace("<ul>", "")
        .replace("</ul>", "")
        .replace("&amp;", "&")
    )
