#!/usr/bin/env bash
# aitask_gate_build.sh - verifier for the `build_verified` gate.
#
# Runs project_config.yaml `verify_build` command(s). Verifier contract:
#   <task-id> <attempt> <run-id>; exit 0=pass 1=fail 2=skip(no command) 3=error.
# Resolved by the orchestrator from registry `verifier: aitask-gate-build`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/yaml_utils.sh
source "$SCRIPT_DIR/lib/yaml_utils.sh"
# shellcheck source=lib/gate_verifier_lib.sh
source "$SCRIPT_DIR/lib/gate_verifier_lib.sh"

run_command_gate build_verified verify_build aitask-gate-build "$@"
