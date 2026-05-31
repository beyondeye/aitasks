#!/usr/bin/env bash
# test_scaffold.sh - Bootstrap a minimal fake .aitask-scripts/ tree.
# Always copies the "system" libs that ./ait and most helpers source
# unconditionally. Caller adds script-specific files on top.
#
# REQUIRES: PROJECT_DIR (path to the real aitasks repo root) is set in
# the caller's scope before invoking setup_fake_aitask_repo().
# shellcheck disable=SC2034  # may be referenced externally

if [[ -z "${_AIT_TEST_SCAFFOLD_LOADED:-}" ]]; then
    _AIT_TEST_SCAFFOLD_LOADED=1

    setup_fake_aitask_repo() {
        local repo_dir="$1"
        mkdir -p "$repo_dir/.aitask-scripts/lib"
        cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh"     "$repo_dir/.aitask-scripts/lib/"
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$repo_dir/.aitask-scripts/lib/"
        cp "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"  "$repo_dir/.aitask-scripts/lib/"
        # yaml_utils.sh is a base leaf lib sourced unconditionally by both
        # task_utils.sh and agentcrew_utils.sh — the two most-copied add-on libs.
        cp "$PROJECT_DIR/.aitask-scripts/lib/yaml_utils.sh"      "$repo_dir/.aitask-scripts/lib/"
        # cross_repo_reexec.sh is sourced at startup by aitask_ls.sh,
        # aitask_query_files.sh, and aitask_find_by_file.sh; its only dep
        # (terminal_compat.sh) is already copied above.
        cp "$PROJECT_DIR/.aitask-scripts/lib/cross_repo_reexec.sh" "$repo_dir/.aitask-scripts/lib/"
    }
fi
