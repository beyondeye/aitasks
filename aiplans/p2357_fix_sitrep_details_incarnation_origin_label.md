---
Task: t2357_fix_sitrep_details_incarnation_origin_label.md
Base branch: main
Output branch: main
---

# t2357 — sitrep details: `incarnation` origin row runs into its value

## Context

The sitrep store writer accepts the origin key `incarnation`
(`.aitask-scripts/lib/sitrep_todo.py` `ORIGIN_KEYS`), but the TUI's
`ORIGIN_LABELS` (`.aitask-scripts/sitrep_tui/sitrep_tui_model.py:800`) has no
entry for it. The item details screen renders each Origin sub-row with
`_field(ORIGIN_LABELS.get(key, key), value, "  ")`
(`.aitask-scripts/sitrep_tui/sitrep_tui_app.py:126`). That pads
`indent + label` with `ljust(_LABEL_W)` (`_LABEL_W = 12`) and then appends the
value directly. `"  incarnation"` is 13 cells, so the output is
`  incarnation<hex>` with no separator. Every crash-recovery item has this row,
because `recovery-apply` writes `origin: task=… incarnation=…`.

Two defects:
1. The key has no label.
2. `_field` can glue any label of 12 or more cells, indent included, to its value.

## Mode and coordination

**Mode: current branch (`main`), as Step 5 resolved under profile `fast`.**
Externalize with `--no-worktree`. There is no task branch and no merge-broker
merge, so the broker's whole-checkout `DIRTY_TREE` criterion does not apply. An
isolated worktree was considered and rejected for two reasons: `fast` refuses
`--worktree`, and the broker would gate the landing on every session's tracked
edits in the shared checkout, not just the overlapping ones.

`t2335_1` (store direction records, format 4) is `Implementing` here. It has
**uncommitted** hunks in three of the files this task edits:
`sitrep_tui_app.py`, `tests/test_sitrep_tui_app.py` and
`website/content/docs/tuis/sitrep/reference.md`. A clean `git diff` at some
moment does not prove it is finished with them. So:

**Readiness precondition (R):**
1. **Explicit handoff.** Either `t2335_1` is `Done`/archived
   (`./.aitask-scripts/aitask_query_files.sh resolve 2335_1` / the archived
   lookup), **or** the user confirms in chat that t2335_1 is finished with these
   three files.
2. **Checkout.** `git rev-parse --abbrev-ref HEAD` is `main`, and the saved
   plan's header has no `Worktree:` line.
3. **Path readiness.** `git diff --quiet HEAD -- <P>` and
   `git diff --cached --quiet -- <P>` pass for every file `P` this plan writes
   (the three shared files and `sitrep_tui_model.py`). The new test file must
   not exist.

**R is evaluated twice:**

- **At the Checkpoint, before the approval prompt.** Run R. Its result (which
  item failed, and the dirty paths) goes **inside the prompt's question text**.
  If R fails, the recommended option is **"Approve and stop here"**. The task
  returns to `Ready` with this approved plan and is re-picked after t2335_1
  lands. Under `fast`, `plan_preference: use_current` goes straight back to the
  Checkpoint, where R runs again. "Start implementation" is only appropriate
  once R passes, or once the user gives the explicit handoff (R1) in that
  answer.
- **Pre-edit recheck — in Step 7, immediately AFTER the standard
  Pre-implementation ownership guard.** It runs before Resource Admission, the
  fork no-op, Step 7's gate recordings and risk-field writes, and any code
  edit. The guard goes first for the reason Resource Admission states: the stop
  releases the lock and reverts the task, so ownership must be confirmed first.
  If the guard cannot confirm or re-acquire ownership, follow its own handling
  and never run the stop sequence. Run R again, since readiness can change
  between the prompt and now. If R fails, **edit nothing** and take the
  explicit stop: run the **Approved-Plan Stop Sequence**
  (`plan-approved-stop.md`) with `stop_reason=deferred` and
  `revert_commit_message="ait: Revert t2357 to Ready after plan approval"`.
  The `closing_message` names what failed and says to re-pick with
  `/aitask-pick 2357` after t2335_1 lands. That sequence records the approval
  idempotently, releases the lock, reverts the task to `Ready` and stamps
  `plan_approved_at`. In current-branch mode there is no worktree or branch to
  clean up.

**While editing — last-accepted-state chain.** After each of my writes, record
the file's sha256. Before every later write to that file, and before the
commit, check three things: its sha256 is unchanged, `git rev-parse HEAD:<P>` is
unchanged, and `git diff --cached --quiet -- <P>` still passes. Any mismatch
means another session wrote. Stop and ask the user; never commit over it.

**Commit:** one path-scoped commit containing all five paths (no partial
landing). Afterwards, check that `git show HEAD:<P>` contains my hunks and
`git status` shows none of my paths dirty.

## Implementation

1. **Label** — `sitrep_tui_model.py` `ORIGIN_LABELS`: add
   `"incarnation": "Episode"`. The aidocs name the concept the "episode key
   (`incarnation=<12 hex>`)". `"  Episode"` is 9 cells, so the value stays in
   the same 12-cell column as Agent/Task/Date. (`"  Incarnation"` would be 13
   cells and misalign the column even with the separator fix.)

