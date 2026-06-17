---
Task: t983_9_running_strip_deconflict_docs.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-17 11:57
---

# p983_9 — Running rename + always-on status strip + t535 actions + deconflict + docs

Final child of t983 (brainstorm TUI IA redesign). Renames the Status tab to
**Running**, adds the always-on header status strip the target IA calls for,
lands the remaining **t535** agent-management actions, finalizes the `b/s/r`
keymap, and does the minimal docs work.

## Context

The brainstorm TUI's last tab is still the opaque **Status** tab (`tab_status`,
key `r`, plain `"Status"` label). The converged target IA (parent t983) is a
3-tab structure **Browse / Session / Running** with an always-on header strip
(`[runner ●] [▶ N running]`). Siblings t983_7 (Compare→overlay) and t983_8
(Session tab) already landed `b`/`s`/`r` provisionally and freed the keys; this
last child completes the rename, the strip, the t535 actions, and the docs.

## Verified current state (corrects the original task's stale assumptions)

Exploration against the as-landed code (`.aitask-scripts/brainstorm/brainstorm_app.py`)
found several divergences from the original task body — **the original plan's
line numbers and several claims are stale**:

1. **Rename blast radius is exactly 9 sites** (not "~5320+"): `BINDINGS` r→`action_tab_status` (`:3848`), TabPane id+label (`:4063`), internal `Label("Status")` (`:4065`), down-arrow focus map `tab_to_container` (`:4110`), up/down nav guard (`:4376`), `action_tab_status` method (`:4902`), tab-activated guard (`:5936`), `_refresh_status_tab` active guard (`:5946`), plus the test `tests/test_brainstorm_node_export.py:37`.
2. **f / H / D do NOT need re-scoping.** `_TAB_SCOPED_ACTIONS` is only `{"open_node_detail": "tab_browse"}` (`:3864`). `check_action` (`:3944`) hardcodes `toggle_deferred`(`f`)→`tab_browse`, `op_help`(`H`)→`tab_actions`; `D` is fully modal-scoped inside `CompareMatrixModal` (`:1301`). **The rename touches none of them** — the original plan's "re-scope f/H/D" step is a no-op based on a misconception.
3. **t535's kill / pause / reset already ship.** `ProcessRow` (`:3095`) has `p:pause k:kill K:hard-kill` wired in `on_key` (`:4336–4373`) via `send_agent_command`/`hard_kill_agent`. `AgentStatusRow` (`:3060`) has `w: reset` (Error→Waiting, `_reset_agent` `:6107`). **The genuine gaps are Cleanup and a distinct Retry** (per user decision).
4. **`b` is not bound.** Browse is reached via `d` (list) / `g` (graph) muscle-memory shortcuts (`:4472`,`:4479`) + `v` toggle; the TabPane label is `(B)rowse`. Finalizing `b/s/r` means **adding** a plain `b` → Browse-tab binding.
5. **No always-on strip exists.** `compose` yields the default `Header()` (`:4020`) then an `initializer_row` Horizontal (`:4021`) above the `TabbedContent`. The strip will be a sibling of `initializer_row` (same proven pattern).
6. **Website has zero brainstorm docs** (`tuis/_index.md:24` says "pending"); `tui_conventions.md` has no brainstorm IA section. Per user decision: minimal docs here + a follow-up task.
7. **t983_9 is NOT the final child — parent must not archive.** `children_to_implement: [t983_9, t983_10, t983_11]`; t983_10/t983_11 are still pending on disk. The task body's "Final child of t983" prose is stale and misleading (see Step 0). Archival safety is verified against the script logic (see Step 9).

## Implementation steps

### Step 0 — Update the task AC (no silent deviation) + fix stale "final child" prose
Before coding, update `aitasks/t983/t983_9_*.md` (commit via `./ait git`) so its
Implementation Plan / Verification reflect reality: kill/pause/reset pre-exist
(this child adds **Cleanup + Retry**); the f/H/D re-scope line is removed (they
are unaffected by the rename); `b` is **added**; docs are minimal + a follow-up
task. This keeps the AC honest before implementation.

