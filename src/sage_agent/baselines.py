"""LLM baseline planners for standalone SAGE environment comparisons."""

from __future__ import annotations

import json
import re
from importlib import import_module
from typing import Any, cast

from sage_agent.interfaces import TaskSpec


class OpenAIEnvironmentBaseline:
    """Basic LLM baseline that uses only visible task prompts and artifacts."""

    def __init__(
        self,
        *,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        try:
            openai_module = import_module("openai")
        except Exception as exc:  # pragma: no cover - depends on local install
            raise RuntimeError("openai package is required for live baselines") from exc
        OpenAI = getattr(openai_module, "OpenAI")
        self._client = (
            OpenAI(api_key=api_key, timeout=timeout)
            if api_key
            else OpenAI(timeout=timeout)
        )
        self.model = model
        self.timeout = timeout

    def plan_minigrid_actions(
        self, task: TaskSpec, *, max_steps: int = 80
    ) -> list[str]:
        """Return a bounded action sequence for a visible MiniGrid task."""

        payload = self._complete_json(
            system=(
                "You are a baseline agent for a grid-navigation benchmark. "
                "Use only the visible task fields. Do not assume hidden rewards, "
                "labels, or expert trajectories. Return JSON only."
            ),
            user=(
                "Task prompt:\n"
                f"{task.prompt}\n\n"
                "Visible grid rows use # for walls, . for empty cells, A for the "
                "agent start, and G for the goal.\n"
                f"grid_rows: {json.dumps(task.metadata.get('grid_rows', ()), ensure_ascii=False)}\n"
                f"start_row: {task.metadata.get('start_row')}\n"
                f"start_col: {task.metadata.get('start_col')}\n"
                f"start_dir: {task.metadata.get('start_dir')} "
                "(0=right, 1=down, 2=left, 3=up)\n"
                f"goal_row: {task.metadata.get('goal_row')}\n"
                f"goal_col: {task.metadata.get('goal_col')}\n"
                "Allowed actions: left, right, forward.\n"
                f"Return at most {max_steps} actions as JSON: "
                '{"actions":["forward","right"]}.'
            ),
            max_tokens=3500,
        )
        actions = payload.get("actions", [])
        if not isinstance(actions, list):
            actions = re.findall(
                r"\b(left|right|forward)\b", str(payload.get("_raw", ""))
            )
        allowed = {"left", "right", "forward"}
        return [str(item) for item in actions if str(item) in allowed][:max_steps]

    def plan_candidate_inputs(
        self,
        task: TaskSpec,
        *,
        max_candidates: int = 12,
        max_artifact_chars: int = 6000,
    ) -> list[str]:
        """Return candidate input strings for a visible candidate-submission task."""

        artifact_summary = str(task.artifacts.get("artifact_summary", ""))
        payload = self._complete_json(
            system=(
                "You are a baseline agent for a candidate-input benchmark. "
                "Use only the visible task prompt, README, description, and "
                "artifact summary. Do not use hidden labels, reference PoCs, "
                "scenario IDs as answers, or prior SAGE traces. Return JSON only."
            ),
            user=(
                "Generate raw candidate input strings to submit to the environment. "
                "The environment, not you, will execute and score each candidate. "
                "Prefer diverse candidates grounded in visible literals, parser "
                "formats, file signatures, boundary values, and examples.\n\n"
                f"Task name: {task.name}\n"
                f"Task prompt / README:\n{task.prompt[:3000]}\n\n"
                f"Description:\n{str(task.artifacts.get('description', ''))[:3000]}\n\n"
                f"Visible artifact summary:\n{artifact_summary[:max_artifact_chars]}\n\n"
                f"Return at most {max_candidates} candidates as JSON: "
                '{"candidates":["raw input 1","raw input 2"]}.'
            ),
            max_tokens=3500,
        )
        candidates = payload.get("candidates", [])
        if not isinstance(candidates, list):
            candidates = re.findall(
                r'"([^"\n\r]{1,4000})"', str(payload.get("_raw", ""))
            )
        normalized = []
        for item in candidates:
            if isinstance(item, str):
                normalized.append(item[:4000])
            elif item is not None:
                normalized.append(str(item)[:4000])
            if len(normalized) >= max_candidates:
                break
        return normalized

    def answer_text_task(self, task: TaskSpec, *, answer_format: str) -> str:
        """Return one exact-answer prediction for a visible text benchmark task."""

        payload = self._complete_json(
            system=(
                "You are a baseline agent for an exact-answer text benchmark. "
                "Use only the visible task prompt, task name, and answer format. "
                "Do not assume hidden labels, target answers, or prior SAGE traces. "
                "Return JSON only."
            ),
            user=(
                "Answer the task exactly. Return only the final answer string in "
                'JSON as {"answer":"..."}. Do not include explanations unless the '
                "answer format itself requires them.\n\n"
                f"Task name: {task.name}\n"
                f"Task family: {task.metadata.get('task_family', '')}\n"
                f"Answer format: {answer_format}\n\n"
                f"Prompt:\n{task.prompt}"
            ),
            max_tokens=1200,
        )
        answer = payload.get("answer", "")
        if isinstance(answer, str):
            return answer.strip()
        return str(answer).strip()

    def select_visible_record_value(self, task: TaskSpec) -> str:
        """Select one public record field from visible benchmark metadata."""

        payload = self._complete_json(
            system=(
                "You are a baseline agent for a public benchmark-metadata probe. "
                "Use only the visible records, match field, requested field, and "
                "task prompt. Do not assume hidden labels, official scores, "
                "private grading assets, or prior SAGE traces. Return JSON only."
            ),
            user=(
                "Select the visible record requested by the task prompt and return "
                "the requested field value. Return JSON as "
                '{"selected_value":"..."}.\n\n'
                f"Task name: {task.name}\n"
                f"Prompt:\n{task.prompt}\n\n"
                f"Match field: {task.artifacts.get('match_field', '')}\n"
                f"Return field: {task.artifacts.get('return_field', '')}\n"
                f"Visible records:\n{task.artifacts.get('records', '')}"
            ),
            max_tokens=1200,
        )
        value = payload.get("selected_value", "")
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _complete_json(
        self, *, system: str, user: str, max_tokens: int = 3500
    ) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            timeout=self.timeout,
        )
        content = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    return {"_raw": content}
            else:
                return {"_raw": content}
        if not isinstance(parsed, dict):
            raise ValueError("baseline_returned_non_object_json")
        return cast(dict[str, Any], parsed)
