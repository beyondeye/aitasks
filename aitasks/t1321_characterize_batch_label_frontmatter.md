---
priority: medium
effort: low
depends: []
issue_type: test
status: Implementing
labels: [aitask-create, bash_scripts, testing]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1312
created_at: 2026-07-29 10:40
updated_at: 2026-07-29 10:42
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

| input | current emitted line |
|---|---|
| `--labels "ui,backend"` | `labels: [ui, backend]` |
| `--labels "ui, backend"` | `labels: [ui,  backend]` (double space preserved) |
| `--labels "UI Stuff,foo-bar!"` | `labels: [UI Stuff, foo-bar!]` (verbatim) |
| `--labels ""` | `labels: []` |

Also pin the two side-effect facts t1312 changes:
- `aitasks/metadata/labels.txt` is NOT written by any batch path today (assert byte-identical before/after).
- The task-creation commit contains only the task file (assert via `git show --name-only --pretty=format: HEAD`; `labels.txt` absent).

Fixture: copy `setup_project` from `tests/test_anchor_create.sh:82-118` (bare remote + clone + `setup_fake_aitask_repo` + `aitask_claim_id.sh --init`); assertions from `tests/lib/asserts.sh`.

**When t1312 lands**, this test's expectations for the non-canonical rows are UPDATED IN THE SAME COMMIT as the normalization change (that is the point: the diff to this file becomes the reviewable record of exactly what changed — `[ui,  backend]` → `[ui, backend]`, `[UI Stuff, foo-bar!]` → `[ui_stuff, foo-bar_]`... per the final sanitizer, and the labels.txt/commit-content expectations flip). Prove the test can fail (negative control): temporarily alter one expected string, run, confirm exit 1, restore.

## Verification

- `bash tests/test_characterize_batch_label_frontmatter.sh` → exit 0, all cases pass against CURRENT `aitask_create.sh`.
- Negative control demonstrated once (documented in the plan/notes).
- `shellcheck` clean on the new test file (info-level baseline OK).
