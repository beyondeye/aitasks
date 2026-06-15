---
Task: t994_minimonitor_ux_shadow_left_footer_twoline_desc.md
Base branch: main
plan_verified: []
---

# t994 — Minimonitor UX polish

## Context

`ait minimonitor` is the compact tmux companion TUI. Four UX rough edges were
reported:

1. The **shadow companion pane** (launched with `e`) spawns to the **right** of
   the minimonitor and has no width floor, so it can come up too narrow. It
   should spawn to the **left** with a configurable minimum width (default 80).
2. The **footer shortcut hints** are cramped and unevenly grouped.
3. The `r:refresh` shortcut is redundant (the TUI auto-refreshes) and should go.
4. The **followed-agent task description** at the top is clipped to a single
   30-char line; it should use two lines.

All four are small, self-contained edits to the minimonitor TUI plus the shared
tmux-launch helper and the settings tab. Implemented as a single task (no child
split). Profile: `fast`, current branch.

---

## 1. Shadow pane: spawn left + configurable min width

### 1a. Extend the shared launch config/helper

`.aitask-scripts/lib/agent_launch_utils.py`

- **`TmuxLaunchConfig` dataclass (line 63):** add two optional fields, used only
  by the split branch:
  ```python
  split_before: bool = False     # tmux -b: place new pane left/above
  split_size: int | None = None  # tmux -l <N>: pane size (cols for -h)
  ```
