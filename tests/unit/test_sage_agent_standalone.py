from pathlib import Path

from sage_agent import SAGEAgent, SAGEConfig
from sage_agent.adapters import CyberGymAdapter, ToolSandboxMiniAdapter
from sage_agent.generators import TemplateHelperGenerator


def test_standalone_sage_births_and_reuses_tool_on_toolsandbox_shape(
    tmp_path: Path,
) -> None:
    agent = SAGEAgent(
        adapter=ToolSandboxMiniAdapter(),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(registry_dir=tmp_path / "registry"),
    )

    first = agent.run(limit=1)
    assert first.environment == "toolsandbox"
    assert first.tools_born == 1
    assert first.tools_accepted == 1

    second = agent.run(limit=2)
    assert second.tools_reused >= 1
    assert second.tasks_succeeded >= 1


def test_standalone_sage_cybergym_adapter_births_log_classifier(
    tmp_path: Path,
) -> None:
    repo_root = Path("external/cybergym")
    agent = SAGEAgent(
        adapter=CyberGymAdapter(repo_root=repo_root),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(registry_dir=tmp_path / "registry"),
    )

    first = agent.run(limit=1)
    assert first.environment == "cybergym"
    assert first.tools_born == 1
    assert first.tools_accepted == 1

    second = agent.run(limit=1)
    assert second.tools_reused == 1
    assert second.tasks_succeeded == 1
