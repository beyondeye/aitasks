#!/usr/bin/env bash
# preflight.sh — source tripwires that must pass before the full suite runs.
# Never shipped: build.sh builds only cmd/*.
#
# The runner package's hang-guard tripwire
# (internal/testmap/runner/isolation_tripwire_test.go) fails a test that starts
# a process without the `isolated` guard. Inside `go test ./...` it is an
# ordinary test: it runs in file order, after tests that could already hang,
# and its failure does not stop the tests after it. Run alone first, it fails
# in seconds and the suite never starts.
#
# Every entry point that runs the suite calls this first, and the suite runs
# only when it exits 0:
#   .github/workflows/goengines-check.yml   (job check)
#   .github/workflows/release.yml           (job goengines)
#   ait engine test                         (.aitask-scripts/aitask_engine.sh)
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
go test -count=1 -run '^TestIsolationTripwire(Catches)?$' ./internal/testmap/runner/
