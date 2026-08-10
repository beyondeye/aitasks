---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [task_metadata, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1468
implemented_with: claudecode/opus5
created_at: 2026-08-10 16:28
updated_at: 2026-08-10 18:29
---

## Context

Parent: t1468 — mark auto-spawned follow-up tasks with a machine-readable kind
so the board and pick queue can distinguish them from genuine new work. 171 of
385 active tasks (44%) are follow-ups; 95 carry no marker at all.

**This is the foundation child and the riskiest one.** It introduces the
`followup_kind:` frontmatter field and makes it survive every round-trip.
Nothing in t1468_2..t1468_6 is meaningful until this lands.

### The design decision (already made — do not re-litigate)

The carrier is a **new orthogonal scalar frontmatter field `followup_kind:`**,
set uniformly on every auto-spawned follow-up *including* manual-verification
tasks (which also keep `issue_type: manual_verification`, a real workflow
dispatch key). The two rejected alternatives and why are recorded in the parent
plan `aiplans/p1468_mark_followup_task_provenance_and_surface_on_board.md`
("Design decision: which metadata carrier") — read it before starting.

### The hazard this child exists to defeat

`aitask_update.sh` parses frontmatter with an allowlist `case "$key" in`
(~`:511-579`, **no default arm** — unmatched keys are silently discarded) and
rebuilds the block from literal `echo`s in `_ait_write_task_file_body`
(~`:695-841`). **Any key not registered in BOTH is destroyed by the next
unrelated `ait update`.** Only `attachments:` / `artifacts:` survive, rescued by
`extract_frontmatter_block()` (~`:614-627`, re-printed ~`:812-819`).

The Python layer needs no work: `parse_frontmatter` / `serialize_frontmatter`
(`.aitask-scripts/lib/task_yaml.py:134-203`) are schema-free and preserve
unknown keys. Bash is the only place a key dies.

## Pre-phase (risk mitigation — do this FIRST)

**`negctrl_field_destruction`.** Before touching any registration site, write the
round-trip test in its **final form**: hand-add a `followup_kind:` line to a
fixture task, run an *unrelated* `ait update --status`, assert the field
**survives**. Run it now and confirm it goes **RED**; record the failing test id
and message in the plan. Then implement, and confirm it goes GREEN with the
assertion **byte-unchanged**.

Asserting the *destroyed* state instead would pass while the bug is present — a
negative control that passes before the fix is not a control.

## Vocabulary — single source of truth

Create `.aitask-scripts/lib/followup_kinds.tsv`, columns `kind` · `glyph` ·
`colour` · `label`, with these eight values:

    manual_verification, risk_mitigation, upstream_defect, verification_failure,
    carry_over, qa_test_gap, review_finding, docs_gap

One value per creation seam in the framework. **Users must not extend this** —
unlike `labels.txt` / `task_types.txt` these are framework-semantic, which is
exactly why the file lives in `lib/` and not in `aitasks/metadata/` (no
`ait setup` / seed / upgrade plumbing needed). Add a reader in
`lib/task_utils.sh` (bash) and a small `lib/followup_kinds.py` (Python) — both
read the **same file**; do not duplicate the list.

Glyph and colour columns are consumed by t1468_3. Pick single-cell-width
geometric glyphs (the `TRAIL_CLASSIFICATION_GLYPHS` set `◆ ▲ ● ⇄ ○` in
`board/aitask_board.py:609-618` is the house precedent); t1468_3 verifies width
at render level.

## Key files to modify

### `.aitask-scripts/aitask_create.sh`
Follow the **`anchor` / `RESOLVED_ANCHOR` pattern**, not the `--verifies`
pattern: the three serializers have divergent positional numbering, so read a
**global** in the renderer bodies rather than adding a 17th positional.
- global near `:48` (beside `BATCH_ANCHOR`)
- usage text near `:115`
- `--followup-kind` arg parse near `:191`
- enum validation near the `resolve_anchor` call site `:2017` (before any file is
  written)
- emit from the global in **all three** serializers — `create_child_task_file`
  ~`:556`, `create_draft_file` ~`:693`, `create_task_file` ~`:1892` — mirroring
  the `if [[ -n "$RESOLVED_ANCHOR" ]]; then echo "anchor: …"` blocks exactly.

`finalize_draft()` (~`:794`, sed-copies at `:823`/`:859`) preserves any key in
the draft, so no work there — but add a test that a drafted-then-finalized task
keeps the field (`tests/test_anchor_create.sh` covers the analogous case).

### `.aitask-scripts/aitask_update.sh`
Eleven sites. Missing any one is silent data loss:
- globals near `:92` (`BATCH_FOLLOWUP_KIND`, `BATCH_FOLLOWUP_KIND_SET`,
  `CURRENT_FOLLOWUP_KIND`)
- usage text near `:241`
- arg parse near `:356` (copy `--anchor`: sets both value and `_SET` flag)
- frontmatter READ arm in the `case` near `:560` (scalar arm shape)
- `write_task_file` — **append as positional arg 33**. `:660-665` states the
  convention explicitly: inserting mid-list silently renumbers every read above.
- emit block near `:792`
- **all three** `write_task_file` call sites: `:1170`, `:1688`, `:2118`
- `has_update` gating near `:1796`
- batch merge near `:2022` (copy the `new_anchor` / `BATCH_ANCHOR_SET` shape)
- validation near `:2257`

**Clearing is key removal, not a tombstone** — the emit block uses the
`if [[ -n … ]]` pattern, so `--followup-kind ""` omits the line.

### Cross-field invariant (both scripts)
Reject `--followup-kind manual_verification` unless the **resulting**
`issue_type` is also `manual_verification` (check the resulting value, so an
update changing only one of the pair is caught). Named error, non-zero exit,
file byte-unchanged. The reverse is **not** required — an MV task may legitimately
be `carry_over`.

### `.aitask-scripts/aitask_fold_mark.sh`
No-op. Add a comment beside the `anchor` / `boardgroup` comments at `:315-323`
explaining why: it is a scalar carrying instance-specific provenance, the primary
keeps its own, and folded files are deleted at archival anyway.

### `.aitask-scripts/board/aitask_merge.py` — the second trap

**Newer-`updated_at`-wins is WRONG here** (do not copy `anchor:312-315`).
`merge_frontmatter` resolves one-sided presence at `:289-294` *before* any field
rule, and the code says so at `:268-270`: that branch "is unconditional and would
resurrect a value the other side deliberately cleared." Since a misclassification
must be correctable — including by clearing the field — a clear must survive
sync. Only base comparison delivers that.

But **`_resolve_base_aware` (`:189`) as written cannot express deletion** and
must not simply be reused:
1. `present` (`:194-196`) is `False` only when **neither** side carries the key.
   When the winning side *deleted* it, the resolver returns
   `local_meta.get(key)` → `None`, and `serialize_frontmatter` writes a literal
   `followup_kind: null` instead of removing the line.
2. It compares through `normalize_group_slug` — boardgroup's tombstone
   semantics, the wrong vocabulary here.

**Fix:** make the resolver **deletion-aware and normaliser-parameterised** —
return the *winning side's* presence separately from its value, and take the
comparison normaliser as an argument. Keep `boardgroup`'s behaviour
byte-identical (it relies on its persisted `""` tombstone); `followup_kind`
passes its own `normalize_followup_kind`. Then add `followup_kind` to
`_BASE_AWARE_FIELDS` (`:164`).

Put it in **none** of `_LIST_UNION_FIELDS` (`:135`), `BOARD_LAYOUT_KEYS` or
`BOARD_KEYS` (`lib/task_yaml.py:55,69`) — `lib/board_columns.py:483`,
`lib/trail_gather.py:313` and `lib/work_report_gather.py:180` read
"metadata ⊆ BOARD_KEYS" as "no real metadata".

## Reference files for patterns

- `aidocs/framework/aitasks_extension_points.md:8-103` — the prescribed
  "Adding a new frontmatter field" checklist; `:65-70` is the **`anchor` worked
  example**, which is this field's exact shape (semantic scalar, not board-owned).
- `tests/test_gate_frontmatter_roundtrip.sh` — the canonical durability test;
  its header `:5-11` names this exact hazard.
- `tests/test_anchor_update.sh:187` — unrelated update preserves the scalar.
- `tests/test_aitask_merge_boardgroup.sh` — base-aware merge cases incl. the
  no-base negative control.

## Documentation (Layer 5 — all of it)

Per `aitasks_extension_points.md:42-60`:
- `seed/aitasks_agent_instructions.seed.md` "## Task File Format", then
  regenerate the `AGENTS.md` mirror via `ait setup` (`>>>aitasks` markers)
- `.codex/instructions.md` and `.opencode/instructions.md` — **markerless,
  hand-edit**; do NOT run `insert_aitasks_instructions`
- `CLAUDE.md` "### Task File Format"
- `website/content/docs/development/task-format.md` "### Frontmatter Fields"
- `aidocs/framework/aitasks_extension_points.md` itself — add `followup_kind` as
  a third worked example beside `anchor`
- `.claude/skills/task-workflow/task-creation-batch.md` Input table (the flag's
  *emission* is t1468_2's job; the Input row belongs here)
- `.claude/skills/aitask-create/SKILL.md` inline flag list

## Verification steps

1. The negative control: RED before implementation (record the test id), GREEN
   after, assertion byte-unchanged.
2. `bash tests/test_<new_roundtrip_test>.sh` — durability under an unrelated
   `--status` update; set / clear / read-modify-write; invalid kind rejected
   non-zero with the file byte-unchanged; draft→finalize carry-through.
3. Merge tests (extend `tests/test_aitask_merge_boardgroup.sh` and
   `tests/test_aitask_merge.py`):
   - one side clears + other unchanged ⇒ **`"followup_kind" not in merged`** —
     assert key *absence*, not `== None`, **and** that the serialized file has no
     `followup_kind:` line at all;
   - both sides changed differently ⇒ `PARTIAL:followup_kind`;
   - no base available ⇒ `PARTIAL` naming the field;
   - **`boardgroup`'s existing cases still pass unchanged** (regression guard on
     the shared resolver).
4. Cross-field invariant: `--followup-kind manual_verification` on a `feature`
   task is rejected non-zero, file byte-unchanged.
5. `bash tests/run_all_python_tests.sh` (read the LAST line for the verdict).
6. `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh
   .aitask-scripts/aitask_fold_mark.sh`

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-10T15:29:36Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-10T16:04:49Z status=pass attempt=1 type=human
