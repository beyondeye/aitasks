---
Task: t1138_add_cross_repo_support_to_syncer_tui.md
Base branch: main
plan_verified: []
---

# t1138 — Add cross-repo support to the syncer TUI

## Context

`ait syncer` today is strictly single-repo: it shows desync state (ahead/behind vs origin) for the CWD repo's `main` + `aitask-data` refs and offers sync/pull/push actions against the CWD. The user wants to see the desync status of **all registered repos in one TUI** and issue push/pull/sync from that single place. The `ait stats` TUI already solved multi-repo discovery (registry + live tmux sessions via `discover_aitasks_sessions(include_registered=True)`); this task reuses that seam.

**User decisions (from exploration + planning; checkpoint revision 2026-07-08 supersedes the earlier selected-repo-fetch model):**
- **Flat multi-repo table** — one `DataTable` with a row per repo×branch (Project column added), everything visible at once; `s`/`u`/`p` act on the highlighted row's repo. No sidebar selector, no separate aggregate view.
- **Per-repo actions only** — no batch fan-out across repos.
- **Least-recently-fetched (LRU) selection** — each automatic refresh tick fetches exactly ONE repo: the one whose last fetched refresh is OLDEST (never-fetched repos first). This composes with manual refreshes: a manually refreshed repo naturally drops to the back of the queue. The interval default becomes **60s** (`REFRESH_TICK_DEFAULT = 60`). The currently focused repo gets **no special treatment** in the automatic cycle. (Supersedes the earlier pure round-robin revision.)
- **Freshness display = plain age** — each repo row shows the **time since its last fetched refresh** (e.g. `32s`, `5m`, `—` if never). No "stale" text, no dim-qualification, no `--stale-after` flag, no `is_stale` threshold, no highlight-triggered on-demand fetch.
- Single-repo behavior (< 2 discovered repos) must be **unchanged** apart from the new 60s default interval (no Project column, same row keys, same actions).

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
def least_recent_fetch_key(sessions, last_fetch_ts: dict[str, float]) -> str | None   # LRU pick
def format_age(seconds: float | None) -> str   # — / 32s / 5m / 1h5m
```
**Row keys are never parsed.** `row_key` is an opaque Textual row id; `(session_key, ref_name)` are recovered exclusively via `self._rows_by_key: dict[str, RowSpec]` built alongside the table rows. No delimiter-concatenation of filesystem paths into the key protocol (paths may contain any text; key validity must not depend on them). Single-repo mode keeps the literal legacy keys `"main"`/`"aitask-data"` — also looked up via the map, never string-split.

Labels via `disambiguate_labels([project_name…], [compact_root…], [compact_root…])` (reused from stats, collision-safe).

**App state:** `self.sessions`, `self.multi_repo = len(sessions) >= 2`, `self._session_by_key`, `self._rows: list[RowSpec]`, per-repo `self._snapshots: dict[str, dict]` (keyed by session_key, `""` in single mode), `self._last_fetch_ts: dict[str, float]` (this stamp map IS the fetch-scheduling state — no separate cursor).

**Table:** in multi-repo mode add a leading **Project** column and one row per `RowSpec` (keyed `row_key`); rename the last column to **Fetched** (relative age). Single-repo mode composes exactly today's columns/rows.

**Refresh flow** (still one `@work(thread=True, exclusive=True, group="syncer-refresh")` worker, plus an explicit request/supersession model — `exclusive=True` cancellation is *cooperative* for thread workers, so a superseded pass can still complete and call back after a newer one; the guard below, not cancellation, is the correctness mechanism):

- **LRU fetch selection — scheduled on ATTEMPTS, displayed from SUCCESSES.** A pure helper owns the pick: `least_recent_fetch_key(sessions, stamps) -> str | None` returns the session key with the OLDEST stamp — unstamped repos first; ties break deterministically by session-list order; `None` for an empty list. The scheduler is fed the **attempt-stamp map** (`self._last_fetch_attempt_ts`, updated for every repo a pass tried to fetch, success or not), NOT the success-stamp map — otherwise a repo with persistent `no_remote`/`fetch_error` never earns a stamp, gets re-picked every tick, and **starves every other repo**. A failing repo's retry cooldown is therefore one full LRU cycle. The **Fetched age display** keeps reading the success-stamp map (`self._last_fetch_ts`) so a failing repo honestly shows a growing age. Each **automatic interval tick** fetches exactly one repo; manual/post-action fetches defer that repo in the attempt order automatically. The focused repo gets no special treatment. Single-repo mode keeps legacy semantics (its one repo is fetched every tick when fetch is enabled).
- **Refresh request model.** All refresh entry points funnel through one method `_request_refresh(fetch_key: str | None)`:
  - **Interval tick** → LRU `fetch_key` as above.
  - **Manual `r`** → explicit user action: fetch the *highlighted* row's repo immediately (an on-demand command, not part of the automatic cycle). Its stamp update then defers that repo in the LRU order. Requests carry an `explicit` flag (manual/post-action = explicit; interval tick = automatic).
  - **Post-action refresh** (after sync/pull/push) → fetch the acted-on repo, so the action's result is visible immediately. Its stamp update likewise defers it in the LRU order.
  - **Fetch toggle `f` off** → ticks still run but pass no fetch key (all local-only; age column keeps growing).
  - **Coalescing — at most one refresh worker at a time, explicit requests never dropped.** If a worker is active (`self._refresh_active`), do **not** spawn another: store the request in a single pending slot holding `(fetch_key, explicit)`. Replacement policy: an **automatic tick never overwrites a pending explicit request** (the tick recurs anyway; the user's manual `r` / post-action target must not be silently dropped); an explicit request replaces anything (latest explicit wins); automatic replaces automatic. When the active worker completes (`_apply_refresh`, and equally on the worker's error path), clear `_refresh_active` and, if a pending request exists, pop it and re-enter `_request_refresh` with it. Superseded work is *prevented*, not just discarded — a large registry cannot accumulate background git passes.
  - When actually starting a worker: bump `self._refresh_gen += 1` (on **every** start, no branch skips the bump), capture `gen`, set `_refresh_active`, start `_refresh_worker(gen, fetch_key)`.
  - The worker snapshots all repos — the picked repo with fetch, the rest local-only (so local commits still surface each tick) — checking `get_current_worker().is_cancelled` between repos. **Every exit path finishes:** the cancelled path schedules a cancellation-specific finish (`_finish_refresh_cancelled`: clears `_refresh_active` but does NOT dispatch the pending slot — cancellation normally means shutdown, and dispatching there could respawn a worker loop; a queued request still fires after the next completed refresh), so `_refresh_active` can never be left stuck true. The normal path hands the **complete result set** back in a single `call_from_thread(self._apply_refresh, gen, results, fetched_keys)`; the error path finishes via `_on_refresh_error`.
  - `self._apply_refresh` **discards superseded results first**: `if gen != self._refresh_gen: return` (still clearing `_refresh_active` / dispatching the pending slot) — no cell writes, no stamp writes. Correctness backstop: an older local-only pass can never overwrite a newer fetched pass.
- Worker pass: for each session `snapshot(None, fetch=self._fetch and s.key == fetch_key, root=s.project_root)`; single-repo mode calls `snapshot(None, self._fetch)` unchanged.
- **Invariant — passive polls never refresh the stamps:** inside `_apply_refresh` (post-gen-guard), every repo in `fetched_keys` gets an **attempt** stamp (scheduling), and only those whose snapshot shows a successful fetch (`should_stamp_fetch`) get a **success** stamp (displayed age). A local-only pass writes NEITHER stamp. Covered by negative-control tests in §5.
- **Freshness column = age since last fetch.** The last column (**Fetched**) shows a compact relative age via a pure `format_age(seconds: float | None) -> str` (`—` never fetched, `32s`, `5m`, `1h5m`). No "stale" wording, no color/dim qualification, no threshold. A lightweight display-only `set_interval` (5s) recomputes just the age cells from the stamps — no git work — so the age ticks up smoothly between refreshes.
- `on_data_table_row_highlighted`: detail-pane refresh + `refresh_bindings()` only (as today) — highlighting never triggers a fetch.

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

**CLI:** change `REFRESH_TICK_DEFAULT` to `60` (keep the existing `--interval` override; update its help text). No new flags. Launcher `aitask_syncer.sh` already forwards `"$@"` — no change (and stays on `require_ait_python` per TUI conventions).

### 5. Tests

- `tests/test_desync_state.py` — add: `snapshot(None, False, root=<fixture repo>)` invoked with a *different* CWD returns that fixture's state (existing fixture-repo pattern in this file).
- `tests/test_sync_action_runner.py` — add:
  - `sync_batch_command` unit tests: `None` → (`["./.aitask-scripts/aitask_sync.sh","--batch"]`, `None`); rooted → absolute script path + `cwd=str(root)`. No live git.
  - **cwd-targeting proof (construction spy):** monkeypatch `subprocess.run` and assert `run_sync_batch(repo_root=<root>)` invokes it with `cwd=str(<root>)` and the target repo's script path in argv — i.e. the subprocess actually targets the selected repo, not the launch CWD. Also assert `repo_root=None` passes `cwd=None` + the legacy relative script (regression pin for the board caller).
- **New** `tests/test_syncer_rows.py` — pure helpers:
  - `build_rows` ordering (current repo first, 2 refs per repo, **opaque non-path row keys**, disambiguated labels) and `_rows_by_key` round-trip (every table row key maps back to its RowSpec — including a session whose project_root contains `::` in the path, proving key validity is path-independent).
  - `single_repo_rows` legacy shape (literal `main`/`aitask-data` keys).
  - `action_allowed_for_ref` full matrix (incl. negative cases); `least_recent_fetch_key` (never-fetched wins over any stamp, oldest stamp wins, deterministic tie-break by session order, single-session, empty list → None, manually-refreshed repo moves to back of queue); **starvation guard**: a repo whose fetch failed (attempt-stamped, no success stamp) is NOT re-picked next tick — the attempt map drives scheduling; `format_age` (None → —, seconds, minutes, hour+minute boundaries).
  - `resolve_action_target`: happy path returns the **selected** session's root + that repo's branch; missing session, non-directory root, and absent snapshot each return their distinct labeled reason; branch is never derived from another repo's snapshot.
  - `discover_syncer_sessions` fallback (monkeypatched discovery raising → synthesized cwd-only list; unregistered cwd → synthesized entry prepended).
- **Refresh supersession + staleness negative controls:** extract the apply-decision as pure helpers used by `_apply_refresh` (e.g. `should_apply(gen, current_gen)` and `should_stamp_fetch(fetched: bool, status: str)`). Tests: superseded generation → discarded (no cell writes, no stamp writes); current generation → applied; local-only (non-fetch) pass never stamps (negative control: passive polling cannot refresh the fetch stamp / displayed age); `fetch_error` never stamps.
- **Coalescing tests:** extract the request decision as a pure helper (`coalesce_request(active, pending, new_key, new_explicit)`). Tests: idle → start; active → defer; automatic replaces automatic (latest wins); explicit replaces automatic AND explicit; **an automatic tick never overwrites a pending explicit request**; completion with a pending slot → exactly one follow-up start; completion with empty slot → no restart; cancellation finish clears the active flag without dispatching pending.

### 6. Docs

Update `website/content/docs/tuis/syncer/_index.md` (current-state prose, no version history): multi-repo table with Project column, per-row actions, least-recently-fetched refresh scheduling + Fetched age column, 60s default interval, single-repo appearance when only one repo is discovered. Use generic placeholder project names in examples.

## Files touched

| File | Change |
|---|---|
| `.aitask-scripts/lib/desync_state.py` | optional `root` param on `snapshot()` |
| `.aitask-scripts/lib/sync_action_runner.py` | `sync_batch_command` seam; `repo_root` params |
| `.aitask-scripts/lib/agent_launch_utils.py` | promote `compact_root` |
| `.aitask-scripts/stats/stats_app.py` | import `compact_root` (drop local copy) |
| `.aitask-scripts/syncer/syncer_app.py` | discovery, row model, multi-repo table, LRU fetch + age column, action retargeting |
| `tests/test_desync_state.py`, `tests/test_sync_action_runner.py`, `tests/test_syncer_rows.py` (new) | per §5 |
| `website/content/docs/tuis/syncer/_index.md` | doc update |

## Verification

1. `python3 tests/test_desync_state.py`, `python3 tests/test_sync_action_runner.py`, `python3 tests/test_syncer_rows.py` — all pass.
2. `shellcheck` not applicable (no shell edits); `python3 -m py_compile` the touched Python files.
3. Live check: `ait syncer` in this repo (5 registered projects) — table shows all repos×refs, current repo first; over successive ticks exactly one repo's Fetched age resets per tick — always the least-recently-fetched one; after `r` on a repo, the automatic cycle picks the others first; ages tick up between refreshes; `s`/`u`/`p` footer hints follow the highlighted row; single-repo regression by temporarily pointing `HOME`/registry at an empty config (or rely on unit tests + code gate).
3b. **Target-repo command proof — primary guarantee is the unit spy (§5), not this step.** The subprocess cwd/argv construction-spy tests are what pin correct targeting. As best-effort *live* corroboration: with a non-current repo's row highlighted, note the mtime of `<that repo>/.git/FETCH_HEAD`, press `u`, and check it advanced while the launch repo's did not (`git pull` reliably touches FETCH_HEAD; the `s` sync path depends on remote/network state, so treat any mtime observation there as indicative only — do not diagnose from it).
4. Stats TUI still runs after the `compact_root` promotion (launch `ait stats`, labels unchanged).
5. Step 9 (Post-Implementation): merge approval, gates run (`risk_evaluated` declared), archive via `aitask_archive.sh`.

## Risk

### Code-health risk: medium
- `sync_action_runner.py` and `desync_state.py` are shared with the board TUI and the monitor session-bar; a signature slip would break those consumers · severity: medium · → mitigation: in-task (all new params are optional with legacy defaults; existing tests + new unit tests pin the `None` path)
- Syncer row-key model rework (composite keys, per-repo snapshots) could regress single-repo behavior or `check_action` gating · severity: medium · → mitigation: manual_verification_cross_repo_syncer
- Concurrent refresh sources (interval tick, manual `r`, post-action) could interleave: a superseded local-only snapshot overwriting a newer fetched one, or accumulated background git passes · severity: medium · → mitigation: in-task structural (single `_request_refresh` funnel + coalescing pending-slot + generation-token discard guard, each unit-tested incl. negative controls) and manual_verification_cross_repo_syncer

### Goal-achievement risk: low
- Assumes every registered repo has `.aitask-scripts/aitask_sync.sh` installed; a repo without it degrades to `NOT_FOUND` notify rather than sync · severity: low · → mitigation: in-task (acceptable degradation; status row still shows desync state)

### Planned mitigations
- timing: after | name: manual_verification_cross_repo_syncer | type: manual_verification | priority: medium | effort: low | addresses: code-health risk (single-repo regression, live multi-repo TUI behavior, refresh scheduling) | desc: Drive the live syncer TUI in a multi-repo environment — multi-repo table layout, least-recently-fetched scheduling + Fetched age column behavior, manual r refresh of the highlighted repo, per-row s/u/p against a non-current repo, single-repo regression appearance.

## Post-Review Changes

### Change Request 1 (2026-07-09 09:05)
- **Requested by user:** Three implementation-review findings: (1) LRU scheduler starves the registry when a repo never earns a success stamp (persistent `no_remote`/`fetch_error` repo re-picked every tick); (2) an automatic interval tick could overwrite a pending explicit (manual `r` / post-action) refresh target in the latest-wins slot; (3) the worker's cooperative-cancellation return path never cleared `_refresh_active`, permanently halting refreshes if cancellation fired outside shutdown.
- **Changes made:** (1) split scheduling from display — new `_last_fetch_attempt_ts` map stamped for every attempted fetch feeds `least_recent_fetch_key`, while `_last_fetch_ts` (success-only) keeps driving the Fetched age display; failing repos now retry after one full LRU cycle. (2) pending slot now holds `(fetch_key, explicit)`; `coalesce_request` gained an `explicit` param — an automatic tick never replaces a pending explicit request, explicit replaces anything, automatic replaces automatic; manual `r` and post-action refreshes are explicit. (3) the cancelled worker path schedules `_finish_refresh_cancelled` (clears the active flag WITHOUT dispatching pending, so shutdown cannot respawn a worker loop). Tests: +starvation-guard LRU test, reworked coalescing tests (explicit-vs-automatic matrix), pilot smoke extended to assert no stamps on a no-fetch pass and the explicit-not-clobbered slot behavior.
- **Files affected:** `.aitask-scripts/syncer/syncer_app.py`, `tests/test_syncer_rows.py`, plan refresh-flow/tests sections.
