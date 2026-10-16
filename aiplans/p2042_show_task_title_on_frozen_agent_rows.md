---
Task: t2042_show_task_title_on_frozen_agent_rows.md
Base branch: main
Output branch: main
---

# t2042 — Show the task title on frozen agent rows

## Context

Frozen agents in `ait minimonitor` and `ait monitor` lost the task-title line
that live agents show under their name row. Both renderers return early on
`snap.frozen` before the title is appended. The early return exists because a
frozen pane was never captured, so nothing capture-derived may appear on it
(t1685, t1705_7). The title is **not** capture-derived. The task id comes from
the window name (`TaskInfoCache.get_task_id_for_pane` →
`task_id_from_window_name`), and the title comes from the task file
(`get_task_info`). `i` (Task Info) already resolves through that same path,
which is why `i` still works on frozen rows. Stand-in windows keep their
`agent-pick-<N>` names, so the id still resolves.

**Coordination:** `minimonitor_app.py` and `monitor_app.py` carry uncommitted
t2039 edits (comments only, ~L3140 / ~L3588). They do not overlap the frozen
branches (~L2414 / ~L1772). The commit waits until t2039's hunks have landed
(see step 6), so this task never commits from a file another task also has
dirty.

## Decision: title only, no gate summary on frozen rows

The gate summary is ledger-derived, so it would be allowed. It is still left
off, for three reasons:
- In the minimonitor the gate summary shares a row with the phase (t1479). With
  the phase removed (capture-derived, it reads `snap.content` /
  `awaiting_input`), the summary would need a whole extra row per frozen agent,
  and this pane's scarce resource is rows.
- A frozen agent is not advancing its task, so the counts on its row do not
  change. `i` still shows the full task, gates included.
- Leaving it off keeps the two apps symmetric. A frozen row says what is true:
  the mark, `F`, the name, `frozen`, and which task the agent belonged to.

## Steps

### 1. `.aitask-scripts/monitor/minimonitor_app.py`

- Add a method `_title_row(self, info) -> str` that returns
  `f"\n  [dim]{markup_literal(title)}"`, with `title = _clip(info.title,
  min(_TITLE_MAX_CELLS, _detail_budget(self._target_width)))`. Move the existing
  t2017 "no closing tag" comment onto it. The comment already notes that a
  following row must not assume it starts unstyled, and the gate row
  (`[dim]…[/]`) is the only thing that can follow.
- Live path (~L2466-2480): replace the inline title construction with
  `line1 += self._title_row(info)`. The output must stay identical.
- Frozen branch (~L2414-2422): build `text = f"{prefix}{name}  [dim]frozen[/]"`,
  then resolve `task_id = self._task_cache.get_task_id_for_pane(snap.pane)`,
  then `info = get_task_info(task_id, snap.pane.session_name)` when an id is
  present. If `info`, append `self._title_row(info)`. Return `text`. Do **not**
  call `_phase_for_snap` / `_gate_cache`.
- Update the frozen-branch comment: the title is allowed because it comes from
  the window name plus the task file and is not capture-derived (the same
  lookup `i` uses). The phase is capture-derived and stays off. The gate
  summary stays off for the reasons recorded above.
- Row-budget block (~L179-182): annotate that the `title` shape follows live
  **and frozen** rows, and that `gates` follows live rows only.

### 2. `.aitask-scripts/monitor/monitor_app.py`

- Add a method `_title_row(self, task_id, info) -> str` that returns
  `f"\n     [dim italic]t{task_id}: {markup_literal(info.title)}"`. Move the
  t2006 "no closing tag, must stay the LAST thing appended" comment onto it.
- Live path (~L1877-1879): `text += self._title_row(task_id, info)`. Output
  unchanged.
- Frozen branch (~L1772-1781): build the existing row into `text`, resolve
  task_id/info the same way, and append the title row when `info` exists. No
  gates, no phase, no shadow stamp.
