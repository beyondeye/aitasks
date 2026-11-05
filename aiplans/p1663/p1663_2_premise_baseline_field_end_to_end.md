---
Task: t1663_2_premise_baseline_field_end_to_end.md
Parent Task: aitasks/t1663_advisory_task_premise_staleness.md
Sibling Tasks: aitasks/t1663/t1663_3_creation_time_seeding_and_carryover.md, aitasks/t1663/t1663_4_workflow_check6_premise_procedure.md, aitasks/t1663/t1663_5_website_docs_premise_staleness.md, aitasks/t1663/t1663_6_retrospective_prompt_rate_evaluation.md
Archived Sibling Plans: aiplans/archived/p1663/p1663_1_premise_core_engine_and_producer.md
Base branch: main
Output branch: main
---

# t1663_2 — `premise_baseline:` frontmatter field, end to end

## Context

t1663_1 shipped the premise-staleness reader (`aitask_premise_stale.sh check`
+ `lib/task_premise.py`). It reads `premise_baseline: <sha> @ <YYYY-MM-DD HH:MM>`
from a task, but nothing can write that field yet: `aitask_update.sh` drops any
key its allowlist parser does not know on the next rewrite, and the sync merge
driver would resolve it by presence (a cleared baseline resurrects) or by
`updated_at` (an unrelated `--status` edit wins it). This task makes the field
a first-class frontmatter field: writer flag, merge rule, extension-point
sweep, a contract test, and the doc surfaces. Design record:
`aidocs/framework/task_premise_staleness.md` ("Field", "Baseline lifecycle").

Decided inputs (from the design record, the t1663_1 sibling notes and the
t1663_1 inbox note, re-verified against the tree):
- The reader accepts only a YAML **string** whose sha half is a full 40- or
  64-hex object id; symbols (`HEAD`, a branch, `abc1234`, `<sha>^`) read
  `SKIP`/`invalid_baseline`. So the writer stores a full lowercase oid and
  always keeps the ` @ <ts>` suffix (which also keeps the value a YAML string —
  an all-digit sha alone would parse as an int).
- Update-path only, like `plan_approved_at`: no `aitask_create.sh` flag
  (t1663_3 adds automatic creation-time seeding separately).
- Read surfaces (`ait ls -v`, board badge/detail row) are deferred to t1663_6 by
  the design record, so no board layer-3 widget here. The board must only
  *preserve* the field (verified: `task_yaml.serialize_frontmatter` round-trips
  `<hex> @ <ts>` byte-identically, including all-digit and uppercase shas).
- Fold: scalar, primary keeps its own — no-op comment, same as
  `plan_approved_at` (the lifecycle table says a fold union must NOT write it).

## Implementation

### 1. Promote the opaque-scalar normalizer (`lib/opaque_scalar.py`, new)

`board/aitask_merge.py:_normalize_opaque_scalar` already serves
`verification_baseline` and `plan_approved_at`; its docstring says the third
such field promotes it instead of adding another copy.

- New stdlib-only leaf module `.aitask-scripts/lib/opaque_scalar.py` with a
  public `normalize_opaque_scalar(raw) -> str` — same body and docstring
  contract (absent / `None` / non-`str` / blank → `""`; real value verbatim,
  never stripped). Module docstring records why it exists (shared comparison
  contract for tombstone-less scalars with no vocabulary of their own) and why
  `followup_kinds.normalize_followup_kind` and
  `board_groups.normalize_group_slug` are NOT rewired onto it (their contracts
  are their vocabularies'; and `followup_kinds.py` is sourced-on-startup through
  the bash bridge and copied into test scaffolds by closure — changing its
  import graph is out of scope).
- `aitask_merge.py`: delete the local def, `from opaque_scalar import
  normalize_opaque_scalar` beside the other lib imports (after the
  `sys.path.insert`), use it for all three entries. Lib placement is safe for
  every fixture: the sync/merge fixtures copy the whole `.aitask-scripts/` tree
  (`tests/test_sync_branch_mode_automerge.sh:119`), and the merge tests import
  via `lib/` on `sys.path`.