- **`launch_in_tmux` split branch (lines 600-615):** extend the argv. Currently:
  ```python
  split_flag = "-h" if config.split_direction == "horizontal" else "-v"
  rc, out = _TMUX.run(["split-window", "-P", "-F", "#{pane_id}",
                       split_flag, "-t", target, *cwd_args, command])
  ```
  Build the flag list so `-b` is added when `config.split_before` and
  `-l <size>` when `config.split_size` is set, e.g.:
  ```python
  split_args = ["split-window", "-P", "-F", "#{pane_id}", split_flag]
  if config.split_before:
      split_args.append("-b")
  if config.split_size is not None:
      split_args += ["-l", str(config.split_size)]
  split_args += ["-t", target, *cwd_args, command]
  ```
  All other `launch_in_tmux` callers leave the new fields at their defaults, so
  their behaviour is byte-for-byte unchanged (the new-window / new-session
  branches don't touch these fields at all). The minimonitor self-spawn at
  lines 800-816 is a *separate* raw `split-window` call and is untouched.

### 1b. New setting `shadow_pane_width` (default 80)

- **`seed/aitasks/metadata/project_config.yaml`** and the live
  **`aitasks/metadata/project_config.yaml`** — add `shadow_pane_width: 80` to
  the `tmux:` block (alongside `default_split`, `shadow_same_window`).
- **`.aitask-scripts/settings/settings_app.py`** — add to `TMUX_CONFIG_SCHEMA`
  (after `shadow_same_window`, ~line 267):
  ```python
  "shadow_pane_width": {
      "summary": "Minimum width (cols) of the shadow agent pane",
      "detail": "Minimum column width for the shadow companion pane spawned "
                "by minimonitor 'e' (default: 80)",
      "type": "int",
      "default": "80",
  },
  ```
  The tmux tab only handles `string`/`enum`/`bool` today, so add an `int`
  branch in both places:
  - `_populate_tmux_tab` (render, ~line 2398): treat `int` like `string` —
    mount a `ConfigRow` with the numeric value as text
    (`id=f"tmux_cfg_{_safe_id(key)}_{rc}"`, same as the string branch).
  - `save_tmux_settings` (persist, ~line 2449): add an `int` branch that reads
    the `ConfigRow.raw_value`, coerces with `int(val)` inside try/except, and
    falls back to `int(info["default"])` on a bad value.

### 1c. Use it in the shadow launch

`.aitask-scripts/monitor/minimonitor_app.py` — `action_launch_shadow`
(same-window branch, lines 978-986). Read the configured width from the already
loaded `tmux_cfg` and pass the new fields:
```python
shadow_width = int(tmux_cfg.get("shadow_pane_width", 80))
cfg = TmuxLaunchConfig(
    session=sess, window=snap.pane.window_name,
    new_session=False, new_window=False,
    split_direction=str(tmux_cfg.get("default_split", "horizontal")),
    split_before=True,          # spawn to the LEFT
    split_size=shadow_width,    # minimum width
    cwd=str(target_root),
)
```
`_load_project_tmux_config` (line 1165) already reads the `tmux:` block, so
`tmux_cfg.get("shadow_pane_width", 80)` works with no loader change; the
fallback default keeps existing projects (whose config lacks the key) at 80.

---

## 2. Footer shortcut reorganization

`.aitask-scripts/monitor/minimonitor_app.py` — the `#mini-key-hints` Static in
`compose()` (lines 201-207). Replace the 4-line text with:
```
i:info  q:quit  tab:agent
s/↑↓:switch  enter:send
d:detect (≈ strip, = raw)
j:tui switcher  m:full monitor
k:kill  n:next  e:shadow
```
(Per the user's chosen footer answer, `k/n/e` are **kept** on a final line so
no hint disappears.) Use the existing `↑↓`/`≈` escapes already in
the file. No `BINDINGS` change for these keys — only the displayed text.

## 3. Remove the refresh shortcut

`.aitask-scripts/monitor/minimonitor_app.py`:
- Remove `Binding("r", "refresh", "Refresh", show=False)` (line 152).
- Ensure `r:refresh` no longer appears in the footer text (handled by §2).
- `action_refresh` (line 1052): check whether any other code path calls it
  (e.g. a timer or `call_later`). `grep -n "action_refresh\|\"refresh\"\|'refresh'\|_refresh_data"`
  — the periodic refresh runs via `_refresh_timer`/`_refresh_data`, not
  `action_refresh`. If nothing else references `action_refresh`, remove the
  method too; if anything does, leave the method and only drop the binding.

## 4. Two-line task description at the top

`.aitask-scripts/monitor/minimonitor_app.py` — `_own_agent_identity_text`
(lines 551-567). Today the title is clipped to 30 chars on one line. Allow two
lines:
- `import textwrap` (stdlib; add to the import block near line 12).
- Compute a per-line width from the pane: `width = max(20, self._target_width - 4)`
  (account for the `padding: 0 1` on `.mini-own-card` plus the 2-space indent).
- `lines = textwrap.wrap(title, width)[:2]`; if `len(lines) == 2` and the title
  was longer, append `…` to the 2nd line.
- Join as `"\n  [dim]" + "[/]\n  [dim]".join(lines) + "[/]"` so each wrapped
  line keeps the existing 2-space dim indent.
- `.mini-own-card` CSS is already `height: auto`, so it grows to two lines with
  no CSS change.

**Scope:** Change only `_own_agent_identity_text` (the top followed-agent
panel — what the user pointed at). Leave the general-list card
`_status_text`/lines 540-548 at its single 30-char line unless it looks
visibly inconsistent during manual verification.

---

## Conventions / guardrails

- **tmux gateway** (`aidocs/framework/tmux_gateway.md`): the new `-b`/`-l`
  flags go inside the existing gateway-routed `_TMUX.run` call — no new raw
  `tmux` call site, so `tests/test_no_raw_tmux.sh` stays green.
- **TUI** edits follow `aidocs/framework/tui_conventions.md`.
- Source of truth is Claude Code; these are Python/YAML/settings changes (no
  skill markdown), so no cross-agent skill port is implied.

## Verification

1. **Unit test (argv mapping)** — extend `tests/test_launch_in_tmux_pane_pid.py`
   (it already mocks `subprocess.run` and inspects argv): add a case building a
   split-branch `TmuxLaunchConfig(split_before=True, split_size=80,
   new_window=False)` and assert the captured argv contains `-h`, `-b`, and the
   `-l`, `80` pair, and that omitting the fields yields neither. Run:
   `python3 tests/test_launch_in_tmux_pane_pid.py`.
2. **Lint:** `shellcheck` not needed (no shell touched); run the Python tests
   above and `python3 -m py_compile` on the three edited `.py` files.
3. **Settings round-trip:** open `ait settings` → Tmux tab → confirm
   `shadow_pane_width` renders as an editable int field, save, and verify
   `aitasks/metadata/project_config.yaml` gains `shadow_pane_width: 80`
   (or the edited value).
4. **Manual (TUI):** in a tmux window with an agent + minimonitor:
   - Press `e` → shadow pane appears **to the left**, ≥80 cols wide.
   - Footer shows the 5-line layout; no `r:refresh`; `r` no longer refreshes.
   - A long task title wraps to two lines in the top followed-agent panel.

## Post-implementation

Follow task-workflow Step 8/9: run tests, commit on the current branch with
message `enhancement: <desc> (t994)`, then archival per the standard flow.

## Risk

### Code-health risk: low
- New `split_before`/`split_size` fields on the shared `TmuxLaunchConfig`
  default to no-op, so all existing `launch_in_tmux` callers are byte-for-byte
  unchanged · severity: low · → mitigation: TBD
- Adding an `int` branch to the settings tmux tab + footer/description text
  edits are display-only and pattern-fitting · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- "Minimum width 80" is implemented as tmux `-l 80` (the pane's *initial*
  width). tmux has no persistent per-pane minimum, so a later window resize can
  shrink the shadow pane below 80 — unlike the minimonitor's own
  `_maybe_pin_width` re-pin. Accepted as matching how the minimonitor spawns its
  own pane; flagged for the manual-verification step · severity: medium ·
  → mitigation: TBD
- Live `split-window -b -h` behavior in a multi-pane agent window (which pane is
  split, exact left placement) is verified manually, not by unit test ·
  severity: low · → mitigation: TBD

_No before/after mitigation tasks proposed — the manual-verification step in the
Verification section covers the medium goal-achievement risk._
