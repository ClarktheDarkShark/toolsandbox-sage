"""Lightweight retry classification schema and provenance verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any, NoReturn

TRANSIENT_EXCEPTION_TYPE_NAMES = (
    "APIConnectionError",
    "APITimeoutError",
    "APIStatusError",
    "InternalServerError",
    "RateLimitError",
    "RetryError",
    "TimeoutException",
    "ReadTimeout",
    "ConnectTimeout",
)
TRANSIENT_TRACEBACK_MARKERS = (
    ("openai_api_connection_error", "openai.APIConnectionError"),
    ("openai_api_timeout_error", "openai.APITimeoutError"),
    ("connection_error", "Connection error."),
    ("read_timeout", "ReadTimeout"),
    ("connect_timeout", "ConnectTimeout"),
    ("rate_limit_error", "RateLimitError"),
    ("retry_error", "RetryError["),
)
RETRY_REASON_KINDS = frozenset({"exception_chain_type", "traceback_marker"})


def _raise(error_type: type[ValueError], message: str) -> NoReturn:
    raise error_type(message)


def validate_successful_retry_provenance(
    item: dict[str, Any],
    *,
    run_dir: Path,
    repo_root: Path,
    arm: str,
    scenario: str,
    error_type: type[ValueError] = ValueError,
) -> None:
    """Fail closed unless a successful row proves every performed retry."""

    label = f"{arm} task {scenario!r}"
    retry_count = item.get("transient_retry_count")
    if isinstance(retry_count, bool) or not isinstance(retry_count, int):
        _raise(error_type, f"{label} has invalid or missing transient_retry_count.")
    if retry_count < 0:
        _raise(error_type, f"{label} has negative transient_retry_count.")

    retry_archives = item.get("transient_retry_archives")
    if not isinstance(retry_archives, list) or not all(
        isinstance(path, str) for path in retry_archives
    ):
        _raise(
            error_type,
            f"{label} has invalid or missing transient_retry_archives.",
        )
    retry_failures = item.get("transient_retry_failures")
    if not isinstance(retry_failures, list):
        _raise(
            error_type,
            f"{label} has invalid or missing transient_retry_failures.",
        )
    if len(retry_failures) != retry_count:
        _raise(
            error_type,
            f"{label} transient retry failure count does not match "
            "transient_retry_count.",
        )

    observed_archive_paths: list[str] = []
    for expected_attempt, failure in enumerate(retry_failures, start=1):
        if not isinstance(failure, dict):
            _raise(
                error_type,
                f"{label} transient retry failure {expected_attempt} is not an object.",
            )
        attempt = failure.get("attempt")
        if (
            isinstance(attempt, bool)
            or not isinstance(attempt, int)
            or attempt != expected_attempt
        ):
            _raise(
                error_type,
                f"{label} transient retry attempts are not exactly 1..{retry_count}.",
            )
        for field in ("exception_type", "exception_message", "traceback"):
            value = failure.get(field)
            if not isinstance(value, str) or not value.strip():
                _raise(
                    error_type,
                    f"{label} transient retry failure {expected_attempt} has "
                    f"invalid or missing {field}.",
                )

        exception_type = failure["exception_type"]
        traceback_text = failure["traceback"]
        chain = failure.get("exception_chain_type_names")
        if (
            not isinstance(chain, list)
            or not chain
            or not all(isinstance(name, str) and name.strip() for name in chain)
        ):
            _raise(
                error_type,
                f"{label} transient retry failure {expected_attempt} has an invalid "
                "exception_chain_type_names.",
            )
        if chain[0] != exception_type:
            _raise(
                error_type,
                f"{label} transient retry failure {expected_attempt} exception chain "
                "does not start with exception_type.",
            )

        retry_reason = failure.get("retry_reason")
        if not isinstance(retry_reason, dict) or set(retry_reason) != {
            "kind",
            "identifier",
        }:
            _raise(
                error_type,
                f"{label} transient retry failure {expected_attempt} has an invalid "
                "retry_reason.",
            )
        reason_kind = retry_reason["kind"]
        reason_identifier = retry_reason["identifier"]
        if (
            not isinstance(reason_kind, str)
            or reason_kind not in RETRY_REASON_KINDS
            or not isinstance(reason_identifier, str)
        ):
            _raise(
                error_type,
                f"{label} transient retry failure {expected_attempt} has a retry "
                "reason outside the producer allowlist.",
            )

        first_chain_identifier = next(
            (name for name in chain if name in TRANSIENT_EXCEPTION_TYPE_NAMES),
            None,
        )
        first_marker = next(
            (
                (identifier, marker)
                for identifier, marker in TRANSIENT_TRACEBACK_MARKERS
                if marker in traceback_text
            ),
            None,
        )
        if reason_kind == "exception_chain_type":
            if reason_identifier not in TRANSIENT_EXCEPTION_TYPE_NAMES:
                _raise(
                    error_type,
                    f"{label} transient retry failure {expected_attempt} has an "
                    "exception-chain identifier outside the producer allowlist.",
                )
            if reason_identifier not in chain:
                _raise(
                    error_type,
                    f"{label} transient retry failure {expected_attempt} retry "
                    "identifier does not occur in its exception chain.",
                )
            if reason_identifier != first_chain_identifier:
                _raise(
                    error_type,
                    f"{label} transient retry failure {expected_attempt} does not "
                    "record the producer's first exception-chain classification.",
                )
        else:
            marker_by_identifier = dict(TRANSIENT_TRACEBACK_MARKERS)
            marker = marker_by_identifier.get(reason_identifier)
            if marker is None:
                _raise(
                    error_type,
                    f"{label} transient retry failure {expected_attempt} has a "
                    "traceback-marker identifier outside the producer allowlist.",
                )
            if marker not in traceback_text:
                _raise(
                    error_type,
                    f"{label} transient retry failure {expected_attempt} traceback "
                    "does not contain its classified marker.",
                )
            if first_chain_identifier is not None or first_marker != (
                reason_identifier,
                marker,
            ):
                _raise(
                    error_type,
                    f"{label} transient retry failure {expected_attempt} does not "
                    "record the producer's first retry classification.",
                )

        archive_path = failure.get("archive_path")
        if not isinstance(archive_path, str):
            _raise(
                error_type,
                f"{label} transient retry failure {expected_attempt} has invalid or "
                "missing archive_path.",
            )
        observed_archive_paths.append(archive_path)
        archive = Path(archive_path)
        resolved_archive = (
            archive.resolve()
            if archive.is_absolute()
            else (repo_root / archive).resolve()
        )
        expected_archive = (
            run_dir
            / "trajectories"
            / f"{scenario}__transient_retry_failed_attempt_{expected_attempt}"
        ).resolve()
        if resolved_archive != expected_archive:
            _raise(
                error_type,
                f"{label} transient retry archive is not the exact expected "
                f"trajectory directory: {resolved_archive}.",
            )
        if not resolved_archive.is_dir():
            _raise(
                error_type,
                f"{label} transient retry archive is not an existing directory: "
                f"{resolved_archive}.",
            )
    if retry_archives != observed_archive_paths:
        _raise(
            error_type,
            f"{label} transient retry archives do not exactly match the failure "
            "records.",
        )
