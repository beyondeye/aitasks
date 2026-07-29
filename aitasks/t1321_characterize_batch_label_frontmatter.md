---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: test
status: Implementing
labels: [aitask-create, bash_scripts, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1312
implemented_with: claudecode/opus5
created_at: 2026-07-29 10:40
updated_at: 2026-07-29 11:51
---

## Origin

Risk-mitigation ("before") for t1312, created at Step 7 from the approved plan's risk evaluation.

## Risk addressed

Code-health — rewriting BATCH_LABELS changes emitted frontmatter. From the plan's `## Risk` section (aiplans/p1312_explore_label_autoadd_and_confirm.md): "Rewriting `BATCH_LABELS`/update inputs changes emitted frontmatter for non-canonical input · severity: medium".

t1312 will make `aitask_create.sh --batch` normalize the `--labels` CSV (trim, lowercase, replace invalid chars with `_`, dedupe) before it reaches `format_yaml_list`, and make `aitask_update.sh` normalize `--labels` / `--add-label` inputs the same way. That intentionally changes the emitted `labels:` frontmatter line for non-canonical inputs. This characterization test pins the CURRENT behavior first, so the normalization change lands against a known baseline and any unintended frontmatter drift (beyond the documented normalization) is caught.

## Goal

Write `tests/test_characterize_batch_label_frontmatter.sh` pinning today's `--batch --labels` frontmatter output across all three creation paths of `.aitask-scripts/aitask_create.sh`:

- **parent** (`--batch --commit`, via `create_task_file`, batch call site ~`:2066`)
- **child** (`--batch --commit --parent N`, via `create_child_task_file`, ~`:2035`)
- **draft** (`--batch` without `--commit`, via `create_draft_file`, ~`:2093`, file lands in gitignored `aitasks/new/`)

For each path, assert the exact `labels:` line emitted for these inputs (current pass-through behavior — `format_yaml_list` at `lib/task_utils.sh:414` is a pure `s/,/, /g` + bracket wrap, no split/trim/sanitize):

| # | input | current emitted line | why it is pinned |
|---|---|---|---|
| 1 | `--labels "ui,backend"` | `labels: [ui, backend]` | canonical — must NOT change under t1312 |
| 2 | `--labels "ui, backend"` | `labels: [ui,  backend]` | double space preserved (no trim) |
| 3 | `--labels "UI Stuff,foo-bar!"` | `labels: [UI Stuff, foo-bar!]` | verbatim (no case-fold, no sanitize) |
| 4 | `--labels ""` | `labels: []` | empty-input branch of `format_yaml_list` |
| 5 | `--labels "foo,FOO,foo"` | `labels: [foo, FOO, foo]` | **no dedupe today** — exact-dup *and* case-fold-dup both survive |
| 6 | `--labels "!!!"` | `labels: [!!!]` | **sanitizes to empty** under t1312's rule; today it passes through verbatim |

Rows 5-6 were added during implementation (see the plan's §0): the original
four-row table omitted **deduplication** and **sanitizes-to-empty**, both of
which t1312 explicitly changes, so a t1312 implementation could have got them
wrong with no before/after review record.

Also pin the two side-effect facts t1312 changes:
- `aitasks/metadata/labels.txt` is NOT written by any batch path today (assert byte-identical before/after).
- The task-creation commit does not contain `labels.txt` (assert via `git show --name-only --pretty=format: HEAD`). Exact expected contents are per-path: the **parent** commit holds only the task file; the **child** commit legitimately holds the child file *and* the parent file (`update_parent_children_to_implement` rewrites it); the **draft** path creates no commit at all.

Fixture: copy `setup_project` from `tests/test_anchor_create.sh:82-118` (bare remote + clone + `setup_fake_aitask_repo` + `aitask_claim_id.sh --init`); assertions from `tests/lib/asserts.sh`.

**When t1312 lands**, this test's expectations for the non-canonical rows (2, 3, 5, 6) are UPDATED IN THE SAME COMMIT as the normalization change (that is the point: the diff to this file becomes the reviewable record of exactly what changed — `[ui,  backend]` → `[ui, backend]`, `[UI Stuff, foo-bar!]` → `[ui_stuff, foo-bar_]`, `[foo, FOO, foo]` → whatever the dedupe rule collapses it to, `[!!!]` → whatever the sanitizer does with a token that reduces to the empty string... per the final sanitizer, and the labels.txt/commit-content expectations flip). Prove the test can fail (negative control): temporarily alter one expected string, run, confirm exit 1, restore.

## Verification

- `bash tests/test_characterize_batch_label_frontmatter.sh` → exit 0, all cases pass against CURRENT `aitask_create.sh`.
- Negative control demonstrated once (documented in the plan/notes).
- `shellcheck` clean on the new test file (info-level baseline OK).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-29T08:51:40Z status=pass attempt=1 type=human
