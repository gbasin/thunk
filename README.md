# Thunk

Multi-agent ensemble planning CLI. Orchestrates Claude Code and OpenAI Codex to collaboratively create implementation plans with human-in-the-loop review.

## Install

```bash
uv venv && source .venv/bin/activate
uv pip install -e .
```

## Usage

```bash
# Start a planning session
thunk init "Add user authentication"

# Wait for agents to complete
thunk wait --session <session_id>

# Review and edit the plan at .thunk/sessions/<id>/turns/001.md

# Continue to next turn after edits
thunk continue --session <session_id>

# Approve when satisfied
thunk approve --session <session_id>
```

## Commands

| Command | Purpose |
|---------|---------|
| `thunk init "task"` | Start new planning session |
| `thunk wait --session <id>` | Block until turn complete |
| `thunk status --session <id>` | Check progress |
| `thunk continue --session <id>` | Start next turn after edits |
| `thunk approve --session <id>` | Lock plan as final |
| `thunk list` | List all sessions |

## How It Works

1. **init**: Creates session, spawns agents (Claude Code + Codex) to explore codebase
2. **Drafting**: Each agent independently creates a plan draft
3. **Peer Review**: Agents review each other's drafts
4. **Synthesis**: Plans are merged into a unified proposal
5. **User Review**: Human edits `.thunk/sessions/<id>/turns/NNN.md`
6. **Iterate**: `continue` starts next turn incorporating feedback
7. **Approve**: Locks the final plan

## Architecture

See [DESIGN.md](DESIGN.md) for full design documentation.

## Development

```bash
pytest                         # tests
pyright src/thunk tests        # typecheck
ruff check . && ruff format .  # lint/format
```
