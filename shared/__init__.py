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


# --- Demo mode (offline, no API key, no cost) ------------------------------
# Pass `--demo` on the command line (or set CURSOR_LAB_DEMO=1) and the lessons
# use these stand-ins instead of real Cursor agents. They mimic just enough of
# the SDK's shape (send -> run, run.text(), run.messages(), run.wait()) that the
# lesson code stays identical between demo and real runs.

import time as _time  # noqa: E402
from types import SimpleNamespace  # noqa: E402


def demo_enabled() -> bool:
    if "--demo" in sys.argv:
        return True
    return os.environ.get("CURSOR_LAB_DEMO", "").strip().lower() in ("1", "true", "yes")


def _canned_reply(prompt: str) -> str:
    """Pick a plausible fake answer based on the role implied by the prompt."""
    p = prompt.lower()
    if any(k in p for k in ("numbered list", "task list", "into tasks",
                            "small, independent", "realistic task")):
        return "1. Outline the key points\n2. Write a first draft\n3. Review and polish"
    if any(k in p for k in ("reviewer", "feedback", "summarize", "verdict", "end-of-day")):
        return (
            "- Clear intent and a sensible structure\n"
            "- Tighten the wording in a couple of places\n"
            "- Add one concrete example\n"
            "Overall: a strong start, ready to refine."
        )
    return (
        "[demo draft] A concise, ready-to-use draft would appear here. "
        "Add your CURSOR_API_KEY and drop --demo for real agent output."
    )


class _FakeRun:
    def __init__(self, text: str):
        self.run_id = "demo-run"
        self._text = text

    def text(self) -> str:
        return self._text

    def wait(self):
        return SimpleNamespace(status="finished", result=self._text, id=self.run_id)

    def messages(self):
        # Simulate streaming by emitting the reply a line at a time.
        for piece in self._text.splitlines(keepends=True):
            _time.sleep(0.03)
            block = SimpleNamespace(type="text", text=piece)
            yield SimpleNamespace(type="assistant",
                                  message=SimpleNamespace(content=[block]))

    stream = messages


class FakeAgent:
    """Offline stand-in that quacks like an SDK agent (context-manager + send)."""

    def __init__(self):
        self.agent_id = "demo-agent"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send(self, prompt: str) -> "_FakeRun":
        return _FakeRun(_canned_reply(prompt))

    def close(self):
        pass


def demo_prompt(message: str):
    """Offline stand-in for Agent.prompt: returns a result-like object."""
    return SimpleNamespace(status="finished", result=_canned_reply(message), id="demo-run")


# --- Windows compatibility shim --------------------------------------------
# cursor-sdk 0.1.8's *sync* local bridge reads the bridge subprocess's stderr
# pipe with `select()`. On Windows `select()` only works on sockets, so it
# raises WinError 10038 and no local agent can start. We swap in a small
# thread-based reader that avoids `select`. (The async runtime is unaffected;
# it already reads via asyncio streams.) No-op on macOS/Linux.

def _patch_sync_bridge_for_windows() -> None:
    if os.name != "nt":
        return
    try:
        import threading
        import time as _t

        from cursor_sdk import _bridge as _b
    except Exception:  # pragma: no cover - SDK not importable
        return

    if getattr(_b, "_read_discovery_patched", False):
        return

    def _read_discovery(process, timeout):
        result: dict = {}
        lines: list[str] = []

        def reader():
            try:
                assert process.stderr is not None
                for raw in process.stderr:  # blocking readline in a thread
                    lines.append(raw)
                    parsed = _b.parse_discovery_line(raw)
                    if parsed is not None:
                        result["discovery"] = parsed
                        return
            except Exception as exc:  # noqa: BLE001
                result["error"] = exc

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        deadline = _t.monotonic() + timeout
        while _t.monotonic() < deadline:
            if "discovery" in result:
                return result["discovery"]
            if "error" in result:
                raise _b.CursorSDKError(f"Bridge discovery read error: {result['error']}")
            if process.poll() is not None and not t.is_alive():
                if "discovery" in result:
                    return result["discovery"]
                raise _b.CursorSDKError(
                    f"Bridge exited before discovery with status {process.returncode}: "
                    + "".join(lines)
                )
            t.join(timeout=0.1)
        raise _b.CursorSDKError("Timed out waiting for bridge discovery")

    _b._read_discovery = _read_discovery
    _b._read_discovery_patched = True


_patch_sync_bridge_for_windows()