2. **Separator** — `sitrep_tui_app.py` `_field`: always leave ≥1 space:
   ```python
   return Content.assemble(((f"{indent}{label}".ljust(_LABEL_W - 1) + " "), "bold"), value)
   ```
   Every label of 11 cells or fewer renders byte-identically (`ljust(11)+" "` ≡
   `ljust(12)`). The longest current label, `Task status` (11), is unchanged.
   The no-value branch is untouched. The docstring states the one-space
   guarantee.

3. **Unit tests** — new `tests/test_sitrep_tui_field_label.py` (unittest, no TUI
   boot; same sys.path prelude as `tests/test_sitrep_tui_app.py`):
   - `set(model.ORIGIN_LABELS) == set(st.ORIGIN_KEYS)`. A future accepted key
     without a label fails here.
   - Every origin label fits the column: `len("  " + label) <= appmod._LABEL_W - 1`.
   - The separator holds for overlong labels:
     `_field("incarnation", "V", "  ").plain == "  incarnation V"`, and
     `_field("A" * 12, "V").plain == "A" * 12 + " V"`.
   - Byte-identical for ≤11 cells: `_field("Task status", "V").plain == "Task status V"`.

4. **End-to-end details test** — `tests/test_sitrep_tui_app.py`, next to
   `test_a_recovery_item_shows_in_recovery_after_a_reload`, reusing its recipe:
   `recover_item(self.root, "30", "crashed", "0123456789ab")`,
   `await app._poll_store()`, `open_details(app, pilot, num)`. It asserts the
   `#sd-body` text contains
   `"Origin\n  Task      t30\n  Episode   0123456789ab"`: the label, the actual
   id and the exact column spacing.

5. **Red proof** — temporarily revert only my two source hunks with Edit (each
   write goes through the chain). Run steps 3–4's tests, confirm the label,
   separator and details assertions fail, then restore. Record the outputs in
   Final Implementation Notes.

6. **Docs** — `website/content/docs/tuis/sitrep/reference.md` Context bullet:
   `Origin (Agent, Task, Commit, Date, Skill, Pane, Episode)`.

## Verification

- `python3 -m unittest tests.test_sitrep_tui_field_label -v`
- `python3 -m unittest tests.test_sitrep_tui_app tests.test_sitrep_tui_frozen_source`
  (every `_field` caller; the existing pin
  `"Origin\n  Agent     agent-pick-10\n…"` must still pass).
- `python3 check_links.py --build` (in `website/`).
- Commit (one, path-scoped, five paths):
  `bug: Label the sitrep incarnation origin row and keep a label/value separator (t2357)`.
- Step 9 (Post-Implementation): current-branch mode, nothing to merge; archival.

## Risk

### Code-health risk: low
None identified. (The overlap with t2335_1 is handled by readiness R at the
Checkpoint and again before the first edit, plus the last-accepted-state chain.
If R fails, nothing is edited and the task stops as a deferred approved plan.)

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** As planned. `ORIGIN_LABELS["incarnation"] = "Episode"`
  (`sitrep_tui_model.py`, with the comment merged into the existing one), and
  `_field` now pads to `_LABEL_W - 1` plus one space (`sitrep_tui_app.py`).
  New `tests/test_sitrep_tui_field_label.py` has 6 tests: key/label parity,
  column fit, the separator for 12/13/20-cell labels, byte-identity for labels
  of 11 cells or fewer, and no padding without a value. The e2e test
  `TabTests.test_a_recovery_items_origin_shows_its_episode` is in
  `tests/test_sitrep_tui_app.py`. The docs Origin list now includes Episode.
- **Readiness R:** passed at the Checkpoint and again after the Step 7
  ownership guard. t2335_1 was archived (its work landed in `95d0169d8`), and
  every path was clean vs HEAD and in the index. The last-accepted-state chain
  (sha256 + `HEAD:<P>` + index, checked before each write) never tripped. Its
  failing arms were self-tested first (`CHAIN_FOREIGN_WRITE`,
  `CHAIN_HEAD_MOVED`).
- **Red proof (pre-fix code, my two source hunks temporarily reverted):**
  - `tests.test_sitrep_tui_field_label`: `FAILED (failures=2, errors=1)`.
    `test_every_accepted_origin_key_has_a_label` FAIL (the set is missing
    `incarnation`); `test_incarnation_reads_as_episode` ERROR (KeyError);
    `test_a_label_filling_the_column_keeps_a_space` FAIL:
    `'  incarnation0123456789ab' != '  incarnation 0123456789ab'`.
  - `TabTests.test_a_recovery_items_origin_shows_its_episode`: FAIL. The
    rendered body held `Origin\n  Task      t30\n  incarnation0123456789ab`,
    which is the defect itself.
- **Verification (fixed code):** `python3 -m unittest
  tests.test_sitrep_tui_field_label tests.test_sitrep_tui_app` passes (96
  tests). `tests/test_sitrep_tui_frozen_source.py` passes under pytest (19).
  Under plain unittest it only fails to import its sibling helper module, which
  is a loader-path issue, not this change. `website/check_links.py --build`:
  `SWEEP: PASSED`.
- **Deviations from plan:** none.
- **Issues encountered:** none beyond the frozen_source runner note above.
- **Key decisions:** the label is "Episode" (9 cells), not "Incarnation" (13
  cells), so the value column stays aligned. The aidocs call the concept the
  "episode key".
- **Upstream defects identified:** None
