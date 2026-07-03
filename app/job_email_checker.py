"""Job email checker - scan Gmail for real responses to your job applications.

This is a self-contained tool you OWN: it talks to Gmail directly through
Google's official API and can run unattended (e.g. from Windows Task Scheduler),
so it never needs a browser or a person after the one-time setup.

    First run (one time, opens a browser to grant read-only access):
        python app/job_email_checker.py --auth

    Normal run (no browser, safe to schedule):
        python app/job_email_checker.py
        python app/job_email_checker.py --days 3     (look back 3 days)

What it does each run:
  1. Searches your inbox for job-related mail in the last N days.
  2. Sorts each message into: interview / offer, recruiter outreach,
     rejection, or auto-acknowledgment (the "we got your application" noise).
  3. Prints a summary and saves it to workspace/output/job-email-summary-<date>.md.

Only READ access is requested - this tool can never send, delete, or change
your email.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from datetime import date, datetime
from pathlib import Path

def app_base_dir() -> Path:
    """Where the tool keeps its files.

    Packaged as a PyInstaller .exe, __file__ points inside a temp extraction
    dir, so keep credentials, token, and summaries next to the executable.
    Running from source, use the project root as before.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = app_base_dir()
OUTPUT_DIR = BASE_DIR / "workspace" / "output"

# Secrets live next to the tool and are git-ignored:
#   credentials.json - the OAuth client you download from Google Cloud (once).
#   token.json       - your saved login, created automatically on first --auth.
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

# Read-only: the tool literally cannot modify your mailbox.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Gmail search: cast a wide net for job-related mail, then classify locally.
SEARCH_TERMS = (
    'interview OR "next steps" OR "move forward" OR recruiter OR '
    '"your application" OR "thank you for applying" OR unfortunately OR '
    'opportunity OR "your candidacy" OR hiring OR "the position" OR '
    'offer OR "schedule a" OR "phone screen" OR "not moving forward"'
)

# Classification keywords, checked in priority order (first match wins).
POSITIVE = (
    "interview", "next step", "move forward", "moving forward", "schedule",
    "phone screen", "phone call", "availability", "times that work",
    "let's talk", "meet with", "offer", "congratulations", "pleased to",
    "would like to speak", "set up a call", "book a time",
)
REJECTION = (
    "unfortunately", "not moving forward", "will not be moving",
    "other candidates", "decided to move", "position has been filled",
    "no longer under consideration", "regret to inform", "not be proceeding",
    "won't be moving", "chosen to pursue", "not selected",
)
RECRUITER = (
    "came across your profile", "saw your background", "reached out",
    "i'm a recruiter", "i am a recruiter", "sourcing", "we think you",
    "strong fit", "based on your profile", "exciting opportunity",
)
AUTO_ACK = (
    "we have received your application", "thank you for applying",
    "application has been received", "received your application",
    "your application was sent", "successfully submitted",
    "thanks for applying", "we've received", "confirm we received",
)


