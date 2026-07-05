"""Fetch a Dice.com job description as plain text.

Usage:
  python fetch_dice_job.py
  python fetch_dice_job.py https://www.dice.com/job-detail/...
"""
import json
import re
import sys
import urllib.request

url = sys.argv[1] if len(sys.argv) > 1 else "https://www.dice.com/job-detail/f655b28d-520a-4d68-9df4-671dfe230e0c"
html = urllib.request.urlopen(url, timeout=20).read().decode("utf-8", "replace")
match = re.search(r'"description": "(.*?)"\s*,\s*"', html, re.S)
if not match:
    print("description not found")
    raise SystemExit(1)

desc = json.loads('"' + match.group(1) + '"')
text = (
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
print(text)