**Also correct the misleading "Final child of t983" / "last child" language** in
the task body: t983_9 is the last *authored* child but **NOT** the last *pending*
one — siblings **t983_10** (manual_verification_brainstorm_ia) and **t983_11**
(wizard_rehost_actions_screen) are still pending in `children_to_implement`. Rephrase
to "last of the original decomposition; t983_10/t983_11 remain — the parent does
**not** archive on this child's completion."

### Step 1 — Rename Status → Running
Mechanical rename across the 9 sites in step (1) above:
- id `tab_status` → `tab_running`; method `action_tab_status` → `action_tab_running`; binding action name updated; TabPane label `"Status"` → `"(R)unning"`; internal `Label("Status")` → `Label("Running")`.
- Update the `tab_to_container` key, both tab-active guards, and the up/down nav guard string to `"tab_running"`.
- Update `tests/test_brainstorm_node_export.py:37` tuple `"tab_status"` → `"tab_running"`.
- **Verify with a grep sweep** that no `tab_status`/`action_tab_status` string survives (silent-key-hide guard).

### Step 2 — Always-on header status strip (with a pure, tested derivation)
- **Pure module-level helpers** (DRY the existing inline logic in `_refresh_status_tab:5966–5977`):
  ```python
  RUNNER_STATE_DISPLAY = {
      "none":    ("No runner",      "#888888"),
      "stopped": ("Runner stopped", "#888888"),
      "stale":   ("Runner stale",   "#FF5555"),
      "active":  ("Runner active",  "#50FA7B"),
  }
  def derive_runner_state(status: str, stale: bool) -> tuple[str, str]:
      key = "none" if status == "none" else "stopped" if status == "stopped" else "stale" if stale else "active"
      return RUNNER_STATE_DISPLAY[key]
  def format_status_strip(status: str, stale: bool, running_count: int) -> str:
      label, color = derive_runner_state(status, stale)
      run = f"▶ {running_count} running" if running_count else "idle"
      return f"[{color}]●[/{color}] {label}   {run}"
  ```
  Refactor `_refresh_status_tab` to call `derive_runner_state` (removes the duplicated status→text/color ladder).
- **Widget:** in `compose`, add `yield Static("", id="runtime_strip", classes="runtime-strip")` between `initializer_row` and the `TabbedContent`.
- **Refresh wiring (always-on, tab-independent):** add `_refresh_status_strip()` that reads `get_runner_info(crew_id)` + `len(get_all_agent_processes(crew_id))` and sets the strip markup via `format_status_strip` (graceful when `crew_id` is empty → "No runner / idle"). Wrap the 30s interval (`:5207`) in a `_refresh_runtime()` that calls `_refresh_status_strip()` (always) then `_refresh_status_tab()` (self-guards on inactive tab). Point the existing post-mutation `set_timer(2.0, self._refresh_status_tab)` sites (kill/pause/`K`) at `_refresh_runtime`, and call `_refresh_status_strip()` once on session load so it paints immediately.

### Step 3 — t535 Running-tab actions: Cleanup + Retry
Kill/pause/reset already exist; add the two gaps (operate on the focused row,
confirm destructive actions per t535):
- **Cleanup (`x`):** on a focused `AgentStatusRow` in a terminal state (Error/Completed) **or** a dead `ProcessRow` → push a small `CleanupAgentModal` confirm (model on `DeleteNodeModal:692`); on confirm, `_cleanup_agent(name)` removes that agent's artifacts (`<name>_status.yaml`, `_alive.yaml`, `_output.md`, `_log.txt` if present), then `_refresh_runtime()`. Warn (no-op) on a still-running row.
- **Retry (`R`):** on a focused `AgentStatusRow` in **Error** state → `_retry_agent(row)`: reuse `_reset_agent` (Error→Waiting, clears error) **and** ensure the runner is live — if `get_runner_info` is `none`/`stopped`/stale, call `start_runner(crew_id)` so the agent actually relaunches (distinct from bare `w: reset`, which only flips status and relies on an already-active runner). Reuses existing gateways — no launch-logic duplication.
- Surface the new keys in the row `render()` hint strings (`AgentStatusRow`: add `R: retry` for Error, `x: cleanup` for terminal; dead `ProcessRow`: add `x: cleanup`).

