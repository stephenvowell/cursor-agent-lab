"""First-run setup — license, Cursor API key, résumé import."""

from __future__ import annotations

import os
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from license import is_licensed, save_license, validate_key

BG = "#0d1528"
PANEL = "#122040"
PANEL2 = "#1a2d5c"
ACCENT = "#3b82f6"
ACCENT_L = "#93c5fd"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
OK = "#4ade80"
FONT = "Segoe UI"


def needs_setup(root: Path) -> bool:
    """Retail installs (frozen exe) require activation; dev source runs skip the gate."""
    if not getattr(sys, "frozen", False):
        return False
    return not is_licensed(root)


def _read_env_key(root: Path, name: str) -> str:
    env = root / ".env"
    if not env.is_file():
        return (os.environ.get(name) or "").strip()
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return (os.environ.get(name) or "").strip()


def _write_env(root: Path, api_key: str) -> None:
    env = root / ".env"
    lines: list[str] = []
    if env.is_file():
        lines = env.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    found = False
    for line in lines:
        if line.strip().startswith("CURSOR_API_KEY="):
            out.append(f'CURSOR_API_KEY={api_key}')
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f'CURSOR_API_KEY={api_key}')
    example = root / ".env.example"
    if not out and example.is_file():
        out = example.read_text(encoding="utf-8").splitlines()
        out = [
            (f'CURSOR_API_KEY={api_key}' if l.strip().startswith("CURSOR_API_KEY=") else l)
            for l in out
        ]
    env.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _import_resume(root: Path, src: Path) -> Path:
    dest_dir = root / "workspace" / "output"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "resume-and-cover-letter.md"
    if src.suffix.lower() in (".md", ".txt"):
        shutil.copy2(src, dest)
    else:
        dest.write_text(
            f"# Résumé import\n\nImported from `{src.name}`. Replace with your full résumé markdown.\n\n"
            f"(Original file: {src})\n",
            encoding="utf-8",
        )
    return dest


class SetupWizard(tk.Toplevel):
    def __init__(self, master: tk.Misc, root: Path) -> None:
        super().__init__(master)
        self.root_dir = root
        self.result = False
        self.title("Career Copilot — Setup")
        self.configure(bg=BG)
        self.geometry("520x480")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        tk.Label(
            self, text="Welcome to Career Copilot", bg=BG, fg=TEXT, font=(FONT, 16, "bold"),
        ).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(
            self,
            text="Activate your license, add your Cursor API key, and import your résumé.",
            bg=BG, fg=MUTED, font=(FONT, 10), wraplength=460, justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 16))

        form = tk.Frame(self, bg=BG)
        form.pack(fill="both", expand=True, padx=24)

        tk.Label(form, text="License key", bg=BG, fg=ACCENT_L, font=(FONT, 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4),
        )
        self.license_var = tk.StringVar(value=_read_env_key(root, "CAREER_COPILOT_LICENSE"))
        lic_row = tk.Frame(form, bg=BG)
        lic_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        tk.Entry(
            lic_row, textvariable=self.license_var, bg=PANEL, fg=TEXT,
            insertbackground=ACCENT_L, relief="flat", font=(FONT, 10), width=36,
        ).pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(
            lic_row, text="Trial", command=lambda: self.license_var.set("CCOP-TRIAL"),
            bg=PANEL2, fg=MUTED, relief="flat", font=(FONT, 9), padx=8,
        ).pack(side="left", padx=(8, 0))

        tk.Label(form, text="Cursor API key", bg=BG, fg=ACCENT_L, font=(FONT, 10, "bold")).grid(
            row=2, column=0, sticky="w", pady=(0, 4),
        )
        self.api_var = tk.StringVar(value=_read_env_key(root, "CURSOR_API_KEY"))
        tk.Entry(
            form, textvariable=self.api_var, bg=PANEL, fg=TEXT, show="•",
            insertbackground=ACCENT_L, relief="flat", font=(FONT, 10),
        ).grid(row=3, column=0, sticky="ew", pady=(0, 4), ipady=6)
        tk.Label(
            form,
            text="Get a key: cursor.com/dashboard/integrations — or use Demo mode without a key.",
            bg=BG, fg=MUTED, font=(FONT, 8), wraplength=460, justify="left",
        ).grid(row=4, column=0, sticky="w", pady=(0, 12))

        tk.Label(form, text="Résumé (markdown or text)", bg=BG, fg=ACCENT_L, font=(FONT, 10, "bold")).grid(
            row=5, column=0, sticky="w", pady=(0, 4),
        )
        self.resume_path = tk.StringVar()
        existing = root / "workspace" / "output" / "resume-and-cover-letter.md"
        if existing.is_file():
            self.resume_path.set(str(existing))
        rrow = tk.Frame(form, bg=BG)
        rrow.grid(row=6, column=0, sticky="ew", pady=(0, 16))
        tk.Entry(
            rrow, textvariable=self.resume_path, bg=PANEL, fg=TEXT,
            insertbackground=ACCENT_L, relief="flat", font=(FONT, 9),
        ).pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(
            rrow, text="Browse…", command=self._browse_resume,
            bg=PANEL2, fg=TEXT, relief="flat", font=(FONT, 9), padx=10,
        ).pack(side="left", padx=(8, 0))

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", padx=24, pady=(0, 20))
        tk.Button(
            btns, text="Activate & Continue", command=self._finish,
            bg=ACCENT, fg="#fff", relief="flat", font=(FONT, 11, "bold"), padx=16, pady=10,
        ).pack(side="right")
        tk.Button(
            btns, text="Cancel", command=self._cancel,
            bg=PANEL, fg=MUTED, relief="flat", font=(FONT, 10), padx=12, pady=10,
        ).pack(side="right", padx=(0, 8))

        form.columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _browse_resume(self) -> None:
        path = filedialog.askopenfilename(
            title="Import résumé",
            filetypes=[
                ("Markdown", "*.md"),
                ("Text", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.resume_path.set(path)

    def _finish(self) -> None:
        lic = self.license_var.get().strip().upper()
        if not validate_key(lic):
            messagebox.showerror(
                "Invalid license",
                "Enter a valid key (CCOP-XXXX-XXXX-XXXX) or click Trial for 14 days.",
                parent=self,
            )
            return
        save_license(self.root_dir, lic)

        api = self.api_var.get().strip()
        if api and api not in ("cursor_your_key_here", ""):
            _write_env(self.root_dir, api)

        resume = self.resume_path.get().strip()
        if resume:
            src = Path(resume)
            if src.is_file():
                _import_resume(self.root_dir, src)

        self.result = True
        self.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.destroy()


def run_setup_wizard(master: tk.Misc, root: Path) -> bool:
    wiz = SetupWizard(master, root)
    master.wait_window(wiz)
    return bool(wiz.result)
