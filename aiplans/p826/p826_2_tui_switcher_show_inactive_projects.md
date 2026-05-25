---
Task: t826_2_tui_switcher_show_inactive_projects.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_1_registry_resolver_projects_cmd_and_create_flag.md, aitasks/t826/t826_3_website_docs_multi_project_workflow.md, aitasks/t826/t826_4_manual_verification_brainstorm_cross_repo_project_references.md
Archived Sibling Plans: aiplans/archived/p826/p826_1_registry_resolver_projects_cmd_and_create_flag.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-25 (pending — append after externalization)
  - claudecode/opus4_7_1m @ 2026-05-25 19:04
---

# Plan: TUI switcher surfaces registered-but-inactive projects (t826_2)

## Context

Second sibling under t826. Today the `ait` IDE TUI switcher's top
"Session:" row only lists projects whose tmux sessions are already
running on the server — to make project X visible in the switcher I
have to `cd` into project X first and run `ait ide` to spin up its
session. This child consumes the per-user registry shipped by t826_1
(`~/.config/aitasks/projects.yaml`) to surface every registered project
in the switcher's Session row even when no live tmux session exists for
it. Selecting an inactive project (Left/Right onto it, then choosing
any TUI from its list) spawns the project's tmux session using the
same bootstrap `ait ide` uses, then `switch-client`s to it.

**Scope note (locked by parent brainstorm):** `ait monitor` is
**out of scope**. Only the TUI switcher gains inactive-project
visibility. The new `include_registered` kwarg on
`discover_aitasks_sessions` defaults to `False` so monitor and every
other current caller is byte-identical to today.

## Verification notes (verify-path refinements from the inline plan)

1. **`tui_switcher.py:8-13` is the module docstring, not code.** The
   actual enumeration call site is `_init_multi_state(discover_aitasks_sessions())`
   at line 378. Multiple downstream sites need to tolerate
   `session=None` for inactive entries: `_render_session_row`
   (line 465), `_cycle_session` (line 639), `_project_root_for_session`
   (line 384), `_populate_list_for` (line 539), `_switch_to`
   (line 771), `_teleport_if_cross` (line 798), and the various
   shortcut/spawn helpers that operate on `self._session`.

