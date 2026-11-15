---
Task: t2299_1_sitrep_store_recover_ref_and_recovery_apply.md
Parent Task: aitasks/t2299_sitrep_track_crashed_agents_for_resume.md
Sibling Tasks: aitasks/t2299/t2299_2_*.md, aitasks/t2299/t2299_3_*.md, aitasks/t2299/t2299_4_*.md
Archived Sibling Plans: aiplans/archived/p2299/p2299_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-15 16:18
---

# Plan: store support for recovery items (t2299_1)

## Context

t2299 tracks crashed agents in sitrep as **one recovery item per task**. The
item is `kind=task` with the stable ref `recover:t<N>`. Its evidence is updated
in place, a done item reopens, and a dismissal covers one *episode* (one claim
attempt, identified by a 12-hex `incarnation`).

This child adds the store mechanics the detector (t2299_2) and refresh/TUI
(t2299_3) rely on:
- the ref grammar;
- the `incarnation` origin key;
- an atomic, rev-guarded `recovery-apply` verb that enforces the dismissal rule;
- store format 3.

The task file holds the full fact sheet (line numbers at af0dca45c).

## Verification record (2026-11-15, HEAD 7a68196d0)

- No commit touched `lib/sitrep_todo.py`, `aitask_sitrep_todo.sh`,
  `lib/sitrep_refresh.py`, `tests/fixtures/sitrep/` or `tests/test_sitrep_todo.sh`
  since af0dca45c, and none of them is dirty. All line refs in the task still hold.
- Ref consumers re-read. `sitrep_tui_model.classify` gives `pick_noref` and `task_ref_id`
  gives None (their `_LOCAL_REF_RE` anchors `^t`). `harvest.ref_owner`/`_known`
  and `corpus.ref_owner` only ever pass `t<N>` refs. `refresh.check_task` is reached
  only via `select_targets` (step 6). So step 6 is the only consumer change.
- **Corrections to the earlier plan:**
  - A `Test 16c` already exists (push refs). The new v2 test is **16d**, and the
    recovery matrix is a new **Test 17**.
  - Hard-coded `format=2` assertions must move to 3: `test_sitrep_todo.sh` T16
    (:716) and T16b (:734); `test_sitrep_todo_format.py` `test_future_format`
    (:108), `test_render_emits_the_parsed_version` (:154) and
    `test_v1_with_a_push_ref…` (:158, the replace source).
  - The incarnation is only a reliable episode key if no other verb can write a
    `recover:` item behind its back. Added step 4b (side-path guards) and the
    no-context incarnation rule in step 4.
  - The writer's `upsert-context` accepted any origin, so a dismissal could
    be silently re-scoped. Covered by step 4b.

## Steps

1. **Ref grammar** (`lib/sitrep_todo.py`).
   - `RECOVER_REF_RE = re.compile(r"^recover:t([1-9][0-9]*(?:_[1-9][0-9]*)?)\Z")`
     (same id grammar as `LOCAL_REF_RE`, but the `t` is mandatory; no bare
     number, no upper case).
   - `normalize_ref`: accept it verbatim, before the push branch; extend the
     error text to name `recover:t<N>[_<M>]`.
   - `parse_recover_ref(ref) -> str | None` returns `"12"` / `"12_3"`.
   - `_check_item_values`: a `recover:` ref requires `kind == "task"`
     (RequestError, which parse_todo turns into a FormatError at the item line).
2. **Origin key.**
   - `ORIGIN_KEYS` gains `incarnation`; `INCARNATION_RE = ^[0-9a-f]{12}\Z`.
   - Validate it in `_check_context_values` (runs both on parse and on input).
   - Helper `context_incarnation(entry) -> str | None`.
3. **Format 3.**
   - `TODO_FORMAT_VERSION = 3`, `TODO_READ_FORMATS = (1, 2, 3)`, `RECOVER_FORMAT = 3`.
     Update the module comment and the wrapper header's FORMAT paragraph (current state only).
   - `parse_todo`: next to the `PUSH_REF_FORMAT` gate, `store.format < RECOVER_FORMAT`
     and a `recover:` ref → `FormatError(... "recover refs need format=3 ...")` at the
     item line. In the context loop, a parsed entry carrying `incarnation`
     in a file below format 3 → `FormatError` at the entry's origin line.
   - `_commit_todo` already renders the current format. A no-op leaves v1/v2
     byte-identical, because ops call it only on change (asserted in 16b/16d).
