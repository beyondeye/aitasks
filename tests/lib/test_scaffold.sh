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
        # tmux_exec.sh is the shell tmux gateway; terminal_compat.sh sources it
        # lazily from ait_tmux_new_session_persistent (t952_4), so any scaffolded
        # test that reaches the persistent-spawn path needs it present.
        cp "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh"      "$repo_dir/.aitask-scripts/lib/"
        cp "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"  "$repo_dir/.aitask-scripts/lib/"
        # yaml_utils.sh is a base leaf lib sourced unconditionally by both
        # task_utils.sh and agentcrew_utils.sh — the two most-copied add-on libs.
        cp "$PROJECT_DIR/.aitask-scripts/lib/yaml_utils.sh"      "$repo_dir/.aitask-scripts/lib/"
        # atomic_write.sh is sourced at startup by every script that replaces a
        # task/plan file in place (aitask_update.sh, aitask_create.sh,
        # aitask_issue_import.sh, aitask_plan_verified.sh,
        # aitask_plan_externalize.sh, aitask_gate_pass.sh, aitask_projects.sh);
        # it is a stdlib-only leaf with no deps of its own (t1379).
        cp "$PROJECT_DIR/.aitask-scripts/lib/atomic_write.sh"    "$repo_dir/.aitask-scripts/lib/"
        # …and its Python sibling, for the same reason on the Python side: any
        # scaffolded test that copies board/, brainstorm/ or diffviewer/ modules
        # imports it transitively. Both are stdlib-only leaves, so copying them
        # unconditionally costs nothing.
        cp "$PROJECT_DIR/.aitask-scripts/lib/atomic_write.py"    "$repo_dir/.aitask-scripts/lib/"
        # cross_repo_reexec.sh is sourced at startup by aitask_ls.sh,
        # aitask_query_files.sh, and aitask_find_by_file.sh; its only dep
        # (terminal_compat.sh) is already copied above.
        cp "$PROJECT_DIR/.aitask-scripts/lib/cross_repo_reexec.sh" "$repo_dir/.aitask-scripts/lib/"
        # followup_kinds_sh.sh is sourced at startup by aitask_create.sh and
        # aitask_update.sh (t1468_1), and it shells out to its Python sibling to
        # derive the vocabulary -- so BOTH must be present or the bridge fails
        # closed and every --followup-kind validation rejects.
        cp "$PROJECT_DIR/.aitask-scripts/lib/followup_kinds_sh.sh" "$repo_dir/.aitask-scripts/lib/"
        cp "$PROJECT_DIR/.aitask-scripts/lib/followup_kinds.py"    "$repo_dir/.aitask-scripts/lib/"
        # stale_lock.sh is sourced at startup by aitask_create.sh and
        # aitask_gate.sh (t1496 — the shared child/gate mutex); a stdlib-only
        # leaf with no deps beyond terminal_compat.sh (already copied above).
        cp "$PROJECT_DIR/.aitask-scripts/lib/stale_lock.sh"        "$repo_dir/.aitask-scripts/lib/"
    }

    # --- Python module closure ---------------------------------------------
    #
    # Copy Python modules from <src_lib> into <dst_lib> along with every
    # <src_lib> sibling they transitively import. The roots are the entry points
    # a test actually drives; the transitive deps are DERIVED, so a new import
    # in a copied module can no longer break a scaffold silently (t1488:
    # board_columns.py grew a `from record_protocol import …` and
    # test_boardcol_update.sh's hand-maintained copy list did not, leaving that
    # file red on main with no FAIL line and no error text at all).
    #
    #     copy_py_closure_from "$PROJECT_DIR/.aitask-scripts/lib" "$d/lib" board_columns
    #     copy_lib_py_closure "$PWD" board_columns        # scaffold-flavored
    #
    # Import extraction is a line scan of `import X` / `from X import …`,
    # top-level AND function-local (deliberately: over-copying a lazily-imported
    # module is harmless, missing one is not). Docstring prose matches the same
    # shape — atomic_write.py's own docstring contains "from the same old text,
    # and the second replace …" — so every candidate is filtered by "does
    # <src_lib>/<name>.py exist". That existence check is what makes the naive
    # scan safe, and it is also what drops stdlib and third-party names (os,
    # json, yaml, …).
    #
    # BLIND SPOT: imports built dynamically (importlib, __import__, a module
    # name assembled at runtime) are invisible to a line scan. The derived
    # closure is therefore NOT exhaustive — a caller relying on a dynamic import
    # must pass that module as an explicit root.
    #
    # Diamonds are copied once and import cycles terminate: a module is marked
    # before its deps are walked.
    #
    # OUTPUTS — documented contract, readable after the call returns:
    #   AIT_PY_CLOSURE_MODULES   space-delimited closure (space-padded on both
    #                            ends), appended at the seen-marking
    #   AIT_PY_CLOSURE_COPIED    number of `cp` invocations
    # The two are bumped at deliberately DIFFERENT points, so they agree only
    # while the dedup guard holds. Inspecting <dst_lib> cannot tell one `cp`
    # from two identical overwrites; comparing these two can — which is what
    # tests/test_scaffold_py_closure.sh asserts.
    #
    # bash-3.2-safe: no `declare -A`, no `mapfile` (the same constraint
    # asserts.sh documents). Recursion rather than an array queue keeps it
    # `set -u`-safe, where expanding an empty array is an error.

    # Ceiling on module visits before the dedup guard is declared broken. The
    # real lib/ tree is ~100 modules, so this is far above any legitimate walk
    # while still turning runaway recursion into a bounded, named failure
    # instead of a hang.
    _AIT_PY_CLOSURE_MAX_VISITS=512

    # Echo the <src_lib> siblings imported by <file>, one per line.
    _py_local_imports() {   # <file> <src_lib>
        local file="$1" src_lib="$2" name
        awk '
            /^[ \t]*import[ \t]+[A-Za-z_]/ {
                tail = $0
                sub(/^[ \t]*import[ \t]+/, "", tail)
                n = split(tail, parts, ",")
                for (i = 1; i <= n; i++) {
                    p = parts[i]
                    sub(/^[ \t]+/, "", p)
                    sub(/[^A-Za-z0-9_].*$/, "", p)
                    if (p != "") print p
                }
                next
            }
            /^[ \t]*from[ \t]+[A-Za-z_]/ {
                p = $2
                sub(/[^A-Za-z0-9_].*$/, "", p)
                if (p != "") print p
            }
        ' "$file" | sort -u | while IFS= read -r name; do
            [ -f "$src_lib/$name.py" ] && printf '%s\n' "$name"
        done
        # The `while` inherits the last `[ -f ]` test's status; a trailing
        # non-local import would otherwise make this function look failed.
        return 0
    }

    _copy_py_closure_visit() {   # <src_lib> <dst_lib> <module>
        local src_lib="$1" dst_lib="$2" mod="$3" dep

        _AIT_PY_CLOSURE_VISITS=$((_AIT_PY_CLOSURE_VISITS + 1))
        if [ "$_AIT_PY_CLOSURE_VISITS" -gt "$_AIT_PY_CLOSURE_MAX_VISITS" ]; then
            echo "copy_py_closure_from: over $_AIT_PY_CLOSURE_MAX_VISITS module visits at '$mod' — the dedup guard is not converging" >&2
            return 1
        fi

        case "$AIT_PY_CLOSURE_MODULES" in
            *" $mod "*) return 0 ;;
        esac

        if [ ! -f "$src_lib/$mod.py" ]; then
            echo "copy_py_closure_from: no such module: $src_lib/$mod.py" >&2
            return 1
        fi

        # Marked BEFORE the deps are walked — this is what terminates a cycle.
        AIT_PY_CLOSURE_MODULES="$AIT_PY_CLOSURE_MODULES$mod "

        cp "$src_lib/$mod.py" "$dst_lib/" || return 1
        AIT_PY_CLOSURE_COPIED=$((AIT_PY_CLOSURE_COPIED + 1))

        for dep in $(_py_local_imports "$src_lib/$mod.py" "$src_lib"); do
            _copy_py_closure_visit "$src_lib" "$dst_lib" "$dep" || return 1
        done
        return 0
    }

    copy_py_closure_from() {   # <src_lib> <dst_lib> <module>...
        local src_lib="$1" dst_lib="$2" mod
        shift 2
        mkdir -p "$dst_lib" || return 1
        AIT_PY_CLOSURE_MODULES=" "
        AIT_PY_CLOSURE_COPIED=0
        _AIT_PY_CLOSURE_VISITS=0
        for mod in "$@"; do
            _copy_py_closure_visit "$src_lib" "$dst_lib" "$mod" || return 1
        done
        return 0
    }

    # Scaffold-flavored wrapper: source is the real repo's lib/, destination is
    # the scaffold's.
    copy_lib_py_closure() {   # <repo_dir> <module>...
        local repo_dir="$1"
        shift
        copy_py_closure_from "$PROJECT_DIR/.aitask-scripts/lib" \
                             "$repo_dir/.aitask-scripts/lib" "$@"
    }
fi
