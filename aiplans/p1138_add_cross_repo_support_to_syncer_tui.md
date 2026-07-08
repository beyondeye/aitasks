---
Task: t1138_add_cross_repo_support_to_syncer_tui.md
Base branch: main
plan_verified: []
---

# t1138 — Add cross-repo support to the syncer TUI

## Context

`ait syncer` today is strictly single-repo: it shows desync state (ahead/behind vs origin) for the CWD repo's `main` + `aitask-data` refs and offers sync/pull/push actions against the CWD. The user wants to see the desync status of **all registered repos in one TUI** and issue push/pull/sync from that single place. The `ait stats` TUI already solved multi-repo discovery (registry + live tmux sessions via `discover_aitasks_sessions(include_registered=True)`); this task reuses that seam.

**User decisions (from exploration + planning):**
- **Flat multi-repo table** — one `DataTable` with a row per repo×branch (Project column added), everything visible at once; `s`/`u`/`p` act on the highlighted row's repo. No sidebar selector, no separate aggregate view.
- **Per-repo actions only** — no batch fan-out across repos.
- **Selected-repo-only fetch** — each refresh tick fetches only the highlighted row's repo; other repos refresh local-only. Per-repo **staleness indicator** when the last *fetched* refresh is older than a configurable threshold (`--stale-after`, default 60s).
- Single-repo behavior (< 2 discovered repos) must be **unchanged** (no Project column, same row keys, same actions).

## Changes

### 1. `.aitask-scripts/lib/desync_state.py` — root-parameterized snapshot

- `snapshot(ref_filter, fetch)` → `snapshot(ref_filter, fetch, root: Path | None = None)`; `root = root if root is not None else repo_root()`. `snapshot_ref` already takes `root` — this just exposes it. All existing callers (CLI `main`, syncer single-repo, monitor session-bar helper) are unchanged via the default.

### 2. `.aitask-scripts/lib/sync_action_runner.py` — repo-targeted action seam

Shared with `ait board` — all new params default to today's behavior (`None` = CWD-relative), so the board caller is untouched.

- **New pure seam** (unit-testable without live git — command resolution split from execution):
  ```python
  def sync_batch_command(repo_root: Path | None = None) -> tuple[list[str], str | None]:
      """(argv, cwd) for the aitask_sync.sh --batch invocation."""
      if repo_root is None:
          return [_SYNC_SCRIPT, "--batch"], None          # legacy CWD-relative
      return [str(repo_root / ".aitask-scripts" / "aitask_sync.sh"), "--batch"], str(repo_root)
  ```
  Running the **target repo's own copy** of `aitask_sync.sh` with `cwd=<root>` honors that repo's installed version and its `_AIT_DATA_WORKTREE` resolution. A missing script path surfaces as the existing `STATUS_NOT_FOUND` (subprocess `FileNotFoundError`).
- `run_sync_batch(timeout=..., repo_root: Path | None = None)` — resolve `(argv, cwd)` via the seam, pass `cwd=` to `subprocess.run`.
- `run_interactive_sync(app, on_done=None, repo_root: Path | None = None)` — `ait_argv = [str(repo_root / "ait"), "sync"]` when rooted else `["./ait", "sync"]`; terminal path passes it to `spawn_in_terminal` (absolute path works — `ait` cds to its own repo root); inline suspend path adds `cwd=`.

### 3. `.aitask-scripts/lib/agent_launch_utils.py` — promote `compact_root`

Move stats' module-private `_compact_root()` (home-abbreviated unique disambiguator, `stats_app.py:63-70`) into `agent_launch_utils.py` as public `compact_root(path) -> str`; update `stats_app.py` to import it. Avoids duplicating it in the syncer (derive-don't-duplicate).

### 4. `.aitask-scripts/syncer/syncer_app.py` — multi-repo table

**Discovery** (module-level, mirrors `discover_stats_sessions`):
```python
def discover_syncer_sessions() -> list[AitasksSession]:
```
- `discover_aitasks_sessions(include_registered=True)`, drop `is_stale` rows; wrap in `try/except` → `[]` on failure (fail back to single-repo, never crash the TUI).
- **Current repo always present and FIRST**: if `realpath(Path.cwd())` isn't among session keys, synthesize `AitasksSession(session="", project_root=cwd, project_name=cwd.name)`; reorder current-first. Guarantees actions on the launch repo work even when unregistered/non-tmux.

