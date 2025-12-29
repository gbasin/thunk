"""Base adapter interface for agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import AgentConfig, AgentStatus


@dataclass
class AgentHandle:
    """Handle to a running agent."""

    agent_id: str
    process: Any  # subprocess.Popen or similar
    log_file: Path

    def is_running(self) -> bool:
        """Check if agent is still running."""
        if hasattr(self.process, "poll"):
            return self.process.poll() is None
        return False

    def get_status(self) -> AgentStatus:
        """Get agent status."""
        if self.is_running():
            return AgentStatus.WORKING
        if hasattr(self.process, "returncode"):
            return AgentStatus.DONE if self.process.returncode == 0 else AgentStatus.ERROR
        return AgentStatus.DONE


class AgentAdapter(ABC):
    """Base class for agent adapters with session continuation support."""

    def __init__(self, config: AgentConfig):
        self.config = config

    @abstractmethod
    def spawn(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
        session_file: Path | None = None,
    ) -> AgentHandle:
        """
        Spawn an agent to work on a task.

        Args:
            worktree: Working directory for the agent
            prompt: The prompt/task for the agent
            output_file: Where the agent should write its output
            log_file: Where to capture agent logs
            session_file: Path to store/read CLI session ID for continuation

        Returns:
            Handle to the running agent
        """
        pass

    def run_sync(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
        timeout: int | None = None,
        session_file: Path | None = None,
        append_log: bool = False,
    ) -> tuple[bool, str]:
        """
        Run agent synchronously.

        Args:
            worktree: Working directory for the agent
            prompt: The prompt/task for the agent
            output_file: Where the agent should write its output
            log_file: Where to capture agent logs
            timeout: Timeout in seconds
            session_file: Path to store/read CLI session ID for continuation
            append_log: If True, append to log file instead of overwriting

        Returns:
            Tuple of (success, output)
        """
        # Default implementation uses spawn and waits
        handle = self.spawn(worktree, prompt, output_file, log_file, session_file)
        if hasattr(handle.process, "wait"):
            handle.process.wait(timeout=timeout)
        if output_file.exists():
            return True, output_file.read_text()
        return False, "No output produced"

    @abstractmethod
    def get_name(self) -> str:
        """Get adapter name for display."""
        pass
