"""Fetch a Dice.com job description as plain text.

Prefer: python -c "from app.fetchers import fetch_job_description; print(fetch_job_description('URL'))"
This wrapper remains for manual CLI use from workspace/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from fetchers import fetch_job_description  # noqa: E402

url = sys.argv[1] if len(sys.argv) > 1 else "https://www.dice.com/job-detail/f655b28d-520a-4d68-9df4-671dfe230e0c"
print(fetch_job_description(url))