**Pure row model** (module-level, unit-testable):
```python
@dataclass(frozen=True)
class RowSpec:
    row_key: str        # OPAQUE generated id — multi: f"r{i}" positional; single: legacy "main"/"aitask-data"
    session_key: str    # "" in single-repo mode
    ref_name: str       # "main" | "aitask-data"
    project_label: str  # "" in single-repo mode

def build_rows(sessions: list[AitasksSession], labels: dict[str, str]) -> list[RowSpec]
def single_repo_rows() -> list[RowSpec]            # legacy: main / aitask-data
def action_allowed_for_ref(action: str, ref_name: str) -> bool   # sync_data↔aitask-data, pull/push↔main
def is_stale(now: float, last_fetch_ts: float | None, threshold: float) -> bool
```
**Row keys are never parsed.** `row_key` is an opaque Textual row id; `(session_key, ref_name)` are recovered exclusively via `self._rows_by_key: dict[str, RowSpec]` built alongside the table rows. No delimiter-concatenation of filesystem paths into the key protocol (paths may contain any text; key validity must not depend on them). Single-repo mode keeps the literal legacy keys `"main"`/`"aitask-data"` — also looked up via the map, never string-split.

Labels via `disambiguate_labels([project_name…], [compact_root…], [compact_root…])` (reused from stats, collision-safe).

**App state:** `self.sessions`, `self.multi_repo = len(sessions) >= 2`, `self._session_by_key`, `self._rows: list[RowSpec]`, per-repo `self._snapshots: dict[str, dict]` (keyed by session_key, `""` in single mode), `self._last_fetch_ts: dict[str, float]`, `self._stale_after` (CLI, default 60).

**Table:** in multi-repo mode add a leading **Project** column and one row per `RowSpec` (keyed `row_key`); rename the last column to **Last fetch**. Single-repo mode composes exactly today's columns/rows.

**Refresh flow** (still one `@work(thread=True, exclusive=True, group="syncer-refresh")` worker, plus an explicit request/supersession model — `exclusive=True` cancellation is *cooperative* for thread workers, so a superseded pass can still complete and call back after a newer one; the guard below, not cancellation, is the correctness mechanism):

