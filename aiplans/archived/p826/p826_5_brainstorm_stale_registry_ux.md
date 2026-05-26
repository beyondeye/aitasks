---
Task: t826_5_brainstorm_stale_registry_ux.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_1_*.md, t826_2_*.md, t826_3_*.md, t826_4_*.md
Archived Sibling Plans: aiplans/archived/p826/p826_1_*.md, p826_2_*.md
Base branch: main
---

# Brainstorm: Stale registry UX (t826_5)

## Context

t826_2 made the TUI switcher surface registered-but-inactive projects in
the Session: row, but kept the cautious behavior of **silently excluding
STALE entries** — registry rows whose path no longer holds the
`aitasks/metadata/project_config.yaml` marker. The user is then blind:
a moved/renamed/deleted project just vanishes from the switcher with
no signal, and its registry row festers forever.

t826_1 already classifies status (`LIVE` / `OK` / `STALE`) in the bash
resolver and `aitask projects list` output. This task scopes the UX for
surfacing STALE in the switcher and giving the user verbs to resolve
each STALE row.

**This is a brainstorm/design task. Its deliverable is a set of
follow-up implementation child tasks; no implementation code lands in
this round.**

## Design Decisions

Following four decisions confirmed with the user before writing this
plan. Recording them here so subsequent child tasks have a stable
reference; if any decision later flips, edit this section and let the
child tasks reflect the change.

### 1. Surface STALE entries in the switcher (dim marker)

STALE registry rows appear in the Session: row **dimmed**, with a `(stale)`
suffix (or `✗` glyph if width-constrained). The `▶` attached-session
marker stays exclusive to the live attached session — STALE never
overlaps with it.

