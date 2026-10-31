---
Task: t2177_upgrade_gitignore_rules_and_trail_recursion_error.md
Base branch: main
Output branch: main
---

# t2177 — upgrade-path `.gitignore` store rules + fail-closed trail RecursionError

## Context

Two upstream defects found during t2173_1:

1. `ait upgrade` runs `install.sh`, which never runs setup. For an existing
   install, install.sh only calls `setup_data_gitignore_symlink_safe` and
   `upgrade_cache_gitignore` (`install.sh:1909-1920`). The setup-only store
   rules `.aitask-gates/`, `.aitask-testmap/`, `.aitask-shadow/` and
   `.aitask-scratchpad/` therefore never reach a project that has only ever
   been upgraded, and their stores show up as untracked there.
   `setup_worktree_dirs_gitignore` (`aiwork/`, `.aitask-crews/`) has the same
   gap and the worse hazard: an unignored worktree is exposed to a broad
   `git add -A`. **This plan includes it, which goes beyond the four rules the
   task names.** `__pycache__/` (`setup_python_cache_gitignore`) is left out on
   purpose: install.sh already installs the scoped
   `.aitask-scripts/.gitignore` seed, which covers the framework's own Python
   caches, and a root `__pycache__/` belongs to the project.
2. `trail_schema.load_trail` (`.aitask-scripts/lib/trail_schema.py:645-652`)
   catches only `ValueError` from `json.loads`. A deeply nested payload raises
   `RecursionError` straight out of `load_trail`, and out of
   `trail_discovery.load_trail_blob`, which catches only
   `TrailValidationError`, into the `@work(thread=True)` discovery worker, so
   the TUI exits. **Probed during planning:** `validate_trail` is reachable
   too. A `scope.topics` item nested 500 deep parses fine, then raises
   `RecursionError` in `_canonical_key` (uniqueItems). A guard on `json.loads`
   alone is not enough.

## Part A — upgrade-path `.gitignore` rules

### A1. `.aitask-scripts/aitask_setup.sh` — generalise the t2173_1 helper

Replace `_ait_add_cache_gitignore_rule <gitignore>` (line ~3146) with
`_ait_add_gitignore_rules <gitignore> <comment> <rule>...`. The contract stays
the same: 0 = added, 1 = all already present, 2 = could not inspect or write.
Every step is checked, and the write is read back.

```bash
_ait_add_gitignore_rules() {
    local gitignore="$1" comment="$2" rc rule
    shift 2
    local missing=()
    if [[ -e "$gitignore" || -L "$gitignore" ]]; then
        for rule in "$@"; do
            rc=0
            grep -qxF -- "$rule" "$gitignore" 2>/dev/null || rc=$?
            case "$rc" in
                0) ;;
                1) missing+=("$rule") ;;
                *) return 2 ;;
            esac
        done
        [[ ${#missing[@]} -gt 0 ]] || return 1
        { echo ""; echo "# $comment"; printf '%s\n' "${missing[@]}"; } \
            2>/dev/null >> "$gitignore" || return 2
    else
        missing=("$@")
        { echo "# $comment"; printf '%s\n' "${missing[@]}"; } \
            2>/dev/null > "$gitignore" || return 2
    fi
    for rule in "${missing[@]}"; do
        grep -qxF -- "$rule" "$gitignore" 2>/dev/null || return 2
    done
    return 0
}
```

Each rule is guarded on its own, the same per-rule behaviour
`setup_worktree_dirs_gitignore` has. A file that already has `.aitask-crews/`
gains only `aiwork/`.

- `setup_cache_gitignore` / `upgrade_cache_gitignore` call
  `_ait_add_gitignore_rules "$gi" "Discovery caches (per-checkout, content-keyed, safe to delete)" ".aitask-cache/"`.
  Their output does not change: tests 27f/27g pin "Could not add
  .aitask-cache/ to .gitignore", "Added .aitask-cache/" and "already in
  .gitignore".
- `_ait_warn_cache_gitignore_failed` becomes
  `_ait_warn_gitignore_rules_failed <what> <rule>...`. It produces the same
  three warn lines with the rule list and the "<what> will show as untracked"
  wording substituted in. The cache caller passes `"The discovery cache"`, so
  the existing text is unchanged.
- New `_ait_upgrade_gitignore_rules <label> <comment> <rule>...`. It writes
  only and is never fatal: 0 → `success "Added <rules> to .gitignore (<label>)"`,
  1 → `success "<label> rules already in .gitignore"`, 2 → warn helper. It
  always returns 0.
- New public `upgrade_store_gitignore_rules`. It calls the wrapper once per
  setup-only group, **in setup's `main()` order and with the exact comment
  strings the `setup_*` functions write**:
  - `.aitask-gates/` — "Gate sidecar logs (per-task verifier output; in-body summary is committed)"
  - `.aitask-testmap/` — "Test map runs, ledger and onboarding scratch (per-checkout)"
  - `.aitask-shadow/` — "Shadow concern-rejection store (per-task, local-only; pruned at archive)"
  - `.aitask-scratchpad/` — "Scratchpad notes (per-task, local-only; pruned at archive)"
  - `aiwork/` + `.aitask-crews/` — "Framework worktrees (local, per-task and per-crew branches)"

  The `setup_*` functions themselves are not changed. Test 27h below pins
  parity: setup and upgrade must produce byte-identical files.
- Update the section comment ("reaches a project by two routes") so it covers
  the store rules too.

### A2. `install.sh` (~line 1915)

Add a block in the same position and under the same contract as the
cache-rule block. It goes before `commit_installed_files`, so the pre-upgrade
dirty baseline decides whether `.gitignore` is committed:

