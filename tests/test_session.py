"""Tests for session management."""

import tempfile
from pathlib import Path

import pytest

from thunk.models import Phase
from thunk.session import SessionManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def manager(temp_dir):
    """Create a session manager with temp directory."""
    return SessionManager(temp_dir / ".thunk")


def test_create_session(manager):
    """Test creating a new session."""
    state = manager.create_session("Add caching layer")

    assert state.session_id is not None
    assert len(state.session_id) == 8
    assert state.task == "Add caching layer"
    assert state.turn == 1
    assert state.phase == Phase.INITIALIZING


def test_load_session(manager):
    """Test loading an existing session."""
    created = manager.create_session("Test task")
    loaded = manager.load_session(created.session_id)

    assert loaded is not None
    assert loaded.session_id == created.session_id
    assert loaded.task == created.task


def test_load_nonexistent_session(manager):
    """Test loading a session that doesn't exist."""
    loaded = manager.load_session("nonexistent")
    assert loaded is None


def test_list_sessions(manager):
    """Test listing sessions."""
    manager.create_session("Task 1")
    manager.create_session("Task 2")

    sessions = manager.list_sessions()

    assert len(sessions) == 2
    tasks = {s.task for s in sessions}
    assert "Task 1" in tasks
    assert "Task 2" in tasks


def test_save_state(manager):
    """Test saving session state."""
    state = manager.create_session("Test task")
    state.turn = 2
    state.phase = Phase.USER_REVIEW
    manager.save_state(state)

    loaded = manager.load_session(state.session_id)

    assert loaded.turn == 2
    assert loaded.phase == Phase.USER_REVIEW


def test_clean_session(manager):
    """Test cleaning up a session."""
    state = manager.create_session("Test task")
    session_id = state.session_id

    assert manager.clean_session(session_id) is True
    assert manager.load_session(session_id) is None


def test_clean_nonexistent_session(manager):
    """Test cleaning a session that doesn't exist."""
    assert manager.clean_session("nonexistent") is False


def test_get_paths(manager):
    """Test getting session paths."""
    state = manager.create_session("Test task")
    paths = manager.get_paths(state.session_id)

    assert paths.root.exists()
    assert paths.meta.exists()
    assert paths.state.exists()
    assert paths.turns.exists()
    assert paths.agents.exists()


def test_turn_file_path(manager):
    """Test turn file path generation."""
    state = manager.create_session("Test task")
    paths = manager.get_paths(state.session_id)

    assert paths.turn_file(1).name == "001.md"
    assert paths.turn_file(10).name == "010.md"
    assert paths.turn_file(100).name == "100.md"


def test_has_questions_empty(manager):
    """Test has_questions with no turn file."""
    state = manager.create_session("Test task")
    assert manager.has_questions(state.session_id) is False


def test_has_questions_with_unanswered(manager):
    """Test has_questions with unanswered questions."""
    state = manager.create_session("Test task")
    paths = manager.get_paths(state.session_id)

    # Create turn file with unanswered question
    turn_file = paths.turn_file(1)
    turn_file.parent.mkdir(parents=True, exist_ok=True)
    turn_file.write_text("""
## Questions

### Q1: What database?
**Context:** Need to choose
**Answer:**

## Summary
TBD
""")

    assert manager.has_questions(state.session_id) is True


def test_has_questions_all_answered(manager):
    """Test has_questions when all questions are answered."""
    state = manager.create_session("Test task")
    paths = manager.get_paths(state.session_id)

    turn_file = paths.turn_file(1)
    turn_file.parent.mkdir(parents=True, exist_ok=True)
    turn_file.write_text("""
## Questions

### Q1: What database?
**Context:** Need to choose
**Answer:** PostgreSQL

## Summary
Use PostgreSQL
""")

    assert manager.has_questions(state.session_id) is False