4. **`op_recovery_apply`** (core).
   Arguments: `--ref` (required; must parse as recover, else exit 2),
   `--expect-rev` (`absent` or a positive int; required), `--incarnation` (12 hex;
   required), `--state open|unknown|done` (required), `--outcome` (required,
   `_single_line`, ≤200, no `|`), `--title`, `--group` (optional),
   `--checked-at now|<ts>` (required), `--input` (context; optional).

   Order:
   1. Validate every argument; parse the context (`validate_context_input`). If a
      context is given, its origin `incarnation` must be present and equal to
      `--incarnation`, else exit 2. Return here on `--check-only`.
   2. `load_todo`; `owner = _ref_owner(store, ref)`.

   | case | result |
   |---|---|
   | `absent`, owner exists | `STALE:c<owner>\|<rev>` |
   | `absent`, no owner | require a context and `--title` (exit 2 otherwise). `alloc_id`, `Revs`, a new `Item(kind=task, derived=script, group=--group or next)`, `_check_context_values` against the store, `_check_related` → `ADDED:c<N>\|<rev>` + `@NEXT_ID` |
   | int rev, no owner | `ABSENT:<ref>` (nothing written; the caller re-reads) |
   | int rev ≠ item rev | `STALE:c<N>\|<rev>` |
   | item dismissed, no context given | `KEPT:c<N>\|dismissed` |
   | item dismissed, no recorded incarnation | `KEPT:c<N>\|dismissed_no_incarnation` |
   | item dismissed, recorded == given | `KEPT:c<N>\|dismissed` |
   | item dismissed, differs, `--state` ≠ open | `KEPT:c<N>\|dismissed` |
   | item dismissed, differs, `--state open`, context | apply all → `REOPENED:c<N>\|<rev>` |
   | item not dismissed, given ≠ recorded (or none recorded) and no context | exit 2: a new incarnation needs its context, or a later dismissal would be scoped to the old episode (contract below) |
   | item done, `--state open` | apply all → `REOPENED:c<N>\|<rev>` |
   | otherwise (open/unknown, or done with state ≠ open) | apply all → `APPLIED:c<N>\|<rev>`, or `UNCHANGED:c<N>\|<rev>` when nothing differs |

   "Apply all": `_apply(item, revs, state, outcome, checked_at, title?, group?)`.
   If the context changed, replace it and take the fresh rev if `_apply` did not
   already (one rev per write, as `op_upsert_context` does). Then ONE
   `_commit_todo`. Never touch `derived`, `kind` or `ref`. Validate the
   context against the store (`_check_context_values(entry, args.store)`, `_check_related`)
   before mutating.

   **Caller contract: two different keys (t2299_2 handoff).** `--incarnation`
   names the episode that the *recorded evidence* belongs to. That is not
   necessarily the lock key the caller just observed:
   - **With a context** (create, evidence refresh, reopen): `--incarnation` =
     the context's origin `incarnation` = the observed episode key. This is the
     only way a recorded incarnation changes.
   - **Without a context** (a state-only verdict, e.g. `done` because a live
     claim B now holds the task, or `unknown`): `--incarnation` = the item's
     **recorded** incarnation, read back from `context c<N>`, never the observed
     key. The item's context (and so its recorded episode A) is left
     byte-identical. When B later crashes, the caller sends B's context with
     `--state open` → `REOPENED`, recorded incarnation becomes B.
   - Passing the observed key without a context is refused (exit 2) on purpose:
     it would claim episode B while keeping A's evidence, and a later dismissal
     would then be scoped to the wrong episode.
   The writer cannot tell the two cases apart from the flag alone, so this
   contract is written into the wrapper header's `recovery-apply` entry and
   sent to t2299_2 as a note (step 10). t2299_2's apply loop step 6.3 ("done or
   unknown … state and outcome only, no context") must pass the recorded key.
