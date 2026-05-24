"""Prepare or verify local ScienceAgentBench official artifacts.

ScienceAgentBench publishes verified task inputs on Hugging Face, but the
datasets/eval/gold/rubric artifacts used for official scoring are distributed as
a password-protected zip by the benchmark authors. This script keeps that
boundary explicit: it validates public inputs, optionally extracts a locally
provided artifact zip, and records whether the official scorer can run.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_SHAREPOINT_URL = (
    "https://buckeyemailosu-my.sharepoint.com/:u:/g/personal/"
    "chen_8336_buckeyemail_osu_edu/"
    "IQB870QrmuqwS5Ck33cHpJfkAVt3LsMeariREIwP3AT7byA?download=1"
)
REQUIRED_DIRS = ("datasets", "eval_programs", "gold_programs", "scoring_rubrics")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify or materialize ScienceAgentBench official artifacts."
    )
    parser.add_argument("--repo", type=Path, default=Path("external/ScienceAgentBench"))
    parser.add_argument("--split", default="verified")
    parser.add_argument("--artifact-zip", type=Path)
    parser.add_argument(
        "--password",
        default="scienceagentbench",
        help="Password for the official benchmark artifact zip.",
    )
    parser.add_argument("--attempt-download", action="store_true")
    parser.add_argument("--download-url", default=DEFAULT_SHAREPOINT_URL)
    parser.add_argument(
        "--status-json",
        type=Path,
        default=Path(
            "artifacts/sage_official_live/scienceagentbench_artifact_status.json"
        ),
    )
    args = parser.parse_args()

    repo = args.repo
    benchmark = repo / "benchmark"
    status: dict[str, object] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "benchmark_path": str(benchmark),
        "split": args.split,
        "required_dirs": list(REQUIRED_DIRS),
        "huggingface_verified_inputs": _hf_status(args.split),
        "artifact_dirs_before": _artifact_dirs(benchmark),
    }

    if args.attempt_download:
        status["download_attempt"] = _attempt_download(args.download_url)

    if args.artifact_zip:
        status["artifact_zip"] = str(args.artifact_zip)
        status["extract_attempt"] = _extract_zip(
            zip_path=args.artifact_zip,
            destination=benchmark,
            password=args.password,
        )

    artifact_dirs_after = _artifact_dirs(benchmark)
    status["artifact_dirs_after"] = artifact_dirs_after
    missing = [name for name, present in artifact_dirs_after.items() if not present]
    status["official_scoring_ready"] = not missing
    status["missing_artifacts"] = missing
    status["next_action"] = (
        "ready_for_scienceagentbench_official_scoring"
        if not missing
        else (
            "download benchmark_verified.zip from the official ScienceAgentBench "
            "SharePoint link using an authenticated browser if needed, then run "
            "this script with --artifact-zip /path/to/benchmark_verified.zip"
        )
    )

    args.status_json.parent.mkdir(parents=True, exist_ok=True)
    args.status_json.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))
    if missing:
        raise SystemExit(2)


def _hf_status(split: str) -> dict[str, object]:
    try:
        from datasets import load_dataset  # type: ignore[import-untyped]
    except Exception as exc:
        return {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    try:
        dataset = load_dataset("osunlp/ScienceAgentBench", split=split, streaming=True)
        first = next(iter(dataset))
    except Exception as exc:
        return {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "available": True,
        "dataset": "osunlp/ScienceAgentBench",
        "split": split,
        "first_instance_id": str(first.get("instance_id", "")),
        "fields": sorted(str(key) for key in first.keys()),
    }


def _artifact_dirs(benchmark: Path) -> dict[str, bool]:
    return {name: (benchmark / name).exists() for name in REQUIRED_DIRS}


def _attempt_download(url: str) -> dict[str, object]:
    target = Path("artifacts/sage_official_live/downloads/benchmark_verified_probe")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=60) as response:
            content_type = response.headers.get("content-type", "")
            first_bytes = response.read(4096)
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
    target.write_bytes(first_bytes)
    looks_like_zip = first_bytes.startswith(b"PK\x03\x04")
    looks_like_auth_page = b"Sign in to your account" in first_bytes[:4096]
    return {
        "status": "zip_detected" if looks_like_zip else "not_zip",
        "content_type": content_type,
        "first_bytes_path": str(target),
        "auth_required": bool(looks_like_auth_page),
        "note": (
            "The public SharePoint URL returned an auth/sign-in page."
            if looks_like_auth_page
            else ""
        ),
    }


def _extract_zip(
    *, zip_path: Path, destination: Path, password: str
) -> dict[str, object]:
    if not zip_path.exists():
        return {"status": "missing_zip", "path": str(zip_path)}
    if not zipfile.is_zipfile(zip_path):
        return {"status": "not_a_zip", "path": str(zip_path)}
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sab_extract_") as temp_name:
        temp_dir = Path(temp_name)
        try:
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(temp_dir, pwd=password.encode("utf-8"))
        except RuntimeError as exc:
            return {"status": "extract_failed", "error": str(exc)}
        source = _find_benchmark_root(temp_dir)
        if source is None:
            return {
                "status": "required_dirs_not_found",
                "top_level": [path.name for path in temp_dir.iterdir()],
            }
        for name in REQUIRED_DIRS:
            src = source / name
            dst = destination / name
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            shutil.copytree(src, dst)
    return {"status": "extracted", "destination": str(destination)}


def _find_benchmark_root(root: Path) -> Path | None:
    candidates = [root, *[path for path in root.rglob("*") if path.is_dir()]]
    for candidate in candidates:
        if all((candidate / name).exists() for name in REQUIRED_DIRS):
            return candidate
    return None


if __name__ == "__main__":
    main()
