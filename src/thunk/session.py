"""Session management for thunk."""

import uuid
from datetime import datetime
from pathlib import Path

import yaml

from .models import AgentStatus, Phase, SessionPaths, SessionState


class SessionManager:
    """Manages planning sessions."""

    def __init__(self, thunk_dir: Path | None = None):
        self.thunk_dir = thunk_dir or Path(".thunk")
        self.sessions_dir = self.thunk_dir / "sessions"

    def create_session(self, feature: str) -> SessionState:
        """Create a new planning session."""
        session_id = uuid.uuid4().hex[:8]
        now = datetime.now()

        # Create session directory structure
        paths = self._get_paths(session_id)
        paths.root.mkdir(parents=True, exist_ok=True)
        paths.turns.mkdir(exist_ok=True)
        paths.agents.mkdir(exist_ok=True)

        # Create initial state
        state = SessionState(
            session_id=session_id,
            feature=feature,
            turn=1,
            phase=Phase.INITIALIZING,
            created_at=now,
            updated_at=now,
        )

        # Write meta.yaml
        meta = {
            "session_id": session_id,
            "feature": feature,
            "created_at": now.isoformat(),
        }
        with open(paths.meta, "w") as f:
            yaml.dump(meta, f)

        # Write initial state
        self._save_state(state)

        return state

    def load_session(self, session_id: str) -> SessionState | None:
        """Load an existing session."""
        paths = self._get_paths(session_id)
        if not paths.root.exists():
            return None

        # Load meta
        with open(paths.meta) as f:
            meta = yaml.safe_load(f)

        # Load state
        with open(paths.state) as f:
            state_data = yaml.safe_load(f)

        return SessionState(
            session_id=session_id,
            feature=meta["feature"],
            turn=state_data["turn"],
            phase=Phase(state_data["phase"]),
            created_at=datetime.fromisoformat(meta["created_at"]),
            updated_at=datetime.fromisoformat(state_data["updated_at"]),
            agents={k: AgentStatus(v) for k, v in state_data.get("agents", {}).items()},
        )

    def save_state(self, state: SessionState) -> None:
        """Save session state."""
        state.updated_at = datetime.now()
        self._save_state(state)

    def _save_state(self, state: SessionState) -> None:
        """Internal save without updating timestamp."""
        paths = self._get_paths(state.session_id)
        state_data = {
            "turn": state.turn,
            "phase": state.phase.value,
            "updated_at": state.updated_at.isoformat(),
            "agents": {k: v.value for k, v in state.agents.items()},
        }
        with open(paths.state, "w") as f:
            yaml.dump(state_data, f)

    def list_sessions(self) -> list[SessionState]:
        """List all sessions."""
        sessions = []
        if not self.sessions_dir.exists():
            return sessions

        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                state = self.load_session(session_dir.name)
                if state:
                    sessions.append(state)

        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    def get_paths(self, session_id: str) -> SessionPaths:
        """Get paths for a session."""
        return self._get_paths(session_id)

    def _get_paths(self, session_id: str) -> SessionPaths:
        """Internal path getter."""
        root = self.sessions_dir / session_id
        return SessionPaths.from_root(root)

    def clean_session(self, session_id: str) -> bool:
        """Remove a session and its data."""
        import shutil

        paths = self._get_paths(session_id)
        if not paths.root.exists():
            return False

        shutil.rmtree(paths.root)
        return True

    def get_current_turn_file(self, session_id: str) -> Path | None:
        """Get the current turn's file path."""
        state = self.load_session(session_id)
        if not state:
            return None

        paths = self._get_paths(session_id)
        return paths.turn_file(state.turn)

    def has_questions(self, session_id: str) -> bool:
        """Check if current turn has unanswered questions."""
        turn_file = self.get_current_turn_file(session_id)
        if not turn_file or not turn_file.exists():
            return False

        content = turn_file.read_text()
        # Look for Questions section with unanswered questions
        if "## Questions" not in content:
            return False

        # Check for empty Answer: fields
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("**Answer:**"):
                # Check if answer is empty (just whitespace or nothing after)
                answer_content = line.replace("**Answer:**", "").strip()
                if not answer_content:
                    # Also check next line in case answer is on new line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if not next_line or next_line.startswith("###") or next_line.startswith("---"):
                            return True
                    else:
                        return True

        return False
