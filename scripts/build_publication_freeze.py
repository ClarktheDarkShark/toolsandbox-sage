#!/usr/bin/env python3
"""Build and verify the immutable Chapter 4 publication provenance bundle.

This utility is intentionally independent of the experiment runner.  It never
executes a benchmark, mutates a registry, or writes to a legacy artifact.  New
files are written only below ``artifacts/publication_cleanup_20260901`` and an
existing file is accepted only when its bytes already equal the deterministic
payload that would be written.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = 1
PUBLICATION_MANIFEST_NAME = "publication_manifest.json"
PUBLICATION_SIDECAR_NAME = "publication_manifest.sha256"
DEFAULT_BUNDLE_ROOT = Path("artifacts/publication_cleanup_20260901")
DEFAULT_CAMPAIGN_MANIFEST = Path(
    "artifacts/chapter4_evidence/"
    "chapter4_final_claim_10x_20260730/campaign_manifest.json"
)
DEFAULT_BENCHMARK = Path(
    "docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json"
)
DEFAULT_LEGACY_BASELINE = Path(
    "artifacts/baselines/control_task_baselines_v140_prefinal_full_uncached_gpt4omini"
)
DEFAULT_RAPID_FIXTURE = Path(".secrets/rapid_api_cache.json")
EXPECTED_TASK_COUNT = 1032
EXPECTED_REPLICATIONS = 10
HASH_ALGORITHM = "sha256"
DIRECTORY_DIGEST_ALGORITHM = (
    "sha256(canonical-json(sorted([{path,type,size,sha256|target}])))"
)

STATIC_ANALYSIS_INPUTS = (
    Path("scripts/run_chapter4_evidence_campaign.py"),
    Path("scripts/build_chapter4_evidence_dashboard.py"),
    Path("scripts/research/chapter4_evidence.py"),
    Path("scripts/research/chapter4_evidence_template.html"),
    Path("scripts/render_chapter4_evidence_tables.py"),
    Path("docs/sage_protocol/chapter4_4omini_data_collection_plan.md"),
    Path("docs/sage_protocol/chapter4_results_completed.tex"),
)

DERIVED_ANALYSIS_OUTPUTS = (
    Path(
        "outputs/chapter4_evidence/chapter4_final_claim_10x_20260730/"
        "dashboard/chapter4_evidence_data.json"
    ),
    Path(
        "outputs/chapter4_evidence/chapter4_final_claim_10x_20260730/"
        "dashboard/chapter4_evidence.html"
    ),
)

ANALYSIS_RUN_FILES = (
    Path("paired_comparison.json"),
    Path("dashboard/task_compare_data.json"),
    Path("protocol_manifest.json"),
    Path("helper_contribution_summary.json"),
)

SAFE_ENVIRONMENT_KEYS = (
    "CONDA_DEFAULT_ENV",
    "CONDA_PREFIX",
    "LANG",
    "LC_ALL",
    "PYTHONHASHSEED",
    "TZ",
    "TOOLSANDBOX_RAPID_CACHE_MODE",
    "TOOLSANDBOX_RAPID_CACHE_PATH",
)

_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE_REQUEST_KEY = re.compile(
    r"(^|[_-])(api[_-]?key|authorization|auth|bearer|cookie|password|secret|token)($|[_-])",
    re.IGNORECASE,
)
_SENSITIVE_SERIALIZED_VALUE = re.compile(
    r"x-rapidapi-key|authorization\s*[:=]|bearer\s+[a-z0-9._~-]|\bsk-[a-z0-9_-]{12,}",
    re.IGNORECASE,
)


class FreezeError(RuntimeError):
    """Raised when a publication-freeze invariant is not satisfied."""


def canonical_json_bytes(payload: Any, *, pretty: bool = False) -> bytes:
    """Return deterministic UTF-8 JSON bytes with a trailing newline."""

    if pretty:
        text = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
    else:
        text = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    return (text + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise FreezeError(f"Path is outside the repository: {path}") from exc


def _resolve_repo_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def file_record(repo_root: Path, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FreezeError(f"Required file is missing: {path}")
    return {
        "path": _repo_relative(repo_root, path),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _directory_entry(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    if path.is_symlink():
        return {
            "path": relative,
            "type": "symlink",
            "target": os.readlink(path),
        }
    if path.is_file():
        return {
            "path": relative,
            "type": "file",
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    raise FreezeError(f"Unsupported directory entry: {path}")


def directory_inventory(repo_root: Path, root: Path) -> dict[str, Any]:
    """Hash every regular file and symlink below *root* deterministically."""

    if not root.is_dir():
        raise FreezeError(f"Required directory is missing: {root}")
    paths = sorted(
        (path for path in root.rglob("*") if path.is_file() or path.is_symlink()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    entries = [_directory_entry(path, root) for path in paths]
    return {
        "path": _repo_relative(repo_root, root),
        "file_count": sum(entry["type"] == "file" for entry in entries),
        "symlink_count": sum(entry["type"] == "symlink" for entry in entries),
        "total_file_bytes": sum(int(entry.get("size") or 0) for entry in entries),
        "directory_sha256": sha256_bytes(canonical_json_bytes(entries)),
        "digest_algorithm": DIRECTORY_DIGEST_ALGORITHM,
        "files": entries,
    }


def tar_inventory(repo_root: Path, archive: Path) -> dict[str, Any]:
    """Return both the exact archive hash and a logical per-member inventory."""

    members: list[dict[str, Any]] = []
    seen: set[str] = set()
    with tarfile.open(archive, "r:gz") as handle:
        for member in sorted(handle.getmembers(), key=lambda item: item.name):
            if member.name in seen:
                raise FreezeError(
                    f"Checkpoint archive contains duplicate member {member.name!r}"
                )
            seen.add(member.name)
            if member.isdir():
                members.append({"path": member.name, "type": "directory"})
            elif member.isfile():
                extracted = handle.extractfile(member)
                if extracted is None:
                    raise FreezeError(f"Cannot read tar member {member.name!r}")
                digest = hashlib.sha256()
                size = 0
                for chunk in iter(lambda: extracted.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
                if size != member.size:
                    raise FreezeError(f"Tar size mismatch for {member.name!r}")
                members.append(
                    {
                        "path": member.name,
                        "type": "file",
                        "size": size,
                        "sha256": digest.hexdigest(),
                    }
                )
            elif member.issym():
                members.append(
                    {
                        "path": member.name,
                        "type": "symlink",
                        "target": member.linkname,
                    }
                )
            elif member.islnk():
                members.append(
                    {
                        "path": member.name,
                        "type": "hardlink",
                        "target": member.linkname,
                    }
                )
            else:
                raise FreezeError(f"Unsupported tar member type for {member.name!r}")
    return {
        **file_record(repo_root, archive),
        "member_count": len(members),
        "logical_content_sha256": sha256_bytes(canonical_json_bytes(members)),
        "logical_digest_algorithm": DIRECTORY_DIGEST_ALGORITHM,
        "members": members,
    }


def tar_member_bytes(archive: Path, member_name: str) -> bytes:
    """Read one regular file from a checkpoint tar without extracting it."""

    with tarfile.open(archive, "r:gz") as handle:
        try:
            member = handle.getmember(member_name)
        except KeyError as exc:
            raise FreezeError(
                f"Checkpoint archive does not contain {member_name!r}"
            ) from exc
        if not member.isfile():
            raise FreezeError(
                f"Checkpoint archive member is not a file: {member_name!r}"
            )
        extracted = handle.extractfile(member)
        if extracted is None:
            raise FreezeError(f"Cannot read checkpoint member {member_name!r}")
        payload = extracted.read()
    if len(payload) != member.size:
        raise FreezeError(f"Checkpoint member size mismatch: {member_name!r}")
    return payload


def immutable_write(path: Path, payload: bytes) -> None:
    """Write a new file, or prove an existing file already has exact bytes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file() or path.read_bytes() != payload:
            raise FreezeError(
                f"Immutable publication artifact already exists with different bytes: {path}"
            )
        return
    with path.open("xb") as handle:
        handle.write(payload)


