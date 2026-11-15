---
Task: t2307_validate_status_in_sitrep_refresh_taskindex.md
Base branch: main
Output branch: main
---

# t2307 — Validate status in `sitrep_refresh.TaskIndex`

## Context

`TaskIndex._lookup` (`.aitask-scripts/lib/sitrep_refresh.py:296-330`) turns any
parseable frontmatter into facts through `_facts()`, which copies
`str(meta.get("status") or "").strip()` without checking it. So an active or
archived record whose status is missing, not a string, or outside the task
vocabulary still comes back as `found=active|archived`. Two consumers act on it:

- `reminder_verdict`: an active `status: Banana` task becomes
  `Verdict("open", "status: Banana")`. That is an "open" verdict from a record
  the refresh never validated. It should be `unknown`.
- `landed_state`: the same record reads as `open`, when it should be
  `unverifiable`. The same goes for `describe()` / `owner_text`, which print
  the bad value as if it were a live state.

t2299_2 (the crash detector) found this and worked around it with
`sitrep_crash.strict_meta`. It also pinned the lax behaviour as a contrast in
`tests/test_sitrep_crash.py::TaskReader::test_archived_records_are_validated`
(`idx.lookup("12").found == "archived"` for `Banana`).

I measured the real repository (2,534 Done, 639 Ready, 57 Postponed,
19 Implementing, 7 Folded, plus 3 records with an empty frontmatter, t20–t22,
and 2 `Completed` records, t27 and one more, all archived). The only archived
records affected already got an `unknown` verdict ("archived with status …"),
so with real data only the outcome text changes, never an item's state. The
real fix is in the active path and in the receiver/owner descriptions.

## Design

- **One vocabulary, one checker, shared.** Add `VALID_STATUSES` and a
  `status_problem(meta) -> str` helper to `sitrep_refresh.py`.
  `sitrep_crash.py` already imports `sitrep_refresh`, so it reuses both instead
  of keeping its own copy. The helper returns exactly the strings `strict_meta`
  produces today (`"no status"`, `"invalid status 'X'"`), so the crash
  detector's warnings (`tests/test_sitrep_crash.sh:323`
  `CRASH_WARN:t21|unreadable: t21_x.md: no status`) stay byte-identical.
- **Validate in the direct lookup only.** `_lookup` validates both its active
  and archived branches. The fold scan (`_build_folds`) stays as it is: it
  answers "which record lists this id in `folded_tasks`", and the migrated
  empty-frontmatter records (t20–t22, `{}`) must keep completing it
  (`HeaderlessArchivedRecords::test_migrated_records_complete_the_scan`).
  A fold-scan receiver with a bad status is still found as the receiver, but
  looking it up then returns `error`. So `describe()` prints "unreadable", the
  reminder still closes as "folded into tN" without the parenthetical, and
  `landed_state` returns `unverifiable`.
- Archive read errors and unparseable frontmatter keep their current
  `TaskFacts("error", ...)` paths.
- Remove the dead `OPEN_STATUSES` constant (`sitrep_refresh.py:132`). Nothing
  uses it (grep shows only its definition), and it names a `Blocked` status the
  framework does not have. Keeping a second, contradictory vocabulary next to
  the new one would invite drift.

## Implementation steps

1. **`.aitask-scripts/lib/sitrep_refresh.py`**
   - Replace `OPEN_STATUSES = (...)` with:
     ```python
     # The task-status vocabulary -- what aitask_update.sh / aitask_pick_own.sh
     # accept. A record whose status is missing or outside it is unreadable.
     VALID_STATUSES = ("Ready", "Editing", "Implementing", "Postponed", "Done", "Folded")
     ```
   - Next to `_meta_of`, add:
     ```python
     def status_problem(meta: dict) -> str:
         """'' for a valid status, else why not: 'no status' (missing, empty or
         not a string) or "invalid status 'X'" (outside VALID_STATUSES)."""
         status = meta.get("status")
         if not isinstance(status, str) or not status.strip():
             return "no status"
         if status.strip() not in VALID_STATUSES:
             return f"invalid status {status.strip()!r}"
         return ""
     ```
   - In `_lookup`, active branch: after the `meta is None` check, add
     `why = status_problem(meta)` and on a non-empty `why` return
     `TaskFacts("error", detail=f"{path.name}: {why}")`. Archived branch: the
     same check, with `found[0]` as the name.
   - Module docstring, EVIDENCE → task bullet: add one sentence saying that a
     record whose status is missing or outside the vocabulary is `unknown`
     (an unverifiable trail entry), never open or done. The fold scan still
     reads such a record's `folded_tasks`.
   - Leave `reminder_verdict` / `landed_state` / `describe` alone. Their
     no-status branches are fail-closed defaults for directly built facts and
     cost nothing.

