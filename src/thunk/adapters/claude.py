"""Claude Code adapter."""

import subprocess
from pathlib import Path

from ..models import AgentConfig
from .base import AgentAdapter, AgentHandle


class ClaudeCodeAdapter(AgentAdapter):
    """Adapter for Claude Code CLI."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)

    def spawn(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
    ) -> AgentHandle:
        """Spawn Claude Code as a subprocess."""
        # Build command
        cmd = [
            "claude",
            "--print",  # Non-interactive mode
            "--output-format", "text",
        ]

        # Add model if specified
        if self.config.model:
            cmd.extend(["--model", self.config.model])

        # Add prompt
        cmd.extend(["-p", prompt])

        # Open log file for output capture
        log_fh = open(log_file, "w")

        # Spawn process
        process = subprocess.Popen(
            cmd,
            cwd=worktree,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            text=True,
        )

        return AgentHandle(
            agent_id=self.config.id,
            process=process,
            log_file=log_file,
        )

    def get_name(self) -> str:
        return f"Claude Code ({self.config.model})"


class ClaudeCodeSyncAdapter(AgentAdapter):
    """Synchronous Claude Code adapter that waits for completion."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)

    def run_sync(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
        timeout: int | None = None,
    ) -> tuple[bool, str]:
        """
        Run Claude Code synchronously and wait for completion.

        Returns:
            Tuple of (success, output)
        """
        cmd = [
            "claude",
            "--print",
            "--output-format", "text",
        ]

        if self.config.model:
            cmd.extend(["--model", self.config.model])

        cmd.extend(["-p", prompt])

        try:
            result = subprocess.run(
                cmd,
                cwd=worktree,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Write output to files
            with open(log_file, "w") as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write("\n--- STDERR ---\n")
                    f.write(result.stderr)

            # Try to extract plan content and write to output file
            # The agent should write the plan in its output
            if result.returncode == 0:
                output_file.write_text(result.stdout)
                return True, result.stdout
            else:
                return False, result.stderr or "Unknown error"

        except subprocess.TimeoutExpired:
            return False, "Timeout expired"
        except Exception as e:
            return False, str(e)

    def spawn(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
    ) -> AgentHandle:
        """For interface compatibility - use run_sync for synchronous operation."""
        # For async operation, use the regular spawn
        cmd = [
            "claude",
            "--print",
            "--output-format", "text",
        ]

        if self.config.model:
            cmd.extend(["--model", self.config.model])

        cmd.extend(["-p", prompt])

        log_fh = open(log_file, "w")

        process = subprocess.Popen(
            cmd,
            cwd=worktree,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            text=True,
        )

        return AgentHandle(
            agent_id=self.config.id,
            process=process,
            log_file=log_file,
        )

    def get_name(self) -> str:
        return f"Claude Code Sync ({self.config.model})"
