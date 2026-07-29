---
Task: t1243_2_board_field_persistence_seam.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_10_group_collapse_and_filtering.md, aitasks/t1243/t1243_11_group_formation_and_block_moves.md, aitasks/t1243/t1243_12_group_membership_commands.md, aitasks/t1243/t1243_13_documentation.md, aitasks/t1243/t1243_14_retrospective_benchmark.md, aitasks/t1243/t1243_15_manual_verification_board_groups_and_reordering.md, aitasks/t1243/t1243_3_gap_indexing.md, aitasks/t1243/t1243_4_render_filter_scoping.md, aitasks/t1243/t1243_5_lateral_dom_transplant.md, aitasks/t1243/t1243_6_multiselect_marking.md, aitasks/t1243/t1243_7_move_to_column_command.md, aitasks/t1243/t1243_8_boardgroup_field_and_model.md, aitasks/t1243/t1243_9_group_focus_and_rendering.md
Archived Sibling Plans: aiplans/archived/p1243/p1243_1_movement_baseline_and_harness.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-29 12:09
---

# t1243_2 — Board field persistence seam

> Child 2 of 14 in the t1243 decomposition. Parent design:
> `aiplans/p1243_board_task_groups_and_fast_reordering.md`. Sibling t1243_1
> (archived) owns the movement characterization harness this child reuses.

## Context

`Task.reload_and_save_board_fields()` is the board's **only** disk-write path for
layout fields. It snapshots `boardcol` and `boardidx` **by name, hardcoded**,
reloads the file (to preserve edits another writer made to other fields),
re-applies exactly those two, and calls the timestamp-neutral `save()`.

Three defects follow, and all must be fixed **before** any group work:

1. **Any board key it does not name is silently dropped.**
   `Task._BOARD_KEYS = BOARD_KEYS` exists on the class and is **never read
   anywhere in the repo** — a dead assignment. t1243_8's `boardgroup` would be
   set in memory and then reloaded away by the very save call meant to persist
   it. Latent today, fatal the moment `BOARD_KEYS` grows.
2. **It cannot express a semantic change.** `save_with_timestamp()` exists and
   is documented "Use for semantic metadata changes", but the board-field path
   never calls it. t1243_8 resolves `boardgroup` on *which side changed the
   field*, which is meaningless if the write records no modification.
3. **Every call writes both layout keys, whatever it mutated.** Five of the seven
   call sites change exactly one of `boardcol` / `boardidx`, yet all of them
   write back both — so a stale in-memory value silently reverts another
   writer's change to the key this operation never touched. Live today, not
   hypothetical.

**Intended outcome:** the seam takes an explicit, validated field set — required,
not defaulted — and derives persistence *and* timestamp behaviour from which
fields it names. A call persists exactly what it mutated, and nothing else.

## Anchor re-verification — done at current HEAD, all anchors hold

`aitask_board.py` is now **9128 lines** (9043 when t1243_1 ran — +85 from the
t1216_2 SHADOW-zone commit). Line numbers moved; every symbol is intact:

- `Task._BOARD_KEYS = BOARD_KEYS` — `aitask_board.py:197`. Confirmed **dead**:
  the only repo-wide hits for `_BOARD_KEYS` are this assignment itself.
- `Task.reload_and_save_board_fields` — `aitask_board.py:260`, still the
  hardcoded two-name body described above. It has **exactly 7 callers, all
  inside `aitask_board.py`** — no external API surface to keep compatible.
- `BOARD_KEYS = ("boardcol", "boardidx")` — `lib/task_yaml.py:49`; imported into
  the board at `aitask_board.py:49`.
- `Task.save` / `_update_timestamp` / `save_with_timestamp` / `Task.load` —
  `aitask_board.py:246` / `251` / `255` / `224`. `save()` does **not** bump
  `updated_at`; `_update_timestamp()` writes `%Y-%m-%d %H:%M` — **minute
  resolution** — via `datetime.now()`, and `datetime` is bound at
  `aitask_board.py:11` as `from datetime import datetime`, so it is patchable
  per-module for a frozen-clock test.
- **`TaskManager` is constructible in-process against a temp tree.**
  `__init__` (`:811-834`) is dict initialisation plus `_ensure_paths()`,
  `load_metadata()`, `load_tasks()` — **no git, no locks, no Textual**
  (`modified_files` / `lock_map` start empty and are filled only by
  `refresh_git_status` / `refresh_lock_map`, which nothing here calls). All three
  read the module globals `TASKS_DIR` (`:66`) and `METADATA_FILE` (`:67`) **at
  call time**, so `mock.patch.object(B, "TASKS_DIR", …)` redirects them.
  *This does not contradict t1243_1*: its isolation finding is that setting the
  **environment variable** `TASK_DIR` is a no-op against `TASKS_DIR = task_dir()`
  already evaluated at import. Patching the **module attribute** is a different
  seam, and it is enough here because no app, no Pilot and no git are involved.
  Its finding 3 (`TASK_DIR` must stay *relative*) is likewise scoped to
  `is_modified`'s porcelain-path comparison, which this child never calls — an
  absolute temp path is correct here.
- `serialize_frontmatter` round-trips `updated_at: 2020-01-01 00:00` as a
  **str**, byte-identically (verified in-memory — the YAML timestamp resolver
  does not claim the seconds-less form).
- `aitask_merge._KEEP_LOCAL_FIELDS = frozenset(BOARD_KEYS)` (`aitask_merge.py:132`)
  — *as found; re-derived from `BOARD_LAYOUT_KEYS` by Change Request 1 below*
  — board keys are local-wins **on cross-checkout sync conflicts**. That is a
  merge policy between two checkouts; it says nothing about a stale in-memory
  value racing a newer write inside one checkout.
