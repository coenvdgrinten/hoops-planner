#!/usr/bin/env bash
# Soak-test the e2e suite: run it N times back-to-back, stop on first failure.
#
# Flaky tests often fail only rarely, so a single green run proves little.
# This loops the full suite (including global-setup's DB wipe + reseed, so
# every run starts from a clean state) and fails fast on the first red run.
#
# Retries are forced to 0: CI's default of 2 would mask flakes and make a
# green soak run meaningless.
#
# Usage: ./scripts/e2e-soak.sh [runs] [workers]
#   runs    default 10
#   workers default 4 (CI target is 2 — ubuntu-latest has 2 vCPUs)
set -u
RUNS=${1:-10}
WORKERS=${2:-4}
cd "$(dirname "$0")/.."

for i in $(seq 1 "$RUNS"); do
  echo ""
  echo "=== Soak run $i/$RUNS (workers=$WORKERS, retries=0) ==="
  if ! pnpm exec playwright test --workers="$WORKERS" --retries=0; then
    echo ""
    echo "SOAK FAILED on run $i/$RUNS"
    exit 1
  fi
done

echo ""
echo "Soak passed: $RUNS/$RUNS runs green (workers=$WORKERS)"
