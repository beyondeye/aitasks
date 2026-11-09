---
priority: medium
effort: medium
depends: [t1981_6]
issue_type: feature
status: Ready
labels: [task_relations, tui, board]
gates: [risk_evaluated]
anchor: 1981
created_at: 2026-11-04 15:39
updated_at: 2026-11-04 15:39
---

## Context

Child of t1981. Design: `aidocs/framework/task_relations.md`. **Read D10.** Code
agents are the first consumers of relations (premise 7). This child adds the
human view of relations and obsolete tasks.

## Scope

1. **A read-only Textual TUI, `ait relations`**, with two tabs.
   - **Relations:** a task picker, then that task's relations: direction, type,
     description, basis, evidence, freshness (`stale:*`), confirmation and
     stage. Also its neighbourhood (relations of related tasks, one hop) and the
     store state lines (disabled / not analysed / stale store).
   - **Obsolete:** tasks sorted by band, with reasons and evidence. Actions go
     through the existing CLIs only, never directly:
     - open the task (board);
     - send a note (`/aitask-note` hand-off or `ait note`);
     - fold (the existing fold flow);
     - dismiss (`ait obsolete dismiss`);
     - archive as obsolete (`aitask_archive.sh --obsolete`).

     Destructive actions ask for confirmation.
2. **Registration** in the TUI switcher (`KNOWN_TUIS` in
   `.aitask-scripts/lib/tui_switcher.py`) and its launcher `.sh`.
3. **Board detail screen**: a "Relations: n (k stale)" field, with a key that
   opens the relations TUI on that task.

## Key files

- New: the TUI module under `.aitask-scripts/` (follow the board package layout
  conventions), the launcher script, tests.
- Changed: `lib/tui_switcher.py`, the board detail screen.

## Reference patterns

- **Read `aidocs/framework/tui_conventions.md` first**: keybindings, the
  switcher, the shared screens.
- **Read `aidocs/framework/testing_conventions.md`** for `App.run_test` and
  `@work` workers.
- `ait trails`: a read-only TUI over a stored artifact. It is the closest
  analogue.

## Implementation plan

See `aiplans/p1981/p1981_7_relations_tui.md`.

## Verification

- `App.run_test` tests over fixture store data: both tabs render; state lines
  for disabled / empty / stale; actions dispatch the right CLI.
- Keybinding dispatch tests, not just render tests.
- The switcher entry works.
- Website docs are t1981_8.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1981_6** id=2026-11-09T09:17:01Z.df4c46096387d7beacf6f601 from=t1981_6 from_verified=yes at=2026-11-09T09:17:01Z base=a5763bd4eaaf17b0afa044e1f1864ddfc2836923 base_branch=main dirty=yes host=omg16
>
> | From t1981_6 (obsolescence layer), committed in e9f3d85a8. Advisory context for the TUI's Obsolete tab.
> | 
> | - **Contract:** `aidocs/framework/task_relations.md` D9, "Obsolescence API".
> | - **Read helpers:** `lib/obsolete_cli.py` has `assessment(store, snap, tid)` (returns the record and its dismissal state), `inputs_freshness(...)`, `list_rows(root, store, snap, min_band, include_dismissed)` and `pick_view(...)`. `ait obsolete show <id> --json` and `ait obsolete evidence <id> --json` exist.
> | - **Only signal rows are stored** in the record's `evidence[]`. Context rows (path facts, age, a non-stale premise, completed origins) are never stored, so the tab must read them live through `evidence --json`.
> | - **`evidence` reports `INCOMPLETE:` in some cases.** It does so for a corrupt or unreachable store; for example, a never-written store read with `--no-fetch` gives `store_unreachable:no_fetch`. Show that as "unknown", never as clear.
> | - **Actions** go through `ait obsolete review` / `dismiss` and `aitask_archive.sh --obsolete`. Folding validates both ends by parsing `aitask_fold_validate.sh` `VALID:` lines.