- Update the stale references: `board/board_widgets.py` `_plan_approved_marker`
  docstring (`board/aitask_merge.py:151` → `lib/opaque_scalar.py`),
  `tests/test_board_plan_approved_marker.py::test_it_is_not_normalize_opaque_scalar`
  (import from `opaque_scalar`), `tests/test_aitask_merge.py::test_opaque_scalar_normalizer_semantics`
  (import from `opaque_scalar`).

### 2. Merge rule — `board/aitask_merge.py`

- Add `"premise_baseline": (normalize_opaque_scalar, True)` to
  `_BASE_AWARE_FIELDS`, with a rationale paragraph in the existing comment
  block: same two failure modes as `verification_baseline` (presence-based
  merge resurrects a baseline that was cleared/dismissed; `updated_at`-newer
  lets an unrelated edit win a field it never touched); `deletion_aware=True`
  because clearing removes the key; divergent advances on both sides fail
  closed to PARTIAL (two different `CHECKED:` shas are two different review
  claims, never guessed between).

### 3. Writer — `.aitask-scripts/aitask_update.sh`

Mirror the `--verification-baseline` / `--plan-approved-at` threading exactly:

- Globals: `BATCH_PREMISE_BASELINE=""`, `BATCH_PREMISE_BASELINE_SET=false`
  (beside :98-101); `CURRENT_PREMISE_BASELINE=""` (beside :159 and the reset at
  :509).
- Help text: new "Premise baseline (batch mode)" block after the deferred-plan
  marker block: value forms, `""` clears, read by `aitask_premise_stale.sh`.
- `parse_args`: `--premise-baseline) BATCH_PREMISE_BASELINE="$2"; BATCH_PREMISE_BASELINE_SET=true; shift 2 ;;`
- `parse_yaml_frontmatter` case: `premise_baseline) CURRENT_PREMISE_BASELINE="$value" ;;`
- `write_task_file`: positional **36** `local premise_baseline="${36:-}"`
  (appended, same comment pattern), emitted right after `plan_approved_at`
  as `premise_baseline: $premise_baseline` only when non-empty (no tombstone).
- All 3 `write_task_file` call sites forward it (`"$CURRENT_PREMISE_BASELINE"`
  in the parent child-completion and interactive paths, `"$new_premise_baseline"`
  in batch); add `saved_premise_baseline` to the child-completion
  save/restore block.
- `has_update` line for `BATCH_PREMISE_BASELINE_SET`.
- **Validation in `main()`**, beside the `--followup-kind` check (after
  `parse_args`, before any file is touched — so a rejection leaves the task
  file and `labels.txt` byte-unchanged). A function `normalize_premise_baseline`
  that sets `BATCH_PREMISE_BASELINE` in place and `die`s directly (never called
  inside `$( )`):
  - `""` → clear (no validation).
  - `<oid>` (40 or 64 hex, any case) → `<lowercase oid> @ $(get_timestamp)`
    (one timestamp home, like `--plan-approved-at now`).
  - `<oid> @ <YYYY-MM-DD HH:MM>` → lowercase oid, timestamp kept.
  - anything else → `die "Invalid --premise-baseline value ... (expected a full
    commit id, optionally followed by ' @ YYYY-MM-DD HH:MM', or \"\" to clear;
    resolve a revision with: git rev-parse --verify <rev>^{commit})"`.
    Symbols are rejected, never resolved: the design requires writing the
    `CHECKED:` sha, never write-time HEAD.
  - then `git cat-file -e "<oid>^{commit}"` must succeed, else
    `die "... is not a commit in this repository"` (also covers a 64-hex id in
    a SHA-1 repo and a non-repo cwd). Runs in the process that owns the task
    tree (the `--project` redirect re-execs in the target root first).
- The interactive path writes nothing new (update-only batch flag); it only
  preserves `CURRENT_PREMISE_BASELINE`.

### 4. Fold — `.aitask-scripts/aitask_fold_mark.sh`

No-op comment after the `plan_approved_at` one: scalar, NOT unioned/merged on
fold; a folded task's baseline describes a different premise, and adopting it
would claim the primary's premise was reviewed at a commit nobody reviewed it at.

### 5. Documentation surfaces (extension-points layer 5)

