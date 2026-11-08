#!/usr/bin/env bash
# framework_copy.sh - copy the framework (or one package of it) into a test
# fixture WITHOUT Python bytecode caches (t2226).
#
# Usage, after PROJECT_DIR is set:
#
#   . "$PROJECT_DIR/tests/lib/framework_copy.sh"
#   copy_framework_tree "$PROJECT_DIR/.aitask-scripts"     "$fixture/.aitask-scripts"
#   copy_framework_tree "$PROJECT_DIR/.aitask-scripts/lib" "$fixture/.aitask-scripts/lib"
#
# Why. A working checkout carries ~12 MB of gitignored __pycache__ dirs under
# .aitask-scripts (half the tree). `cp -r` copied them into every fixture, and
# fixtures that `git add -A` committed them too: test_sync_deferral_and_quarantine.sh
# alone grew /tmp by ~2 GB from a real checkout (~1 GB from a clean tree), which
# exhausted the per-user tmpfs quota and failed unrelated sync tests under
# parallel load. The copies were useless anyway -- `cp -r` gives each .py a fresh
# mtime, so Python treats every copied .pyc as stale and recompiles it.
#
# Semantics: the CONTENTS of <src_dir> land in <dst_dir>, which is created when
# missing (= `cp -r src dst` for a fresh dst, = `cp -r src/. dst/` for an existing
# one). Excluded: every __pycache__/ directory and every *.pyc, at any depth.
# Kept: everything else, including untracked work-in-progress files -- this is
# deliberately NOT `git ls-files`, because a fixture must exercise the tree as it
# stands. Mode bits are kept; mtimes are not restored (-m), matching `cp -r`.
#
# tests/test_framework_copy.sh forbids a recursive `cp` from
# PROJECT_DIR/.aitask-scripts in any tracked tests/*.sh file: use this instead.

# copy_framework_tree <src_dir> <dst_dir>
copy_framework_tree() {
    local src="$1" dst="$2"
    local -a st
    if [[ ! -d "$src" ]]; then
        echo "copy_framework_tree: not a directory: $src" >&2
        return 1
    fi
    mkdir -p "$dst" || return 1
    tar -C "$src" --exclude='__pycache__' --exclude='*.pyc' -cf - . | tar -C "$dst" -xmf -
    st=("${PIPESTATUS[@]}")
    [[ "${st[0]}" -eq 0 && "${st[1]}" -eq 0 ]]
}
