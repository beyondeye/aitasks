---
Task: t2017_render_remaining_user_text_literally_in_monitor_markup.md
Base branch: main
Output branch: main
---

### Pre-phase (risk mitigations)
1. [characterize_own_panel] Before touching `_own_agent_identity_text` /
   `_own_card_text`, write a characterization test in the new test module
   (`OwnPanelCharacterizationTests`). It mounts the own card's `Static` through
   a minimal `App.run_test` host fed by `_own_card_text(...)` on a
   `__new__`-built `MiniMonitorApp` with a fake task cache. It records the
   rendered `.plain` and the `(start, end, style)` spans for five benign cases:
   (a) name only, no mark; (b) mark `KIND_NONE` + name; (c) name + title that
   wraps to two lines at `_target_width = 40`; (d) (c) + phase `"planning"`;
   (e) frozen with stamp. Hard-code the expected values captured from the
   **pre-change** code into the test, and run it green before the change.
   After the switch to Content, it must pass unchanged: no expected value may
   be edited.

## Context

t2006 (`337d0f6e0`) made window names, task titles and pane commands render
literally in three `ait monitor` surfaces (agent/other card rows, preview
header, `KillConfirmDialog`) and introduced two primitives:

- `markup_literal()` (`monitor_shared.py:364`) — prefix every `[` with `\`,
  never double a backslash. Exact round trip under Textual's parser **as long
  as the value is not directly followed by a tag** (a trailing `\` turns the
  next `[` into text — no string escaping can express it).
- `Content.from_markup(template, **variables)` — `$name` values are
  substituted after tokenizing, so they are always literal, even right before
  a tag.

Every other monitor/minimonitor sink that interpolates tmux window names,
session names, task titles/frontmatter, or pane commands is still raw or uses
`rich.markup.escape`, which is wrong under Textual (probed on Textual 8.2.7):

| input | `escape()` under Textual | raw |
|---|---|---|
| `agent-\[bold]y` | `agent-\\[bold]y` (doubled `\`) | `[bold]` eaten |
| `x\` | `x\\` (doubled) | ok |
| `a [ b` + later tag | **swallows the following tag** | same |
| `[/]` | ok | **MarkupError** (crash for Statics) |

Scope (user-confirmed): every sink carrying window names, session names, task
titles/frontmatter fields, or pane commands, in `monitor_app.py`,
`monitor_shared.py`, `minimonitor_app.py`. The other `escape()` users (concern
text `_escape_markup`, concern entry meta, block meta, stale detail,
column-picker titles, draft paths) are out of scope → recorded as an upstream
defect in Final Implementation Notes for a follow-up.

## Rules applied per sink (one rule, chosen by what follows the value)

1. **Toast with no intended styling** → `notify(..., markup=False)` (precedent:
   `minimonitor_app.py` "Moved t… → {title}" toasts already do this).
2. **Value followed by plain text / spaces / newline, or ending the markup** →
   `markup_literal(value)` (leave the trailing style open when the value ends
   the markup — t2006's pattern; Textual closes it at EOF).
3. **Value directly before a tag in a widget built once** (dialog Statics,
   Labels) → `Content.from_markup(template, **variables)`, with **every**
   user field a `$variable` — never mix an f-string-interpolated user value
   into a variables template (`safe_substitute` would expand a `$name` inside
   it, and `$$` would collapse).
4. **Static text with no markup at all** → `Content(text)` (plain, cannot be
   parsed).

## Implementation steps

### monitor_shared.py
- `format_session_divider` (:361): `escape(label)` → `markup_literal(label)`
  (label is followed by ` ──`). Update docstring (t1580 note → Textual reason).
- `AgentMarksMixin` toasts "Prioritized / Parked … hidden / Parked / Unmarked
  {window}" (:870-884) and "Mark failed: {first}" (:889 — a corrupt-store
  error that quotes stored window names): add `markup=False`.
- `_poll_frozen_outcome` restore/drop verdict toast (:1078): add
  `markup=False`. The note is plain text in every branch, but
  `agent_sessions.restore_verdict` copies the record's `last_error` reason
  into it. For a survivor refusal that is
  `restore_survivor:<session>:<window>|pane:<id>`
  (`agent_frozen_ops.survivor_detail`, persisted by `agent_restore`).
  Probed: a window named `agent-[dim]oops` displays as `agent-oops`. This is
  the same indirect-user-text class as the "Launch failed: {err}" toasts.
- Freeze-one body (:1158): build with
  `Content.from_markup("[bold]$window[/]\n\nThe agent process ends. …", window=window)`.
- `FreezeConfirmDialog.__init__`: `body: str | Content` (Static accepts both);
  docstring line on why callers pass Content for user text. Header
  `escape(self._title)` untouched (framework text).
- `TaskDetailDialog._detail_widgets` header (:2272):
  `Content.from_markup("[bold]t$task_id: $title[/]", task_id=…, title=…)`;
  meta line (:2276, frontmatter only, no markup) → `Content(f"Priority: …")`.
- `TaskDetailDialog.action_toggle_plan` header (:2313):
  `Content.from_markup("[bold]t$task_id: $title[/] $label", …, label=f"[{label}]")`
  — also fixes a pre-existing bug: the literal `[Plan]` / `[Task]` indicator
  is read as an unknown tag today and never renders (probed: plain is `t42: x `).
- `TaskPickConfirmDialog`: `#pick-eligibility`, `#pick-running`,
  `#pick-kill-detail` (compose + `on_checkbox_changed`) carry status /
  window names and no markup → wrap in `Content(...)` at the Static boundary
  (`_kill_detail_text` / `_eligibility_lines` keep returning `str`).
- `NextSiblingDialog.compose` (:2855-2857): `Content.from_markup` over the
  joined lines with `$cur_id/$cur_title/$cur_status/$sug_id/$sug_title`;
  `_followup_prefix(...)` (framework markup, no `$`) stays in the template.
- `_SiblingRow.render` (:2929): `markup_literal(self._title)` (followed by
  `  [bold red]…` — two spaces — or EOF); stays `str` (tests use `in`/`index`).

### monitor_app.py
- `SessionRenameDialog` Label (:290-294): `Content.from_markup` with
  `$current` / `$expected`.
- `RestartConfirmDialog.compose` (:356-366): `Content.from_markup` over the
  lines with `$task_id/$title/$status` (status also appears inside
  `[yellow]…'$status'…[/]`), mirroring `KillConfirmDialog`.
- Toasts → `markup=False`: session mismatch (:778), "Session renamed" (:800),
  "Switched to" (:2977), "No log file found" / "Opening log" (:3546/:3556),
  "Killed" / "Failed to kill" (:3640/:3643), "Killed {old_name}" (:3745),
  "Killed {old_window_name}" (:3842), "Launch failed: {err}" (:3751, :3845 —
  tmux stderr names the session).
- `_rebuild_session_bar` (:1715, :1728): `markup_literal(attached)` /
  `markup_literal(self._session)` (followed by `)` / ` (`).
- Drop-frozen body (:3577): `Content.from_markup("[bold]$window[/]\n\n…", window=window)`.
- Remove the now-unused `from rich.markup import escape` import.

### minimonitor_app.py
(another session — t2009 — has uncommitted hunks in this file around the
review-loop hold code, ~4220-4890; none of mine overlap them. See "Commit".)
- `_own_header_text` (:320): `escape(_clip(...))` → `markup_literal(_clip(...))`
  (followed by ` ──`); docstring wording.
- Session bar (:2373): `markup_literal(self._session)` (followed by `  `).
- `_row_name` (:2504): `markup_literal(_clip(...))` — every caller puts `"  "`
  after the name. Docstring.
- List title row (:2467): `f"\n  [dim]{markup_literal(title)}"` with the
  `[dim]` **left open** — a clipped title can end in `\`. The only row that can
  follow it is the gate/phase row, itself `[dim]…[/]` in full, so the open span
  adds nothing it renders; comment states this invariant. Per-line splitting in
  existing tests (`split("\n")[2]` parsed alone) keeps working.
- `_other_card_text` (:2536-2539): `markup_literal` both; the command ends the
  row, so `[dim]` is left open (t2006's monitor pattern).
- `_own_agent_identity_text` (:2541-2592) — name parts `[bold]{part}[/]` and
  title lines `[dim]{wline}[/]` are **raw** today, each directly before a tag,
  and the result is composed further by `_own_card_text`. Return a `Content`
  built by `Content.from_markup(template, **vars)` (`$n0`, `$n1`, `$t0`, `$t1`).
  `_own_card_text` returns `Content`: framework parts via
  `Content.from_markup(...)`, identity concatenated as Content (never
  re-parsed); the frozen stamp is a `$stamp` variable. `_own_identity_text`
  annotation → `Content | str` (`""` floor at :1308 stays valid: `Content + ""`
  and `"" + Content` both work). Both widget sinks (`Static(...)` at :2793,
  `.update(...)` at :2704) already accept Content.
- Drop-frozen body (:3108): Content template, as in monitor_app.
- Toasts → `markup=False`: "Killed" / "Failed to kill" (:3134/:3137),
  "Launch failed: {err}" (:3270), "Auto-recheck loop disarmed: {message}"
  (:4219 — `loop_reason_message` embeds the shadow command; plain text),
  auto-recheck unavailable (:4375, :4417 — pane command), "Switched to"
  (:5269).
- Imports: add `from textual.content import Content` and `markup_literal` to
  the `monitor_shared` import block; remove the now-unused `escape` import.

### Out of scope → Final Implementation Notes "Upstream defects identified"
- `lib/tui_switcher.py:387` (window name raw), `:816-841` (session labels raw
  before `[/]` — a session named `[/]` raises MarkupError in every TUI's
  switcher), `:1388` ("Failed to switch to {name}" toast).
- `monitor_shared.py` `escape()` users for concern text / meta / block meta /
  stale detail / column titles / draft paths (`_escape_markup` :3647, :4892,
  :5196, :5224, :3119, :3269, :1573) — same doubled-backslash / lone-`[`
  defect under Textual.
- `minimonitor_app.py:3330` "Not a task number: {raw!r}" — typed input raw in
  a toast.

### Docstring
- `markup_literal` docstring: add the fourth option (a toast with no styling →
  `markup=False`) and point at this task's rule set; no other shared-helper
  changes.

## Tests

### Update (type changes only)
- `tests/test_monitor_frozen_filter.py:1383,1398,1413` —
  `Text.from_markup(app._own_card_text(...)).plain` → `app._own_card_text(...).plain`.
- `tests/test_monitor_shadow_status.py:508-510` — assert on `panel.plain`.
- `tests/test_multi_session_minimonitor.sh:395-399` — `text.plain`.

### New: `tests/test_monitor_markup_literal_sinks.py`
Hostile corpus (mirrors `test_monitor_markup_escape.py`): `agent-[/]x`,
`agent-[bold]y`, `agent-\[bold]y`, `agent-x\`, `a [ b`, plus titles
`Fix [/] and [dim]x[/dim]`, `a \[bold] b`, `ends with \`. Every check parses
with Textual (`Content.from_markup` / mounted `render()`), never Rich, and
compares exact plain text (and the covering style where a field ends its row).

**Fixture construction: the repo-wide Rule C scanner must find nothing here.**
`tests/test_textual_markup_colours.py::MarkupStructureScanTests` parses every
string constant and f-string under `tests/` with Textual whenever it holds a
named close (`[/dim]`) plus a candidate open tag. A hostile literal like
`Fix [/] and [dim]x[/dim]` is a finding; it is the one at
`test_monitor_markup_escape.py:69` that fails the suite today, owned by
t2021. So in this module:
- no single string constant or f-string may carry a named close tag. Build
  the corpus at runtime from tag fragments:
  `OPEN, CLOSE = "[", "]"`, `def tag(body): return OPEN + body + CLOSE`.
  For example, the hostile title is
  `"Fix " + tag("/") + " and " + tag("dim") + "x" + tag("/dim")`, and
  every expected-markup assertion is written the same way;
- `ScannerSelfCheckTests.test_this_module_adds_no_structure_findings`
  imports the scanner's `scan_source_structure` (adding `tests/` to
  `sys.path`) and asserts `[]` for this file's own source. The pre-existing
  t2021 finding therefore cannot mask a new one here. Its negative control
  runs the same function over an inline source string, itself assembled
  from fragments, that contains a hostile literal, and asserts exactly one
  finding, so the self-check cannot pass vacuously.

- **Pure builders** (`__new__`-built apps): `format_session_divider`,
  `_own_header_text`, minimonitor `_agent_card_text` (live/parked/frozen name
  row; title row exact + dim-covered; with a gated phase row: the phase row's
  plain and spans identical for a hostile vs a benign title — pins the
  open-span invariant), `_other_card_text`, `_own_agent_identity_text` /
  `_own_card_text` (bold name, dim title, phase row not bold), monitor
  `_rebuild_session_bar` single + multi (via a fake `SessionBar` capture),
  minimonitor session bar, `_SiblingRow.render`.
- **Dialogs, mounted** (`App.run_test` host pushing the screen, reading
  `query_one(...).render().plain`): `RestartConfirmDialog`,
  `SessionRenameDialog`, `NextSiblingDialog`, `TaskDetailDialog` (header,
  meta, and after `p` toggle shows `[Plan]` literally — the pre-existing-bug
  pin), `TaskPickConfirmDialog` running / kill-detail / eligibility lines,
  `FreezeConfirmDialog` bodies built by both apps' freeze/drop callers
  (capture `push_screen`, mount the captured dialog).
- **Toasts**: each in-scope `notify` call site invoked with a hostile name
  through a spy `notify` that records `(message, markup)`; assert the exact
  message and `markup is False`. A table-driven test listing every site, so a
  new raw toast is a one-line addition.
- **Restore-failure toast** (the indirect path): patch
  `agent_sessions.SessionsView` to serve a record that is `frozen`, has
  `restore_attempts` above the snapshot, and has
  `last_error = "n1:" + survivor_detail({"session": "s1", "window": hostile,
  "pane_id": "%3"})`, built with the real `agent_frozen_ops.survivor_detail`.
  Capture `set_interval`'s callback, fire one tick, and assert the spy toast
  message contains `hostile` verbatim with `markup is False`. A second case
  covers the drop verdict.
- **Mounted toast anchor**: one `run_test` app sends a hostile-name toast
  through a real call site (`action_switch_to` with a fake monitor) and
  asserts the mounted `Toast`'s rendered plain text equals the message. This
  proves Textual honours `markup=False` end to end, so the spy table is not
  the only evidence.
- **Negative controls**: (a) `escape()` still fails the `a [ b`+tag and
  `x\` round trips under Textual (reason the migration exists); (b) a
  variables template with a user value that contains `$title` stays literal.

### Run
```bash
python3 tests/test_monitor_markup_literal_sinks.py
python3 tests/test_textual_markup_colours.py   # explicit: its ONLY structure
    # finding must remain test_monitor_markup_escape.py:69 (t2021's); none may
    # name test_monitor_markup_literal_sinks.py
python3 tests/test_monitor_markup_escape.py
python3 tests/test_kill_confirm_dialog.py
bash tests/run_all_python_tests.sh --test-dir tests   # full suite; read the last line
bash tests/test_multi_session_minimonitor.sh
bash tests/test_multi_session_monitor.sh
```
Plus each directly affected module: `test_monitor_session_divider.py`,
`test_minimonitor_own_header_session.py`, `test_minimonitor_row_budget.py`,
`test_minimonitor_gate_phase_row.py`, `test_minimonitor_other_section.py`,
`test_monitor_frozen_filter.py`, `test_monitor_shadow_status.py`,
`test_minimonitor_own_mark.py`, `test_minimonitor_own_task_info.py`,
`test_minimonitor_pick_by_number.py`, `test_monitor_sibling_row_render.py`,
`test_textual_markup_structure.py`, `test_markup_colour_contract.py`.

## Commit (shared worktree)
`minimonitor_app.py` (and `tests/test_minimonitor_concern_action.py`) carry
t2009's uncommitted hunks; my :4219 edit is adjacent to its `_loop_hold` hunk.
At commit time:
- If t2009 has committed by then, a plain path-scoped
  `git commit -F - -- <my files>` suffices.
- Otherwise whitelist, never blacklist: rebuild the `minimonitor_app.py` blob
  as `git show HEAD:<path>` + my edits replayed by a scratch script (each edit
  is an exact old→new replacement, asserted to match once), stage it via a
  temp `GIT_INDEX_FILE` (`hash-object -w` + `update-index --cacheinfo`) along
  with my other files, commit from that index, and confirm the committed
  blob contains none of t2009's hunks (`git diff <sha> -- <path>` in the
  worktree shows exactly t2009's hunks). The worktree file keeps both
  sessions' hunks. Never stash, never restore. Then the isolated verification
  in the post-phase mitigation below.

## Step 9
Post-implementation per task-workflow Step 9 (current branch, no worktree):
archive t2017 and its plan.

### Post-phase (risk mitigations)
1. [isolated_commit_verification] After the code commit, check out the commit
   with `git worktree add --detach <scratch>/wt-new <sha>` and the parent with
   `git worktree add --detach <scratch>/wt-old <sha>^`. Link task data with
   `./.aitask-scripts/aitask_init_data.sh --link-worktree`. In both, run the
   new test module and every directly affected module listed under Tests
   (plus `tests/test_multi_session_minimonitor.sh`). Attribute only the delta:
   every module must pass in `wt-new`, and any failure must also fail
   identically in `wt-old`. Then check the commit's OWN diff against its
   parent for foreign changes, never the whole blob (t2009 landed as
   `a8f308a4b`, so its identifiers are legitimately in the baseline):
   - `git diff --name-only <sha>^ <sha>` lists exactly the seven t2017
     paths (the three monitor modules, the new test module, and the three
     updated tests);
   - for each tracked path, the commit's diff
     `git -c diff.mnemonicPrefix=false diff --no-color --no-ext-diff <sha>^ <sha> -- <path>`
     is byte-identical (`cmp`) to the snapshot taken with the same flags,
     `git -c diff.mnemonicPrefix=false diff --no-color --no-ext-diff HEAD -- <path>`,
     and saved to the scratchpad immediately before the commit. The flags
     must be identical on both commands: the user's global config sets
     `diff.mnemonicPrefix=true`, which writes `c/`/`w/` headers for a
     worktree diff but `a/`/`b/` for a commit-to-commit one, so a correct
     commit would compare unequal (reproduced in a temporary repo; with
     `false` on both commands the comparison holds). For the new, untracked
     test module, which `git diff HEAD` cannot show, `git show <sha>:<path>`
     must be identical to a copy of the file saved at the same moment.
     Identity in both directions proves no foreign hunk rode along and none
     of mine was dropped.
   Then remove both worktrees with `git worktree remove`.

## Risk

### Code-health risk: low
- `minimonitor_app.py` carries t2009's uncommitted hunks, and my :4219 toast edit sits next to one of them; a selectively staged commit could leak one of t2009's hunks or drop one of mine. The working tree cannot show this, because it holds both halves · severity: low (residual — addressed by inline post-phase isolated_commit_verification) · → mitigation: inline post-phase isolated_commit_verification
- The own panel's identity/card change from `str` to `Content`. Any caller that concatenates markup `str` onto it would get that markup as literal text, because `Content + str` is plain. Grep found only the two widget sinks plus three tests, but a silent restyle of the phase/frozen row is the failure mode · severity: low (residual — addressed by inline pre-phase characterize_own_panel) · → mitigation: inline pre-phase characterize_own_panel
- The minimonitor title row leaves `[dim]` open. Any future non-dim row appended after it would be dimmed. Pinned by a hostile-vs-benign span-equality test · severity: low · → mitigation: none (pinned by the new test)

### Goal-achievement risk: low
- A missed sink. Mitigated by the exhaustive sweep (agent + greps) and the table-driven toast test; `lib/tui_switcher.py` is deliberately out of scope (user-confirmed) and recorded for follow-up · severity: low · → mitigation: none
- Hostile fixtures in the new test module could add a Rule C finding to `tests/test_textual_markup_colours.py`, hidden behind the pre-existing t2021 finding that already fails it. Mitigated by building fixtures from tag fragments at runtime and by the module's own `scan_source_structure` self-check (with a negative control) · severity: low · → mitigation: none (built into the test design)
- Indirect user text: persisted error fields such as `last_error` can carry window or session names into toasts. Covered by the restore/drop verdict toast and the launch-error toasts; the notify sweep found no other such path in the three files · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_own_panel | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: own panel str→Content restyle | desc: pin the docked panel's rendered plain+spans for benign inputs before the Content switch
- timing: post-phase | name: isolated_commit_verification | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: selective-staging leak next to t2009's hunks | desc: run affected suites in detached worktrees of the commit and its parent; attribute only the delta

## Post-Review Changes

### Change Request 1 (2026-10-16 00:45)
- **Requested by user:** The post-phase `isolated_commit_verification` required the committed `minimonitor_app.py` to contain none of t2009's identifiers. t2009 has since landed (`a8f308a4b`; `git show HEAD` contains both `live: bool = True` and `if ctrl.confirm_fire(token`), so that whole-blob check would flag a correct commit. Check the commit's diff against its parent instead.
- **Changes made:** Replaced the identifier check with a parent-diff check. The commit must touch exactly the seven t2017 paths, and each path's `<sha>^..<sha>` diff must be byte-identical to the pre-commit `git diff HEAD` snapshot. t2009 being committed also means the Commit section's first branch applies: a plain path-scoped `git commit -F - -- <paths>`, with no temp index.
- **Files affected:** `aiplans/p2017_render_remaining_user_text_literally_in_monitor_markup.md` (plan only).

### Change Request 2 (2026-10-16 00:55)
- **Requested by user:** The amended check compared `git diff HEAD -- <path>` with `git diff <sha>^ <sha> -- <path>` byte for byte. Under this repo's `diff.mnemonicPrefix=true`, the first writes `c/`/`w/` headers and the second `a/`/`b/`, so a correct commit would fail.
- **Changes made:** Verified the setting (`~/.config/git/config: diff.mnemonicprefix true`) and reproduced the mismatch in a scratch repo: `DEFAULT_DIFFER` with defaults, `FIXED_SAME` with `-c diff.mnemonicPrefix=false` on both commands. Both commands now run as `git -c diff.mnemonicPrefix=false diff --no-color --no-ext-diff`.
- **Files affected:** `aiplans/p2017_render_remaining_user_text_literally_in_monitor_markup.md` (plan only).

## Final Implementation Notes
- **Actual work done:** Every sink in `monitor_app.py`, `monitor_shared.py` and `minimonitor_app.py` that carries a tmux window name, session name, task title or frontmatter field, or pane command now renders it literally. The four rules were applied by what follows each value:
  - Toasts with no styling get `notify(..., markup=False)`. That is 23 sites, including indirect ones: the restore/drop verdict toast (quotes `last_error`), mark-failed, launch-failed, and the auto-recheck disarm (shadow command).
  - Dialog Statics and Labels use `Content.from_markup(template, **variables)`: Restart, SessionRename, NextSibling, the TaskDetail header and toggle, and the freeze and drop bodies.
  - Text with no markup is wrapped as `Content(text)`: the TaskDetail meta line and the TaskPickConfirm eligibility, running and kill-detail lines.
  - Values followed by text use `markup_literal`: the session divider, both session bars, the own header, the minimonitor name, title and other rows, and `_SiblingRow`.
  - `rich.markup.escape` is no longer imported by `monitor_app.py` or `minimonitor_app.py`.
  - The minimonitor docked panel (`_own_agent_identity_text` / `_own_card_text`) now builds `Content` rather than markup `str`. The pre-phase characterization test, captured from the old code and never edited, proves benign input renders identically, cell for cell and span for span.
- **Deviations from plan:**
  - The minimonitor title row's open `[dim]` also covers the following phase row's two-space indent. That is invisible, because a style on a blank cell draws nothing. The guard test therefore compares the phase row's visible cells, not every cell.
  - The mounted toast anchor needed `run_test(notifications=True)`, because Textual disables toasts under `run_test` by default.
  - t2009 landed (`a8f308a4b`) before the commit, so the plain path-scoped commit applied and the temp-index fallback was not needed.
- **Issues encountered:**
  - Plan review found two gaps: the restore verdict toast (an indirect path for user text) and hostile fixtures colliding with the repo-wide Rule C scanner. Both were added before implementation.
  - Post-implementation review found that the post-phase verification check was wrong twice: first it forbade identifiers that were legitimately committed, then it compared diffs whose headers differ under `diff.mnemonicPrefix`. See Post-Review Changes.
- **Key decisions:**
  - Fixtures are assembled from `tag()` fragments, so no literal holds a named closing tag. `ScannerSelfCheckTests` scans this module itself, with a negative control. t2021 later settled a compatible convention (split literals with `+`; `d9723ab55`).
  - The list builders that tests split by line keep returning `str`. Only the docked panel, whose rows each sit before a closing tag, moved to `Content`.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/tui_switcher.py:816-841` — session labels are interpolated raw before `[/]` / ` (stale)[/]`, so a session named `[/]` raises MarkupError in every TUI's switcher. The same file also inserts a window name raw at `:387` and in the "Failed to switch to {name}" toast at `:1388`.
  - `.aitask-scripts/monitor/monitor_shared.py:3686` — `_escape_markup` and the other remaining `escape()` users (concern entry meta `:4955`, block meta `:5259`, stale detail `:5287`/`:5295`, column picker `:3182`, column move `:3333`, draft paths `:1596`) are built on `rich.markup.escape`. That is wrong under Textual: it doubles a backslash before a bracket and a trailing backslash. (Line numbers as of the t2017 commit.)
  - `.aitask-scripts/monitor/minimonitor_app.py:3377` — the "Not a task number: {raw!r}" toast puts typed input into a markup-parsed toast raw.
