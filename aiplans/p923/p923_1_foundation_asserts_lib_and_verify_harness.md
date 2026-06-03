---
Task: t923_1_foundation_asserts_lib_and_verify_harness.md
Parent Task: aitasks/t923_consolidate_test_assert_helpers_shared_lib.md
Sibling Tasks: aitasks/t923/t923_2_migrate_fixed_string_files.md, aitasks/t923/t923_3_migrate_case_insensitive_files.md, aitasks/t923/t923_4_migrate_regex_files.md, aitasks/t923/t923_5_synonyms_stragglers_and_final_gates.md
Archived Sibling Plans: aiplans/archived/p923/p923_*_*.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-03 12:09
---

# Plan: Foundation — shared asserts lib + verify harness + pilot (t923_1)

Foundation for the t923 consolidation. Builds the shared library, the
before/after verification harness, and migrates a ~10-file pilot. Siblings
923_2..5 depend on the API and recipe established here.

## Context

t920 added a `--` end-of-options guard to the `grep` in `assert_contains` /
`assert_not_contains` across the test suite — and had to do so in ~70 separate
inline copies because there is **no shared assert library**. Every
`tests/test_*.sh` redefines its own helpers. This foundation child builds the
shared lib + a before/after verification safety net + a small pilot to prove
the pattern; siblings 923_2..5 do the bulk migration, each depending on this
child's API and recipe.

## Verify-pass findings (2026-06-03 — codebase re-checked against the plan)

- **State confirmed:** `tests/lib/asserts.sh` and `tests/lib/assert_migration_verify.sh`
  do **not** exist yet. `tests/lib/` holds `test_scaffold.sh`, `require_no_tmux.sh`,
  `venv_python.sh`. 168 `tests/test_*.sh`; **136** define `assert_contains()` inline.
- **Buckets confirmed (matches parent):** fixed `-qF` = 66, case-insensitive
  (`-qi`/`-qiF`) = 33, regex (`-qE`/plain `-q`) = 26, `other` = 4 (manual
  flavor inspection — handled in 923_5). Bucketing command from the parent task
  reproduces these.
- **Sourcing pattern confirmed:** files source the scaffold via the absolute
  `$PROJECT_DIR` path before any `cd`:
  `. "$PROJECT_DIR/tests/lib/test_scaffold.sh"` (with `SCRIPT_DIR`/`PROJECT_DIR`
  computed at the top). `asserts.sh` is inserted on the line immediately after.
- **FINDING 1 — corrected pilot exemplar:** the original plan suggested
  `test_claim_id.sh` as a *fixed-string* exemplar, but its inline
  `assert_contains` is `echo "$actual" | grep -qi -- "$expected"` — **case-insensitive
  regex** (`-qi`, not `-qF`). It belongs in the `_ci` bucket. Use real `-qF`
  fixed exemplars instead: `test_agent_instructions.sh`, `test_aitask_merge.sh`,
  `test_aitask_projects_remove.sh` / `_doctor.sh` / `_prune.sh` / `_update.sh`
  (these use the here-string form `grep -qF -- "$needle" <<< "$haystack"`).
  Regex `-qE` exemplar: `test_keybinding_registry.sh`.
- **FINDING 2 — summary-line formats vary widely.** Only ~49/168 files emit the
  canonical `Results: $PASS passed, $FAIL failed, $TOTAL total`; others vary
  (`$PASS passed, $FAIL failed` without "Results:", `out of $TOTAL total`,
  lowercase `$fail`, `$FAILS`, or no machine-parseable summary at all). The
  harness must therefore treat **`^FAIL:` line count + process exit status as
  the PRIMARY signal**, with summary-line parsing as a best-effort secondary —
  not the other way around.
- **FINDING 3 — invocation variants:** inline `assert_contains` bodies come in
  two shapes — `echo "$actual" | grep …` and `grep … <<< "$haystack"`. Both
  append a trailing newline; the lib's `printf '%s' "$haystack" | grep …` does
  **not**. Keep the needle-audit caveat (Step 1 note) for needles that rely on
  a trailing-newline match.
