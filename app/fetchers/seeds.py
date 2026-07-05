"""Load seed job URLs from config/seed_urls.yaml and fetch descriptions."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SEEDS_PATH = PROJECT_ROOT / "config" / "seed_urls.yaml"


def load_seed_urls() -> list[dict]:
    """Return [{url, company?, note?}, ...] from seed_urls.yaml."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return _parse_seeds_plain(SEEDS_PATH.read_text(encoding="utf-8"))

    try:
        data = yaml.safe_load(SEEDS_PATH.read_text(encoding="utf-8"))
    except OSError:
        return []
    if not data or not isinstance(data, dict):
        return []
    seeds = data.get("seeds") or []
    return [s for s in seeds if isinstance(s, dict) and s.get("url")]


def _parse_seeds_plain(text: str) -> list[dict]:
    """Minimal parser when PyYAML is not installed."""
    seeds: list[dict] = []
    current: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- url:"):
            if current.get("url"):
                seeds.append(current)
            current = {"url": line.split(":", 1)[1].strip().strip('"\'')}
        elif line.startswith("company:") and current:
            current["company"] = line.split(":", 1)[1].strip().strip('"\'')
        elif line.startswith("note:") and current:
            current["note"] = line.split(":", 1)[1].strip().strip('"\'')
        elif line.startswith("type:") and current:
            current["type"] = line.split(":", 1)[1].strip().strip('"\'')
    if current.get("url"):
        seeds.append(current)
    return seeds


def _is_search_seed(seed: dict, url: str) -> bool:
    if seed.get("type") == "search":
        return True
    lower = url.lower()
    if "linkedin.com/jobs/search" in lower or "indeed.com/jobs?" in lower:
        return True
    return False


def _search_seed_description(seed: dict) -> str:
    company = seed.get("company") or "Job board"
    note = seed.get("note") or ""
    return (
        f"({company} search results page — use live web search to open this URL, "
        f"find current individual job postings, and include real job URLs in your table. "
        f"{note})"
    )


def load_seed_postings(fetch_fn) -> list[dict]:
    """Fetch each seed URL; return [{url, company, note, description}, ...]."""
    postings: list[dict] = []
    for seed in load_seed_urls():
        url = str(seed["url"]).strip()
        if _is_search_seed(seed, url):
            desc = _search_seed_description(seed)
        else:
            try:
                desc = fetch_fn(url)
            except Exception as exc:  # noqa: BLE001
                desc = f"(fetch failed: {exc})"
        postings.append(
            {
                "url": url,
                "company": seed.get("company") or "",
                "note": seed.get("note") or "",
                "type": seed.get("type") or "posting",
                "description": desc,
            }
        )
    return postings
