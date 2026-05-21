"""Standalone SAGE agent package.

The :mod:`sage_agent` package is the environment-neutral boundary for SAGE.
It intentionally contains no ToolSandbox-specific assumptions. Environments
provide adapters; SAGE provides the gap-to-helper lifecycle.
"""

from sage_agent.baselines import OpenAIEnvironmentBaseline
from sage_agent.controller import SAGEAgent, SAGEConfig, SAGERunSummary
from sage_agent.dashboard import open_standalone_dashboard, write_standalone_dashboard
from sage_agent.gap_mining import mine_gap_signals
from sage_agent.generators import OpenAIHelperGenerator, TemplateHelperGenerator
from sage_agent.integrity import (
    IntegrityError,
    IntegrityIssue,
    IntegrityReport,
    ResearchIntegrityPolicy,
)
from sage_agent.interfaces import (
    EnvironmentAdapter,
    EnvironmentProfile,
    GapSignal,
    HelperCandidate,
    HelperGenerator,
    HelperRecord,
    HelperRepairGenerator,
    HelperSpec,
    HelperValidationReport,
    TaskRunResult,
    TaskSpec,
    ToolUseRecord,
    ValidationCase,
)
from sage_agent.lifecycle import HelperLifecycleAssessment, assess_helper_lifecycle
from sage_agent.registry import LocalSAGERegistry

__all__ = [
    "EnvironmentAdapter",
    "EnvironmentProfile",
    "GapSignal",
    "HelperCandidate",
    "HelperGenerator",
    "HelperLifecycleAssessment",
    "HelperRecord",
    "HelperRepairGenerator",
    "HelperSpec",
    "HelperValidationReport",
    "IntegrityError",
    "IntegrityIssue",
    "IntegrityReport",
    "LocalSAGERegistry",
    "OpenAIEnvironmentBaseline",
    "OpenAIHelperGenerator",
    "ResearchIntegrityPolicy",
    "SAGEAgent",
    "SAGEConfig",
    "SAGERunSummary",
    "TemplateHelperGenerator",
    "TaskRunResult",
    "TaskSpec",
    "ToolUseRecord",
    "ValidationCase",
    "assess_helper_lifecycle",
    "mine_gap_signals",
    "open_standalone_dashboard",
    "write_standalone_dashboard",
]