- **FINDING 4 — macOS-driven `assert_eq` drift (20 files trim whitespace).**
  20 of the inline `assert_eq` definitions trim their args via `xargs`/`tr -d`
  (e.g. `test_sync.sh`, `test_task_git.sh`, `test_data_branch_setup.sh`, the
  `test_archive_*` family). This exists specifically to absorb BSD `wc -l`'s
  leading-space padding on macOS (see `aidocs/framework/sed_macos_issues.md`
  "wc -l Output Whitespace"). The shared draft `assert_eq` does **not** trim —
  migrating a trimming file to it would silently change behavior on macOS
  (a `wc -l`-derived count would no longer string-equal a bare number). This is
  the foundation's most important drift decision because all four migration
  siblings inherit it. **Resolution (this task):** add a named
  `assert_eq_trim` variant to the lib (parallel to the `_ci`/`_re` pattern),
  include ≥1 trimming-`assert_eq` file in the pilot, and document the mapping
  rule for siblings: *a file whose inline `assert_eq` trims → remap its
  `assert_eq` call sites to `assert_eq_trim`; non-trimming files stay on the
  default.* The harness (Step 2) is the backstop — any count divergence on a
  mis-mapped file is caught before commit.

## macOS / BSD portability (must hold — this lib runs on every contributor's machine)

The parent task mandates BSD-safe code; concretely for this task:

- **`asserts.sh`:** every grep flag used (`-qF`, `-qiF`, `-qE`, and the t920
  `--` guard) is BSD-safe. No `sed`, `date -d`, `mktemp`, or `base64` in the
  lib. Use only bash-3.2-safe constructs (no `mapfile`/`readarray`,
  `declare -A`, or `${var^^}` — none are needed). Shebang `#!/usr/bin/env bash`.
- **`assert_migration_verify.sh` (the main new BSD surface):**
  - `grep -c '^FAIL:'` exits **1 on zero matches** — under `set -euo pipefail`
    that aborts. Guard it: `count=$(grep -c '^FAIL:' <<<"$out" || true)`.
  - `wc -l` pads with leading spaces on BSD — keep counts in arithmetic
    contexts, or trim with `tr -d ' '`/`xargs` before any string compare.
  - No `mapfile`/`readarray` (bash-4 only) — use a `while read` loop.
  - Temp baseline via the template form `mktemp "${TMPDIR:-/tmp}/ait_assert_XXXXXX"`
    (never `--suffix`); if any temp **dir** path is later compared, canonicalize
    with `pwd -P` (t658 lesson). Plain `date '+…'` only (never `date -d`).
  - No `grep -P`; no `sed -i` (if in-place editing is ever needed, source
    `.aitask-scripts/lib/terminal_compat.sh` and use `sed_inplace`).
- **Pilot migration (Step 3):** perform inline-block removal with the editor,
  **not** `sed -i`, to sidestep BSD-sed entirely. Do not source
  `terminal_compat.sh` into test files just for this.

## Design decisions (locked at parent planning)

- `assert_contains` / `assert_not_contains` default to **fixed-string**
  (`grep -qF`). Explicit named variants `_ci` (case-insensitive, `grep -qiF`)
  and `_re` (extended-regex, `grep -qE`) absorb the other two flavors found in
  the suite. Later children remap each file's call sites to the variant
  matching that file's original inline flavor.
- Functions only; counters (`PASS`/`FAIL`/`TOTAL`) stay file-local and are
  referenced by the lib as globals.
- Scope: consolidate only the genuinely-duplicated **core** helpers. Single-use
  domain helpers stay inline. Synonym-named exit helpers handled in 923_5.

## Step 1 — Create `tests/lib/asserts.sh`

Draft (refine wording to match the dominant existing messages):

