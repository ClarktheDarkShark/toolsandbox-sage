"""Terminal-Bench agent wrappers used by SAGE official live runs.

This module is imported inside the Terminal-Bench virtual environment by
``tb run --agent-import-path``. It deliberately keeps the integration thin:
Terminal-Bench owns terminal execution and scoring, while SAGE supplies a
small evolving guidance file that is appended to the task instruction.
"""

from __future__ import annotations

from pathlib import Path

from terminal_bench.agents.terminus_1 import Terminus


class SAGEGuidedTerminus(Terminus):
    """Terminus agent variant that consumes SAGE-generated run guidance."""

    @staticmethod
    def name() -> str:
        return "sage-guided-terminus"

    def __init__(self, helper_path: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._helper_path = Path(helper_path) if helper_path else None

    def perform_task(self, instruction, session, logging_dir=None):
        guidance = self._load_guidance()
        if guidance:
            instruction = (
                f"{instruction}\n\n"
                "SAGE generated guidance from prior official harness outcomes:\n"
                f"{guidance}\n"
                "Use this guidance only when it helps the current task. Do not "
                "skip validation, do not assume hidden tests, and do not modify "
                "files outside the task workspace."
            )
        return super().perform_task(instruction, session, logging_dir)

    def _load_guidance(self) -> str:
        if self._helper_path is None or not self._helper_path.exists():
            return ""
        return self._helper_path.read_text(encoding="utf-8").strip()
