---
Task: t2338_sitrep_in_tui_switcher_and_minimonitor_hint_line.md
Base branch: main
Output branch: main
---

# t2338 — Sitrep row in the TUI switcher + `S:sitrep` on the minimonitor switcher line

## Context

The sitrep window (sitrep agent + sitrep TUI + minimonitor) is in practice only
opened from the minimonitor's `S`. The TUI switcher (`j`) already has a hidden
`S` quick-jump (t2175_5) but no list row, so sitrep is not visible "like the
other TUIs" and its window only shows up under "Code Agents" as `agent-sitrep`.
The user wants a switcher row to open/switch to it, and wants `S:sitrep` on the
minimonitor hint line that holds `j:switcher  m:monitor`.

Constraint (from the task): sitrep must NOT become a `TUI_REGISTRY` entry —
`TUI_NAMES` feeds `monitor_core.spawn_tui` / applink router (a registry row would
spawn a stray `sitrep` window) and `_switch_to` matches by exact window name.
So the row is special-cased inside the switcher and always routes through the
existing idempotent focus-or-spawn path (`_dispatch_sitrep_open` →
`aitask_sitrep.sh open --root <selected root> --session <selected session>`).

Branch setup: profile `fast`, current branch (`main`), no worktree — as
resolved at Step 5. A dedicated worktree was considered because other sessions
held uncommitted changes in files this task touches (t2051 in
`monitor/monitor_core.py`, t2334 in `aidocs/framework/sitrep.md`, t2278_5's
screenshot markers in the docs pages). All three have since landed
(`9da106b51`, `514783b73`, `45539803d`); re-checked 2026-11-21: every path this
task touches is clean against HEAD and nothing is staged. The commit rule below
re-checks that at commit time instead of assuming it.

### Sequencing with t2340 (in flight on the same switcher file)

t2340 (switcher dialog clipped in the minimonitor pane, `tui_switcher.py:556`
fixed width 44) is `Implementing`, its agent is alive — verified 2026-11-22:
lock pid 1952803 on host omg16 with the lock's recorded `pid_starttime`
15074552 equal to `/proc/1952803/stat` field 22 (not a recycled pid), running
`claude … /aitask-pick 2340` in pane `%146` (`aitasks:agent-pick-2340`) on the
`-L ait` server, actively planning in plan mode at capture time. No registered
worktree, no plan file yet. It edits `.aitask-scripts/lib/tui_switcher.py`
in this same checkout. A per-file check cannot exclude a late same-file hunk
from `git commit -o`, so the two tasks are sequenced instead of interleaved:

- **Phase A (independent of t2340, now)**: §1b `monitor_core.py` fresh-spawn
  focus + its unit/live tests, §2 `minimonitor_keys.py` + its tests. Neither
  file is named by t2340. Implemented and tested, **not committed and not
  reviewed** at this point — no gate is recorded for Phase A.
- **Gate B — before the first edit of `tui_switcher.py`**: t2340 must have
  landed: its `(t2340)` commit touching `tui_switcher.py` is in `main`
  (`git log --oneline --grep='(t2340)' -- .aitask-scripts/lib/tui_switcher.py`)
  AND t2340 is no longer `Implementing` (archived, or its lock released), AND
  `git status --short -- .aitask-scripts/lib/tui_switcher.py` is empty. Then
  re-read the changed switcher code (line numbers, dialog width / narrow
  layout) and re-check that the Sitrep row and its `(Shift+S)` hint fit the
  width t2340 settled on (render the narrow layout).
- **If Gate B is not met when Phase A is done**, ask the user:
  - *Wait* — re-check Gate B on request; nothing is committed meanwhile.
  - *Ship Phase A as its own task* — create a separate task for the
    fresh-spawn focus fix + minimonitor hint move (its own plan = this plan's
    §1b/§2, its own Step 8 review, commit and archival), so it carries its own
    checkpoints; t2338 is then rescoped to Phase B and keeps only its
    `plan_approved` checkpoint (resume → `IMPLEMENT`, never `POSTIMPL`).
  Never record a Step 8 `review_approved` for t2338 with Phase B missing: the
  resume logic keys on that task-wide checkpoint and would route a resume to
  `POSTIMPL` (Step 9 / archival) without the Sitrep row.
