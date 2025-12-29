# Thunk: Multi-Agent Ensemble Planning CLI

## Overview

A Python CLI that orchestrates multiple AI coding agents (different models) to independently plan feature work, then synthesizes their outputs into a unified plan with human-in-the-loop review.

**Key design choice**: Thunk is designed to be **agent-invokable**—called as a tool from parent agent harnesses (Claude Code, etc.) rather than used directly by humans. All output is JSON-parseable.

Inspired by [Factory Droid's planning architecture](https://factory.ai/news/code-droid-technical-report):
- "A droid is only as good as its plan"
- Multi-model sampling for diversity and robustness
- Subtask decomposition with explicit plan tracking

## Core Concepts

### Ensemble Planning
Each agent independently explores the codebase and drafts a plan. Variation in inference engines/models leads to different observations. A synthesizer merges the best ideas.

### File-Based Protocol
Agents communicate via well-known files in `.thunk/`. This is agent-agnostic—any tool that can read/write files can participate.

### Async Questions
Agents can post questions mid-planning. The orchestrator collects and routes them to the user asynchronously.

---

## MVP Scope: Planning Phase Only

### Commands

All commands output JSON. Minimal command set—the PLAN file is the interface.

```bash
# Session management
thunk init "Add caching layer to API"       # Start session
thunk list                                   # List all sessions
thunk clean --session <id>                   # Remove session data

# Core loop (only 3 commands needed)
thunk wait --session <id>                    # Block until turn complete, returns user_file path
thunk continue --session <id>               # User done editing, start next turn
thunk approve --session <id>                 # Lock current plan as final

# Utilities
thunk status --session <id>                  # Check progress without blocking
thunk diff --session <id>                    # Show changes between turns
```

### Example: Claude Code Tool Call Sequence

Simple 3-command loop:

```
Step 1: thunk init "Add caching layer"
        → {"session_id": "abc123", "turn": 1, "hint": "call wait"}

Step 2: thunk wait --session abc123
        → {"turn": 1, "phase": "user_review",
           "file": ".thunk/sessions/abc123/turns/001.md",
           "has_questions": true,
           "hint": "User should edit file, then call continue or approve"}

Step 3: Claude tells user:
        "Turn 1 ready at .thunk/sessions/abc123/turns/001.md
         There are questions to answer. Edit the file, then let me know."

Step 4: User edits file (answers questions, makes changes)

Step 5: User says "done with edits"
        Claude calls: thunk continue --session abc123
        → {"turn": 2, "phase": "working", "hint": "call wait"}

Step 6: thunk wait --session abc123
        → {"turn": 2, "phase": "user_review",
           "file": ".thunk/sessions/abc123/turns/002.md",
           "has_questions": false,
           "hint": "No more questions. User can edit or approve"}

Step 7: User reviews, says "looks good"
        Claude calls: thunk approve --session abc123
        → {"phase": "approved", "final_turn": 2,
           "plan_path": ".thunk/sessions/abc123/PLAN.md"}
```

**Core loop**: `wait` → user edits → `continue` (or `approve`)

### Unified PLAN File Format

One file format for everything—questions, plan content, user feedback:

```markdown
# Plan: Add Caching Layer

## Questions (please answer inline)

### Q1: Redis or in-memory caching?
**Context:** Redis enables horizontal scaling but adds infrastructure.
**Answer:**

### Q2: Cache invalidation strategy?
**Context:** Time-based TTL, manual invalidation, or both?
**Answer:**

---

## Summary

Use Redis for distributed caching with decorator-based integration...

## Tasks

- [ ] **Task 1**: Create Redis client wrapper
  - **Files:** `src/cache/redis_client.py`
  - **Rationale:** Encapsulate connection logic

## Risks

- TBD (depends on answers above)
```

**User edits naturally** - answers questions, modifies content, adds comments. Agents interpret the diff for next turn.

### Iterative Planning Flow with Critique Rounds

Plans evolve through multiple refinement rounds. Each round produces a versioned plan file (never overwritten):

```
┌─────────────────────────────────────────────────────────────────┐
│ Phase: EXPLORE                                                  │
│   ├── Spawn agents to understand codebase                       │
│   ├── Agents write questions to .thunk/sessions/<id>/questions/ │
│   └── Wait for all agents                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase: Q&A                                                      │
│   ├── thunk questions → collect all questions                   │
│   ├── Route to user, get answers                                │
│   └── thunk answer → store answers                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase: SKELETON (Plan v1)                                       │
│   ├── Spawn agents with: feature + Q&A + "write skeleton plan"  │
│   ├── Each agent writes PLAN-001.md (high-level approach)       │
│   └── Synthesize into .thunk/synthesis/PLAN-001.md              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase: CRITIQUE (repeat until approved)                         │
│   ├── User reviews synthesized plan                             │
│   ├── User provides critique OR approves                        │
│   └── If critique: agents see feedback, write PLAN-00N.md       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase: APPROVED                                                 │
│   ├── Final plan locked                                         │
│   └── Ready for execution (future)                              │
└─────────────────────────────────────────────────────────────────┘
```

**Version tracking (never overwrite):**
```
worktree-thunk-abc123-opus/
├── PLAN-001.md   # Skeleton: high-level approach
├── PLAN-002.md   # After critique round 1: more detail
├── PLAN-003.md   # After critique round 2: fully specified
└── PLAN.md       # Symlink to latest version
```

**Plan maturity levels:**
- **Skeleton (v1)**: Major components, key decisions, rough task outline
- **Draft (v2+)**: Detailed tasks, file lists, dependencies, rationale
- **Final**: Fully specified with risks, alternatives, implementation notes

### Multi-Session Support

Multiple thunk sessions can run in parallel:

```bash
# Start multiple sessions
s1=$(thunk init "Add caching" | jq -r .session_id)
s2=$(thunk init "Fix auth bug" | jq -r .session_id)

# Check specific session
thunk status --session $s1

# List all sessions
thunk list  # returns [{"session_id": "abc", "status": "exploring"}, ...]
```

---

## File Structure

Simple user-facing structure. Agent internals in optional subdirectory:

```
.thunk/
├── config.yaml                      # Global agent configs
└── sessions/
    └── swift-river/                 # Human-friendly session ID
        ├── meta.yaml                # Task description, timestamp
        ├── state.yaml               # {turn: 2, phase: "user_review", agent_plan_ids: {...}}
        │
        ├── bold-peak.md             # Agent's working plan (opaque name, thunk-managed)
        ├── calm-forest.md           # Another agent's working plan
        │
        ├── turns/                   # USER-FACING: numbered synthesis files
        │   ├── 001.md               # Turn 1 synthesis (user edits this)
        │   ├── 001.snapshot.md      # Pre-edit snapshot for diffing
        │   ├── 002.md               # Turn 2 synthesis
        │   └── ...
        │
        ├── agents/                  # Agent work for transparency
        │   ├── opus/
        │   │   └── cli_session_id.txt   # Claude Code session ID (for --resume)
        │   ├── codex/
        │   │   └── cli_session_id.txt   # Codex session ID (for resume)
        │   ├── turn-001/
        │   │   ├── opus-draft.md
        │   │   ├── opus-final.md    # After peer review
        │   │   ├── codex-draft.md
        │   │   └── codex-final.md
        │   └── turn-002/
        │       └── ...
        │
        ├── workdir/                 # Agent working directories
        │   ├── opus/
        │   └── codex/
        │
        └── PLAN.md                  # Symlink to approved turn
```

**Naming:** Session IDs and agent plan files use human-friendly names like `swift-river`, `bold-peak`. This prevents models from getting confused about which file belongs to which agent—they just follow the path given in the prompt.

**User sees**: `turns/001.md`, `turns/002.md`, etc.
**Agents read/write**: Their opaque working file (e.g., `bold-peak.md`) synced after each synthesis
**Debug/inspect**: `agents/` subdirectory has all drafts and peer-reviewed versions

**Turn flow:**
1. Agents read their working file (`bold-peak.md`), write draft
2. Peer review, write final
3. Synthesis → writes to `turns/NNN.md` AND overwrites each agent's working file
4. User edits `turns/NNN.md`
5. Next turn: agents read their file (now contains synthesis), get user diff

---

## Plan Format (Markdown with Required Sections)

Using markdown instead of YAML—more natural for agents and humans. Required sections are lintable.

```markdown
# Plan: Add Caching Layer to API

**Version:** 3
**Status:** draft | approved
**Feature:** Add caching layer to API

## Summary

Brief 2-3 sentence overview of the approach. This section is required.

## Narrative

This approach uses Redis for distributed caching because the API runs
on multiple instances. We wrap the Redis client for testability and
use decorators to avoid invasive changes to existing handlers.

This section explains the reasoning and tradeoffs in detail.

## Tasks

- [ ] **Task 1**: Create Redis client wrapper
  - **Files:** `src/cache/redis_client.py` (create), `src/cache/__init__.py` (modify)
  - **Rationale:** Encapsulate connection logic for testability
  - **Dependencies:** none

- [ ] **Task 2**: Add cache decorator for API endpoints
  - **Files:** `src/api/decorators.py` (create), `src/api/routes.py` (modify)
  - **Rationale:** Non-invasive way to add caching to existing handlers
  - **Dependencies:** Task 1

## Open Questions

- **Q1**: Should cache TTL be configurable per-endpoint?
  - **Context:** Some endpoints have data that changes frequently
  - **Blocking:** no

## Risks

- **Cache invalidation complexity** (severity: medium)
  - **Mitigation:** Start with time-based expiry, add explicit invalidation later

## Alternatives Considered

- **In-memory LRU cache**: Rejected because it won't work with multiple API instances
```

**Lint rules (enforced by `thunk lint`):**
- Must have `# Plan:` header
- Must have `## Summary` section (required)
- Must have `## Tasks` section (required)
- Tasks must have **Files:** and **Dependencies:** fields
- Should have `## Risks` section (warning if missing)
- May have `## Narrative`, `## Open Questions`, `## Alternatives Considered` (optional)

---

## Agent Adapters

### Session Continuation

Both Claude Code and Codex support **session continuation** in headless mode. This is critical for preserving context across turns—agents accumulate codebase understanding rather than starting fresh each time.

**Why this matters:**
- Turn 1 (explore): Agent reads files, understands patterns, builds mental model
- Turn 2+ (refine): Agent resumes with full context, doesn't re-explore from scratch
- Dramatically improves plan quality and reduces token usage

**Session ID storage:**
```
.thunk/sessions/<session_id>/agents/
├── opus/
│   └── cli_session_id.txt    # Claude Code session ID
└── codex/
    └── cli_session_id.txt    # Codex session ID
```

### Context Injection Strategy

**Problem:** How do agents receive updates from synthesis and user edits without diverging from canonical state?

**Solution:** Opaque per-agent working files + synthesis overwrite + user edits as diff.

1. **Per-agent working files with opaque names:** Each agent has their own plan file with a human-friendly but opaque name (e.g., `bold-peak.md`). The mapping from agent_id → plan_id is stored in `state.yaml`. This prevents models from getting confused about which file belongs to which agent.

2. **Lazy initialization:** Plan IDs are generated when the orchestrator first runs, not at session creation. This decouples session management from agent configuration.

3. **After AI synthesis:** Thunk overwrites each agent's working file with the synthesis. All agents start the next turn from the same canonical baseline.

4. **After user edits:** Agents receive a diff of user changes in the prompt, preserving their agency to interpret feedback.

5. **Snapshot for diffing:** When synthesis is written, a `.snapshot.md` copy is saved. We diff against the snapshot to extract only user changes.

6. **Self-discovery:** Agents explore the codebase themselves (AGENTS.md, README.md) rather than receiving context in prompts. Session continuation preserves this knowledge.

**Turn flow:**
```
Turn 1:
  - Orchestrator generates plan IDs: {opus: "bold-peak", codex: "calm-forest"}
  - Agents explore codebase, discover AGENTS.md/README.md
  - Write drafts to agents/turn-001/{agent}-draft.md
  - Peer review, write finals
  - Synthesis → turns/001.md + bold-peak.md + calm-forest.md (all identical)
  - User edits turns/001.md

Turn 2:
  - Agents read their working file (bold-peak.md) - contains synthesis
  - Prompt includes user diff: "incorporate this feedback: [diff]"
  - Session continuation preserves codebase knowledge from Turn 1
```

**Why this works:**
- Opaque file names prevent model confusion
- Synthesis overwrite keeps all agents in sync (no divergence)
- User edits as diff preserves agent judgment
- Self-discovery is more agentic than prompt injection
- Session continuation preserves exploration context

### Claude Code (Opus 4.5)

```python
def spawn_claude_agent(
    worktree: Path,
    prompt: str,
    config: AgentConfig,
    session_file: Path | None = None  # For continuation
) -> tuple[Process, str]:
    """Spawn Claude Code agent, optionally resuming a session."""

    cmd = [
        "claude",
        "--model", "opus",
        "--print",
        "--output-format", "json",  # Capture session_id
        "--cwd", str(worktree),
    ]

    # Resume if we have a previous session
    if session_file and session_file.exists():
        cli_session_id = session_file.read_text().strip()
        cmd.extend(["--resume", cli_session_id])

    cmd.extend(["-p", prompt])

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # Parse JSON output to get session_id for next turn
    output = json.loads(proc.stdout.read())
    new_session_id = output.get("session_id")

    return proc, new_session_id


# Usage across turns:
# Turn 1: session_id = spawn_claude_agent(worktree, explore_prompt, config)
#         save session_id to .thunk/sessions/<id>/agents/opus/cli_session_id.txt
# Turn 2: spawn_claude_agent(worktree, refine_prompt, config, session_file=session_file)
#         Agent resumes with full exploration context intact
```

### OpenAI Codex

```python
def spawn_codex_agent(
    worktree: Path,
    prompt: str,
    config: AgentConfig,
    session_file: Path | None = None  # For continuation
) -> tuple[Process, str | None]:
    """Spawn Codex CLI agent, optionally resuming a session."""

    cmd = ["codex", "exec"]

    # Resume if we have a previous session
    if session_file and session_file.exists():
        cmd.extend(["resume", "--last"])  # Or use specific session ID

    cmd.append(prompt)

    proc = subprocess.Popen(
        cmd,
        cwd=worktree,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    return proc, None  # Codex handles session internally


# Codex session storage: ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
# Use `codex resume --last` or `codex resume <SESSION_ID>` for continuation
```

**Note:** Codex stores sessions at `~/.codex/sessions/` as JSONL files. The `codex resume` command can resume by session ID or use `--last` for most recent.

### Agent Prompt Templates

**EXPLORE Phase Prompt:**
```markdown
# Exploration Task

You are exploring a codebase to prepare for planning a feature implementation.

## Feature Request
{feature_description}

## Project Context
{agents_md_content}

## Instructions
1. Explore the codebase to understand existing patterns relevant to this feature
2. Identify any questions that would affect how you'd implement this
3. Write your questions to: .thunk/sessions/{session_id}/questions/{agent_id}.md

## Question Format (markdown)
# Questions

## Q1: Should we use Redis or in-memory caching?
**Context:** Redis adds complexity but enables distributed caching
**Blocking:** yes

## Q2: ...

When done, write: {"phase": "explore", "status": "done"} to status.json
```

**SKELETON Phase Prompt (v1):**
```markdown
# Skeleton Planning Task

Write a HIGH-LEVEL skeleton plan. Focus on major decisions and approach, not details.

## Feature Request
{feature_description}

## Project Context
{agents_md_content}

## Questions & Answers
{all_questions_and_answers}

## Instructions
- Write PLAN-001.md with a skeleton plan
- Focus on: overall approach, major components, key decisions
- Don't worry about detailed task breakdowns yet
- Include rough file list and dependencies
- Identify the biggest risks/unknowns

This is version 1. It will be critiqued and refined in subsequent rounds.
```

**REFINE Phase Prompt (v2+):**
```markdown
# Plan Refinement Task

The user edited the synthesized plan. Interpret their changes and improve your plan.

## Feature Request
{feature_description}

## Original Synthesized Plan (v{prev_version})
{original_synthesis}

## User-Edited Plan (what user changed)
{user_edited_plan}

## Diff (changes user made)
{diff}

## Your Previous Plan (v{prev_version}/final.md)
{your_previous_plan}

## Other Agents' Previous Plans
{other_agent_plans}

## Instructions
Interpret the user's natural edits:
- **Deletions/strikethroughs**: User doesn't want this. Remove or rethink.
- **Additions**: User added text. This is a requirement or question.
- **Questions in text**: User wants these answered. Address them directly.
- **Comments (<!-- -->)**: User feedback. Incorporate and remove marker.
- **Unchanged sections**: User is satisfied. Keep unless you can improve.

User's direct edits are REQUIREMENTS - incorporate them exactly.
User's questions need your THINKING - address each one thoroughly.

Write v{new_version}/draft.md that addresses ALL user feedback.
```

---

## Synthesis Logic

The synthesizer agent receives all agent plans (for a given version) and produces a merged result:

```markdown
# Synthesis Task

You are synthesizing multiple implementation plans into a unified plan.

## Plans to Merge

### Opus Agent (PLAN-{version}.md)
{opus_plan_content}

### Codex Agent (PLAN-{version}.md)
{codex_plan_content}

## Instructions
1. Identify common themes across plans
2. Note where plans diverge—pick the best approach or flag for user review
3. Combine the best ideas from each plan
4. Merge narratives into a coherent explanation
5. Produce a unified plan in the standard markdown format

## Conflict Handling
If agents disagree on approach, add a ## Conflicts section:

## Conflicts

- **Caching strategy**
  - Opus: Redis with TTL
  - Codex: In-memory LRU
  - **Recommendation:** Redis (enables horizontal scaling)
  - **Needs user input:** no

## Output
Write to .thunk/sessions/{session_id}/synthesis/PLAN-{version}.md
```

---

## Configuration (config.yaml)

```yaml
agents:
  - id: opus
    type: claude
    model: claude-opus-4-5-20251101
    enabled: true

  - id: codex
    type: openai
    model: codex-mini-latest  # or o3, gpt-4.5, etc.
    enabled: true

synthesizer:
  type: claude
  model: opus

settings:
  timeout: null          # No timeout by default
  auto_synthesize: true  # Run synthesis when all agents done
  worktree_prefix: "worktree-thunk"
```

---

## Implementation Plan

### Phase 1: Project Setup
- [ ] Create `~/Documents/GitHub/thunk`
- [ ] Initialize Python project with `uv`
- [ ] Set up CLI framework (click or typer)
- [ ] Create AGENTS.md for the thunk project itself

### Phase 2: Core Infrastructure
- [ ] `.thunk/` directory management
- [ ] Git worktree creation/cleanup
- [ ] Config loading (config.yaml)
- [ ] Status file polling/monitoring

### Phase 3: Agent Adapters
- [ ] Claude Code adapter (subprocess)
- [ ] OpenAI Codex adapter (API)
- [ ] Agent prompt templating
- [ ] Output capture and logging

### Phase 4: Orchestration
- [ ] `thunk init` - setup session, spawn agents
- [ ] `thunk status` - show agent progress
- [ ] Agent completion detection
- [ ] Auto-synthesis trigger

### Phase 5: Question Routing
- [ ] Question file format and polling
- [ ] `thunk questions` - display pending
- [ ] `thunk answer` - interactive answering
- [ ] Answer distribution to agents

### Phase 6: Synthesis
- [ ] Collect all agent plans
- [ ] Synthesizer agent prompt
- [ ] `thunk synthesize` command
- [ ] Conflict detection and flagging

### Phase 7: Review & Approval
- [ ] `thunk show` - display synthesized plan
- [ ] `thunk approve` - lock plan
- [ ] Plan export formats

---

## Key Files to Create

```
~/Documents/GitHub/thunk/
├── pyproject.toml
├── AGENTS.md
├── src/thunk/
│   ├── __init__.py
│   ├── cli.py              # CLI entry points (click/typer)
│   ├── orchestrator.py     # Phase management, agent coordination
│   ├── session.py          # Session lifecycle, state management
│   ├── config.py           # Config loading (config.yaml)
│   ├── worktree.py         # Git worktree create/cleanup
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py         # Agent adapter interface
│   │   ├── claude.py       # Claude Code subprocess adapter
│   │   └── openai.py       # OpenAI API adapter
│   ├── schema.py           # PLAN.yaml pydantic models
│   ├── prompts.py          # Prompt templates (explore, plan, synthesize)
│   ├── synthesizer.py      # Plan merging logic
│   └── questions.py        # Question collection/routing
└── tests/
    ├── test_cli.py
    ├── test_session.py
    ├── test_worktree.py
    └── test_schema.py
```

---

## Decisions Made

- **Project name**: thunk
- **Initial agents**: Opus + Codex from day 1
- **Interface**: CLI with JSON output, 3 core commands (wait, continue, approve)
- **Turn-based model**: Each turn creates numbered file (001.md, 002.md, ...)
- **Simple user-facing structure**: `turns/` has what user sees, `agents/` has internals
- **Unified PLAN format**: One file format with Questions section when needed
- **File-based everything**: Questions answered in file, critique via file edits
- **No special syntax**: Users edit naturally, agents interpret the diff
- **Agent collaboration**: Drafts → peer review → finals → synthesis per turn
- **Sessions**: Multi-session support via session IDs
- **Git tracking**: Minimal—`.thunk/` is gitignored
- **Response format**: Returns file paths (not content), includes hints
- **Session continuation**: Agents resume CLI sessions across turns to preserve codebase exploration context (Claude Code `--resume`, Codex `resume --last`)

## Alternatives Considered

Explored from first principles:
- **Git-native** (branches per agent): Elegant but pollutes repo history
- **Conversation-as-artifact**: Good transparency, hard to extract actionable plan
- **Whiteboard model** (single shared doc): Simple but loses parallelism
- **Conventions-only** (no CLI): Maximum portability but fragile coordination
- **Diff-based communication**: Clever but overcomplicates

**Conclusion**: Turn-based with simple `turns/` + optional `agents/` is the right balance of simplicity and transparency.
