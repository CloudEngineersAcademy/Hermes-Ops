#!/usr/bin/env python3
"""
Hermes Ops — Session Saver
==========================
Saves the current Hermes session transcript and any tracked files
to the Hermes-Ops GitHub repository on a schedule.

Usage:
    python3 /Users/user/Hermes-Ops/scripts/save_session.py [--on-demand]

Environment:
    GITHUB_TOKEN — Personal Access Token with repo scope.
"""

import os
import sys
import json
import subprocess
import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HERMES_OPS_DIR = Path("/Users/user/Hermes-Ops")
SESSIONS_DIR = HERMES_OPS_DIR / "sessions"
SCRIPTS_DIR = HERMES_OPS_DIR / "scripts"
CONFIGS_DIR = HERMES_OPS_DIR / "configs"
NOTES_DIR = HERMES_OPS_DIR / "notes"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not GITHUB_TOKEN:
    # Fallback: read from a secure location if available
    token_file = Path("/Users/user/.hermes/secrets/github_pat")
    if token_file.exists():
        GITHUB_TOKEN = token_file.read_text().strip()

if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN not set and no fallback found.", file=sys.stderr)
    sys.exit(1)

REMOTE_URL = f"https://{GITHUB_TOKEN}@github.com/CloudEngineersAcademy/Hermes-Ops.git"

TODAY = datetime.date.today()
SESSION_DIR = SESSIONS_DIR / TODAY.isoformat()
SESSION_FILE = SESSION_DIR / "transcript.md"
SESSION_JSON = SESSION_DIR / "metadata.json"

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
        # Nothing to commit is not an error
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

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
from typing import Optional

def save_transcript(transcript_text: str, metadata: Optional[dict] = None):
    """Save a session transcript to the sessions directory."""
    ensure_dir(SESSION_DIR)

    # Append or create transcript
    mode = "a" if SESSION_FILE.exists() else "w"
    with open(SESSION_FILE, mode, encoding="utf-8") as f:
        f.write(transcript_text)
        f.write("\n")

    # Save metadata
    meta = {
        "date": TODAY.isoformat(),
        "timestamp": datetime.datetime.now().isoformat(),
        "source": "hermes-ops-saver",
    }
    if metadata:
        meta.update(metadata)

    with open(SESSION_JSON, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)

    print(f"Saved transcript to {SESSION_FILE}")

def save_file(file_path: Path, dest_relative: str):
    """Copy a file into the Hermes-Ops repo."""
    src = Path(file_path)
    if not src.exists():
        print(f"Source not found: {src}", file=sys.stderr)
        return False

    dest = HERMES_OPS_DIR / dest_relative
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(src, "r", encoding="utf-8") as f:
        content = f.read()

    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Copied {src} -> {dest}")
    return True

def save_configs():
    """Save relevant configuration files."""
    configs_to_save = [
        # (.hermes config, .zshrc, etc. — add as needed)
    ]
    for rel_path in configs_to_save:
        src = Path.home() / rel_path
        save_file(src, f"configs/{rel_path}")

def main():
    on_demand = "--on-demand" in sys.argv

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-save: session snapshot — {timestamp}"

    # In a real deployment, the transcript would come from the Hermes session
    # For now, we save a placeholder that gets replaced by the actual integration
    transcript = f"""# Auto-saved Session Snapshot
**Timestamp:** {timestamp}
**Source:** Hermes Ops automated save
"""

    save_transcript(transcript, {"mode": "scheduled" if not on_demand else "on-demand"})
    git_commit_and_push(commit_msg)

    if on_demand:
        print("\nOn-demand save complete.")

if __name__ == "__main__":
    main()