def immutable_copy(source: Path, destination: Path) -> None:
    immutable_write(destination, source.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FreezeError(f"Expected JSON object: {path}")
    return payload


def benchmark_names(path: Path) -> list[str]:
    payload = _load_json(path)
    split = payload.get("splits", {}).get("full_benchmark")
    if not isinstance(split, list):
        raise FreezeError("Benchmark has no full_benchmark list")
    names = [str(item.get("name") or "") for item in split if isinstance(item, dict)]
    if len(names) != EXPECTED_TASK_COUNT or len(set(names)) != EXPECTED_TASK_COUNT:
        raise FreezeError(
            f"Expected {EXPECTED_TASK_COUNT} unique benchmark tasks, found "
            f"{len(names)} entries and {len(set(names))} unique names"
        )
    if any(not name for name in names):
        raise FreezeError("Benchmark contains an empty scenario name")
    return names


def _read_jsonl_with_raw(path: Path) -> list[tuple[dict[str, Any], bytes]]:
    rows: list[tuple[dict[str, Any], bytes]] = []
    with path.open("rb") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise FreezeError(f"Invalid JSONL at {path}:{line_number}") from exc
            if not isinstance(payload, dict):
                raise FreezeError(f"Non-object JSONL record at {path}:{line_number}")
            rows.append((payload, raw))
    return rows


def original_v140_snapshot_bytes(
    *, legacy_cache_root: Path, benchmark: Path
) -> tuple[bytes, dict[str, Any]]:
    """Extract exactly the uncontaminated original-v140 task records.

    The output is ordered by the committed benchmark and uses canonical JSONL.
    It is deliberately not laid out as a runnable ControlBaselineCache.
    """

    source_report_path = legacy_cache_root / "v140_source_report.json"
    records_path = legacy_cache_root / "compact_records.jsonl"
    source_report = _load_json(source_report_path)
    source_control_dir = str(source_report.get("source_control_dir") or "")
    if not source_control_dir:
        raise FreezeError("v140 source report has no source_control_dir")
    selected: dict[str, dict[str, Any]] = {}
    total_records = 0
    for row, _raw in _read_jsonl_with_raw(records_path):
        total_records += 1
        if str(row.get("run_dir") or "") != source_control_dir:
            continue
        scenario = str(row.get("scenario_key") or "")
        if not scenario or scenario in selected:
            raise FreezeError(
                f"Original-v140 selection has empty or duplicate scenario {scenario!r}"
            )
        if not bool(row.get("valid_for_cache")) or not bool(row.get("complete_run")):
            raise FreezeError(f"Original-v140 record is not complete/valid: {scenario}")
        selected[scenario] = row

    names = benchmark_names(benchmark)
    missing = sorted(set(names) - set(selected))
    unexpected = sorted(set(selected) - set(names))
    if missing or unexpected or len(selected) != EXPECTED_TASK_COUNT:
        raise FreezeError(
            "Original-v140 records do not exactly cover the benchmark: "
            f"missing={missing[:5]}, unexpected={unexpected[:5]}, "
            f"selected={len(selected)}"
        )
    ordered = [selected[name] for name in names]
    output = b"".join(canonical_json_bytes(row) for row in ordered)
    scored = [
        float(row["outcome_score"])
        for row in ordered
        if row.get("outcome_score") is not None
    ]
    metadata = {
        "usage": "historical_sensitivity_reference_only",
        "eligible_for_new_experiment_runs": False,
        "warning": (
            "This immutable 1,032-record snapshot is not the baseline used by "
            "the final campaign and must not be passed to --control-cache-root."
        ),
        "legacy_cache_source": records_path.as_posix(),
        "legacy_cache_total_records_at_freeze": total_records,
        "source_control_dir": source_control_dir,
        "source_run_root": str(source_report.get("source_run_root") or ""),
        "record_count": len(ordered),
        "unique_scenario_count": len(selected),
        "outcome_scored_record_count": len(scored),
        "canonical_score_mean": sum(float(row["canonical_score"]) for row in ordered)
        / len(ordered),
        "outcome_score_mean": sum(scored) / len(scored),
        "snapshot_sha256": sha256_bytes(output),
    }
    return output, metadata


def _walk_request_keys(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if _SENSITIVE_REQUEST_KEY.search(key_text):
                raise FreezeError(
                    "RapidAPI request fixture contains a sensitive key at "
                    + ".".join(path + (key_text,))
                )
            _walk_request_keys(item, path + (key_text,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_request_keys(item, path + (str(index),))


def sanitized_rapid_fixture_bytes(source: Path) -> tuple[bytes, dict[str, Any]]:
    payload = _load_json(source)
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        raise FreezeError("RapidAPI fixture has no entries object")
    sanitized: dict[str, Any] = {}
    hosts: set[str] = set()
    for key in sorted(entries):
        if not _HEX_SHA256.fullmatch(str(key)):
            raise FreezeError(f"Invalid RapidAPI cache key: {key!r}")
        entry = entries[key]
        if not isinstance(entry, dict):
            raise FreezeError(f"RapidAPI entry {key} is not an object")
        request = entry.get("request")
        response = entry.get("response")
        if not isinstance(request, dict) or not isinstance(response, dict):
            raise FreezeError(f"RapidAPI entry {key} lacks request/response objects")
        if set(request) != {"host", "params", "url"}:
            raise FreezeError(
                f"RapidAPI request {key} has unexpected fields {sorted(request)}"
            )
        clean_request = {
            "host": str(request["host"]),
            "params": request["params"],
            "url": str(request["url"]),
        }
        _walk_request_keys(clean_request.get("params"), ("params",))
        parsed = urllib.parse.urlsplit(clean_request["url"])
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise FreezeError(f"RapidAPI request {key} has an unsafe URL")
        expected_key = sha256_bytes(
            json.dumps(
                clean_request,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        )
        if expected_key != key:
            raise FreezeError(
                f"RapidAPI request hash mismatch: stored={key}, expected={expected_key}"
            )
        hosts.add(clean_request["host"])
        sanitized[key] = {"request": clean_request, "response": response}
    output = canonical_json_bytes({"entries": sanitized}, pretty=True)
    if _SENSITIVE_SERIALIZED_VALUE.search(output.decode("utf-8")):
        raise FreezeError("Sanitized RapidAPI fixture still matches a secret pattern")
    metadata = {
        "entry_count": len(sanitized),
        "host_count": len(hosts),
        "hosts": sorted(hosts),
        "request_fields_allowlist": ["host", "params", "url"],
        "request_cache_keys_revalidated": len(sanitized),
        "contains_api_credentials": False,
        "required_mode": "read_only",
        "sanitized_fixture_sha256": sha256_bytes(output),
    }
    return output, metadata


def _subprocess_output(command: Sequence[str], *, cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ):
        return None
    return completed.stdout


def _installed_distributions() -> list[dict[str, str]]:
    packages: dict[tuple[str, str], dict[str, str]] = {}
    for distribution in importlib.metadata.distributions():
        name = str(distribution.metadata.get("Name") or "").strip()
        version = str(distribution.version or "").strip()
        if not name:
            continue
        key = (name.casefold(), version)
        packages[key] = {"name": name, "version": version}
    return [packages[key] for key in sorted(packages)]


def capture_environment(repo_root: Path) -> tuple[bytes, bytes, bytes | None]:
    distributions = _installed_distributions()
    declaration_paths = [repo_root / "pyproject.toml", repo_root / "environment.yml"]
    payload = {
        "capture_scope": (
            "current_publication_cleanup_host; historical campaign package state "
            "was not recorded and cannot be reconstructed from this capture"
        ),
        "python": {
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "version_detail": sys.version,
            "compiler": platform.python_compiler(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "mac_ver": platform.mac_ver()[0],
        },
        "safe_environment": {key: os.environ.get(key) for key in SAFE_ENVIRONMENT_KEYS},
        "installed_distributions": distributions,
        "source_environment_declarations": [
            file_record(repo_root, path) for path in declaration_paths if path.exists()
        ],
        "git_version": (
            _subprocess_output(["git", "--version"], cwd=repo_root) or ""
        ).strip(),
    }
    pip_lines = [f"{item['name']}=={item['version']}" for item in distributions]
    pip_bytes = ("\n".join(pip_lines) + "\n").encode("utf-8")
    conda_output = None
    conda = shutil.which("conda")
    if conda:
        conda_output = _subprocess_output([conda, "list", "--explicit"], cwd=repo_root)
    conda_bytes = conda_output.encode("utf-8") if conda_output else None
    return canonical_json_bytes(payload, pretty=True), pip_bytes, conda_bytes


def git_checkpoint(repo_root: Path, commit: str) -> dict[str, Any]:
    resolved = _subprocess_output(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=repo_root
    )
    if not resolved:
        raise FreezeError(f"Cannot resolve checkpoint commit {commit!r}")
    commit_hash = resolved.strip()
    tree = (
        _subprocess_output(
            ["git", "rev-parse", f"{commit_hash}^{{tree}}"], cwd=repo_root
        )
        or ""
    ).strip()
    parents = (
        (
            _subprocess_output(
                ["git", "show", "-s", "--format=%P", commit_hash], cwd=repo_root
            )
            or ""
        )
        .strip()
        .split()
    )
    subject = (
        _subprocess_output(
            ["git", "show", "-s", "--format=%s", commit_hash], cwd=repo_root
        )
        or ""
    ).strip()
    if not tree:
        raise FreezeError(f"Cannot resolve checkpoint tree for {commit_hash}")
    return {
        "commit": commit_hash,
        "tree": tree,
        "parents": parents,
        "subject": subject,
    }


def registry_inventory(
    *, repo_root: Path, campaign_manifest: dict[str, Any]
) -> dict[str, Any]:
    pairs = campaign_manifest.get("run_pairs")
    if not isinstance(pairs, list) or len(pairs) != EXPECTED_REPLICATIONS:
        raise FreezeError(
            f"Expected {EXPECTED_REPLICATIONS} campaign run pairs, found "
            f"{len(pairs) if isinstance(pairs, list) else 'invalid'}"
        )
    output: list[dict[str, Any]] = []
    for pair in pairs:
        replication = int(pair.get("replication") or 0)
        online_entry = pair.get("online") or {}
        frozen_entry = pair.get("frozen") or {}
        online_dir = _resolve_repo_path(
            repo_root, str(online_entry.get("registry_dir") or "")
        )
        frozen_run_root = _resolve_repo_path(
            repo_root, str(frozen_entry.get("run_root") or "")
        )
        protocol_path = frozen_run_root / "protocol_manifest.json"
        protocol = _load_json(protocol_path)
        frozen_dir = _resolve_repo_path(
            repo_root,
            str(protocol.get("registry_dir") or frozen_entry.get("registry_dir") or ""),
        )
        declared_frozen_dir = _resolve_repo_path(
            repo_root, str(frozen_entry.get("registry_dir") or "")
        )
        online_inventory = directory_inventory(repo_root, online_dir)
        frozen_inventory = directory_inventory(repo_root, frozen_dir)
        online_manifest = online_dir / "registry_manifest.json"
        frozen_manifest = frozen_dir / "registry_manifest.json"
        online_manifest_hash = sha256_file(online_manifest)
        frozen_manifest_hash = sha256_file(frozen_manifest)
        if online_manifest_hash != frozen_manifest_hash:
            raise FreezeError(
                f"Replication {replication} online/frozen registry manifests differ"
            )
        manifest_payload = _load_json(online_manifest)
        tools = manifest_payload.get("tools") or {}
        tool_count = len(tools) if isinstance(tools, (dict, list)) else 0
        output.append(
            {
                "replication": replication,
                "completed_online_run_root": str(online_entry.get("run_root") or ""),
                "completed_frozen_run_root": str(frozen_entry.get("run_root") or ""),
                "online_registry": online_inventory,
                "frozen_registry": frozen_inventory,
                "campaign_declared_frozen_registry": _repo_relative(
                    repo_root, declared_frozen_dir
                ),
                "actual_frozen_registry_from_protocol": _repo_relative(
                    repo_root, frozen_dir
                ),
                "actual_differs_from_campaign_declared": (
                    frozen_dir.resolve() != declared_frozen_dir.resolve()
                ),
                "paired_registry_manifest_sha256": online_manifest_hash,
                "paired_registry_manifests_byte_identical": True,
                "tool_count": tool_count,
            }
        )
    if [item["replication"] for item in output] != list(
        range(1, EXPECTED_REPLICATIONS + 1)
    ):
        raise FreezeError("Campaign replications are not ordered 1 through 10")
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": (
            "Per-file immutable hashes for both the online source registry and "
            "the actual registry directory used by each completed frozen run."
        ),
        "replication_count": len(output),
        "directory_digest_algorithm": DIRECTORY_DIGEST_ALGORITHM,
        "pairs": output,
    }


def analysis_inventory(
    *,
    repo_root: Path,
    campaign_manifest_path: Path,
    campaign_manifest: dict[str, Any],
    frozen_static_inputs: Sequence[tuple[Path, Path]],
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for pair in campaign_manifest.get("run_pairs") or []:
        replication = int(pair.get("replication") or 0)
        for arm in ("online", "frozen"):
            entry = pair.get(arm) or {}
            run_root = _resolve_repo_path(repo_root, str(entry.get("run_root") or ""))
            files = [
                file_record(repo_root, run_root / relative)
                for relative in ANALYSIS_RUN_FILES
            ]
            runs.append(
                {
                    "replication": replication,
                    "arm": arm,
                    "run_root": _repo_relative(repo_root, run_root),
                    "files": files,
                }
            )
    if len(runs) != EXPECTED_REPLICATIONS * 2:
        raise FreezeError(f"Expected 20 analysis run entries, found {len(runs)}")
    artifact_roots = (
        repo_root
        / "artifacts/chapter4_current_sage_replications/current_sage_rep5_20260723_220047",
        repo_root / "artifacts/chapter4_evidence/chapter4_final_claim_10x_20260730",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_manifest": file_record(repo_root, campaign_manifest_path),
        "static_analysis_inputs": [
            {
                "historical_source_path": source.as_posix(),
                "frozen_copy": file_record(repo_root, frozen_copy),
                "source_worktree_may_change_after_freeze": True,
            }
            for source, frozen_copy in frozen_static_inputs
        ],
        "derived_analysis_outputs": [
            file_record(repo_root, repo_root / path)
            for path in DERIVED_ANALYSIS_OUTPUTS
        ],
        "run_inputs": runs,
        "campaign_artifact_directories": [
            directory_inventory(repo_root, root) for root in artifact_roots
        ],
    }


def _copy_small_inputs(
    repo_root: Path,
    bundle_root: Path,
    checkpoint_archive: Path,
) -> tuple[list[Path], list[tuple[Path, Path]]]:
    copies = [
        (
            repo_root / DEFAULT_BENCHMARK,
            bundle_root / "inputs" / DEFAULT_BENCHMARK.name,
        ),
        (
            repo_root / DEFAULT_CAMPAIGN_MANIFEST,
            bundle_root / "analysis" / "campaign_manifest.json",
        ),
        (
            repo_root / DERIVED_ANALYSIS_OUTPUTS[0],
            bundle_root / "analysis" / "chapter4_evidence_data.json",
        ),
        (
            repo_root / DERIVED_ANALYSIS_OUTPUTS[1],
            bundle_root / "analysis" / "chapter4_evidence.html",
        ),
    ]
    destinations: list[Path] = []
    for source, destination in copies:
        immutable_copy(source, destination)
        destinations.append(destination)
    frozen_static_inputs: list[tuple[Path, Path]] = []
    for relative in STATIC_ANALYSIS_INPUTS:
        destination = bundle_root / "analysis" / "checkpoint_source" / relative
        immutable_write(
            destination, tar_member_bytes(checkpoint_archive, relative.as_posix())
        )
        destinations.append(destination)
        frozen_static_inputs.append((relative, destination))
    return destinations, frozen_static_inputs


def _all_bundle_files(bundle_root: Path) -> Iterable[Path]:
    for path in sorted(bundle_root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        if path.name.startswith("publication_freeze_manifest") or path.name.startswith(
            "publication_manifest"
        ):
            continue
        yield path


def build(args: argparse.Namespace) -> Path:
    repo_root = args.repo_root.resolve()
    bundle_root = _resolve_repo_path(repo_root, args.bundle_root).resolve()
    expected_bundle = (repo_root / DEFAULT_BUNDLE_ROOT).resolve()
    if bundle_root != expected_bundle:
        raise FreezeError(
            f"Publication output is restricted to {expected_bundle}; found {bundle_root}"
        )
    campaign_path = repo_root / DEFAULT_CAMPAIGN_MANIFEST
    benchmark_path = repo_root / DEFAULT_BENCHMARK
    legacy_baseline = repo_root / DEFAULT_LEGACY_BASELINE
    rapid_source = repo_root / DEFAULT_RAPID_FIXTURE
    campaign = _load_json(campaign_path)

    print("freeze: checkpoint inventory")
    checkpoint_archive = bundle_root / "checkpoints" / "pre_p0_r1_source.tar.gz"
    checkpoint_patch = bundle_root / "checkpoints" / "pre_p0_r1_tracked.patch"
    checkpoint_untracked = bundle_root / "checkpoints" / "pre_p0_r1_untracked_files.txt"
    checkpoint = git_checkpoint(repo_root, args.checkpoint_commit)
    checkpoint["source_archive"] = tar_inventory(repo_root, checkpoint_archive)
    checkpoint["tracked_patch"] = file_record(repo_root, checkpoint_patch)
    checkpoint["untracked_file_list"] = file_record(repo_root, checkpoint_untracked)

    print("freeze: benchmark and original-v140 reference")
    names = benchmark_names(benchmark_path)
    copied_paths, frozen_static_inputs = _copy_small_inputs(
        repo_root,
        bundle_root,
        checkpoint_archive,
    )
    snapshot_bytes, baseline_metadata = original_v140_snapshot_bytes(
        legacy_cache_root=legacy_baseline,
        benchmark=benchmark_path,
    )
    baseline_snapshot = (
        bundle_root / "baseline" / "original_v140_reference_records.jsonl"
    )
    baseline_source_report = (
        bundle_root / "baseline" / "original_v140_source_report.json"
    )
    baseline_metadata_path = (
        bundle_root / "baseline" / "original_v140_reference_metadata.json"
    )
    immutable_write(baseline_snapshot, snapshot_bytes)
    immutable_copy(legacy_baseline / "v140_source_report.json", baseline_source_report)
    baseline_metadata.update(
        {
            "snapshot_path": _repo_relative(repo_root, baseline_snapshot),
            "legacy_cache_content_at_freeze": {
                "compact_records": file_record(
                    repo_root, legacy_baseline / "compact_records.jsonl"
                ),
                "index": file_record(repo_root, legacy_baseline / "index.jsonl"),
                "cache_manifest": file_record(
                    repo_root, legacy_baseline / "cache_manifest.json"
                ),
                "source_report": file_record(
                    repo_root, legacy_baseline / "v140_source_report.json"
                ),
            },
        }
    )
    immutable_write(
        baseline_metadata_path, canonical_json_bytes(baseline_metadata, pretty=True)
    )

    print("freeze: RapidAPI fixture and current environment")
    rapid_bytes, rapid_metadata = sanitized_rapid_fixture_bytes(rapid_source)
    rapid_destination = bundle_root / "fixtures" / "rapid_api_cache.sanitized.json"
    immutable_write(rapid_destination, rapid_bytes)
    environment_bytes, packages_bytes, conda_bytes = capture_environment(repo_root)
    environment_path = bundle_root / "environment" / "environment.json"
    packages_path = bundle_root / "environment" / "python_packages.txt"
    immutable_write(environment_path, environment_bytes)
    immutable_write(packages_path, packages_bytes)
    environment_files = [environment_path, packages_path]
    if conda_bytes is not None:
        conda_path = bundle_root / "environment" / "conda_explicit.txt"
        immutable_write(conda_path, conda_bytes)
        environment_files.append(conda_path)

    print("freeze: paired registry inventories")
    registry_payload = registry_inventory(
        repo_root=repo_root,
        campaign_manifest=campaign,
    )
    registry_path = bundle_root / "registries" / "registry_inventory.json"
    immutable_write(registry_path, canonical_json_bytes(registry_payload, pretty=True))

    print("freeze: final analysis and campaign inventories")
    analysis_payload = analysis_inventory(
        repo_root=repo_root,
        campaign_manifest_path=campaign_path,
        campaign_manifest=campaign,
        frozen_static_inputs=frozen_static_inputs,
    )
    analysis_path = (
        bundle_root / "analysis" / "publication_analysis_inputs_inventory.json"
    )
    immutable_write(analysis_path, canonical_json_bytes(analysis_payload, pretty=True))

    builder_path = repo_root / "scripts" / "build_publication_freeze.py"
    builder_test_path = repo_root / "tests" / "unit" / "test_publication_freeze.py"
    frozen_builder_path = bundle_root / "machinery" / builder_path.name
    frozen_builder_test_path = bundle_root / "machinery" / builder_test_path.name
    immutable_copy(builder_path, frozen_builder_path)
    immutable_copy(builder_test_path, frozen_builder_test_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "revision": 2,
        "bundle_id": "publication_cleanup_20260901",
        "purpose": (
            "Immutable, content-addressed provenance for the Chapter 4 final "
            "10-online/10-frozen evidence campaign. No experiment was executed."
        ),
        "hash_algorithm": HASH_ALGORITHM,
        "directory_digest_algorithm": DIRECTORY_DIGEST_ALGORITHM,
        "immutability_policy": {
            "legacy_artifacts_mutated": False,
            "existing_bundle_files_overwritten": False,
            "write_scope": _repo_relative(repo_root, bundle_root),
            "build_behavior": (
                "create absent files; require byte equality for any existing file"
            ),
        },
        "builder": {
            "historical_source_path": _repo_relative(repo_root, builder_path),
            "frozen_copy": file_record(repo_root, frozen_builder_path),
            "focused_test": file_record(repo_root, frozen_builder_test_path),
        },
        "checkpoint": checkpoint,
        "benchmark": {
            **file_record(repo_root, benchmark_path),
            "copied_path": _repo_relative(
                repo_root, bundle_root / "inputs" / benchmark_path.name
            ),
            "task_count": len(names),
            "unique_task_count": len(set(names)),
            "ordered_task_names_sha256": sha256_bytes(
                ("\n".join(names) + "\n").encode("utf-8")
            ),
            "first_task": names[0],
            "last_task": names[-1],
        },
        "historical_original_v140_reference": baseline_metadata,
        "paired_registries": {
            "inventory": file_record(repo_root, registry_path),
            "replication_count": registry_payload["replication_count"],
            "online_directories_copied": False,
            "frozen_directories_copied": False,
            "reason_not_copied": (
                "Source directories remain preserved; deterministic per-file "
                "hash inventories pin every directory byte without duplication."
            ),
        },
        "rapidapi_fixture": {
            **rapid_metadata,
            "source": file_record(repo_root, rapid_source),
            "sanitized_copy": file_record(repo_root, rapid_destination),
            "original_campaign_recorded_fixture_hash": False,
        },
        "environment": {
            "capture_scope": "current cleanup host, not historical run host",
            "files": [file_record(repo_root, path) for path in environment_files],
        },
        "analysis": {
            "inventory": file_record(repo_root, analysis_path),
            "run_count": len(analysis_payload["run_inputs"]),
            "small_exact_copies": [
                file_record(repo_root, path) for path in copied_paths
            ],
            "large_run_inputs_copied": False,
        },
        "limitations": [
            (
                "The historical study used live, unseeded gpt-4o-mini calls; "
                "identical online or frozen rerun scores are not guaranteed."
            ),
            (
                "The study manifests record three dirty-tree hashes, but the "
                "original launcher and those exact dirty trees are unavailable."
            ),
            (
                "The environment capture describes the cleanup host, because "
                "the historical campaign did not save a package lock or freeze."
            ),
            (
                "The sanitized RapidAPI fixture is the current preserved fixture; "
                "the original campaign did not record its fixture hash or path."
            ),
            (
                "The pure original-v140 snapshot is historical sensitivity data "
                "only. The final campaign used the then-expanded 1,182-record cache."
            ),
            (
                "Large registries and analysis inputs are content-inventoried in "
                "place, not duplicated into this publication bundle."
            ),
        ],
        "supersedes": (
            "publication_freeze_manifest.json, an initial local build whose "
            "verification incorrectly required actively cleaned source files "
            "to remain unchanged; it is retained rather than overwritten."
        ),
    }
    manifest["bundle_files"] = [
        file_record(repo_root, path) for path in _all_bundle_files(bundle_root)
    ]
    manifest_path = bundle_root / PUBLICATION_MANIFEST_NAME
    manifest_bytes = canonical_json_bytes(manifest, pretty=True)
    immutable_write(manifest_path, manifest_bytes)
    sidecar = bundle_root / PUBLICATION_SIDECAR_NAME
    immutable_write(
        sidecar,
        f"{sha256_bytes(manifest_bytes)}  {manifest_path.name}\n".encode("ascii"),
    )
    print(f"freeze: manifest {manifest_path}")
    print(f"freeze: manifest_sha256 {sha256_bytes(manifest_bytes)}")
    return manifest_path


def _assert_file_record(repo_root: Path, record: dict[str, Any]) -> None:
    path = repo_root / str(record["path"])
    actual = file_record(repo_root, path)
    expected = {key: record[key] for key in ("path", "size", "sha256")}
    if actual != expected:
        raise FreezeError(f"File provenance mismatch: {path}")


def _assert_directory_record(repo_root: Path, expected: dict[str, Any]) -> None:
    actual = directory_inventory(repo_root, repo_root / str(expected["path"]))
    if actual != expected:
        raise FreezeError(f"Directory provenance mismatch: {expected['path']}")


def verify(args: argparse.Namespace) -> Path:
    repo_root = args.repo_root.resolve()
    bundle_root = _resolve_repo_path(repo_root, args.bundle_root).resolve()
    manifest_path = bundle_root / PUBLICATION_MANIFEST_NAME
    sidecar_path = bundle_root / PUBLICATION_SIDECAR_NAME
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    expected_sidecar = f"{sha256_bytes(manifest_bytes)}  {manifest_path.name}\n"
    if sidecar_path.read_text(encoding="ascii") != expected_sidecar:
        raise FreezeError("Publication manifest sidecar hash mismatch")
    if int(manifest.get("schema_version") or 0) != SCHEMA_VERSION:
        raise FreezeError("Unsupported publication manifest schema")

    print("verify: bundle files")
    for record in manifest.get("bundle_files") or []:
        _assert_file_record(repo_root, record)
    _assert_file_record(repo_root, manifest["builder"]["frozen_copy"])
    _assert_file_record(repo_root, manifest["builder"]["focused_test"])
    _assert_file_record(repo_root, manifest["benchmark"])
    if (
        len(benchmark_names(repo_root / manifest["benchmark"]["path"]))
        != EXPECTED_TASK_COUNT
    ):
        raise FreezeError("Benchmark task count changed")

    print("verify: checkpoint")
    checkpoint = manifest["checkpoint"]
    current_checkpoint = git_checkpoint(repo_root, checkpoint["commit"])
    for key in ("commit", "tree", "parents", "subject"):
        if current_checkpoint[key] != checkpoint[key]:
            raise FreezeError(f"Checkpoint Git metadata changed: {key}")
    archive_expected = checkpoint["source_archive"]
    archive_actual = tar_inventory(repo_root, repo_root / archive_expected["path"])
    if archive_actual != archive_expected:
        raise FreezeError("Checkpoint source archive provenance mismatch")
    _assert_file_record(repo_root, checkpoint["tracked_patch"])
    _assert_file_record(repo_root, checkpoint["untracked_file_list"])

    print("verify: original-v140 historical reference")
    baseline = manifest["historical_original_v140_reference"]
    snapshot_path = repo_root / baseline["snapshot_path"]
    regenerated, regenerated_metadata = original_v140_snapshot_bytes(
        legacy_cache_root=repo_root / DEFAULT_LEGACY_BASELINE,
        benchmark=repo_root / DEFAULT_BENCHMARK,
    )
    if snapshot_path.read_bytes() != regenerated:
        raise FreezeError("Original-v140 reference snapshot cannot be regenerated")
    for key in (
        "record_count",
        "unique_scenario_count",
        "outcome_scored_record_count",
        "canonical_score_mean",
        "outcome_score_mean",
        "snapshot_sha256",
    ):
        if regenerated_metadata[key] != baseline[key]:
            raise FreezeError(f"Original-v140 metadata mismatch: {key}")
    for record in baseline["legacy_cache_content_at_freeze"].values():
        _assert_file_record(repo_root, record)

    print("verify: RapidAPI fixture")
    rapid = manifest["rapidapi_fixture"]
    _assert_file_record(repo_root, rapid["source"])
    _assert_file_record(repo_root, rapid["sanitized_copy"])
    sanitized, metadata = sanitized_rapid_fixture_bytes(
        repo_root / rapid["source"]["path"]
    )
    if (repo_root / rapid["sanitized_copy"]["path"]).read_bytes() != sanitized:
        raise FreezeError("Sanitized RapidAPI fixture cannot be regenerated")
    if metadata["entry_count"] != rapid["entry_count"]:
        raise FreezeError("RapidAPI entry count changed")

    print("verify: registries")
    registry_inventory_path = (
        repo_root / manifest["paired_registries"]["inventory"]["path"]
    )
    _assert_file_record(repo_root, manifest["paired_registries"]["inventory"])
    registries = _load_json(registry_inventory_path)
    if int(registries.get("replication_count") or 0) != EXPECTED_REPLICATIONS:
        raise FreezeError("Registry inventory replication count mismatch")
    for pair in registries.get("pairs") or []:
        _assert_directory_record(repo_root, pair["online_registry"])
        _assert_directory_record(repo_root, pair["frozen_registry"])
        online_manifest = (
            repo_root / pair["online_registry"]["path"] / "registry_manifest.json"
        )
        frozen_manifest = (
            repo_root / pair["frozen_registry"]["path"] / "registry_manifest.json"
        )
        if sha256_file(online_manifest) != sha256_file(frozen_manifest):
            raise FreezeError(
                f"Registry pair {pair['replication']} manifest equality changed"
            )

    print("verify: analysis and campaign inputs")
    analysis_inventory_path = repo_root / manifest["analysis"]["inventory"]["path"]
    _assert_file_record(repo_root, manifest["analysis"]["inventory"])
    analysis = _load_json(analysis_inventory_path)
    _assert_file_record(repo_root, analysis["campaign_manifest"])
    for record in analysis["static_analysis_inputs"]:
        _assert_file_record(repo_root, record["frozen_copy"])
    for record in analysis["derived_analysis_outputs"]:
        _assert_file_record(repo_root, record)
    for run in analysis["run_inputs"]:
        for record in run["files"]:
            _assert_file_record(repo_root, record)
    for record in analysis["campaign_artifact_directories"]:
        _assert_directory_record(repo_root, record)

    print(f"verify: PASS {manifest_path}")
    print(f"verify: manifest_sha256 {sha256_bytes(manifest_bytes)}")
    return manifest_path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    for command in ("build", "verify"):
        child = subparsers.add_parser(command)
        child.add_argument("--repo-root", type=Path, default=Path("."))
        child.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
        if command == "build":
            child.add_argument(
                "--checkpoint-commit",
                default="HEAD",
                help="Exact pre-cleanup checkpoint commit to pin.",
            )
    return result


def main() -> None:
    args = parser().parse_args()
    try:
        if args.command == "build":
            build(args)
        else:
            verify(args)
    except FreezeError as exc:
        raise SystemExit(f"publication_freeze_error: {exc}") from exc


if __name__ == "__main__":
    main()
