"""Fetch real job posting text from URLs (Dice, generic HTTP)."""

from fetchers.dice import fetch_dice_job
from fetchers.http import fetch_url_text
from fetchers.seeds import load_seed_postings

__all__ = ["fetch_dice_job", "fetch_job_description", "fetch_url_text", "load_seed_postings"]


def fetch_job_description(url: str, *, max_chars: int = 8000) -> str:
    """Return plain-text job description for a posting URL."""
    url = url.strip()
    if "dice.com" in url.lower():
        text = fetch_dice_job(url)
    else:
        text = fetch_url_text(url)
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n… (truncated)"
    return text
