---
Task: t2254_archive_child_flow_reason_leaks_to_parent.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2254 — Keep the archive reason on the flagged task, not its auto-archived parent

## Context

`aitask_archive.sh` takes `--superseded` / `--obsolete` for ONE task, but
`archive_metadata_update` reads the script-global `SUPERSEDED` / `OBSOLETE`
flags. In `archive_child`, when the archived child was the parent's last
pending child, the parent is archived in the same run through the same helper
(`aitask_archive.sh:595`) and inherits the child's `archived_reason`. A parent
whose other children landed as completed work is then:

- reported `dropped` instead of `landed` by `relations_consume.end_state`
  (`.aitask-scripts/lib/relations_consume.py:424`, task_relations.md D8);
- skipped by `fire_landed_triggers` (`aitask_archive.sh:899`), which returns
  early on the global flags, so `obsolescence landed <parent>` never fires.

Callers that hit this: the board's child Delete/Archive flow
(`board/aitask_board.py:6673`, `--superseded <id>`) and `ait obsolete review`
(`aitask_obsolete.sh:142`, `--obsolete <id>`).

**Rule (user decision): derive the parent's reason from its children.**
- The auto-archived parent is **completed work** when any of its children
  landed: this child (archived without a reason) or an archived sibling,
  whether its record is loose or bundled.
- It **takes this run's reason** only when every sibling record was read and
  none landed.
- When a record cannot be read (an unreadable loose file, a bundle that cannot
  be listed, an entry that cannot be extracted), "none landed" is unproven, and
  the parent falls back to completed work. The script then says it could not
  verify. It never claims that a child landed.

Bundled records are read with the existing archive primitives, not assumed from
the bundle's existence. `aitask_zip_old.sh` does not bundle `t<N>/` while
`aitasks/t<N>/` exists, but an orphaned parent that later regains children can
have bundled siblings. `cmd_unpack` removes an entry from its bundle when it
extracts it, so each record lives in exactly one place.

"Landed" has one definition: the one `end_state` reads and the D8 doc states.
It is an archived file with `status: Done`, no `archived_reason`, and (as the
trigger already requires) no `folded_into`.

No concurrent edits: `git status` is clean for every target file, and no other
`Implementing` task names them.

## Implementation steps

All code changes are in `.aitask-scripts/aitask_archive.sh`.

1. **Per-run reason, read once.** At the end of `parse_args`, after the
   mutual-exclusion check, derive a new global `ARCHIVE_REASON`
   (`""` | `superseded` | `obsolete`) from the two booleans with an `if/elif`
   block. Declare `ARCHIVE_REASON=""` in the Configuration block, with a comment
   saying it names the task the flag targets only. After this change
   `SUPERSEDED` / `OBSOLETE` are read only by `parse_args`.

2. **`archive_metadata_update <file> [reason]`.** Take the reason as an explicit
   `$2` (`local reason="${2:-}"`) and stop reading the globals. Keep the awk
   insertion `print "archived_reason: " r` byte-identical on its own line,
   because `tests/lib/docs_vocabulary_scan.py` OTHER_WRITERS pins that needle.
   The dry-run info line appends `, archived_reason=<r>` when a reason is set.
   Callers:
   - `archive_parent`: `archive_metadata_update "$task_file" "$ARCHIVE_REASON"`
   - `archive_child` (child): `archive_metadata_update "$child_task_file" "$ARCHIVE_REASON"`
   - `archive_child` (parent): `archive_metadata_update "$parent_task_file" "$parent_reason"` (step 4)