### Step 4 — Keybinding finalize (`b/s/r`)
- Add `Binding("b", "tab_browse", "Browse", show=False)` and `action_tab_browse` (select `tab_browse`, **preserve** the persisted view — do not force list/graph). Keep `d`/`g` as the documented view-specific muscle-memory entries and `v` as the toggle.
- `s` (Session) and `r` (Running) are already final; `v`/`space`/`c`/`A`/`Enter` unchanged. f/H/D untouched (see verified-state #2).

### Step 5 — CSS
Add `.runtime-strip { height: 1; padding: 0 1; }` near `.status-header` (`:3174`). Optional dim styling consistent with `initializer-row`.

### Step 6 — Docs (minimal) + follow-up task
- `aidocs/framework/tui_conventions.md`: add a concise note that brainstorm's IA is the 3 tabs **Browse / Session / Running** + an always-on runtime strip.
- Confirm `brainstorm` stays in every user-facing TUI list (board, monitor, minimonitor, codebrowser, settings, brainstorm). No website page is deleted.
- **Create a standalone follow-up task** (Step 7, via `aitask_create.sh --batch`, `documentation` type, labels `brainstorming,tui`): "Document the brainstorm TUI on the website (Browse/Session/Running tabs, runtime strip, keymap)" — fills the `tuis/_index.md:24` "pending" gap that is out of scope here.

### Step 7 — Tests
- **NEW `tests/test_brainstorm_header_strip.py`** — pure-function unit test following the `tests/test_brainstorm_wizard_steps.py` import pattern (`sys.path.insert` for `.aitask-scripts` + `lib`, import the helpers directly, `unittest.TestCase`). Cover `derive_runner_state` (all four state/stale combinations → label+color) and `format_status_strip` (0 → "idle", N → "▶ N running"; correct dot color per state).
- **Add a 3-tab structure assertion** (extend an existing structural test or add a small one) asserting the tab ids are exactly `tab_browse`/`tab_actions`/`tab_session`/`tab_running` and the `r` binding maps to `action_tab_running` — locks the rename against regression.
- Update `tests/test_brainstorm_node_export.py:37` (the `tab_status`→`tab_running` literal).

## Corrections to original task AC (explicit, per "no silent AC deviation")
- "Implement kill/cleanup/retry" → kill/pause/reset **pre-exist**; this child adds **Cleanup + a distinct Retry** (re-launch via reset + ensure-runner).
- "Re-scope f/H/D in `_TAB_SCOPED_ACTIONS`/`check_action`" → **dropped**: f/H/D are not Running-scoped; the rename does not affect them.
- "Manual: f/H/D work under their new tabs" → corrected to: `b/s/r` navigate; header strip shows runner+count; Running-tab actions (pause/kill/cleanup/retry) dispatch.
- Website docs narrowed to "keep brainstorm listed" + a **follow-up task** for full pages.

## Risk

### Code-health risk: medium
- The `tab_status` → `tab_running` rename spans 9 sites in a load-bearing file; a missed reference silently hides a key binding or breaks down-arrow focus. · severity: medium · → mitigation: in-task grep-sweep + the new 3-tab structure assertion (no separate task)
- `Cleanup` deletes agent status artifacts (irreversible, loses logs) if mis-targeted. · severity: medium · → mitigation: confirm modal + terminal-state-only targeting, in-task (no separate task)

### Goal-achievement risk: medium
- "Distinct Retry" relies on reset-to-Waiting + ensuring the runner is live (the existing pickup model); a user expecting an immediate in-process respawn could see a mismatch. · severity: low · → mitigation: covered by sibling t983_10 (manual_verification_brainstorm_ia) + in-task pilot (no separate task)

## Verification
- **Pure unit:** `tests/test_brainstorm_header_strip.py` green.
- **Structure:** 3-tab assertion + updated `test_brainstorm_node_export.py` green.
- **Suite:** `python -m pytest tests/test_brainstorm*.py` (or the repo's bash runner) green.
- **Manual / pilot:** `b`/`s`/`r` navigate; always-on strip shows runner state + running count and updates off-tab; on the Running tab `x` (cleanup, confirmed) and `R` (retry → relaunch) dispatch on a focused failed agent; `p`/`k`/`K`/`w`/`e`/`L` still work.
- No skill/stub surface is touched, so `aitask_skill_verify.sh` is **not** required (docs-only changes per CLAUDE.md).

## Step 9 — Post-implementation
Archive via `./.aitask-scripts/aitask_archive.sh 983_9`. **The parent t983 will NOT
archive on this child** — verified mechanism: `aitask_archive.sh` removes t983_9
from `children_to_implement` (`aitask_update.sh --remove-child`, `aitask_archive.sh:432`),
re-reads the field (`:460`), and archives the parent **only if it is now empty**
(`:463`). With `t983_10` and `t983_11` still present and pending, `remaining_children`
is non-empty, so no `PARENT_ARCHIVED` line fires and the parent stays active. (The
archive decision is data-driven on `children_to_implement`, independent of any "final
child" prose.)

## Final Implementation Notes
- **Actual work done:** Renamed Status→Running across all 9 verified sites in
  `brainstorm_app.py` (grep-clean). Added pure `derive_runner_state` /
  `format_status_strip` helpers + `_TERMINAL_AGENT_STATES`, an always-on
  `#runtime_strip` `Static` above the tabs, and `_refresh_status_strip` /
  `_refresh_runtime` (wired into the 30s interval, the post-mutation 2.0s
  timers, and an initial on-load paint). Refactored `_refresh_status_tab` to
  reuse `derive_runner_state` (removed the duplicated status→text/color ladder).
  Added t535's two gaps: `x` Cleanup (new `CleanupAgentModal` confirm →
  `_cleanup_agent` removes `_status/_alive/_output/_log` files) and `R` Retry
  (`_retry_agent` = reset + `start_runner` if the runner is down). Added `b`→
  Browse (`action_tab_browse`, preserves the persisted view). New CSS
  `.runtime-strip`. Updated row hint strings. Docs: 3-tab IA note in
  `aidocs/framework/tui_conventions.md`. Tests: new
  `tests/test_brainstorm_header_strip.py` (pure derivations + b/s/r keymap +
  rename-completeness lock), updated `tests/test_brainstorm_node_export.py`.
- **Deviations from plan:** None material. Confirmed the original task's
  "re-scope f/H/D" step was a misconception (they are not Running-scoped) and
  dropped it; the AC was reconciled and committed before coding (no silent
  deviation). `action_tab_browse` had to be **added** (it did not exist — Browse
  was only reachable via `d`/`g`).
- **Issues encountered:** A stray unrelated working-tree change
  (`aidocs/applink/monitor_port_design.md`) from a concurrent session was
  present; it was deliberately excluded from the code commit (path-scoped `git
  add`).
- **Key decisions:** Cleanup/Retry are per-row `on_key` handlers with render-time
  hints (matching the existing `p`/`k`/`K`/`w`/`e`/`L` pattern), NOT footer
  `Binding`s — they are contextual to a focused Running-tab row and must not show
  globally. Retry goes through `start_runner` rather than duplicating launch
  logic. The runtime strip refresh is tab-independent (unlike `_refresh_status_tab`,
  which self-guards on the active tab).
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** The 3-tab IA (Browse/Session/Running) + always-on
  runtime strip is now the canonical brainstorm shape — see the new
  `tui_conventions.md` section. The Running tab keeps the ids `status_header` /
  `status_content` / `status_polling_indicator` (only the *tab* id changed to
  `tab_running`). An **Actions tab (`tab_actions`, `a`) still exists** hosting
  the wizard — its folding into the contextual Operations dialog is **not** part
  of this child (out of scope; see t983_11 wizard-rehost). Full website
  brainstorm docs were spun out to **t1023**. Pending siblings: **t983_10**
  (manual verification) and **t983_11** (wizard rehost) — the parent t983 stays
  active until both land.