2. **`.aitask-scripts/lib/sitrep_crash.py`**
   - `VALID_STATUSES = sitrep_refresh.VALID_STATUSES` (keep the name: the module
     uses it).
   - In `strict_meta`, replace the two inline checks with
     `why = sitrep_refresh.status_problem(meta)`, then
     `if why: return meta, f"{name}: {why}"`. The strings stay identical.

3. **`tests/test_sitrep_crash.py`**: flip the contrast at line 444-445:
   ```python
   # TaskIndex validates the status too (t2307): same verdict class as above.
   facts = idx.lookup("12")
   self.assertEqual(facts.found, "error")
   self.assertIn("invalid status 'Banana'", facts.detail)
   ```

4. **`tests/test_sitrep_refresh.py`**
   - Update `HeaderlessArchivedRecords::test_a_migrated_historical_task_is_never_made_done`.
     The state stays `unknown`, but the outcome is now
     `"lookup failed: t<tid>_x.md: no status"`. Assert the state, and assert the
     outcome with `assertIn("no status", ...)`.
   - Add `class StatusValidation(TreeCase)`, written with raw frontmatter where
     the status must be absent (`_task_text(None)` would write `status: None`,
     which YAML reads as the string "None"):
     - active `Banana`, `status:` (empty), no `status` key, non-string
       (`status: [Done]`, `status: 5`): each gives a verdict with state
       `unknown`, outcome starting `lookup failed:` and naming the reason;
       `lookup().found == "error"`; `landed_state(...)[0] == "unverifiable"`.
     - archived loose and bundled, for `Banana` and for no status, including a
       `Banana` record that carries `completed_at`: `unknown`, never `done`;
       `unverifiable`.
     - child id (`13_1`, archived, `Banana`): `unknown`.
     - receiver with a bad status: `t31 Folded folded_into=30`, `t30 Banana`.
       Reminder for 31 is `Verdict("done", "folded into t30")` (no
       parenthetical); `landed_state("31") == ("unverifiable", ["31", "30"])`;
       `describe(idx.lookup("30")) == "unreadable"`. And through the fold scan:
       `t30 Banana folded_tasks: [41]` gives the reminder for 41 as done
       "folded into t30" (the scan still reads the record), and `landed_state`
       as unverifiable.
     - **Control**, every one of the six valid statuses, active and archived:
       `lookup().found` is `active` / `archived` and the status is carried
       through, so the check cannot be passing because everything fails.
       Surrounding whitespace (`status: " Done "`) still validates.

## Verification

- `python3 tests/test_sitrep_refresh.py`
- `python3 tests/test_sitrep_crash.py`
- `bash tests/test_sitrep_crash.sh` (pins the `no status` warning text) and
  `bash tests/test_sitrep_refresh.sh` (end-to-end runs)
- `python3 tests/test_monitor_sitrep_refresh.py` and the sitrep TUI tests that
  import `sitrep_refresh`: `tests/test_sitrep_tui_actions.py`,
  `tests/test_sitrep_tui_app.py`
- Pre-fix control: before step 1, run the new `StatusValidation` tests against
  the unmodified module and record which fail. The invalid-status cases should
  fail; the valid-status controls should pass.
- Step 9 (Post-Implementation): commit, archive.

## Risk

### Code-health risk: low
- Existing sitrep todo items that point at the archived `Completed` / empty-frontmatter records (t20–t22, t27) get a new outcome text on the next refresh ("lookup failed: …: invalid status 'Completed'" instead of "archived with status Completed"). Their state stays `unknown`, and the change is a single store write per item. · severity: low · → mitigation: none (expected effect)

### Goal-achievement risk: low
None identified.
