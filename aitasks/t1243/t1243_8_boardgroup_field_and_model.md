---
priority: high
effort: high
depends: [t1243_7]
issue_type: feature
status: Ready
labels: [aitask_board, tui, python, gitremote]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-07-28 01:15
updated_at: 2026-07-28 01:15
---

## Context

**Child 8 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — Workstream C).

This child lands the **data model** for in-column task groups: a new
`boardgroup` frontmatter field, its merge semantics, its CLI surface, and the
pure derivation that turns it into rendered groups. No board widgets here —
rendering is t1243_9.

**Depends on t1243_2**: the board's save path drops any board key it does not
name, so `boardgroup` cannot persist until that seam iterates `BOARD_KEYS`.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## The data model (decided; alternatives rejected in the parent plan)

```yaml
boardcol: now
boardidx: 3072
boardgroup: perf_work
```

- **Group identity is the slug**; display title is the slug rendered for humans
  (`perf_work` -> "perf work"). No registry, no ids, no title/colour store in v1.
- **Membership** = tasks in the same column sharing the slug. Identity is
  `(column, slug)`.
- A single-member group renders as a plain card (mirrors how
  `_build_topic_lanes` collapses singleton lanes into "Ungrouped").

## Key files to modify

- `.aitask-scripts/lib/task_yaml.py` — the key split (below).
- `.aitask-scripts/board/aitask_merge.py` — `_KEEP_LOCAL_FIELDS`,
  `merge_frontmatter` signature, new `boardgroup` resolution.
- `.aitask-scripts/aitask_sync.sh` — extract and pass the merge base.
- `.aitask-scripts/aitask_update.sh` — `--boardgroup` (update-only).
- `.aitask-scripts/aitask_fold_mark.sh` — no-op note (scalar; primary wins).
- `.aitask-scripts/lib/board_groups.py` — **new**, pure derivation.
- `tests/test_board_groups.py`, `tests/test_aitask_merge_boardgroup.sh` — **new**.

## Implementation plan

### 1. Split `BOARD_KEYS` — it is currently doing two different jobs

```python
# lib/task_yaml.py
BOARD_LAYOUT_KEYS = ("boardcol", "boardidx")            # per-checkout layout
BOARD_KEYS        = BOARD_LAYOUT_KEYS + ("boardgroup",) # all board-owned keys
```

| Consumer | Set | Why |
|---|---|---|
| `serialize_frontmatter` key ordering | `BOARD_KEYS` | `boardgroup` serialises last with the others |
| "empty metadata" probe (`lib/work_report_gather.py`, `lib/trail_gather.py`) | `BOARD_KEYS` | a task carrying only board keys still reads as empty |
| `_KEEP_LOCAL_FIELDS` in `aitask_merge.py` | **`BOARD_LAYOUT_KEYS`** (narrowed) | layout stays local-wins; membership must not |
| t1243_2's save-path snapshot loop | `BOARD_KEYS` | every board key survives the reload |

### 2. Merge semantics — the hard part

Which column a card sits in is per-checkout layout, so `_KEEP_LOCAL_FIELDS` is
right for it. **Group membership is shared task organization** — a user who
groups on one machine expects the group on another. But two independent defects
block the obvious rules:

- *No deletion semantics.* `merge_frontmatter` resolves one-sided presence
  **first and unconditionally** (`in_local and not in_remote -> local`,
  `in_remote and not in_local -> remote`), before any field rule. A side that
  clears the field by omitting the key loses to a side that still carries it —
  **membership resurrects on sync**.
- *No field-level causality.* `updated_at` is **task-wide** and only
  minute-resolution (`%Y-%m-%d %H:%M`). Machine A removes a task from its group
  at t1; unsynced machine B edits only `status` at t2 > t1 while still carrying
  the old `boardgroup`; newer-wins hands the field to B, **which never touched
  it**. At minute granularity, bulk group operations tie constantly.

**Decision: base-aware change detection, with the base read from git's index.**

The diff3 base is **not** available in production: `merge.conflictStyle` is
configured nowhere (git config, `.aitask-scripts/`, `seed/`), so git emits 2-way
markers with no `|||||||` section; `aitask_sync.sh` runs a plain
`task_git pull --rebase` and hands the conflicted file to
`aitask_merge.py --batch --rebase`, whose `main()` reads only the file's text.
Plumbing the parser's `base_lines` through would be **dead code**. (Note
`tests/test_aitask_merge.sh` is entirely hand-written fixtures with exactly one
diff3 case — it could not have caught this.)

Read the base from **git's conflicted index** instead: for a conflicted path git
holds stage 1 = merge base, stage 2 = ours, stage 3 = theirs. Split ownership so
the Python stays a pure text merger:

