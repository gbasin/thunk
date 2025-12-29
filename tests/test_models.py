"""Tests for data models."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from thunk.models import (
    AgentConfig,
    AgentStatus,
    Phase,
    SessionPaths,
    SessionState,
    ThunkConfig,
)


class TestPhase:
    """Tests for Phase enum."""

    def test_phase_values(self):
        """Test all phase values exist."""
        assert Phase.INITIALIZING.value == "initializing"
        assert Phase.DRAFTING.value == "drafting"
        assert Phase.PEER_REVIEW.value == "peer_review"
        assert Phase.SYNTHESIZING.value == "synthesizing"
        assert Phase.USER_REVIEW.value == "user_review"
        assert Phase.APPROVED.value == "approved"
        assert Phase.ERROR.value == "error"

    def test_phase_is_string_enum(self):
        """Test Phase is a string enum."""
        assert isinstance(Phase.DRAFTING.value, str)
        assert str(Phase.DRAFTING) == "Phase.DRAFTING"


class TestAgentStatus:
    """Tests for AgentStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert AgentStatus.PENDING.value == "pending"
        assert AgentStatus.WORKING.value == "working"
        assert AgentStatus.DONE.value == "done"
        assert AgentStatus.ERROR.value == "error"


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_agent_config_defaults(self):
        """Test AgentConfig default values."""
        config = AgentConfig(id="test", type="claude", model="opus")
        assert config.enabled is True

    def test_agent_config_disabled(self):
        """Test AgentConfig with disabled."""
        config = AgentConfig(id="test", type="claude", model="opus", enabled=False)
        assert config.enabled is False


class TestSessionState:
    """Tests for SessionState."""

    def test_session_state_to_dict(self):
        """Test SessionState.to_dict serialization."""
        now = datetime.now()
        state = SessionState(
            session_id="test-session",
            task="Test task",
            turn=2,
            phase=Phase.USER_REVIEW,
            created_at=now,
            updated_at=now,
            agents={"opus": AgentStatus.DONE},
            agent_plan_ids={"opus": "sunny-glade"},
        )

        d = state.to_dict()

        assert d["session_id"] == "test-session"
        assert d["task"] == "Test task"
        assert d["turn"] == 2
        assert d["phase"] == "user_review"
        assert d["agents"] == {"opus": "done"}
        assert d["agent_plan_ids"] == {"opus": "sunny-glade"}
        assert "created_at" in d
        assert "updated_at" in d

    def test_session_state_defaults(self):
        """Test SessionState default values."""
        now = datetime.now()
        state = SessionState(
            session_id="test",
            task="Test",
            turn=1,
            phase=Phase.INITIALIZING,
            created_at=now,
            updated_at=now,
        )

        assert state.agents == {}
        assert state.agent_plan_ids == {}


class TestSessionPaths:
    """Tests for SessionPaths."""

    @pytest.fixture
    def temp_root(self):
        """Create a temporary root directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_from_root(self, temp_root):
        """Test SessionPaths.from_root factory."""
        paths = SessionPaths.from_root(temp_root)

        assert paths.root == temp_root
        assert paths.meta == temp_root / "meta.yaml"
        assert paths.state == temp_root / "state.yaml"
        assert paths.turns == temp_root / "turns"
        assert paths.agents == temp_root / "agents"

    def test_turn_file(self, temp_root):
        """Test turn file path generation."""
        paths = SessionPaths.from_root(temp_root)

        assert paths.turn_file(1) == temp_root / "turns" / "001.md"
        assert paths.turn_file(10) == temp_root / "turns" / "010.md"
        assert paths.turn_file(100) == temp_root / "turns" / "100.md"

    def test_turn_snapshot_dir(self, temp_root):
        """Test turn snapshot directory path."""
        paths = SessionPaths.from_root(temp_root)

        assert paths.turn_snapshot_dir(1) == temp_root / "turns" / "001"
        assert paths.turn_snapshot_dir(5) == temp_root / "turns" / "005"

    def test_agent_plan_file(self, temp_root):
        """Test agent plan file path."""
        paths = SessionPaths.from_root(temp_root)

        assert paths.agent_plan_file("sunny-glade") == temp_root / "sunny-glade.md"
        assert paths.agent_plan_file("bold-peak") == temp_root / "bold-peak.md"

    def test_agent_log_file(self, temp_root):
        """Test agent log file path."""
        paths = SessionPaths.from_root(temp_root)

        assert paths.agent_log_file("sunny-glade") == temp_root / "agents" / "sunny-glade.log"

    def test_agent_session_file(self, temp_root):
        """Test agent CLI session file path."""
        paths = SessionPaths.from_root(temp_root)

        expected = temp_root / "agents" / "sunny-glade" / "cli_session_id.txt"
        assert paths.agent_session_file("sunny-glade") == expected

    def test_agent_dir(self, temp_root):
        """Test agent directory path."""
        paths = SessionPaths.from_root(temp_root)

        assert paths.agent_dir("sunny-glade") == temp_root / "agents" / "sunny-glade"


class TestThunkConfig:
    """Tests for ThunkConfig."""

    def test_default_config(self):
        """Test ThunkConfig.default factory."""
        config = ThunkConfig.default()

        assert len(config.agents) == 2
        assert config.agents[0].id == "opus"
        assert config.agents[0].type == "claude"
        assert config.agents[1].id == "codex"
        assert config.agents[1].type == "codex"
        assert config.synthesizer.id == "synthesizer"
        assert config.timeout is None

    def test_config_with_timeout(self):
        """Test ThunkConfig with timeout."""
        config = ThunkConfig(
            agents=[AgentConfig(id="test", type="claude", model="opus")],
            synthesizer=AgentConfig(id="synth", type="claude", model="opus"),
            timeout=300,
        )

        assert config.timeout == 300
