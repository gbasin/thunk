"""Data models for thunk."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class Phase(str, Enum):
    """Session phase."""

    INITIALIZING = "initializing"
    DRAFTING = "drafting"
    PEER_REVIEW = "peer_review"
    SYNTHESIZING = "synthesizing"
    USER_REVIEW = "user_review"
    APPROVED = "approved"
    ERROR = "error"


class AgentStatus(str, Enum):
    """Agent status within a turn."""

    PENDING = "pending"
    WORKING = "working"
    DONE = "done"
    ERROR = "error"


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    id: str
    type: str  # "claude" or "openai"
    model: str
    enabled: bool = True


@dataclass
class SessionState:
    """Current state of a planning session."""

    session_id: str
    task: str
    turn: int
    phase: Phase
    created_at: datetime
    updated_at: datetime
    agents: dict[str, AgentStatus] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task": self.task,
            "turn": self.turn,
            "phase": self.phase.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "agents": {k: v.value for k, v in self.agents.items()},
        }


@dataclass
class SessionPaths:
    """Paths for a session."""

    root: Path  # .thunk/sessions/<session_id>/
    meta: Path  # meta.yaml
    state: Path  # state.yaml
    turns: Path  # turns/
    agents: Path  # agents/

    @classmethod
    def from_root(cls, root: Path) -> "SessionPaths":
        return cls(
            root=root,
            meta=root / "meta.yaml",
            state=root / "state.yaml",
            turns=root / "turns",
            agents=root / "agents",
        )

    def turn_file(self, turn: int) -> Path:
        """Get path to a turn's synthesis file."""
        return self.turns / f"{turn:03d}.md"

    def agent_turn_dir(self, turn: int) -> Path:
        """Get path to agent work for a turn."""
        return self.agents / f"turn-{turn:03d}"

    def agent_session_file(self, agent_id: str) -> Path:
        """Get path to an agent's CLI session ID file for continuation."""
        return self.agents / agent_id / "cli_session_id.txt"

    def agent_dir(self, agent_id: str) -> Path:
        """Get path to an agent's directory."""
        return self.agents / agent_id

    def agent_plan_file(self, agent_id: str) -> Path:
        """Get path to an agent's working plan file.

        This file is the agent's "view" of the plan. Thunk overwrites it
        with the synthesis after each turn, so agents stay in sync.
        """
        return self.root / f"{agent_id}.md"


@dataclass
class ThunkConfig:
    """Global thunk configuration."""

    agents: list[AgentConfig]
    synthesizer: AgentConfig
    timeout: int | None = None

    @classmethod
    def default(cls) -> "ThunkConfig":
        return cls(
            agents=[
                AgentConfig(id="opus", type="claude", model="opus"),
                AgentConfig(id="codex", type="codex", model="codex-mini-latest"),
            ],
            synthesizer=AgentConfig(id="synthesizer", type="claude", model="opus"),
        )
