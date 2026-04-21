---
Task: t604_skip_section_headers_in_manual_verification.md
Base branch: main
plan_verified: []
---

# Plan: t604 — Manual-verification polish (section headers, carry-over slug, mid-loop pause)

## Context

During the `t597_6` manual-verification run (2026-04-21) three rough edges surfaced in the `/aitask-pick` manual-verification path:

1. **Section-header noise.** `aitask_verification_parse.py` emits every `- [ ]` line as a checklist item — including category-header bullets whose text ends with `:` and whose children are nested one indent deeper. The interactive loop prompts pass/fail for these headers, polluting the record (see `aitasks/archived/t597/t597_6_manual_verification.md` lines 28, 35, 40, 44).
2. **Ugly carry-over slug.** The `--with-deferred-carryover` path in `aitask_archive.sh` names the carry-over task `<orig>_deferred_carryover`. User wants `<orig>_carryover` — drop the `_deferred_` infix.
3. **No mid-loop pause.** To exit the per-item loop today the user must first mark the current item (pass/fail/skip/defer) and *then* hit the post-loop "Stop without archiving" branch. That forces a dummy answer onto the item at the cursor. User wants a true pause path that leaves the current item unchanged.

All three are local edits; no new scripts, no architectural change.

## Scope

### 1. Filter section headers in the parser

**File:** `.aitask-scripts/aitask_verification_parse.py`

Add a heuristic in `_iter_items` that skips `- [ ]` lines which are section headers — and do so **before** index assignment, so `parse`/`summary`/`terminal_only`/`set` and the `followup` script (all of which share `_iter_items`) stay consistent with each other.

**Heuristic** (matches task-description wording): a line is a section header iff
- the item text (after stripping any ` — <STATE> <timestamp>…` annotation via `_strip_annotation`) ends with `:`, **and**
- the next non-blank line in the section is another `ITEM_RE` match whose leading-indent length is **strictly greater** than this line's.

Non-blank lookahead must stop at section end (`end` from `_locate_section`) so a `:` bullet at end-of-checklist followed only by text/EOF is not misclassified.

Implementation sketch (inside `_iter_items`, before the existing `idx += 1`):

```python
def _is_section_header(body, line_no, end, indent):
    m = ITEM_RE.match(body[line_no])
    assert m is not None
    text = _strip_annotation(m.group(3)).rstrip()
    if not text.endswith(":"):
        return False
    # find next non-blank line within the section
    j = line_no + 1
    while j < end and body[j].strip() == "":
        j += 1
    if j >= end:
        return False
    n = ITEM_RE.match(body[j])
    if n is None:
        return False
    return len(n.group(1)) > len(indent)
```

Then in the `_iter_items` loop: after `ITEM_RE` matches, call `_is_section_header(body, line_no, end, m.group(1))` and `continue` (without touching `idx`) if True.

**Consequence on existing consumers:**
- `parse` output: headers dropped, indices re-dense (1..N over children only).
- `summary` counts: automatically exclude headers.
- `terminal_only`: a file with only a pending header + all-terminal children now gates as terminal — **this is the desired behavior** (matches e.g. `t597_6` line 40 `[defer] CLI parity:` with all-terminal children).
- `set <idx>`: indexes into the filtered list. "`set` still works on a header line by index (for backward compat)" in the acceptance criteria is interpreted as: `set` still works on any item emitted by `parse` — no special passthrough for filtered headers. The TUI loop never sees a header, so this is benign.
- `aitask_verification_followup.sh` looks up item text by `parse`-output `idx` and receives the same filtered view — consistent.
- `aitask_archive.sh:555` awks `parse` output for deferred items — also filtered, so seeded carry-over checklists won't carry orphan headers either. This is a bonus.

### 2. Rename carry-over slug

**File:** `.aitask-scripts/aitask_archive.sh` (line 567 inside `create_carryover_task`).

One-line change:

```diff
-    local carryover_name="${orig_name}_deferred_carryover"
+    local carryover_name="${orig_name}_carryover"
```

