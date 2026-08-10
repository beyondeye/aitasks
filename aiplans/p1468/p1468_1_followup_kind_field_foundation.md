---
Task: t1468_1_followup_kind_field_foundation.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_2_*.md, aitasks/t1468/t1468_3_*.md, aitasks/t1468/t1468_4_*.md, aitasks/t1468/t1468_5_*.md, aitasks/t1468/t1468_6_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
---

# p1468_1 — `followup_kind` frontmatter field foundation

Context, the design decision, and the full site inventory are in the task file
`aitasks/t1468/t1468_1_followup_kind_field_foundation.md`. The parent plan
`aiplans/p1468_mark_followup_task_provenance_and_surface_on_board.md` records why
this carrier was chosen over the two rejected options. This plan is the ordered
execution.

## Pre-phase (risk mitigations)

**Step 0 — `negctrl_field_destruction`.** Before editing any source file:

1. Write the round-trip test in its **final form** — fixture task with a
   hand-added `followup_kind: risk_mitigation` line, run
   `aitask_update.sh --batch <id> --status Ready`, assert the line **survives**.
2. Run it. Confirm **RED**. Record the failing test id and the exact failure
   message in this plan's Final Implementation Notes.
3. Only then proceed. At the end, the same assertion — **byte-unchanged** — must
   pass.

A control that passes before the fix is not a control: asserting the *destroyed*
state would go green against today's broken behaviour and prove nothing.

## Implementation steps

### 1. Vocabulary file and readers

1.1 Create `.aitask-scripts/lib/followup_kinds.tsv` — tab-separated,
`kind`, `glyph`, `colour`, `label`, one comment header line. Eight rows:
`manual_verification`, `risk_mitigation`, `upstream_defect`,
`verification_failure`, `carry_over`, `qa_test_gap`, `review_finding`,
`docs_gap`.

Choose single-cell-width geometric glyphs; `TRAIL_CLASSIFICATION_GLYPHS`
(`board/aitask_board.py:609-618`, `◆ ▲ ● ⇄ ○`) is the house precedent for the
class of character that renders reliably. Width is *verified* in t1468_3 — pick
conservatively here so that child does not have to renegotiate the vocabulary.

1.2 Bash reader in `.aitask-scripts/lib/task_utils.sh`: a function returning the
kind column (for validation) and one resolving a row. Follow the existing helper
style in that file.

1.3 Python reader `.aitask-scripts/lib/followup_kinds.py`: parse the **same
file**; expose the ordered kind list and a `kind → (glyph, colour, label)` map.
No second copy of the vocabulary anywhere.

### 2. `aitask_create.sh` — the `anchor` pattern, not the `verifies` pattern

The three serializers have divergent positional numbering, so the value is read
from a **global** inside the renderer bodies. Do **not** add a 17th positional.

2.1 Global `BATCH_FOLLOWUP_KIND=""` near `:48`, beside `BATCH_ANCHOR`.
2.2 Usage text near `:115`.
2.3 Arg parse `--followup-kind) BATCH_FOLLOWUP_KIND="$2"; shift 2 ;;` near `:191`.
2.4 Enum validation near the `resolve_anchor` call site `:2017` — **before any
file is written**, so an invalid value never produces a partial task.
2.5 Emit blocks in **all three** serializers, mirroring the `RESOLVED_ANCHOR`
shape exactly: `create_child_task_file` ~`:556`, `create_draft_file` ~`:693`,
`create_task_file` ~`:1892`.

```bash
        # Only write followup_kind (auto-spawned follow-up provenance) if present
        if [[ -n "$BATCH_FOLLOWUP_KIND" ]]; then
            echo "followup_kind: $BATCH_FOLLOWUP_KIND"
        fi
```

`finalize_draft()` needs no change — its `sed` copy (`:823`/`:859`) preserves any
key already in the draft — but the draft→finalize path gets a test.

### 3. `aitask_update.sh` — eleven sites, all of them

Work through them in this order and check each off; a missed site is silent data
loss, not a visible failure.

| # | site | ~line | shape to copy |
|---|---|---|---|
| 1 | globals `BATCH_FOLLOWUP_KIND`, `BATCH_FOLLOWUP_KIND_SET`, `CURRENT_FOLLOWUP_KIND` | `:92` / `:127` | `BATCH_ANCHOR*` / `CURRENT_ANCHOR` |
| 2 | usage text | `:241` | anchor block |
| 3 | arg parse (sets value **and** `_SET` flag) | `:356` | `--anchor` |
| 4 | default reset in `parse_yaml_frontmatter` | `:430-470` | `CURRENT_ANCHOR` |
| 5 | READ arm in `case "$key" in` | `:560` | `anchor) CURRENT_ANCHOR="$value" ;;` |
| 6 | `write_task_file` **positional arg 33** | `:629-665` | see note below |
| 7 | emit block in `_ait_write_task_file_body` | `:792` | anchor emit |
| 8 | call site — parent children cleanup | `:1170` | passes `CURRENT_*` |
| 9 | call site — non-batch/interactive write | `:1688` | passes `CURRENT_*` |
| 10 | call site — batch write | `:2118` | passes `new_*` |
| 11 | `has_update` gating + batch merge + validation | `:1796`, `:2022`, `:2257` | `BATCH_ANCHOR_SET` |

