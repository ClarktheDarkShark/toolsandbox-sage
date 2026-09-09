#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_DIR="${1:-$ROOT_DIR/.venv-publication}"
PYTHON_VERSION="3.12.7"
LOCK_FILE="$ROOT_DIR/requirements-publication-lock.txt"

BOOTSTRAP_PYTHON="$(command -v python3.12 || true)"
if [[ -z "$BOOTSTRAP_PYTHON" ]]; then
  echo "python3.12 is required but was not found on PATH" >&2
  exit 1
fi
if [[ ! -f "$LOCK_FILE" ]]; then
  echo "Publication environment lock is missing: $LOCK_FILE" >&2
  exit 1
fi

BOOTSTRAP_VERSION="$("$BOOTSTRAP_PYTHON" -c 'import platform; print(platform.python_version())')"
if [[ "$BOOTSTRAP_VERSION" != "$PYTHON_VERSION" ]]; then
  echo "python3.12 resolves to ${BOOTSTRAP_VERSION}; Python ${PYTHON_VERSION} is required." >&2
  exit 1
fi

if [[ -e "$ENV_DIR" ]]; then
  if [[ ! -x "$ENV_DIR/bin/python" ]]; then
    echo "Existing environment path has no Python executable: $ENV_DIR" >&2
    exit 1
  fi
  OBSERVED_VERSION="$("$ENV_DIR/bin/python" -c 'import platform; print(platform.python_version())')"
  if [[ "$OBSERVED_VERSION" != "$PYTHON_VERSION" ]]; then
    echo "Existing environment uses Python ${OBSERVED_VERSION}; Python ${PYTHON_VERSION} is required." >&2
    echo "Choose a new path or remove the incompatible environment explicitly." >&2
    exit 1
  fi
  echo "Using existing virtual environment: $ENV_DIR"
else
  "$BOOTSTRAP_PYTHON" -m venv "$ENV_DIR"
fi

ENV_PYTHON="$ENV_DIR/bin/python"
"$ENV_PYTHON" -m pip install --requirement "$LOCK_FILE"
"$ENV_PYTHON" -m pip install --no-deps --editable "$ROOT_DIR"

# On macOS, virtual environments created inside a hidden/iCloud-synchronized
# directory can propagate UF_HIDDEN through the environment tree. CPython then
# skips editable-install .pth files, silently disabling the package outside
# PYTHONPATH. Normalize only this explicitly selected virtual environment before
# the isolated import provenance check.
if [[ "$(uname -s)" == "Darwin" ]]; then
  /usr/bin/chflags -R nohidden "$ENV_DIR"
fi

"$ENV_PYTHON" -m pip check
"$ENV_PYTHON" "$ROOT_DIR/scripts/verify_publication_environment.py" \
  --lock "$LOCK_FILE"

echo "Publication environment ready: $ENV_DIR"
echo "Activate with: source '$ENV_DIR/bin/activate'"