3. **New helpers**, placed before `archive_parent`. Every conditional is an
   explicit `if … fi`, never a trailing `[[ ]] && …`, so no non-zero status
   leaks from a function body under errexit.
   - `archived_file_landed <file>` — returns 0 iff the file passes `-f`, its
     `status` is `Done`, and `archived_reason` and `folded_into` are both empty
     (via `read_yaml_field … 2>/dev/null || true`). Its comment cites
     `end_state` / D8 as the single definition.
   - `parent_archive_decision <parent_num> <child_id> <child_reason>` prints
     exactly one line `<VERDICT>|<detail>` and **always returns 0** (it runs
     inside `$( )`):
     - empty `child_reason` → `LANDED|t<child_id>` with no scan, so normal runs
       are unchanged;
     - **loose records**: for each `$ARCHIVED_DIR/t<P>/t<P>_*_*.md`, take the
       sibling id from the basename (`^t(<P>_[0-9]+)_`) and skip this child.
       An unreadable file (`! -r`) records the first failure and continues.
       `archived_file_landed` → print `LANDED|t<sid>` and return;
     - **bundled records**: the candidate set is the one
       `_search_numbered_then_legacy` / `cmd_unpack` use. It is
       `archive_path_for_id "$P" "$ARCHIVED_DIR"`, its `.tar.gz` twin,
       `$ARCHIVED_DIR/old.tar.zst` and `$ARCHIVED_DIR/old.tar.gz`, each only if
       `-f`. For each bundle:
       - `rc=0; listing=$(_archive_list "$b") || rc=$?`. A non-zero `rc` records
         `unlistable bundle <b>` and moves on; `pipefail` carries a zstd failure
         out of the zst pipeline.
       - For each listed entry matching `(^|/)t<P>/t(<P>_[0-9]+)_[^/]*\.md$`
         (regex held in a variable), skip this child. Then run
         `_extract_from_archive "$b" "$entry"`: a non-zero status records
         `unextractable <entry> in <b>` and continues. Otherwise count the
         record as read and check it with `archived_file_landed
         "$_AIT_EXTRACT_RESULT"` → `LANDED|t<sid>` and return.
       - The extraction dir is tagged, and the owning shell's EXIT sweep
         (`_ait_archive_cleanup`, armed when `archive_utils.sh` is sourced)
         removes it.
     - end: any recorded failure → `UNVERIFIED|<first failure>`; otherwise
       `NONE_LANDED|<records read>`.
     Positive landed evidence wins even when another record failed to read.

