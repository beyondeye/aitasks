---
Task: t2174_tui_switcher_spawn_minimonitor_companion.md
Base branch: main
Output branch: main
---

# t2174 — TUI switcher: spawn a minimonitor companion beside the host TUI

## Context

A minimonitor companion is auto-spawned only for code-agent windows and the git
TUI. Every other framework TUI window (board, trails, codebrowser, settings,
stats, syncer, brainstorm, applink, chatlink, frozenagent) has none. Getting back
from one of them to a given agent means reopening the switcher and scanning the
list. This adds a switcher quick-jump, **`M`**, that splits a minimonitor into the
window of the TUI the switcher was opened from. It is shown only when that window
has no companion yet.

Decisions (task "Design decisions"; the auto_spawn one was confirmed with the user):
- Never offered in `monitor` / `minimonitor` (or when `current_tui` is empty).
- Target = the host TUI's own window, resolved from `$TMUX_PANE` and verified
  against the gateway server. It does not depend on the session being browsed
  with ←/→. The pane id and window index are passed explicitly, never looked up
  by name.
- **`auto_spawn: false` is bypassed** for this explicit request, through a new
  `explicit=True` kwarg (not a reuse of `force_companion`).
- The overcrowding gate (3+ real panes) and the lock stay. If either refuses,
  the user gets a warning notification. The overlay's mount-time probe is
  advisory; the locked check in `maybe_spawn_minimonitor` decides.
