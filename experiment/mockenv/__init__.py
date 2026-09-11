"""Fully synthetic mock environment.

Nothing in this package performs network access, touches real credentials, or
changes anything outside a repository-local sandbox directory. The "dangerous"
operations mutate an in-memory dictionary.
"""

from experiment.mockenv.registry import TOOL_REGISTRY, ToolSpec, privileged_tools
from experiment.mockenv.services import MockEnvironment

__all__ = ["TOOL_REGISTRY", "ToolSpec", "privileged_tools", "MockEnvironment"]
