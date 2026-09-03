from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

import scripts.verify_publication_environment as environment_verifier
from scripts.verify_publication_environment import (
    DistributionRecord,
    EnvironmentVerificationError,
    verify_environment,
)


def _write_lock(path: Path, text: str = "Alpha_Package==1.2.3\n") -> str:
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _external(
    root: Path,
    name: str = "Alpha-Package",
    version: str = "1.2.3",
) -> DistributionRecord:
    return DistributionRecord(
        name=name,
        version=version,
        metadata_path=root / "site-packages" / f"{name}.dist-info",
    )


def _editable_project(repo: Path, metadata_root: Path) -> DistributionRecord:
    return DistributionRecord(
        name="toolsandbox-sage",
        version="0.1.0",
        metadata_path=metadata_root / "toolsandbox_sage-0.1.0.dist-info",
        direct_url_json=json.dumps(
            {
                "dir_info": {"editable": True},
                "url": repo.as_uri(),
            }
        ),
    )


def test_exact_environment_passes_and_allows_only_repo_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    lock = repo / "requirements-publication-lock.txt"
    lock_hash = _write_lock(lock)
    records = (
        _external(tmp_path),
        DistributionRecord(
            name="tool_sandbox",
            version="0.0.1",
            metadata_path=repo / "tool_sandbox.egg-info",
        ),
        _editable_project(repo, tmp_path / "site-packages"),
    )

    report = verify_environment(
        lock,
        repo_root=repo,
        expected_lock_sha256=lock_hash,
        python_version=(3, 12, 7),
        python_executable=str(tmp_path / "venv" / "bin" / "python"),
        python_prefix=str(tmp_path / "venv"),
        python_base_prefix=str(tmp_path / "base"),
        python_implementation="CPython",
        platform_system="Darwin",
        platform_machine="arm64",
        installed_distributions=records,
        pip_checker=lambda: "No broken requirements found.",
    )

    assert report["status"] == "pass"
    assert report["external_distribution_count"] == 1
    assert (
        report["external_distribution_sha256"]
        == hashlib.sha256(b"alpha-package==1.2.3\n").hexdigest()
    )
    assert report["environment_lock_sha256"] == lock_hash
    repository_metadata = report["repository_distribution_metadata"]
    assert isinstance(repository_metadata, list)
    repository_names: list[object] = []
    for item in repository_metadata:
        assert isinstance(item, dict)
        repository_names.append(item["name"])
    assert repository_names == [
        "tool-sandbox",
        "toolsandbox-sage",
    ]
    assert report["pip_check"] == "No broken requirements found."


def test_verifier_requires_exact_python_and_lock_hash(tmp_path: Path) -> None:
    lock = tmp_path / "requirements-publication-lock.txt"
    lock_hash = _write_lock(lock)

    with pytest.raises(EnvironmentVerificationError, match="Python 3.12.7 exactly"):
        verify_environment(
            lock,
            repo_root=tmp_path,
            expected_lock_sha256=lock_hash,
            python_version=(3, 12, 6),
            python_prefix=str(tmp_path / "venv"),
            python_base_prefix=str(tmp_path / "base"),
            python_implementation="CPython",
            platform_system="Darwin",
            platform_machine="arm64",
            installed_distributions=(),
            pip_checker=lambda: "pass",
        )

    with pytest.raises(EnvironmentVerificationError, match="lock hash mismatch"):
        verify_environment(
            lock,
            repo_root=tmp_path,
            expected_lock_sha256="0" * 64,
            python_version=(3, 12, 7),
            python_prefix=str(tmp_path / "venv"),
            python_base_prefix=str(tmp_path / "base"),
            python_implementation="CPython",
            platform_system="Darwin",
            platform_machine="arm64",
            installed_distributions=(),
            pip_checker=lambda: "pass",
        )


def test_verifier_requires_isolated_validated_platform(tmp_path: Path) -> None:
    lock = tmp_path / "requirements-publication-lock.txt"
    lock_hash = _write_lock(lock)
    common: dict[str, Any] = {
        "repo_root": tmp_path,
        "expected_lock_sha256": lock_hash,
        "python_version": (3, 12, 7),
        "installed_distributions": (),
        "pip_checker": lambda: "pass",
    }

    with pytest.raises(EnvironmentVerificationError, match="isolated virtual"):
        verify_environment(
            lock,
            python_prefix=str(tmp_path / "base"),
            python_base_prefix=str(tmp_path / "base"),
            python_implementation="CPython",
            platform_system="Darwin",
            platform_machine="arm64",
            **common,
        )

    with pytest.raises(EnvironmentVerificationError, match="Darwin/arm64"):
        verify_environment(
            lock,
            python_prefix=str(tmp_path / "venv"),
            python_base_prefix=str(tmp_path / "base"),
            python_implementation="CPython",
            platform_system="Linux",
            platform_machine="x86_64",
            **common,
        )