- `aitask_sync.sh` — which already owns the git context via `task_git` (the
  `.aitask-data` worktree) — extracts `task_git show ":1:$file_path"` to a temp
  file and passes `--base-file <tmp>`. Stage 1 is the merge base regardless of
  rebase side inversion, so the existing `--rebase` local/remote swap is
  unchanged and the base needs **no** swap.
- `aitask_merge.py` gains `--base-file` and uses it as the third side. The diff3
  marker parser is retained **only** as a fallback for invocations outside a
  conflicted index.
- An add/add conflict has no stage 1; `git show :1:` fails, there is genuinely no
  base, and PARTIAL is correct.

Resolution table:

| base vs sides | Result |
|---|---|
| only local differs from base | local |
| only remote differs from base | remote |
| both differ, same value | that value |
| both differ, different values | **unresolved / PARTIAL** |
| no base and values diverge | **unresolved / PARTIAL** (fail closed) |

**Tombstone on write.** Removing a task from a group writes `boardgroup: ""`
rather than deleting the key (omit != clear). `""` renders as ungrouped, presence
stays symmetric for any task ever grouped, and the resolution stays readable.

*Rejected alternative:* forcing `merge.conflictStyle=diff3` on the sync rebase
paths. It only covers conflicts produced by that invocation, so anything from a
manual `git pull` or an IDE merge still arrives 2-way — a partial fix that also
reaches into the user's git behaviour.

*Noted, not fixed here:* `anchor` merges newer-wins and has the same task-wide
timestamp weakness. Record it in Final Implementation Notes; do not expand scope.

### 3. Timestamp discipline

Every `boardgroup` mutation advances `updated_at`: the in-process bulk path via
t1243_2's `reload_and_save_board_fields(semantic=True)`, and the
`aitask_update.sh --boardgroup` path (which advances it itself). Layout-only
moves stay timestamp-neutral.

### 4. `lib/board_groups.py` — the INV-R derivation

> **INV-R (render determinism).** A column's rendered order is a **pure, total
> function of the persisted state of that column's tasks.** Two checkouts holding
> identical task files render identical order, and reloading after any operation
> reproduces the order that was on screen.

Contiguity of `boardidx` is **explicitly NOT an invariant** — it is unachievable
here, because `boardgroup` is shared while `boardidx` stays per-checkout: after a
sync a remotely-added member arrives carrying the group but keeping its local
scattered index, and a remotely-removed member arrives with the tombstone but not
the sender's repositioning write. Repairing that on load would write task files
every time the board opens after a sync, and two checkouts could ping-pong
repairs forever.

Derivation (mirrors `_build_topic_lanes`, which already derives lanes from
`anchor` without touching an index):

1. Walk `get_column_tasks(col)` (already sorted by
   `(normalize_board_idx, filename)`). A task with a non-empty `boardgroup` joins
   that slug's **group unit**; every other task is a **singleton unit**.
2. A unit's sort key is the key of its **first** member in that walk.
3. Units are emitted in sort-key order; members render inside their unit in walk
   order. A group unit with one member renders as a plain card.

Consequences, stated honestly: grouping **never writes an index** (formation is K
`boardgroup` writes, removal is 1); a non-member whose index falls between two
members renders **outside** the block at its own key position; and **no post-sync
reconciliation exists or is needed**.

Also export the **shared match predicate** t1243_4 factored to data level, so
t1243_10 can evaluate a collapsed group's members that have no mounted widget.

### 5. CLI + extension-points sweep

`--boardgroup SLUG` in `aitask_update.sh` only (mirroring `--boardidx`, which is
update-only and absent from `aitask_create.sh`); `""` clears. Slug validation:
`^[a-z0-9_]+$` after normalisation. Walk
`aidocs/framework/aitasks_extension_points.md` "Adding a new frontmatter field"
and surface any layer this task does not cover as a note for t1243_13 (docs).

## Verification

- Pure unit tests for the INV-R derivation: scattered indices, ties, an
  interleaved non-member, a singleton group, an empty column.
- **Two post-sync fixtures** — "remote add" and "remote remove" merge results —
  rendering identically and stably, proving no reconciliation is needed.
- Merge **unit** tests: local-only change, remote-only change, both-changed-same,
  both-changed-different (PARTIAL), deletion from each side, no base (PARTIAL),
  identical, absent-on-both.
- **Temporary-repository integration test** (this is the one that matters):
  `git init`, commit a task with `boardgroup: perf_work`, have one side clear it
  and the other change only `status`, produce a genuine conflict through the real
  rebase path **under the repo's default conflict style**, run the actual merge
  driver, and assert the **cleared** side wins — the `status`-only edit must not
  win a field it never touched.
- **Negative control:** the same scenario with the base withheld yields PARTIAL,
  proving the base is what decided it.
- **Guard test:** every driver invocation site in `aitask_sync.sh` passes
  `--base-file`.
- `aitask_update.sh --boardgroup` round-trip advances `updated_at`; `""` clears.
- A `boardgroup` set in memory survives t1243_2's save seam.
