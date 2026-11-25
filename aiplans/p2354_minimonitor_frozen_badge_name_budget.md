---
Task: t2354_minimonitor_frozen_badge_name_budget.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2354 — frozen-row sitrep badge replaces the `frozen` word

## Context

On a 40-column `ait minimonitor`, a frozen agent's row is
`<mark>F␠<name>␠␠frozen␠<badge>`. The t2337 sitrep badge comes out of the name
budget on top of the word `frozen`, so the name drops to 8-17 cells. That is
below the module's own `_MIN_NAME_CELLS = 12` floor, and the task id gets cut off
(`pick-226…` for `agent-pick-2261_2`). The bold-cyan `F` in the prefix already
says "frozen", and only frozen rows ever get a badge, so the word repeats the `F`.

**Decision (confirmed with the user):** once a validated sitrep verdict exists,
the badge is shown **in place of** the word `frozen`, in **both** TUIs
(`ait minimonitor` and `ait monitor`). One shared helper renders it, so the two
TUIs cannot drift. With no verdict yet (`None`), the row still reads `frozen`.

Name room on minimonitor row 1 at the default width (budget 36 = prefix 3 + gap 2
+ word/badge + name):

| state | shown | cells | name room |
|---|---|---|---|
| `None` | `frozen` | 6 | 25 |
| `nothing` | `drop ok` | 7 | 24 |
| `unknown` | `sitrep ?` | 8 | 23 |
| `unlinked` | `drop ok, ?` | 10 | 21 |
| `unharvested` | `unharvested` | 11 | 20 |
| `triage_open` / `closed` / `review_pending` | `drop ok, triage` … | 15 | 16 |
| `triaged` | `drop ok, triaged` | 16 | 15 |

Every state stays at or above `_MIN_NAME_CELLS` (12).

## Implementation

### 1. `.aitask-scripts/monitor/monitor_shared.py` — one shared seam

Next to `FROZEN_SITREP_BADGES`:

- Refactor: `_frozen_sitrep_badge_markup(state)` returns the segment markup with
  **no** leading space (`"".join(f"[{style}]{text}[/]" ...)`).
  `format_frozen_sitrep_badge(state)` stays as it is (`""` for `None`, otherwise
  `" " + markup`), because the docked own-agent card still uses it after its
  `frozen <stamp>` line.
- New `format_frozen_state(state) -> str`: `"[dim]frozen[/]"` when `state is None`,
  otherwise `_frozen_sitrep_badge_markup(state)`. Unknown keys raise `KeyError`
  (the same guard as before). The docstring says why: the `F` already says frozen,
  and the badge replaces the word in both TUIs. In `ait monitor` there is room for
  the word, but it is dropped there too so the two TUIs show the same words.
- New `frozen_state_width(state) -> int`: `cell_len("frozen")` for `None`,
  otherwise `sum(cell_len(text) ...)`. This becomes the **only** width
  calculation.
- **Remove `frozen_sitrep_badge_width`.** The list row was its only production
  caller, and the docked card never measures its suffix. The docked suffix is
  `" " + _frozen_sitrep_badge_markup(state)`, so where a test needs its width it
  is `1 + frozen_state_width(state)`. Its test assertions move to the new helper
  (step 4), so production and tests cover one calculation.
- Update the comment above `FROZEN_SITREP_BADGES` and the docstring of
  `format_frozen_sitrep_badge`: it is now only the docked card's suffix.

### 2. `.aitask-scripts/monitor/minimonitor_app.py`

- Import `format_frozen_state` and `frozen_state_width`. Drop
  `frozen_sitrep_badge_width` from the import (the helper is removed). Keep
  `format_frozen_sitrep_badge` (the docked card at ~line 3364 uses it).
- In the frozen branch of `_agent_card_text` (~line 3027):
  ```python
  sitrep_state = self._frozen_sitrep_state(snap)
  name = self._row_name(snap, prefix, frozen_state_width(sitrep_state))
  text = f"{prefix}{name}  {format_frozen_state(sitrep_state)}"
  ```
  Rewrite the comment: the badge takes the word's place, and the reason is the
  name floor, with a reference to rule 3.