def die(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def get_service(interactive: bool):
    """Return an authorized Gmail API client.

    On the first run (interactive=True) this opens a browser to authorize and
    saves token.json. Afterwards it silently reuses/refreshes that token, which
    is what lets the tool run unattended from Task Scheduler.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        die(
            "Missing Google API packages. Install them with:\n"
            "  python -m pip install -r requirements.txt"
        )

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif interactive:
            if not CREDENTIALS_FILE.exists():
                relaunch = (
                    "run this app again"
                    if getattr(sys, "frozen", False)
                    else "run:  python app/job_email_checker.py --auth"
                )
                die(
                    f"Can't find {CREDENTIALS_FILE.name}.\n"
                    "Download your OAuth client (Desktop app) from Google Cloud and "
                    "save it as\n"
                    f"  {CREDENTIALS_FILE}\n"
                    f"then {relaunch}."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        else:
            setup = (
                "run this app again to authorize"
                if getattr(sys, "frozen", False)
                else "run the one-time setup:\n  python app/job_email_checker.py --auth"
            )
            die(f"Not authorized yet (no valid token.json). {setup}")
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=creds)


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def classify(text: str) -> str:
    """Bucket a message by its content. Order matters: strongest signal first."""
    t = text.lower()
    if any(k in t for k in POSITIVE):
        return "interview"
    if any(k in t for k in REJECTION):
        return "rejection"
    if any(k in t for k in RECRUITER):
        return "recruiter"
    if any(k in t for k in AUTO_ACK):
        return "auto-ack"
    return "other"


def fetch_messages(service, days: int) -> list[dict]:
    """Return classified job-related messages from the last `days` days."""
    query = f"newer_than:{days}d ({SEARCH_TERMS})"
    resp = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=50)
        .execute()
    )
    ids = [m["id"] for m in resp.get("messages", [])]

    out: list[dict] = []
    for mid in ids:
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=mid,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        headers = msg.get("payload", {}).get("headers", [])
        snippet = msg.get("snippet", "")
        subject = _header(headers, "Subject")
        sender = _header(headers, "From")
        out.append(
            {
                "from": sender,
                "subject": subject,
                "snippet": snippet,
                "category": classify(f"{subject} {snippet}"),
            }
        )
    return out


SECTION_TITLES = {
    "interview": "Interviews / positive replies",
    "recruiter": "Recruiter outreach",
    "rejection": "Rejections",
    "other": "Other job-related mail",
    "auto-ack": "Auto-acknowledgments (low priority)",
}
SECTION_ORDER = ["interview", "recruiter", "rejection", "other", "auto-ack"]


def build_summary(messages: list[dict], days: int) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Job email summary - {stamp}",
        "",
        f"Scanned the last {days} day(s). Found {len(messages)} job-related "
        "message(s).",
        "",
    ]
    real = [m for m in messages if m["category"] != "auto-ack"]
    if not real:
        lines.append("**No real responses yet** - only auto-acknowledgments "
                     "(or nothing). Nothing to act on today.")
        lines.append("")
    for cat in SECTION_ORDER:
        group = [m for m in messages if m["category"] == cat]
        if not group:
            continue
        lines.append(f"## {SECTION_TITLES[cat]} ({len(group)})")
        lines.append("")
        for m in group:
            lines.append(f"- **{m['subject'] or '(no subject)'}**")
            lines.append(f"  - From: {m['from']}")
            lines.append(f"  - {m['snippet']}")
        lines.append("")
    return "\n".join(lines)


def build_popup_text(messages: list[dict], days: int) -> str:
    """A short, glanceable version of the summary for the desktop popup."""
    real = [m for m in messages if m["category"] != "auto-ack"]
    lines = [f"{len(real)} real / {len(messages)} total (last {days} day)."]
    if not real:
        lines.append("")
        lines.append("No new real responses today.")
        return "\n".join(lines)
    for cat in ("interview", "recruiter", "rejection", "other"):
        group = [m for m in messages if m["category"] == cat]
        if not group:
            continue
        lines.append("")
        lines.append(f"{SECTION_TITLES[cat]}:")
        for m in group:
            subject = (m["subject"] or "(no subject)")[:70]
            lines.append(f"  - {subject}")
    return "\n".join(lines)


def show_popup(messages: list[dict], days: int) -> None:
    """Show a native Windows popup with the summary. No-op off Windows."""
    if os.name != "nt":
        return
    try:
        import ctypes

        title = "Job inbox check"
        body = build_popup_text(messages, days)
        MB_ICONINFORMATION = 0x40
        MB_SETFOREGROUND = 0x10000
        MB_TOPMOST = 0x40000
        ctypes.windll.user32.MessageBoxW(
            0, body, title, MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST
        )
    except Exception:
        pass  # a failed popup should never break the run


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan Gmail for job responses.")
    parser.add_argument(
        "--auth",
        action="store_true",
        help="One-time setup: open a browser to authorize Gmail access.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.environ.get("JOB_EMAIL_DAYS", "1")),
        help="How many days back to search (default: 1).",
    )
    parser.add_argument(
        "--no-popup",
        action="store_true",
        help="Don't show the desktop popup (still prints and saves the summary).",
    )
    args = parser.parse_args()

    # As a packaged app, the first double-click has no token yet - authorize
    # automatically (opens a browser once) instead of failing with an error.
    frozen = getattr(sys, "frozen", False)
    interactive = args.auth or (frozen and not TOKEN_FILE.exists())

    service = get_service(interactive=interactive)

    if args.auth:
        print("Authorized. token.json saved - future runs need no browser.\n")

    messages = fetch_messages(service, args.days)
    summary = build_summary(messages, args.days)

    print(summary)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"job-email-summary-{date.today().isoformat()}.md"
    out_path.write_text(summary, encoding="utf-8")
    print(f"\nSaved -> {out_path}")

    if not args.no_popup:
        show_popup(messages, args.days)


if __name__ == "__main__":
    # A double-clicked .exe closes instantly on exit; pause so the user can read
    # the summary (or any setup message). No effect when run from source.
    try:
        main()
    finally:
        if getattr(sys, "frozen", False):
            try:
                input("\nPress Enter to close...")
            except (EOFError, KeyboardInterrupt):
                pass