- **Phase B (after Gate B)**: §1 switcher row, §3 switcher tests, §4 docs.
- **One official Step 8 review after both phases**, covering the whole t2338
  change; then the commits (both after that single review, each through the
  commit gates below):
  - A: `enhancement: Focus a freshly spawned sitrep window from another session and move S:sitrep to the minimonitor switcher line (t2338)` — `monitor_core.py`, `minimonitor_keys.py`, their tests;
  - B: `enhancement: Add a Sitrep row to the TUI switcher (t2338)` — `tui_switcher.py`, switcher tests, docs.
- **Note to t2340 (once the plan is approved, before Phase A)**:
  via the `/aitask-note` flow, body passed with `--file -` (quoted heredoc):

  ```bash
  ./ait note 2340 --from 2338 --with-live --file - <<'EOF'
  Advisory (t2338): t2338 will add a "Sitrep" row with a "(Shift+S)" key hint
  to the TUI switcher list. It will not edit .aitask-scripts/lib/tui_switcher.py
  until t2340 has landed. If t2340 measures the list's widest row for the
  minimonitor-pane width, that row is coming.
  EOF
  ```

  `NOTE_APPENDED:` is the success line; `LIVE_NONE:` after it is still success.

## Implementation

### 1. `.aitask-scripts/lib/tui_switcher.py`

- **Constants** (near `_TUI_SHORTCUTS`):
  - `_SITREP_ROW = "sitrep"`, `_SITREP_LABEL = "Sitrep"`.
  - Add `"sitrep": "S"` to `_TUI_SHORTCUTS` (action id `shortcut_sitrep` already
    exists, so `_resolve_tui_shortcut("sitrep")` resolves the live/overridden key).
- **Row key hint must not read `(S)` for both Settings and Sitrep**:
  `display_form()` capitalises, so `s` and `S` both render `(S)`. In
  `_TuiListItem.compose`, render a single uppercase alpha key as
  `display_form(f"shift+{key.lower()}")` → `(Shift+S)` (same spell-shift rule
  `_hint_segment` already uses for `M`). Factor as a tiny helper
  `_row_key_label(key)`. No existing row key is uppercase, so other rows are
  unchanged.
- **Helper** `_sitrep_windows(names) -> list[str]`: lazy
  `from sitrep_harvest import SITREP_WINDOW_RE` (lazy: `sitrep_harvest` pulls
  `sitrep_todo`; keep the switcher's import graph unchanged) and return the names
  matching it. Single source of truth for the window grammar.
- **`_populate_list_for`**: after the `_build_tui_list` loop and before the
  dynamic brainstorm rows, append the Sitrep row:
  `running = bool(_sitrep_windows(self._running_names))`,
  `is_current=False` **always** — the row is never disabled and never `▶`.
  Reason (review concern): `current_tui_name == "sitrep_tui"` is also set by the
  standalone `ait sitrep tui` in a spare pane, so it does not establish that the
  row's destination (the repo's sitrep window) is where the user is; selecting
  from inside the real sitrep window is harmless (`focused` toast).
  `first_selectable_idx` bookkeeping as for other rows. The `●` means "a sitrep
  window exists in this session" (name match, like every other row's dot); the
  destination is resolved at selection by the stamp-matching focus-or-spawn path.
  No "current sitrep TUI" name set is added.
- **No de-duplication from "Code Agents"** (review concern): the `agent-sitrep*`
  windows stay listed as direct rows. The lib-level switcher cannot prove that the
  repository action targets a given window id (a lone frozen `agent-sitrep` is
  skipped by the launcher, which opens a new window), and `lib/` must not import
  `monitor_core`'s role lookup. A direct row is never hidden.
