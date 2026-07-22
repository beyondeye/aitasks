#!/usr/bin/env bash

# aitask_work_report_gather.sh - Deterministic report input for /aitask-work-report.
#
# Emits board columns, the parent tasks they contain (in board order), a
# per-bucket throughput estimate and a completion projection. Internal skill
# helper — deliberately NOT wired into the `ait` dispatcher.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

exec "$PYTHON" "$SCRIPT_DIR/lib/work_report_gather.py" "$@"
