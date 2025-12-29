"""Claude Code adapter with session continuation support."""

import json
import subprocess
from pathlib import Path

from ..models import AgentConfig
from .base import AgentAdapter, AgentHandle


def _read_session_id(session_file: Path | None) -> str | None:
    """Safely read session ID from file."""
    if not session_file or not session_file.exists():
        return None
    try:
        return session_file.read_text().strip() or None
    except (OSError, UnicodeDecodeError):
        return None


def _write_session_id(session_file: Path | None, session_id: str | None) -> None:
    """Atomically write session ID to file."""
    if not session_file or not session_id:
        return
    session_file.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write using temp file
    temp_file = session_file.with_suffix(".tmp")
    temp_file.write_text(session_id)
    temp_file.replace(session_file)


class ClaudeCodeAdapter(AgentAdapter):
    """Adapter for Claude Code CLI with session continuation."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)

    def _build_cmd(self, prompt: str, session_file: Path | None = None) -> list[str]:
        """Build command with optional session resumption."""
        cmd = ["claude", "--print", "--output-format", "json"]

        if self.config.model:
            cmd.extend(["--model", self.config.model])

        cli_session_id = _read_session_id(session_file)
        if cli_session_id:
            cmd.extend(["--resume", cli_session_id])

        cmd.extend(["-p", prompt])
        return cmd

    def spawn(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
        session_file: Path | None = None,
    ) -> AgentHandle:
        """Spawn Claude Code as a subprocess, optionally resuming a session."""
        cmd = self._build_cmd(prompt, session_file)

        # Note: log_fh intentionally left open - will be closed when process exits
        # and file descriptor is garbage collected. For proper cleanup, use run_sync.
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
        return f"Claude Code ({self.config.model})"


class ClaudeCodeSyncAdapter(AgentAdapter):
    """Synchronous Claude Code adapter with session continuation."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)

    def _build_cmd(
        self,
        prompt: str,
        session_file: Path | None = None,
        project_root: Path | None = None,
    ) -> list[str]:
        """Build command with optional session resumption and project permissions."""
        cmd = ["claude", "--print", "--output-format", "json"]

        if self.config.model:
            cmd.extend(["--model", self.config.model])

        # Allow full access within project directory
        if project_root:
            cmd.extend(["--add-dir", str(project_root)])
            # Allow all tools needed for exploration and planning
            cmd.extend(
                [
                    "--allowedTools",
                    # File operations
                    "Read",
                    "Edit",
                    "Write",
                    "MultiEdit",
                    "Glob",
                    "Grep",
                    "LS",
                    # Notebook support
                    "NotebookRead",
                    "NotebookEdit",
                    # Web access for research
                    "WebFetch",
                    "WebSearch",
                    # Subagents for complex exploration
                    "Task",
                    # Bash - allow most common commands for exploration
                    "Bash(git:*)",
                    "Bash(ls:*)",
                    "Bash(find:*)",
                    "Bash(cat:*)",
                    "Bash(head:*)",
                    "Bash(tail:*)",
                    "Bash(wc:*)",
                    "Bash(grep:*)",
                    "Bash(rg:*)",
                    "Bash(tree:*)",
                    "Bash(file:*)",
                    "Bash(stat:*)",
                    "Bash(du:*)",
                    "Bash(pwd:*)",
                    "Bash(echo:*)",
                    "Bash(which:*)",
                    "Bash(env:*)",
                    "Bash(python:*)",
                    "Bash(python3:*)",
                    "Bash(node:*)",
                    "Bash(npm:*)",
                    "Bash(pnpm:*)",
                    "Bash(yarn:*)",
                    "Bash(pip:*)",
                    "Bash(uv:*)",
                    "Bash(cargo:*)",
                    "Bash(go:*)",
                    "Bash(make:*)",
                    "Bash(jq:*)",
                    "Bash(curl:*)",
                    "Bash(diff:*)",
                    "Bash(sort:*)",
                    "Bash(uniq:*)",
                    "Bash(xargs:*)",
                    "Bash(sed:*)",
                    "Bash(awk:*)",
                ]
            )

        cli_session_id = _read_session_id(session_file)
        if cli_session_id:
            cmd.extend(["--resume", cli_session_id])

        cmd.extend(["-p", prompt])
        return cmd

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
        Run Claude Code synchronously with session continuation.
        Streams output to log file in real-time.

        Returns:
            Tuple of (success, output)
        """
        cmd = self._build_cmd(prompt, session_file, project_root=worktree)

        try:
            # Use Popen to stream output in real-time
            log_mode = "a" if append_log else "w"
            with open(log_file, log_mode) as log_fh:
                if append_log:
                    log_fh.write(f"\n{'=' * 60}\n")
                    log_fh.write("=== New run ===\n")
                    log_fh.write(f"{'=' * 60}\n\n")
                process = subprocess.Popen(
                    cmd,
                    cwd=worktree,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                # Stream output to log file as it arrives
                output_lines: list[str] = []
                assert process.stdout is not None
                for line in process.stdout:
                    log_fh.write(line)
                    log_fh.flush()
                    output_lines.append(line)

                process.wait(timeout=timeout)
                full_output = "".join(output_lines)

            # Parse JSON output to extract session_id and result
            output_text = full_output
            new_session_id = None

            try:
                data = json.loads(full_output)
                new_session_id = data.get("session_id")
                output_text = data.get("result", full_output)
            except json.JSONDecodeError:
                pass  # Fall back to raw output

            # Save session ID atomically
            _write_session_id(session_file, new_session_id)

            if process.returncode == 0:
                # Don't overwrite output_file - agent should have written to it directly
                # Only write if file doesn't exist or is empty (agent failed to write)
                if not output_file.exists() or output_file.stat().st_size == 0:
                    output_file.write_text(output_text)
                return True, output_file.read_text() if output_file.exists() else output_text
            else:
                return False, full_output or "Unknown error"

        except subprocess.TimeoutExpired:
            return False, "Timeout expired"
        except FileNotFoundError:
            return False, "claude CLI not found. Install from: https://claude.ai/code"
        except Exception as e:
            return False, str(e)

    def spawn(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
        session_file: Path | None = None,
    ) -> AgentHandle:
        """Spawn Claude Code as a subprocess."""
        cmd = self._build_cmd(prompt, session_file, project_root=worktree)

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
