"""Prompt templates for agents."""

PLAN_FORMAT = """
## Questions (if any)

If you have questions that would affect the plan, add them here:

### Q1: [Question]
**Context:** [Why this matters]
**Answer:**

---

## Notes for Agents

<!-- Add feedback for agents here. Delete this comment when adding notes. -->

---

## Summary

[2-3 sentence overview of the approach]

## Tasks

- [ ] **Task 1**: [Description]
  - **Files:** `path/to/file.py` (create|modify)
  - **Rationale:** [Why this task]
  - **Dependencies:** none | Task N

## Risks

- **[Risk name]** (severity: high|medium|low)
  - **Mitigation:** [How to address]

## Alternatives Considered

- **[Alternative]**: Rejected because [reason]
"""

DRAFT_PROMPT_INITIAL = """# Planning Task (Turn 1)

Create a plan for this task.

## Task
{task}

## Instructions
1. Explore the codebase - look for AGENTS.md, README.md, or documentation
2. Understand the project's conventions, architecture, and patterns
3. Identify key decisions and unknowns
4. Write a detailed plan

Write your plan to: `{output_file}`

{plan_format}
"""

DRAFT_PROMPT = """# Planning Task (Turn {turn})

Refine the plan based on feedback.

## Task
{task}

## Your Working Plan
Read your current plan from: `{plan_file}`

This file contains the synthesized plan from the previous turn.

## User Feedback
{user_feedback}

## Instructions
1. Read your current plan file
2. Review the user feedback above
3. Update the plan incorporating the feedback
4. Write your updated plan to: `{output_file}`

{plan_format}
"""

PEER_REVIEW_PROMPT = """# Peer Review Task

You wrote an initial draft. Now review your peer's draft and improve your plan.

## Task
{task}

## Your Draft
{own_draft}

## Peer's Draft ({peer_id})
{peer_draft}

## Instructions
1. Review your peer's approach
2. Identify ideas from their plan that improve yours
3. Note any conflicts and resolve them
4. Write an improved plan incorporating the best of both

Your final plan should be BETTER than your draft.

{plan_format}
"""

SYNTHESIS_PROMPT = """# Synthesis Task

Combine multiple agent plans into a unified plan.

## Task
{task}
{user_changes_section}
## Agent Plans

{agent_plans}

## Instructions
1. Identify common themes across plans
2. Note where plans diverge—pick the best approach or flag for user
3. Combine the best ideas from each plan
4. Merge into a coherent unified plan

If agents disagree, add a ## Conflicts section explaining the options.

Write your unified plan to: `{output_file}`

{plan_format}
"""

SYNTHESIS_USER_CHANGES = """
## User's Changes From Previous Turn (IMPORTANT)

The user made these changes to the plan:

{user_diff}

**Interpret user intent:**
- **New requirements** (firm statements like "Must support X"): MUST appear in final plan
- **Questions** ("What about..?", "Should we..?"): Verify agents addressed them;
  include the ANSWER in the plan, not the question itself
- **Uncertain language** ("maybe", "consider", "could"): Treat as suggestions to
  evaluate against agent plans, not hard requirements
- **Comments/TODOs** (<!-- -->, TODO:, NOTE:): Notes for agents, not final plan content
- **Deletions**: Do NOT re-add deleted content under any circumstances

**Key principle:** Respect the user's INTENT, not just their exact words.
If the user asked a question, the agents should have answered it—synthesize their answer.
If the user deleted something, it stays deleted even if agents still mention it.
"""

REFINE_PROMPT = """# Plan Refinement Task (Turn {turn})

The user edited the plan. Interpret their changes and improve.

## Task
{task}

## Current Plan
Read the current synthesized plan from: `{plan_file}`

This is your starting point - it represents the merged consensus from all agents.

## User's Changes (Diff)
```diff
{diff}
```

## Instructions
Interpret the user's edits:
- **Deletions**: User doesn't want this. Remove or rethink.
- **Additions**: User added text. This is a requirement or question.
- **Questions in text**: User wants these answered. Address directly.
- **Comments**: User feedback. Incorporate and remove marker.
- **Unchanged sections**: User is satisfied. Keep unless you can improve.

User's direct edits are REQUIREMENTS - incorporate them exactly.
User's questions need your THINKING - address each thoroughly.

Write your updated plan to: `{output_file}`

{plan_format}
"""


def get_draft_prompt(
    task: str,
    turn: int,
    output_file: str,
    plan_file: str = "",
    user_feedback: str = "",
) -> str:
    """Get the draft prompt.

    Args:
        task: Task description
        turn: Current turn number
        output_file: Path where agent should write their plan
        plan_file: Path to agent's working plan file (for turn > 1)
        user_feedback: User's feedback/diff from previous turn
    """
    if turn == 1:
        return DRAFT_PROMPT_INITIAL.format(
            task=task,
            output_file=output_file,
            plan_format=PLAN_FORMAT,
        )
    else:
        return DRAFT_PROMPT.format(
            task=task,
            turn=turn,
            plan_file=plan_file,
            user_feedback=user_feedback or "No specific feedback - improve as you see fit.",
            output_file=output_file,
            plan_format=PLAN_FORMAT,
        )


def get_peer_review_prompt(
    task: str,
    own_draft: str,
    peer_id: str,
    peer_draft: str,
) -> str:
    """Get the peer review prompt."""
    return PEER_REVIEW_PROMPT.format(
        task=task,
        own_draft=own_draft,
        peer_id=peer_id,
        peer_draft=peer_draft,
        plan_format=PLAN_FORMAT,
    )


def get_synthesis_prompt(
    task: str,
    agent_plans: dict[str, str],
    output_file: str,
    user_diff: str = "",
) -> str:
    """Get the synthesis prompt.

    Args:
        task: Task description
        agent_plans: Dict mapping agent_id to their plan content
        output_file: Path where synthesizer should write the unified plan
        user_diff: User's changes from previous turn (for turn > 1)
    """
    plans_text = ""
    for agent_id, plan in agent_plans.items():
        plans_text += f"### {agent_id}\n\n{plan}\n\n"

    # Include user changes section if there's a diff
    if user_diff:
        user_changes_section = SYNTHESIS_USER_CHANGES.format(user_diff=user_diff)
    else:
        user_changes_section = ""

    return SYNTHESIS_PROMPT.format(
        task=task,
        user_changes_section=user_changes_section,
        agent_plans=plans_text,
        output_file=output_file,
        plan_format=PLAN_FORMAT,
    )


def get_refine_prompt(
    task: str,
    turn: int,
    plan_file: str,
    output_file: str,
    diff: str,
) -> str:
    """Get the refinement prompt.

    Args:
        task: Task description
        turn: Current turn number
        plan_file: Path to current synthesized plan (agents read this)
        output_file: Path where agent should write updated plan
        diff: Unified diff of user's changes
    """
    return REFINE_PROMPT.format(
        task=task,
        turn=turn,
        plan_file=plan_file,
        output_file=output_file,
        diff=diff,
        plan_format=PLAN_FORMAT,
    )