4. **`archive_child` parent branch.** Declare `local parent_reason=""` next to
   `parent_plan_file` at the top of the function. In the
   `remaining_children`-empty branch, before the parent's metadata update, run
   `decision=$(parent_archive_decision "$parent_num" "$task_id" "$ARCHIVE_REASON") || decision=""`
   and split it at the first `|` into verdict and detail. Then:
   - `NONE_LANDED` → `parent_reason="$ARCHIVE_REASON"`; info "Parent
     t<P>: no child landed (<n> other archived child record(s) read) —
     archiving the parent as <reason> too."
   - `LANDED` → `parent_reason=""`. When `ARCHIVE_REASON` is set, info "Parent
     t<P>: t<sid> landed — archiving the parent as completed work."
   - anything else (`UNVERIFIED`, or an empty or garbled decision, which is the
     errexit-safe failure branch) → `parent_reason=""`; warn (stderr) "Parent
     t<P>: could not read every child record (<detail, or 'decision helper
     failed'>) — no proof that none landed, so the parent is archived as
     completed work." This message never says a child landed.
   Then call `archive_metadata_update "$parent_task_file" "$parent_reason"`.

5. **`LANDED_IDS` only for completed work.**
   - `archive_parent`: `if [[ -z "$ARCHIVE_REASON" ]]; then LANDED_IDS+=("$task_num"); fi`
   - `archive_child`: the child id when `ARCHIVE_REASON` is empty; the parent
     when `parent_archived == true && -z "$parent_reason"`.

6. **`fire_landed_triggers` decides per id.** Drop `SUPERSEDED` / `OBSOLETE`
   from the early return (keep `DRY_RUN` / `NO_COMMIT`). Replace the two
   per-file checks with `archived_file_landed "$file" || continue`. This keeps
   the file check as a second guard behind step 5, and adds the D8
   `status: Done` condition.

7. **Help text.** Keep the `--superseded` line containing `archived_reason`,
   which pins test 12c of `tests/test_docs_vocabulary_coverage.sh`. Add one
   indented line under `--obsolete`: "The reason goes on the named task only; a
   parent the child flow auto-archives takes it only when none of its children
   landed". Update the comment above `fire_landed_triggers` to match.

8. **Tests — `tests/test_archive_obsolete.sh`** (in-process counters, no
   subshells). Reuse `setup_project` / `task` / `commit_all`. Add an
   `archived_child <parent> <n> [reason]` writer for a loose archived sibling,
   and a `bundle <path> <entries…>` builder: stage files under
   `<tmp>/stage/t<P>/` and run `tar -czf` for `.tar.gz`, or `tar -cf - -C stage
   . | zstd -q -o` for `.tar.zst`. That is the same `./t<P>/…` member shape
   `aitask_zip_old.sh` writes. Cases:
   - `test_child_reason_stays_on_child`: for each of `superseded` / `obsolete`
     (parents 50, 51), loose sibling `t5x_1` landed, last child `t5x_2`
     archived `--<reason>`. Assert exit 0, the child carries
     `archived_reason: <reason>`, the parent archived file has `status: Done`
     and **no** `archived_reason`, CALLS == `obsolescence landed 5x`, and the
     output names `t5x_1 landed`.
   - `test_parent_inherits_when_no_child_landed`: loose sibling `t52_1`
     archived `superseded`, last child `--obsolete 52_2` → parent
     `archived_reason: obsolete`, CALLS empty, output says `no child landed`.
   - `test_single_child_parent_inherits`: only child `--superseded 53_1` →
     parent superseded, CALLS empty.
   - `test_all_dropped_bundle_parent_inherits`: no loose siblings. The numbered
     bundle `aitasks/archived/_b0/old0.tar.zst` holds `t54_1` (superseded) and
     `t54_2` (obsolete); `--obsolete 54_3` → parent `archived_reason: obsolete`,
     CALLS empty, output `2 other archived child record(s) read`.
   - `test_bundled_landed_sibling_keeps_parent_completed`: loose sibling
     `t56_1` dropped (superseded); the legacy `aitasks/archived/old.tar.gz`
     holds a landed `t56_2`; `--obsolete 56_3` → parent has no reason, CALLS ==
     `obsolescence landed 56`, output names `t56_2 landed`.
   - `test_unreadable_bundle_falls_back_to_completed`: garbage bytes at
     `aitasks/archived/old.tar.gz`, only child `--obsolete 57_1` → exit 0, the
     parent has no reason, stderr carries `could not read every child record`,
     output does **not** contain `landed — archiving` (no false landed claim),
     CALLS == `obsolescence landed 57`.
   - Extend `test_dry_run_fires_nothing` with `--dry-run --obsolete`, asserting
     the output carries `archived_reason=obsolete`.
   - Register the new functions in the run list.

9. **Docs (current-state wording only).**
   - `aidocs/framework/task_relations.md`: update the `landed` trigger row
     (~line 620) and "The landed trigger" bullets (~1487-1488). The decision is
     per archived id, read from its archived file, and the task a
     `--superseded` / `--obsolete` flag names fires nothing. Add the
     auto-archived-parent rule: it is completed work and fires when any child
     landed, with loose and bundled records both read. It takes the run's
     reason only when every record was read and none landed. A record that
     cannot be read leaves that unproven, so the parent is completed work.
   - `website/content/docs/development/task-format.md`, `archived_reason` row:
     the reason is written on the task the flag names; a parent the child flow
     auto-archives takes it only when none of its children landed.
   - `website/content/docs/concepts/parent-child.md` line 11: add one clause.
     The auto-archived parent counts as completed work when any child was
     completed, and is marked superseded / obsolete only when none was.

### Post-phase (risk mitigations)

1. [archive_errexit_sweep] Add `test_flagged_child_with_siblings_left` to
   `tests/test_archive_obsolete.sh`: parent `t55` with
   `children_to_implement: [t55_1, t55_2]`, `--superseded 55_1`. Assert exit 0,
   HEAD advanced by one commit, the child archived file carries
   `archived_reason: superseded`, `aitasks/t55_parent.md` is still active with
   no `archived_reason`, and CALLS is empty. Then run the archive family
   (every `tests/test_archive*.sh` + `tests/test_docs_vocabulary_coverage.sh`)
   twice. First run it in a scratch detached worktree at HEAD (the baseline;
   new test files are not copied in). Then run it on the fixed tree. Compare
   the sets of FAIL assertion descriptions per file, not exit codes. Any
   description failing only on the fixed tree is a regression and blocks the
   commit.

## Verification

- `bash tests/test_archive_obsolete.sh`: all pass.
- **Red proof:** in a scratch detached worktree at HEAD (scratchpad; never
  stash or restore the shared tree), copy in the new test file only and run it.
  `test_child_reason_stays_on_child`, `test_bundled_landed_sibling_keeps_parent_completed`
  and `test_unreadable_bundle_falls_back_to_completed` must FAIL there (pre-fix:
  the parent inherits the reason, no landed call). The "inherits" cases pass
  pre-fix too; they guard the rule's other half, not the defect.
- **Guard-specific mutants** (scratch copies of the fixed script, run in that
  scratch worktree):
  - (a) skip the bundled-records scan → only
    `test_bundled_landed_sibling_keeps_parent_completed` fails;
  - (b) treat any bundle that lists a sibling as `UNVERIFIED` without reading
    it (the shape the review rejected) → only
    `test_all_dropped_bundle_parent_inherits` fails.

## Implementation progress (all steps done)

- Steps 1-9 and the post-phase are implemented as planned.
- Plan review fix: bundled sibling records are READ via `_archive_list` +
  `_extract_from_archive`. `UNVERIFIED` is used only on an actual read failure,
  and its warning never claims that a child landed.
- **Deviation — mutant predictions were imprecise.** Each mutant fails its
  target case's state assertions *and* one message assertion in the other
  bundle case:
  - (a) skip entry extraction: the bundled-landed case fails on state (parent
    took the reason, no landed call) and the all-dropped case fails on its
    record count (`2 … read`);
  - (b) existence-only: the all-dropped case fails on state (parent lost its
    reason, fired `landed 54`) and the bundled-landed case fails on `names the
    bundled landed sibling`. That second failure confirms that an uncertain
    verdict never claims a landing.
- **Red proof** (new test file vs the HEAD script): 16/66 fail. These are the
  defect assertions in the landed-sibling, bundled-landed and unreadable-bundle
  cases, plus the new message assertions. The "inherits" cases' state
  assertions pass pre-fix, as expected.
- **archive_errexit_sweep:** every `tests/test_archive*.sh` (12 files) plus
  `test_docs_vocabulary_coverage.sh`, run on the fixed tree: 0 FAIL
  descriptions. Baseline (scratch HEAD worktree): 0, apart from 2
  environmental vocab failures, where the live-repo scan crashes because the
  worktree has no `aitasks/`. Nothing fails only on the fixed tree.
- Other checks:
  - `tests/test_board_task_op_worker_groups.py`: 9 passed;
  - vocab re-run after the doc edits: 32/32;
  - `check_links.py --build`: PASSED;
  - shellcheck findings identical to HEAD (info-level only);
  - no `ait-archive.*` temp dirs left after the runs.
- Environment: `/tmp` hit its per-user tmpfs quota mid-run. With the user's
  approval, stale `/tmp/tmp.*` dirs (>1 day) and Claude session temp dirs
  (>2 days, judged by the newest file inside) were removed, freeing ~9G.
- The whole archive family (see the post-phase), plus
  `tests/test_board_task_op_worker_groups.py` via the Python runner's
  `--test-dir` or unittest.
- `shellcheck .aitask-scripts/aitask_archive.sh`.
- `cd website && python3 check_links.py --build` (mandatory after a website edit).

## Step 9 (Post-Implementation)

Commit the code and docs with
`bug: Keep the archive reason on the flagged child, not its auto-archived parent (t2254)`,
naming the paths explicitly. Then use the workflow's Step 9: archive t2254 with
`aitask_archive.sh` and push via `./ait git push`.

## Risk

### Code-health risk: medium
- `aitask_archive.sh` is a load-bearing path. A new conditional or `$( )` helper
  that returns non-zero under `set -e` after `archive_move` but before the
  commit would leave a half-done archival (files moved, nothing committed).
  The plan uses explicit `if` forms, an always-0 decision helper and a
  `|| decision=""` failure branch, and every new case asserts exit 0 plus the
  commit. · severity: medium · → mitigation: inline post-phase archive_errexit_sweep
- Reading bundled records adds extraction through `_extract_from_archive`
  inside `$( )`. It relies on the tag-swept temp dirs, the same route
  `resolve_task_file` already takes. · severity: low · → mitigation: none proposed (in-plan)
- `archive_metadata_update`'s signature changes. All three call sites are in
  this file and are updated together. · severity: low · → mitigation: none proposed (in-plan)

### Goal-achievement risk: low
- A record that cannot be read makes "none landed" unproven, so the parent is
  archived as completed work. In that failure case an all-dropped parent reads
  as landed. The error is advisory, it is announced on stderr, and it is
  covered by `test_unreadable_bundle_falls_back_to_completed`. · severity: low · → mitigation: none proposed (in-plan)

### Planned mitigations
- timing: post-phase | name: archive_errexit_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — errexit leak leaving a half-done archival | desc: flagged-child-with-siblings-left regression case + baseline-vs-fixed failing-assertion comparison over the archive test family

## Post-Review Changes

### Change Request 1 (2026-11-09 17:50)
- **Requested by user:**
  1. (medium, blocking) `parent_archive_decision` scanned loose siblings and then bundles. A `cmd_unpack` handoff between the two scans (record copied loose, emptied bundle removed) hid a landed sibling from both, so the helper returned `NONE_LANDED|0` and the parent took the child's reason. Asked to detect the handoff or recheck before certifying `NONE_LANDED`, with a deterministic regression case.
  2. (low, follow-up) Each bundled sibling re-decompresses the archive through `_extract_from_archive`. Asked for a single-pass read as a separate improvement.
- **Changes made:**
  1. A scan order cannot fix this: `ait zip-old` and its unpack each write the new location before removing the old one, so the two directions need opposite orders. In `archive_child` the `aitasks/t<N>/` rmdir also runs before the decision, which makes a concurrent zip possible.
     - The scan now runs between two content fingerprints (`cksum`) of every evidence source: the loose `t<P>_*` records and the candidate bundles. `NONE_LANDED` is certified only when they match. Otherwise it re-scans, up to `PARENT_SCAN_ATTEMPTS=3`, and then reports `UNVERIFIED|child records kept changing during the scan (3 attempts)`. LANDED still wins at once.
     - Residual, documented in the comment: a change fully undone within one scan is not seen.
     - New test-only seam `AIT_ARCHIVE_PARENT_SCAN_HOOK` (pattern: `AIT_CAS_BEFORE_SWAP_HOOK`). It runs between the loose and bundle scans with `AIT_ARCHIVE_SCAN_ATTEMPT` exported, sends its output to stderr, and its status is ignored.
     - Two new cases. `test_unpack_handoff_between_scans_is_rechecked` simulates `cmd_unpack` on attempt 1; its witness log asserts the hook ran only on attempt 1 and the rescan found the record loose. `test_records_that_keep_changing_are_unverified` makes the hook alter a dropped record on every attempt and asserts 3 attempts, then UNVERIFIED and completed work with no landed claim.
     - Mutant c (stability check forced true) fails exactly those two cases. Mutants a and b behave as before, and the HEAD script fails the new cases.
     - `tests/test_archive_obsolete.sh`: 78/78 pass. Archive family re-run on the fixed tree: 13 files, 0 FAIL descriptions. Shellcheck findings identical to HEAD.
     - `task_relations.md` landed-trigger bullets now state the stable-view requirement.
  2. Filed as follow-up **t2263** (performance, low): single-pass bundle read, with a decompression-count test.
- **Files affected:** `.aitask-scripts/aitask_archive.sh`, `tests/test_archive_obsolete.sh`, `aidocs/framework/task_relations.md`

### Change Request 2 (2026-11-09 18:05)
- **Requested by user:** (low, follow-up) The `before` fingerprint runs ahead of the loose scan and checksums every candidate bundle, even when a loose landed sibling immediately proves LANDED. A probe confirmed this. t2263 wrongly said the loose-record path was unaffected. Asked to extend t2263 to cover the cost and correct that assumption; positive loose evidence could be accepted before hashing bundles, while keeping the stability check before a negative verdict.
- **Changes made:** Verified in the code (`before=$(_child_evidence_fingerprint …)` sits at the top of each attempt). t2263 was rewritten with two findings and the assumption corrected:
  - its approach accepts positive loose evidence before any fingerprint, while a full re-scan stays bracketed before `NONE_LANDED`;
  - its verification adds a zero-bundle-reads assertion for the loose-positive path and re-runs mutant c.
  - Committed: "ait: Extend t2263 with the loose-positive fingerprint cost".
  - No code change in t2254; the disposition was follow-up.
- **Files affected:** `aitasks/t2263_archive_parent_decision_single_pass_bundle_read.md`

## Final Implementation Notes
- **Actual work done:**
  - `aitask_archive.sh`:
    - The per-run `ARCHIVE_REASON` is derived once in `parse_args`.
    - `archive_metadata_update <file> [reason]` takes the reason explicitly. The awk `print "archived_reason: "` needle is kept for the docs-vocabulary registry.
    - New `archived_file_landed`: the single "landed" definition (Done, no `archived_reason`, no `folded_into`).
    - New `parent_archive_decision`: LANDED / NONE_LANDED / UNVERIFIED over loose and bundled sibling records, read via `_archive_list` + `_extract_from_archive`. A stability loop brackets the scan with `cksum` fingerprints, up to `PARENT_SCAN_ATTEMPTS=3`.
    - `archive_child` decides the parent's own reason, with distinct info/warn messages per verdict.
    - `LANDED_IDS` takes only completed work.
    - `fire_landed_triggers` decides per archived file.
    - Help text updated; test-only seam `AIT_ARCHIVE_PARENT_SCAN_HOOK` added.
  - Tests: 9 new cases plus a dry-run assertion in `tests/test_archive_obsolete.sh` (78/78).
  - Docs: `aidocs/framework/task_relations.md` (landed trigger), website `task-format.md` (`archived_reason` row) and `concepts/parent-child.md`.
- **Deviations from plan:**
  - Plan review: bundled records are read, not inferred from the bundle's existence. The uncertainty fallback is used only on real read failures, and its message never claims a child landed.
  - Change Request 1: added the fingerprint stability loop and the test seam.
  - The mutant predictions were imprecise: each mutant also fails one message assertion in the sibling bundle case (see "Implementation progress").
- **Issues encountered:**
  - `/tmp` (tmpfs) hit its per-user quota mid-verification. With the user's approval, stale `/tmp/tmp.*` dirs and old Claude session temp dirs were removed (about 9G).
  - Baseline-worktree vocab failures were environmental: the scratch worktree has no `aitasks/`.
- **Key decisions:**
  - User rule: derive the parent's reason from its children. Positive landed evidence wins at once and needs no stable view.
  - `NONE_LANDED` needs every record read **and** a stable view.
  - Unproven → completed work, with a stderr warning.
  - Free-text info/warn only; no new structured stdout line, so the skill parsers are unchanged.
  - The code-agent trailer comes from `ait codeagent coauthor`.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_zip_old.sh:386-393` — `cmd_unpack`'s `search_list` omits the numbered `.tar.gz` twin (`_bN/oldM.tar.gz`) that `_find_archive_for_task` / `_search_numbered_then_legacy` fall back to (`lib/archive_utils.sh:345`). `ait zip-old unpack <N>` therefore cannot restore a task from a numbered `.tar.gz` bundle that the resolvers can still read.
- **Follow-ups:** t2263 (performance, low) covers the single-pass bundle read and accepting loose positive evidence before any bundle hashing.