- Budget comment block (~line 268): replace the `frozen` line with the two shapes:
  ```
  #     frozen  <mark>F␠<name>␠␠frozen    name = 36 − 3 − 2 − 6  = 25
  #             <mark>F␠<name>␠␠<badge>   badge in place of `frozen` (t2354):
  #             7..16 cells ⇒ name 24..15, widest `drop ok, triaged` → 15
  ```

### 3. `.aitask-scripts/monitor/monitor_app.py` (~line 1943)

Replace `[dim]frozen[/]{format_frozen_sitrep_badge(...)}` with
`{format_frozen_state(self._frozen_sitrep_state(snap))}`, fix the import, and
update the comment: the badge replaces the word in both TUIs so they show the same
words, even though this TUI does not clip names.

### 4. Tests

`tests/test_minimonitor_row_budget.py`: a new test class `FrozenBadgeNameFloorTests`
(or a method in `NameFloorTests`). It loops over `[None, *ms.FROZEN_SITREP_BADGES]`
at `_TARGET_WIDTH`, and stubs `app._frozen_sitrep_state = lambda snap: state` on
`_row_app()`:
- name `"agent-" + "x"*60`: the row fits `_row_budget`, the single `x+…` run is
  ≥ `mm._MIN_NAME_CELLS`, and the row ends with `frozen` (for `None`) or with the
  badge's plain text, and contains no `frozen` word otherwise;
- the row **starts with the frozen prefix**: `_plain(ms.format_frozen_prefix(kind))
  + " "`, checked for `KIND_NONE` and `KIND_PRIORITY`. With a badge shown, the
  `F` is the only frozen marker left, so a row that lost it must fail;
- names `agent-pick-2261_2` and `agent-pick-1351_12`: `pick-2261_2` /
  `pick-1351_12` appear whole, with no `…`.
Because the loop runs over every `FROZEN_SITREP_BADGES` key, a badge state added
later that is too wide fails this test.

`tests/test_monitor_frozen_sitrep_badge.py`:
- `FormatterTests`: these tests now cover `frozen_state_width` instead of the
  removed helper:
  - `test_the_width_matches_the_render` loops over `None` plus every state.
    `frozen_state_width` must equal the cell width of `format_frozen_state`. The
    docked suffix `format_frozen_sitrep_badge` (for non-`None` states) must equal
    `1 + frozen_state_width(state)` and start with a space.
  - `test_none_renders_nothing` becomes: `format_frozen_sitrep_badge(None) == ""`
    and `format_frozen_state(None)` renders plain `frozen` with width 6.
  - New checks: a badged render has no leading space and no `frozen`, and an
    unknown key raises in `format_frozen_state` too.
- `RowTests`: `"frozen drop ok, triage"` becomes three checks, in both TUIs:
  the row contains `drop ok, triage`, its first line has no `frozen`, and its
  first line still carries the frozen prefix, i.e. contains
  `_plain(format_frozen_prefix(KIND_NONE)) + " "` (`☆F `) at the mark position
  (minimonitor: the start of the row; `ait monitor`: after its one-space
  indent). `"frozen sitrep ?"` changes the same way, with the same prefix check. `test_no_result_renders_no_badge`
  stays as it is (the word is still shown).
  `test_the_minimonitor_name_budget_pays_for_the_badge` becomes
  `name_bare − name_badged == frozen_state_width(TRIAGED) − frozen_state_width(None)`.

### 5. Docs (current-state wording)

My change makes these passages wrong, so I fix them here:
- `website/content/docs/workflows/freeze-and-restore-agents.md` ~76: "After the
  word `frozen`, the row shows…" becomes: once sitrep has read the state, the row
  shows the state in place of the word `frozen`. Keep the list. "The row shows
  nothing extra until the state has been read" becomes "Until the state has been
  read, the row shows `frozen`."
- `website/content/docs/workflows/sitrep.md:41`: "after `frozen` comes …" becomes
  "in place of `frozen` it shows …".