- Update the frozen-branch comment the same way as in step 1. The parked-branch
  comment stays as it is (parked rows are out of scope).

### 3. Tests: `tests/test_monitor_frozen_filter.py` (`FrozenRowRenderTests`)

Add the fakes `_TitledTaskCache(title)` (resolves `"2042"` →
`TaskInfo(task_id="2042", …, title=title, …)`) and `_RecordingGateCache`.
`_RecordingGateCache.summary_for` returns `"1/1 pass"`, and `phase_for` records
the call and returns `PhaseSignal(phase="IMPLEMENT")`. Minimonitor needs
`_gate_cache` set on the app, and both apps need `_gate_cache` for the live
control. New cases, each over `BOTH_APPS`:

- `test_frozen_row_shows_the_task_title`: the title appears on the frozen row.
  Every existing forbidden glyph/word (`●`, `◆`, `≈`, `=`, `IDLE`, `PROMPT`,
  `Active`) is still absent. `IMPLEMENT` (the phase) and `1/1` (the gates) are
  absent, and `phase_for` was **never called**.
- `test_live_row_with_the_same_fixture_shows_phase_and_gates`: a positive
  control. The same caches on a live snapshot render the title, `IMPLEMENT` and
  `1/1`, so the frozen-row absence above discriminates on `frozen`, not on the
  fixture.
- `test_frozen_row_without_a_task_stays_one_line`: the existing `_FakeTaskCache`
  (`None`) gives a single-line row. This pins the no-task case.

These rows are parsed with **Textual** (`textual.content.Content.from_markup`),
not this file's Rich-based `row()` helper. A new `textual_row()` helper sits
beside `row()`, and the existing tests keep `row()` unchanged.

Also update the module docstring's `FrozenRowRenderTests` paragraph: the title
is allowed because it is not capture-derived, and the phase and gates stay off.

### 3b. Hostile titles on frozen rows, Textual-parsed (review finding)

Rich and Textual escape differently. `test_monitor_markup_literal_sinks.py`'s
docstring says a Rich-based assertion cannot see the defect. So the
hostile-title cases go into the two suites that already parse card rows with
Textual and already own scanner-safe hostile fixtures (`TITLES`, assembled with
`tag()`, so `test_textual_markup_colours.py` Rule C does not flag a literal):

- `tests/test_monitor_markup_literal_sinks.py` `MiniListRowTests`: add
  `test_frozen_title_row_is_exact_and_dim`. For every `TITLES` entry, render
  `mini_app(title)._agent_card_text(snapshot("agent-a", frozen=True))` and
  `parse()` it (`Content.from_markup`). Assert three things. Line 0 ends with
  `"agent-a  frozen"`, so the `[dim]frozen[/]` tag still parsed. The card has
  exactly 2 lines. `lines[1] == f"  {_clip(title)}"`, the title after the
  intended clipping: `mm._clip(title, min(mm._TITLE_MAX_CELLS,
  mm._detail_budget(40)))`. Every `TITLES` entry is below 30 cells, so this is
  the full title, and the expression keeps the assertion honest if a fixture
  grows. Also assert `"dim"` covers the title span via `covering()`.
- `tests/test_monitor_markup_escape.py` `RowShapeTests`: add
  `test_frozen_task_title_row_is_exact_and_fully_styled`, mirroring
  `test_task_title_row_is_exact_and_fully_styled` with a frozen snapshot.
  `lines[0]` ends with `"(0)  frozen"`, `len(lines) == 2`,
  `lines[1] == f"     t42: {title}"` (the full monitor does not clip), and
  `"dim italic"` covers from `t42: ` to the end.
- Neither file's existing frozen-row tests change. They build their apps with
  no task (`title=None`), so the row stays one line, and their `endswith(kind)`
  assertions still hold.

### 4. `tests/test_minimonitor_row_budget.py`

- In `test_parked_and_frozen_rows_fit`, nothing changes (`_row_app` has no task,
  so the check stays on line 1).