- **Selection**: add `_activate_tui_item(item)` used by both
  `action_select_tui` and `on_list_view_selected` (they are currently identical
  copies): `item.tui_name == _SITREP_ROW` → `self.action_shortcut_sitrep()`
  (stale-entry / session-live checks, dismiss, worker + toast — unchanged
  code path); otherwise the current `_switch_to(...)` behaviour. Routing on the
  `_TuiListItem` (not inside `_switch_to`) means an "Other" window that happens
  to be literally named `sitrep` still switches normally.
- `action_shortcut_sitrep` / `_dispatch_sitrep_open` / `_open_sitrep_async`:
  unchanged. `_HINT_ITEMS`: unchanged (row already over budget; documented).

### 1b. `.aitask-scripts/monitor/monitor_core.py` — a fresh spawn must focus (review concern, verified)

Verified in `spawn_sitrep` (re-checked after t2051 landed: the `spawned`
block is at ~6011-6021): the `focused` branch and every repair
branch call `switch_to_pane_anywhere(agent)` when `select_window`, but the
`spawned` branch (`_sitrep_launch_agent_window` → `new-window`, selected only
inside the TARGET session) returns without switching the attached client. So
from another attached session (the switcher's cross-session case, and the
monitor's `S` on an agent of another session) a cold open leaves the client in
the source session.

Fix: in the `status == "spawned"` block, after the companion spawn and before
the return, `if select_window and not switch_to_pane_anywhere(agent):
warns.append("focus_failed")` — same order and warning token as the repair path
(the companion spawn runs first so it cannot steal focus afterwards;
`sitrep_open_message` already renders `focus_failed` as a warning suffix).
`select_window=False` (`--no-select`) keeps its no-move contract.

- Unit (`tests/test_sitrep_window.py` `SpawnTests`): cold spawn with
  `select_window=True` → `self.focus.assert_called_once_with("%42")`, detail "";
  with `select_window=False` → focus not called; focus returning False →
  `status="spawned"`, detail contains `focus_failed`; the frozen-TUI-moved
  spawn (H path) also focuses.
- Live (new `tests/test_sitrep_window_select_live.sh`, private server via
  `require_isolated_tmux`, same seams/driver shape as
  `test_sitrep_window_live.sh` but `select_window` from argv): sessions A and
  B; a real client attached to A through `script -qfc "tmux -L <sock> attach -t A"`
  (SKIP if `script` is unavailable); (1) cold spawn for session B → the client's
  `#{client_session}` is B and its active pane is the returned agent pane;
  (2) `switch-client -c <tty> -t A`, call again → `focused`, client back in B on
  the same pane, no new window; (3) mutant control `AIT_LIVE_MUTANT_NO_FIRST_FOCUS=1`
  (first `switch_to_pane_anywhere` is a no-op) turns assertion (1) red.
  The driver runs with `TMUX` / `TMUX_PANE` of a pane in session A, the way the
  switcher's worker runs inside its host TUI pane, so `switch-client`'s
  current-client resolution follows the real call path. Since t2051
  (`9da106b51`) a monitor keeps a `-C` control client attached to a helper
  session; case (1) is also run with such a control client attached to a third
  session, and asserts that the terminal client is the one moved and the
  control client's session is unchanged.
  Plus a one-off pre-fix control during implementation: run the driver with
  `PYTHONPATH` pointed at a detached worktree of the parent commit → client
  stays in A (reproduces the reported bug).

### 2. `.aitask-scripts/monitor/minimonitor_keys.py`

- Move `HintSeg(("open_sitrep",), "sitrep")` from the `loop/keys/multi` line to
  the `switcher/monitor` line → `j:switcher  m:monitor  S:sitrep` (33 cells at
  40 cols, ≤ 38).
- **Measure, don't eyeball** (per the comment block): render at (15,30),
  (18,·), (22,·), (40,·) before and after, reading `#mini-key-hints` region
  height with `short` removed (`_key_hints_desired_rows()`). Requirement: width
  15 ≤ 29 rows, width 40 stays 10 rows. Add a `t2338` row to the measurement
  table and a history bullet. If width 15 goes over budget, buy the row back in
  the same line set (e.g. move `M:multi`/`k:keys` grouping) and re-measure; if it
  cannot be bought back, stop and report rather than shrink unrelated labels.
- Help entries: extend the `tui_switcher` HelpEntry text to mention sitrep
  ("…settings, brainstorm or sitrep…"); move the `open_sitrep` HelpEntry next to
  "Full monitor" so the help order follows the band.

### 3. Tests

- `tests/test_tui_switcher_companion_spawn.py` (or a new focused
  `tests/test_tui_switcher_sitrep_row.py` if cleaner), using the existing
  `_populate_list_for` harness pattern (patched `_TMUX` / `_session_windows`,
  `_build_tui_list`, `_discover_brainstorm_sessions`):
  - the Sitrep row is present, not running with no sitrep window, running with
    `agent-sitrep` / `agent-sitrep-3`, not running with near-misses
    (`agent-sitrepx`, `agent-pick-sitrep`);
  - with `current_tui="sitrep_tui"` in the attached session (the standalone
    `ait sitrep tui` entry point) the row is NOT current and NOT disabled, and
    activating it dispatches the open;
  - a sole (frozen-style) `agent-sitrep` window stays listed under Code Agents as
    a direct row (with its window id) alongside the Sitrep row; two sitrep
    windows → both listed;
  - activating the Sitrep row calls `action_shortcut_sitrep` (stub
    `_dispatch_sitrep_open`, assert selected root/session, dismissed) and never
    `_switch_to`; activating a normal row still calls `_switch_to`; an "Other"
    window named `sitrep` routes to `_switch_to` with its window id;
  - row key label: `S` → `Shift+S`, `s` → `S`.
- `tests/test_monitor_sitrep_harvest_close.py` `SwitcherSitrepTests`: add
  `_TUI_SHORTCUTS["sitrep"] == "S"` alongside the existing binding assertion.
- `tests/test_minimonitor_key_hints_modes.py`: if it pins the line layout, update;
  add an assertion that `open_sitrep` shares a line with `tui_switcher` and
  `switch_to_monitor`.
- Run (each individually): `test_tui_switcher_companion_spawn.py`,
  `test_monitor_sitrep_harvest_close.py`, `test_git_tui_config.py`,
  `test_tui_switcher_git_shortcut_root.py`, `test_tui_switcher_hint_text.py`,
  `test_minimonitor_key_hints_modes.py`, `test_minimonitor_top_chrome_render.py`,
  and bash `test_tui_switcher_brainstorm_session.sh`,
  `test_tui_switcher_multi_session.sh`, `test_tui_switcher_footer_fit.sh`,
  `test_no_raw_tmux.sh`.

### 4. Docs (current-state wording, no history)

- `website/content/docs/tuis/_index.md` (~35): add Sitrep to the listed rows,
  drop it from the "reachable even though the hint row does not advertise them"
  clause; say selecting it opens or switches to the selected session's
  repository sitrep window.
- `website/content/docs/workflows/sitrep.md` (~23) and
  `website/content/docs/tuis/sitrep/_index.md` (~39): mention the switcher's
  Sitrep row next to `S`.
- `website/content/docs/tuis/minimonitor/how-to.md` (~398): add sitrep to the
  switcher's listed TUIs.
- `aidocs/framework/sitrep.md` (~29): "`S` and the Sitrep row in the TUI
  switcher".
- `aidocs/framework/tui_conventions.md` (after the four-part registry rule): a
  short paragraph — a switcher row that is not a launchable TUI (Sitrep) is
  special-cased in `_populate_list_for` + `_activate_tui_item`, never a registry
  entry, because `TUI_NAMES` feeds `spawn_tui`/applink.
- Run `python3 website/check_links.py --build`.
- The switcher screenshots (`tui_switcher_dialog`, `_from_minimonitor`) came
  from the screenshot task and may show the old row list. Flag their refresh
  in the final report.

### Commit hygiene (shared checkout, current branch)

- **Edit gate**: immediately before the first edit of each file, confirm
  `git status --short -- <file>` is empty (another session may have re-dirtied
  it). A dirty file → stop and report; do not edit around foreign hunks.
- **Commit gate**: before committing, `git diff -- <my paths>` is reviewed hunk
  by hunk and must contain only t2338 changes; `git diff --cached --name-only
  -- <commit paths>` must be empty (nothing foreign staged ON MY PATHS). Other
  sessions' staged entries elsewhere (currently two staged screenshot
  deletions under `website/static/imgs/`) are left alone: `commit -o` with
  named paths does not include them and keeps them staged.
