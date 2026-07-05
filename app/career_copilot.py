"""Career Copilot - a desktop command center for the job-hunt toolkit.

One window that runs the three tools in this repo AND keeps all their output
(and your yes/no answers) inside an embedded console - no popup terminals:

  * Email Check   -> app/job_email_checker.py   (scan Gmail for job replies)
  * Job Hunter    -> app/job_hunter.py          (Job Scout + score + rank + letters)
  * Task Assistant-> app/task_assistant.py      (plan + draft your day)

The tools are interactive (they ask you to approve every agent step). This app
captures their output into the console panel and sends your input (the input
row + Yes/No buttons) to the running tool's stdin. Styled to match stephenv.net
(dark navy + blue).

Run:  python app/career_copilot.py
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from license import is_licensed, license_status_label  # noqa: E402
from paths import resolve_project_root, resolve_python_exe  # noqa: E402
from setup_wizard import needs_setup, run_setup_wizard  # noqa: E402

PROJECT_ROOT = resolve_project_root()
APP_DIR = PROJECT_ROOT / "app"
VENV_PY = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

# --- Palette (from stephenv.net: assets/css/custom.css + main.css) ----------
BG = "#0d1528"
PANEL = "#122040"
PANEL2 = "#1a2d5c"
CONSOLE_BG = "#080e1c"
ACCENT = "#3b82f6"
ACCENT_H = "#2563eb"
ACCENT_L = "#93c5fd"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
DANGER = "#f87171"
DANGER_H = "#dc2626"
OK = "#4ade80"

FONT = "Segoe UI"
MONO = "Consolas"

_DONE = object()  # sentinel pushed on the queue when a tool exits


def assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle and (Path(bundle) / "assets").is_dir():
            return Path(bundle) / "assets"
    return PROJECT_ROOT / "assets"


def _header_logo_photo(master: tk.Misc, *, height: int = 40) -> tk.PhotoImage | None:
    """Satori mark tinted light for dark header (black SVG is invisible on navy)."""
    assets = assets_dir()
    for name in ("satori-header.png", "satori-icon.png", "copilot-icon.png"):
        path = assets / name
        if not path.is_file():
            continue
        if name == "satori-header.png":
            try:
                return tk.PhotoImage(master=master, file=str(path))
            except tk.TclError:
                continue
        try:
            from PIL import Image, ImageTk

            img = Image.open(path).convert("RGBA")
            accent = (147, 197, 253)  # ACCENT_L
            px = img.load()
            w, h = img.size
            for y in range(h):
                for x in range(w):
                    r, g, b, a = px[x, y]
                    if a > 24 and (r + g + b) < 420:
                        px[x, y] = (*accent, a)
            new_w = max(1, int(w * height / h))
            img = img.resize((new_w, height), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img, master=master)
        except Exception:  # noqa: BLE001
            try:
                img = tk.PhotoImage(master=master, file=str(path))
                if img.height() > height:
                    f = max(1, img.height() // height)
                    return img.subsample(f, f)
                return img
            except tk.TclError:
                continue
    return None


def python_exe() -> str:
    return resolve_python_exe(PROJECT_ROOT)


def has_api_key() -> bool:
    if (os.environ.get("CURSOR_API_KEY") or "").strip():
        return True
    try:
        env = PROJECT_ROOT / ".env"
        if not env.is_file():
            return False
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("CURSOR_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                return val not in ("", "cursor_your_key_here")
    except OSError:
        pass
    return False


def has_gmail_creds() -> bool:
    return (PROJECT_ROOT / "credentials.json").exists()


class Copilot(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Career Copilot")
        self.configure(bg=BG)
        self.geometry("760x780")
        self.minsize(640, 680)

        self.demo = tk.BooleanVar(value=False)
        self.proc: subprocess.Popen | None = None
        self.out_q: queue.Queue = queue.Queue()
        self.run_buttons: list[tk.Button] = []
        self.current_tool = ""
        self._roles: list[dict] = []

        self._set_icon()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._drain_queue)

    def _set_icon(self) -> None:
        assets = assets_dir()
        for ico_name in ("satori-icon.ico", "copilot-icon.ico"):
            ico = assets / ico_name
            try:
                if ico.exists():
                    self.iconbitmap(default=str(ico))
                    return
            except Exception:  # noqa: BLE001
                pass
        for png_name in ("satori-icon.png", "copilot-icon.png"):
            png = assets / png_name
            try:
                if png.exists():
                    self._icon_img = tk.PhotoImage(file=str(png))
                    self.iconphoto(True, self._icon_img)
                    return
            except Exception:  # noqa: BLE001
                pass

    # -- styled widgets ------------------------------------------------------
    def _btn(self, parent, text, command, *, base=ACCENT, hover=ACCENT_H,
             fg="#ffffff", font=(FONT, 10, "bold"), padx=12, pady=8, width=0):
        b = tk.Button(parent, text=text, command=command, bg=base, fg=fg,
                      activebackground=hover, activeforeground="#ffffff",
                      relief="flat", bd=0, cursor="hand2", font=font,
                      padx=padx, pady=pady, width=width)
        b.bind("<Enter>", lambda _e: b.configure(bg=hover) if str(b["state"]) != "disabled" else None)
        b.bind("<Leave>", lambda _e: b.configure(bg=base) if str(b["state"]) != "disabled" else None)
        b._base = base  # type: ignore[attr-defined]
        return b

    # -- layout --------------------------------------------------------------
    def _build(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=22, pady=(18, 4))

        title_row = tk.Frame(header, bg=BG)
        title_row.pack(side="left")

        self._logo_img = _header_logo_photo(self, height=40)
        if self._logo_img is not None:
            tk.Label(title_row, image=self._logo_img, bg=BG).pack(side="left", padx=(0, 12))

        tk.Label(
            title_row, text="Career Copilot", bg=BG, fg=TEXT, font=(FONT, 22, "bold"),
        ).pack(side="left")

        self.status_lbl = tk.Label(header, text="idle", bg=BG, fg=MUTED,
                                    font=(FONT, 10, "italic"))
        self.status_lbl.pack(side="right")

        status = tk.Frame(self, bg=BG)
        status.pack(fill="x", padx=22, pady=(0, 8))
        self._chip(status, "API key", has_api_key())
        self._chip(status, "License", is_licensed(PROJECT_ROOT))
        self._chip(status, "Gmail", has_gmail_creds())
        self._chip(status, "venv", VENV_PY.exists())

        # tool buttons row
        tools = tk.Frame(self, bg=BG)
        tools.pack(fill="x", padx=22, pady=(0, 8))
        for emoji, label, script, agent, extra in (
            # --no-popup keeps the email summary in the console, not a dialog.
            ("\U0001F4E7", "Email Check", "job_email_checker.py", False, ("--no-popup",)),
            ("\U0001F3AF", "Job Scout + Hunter", "job_hunter.py", True, ()),
            ("\U0001F5D3", "Task Assistant", "task_assistant.py", True, ()),
        ):
            b = self._btn(
                tools, f"{emoji}  {label}",
                lambda s=script, a=agent, x=extra: self._start_tool(s, a, x),
                base=PANEL, hover=PANEL2, fg=TEXT, font=(FONT, 10, "bold"),
            )
            b.pack(side="left", padx=(0, 8))
            self.run_buttons.append(b)

        tk.Checkbutton(
            tools, text="Demo mode", variable=self.demo, bg=BG, fg=MUTED,
            selectcolor=PANEL, activebackground=BG, activeforeground=ACCENT_L,
            font=(FONT, 9), bd=0, highlightthickness=0, cursor="hand2",
        ).pack(side="left", padx=(6, 0))

        self._btn(tools, "Re-auth Gmail",
                  lambda: self._start_tool("job_email_checker.py", False, ("--auth",)),
                  base=PANEL, hover=PANEL2, fg=ACCENT_L, font=(FONT, 9),
                  padx=10, pady=6).pack(side="right")
        self._btn(tools, "Setup",
                  self._open_setup,
                  base=PANEL, hover=PANEL2, fg=ACCENT_L, font=(FONT, 9),
                  padx=10, pady=6).pack(side="right", padx=(0, 6))

        # roles table (populated when Job Hunter emits @@SCOUT_JSON)
        roles_wrap = tk.Frame(self, bg=BG)
        roles_wrap.pack(fill="x", padx=22, pady=(0, 6))
        tk.Label(
            roles_wrap, text="Roles", bg=BG, fg=MUTED, font=(FONT, 9, "bold"),
        ).pack(anchor="w")
        tree_frame = tk.Frame(roles_wrap, bg=ACCENT)
        tree_frame.pack(fill="x", pady=(4, 0))
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Roles.Treeview",
            background=CONSOLE_BG,
            foreground=TEXT,
            fieldbackground=CONSOLE_BG,
            borderwidth=0,
            rowheight=22,
        )
        style.configure(
            "Roles.Treeview.Heading",
            background=PANEL2,
            foreground=ACCENT_L,
            relief="flat",
        )
        style.map("Roles.Treeview", background=[("selected", PANEL2)])
        self.roles_tree = ttk.Treeview(
            tree_frame,
            columns=("fit", "company", "role", "remote", "url"),
            show="headings",
            height=4,
            style="Roles.Treeview",
        )
        for col, label, width in (
            ("fit", "Fit", 44),
            ("company", "Company", 140),
            ("role", "Role", 180),
            ("remote", "Remote", 56),
            ("url", "URL", 220),
        ):
            self.roles_tree.heading(col, text=label)
            self.roles_tree.column(col, width=width, stretch=(col == "role"))
        self.roles_tree.pack(side="left", fill="x", expand=True, padx=1, pady=1)
        r_sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.roles_tree.yview)
        r_sb.pack(side="right", fill="y")
        self.roles_tree.configure(yscrollcommand=r_sb.set)

        role_btns = tk.Frame(roles_wrap, bg=BG)
        role_btns.pack(fill="x", pady=(6, 0))
        self._btn(
            role_btns, "Open URL", self._open_selected_url,
            base=PANEL, hover=PANEL2, fg=ACCENT_L, font=(FONT, 9), padx=10, pady=5,
        ).pack(side="left", padx=(0, 6))
        self._btn(
            role_btns, "Yes (approve step)", lambda: self._send("y"),
            base=PANEL, hover=PANEL2, fg=OK, font=(FONT, 9), padx=10, pady=5,
        ).pack(side="left", padx=(0, 6))
        self._btn(
            role_btns, "No (skip step)", lambda: self._send("n"),
            base=PANEL, hover=PANEL2, fg=DANGER, font=(FONT, 9), padx=10, pady=5,
        ).pack(side="left")

        # console output
        con_wrap = tk.Frame(self, bg=ACCENT)
        con_wrap.pack(fill="both", expand=True, padx=22, pady=(0, 8))
        self.console = tk.Text(
            con_wrap, bg=CONSOLE_BG, fg=TEXT, insertbackground=ACCENT_L,
            font=(MONO, 10), relief="flat", bd=0, wrap="word", padx=12, pady=10,
            state="disabled", height=16,
        )
        self.console.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        sb = tk.Scrollbar(con_wrap, command=self.console.yview)
        sb.pack(side="right", fill="y")
        self.console.configure(yscrollcommand=sb.set)
        self.console.tag_configure("you", foreground=ACCENT_L)
        self.console.tag_configure("sys", foreground=MUTED, font=(MONO, 9, "italic"))
        self._log("Pick a tool above. Job Hunter fills the Roles table after scout.\n"
                  "Answer prompts below with Yes / No.\n", "sys")

        # input row
        inp = tk.Frame(self, bg=BG)
        inp.pack(fill="x", padx=22, pady=(0, 16))
        self.entry = tk.Entry(inp, bg=PANEL, fg=TEXT, insertbackground=ACCENT_L,
                              relief="flat", font=(MONO, 10), disabledbackground=PANEL)
        self.entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self._send(self.entry.get()))

        self._btn(inp, "Send", lambda: self._send(self.entry.get()),
                  padx=14).pack(side="left", padx=(0, 6))
        self._btn(inp, "Yes", lambda: self._send("y"), base=PANEL, hover=PANEL2,
                  fg=OK, width=4).pack(side="left", padx=(0, 6))
        self._btn(inp, "No", lambda: self._send("n"), base=PANEL, hover=PANEL2,
                  fg=DANGER, width=4).pack(side="left", padx=(0, 6))
        self.stop_btn = self._btn(inp, "Stop", self._stop, base=DANGER,
                                  hover=DANGER_H, width=5)
        self.stop_btn.pack(side="left", padx=(0, 6))
        self._btn(inp, "Clear", self._clear, base=PANEL, hover=PANEL2, fg=MUTED,
                  width=5).pack(side="left")

        self._set_running(False)

    def _chip(self, parent, label, ok: bool) -> None:
        chip = tk.Frame(parent, bg=BG)
        chip.pack(side="left", padx=(0, 14))
        tk.Label(chip, text="\u25CF", bg=BG, fg=(OK if ok else DANGER),
                 font=(FONT, 10)).pack(side="left")
        tk.Label(chip, text=f" {label}", bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left")

    def _clear_roles(self) -> None:
        for row in self.roles_tree.get_children():
            self.roles_tree.delete(row)
        self._roles = []

    def _load_roles(self, json_path: str | Path) -> None:
        path = Path(json_path)
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        roles = data.get("roles") or []
        self._clear_roles()
        self._roles = roles
        for role in roles:
            self.roles_tree.insert(
                "",
                "end",
                values=(
                    role.get("fit", ""),
                    role.get("company", ""),
                    role.get("role", ""),
                    role.get("remote", ""),
                    role.get("url", ""),
                ),
            )
        self._log(f"\n[Loaded {len(roles)} role(s) into table]\n", "sys")

    def _open_selected_url(self) -> None:
        sel = self.roles_tree.selection()
        if not sel:
            self._log("\n[Select a role row first]\n", "sys")
            return
        vals = self.roles_tree.item(sel[0], "values")
        url = vals[4] if len(vals) > 4 else ""
        if url.startswith("http"):
            webbrowser.open(url)
            self._log(f"\n[Opened {url}]\n", "sys")
        else:
            self._log("\n[No URL in selected row]\n", "sys")

    def _filter_gui_lines(self, text: str) -> str:
        """Strip @@SCOUT_JSON bridge lines from console; load table instead."""
        out: list[str] = []
        for line in text.splitlines(keepends=True):
            if line.startswith("@@SCOUT_JSON "):
                path = line.strip().split(" ", 1)[1]
                self.after(0, lambda p=path: self._load_roles(p))
            else:
                out.append(line)
        return "".join(out)

    # -- console helpers -----------------------------------------------------
    def _log(self, text: str, tag: str | None = None) -> None:
        self.console.configure(state="normal")
        self.console.insert("end", text, tag or ())
        self.console.see("end")
        self.console.configure(state="disabled")

    def _clear(self) -> None:
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    # -- process control -----------------------------------------------------
    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        for b in self.run_buttons:
            b.configure(state=state, bg=(PANEL if not running else "#0f1830"))
        self.entry.configure(state=("normal" if running else "disabled"))
        self.stop_btn.configure(state=("normal" if running else "disabled"))
        self.status_lbl.configure(
            text=(f"running: {self.current_tool}" if running else "idle"),
            fg=(OK if running else MUTED),
        )
        if running:
            self.entry.focus_set()

    def _open_setup(self) -> None:
        run_setup_wizard(self, PROJECT_ROOT)

    def _start_tool(self, script: str, agent: bool, extra: tuple[str, ...] = ()) -> None:
        if getattr(sys, "frozen", False) and not is_licensed(PROJECT_ROOT):
            self._log("\n[Activate a license in Setup before running tools]\n", "sys")
            self._open_setup()
            return
        if self.proc is not None:
            self._log("\n[a tool is already running - Stop it first]\n", "sys")
            return
        args = list(extra)
        if agent and self.demo.get():
            args.append("--demo")

        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["COPILOT_GUI"] = "1"
        cmd = [python_exe(), "-u", str(APP_DIR / script), *args]
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        self._clear()
        self._clear_roles()
        self.current_tool = script
        self._log(f"$ {' '.join([Path(cmd[0]).name, *cmd[1:]])}\n\n", "sys")
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=str(PROJECT_ROOT), env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=no_window,
            )
        except Exception as exc:  # noqa: BLE001
            self._log(f"[failed to start: {exc}]\n", "sys")
            self.proc = None
            return
        self._set_running(True)
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()

    def _reader(self, proc: subprocess.Popen) -> None:
        try:
            assert proc.stdout is not None
            while True:
                ch = proc.stdout.read(1)
                if ch == "":
                    break
                self.out_q.put(ch)
        except Exception:  # noqa: BLE001
            pass
        finally:
            proc.wait()
            self.out_q.put((_DONE, proc.returncode))

    def _drain_queue(self) -> None:
        chunks: list[str] = []
        done_code = None
        try:
            while True:
                item = self.out_q.get_nowait()
                if isinstance(item, tuple) and item and item[0] is _DONE:
                    done_code = item[1]
                    break
                chunks.append(item)
        except queue.Empty:
            pass
        if chunks:
            self._log(self._filter_gui_lines("".join(chunks)))
        if done_code is not None:
            self._log(f"\n\n[{self.current_tool} finished, exit code {done_code}]\n", "sys")
            self.proc = None
            self._set_running(False)
        self.after(50, self._drain_queue)

    def _send(self, text: str) -> None:
        if self.proc is None or self.proc.stdin is None:
            return
        try:
            self.proc.stdin.write(text + "\n")
            self.proc.stdin.flush()
            self._log(f"{text or '(enter)'}\n", "you")
        except Exception as exc:  # noqa: BLE001
            self._log(f"[couldn't send input: {exc}]\n", "sys")
        self.entry.delete(0, "end")

    def _stop(self) -> None:
        if self.proc is not None:
            self._log("\n[stopping...]\n", "sys")
            try:
                self.proc.terminate()
            except Exception:  # noqa: BLE001
                pass

    def _on_close(self) -> None:
        self._stop()
        self.destroy()


def main() -> None:
    app = Copilot()
    if needs_setup(PROJECT_ROOT):
        app.withdraw()
        if not run_setup_wizard(app, PROJECT_ROOT):
            app.destroy()
            return
        app.deiconify()
    if "--demo" in sys.argv:
        app.demo.set(True)
        extra: tuple[str, ...] = ("--unattended",) if "--unattended" in sys.argv else ()
        app.after(600, lambda: app._start_tool("job_hunter.py", True, extra))
    app.mainloop()


if __name__ == "__main__":
    main()