- project_root = `Path.cwd()` (the host TUI's project), not the browsed one.
- On success the overlay is dismissed. `maybe_spawn_minimonitor` refocuses the
  TUI pane.

Working on the current branch (`main`), profile `fast`.

## Implementation

### 1. `.aitask-scripts/lib/agent_launch_utils.py` — share the classification, add the probe

a. **Extract the pane-list format and classifier** from `_companion_check_and_split`
   (≈ line 2532) so the split path and the new probe cannot drift:

   ```python
   def _companion_pane_format() -> str:
       helper_fields = "|".join(f"#{{{opt}}}" for opt in BOUND_HELPER_TARGET_OPTIONS)
       return (f"#{{pane_id}}|#{{{MONITOR_KIND_OPTION}}}|{helper_fields}"
               "|#{@aitask_frozen}|#{pane_dead}|#{pane_start_command}")

   @dataclass(frozen=True)
   class _CompanionScan:
       present: bool                  # live-marked, or booting (start cmd, not dead)
       real_panes: int                # occupants counted toward the 3-pane limit
       window_panes: frozenset[str]
       stale_marked: tuple[str, ...]  # panes whose marker's process is gone

   def _scan_companion_window(out: str) -> _CompanionScan: ...
   ```
   The scan runs the same per-row rules, in the same order, as today's loop:
   frozen → counted real; marker → `monitor_marker_alive` ? present : stale (a
   helper, never counted); start command == `_COMPANION_START_COMMAND` → present
   unless dead (dead = helper); bound helper → skipped; else real. Differences
   from today: there is **no early return** and **no tmux side effect**. The
   long explanatory comment block moves onto the scan.

b. **`_companion_check_and_split` uses the scan.** It runs `list-panes` with
   `_companion_pane_format()`, keeps the `agent_pane and rc != 0` fail-closed
   rule, self-heals every `scan.stale_marked` pane (same
   `set-option -pu … MONITOR_KIND_OPTION` spawn as today), then refuses on
   `scan.present`, on `scan.real_panes >= 3`, and when `agent_pane` is not in
   `scan.window_panes`. The rest is unchanged. One behaviour delta, stated in a
   comment: a stale marker that sits *after* a live companion is now healed too.
   Before, the early return skipped it. Healing a marker whose process is
   verified gone is always correct.

c. **New read-only probe**, beside it:
   ```python
   def companion_present(pane: str) -> bool | None:
       """Does ``pane``'s window already hold a monitor/minimonitor companion?
       Read-only twin of the split path's eligibility read (same scan): a live
       marker or a booting `ait minimonitor` means present. Never self-heals.
       None = unknown (empty pane, tmux failure, pane absent from the listing);
       callers fail closed."""
       if not pane:
           return None
       rc, out = _TMUX.run(["list-panes", "-t", pane, "-F", _companion_pane_format()])
       if rc != 0:
           return None
       scan = _scan_companion_window(out)
       if pane not in scan.window_panes:
           return None
       return scan.present
   ```
   `-t <pane>` lists that pane's window (t2039: an untargeted list resolves to the
   session's current window).

d. **`gateway_pane_window(pane, tmux_env) -> tuple[str, str] | None`** returns
   `(session, window_index)`, applying the same server-identity rule as
   `current_tmux_session` (t1951). Factor the socket comparison out of
   `_gateway_pane_session` into `_gateway_socket_matches(sock, tmux_env)` and use
   it in both. **Leave `_gateway_pane_session`'s `#{socket_path}\t#{session_name}`
   format unchanged**: `tests/test_trails_focus_writer.py` and
   `tests/test_pick_command_screen.py` pin it. The new function does its own
   `display-message -p -t <pane> '#{socket_path}\t#{session_name}\t#{window_index}'`.

e. **`maybe_spawn_minimonitor(..., explicit: bool = False)`**: change the gate to
   `if not auto_spawn and not explicit: return None`. In the docstring,
   `explicit` means a user-requested spawn: `auto_spawn` governs *automatic*
   spawning only. Every other gate still applies.

### 2. `.aitask-scripts/lib/tui_switcher.py` — key, hint, action

a. Import `companion_present` and `gateway_pane_window` in the existing
   `from agent_launch_utils import (...)` block. `maybe_spawn_minimonitor` stays a
   local import inside the action, as in `_launch_git_with_companion`.

b. Add `Binding("M", "spawn_minimonitor", "Minimonitor here", show=False)` to
   `_QUICK_JUMP_BINDINGS`. It is then registered under `shared.tui_switcher`
   automatically: the `?` editor and Settings → Shortcuts both list it, and it is
   added to `_OVERLAY_RESERVED_KEYS`. Add a module constant
   `_COMPANION_INELIGIBLE_HOSTS = frozenset({"monitor", "minimonitor"})` and a
   `_CompanionTarget(NamedTuple)` with `session, window_index, pane, project_root`.

c. `__init__`: `self._companion_target: _CompanionTarget | None = None`.
   Add a new method:
   ```python
   def _resolve_companion_target(self) -> _CompanionTarget | None:
       """The host TUI's own window, when a companion may be offered there.
       Fails closed: an ineligible host, an unverifiable $TMUX_PANE, or an
       unknown probe result all hide the option."""
       if not self._current_tui or self._current_tui in _COMPANION_INELIGIBLE_HOSTS:
           return None
       pane = os.environ.get("TMUX_PANE", "")
       location = gateway_pane_window(pane, os.environ.get("TMUX", ""))
       if location is None:
           return None
       if companion_present(pane) is not False:   # present, or unknown
           return None
       return _CompanionTarget(location[0], location[1], pane, Path.cwd())
   ```
   `on_mount` sets `self._companion_target = self._resolve_companion_target()`
   before `self._render_hint()`. That costs two tmux calls, the same order as the
   existing synchronous `get_tmux_windows`. Ineligible hosts make no calls.

d. **Shift-aware hint segment.** `render_label` matches a single-letter key
   case-insensitively, so the plain `_hint_segment` would render `M` as
   `(M)inimonitor`, which looks exactly like monitor's `(M)onitor` (verified:
   `render_label('monitor','m')` → `(M)onitor`, `render_label('minimonitor','M')`
   → `(M)inimonitor`). A user following the hint could press `m` and land in the
   full monitor. Add a keyword-only `spell_shift: bool = False` to
   `_hint_segment`. When it is set and the **resolved** key is a single uppercase
   letter, render it as the combo `shift+<lower>`. `render_label` then produces
   the multi-key prefix form, `(Shift+M) minimonitor`, and the existing
   `_KEY_PAREN_RE` styling applies unchanged:
   ```python
   def _hint_segment(action_id, label, default_key, *, spell_shift=False) -> str:
       key = resolve_key(_TUI_SWITCHER_SCOPE, action_id, default_key) or default_key
       if spell_shift and len(key) == 1 and key.isalpha() and key.isupper():
           # A bare `M` renders as `(M)`, indistinguishable from `m` (monitor).
           key = f"shift+{key.lower()}"
       rendered = render_label(label, key)
       ...
   ```
   A rebind is still reflected because the resolved key is used: `w` gives
   `(W) minimonitor`, and `ctrl+o` gives `(Ctrl+O) minimonitor`. Only the new
   segment passes `spell_shift=True`. Every existing segment, and the
   `test_tui_switcher_hint_text.py` pins on them (`e(X)plore+` etc.), is
   unchanged.

   `_render_hint`: when `self._companion_target` is set, prefix the **second**
   line (the `Enter switch …` line, in both single- and multi-session branches)
   with `_hint_segment("spawn_minimonitor", "minimonitor", "M", spell_shift=True) + "  "`.
   The 122-col first row is untouched. The narrow
   minimonitor host never shows this hint (it is ineligible), so its footer is
   unchanged. In wide hosts the dialog gains at most one wrapped hint row.

