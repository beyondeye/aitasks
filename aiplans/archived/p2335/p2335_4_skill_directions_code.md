---
Task: t2335_4_skill_directions_code.md
Parent Task: aitasks/t2335_sitrep_work_directions.md
Sibling Tasks: aitasks/t2335/t2335_5_tui_directions_tab.md, aitasks/t2335/t2335_6_manual_verification_work_directions.md
Archived Sibling Plans: aiplans/archived/p2335/p2335_1_store_direction_records_format_4.md, aiplans/archived/p2335/p2335_2_refresh_direction_freshness.md, aiplans/archived/p2335/p2335_3_trails_highlight_and_critical_path_overlay.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2335_4 — sitrep skill: the `>d` directions code

## Context

Work directions are a ranked set of lines of work in the sitrep store. The store
verbs (t2335_1), the refresh verdict and the two proposal reads (t2335_2) and the
trail critical-path verb (t2335_3) have landed. Nothing creates or maintains
directions yet. This child adds that to the sitrep skill: a `>d` code that
proposes the grouping, records and one ranked order, confirms once and saves
through the writer; direction-aware `>q`, `>p` and `>w`; and the docs.

Contracts this plan builds on (read them before editing):

- `aidocs/framework/sitrep.md`: "Directions" (record, membership, baseline
  evidence, "The freshness verdict", "Saving a proposal") and "The skill".
- Header of `.aitask-scripts/aitask_sitrep_todo.sh` (wire lines of `directions`,
  `direction-assign --batch`, `direction-set`, `direction-rank`,
  `direction-remove`).
- Header of `.aitask-scripts/aitask_sitrep_refresh.sh` ("PROPOSAL VERBS":
  `snapshot`, `recheck`).
- Module docstring of `.aitask-scripts/lib/trail_gather.py`, "CRITICAL PATH".
- `aidocs/framework/skill_authoring_conventions.md` (goldens, NON-SKIPPABLE
  banner, the AskUserQuestion visibility rule) and `stub-skill-pattern.md`.

### Decisions taken during planning (user-confirmed 2026-11-27)

1. **Trail membership gets a read verb.** `>d` must say which trails hold a
   direction's tasks, and may offer `/aitask-trail` only when none does. Only the
   sitrep TUI computes that today, in-process. This task adds
   `aitask_trail_gather.sh membership --tasks <ids>` (the helper is already on
   the five allow-lists) and moves the TUI's pure derivation into `lib/` so the
   TUI and the verb share one code path.
2. **The "Requests from the sitrep TUI" line for `>d` stays with t2335_5.**
   Check r of `tests/test_sitrep_skill_contract.sh` refuses a code in that
   section that `AGENT_REQUESTS` does not have (`STALE_DOC_CODE`), and the row is
   t2335_5's. Here the `>d` capability carries its own fresh read and
   known-direction check, which hand-typed input needs anyway. t2335_5 gets a
   note with the exact line; the unchanged parity test forces it to add the line
   with its row. This deviates from the task text on purpose.

3. **A summary and its situation text are saved in one write** (added during
   plan review). `situation` is its own commit with no `--expect-rev`, so
   "`direction-set`, then `direction-rank`, then `situation`" can stop at a rank
   refusal with the new summary saved beside the old text. The store's writer
   gets a `--with-situation` form of `direction-set` (step 2b): record and text
   change together, or neither does. For the same reason `situation` gets an
   optional `--expect-rev`, checked under the lock, so `>w` cannot write a text
   that only agreed with a summary another session has since replaced. Both
   extend t2335_1's writer, in scope because the task requires that the two
   accounts never contradict.

### Facts found during exploration

- The skill directory may hold exactly `SKILL.md` and `SKILL.md.j2` (Test 0 of
  `tests/test_skill_render_aitask_sitrep.sh`), so `>d` is written inline, not as
  a procedure file.
- `tests/test_sitrep_skill_contract.sh` line 230 asserts the skill never names
  `aitask_sitrep_refresh.sh`. `>d` names it for `snapshot` / `recheck`, so that
  assertion is replaced by a stricter one (step 4).
- Check b of that test covers only `aitask_sitrep_todo.sh` and
  `aitask_sitrep.sh` verbs. It is extended to the two other helpers.
- All five helpers are already on the five allow-lists. No permission edit.
- `direction-set` resets freshness to `unknown` and never writes `current`; the
  refresh writes the verdict. After a save a direction reads `unknown` until the
  next refresh (the TUI's `r`, or the monitor's maintenance pass).
- A baseline lists members, task statuses, trail verdicts and the next pointer.
  Critical-path detail is not in it, so a saved summary must not quote it.
- A move is one `direction-assign` line naming the destination; it removes the
  item from its source direction and resets the freshness of both blocks.
- `direction-rank` refuses empty input unless `--clear` is given, and refuses
  `--clear` with input (`op_direction_rank` in `lib/sitrep_todo.py`).
- An item's group (Pick now / Next / Waiting) is stored, not computed. The
  picker's own verdict is `aitask_ls.sh -v --all-levels 9999`: Ready tasks at
  every level, each `Status: Ready`, `Status: Blocked (by …)`,
  `Blocked [unverified]` or `Has children`. `aitask_ls.sh` is on all five
  allow-lists.
- The store accepts cross-repo task refs (`<project>#<N>`); the membership scan
  covers the trails this project owns only.