**Arg 33, appended — not inserted.** `:660-665` states the convention: placing a
new field beside a related one mid-list silently renumbers every positional read
above it.

**Clearing removes the key.** The emit uses `if [[ -n … ]]`, so
`--followup-kind ""` omits the line entirely. This is deliberate and the merge
rule in step 5 depends on it — there is no tombstone value.

### 4. Cross-field invariant (both scripts)

Reject `--followup-kind manual_verification` unless the **resulting** `issue_type`
is also `manual_verification`. Check the *resulting* value, not the flag, so an
update that changes only one half of the pair is caught. Named error message,
non-zero exit, file byte-unchanged.

The converse is legal and must stay legal: an `issue_type: manual_verification`
task may carry `followup_kind: carry_over`.

### 5. `aitask_merge.py` — make the resolver deletion-aware

Newer-`updated_at`-wins is **wrong** here; do not copy the `anchor` branch
(`:312-315`). `merge_frontmatter` resolves one-sided presence at `:289-294`
*before* any field rule, and `:268-270` says so: that branch "is unconditional and
would resurrect a value the other side deliberately cleared."

But `_resolve_base_aware` (`:189`) cannot be reused as-is either:

- `present` (`:194-196`) is `False` only when **neither** side has the key. When
  the winning side *deleted* it, the resolver returns `local_meta.get(key)` →
  `None`, and `serialize_frontmatter` writes a literal `followup_kind: null`.
- It compares through `normalize_group_slug` — boardgroup's tombstone semantics.

5.1 Change the signature to take the comparison normaliser as an argument and to
return the **winning side's** presence separately from its value.
5.2 Keep `boardgroup` byte-identical in behaviour — it relies on its persisted
`""` tombstone, so it keeps passing `normalize_group_slug` and its present-when-
either-side-has-it semantics.
5.3 `followup_kind` passes `normalize_followup_kind` and deletion-aware presence.
5.4 Add `followup_kind` to `_BASE_AWARE_FIELDS` (`:164`) with a comment naming
the two defects above.
5.5 Add it to **none** of `_LIST_UNION_FIELDS` (`:135`), `BOARD_LAYOUT_KEYS` or
`BOARD_KEYS` (`lib/task_yaml.py:55,69`) — three modules read
"metadata ⊆ BOARD_KEYS" as "no real metadata".

### 6. `aitask_fold_mark.sh`

No-op. Add the explanatory comment beside the `anchor` / `boardgroup` no-op
comments at `:315-323`: instance-specific scalar provenance, the primary keeps
its own, folded files are deleted at archival.

### 7. Documentation — Layer 5, all of it

Per `aidocs/framework/aitasks_extension_points.md:42-60`:

- `seed/aitasks_agent_instructions.seed.md` "## Task File Format", then
  regenerate the `AGENTS.md` mirror via `ait setup` (`>>>aitasks` markers)
- `.codex/instructions.md`, `.opencode/instructions.md` — **markerless**;
  hand-edit, do **not** run `insert_aitasks_instructions`
- `CLAUDE.md` "### Task File Format"
- `website/content/docs/development/task-format.md` "### Frontmatter Fields"
- `aidocs/framework/aitasks_extension_points.md` — add `followup_kind` as a third
  worked example beside `anchor` (`:65-70`), naming the merge-resolver wrinkle so
  the next scalar field does not repeat it
- `.claude/skills/task-workflow/task-creation-batch.md` Input table row (the
  flag's *emission* is t1468_2)
- `.claude/skills/aitask-create/SKILL.md` inline flag list

## Verification

1. The negative control from Step 0: RED before, GREEN after, assertion
   byte-unchanged. Record both states.
2. New round-trip test (clone `tests/test_gate_frontmatter_roundtrip.sh` +
   `tests/test_anchor_update.sh`): durability under an unrelated `--status`
   update; set; clear (line **absent**, not empty); read-modify-write; invalid
   kind rejected non-zero with the file byte-unchanged; a task never created with
   the flag never gains an empty field; draft→finalize carry-through.
3. Merge tests (extend `tests/test_aitask_merge_boardgroup.sh` and
   `tests/test_aitask_merge.py`):
   - one side clears, other unchanged ⇒ `"followup_kind" not in merged` **and**
     the serialized file has no `followup_kind:` line — assert absence, not
     `== None`;
   - both sides changed differently ⇒ `PARTIAL:followup_kind`;
   - no base available ⇒ `PARTIAL` naming the field;
   - **every existing `boardgroup` case still passes unchanged** — the regression
     guard on the shared resolver.
4. Cross-field invariant: `--followup-kind manual_verification` on a `feature`
   task rejected non-zero, file byte-unchanged; the converse pairing accepted.
5. `bash tests/run_all_python_tests.sh` — read the **last** line for the verdict.
6. `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh
   .aitask-scripts/aitask_fold_mark.sh`

## Notes for sibling tasks

- The glyph/colour columns land here; t1468_3 consumes them and owns width and
  colour verification.
- Clearing is key removal with no tombstone — any sibling reading the field must
  treat *absent* as "not a follow-up".
- The `_resolve_base_aware` signature changes here. A sibling touching
  `aitask_merge.py` should read the new contract first.