e. Action:
   ```python
   def action_spawn_minimonitor(self) -> None:
       """Split a minimonitor into the window of the TUI this switcher was opened
       from (never the browsed session's). The mount-time probe only decides
       whether to offer it; the locked check in maybe_spawn_minimonitor decides
       whether it happens."""
       target = self._companion_target
       if target is None:
           return
       from agent_launch_utils import maybe_spawn_minimonitor
       companion = maybe_spawn_minimonitor(
           target.session, self._current_tui,
           window_index=target.window_index, force_companion=True, explicit=True,
           project_root=target.project_root, agent_pane=target.pane,
       )
       if companion is None:
           self.app.notify(
               "Minimonitor not added: this window already has one, holds 3+ "
               "panes, or tmux was busy", severity="warning")
           return
       self.dismiss(None)
   ```
   The cleanup hook is armed inside `maybe_spawn_minimonitor` (explicit
   `agent_pane`), so no second arming is needed. The git path needed one only
   because it passes no `agent_pane`.

### 3. Tests — new `tests/test_tui_switcher_companion_spawn.py` (unittest; picked up by the Python runner)

A small scripted `_TMUX` fake (pattern from `tests/test_minimonitor_instance_guard.py`
`_FakeTmux` / `_render_panes`, socket dir from `_LockDir`) covering:
- **Probe**: live marker → True; stale marker → False **and no `set-option` call**
  (read-only); unverifiable `garbage:123` → True; booting start command (not dead)
  → True; dead companion → False; bound helper (shadow target) only → False;
  `list-panes` rc≠0 → None; pane missing from listing → None; empty pane → None;
  the `list-panes` argv targets `-t <pane>`.
- **Parity**: for a table of layouts under the 3-pane limit, `companion_present`
  is True exactly when `maybe_spawn_minimonitor(..., agent_pane=…)` refuses.
- **explicit**: a temp project_root whose `project_config.yaml` sets
  `auto_spawn: false`: without `explicit` there is no split; with
  `explicit=True` it splits.
- **gateway_pane_window**: matching socket → `(session, index)`; foreign socket → None;
  rc≠0 → None; empty pane/env → None.
- **Overlay** (no Textual runtime; patch `ts.gateway_pane_window` /
  `ts.companion_present` and env):
  - `_resolve_companion_target` returns None for `monitor`, `minimonitor` and `""`
    without calling the probe. It also returns None for probe True and probe
    None, and returns the target for probe False.
  - `_render_hint` (Label stub as in `test_tui_switcher_hint_text.py`) contains
    the `(Shift+M) minimonitor` segment iff a target is set, in both single- and
    multi-session modes, and **never** `(M)inimonitor`, which would collide with
    `(M)onitor`.
  - `_hint_segment(..., spell_shift=True)` under a patched `resolve_key`:
    `M` → `(Shift+M) minimonitor`, `w` → `(W) minimonitor`, `ctrl+o` →
    `(Ctrl+O) minimonitor`. Without `spell_shift`, the output for every
    `_HINT_ITEMS` entry is byte-identical to before.
  - The action with no target never calls `maybe_spawn_minimonitor`. With a
    target and `_selected_key` moved to *another* session entry, it is called
    with the target's session, window_index and pane, `force_companion=True`
    and `explicit=True`. Success dismisses; a None result notifies a warning and
    does not dismiss.
  - Binding table: exactly one `spawn_minimonitor` binding, default key `M`, no
    key collision inside `_QUICK_JUMP_BINDINGS`.

Existing suites that must stay green, unchanged:
`tests/test_minimonitor_instance_guard.py` (refactor guard),
`tests/test_tui_switcher_hint_text.py`, `tests/test_tui_switcher_footer_fit.sh`,
`tests/test_shortcut_scopes.py` (derives quick-jumps from the table),
`tests/test_tui_switcher_agent_launch.py`, `tests/test_tui_switcher_multi_session.sh`,
`tests/test_no_raw_tmux.sh`, `tests/test_helper_panes.py`.

### 4. Docs (current-state prose only)

- Docs name the key as **Shift+M** (`M`), never a bare "m", for the same
  reason as the hint.