- `snapshot` and `recheck` refuse empty input (`parse_proposal`: "no proposal
  lines on stdin", exit 2).
- A trail's `NEXT:` reads status `Ready` and the trail's blockers. A Ready
  parent with pending children can be `NEXT:` there while `ait ls` shows
  `Has children` and a pick opens child selection.
- `ait trails --highlight` refuses more than 256 distinct ids (`HIGHLIGHT_MAX`)
  and names the remedy: the first 256 plus `--highlight-total`. The launcher
  (`_prepare_trails_highlight`) normalises ids, drops duplicates in caller
  order and cuts the same way.
- Today's `>w` writes situation text unconditionally.
- `situation <direction>` takes no `--expect-rev` and commits by itself; every
  write to a block gives it a new rev (the rev covers the record and the
  situation text together).
- `directions` does not print situation text. It is in Part 1, read with
  `read todo` (the block under `#### <slug> | rev=<N>`, after its nine header
  lines).
- `ait trails` refuses a `--highlight-direction` longer than 512 characters
  (`HIGHLIGHT_DIRECTION_MAX`); the store's slug grammar has no such bound, and
  the launcher leaves an over-long slug out and still opens the highlight.
- `website/content/docs/workflows/sitrep.md` already has a three-sentence
  `## Work directions` section (lines 45-47). No page links to its anchor.
- t2199 (port of the sitrep operation to Codex / OpenCode) is `Implementing`
  since 2026-11-12 with no plan file. Its sections of `sitrep.md` ("Code
  agents") and of the skill page are not touched here. It needs nothing built
  for `>d` (the skill renders agent-invariant, Test 1b), only to include `>d`
  in its end-to-end check: a note, sent at step 9.

## Implementation steps

### Pre-phase (risk mitigations)

1. [baseline_tui_trail_tests] Before any edit of step 1, run
   `~/.aitask/venv/bin/python -m pytest -q tests/test_sitrep_tui_trails.py
   tests/test_sitrep_tui_trails_actions.py tests/test_sitrep_tui_app.py
   tests/test_sitrep_tui_actions.py` and record, per file, the passed / failed /
   skipped counts in this plan. After step 1 run the same command: every count
   must be identical (no test lost, none newly skipped). A difference stops the
   work until it is explained.

### 1. Shared trail-membership derivation: new `.aitask-scripts/lib/trail_membership.py`

Move, unchanged in behaviour, from
`.aitask-scripts/sitrep_tui/sitrep_tui_trails.py` into the new stdlib-plus-lib
module (no Textual import): the constants `IN, NONE, UNKNOWN, LOOKING, OFF`, the
dataclasses `TrailRef`, `TaskTrails`, `Membership`, the singletons
`TASK_TRAILS_OFF` / `TASK_TRAILS_LOOKING`, `_ordinals`, `membership_from_export`
and `scan_membership`.

`sitrep_tui_trails.py` then imports those names from `trail_membership` at
module level, so every existing reference keeps working (`trails_model.IN`,
`tt.TrailRef`, `tt.Membership`, `tt.membership_from_export`,
`tt.scan_membership`). Keep `TRAILS_RESCAN_INTERVAL` and the picker dialog in
the TUI module. Update the two module docstrings.

Patch-point check before moving: `tests/test_sitrep_tui_trails.py` patches
`trail_links.export_project` and calls `tt.scan_membership`; `scan_membership`
imports `trail_links` inside the function, so the patch still applies after the
move. Grep `tests/` and `sitrep_tui/` for `patch.object(tt,` /
`patch("sitrep_tui.sitrep_tui_trails.` before the move; a name patched on the
TUI module but resolved inside `trail_membership` needs its patch target moved.

### 2. The `membership` read verb

`.aitask-scripts/lib/trail_gather.py`:

- `build_parser`: `membership` with `--tasks` (required, "comma-separated task
  ids (12, t12_3, proj#12)").
- `main`: dispatch to `cmd_membership`.
- `cmd_membership(args, out=None)`:
  1. `local_name = local_project_name()` (exit 3 when unset, as for
     `critical-path`).
  2. Canonicalise every value with the existing `canonical_id`; a value that
     parses as neither prints `ERROR:bad_task:<value>` alone, exit 0 (the
     `bad_highlight` shape). Duplicates collapse in caller order.
  3. `import trail_membership` lazily, inside the function, so `snapshot`,
     `drift` and `critical-path` keep their import cost (the refresh runs
     `drift` once per trail). Call `trail_membership.scan_membership(os.getcwd())`:
     the same export subprocess, 30 s timeout and typed errors the TUI uses.
  4. Print the lines from a pure `membership_lines(membership, refs, local_name)`
     (unit-testable without a repository).
- Protocol, added to the module docstring next to "CRITICAL PATH" and to the
  verb list of `aitask_trail_gather.sh`'s header (`#   membership --tasks
  <id,id,...>`, which check b of the contract test reads):

  ```
  IN_TRAIL:<ref>|<handle>|<waves csv or ->|<trail name>     one per (task, trail); name LAST
  NO_TRAIL:<ref>                                            a COMPLETE scan found it in no trail
  UNKNOWN:<ref>|<reason>                                    see below
  MEMBERSHIP:in=<n>|none=<n>|unknown=<n>|scan=<complete|partial|failed>|<detail or ->   final
  ```

  `<ref>` is the canonical `<project>#<id>`, as in `critical-path`. Rules, the
  TUI's fail-closed ones:
  - `NO_TRAIL` only when the scan is complete. A partial scan that found
    nothing for a task is `UNKNOWN:<ref>|<the partial note>`.
  - A failed scan makes every ref `UNKNOWN` with the failure reason.
  - A task found in some trails during a partial scan keeps its `IN_TRAIL`
    lines; `scan=partial` on the final line says the list may be short.
  - A ref of another project is `UNKNOWN:<ref>|cross_repo_not_searched`:
    project names are never compared as strings (the `trail_links` rule).
  - The trail name is untrusted text: pass it through the sanitizer
    `critical_path_lines` uses for its free field.
- The wrapper needs no change beyond the header: `membership` takes no
  `--trail`, so the `art:` rewrite does not apply.

### 2b. The writer: a paired `direction-set` and a guarded `situation`

`.aitask-scripts/lib/sitrep_todo.py` and `.aitask-scripts/aitask_sitrep_todo.sh`.
Additive and gated on one new flag: without it, `direction-set` behaves exactly
as today.

- `direction-set … --summary-file - --digest H --with-situation`: stdin is the
  summary on line 1 and the situation text on the lines after it.
  - Shell (`cmd_direction_set`): accept `--with-situation`; it needs
    `--summary-file -` (else exit 2); pass it through.
  - Parser: `--with-situation` (`store_true`) on the `direction-set` subparser.
  - `op_direction_set`: with the flag, split the input at the first newline. The
    first line goes through the existing summary path and must be non-empty
    (exit 2 otherwise: the paired form saves a summary). The rest goes through
    `validate_situation`, the `situation` verb's own rule (at most 1200 bytes,
    no line starting with `#`, no carriage return); no line after the first
    clears the text. `new.situation` is set before the existing checks, so the
    `--expect-rev` check, the baseline check (`EVIDENCE_CHANGED`) and
    `is_empty` all cover the paired state, and ONE `_commit_todo` writes it.
  - The `unchanged` answer compares the header lines AND, with the flag, the
    situation text; a write that changes only the text answers `updated`.
  - Any refusal (`STALE:`, `ABSENT:`, `EVIDENCE_CHANGED:`, exit 2) writes
    neither part. Wire lines are unchanged.
- `situation <direction> [--expect-rev absent|<rev>]`: the optional guard.
  - Shell (`cmd_situation`) and parser: accept the flag and pass it through.
  - `op_situation`: when given, parse it with the existing `_parse_expect_rev`
    and check it with `_expect_direction(slug, d, expect)` right after
    `load_todo`, which runs under the store lock, before either branch (set and
    clear). A block whose rev differs, or `absent` against an existing block,
    answers `STALE:<slug>|<rev>`; a rev given for a direction with no block
    answers `ABSENT:<slug>`; nothing is written. Without the flag the verb
    behaves as today.
- Header of `aitask_sitrep_todo.sh`: the `direction-set` usage line gains
  `[--with-situation]` and three lines stating the rule above; the `situation`
  line gains `[--expect-rev absent|<rev>]` and its two refusal lines.
- Tests, in `tests/test_sitrep_todo.sh` (Test 18, `direction-set`), using the
  existing helpers (`set_summary`, `dir_rev`): a paired write sets summary,
  digest and text under one new rev; a paired write refused by a stale rev and
  one refused by `EVIDENCE_CHANGED` leave summary AND text byte-identical
  (`read todo` before and after); the flag without `--summary-file -`, an empty
  first line, a `#` line and an over-long text are exit 2 with nothing written;
  no line after the first clears the text and keeps the record; a paired write
  equal to the stored state is `unchanged` with the rev kept; and without the
  flag a two-line input is still refused as today (the control that the old
  path did not move). Mutant, in a scratch copy, recorded in the final notes:
  commit the summary before validating the text and show the "over-long text
  writes nothing" case fails.
- Tests for the `situation` guard, same file: the matching rev sets the text and
  the same call for a clear removes it; a stale rev is `STALE:` with the text
  and the rev unchanged, for set and for clear; `absent` writes the first text
  of a direction with no block and is `STALE:` against an existing block; a rev
  for a direction with no block is `ABSENT:`; without the flag every existing
  `situation` assertion still passes unmodified.
  **The interleaving**, sequential and deterministic: session one reads
  `directions` (rev R1) and `read todo`; session two saves a new pair with
  `direction-set … --with-situation` (rev R2); session one's
  `situation --expect-rev R1` answers `STALE:<slug>|R2` and `read todo` still
  shows session two's summary and text. Control: the same sequence with
  session one's call left unguarded overwrites the text, which is the defect
  the guard closes. Mutant, in a scratch copy: skip the `_expect_direction`
  call and show the interleaving case fails.

### 3. The skill template: `.claude/skills/aitask-sitrep/SKILL.md.j2`

Write in the template's existing style (80 columns, imperative, no Jinja beyond
the frontmatter). Strings other tests pin must survive: the eight advisory
sentences of check d (including `Never rank tasks yourself`), the mutant anchors
(`aitask_sitrep.sh root`, `aitask_sitrep_todo.sh list`, the `>tr` heading, the
`>p` request line, `  - trail: <HANDLE>`), and
``**`crashed-agents` is the direction of every crash-recovery item**``.
A helper name is followed by a space and a word only when that word is a verb
(check b reads `<helper>.sh <word>`).

**3a. Step 0.** Step 2 also runs `aitask_sitrep_todo.sh directions`. The greeting
gains one clause: the number of directions, how many read `stale` or `unknown`,
and the `UNASSIGNED` count. Keep "Do not harvest or refresh".

**3b. Writing.** Extend the verb list: `direction-assign`, `direction-set`
(with `--with-situation` when a summary and its situation text change
together), `direction-rank`, and `direction-remove` only on the user's explicit request to
delete a direction; plus the two proposal reads of
`./.aitask-scripts/aitask_sitrep_refresh.sh` (`snapshot`, `recheck`). State
that `direction-freshness` and `retain-baseline` are not agent verbs (the
refresh writes the verdict; `snapshot` retains the baseline), that
`direction-set` takes `--expect-rev absent` for a direction with no record
(`rev` `-`), and that `STALE:` / `STALE_ORDER:` / `EVIDENCE_CHANGED:` /
`ABSENT:` all mean "nothing written by that call: re-read, never retry blind".

**3c. New capability, between `>w` and `>q`:**
`` ### `>d [<direction>]` — work directions ``. Content, in this order:

*Opening.* A direction's record is its title, rank, linked trails, next step
and summary. A bare `>d` proposes the whole set: which pending items belong to
which direction, each record, and ONE ranked order. `>d <direction>`
re-summarises only that direction; its members and every rank stay. Freshness
(`current`, `stale`, `unknown`) is computed by the refresh, never by the agent.

1. **Read (code, not judgement).** `list`, then `directions` (bare) or
   `directions <direction>`; document the `DIRECTION:` field order,
   `DIRECTION_SUMMARY`, `DIRECTION_DRIFT`, `DIRECTION_MEMBER`,
   `UNASSIGNED:<n>|c1,c2`, `NO_DIRECTIONS`. `NOT_FOUND:<direction>` (exit 2):
   say what `directions` lists and write nothing. Then `context c<N>` for every
   pending member, and for a bare `>d` every unassigned item.
   **Also `aitask_sitrep_todo.sh read todo`, as part of this read.**
   `directions` does not print situation text; each direction's current text is
   the lines of its `#### <slug> | rev=<N>` block after the nine header lines.
   The rev in that heading must equal the one `directions` printed for the
   block; when it does not, the store moved between the two reads: read both
   again.
   Keep, per direction, the **state the proposal is drafted from**: its rev and
   its saved title, rank, trails, next, summary, digest and situation text.
   Step 7 compares against it.
2. **Trail evidence** for EVERY task ref of those items: `t<N>`, the task of a
   `recover:t<N>`, and a cross-repo `<project>#<N>` exactly as stored. None is
   left out: a ref that is not passed cannot be reported as unsearched.

   ```bash
   ./.aitask-scripts/aitask_trail_gather.sh membership --tasks <IDS>
   ./.aitask-scripts/aitask_trail_gather.sh critical-path --trail <HANDLE> --highlight <IDS>
   ```

   `membership` answers for the trails this project owns: `IN_TRAIL:`,
   `NO_TRAIL:` (only from a complete scan) or `UNKNOWN:<ref>|<reason>` per ref
   (a ref of another project is always `UNKNOWN`: its project's trails were not
   searched), then the final `MEMBERSHIP:…|scan=<complete|partial|failed>|…`.
   `critical-path` once per trail that holds at least one of a direction's
   tasks, highlighting that direction's ids. Consumer rules, condensed from the
   docstring: `NEXT:` is pick eligibility and carries the TRAIL's freshness
   word, which is not the direction's; `IN_PROGRESS:` / `ON_HOLD:` are not
   picks; `BLOCKER:` (transitive) and `BLOCKED_BY:` (direct) name what a task
   waits on; `OUTSIDE:` / `XDEP:` block and are not followed, and an `OUTSIDE`
   ref is never pick advice; `…|unresolved|bundled` means Done but bundled, so
   the dependent is not a pick; `NOT_IN_TRAIL:` has no readiness; a lone
   `ERROR:` line is reported as it is. The verb probes cross-repo statuses
   synchronously (10 s each): say so when a trail has many.
3. **Draft the proposal** (bare `>d`). Reuse the directions `directions` lists
   before proposing a new slug; a new slug only for items none fits. Never move
   a `recover:` item and never name `crashed-agents` for an ordinary item; its
   members are derived (`=` in the proposal line). Per direction: title (one
   line, at most 120 characters), linked trails (the handles that hold at least
   one of its tasks; at most 8; only `art:trail-…` handles can be linked), the
   next step (the **eligibility rule** below; none when no task passes it), and
   its place in ONE ranked order with a reason per position. Ranking evidence: each task's priority and effort (through the
   `task:` pointer), the crash-recovery tiers of `>p`, each trail's `NEXT:`
   lines and waves, and `/aitask-backlog-roadmap --show` (read-only). The order
   to save is always COMPLETE: every direction ranked now, in its place, plus
   the newly ranked ones. Every direction that gains or loses a member is part
   of the proposal, because its evidence changes.
   For `>d <direction>`: members as stored (`=`); propose title, trails and next
   again only where the evidence changed; no rank.

   **Eligibility rule** (one definition; `>p` uses the same one). The Pick now
   group is a stored grouping and proves nothing about whether a task can be
   picked. A task is proposed as a next step only on positive evidence read in
   this turn, and a known blocker always wins:
   1. *Blocked wins.* A task that any `critical-path` call of this turn reports
      with a readiness other than `next` (`blocked`, `unresolved`, `unverified`,
      `in_progress`, `on_hold`, `landed`, `released`) is not eligible, even when
      another trail prints `NEXT:` for it and whatever its group. Keep its
      `BLOCKER:` / `BLOCKED_BY:` / `OUTSIDE:` / `XDEP:` lines: they are what the
      direction waits on.
   2. *The picker's verdict, for every candidate.* Read it once per turn:

      ```bash
      ./.aitask-scripts/aitask_ls.sh -v --all-levels 9999
      ```

      A local task is eligible only when its line reads exactly
      `Status: Ready`. This holds for a task with a `NEXT:` line too: `NEXT:`
      reads the task's status and the trail's blockers, not the picker, so a
      Ready parent with pending children is `NEXT:` in a trail and
      `Has children` here, where a pick opens child selection.
      `Status: Blocked (by …)`, `Blocked [unverified]`, `Has children`, or no
      line at all (the listing holds Ready tasks only): not eligible; quote the
      line, or say the task is not Ready. For a `Has children` parent the
      candidates are its children whose own lines read `Status: Ready`: name
      the parent as what the trail orders next and the child as the pick. A
      task that a `(by …)` part names is eligible only by this same check. A
      cross-repo ref has no line here: not eligible.
   3. *Trail evidence qualifies the claim, never replaces rule 2.* A task some
      linked trail knows must also have a `NEXT:` line there (rule 1 already
      excludes every other readiness); quote that trail's freshness word. It
      may be a task outside the direction that must land first (a critical-path
      predecessor): say so. A task no trail knows (`NOT_IN_TRAIL` everywhere,
      or no linked trail) is eligible on the picker's verdict alone, said as
      "no trail of this project orders it".
   Blocker lines from the trail and from the picker are both kept and reported.
   Candidates are the direction's pending task members first, then the tasks
   they wait on. With no eligible task the next step is none (`-`), and the
   proposal says what the direction waits on. A non-task item (`c<N>`, an
   action or a watch) may be the next step only when it is `open`; say that it
   is an item, not a pick.
4. **Snapshot — the one read for summary and baseline.**

   ```bash
   ./.aitask-scripts/aitask_sitrep_refresh.sh snapshot <<'SITREP_PROPOSAL'
   <PROPOSAL>
   SITREP_PROPOSAL
   ```

   (example block `direction-snapshot`). One line per direction whose record or
   members the proposal edits, `<direction>|<members>|<trails>|<next>`; a
   direction that only changes rank has no line. Each field is `=` (as stored), `-`
   (none) or a value (`c1,c2`; handles; a task ref or `c<N>`). Result lines:
   `SNAPSHOT:<slug>|<digest>|baselines/<digest>.txt|<pending>|<unreadable count>`,
   `SNAPSHOT_UNREADABLE:<slug>|<kind>|<key>` (the summary can still be saved;
   tell the user the direction will read `unknown` until that input can be
   read), `SNAPSHOT_TOO_LARGE:<slug>|<bytes>|<limit>` (below), final
   `SNAPSHOTS:<retained>|<refused>`. `SNAPSHOT_FAILED:` / `SNAPSHOT_INCOMPLETE:`
   or exit 1: nothing is proposed from a prefix; report and stop. Exit 2: fix
   the line (an unknown member, a `next` item that does not exist).
   Read each `<store>/baselines/<digest>.txt` and write that direction's summary
   **from that file only**: one line, at most 400 characters, saying what its
   member, task, trail and next lines show. What blocks what (the critical-path
   lines) goes in the proposal text and in `>q` answers, never in a summary: it
   is not in the baseline, so a summary quoting it could go wrong without
   turning stale. A baseline is never taken again at write time.
   **Too large:** say so. For an ordinary direction offer a split into two
   directions. `crashed-agents` cannot be split: it keeps its rank and situation
   text and has no summary until its pending items shrink.
5. **Confirm once.** `⚠️ NON-SKIPPABLE` banner in the convention's wording
   (execution profiles: no key covers it; auto mode and "don't ask" do not; the
   only opt-out is the user deciding the proposal in chat first). Per the
   visibility rule the `AskUserQuestion` text itself carries the condensed
   proposal: one or two lines per direction (slug, title, members gained and
   lost, trails, next, summary), then the FULL ranked order with a reason per
   position, then items left in no direction. Options "Save all" / "Let me
   adjust" / "Not now". "Let me adjust": the user may reorder, drop or edit. A
   dropped direction loses only its proposed edits: no `direction-set` for it,
   and its saved record, members and current rank stay; it stays in the order
   unless the user explicitly asked to unrank it.
   **A move touches two directions.** Moving an item from A to B is ONE assign
   line that names B and takes the item out of A, so leaving out A's
   `direction-set` does not keep A's members. When either endpoint of a move is
   dropped, the move is cancelled: its assign line is not sent, and the item
   stays where it is. That changes the member set of the OTHER endpoint, which
   is still in the proposal, so its proposal line, snapshot and summary are
   rebuilt. (An item moved out of or into "no direction" has one endpoint.)
   After any adjustment that changes a member set, trails or next, including a
   cancelled move, run `snapshot` again for those lines, rewrite those summaries
   from the new baselines, and ask again with the rebuilt proposal. "Not now":
   write nothing. A proposal with nothing to change (no assignment, no record
   edit, the order as it is) is reported as such and ends here without a prompt
   and without a write.
6. **Recheck before the first write.**

   ```bash
   ./.aitask-scripts/aitask_sitrep_refresh.sh recheck <<'SITREP_PROPOSAL'
   <PROPOSAL_DIGESTS>
   SITREP_PROPOSAL
   ```

   (example block `direction-recheck`; the same lines plus `|<digest>`). Write
   only after exit 0 and `RECHECK:same`. `RECHECK:changed|<n>` (with
   `RECHECK_CHANGED:` / `RECHECK_REASON:` lines) or `RECHECK_FAILED:`: nothing is
   written; re-read (step 1), revise, snapshot, confirm again. A prefix of
   results is never a pass.
   **Rank-only save.** The proposal lines are the directions with a record or
   membership edit. When the CONFIRMED proposal has none (the user dropped every
   record edit, or asked only to reorder or unrank), there is nothing to
   snapshot and nothing to recheck: both verbs refuse empty input, and no
   summary or baseline is being saved. Skip steps 4 and 6 for it, keep the
   confirmation of the full order, and send only the `direction-rank` call of
   step 7 (or its `--clear` form), with `--expect-ranked` = the order seen in
   step 1 and each direction's rev from a fresh `directions` read. The writer's
   `STALE_ORDER:` / `STALE:` / `ABSENT:` answers are the guard for that write.
   Baselines an earlier `snapshot` of the same proposal retained stay unused:
   they name nothing until a `direction-set` uses them.
7. **Save, in this order; stop at the first refusal.** Four example blocks:
   - `direction-assign`: `direction-assign --batch`, stdin
     `<id>|<rev>|<direction or ->` per item whose direction changes (revs from
     the step-1 `list`), only for moves whose endpoints are both still in the
     confirmed proposal; skip it when no membership changes. All or nothing:
     `STALE:c<N>|<rev>`, `NOT_FOUND:c<N>` or `KEPT:c<N>|recovery` means nothing
     was written. Else `ASSIGNED:` lines and `DIRECTION:<slug>|updated|<rev>` per
     block that gained or lost a member. Never use `upsert-context` for a
     membership change.
   - **The rev hand-off is verified, never assumed.** `direction-assign` checks
     item revs only. The rev it prints for a block can therefore sit on top of
     an edit another session made to that direction after the step-1 read (a
     new summary, a new situation text, a changed title, trails or next), and a
     `direction-set` sent with that rev would pass its check and overwrite or
     contradict that edit. So, for every block `direction-assign` printed,
     before its `direction-set`: read `directions <slug>` and `read todo` again
     and require both of
     - the block's rev equals the rev `direction-assign` printed, and
     - its title, rank, trails, next, summary, digest and situation text equal
       the state kept in step 1. `freshness`, `checked_at` and `drift` are not
       compared: the assignment resets them.
     Both hold: that rev is the block's `--expect-rev`. Either fails: the
     direction was edited by someone else. Send no `direction-set` for it. The
     assignments that landed stay (step 8). Report the difference, re-read
     (step 1), redraft the remaining edits for that direction from what is
     there now, and confirm again before writing them.
     A block `direction-assign` did not print keeps its step-1 rev, which the
     writer checks itself; a direction that had no block uses `absent`.
   - `direction-set`, once per direction in the proposal:
     `direction-set <DIRECTION> --expect-rev <DIRECTION_REV> --title "<TITLE>"
     --trails "<TRAILS>" --next "<NEXT>" --summary-file - --digest <DIGEST>`
     with the one-line summary on stdin. `--trails` / `--next` carry exactly the
     values of the proposal line (empty string for none; leave the flag out for
     `=`). Answers: `DIRECTION:<slug>|created|updated|unchanged|<rev>`, or
     `STALE:` / `ABSENT:` / `EVIDENCE_CHANGED:<slug>|<kind>|<key>` (nothing
     written).
   - `direction-set-paired`, instead of the plain form, for a direction whose
     existing situation text would contradict its new summary: the same call
     with `--with-situation`, stdin = the summary on line 1, then the rewritten
     situation text (shown in the same confirmation). Summary and text are one
     write: both saved, or on any refusal neither. This is the only way `>d`
     changes situation text; it never follows a `direction-set` with a separate
     `situation` call, because a refusal in between (the rank's, a busy lock)
     would leave the store with two accounts that disagree.
   - `direction-rank` (bare `>d` only): `direction-rank --expect-ranked
     <ORDER_SEEN>` (the full ranked order of the step-1 read, `-` for none),
     stdin `<direction>|<rev or absent>` per line in the confirmed order, revs
     from a fresh `directions` read after the last `direction-set`.
     `RANKED:` / `UNRANKED:` lines, or `STALE_ORDER:` / `STALE:` / `ABSENT:`
     (nothing written). Three cases by the confirmed order:
     - it equals the order seen in step 1 and names no new direction: no
       `direction-rank` call;
     - it is non-empty and differs: the call above;
     - it is EMPTY because the user explicitly asked to unrank every ranked
       direction (the order seen was not empty): the writer refuses empty input
       without `--clear`, so the call is `direction-rank --expect-ranked
       <ORDER_SEEN> --clear` with no stdin lines (example block
       `direction-rank-clear`), answered by `UNRANKED:` lines.
     An order that is empty because nothing was ranked and nothing is to be
     ranked is the first case, not the third: never send `--clear` unless the
     user asked to unrank.
8. **A refusal stops the sequence.** Earlier writes of the same save stay and
   are valid by themselves (a direction with new members and its previous
   summary reads `unknown`, never `current`; a direction whose record was saved
   has a summary and a situation text that agree, because they were one write,
   whether or not the rank was saved after it). Report which writes landed and
   which did not, quoting the result lines; re-read `directions`; revise only
   what is left; confirm; resume. Never retry blind, never roll back.
9. **Afterwards.** Say that the saved directions read `unknown` until the next
   refresh computes their verdict, and name the TUI's `r`.
   **Seeing a direction in its trail.** For a direction with a linked trail,
   name a command for the user to run, built by the rule the trails launcher
   uses (`_prepare_trails_highlight` in `lib/agent_launch_utils.py`):
   `ait trails --trail <handle> --highlight <ids> --highlight-direction=<slug>`.
   `--highlight-direction` is added only when the slug is at most 512
   characters: `ait trails` refuses a longer one, so it is left out, as the
   launcher does, and the user is told the trail opens with the title only (or
   with no direction name when the title is left out too).
   `<ids>` are the direction's task refs in the order `directions` lists its
   members, in the wire form (no `t` before the number; `<project>#<N>` kept),
   duplicates dropped. `ait trails` refuses more than 256 ids: with more, pass
   the first 256 and add `--highlight-total=<the full count>`, and tell the
   user the overlay marks 256 of that many tasks. Add
   `--highlight-title='<title>'` only when the title holds no single quote;
   otherwise leave it out, and the banner shows the slug. The command is named,
   never run.
   **Uncovered directions.** Coverage is about the trails this project owns. A
   direction is uncovered only when all three hold: it has at least one task
   ref; `membership` ended `scan=complete`; and EVERY task ref of the direction,
   passed in that call, came back `NO_TRAIL`. Then offer to create a trail with
   `/aitask-trail` (an ad-hoc set of tasks, or its topics), worded as "no trail
   of this project holds these tasks", and run it only on the user's yes; that
   skill asks again before it writes. One `UNKNOWN` line (a partial or failed
   scan, or a task of another project) means coverage is unknown: say which
   refs, and offer nothing. A direction with no task ref (only actions,
   questions or watches) gives no evidence either way: offer nothing. Never one
   trail per direction by default.
   **Deleting.** `direction-remove <direction> --expect-rev <rev>` only when the
   user explicitly asks to delete that direction; it leaves the items assigned.
   Leaving a direction out of a proposal never means delete.

**3d. `>w`.** Add the relation: the summary `>d` saves is the short form (one
line, shown where directions are listed); the situation text is the long form
(one to three sentences naming item ids). The store must never hold two
accounts of one direction that contradict each other, so the write is no longer
unconditional:

- Before writing a direction's text, read `directions` (bare `>w`) or
  `directions <direction>`, and keep the block's `<rev>` from its `DIRECTION:`
  line (`-` means no block).
- **Every `situation` write is guarded.** The `situation` example gains
  `--expect-rev <DIRECTION_REV>`: that rev, or `absent` for `-`. The writer
  checks it under its lock. `STALE:<slug>|<rev>` or `ABSENT:<slug>` means the
  block changed after the read (another session saved a summary, a pair, or a
  text): nothing was written. Read `directions` again and REPEAT the comparison
  below against what is there now; never resend the same text with the new
  rev unseen. This holds for a direction with no summary too, and for the
  clear (empty input).
- A direction with no `DIRECTION_SUMMARY` line has nothing to contradict: write
  (guarded).
- With a summary: draft the text from the items, then compare the draft with
  the summary. They agree: write. They disagree (the summary calls an item open
  that the draft calls done, names a different next step, and so on): re-read
  `list` and the members' contexts once and correct the draft where the draft
  was wrong.
- A disagreement that survives that re-read **pauses the write**, whatever the
  record's freshness reads: no `situation` call for that direction. Say what
  differs, quoting the summary and the `DIRECTION_DRIFT` reasons, and offer
  `>d <direction>`, which re-summarises from the current evidence and saves the
  summary and the rewritten situation text in ONE confirmation and ONE write
  (`direction-set-paired`, step 7 of `>d`). When the record
  reads `current` although the items moved, also name the TUI's `r`. The text
  is written only through that `>d`, or by a later `>w` once the two agree.
- A bare `>w` writes the directions that agree and lists the paused ones. The
  same rule applies where `>t` step 5 rewrites situation text.
- `>w` never changes a summary. Removing the text of a direction that no longer
  applies (empty input) is not a new account and is not paused.
- A record that reads `stale` or `unknown` while the two texts agree is written,
  with one line naming `>d <direction>`.

**3e. `>q`.** Add a paragraph for questions about a direction ("what is blocking
X", "what should I do next on Y", "which direction is behind"): read
`directions` fresh, the pending members' contexts and sources, and
`critical-path` over its linked trails; answer from those, never from the saved
summary or situation text. A `stale` or `unknown` direction is called out first,
with its `DIRECTION_DRIFT` reasons and `>d <direction>`; a direction with no
record is "never summarised". A `NEXT:` is quoted with the trail's own
freshness word. Logged to `qa.md` with the members relied on.

**3f. `>p`.** After "Crashed work first": the directions in their confirmed
order. Walk the ranked directions from rank 1 to the first with an eligible
task, judged fresh by the **eligibility rule** of `>d` step 3 (read
`membership` and `critical-path` for the direction's task refs now; a blocked
reading wins; every candidate, a `NEXT:` one included, needs `Status: Ready`
in the `ait ls` read, and a `Has children` parent yields its Ready children).
Neither the Pick now group nor the saved `next` makes a task eligible:
the saved `next` is named only when this fresh reading agrees with it, and
when it does not, say so and name `>d <direction>`. Name the eligible task and
`/aitask-pick <id>` for the user. One line per higher-ranked direction skipped,
on what it waits on, from the blocker lines. Call out `stale` / `unknown` directions. With no
ranked direction say so and name `>d`. Then relate to the backlog roadmap as
today. The order is the user's confirmed one; `Never rank tasks yourself` and
"never pick" stay.

**3g. "Done in the sitrep TUI, not here" and the Guardrail.** The freshness of a
direction is written by the refresh: name `r`; `snapshot` and `recheck` are
proposal reads of `>d`, not the refresh. Guardrail: recovery items are read,
never written, including by `direction-assign`; `crashed-agents` is ranked and
summarised like any direction but never assigned to; a trail is created and a
direction deleted only on the user's explicit yes.

**3h. "Requests from the sitrep TUI":** no `>d` line (decision 2). One wording
fix only: its last paragraph says `situation` takes no `--expect-rev`; it now
takes the rev of the fresh `directions` read, like the other writes there. No
`>` code is added to or removed from the section, so parity check r is
unaffected.

### 4. `tests/test_sitrep_skill_contract.sh`

- Header comment: describe the new section and the changed assertion.
- Check a: replace `assert_not_contains … "aitask_sitrep_refresh.sh"` with: every
  occurrence of `aitask_sitrep_refresh.sh` in the render is followed by
  ` snapshot` or ` recheck` (count of other occurrences is 0), plus
  `assert_contains` for both verbs. The intent "the skill never runs the
  refresh itself" stays tested.
- Check a, allow-list count: the skill now names `./.aitask-scripts/aitask_ls.sh`
  (the eligibility read). `.claude/settings.local.json` holds two lines the
  current pattern `/aitask_ls\.sh[":* ]` matches: the real entry (line 37) and a
  legacy `./aiscripts/aitask_ls.sh` entry (line 160), so the check would report
  `ALLOWLIST:aitask_ls.sh:settings.local.json:2`. Anchor the pattern on the path
  the skill actually uses, `\.aitask-scripts/<helper>[":* ]`: still exactly one
  entry per file, and an entry for another directory no longer counts for or
  against. Confirm before the edit that every helper the skill names still
  counts 1 in all five files, and keep the existing `MISSING_HELPER` mutant.
  Add a mutant: a copy of one permission file without the `aitask_ls.sh` entry
  is reported (`ALLOWLIST:aitask_ls.sh:…:0`); `check_helpers` takes the
  permission files from `PERMISSION_FILES`, so the mutant swaps one path in
  that array for the copy and restores it.
- Check b: extend the helper alternation to `aitask_sitrep_refresh` and
  `aitask_trail_gather`.
- Section c: the existing `situation` example run now needs
  `SX_DIRECTION_REV` (`absent` for the first text of a direction). Add the
  guarded cases through the example block itself: a stale `SX_DIRECTION_REV` →
  `STALE:` and `read todo` unchanged; the fresh rev → `SITUATION:<slug>|set`.
- New section `f` (directions, end to end from the skill's example blocks, in a
  scratch repository): add two task items through the writer; fill and run
  `direction-snapshot` → one `SNAPSHOT:` line and `SNAPSHOTS:1|0`, and the
  retained baseline file exists under the store; `direction-recheck` → exit 0,
  `RECHECK:same`; `direction-assign` → `ASSIGNED:` lines; `direction-set` with
  `--expect-rev absent` → `DIRECTION:<slug>|created|`; `direction-rank` with
  `--expect-ranked -` → `RANKED:<slug>|1|`; `directions` then shows the rank,
  the digest and `DIRECTION_SUMMARY`. Unranking the last ranked direction: the
  `direction-rank` example with empty input → exit 2 and the rank still there
  (why the skill needs the flag); the `direction-rank-clear` example with
  `--expect-ranked <slug>` → `UNRANKED:<slug>|` and `directions` shows rank `-`
  with the record kept. The eligibility read: in the scratch repository a task
  file `t51` with `depends: [52]` and a Ready `t52` make the skill's
  `aitask_ls.sh -v --all-levels 9999` line (run as written in the render) show
  `t51` as `Status: Blocked (by t52)` and `t52` as `Status: Ready`, which is the
  evidence the eligibility rule reads; a Ready parent `t60` with a pending
  child `t60_1` shows `Has children` and the child `Status: Ready`. Rank-only
  writes: the `direction-snapshot` example with empty input → exit 2 and
  nothing retained (why a rank-only save skips it), then the `direction-rank`
  example alone, with no snapshot or recheck before it, changes the order of
  two ranked directions. The paired write: the `direction-set-paired` example
  sets summary and situation text under one rev; then, with another direction
  ranked behind the caller's back, the `direction-rank` example answers
  `STALE_ORDER:` and `read todo` shows that direction's summary and situation
  text still the pair just saved; a paired example refused by a stale rev
  leaves both parts unchanged. The assignment hand-off: with direction B holding
  a summary and a situation text, a second writer call changes B's situation
  text, then the `direction-assign` example moves an item into B: assert that
  it prints a rev for B, that `read todo` at that rev shows the second writer's
  text (so the printed rev alone proves nothing about B's fields, which is why
  the skill compares them), and that the `direction-set` example sent with the
  printed rev WOULD be accepted (the control that shows the comparison, not the
  writer, is what stops it). The suggested trails command: every
  `--highlight…` flag the render names is an argument of
  `board/trails_app.py`, and the two limits the render states equal
  `HIGHLIGHT_MAX` and `HIGHLIGHT_DIRECTION_MAX` in `lib/agent_launch_utils.py`
  (read from the module, so they cannot drift). Refusal control: close a member
  (`set-state … done`), run the `direction-recheck` example with the old digest
  → exit 1 and `RECHECK:changed|1`, and the `direction-set` example with the old
  digest → `EVIDENCE_CHANGED:` with `directions` unchanged.
- Section m: one mutant per new check: `aitask_sitrep_refresh.sh snapshot` →
  `… frobnicate` is reported by check b; a bare `aitask_sitrep_refresh.sh --root .`
  appended to the copy is reported by the new check a.

### 5. `tests/test_skill_render_aitask_sitrep.sh` and goldens

- Add `` '### `>d [<direction>]`' `` to `SHORTCODES` (Test 2s).
- Regenerate the three goldens in `tests/golden/skills/aitask-sitrep/` with the
  loop from "Regenerate goldens after any `.md.j2` or closure edit", and review
  the diff: it must show only the edits of step 3.

### 6. Tests for the verb: new `tests/test_trail_membership.py`

- `membership_lines` (pure) over hand-built `Membership` values: one, two and no
  trails; waves; a partial scan (positive evidence kept, the unlisted task
  `UNKNOWN`, never `NO_TRAIL`); a failed scan (every ref `UNKNOWN`); a ref of
  another project; duplicate ids; the final line's counts.
- CLI: `ERROR:bad_task:` alone for a bad id; one end-to-end run of
  `aitask_trail_gather.sh membership --tasks 5,7,9` over a real fixture
  repository with two stored trails, borrowing the `EndToEndTests` helpers of
  `tests/test_trail_links.py` the way `tests/test_sitrep_tui_trails.py` does:
  task 7 in two trails, task 9 `NO_TRAIL`, `scan=complete`.
- Mutant, run in a scratch copy and recorded in the plan's final notes: remove
  the "partial scan → `UNKNOWN`" branch and show the partial-scan test fails.
- `tests/test_sitrep_tui_trails.py` and `tests/test_sitrep_tui_trails_actions.py`
  must pass unmodified: they are the regression check of the move in step 1.

### 7. Contributor docs: `aidocs/framework/sitrep.md`

- "The skill": add `>d [<direction>]` to **Codes**; add the direction verbs and
  the two proposal reads to **Writes only through writer verbs**; a new
  **Directions** bullet (the `>d` flow in five lines: read, snapshot, one
  confirmation, recheck, assign / set / rank; refusal handling; uncovered
  directions; `>d <direction>`); how `>q`, `>p` and `>w` use directions; in
  **Requests from the sitrep TUI** one sentence that `>d` is typed by hand and
  checks its direction itself.
- "Saving a proposal": one sentence that a proposed move touches two
  directions and is sent only while both are in the confirmed proposal, one
  that an explicit unranking of every ranked direction is the `--clear` form,
  and the paired write: `direction-set --with-situation` saves a summary and
  its situation text together, so no step of the sequence can leave them
  disagreeing; add the row to the "Refused step / Already saved" table's
  wording. "The record": `situation text` is written by `situation` (with an
  optional `--expect-rev`, which the skill always passes) or by the paired
  `direction-set`.
- "The skill": the eligibility rule in two sentences (a blocked reading wins;
  every candidate, a trail's `NEXT:` included, needs `Status: Ready` from
  `ait ls`; the Pick now group and a saved `next` are not evidence), the three
  conditions of an uncovered direction, the rank-only save (no snapshot, no
  recheck, the `--expect-ranked` guard), the `>w` pause on a surviving
  disagreement with the summary, the bounded `ait trails` command, and the
  verified rev hand-off after `direction-assign` (it checks item revs only, so
  the skill compares the block's saved fields and situation text with the
  state the proposal was drafted from before it uses the printed rev).
- "Membership": one sentence that the rev `direction-assign` prints for a block
  says the block changed, not that nothing else changed it since a caller's
  earlier read.
- "Permissions": add `aitask_ls.sh` to the helpers the skill calls.
- "The sitrep TUI", **Trail membership**: name `lib/trail_membership.py` as the
  shared derivation and the `membership` verb as its CLI form.
- "Permissions": the skill calls the refresh helper only for `snapshot` and
  `recheck`.
- "Tests" table: the contract test's direction section; a row for
  `tests/test_trail_membership.py`.
- Header of `aitask_sitrep_refresh.sh`, "Callers": the sitrep skill calls
  `snapshot` and `recheck`; drop the "owes the permission touchpoints" clause
  (they exist).

### 8. Website docs

Read `aitasks/metadata/doc_update_guide.md` first; state only what works after
this commit (no Directions tab, no TUI key for `>d`: those are t2335_5's).

- `website/content/docs/workflows/sitrep.md`: replace `## Work directions`
  with `## Work directions and implementation trails`.
  - Two opening sentences: what a direction is, and that sitrep links it to
    [implementation trails] by task id.
  - A short comparison table, direction vs trail: what it groups (sitrep items
    around a current line of work / tasks in waves), how it is ordered (a rank
    among directions that you confirm / waves, dependencies and evidence inside
    one trail), what it gives you (a summary and a suggested next step / a
    recommended landing order with reasons), when to use each.
  - ONE numbered procedure with the worked example inside it (the names the
    trails how-to already uses: `art:trail-checkout`, tasks 12, 14_2, 31,
    "Stabilize CI"): ask with `>d`; confirm once, after reordering or dropping;
    how the agent links trails by task id (a direction can use several trails, a
    trail can serve several directions); the example where task 12 is outside
    the direction, sits in an earlier wave, and so must land first; opening the
    trail with `ait trails --trail … --highlight … --highlight-title=…` to see
    the `★` and `»` cards while the saved trail stays as it is (link to
    "How to See Where a Group of Tasks Stands in a Trail"); `r`, then
    `>d <direction>` for a direction that went stale; when the agent offers
    `/aitask-trail`: only for a direction that has tasks, none of which is in a
    trail of this project, and never when it could not read every trail or the
    direction holds a task of another project.
- `website/content/docs/concepts/implementation-trails.md`: one "See also"
  bullet to the new section. The section links back to the concept page.
- `website/content/docs/skills/aitask-sitrep.md`: a `>d [<direction>]` row in
  the Capabilities table; `>w`, `>q`, `>p` rows updated; the opening sentence
  names directions; "What it never does" gains "rank directions or create a
  trail without your yes". Its "Requests" section is unchanged.
- Run `cd website && python3 check_links.py --build` and
  `python3 check_screenshots.py`; offer `python3 check_link_relevance.py`.

### 9. Notes to other tasks (after the code commit, through `/aitask-note`)

- **t2335_5:** the Requests-section line is yours, with its `AGENT_REQUESTS`
  row (exact lines: `` `>d <direction>` — re-summarise that direction (`>d`) ``
  and the store-wide `` `>d` ``; fresh-read check: a direction `directions`
  lists), and the goldens regenerate with it; the membership dataclasses now
  live in `lib/trail_membership.py`; a saved direction reads `unknown` until a
  refresh; the workflow page's new section shows the `ait trails --highlight`
  command where the `z` key will go.
- **t2335_6:** between "the agent rewrites it" and "the row reads current" a
  refresh (`r`) is needed.
- **t2199:** include `>d` in the end-to-end check on Codex / OpenCode (heredoc
  stdin to `snapshot` / `recheck` / `direction-*`, the single confirmation, the
  nested `/aitask-trail` offer). Nothing else is needed for the port.

### Post-phase (risk mitigations)

1. [walk_rendered_d_flow] Render the skill (`skill_template.py` with
   `default.yaml`, agent `claude`) and follow its `>d` section literally in a
   scratch repository, taking every command from the rendered text and nothing
   from memory of this plan. Cases, each ending with a `directions` and `list`
   read that is compared with the expectation written down beforehand:
   (a) a bare `>d` over a store with one existing direction, items for one new
   direction, one item that moves between directions, ending in a saved rank.
   (b) Dropped direction with a move. The proposal moves item X from A to B.
   "Let me adjust" drops A: expect the move cancelled (no assign line for X, X
   still in A), B's line, snapshot and summary rebuilt without X, a second
   confirmation, and A's record, members and rank unchanged after the save.
   Repeat with B dropped instead: X stays in A and A's line is rebuilt with X.
   (c) A refusal: close a member between `snapshot` and `recheck`, confirm
   nothing was written, then finish the save through the documented recovery.
   (d) `>d <direction>`, checking that no other direction's rev or rank moved.
   (e) Next-step eligibility. A direction with no linked trail whose Pick now
   member `t51` has an unfinished prerequisite `t52` (`depends: [52]`): expect
   `t51` NOT proposed as the next step, the `Blocked (by t52)` line quoted, and
   `t52` named only after its own `Status: Ready` line. Then a member that a
   trail's `critical-path` reports `blocked` while it sits in Pick now: expect
   it not proposed, with its blocker lines kept. Ask `>p` over the same store
   and expect the same answer.
   (f) Rank edges. The user asks to unrank the only ranked direction: expect
   `direction-rank … --clear` with the order seen, and `UNRANKED:`. Separately,
   a store where nothing is ranked and the proposal ranks nothing, and a
   proposal with nothing to change at all: expect no `direction-rank` call, no
   `--clear`, no write, and the user told there is nothing to save.
   (g) Coverage. A direction with one local task in no trail and one
   `<project>#<N>` task: expect both refs passed to `membership`, an `UNKNOWN`
   line for the foreign one, and no `/aitask-trail` offer. A direction with no
   task ref: no offer. A direction whose refs are all `NO_TRAIL` on a complete
   scan: the offer, worded as about this project's trails.
   (h) Rank-only save. "Let me adjust" drops every record edit and swaps two
   ranked directions: expect no `snapshot`, no `recheck`, one confirmation of
   the full order, and one `direction-rank` with the order seen. Then the same
   with an explicit "unrank everything": expect only the `--clear` call.
   (i) A parent as the trail's next. A stored trail whose `NEXT:` is a Ready
   parent with pending children: expect the parent not named as the pick, its
   `Has children` line quoted, and a child with its own `Status: Ready` line
   named instead; with no Ready child, no next step. Same answer from `>p`.
   (j) Contradictory accounts. A direction with a saved summary that calls `c1`
   open; close `c1`; then `>w <direction>`: expect NO `situation` write, the
   difference and the drift reasons reported, and `>d <direction>` offered.
   The race: start `>w <direction>` on a direction whose text and summary
   agree, and after its `directions` read save a different pair from a second
   shell: expect `STALE:` from the guarded `situation` call, the second shell's
   pair intact, a fresh read, the comparison repeated against the new summary,
   and (as that summary now disagrees with the draft) the write paused.
   `>d <direction>` on a direction that has situation text: expect `read todo`
   among its reads and the paired form chosen from that text.
   (l) An edit under the assignment. A bare `>d` whose confirmed proposal moves
   item X into direction B and re-summarises B. After the confirmation and
   before `direction-assign`, a second shell writes a new situation text to B
   (`situation B --expect-rev <rev>`). Run the save: expect `direction-assign`
   to succeed and print a rev for B, the verification read to find B's
   situation text different from the step-1 state, NO `direction-set` for B,
   the second shell's text intact, X's assignment kept and reported as landed,
   and B's remaining edits re-read, redrafted and confirmed again. Repeat with
   the second shell changing B's summary instead, and with it editing B AFTER
   the assignment (the rev then differs from the printed one): same outcome.
   Control: with no intervening edit the verification passes and the set uses
   the printed rev.
   Then `>d <direction>`: expect summary and situation text rewritten in one
   confirmation and ONE `direction-set … --with-situation` call, with no
   `situation` call anywhere in the save, and agreeing afterwards. In a bare
   `>d` that pairs a direction this way and also changes the rank, rank another
   direction from a second shell between the set and the rank: expect
   `STALE_ORDER:`, the save reported as stopped there, and that direction's
   saved summary and situation text in agreement. A bare `>w` over that store plus a
   second, consistent direction: expect the second written, the first listed
   as paused.
   (k) The trails command. A direction with 257 task refs (items added in a
   loop): expect the named command to carry 256 ids, `--highlight-total=257`
   and the "256 of 257" sentence. Feed both that argv and the uncut 257-id
   argv to the argument validation of `board/trails_app.py` (its parser
   function, without starting the TUI): the first is accepted, the second
   refused. A title containing a single quote: expect no `--highlight-title`.
   A direction whose slug is 513 characters long: expect no
   `--highlight-direction` in the named command and the sentence about it; the
   validation accepts that argv and refuses the same argv with the slug added.
   Wherever a value had to be guessed, a result line was not explained, or the
   outcome differed from the expectation, fix the template (and regenerate the
   goldens) and re-run that case. Put the commands and their result lines,
   verbatim, in this plan's final notes.
2. [docs_current_state_check] Grep the three changed website pages for anything
   that exists only after t2335_5 (a Directions tab, a request key for `>d`,
   `z` on a direction) and remove it; then run `/aitask-docs-review` on
   `website/content/docs/workflows/sitrep.md` and act on what it reports for
   the new section.

### Post-implementation

Step 9 of the task workflow (review, commit, archival). Commit type `feature`,
message suffix `(t2335_4)`; goldens in the same commit as the template.

## Verification

```bash
bash tests/test_sitrep_todo.sh
~/.aitask/venv/bin/python -m pytest -q tests/test_sitrep_todo_format.py
bash tests/test_sitrep_skill_contract.sh
bash tests/test_skill_render_aitask_sitrep.sh
./.aitask-scripts/aitask_skill_verify.sh
~/.aitask/venv/bin/python -m pytest -q tests/test_trail_membership.py \
  tests/test_sitrep_tui_trails.py tests/test_sitrep_tui_trails_actions.py \
  tests/test_trail_gather.py tests/test_trail_links.py tests/test_sitrep_tui_requests.py
bash tests/test_helper_whitelist_coverage.sh
shellcheck .aitask-scripts/aitask_trail_gather.sh .aitask-scripts/aitask_sitrep_refresh.sh
(cd website && python3 check_links.py --build && python3 check_screenshots.py)
```

Live, read-only, against this repository: `aitask_sitrep_todo.sh directions`,
`aitask_trail_gather.sh membership --tasks <three real ids>` and one
`critical-path` call, comparing each printed line with what the skill text
says. `snapshot` writes a baseline into the store, so it runs only in the
contract test's scratch repository, never against the live store.

Known unrelated failure: `tests/test_trail_skill_contract.sh` has 6 failing
assertions with the trail skill files unmodified (recorded by t2335_3).

## Risk

### Code-health risk: medium
- `direction-set --with-situation` and `situation --expect-rev` extend the one writer of a store that cannot be rebuilt; a mistake in the gating would change what the existing forms write · severity: medium · → mitigation: none (each is gated on one new optional flag; step 2b pins both old paths with control cases and adds a mutant per guard, and the writer's existing suite runs unchanged)
- Moving the membership derivation out of `sitrep_tui_trails.py` changes where a live TUI path resolves its names; a patch target or import that still points at the old module would fail only at runtime · severity: low (residual — addressed by inline pre-phase baseline_tui_trail_tests) · → mitigation: inline pre-phase baseline_tui_trail_tests
- The contract test's "never names the refresh helper" assertion is replaced, which could weaken the rule that the skill never runs the refresh itself · severity: low · → mitigation: none (step 4 adds a mutant that must turn the new assertion red)

### Goal-achievement risk: medium
- The `>d` save sequence is prose an agent follows (the verified rev hand-off from `direction-assign` to `direction-set` and on to `direction-rank`, the complete rank order, its `--clear` edge and the rank-only save, a move cancelled when either endpoint is dropped, the next-step eligibility rule, the coverage conditions, the `>w` pause). The tests prove each documented command is accepted, not that the prose is followable without a gap · severity: medium (residual — the author's walk-through is inline post-phase walk_rendered_d_flow; a live agent following it is checked only by t2335_6) · → mitigation: inline post-phase walk_rendered_d_flow
- The website section could describe behaviour that only exists after t2335_5 (the Directions tab, a TUI key for `>d`) · severity: low (residual — addressed by inline post-phase docs_current_state_check) · → mitigation: inline post-phase docs_current_state_check

### Planned mitigations
- timing: pre-phase | name: baseline_tui_trail_tests | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the membership move changing where a live TUI path resolves its names | desc: record the four sitrep TUI test files' pass counts before the move and require the same counts after it
- timing: post-phase | name: walk_rendered_d_flow | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: the `>d` save sequence being prose whose gaps the tests cannot see | desc: follow the rendered `>d` text literally in a scratch repository (full save, a dropped direction, a refusal, one direction) and fix the prose where a value had to be guessed
- timing: post-phase | name: docs_current_state_check | type: documentation | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: the website describing behaviour that only exists after t2335_5 | desc: grep the changed pages for t2335_5-only behaviour and run /aitask-docs-review on the new workflow section

## Final Implementation Notes

- **Actual work done:** every plan step, the pre-phase and both post-phases.
  - `lib/trail_membership.py` (new): the membership derivation moved out of `sitrep_tui/sitrep_tui_trails.py`, which re-exports the same objects.
  - `lib/trail_gather.py`, `aitask_trail_gather.sh`: the `membership --tasks` read verb (`IN_TRAIL` / `NO_TRAIL` / `UNKNOWN` / final `MEMBERSHIP:` line).
  - `lib/sitrep_todo.py`, `aitask_sitrep_todo.sh`: `direction-set --with-situation` (summary and situation text in one write) and `situation --expect-rev` (optional guard, under the lock).
  - `.claude/skills/aitask-sitrep/SKILL.md.j2` and its three goldens: the `>d` capability, the guarded `>w` with its pause, direction questions in `>q`, the direction order in `>p`, Step 0, Writing, the TUI and Guardrail sections.
  - Tests: `tests/test_trail_membership.py` (new, 10), `tests/test_sitrep_todo.sh` Tests 18p and 18s (660 -> 728 assertions), `tests/test_sitrep_skill_contract.sh` (section f, new checks a/b, mutants; 128 assertions), `tests/test_skill_render_aitask_sitrep.sh` (the `>d` heading).
  - Docs: `aidocs/framework/sitrep.md`, `website/content/docs/workflows/sitrep.md` (section "Work directions and implementation trails"), `website/content/docs/skills/aitask-sitrep.md`, `website/content/docs/concepts/implementation-trails.md`; the caller note in the header of `aitask_sitrep_refresh.sh`.
- **Deviations from plan:**
  - The "Requests from the sitrep TUI" line for `>d` is left to t2335_5 (planning decision 2), against the task text.
  - Two writer extensions and one read verb were added during planning and plan review; the task text named none of them.
  - The docs review of the post-phase was a self-review of the changed sections by their author, not an independent reader.
- **Issues encountered:**
  - `direction-assign` answers `DIRECTION:<slug>|unchanged|<rev>` (rev not moved) for a block that already read `unknown`; the plan assumed `updated`. The skill and the contract test state both forms. It makes the rev verification of `>d` step 7 necessary even more often.
  - A wave alone does not block: only an earlier-wave entry classified `hard_prerequisite` is a strong edge; `core` / `preferred_predecessor` are `ADVISORY:`. The website's worked example and the skill's line list say so.
  - Pre-phase: the first post-move run of `tests/test_sitrep_tui_app.py` reported 1 failed / 89 passed while three other suites ran concurrently; the failing test's name was not captured. Two re-runs (one under the same load) and the final run gave 90 passed. Treated as a load flake, not explained further.
  - A harness with `rm -rf "$var"` was refused by the agent's safety check; the mutant harness below uses fresh `mktemp` directories and removes nothing.
- **Key decisions:** one eligibility rule shared by `>d` and `>p` (a blocked trail reading wins; every candidate needs `Status: Ready` from `aitask_ls.sh -v --all-levels 9999`); coverage claims need every ref passed and at least one task ref; a summary is written from its baseline file only; texts that must agree are one write; every direction write carries a compared rev.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t2335_5: add the `>d <direction>` (and store-wide `>d`) line to the skill's "Requests from the sitrep TUI" section together with the `AGENT_REQUESTS` row, and regenerate the goldens; parity check r forces it. Import membership types from `lib/trail_membership.py` (the TUI module re-exports them). A direction saved by `>d` reads `unknown` until a refresh. The workflow page's new section shows the `ait trails --highlight` command where the `z` key will go.
  - t2335_6: between "the agent rewrites it" and "the row reads current" a refresh (`r`) is needed. `>w` may now refuse to write and offer `>d <direction>`.
  - t2199: include `>d` in the Codex / OpenCode end-to-end check (heredoc stdin to `snapshot` / `recheck` / `direction-*`, the one confirmation, the nested `/aitask-trail` offer).

### Pre-phase evidence: baseline_tui_trail_tests

| File | before the move | after the move (final run) |
|---|---|---|
| `tests/test_sitrep_tui_trails.py` | 14 passed | 14 passed |
| `tests/test_sitrep_tui_trails_actions.py` | 26 passed | 26 passed |
| `tests/test_sitrep_tui_app.py` | 90 passed | 90 passed (first post-move run: 1 failed, see "Issues encountered") |
| `tests/test_sitrep_tui_actions.py` | 81 passed | 81 passed |

### Post-phase evidence: guard mutants

Control: 7 membership-line tests and 728 writer assertions pass. Every mutant was killed:

| Mutant (the guard removed) | A failing assertion that names it |
|---|---|
| a partial scan is `UNKNOWN` | `test_a_partial_scan_keeps_what_it_found_and_never_says_no_trail` |
| a foreign ref is not searched | `test_a_task_of_another_project_is_never_searched`, `test_uncovered_needs_every_ref_to_be_no_trail` |
| the `situation` rev guard | "session one's guarded write is refused" (got `SITUATION:alpha|set`) and 7 more |
| the paired text is validated before the write | "an over-long text -> exit 2" (got 0) |
| `unchanged` compares the text | "a pair that changes only the text -> updated" (got `unchanged`) |
| `--with-situation` needs `--summary-file -` | "--with-situation without --summary-file - -> exit 2" (got 0) |

The harness, verbatim (`bash mutants.sh <repo root> <scratch parent dir>`):

```bash
#!/usr/bin/env bash
# guard mutants (t2335_4): remove one guard at a time in a SCRATCH COPY of the
# tree and run the tests that name it. Never touches the working tree, and
# removes nothing: every copy goes into a fresh mktemp directory.
# Usage: mutants.sh <repo root> <scratch parent dir>
set -uo pipefail
REPO="$1"
PARENT="$2"
PY="$HOME/.aitask/venv/bin/python"
WORK="$(mktemp -d "$PARENT/mutants.XXXXXX")"
mkdir -p "$WORK/base/tests/fixtures"
cp -a "$REPO/.aitask-scripts" "$WORK/base/.aitask-scripts"
cp -a "$REPO/tests/lib" "$WORK/base/tests/lib"
cp -a "$REPO/tests/fixtures/sitrep" "$WORK/base/tests/fixtures/sitrep"
cp "$REPO/tests/test_sitrep_todo.sh" "$REPO/tests/test_trail_membership.py" \
   "$REPO/tests/test_trail_links.py" "$WORK/base/tests/"
find "$WORK/base" -name __pycache__ -type d -prune -exec rm -r {} +

MEMBER_CMD="$PY -m pytest -q tests/test_trail_membership.py -k MembershipLinesTests -p no:cacheprovider"
WRITER_CMD="bash tests/test_sitrep_todo.sh"
show() { grep -E "^FAIL|^FAILED|passed|failed|^Results" | cut -c1-210 | head -8; }

echo "=== CONTROL (no mutation)"
(cd "$WORK/base" && $MEMBER_CMD 2>&1 | show; $WRITER_CMD 2>&1 | show)

# mutant <name> <test command> ; the python patch comes on stdin
mutant() {
    local name="$1" cmd="$2" tree="$WORK/$1"
    cp -a "$WORK/base" "$tree"
    if ! python3 - "$tree" /dev/fd/3 3<&0 <<'PYEOF'
import sys
tree = sys.argv[1]
def sub(rel, old, new):
    p = tree + "/.aitask-scripts/" + rel
    s = open(p, encoding="utf-8").read()
    assert s.count(old) == 1, (rel, s.count(old), old[:50])
    open(p, "w", encoding="utf-8").write(s.replace(old, new))
exec(open(sys.argv[2]).read())
PYEOF
    then echo "=== MUTANT $name: PATCH DID NOT APPLY"; return; fi
    echo "=== MUTANT $name"
    (cd "$tree" && $cmd 2>&1 | show)
}

mutant partial_scan_is_unknown "$MEMBER_CMD" <<'EOF'
sub("lib/trail_membership.py", """        if self.partial:
            return TaskTrails(UNKNOWN, reason=self.partial)
""", "")
EOF

mutant foreign_ref_not_searched "$MEMBER_CMD" <<'EOF'
sub("lib/trail_gather.py", """        if project != local_name:
            counts[tm.UNKNOWN] += 1
            lines.append(f"UNKNOWN:{ref}|cross_repo_not_searched")
            continue
""", "")
EOF

mutant situation_guard "$WRITER_CMD" <<'EOF'
sub("lib/sitrep_todo.py", """    if guarded and not _expect_direction(slug, d, expect):
        return
""", "")
EOF

mutant paired_text_validated_before_the_write "$WRITER_CMD" <<'EOF'
sub("lib/sitrep_todo.py", """            situation = validate_situation(rest)
            text = first
""", """            situation = [ln for ln in rest.split(chr(10)) if ln]
            text = first
""")
EOF

mutant paired_unchanged_compares_the_text "$WRITER_CMD" <<'EOF'
sub("lib/sitrep_todo.py", """    if (old is not None and old.header_lines() == new.header_lines()
            and old.situation == new.situation):
""", """    if old is not None and old.header_lines() == new.header_lines():
""")
EOF

mutant paired_needs_summary_file "$WRITER_CMD" <<'EOF'
sub("lib/sitrep_todo.py", """    if args.with_situation and not args.input:
        raise RequestError("--with-situation goes with --summary-file -")
""", "")
sub("aitask_sitrep_todo.sh", """        [[ "$summary" == true ]] || err_usage "--with-situation goes with --summary-file -"
""", "")
EOF
echo "=== done ($WORK)"
```

### Post-phase evidence: walk_rendered_d_flow

Scratch project: tasks t12, t31 (`depends: [12]`), t60 (parent of t60_1), t51 (`depends: [52]`), t52, t70; one stored trail `art:trail-checkout` (wave 1: t12, t60; wave 2: t31); items c1..c7 (c7 = `other#5`). Every command was taken from the rendered skill. Result lines, verbatim:

```
step 2   IN_TRAIL:walk#31|art:trail-checkout|2|Checkout trail
         NO_TRAIL:walk#51 / NO_TRAIL:walk#70 / UNKNOWN:other#5|cross_repo_not_searched
         MEMBERSHIP:in=3|none=2|unknown=1|scan=complete|-
         HIGHLIGHT:walk#31|2|open|blocked|1|Ready|-   NEXT:walk#12|1|stale
         BLOCKED_BY:walk#31|walk#12|1|depends|open|-   PATH:walk#12|1|depends|open|next|Ready|-   ADVISORY:walk#60|1|open|-
picker   t31_task.md [Status: Blocked (by 12), ...]   t51_task.md [Status: Blocked (by 52), ...]
         t60_task.md [Status: Has children, ...]      t60_1_task.md [Status: Ready, ...]
         highlight 60: NEXT:walk#60|1|stale  (the trail's next is a parent; the pick is its Ready child)
(a)      SNAPSHOT:checkout|e92ef8f7a67a8cf5|baselines/e92ef8f7a67a8cf5.txt|2|0   SNAPSHOTS:2|0   RECHECK:same
         ASSIGNED:c2|checkout|9 ... DIRECTION:checkout|unchanged|8   (rev and fields equal the step-1 state)
         DIRECTION:checkout|updated|13 (paired)   DIRECTION:payments|created|14   RANKED:checkout|1|15   RANKED:payments|2|16
         after the TUI's refresh: REFRESH_DIRECTION:checkout|unknown->current|applied|
(b)      move c5 payments->checkout, payments dropped: no assign line; checkout re-snapshotted without c5;
         DIRECTION:checkout|updated|25; payments block, members and rank unchanged
(b')     checkout dropped instead: payments re-snapshotted with c5; DIRECTION:payments|updated|26; checkout block unchanged
(c)      RECHECK_REASON:payments|member_closed|1|c4   RECHECK:changed|1   exit 1   nothing written; then re-read, snapshot, RECHECK:same, DIRECTION:payments|updated|28
(d)      >d checkout: DIRECTION:checkout|updated|29; payments rev 28 -> 28, both ranks kept
(h)      rank-only swap: RANKED:payments|1|30 RANKED:checkout|2|31; baselines 6 -> 6 (no snapshot)
(f)      empty order without --clear: exit 2; with --clear: UNRANKED:checkout|32 UNRANKED:payments|33
(j)      >w checkout after c2 closed: draft and summary disagree after the re-read -> no situation call;
         >d checkout: DIRECTION:checkout|updated|37 (one --with-situation call; summary and text agree)
         race: a second session's pair, then `situation payments --expect-rev 35` -> STALE:payments|40, the pair intact
(l)      a second shell writes checkout's situation text after the confirmation; ASSIGNED:c6|checkout|39
         DIRECTION:checkout|unchanged|38; block rev 38 == printed rev, but the situation text differs from the
         step-1 state -> no direction-set; the assignment stays
(k)      256 ids + --highlight-total=257: accepted; 257 ids: refused; a 513-character slug: refused, left out: accepted
```

In (c) the operator's script took one digest from a directory listing instead of the `SNAPSHOT:` line; the refusal shown is the real one for that proposal. Prose fixed because of the walk: the `PATH:` / `ADVISORY:` / `LANDED:` / `RELEASED:` / `SUPERSEDED:` / `TRAIL:` / `FRESHNESS:` / `SUMMARY:` lines were unexplained; `RECHECK_SAME:` was not named; the digest's source and how to spot a parent's children were not stated; the picker's listing was missing from the "never in a summary" rule.

### Post-phase evidence: docs_current_state_check

A grep of the added website lines for a Directions tab, a request key for `>d` or `z` on a direction found none. The docs review found one level finding on `workflows/sitrep.md` (two status tokens quoted as code on an intermediate page), reworded. `check_links.py --build`: SWEEP: PASSED; `check_screenshots.py`: PASSED.

## Post-Review Changes

### Change Request 1 (2026-11-27 11:40)
- **Requested by user:** five review findings on the skill text: the confirmation showed only a "text rewritten" marker; a partial or failed membership scan could erase a saved trail link; a parent's Ready child was named without its own trail evidence; unversioned (older-format) blocks and block-less directions have no rev to compare; `>p` repeated the whole-project membership scan per direction.
- **Changes made:** the confirmation carries each replaced situation text in full; a saved link is removed only on a complete scan with no `UNKNOWN:` ref and no `IN_TRAIL:` line for it, otherwise every saved link is kept; a child (and a `(by …)` task) gets its own `membership` + `critical-path` before it is named; step 1 documents the two rev-less cases (`absent`); `>p` runs `membership` once for all ranked directions. Goldens regenerated.
- **Files affected:** `.claude/skills/aitask-sitrep/SKILL.md.j2`, `tests/golden/skills/aitask-sitrep/SKILL-{default,fast,remote}-claude.md`
- **Evidence:** the format-3 case was reproduced on a copy of `tests/fixtures/sitrep/store_v3` (`DIRECTION:sitrep|-|…`, heading `#### sitrep` followed directly by its text). NOT exercised in a walk: an unreadable saved trail (a partial scan), and a child blocked in a later wave than its parent; both rules are prose only.

### Change Request 2 (2026-11-27 12:05)
- **Requested by user:** rule 3 of the eligibility rule let the picker's verdict alone stand on "no linked trail" without a complete negative membership result for the candidate.
- **Changes made:** the picker-only fallback needs the candidate's own `NO_TRAIL:` line. With `UNKNOWN:` and no `NEXT:` line from a trail that was read, the task is not named and the pick is reported as not verifiable. Goldens regenerated.
- **Files affected:** `.claude/skills/aitask-sitrep/SKILL.md.j2`, the three goldens
- **Evidence (scratch project, a second trail `art:trail-kids`: wave 1 `t52` as `hard_prerequisite`, wave 2 the Ready child `t60_1`):**

```
manifest of the trail broken:
UNKNOWN:walk#60_1|art:trail-kids did not load
UNKNOWN:walk#70|art:trail-kids did not load
MEMBERSHIP:in=0|none=0|unknown=2|scan=partial|art:trail-kids did not load     -> t60_1 is not named as a pick
manifest restored:
IN_TRAIL:walk#60_1|art:trail-kids|2|Kids trail
HIGHLIGHT:walk#60_1|2|open|blocked|1|Ready|-
BLOCKED_BY:walk#60_1|walk#52|1|wave|open|-                                     -> blocked; its parent's NEXT: said nothing about it
```

  The same run shows a partial scan reporting no `IN_TRAIL:` line for a trail that does hold the task, which is the case the "keep saved links" rule of Change Request 1 covers.