```bash
#!/usr/bin/env bash
# tests/lib/asserts.sh — shared assertion helpers for the test suite.
# Source AFTER tests/lib/test_scaffold.sh, via the absolute $PROJECT_DIR path.
# Functions mutate the caller's file-global PASS / FAIL / TOTAL counters.
# BSD-safe (no GNU-only grep/sed flags). See aidocs/framework/sed_macos_issues.md.

[[ -n "${_AIT_ASSERTS_LOADED:-}" ]] && return 0
_AIT_ASSERTS_LOADED=1

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

# Whitespace-trimming variant — absorbs BSD `wc -l` leading-space padding on
# macOS (see FINDING 4). Migrate files whose inline assert_eq trimmed (xargs/tr)
# to this; leave non-trimming files on the default assert_eq above.
assert_eq_trim() {
    local desc="$1" expected actual
    expected="$(printf '%s' "$2" | xargs)" actual="$(printf '%s' "$3" | xargs)"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

# --- substring / pattern containment ---------------------------------------
# Default: fixed-string (literal) match. Use _ci for case-insensitive,
# _re for extended-regex. All carry the t920 `--` end-of-options guard.

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$needle', got '$haystack')"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output NOT containing '$needle', got '$haystack')"
    else
        PASS=$((PASS + 1))
    fi
}

assert_contains_ci()      { local d="$1" n="$2" h="$3"; TOTAL=$((TOTAL+1)); if printf '%s' "$h" | grep -qiF -- "$n"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (expected output containing (ci) '$n', got '$h')"; fi; }
assert_not_contains_ci()  { local d="$1" n="$2" h="$3"; TOTAL=$((TOTAL+1)); if printf '%s' "$h" | grep -qiF -- "$n"; then FAIL=$((FAIL+1)); echo "FAIL: $d (expected output NOT containing (ci) '$n', got '$h')"; else PASS=$((PASS+1)); fi; }
assert_contains_re()      { local d="$1" n="$2" h="$3"; TOTAL=$((TOTAL+1)); if printf '%s' "$h" | grep -qE -- "$n"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (expected output matching /$n/, got '$h')"; fi; }
assert_not_contains_re()  { local d="$1" n="$2" h="$3"; TOTAL=$((TOTAL+1)); if printf '%s' "$h" | grep -qE -- "$n"; then FAIL=$((FAIL+1)); echo "FAIL: $d (expected output NOT matching /$n/, got '$h')"; else PASS=$((PASS+1)); fi; }

# --- exit-code -------------------------------------------------------------
assert_exit_zero() {
    local desc="$1"; shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: $desc (command exited non-zero)"; fi
}

assert_exit_nonzero() {
    local desc="$1"; shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then FAIL=$((FAIL + 1)); echo "FAIL: $desc (expected non-zero exit, got 0)"; else PASS=$((PASS + 1)); fi
}

# --- filesystem ------------------------------------------------------------
assert_file_exists()     { local d="$1" p="$2"; TOTAL=$((TOTAL+1)); if [[ -f "$p" ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (file not found: $p)"; fi; }
assert_file_not_exists() { local d="$1" p="$2"; TOTAL=$((TOTAL+1)); if [[ ! -f "$p" ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (file unexpectedly exists: $p)"; fi; }
assert_dir_exists()      { local d="$1" p="$2"; TOTAL=$((TOTAL+1)); if [[ -d "$p" ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (dir not found: $p)"; fi; }
assert_dir_not_exists()  { local d="$1" p="$2"; TOTAL=$((TOTAL+1)); if [[ ! -d "$p" ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (dir unexpectedly exists: $p)"; fi; }
```

**IMPORTANT — match existing semantics, then verify empirically:** before
finalizing the FAIL-message wording and the exact `[[ -f ]]` / arg signatures,
diff against the real inline definitions of the pilot files. The existing
`assert_contains` used `echo "$actual" | grep …` (or `<<< "$haystack"`);
`printf '%s'` avoids `echo` backslash/`-n` surprises but verify it does not
change matching for needles that relied on a trailing newline (see FINDING 3).
If any pilot count shifts, reconcile the lib to the real behavior (the lib must
match what files rely on, not the other way around).

## Step 2 — Create `tests/lib/assert_migration_verify.sh`

A before/after counts harness. Suggested interface:

```
assert_migration_verify.sh snapshot <baseline_file> <test_file>...   # Mode A
assert_migration_verify.sh check    <baseline_file> <test_file>...    # Mode B
```

- Runs each `<test_file>` standalone (`bash "$f"`), captures stdout+exit status.
  **PRIMARY signal (per FINDING 2): count `^FAIL:` lines and record the process
  exit status.** As a best-effort secondary, also try to parse a summary line
  (multiple formats: `Results: N passed, N failed, N total`,
  `N passed, N failed`, `… out of N total`) — but never depend on it, since
  ~119/168 files lack the canonical form.
- `snapshot` writes `relpath|PASS|FAIL|TOTAL|EXIT` per file to the baseline
  (use the FAIL-line count for FAIL; derive PASS/TOTAL from the summary when
  available, else leave `-`).
- `check` re-runs and diffs against the baseline; prints any `CHANGED:<file> …`
  line and exits nonzero if the FAIL count or exit status differs.
- Self-contained, BSD-safe, `set -euo pipefail`, `#!/usr/bin/env bash`.
- Run files individually (NOT batched) to avoid the ~6 known cross-contamination
  failures noted in t920.

