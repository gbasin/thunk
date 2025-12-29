"""OpenAI API adapter."""

import os
from pathlib import Path

from ..models import AgentConfig
from .base import AgentAdapter, AgentHandle


class OpenAIAdapter(AgentAdapter):
    """Adapter for OpenAI API."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.api_key = os.environ.get("OPENAI_API_KEY")

    def spawn(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
    ) -> AgentHandle:
        """
        Spawn is not ideal for API calls - use run_sync instead.
        This implementation starts a background thread.
        """
        import threading

        # Create a simple wrapper that we can poll
        class APIProcess:
            def __init__(self):
                self.returncode: int | None = None
                self.output: str = ""
                self.error: str = ""

            def poll(self) -> int | None:
                return self.returncode

        process = APIProcess()

        def run_api():
            try:
                success, output = self.run_sync(worktree, prompt, output_file, log_file)
                process.output = output
                process.returncode = 0 if success else 1
            except Exception as e:
                process.error = str(e)
                process.returncode = 1

        thread = threading.Thread(target=run_api)
        thread.start()

        return AgentHandle(
            agent_id=self.config.id,
            process=process,
            log_file=log_file,
        )

    def run_sync(
        self,
        worktree: Path,
        prompt: str,
        output_file: Path,
        log_file: Path,
        timeout: int | None = None,
    ) -> tuple[bool, str]:
        """
        Run OpenAI API call synchronously.

        Returns:
            Tuple of (success, output)
        """
        try:
            # Import here to make openai optional
            from openai import OpenAI
        except ImportError:
            return False, "openai package not installed. Run: pip install openai"

        if not self.api_key:
            return False, "OPENAI_API_KEY environment variable not set"

        client = OpenAI(api_key=self.api_key)

        try:
            # Build context about the worktree
            context = self._build_context(worktree)

            system_msg = "You are a software architect creating implementation plans."
            response = client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"{context}\n\n{prompt}"},
                ],
                timeout=timeout,
            )

            output = response.choices[0].message.content or ""

            # Write to files
            with open(log_file, "w") as f:
                f.write(f"Model: {self.config.model}\n")
                f.write(f"Tokens: {response.usage.total_tokens if response.usage else 'unknown'}\n")
                f.write("---\n")
                f.write(output)

            output_file.write_text(output)

            return True, output

        except Exception as e:
            error_msg = str(e)
            with open(log_file, "w") as f:
                f.write(f"Error: {error_msg}\n")
            return False, error_msg

    def _build_context(self, worktree: Path) -> str:
        """Build context about the working directory."""
        # Read AGENTS.md if it exists
        agents_md = worktree / "AGENTS.md"
        if agents_md.exists():
            return f"Project context:\n{agents_md.read_text()}\n"

        # Fallback: read README
        readme = worktree / "README.md"
        if readme.exists():
            return f"Project README:\n{readme.read_text()}\n"

        return ""

    def get_name(self) -> str:
        return f"OpenAI ({self.config.model})"