def test_verifier_requires_editable_checkout_metadata(tmp_path: Path) -> None:
    lock = tmp_path / "requirements-publication-lock.txt"
    lock_hash = _write_lock(lock)

    with pytest.raises(
        EnvironmentVerificationError, match="missing repository-local editable metadata"
    ):
        verify_environment(
            lock,
            repo_root=tmp_path,
            expected_lock_sha256=lock_hash,
            python_version=(3, 12, 7),
            python_prefix=str(tmp_path / "venv"),
            python_base_prefix=str(tmp_path / "base"),
            python_implementation="CPython",
            platform_system="Darwin",
            platform_machine="arm64",
            installed_distributions=(_external(tmp_path),),
            pip_checker=lambda: "pass",
        )


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ((), "missing locked distributions"),
        (
            (
                DistributionRecord(
                    name="Alpha-Package",
                    version="9.9.9",
                    metadata_path=Path("/external/alpha.dist-info"),
                ),
            ),
            "version mismatches",
        ),
        (
            (
                DistributionRecord(
                    name="Alpha-Package",
                    version="1.2.3",
                    metadata_path=Path("/external/alpha.dist-info"),
                ),
                DistributionRecord(
                    name="Surprise",
                    version="1.0",
                    metadata_path=Path("/external/surprise.dist-info"),
                ),
            ),
            "unexpected external distributions",
        ),
    ],
)
def test_verifier_rejects_missing_mismatched_or_unexpected_external_packages(
    tmp_path: Path,
    records: tuple[DistributionRecord, ...],
    message: str,
) -> None:
    lock = tmp_path / "requirements-publication-lock.txt"
    lock_hash = _write_lock(lock)

    with pytest.raises(EnvironmentVerificationError, match=message):
        verify_environment(
            lock,
            repo_root=tmp_path,
            expected_lock_sha256=lock_hash,
            python_version=(3, 12, 7),
            python_prefix=str(tmp_path / "venv"),
            python_base_prefix=str(tmp_path / "base"),
            python_implementation="CPython",
            platform_system="Darwin",
            platform_machine="arm64",
            installed_distributions=records,
            pip_checker=lambda: "pass",
        )


def test_external_distribution_cannot_masquerade_as_repo_metadata(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "requirements-publication-lock.txt"
    lock_hash = _write_lock(lock)
    records = (
        _external(tmp_path),
        DistributionRecord(
            name="toolsandbox-sage",
            version="0.1.0",
            metadata_path=tmp_path
            / "foreign-site-packages"
            / "toolsandbox_sage.dist-info",
        ),
    )

    with pytest.raises(
        EnvironmentVerificationError, match="unexpected external distributions"
    ):
        verify_environment(
            lock,
            repo_root=tmp_path / "repo",
            expected_lock_sha256=lock_hash,
            python_version=(3, 12, 7),
            python_prefix=str(tmp_path / "venv"),
            python_base_prefix=str(tmp_path / "base"),
            python_implementation="CPython",
            platform_system="Darwin",
            platform_machine="arm64",
            installed_distributions=records,
            pip_checker=lambda: "pass",
        )


def test_verifier_fails_closed_when_pip_check_fails(tmp_path: Path) -> None:
    lock = tmp_path / "requirements-publication-lock.txt"
    lock_hash = _write_lock(lock)

    def fail_pip_check() -> str:
        raise EnvironmentVerificationError("pip dependency check failed: broken")

    with pytest.raises(EnvironmentVerificationError, match="dependency check failed"):
        verify_environment(
            lock,
            repo_root=tmp_path,
            expected_lock_sha256=lock_hash,
            python_version=(3, 12, 7),
            python_prefix=str(tmp_path / "venv"),
            python_base_prefix=str(tmp_path / "base"),
            python_implementation="CPython",
            platform_system="Darwin",
            platform_machine="arm64",
            installed_distributions=(
                _external(tmp_path),
                _editable_project(tmp_path, tmp_path / "site-packages"),
            ),
            pip_checker=fail_pip_check,
        )


def test_pip_check_nonzero_exit_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: object, **kwargs: object) -> object:
        return subprocess.CompletedProcess(
            args=["python", "-m", "pip", "check"],
            returncode=1,
            stdout="broken requirement\n",
            stderr="",
        )

    monkeypatch.setattr(
        "scripts.verify_publication_environment.subprocess.run",
        fake_run,
    )

    with pytest.raises(EnvironmentVerificationError, match="broken requirement"):
        environment_verifier._run_pip_check()