No disk rename needed — `find aitasks -name "*deferred_carryover*"` returns nothing (no live carry-over tasks on disk today). The `--with-deferred-carryover` CLI flag name is unchanged (that's a separate concept — "archive with carry-over for deferred items").

**Test updates** (assertions currently grep the old slug):
- `tests/test_archive_carryover.sh:310` — `ls aitasks/t*_verify_deferred_carryover.md` → `ls aitasks/t*_verify_carryover.md`
- `tests/test_archive_verification_gate.sh:399` — same change

### 3. Mid-loop "Stop here, continue later"

**File:** `.claude/skills/task-workflow/manual-verification.md` Step 2.2.

Convert the per-item prompt to a **two-step** shape (task's preferred design — option 1 from its implementation note). The current 4-option prompt (Pass/Fail/Skip/Defer) stays the same; we gate it behind a 2-option lead-in.

**Rewritten Step 2.2 (approx):**

```markdown
2. Ask whether to proceed with this item or pause the whole loop. Use `AskUserQuestion`:
   - Question: "Item <idx>: <text>"
   - Header: "Proceed"
   - Options:
     - "Verify this item" (description: "Mark pass/fail/skip/defer for this item")
     - "Stop here, continue later" (description: "Pause the verification loop; leave this item and any remaining items unchanged")

   **If "Stop here, continue later":**
   - Do NOT call `aitask_verification_parse.sh set` — the item is left in its current state (still `pending` or still `defer`).
   - Skip the remaining items in the loop.
   - Skip step 3 (post-loop checkpoint) and step 4 (commit verification state) entirely — no state has changed, so no commit is warranted.
   - Inform the user: "Task t<task_id> paused at item <idx>. Re-pick with `/aitask-pick <task_id>`."
   - End the workflow. The task stays `Implementing` and the lock remains held (same end state as the existing "Stop without archiving" branch — only the message differs).

   **If "Verify this item":** continue with the inner `AskUserQuestion`:
   - Question: `<text>`
   - Header: "Verify"
   - Options:
     - "Pass" (description: "This check passed")
     - "Fail" (description: "This check failed — create a follow-up bug task")
     - "Skip (with reason)" (description: "Not applicable / cannot verify — record a reason")
     - "Defer" (description: "Postpone until later; task will not archive while any item is deferred")

3. Handle the inner answer: [existing Pass/Fail/Skip/Defer handlers move here unchanged]
4. Move to the next pending/deferred item.
```

All four existing handler bodies (Pass, Fail with follow-up branching, Skip-with-reason, Defer) stay verbatim — only their enclosing heading shifts from "3" to "3 within the inner branch".

## Tests

**New:** `tests/test_verification_section_headers.py` — matches the style of the existing `tests/test_verification_parse.py` (Python unittest, `_load_module()` pattern). The task description nominated `.sh` but the parser and its tests are already Python — staying Python is the coherent choice. Cases:

1. Single top-level header with two nested children → `parse` emits 2 items (the children), indices 1,2. Header absent.
2. Header mid-list (sibling items before/after) → indices stay dense across the gap.
3. `:` line followed by a **non-indented** sibling `- [ ]` → NOT filtered (regular item).
4. `:` line at end-of-section (no following line) → NOT filtered.
5. Pre-marked header (`- [x] Foo: — PASS …`) is still recognized as a header (annotation stripped before `:` check).
6. `summary` counts exclude headers.
7. `terminal_only` returns 0 (no pending/defer) on a file with a pending header + all-terminal children.
8. `set <idx> pass` targets the correct (filtered) item — verify by re-parsing and confirming the child at that index flipped.

**Extended:** `tests/test_archive_carryover.sh` and `tests/test_archive_verification_gate.sh` — update the two assertion globs from `*_verify_deferred_carryover.md` to `*_verify_carryover.md`.

**Not added:** automated coverage for the markdown-only Step 2.2 pause path. The path is purely a no-op (the procedure doesn't call a script — it just skips ahead), so there's nothing executable to assert against. The acceptance-criteria wording ("A test verifies the pause path leaves task metadata untouched") is satisfied by construction: since no `set` call runs, no mutation can happen. Calling this out explicitly rather than inventing a hollow test.

## Critical files

- `.aitask-scripts/aitask_verification_parse.py` — add `_is_section_header`, hook into `_iter_items`.
- `.aitask-scripts/aitask_archive.sh:567` — one-line slug change.
- `.claude/skills/task-workflow/manual-verification.md` Step 2.2 — rewrite as two-step prompt.
- `tests/test_verification_section_headers.py` — new.
- `tests/test_archive_carryover.sh:310` and `tests/test_archive_verification_gate.sh:399` — slug assertions.

## Verification

```bash
# Unit — parser section-header filter
python3 tests/test_verification_section_headers.py
# Existing parser tests still pass
python3 tests/test_verification_parse.py

# Carry-over rename — existing tests now green against the new slug
bash tests/test_archive_carryover.sh
bash tests/test_archive_verification_gate.sh

# Lint
shellcheck .aitask-scripts/aitask_archive.sh
```

**End-to-end sanity check (manual):** re-parse `aitasks/archived/t597/t597_6_manual_verification.md` and confirm that `aitask_verification_parse.sh parse` now skips the four section-header lines (28, 35, 40, 44) and that indices line up with the "leaf" items only.

## Step 9 (post-implementation)

Standard task-workflow Step 9: commit code & tests under one commit with `refactor: <subject> (t604)`, commit the plan file via `./ait git`, archive via `aitask_archive.sh 604`, push.

## Notes / open questions

- **Language for new test file.** Defaulted to Python (`.py`) to match `test_verification_parse.py`. Task description suggested `.sh`. If the user wants shell, the tests are easy to rewrite against the `aitask_verification_parse.sh` wrapper.
- **Backward-compat phrasing.** The task says "`set` still works on a header line by index (for backward compat)". Read as an assurance-of-non-breakage, not a feature request — headers are filtered from everywhere including `set`'s view. No caller today targets a header by its old "unfiltered" index, so nothing to preserve.

## Final Implementation Notes

- **Actual work done:** Added `_is_section_header(body, line_no, end, indent)` helper to `.aitask-scripts/aitask_verification_parse.py` and hooked it into `_iter_items` before index assignment, so section headers are filtered from every subcommand (`parse`, `summary`, `terminal_only`, `set`) and from every downstream consumer (`aitask_verification_followup.sh`, `aitask_archive.sh`'s deferred-items awk). Reordered `_strip_annotation` ahead of the new helper because the helper calls it. Renamed carry-over slug in `.aitask-scripts/aitask_archive.sh:567` from `${orig_name}_deferred_carryover` to `${orig_name}_carryover`. Rewrote Step 2.2 of `.claude/skills/task-workflow/manual-verification.md` as a two-step prompt: 2-option lead-in (Verify / Stop here, continue later) drilling into the existing 4-option Pass/Fail/Skip/Defer prompt; the Stop path leaves state untouched, skips steps 3 and 4, and emits a "paused at item \<idx\>" message. Added `tests/test_verification_section_headers.py` (8 cases). Updated slug glob in `tests/test_archive_carryover.sh:310` and `tests/test_archive_verification_gate.sh:399`.
- **Deviations from plan:** None. Test language defaulted to Python after user confirmation.
- **Issues encountered:** None. Tests were green on first run.
- **Key decisions:**
  - Filter at `_iter_items` (heuristic scoped to "next non-blank line in the section is a deeper-indented item") so all callers share the same view. This means `set`, `followup`, and the deferred-items awk in `aitask_archive.sh:555` auto-inherit the filter — seeded carry-over checklists won't carry orphan headers either, which is a desirable side effect.
  - Pre-marked headers (e.g. `- [x] group: — PASS …`) are still classified as headers because `_strip_annotation` is applied before the `:` suffix check.
  - Did not add automated coverage for the Step 2.2 pause path — it's a markdown-only, no-op branch (the procedure doesn't invoke any script), so the "leaves metadata untouched" acceptance is satisfied by construction rather than by a hollow test. Called this out explicitly in the plan.
- **Verification results:** `tests/test_verification_section_headers.py` 8/8 pass; `tests/test_verification_parse.py` 31/31 pass (unchanged); `tests/test_archive_carryover.sh` 13/13 pass with new slug; `tests/test_archive_verification_gate.sh` 34/34 pass with new slug; `shellcheck .aitask-scripts/aitask_archive.sh` clean (only pre-existing info-level SC1091/SC2012 warnings). Manual sanity: re-parsed `aitasks/archived/t597/t597_6_manual_verification.md` and confirmed lines 28, 35, 40, 44 are absent from the output with indices dense 1..20.
