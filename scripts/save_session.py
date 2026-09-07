#!/usr/bin/env python3
"""
Hermes Ops — Session Saver (with transcript integration)
=========================================================
Reads session transcripts from ~/.hermes/state.db and saves them
incrementally to the Hermes-Ops GitHub repository.

Reads messages from the Hermes sessions table, tracks the last saved
message timestamp, and only saves new/updated messages each run.

Usage:
    python3 /Users/user/Hermes-Ops/scripts/save_session.py [--on-demand] [--session-id ID]

Environment:
    GITHUB_TOKEN — Personal Access Token with repo scope.
    HERMES_STATE_DB — path to state.db (default: ~/.hermes/state.db)
"""

import os
import sys
import json
import re
import sqlite3
import subprocess
import datetime
from pathlib import Path
from typing import Optional, List

# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------
# Patterns that look like secrets. Matched case-insensitively.
SECRET_PATTERNS = [
    # GitHub PATs: ghp_, gho_, ghr_, ghs_, ghu_
    (re.compile(r'(gh[pouahs]_[A-Za-z0-9]{36,})', re.IGNORECASE), '***REDACTED_GITHUB_TOKEN***'),
    # Generic hex tokens (40+ hex chars) — API keys, hashes, etc.
    (re.compile(r'[A-Fa-f0-9]{40,}', re.IGNORECASE), '***REDACTED_TOKEN***'),
    # Bearer tokens
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_.~+/]+=*', re.IGNORECASE), '***REDACTED_BEARER_TOKEN***'),
    # AWS access keys (AKIA + 16 uppercase alphanumeric)
    (re.compile(r'AKIA[0-9A-Z]{16}', re.IGNORECASE), '***REDACTED_AWS_KEY***'),
    # Private key headers (RSA, OPENSSH, EC, PGP)
    (re.compile(r'-----BEGIN (RSA |EC |OPENSSH |PGP)PRIVATE KEY-----', re.IGNORECASE), '***REDACTED_PRIVATE_KEY***'),
]

def redact_secrets(text: str) -> str:
    """Scan text for secrets and replace them with redaction markers."""
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HERMES_OPS_DIR = Path("/Users/user/Hermes-Ops")
SESSIONS_DIR = HERMES_OPS_DIR / "sessions"
SCRIPTS_DIR = HERMES_OPS_DIR / "scripts"
CONFIGS_DIR = HERMES_OPS_DIR / "configs"
NOTES_DIR = HERMES_OPS_DIR / "notes"

# Where the Hermes session database lives
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
STATE_DB = Path(os.environ.get("HERMES_STATE_DB", str(HERMES_HOME / "state.db")))

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not GITHUB_TOKEN:
    token_file = HERMES_OPS_DIR / ".env"
    if token_file.exists():
        for line in token_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("GITHUB_TOKEN=") and not line.startswith("#"):
                GITHUB_TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN not set and no fallback found.", file=sys.stderr)
    sys.exit(1)

REMOTE_URL = f"https://{GITHUB_TOKEN}@github.com/CloudEngineersAcademy/Hermes-Ops.git"

