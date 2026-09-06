#!/usr/bin/env python3
"""Verify that the staged transcript has no full PAT strings."""
import re
import subprocess
import sys

# Get the staged version of the transcript
result = subprocess.run(
    ["git", "show", ":sessions/2026-09-06/transcript.md"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print("Could not read staged transcript.")
    sys.exit(1)

content = result.stdout

# Check for any full PAT pattern (ghp_/gho_/ghu_/ghr_/ghs_ + 36+ alphanumeric chars)
pat_pattern = re.compile(r'gh[pouahs]_[A-Za-z0-9]{36,}', re.IGNORECASE)
matches = pat_pattern.findall(content)

print(f"Staged transcript — full PAT matches: {len(matches)}")
for m in matches:
    print(f"  FOUND: {m[:30]}...")

# Check for any 40+ char hex strings (potential API keys)
hex_pattern = re.compile(r'[A-Fa-f0-9]{40,}')
hex_matches = hex_pattern.findall(content)
print(f"Staged transcript — long hex matches: {len(hex_matches)}")

# Show line count and size
lines = content.splitlines()
print(f"Staged transcript lines: {len(lines)}")
print(f"Staged transcript size: {len(content)} bytes")

if not matches and not hex_matches:
    print("\n✓ Staged transcript looks clean — no full secrets found.")
    sys.exit(0)
else:
    print("\n⚠ Secrets found in staged transcript — DO NOT PUSH.")
    sys.exit(1)
