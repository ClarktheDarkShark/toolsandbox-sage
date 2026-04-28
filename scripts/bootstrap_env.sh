#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${1:-toolsandbox-sage}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is required but was not found on PATH" >&2
  exit 1
fi

if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  echo "Using existing conda env: ${ENV_NAME}"
else
  conda create -n "${ENV_NAME}" python=3.9 -y
fi

conda run -n "${ENV_NAME}" python -m pip install --upgrade pip
conda run -n "${ENV_NAME}" python -m pip install -e ".[dev]"
conda run -n "${ENV_NAME}" pre-commit install
conda run -n "${ENV_NAME}" tool_sandbox --help >/dev/null

echo "Environment ready: ${ENV_NAME}"
