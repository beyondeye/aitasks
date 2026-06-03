---
Task: t923_4_migrate_regex_files.md
Parent Task: aitasks/t923_consolidate_test_assert_helpers_shared_lib.md
Sibling Tasks: aitasks/t923/t923_1_*.md, aitasks/t923/t923_2_*.md, aitasks/t923/t923_3_*.md, aitasks/t923/t923_5_*.md
Archived Sibling Plans: aiplans/archived/p923/p923_1_*.md, aiplans/archived/p923/p923_3_*.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-03 15:42
---

# Plan: Migrate regex (`grep -q` / `grep -qE`) files (t923_4)

Depends on 923_1/923_2/923_3 (all landed). **Read 923_1's plan for the API/recipe
and 923_3's notes for the two-dimensional needle-audit pattern.** This plan
reuses 923_1's proven block-removal/source-insertion recipe and the
`assert_migration_verify.sh` harness verbatim.

These files' inline `assert_contains` uses plain `grep -q` (case-sensitive
**regex**) or `grep -qE`. Call sites map to the shared **`assert_contains_re` /
`assert_not_contains_re`** (`grep -qE`) — UNLESS a needle audit shows the needle
contains no regex metacharacters used *as* regex, in which case the fixed-string
default `assert_contains` is behavior-equivalent (often *more* correct) and is
the right target.

## Verify-pass findings (2026-06-03 — re-checked against the current codebase)

- **Foundation present & reused as-is.** `tests/lib/asserts.sh` defines
  `assert_contains_re` (line 108) and `assert_not_contains_re` (line 119), both
  `grep -qE` with the t920 `--` guard, plus `assert_eq_trim`.
  `tests/lib/assert_migration_verify.sh` exists and is executable.
- **Regex bucket = exactly 24 files** (regenerated mechanically — the inline
  `assert_contains` files whose body uses `grep -q…` and is NOT `grep -qF`):
  `test_apply_initializer_output.sh`, `test_apply_initializer_tolerant.sh`,
  `test_archive_carryover.sh`, `test_archive_folded.sh`,
  `test_archive_related_issues.sh`, `test_archive_utils.sh`,
  `test_archive_verification_gate.sh`, `test_explain_cleanup.sh`,
  `test_explain_format_context.sh`, `test_extract_auto_naming.sh`,
  `test_init_data.sh`, `test_launch_mode_field.sh`, `test_plan_externalize.sh`,
  `test_plan_verified.sh`, `test_python_resolve_pypy.sh`, `test_python_resolve.sh`,
  `test_query.sh`, `test_resolve_tar_zst.sh`, `test_revert_analyze.sh`,
  `test_risk_mitigation_landed.sh`, `test_scan_profiles.sh`,
  `test_setup_find_modern_python.sh`, `test_skill_rerender.sh`, `test_task_push.sh`.
  (Regenerate in Step 1 — don't trust this hardcoded list.) 22 use plain
  `grep -q` (BRE); **2 use genuine `grep -qE`** (ERE): `test_setup_find_modern_python.sh`
  and `test_extract_auto_naming.sh`.
- **The 3 named "manual-inspection" files are now classified: all literal.** The
  parent flagged `test_add_model.sh`, `test_update_multiline_yaml.sh`,
  `test_yaml_utils.sh` as ambiguous because their `assert_contains` uses the
  **glob form** `[[ "$haystack" == *"$needle"* ]]` (no grep at all). With the
  needle quoted, that is a **literal substring** match — equivalent to fixed-string
  `grep -qF`. → They map to the **default `assert_contains`** (NOT `_re`).
- **FINDING (trim) — 6 regex-bucket files have a trimming inline `assert_eq`.**
  The plan body said nothing about trim; 923_3 explicitly warned "do not assume
  zero — re-run the probe." Probe result (inline `assert_eq` using `xargs`/`tr -d`,
  the macOS BSD `wc -l` padding absorber, 923_1 FINDING 4):
  `test_archive_carryover.sh`, `test_archive_folded.sh`,
  `test_archive_related_issues.sh`, `test_archive_verification_gate.sh`,
  `test_init_data.sh`, `test_task_push.sh`. **These 6 must remap their `assert_eq`
  call sites to `assert_eq_trim`** (regenerate the probe in Step 1).
