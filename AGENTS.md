# AGENTS.md — How to work in this repo

## Environment

- Python 3.11+ via `uv`
- CLI tools: `uv`, `git`

## Quick Start

    uv venv && source .venv/bin/activate
    uv pip install -e ".[dev]"
    thunk --help

## Repo Commands

    pytest                         # tests
    pyright src/thunk tests        # typecheck
    ruff check . && ruff format .  # lint/format

## Coding Standards

- Python 3.11+, type annotations on public APIs
- `ruff format` for style, `pytest` for tests
- Keep files <500 LOC; refactor when needed
- Fix root causes, not symptoms

## Git Rules

- Check `git status`/`git diff` before commits
- Atomic commits; push only when asked
- Never destructive ops (`reset --hard`, `force push`) without explicit consent
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`

## Critical Thinking

- Read more code when stuck
- Document unexpected behavior
- Call out conflicts between instructions

## Project Overview

Thunk is a multi-agent ensemble planning CLI. It orchestrates multiple AI agents
(Claude Code, OpenAI Codex) to collaboratively create implementation plans for
feature work, with human-in-the-loop review.

See `DESIGN.md` for the full architecture and design decisions.

## Commands

    thunk init "feature description"     # Start planning session
    thunk wait --session <id>            # Block until turn complete
    thunk continue --session <id>        # Start next turn after user edits
    thunk approve --session <id>         # Lock plan as final
    thunk status --session <id>          # Check progress
    thunk list                           # List all sessions
    thunk clean --session <id>           # Remove session
    thunk diff --session <id>            # Show changes between turns

## Architecture

    src/thunk/
    ├── cli.py           # Click CLI commands
    ├── models.py        # Data models (SessionState, Phase, etc.)
    ├── session.py       # Session management
    ├── orchestrator.py  # Turn orchestration (draft → peer review → synthesis)
    ├── prompts.py       # Agent prompt templates
    └── adapters/
        ├── base.py      # AgentAdapter interface
        ├── claude.py    # Claude Code adapter (with session continuation)
        └── codex.py     # Codex CLI adapter (with session continuation)

## Session File Structure

    .thunk/sessions/<session_id>/
    ├── meta.yaml        # Feature description, timestamp
    ├── state.yaml       # Current turn, phase
    ├── turns/
    │   ├── 001.md       # Turn 1 synthesis
    │   ├── 002.md       # Turn 2
    │   └── ...
    ├── agents/
    │   ├── opus/
    │   │   └── cli_session_id.txt   # For --resume
    │   ├── codex/
    │   │   └── cli_session_id.txt   # For resume
    │   └── turn-001/
    │       ├── opus-draft.md
    │       ├── opus-final.md
    │       └── ...
    └── PLAN.md          # Symlink to approved turn
