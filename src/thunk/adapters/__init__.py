"""Agent adapters for thunk."""

from .base import AgentAdapter, AgentHandle
from .claude import ClaudeCodeAdapter

__all__ = ["AgentAdapter", "AgentHandle", "ClaudeCodeAdapter"]