- Commit with only my paths named: `git commit -o -m <msg> -- <my paths>` (no
  bare `commit`, no index-wide reset). `commit -o` needs new files to be known
  to git, so the new test files alone are `git add -- <new files>` first, and
  `git diff --cached --name-only -- <commit paths>` must then list exactly
  those new files. After the commit, `git diff --cached --name-only` outside my
  paths must equal what it was before (the other sessions' staged entries
  preserved).
- **Patch identity, not just file names**: at review time save the reviewed
  patch after the new files are `git add`ed, `git diff HEAD --binary -- <my
  paths> > $scratch/reviewed_<A|B>.patch` (covers tracked edits and the new
  files), and commit at once from that state. After the commit, `git show --format=
  --binary <sha> > $scratch/committed_<A|B>.patch` for the exact commit SHA
  (not `HEAD`, which another session may have moved) and `diff` the two with
  `index` lines stripped: they must be identical. Any extra hunk → stop and
  report (do not amend over another session's work without the user).
- If a gate fails because another session's hunk appeared in one of my files,
  stop and ask; fall back to a dedicated worktree only with the user's go-ahead.

Commits: A and B as in "Sequencing with t2340" — each run through the gates above separately.

### Step 9

Post-implementation per task-workflow Step 9 on the current branch (no merge
step: work lands directly on `main`), then archival.

## Verification

- Unit/integration tests listed in §3, each run individually, all PASS.
- Measured minimonitor band heights (before/after table) within budget.
- `bash tests/test_sitrep_window_select_live.sh` (cold + repeat from another
  attached session, mutant control red), `tests/test_sitrep_window.py`,
  `tests/test_sitrep_window_live.sh` (unchanged `select_window=False` contract).
- Manual (if a tmux session is available): `j` → Sitrep row shows `(Shift+S)`,
  `●` when the sitrep window exists; Enter opens/focuses it, also from another
  session; `agent-sitrep` still listed under Code Agents; minimonitor shows
  `j:switcher  m:monitor  S:sitrep` on one line at normal width.

## Risk

### Code-health risk: medium
- Selection handlers refactored into one `_activate_tui_item`; a mis-route could break Enter on normal rows · severity: low · → mitigation: covered by plan §3 tests (normal row, Other window named `sitrep`, Sitrep row)
- `(S)` key-hint ambiguity with Settings · severity: low · → mitigation: covered by plan §1 (`Shift+S` row label) + §3 test

- Fresh-spawn focus change alters every `open` caller without `--no-select` (`ait sitrep`, monitor/minimonitor `S`, sitrep TUI `A`) · severity: low · → mitigation: covered by §1b unit + live tests; it matches the documented "takes you to that window" behaviour and the existing repair/focus branches
- A concurrent session re-dirties a touched file in the shared checkout before the commit · severity: medium · → mitigation: covered by plan "Commit hygiene" (edit gate + commit gate, path-scoped `commit -o`, stop-and-ask on a foreign hunk)

### Goal-achievement risk: low
- Moving `S:sitrep` could push the width-15 band over its 29-row budget · severity: low · → mitigation: covered by plan §2 measure-before/after with a defined fallback
- Running dot is name-based (not stamp-based): `●` for a lone frozen or another root's sitrep window · severity: low · → mitigation: accepted — same meaning as other rows' dot ("window exists"); the row is never disabled and the destination is resolved at selection; direct window rows stay listed
