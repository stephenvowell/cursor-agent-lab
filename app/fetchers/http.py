"""Generic HTTP fetch — strip HTML tags for simple job pages."""

from __future__ import annotations

import re
import urllib.request


def fetch_url_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CareerCopilot/1.0 (job research; +https://stephenv.net)"},
    )
    raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
