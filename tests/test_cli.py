"""Tests for CLI commands."""

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from thunk.cli import main


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_init_command(runner, temp_dir):
    """Test init command."""
    result = runner.invoke(
        main, ["--thunk-dir", str(temp_dir / ".thunk"), "init", "Add caching layer"]
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "session_id" in data
    assert data["turn"] == 1


def test_list_command_empty(runner, temp_dir):
    """Test list command with no sessions."""
    result = runner.invoke(main, ["--thunk-dir", str(temp_dir / ".thunk"), "list"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["sessions"] == []


def test_list_command_with_sessions(runner, temp_dir):
    """Test list command with sessions."""
    thunk_dir = str(temp_dir / ".thunk")

    # Create two sessions
    runner.invoke(main, ["--thunk-dir", thunk_dir, "init", "Feature 1"])
    runner.invoke(main, ["--thunk-dir", thunk_dir, "init", "Feature 2"])

    result = runner.invoke(main, ["--thunk-dir", thunk_dir, "list"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["sessions"]) == 2


def test_status_command(runner, temp_dir):
    """Test status command."""
    thunk_dir = str(temp_dir / ".thunk")

    # Create a session
    init_result = runner.invoke(main, ["--thunk-dir", thunk_dir, "init", "Test feature"])
    session_id = json.loads(init_result.output)["session_id"]

    # Check status
    result = runner.invoke(main, ["--thunk-dir", thunk_dir, "status", "--session", session_id])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["session_id"] == session_id
    assert data["turn"] == 1


def test_status_nonexistent_session(runner, temp_dir):
    """Test status command for nonexistent session."""
    result = runner.invoke(
        main, ["--thunk-dir", str(temp_dir / ".thunk"), "status", "--session", "nonexistent"]
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert "error" in data


def test_clean_command(runner, temp_dir):
    """Test clean command."""
    thunk_dir = str(temp_dir / ".thunk")

    # Create a session
    init_result = runner.invoke(main, ["--thunk-dir", thunk_dir, "init", "Test feature"])
    session_id = json.loads(init_result.output)["session_id"]

    # Clean it
    result = runner.invoke(main, ["--thunk-dir", thunk_dir, "clean", "--session", session_id])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["cleaned"] is True

    # Verify it's gone
    status_result = runner.invoke(
        main, ["--thunk-dir", thunk_dir, "status", "--session", session_id]
    )
    assert status_result.exit_code == 1


def test_pretty_output(runner, temp_dir):
    """Test pretty JSON output."""
    result = runner.invoke(
        main, ["--thunk-dir", str(temp_dir / ".thunk"), "--pretty", "init", "Test feature"]
    )

    assert result.exit_code == 0
    # Pretty output should have newlines and indentation
    assert "\n" in result.output
    assert "  " in result.output


def test_approve_requires_user_review_phase(runner, temp_dir):
    """Test that approve fails if not in user_review phase."""
    thunk_dir = str(temp_dir / ".thunk")

    # Create a session (starts in drafting phase after init)
    init_result = runner.invoke(main, ["--thunk-dir", thunk_dir, "init", "Test feature"])
    session_id = json.loads(init_result.output)["session_id"]

    # Try to approve immediately
    result = runner.invoke(main, ["--thunk-dir", thunk_dir, "approve", "--session", session_id])

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert "error" in data


def test_continue_requires_user_review_phase(runner, temp_dir):
    """Test that continue fails if not in user_review phase."""
    thunk_dir = str(temp_dir / ".thunk")

    # Create a session
    init_result = runner.invoke(main, ["--thunk-dir", thunk_dir, "init", "Test feature"])
    session_id = json.loads(init_result.output)["session_id"]

    # Try to continue immediately
    result = runner.invoke(main, ["--thunk-dir", thunk_dir, "continue", "--session", session_id])

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert "error" in data