4b. **Side-path guards (one writer for recover items).**
   - `op_add`: a `recover:` ref → exit 2 ("recover items are written by
     recovery-apply").
   - `op_update`: setting `--ref` to a `recover:` ref, changing the ref of an item
     that holds one, or `--kind` ≠ task on such an item → exit 2.
   - `op_upsert_context` on an item with a `recover:` ref: the new entry's
     incarnation must equal the recorded one (missing or different → exit 2).
     The incarnation changes only through `recovery-apply`.
   - `set-state` / `dismiss` / `set-state --batch` stay as they are. Dismissing
     is the user's, and a batch already KEEPs dismissed items.
5. **Wrapper** (`aitask_sitrep_todo.sh`).
   - `cmd_recovery_apply`: flag loop like `cmd_add` for `--ref --expect-rev
     --incarnation --state --outcome --title --group --checked-at`;
     `--context-file -` → `read_stdin` + `--input -`; then `precheck` and `mutate todo recovery-apply`.
   - Dispatch entry `recovery-apply)`; a usage line; header contract lines (verb,
     result lines ADDED/APPLIED/UNCHANGED/REOPENED/STALE/ABSENT/KEPT, the
     `recover:` ref, exit 0/2/3/4); the `Refs:` line gains `recover:t<N>[_<M>]`.
   - argparse: `mk("recovery-apply", op_recovery_apply, True, True)` with the
     flags. `--expect-rev` is a string (parsed in the op: `absent` or an int).
6. **Refresh exclusion** (`lib/sitrep_refresh.py` `select_targets`): before the
   task branch, `if it.kind == "task" and st.parse_recover_ref(it.ref): continue`
   with a comment saying t2299_3 adds `check="recovery"`.
7. **Ref-consumer inventory**: re-run the grep at implementation time, confirm
   the verification record above, and list it in Final Implementation Notes.
8. **Fixtures.**
   - `cp -R tests/fixtures/sitrep/store tests/fixtures/sitrep/store_v2`, and copy
     `expected_list.txt` → `expected_list_v2.txt`.
   - Build the new `store/` with the real writer on a scratch copy:
     `recovery-apply --expect-rev absent` for `recover:t42` (open, group now,
     outcome `crashed · plan approved`, origin `task=t42 incarnation=0123456789ab`)
     and for `recover:t43`, then `dismiss` it. Copy the result back in
     (todo.md, next_id, next_rev; .bak excluded as today). Pin `AITASK_SITREP_NOW`.
   - Regenerate `expected_list.txt` (and `expected_check_sources.txt`,
     `expected_context_c1.txt` only if they change) with the writer.
     Review every diff by hand.
9. **Tests.**
   - `tests/test_sitrep_todo.sh`:
     - T16: the format assertion becomes 3.
     - T16b: the upgrade lands on format=3.
     - New **T16d**: `store_v2` is read byte-identical; `list --machine` ==
       `expected_list_v2.txt`; a no-op update leaves it byte-identical; a changing
       update upgrades line 2 to format=3, every other line except the touched item unchanged.
       A v2 file with a hand-inserted `recover:` item, and one with an `incarnation`
       origin, → exit 4.
     - New **T17** recovery-apply matrix: one assertion per row of the step-4 table.
       Also: a non-recover ref → exit 2; a context/flag incarnation mismatch → exit 2;
       a bad incarnation value (11 hex, upper case, non-hex) → exit 2; an absent
       create without context or title → exit 2; the 4b guards (`add --ref recover:`,
       `update --ref recover:`, `update --kind action` on a recover item,
       `upsert-context` with a different/missing incarnation) → exit 2;
       a dismissed NON-recover item is unaffected (`set-state --batch` → KEPT);
       a reopen and its new context land in one generation (one rev, `.bak` = the prior generation).
       Every refusal asserts todo.md is unchanged.
     - **Episode handoff sequence** (the t2299_2 contract, one focused test):
       create `recover:t50` open with context incarnation A → a state-only
       `--state done --incarnation A` (no context) → `APPLIED`, state done, the
       `### c<N>` context block byte-identical (still A). Negative control: the
       same state-only call with `--incarnation B` → exit 2, todo.md unchanged.
       Then `--state open --incarnation B` with B's context → `REOPENED`,
       recorded incarnation now B. Then `dismiss`, and a repeat of the B apply →
       `KEPT:c<N>|dismissed` (the dismissal is scoped to B).
     - Atomic-write property: `park_and_kill write:after_backup` on a
       `recovery-apply` reopen → todo.md is still the old generation, and the next
       writer succeeds.
   - `tests/test_sitrep_todo_format.py`: the version tests move to 3.
     `test_future_format` uses `format=4`. Add the recover grammar
     (good/bad spellings), the kind binding at parse, a v2 file with recover/incarnation refused,
     and the round trip of the new fixture.
   - `tests/test_sitrep_refresh.py`: `select_targets` skips an open recover item
     and still selects a plain `t<N>` task.

10. **Sibling handoff** (after the tests pass, before the Step 8 commit): send
    t2299_2 a durable note with the `/aitask-note` skill
    (`./ait note 2299_2 --from 2299_1 --with-live --file -`). It says that state-only
    verdicts (`done` / `unknown`, no context) must pass the item's recorded
    incarnation (from `context c<N>`), not the observed lock key; that the
    observed key goes only with a context; that a mismatch exits 2; and it names
    the T17 handoff-sequence test as the pinned contract. The verb's result
    lines include `ABSENT:<ref>`, which its reply mapping (its step 6.4) should
    handle.

### Post-phase (risk mitigations)

1. [recover_writepath_guard_matrix] In `tests/test_sitrep_todo.sh`, add a
   table-driven section (inside T17) over a store holding one open recover item
   with a recorded incarnation. For every mutating verb other than
   `recovery-apply` (`add`, `update`, `upsert-context`, `set-state`,
   `dismiss`, `set-state --batch`, `situation`, `qa`), run the verb in the way
   most likely to touch the recover item. Assert either exit 2 with todo.md
   unchanged, or success with the item's `ref=` and its context's
   `incarnation=` byte-identical to before. Then assert that only
   `recovery-apply` (the new-incarnation reopen row) changes the recorded
   incarnation.
2. [fixture_diff_audit] After step 8, run
   `diff tests/fixtures/sitrep/store_v2/todo.md tests/fixtures/sitrep/store/todo.md`
   and `diff tests/fixtures/sitrep/expected_list_v2.txt tests/fixtures/sitrep/expected_list.txt`.
   The only allowed differences are line 2 (`format=2` → `format=3`), the
   added c7/c8 item lines, and their `### c7` / `### c8` context blocks.
   `expected_context_c1.txt` and `expected_check_sources.txt` must be
   unchanged (`git diff --exit-code` on both). Record both diffs verbatim in
   Final Implementation Notes.

## Verification

- `bash tests/test_sitrep_todo.sh`
- `python3 -m pytest tests/test_sitrep_todo_format.py tests/test_sitrep_refresh.py tests/test_sitrep_corpus.py tests/test_sitrep_tui_app.py tests/test_sitrep_tui_actions.py tests/test_monitor_sitrep_refresh.py -q`
  (the TUI and monitor tests share the store model)
- `bash tests/test_sitrep_refresh.sh`, `bash tests/test_sitrep_harvest.sh`,
  `bash tests/test_sitrep_corpus.sh`, `python3 -m pytest tests/test_sitrep_harvest.py tests/test_sitrep_corpus_fixtures.py -q`
  (consumers of the writer)
- `shellcheck .aitask-scripts/aitask_sitrep_todo.sh`

## Risk

### Code-health risk: medium
- The format bump makes older framework code that reads this store (e.g. a linked worktree on an old checkout) report "unsupported format". This is the same trade-off `push:` accepted. · severity: low · → mitigation: none (accepted)
- `recovery-apply` is a second write path for item state beside `set-state`, and other verbs could write a `recover:` item or its incarnation behind its back, which would break the episode-scoped dismissal. · severity: low (residual: the step 4b guards are pinned by the inline post-phase recover_writepath_guard_matrix) · → mitigation: inline post-phase recover_writepath_guard_matrix
- Fixture regeneration can silently change expected outputs that other suites rely on. · severity: low (residual: addressed by the inline post-phase fixture_diff_audit) · → mitigation: inline post-phase fixture_diff_audit

### Goal-achievement risk: low
- The no-context incarnation guard conflicts with t2299_2's planned apply loop, which sends state-only `done`/`unknown` verdicts with the newly observed key. That would leave a stale crash item open. · severity: low (residual: resolved by the step 4 caller contract, the T17 episode-handoff test and the step 10 note to t2299_2) · → mitigation: none (addressed in-plan, user review 2026-11-15)

### Planned mitigations
- timing: post-phase | name: recover_writepath_guard_matrix | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: second write path / dismissal leak | desc: table-driven test that every non-recovery-apply mutating verb refuses or preserves a recover item's ref and incarnation
- timing: post-phase | name: fixture_diff_audit | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: fixture regeneration drift | desc: diff the regenerated fixture against store_v2 and allow only the format line and the c7/c8 additions

## Step 9

Post-implementation: commit only this task's paths (`feature: … (t2299_1)`),
then archive through Step 9. Never `git restore` / `stash` / checkout: the tree
holds other crashed tasks' hunks.

## Final Implementation Notes

- **Actual work done:** Implemented as planned. In `lib/sitrep_todo.py`:
  - `RECOVER_REF_RE`, `INCARNATION_RE`, `parse_recover_ref` and `context_incarnation`;
  - the kind binding in `_check_item_values`;
  - format 3 (`RECOVER_FORMAT`), with item-line and origin-line gates in `parse_todo`;
  - `_parse_expect_rev` and `op_recovery_apply`;
  - the 4b side-path guards in `op_add`, `op_update` and `op_upsert_context`.

  The wrapper gained `cmd_recovery_apply`, its dispatch, its usage line, and header contract lines covering the two-key rule. `select_targets` skips recover items. The fixtures and tests are as in steps 8 and 9 plus the post-phase. The note to t2299_2 was sent as `2026-11-15T14:35:19Z.8064b4670be300333b50718d` (`LIVE_NONE:unlocked`).
- **Deviations from plan:**
  - The user's plan review added the caller contract with two keys (a state-only apply passes the RECORDED incarnation), Test 17b and the step 10 note to t2299_2.
  - Test numbering is 16d / 17 / 17b / 17c (guard matrix) / 17d (atomic kill), because 16c already existed.
  - `--state dismissed` is refused by recovery-apply (only open/unknown/done), so dismissal stays the user's.
- **Issues encountered:** None. `shellcheck` reports SC1091 "not following" info notices unless it runs from `.aitask-scripts/` with `-x`, where it is clean.
- **Key decisions:**
  - `ABSENT:<ref>` (exit 0, nothing written) is the reply when a numeric rev is given but no item holds the ref.
  - A context-only change on recovery-apply takes exactly one fresh rev.
  - `recovery-apply` never touches `derived`, `kind` or `ref`.
  - The dismissed checks (`KEPT`) run before the no-context incarnation guard, so a dismissed item is never an exit 2.
- **Ref-consumer inventory (step 7, re-grepped at implementation time):**
  - `lib/sitrep_corpus.py` `ref_owner`/`normalize_ref`: only its own `t<N>` refs; no change.
  - `lib/sitrep_harvest.py` `ref_owner`/`_known`: only `t<N>` refs; a recover item never blocks a harvest `t<N>` item (different ref); no change.
  - `lib/sitrep_refresh.py`: `select_targets` now skips recover items, so `check_task` is never reached for them.
  - `sitrep_tui/sitrep_tui_model.py`: `classify` gives `pick_noref`, `_fields` gives no pick id, and `task_ref_id` gives None (its `_LOCAL_REF_RE` anchors `^t`). t2299_3 owns the real routing.
  - `sitrep_tui/sitrep_tui_actions.py` and `sitrep_tui_app.py`: these call `task_ref_id`, so they get None and recover items are not pickable yet.
  - `lib/sitrep_cli.py`: no ref handling.
- **Fixture diff audit (post-phase 2):**
  - `store_v2/todo.md` → `store/todo.md`: line 2 changes `format=2` → `format=3`; adds the `- c7 | rev=9 | … ref=recover:t42 …` and `- c8 | rev=11 | … state=dismissed … ref=recover:t43 …` lines and their `### c7` / `### c8` context blocks (incarnations `0123456789ab` and `89abcdef0123`).
  - `expected_list_v2.txt` → `expected_list.txt`: adds the `ITEM:c7|9|…` and `ITEM:c8|11|…` lines.
  - `expected_context_c1.txt` and `expected_check_sources.txt` are unchanged.
- **Mutant checks (isolated scratch copy):**
  - Removing the no-context incarnation guard fails 3 assertions (Test 17b).
  - Removing the upsert-context incarnation guard fails 4 assertions (Test 17c).
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t2299_2: see the note above.
    - State-only verdicts pass the recorded incarnation, read with `context c<N>` / `context_incarnation`.
    - The observed key goes only with its context.
    - Replies include `ABSENT:`.
    - Creates need `--title` and a context.
    - The group defaults to `next`.
  - t2299_3: add `check="recovery"` where `select_targets` now `continue`s, and route the TUI pick using `st.parse_recover_ref` (task_ref_id is None for recover items today).
  - t2299_4: `aidocs/framework/sitrep.md` should describe format 3, the `recover:` ref, the incarnation key and the one-writer rule for recover items.
