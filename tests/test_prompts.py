"""Tests for prompt generation."""

from thunk.prompts import (
    PLAN_FORMAT,
    get_draft_prompt,
    get_peer_review_prompt,
    get_refine_prompt,
    get_synthesis_prompt,
)


def test_get_draft_prompt_turn_1():
    """Test draft prompt for initial turn."""
    prompt = get_draft_prompt(
        task="Add caching layer",
        turn=1,
        output_file="/path/to/plan.md",
    )

    assert "Add caching layer" in prompt
    assert "Turn 1" in prompt
    assert "/path/to/plan.md" in prompt
    assert "Explore the codebase" in prompt
    assert PLAN_FORMAT in prompt


def test_get_draft_prompt_turn_2():
    """Test draft prompt for subsequent turns."""
    prompt = get_draft_prompt(
        task="Add caching layer",
        turn=2,
        output_file="/path/to/plan.md",
        plan_file="/path/to/working.md",
        user_feedback="Please add Redis support",
    )

    assert "Add caching layer" in prompt
    assert "Turn 2" in prompt
    assert "/path/to/plan.md" in prompt
    assert "/path/to/working.md" in prompt
    assert "Please add Redis support" in prompt


def test_get_draft_prompt_no_feedback():
    """Test draft prompt without user feedback uses default."""
    prompt = get_draft_prompt(
        task="Add caching layer",
        turn=2,
        output_file="/path/to/plan.md",
        plan_file="/path/to/working.md",
    )

    assert "No specific feedback" in prompt


def test_get_peer_review_prompt():
    """Test peer review prompt generation."""
    prompt = get_peer_review_prompt(
        task="Add caching layer",
        own_draft="My plan content",
        peer_id="sunny-glade",
        peer_draft="Peer plan content",
    )

    assert "Add caching layer" in prompt
    assert "My plan content" in prompt
    assert "sunny-glade" in prompt
    assert "Peer plan content" in prompt
    assert "Peer Review" in prompt
    assert PLAN_FORMAT in prompt


def test_get_synthesis_prompt():
    """Test synthesis prompt generation."""
    prompt = get_synthesis_prompt(
        task="Add caching layer",
        agent_plans={
            "opus": "Opus plan content",
            "codex": "Codex plan content",
        },
    )

    assert "Add caching layer" in prompt
    assert "opus" in prompt
    assert "Opus plan content" in prompt
    assert "codex" in prompt
    assert "Codex plan content" in prompt
    assert "Synthesis" in prompt
    assert PLAN_FORMAT in prompt


def test_get_synthesis_prompt_single_agent():
    """Test synthesis prompt with single agent."""
    prompt = get_synthesis_prompt(
        task="Add caching layer",
        agent_plans={"opus": "Solo plan content"},
    )

    assert "opus" in prompt
    assert "Solo plan content" in prompt


def test_get_refine_prompt():
    """Test refinement prompt generation."""
    prompt = get_refine_prompt(
        task="Add caching layer",
        turn=3,
        plan_file="/path/to/current.md",
        output_file="/path/to/output.md",
        diff="- old line\n+ new line",
    )

    assert "Add caching layer" in prompt
    assert "Turn 3" in prompt
    assert "/path/to/current.md" in prompt
    assert "/path/to/output.md" in prompt
    assert "- old line" in prompt
    assert "+ new line" in prompt
    assert "Refinement" in prompt
    assert PLAN_FORMAT in prompt


def test_plan_format_has_required_sections():
    """Test that PLAN_FORMAT includes required sections."""
    assert "## Questions" in PLAN_FORMAT
    assert "## Summary" in PLAN_FORMAT
    assert "## Tasks" in PLAN_FORMAT
    assert "## Risks" in PLAN_FORMAT