## Step 3 — Pilot migration (~10 files)

Pick a spread across flavors (buckets confirmed above). Use the **corrected**
exemplars from FINDING 1:
- ~4 fixed (`-qF`): e.g. `test_agent_instructions.sh`, `test_aitask_merge.sh`,
  `test_aitask_projects_remove.sh`, `test_aitask_projects_doctor.sh`.
- ~3 case-insensitive (`-qi`): e.g. `test_claim_id.sh` (the original
  "fixed" suggestion — actually `_ci`), plus two more from the ci bucket.
- ~3 regex (`-qE`/plain `-q`): e.g. `test_keybinding_registry.sh` plus two more.
- Include at least one file that also defines exit/file helpers.
- Include at least one **trimming-`assert_eq`** file (FINDING 4) — e.g.
  `test_sync.sh` or `test_task_git.sh` — to exercise the `assert_eq_trim` remap
  and prove macOS counts hold.

Per file:
1. `snapshot` the file into a pilot baseline.
2. Insert `. "$PROJECT_DIR/tests/lib/asserts.sh"` right after the existing
   `. "$PROJECT_DIR/tests/lib/test_scaffold.sh"` line.
3. Delete the inline defs now provided by the lib; keep file-local
   `PASS=0/FAIL=0/TOTAL=0` and any single-use/domain helpers.
4. Remap call sites: `_ci` for case-insensitive files, `_re` for regex files
   (with needle audit — literal/correct-case needles can stay on the default);
   `assert_eq` → `assert_eq_trim` for files whose inline `assert_eq` trimmed.
5. `check` against the baseline — counts MUST match (on macOS too — the
   trim/`wc -l` interplay is the likeliest source of a divergence).

## Step 4 — Verify

- `shellcheck tests/lib/asserts.sh tests/lib/assert_migration_verify.sh` clean
  (modulo pre-existing info notes).
- All pilot files: standalone counts identical before vs after (via the harness).
- `grep -nE '^assert_contains\(\)' tests/lib/asserts.sh` → exactly one; pilot
  files no longer define it inline.

## Risk

### Code-health risk: medium
- Shared lib API + source-insertion recipe are load-bearing — siblings 923_2..5
  inherit them; a wrong API shape or semantic drift here propagates across the
  whole suite. · severity: medium · → mitigation: in-task verify harness (built
  in Step 2, re-run on every pilot file in Step 3)
- `printf '%s'` (lib) vs `echo`/`<<<` (inline) trailing-newline difference, and
  `_ci` remap turning `-qi` regex into `-qiF` fixed, could change matching for
  some needles. · severity: medium · → mitigation: needle audit (Step 1 note) +
  before/after count check (harness)
- macOS-only behavior change: 20 files' inline `assert_eq` trims whitespace to
  absorb BSD `wc -l` padding (FINDING 4); collapsing them onto a non-trimming
  shared `assert_eq` would break those tests on macOS. · severity: medium ·
  → mitigation: dedicated `assert_eq_trim` variant + sibling mapping rule +
  trim-file in the pilot, all backed by the harness

### Goal-achievement risk: low
- Varied test summary-line formats (FINDING 2) could make a naive harness
  miscount. · severity: low · → mitigation: harness uses `^FAIL:` line count +
  exit status as the primary signal, not summary parsing
- None otherwise: goal is well-scoped and the approach was validated against
  the current codebase during this verify pass.

_No separate before/after mitigation tasks: the principal code-health risk is
mitigated in-task by the verification harness, which is this task's own
deliverable._

## Final Implementation Notes (siblings 923_2..5 depend on this — read it)

### What was built

- **`tests/lib/asserts.sh`** — the canonical shared helpers. Final API (functions
  only; mutate caller's file-local `PASS`/`FAIL`/`TOTAL`; double-source-guarded
  with `_AIT_ASSERTS_LOADED`; BSD/bash-3.2-safe; t920 `--` guard on every grep):
  - `assert_eq(desc, expected, actual)` — exact `[[ == ]]`.
  - `assert_eq_trim(desc, expected, actual)` — trims both args via
    `printf '%s' | xargs`. **Use for files whose inline `assert_eq` trimmed
    (`xargs`/`tr`).** Exists to absorb BSD `wc -l` leading-space padding on macOS.
  - `assert_contains` / `assert_not_contains` — fixed-string (`grep -qF`).
  - `assert_contains_ci` / `assert_not_contains_ci` — case-insensitive fixed
    (`grep -qiF`).
  - `assert_contains_re` / `assert_not_contains_re` — extended-regex (`grep -qE`).
  - `assert_exit_zero` / `assert_exit_nonzero` (cmd...).
  - `assert_file_exists` / `assert_file_not_exists` / `assert_dir_exists` /
    `assert_dir_not_exists` (desc, path).