def test_publication_launcher_binds_environment_and_git_provenance() -> None:
    launcher = (
        environment_verifier.REPO_ROOT / "scripts/run_native_action_4omini_ab.sh"
    ).read_text(encoding="utf-8")

    assert "scripts/verify_publication_environment.py" in launcher
    assert launcher.index('export PYTHONPATH="src:."') < launcher.index(
        "scripts/verify_publication_environment.py"
    )
    assert "git status --porcelain --untracked-files=all" in launcher
    assert '"$PYTHON_EXECUTABLE" scripts/run_sage_protocol.py' in launcher
    assert '"$PYTHON_EXECUTABLE" scripts/verify_publication_run.py' in launcher
    assert "--actor-selection-mode policy" in launcher
    assert "--inventory-authority-capture-dir" in launcher
    assert '"$PYTHON_EXECUTABLE" scripts/run_sage_auto_selection_replay.py' in launcher
    assert '--cohort "$SIZE"' in launcher
    assert "--expected-benchmark-sha256" not in launcher
    assert "--expected-scenario-order-sha256" not in launcher
    assert "SAGE_AUTO_SELECTION_PILOT_EVIDENCE" in launcher
    assert "--selector-pilot-evidence" in launcher
    assert (
        'AUTO_REPLAY_CMD+=(--pilot-evidence "$SELECTOR_PILOT_EVIDENCE_PATH")'
        in launcher
    )
    root_guard_index = launcher.index(
        "Publication $root_label root must not already exist"
    )
    assert root_guard_index < launcher.index('mkdir -p "$ARM_ARTIFACTS"')
    assert launcher.index("--selector-pilot-evidence") < launcher.index(
        'mkdir -p "$ARM_ARTIFACTS"'
    )
    for provenance_field in (
        "python_executable=",
        "python_version=",
        "environment_lock_sha256=",
        "external_distribution_count=",
        "external_distribution_sha256=",
        "git_commit=",
        "git_tree=",
        "git_status=clean",
        "openai_max_retries=",
        "openai_transient_retry_delays_seconds=",
        "generation_transient_retry_delays_seconds=",
        "transient_scenario_retry_attempts=",
        "openai_request_timeout_seconds=",
        "generation_openai_request_timeout_seconds=",
    ):
        assert provenance_field in launcher
    assert 'pin_publication_env SAGE_OPENAI_MAX_RETRIES "5"' in launcher
    assert (
        'pin_publication_env SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS "1,3"'
        in launcher
    )
    assert (
        'pin_publication_env SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS "1,3"'
        in launcher
    )
    assert (
        'pin_publication_env SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS "4"' in launcher
    )
    assert (
        "generator_contract_and_repair_analysis_memoization=within_run_only" in launcher
    )
    assert "openai_provider_prompt_prefix_cache=automatic_implicit" in launcher
    assert "Publication runs forbid active diagnostic force variable" in launcher
    for env_name in (
        "SAGE_DIAGNOSTIC_EXPOSE_TOOL_NAME",
        "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME",
        "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR",
        "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL",
    ):
        assert env_name in launcher


def test_publication_run_verifier_cli_uses_only_internal_cohort_pins() -> None:
    verifier = (
        environment_verifier.REPO_ROOT / "scripts/verify_publication_run.py"
    ).read_text(encoding="utf-8")

    assert '"--cohort"' in verifier
    assert '"--selector-pilot-evidence"' in verifier
    assert '"--expected-tasks"' not in verifier
    assert '"--expected-benchmark-sha256"' not in verifier
    assert '"--expected-scenario-order-sha256"' not in verifier


def test_publication_bootstrap_does_not_install_development_extras() -> None:
    bootstrap = (environment_verifier.REPO_ROOT / "scripts/bootstrap_env.sh").read_text(
        encoding="utf-8"
    )

    assert "python3.12" in bootstrap
    assert " -m venv " in bootstrap
    assert '--no-deps --editable "$ROOT_DIR"' in bootstrap
    assert ".[dev" not in bootstrap
    assert "pre-commit" not in bootstrap
    assert "conda" not in bootstrap
