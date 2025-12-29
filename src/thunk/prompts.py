"""Prompt templates for agents."""

PLAN_FORMAT = """
## Questions (if any)

If you have questions that would affect the plan, add them here:

### Q1: [Question]
**Context:** [Why this matters]
**Answer:**

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

EXPLORE_PROMPT = """# Exploration Task

You are exploring a codebase to prepare for planning a feature implementation.

## Feature Request
{feature}

## Project Context
{context}

## Instructions
1. Explore the codebase to understand existing patterns relevant to this feature
2. Identify any questions that would affect how you'd implement this
3. Write a skeleton plan with your initial thoughts and questions

Write your output as a markdown plan with the following structure:
{plan_format}

Focus on:
- Understanding existing patterns
- Identifying key decisions that need user input
- Noting risks and unknowns
"""

DRAFT_PROMPT = """# Planning Task (Turn {turn})

Create a plan for implementing this feature.

## Feature Request
{feature}

## Project Context
{context}

## Previous Q&A
{qa_history}

## User's Previous Edits
{user_edits}

## Instructions
Write a detailed implementation plan addressing any user feedback from previous turns.

{plan_format}
"""

PEER_REVIEW_PROMPT = """# Peer Review Task

You wrote an initial draft. Now review your peer's draft and improve your plan.

## Feature Request
{feature}

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

## Feature Request
{feature}

## Agent Plans

{agent_plans}

## Instructions
1. Identify common themes across plans
2. Note where plans diverge—pick the best approach or flag for user
3. Combine the best ideas from each plan
4. Merge into a coherent unified plan

If agents disagree, add a ## Conflicts section explaining the options.

{plan_format}
"""

REFINE_PROMPT = """# Plan Refinement Task (Turn {turn})

The user edited the previous plan. Interpret their changes and improve.

## Feature Request
{feature}

## Original Plan (Turn {prev_turn})
{original_plan}

## User-Edited Plan
{user_edited_plan}

## Changes (Diff)
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

{plan_format}
"""


def get_explore_prompt(feature: str, context: str) -> str:
    """Get the exploration prompt."""
    return EXPLORE_PROMPT.format(
        feature=feature,
        context=context,
        plan_format=PLAN_FORMAT,
    )


def get_draft_prompt(
    feature: str,
    context: str,
    turn: int,
    qa_history: str = "",
    user_edits: str = "",
) -> str:
    """Get the draft prompt."""
    return DRAFT_PROMPT.format(
        feature=feature,
        context=context,
        turn=turn,
        qa_history=qa_history or "None yet.",
        user_edits=user_edits or "First turn - no previous edits.",
        plan_format=PLAN_FORMAT,
    )


def get_peer_review_prompt(
    feature: str,
    own_draft: str,
    peer_id: str,
    peer_draft: str,
) -> str:
    """Get the peer review prompt."""
    return PEER_REVIEW_PROMPT.format(
        feature=feature,
        own_draft=own_draft,
        peer_id=peer_id,
        peer_draft=peer_draft,
        plan_format=PLAN_FORMAT,
    )


def get_synthesis_prompt(feature: str, agent_plans: dict[str, str]) -> str:
    """Get the synthesis prompt."""
    plans_text = ""
    for agent_id, plan in agent_plans.items():
        plans_text += f"### {agent_id}\n\n{plan}\n\n"

    return SYNTHESIS_PROMPT.format(
        feature=feature,
        agent_plans=plans_text,
        plan_format=PLAN_FORMAT,
    )


def get_refine_prompt(
    feature: str,
    turn: int,
    original_plan: str,
    user_edited_plan: str,
    diff: str,
) -> str:
    """Get the refinement prompt."""
    return REFINE_PROMPT.format(
        feature=feature,
        turn=turn,
        prev_turn=turn - 1,
        original_plan=original_plan,
        user_edited_plan=user_edited_plan,
        diff=diff,
        plan_format=PLAN_FORMAT,
    )