- `website/content/docs/tuis/monitor/how-to.md` ~71 and ~274, and
  `website/content/docs/tuis/minimonitor/how-to.md` ~56 and ~366: add "or, once
  sitrep has read it, the state badge in its place". Add one badged example line
  to the minimonitor code block.
- `aidocs/framework/sitrep.md:680`: "reads `frozen` plus an advisory badge"
  becomes "reads the advisory badge in place of `frozen` (t2354)".
- Leave CHANGELOG and the blog post alone (they are release history).
- Run `cd website && python3 check_links.py --build`.
- Send a note to t2351 (Ready, it edits the same freeze-and-restore/sitrep
  passages) saying the wording changed and its line numbers may have moved.

## Plan-review dispositions

Both points from the plan review were checked, found valid and **folded in
here** (each is low effort), not spawned as follow-ups:
- *frozen marker tests*: the prefix checks in step 4 (both test files, both TUIs).
- *badge width helper*: `frozen_sitrep_badge_width` is removed and
  `frozen_state_width` is the one width calculation (steps 1 and 4).

## Out of scope / follow-up

The docked own-agent card's second line, `  frozen 2026-11-24T18:52:00Z drop ok,
triaged`, is 46 cells against a 36-cell row, so it wraps. That overflow is already
on main from t2337 and is a separate fix: I will offer a follow-up task at Step 8.
The two items the task lists as out of scope also stay out.

## Verification

- `python3 tests/test_minimonitor_row_budget.py`
- `python3 tests/test_monitor_frozen_sitrep_badge.py`
- `bash tests/run_all_python_tests.sh --test-dir tests` is too much here. Instead,
  grep the tests for frozen-row assertions (`grep -rln "frozen" tests/*.py | xargs
  grep -l "_agent_card_text\|_format_agent_card_text"`) and run each file found.
- Pre-fix control: the new floor test fails on the current code for the
  `drop ok, triage`/`triaged` states (name 9/8 < 12). I check this by
  temporarily reverting only the minimonitor branch in a scratch copy. I do not
  stash or restore anything in the shared worktree.
- `shellcheck` is not needed (no shell changes).
- `cd website && python3 check_links.py --build`.

## Step 9

Post-implementation: review, commit (`bug: … (t2354)`), and archival per Step 9
of the task workflow.

## Risk

### Code-health risk: low
- Two TUIs and their tests change on the shared seam. Existing tests that pin
  the literal `frozen drop ok, …` text must be updated, or they fail. Those tests
  are found by grep and updated in this change · severity: low · → mitigation: none needed
  (covered by the verification step)

### Goal-achievement risk: low
- A user who learned "frozen + badge" may at first read a badged row as not
  frozen. The cyan `F` and the docs updated in this change cover that
  · severity: low · → mitigation: none needed

## Final Implementation Notes

- **Actual work done:** Steps 1-5 as planned. `monitor_shared.py` gained
  `format_frozen_state` / `frozen_state_width` (the one width calculation) on
  top of a private `_frozen_sitrep_badge_markup`; `frozen_sitrep_badge_width`
  was removed. Both TUIs' frozen list rows render `format_frozen_state`.
  `format_frozen_sitrep_badge` remains only for the docked card's suffix.
- **Deviations from plan:** none in code. Docs: `freeze-and-restore-agents.md`,
  `workflows/sitrep.md`, `tuis/monitor/how-to.md` (two passages),
  `tuis/minimonitor/how-to.md` (two passages, plus a badged example row) and
  `aidocs/framework/sitrep.md` (badge paragraph; also names the docked card's
  different shape).
- **Issues encountered:** `aidocs/framework/sitrep.md` carried in-flight
  t2350's uncommitted hunk (~line 729), so only this task's hunk (~line 680)
  is staged for this commit.
- **Key decisions:** the badge replaces the word in both TUIs (user's choice),
  through one shared helper; `frozen_sitrep_badge_width` was retired so there is
  one width calculation. The code commit is `33ffb187c`, built from a private
  index and landed with a CAS `update-ref` (see Change Requests 1-2).
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/minimonitor_app.py:3359-3367` — the docked own-agent
    card's second line `  frozen <YYYY-MM-DDTHH:MM:SSZ> <badge>` is 2+6+1+20+17 =
    46 cells against 36 at the default width for `drop ok, triaged`, so it wraps,
    and `_OWN_PANEL_MAX_ROWS` reserves one row for it (pre-existing from t2337).
- **Pre-fix control:** the new `FrozenBadgeNameFloorTests` was written first
  and run against the unchanged code: 24 failures (all badged states fail the
  no-`frozen` check; `triage_open`/`triaged`/`closed`/`review_pending` cut
  `pick-2261_2` and `pick-1351_12`). The prefix test passed there as well, as
  expected: it guards the `F` against a future regression.
- **Verification:** the 14 test files that render frozen rows all pass,
  including `test_minimonitor_row_budget.py` (19) and
  `test_monitor_frozen_sitrep_badge.py` (16). `check_links.py --build` passes.

## Post-Review Changes

### Change Request 1 (2026-11-24 20:10)
- **Requested by user:** `aidocs/framework/sitrep.md` holds this task's badge
  paragraph and in-flight t2350's uncommitted reverse-index hunk. Staging only
  this task's hunk is not enough, because Step 8's `git commit -- <paths>`
  commits a tracked path's working-tree content. Isolate the reviewed patch, and
  check that the commit leaves out the t2350 hunk.
- **Changes made:** no source change. The commit is built from a private index
  (`GIT_INDEX_FILE` in the session scratchpad), seeded with `git read-tree
  <base>`. The 9 files with only t2354 edits are added from the working tree.
  The shared file is added as `<base>`'s blob with only this task's paragraph
  replaced (`git hash-object -w` + `update-index --cacheinfo`). The commit is
  made with `git commit-tree` and lands through a compare-and-swap
  `git update-ref refs/heads/main <new> <base>`, so it cannot overwrite a commit
  another session pushed meanwhile. The repo has no git hooks, so commit-tree
  skips nothing. The real index entries for exactly these paths are then
  refreshed (superseded by Change Request 2: a guarded `read-tree`, not a
  path-scoped reset). Checked before the
  commit: the tree diff against base is exactly the 10 t2354 files; the t2350
  marker `Reverse index (t2350)` occurs 0 times in the tree's copy, and
  `format_frozen_state` occurs once; the 6 key frozen-row test files pass when
  run against the extracted tree alone (`git archive` + `python3 -I`).
- **Files affected:** none beyond the reviewed set (commit mechanics only).

### Change Request 2 (2026-11-24 20:35)
- **Requested by user:** (1) After `update-ref`, the real-index refresh must
  keep any staging that arrived after the empty-index check. A path-scoped
  `reset` silently replaces a newer staged entry, so use a guarded update and
  handle a refusal without overwriting staged work. (2)
  `website/content/docs/workflows/sitrep.md:41` reads as an unconditional
  replacement and leaves out `sitrep ?`. Say what readers see while the
  verdict is pending or could not be read.
- **Changes made:** (1) The refresh is `git read-tree -i -m <base> <new>`.
  Checked in a scratch repo: an unrelated staged path is kept and my paths
  move to `<new>`; a staged entry for one of my paths makes git refuse
  (exit 128) and keeps the staged entry. A refusal is reported to the user and
  never forced. (2) The summary now says the row reads `frozen` until the
  state is read, then shows the state in place of the word, and `sitrep ?`
  when the state could not be read (never safe). The link check passes.
- **Also:** in-flight t2350 committed `12445d7` meanwhile, so the guard
  `HEAD == base` failed before anything was written. t2350 committed without
  its `aidocs/framework/sitrep.md` hunk, which is still uncommitted. The tree is
  rebuilt on `12445d7` by `build_tree.sh` (scratchpad), which re-derives the
  shared file from the new base's blob. Checked: 10 changed paths, t2350 hunk
  0, t2354 hunk 1, every file equals the working tree. 8 test files pass
  against the extracted tree alone, including t2350's
  `test_frozen_sitrep.py` and `test_sitrep_tui_frozen_source.py`.
- **Files affected:** `website/content/docs/workflows/sitrep.md`.
