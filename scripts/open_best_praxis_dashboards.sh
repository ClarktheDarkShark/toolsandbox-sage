#!/usr/bin/env bash
set -euo pipefail

# Open the latest completed Praxis combined-treatment validation sequence before
# the self-evolution branch work. The original run ports were transient; this
# script serves the same dashboard files through a live local dashboard picker.

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-62536}"
CURL="${CURL:-/usr/bin/curl}"
LSOF="${LSOF:-/usr/sbin/lsof}"
OPEN="${OPEN:-/usr/bin/open}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVER_SCRIPT="${REPO_ROOT}/scripts/serve_dashboard_picker.py"
LOG_DIR="${REPO_ROOT}/outputs/dashboard_picker"
LOG_FILE="${LOG_DIR}/port_${PORT}.log"

declare -a DASHBOARD_PATHS=(
  "/outputs/praxis_combined_bridge_policy/formal500_order_first100_v3_bridge_repair_rapid_cache/validate_100_20260511_171441/dashboard/task_compare.html"
  "/outputs/praxis_combined_bridge_policy/formal500_order_first250_v2_bridge_repair_rapid_cache/validate_250_20260511_172919/dashboard/task_compare.html"
  "/outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013/dashboard/task_compare.html"
)

url_for_path() {
  printf 'http://%s:%s%s' "${HOST}" "${PORT}" "$1"
}

url_is_available() {
  "${CURL}" -fsS -o /dev/null "$(url_for_path "${DASHBOARD_PATHS[0]}")"
}

port_is_listening() {
  "${LSOF}" -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1
}

start_server() {
  mkdir -p "${LOG_DIR}"
  nohup python3 "${SERVER_SCRIPT}" \
    --host "${HOST}" \
    --port "${PORT}" \
    --root "${REPO_ROOT}" \
    >"${LOG_FILE}" 2>&1 &
  echo "Started dashboard picker on http://${HOST}:${PORT}/"
  echo "Log: ${LOG_FILE}"
}

if ! url_is_available; then
  if port_is_listening; then
    echo "Port ${PORT} is already in use, but it is not serving the Praxis dashboards." >&2
    echo "Either stop that process or rerun with a different port, for example:" >&2
    echo "  PORT=62624 $0" >&2
    exit 1
  fi

  start_server
  for _ in {1..40}; do
    if url_is_available; then
      break
    fi
    sleep 0.25
  done
fi

if ! url_is_available; then
  echo "Dashboard server started, but the Praxis dashboards are still unavailable." >&2
  echo "Check that the sibling toolsandbox-sage-praxis-final-hardening worktree exists." >&2
  echo "Log: ${LOG_FILE}" >&2
  exit 1
fi

echo "Opening Praxis validation dashboards:"
for path in "${DASHBOARD_PATHS[@]}"; do
  url="$(url_for_path "${path}")"
  echo "  ${url}"
  "${OPEN}" "${url}"
done