- `seed/aitasks_agent_instructions.seed.md` Task File Format block: a
  `premise_baseline: <sha> @ 2026-02-01 14:30` line + comment (after
  `plan_approved_at`). Regenerate `AGENTS.md`, `.codex/instructions.md`,
  `.opencode/instructions.md` through the generator
  (`assemble_aitasks_instructions` + `insert_aitasks_instructions`, the recovery
  loop in `aitasks_extension_points.md`; `update_agentsmd` for `AGENTS.md`), then
  `bash tests/test_agent_instructions.sh` (T25–T27 byte-compare).
- `CLAUDE.md` Task File Format block: the same line (hand-maintained).
- `website/content/docs/development/task-format.md`: a `premise_baseline` row
  after `plan_approved_at`, naming `ait update --premise-baseline` (update-only,
  person-settable), and add it to the "flag is named in its own row — see
  `verification_baseline` and `boardgroup`" sentence. Run
  `python3 check_links.py --build` (in `website/`).
- `.claude/skills/task-workflow/task-creation-batch.md`: after the
  `active_gates*` note, a short note: `premise_baseline` is not a creation
  input either — there is no creation flag; it is set on an existing task with
  `aitask_update.sh --premise-baseline`. Regenerate the three procedure goldens
  `tests/golden/procs/task-workflow/task-creation-batch-{default,fast,remote}.md`
  (loop in `tests/test_skill_render_task_workflow.sh`), review the diff is
  exactly the note, run that test + `./.aitask-scripts/aitask_skill_verify.sh`.
  (Codex/OpenCode trees render from this source; no separate port task.)
- `aidocs/framework/aitasks_extension_points.md`: a short "Worked example —
  `premise_baseline` (t1663_2)" after `plan_approved_at`: shape-identical
  update-only/no-tombstone/deletion-aware field; the third opaque-scalar user
  promoted the comparison helper to `lib/opaque_scalar.py`; the writer
  validates by grammar **and** commit existence and refuses symbols; no board
  layer 3 (read surfaces deferred by the design record).
- `aidocs/framework/task_premise_staleness.md` "Field" section: current-state
  description of the writer's accepted forms, the commit-existence check, and
  the promoted helper name (replace "This is the third user ... promotes" with
  the fact).

### 6. Tests

**a. `tests/test_premise_baseline_field.sh`** (new; contract + round trip, in a
`git init` fixture under `fixture_mktemp_d`; plain-function bodies, no
subshell test bodies, so the in-process counters suffice):
- Part A durability: unrelated `--status` / `--priority` updates preserve the
  value byte-exactly; a child's `--status Done` (parent child-completion write
  path) preserves the parent's value, with a non-vacuity check that the parent
  was rewritten.
- Part B set/clear: `<oid> @ <ts>` written verbatim; uppercase oid stored
  lowercase; bare `<oid>` stamped with a well-formed `YYYY-MM-DD HH:MM`; `""`
  removes the key; clearing an absent key stays absent; a task never given the
  flag sprouts no key.
- Part C rejection, each non-zero with the task file byte-unchanged: `HEAD`,
  `main`, a 7-char abbreviation, `<oid>^`, `<oid> @ 2026-11-05`, `<oid>@<ts>`
  (no spaces), trailing garbage, a well-formed 40-hex id that is not an object
  in the repo, a 64-hex id in the SHA-1 fixture, and a tree (not commit) oid.
- Part D "must NOT write" pins: `--file-ref` / `--add-verifies` on a task with
  no baseline does not create one (lifecycle table: scope acquired after
  creation is not written); an `aitask_fold_mark.sh` source check — the file
  contains no `premise_baseline:` emit.
- Part E structural: every `write_task_file` call site forwards
  `CURRENT_PREMISE_BASELINE|new_premise_baseline` (count == 3, regex shape of
  `test_plan_approved_at_roundtrip.sh` Part E); exactly one `premise_baseline:`
  emit in `aitask_update.sh`; across `.aitask-scripts/*.sh` the only file that
  emits a `premise_baseline:` line is `aitask_update.sh` (t1663_3 extends this
  pin when it adds seeding).
- Part F end to end against the shipped reader: write the baseline with the
  flag at commit C1 on a task with `file_references: [lib/a.sh]`;
  `aitask_premise_stale.sh check` reads `DECISION:FRESH` and `BASELINE:<oid>|…`;
  commit a change to `lib/a.sh`, re-check → `DECISION:ASK_STALE` with
  `CHANGED:lib/a.sh|…`. Same with the bare-oid (stamped) form.

