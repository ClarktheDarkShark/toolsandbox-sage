#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BATCH_LABEL="${1:-ch4_primary}"
REPLICATES="${2:-3}"
START_PORT="${3:-63105}"
RUN_NAMESPACE="${CHAPTER4_RUN_NAMESPACE:-chapter4_4omini_full_runs}"

if ! [[ "$REPLICATES" =~ ^[0-9]+$ ]] || [[ "$REPLICATES" -lt 1 ]]; then
  echo "REPLICATES must be a positive integer." >&2
  exit 1
fi
if ! [[ "$START_PORT" =~ ^[0-9]+$ ]] || [[ "$START_PORT" -lt 1 ]]; then
  echo "START_PORT must be a positive integer." >&2
  exit 1
fi

RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
SAFE_BATCH_LABEL="$(echo "$BATCH_LABEL" | tr -cs 'A-Za-z0-9_-' '_' | sed 's/^_//; s/_$//')"
BATCH_ROOT="artifacts/${RUN_NAMESPACE}/${SAFE_BATCH_LABEL}_parallel_${RUN_STAMP}"
mkdir -p "$BATCH_ROOT"

MANIFEST="$BATCH_ROOT/batch_manifest.tsv"
{
  printf 'replicate\tlabel\tport\tpid\tlog\n'
} > "$MANIFEST"

echo "Chapter 4 4o-mini parallel batch"
echo "Batch label: $SAFE_BATCH_LABEL"
echo "Replicates: $REPLICATES"
echo "Start port: $START_PORT"
echo "Batch root: $BATCH_ROOT"

pids=()
labels=()
logs=()

for idx in $(seq 1 "$REPLICATES"); do
  rep="$(printf '%02d' "$idx")"
  label="${SAFE_BATCH_LABEL}_rep${rep}"
  port=$((START_PORT + idx - 1))
  log="$BATCH_ROOT/${label}.log"

  echo "Launching $label on dashboard port $port"
  (
    scripts/run_chapter4_4omini_full_claim_run.sh "$label" "$port"
  ) > "$log" 2>&1 &

  pid=$!
  pids+=("$pid")
  labels+=("$label")
  logs+=("$log")
  printf '%s\t%s\t%s\t%s\t%s\n' "$rep" "$label" "$port" "$pid" "$log" >> "$MANIFEST"
done

echo
echo "All requested replications are running."
echo "Batch manifest: $MANIFEST"
echo "Logs:"
for idx in "${!labels[@]}"; do
  echo "  ${labels[$idx]} pid=${pids[$idx]} log=${logs[$idx]}"
done

echo
echo "Waiting for all replications to finish..."

status=0
for idx in "${!pids[@]}"; do
  pid="${pids[$idx]}"
  label="${labels[$idx]}"
  if wait "$pid"; then
    echo "$label completed successfully."
  else
    rc=$?
    echo "$label failed with exit code $rc. See ${logs[$idx]}" >&2
    status=1
  fi
done

exit "$status"
