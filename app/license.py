"""Simple license gate for Career Copilot (retail keys + 14-day trial)."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

_SALT = "career-copilot-v1-stephenv"
LICENSE_FILE = "license.json"
TRIAL_DAYS = 14


def _checksum(body: str) -> str:
    return hashlib.sha256((body + _SALT).encode()).hexdigest()[:4].upper()


def validate_key(key: str) -> bool:
    key = key.strip().upper()
    if key == "CCOP-TRIAL":
        return True
    if not key.startswith("CCOP-"):
        return False
    parts = key.split("-")
    if len(parts) != 4:
        return False
    body = "-".join(parts[:3])
    return parts[3] == _checksum(body)


def generate_key() -> str:
    import secrets

    a = secrets.token_hex(2).upper()[:4]
    b = secrets.token_hex(2).upper()[:4]
    body = f"CCOP-{a}-{b}"
    return f"{body}-{_checksum(body)}"


def license_path(root: Path) -> Path:
    return root / LICENSE_FILE


def load_license(root: Path) -> dict | None:
    path = license_path(root)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_license(root: Path, key: str) -> None:
    key = key.strip().upper()
    data: dict = {"key": key, "activated": date.today().isoformat()}
    if key == "CCOP-TRIAL":
        data["trial_expires"] = (date.today() + timedelta(days=TRIAL_DAYS)).isoformat()
    license_path(root).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def is_licensed(root: Path) -> bool:
    data = load_license(root)
    if not data:
        return False
    key = str(data.get("key", "")).strip().upper()
    if not validate_key(key):
        return False
    if key == "CCOP-TRIAL":
        exp = data.get("trial_expires")
        if exp:
            try:
                return date.today() <= date.fromisoformat(str(exp))
            except ValueError:
                return False
    return True


def license_status_label(root: Path) -> str:
    data = load_license(root)
    if not data:
        return "unlicensed"
    key = str(data.get("key", ""))
    if key.upper() == "CCOP-TRIAL":
        exp = data.get("trial_expires", "?")
        return f"trial (until {exp})"
    return "licensed"