- `website/content/docs/tuis/minimonitor/how-to.md`: add the switcher's `M` key
  to the list of spawn routes (≈ line 17). Add a short "How to add a minimonitor
  beside any TUI" section covering: press `j` then `M`; it is offered only when
  the window has none; it is not offered in monitor/minimonitor; the 3-pane
  limit applies; `auto_spawn: false` does not block it. Note that last point in
  the auto-spawn config passage too (≈ line 429).
- `website/content/docs/tuis/minimonitor/_index.md`: the spawn-routes list (≈ line 56).
- `website/content/docs/tuis/_index.md` line 34: the "Minimonitor is not listed in
  the switcher itself…" sentence gains the `M` route.
- `website/content/docs/tuis/monitor/_index.md` line 76: add the `M` key
  sentence, and drop "minimonitor" from that sentence's list of switcher
  entries. It is not a list entry, as `tuis/_index.md` already states.
- Run `cd website && python3 check_links.py --build`.

### Post-phase (risk mitigations)

1. [live_quit_closes_window] Live check on an **isolated** tmux server, never the
   user's `-L ait` one. Export `TMUX_TMPDIR=<scratchpad>/tmux` and
   `AITASKS_TMUX_SOCKET=t2174live`, then start
   `tmux -L t2174live new-session -d -s t2174 -x 200 -y 50 -c <repo> './ait stats'`,
   so the server, and therefore the TUI's switcher, inherit the socket. After
   boot: `send-keys j`, then capture the overlay and confirm the hint reads
   `(Shift+M) minimonitor`; then `send-keys M`. Assert that `list-panes` shows 2 panes, one
   running `ait minimonitor`, and that the stats pane has `remain-on-exit on`
   plus a `pane-died` cleanup hook. Then `send-keys q` to stats. Assert that the
   window/session is gone within a few seconds, which means the cleanup hook
   killed both panes. Also re-open the switcher in a window that already has a
   companion and confirm the hint is absent. Report the observed results
   verbatim in the Final Implementation Notes. Kill the scratch server by its
   `-L t2174live` socket only.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` is too broad. Instead
  run the targeted modules directly: `python3 tests/test_tui_switcher_companion_spawn.py`,
  `python3 tests/test_minimonitor_instance_guard.py`,
  `python3 tests/test_tui_switcher_hint_text.py`, `python3 tests/test_shortcut_scopes.py`,
  `python3 tests/test_tui_switcher_agent_launch.py`, `python3 tests/test_helper_panes.py`,
  `python3 tests/test_trails_focus_writer.py`, `python3 tests/test_pick_command_screen.py`.
- `bash tests/test_tui_switcher_footer_fit.sh`, `bash tests/test_tui_switcher_multi_session.sh`,
  `bash tests/test_no_raw_tmux.sh`, `bash tests/test_companion_cleanup_ordering.sh`.
- The live check in the post-phase.
- `website/check_links.py --build`.

Then Step 9 (Post-Implementation): commit, archive, push via the task workflow.

## Risk

### Code-health risk: medium
- Refactoring the companion eligibility loop in `_companion_check_and_split` touches the load-bearing spawn path used by every companion flow (agent launches, `ait ide`, frozen restore, git). A mis-ported rule would silently allow duplicate companions or block spawns. Bounded by the existing `test_minimonitor_instance_guard.py` suite (guard, booting, dead, helper, frozen, lock cases) plus the new parity test · severity: medium · → mitigation: none (covered by the existing suite + parity test)
- `remain-on-exit on` plus a `pane-died` hook now land on TUI panes that get a companion. If a TUI's quit didn't fire the hook, its dead pane would linger. The git TUI already takes this path · severity: low (residual — addressed by inline post-phase live_quit_closes_window) · → mitigation: inline post-phase live_quit_closes_window

### Goal-achievement risk: low
- The mount-time probe can be stale by the time `M` is pressed (another companion booted in between). The locked re-check in `maybe_spawn_minimonitor` refuses and the user is notified, so the result is a refusal rather than a duplicate · severity: low · → mitigation: none
- The case-insensitive key renderer would show `M` as `(M)`, the same as monitor's `m`, so the user could press the wrong key (found in plan review). The design addresses it in step 2d (the `spell_shift` hint, pinned by tests) · severity: low (residual) · → mitigation: none (designed in)

### Planned mitigations
- timing: post-phase | name: live_quit_closes_window | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: remain-on-exit/pane-died on TUI panes | desc: live isolated-tmux check that M spawns a companion beside a Textual TUI and that quitting the TUI closes the window
