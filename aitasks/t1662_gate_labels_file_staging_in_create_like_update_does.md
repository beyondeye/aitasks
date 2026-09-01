---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, task_metadata, robustness]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-01 11:06
updated_at: 2026-09-01 11:07
---

## Origin

Surfaced while implementing t1599_2 (scoping `aitask_fold_mark.sh`'s commit and
guarding its amend). Enumerating what an amend-preceding `ait create` commit
legitimately contains required auditing every staging site in
`aitask_create.sh`, which is where this turned up.

## Defect

`aitask_create.sh` stages the label vocabulary **unconditionally** at every
commit site:

- `:863` (child), `:900` (parent), `:2060` (`commit_task`), `:2237` (batch
  child), `:2269` (batch parent) — each `task_git add "$LABELS_FILE" 2>/dev/null || true`

`aitasks/metadata/labels.txt` is a **shared global**, not task-owned. If it is
dirty for any reason — most commonly because a concurrent session just added a
label — the unconditional `add` stages that other session's edit and the
following commit carries it under a message naming *this* task.

`aitask_update.sh:2265-2271` already has the correct pattern for the same file:

```bash
# Only when this update actually appended to the vocabulary — otherwise
# labels.txt would be left dirty for an unrelated commit to sweep up.
if [[ "$_stage_labels" == true ]]; then
    task_git add "$LABELS_FILE" 2>/dev/null || true
fi
```

`aitask_create.sh` has no equivalent flag. The two writers of the same file
disagree about when to stage it.

## Why path-scoping does not fix this — t1599_4 is not a duplicate

`t1599_4` owns `aitask_create.sh` and scopes its **commits** (`:864`, `:902`,
`:904`, `:1958`, `:2136`, …). That is necessary but insufficient here: the
scoped pathspec must still *include* `labels.txt`, because a create that really
did add a label must commit it. So the foreign label edit rides along either
way. Only a "did *this* invocation append to the vocabulary?" gate distinguishes
them.

The two changes are complementary and touch the same file, so sequence them
behind `t1599_4` (or fold this into it) rather than landing both blind.

## Suggested fix

Mirror `aitask_update.sh`: have `add_label_to_file` / the label-registration path
report whether it actually appended, set a `_stage_labels`-style flag, and gate
all five `add "$LABELS_FILE"` sites on it. Reuse the existing name so the two
writers read the same way.

Note `lib/task_utils.sh` owns the canonical accessor `labels_file_path()` and
the label helpers (`sanitize_label` / `ensure_labels_file` / `add_label_to_file`)
— the "did it append" signal probably belongs there, so both writers share it
rather than each deriving it.

## Verification

- Seed a dirty `labels.txt` (simulating a concurrent session's append), run
  `ait create --batch --commit` with labels that are **already** in the
  vocabulary, and assert the resulting commit does **not** contain
  `aitasks/metadata/labels.txt` and that the file is still dirty afterwards.
- Negative control: the assertion must fail against today's unconditional `add`.
- Positive case: a create that introduces a genuinely new label **must** still
  commit `labels.txt` in the same commit — the co-change is legitimate and
  dropping it would leave the vocabulary uncommitted.
- Cover all five staging sites, or prove they share one gate.
