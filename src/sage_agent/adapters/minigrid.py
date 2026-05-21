"""MiniGrid adapter for standalone SAGE generalization smoke tests.

The adapter uses official MiniGrid environments through their public Gymnasium
API. It exposes a fully observed grid state as the task artifact for this smoke:
SAGE sees walls, the agent start pose, the goal position, and allowed action
names, then must generate a reusable deterministic action planner. It does not
expose episode rewards, labels, expert trajectories, or reference policies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from sage_agent.interfaces import (
    EnvironmentProfile,
    GapSignal,
    HelperRecord,
    TaskRunResult,
    TaskSpec,
    ToolUseRecord,
    ValidationCase,
)
from sage_agent.validation import validate_helper_candidate


@dataclass
class MiniGridAdapter:
    """Small official MiniGrid smoke adapter.

    This is intentionally bounded and deterministic. It validates that the
    standalone SAGE lifecycle can adapt to a stateful grid-navigation API that
    is neither ToolSandbox nor CyberGym.
    """

    env_ids: tuple[str, ...] = (
        "MiniGrid-Empty-5x5-v0",
        "MiniGrid-Empty-6x6-v0",
        "MiniGrid-Empty-8x8-v0",
    )
    seeds: tuple[int, ...] = (1, 2, 3, 4, 5)
    max_steps: int = 80
    _tasks: tuple[TaskSpec, ...] = field(default=(), init=False)

    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name="minigrid",
            description=(
                "Official MiniGrid goal-oriented grid-world environments using "
                "visible grid observations and discrete navigation actions."
            ),
            base_tools=("reset", "step"),
            action_tools=("left", "right", "forward"),
            observation_fields=(
                "grid_rows",
                "agent_start",
                "agent_direction",
                "goal_position",
                "allowed_actions",
            ),
            helper_families=("grid_action_planner",),
            safety_rules=(
                "helpers may only plan action names",
                "helpers must not step the environment or mutate state",
                "environment adapter executes and scores actions privately",
            ),
            metadata={
                "paper": (
                    "Minigrid & Miniworld: Modular & Customizable Reinforcement "
                    "Learning Environments for Goal-Oriented Tasks"
                ),
                "repo": "https://github.com/Farama-Foundation/Minigrid",
            },
        )

    def prepare(self) -> None:
        self._tasks = tuple(self._build_tasks())

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        if not self._tasks:
            self.prepare()
        return tuple(self._tasks[:limit] if limit is not None else self._tasks)

    def route_helpers(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> tuple[str, ...]:
        del task
        return tuple(
            name
            for name, record in helpers.items()
            if record.candidate.spec.family == "grid_action_planner"
            and not record.retired
        )[:2]

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        if not helpers:
            return self._run_baseline(task)
        name, record = next(iter(helpers.items()))
        validation = validate_helper_candidate(record.candidate)
        if not validation.accepted:
            return TaskRunResult(
                task=task,
                success=False,
                score=0.0,
                outcome_score=0.0,
                transcript=(f"Generated helper {name} failed validation.",),
                tool_uses=(ToolUseRecord(name, generated_helper=True, success=False),),
            )
        function = _load_helper(record)
        planner_result = function(
            grid_rows=list(task.metadata["grid_rows"]),
            start_row=int(task.metadata["start_row"]),
            start_col=int(task.metadata["start_col"]),
            start_dir=int(task.metadata["start_dir"]),
            goal_row=int(task.metadata["goal_row"]),
            goal_col=int(task.metadata["goal_col"]),
            blocked_symbols=["#", "L"],
        )
        action_names = [
            str(item)
            for item in planner_result.get("actions", [])
            if str(item) in {"left", "right", "forward"}
        ]
        executed = self._execute_actions(task, action_names)
        return TaskRunResult(
            task=task,
            success=executed["success"],
            score=executed["score"],
            outcome_score=executed["score"],
            transcript=(
                f"{name} planned {len(action_names)} actions: {action_names[:20]}",
                f"MiniGrid execution success={executed['success']} reward={executed['reward']}",
            ),
            tool_uses=(
                ToolUseRecord(
                    tool_name=name,
                    arguments={
                        "grid_rows": list(task.metadata["grid_rows"]),
                        "start_row": task.metadata["start_row"],
                        "start_col": task.metadata["start_col"],
                        "start_dir": task.metadata["start_dir"],
                        "goal_row": task.metadata["goal_row"],
                        "goal_col": task.metadata["goal_col"],
                    },
                    result=planner_result,
                    success=executed["success"],
                    generated_helper=True,
                ),
            ),
            artifacts={
                "planned_actions": action_names,
                "steps": executed["steps"],
                "reward": executed["reward"],
            },
        )

    def observe_gap(
        self,
        task: TaskSpec,
        result: TaskRunResult,
        helpers: Mapping[str, HelperRecord],
    ) -> GapSignal | None:
        if result.success or any(
            record.candidate.spec.family == "grid_action_planner"
            for record in helpers.values()
        ):
            return None
        return GapSignal(
            key="grid_shortest_path_action_planning",
            summary=(
                "Plan a shortest safe action sequence from a visible grid state, "
                "start position, start direction, and goal position."
            ),
            source_task_id=task.task_id,
            source_environment="minigrid",
            severity=0.9,
            suggested_tool_name="plan_grid_shortest_path_actions",
            suggested_helper_family="grid_action_planner",
            evidence=(
                "visible grid rows",
                "agent start pose",
                "goal cell",
                "discrete navigation actions",
            ),
            required_inputs={
                "grid_rows": "list[str]",
                "start_row": "int",
                "start_col": "int",
                "start_dir": "int",
                "goal_row": "int",
                "goal_col": "int",
                "blocked_symbols": "list[str]",
            },
            expected_outputs={
                "actions": "list[str]",
                "action_count": "int",
                "path_found": "bool",
                "abstain": "bool",
                "abstain_reason": "str",
            },
            generation_directives={"template": "grid_shortest_path_action_planner"},
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        del gap
        return (
            ValidationCase(
                name="straight_then_down",
                inputs={
                    "grid_rows": ["#####", "#A..#", "#...#", "#..G#", "#####"],
                    "start_row": 1,
                    "start_col": 1,
                    "start_dir": 0,
                    "goal_row": 3,
                    "goal_col": 3,
                    "blocked_symbols": ["#"],
                },
                expected={
                    "actions": ["forward", "forward", "right", "forward", "forward"],
                    "path_found": True,
                    "abstain": False,
                },
            ),
            ValidationCase(
                name="blocked_no_path",
                inputs={
                    "grid_rows": ["#####", "#A#G#", "#####"],
                    "start_row": 1,
                    "start_col": 1,
                    "start_dir": 0,
                    "goal_row": 1,
                    "goal_col": 3,
                    "blocked_symbols": ["#"],
                },
                expected={"path_found": False, "abstain": True},
                should_abstain=True,
            ),
        )

    def _build_tasks(self) -> list[TaskSpec]:
        tasks: list[TaskSpec] = []
        index = 0
        for env_id in self.env_ids:
            for seed in self.seeds:
                state = self._visible_state(env_id, seed)
                index += 1
                tasks.append(
                    TaskSpec(
                        task_id=f"minigrid:{env_id}:{seed}",
                        name=f"MiniGrid navigation {env_id} seed {seed}",
                        prompt=(
                            "Reach the goal using only allowed discrete actions. "
                            "Use visible grid rows and start pose; do not use an "
                            "expert trajectory."
                        ),
                        artifacts={
                            "grid_ascii": "\n".join(state["grid_rows"]),
                            "grid_rows": json.dumps(state["grid_rows"]),
                            "allowed_actions": "left,right,forward",
                        },
                        metadata={
                            "env_id": env_id,
                            "seed": seed,
                            "grid_rows": tuple(state["grid_rows"]),
                            "start_row": state["start_row"],
                            "start_col": state["start_col"],
                            "start_dir": state["start_dir"],
                            "goal_row": state["goal_row"],
                            "goal_col": state["goal_col"],
                            "order_index": index,
                        },
                    )
                )
        return tasks

    def _run_baseline(self, task: TaskSpec) -> TaskRunResult:
        actions = ["forward"] * min(self.max_steps, 12)
        executed = self._execute_actions(task, actions)
        return TaskRunResult(
            task=task,
            success=executed["success"],
            score=executed["score"],
            outcome_score=executed["score"],
            transcript=(
                f"Baseline executed fixed forward policy for {executed['steps']} steps.",
            ),
            artifacts={
                "planned_actions": actions,
                "steps": executed["steps"],
                "reward": executed["reward"],
            },
        )

    def _execute_actions(
        self, task: TaskSpec, action_names: list[str]
    ) -> dict[str, Any]:
        import gymnasium as gym
        import minigrid  # noqa: F401 - registers MiniGrid environments

        env = gym.make(str(task.metadata["env_id"]), render_mode=None)
        try:
            env.reset(seed=int(task.metadata["seed"]))
            action_map = {
                "left": env.unwrapped.actions.left,
                "right": env.unwrapped.actions.right,
                "forward": env.unwrapped.actions.forward,
            }
            reward_total = 0.0
            success = False
            steps = 0
            for action_name in action_names[: self.max_steps]:
                _, reward, terminated, truncated, _ = env.step(action_map[action_name])
                reward_total += float(reward)
                steps += 1
                if terminated or truncated:
                    success = bool(reward > 0)
                    break
            return {
                "success": success,
                "score": 1.0 if success else 0.0,
                "reward": reward_total,
                "steps": steps,
            }
        finally:
            env.close()

    def _visible_state(self, env_id: str, seed: int) -> dict[str, Any]:
        import gymnasium as gym
        import minigrid  # noqa: F401 - registers MiniGrid environments

        env = gym.make(env_id, render_mode=None)
        try:
            env.reset(seed=seed)
            unwrapped = env.unwrapped
            agent_col, agent_row = unwrapped.agent_pos
            goal_row = -1
            goal_col = -1
            rows: list[str] = []
            for row in range(unwrapped.height):
                chars: list[str] = []
                for col in range(unwrapped.width):
                    if (col, row) == tuple(unwrapped.agent_pos):
                        chars.append("A")
                        continue
                    cell = unwrapped.grid.get(col, row)
                    if cell is None:
                        chars.append(".")
                    elif cell.type == "wall":
                        chars.append("#")
                    elif cell.type == "goal":
                        chars.append("G")
                        goal_row = row
                        goal_col = col
                    elif cell.type == "lava":
                        chars.append("L")
                    else:
                        chars.append("?")
                rows.append("".join(chars))
            return {
                "grid_rows": rows,
                "start_row": int(agent_row),
                "start_col": int(agent_col),
                "start_dir": int(unwrapped.agent_dir),
                "goal_row": goal_row,
                "goal_col": goal_col,
            }
        finally:
            env.close()


def _load_helper(record: HelperRecord):
    namespace: dict[str, object] = {}
    exec(  # noqa: S102 - helper already passed standalone validator
        record.candidate.code,
        {"__builtins__": _safe_builtins()},
        namespace,
    )
    return namespace[record.candidate.spec.name]


def _safe_builtins() -> dict[str, object]:
    return {
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "isinstance": isinstance,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "range": range,
        "reversed": reversed,
        "set": set,
        "str": str,
        "tuple": tuple,
    }