- **`tests/lib/assert_migration_verify.sh`** — the before/after safety net.
  Invocation:
  ```
  tests/lib/assert_migration_verify.sh snapshot <baseline> <file>...   # BEFORE migrating
  tests/lib/assert_migration_verify.sh check    <baseline> <file>...   # AFTER  migrating
  ```
  Records `relpath|PASS|FAIL|TOTAL|EXIT`; **`check` fails only on a FAIL-count or
  EXIT-status change** (PASS/TOTAL are context-only because summary formats vary —
  see FINDING 2). Runs each file standalone. Reuse this harness verbatim.

### The migration recipe (per file) — proven on the 10-file pilot

1. `snapshot` the file into a baseline first.
2. Insert `. "$PROJECT_DIR/tests/lib/asserts.sh"` **immediately after the line
   that defines/sources `PROJECT_DIR`** (for most files that is right after
   `. "$PROJECT_DIR/tests/lib/test_scaffold.sh"`; **but many files don't source
   the scaffold at all** — they compute `PROJECT_DIR` inline. Anchor on
   `PROJECT_DIR`, not the scaffold line).
3. Delete the inline defs the lib now provides. **Keep** file-local
   `PASS=0/FAIL=0/TOTAL=0` and any single-use/domain helpers
   (`assert_exit_code`, `assert_file_contains`, …) — those stay inline.
4. Remap call sites to the variant matching the file's **original** flavor:
   - inline `grep -qi…` → `assert_contains_ci` (after needle audit).
   - inline `grep -qE` or plain `grep -q` (regex) → `assert_contains_re`.
   - inline `grep -qF` (fixed) → default `assert_contains` (no remap).
   - inline `assert_eq` that trimmed → `assert_eq_trim`.
5. `check` against the baseline — FAIL count + EXIT must be identical.

### Key facts / gotchas for siblings

- **Counts are wording-independent.** Migration is count-neutral as long as each
  assertion's *match condition* is preserved; the lib's FAIL-message wording need
  not match the old inline wording (the FAIL branch only runs on failure, which
  the harness counts). So don't fret over message text — fret over the grep flag
  and the trim behavior.
- **Needle audit (BRE vs ERE).** Files using **plain `grep -q`** are BRE; the
  `_re` variant is `grep -qE` (ERE). They agree **only when needles contain no
  ERE-only metacharacters** (`+ ? | ( ) { }`). The pilot's plain-`-q` files
  (`test_sync`, `test_archive_scan`) had only literal needles + `.` wildcards
  (identical in BRE/ERE), so `_re` was safe. **Audit each plain-`-q` file's
  needles**; if any use `+?|(){}` literally, escape them or keep that call on a
  fixed variant. Literal/correct-case needles may also just stay on the default
  fixed `assert_contains`.
- **`printf '%s'` vs `echo`/`<<<`.** The lib uses `printf '%s' "$haystack" | grep`
  (no trailing newline). Inline helpers used `echo …|` or `<<< …` (trailing
  newline). Immaterial for substring containment; no pilot count shifted.
- **Parent plan correction:** `test_claim_id.sh` was suggested as a *fixed*
  exemplar but is actually `-qi` (case-insensitive) → it migrated to
  `assert_contains_ci`. Real fixed `-qF` exemplars: `test_agent_instructions.sh`,
  `test_aitask_merge.sh`, `test_aitask_projects_{doctor,remove}.sh`.

### Pilot set migrated (all count-identical before/after)

Fixed: `test_aitask_merge.sh`, `test_agent_instructions.sh`,
`test_aitask_projects_doctor.sh`, `test_aitask_projects_remove.sh`.
CI: `test_claim_id.sh`, `test_task_git.sh` (also trim-eq), `test_agent_string.sh`.
Regex: `test_keybinding_registry.sh` (`-qE`), `test_sync.sh` (plain-`-q` + trim-eq
+ file-helper), `test_archive_scan.sh` (plain-`-q`). Net −143 lines.

### Upstream defects identified

None.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
