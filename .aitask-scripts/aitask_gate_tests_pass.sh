#!/usr/bin/env bash
# aitask_gate_tests_pass.sh - verifier for the `tests_pass` gate.
#
# Runs project_config.yaml `test_command` command(s). Verifier contract:
#   <task-id> <attempt> <run-id>; exit 0=pass 1=fail 2=skip 3=error.
# A `skip` is either "no test_command configured" or a command that declared it
# did not run (exit 2, opt-in per key via project_config.yaml
# `gate_command_exit_contract`) -- see lib/gate_verifier_lib.sh for the
# command-exit table. These codes are the VERIFIER's, not the command's.
# Resolved by the orchestrator from registry `verifier: aitask-gate-tests-pass`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/yaml_utils.sh
source "$SCRIPT_DIR/lib/yaml_utils.sh"
# shellcheck source=lib/gate_verifier_lib.sh
source "$SCRIPT_DIR/lib/gate_verifier_lib.sh"

run_command_gate tests_pass test_command aitask-gate-tests-pass "$@"