Selecting a STALE entry **does not** attempt a tmux bootstrap. Instead
the switcher pushes a modal offering inline prune / repoint / keep
(reusing the doctor verb's per-entry handler — see decision #2).

Rationale (vs. hiding): A registered-but-broken project is a user
intent statement that something went wrong. Hiding it is silent
failure. Dim styling keeps the row visually subordinate to actionable
rows.

### 2. `ait projects` verbs: full set (remove, update, prune, doctor)

Four new verbs, one per child task:

- **`ait projects remove <name>`** — atomic; drop a single entry by
  name. Confirm prompt unless `--force`. No path check (works on
  STALE and OK alike). Carried over from t826_1's Out-of-Scope list.
- **`ait projects update <name> <new_path>`** — atomic; repoint a
  known entry whose path moved. Verifies new path holds the marker
  file before writing.
- **`ait projects prune`** — bulk; delete every STALE entry. Always
  shows a list first; `--dry-run` prints without writing; per-entry
  `--confirm` (default) or `--yes` to skip prompts.
- **`ait projects doctor`** — interactive scan. Iterates STALE
  entries and offers per-entry: prune / update (prompt for new
  path) / clone-from-`git_remote` (when `--clone` is passed and the
  entry has a `git_remote` field) / keep. Front-end for the rest;
  composes the three atomic verbs internally.

Naming/style mirrors existing verbs (`add`, `list`, `resolve`, `exec`)
in `.aitask-scripts/aitask_projects.sh`.

### 3. Auto-clone from `git_remote`: opt-in via `doctor --clone`

`git_remote` is read but never auto-acts. Only `ait projects doctor
--clone` exposes the "clone from git_remote into the registered path"
option as a per-entry choice. Without `--clone`, doctor never offers
the clone action. There is no top-level `ait projects clone <name>`
verb in this scope — clone is gated through doctor's per-entry flow
so the user always confirms the path it would land in.

Rationale: cloud-agent path-divergence (the original use case) is
real, but a surprise `git clone` into an absolute path under the
user's home is the wrong default. Gating it behind two opt-ins
(`--clone` flag + per-entry prompt) keeps the side effect explicit.

### 4. Detection cadence: every switcher render

`os.path.isfile(<root>/aitasks/metadata/project_config.yaml)` per
registry entry on every switcher render. With <20 entries × ~10μs,
total per-render cost is <1ms — well below any perceptible latency.

No caching, no background timer, no TTL. The existing
`_read_registry_index` helper in `agent_launch_utils.py` already does
the marker-file probe (silently skipping STALE today); the surface
change is to return a 3-tuple `(name, path, status)` instead of a
2-tuple `(name, path)`, so callers can decide whether to render or skip.

`status` values: `"OK"` (path holds marker, no live tmux session) and
`"STALE"` (path missing marker). The `"LIVE"` classification stays in
the bash resolver where it has access to `tmux list-sessions`; the
Python side already merges live and registry views downstream of
`_read_registry_index`.

## Open Questions — Resolved

- **Cache the marker-file probe?** No (decision #4). Revisit if a real
  user ever registers 200+ projects.
- **`last_opened` auto-prune candidates?** No. `doctor` may display
  `last opened: <date>` as a hint in the per-entry prompt, but never
  auto-deletes. Auto-deletion of registry entries is irrecoverable
  without re-running `ait projects add` from each project root, which
  the user might not have on disk.
- **Per-machine path divergence (same registry on two PCs).** Not a
  concern today: the registry lives under `~/.config/aitasks/`
  (XDG-config, per-user, per-machine). Nobody syncs it across
  machines, and each host runs its own `ait projects add` from its
  own project roots, so registries diverge naturally. The
  cloud-agent case is covered by the `doctor --clone` flow (boot
  with empty registry, clone or re-add as needed).

## Follow-up Implementation Child Tasks

The brainstorm produces five concrete child tasks under t826. They are
ordered for sequential pickup; each is sized to be implementable in
one Claude Code session at `fast` profile.

### Child A — t826_6: Status-aware `_read_registry_index`

**Scope:** Modify `_read_registry_index` in
`.aitask-scripts/lib/agent_launch_utils.py` to return
`list[tuple[str, Path, str]]` instead of `list[tuple[str, Path]]`,
where the third element is `"OK"` or `"STALE"`. Stop silently skipping
STALE entries. Update `discover_aitasks_sessions` to:

- Add a new `is_stale: bool = False` field on `AitasksSession`.
- Synthesize STALE registry rows with `is_live=False, is_stale=True`
  (still surfaces in the live-dedup map by `project_name`, so a
  STALE entry whose `project_name` matches a live entry is
  suppressed — the live one wins).

**Bash side:** Extract a `classify_registry_entry(name, path)` helper
in `aitask_projects.sh` that returns `LIVE` / `OK` / `STALE`, replacing
the inline logic at lines 232-238 of `cmd_list`. New verbs in children
B–D will reuse it.

**Tests:** Extend `tests/test_discover_include_registered.py` to
verify the new tuple shape, STALE entries reach the consumer, and
`is_stale` is set correctly.

### Child B — t826_7: `ait projects remove` + `update`

**Scope:** Two new bash verbs in `aitask_projects.sh`:

- `cmd_remove <name>` — confirm-or-`--force`, then rebuild the
  registry minus the named entry (same `awk -F'|' '$1 != name'`
  pattern as `cmd_add`).
- `cmd_update <name> <new_path>` — verify `<new_path>` holds the
  marker file, then rebuild keeping the entry but with the new path.
  Refresh `last_opened` to today.

Both write via `atomic_write` (already in the file) and emit a
success line for scripted callers.

**Tests:** New `tests/test_aitask_projects_remove.sh` and
`tests/test_aitask_projects_update.sh` covering happy path,
missing-name error, and (for update) marker-missing rejection.

### Child C — t826_8: `ait projects prune`

**Scope:** New `cmd_prune` verb in `aitask_projects.sh` that iterates
the registry, classifies each entry, and removes every `STALE` row.
Flags: `--dry-run` (print would-remove list, no write), default
behavior asks per-entry confirm, `--yes` skips confirms.

Reuses the `classify_registry_entry` helper from Child A. Internally
calls `cmd_remove --force` per row (after the per-entry confirm
returns yes) to avoid duplicating the registry-rewrite logic.

**Tests:** `tests/test_aitask_projects_prune.sh` covering: no stale
entries (no-op), mixed stale/OK (only stale removed), `--dry-run`
(no write), and the confirm-each-entry path.

### Child D — t826_9: `ait projects doctor`

**Scope:** New `cmd_doctor` verb in `aitask_projects.sh`. Interactive
loop over STALE entries. For each:

```
[1/3] STALE: aitasks_mobile → /home/ddt/Work/aitasks_mobile
      last opened: 2026-04-12
      git_remote: git@github.com:beyondeye/aitasks_mobile.git

      Action? [p]rune / [u]pdate / [c]lone / [k]eep / [s]kip-all
```

Branches:
- `p` (prune) — call `cmd_remove --force <name>`.
- `u` (update) — prompt for new path, validate marker, call
  `cmd_update <name> <new_path>`.
- `c` (clone) — **only offered when `--clone` flag was passed AND
  the entry has a `git_remote`.** Confirms the target path, runs
  `git clone <remote> <path>`, then ensures the marker file exists
  (clone may pull a non-aitasks repo, in which case warn and leave
  the registry row STALE).
- `k` (keep) — no-op for this entry.
- `s` (skip-all) — break the loop, leave remaining stale entries.

**Tests:** `tests/test_aitask_projects_doctor.sh` driving the
interactive prompts via heredoc input on stdin. Cover prune branch,
update branch, keep branch, skip-all, and `--clone` enabled +
disabled.

### Child E — t826_10: Switcher renders STALE inline + race-handling

**Scope:** Wire the switcher to render and resolve STALE entries:

1. **Render** (`tui_switcher.py::_render_session_row`, line 465):
   when an `AitasksSession` has `is_stale=True`, render its segment
   dimmed (`Style(dim=True)`) with a ` (stale)` suffix (or `✗` if
   row width is constrained — codify the breakpoint when implementing).

2. **Selection handler** (the spawn entry points in `_switch_to`,
   `action_shortcut_explore`, `action_shortcut_create`): before
   `_ensure_session_live` runs, check `is_stale`. If True, push a
   new `StaleEntryModal` (a small modal in `.aitask-scripts/lib/`
   that offers Prune / Repoint / Cancel). On Prune, shell out to
   `aitask_projects.sh remove --force <name>`. On Repoint, push a
   second modal asking for the new path, then call
   `aitask_projects.sh update <name> <new_path>`. After either,
   refresh `self._all_sessions` (re-run
   `discover_aitasks_sessions(include_registered=True)`) and rebuild
   the Session row.

3. **Race-handling** (the case where an entry was OK at switcher
   mount but became STALE before the user pressed Enter): extend
   `tmux_bootstrap.sh::spawn_session_detached` to fail with a
   structured exit code + a `BOOTSTRAP_FAILED:stale_path` line on
   stderr when the target's marker file is missing. `_ensure_session_live`
   catches this exit code and pushes the same `StaleEntryModal`.

4. **Modal CSS** lives in the modal file (`StaleEntryModal`
   self-contained — modal CSS must not depend on App-level styles,
   per the existing convention).

**Tests:**
- `tests/test_stale_entry_modal.py` (or extend
  `tests/test_tui_switcher.py` if it exists) covering render-dimming,
  prune action, repoint action, modal CSS isolation.
- Manual verification covered separately by extending the t826_4
  manual-verification checklist (cross-reference added in Child E's
  task description).

## Out of Scope (and rationale)

- **Auto-prune by `last_opened` age.** Considered and rejected — too
  destructive as an automatic action. Doctor may *display* the age
  as a hint, but never acts on it without explicit user input.

- **Top-level `ait projects clone <name>` verb.** Folded into
  `doctor --clone` (decision #3) to keep the side effect gated
  behind an interactive confirm.

- **Caching the marker-file probe.** Not needed at <20 entries
  (decision #4). Revisit if registry size grows substantially.

- **Cross-repo merge / CI coordination.** Carried over from parent
  brainstorm t826's Out of Scope; not in this task's lineage.

## References

- Parent brainstorm: `aitasks/t826_brainstorm_cross_repo_project_references.md`
- t826_1 archived plan: `aiplans/archived/p826/p826_1_registry_resolver_projects_cmd_and_create_flag.md`
  (LIVE/OK/STALE classification semantics; `aitask_projects.sh` v1).
- t826_2 archived plan: `aiplans/archived/p826/p826_2_tui_switcher_show_inactive_projects.md`
  (current silent-exclusion behavior; `_read_registry_index` helper;
  `tmux_bootstrap.sh` extraction; `is_live` on `AitasksSession`).
- t826_4 (manual verification, pending): extend its checklist when
  Child E lands so the stale-entry modal flow is human-verified.
- Authoring-side aidoc: `aidocs/cross_repo_references.md` (registry
  schema + resolver semantics — update when Child A changes the
  Python helper's return shape).

## Verification (this task)

This is a design-only task. Verification is:

1. The five child task files (t826_6 through t826_10) are created
   under `aitasks/t826/` with the full Context / Implementation Plan /
   Verification structure required by Child Task Documentation
   Requirements.
2. Each child auto-registers in t826's `children_to_implement` via
   `aitask_create.sh --batch --parent 826`.
3. This plan file (`aiplans/p826/p826_5_brainstorm_stale_registry_ux.md`)
   is committed alongside the child task files via `./ait git`.
4. No source code (`.py`, `.sh`) is modified in this round — confirm
   with `git diff --stat` showing only `aiplans/` and `aitasks/`.

## Step 9 reference

After approval and child task creation, follow the shared workflow's
Step 9. No worktree to clean (profile `fast` works on the current
branch). Archival closes t826_5 and the new children become the next
pickups under t826.
