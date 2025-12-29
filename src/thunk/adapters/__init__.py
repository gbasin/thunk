"""Agent adapters for thunk.

Two CLI-based adapters with session continuation:
- ClaudeCodeAdapter/ClaudeCodeSyncAdapter: Uses `claude` CLI with --resume
- CodexCLIAdapter/CodexCLISyncAdapter: Uses `codex exec` with resume --last
"""

from .base import AgentAdapter, AgentHandle
from .claude import ClaudeCodeAdapter, ClaudeCodeSyncAdapter
from .codex import CodexCLIAdapter, CodexCLISyncAdapter

__all__ = [
    "AgentAdapter",
    "AgentHandle",
    "ClaudeCodeAdapter",
    "ClaudeCodeSyncAdapter",
    "CodexCLIAdapter",
    "CodexCLISyncAdapter",
]
