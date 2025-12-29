# AGENTS.md — Thunk Development Guide

## Overview

Thunk is a multi-agent ensemble planning CLI. It orchestrates multiple AI agents (Claude, OpenAI) to collaboratively create implementation plans, with human-in-the-loop review.

## Quick Start

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
thunk --help
```

## Commands

```bash
thunk init "feature description"     # Start planning session
thunk wait --session <id>            # Block until turn complete
thunk continue --session <id>        # Start next turn after user edits
thunk approve --session <id>         # Lock plan as final
thunk status --session <id>          # Check progress
thunk list                           # List all sessions
thunk clean --session <id>           # Remove session
thunk diff --session <id>            # Show changes between turns
```

## Architecture

```
src/thunk/
├── cli.py           # Click CLI commands
├── models.py        # Data models (SessionState, Phase, etc.)
├── session.py       # Session management
├── orchestrator.py  # Turn orchestration (draft → peer review → synthesis)
├── prompts.py       # Agent prompt templates
├── worktree.py      # Git worktree management
└── adapters/
    ├── base.py      # AgentAdapter interface
    ├── claude.py    # Claude Code adapter
    └── openai.py    # OpenAI API adapter
```

## Testing

```bash
pytest                          # Run tests
pyright src/thunk tests         # Type check
ruff check . && ruff format .   # Lint and format
```

## Session File Structure

```
.thunk/sessions/<session_id>/
├── meta.yaml        # Feature description, timestamp
├── state.yaml       # Current turn, phase
├── turns/
│   ├── 001.md       # Turn 1 synthesis
│   ├── 002.md       # Turn 2
│   └── ...
├── agents/
│   └── turn-001/
│       ├── opus-draft.md
│       ├── opus-final.md
│       └── ...
└── PLAN.md          # Symlink to approved turn
```

## Key Concepts

- **Turn**: One iteration of drafting → peer review → synthesis → user review
- **Phase**: Current state within a turn (drafting, peer_review, synthesizing, user_review)
- **Session**: A complete planning effort for one feature
- **Synthesis**: Merging multiple agent plans into one unified plan

## Coding Standards

- Python 3.11+, type annotations on public APIs
- Use `ruff format` for style
- Keep files focused and under 500 lines
- All CLI output is JSON for machine parsing