- **Refresh request model.** All refresh entry points (interval tick, `r`, post-action, fetch toggle, highlight change) funnel through one method `_request_refresh(fetch_key: str | None)`:
  - **Every ordinary entry point resolves the highlighted row first.** `action_refresh()` (used by the interval tick, `r`, post-action refreshes, and the fetch toggle) computes `fetch_key = self._selected_row().session_key` in multi-repo mode (single-repo mode passes the legacy global-fetch semantics) and calls `_request_refresh(fetch_key)`. So the selected repo is fetched on *every* tick, not only on highlight change — stale rows for the repo you're looking at always clear on the next tick. The highlight handler additionally calls `_request_refresh(new_key)` immediately, gated on `is_stale`.
  - **Coalescing — at most one refresh worker at a time.** If a worker is active (`self._refresh_active`), do **not** spawn another: store the request in a single pending slot `self._pending_fetch_key = fetch_key` (latest request wins — later revisions override earlier ones). When the active worker completes (`_apply_refresh`, and equally on the worker's error path), clear `_refresh_active` and, if a pending request exists, pop it and re-enter `_request_refresh` with it. Superseded work is therefore *prevented*, not just discarded — rapid cursor movement or a large registry cannot accumulate background git passes.
  - When actually starting a worker: bump `self._refresh_gen += 1` (on **every** start, no branch skips the bump), capture `gen`, set `_refresh_active`, start `_refresh_worker(gen, fetch_key)`.
  - The worker snapshots all repos — checking `get_current_worker().is_cancelled` between repos and bailing early (cooperative-cancellation belt for any path that still cancels, e.g. app shutdown) — then hands the **complete result set** back in a single `call_from_thread(self._apply_refresh, gen, results, fetched_keys)`.
  - `self._apply_refresh` **discards superseded results first**: `if gen != self._refresh_gen: return` (still clearing `_refresh_active` / dispatching the pending slot) — no cell writes, no stamp writes. With coalescing this guard should rarely trigger; it remains the correctness backstop so an older local-only pass can never overwrite a newer fetched pass and the stale marker cannot flicker backwards.
- Worker pass: for each session `snapshot(None, fetch=self._fetch and s.key == fetch_key, root=s.project_root)`; single-repo mode calls `snapshot(None, self._fetch)` unchanged.
- **Invariant — passive polls never refresh the staleness stamp:** `self._last_fetch_ts[key] = time.time()` is written (inside `_apply_refresh`, post-gen-guard) **only** for repos in `fetched_keys` whose snapshot did not return `fetch_error`/`no_remote`. A local-only refresh of a non-selected repo must leave its stamp (and thus its stale marker) untouched. Covered by a negative-control test in §5.
- **Stale rows visually qualify their data, not just the timestamp:** for a stale repo, the Status/Ahead/Behind cells render `[dim]…[/]` (data is "last fetched status", not current), and the **Last fetch** cell shows `[yellow]{clock} stale[/]` (never fetched: `[yellow]— stale[/]`). Fresh rows render normally. When fetch is globally off (`f`), the Last fetch cell shows `[dim]fetch off[/]` and all rows use the stale (dim) rendering — nothing looks authoritative that isn't.
- `on_data_table_row_highlighted`: if the newly highlighted row's repo `is_stale` → `_request_refresh(that session_key)` (on-demand fetch). The staleness guard bounds it: cursor movement within a fresh repo's rows is a no-op, and repeated crossings re-fetch at most once per staleness window; concurrent requests are resolved by the generation guard (latest wins).

**Selection & gating:**
- `_selected_row() -> RowSpec` replaces `_selected_ref_name()` (row-key → RowSpec lookup).
- `check_action` delegates to `action_allowed_for_ref(action, selected.ref_name)` — per-row gating; unchanged semantics per ref.

**Actions retargeted at the selected row's repo:**

- **Pure preflight helper** (module-level, unit-tested) — resolves the action target *before* any subprocess runs, and returns distinct reasons naming the project:
  ```python
  @dataclass(frozen=True)
  class ActionTarget:
      root: Path            # target repo root (cwd for the git/sync subprocess)
      branch: str | None    # physical main branch (pull/push only)
      label: str            # project label for user-facing messages

  def resolve_action_target(row: RowSpec, session_by_key, snapshots) -> ActionTarget | str:
      # error strings name the project, e.g.:
      #  "<label>: project root missing or not a directory (<path>)"
      #  "<label>: no status snapshot yet — refresh (r) first"
  ```
  Checks, in order: session exists for `row.session_key`; `root.is_dir()`; a snapshot for that key exists (pull/push derive `branch = physical_main_branch(snapshot)` — never from a different repo's snapshot; sync-data does not require branch). On error → `self.notify(reason, severity="error")` and **no subprocess is constructed**. Single-repo mode passes through with `root=None` semantics (exact legacy behavior).
- `_sync_data_worker` → preflight, then `run_sync_batch(repo_root=target.root)` (single mode: `repo_root=None`).
- `_main_pull_worker` / `_main_push_worker` → preflight, then existing HEAD/dirty-tree checks and `self._git([...], cwd=str(target.root))` with `target.branch`. All existing warning/error notifications gain the `<label>: ` prefix in multi-repo mode.
- `_on_conflict_resolved` → `run_interactive_sync(..., repo_root=target.root)`.
- `_launch_resolution_agent`: `project_root = <selected root>` instead of `Path(".")`; include the project label in the failure-screen title and `agent-syncfix-…` window name.
- Detail pane + failure context: prefix the project label in multi-repo mode so it's unambiguous which repo an error/detail refers to.

**CLI:** add `--stale-after <seconds>` (default 60) to `parse_args`; document in `--help`. Launcher `aitask_syncer.sh` already forwards `"$@"` — no change (and stays on `require_ait_python` per TUI conventions).

### 5. Tests

- `tests/test_desync_state.py` — add: `snapshot(None, False, root=<fixture repo>)` invoked with a *different* CWD returns that fixture's state (existing fixture-repo pattern in this file).
- `tests/test_sync_action_runner.py` — add:
  - `sync_batch_command` unit tests: `None` → (`["./.aitask-scripts/aitask_sync.sh","--batch"]`, `None`); rooted → absolute script path + `cwd=str(root)`. No live git.
  - **cwd-targeting proof (construction spy):** monkeypatch `subprocess.run` and assert `run_sync_batch(repo_root=<root>)` invokes it with `cwd=str(<root>)` and the target repo's script path in argv — i.e. the subprocess actually targets the selected repo, not the launch CWD. Also assert `repo_root=None` passes `cwd=None` + the legacy relative script (regression pin for the board caller).
- **New** `tests/test_syncer_rows.py` — pure helpers:
  - `build_rows` ordering (current repo first, 2 refs per repo, **opaque non-path row keys**, disambiguated labels) and `_rows_by_key` round-trip (every table row key maps back to its RowSpec — including a session whose project_root contains `::` in the path, proving key validity is path-independent).
  - `single_repo_rows` legacy shape (literal `main`/`aitask-data` keys).
  - `action_allowed_for_ref` full matrix (incl. negative cases); `is_stale` boundaries (None ts, exactly-at-threshold).
  - `resolve_action_target`: happy path returns the **selected** session's root + that repo's branch; missing session, non-directory root, and absent snapshot each return their distinct labeled reason; branch is never derived from another repo's snapshot.
  - `discover_syncer_sessions` fallback (monkeypatched discovery raising → synthesized cwd-only list; unregistered cwd → synthesized entry prepended).
- **Refresh supersession + staleness negative controls:** extract the apply-decision as pure helpers used by `_apply_refresh` (e.g. `should_apply(gen, current_gen)` and `should_stamp_fetch(fetched: bool, status: str)`). Tests: superseded generation → discarded (no cell writes, no stamp writes); current generation → applied; local-only (non-fetch) pass never stamps (negative control: passive polling cannot refresh the staleness stamp); `fetch_error` never stamps.
- **Coalescing tests:** extract the request decision as a pure helper (e.g. `coalesce_request(active: bool, pending: str | None | UNSET, new_key) -> Start | Defer(pending')`). Tests: idle → start; active → defer with latest-wins pending replacement; completion with a pending slot → exactly one follow-up start; completion with empty slot → no restart (no self-perpetuating refresh loop).

### 6. Docs

Update `website/content/docs/tuis/syncer/_index.md` (current-state prose, no version history): multi-repo table with Project column, per-row actions, selected-repo fetch + staleness indicator, `--stale-after` flag, single-repo appearance when only one repo is discovered. Use generic placeholder project names in examples.

## Files touched

| File | Change |
|---|---|
| `.aitask-scripts/lib/desync_state.py` | optional `root` param on `snapshot()` |
| `.aitask-scripts/lib/sync_action_runner.py` | `sync_batch_command` seam; `repo_root` params |
| `.aitask-scripts/lib/agent_launch_utils.py` | promote `compact_root` |
| `.aitask-scripts/stats/stats_app.py` | import `compact_root` (drop local copy) |
| `.aitask-scripts/syncer/syncer_app.py` | discovery, row model, multi-repo table, staleness, action retargeting, `--stale-after` |
| `tests/test_desync_state.py`, `tests/test_sync_action_runner.py`, `tests/test_syncer_rows.py` (new) | per §5 |
| `website/content/docs/tuis/syncer/_index.md` | doc update |

## Verification

1. `python3 tests/test_desync_state.py`, `python3 tests/test_sync_action_runner.py`, `python3 tests/test_syncer_rows.py` — all pass.
2. `shellcheck` not applicable (no shell edits); `python3 -m py_compile` the touched Python files.
3. Live check: `ait syncer` in this repo (5 registered projects) — table shows all repos×refs, current repo first; highlight a non-current repo → on-demand fetch clears its stale marker; stale rows render dimmed; `s`/`u`/`p` footer hints follow the highlighted row; single-repo regression by temporarily pointing `HOME`/registry at an empty config (or rely on unit tests + code gate).
3b. **Target-repo command proof — primary guarantee is the unit spy (§5), not this step.** The subprocess cwd/argv construction-spy tests are what pin correct targeting. As best-effort *live* corroboration: with a non-current repo's row highlighted, note the mtime of `<that repo>/.git/FETCH_HEAD`, press `u`, and check it advanced while the launch repo's did not (`git pull` reliably touches FETCH_HEAD; the `s` sync path depends on remote/network state, so treat any mtime observation there as indicative only — do not diagnose from it).
4. Stats TUI still runs after the `compact_root` promotion (launch `ait stats`, labels unchanged).
5. Step 9 (Post-Implementation): merge approval, gates run (`risk_evaluated` declared), archive via `aitask_archive.sh`.

## Risk

### Code-health risk: medium
- `sync_action_runner.py` and `desync_state.py` are shared with the board TUI and the monitor session-bar; a signature slip would break those consumers · severity: medium · → mitigation: in-task (all new params are optional with legacy defaults; existing tests + new unit tests pin the `None` path)
- Syncer row-key model rework (composite keys, per-repo snapshots) could regress single-repo behavior or `check_action` gating · severity: medium · → mitigation: manual_verification_cross_repo_syncer
- Concurrent refresh sources (interval tick, highlight-triggered fetch, post-action) could interleave: a superseded local-only snapshot overwriting a newer fetched one, or refresh churn from cursor movement · severity: medium · → mitigation: in-task structural (single `_request_refresh` funnel + generation-token discard guard + staleness-gated triggers, each unit-tested incl. negative controls) and manual_verification_cross_repo_syncer

### Goal-achievement risk: low
- Assumes every registered repo has `.aitask-scripts/aitask_sync.sh` installed; a repo without it degrades to `NOT_FOUND` notify rather than sync · severity: low · → mitigation: in-task (acceptable degradation; status row still shows desync state)

### Planned mitigations
- timing: after | name: manual_verification_cross_repo_syncer | type: manual_verification | priority: medium | effort: low | addresses: code-health risk (single-repo regression, live multi-repo TUI behavior, refresh/staleness churn) | desc: Drive the live syncer TUI in a multi-repo environment — multi-repo table layout, staleness marker + on-demand fetch on highlight, per-row s/u/p against a non-current repo, single-repo regression appearance.
