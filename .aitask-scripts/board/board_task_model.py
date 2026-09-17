"""The board's task model: `Task` and the move/merge result types (t1794_4).

Moved verbatim out of `aitask_board.py` so a second App (the stand-alone
`ait trails` TUI) and headless callers can hold tasks without importing the
Kanban app. `aitask_board.py` re-exports every name here, so `ab.Task` keeps
resolving; the class is ONE object across every fixture load.

Contract (t1794, C1/C2): flat imports only, never `aitask_board`; no task-dir
resolution — a `Task` is built from the path its caller hands it. A stub of a
name called inside this module (`datetime` for `Task._update_timestamp`) must
patch it HERE, reachable as `ab.board_task_model`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from atomic_write import atomic_write_text
from board_columns import UNORDERED_ID
from task_yaml import (
    BOARD_KEYS, BOARD_LAYOUT_KEYS, parse_frontmatter, serialize_frontmatter,
)


class Task:
    # Both are READ by reload_and_save_board_fields: the layout set is its
    # "is this a semantic write?" discriminator; the full set is the vocabulary
    # its required `fields` argument is validated against.
    _BOARD_LAYOUT_KEYS = BOARD_LAYOUT_KEYS
    _BOARD_KEYS = BOARD_KEYS

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.filename = filepath.name
        self.content = ""
        self.metadata = {}
        self._original_key_order: list = []
        self.archived = False
        self._search_haystack = None        # memo; see `search_haystack`
        self.load_ok = True
        self.load()

    @classmethod
    def from_text(cls, filepath: Path, raw: str, archived: bool = False) -> "Task":
        task = cls.__new__(cls)
        task.filepath = filepath
        task.filename = filepath.name
        task.content = ""
        task.metadata = {}
        task._original_key_order = []
        task.archived = archived
        # `__new__` bypasses __init__, so the memo slot must be seeded here too —
        # without it `search_haystack` raises AttributeError on archived tasks.
        task._search_haystack = None
        task.load_ok = True                 # parsed from text, never read failed
        result = parse_frontmatter(raw)
        if result:
            task.metadata, task.content, task._original_key_order = result
        else:
            task.content = raw
        return task

    def _invalidate_search_haystack(self):
        self._search_haystack = None

    @property
    def search_haystack(self) -> str:
        """Lowercased ``"<filename> <metadata>"`` — the board search corpus (t1243_4).

        `apply_filter` used to rebuild this string per card per pass. It is memoized
        on the **Task**, not on the card, for two reasons: t1243_10 evaluates
        collapsed-group members that mount no widget at all, and
        `_move_task_vertical` mutates `board_idx` and then reorders the DOM *without*
        a recompose — a card-lifetime memo would serve a stale string there, because
        the corpus stringifies the whole metadata dict, board keys included.

        The memo is invalidated at the full set of sites that can change its inputs,
        enumerated rather than assumed:

        * `load()` — metadata replaced wholesale. Also covers `TaskManager.reload_task`,
          which calls `load()` on the SAME object rather than building a new one.
        * `save()` — the tail of every persisted metadata mutation (`save_with_timestamp`,
          the detail-screen edits, the dependency-cleanup helpers).
        * the `board_col` / `board_idx` setters — in-memory board-key mutation with no
          save in between (the gap-indexing movers).

        A metadata mutation that is neither saved nor a board-key write would go stale;
        there is none today.
        """
        if self._search_haystack is None:
            self._search_haystack = f"{self.filename} {self.metadata}".lower()
        return self._search_haystack

    def load(self):
        """Load task from disk. Returns True on success, False on failure.

        Also records the outcome on `self.load_ok`, because `__init__` discards
        the return value and a failed load is indistinguishable from an empty
        stub afterwards — both leave `metadata == {}` (t1377_4).
        """
        self._invalidate_search_haystack()
        if self.archived and not self.filepath.exists():
            self.load_ok = True
            return True
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                raw = f.read()

            result = parse_frontmatter(raw)
            if result:
                self.metadata, self.content, self._original_key_order = result
            else:
                self.metadata = {}
                self._original_key_order = []
                self.content = raw
            self.load_ok = True
            return True
        except Exception as e:
            self.metadata = {}
            self._original_key_order = []
            self.content = str(e)
            self.load_ok = False
            return False

    def save(self):
        self._invalidate_search_haystack()
        content = serialize_frontmatter(self.metadata, self.content, self._original_key_order)
        # Atomic replace, not `open(..., "w")` (t1379): a plain write truncates
        # the task file before any bytes land, and `_iter_active_task_frontmatter`
        # (lib/trail_discovery.py) reads live task frontmatter from disk while the
        # board is running.
        atomic_write_text(str(self.filepath), content)

    def _update_timestamp(self):
        """Update the updated_at metadata field to current time."""
        self.metadata["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    def save_with_timestamp(self):
        """Save task with updated_at timestamp. Use for semantic metadata changes."""
        self._update_timestamp()
        self.save()

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

        Skips the save if the file no longer exists (e.g. archived/deleted).
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
            if value is not None:  # preserves "" (tombstone); never invents a key
                self.metadata[key] = value
        if semantic:
            self._update_timestamp()
        self.save()

    @property
    def board_col(self):
        return self.metadata.get("boardcol", UNORDERED_ID)

    @board_col.setter
    def board_col(self, value):
        self.metadata["boardcol"] = value
        self._invalidate_search_haystack()

    @property
    def board_idx(self):
        return self.metadata.get("boardidx", 0)

    @board_idx.setter
    def board_idx(self, value):
        self.metadata["boardidx"] = value
        self._invalidate_search_haystack()


@dataclass(frozen=True)
class MoveResult:
    """Outcome of a board move (t1243_3).

    A bare bool cannot tell a caller WHICH items were refused, and the
    move-to-column command (t1243_7) has to name them back to the user. So the
    move methods report `moved` in input order, `refused` as `(name, reason)`
    pairs, and whether a compaction ran.

    `refused` non-empty always means NOTHING was written — the batch move
    resolves every name before its first write.
    """

    moved: tuple[str, ...] = ()
    refused: tuple[tuple[str, str], ...] = ()
    compacted: bool = False

    @property
    def ok(self) -> bool:
        return not self.refused


#: Reserved `MergeResult.failed` keys. Never real filenames, so a caller can tell
#: a task-write failure from a config-write failure — and a retryable merge from a
#: pending local cleanup.
MERGE_METADATA_KEY = "<metadata>"
MERGE_METADATA_LOCAL_KEY = "<metadata:local>"
MERGE_UNVERIFIABLE_KEY = "<unverifiable>"


@dataclass(frozen=True)
class MergeResult:
    """Outcome of an N->1 column merge (t1377_4).

    Deliberately NOT a `MoveResult`. That type's docstring guarantees "`refused`
    non-empty always means NOTHING was written", and a merge writes one task file
    per member before touching config — so reporting write failures through
    `refused` would make that invariant a lie for every existing consumer.

    `refused` here keeps the same meaning (input validation only, nothing
    written). `failed` is the separate channel for partial progress.

    **The merge is not transactional, and recovery depends on the failure
    class.** Per-file writes are atomic (`Task.save` -> `atomic_write_text`), so
    no file is ever corrupt, but the multi-file operation is not:

    ==========================  =========================  ======================
    failure                     in-memory left as          retry with
    ==========================  =========================  ======================
    task write (OSError)        reconciled to disk         `merge_columns`
    metadata, project write     rolled back pre-removal    `merge_columns`
    metadata, local write       as-is (sources removed)    `save_metadata`
    ==========================  =========================  ======================

    The first two converge on a re-run because in-memory state matches disk, so a
    member is absent from its source exactly when it really moved. The third
    CANNOT be retried with `merge_columns`: the column removal is already durable,
    so a fresh manager refuses the sources as unknown ids. Its pending work is the
    user-local `collapsed_columns` prune, which `_prune_orphan_collapsed_columns`
    also heals at load time on any later session.
    """

    merged: tuple[str, ...] = ()
    failed: tuple[tuple[str, str], ...] = ()
    sources_removed: tuple[str, ...] = ()
    refused: tuple[tuple[str, str], ...] = ()

    @property
    def complete(self) -> bool:
        return not (self.failed or self.refused)