- The board never reloads on its own by default: `auto_refresh_minutes` defaults
  to `0` (`:849`), and `_auto_refresh_tick` (`:5886`) is the only periodic
  reload. A board left open holds its `Task` objects indefinitely, so the stale
  window is unbounded.
- t1243_1's write spy forwards `*a, **kw` (`tests/test_board_movement.py:367`),
  so narrowing the call sites needs no change to that harness. It also exposes
  `build_tree`, `fixture_name`, `snapshot`, `diff_snapshots` as module-level
  helpers. No `tests/__init__.py`, pytest is absent → the runner uses
  `unittest discover -s tests`, which puts `tests/` on `sys.path`; a cross-import
  resolves under discovery, under pytest-if-installed, and standalone.

## The write-back hazard, in three directions

Every failure below is silent — timestamp-neutral, or timestamped on the wrong
side — so neither `_newer_side` nor t1243_8's base-aware resolution can detect it.

**A — a layout move resurrects shared membership.** Once `boardgroup` is in
`BOARD_KEYS` and the loop iterates all of it: board opens with card X at
`boardgroup: A`; `boardgroup: B` lands on disk (another checkout's change pulled
in by `_auto_refresh_tick`'s own `sync_on_refresh`, or `aitask_update.sh
--boardgroup`); the user presses `shift+→`; the reload reads `B` and the
re-apply writes `A` back. t1243_8's consumer table narrows `_KEEP_LOCAL_FIELDS`
to `BOARD_LAYOUT_KEYS` **because** "layout stays local-wins; membership must
not" — handing the layout write path the full key set reinstates local-wins one
layer below the merge tool.

**B — a semantic write resurrects stale layout.** The mirror image, which a
`LAYOUT ∪ named_fields` union would still have: a stale object holds
`boardidx: 10`, another writer moves the card to `20`, and a group mutation from
that stale object re-applies `10` alongside `boardgroup`.

**C — a single-key layout op resurrects the other layout key. This one is live
today.** `normalize_indices` mutates only `board_idx`, but writes `boardcol` too:
another writer moves card X from `c0` to `c1` on disk; this board still believes
X is in `c0`, renumbers `c0`, and the save reloads `c1` and writes `c0` back —
**silently yanking the card out of the column someone just moved it to.**
`update_column` is the mirror: it renames a column, mutates only `board_col`, and
re-applies a stale `boardidx` over a newer index.

The fix for all three is one rule: **a call persists exactly the fields it names,
and it must name them.**

## Design decisions

**1. `lib/task_yaml.py` gains the key split t1243_8 was going to introduce.**

```python
BOARD_LAYOUT_KEYS = ("boardcol", "boardidx")   # per-checkout layout
BOARD_KEYS = BOARD_LAYOUT_KEYS                 # all board-owned keys (t1243_8 appends "boardgroup")
```

Today the two are equal, so every consumer is unchanged. Introducing the split
here is what lets the seam distinguish layout from shared fields *before* a
shared field exists, so t1243_8's one-line `BOARD_KEYS` extension cannot silently
change the seam's behaviour.

**2. `fields` is REQUIRED — there is no default.** A default is what let hazard C
live for the lifetime of this code: it is always *plausible* and never *stated*.
With no default, every caller — the seven that exist and any t1243_11 adds — must
say what it mutated, and "carries a field it did not mutate" becomes a visible
claim in the diff rather than an omission. The seam has no external callers, so
this costs nothing outside the file.

| call | persisted | `updated_at` |
|---|---|---|
| `fields=("boardidx",)` | `boardidx` only | untouched (pure layout subset) |
| `fields=("boardcol","boardidx")` | both | untouched |
| `fields=("boardgroup",)` | `boardgroup` only | set (hazard B excluded) |
| `fields=("boardgroup","boardidx")` | both — an intentional combined mutation | set |
| `fields=("status",)` / `("boardgruop",)` / `()` | — | **`ValueError`** |

**3. Persistence *and* timestamp are both derived from the named set — ownership,
not a second flag.** `semantic = any(k not in _BOARD_LAYOUT_KEYS for k in keys)`.
A free-form `semantic: bool` could timestamp a pure layout move; a field tuple
with no validation could timestamp a typo while discarding the value it meant to
write (`metadata.get("boardgruop")` is `None`, so the re-apply loop skips it).
Validating against `_BOARD_KEYS` and deriving the timestamp from set membership
removes both. Unknown names **raise** — the argument is a literal in board
source, not user data, so failing loudly at the seam beats silently dropping a
membership write.

*This supersedes the `semantic: bool = False` sketch in the task file, the
p1243_2 execution plan and the parent design, and it changes all seven call
sites. Step 5 corrects every artifact — deviating silently is what leaves the
unsafe contract written down in three places.*

**4. Both class attributes become live.** `_BOARD_LAYOUT_KEYS` is the semantic
discriminator; `_BOARD_KEYS` is the validation vocabulary. The dead assignment is
retired by *reading* it, per the task file's "delete it or have the loop read it
— leave no unread duplicate". Patching either on the class is a test seam that
cannot leak into `_is_phantom_stub`, `serialize_frontmatter` or
`_KEEP_LOCAL_FIELDS`, all of which read module-level constants rather than the
class attributes (`BOARD_KEYS` for the first three; `BOARD_LAYOUT_KEYS` for
`_KEEP_LOCAL_FIELDS` after Change Request 1 below).

**5. `if v is not None`** preserves an empty-string tombstone (t1243_8 writes
`boardgroup: ""` for "removed from group") while never inventing a key that was
genuinely absent. `delete_column` writes `board_idx = 0` — falsy but not `None`,
so the guard must test `is not None`, never truthiness.

**6. The concurrency claim is narrowed to what the code does.** The reload and
the save are two separate opens with nothing between them: an external write
landing *after* `load()` returns is overwritten. The current docstring's
"Prevents overwriting external changes to non-board fields" over-claims a
best-effort guard. Adding locking or version detection would mean a write
protocol the parent design does not call for and no other writer participates in
(`aitask_update.sh` writes files directly) — out of scope for a seam-prep child.
The claim is narrowed in the docstring and the surviving window is **pinned by a
test** rather than left as prose.

**7. The timestamp contract is "sets `updated_at` to the current minute", not
"advances it".** `_update_timestamp()` is minute-resolution, so two semantic
writes in the same minute produce the same value. Making it monotonic would mean
changing `_update_timestamp` itself — used by `save_with_timestamp` across the
board — and would fabricate future timestamps. t1243_8 §2 already names this
weakness ("At minute granularity, bulk group operations tie constantly") and is
why it chose base-aware change detection over newer-wins. The tests assert the
weaker, true contract and pin the same-minute case, under a **frozen clock** so
neither assertion can straddle a minute boundary.

**8. Tests run in-process; the call-site mapping is verified through the real
callers.** `Task` needs no directory at all (explicit `filepath`), and
`TaskManager` needs only two patched module attributes (see anchors), so the
seam-level and caller-level tests both run without a subprocess, without Textual
and without git. Only `_move_task_to_extreme` — a `KanbanApp` method — is out of
reach without a Pilot harness; a structural guard covers it and says so.

## Implementation

### Step 1 — the key split (`.aitask-scripts/lib/task_yaml.py`)

Replace the single constant at `:49` with the two shown in decision 1, each
carrying a one-line comment naming its policy. No consumer changes: `BOARD_KEYS`
keeps its current value, so `serialize_frontmatter`, `_is_phantom_stub`,
`work_report_gather`, `trail_gather` and `_KEEP_LOCAL_FIELDS` all behave
identically.

### Step 2 — rewrite the seam (`.aitask-scripts/board/aitask_board.py`)

Import `BOARD_LAYOUT_KEYS` alongside `BOARD_KEYS` at `:49`. Replace the dead
`_BOARD_KEYS` (`:197`) with the two attributes the method reads, and rewrite the
method (`:260`):

```python
class Task:
    # Both are READ by reload_and_save_board_fields: the layout set is its
    # "is this a semantic write?" discriminator; the full set is the vocabulary
    # the required `fields` argument is validated against.
    _BOARD_LAYOUT_KEYS = BOARD_LAYOUT_KEYS
    _BOARD_KEYS = BOARD_KEYS

    def reload_and_save_board_fields(self, fields):
        """Reload from disk, re-apply the named board fields, and save.

        Re-reads the file so that edits another writer made **before this call**
        (a status set by a coding agent, a synced-in change) are not lost to the
        board's in-memory copy. It is best-effort, not atomic: the reload and the
        write are separate opens, so an edit landing *between* them is still
        overwritten. No lock is taken and no other writer participates in one.

        ``fields`` is the exact set of board keys this call is persisting, and
        is **required** — pass what you mutated, e.g. ``("boardidx",)`` for a
        vertical move. **Only the named fields survive the reload.** A call must
        never carry a field it did not mutate, in any direction: re-applying a
        stale ``boardcol`` from an index-only operation reverts another writer's
        column move; re-applying a stale shared field overwrites another
        checkout's membership change; re-applying a stale ``boardidx`` from a
        membership write discards a newer local move.

        Naming any key outside ``_BOARD_LAYOUT_KEYS`` makes this a semantic
        write: ``updated_at`` is set to the current minute. Note
        ``_update_timestamp`` is minute-resolution — a semantic write sets
        ``updated_at`` to the current minute, it does not guarantee a strictly
        greater value than the one already stored.

        Raises ``ValueError`` for an empty or unknown ``fields`` — both are
        caller bugs that would otherwise silently persist nothing, or timestamp
        a write whose value was dropped because the key name was misspelled.

        Skips the save entirely if the file no longer exists (archived/deleted)
        — it is never recreated.
        """
        keys = tuple(fields)
        if not keys:
            raise ValueError("reload_and_save_board_fields: fields is empty — "
                             "name the board keys this call mutated")
        unknown = [k for k in keys if k not in self._BOARD_KEYS]
        if unknown:
            raise ValueError(f"reload_and_save_board_fields: not board keys: "
                             f"{unknown} (known: {list(self._BOARD_KEYS)})")
        semantic = any(k not in self._BOARD_LAYOUT_KEYS for k in keys)

        snapshot = {k: self.metadata.get(k) for k in keys}
        if not self.load():
            return  # File gone (archived/deleted) — do NOT recreate it
        for key, value in snapshot.items():
            if value is not None:   # preserves "" (tombstone); never invents a key
                self.metadata[key] = value
        if semantic:
            self._update_timestamp()
        self.save()
```

### Step 3 — audit all seven call sites and pass the actual mutation

Each site's field set is read off the assignments immediately above the call:

| site | assigns | `fields=` |
|---|---|---|
| `move_task_col` `:1307-1309` | `board_col`, `board_idx` | `("boardcol", "boardidx")` |
| `swap_tasks` `:1315-1316` (t1) | `board_idx` | `("boardidx",)` |
| `swap_tasks` `:1315-1317` (t2) | `board_idx` | `("boardidx",)` |
| `normalize_indices` `:1325-1326` | `board_idx` | `("boardidx",)` |
| `update_column` `:1349-1350` | `board_col` | `("boardcol",)` |
| `delete_column` `:1378-1380` | `board_col`, `board_idx` | `("boardcol", "boardidx")` |
| `_move_task_to_extreme` `:8272-8275` | `board_idx` | `("boardidx",)` |

Five of the seven narrow to one key — that is hazard C, closed. Every site stays
timestamp-neutral (no semantic key is named), which is what the task file's "do
not flip them" requires.

**This is behaviour-preserving without a concurrent writer and behaviour-
correcting with one:** when the un-named key's in-memory and on-disk values agree
— always true in a single-writer test — re-applying it or not produces identical
bytes. Step 4C is what pins the mapping itself; see the note there on why
`FLIP_TABLE` alone cannot.

### Step 4 — tests (`tests/test_board_persistence_seam.py`, new)

Reuses t1243_1's fixture and differ by importing its public helpers — no second
fixture is built:

```python
from test_board_movement import build_tree, diff_snapshots, fixture_name, snapshot
import aitask_board as B
```

with `sys.path` bootstrapped from `__file__` over `tests/`,
`.aitask-scripts/board`, `.aitask-scripts/lib` (t1236: the runner supplies no
`PYTHONPATH`). Two local helpers:

```python
def external_edit(path, **changes):
    """Rewrite a task file through the canonical serializer, as another writer would."""
    meta, body, order = parse_frontmatter(path.read_text(encoding="utf-8"))
    meta.update(changes)
    path.write_text(serialize_frontmatter(meta, body, order), encoding="utf-8")


class _FrozenDatetime(datetime):
    """Real datetime subclass with a pinned now() — strftime/strptime intact."""
    _frozen = None
    @classmethod
    def now(cls, tz=None):
        return cls._frozen
```

`SEM = "boardgroup"` is a synthetic stand-in for t1243_8's field, injected by
patching `B.Task._BOARD_KEYS` to `BOARD_LAYOUT_KEYS + (SEM,)` while leaving
`_BOARD_LAYOUT_KEYS` alone — so the layout/shared contract is tested generally,
not waiting on that child. All cases run over **real files** in a temp tree.

#### 4A — seam contract (direct `Task` construction)

1. **Pre-reload external edit survives** — set `board_idx` in memory, then
   `external_edit(status="Done")`; after the save **both** the board field and
   the external `status` are on disk.
2. **Post-reload external edit is lost — the documented window.** Wrap the
   instance's `load` so the external edit runs *after* the real reload returns,
   then assert the edit is gone. Deterministic, no threads. Pins the narrowed
   claim of decision 6 as an executable contract rather than prose.
3. **Hazard C, stale cross-layout — an index-only call never rewrites the
   column.** Object holds `boardcol="c0"`; `external_edit(boardcol="c1")`; call
   `fields=("boardidx",)` with a new index → disk keeps `boardcol: c1` **and**
   takes the new index.
4. **Hazard C mirror — a column-only call never rewrites the index.** Object
   holds `boardidx=10`; `external_edit(boardidx=20)`; call `fields=("boardcol",)`
   → disk keeps `boardidx: 20`.
5. **Hazard A — a layout call never writes a shared field back.**
   `boardgroup="A"` in memory, `external_edit(boardgroup="B")`, call
   `fields=("boardcol","boardidx")` → disk still reads `"B"`, `updated_at`
   untouched.
6. **Hazard B — a semantic-only call never writes stale layout back.** Object
   holds `boardidx=10`; `external_edit(boardidx=20)`; call
   `fields=("boardgroup",)` → disk reads `boardidx: 20` **and** the in-memory
   `boardgroup`.
7. **An intentional combined mutation persists both** —
   `fields=("boardgroup","boardidx")` writes both from memory and timestamps.
8. **Named-field companions** — an `""` tombstone survives; a key absent from
   memory is never invented; a concurrently-edited `status` survives a semantic
   write.
9. **Validation** — `fields=("status",)` and `fields=("boardgruop",)` each raise
   `ValueError` naming the offending key; `fields=()` raises; the file is
   **unmodified** after each raise (the guard runs before any write). Plus an
   `inspect.signature` assertion that `fields` has **no default** — the one
   structural fact that keeps hazard C from being re-introduced by a future
   convenience default.
10. **Timestamp discipline, under `_FrozenDatetime`** — unchanged task + a
    layout `fields` → `diff_snapshots(...)["changed"] == set()` (byte-identical);
    changed `boardidx` → seeded `updated_at: 2020-01-01 00:00` untouched and
    every non-board key and the body survive; `fields=("boardgroup",)` →
    `updated_at` equals the frozen minute exactly; **two semantic writes under
    the same frozen minute leave `updated_at` equal**, and advancing the frozen
    clock by one minute changes it — the non-advancement of decision 7, pinned
    without a wall-clock race.
11. **Missing file** — delete the file, then save → it is **not** recreated.

#### 4B — negative controls (four, automated, no manual revert)

Cases 3, 5, 6 and 8 keep their assertions in helpers the controls re-run
verbatim under a patched-in defective body, asserting `AssertionError`. One
control per rejected design:

- `_legacy_two_name_body` (pre-t1243_2, hardcoded pair) → **case 8 fails** (the
  drop bug this child fixes);
- `_broad_default_body` (ignores `fields`, always writes both layout keys —
  today's behaviour, and any future convenience default) → **case 3 fails**
  (hazard C);
- `_naive_all_board_keys_body` (the task file's "iterate all `BOARD_KEYS`") →
  **case 5 fails** (hazard A);
- `_layout_plus_named_body` (layout ∪ named — this plan's earlier revision) →
  **case 6 fails** (hazard B).

`mock.patch.object` restores every patched attribute even on failure — no
`git checkout` is involved.

#### 4C — call-site mapping (the Step 3 audit, verified)

4A calls the seam with the correct tuple itself, so it proves the *seam* is
right and says nothing about what the *callers* pass. `FLIP_TABLE` does not close
the gap either: it catches a caller that **omits** a field it genuinely mutated
(the mutated value differs from disk, so it fails to persist), but an **extra**
field is byte-identical in an uncontended harness — `swap_tasks` could pass
`("boardcol","boardidx")`, keep every existing assertion green, and still carry
hazard C. Two complementary guards close it:

**Runtime spy through the real callers (primary).** Under
`mock.patch.object(B, "TASKS_DIR", tree / "aitasks")` and the matching
`METADATA_FILE`, build a real `TaskManager()` over a `build_tree` fixture and
wrap `B.Task.reload_and_save_board_fields` to record `(filename, tuple(fields))`
per call. Then invoke each real method and assert the **exact recorded sequence**
— count, order and tuples:

| driver | expected records |
|---|---|
| `manager.move_task_col(name, "c1")` | one `("boardcol","boardidx")` |
| `manager.swap_tasks(a, b)` | two `("boardidx",)`, in call order |
| `manager.normalize_indices("c0")` | one `("boardidx",)` per renumbered task |
| `manager.update_column("c0","c9",…)` | one `("boardcol",)` per task in the column |
| `manager.delete_column("c0")` | one `("boardcol","boardidx")` per task |

Frozen like `FLIP_TABLE`: a new or changed call site must consciously edit this
table. Two of these also get the **end-to-end hazard-C assertion through
production code**, which 4A cannot give: externally change `boardcol` on disk,
then run `manager.normalize_indices("c0")` → the column is **not** reverted; and
externally change `boardidx`, then `manager.update_column(...)` → the index is
**not** reverted.

`mock.patch.object` restores `TASKS_DIR`/`METADATA_FILE` deterministically even
on failure — required, because the suite shares one interpreter and t1243_1's
`IsolationNegativeControlTests` asserts `aitask_board.TASKS_DIR == Path("aitasks")`.

**AST guard (complement).** Parse `aitask_board.py`, map every
`reload_and_save_board_fields` call to its enclosing function and its literal
`fields` tuple, and assert equality with the Step 3 table. It covers
`_move_task_to_extreme` — the one site the runtime spy cannot reach without a
Pilot harness — and fails on a new, removed or relocated call site. It **fails
closed** on a non-literal argument (a computed tuple it cannot read) rather than
skipping it, so "unanalysable" can never pass silently.

### Step 5 — correct every artifact that prescribes the old contract

The superseded contract — `semantic: bool`, iterate all `BOARD_KEYS`, "advances
`updated_at`", callers unchanged — is written into four places. Leaving any of
them would teach the unsafe shape to whoever implements t1243_8 or t1243_11. All
are edited and committed with `./ait git` in the same task-data commit as the plan:

1. **`aitasks/t1243/t1243_2_…md`** (this task) — the `## Implementation plan`
   code block and the `## Verification` bullets (items 2 and 3), to the required
   `fields=` API, the derived-timestamp rule, the current-minute contract, and
   the call-site audit. Add hazards A, B and C as the reason.
2. **`aiplans/p1243_board_task_groups_and_fast_reordering.md`** (parent design) —
   the "Key split" consumer-table row at `:515` (*save-path snapshot loop* → the
   **named, required** field set); the code block and prose at `:527-544`; the
   child-2 decomposition row at `:944` (description and verification cells); and
   the child-8 row's "a group field survives the t1243_2 save seam" at `:950` →
   survives a **named-field** save and is *not* written back by a layout move.
   The plan's *current-state* table (`:42-56`) and anchor re-verification
   (`:113-114`) describe the code **as it was**; they are point-in-time records
   and are deliberately left intact.
3. **`aitasks/t1243/t1243_8_…md`** — the consumer-table row for the save-path
   loop; §3 Timestamp discipline (the bulk path calls
   `reload_and_save_board_fields(fields=("boardgroup",))`; there is no
   `semantic=True` bool); and the verification bullet, as in (2). Also note
   `BOARD_LAYOUT_KEYS` already exists — t1243_8 only appends `"boardgroup"` to
   `BOARD_KEYS`.
4. **`aiplans/p1243/p1243_2_…md`** — needs no manual edit: Step 6 externalization
   runs with `--force` and overwrites it with this plan. `p1243_8`'s plan defers
   to t1243_8's task-file table and needs no edit.

t1243_11 (block moves) adds call sites to this seam; the required `fields`
argument plus 4C's frozen table make it state its mutation, so no advisory note
is needed there.

## Verification

```bash
/home/ddt/.aitask/venv/bin/python -m unittest tests.test_board_persistence_seam -v
bash tests/run_all_python_tests.sh          # read ONLY the last line for the verdict
```

- All 4A cases pass; all four 4B controls raise as expected.
- 4C's runtime table matches exactly for the five `TaskManager` callers, and both
  end-to-end hazard-C assertions hold; the AST guard matches the Step 3 table for
  all seven sites, including `_move_task_to_extreme`.
- **`tests/test_board_movement.py` passes with `FLIP_TABLE` unedited.** Narrowing
  the call sites changes no bytes and no write counts under a single writer, so
  the unchanged frozen table is ground truth for "zero behavioural delta in the
  uncontended case" — **not** for the mapping itself, which 4C owns. **If the
  flip table does change, stop** — that is a real behavioural delta to diagnose,
  not a table to edit (t1243_1's own note: a silent pass after a rewrite is a bug
  in the table).
- `git -C .aitask-data status --porcelain -- aitasks/` shows only the Step 5
  task-file edits — no test run touches the real `aitasks/` tree; the
  `TASKS_DIR` patch is asserted restored after 4C.
- `grep -rn "_BOARD_KEYS\|_BOARD_LAYOUT_KEYS" .aitask-scripts/` shows both
  attributes read, not merely assigned.
- `grep -n "reload_and_save_board_fields()" .aitask-scripts/board/aitask_board.py`
  returns nothing — every call site names its fields.
- `grep -rn "semantic=True\|semantic: bool" aitasks/t1243/ aiplans/p1243*` returns
  nothing — Step 5 left no artifact teaching the superseded contract.

Step 9 (Post-Implementation) then runs the merge / gate / archival flow as usual.

## Risk

### Code-health risk: medium

- **Step 3 changes all seven production call sites** on the board's sole
  layout-write path — a wrong field set at any one of them either stops
  persisting a value the operation did mutate, or silently keeps hazard C alive ·
  severity: medium · → mitigation: 4C pins the mapping two ways — a runtime spy
  asserting the exact recorded tuples through the five real `TaskManager`
  callers (plus two end-to-end hazard-C assertions), and a fail-closed AST guard
  covering all seven sites including the app-level one. `FLIP_TABLE` is kept as
  an independent check on the *uncontended* byte/write behaviour, and its known
  blind spot (an extra field is byte-identical) is what 4C exists for.
- `reload_and_save_board_fields` now raises where it previously could not, inside
  Textual action handlers · severity: low · → mitigation: the argument is always
  a literal in board source, never user data, so a bad value fails on the first
  keypress in development; case 9 asserts the guard runs before any write, so a
  raise cannot leave a half-written file.
- 4C patches `B.TASKS_DIR` / `B.METADATA_FILE` in the shared suite interpreter; a
  leak would point later tests — and t1243_1's isolation control — at a deleted
  temp tree · severity: medium · → mitigation: `mock.patch.object` scoping only,
  never bare assignment, plus an explicit post-block assertion that both
  attributes equal their pre-test values (mirrors t1243_1's env-hygiene finding).
- `fields=` has no shared-key production caller until t1243_8, so the semantic
  branch is unexercised outside tests · severity: low · → mitigation: 4A cases
  5–10 exercise every cell of the decision-2 table, and Step 5 corrects all four
  artifacts so the first real caller uses the intended signature.
- The new test file **cross-imports another test module**, which no test in this
  repo does today · severity: low · → mitigation: the import is of four public
  module-level helpers only, `sys.path` is bootstrapped from `__file__`, and the
  task file and plan both direct this reuse rather than a duplicate fixture.
- Step 5 edits three sibling/parent task-data artifacts · severity: low ·
  → mitigation: the edits are confined to the passages that prescribe this
  seam's API, point-in-time current-state records are deliberately left intact,
  and a grep in Verification proves no artifact still teaches the old contract.

### Goal-achievement risk: low

- The deliverable is specified down to the method body and the per-call-site
  field sets, and every anchor was re-verified at current `HEAD` · severity: low ·
  → mitigation: none needed.
- Hazard C is a **live** bug being fixed opportunistically inside a seam-prep
  child, widening it beyond the task file's stated scope · severity: low ·
  → mitigation: the task file's own invariant ("the seam must not carry a field
  it did not mutate") is what demands it; leaving it would ship a seam whose
  contract its own callers violate on day one. Step 5 records the widened scope
  in the task file rather than deviating silently.
- `_move_task_to_extreme` is verified structurally (AST) but not behaviourally,
  because reaching it needs a Pilot harness · severity: low · → mitigation: it is
  a three-line `board_idx`-only mutation, the AST guard pins its literal tuple,
  and t1243_1's `extreme_top` / `extreme_bottom` flip-table scenarios already
  drive it end-to-end and assert its final on-disk state.
- The narrowed concurrency guarantee (decision 6) and the non-monotonic timestamp
  (decision 7) are weaker than the original task file implied · severity: low ·
  → mitigation: both are stated in the docstring, pinned by 4A cases 2 and 10,
  written into the task file by Step 5, and recorded in Final Implementation
  Notes — t1243_8 already assumes the weaker timestamp.

---

## Post-Review Changes

### Change Request 1 (2026-07-29 13:44) — merge-side field ownership

- **Requested by user:** `aidocs/framework/aitasks_extension_points.md` was
  edited to say `_KEEP_LOCAL_FIELDS` follows `BOARD_LAYOUT_KEYS`, but
  `aitask_merge.py:132` still built it from `BOARD_KEYS`. True only while the two
  are equal — the moment t1243_8 appends `boardgroup`, membership would become
  silently local-wins, contradicting the new guidance and re-creating hazard A at
  the merge layer. Either derive it from `BOARD_LAYOUT_KEYS` now, or state the
  remaining dependency.
- **Changes made:** Derived it now — the same zero-behaviour-change-today,
  structural fix used for the save path. `aitask_merge.py` imports
  `BOARD_LAYOUT_KEYS` instead of `BOARD_KEYS` and `_KEEP_LOCAL_FIELDS =
  frozenset(BOARD_LAYOUT_KEYS)`, with a comment stating that a shared key must
  opt in to its own merge rule rather than inherit silent local-wins. Added
  `MergeFieldOwnershipTests`: one test pinning the exact set, and one —
  `test_no_shared_board_key_is_ever_local_wins` — that keeps meaning as
  `BOARD_KEYS` grows and is what fails if anyone re-points the derivation.
  Verified the guard discriminates: the post-t1243_8 *wrong* derivation leaks
  `boardgroup` into the local-wins set, the current one does not.
  `tests/test_aitask_merge.sh` 43/43. Downstream artifacts updated so t1243_8 no
  longer claims to own this narrowing (`t1243_8` task file §1 + consumer table,
  `p1243_8` Step 1, parent plan `:514` and the child-8 decomposition row).
- **Files affected:** `.aitask-scripts/board/aitask_merge.py`,
  `tests/test_board_persistence_seam.py`,
  `aitasks/t1243/t1243_8_boardgroup_field_and_model.md`,
  `aiplans/p1243/p1243_8_boardgroup_field_and_model.md`,
  `aiplans/p1243_board_task_groups_and_fast_reordering.md`.

### Change Request 2 (2026-07-29 13:44) — task-data commit entanglement

- **Requested by user:** commit `d164c6b3d` ("ait: Start work on t1312") contains
  the contract edits to `t1243_2`, `t1243_8`, `t1243_11` and `t1243_12`. A
  concurrent session's broad `./ait git add aitasks/` swept this task's in-flight
  edits into its own commit. Reverting or rewriting t1312 would therefore delete
  t1243 specifications, and the changes are not attributable to t1243_2.
- **Record (durable, archives with this task):** the affected paths are
  `aitasks/t1243/t1243_{2,8,11,12}*.md`; the content in `d164c6b3d` is
  byte-identical to the working tree (verified with `./ait git diff -- aitasks/t1243/`,
  empty). **If `d164c6b3d` / t1312 is ever reverted or rewritten, these four
  files must be re-checked against this plan — their contract edits belong to
  t1243_2, not t1312.**
- **Why it was not repaired by rewriting history:** `d164c6b3d` is no longer the
  tip; three further commits from the concurrent session sit on top of it
  (`b7920941f` at the time of review), and that session is actively committing to
  the shared `aitask-data` branch. Splitting `d164c6b3d` means rewriting all
  four commits, which would orphan any commit the other session makes during the
  rebase. A revert-then-reapply "forward repair" was also considered and
  **rejected as ineffective**: a later `git revert d164c6b3d` would still strip
  the content cleanly, so it would add two noisy commits while fixing nothing.
- **Disposition:** escalated to the user as an explicit decision rather than
  performed unilaterally, since rewriting shared history is destructive and
  affects another session's work.

### Change Request 3 (2026-07-29 13:57) — ownership documentation

- **Requested by user:** the merge implementation was correct but its
  documentation was internally contradictory. Three defects: (i)
  `task_yaml.py:52-55` and (ii) the parent plan's current-state row `:55` both
  still said `BOARD_KEYS` drives `_KEEP_LOCAL_FIELDS`, which CR1 had just made
  false; and (iii) the extension guide's new 4b claimed a shared key placed in
  `BOARD_LAYOUT_KEYS` "would be written back by every layout move" — **wrong**,
  because the required exact caller tuples prevent that. The real hazards of
  misplacing a shared key are silent local-wins merging and no `updated_at`.
- **Changes made:**
  - `task_yaml.py` — rewrote both comments. `BOARD_LAYOUT_KEYS` is now documented
    as defining **two policies** (silent local-wins merge; layout writes record no
    timestamp), and `BOARD_KEYS` as key ordering + empty-metadata probe + the
    save path's validation vocabulary. Explicitly notes a key is not at risk of
    being written back by unrelated layout moves either way.
  - `aidocs/.../aitasks_extension_points.md` 4b — replaced the false rationale
    with the two real policies, and stated up front that no key is written back by
    a move that did not name it, **whichever set it is in**. 4 now says
    `_KEEP_LOCAL_FIELDS` is *derived from* `BOARD_LAYOUT_KEYS`.
  - Parent plan — added a header to "Verified current state" marking it a
    point-in-time record, and annotated the two rows t1243_2 superseded
    (`reload_and_save_board_fields` and `lib/task_yaml.py BOARD_KEYS`) with both
    the original text and the current behaviour, rather than rewriting history.
  - This plan — corrected two of its own now-imprecise statements (the anchor
    entry for `_KEEP_LOCAL_FIELDS`, and the test-seam note in design decision 4).
- **Note on the error's origin:** the false claim in 4b was a leftover rationale
  from an earlier revision of this plan, where the seam still took a defaulted
  field set. Making `fields` required removed that hazard but the justification
  was not re-swept — the same class of stale-rationale defect this task's Step 5
  exists to prevent.
- **Files affected:** `.aitask-scripts/lib/task_yaml.py`,
  `aidocs/framework/aitasks_extension_points.md`,
  `aiplans/p1243_board_task_groups_and_fast_reordering.md`,
  `aiplans/p1243/p1243_2_board_field_persistence_seam.md`.
- **Verification:** 35/35 seam, 43/43 merge, 12/12 movement (`FLIP_TABLE` still
  unedited).

---

## Final Implementation Notes

- **Actual work done:** the seam now takes a **required, validated** `fields`
  set and persists exactly what a caller names.
  - `lib/task_yaml.py` — `BOARD_LAYOUT_KEYS` / `BOARD_KEYS` split (equal in value
    until t1243_8 appends `boardgroup`).
  - `board/aitask_board.py` — `reload_and_save_board_fields(fields)`: raises on an
    empty or non-board `fields`, derives `semantic` from
    `any(k not in _BOARD_LAYOUT_KEYS)`, keeps the `is not None` tombstone guard
    and the never-recreate-a-deleted-file behaviour. Both class attributes
    (`_BOARD_LAYOUT_KEYS`, `_BOARD_KEYS`) are now read, retiring the dead
    assignment. **All seven call sites audited** to their actual mutation — five
    narrowed to a single key.
  - `board/aitask_merge.py` — `_KEEP_LOCAL_FIELDS` derived from
    `BOARD_LAYOUT_KEYS` (CR1).
  - `tests/test_board_persistence_seam.py` — **new**, 35 tests: seam contract,
    timestamp discipline under a frozen clock, four negative controls, the
    call-site mapping (runtime spy through five real `TaskManager` callers + a
    fail-closed AST guard with its own discrimination self-tests), and merge
    field ownership.
  - `aidocs/framework/aitasks_extension_points.md` — layer 4 corrected, new
    layer 4b for the save path.

- **Deviations from plan:**
  1. **Three defects, not two.** Planning found a *live* third bug (hazard C):
     five of seven call sites mutate one layout key and write back both, so
     `normalize_indices` could yank a card out of a column another writer had just
     moved it to. Fixing it widened the change from one method to all seven call
     sites and raised code-health risk low → medium.
  2. **`semantic: bool` became a required `fields` set.** Three review rounds
     drove this: a bool could timestamp a pure layout move; a `LAYOUT ∪ fields`
     union still let a membership write clobber a newer `boardidx`; and an
     unvalidated tuple let a typo (`boardgruop`) timestamp a write whose value was
     silently dropped. The final shape makes each of those unrepresentable.
  3. **Step 5 covered six artifacts, not four.** The plan enumerated t1243_2, the
     parent design and t1243_8; the verification grep found **t1243_11** and
     **t1243_12** also prescribing `semantic=True`, plus
     `aidocs/framework/aitasks_extension_points.md` naming the wrong constant and
     omitting the save path entirely. Running the plan's own greps is what caught
     them.
  4. **No subprocess isolation** (t1243_1 uses one). `Task` needs no directory
     constant, and `TaskManager` needs only `mock.patch.object` on `B.TASKS_DIR` /
     `B.METADATA_FILE` — the module *attribute* is a different seam from the
     `TASK_DIR` *env var* whose in-process override t1243_1 proved inert.
  5. **Added two AST-guard self-tests and one merge-ownership pair** beyond the
     plan, because the guard's fail-closed branch and the merge invariant were
     otherwise unexercised.

- **Issues encountered:**
  - The full suite reports **1 failure**, `test_board_work_report`
    `WorkReportFullColumnUnderSearchTests.test_hidden_cards_still_listed`
    (`133 != 134`). **Not caused by this task** — see Upstream defects. It is a
    live-tree data condition introduced by a concurrent session at 09:55, before
    any code edit here; `_parse_filename`, `get_column_tasks` and the work-report
    path are untouched by this diff.
  - **A concurrent session swept this task's task-file edits into its own
    commit** — see Change Request 2. Content intact, attribution wrong; the user
    chose to keep a documented record rather than rewrite shared history.
  - The plan's own verification grep (`semantic=True|semantic: bool`) over-matched
    its own corrective prose; it needs the "there is no …" exclusions applied when
    re-run.

- **Key decisions:**
  - `fields` is **required**. A default is always plausible and never stated —
    which is precisely how hazard C survived unnoticed.
  - Persistence *and* timestamp both derive from the named set. Ownership, not a
    second flag, so no combination can be individually wrong.
  - The split constants landed here rather than in t1243_8, so t1243_8's one-line
    `BOARD_KEYS` append cannot silently change either the save path or the merge
    rule.
  - Contract claims narrowed to what the code does: the reload→save window is
    **not** atomic, and a semantic write **sets the current minute** rather than
    advancing. Both pinned by tests instead of prose.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_create.sh:1809 — filename="t${task_num}_${task_name}.md"
    has no guard that task_num is non-empty, so an empty id silently produces a
    numberless task file (t_<slug>.md). One exists in the live tree
    (aitasks/t_refresh_codeagent_suite_default_model_expectations.md, committed
    2026-07-29 09:55 in 9e7f18326) and it breaks test_board_work_report.`
  - `.aitask-scripts/board/aitask_board.py:7258-7262 — the work-report entries
    loop silently "continue"s past a task whose filename TaskCard._parse_filename
    cannot parse, so the selection screen under-reports versus get_column_tasks;
    test_board_work_report asserts the two are equal, so one unparseable file in
    the tree fails the suite with no indication of which file or why.`

- **Notes for sibling tasks:**
  - **t1243_8 is now smaller.** `BOARD_LAYOUT_KEYS` and the `_KEEP_LOCAL_FIELDS`
    narrowing already exist; it only appends `"boardgroup"` to `BOARD_KEYS`. Its
    task file and plan were updated accordingly. Its membership writes use
    `reload_and_save_board_fields(fields=("boardgroup",))` — **there is no
    `semantic=True` bool**.
  - **Never widen the save path to iterate `BOARD_KEYS`.** Three hazards (A/B/C)
    and four negative controls in `tests/test_board_persistence_seam.py` exist
    specifically to stop that; each control pins one rejected design.
  - **t1243_11 must name `("boardgroup",)` only** on formation/removal. Naming
    `boardidx` too would discard a concurrent move.
  - **`EXPECTED_CALL_SITES` is frozen like `FLIP_TABLE`.** Any task adding a call
    site (t1243_11 especially) must consciously edit it; a silent pass after a
    rewrite is a bug in the table.
  - `updated_at` is minute-resolution and **not monotonic**. Do not build
    field-level causality on it — t1243_8's base-aware detection is the reason.
  - Anyone testing board internals: `TaskManager` is constructible in-process by
    patching `B.TASKS_DIR` / `B.METADATA_FILE`; a subprocess is only needed when
    the *env var* or a Textual app is involved.