```bash
    # Same contract and position for the setup-only store and worktree rules
    # (t2177): an upgraded-only project otherwise never ignores them.
    if [[ "$EXISTING_INSTALL" == true ]] && \
       declare -F upgrade_store_gitignore_rules >/dev/null; then
        info "Checking .gitignore store and worktree entries..."
        upgrade_store_gitignore_rules
    fi
```

### A3. Tests

`tests/test_install_upgrade_dirty_baseline.sh`:
- Cases K and K2 loop over `UPGRADE_RULES=(.aitask-cache/ .aitask-gates/ .aitask-testmap/ .aitask-shadow/ .aitask-scratchpad/ aiwork/ .aitask-crews/)`.
- **K** checks that each rule is on disk and in HEAD, that `.gitignore` is
  clean, and that the upgrade commit carries `.gitignore`. A file written under
  each store directory must stay out of `git status --untracked-files=all`.
  After a second upgrade, each rule appears exactly once.
- **K2** (dirty `.gitignore`) checks that each rule is on disk but absent from
  HEAD, and that `.gitignore` is still ` M`.
- **K3** (new): the `.gitignore` already carries `.aitask-crews/` by hand. It
  gains `aiwork/` and still has exactly one `.aitask-crews/`.
- Update the header comment.

`tests/test_setup_git.sh`, next to 27f/27g:
- **27f**: add `upgrade_store_gitignore_rules` to the failure loop (readonly
  and directory faults). It must be non-fatal, report "Could not add", make no
  "Added" or "already" claim, and make no commit.
- **27g'**: `upgrade_store_gitignore_rules` writes every rule and makes no
  commit. A second run reports "already" and duplicates nothing.
- **27h, parity**: in repo A run `setup_gate_logs_gitignore`,
  `setup_testmap_gitignore`, `setup_shadow_store_gitignore`,
  `setup_scratchpad_gitignore` and `setup_worktree_dirs_gitignore`. In repo B
  run `upgrade_store_gitignore_rules`. Both start from the same base, and the
  two `.gitignore` files must be byte-identical. This pins rules, comments and
  order against drift.
- **27i, drift guard**: extract every `setup_[a-z_]*gitignore` call from
  `main()` in `aitask_setup.sh`. Each one must be in the upgrade-covered set,
  or `setup_cache_gitignore`, or the explicit exclusion
  `setup_python_cache_gitignore`. A future setup-only rule then fails here
  until an upgrade route is decided for it.

## Part B — fail-closed `RecursionError` in trail loading

### B1. `.aitask-scripts/lib/trail_schema.py`

- `load_trail`: after the `except ValueError` branch, add
  ```python
  except RecursionError:
      raise TrailValidationError(
          [TrailIssue("$", "nesting",
                      "JSON nests too deeply to parse (%s)" % origin)])
  ```
- `validate_trail`: wrap the `_check_node` and `_semantic_checks` calls in
  `try/except RecursionError`. On that error, append
  `TrailIssue("$", "nesting", "document nests too deeply to validate")` and
  return the issues. Only `RecursionError` is caught. The interpreter's own
  `RuntimeError` for unsupported or unresolvable schema keywords still
  propagates, as before. Putting the fix in `validate_trail` covers its direct
  callers too: the CLI and `test_roadmap_integration`.
- `trail_discovery_cache.py:369` catches
  `(TrailValidationError, RecursionError)` and stays as it is. It is harmless
  defence in depth.

### B2. Tests

- `tests/test_trail_schema.py`, new class:
  - `load_trail(b"[" * 200000 + b"]" * 200000)` raises `TrailValidationError`
    with a `nesting` issue, not `RecursionError`.
  - The `gate_framework.json` fixture with `scope.topics` set to two 500-deep
    nested lists: `validate_trail` returns an issue list containing `nesting`,
    and `load_trail` of its bytes raises `TrailValidationError`.
  - The schema `RuntimeError` still propagates. This is already covered by
    existing tests; check that they still pass.
- `tests/test_trail_discovery.py` `LoadTrailBlobTests`: add a test where
  `fake_run` writes the deep payload to the `--out` path, with the **real**
  `load_trail`. Expect `doc is None`, an error of
  `"invalid trail document: 1 issue(s)"`, and no raise.

## Verification

- `bash tests/test_install_upgrade_dirty_baseline.sh` and
  `bash tests/test_setup_git.sh` both pass.
- **Red proof:** `INSTALL_SH=<pre-fix install.sh from git show HEAD:install.sh>`
  turns K red for the store rules. Running the new trail tests against the
  pre-fix `trail_schema.py` (a temporary copy, not git-restore) shows
  `RecursionError`.
- `python3 -m unittest tests.test_trail_schema tests.test_trail_discovery tests.test_trail_discovery_cache`
- `shellcheck .aitask-scripts/aitask_setup.sh install.sh`
- The full Python suite: `bash tests/run_all_python_tests.sh`; read the final
  verdict line.

## Step 9

Post-implementation: commit the code and plan separately, then archive via
the standard Step 9 flow (current branch, no merge).

## Risk

### Code-health risk: low
- The installer upgrade path gains one more never-fatal, `declare -F`-guarded
  write-only call. It is the same shape as the existing t2173_1 cache block,
  sits in the same position before `commit_installed_files`, and the existing
  K/K2 cases already exercise the dirty-baseline contract · severity: low · → mitigation: none needed (covered by plan tests K/K2/K3)
- The rule and comment strings are duplicated between the `setup_*` functions
  and `upgrade_store_gitignore_rules` · severity: low · → mitigation: none needed (parity test 27h + drift guard 27i are part of the plan)

### Goal-achievement risk: low
None identified. Both defects are reproduced and both fixes are covered by
red-provable tests. Adding the worktree rules goes beyond the task's four, and
the Context section calls this out for approval.
