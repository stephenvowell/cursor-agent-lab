"""Resolve install root and Python interpreter (dev, pack folder, or frozen exe)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT_MARKER = "career_copilot_root.txt"


def _has_pack_layout(root: Path) -> bool:
    return (
        (root / "app" / "career_copilot.py").is_file()
        and (root / "shared" / "__init__.py").is_file()
        and (root / "app" / "job_hunter.py").is_file()
    )


def resolve_project_root() -> Path:
    """Find the Career Copilot install folder."""
    if not getattr(sys, "frozen", False):
        return APP_DIR.parent

    exe_dir = Path(sys.executable).resolve().parent
    marker = exe_dir / ROOT_MARKER
    if marker.is_file():
        marked = Path(marker.read_text(encoding="utf-8-sig").strip())
        if _has_pack_layout(marked):
            return marked

    for candidate in (
        exe_dir / "pack",
        exe_dir.parent,
        exe_dir,
        Path(os.environ.get("CAREER_COPILOT_ROOT", "")),
    ):
        if candidate and _has_pack_layout(Path(candidate)):
            return Path(candidate)

    for parent in exe_dir.parents:
        if _has_pack_layout(parent):
            return parent

    return exe_dir


def resolve_python_exe(root: Path) -> str:
    """Real Python for job_hunter / email tools — not the frozen GUI exe."""
    venv_py = root / ".venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return str(venv_py)

    if not getattr(sys, "frozen", False) and sys.executable:
        return sys.executable

    for candidate in (
        os.environ.get("CAREER_COPILOT_PYTHON", ""),
        shutil.which("python") or "",
    ):
        if candidate and Path(candidate).is_file():
            return str(candidate)

    raise FileNotFoundError(
        "No Python interpreter found for Career Copilot tools.\n"
        f"Expected venv at: {venv_py}\n"
        "Re-run the installer or: python -m venv .venv && pip install -r requirements.txt"
    )


def write_root_marker(root: Path, exe_dir: Path) -> None:
    exe_dir.mkdir(parents=True, exist_ok=True)
    (exe_dir / ROOT_MARKER).write_text(str(root.resolve()) + "\n", encoding="utf-8")
