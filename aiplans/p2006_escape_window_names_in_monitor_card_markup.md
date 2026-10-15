---
Task: t2006_escape_window_names_in_monitor_card_markup.md
Base branch: main
Output branch: main
---

# t2006 — Render user-derived fields literally in `ait monitor` cards, preview header and kill dialog

## Context

`ait monitor` interpolates the raw tmux window name into markup. A window named
`agent-[/]x` (any user can rename a window) crashes the TUI. A `Static` widget given
`" 1:agent-[/]x (0)  [dim]parked[/]"` raises `MarkupError: auto closing tag ('[/]')
has nothing to close` inside `run_test`; I checked this. A name like `agent-[bold]y`
fails silently instead: the tag is swallowed. t1351 fixed the same defect in
minimonitor with `rich.markup.escape`.

**`escape()` is not enough under Textual's parser.** Probes in the installed environment
(Textual 8.2.7, Rich 14.3.2) show this:
- Textual's tokenizer opens a tag at `(?<!\\)\[`. Its text tokens un-escape exactly `\[` → `[`. Every other backslash stays literal: `\\` is **not** collapsed.
- `rich.markup.escape` and `textual.markup.escape` (they are identical) double the backslashes before a bracket. So the window name `agent-\[bold]y` displays as `agent-\\[bold]y`.
- A field that ends in `\` and is followed by the template's closing tag (`[dim italic]t42: ends \` + `[/]`) turns that tag into literal `[/]`, and the style never closes. Under Textual's grammar it is impossible to write a backslash immediately before a real tag.
- Rich's `Text.from_markup` renders both cases correctly. A Rich-parsed test therefore cannot see the defect; only Textual's parser (`textual.content.Content.from_markup`, which is what `Static` uses) can.

The probes also show what does work:
- (a) Prefix every `[` with `\` and leave backslashes untouched. Under Textual this round-trips exactly for every value, as long as a value ending in `\` is not directly followed by a tag.
- (b) When a still-open style is left open, Textual closes it at end of input.
- (c) `Content.from_markup(template, **variables)` substitutes `$name` **after** tokenizing, so the values are inserted literally and the spans are correct.

**Scope (user decision, 2026-10-15):** the card rows and the preview header (both named by the task), plus the shared `KillConfirmDialog`. The dialog is a confirmed crash on `k` for such a window in **both** monitor and minimonitor. Fixes stay within these surfaces. **Handed to one follow-up at Step 8b** (line numbers as of `d931e10c3`). The audit in Verification checks against exactly this list:
- the `monitor_app.py` toasts that name a window, at ≈:2951 (via `name` from :2950), :3527, :3530, :3614, :3617, :3719 and :3816. I checked these: no crash, but the tag is swallowed.
- task-title markup sinks in dialogs:
  - `RestartConfirmDialog` "Current:" row (`monitor_app.py:355`)
  - `TaskDetailDialog` title and header (`monitor_shared.py:2244`, `:2285`)
  - `NextSiblingDialog` current and suggested rows (`monitor_shared.py:2812`, `:2814`)
  - `_SiblingRow.render` (`monitor_shared.py:2886`)
- minimonitor's toasts.
- the status-bar session names and the `Session renamed` toast.
- the existing `rich.markup.escape` users rendered by Textual, which carry the same backslash defect: minimonitor `_row_name` / title / `_own_header_text`, `format_session_divider`, `monitor_shared.py:1130` and `monitor_app.py:3551`.

**Representation per surface:**
- **Card builders keep returning markup `str`.** About 8 test files pin their markup substrings (`[bold magenta]◆[/]`) and the byte-identical-row invariants (t1133), so changing the return type is out of proportion here. They use helper (a). The two fields that end their row (the task title and the OTHER row's command) end the string **with no closing tag**, using (b), so a trailing backslash is safe.
- **Preview header and kill dialog** are each a single `update()` / `Static()` sink, and no test reads their string. They use (c): a `Content.from_markup` template with `$variables`.

Files touched (none of them is dirty in the shared worktree):
- `.aitask-scripts/monitor/monitor_shared.py`
- `.aitask-scripts/monitor/monitor_app.py`
- `tests/test_kill_confirm_dialog.py`
- `tests/test_monitor_markup_escape.py` (new)

## Implementation

Order: write the tests first (steps 1–2) and run them against the **unmodified**
source as the red proof, then fix (steps 3–5). No stash is needed: the source is only
edited after the red run. The tests reach the new helper module-qualified
(`ms.markup_literal`), so before the fix only the helper test errors, and the row
tests still run and fail for the real reason.

Hostile value tables, shared by both test files:
- names:
  - `agent-[/]x` (raises)
  - `agent-[bold]y` (swallowed)
  - `agent-\[bold]y` (backslash before a bracket)
  - `agent-x\` (trailing backslash)
  - `"agent-" + "[/]x[dim]" * 5`
- titles:
  - `Fix [/] and [dim]x[/dim]`
  - `a \[bold] b`
  - `ends with \` (trailing backslash before the template's closing tag)
- commands:
  - `[/]cmd`
  - `\[x]`
  - `cmd\`

1. **New `tests/test_monitor_markup_escape.py`.** Header and imports follow
   `tests/test_monitor_agent_marks.py`: sys.path inserts, pop `TMUX`/`TMUX_PANE`, and
   real `TmuxPaneInfo` / `PaneSnapshot` / `TaskInfo`. Every assertion parses with
   **Textual's** `Content.from_markup(...)` or reads a mounted widget's
   `render().plain`, never Rich's `Text.from_markup`.
   - `MarkupLiteralTests`. For every table value, `Content.from_markup(f"[bold]{ms.markup_literal(v)} (0)[/]").plain == f"{v} (0)"`. A **negative control** shows that `rich.markup.escape` fails the same round trip for `agent-\[bold]y`, so the table can tell the two apart.
   - `RowShapeTests`. This uses a `__new__` stub shaped like `_MarksFixture.app`:
     - `_monitor` fake (`stripped`, not overridden, shadow `None`)
     - `_completed_pane_ids = frozenset()`
     - `_has_fresh_concerns = lambda pid: False`
     - `_mark_kind = lambda snap: KIND_NONE`
     - `_task_cache` fake (task `"42"`)
     - `_gate_cache` fake (`summary_for → ""`, `phase_for → PhaseSignal()`)

     The cases:
     - **Live, parked and frozen rows** for every name: `f"1:{name} (0)"` is in the plain text. Parked and frozen also end with `parked` / `frozen`, which proves the trailing tag still parses.
     - **Live row with a task** for every title: line 2's plain text **equals** `f"     t42: {title}"`, and one `dim italic` span covers exactly the text after the indent.
     - **OTHER row** for every name × command: the plain text **equals** `f" ○ 1:{name} (0)  {cmd}"`, and a `dim` span covers the command.

     Exact equality catches a doubled backslash, a leaked `[/]` and a swallowed tag alike.
   - `MountedTests`. A real `MonitorApp(session=…, project_root=tmp)` under `run_test(size=(120, 30))`. After mount, swap in the fakes, as `test_mounted_card_renders_the_mark` does.
     - **Cards:** an agent named `agent-\[bold]y` with the title `ends with \`, and an OTHER pane `agent-[/]x` running `cmd\`. Call `_rebuild_pane_list()` and then `await pilot.pause()`. Each card's `render().plain` carries the exact strings above.
     - **Header:** focus the agent, using `content=""` so the `(empty)` branch runs and no worker starts, and call `_update_content_preview()`. The plain text of `#content-header` must **equal** `"Content Preview (1:agent-\[bold]y) t42: ends with \"`. Repeat with `_active_zone = Zone.PREVIEW`: the plain text then also ends with ` LIVE`, which proves the tag after the title still parses.
     - `self.assertIsNone(app.return_code)` holds after each test.
2. **Extend `tests/test_kill_confirm_dialog.py`.** Give `_KillDialogHost.__init__` optional `snap` / `task_info`, defaulting to the existing builders, so the current tests do not change. Add `test_user_fields_with_markup_render_literally`. It mounts the dialog with window `agent-\[bold]y`, title `Fix [/] ends with \` and command `cmd\`. The plain lines of `#kill-details` must **equal**:
   - `Window:   1:agent-\[bold]y (pane 0)`, with a `bold` span over `1:agent-\[bold]y`
   - `Task:     t995: Fix [/] ends with \`
   - `Process:  cmd\ (PID 4242)`

   A second case uses `agent-[/]x`, which crashes today.
3. **`monitor_shared.py`: add `markup_literal(value: str) -> str`.** It goes next to `format_session_divider` and returns `value.replace("[", "\\[")`. The docstring states:
   - the Textual-parser facts above
   - why `escape()` is wrong under Textual
   - the one constraint: a value that may end in `\` must not sit directly before a tag. Such a value either ends the markup, where open styles close at end of input, or goes through `Content.from_markup(template, **variables)`.
4. **`monitor_app.py`.** Import `markup_literal` from `monitor.monitor_shared` and `Content` from `textual.content`.
   - `_format_agent_card_text`:
     - `markup_literal(snap.pane.window_name)` in the frozen, parked and live rows (≈:1763, :1775, :1808). There the name is followed by ` (`.
     - The task row becomes `f"\n     [dim italic]t{task_id}: {markup_literal(info.title)}"` with **no** closing `[/]`. A comment says why and that it must stay the builder's last append.
   - `_format_other_card_text`: `markup_literal` on the window name, and the command as the final `[dim]{markup_literal(cmd)}` with no closing tag. A comment points to the same constraint.
   - `_update_content_preview`: build the header as a single `Content.from_markup(...)` template. Window index, name, task id and title become `$idx` / `$name` / `$tid` / `$title`, keeping today's bold / dim italic / zone variants and the `{tag}` suffix. Pass that template to `header.update(...)`. Gate and phase text stay as they are: they are framework-generated, and minimonitor leaves them unescaped too.
5. **`monitor_shared.py` `KillConfirmDialog.compose`.** `#kill-details` becomes `Static(Content.from_markup("\n".join(parts), window=…, title=…, cmd=…), id="kill-details")`:
   - `$window`, `$title` and `$cmd` replace the raw interpolations.
   - Index, pid, priority, status and `format_pane_status` stay as template text. They are numbers or framework vocabulary, and contain no `$`.
   - Import `Content` if it is not already imported.
6. Re-run steps 1–2 (green), then run the neighbouring suites (Verification).

## Verification

- Red proof, before steps 3–5:
  - `~/.aitask/venv/bin/python tests/test_monitor_markup_escape.py` fails: MarkupError, inequality, or the missing helper.
  - `~/.aitask/venv/bin/python tests/test_kill_confirm_dialog.py` fails in the new test only.
- Green: both files pass after the fix.
- No regressions. Ordinary names contain no `[`, so `markup_literal` is the identity and rows stay byte-identical. Run one by one:
  - `test_monitor_agent_marks.py`
  - `test_monitor_parked_filter.py`
  - `test_monitor_frozen_filter.py`
  - `test_monitor_completed_status.py`
  - `test_monitor_shadow_status.py`
  - `test_monitor_concern_action.py`
  - `test_shadow_phase_restamp.py`
  - `test_monitor_preview_offload.py`
  - `test_kill_confirm_dialog.py`
  - `test_minimonitor_row_budget.py`
  - `bash tests/test_multi_session_monitor.sh`
- Grep audit: `grep -n 'window_name}\|title}\|current_command}' .aitask-scripts/monitor/monitor_app.py .aitask-scripts/monitor/monitor_shared.py`. This is broader than `info.title}`, so it also catches `self._title}`-style dialog fields. After the fix, **no selected-surface line** may remain: none of the card builders, `pane_label` / the header, or `KillConfirmDialog`. Every remaining hit must fall into one of these classes:
  - **Deferred sink** (in the Context follow-up list): `monitor_app.py` :355, :2950 (→ :2951 toast) and :3816; `monitor_shared.py` :2244, :2285, :2812, :2814 and :2886.
  - **Not a sink:** `monitor_app.py` :3638 and :3767 are value assignments forwarded to the dialogs above, where the sink is the dialog. `monitor_shared.py:5216` renders the framework constant `_CONCERN_SECTIONS`.

  A hit outside both classes is an unclassified sink. Classify it before committing: fix it if it is on a selected surface, otherwise add it to the follow-up. The toasts that interpolate a local variable (`{name}`, `{agent_name}`) do not match the grep, so they are enumerated in the Context list instead.

## Step 9 (Post-Implementation)

Commit the code with `bug: … (t2006)`, naming only the four files, then archive through
the standard Step 9 flow. Create the single upstream follow-up at Step 8b.

## Risk

### Code-health risk: low
- There are two representations in one feature: a `str` helper for the cards, and `Content` templates for the header and dialog. The next editor could reach for `escape()` or the wrong one. · severity: low · → mitigation: none (in-plan: the `markup_literal` docstring names both and when each applies; the follow-up migrates the remaining `escape()` users onto them)
- The title and OTHER-command fields rely on ending their builder's string with the style left open. Appending after them later would move that style onto the new text. · severity: low · → mitigation: none (in-plan: comments at both sites, plus the exact-plain-text and span assertions in step 1, which fail if anything is appended or the span changes)

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Implemented as planned:
  - `markup_literal()` in `monitor_shared.py` prefixes each `[` with `\` and never doubles a backslash. It is applied to the window name in the live, parked, frozen and OTHER card rows of `monitor_app.py`, and to the task title and OTHER-row command. Those two end their row with the style left open, so a trailing backslash is safe.
  - The preview header (`_update_content_preview`) and `KillConfirmDialog`'s `#kill-details` are built with `Content.from_markup(template, **variables)`.
  - Tests:
    - new `tests/test_monitor_markup_escape.py` (8 tests: helper round-trip, a `rich.escape` negative control, the row-shape matrix, mounted cards and header)
    - a new hostile-field case in `tests/test_kill_confirm_dialog.py`
- **Deviations from plan:**
  - The kill dialog's `priority` and `status` also became `$variables`; the plan had kept them as template text. They are read raw from frontmatter, so as template text a `$`-bearing value would reach `string.Template` substitution. It is the same surface and costs nothing.
  - The test files reach the helper module-qualified (`ms.markup_literal`), so the red run errored only in the helper test.
- **Issues encountered:**
  - The first plan used `rich.markup.escape`. Review found, and probes confirmed, that under Textual's parser it doubles the backslashes before a bracket, and that a trailing backslash turns the next tag into text. Redesigned as above.
  - Red proof before the fix:
    - mounted cards and the kill dialog: MarkupError
    - `agent-[bold]y`: swallowed to `agent-y`
    - title `ends with \` rendered as `ends with [/]`
    - command `cmd\` rendered as `cmd[/]`
  - Green after the fix. Neighbouring suites all pass:
    - agent_marks, parked/frozen filter, completed/shadow status, concern_action, phase_restamp
    - preview_offload, finalize_offload, focus_switch, shadow_zone, frozen_capture
    - minimonitor_row_budget, frozenagent_app, test_multi_session_monitor.sh 47/47
- **Key decisions:**
  - The card builders keep returning markup `str`. About 8 test files pin their markup substrings and byte-identical-row invariants (t1133).
  - The header and the dialog are single sinks that nothing else reads, so they use `Content` templates.
  - Textual facts the design rests on:
    - A `[` preceded by a backslash never opens a tag.
    - Text un-escapes exactly `\[`.
    - A style still open at end of input closes there.
    - `$variables` are substituted after tokenizing.
- **Upstream defects identified:** These are the deferred markup sinks outside this task's selected surfaces. Line numbers are as of this commit.
  - `.aitask-scripts/monitor/monitor_app.py:2977` — `Switched to {name}` toast. This is one of several window-name toasts in this file (also `No log file found for` / `Opening log for {agent_name}`, `Killed` / `Failed to kill {name}`, `Killed {old_name}` and `Killed {old_window_name}` at :3842). None of them crash; a `[dim]`-style name is swallowed.
  - `.aitask-scripts/monitor/monitor_app.py:356` — `RestartConfirmDialog` "Current:" row interpolates the task title raw into a Static. `[/]` raises MarkupError.
  - `.aitask-scripts/monitor/monitor_shared.py:2272` — `TaskDetailDialog` title Static interpolates `info.title` raw. The header `update` at :2313 does the same.
  - `.aitask-scripts/monitor/monitor_shared.py:2855` — `NextSiblingDialog` current and suggested rows (:2855, :2857) interpolate task titles raw.
  - `.aitask-scripts/monitor/monitor_shared.py:2929` — `_SiblingRow.render` interpolates the sibling title raw.
  - `.aitask-scripts/monitor/monitor_app.py:1728` — the status bar interpolates session names raw (`session: …` / `(attached: …)`), as does the `Session renamed to` toast at :800.
  - `.aitask-scripts/monitor/monitor_shared.py:361` — `format_session_divider` uses `rich.markup.escape`, which is wrong under Textual: it doubles the backslashes before a bracket. The same applies to `monitor_shared.py:1158`, `monitor_app.py:3577`, and minimonitor `_row_name` / title / `_own_header_text` and its toasts.
