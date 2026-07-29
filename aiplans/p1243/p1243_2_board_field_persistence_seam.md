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
`_KEEP_LOCAL_FIELDS`, all of which read the module-level `BOARD_KEYS`.

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