**b. `tests/test_aitask_merge.py`** — new `TestMergePremiseBaseline` mirroring
`TestMergePlanApprovedAt`, values `<40-hex> @ <ts>`:
- (a) local clear vs stale remote carrier → stays cleared, key absent (not
  `None`), not unresolved; and the mirror direction;
- (b) stale side with a newer `updated_at` from an unrelated `--status` edit
  does not win; remote's advance wins;
- (c) divergent advances on both sides → in `unresolved` (PARTIAL), and no
  base available → unresolved;
- advance vs unchanged wins; identical sides no conflict;
- guards: in `_BASE_AWARE_FIELDS`, `deletion_aware`, not in
  `_KEEP_LOCAL_FIELDS`/`_LIST_UNION_FIELDS`; all three opaque entries are the
  very `opaque_scalar.normalize_opaque_scalar` object, and `aitask_merge`
  defines no function of its own whose name contains `opaque_scalar` (AST).

**c. `tests/test_premise_baseline_board_roundtrip.py`** (new): through
`board_task_model.Task` on a temp file carrying `premise_baseline:` (lowercase,
all-digit, 64-hex variants): `save()` leaves the file byte-identical;
`reload_and_save_board_fields(("boardidx",))` keeps the field verbatim; and
`merge_frontmatter` + `serialize_frontmatter` of two identical sides keeps it.

## Verification

```bash
bash tests/test_premise_baseline_field.sh
bash tests/test_plan_approved_at_roundtrip.sh        # positional neighbours
bash tests/test_verification_stale.sh
bash tests/test_followup_kind_roundtrip.sh
bash tests/test_atomic_task_file_writes.sh
bash tests/test_premise_stale.sh
bash tests/test_aitask_merge.sh
bash tests/test_aitask_merge_boardgroup.sh
bash tests/test_agent_instructions.sh
bash tests/test_skill_render_task_workflow.sh
./.aitask-scripts/aitask_skill_verify.sh
bash tests/run_all_python_tests.sh --test-dir tests   # verdict = last line
shellcheck .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_fold_mark.sh
(cd website && python3 check_links.py --build)
```

Red proofs (scratch copies, not committed): drop the positional at the
child-completion call site → Part A parent case and Part E fail; remove
`premise_baseline` from `_BASE_AWARE_FIELDS` → merge cases (a)/(b) fail.

Then Step 9 (Post-Implementation): code commit `feature: … (t1663_2)` by named
paths, plan commit via `aitask_task_commit.sh`, gates, archival.

## Risk

### Code-health risk: medium
- `aitask_update.sh` threads the field as positional 36 through three `write_task_file` call sites plus a save/restore block; one missed site silently drops the field on that path · severity: medium · → mitigation: none (covered in-plan by test 6a Part A child-completion case + Part E structural pin)
- Promoting the normalizer changes the merge driver's import graph on the sync-critical path; a fixture that copied a hand-picked lib set would break · severity: low · → mitigation: none (checked: every merge/sync fixture copies the whole `.aitask-scripts/` tree; the merge suites run in Verification)
- Editing `task-creation-batch.md` shifts three procedure goldens · severity: low · → mitigation: none (goldens regenerated and diff-reviewed in the same commit; skill verify + render test)

### Goal-achievement risk: low
- Writer and reader grammars could drift (the writer accepting a value the reader reads as `invalid_baseline`) · severity: low · → mitigation: none (covered in-plan by test 6a Part F, writer→shipped reader end to end)

## Final Implementation Notes
- **Actual work done:** All six plan sections landed as written.
  - `lib/opaque_scalar.py` (new): `normalize_opaque_scalar`. `aitask_merge.py` imports it for all three opaque fields, and its private copy is removed.
  - `premise_baseline` added to `_BASE_AWARE_FIELDS` (deletion-aware), with its rationale paragraph.
  - `aitask_update.sh`: `--premise-baseline` and positional 36, threaded through all three `write_task_file` call sites and the child-completion save/restore block. `normalize_premise_baseline` runs in `main()` before any write.
  - The fold no-op comment.
  - Doc surfaces: the seed plus its regenerated `AGENTS.md`, `.codex/instructions.md` and `.opencode/instructions.md`; `CLAUDE.md`; the website field table and its person-settable sentence; the `task-creation-batch.md` note with its three goldens; both aidocs records.
  - Tests: `tests/test_premise_baseline_field.sh` (71 assertions), `tests/test_premise_baseline_board_roundtrip.py` (4 tests) and `TestMergePremiseBaseline` (13 tests). The two existing tests that named the old private helper now import the shared one.