# Track file: stores the last saved message timestamp per session
TRACK_FILE = HERMES_OPS_DIR / ".last_saved.json"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def run(cmd, cwd=None):
    """Run a shell command, return (stdout, stderr, returncode)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd,
        env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN}
    )
    return result.stdout, result.stderr, result.returncode

def ensure_dir(path):
    path.mkdir(parents=True, exist_ok=True)

def git_commit_and_push(commit_msg):
    """Stage all changes, commit, and push."""
    stdout, stderr, rc = run("git add -A", cwd=HERMES_OPS_DIR)
    if rc != 0:
        print(f"git add failed: {stderr}", file=sys.stderr)
        return False

    stdout, stderr, rc = run(f'git commit -m "{commit_msg}"', cwd=HERMES_OPS_DIR)
    if rc != 0:
        if "nothing to commit" in stderr.lower():
            print("Nothing to commit — skipping.")
            return True
        print(f"git commit failed: {stderr}", file=sys.stderr)
        return False

    stdout, stderr, rc = run("git push origin main", cwd=HERMES_OPS_DIR)
    if rc != 0:
        print(f"git push failed: {stderr}", file=sys.stderr)
        return False

    print(f"Pushed: {commit_msg}")
    return True

def load_tracker() -> dict:
    """Load the last-saved tracker from disk."""
    if TRACK_FILE.exists():
        try:
            return json.loads(TRACK_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def save_tracker(tracker: dict):
    """Persist the tracker."""
    TRACK_FILE.write_text(json.dumps(tracker, indent=2, default=str))

# ---------------------------------------------------------------------------
# Hermes DB access
# ---------------------------------------------------------------------------
def get_db_connection() -> sqlite3.Connection:
    """Open a read-only connection to the Hermes state database."""
    if not STATE_DB.exists():
        raise FileNotFoundError(f"Hermes state DB not found: {STATE_DB}")
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    return conn

def get_active_sessions(conn) -> List[sqlite3.Row]:
    """Return sessions that are currently active (no ended_at) or recently ended."""
    cur = conn.cursor()
    cutoff = datetime.datetime.now().timestamp() - (7 * 24 * 3600)
    cur.execute(
        """
        SELECT id, title, display_name, source, started_at, ended_at,
               message_count, cwd, git_branch, git_repo_root
        FROM sessions
        WHERE (ended_at IS NULL OR ended_at > ?)
        ORDER BY started_at DESC
        """,
        (cutoff,)
    )
    return cur.fetchall()

def get_session_messages(conn, session_id: str) -> List[sqlite3.Row]:
    """Return all messages for a session, ordered by timestamp."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, role, content, timestamp, token_count, tool_calls,
               tool_name, effect_disposition, display_kind, display_metadata
        FROM messages
        WHERE session_id = ?
        ORDER BY timestamp ASC
        """,
        (session_id,)
    )
    return cur.fetchall()

def get_new_messages(
    conn,
    session_id: str,
    last_saved_ts: Optional[float]
) -> List[sqlite3.Row]:
    """Return messages newer than last_saved_ts (incremental)."""
    cur = conn.cursor()
    if last_saved_ts is not None:
        cur.execute(
            """
            SELECT id, role, content, timestamp, token_count, tool_calls,
                   tool_name, effect_disposition, display_kind, display_metadata
            FROM messages
            WHERE session_id = ? AND timestamp > ?
            ORDER BY timestamp ASC
            """,
            (session_id, last_saved_ts)
        )
    else:
        return get_session_messages(conn, session_id)
    return cur.fetchall()

# ---------------------------------------------------------------------------
# Transcript formatting
# ---------------------------------------------------------------------------
def format_role(role: str) -> str:
    """Map role to a display label."""
    role = (role or "").lower()
    if role == "user":
        return "Amir"
    elif role == "assistant":
        return "Hermes Agent"
    elif "tool" in role:
        return "Tool"
    return role.title() if role else "Unknown"

def format_transcript(
    session: sqlite3.Row,
    messages: List[sqlite3.Row],
    source_name: str = "Amir"
) -> str:
    """Format a session + its messages into a markdown transcript."""
    lines = []

    started = datetime.datetime.fromtimestamp(session["started_at"]).strftime("%Y-%m-%d %H:%M")
    ended = session["ended_at"]
    end_str = datetime.datetime.fromtimestamp(ended).strftime("%Y-%m-%d %H:%M") if ended else "in progress"

    session_id_short = (session["id"] or "")[:20]
    title = session["title"] or "Untitled"

    lines.append(f"# Session: {started[:10]} — {title}")
    lines.append("")
    lines.append(f"**Date:** {started[:10]}")
    lines.append(f"**Session ID:** {session_id_short}...")
    lines.append(f"**Source:** {session['source'] or 'desktop'}")
    lines.append(f"**Messages in this save:** {len(messages)}")
    lines.append(f"**Status:** {end_str}")
    lines.append("")

    if session["cwd"]:
        lines.append(f"**Working directory:** {session['cwd']}")
        lines.append("")

    lines.append("---")
    lines.append("")

    for msg in messages:
        role_label = format_role(msg["role"])
        content = msg["content"] or ""
        display_kind = msg["display_kind"] or ""
        ts = datetime.datetime.fromtimestamp(msg["timestamp"]).strftime("%H:%M:%S") if msg["timestamp"] else ""

        if "think" in display_kind or "reasoning" in display_kind:
            lines.append(f"**{role_label} [reasoning]:**")
            lines.append("")
            lines.append(content.strip())
            lines.append("")
        elif "tool_call" in display_kind or msg["tool_calls"]:
            tool_info = msg["tool_calls"] or ""
            lines.append(f"**{role_label} [tool call]:**")
            lines.append(f"```")
            lines.append(tool_info[:500])
            lines.append("```")
            lines.append("")
        else:
            if ts:
                lines.append(f"**{role_label}** ({ts}):")
            else:
                lines.append(f"**{role_label}:**")
            lines.append("")
            lines.append(content.strip())
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*Session end: {end_str}*")

    return "\n".join(lines)

def format_metadata(session: sqlite3.Row, messages: List[sqlite3.Row], source_name: str) -> dict:
    """Return metadata dict for the save."""
    ended = session["ended_at"]
    return {
        "session_id": session["id"],
        "title": session["title"],
        "source": session["source"],
        "started_at": datetime.datetime.fromtimestamp(session["started_at"]).isoformat(),
        "ended_at": datetime.datetime.fromtimestamp(ended).isoformat() if ended else None,
        "messages_saved": len(messages),
        "total_messages": session["message_count"] or 0,
        "cwd": session["cwd"] if session["cwd"] is not None else None,
        "saved_by": "hermes-ops-transcript",
    }

# ---------------------------------------------------------------------------
# main save logic
# ---------------------------------------------------------------------------
def save_all_active_sessions(on_demand: bool = False):
    """Save transcripts for all active sessions incrementally."""
    tracker = load_tracker()
    conn = get_db_connection()

    try:
        sessions = get_active_sessions(conn)
        if not sessions:
            print("No active sessions found in Hermes state DB.")
            return

        print(f"Found {len(sessions)} active session(s).")

        any_saved = False
        for session in sessions:
            session_id = session["id"]
            last_saved = tracker.get(session_id, {}).get("last_message_ts")

            messages = get_new_messages(conn, session_id, last_saved)

            if not messages:
                print(f"  Session {session_id[:20]}...: no new messages.")
                continue

            source_name = "Amir"
            today = datetime.date.today()
            session_dir = SESSIONS_DIR / today.isoformat()
            ensure_dir(session_dir)

            transcript_file = session_dir / "transcript.md"
            mode = "a" if transcript_file.exists() else "w"

            transcript = format_transcript(session, messages, source_name)
            transcript = redact_secrets(transcript)

            with open(transcript_file, mode, encoding="utf-8") as f:
                if mode == "a" and transcript_file.exists():
                    f.write("\n\n")
                f.write(transcript)
                f.write("\n")

            meta_file = session_dir / f"{session_id[:20]}.meta.json"
            metadata = format_metadata(session, messages, source_name)
            meta_file.write_text(json.dumps(metadata, indent=2, default=str))

            latest_ts = max(m["timestamp"] for m in messages if m["timestamp"])
            tracker[session_id] = {
                "last_message_ts": latest_ts,
                "last_saved_at": datetime.datetime.now().isoformat(),
                "messages_saved": len(messages),
                "title": session["title"],
            }

            any_saved = True
            print(f"  Saved {len(messages)} message(s) from session {session_id[:20]}... to {transcript_file}")

        if any_saved:
            save_tracker(tracker)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            mode_label = "on-demand" if on_demand else "scheduled"
            commit_msg = f"Transcript save [{mode_label}]: {len(sessions)} session(s) — {timestamp}"
            git_commit_and_push(commit_msg)
        else:
            print("No new messages to save across all sessions.")

    finally:
        conn.close()


def save_specific_session(session_id: str, on_demand: bool = False):
    """Save a specific session by ID (full extract, not incremental)."""
    conn = get_db_connection()
    try:
        sessions = get_active_sessions(conn)
        session = None
        for s in sessions:
            if s["id"] == session_id:
                session = s
                break

        if not session:
            cur = conn.cursor()
            cur.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cur.fetchone()
            if row:
                session = row
            else:
                print(f"Session {session_id} not found.", file=sys.stderr)
                return

        messages = get_session_messages(conn, session_id)

        today = datetime.date.today()
        session_dir = SESSIONS_DIR / today.isoformat()
        ensure_dir(session_dir)

        transcript_file = session_dir / f"{session_id[:20]}.transcript.md"
        transcript = format_transcript(session, messages)
        transcript = redact_secrets(transcript)
        transcript_file.write_text(transcript, encoding="utf-8")

        meta_file = session_dir / f"{session_id[:20]}.meta.json"
        metadata = format_metadata(session, messages, "Amir")
        meta_file.write_text(json.dumps(metadata, indent=2, default=str))

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Full transcript: {session['title'] or session_id[:20]} — {timestamp}"
        git_commit_and_push(commit_msg)

        print(f"Saved full transcript for {session_id[:20]}... → {transcript_file}")

    finally:
        conn.close()

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    on_demand = "--on-demand" in sys.argv
    session_id = None
    for arg in sys.argv:
        if arg.startswith("--session-id="):
            session_id = arg.split("=", 1)[1]

    if session_id:
        save_specific_session(session_id, on_demand)
    else:
        save_all_active_sessions(on_demand)

if __name__ == "__main__":
    main()
