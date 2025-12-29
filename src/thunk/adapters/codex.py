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

    def _build_cmd(self, prompt: str, session_file: Path | None = None) -> list[str]:
        """Build command with optional session resumption."""
        thread_id = _read_thread_id(session_file)

        if thread_id:
            # Resume existing session: codex resume <thread_id> --json "prompt"
            return ["codex", "resume", thread_id, "--json", prompt]
        else:
            # New session: codex exec --json "prompt"
            return ["codex", "exec", "--json", prompt]

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

        Returns:
            Tuple of (success, output)
        """
        cmd = self._build_cmd(prompt, session_file)

        try:
            result = subprocess.run(
                cmd,
                cwd=worktree,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Parse output
            thread_id, final_output = _parse_codex_output(result.stdout)

            # Save thread_id atomically
            _write_thread_id(session_file, thread_id)

            # Write output to files
            with open(log_file, "w") as f:
                f.write(f"Thread ID: {thread_id}\n---\n")
                f.write(result.stdout)
                if result.stderr:
                    f.write("\n--- STDERR ---\n")
                    f.write(result.stderr)

            if result.returncode == 0:
                output_file.write_text(final_output)
                return True, final_output
            else:
                return False, result.stderr or "Unknown error"

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
        return f"Codex CLI Sync ({self.config.model})"