2. **`aitask_ide.sh` has three bootstrap paths, not one.** Lines
   123-137 (already inside tmux — uses `new-window`), 139-146 (existing
   session — `attach`), and 148-155 (fresh session — `new-session -d`
   + `attach`). Only the fresh-session path's *spawn* portion is what
   the switcher needs (it must NOT attach — the switcher uses
   `switch-client` for cross-session teleport instead). The extract
   should be a `spawn_session_detached <project_root>` helper that:
     - Reads the target project's `aitasks/metadata/project_config.yaml::tmux.default_session`
       (mirroring `resolve_session()` in `aitask_ide.sh`, falling back
       to `"aitasks"` per existing behavior).
     - `tmux new-session -d -s "$SESSION" -n monitor 'ait monitor'`
       (with `cwd=<project_root>` so the monitor window starts in the
       right project).
     - Calls `set_project_registry`'s body (tmux global env var write +
       `aitask_projects.sh add`).
     - Optionally seeds the syncer window (reuse `ensure_syncer_window`'s
       body — same `read_syncer_autostart` logic on the target
       project's config).

3. **`include_registered=True` on the Python side needs a YAML reader.**
   `aitask_projects.sh::list_registry_entries` (lines 124-174) is bash
   and not callable from Python without a subprocess. Two options:
     - **(Chosen)** Add a small `_read_registry_index() -> list[tuple[str, Path]]`
       helper in `agent_launch_utils.py` that line-parses the registry
       file with the same patterns the awk script uses. No PyYAML
       dependency, mirrors the bash reader's behavior 1:1, single
       source of truth for the field set (`name`, `path`, optional
       `git_remote`, optional `last_opened`).
     - Rejected: subprocess-shell to `aitask_projects.sh` — would
       require a new machine-readable verb and adds spawn cost on
       every TUI render.

4. **Effective session name for inactive entries.** A project's tmux
   session name is **not** always its directory basename — it comes
   from `aitasks/metadata/project_config.yaml::tmux.default_session`
   (with `"aitasks"` as a literal fallback when the field is absent).
   The `AitasksSession` produced for an inactive entry should carry
   the resolved session name in its `session` field (not `None`) so
   `_render_session_row` can show it and `_cycle_session` can land on
   it. A new `is_live: bool` field (rather than overloading
   `session=None`) cleanly distinguishes the two cases without
   breaking the `session: str` invariant downstream code already
   relies on.

5. **`tests/lib/test_scaffold.sh` baseline.** Confirmed current libs:
   `aitask_path.sh`, `terminal_compat.sh`, `python_resolve.sh`,
   `yaml_utils.sh`. If `tmux_bootstrap.sh` becomes part of `./ait`'s
   source-on-startup chain, the scaffold must be updated in the same
   commit (per CLAUDE.md). If it's only sourced on-demand by
   `aitask_ide.sh` (and shelled out to by the switcher), no scaffold
   update is needed. **Decision: source on-demand** — only
   `aitask_ide.sh` sources it; the switcher invokes it via subprocess.

## Implementation Plan

### Step 0 — Spawn follow-up sibling for stale-registry UX

Before touching any code, create a new sibling brainstorm task under
the t826 parent capturing the stale-registry UX work. This ensures
the follow-up is committed to disk before t826_2 implementation
starts (so it can't be lost in the workflow). The task is a
brainstorm/design task (no implementation yet — the user wants to
think about UX first).

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --parent 826 \
  --name "brainstorm_stale_registry_ux" \
  --priority medium \
  --effort medium \
  --type feature \
  --labels "brainstorming,cross_repo,tui_switcher,aitask_projects" \
  --desc-file - <<'TASK_DESC'
## Context

Spun off during t826_2 (TUI switcher surfaces inactive projects).
t826_2 silently excludes STALE registry entries (path missing the
`aitasks/metadata/project_config.yaml` marker) from the switcher's
Session row, matching how the rest of the resolver already filters
them. That's the safe minimum, but it leaves the user blind: a
project that was moved, renamed, or deleted on disk just disappears
from the switcher with no signal, and the registry entry sits stale
forever.

This brainstorm task scopes the UX for surfacing and resolving
stale registry entries. **No implementation in this round — design
first.**

## Goals

1. **Detection trigger** — where does the staleness check fire?
   Every switcher render (cheap, but adds latency)? On a background
   timer? Only on-demand via `ait projects doctor`? Some hybrid
   (e.g., cache freshness with a TTL)?

2. **Surface in switcher** — should STALE entries appear in the
   Session: row with a visual marker (e.g., `?` or red)? Or hide
   them from the switcher entirely and surface only in
   `ait projects list`? Trade-off: visibility vs. clutter for users
   who've registered many projects.

3. **`ait projects` verbs to add** — minimum probably:
   - `ait projects prune` — delete every STALE entry, with
     `--dry-run` and per-entry confirm.
   - `ait projects update <name> <new_path>` — repoint a known
     entry whose path moved.
   - `ait projects remove <name>` — drop an entry explicitly
     (carried over from t826_1's out-of-scope list).
   - `ait projects doctor` (optional) — interactive scan that
     offers prune/update/keep for each STALE entry.

4. **Auto-clone from `git_remote`** — for entries with a recorded
   `git_remote`, should `doctor` (or a `--clone` flag) offer to
   re-clone the project into the original path? Useful for cloud
   agents that lose `/home/<user>/Work/...` between runs. Risk:
   nudges users to re-create stale paths instead of repointing.

5. **Switcher behavior when a selected entry turns out to be
   STALE between `ait projects list` and a `tmux new-session` call**
   — race condition (path was valid at switcher mount, deleted by
   the time the user hits Enter). Should the bootstrap helper
   propagate a clear error to the switcher overlay
   (e.g. `BOOTSTRAP_FAILED:stale_path`) and the switcher should
   offer prune/repoint inline?

## Open Questions

- Is the staleness check expensive enough to need caching, or is a
  bare `os.path.isfile` per registry entry on every switcher render
  fine? (Probably the latter — registries will have <20 entries
  in practice.)
- Should `last_opened` factor in? E.g., entries not opened in N
  months auto-prune candidates?
- Where does the cloud-agent / per-machine path-divergence problem
  fit? (Same registry on two PCs with different home paths.) Is
  that this task's concern or a separate per-machine override
  brainstorm?

## Out of Scope

- Implementation of any of the above — this round produces a
  design decision + a list of follow-up child implementation
  tasks under t826 (or a new parent if the scope grows).
- Cross-repo *merge* coordination, CI/pipelines (carried over
  from parent brainstorm t826).

## References

- Parent brainstorm: `aitasks/t826_brainstorm_cross_repo_project_references.md`
- Sibling t826_1 archive plan:
  `aiplans/archived/p826/p826_1_registry_resolver_projects_cmd_and_create_flag.md`
  (the LIVE / OK / STALE status semantics it ships).
- Sibling t826_2 (this brainstorm's origin):
  `aitasks/t826/t826_2_tui_switcher_show_inactive_projects.md`
  ("Out of Scope" section explains why staleness UX is deferred).
- Authoring-side aidoc: `aidocs/cross_repo_references.md` (registry
  schema + resolver semantics).
TASK_DESC
```

After creation, capture the new task ID (parse from the
`Created: aitasks/t826/t826_<N>_brainstorm_stale_registry_ux.md`
output) and update t826_2's "Out of Scope" cross-reference to point
at the concrete new sibling ID. (The new sibling auto-registers
under t826's `children_to_implement` via the `--parent` flag.)

### Step 1 — Extend `AitasksSession` dataclass

`.aitask-scripts/lib/agent_launch_utils.py` (lines 74-85):

```python
@dataclass(frozen=True)
class AitasksSession:
    session: str          # tmux session name (resolved from config for inactive)
    project_root: Path
    project_name: str
    is_live: bool = True  # False when synthesized from the per-user registry
```

`is_live=True` default preserves existing constructor call sites
(line 309 in `discover_aitasks_sessions`) — they need no change.

### Step 2 — Add `_read_registry_index` helper

`.aitask-scripts/lib/agent_launch_utils.py` (new private helper, near
the existing `_read_registry_entry` / `_walk_up_to_aitasks` block,
~line 254):

```python
def _read_registry_index() -> list[tuple[str, Path]]:
    """Read `~/.config/aitasks/projects.yaml` as (name, path) pairs.

    Mirrors `aitask_projects.sh::list_registry_entries` with a simple
    line parser — no PyYAML dependency. Honors the
    `AITASKS_PROJECTS_INDEX` env var (same override the bash side
    supports). Skips entries whose path no longer holds the project
    marker file (stale entries are treated as absent for the switcher,
    matching the bash side's STALE handling).
    """
```

Behavior:
- Path: `os.environ.get("AITASKS_PROJECTS_INDEX") or "~/.config/aitasks/projects.yaml"`
  (expand `~`).
- Returns `[]` if the file doesn't exist or is empty.
- Parse: walk lines, on `- name:` line emit the prior entry (if any)
  and start a new one; on `path:` line capture the path. Mirror the
  unquote logic the awk parser uses (strip surrounding `"` / `'`).
- Skip entries where the path doesn't exist or doesn't contain
  `aitasks/metadata/project_config.yaml`.

### Step 3 — Resolve target session name from project config

New helper in `agent_launch_utils.py`:

```python
def _read_default_session(project_root: Path) -> str:
    """Read `tmux.default_session` from a project's config; default 'aitasks'."""
```

Mirrors `aitask_ide.sh::resolve_session` (lines 46-72), reading the
`tmux:` block and `default_session:` field with the same awk-style
indentation rules. Falls back to `"aitasks"` literal when absent
(matching the bash default).

### Step 4 — Extend `discover_aitasks_sessions` with `include_registered`

`.aitask-scripts/lib/agent_launch_utils.py` (lines 255-316):

```python
def discover_aitasks_sessions(
    *, include_registered: bool = False
) -> list[AitasksSession]:
```

- Keep existing live-tmux discovery loop (lines 271-313) untouched.
  All entries it produces have `is_live=True` (the default), so they
  remain byte-identical to today.
- After the live-tmux loop, when `include_registered=True`:
  - Build a `live_names = {s.project_name for s in found}` set
    (dedupe by `project_name`, since session naming may differ
    between live and registry views).
  - For each `(name, root)` in `_read_registry_index()`:
    - If `name in live_names`: skip (already covered by a live entry).
    - Otherwise: synthesize
      `AitasksSession(session=_read_default_session(root), project_root=root, project_name=name, is_live=False)`
      and append.
- Resort `found` by `session` at the end (same as today).

**Crucial invariant**: when called without `include_registered`, the
output is byte-identical to today. Captured by Step 8's regression test.

### Step 5 — Extract bootstrap helper

Create `.aitask-scripts/lib/tmux_bootstrap.sh`:

```bash
#!/usr/bin/env bash
# tmux_bootstrap.sh - Shared "spawn a project's tmux session detached"
# helper. Source from aitask_ide.sh; shell out to from tui_switcher.py
# (via the standalone CLI invocation form below).
set -euo pipefail

# Standalone CLI form (called by tui_switcher.py via subprocess):
#   tmux_bootstrap.sh <project_root>
# Sources its own deps when invoked as a script (vs. sourced as a lib).
```

Public functions exported by sourcing:
- `spawn_session_detached <project_root>` — the full bootstrap:
  resolve session name from `<project_root>/aitasks/metadata/project_config.yaml`,
  `tmux new-session -d -s "$SESSION" -c "$project_root" -n monitor 'ait monitor'`
  (no-op via `tmux has-session` guard if already exists), set
  `AITASKS_PROJECT_<sess>` global env, call `aitask_projects.sh add`,
  optionally seed syncer window via `ensure_syncer_window` logic ported
  from `aitask_ide.sh` (reading the target project's autostart flag).
- Helpers ported from `aitask_ide.sh`: `_resolve_session_for_root`,
  `_read_syncer_autostart_for_root`, `_set_project_registry_for_root`,
  `_ensure_syncer_window_for_session` (parameterized versions of the
  inline functions today).

When invoked as `bash tmux_bootstrap.sh <project_root>` (standalone),
sources its own dependency chain
(`terminal_compat.sh`) and dispatches to `spawn_session_detached`.

**Update `aitask_ide.sh`** (lines 96-155):
- `source "$SCRIPT_DIR/lib/tmux_bootstrap.sh"` near the existing
  `terminal_compat.sh` source (line 6).
- Replace `resolve_session`, `read_syncer_autostart`,
  `set_project_registry`, `ensure_syncer_window` bodies with thin
  wrappers that delegate to the helper functions on `"$PWD"`. The
  three call paths (inside-tmux line 123, existing-session line 139,
  fresh-session line 148) keep their existing structure — only the
  spawn body for the fresh-session path (line 152) is now equivalent
  to `spawn_session_detached "$(pwd)"` (followed by the existing
  `exec tmux attach` line). For consistency, keep the inline form
  for the inside-tmux / existing-session paths so attach semantics
  stay obvious.

### Step 6 — Wire `tui_switcher.py` to consume registry entries

`.aitask-scripts/lib/tui_switcher.py`:

- Line 378 (`on_mount`):
  `self._init_multi_state(discover_aitasks_sessions(include_registered=True))`.

- `_init_multi_state` (line 431): treat synthesized entries
  (`is_live=False`) the same as live ones for membership / multi_mode
  purposes. Multi-mode triggers iff `len(sessions) >= 2` AND either
  the attached session is in `sessions` OR there's at least one live
  entry. (Edge case: switcher opened from a non-aitasks session, no
  live aitasks sessions, but registry has entries — show single-session
  view of the registry's first entry. Document the behavior in a
  comment.)

- `_render_session_row` (line 465): render inactive entries with the
  **same** styling as live ones (per user preference — no extra
  marker). They appear in the Session: row alongside live entries.
  The `▶` attached-session marker still only applies to the live
  attached session.

- `_project_root_for_session` (line 384): already iterates
  `self._all_sessions` to find a matching `project_root` — works
  unchanged for inactive entries (their `session` field carries the
  resolved name, and their `project_root` is the registry path).

- `_populate_list_for` (line 539): when the selected session is
  inactive (no live tmux session), `get_tmux_windows(session)`
  returns `[]` — so every TUI entry in the list naturally renders as
  "not running" (dim circle, the existing display path). No code
  change needed beyond confirming this branch works; add a guard if
  `get_tmux_windows` raises on a non-existent session.

- `_switch_to` (line 771) — new pre-spawn branch:
  ```python
  selected_entry = next((s for s in self._all_sessions if s.session == self._session), None)
  if selected_entry is not None and not selected_entry.is_live:
      # Bootstrap the inactive session before doing anything else.
      script = str(Path(__file__).resolve().parent / "tmux_bootstrap.sh")
      result = subprocess.run(
          ["bash", script, str(selected_entry.project_root)],
          capture_output=True, text=True, timeout=15,
      )
      if result.returncode != 0:
          self.app.notify(
              f"Failed to bootstrap session for {selected_entry.project_name}",
              severity="error",
          )
          return
      # The session now exists; mark this entry as live for the rest
      # of the dispatch so _teleport_if_cross fires correctly.
      # (No need to refresh self._all_sessions — we just need
      # _teleport_if_cross's "session != attached" check, which is
      # already true.)
  # ... existing _switch_to body ...
  ```
- Cover the same bootstrap call in `_launch_git_with_companion`,
  `action_shortcut_explore`, `action_shortcut_create` — every path
  that spawns a window in `self._session`. Easiest: extract a
  `_ensure_session_live() -> bool` helper that runs the bootstrap
  once-per-action and returns True/False, and call it at the top of
  `_switch_to` and the three shortcut spawn paths.

### Step 7 — Tests

Create `tests/test_discover_include_registered.py`:

- Round-trip:
  - Set up a fake `AITASKS_PROJECTS_INDEX` pointing at a temp file
    listing two fake projects (each with a real
    `aitasks/metadata/project_config.yaml` marker).
  - Call `discover_aitasks_sessions(include_registered=True)` from a
    process with no tmux access (mock `subprocess.run` for
    `tmux list-sessions` to return empty / failure).
  - Assert both fake projects appear with `is_live=False` and the
    resolved session name comes from each project's
    `tmux.default_session` (test both cases: with field set, and
    fallback to `"aitasks"`).
- Stale skip: an entry whose path is missing the marker file is
  excluded.
- Index override: confirm `AITASKS_PROJECTS_INDEX` env var is honored.

Create `tests/test_discover_default_unchanged.py` (regression):

- Mock `tmux list-sessions` / `tmux list-panes` to return a fixed,
  representative response that today produces a known
  `AitasksSession` list.
- Call `discover_aitasks_sessions()` (no flag).
- Assert the returned list is byte-identical to the pre-change
  baseline (same length, same `(session, project_root, project_name)`
  tuples, all `is_live=True`).
- Same call with `_read_registry_index` patched to return non-empty
  registry — still no leak into the default-flag result.

Both tests run via the existing pattern (`bash` wrapper if needed,
or direct `python3` if Python is on PATH; mirror existing
`tests/test_*.py` invocation in the repo).

### Step 8 — Manual verification

1. Ensure `~/.config/aitasks/projects.yaml` has at least one
   inactive entry (e.g., `aitasks_mobile`, with its tmux session
   killed). Confirm `ait projects list` shows it as `OK`.
2. Open `ait ide` (or any TUI that uses the switcher) in
   `/home/ddt/Work/aitasks`. Press `j` to open the switcher.
   Confirm the Session: row lists both `aitasks` (live, marked `▶`)
   and `aitasks_mobile` (inactive, no marker).
3. Press `→` to cycle to `aitasks_mobile`. The TUI list now shows
   all TUIs as not-running (dim circles).
4. Press `b` (board shortcut). Expected: `tmux_bootstrap.sh`
   spawns the `aitasks_mobile` session detached, the switcher
   `switch-client`s us to it, and a `board` window opens.
5. Confirm `ait monitor` (still in scope-frozen behavior) shows
   only live sessions — the inactive `aitasks_mobile` entry must
   NOT have leaked into monitor's view.
6. `shellcheck .aitask-scripts/lib/tmux_bootstrap.sh
   .aitask-scripts/aitask_ide.sh` — clean.
7. Run the full test suite: `bash tests/test_*.sh` (where
   applicable) plus the two new tests.

## Key Files

**Modified:**
- `.aitask-scripts/lib/agent_launch_utils.py` — `AitasksSession`
  (+`is_live`), `discover_aitasks_sessions` (+`include_registered`
  kwarg), new `_read_registry_index` + `_read_default_session`
  helpers.
- `.aitask-scripts/lib/tui_switcher.py` — pass
  `include_registered=True`; add `_ensure_session_live` helper and
  call from `_switch_to` + shortcut spawn paths.
- `.aitask-scripts/aitask_ide.sh` — source the new helper, thin out
  the now-shared bootstrap functions.

**Created:**
- `.aitask-scripts/lib/tmux_bootstrap.sh` — shared
  `spawn_session_detached` helper (sourced + standalone CLI forms).
- `tests/test_discover_include_registered.py` — round-trip + stale +
  env-var-override assertions for the new flag.
- `tests/test_discover_default_unchanged.py` — regression that the
  default (no-flag) call is byte-identical to pre-change behavior.

**Not modified (explicit non-changes):**
- `.aitask-scripts/aitask_monitor.sh`, `.aitask-scripts/lib/tmux_monitor.py`
  — out of scope (parent-brainstorm-locked).
- `tests/lib/test_scaffold.sh` — `tmux_bootstrap.sh` is sourced
  on-demand by `aitask_ide.sh` only, not added to `./ait`'s
  source-on-startup chain. No scaffold update needed.

## Reused Code

- `agent_launch_utils.py`:
  - `_read_registry_entry` (line 224) — pattern for reading per-
    session tmux global env; the new helpers mirror its error
    handling.
  - `_walk_up_to_aitasks` (line 211) — pattern for "is this an
    aitasks project root" check; the new `_read_registry_index`
    uses the same marker-file probe.
- `aitask_projects.sh::list_registry_entries` (lines 124-174) —
  the canonical YAML parsing pattern the Python helper mirrors.
  Single source of truth for the field set.
- `aitask_ide.sh::resolve_session` (lines 46-72), `read_syncer_autostart`
  (74-94), `set_project_registry` (108-114), `ensure_syncer_window`
  (116-121) — bodies that move into `tmux_bootstrap.sh` as
  parameterized helpers.
- `tui_switcher.py::_teleport_if_cross` (line 798) — already handles
  the `switch-client` part for cross-session moves; works unchanged
  once the session has been bootstrapped.

## Verification

- Unit / regression tests:
  ```bash
  python3 tests/test_discover_include_registered.py
  python3 tests/test_discover_default_unchanged.py
  ```
- Lint:
  ```bash
  shellcheck .aitask-scripts/lib/tmux_bootstrap.sh \
             .aitask-scripts/aitask_ide.sh
  ```
- Full bash test suite:
  ```bash
  for t in tests/test_*.sh; do bash "$t" || echo "FAILED: $t"; done
  ```
- Manual: see Step 8 above (six checks).

## Out of Scope

- `ait monitor` multi-project view (locked by parent brainstorm).
- Visual indicators for inactive entries in the switcher's Session
  row (user said "probably not needed" — activity is implied by
  switch-vs-spawn behavior on selection).
- **Stale registry handling / UX** — deferred to sibling brainstorm
  task `t826_5` (`aitasks/t826/t826_5_brainstorm_stale_registry_ux.md`,
  created in Step 0). t826_2 silently excludes
  STALE entries (path missing the marker file) from the switcher,
  matching how `_walk_up_to_aitasks` already filters. All richer
  behaviors — surfacing stale entries, prune/update/remove
  subcommands, detection cadence, in-switcher markers, race-handling
  for entries that turn STALE mid-action, and `git_remote` auto-clone
  — live in that brainstorm.

## Step 9 reference

After implementation and review, follow the shared workflow's Step 9.
No worktree to clean (profile `fast` works on the current branch).
