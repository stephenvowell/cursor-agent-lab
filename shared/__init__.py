"""Shared helpers for the Cursor Agent Lab.

These utilities keep the lessons readable and enforce the lab's one rule:
**nothing happens without your say-so.** Every agent action in this project
is meant to pass through `approve()` first, so you always stay in the loop.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Load CURSOR_API_KEY (and friends) from a local .env if python-dotenv is
# installed. Harmless if it isn't.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

# Model used across the lab. "composer-2.5" is a sensible default; "auto"
# lets the server choose. Model is REQUIRED for local agents.
MODEL = os.environ.get("CURSOR_LAB_MODEL", "composer-2.5").strip() or "composer-2.5"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = PROJECT_ROOT / "workspace"      # agents run against this sandbox
OUTPUT_DIR = WORKSPACE / "output"           # approved drafts land here


def require_api_key() -> str:
    """Return the Cursor API key, or exit with a friendly message."""
    key = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if not key:
        print(
            "\nCURSOR_API_KEY is not set.\n"
            "  1. Create a key: https://cursor.com/dashboard/integrations\n"
            "  2. Copy .env.example to .env and paste it in, or set it now:\n"
            '       $env:CURSOR_API_KEY = "cursor_..."   (PowerShell)\n',
            file=sys.stderr,
        )
        raise SystemExit(1)
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    return key


def rule(char: str = "-", width: int = 66) -> None:
    print(char * width)


def banner(title: str) -> None:
    rule("=")
    print(title)
    rule("=")


def approve(action: str, *, default_yes: bool = False) -> bool:
    """The heart of 'not autonomous': ask before doing anything.

    Prints what is about to happen and returns True only if you approve.
    Answering nothing uses `default_yes`.
    """
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        answer = input(f"\n>> {action}\n   Proceed? {suffix} ").strip().lower()
    except EOFError:
        return False
    if not answer:
        return default_yes
    return answer in ("y", "yes")


def ask_text(prompt: str) -> str:
    """Prompt the human for a line of text (empty allowed)."""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def stream_text(run) -> str:
    """Print an agent's assistant text as it streams; return the full text.

    Mirrors the documented shape: iterate `run.messages()`, pull `text`
    blocks out of assistant messages, then always call `run.wait()`.
    """
    chunks: list[str] = []
    for message in run.messages():
        if getattr(message, "type", None) == "assistant":
            for block in message.message.content:
                if getattr(block, "type", None) == "text":
                    print(block.text, end="", flush=True)
                    chunks.append(block.text)
    run.wait()  # terminal result + releases the run's watchers
    print()
    return "".join(chunks)


def save_output(name: str, text: str) -> Path:
    """Persist an approved draft into workspace/output/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    path.write_text(text, encoding="utf-8")
    return path
