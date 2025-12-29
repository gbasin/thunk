"""Codex CLI adapter with session continuation support."""

import json
import subprocess
from pathlib import Path

from ..models import AgentConfig
from .base import AgentAdapter, AgentHandle


def _read_thread_id(session_file: Path | None) -> str | None:
    """Safely read thread ID from file."""
    if not session_file or not session_file.exists():
        return None
    try:
        return session_file.read_text().strip() or None
    except (OSError, UnicodeDecodeError):
        return None


def _write_thread_id(session_file: Path | None, thread_id: str | None) -> None:
    """Atomically write thread ID to file."""
    if not session_file or not thread_id:
        return
    session_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = session_file.with_suffix(".tmp")
    temp_file.write_text(thread_id)
    temp_file.replace(session_file)


def _parse_codex_output(stdout: str) -> tuple[str | None, str]:
    """Parse Codex JSON lines output to extract thread_id and final message."""
    thread_id = None
    messages: list[str] = []

    for line in stdout.strip().split("\n"):
        if not line:
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "thread.started":
                thread_id = event.get("thread_id")
            elif event.get("type") == "item.message" and event.get("role") == "assistant":
                content = event.get("content", "")
                if content:
                    messages.append(content)
        except json.JSONDecodeError:
            pass  # Skip non-JSON lines

    final_output = messages[-1] if messages else stdout
    return thread_id, final_output


class CodexCLIAdapter(AgentAdapter):
    """Adapter for OpenAI Codex CLI with session continuation."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)

    def _build_cmd(self, prompt: str, session_file: Path | None = None) -> list[str]:
        """Build command with optional session resumption."""
        thread_id = _read_thread_id(session_file)

        if thread_id:
            # Resume existing session: codex resume <thread_id> --json "prompt"
            return ["codex", "resume", thread_id, "--json", prompt]
        else:
            # New session: codex exec --json "prompt"
            return ["codex", "exec", "--json", prompt]

    def spawn(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
        session_file: Path | None = None,
    ) -> AgentHandle:
        """Spawn Codex CLI as a subprocess, optionally resuming a session."""
        cmd = self._build_cmd(prompt, session_file)

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
        return f"Codex CLI ({self.config.model})"


class CodexCLISyncAdapter(AgentAdapter):
    """Synchronous Codex CLI adapter with session continuation."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)

    def _build_cmd(
        self,
        prompt: str,
        session_file: Path | None = None,
        project_root: Path | None = None,
    ) -> list[str]:
        """Build command with optional session resumption and project permissions."""
        thread_id = _read_thread_id(session_file)

        if thread_id:
            # Resume existing session
            cmd = ["codex", "resume", thread_id, "--json"]
            # Add project root for resumed sessions too
            if project_root:
                cmd.extend(["--add-dir", str(project_root)])
        else:
            # New session with full auto mode for minimal friction
            cmd = ["codex", "exec", "--json"]
            # --full-auto enables workspace-write sandbox + auto-approve
            cmd.append("--full-auto")
            # Add project root as additional writable directory
            if project_root:
                cmd.extend(["--add-dir", str(project_root)])

        cmd.append(prompt)
        return cmd

    def run_sync(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
        timeout: int | None = None,
        session_file: Path | None = None,
    ) -> tuple[bool, str]:
        """
        Run Codex CLI synchronously with session continuation.
        Streams output to log file in real-time.

        Returns:
            Tuple of (success, output)
        """
        cmd = self._build_cmd(prompt, session_file, project_root=worktree)

        try:
            # Use Popen to stream output in real-time
            with open(log_file, "w") as log_fh:
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

            # Parse output
            thread_id, final_output = _parse_codex_output(full_output)

            # Save thread_id atomically
            _write_thread_id(session_file, thread_id)

            if process.returncode == 0:
                output_file.write_text(final_output)
                return True, final_output
            else:
                return False, full_output or "Unknown error"

        except subprocess.TimeoutExpired:
            return False, "Timeout expired"
        except FileNotFoundError:
            return False, "codex CLI not found. Install with: npm install -g @openai/codex"
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
        """Spawn Codex CLI as a subprocess."""
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
        return f"Codex CLI Sync ({self.config.model})"