- Add `test_frozen_title_fits_the_detail_budget`: frozen snap, `"漢" * 40`
  title. Row 2 is ≤ `2 + _detail_budget(40)` and ends with `…`. The card has
  exactly 2 lines (no gate row).

### 5. Docked panel

`_own_agent_identity_text` is not touched. It already renders the title
regardless of frozen state. Verify with `git diff` that its body is unchanged.

### 6. Commit hygiene (Step 8): a handoff to t2039, then a plain path-scoped commit

The commit uses no hunk-selective staging, no private index and no hand-written
index updates. Every check-then-write on the shared index races a concurrent
session, and git already serializes the one operation needed:
`git commit -o -- <paths>` builds the commit **and** updates those paths' index
entries while holding its own `index.lock`. That is correct exactly when
`git diff HEAD -- <paths>` is entirely this task's, so the commit is gated on
that precondition:

1. **Edit set** (from my own Edit history, never from `git diff --name-only`):
   the two app files plus the four test files from steps 3, 3b and 4.
2. **Handoff gate.** Right before committing, check
   `git diff HEAD -- <edit set>` for any hunk that is not mine. Today that means
   t2039's ~L3140 / ~L3588 comment hunks.
   - **None** (t2039 has already landed): go to 3.
   - **Still present:** do not commit around them. Tell the t2039 session (via
     `ListAgents` / `SendMessage` if it is reachable) that t2042 is waiting on
     its comment hunks in `minimonitor_app.py` / `monitor_app.py`, then wait
     for its commit. Watch for it with `Monitor` until the foreign hunks are
     gone from `git diff HEAD`, with a long timeout. If it does not land within
     a reasonable time, stop and ask the user. Possible answers are to keep
     waiting, or to leave t2042 committed-pending (reviewed but not committed,
     to be committed on a later pick). Never strip, stash or restore t2039's
     lines.
3. **Commit:**
   ```bash
   git commit -o -F - -- <edit set> <<'EOF'
   bug: Show the task title on frozen agent rows in monitor and minimonitor (t2042)

   <code-agent trailer>
   EOF
   ```
   Then `git show --stat <sha>` must list exactly the six files, and
   `git status --porcelain -- <edit set>` must be empty.

The plan file is committed separately via `aitask_task_commit.sh` (named path),
as Step 8 specifies.

## Verification

- `python3 tests/test_monitor_frozen_filter.py`
- `python3 tests/test_minimonitor_row_budget.py`
- `python3 tests/test_monitor_markup_literal_sinks.py` and
  `python3 tests/test_monitor_markup_escape.py`. Both include their own
  scanner self-checks, which must stay green.
- `python3 tests/test_textual_markup_colours.py` (the Rule C scan over
  `tests/`)
- Other modules that call the card builders:
  `test_monitor_parked_filter.py`, `test_monitor_completed_status.py`,
  `test_monitor_shadow_status.py`, `test_shadow_phase_restamp.py`,
  `test_monitor_concern_action.py`, `test_monitor_agent_marks.py`
- After the step-6 handoff the committed blobs equal the working tree for
  every edited path, so the working-tree run is also the committed tree's
  run. Re-run the four directly affected modules if t2039 landed between the
  test run and the commit.
- `bash tests/run_all_python_tests.sh --test-dir tests` is optional. Check the
  last-line verdict.

## Post-implementation

Step 9 of the task workflow: archive the task and plan (current-branch mode,
no merge).

## Risk

### Code-health risk: low
None identified. The change is two renderer branches plus a helper extracted
from identical existing code. The live output is byte-identical, which the
existing title tests pin. The one hazard, committing from files that t2039
also has dirty, is designed out by step 6: the commit waits until t2039 has
landed, then uses git's own serialized `commit -o`. It is not left as a
residual risk.

### Goal-achievement risk: low
None identified. The task id/title path is the one `i` already uses
successfully on frozen rows, and the user-visible requirement (a title line
under frozen rows in both apps) is covered directly by the new tests.