- **FINDING (positive `_re`) — one genuine wildcard/anchor needle pre-identified.**
  `test_archive_carryover.sh:274`
  `assert_contains "Stub received --desc flag" "^--desc$" "$arg_log_contents"` —
  `^…$` line anchors are load-bearing under plain `grep -q`. → **`assert_contains_re`**
  (preserves the anchors). The harness backstops every other positive call: try
  the default fixed, and any wildcard that actually mattered shows a FAIL-count
  delta → switch that one call to `_re`.
- **FINDING (FINDING-D blind spot, `assert_not_contains`) — none need `_re`.** I
  scanned every `assert_not_contains` call site in the 24 files for metacharacters.
  All hits were either false positives (the `$` of `$output`/`$result` variables)
  or **literal-intended** needles — e.g. `test_explain_format_context.sh:205`
  `"Task: t100_auth.md"` (the `.` is a filename dot) and `test_scan_profiles.sh:188`
  `"PROFILE|bad.yaml"` (under BRE plain `-q`, `|` is already literal; the `.` is a
  filename dot). For `assert_not_contains`, collapsing those to fixed makes the
  match *stricter* and matches the literal intent, so the **default fixed
  `assert_not_contains` is safe and more correct**. No `_re` remap is warranted —
  but per 923_3 FINDING D, confirm these by reading the diff, not the harness
  (a regex→fixed downgrade on `not_contains` passes vacuously).

## Scope boundary vs 923_5 — DO NOT over-reach (read before implementing)

A re-scan shows **37 files still define `assert_contains` inline**, but only the
**24 regex + 3 named-literal trio (27 total)** are 923_4's job. The remaining 10
belong to **923_5** ("synonyms, stragglers, and final gates"). Do **not** migrate
these in 923_4 — flag them for 923_5 in the Final Notes:

- **3 `grep -qF` fixed stragglers** (newcomers, not regex):
  `test_opencode_setup.sh`, `test_skill_render_aitask_pickn.sh`,
  `test_skill_render_task_workflown.sh`.
- **7 glob-form (`[[ ==*…* ]]`, literal) newcomers** beyond the named trio:
  `test_multi_session_minimonitor.sh`, `test_multi_session_monitor.sh`,
  `test_multi_session_primitives.sh`, `test_resolve_detected_agent.sh`,
  `test_tui_switcher_footer_fit.sh`, `test_tui_switcher_multi_session.sh`,
  `test_verified_update_flags.sh`.

(923_5's final gate — "no inline `assert_contains()` except in `asserts.sh`" — will
catch these; 923_4 staying in scope keeps the boundary honest.)

## Step 1 — Regenerate the lists (don't trust the hardcoded sets above)

1. Regenerate the **24-file regex bucket** mechanically: inline-`assert_contains`
   files whose function body's `grep -q…` is not `-qF`. Confirm count = 24 and
   that exactly 2 are `grep -qE` (`test_setup_find_modern_python.sh`,
   `test_extract_auto_naming.sh`).
2. Confirm the **3 named files** are glob-form/literal (`test_add_model.sh`,
   `test_update_multiline_yaml.sh`, `test_yaml_utils.sh`) → default `assert_contains`.
3. Re-run the **trim probe** over the 27; confirm the 6 trim-eq files listed above.
4. Re-run the **metacharacter scan** over `assert_contains` / `assert_not_contains`
   call sites; confirm the single positive `_re` (`test_archive_carryover.sh:274`)
   and that no `assert_not_contains` needle is a genuine ERE-regex.

## Step 2 — Migrate in verified batches (~9/batch → 3 batches)

For each batch, per 923_1's recipe (block-removal/insertion with the **editor**,
never `sed -i`):