- **Deviations from plan:**
  - The `task-creation-batch.md` edit also required re-rendering three **committed** remote prerenders: `.claude/skills/task-workflow-remote-/`, `.agents/skills/task-workflow-remote-codex-/` and `.opencode/skills/task-workflow-remote-/` `task-creation-batch.md`. `aitask_skill_verify.sh` flagged them as stale. They were refreshed by rendering only the `aitask-pickrem` / `aitask-pickweb` remote closures (3 agents), not `aitask_skill_rerender.sh remote`, so other sessions' uncommitted skill sources were not swept into tracked prerenders. Each diff is exactly the note.
  - Test 6a gained cases beyond the plan:
    - a rejected value plus `--add-label` leaves `labels.txt` untouched (proves validate-before-mutation);
    - a non-repo cwd is refused;
    - a positive SHA-256 repository case (a 64-hex id is accepted);
    - `HEAD~1`, a leading space and a `T`-separated timestamp are rejected.
  - Merge tests gained cases beyond the plan: "clear vs advance → unresolved" and "first stamp beats a side that never had it".
- **Issues encountered:**
  - The board round-trip test's first non-vacuity edit used `status: Editing`. The merge driver deliberately leaves a non-`Implementing` status conflict unresolved, so the test now uses `Implementing`. This was a test-setup error, not a field defect.
  - The full Python suite reads `PYTHON SUITE: FAILED`, with 3 failures, all in `tests/test_concern_body_display_contract.py`. That test scans the `monitor/` package, which another session is editing uncommitted (`minimonitor_app.py`, `sitrep_close.py`, new `minimonitor_keys.py`). It imports no file this task changed.
  - `tests/test_fold_file_refs_union.sh` fails 4/13 in the shared worktree. It passes 13/13 on a `git archive HEAD` export, including with this task's `aitask_update.sh` and `aitask_fold_mark.sh` overlaid. On the current tree with only this task's two scripts reverted to HEAD, the same 4 still fail. The cause is another session's uncommitted `lib/task_utils.sh` / `lib/yaml_utils.sh` / `tests/lib/test_scaffold.sh` edits.
- **Red proofs (scratch copies, not committed):**
  - The child-completion call site without the positional fails 2 assertions: the parent case reads `''`, and the forwarding pin reads 2 of 3.
  - Without `git cat-file -e`, 11 assertions fail: the missing-40/64-hex, tree-oid and non-repo cases are accepted and the file is rewritten.
  - With `premise_baseline` removed from `_BASE_AWARE_FIELDS`, 8 of 13 merge tests fail, including (a) clear-not-resurrected and (b) stale-unrelated-edit.
- **Key decisions:**
  - Symbolic revisions are rejected, never resolved, so no caller can store write-time HEAD.
  - A bare oid is stamped with `get_timestamp`, which keeps one timestamp home, as with `--plan-approved-at now`.
  - `normalize_followup_kind` and `normalize_group_slug` keep their own bodies. Their contracts are their vocabularies', and rewiring `followup_kinds.py` would change a bridge-sourced module's import graph.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t1663_3 (seeding/carryover):
    - Store `git rev-parse --verify HEAD^{commit}` output, lowercased, with ` @ <ts>`. A bare oid through `aitask_update.sh --premise-baseline <oid>` gets the stamp for free.
    - `tests/test_premise_baseline_field.sh` Part E pins `aitask_update.sh` as the **only** shell file emitting `premise_baseline:`. Adding seeding to `aitask_create.sh` / `aitask_archive.sh` must extend that pin deliberately.
    - The `task-creation-batch.md` note says there is no creation flag. Keep that true, or update the note and its goldens and the three remote prerenders.
  - t1663_4 (Check 6): advance by `aitask_update.sh --batch <id> --premise-baseline "<CHECKED sha>"`. The writer verifies the commit exists and refuses symbols. A rejected value exits non-zero with the file untouched.
  - The merge driver resolves divergent advances to PARTIAL by design.
