"""Standalone SAGE agent package.

The :mod:`sage_agent` package is the environment-neutral boundary for SAGE.
It intentionally contains no ToolSandbox-specific assumptions. Environments
provide adapters; SAGE provides the gap-to-helper lifecycle.
"""

from sage_agent.controller import SAGEAgent, SAGEConfig, SAGERunSummary
from sage_agent.interfaces import (
    EnvironmentAdapter,
    EnvironmentProfile,
    GapSignal,
    HelperCandidate,
    HelperRecord,
    HelperSpec,
    HelperValidationReport,
    TaskRunResult,
    TaskSpec,
    ToolUseRecord,
    ValidationCase,
)
from sage_agent.registry import LocalSAGERegistry

__all__ = [
    "EnvironmentAdapter",
    "EnvironmentProfile",
    "GapSignal",
    "HelperCandidate",
    "HelperRecord",
    "HelperSpec",
    "HelperValidationReport",
    "LocalSAGERegistry",
    "SAGEAgent",
    "SAGEConfig",
    "SAGERunSummary",
    "TaskRunResult",
    "TaskSpec",
    "ToolUseRecord",
    "ValidationCase",
]