1. `tests/lib/assert_migration_verify.sh snapshot <baseline> <files...>`.
2. Per file:
   - Insert `. "$PROJECT_DIR/tests/lib/asserts.sh"` anchored on the `PROJECT_DIR`
     line (right after the `test_scaffold.sh` source when present, else right
     after the inline `PROJECT_DIR=…`).
   - Delete the inline defs the lib now provides (`assert_eq`, `assert_contains`,
     `assert_not_contains`, and any `assert_exit_*` / `assert_file_*` /
     `assert_dir_*` the file duplicates). **Keep** file-local `PASS=0/FAIL=0/TOTAL=0`,
     single-use/domain helpers, and synonym-named exit helpers (923_5's job).
   - **Needle audit + remap** per call:
     - Genuine regex needle (anchors `^`/`$`, `.`/`.*` used as wildcard, char
       class `[…]`, or ERE `( ) | + ? { }` in a `-qE` file) → `assert_contains_re`
       / `assert_not_contains_re`. Known: `test_archive_carryover.sh:274` `^--desc$`.
     - Literal needle (no metachar, or `.`/`|` plainly meant literally like
       `t42.md`) → default fixed `assert_contains` / `assert_not_contains`
       (fixed is *more* correct there).
     - The 3 glob-form files → default fixed `assert_contains`.
   - **Trim remap:** the 6 trim-eq files → `assert_eq` call sites become
     `assert_eq_trim`.
3. `tests/lib/assert_migration_verify.sh check <baseline> <files...>` — FAIL count
   + exit status MUST be identical per file. A delta means a metacharacter
   mattered → switch that call to `_re` (or fix a latent test bug — note it).
   **Remember the FINDING-D blind spot:** a green check does NOT prove an
   `assert_not_contains` regex needle was handled — read those remaps in the diff.
4. `shellcheck` a sample (modulo the benign SC1091 info note from the new dynamic
   `source` line).
5. Commit the batch with plain `git`:
   `refactor: Consolidate regex assert helpers, batch N (t923_4)`.

## Step 3 — Verify

- Standalone FAIL-count + exit identical before vs after for every migrated file
  (the harness is the gate).
- The 3 named files correctly classified (literal → default) and migrated.
- `grep -rlE '^assert_contains\(\)' tests/` lists none of the 27 migrated files
  (only `tests/lib/asserts.sh` and the 10 files explicitly deferred to 923_5).
- `test_archive_carryover.sh:274` uses `assert_contains_re`; confirm by reading
  the diff, not just the harness.
- `shellcheck` clean on a sample.

## Glob→grep caveat (audit the 3 named files)

`[[ $h == *"$n"* ]]` matches across embedded newlines and treats an empty needle
as always-true; `grep -qF` is per-line and `grep -qF -- ""` matches any non-empty
line. For the 3 glob-form files, confirm no needle contains an embedded newline or
is empty before mapping to fixed. The harness backstops (count delta), but flag any
such needle and keep it on a behavior-preserving form if found.

## Risk

### Code-health risk: low
- Blast radius is 27 files, but each change is a pure, mechanical, individually
  harness-gated consolidation (FAIL-count + exit must match before/after). No
  structural stragglers in this bucket (all 27 define `PROJECT_DIR` before the
  first helper block). · severity: low · → mitigation: in-task verify harness
  (923_1 deliverable), per batch.

### Goal-achievement risk: low
- **Regex/glob → fixed semantic drift.** Mapping `grep -q` (BRE regex) or
  `[[ ==*…* ]]` (glob) call sites to fixed `grep -qF` can neutralize a
  metacharacter; for `assert_not_contains` the harness does **not** catch the
  drift (vacuous pass, 923_3 FINDING D). · severity: low (after mitigation) ·
  → mitigation: the needle audit in Step 2 with the `_re` escape hatch, the
  by-hand audit of `assert_not_contains` needles (already pre-scanned this pass —
  all literal), the one pre-identified positive `_re` remap, and the count harness
  backstopping the positive-`contains` direction.
- **Trim files (`assert_eq_trim`).** 6 files trim whitespace to absorb macOS BSD
  `wc -l` padding; collapsing them onto the non-trimming `assert_eq` would break
  on macOS only. · severity: low · → mitigation: remap those 6 to `assert_eq_trim`
  (probe re-run in Step 1); harness is the backstop on Linux.

_No before/after mitigation tasks: the principal risk (semantic drift across the
bucket) is mitigated in-task by the needle audit + 923_1's verification harness,
re-run on every migrated file. Mirrors 923_1/923_2/923_3's framing._

## Final Implementation Notes (fill in at Step 8)

Classification of the 3 named files; the genuine-regex needle(s) mapped to `_re`;
the 6 trim-eq remaps; any latent bug surfaced (→ "Upstream defects identified");
and **the 10 files deferred to 923_5** (3 fixed stragglers + 7 glob newcomers) so
923_5's final gate has them enumerated.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
