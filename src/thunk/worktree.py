"""Git worktree management for thunk."""

import subprocess
from pathlib import Path


class WorktreeManager:
    """Manages git worktrees for agent isolation."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def create_worktree(self, session_id: str, agent_id: str) -> Path:
        """
        Create a git worktree for an agent.

        Returns the path to the worktree.
        """
        worktree_name = f"worktree-thunk-{session_id}-{agent_id}"
        worktree_path = self.repo_root.parent / worktree_name

        if worktree_path.exists():
            # Already exists, return it
            return worktree_path

        try:
            # Create a new worktree from HEAD
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(worktree_path)],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create worktree: {e.stderr.decode()}")

        return worktree_path

    def remove_worktree(self, session_id: str, agent_id: str) -> bool:
        """Remove an agent's worktree."""
        worktree_name = f"worktree-thunk-{session_id}-{agent_id}"
        worktree_path = self.repo_root.parent / worktree_name

        if not worktree_path.exists():
            return False

        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            # Try manual cleanup
            import shutil
            try:
                shutil.rmtree(worktree_path)
                # Prune worktree references
                subprocess.run(
                    ["git", "worktree", "prune"],
                    cwd=self.repo_root,
                    capture_output=True,
                )
                return True
            except Exception:
                return False

    def remove_all_session_worktrees(self, session_id: str) -> int:
        """Remove all worktrees for a session. Returns count removed."""
        prefix = f"worktree-thunk-{session_id}-"
        removed = 0

        for path in self.repo_root.parent.iterdir():
            if path.is_dir() and path.name.startswith(prefix):
                agent_id = path.name.replace(prefix, "")
                if self.remove_worktree(session_id, agent_id):
                    removed += 1

        return removed

    def list_worktrees(self, session_id: str | None = None) -> list[Path]:
        """List worktrees, optionally filtered by session."""
        prefix = "worktree-thunk-"
        if session_id:
            prefix = f"worktree-thunk-{session_id}-"

        worktrees = []
        for path in self.repo_root.parent.iterdir():
            if path.is_dir() and path.name.startswith(prefix):
                worktrees.append(path)

        return worktrees

    @staticmethod
    def is_git_repo(path: Path) -> bool:
        """Check if path is inside a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=path,
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def get_repo_root(path: Path) -> Path | None:
        """Get the root of the git repository containing path."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except Exception:
            pass
        return None
