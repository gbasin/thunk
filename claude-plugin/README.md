# Thunk Claude Code Plugin

Claude Code plugin for the thunk multi-agent ensemble planning CLI.

## Installation

```bash
# From this repo
claude --plugin-dir ./claude-plugin

# Or symlink to your plugins directory
ln -s /path/to/thunk/claude-plugin ~/.claude/plugins/thunk
```

## Commands

| Command | Description |
|---------|-------------|
| `/thunk:plan <feature>` | Start a planning session |
| `/thunk:continue <session_id>` | Continue after editing |
| `/thunk:approve <session_id>` | Lock plan as final |
| `/thunk:status <session_id>` | Check session status |
| `/thunk:list` | List all sessions |

## Example

```
> /thunk:plan Add rate limiting to API endpoints

Started planning session `f8e7d6c5` for "Add rate limiting to API endpoints"
Agents are working...

Done! Plan ready at: .thunk/sessions/f8e7d6c5/turns/001.md

> [edit the file]

> /thunk:continue f8e7d6c5

Turn 2 complete. Plan at: .thunk/sessions/f8e7d6c5/turns/002.md

> /thunk:approve f8e7d6c5

Plan approved! Final plan: .thunk/sessions/f8e7d6c5/PLAN.md
```

## Skill

The plugin also includes a skill that teaches Claude about thunk syntax and workflow. It activates automatically when discussing planning sessions.
