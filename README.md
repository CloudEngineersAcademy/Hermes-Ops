# Hermes Ops

> **Owner:** Amir  
> **Email:** casualclassvideos@gmail.com  
> **Repo:** CloudEngineersAcademy/Hermes-Ops (Private)

## Purpose

This repository stores everything we work on together — all chat transcripts, files, scripts, and configuration changes. Every session is saved with timestamps so there's a complete, ongoing record of our work.

## What Gets Saved

- **Chat transcripts** — full conversation logs between Amir and Hermes Agent
- **Files & scripts** — any code, documents, or scripts created during sessions
- **Configuration changes** — any settings, configs, or environment changes, documented with timestamps
- **Session notes** — summaries and context for each session

## Structure

```
Hermes-Ops/
├── README.md              # This file
├── sessions/              # Chat transcripts organized by date
│   └── 2026-09-05/        # Example: first session
│       └── transcript.md
├── scripts/               # Scripts and tools created
├── configs/               # Configuration files and changes
└── notes/                 # Session notes and context
```

## How It Works

- Conversations and work are saved to this repo on a **schedule** (periodic automatic commits)
- You can also request an **on-demand save** at any time
- Each commit includes a timestamp and a brief description of what changed
- The repository is **private** — only you (and collaborators you add) can see it

## Authentication

The repo is accessed using a GitHub Personal Access Token (PAT) with `repo` scope. The token is stored securely and only used for pushing to this repository.


## Security — Secret Redaction

Before any transcript is saved to the repo, the saver scans it for secrets (GitHub PATs, bearer tokens, long hex strings) and redacts them with `***REDACTED_...***` markers. This prevents accidentally committing credentials that may have been pasted in chat.

Patterns detected:
- GitHub PATs (`ghp_`, `gho_`, `ghu_`, etc.)
- Bearer tokens
- Long hex strings (40+ chars, e.g. SHA hashes, API keys)

## Getting Started

This is the initial commit — setting up the repo structure and documentation.

---

*Last updated: 2026-09-06*
