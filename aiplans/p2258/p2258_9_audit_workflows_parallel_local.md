---
Task: t2258_9_audit_workflows_parallel_local.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_*_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-12 19:40
---

# t2258_9: Workflows audit, Parallel group (local part)

## Context

Split from t2258_4 at its planning (2026-11-12). This child audits six pages of
`website/content/docs/workflows/` (about 950 lines) against the level model in
`aitasks/metadata/doc_update_guide.md`, using `aitask-docs-review`. The method
binding it is the task body's "Method (binding)", which follows the parent
plan's "Common audit method".

## Verification of the existing plan (verify path, 2026-11-12, main @ 86d4f4aba)

The pending plan was a skeleton: the right steps, but no inventory and no
restructure design. Checked against the tree:

- **Five of the six pages are clean.** `crash-recovery.md` became dirty during
  planning: t2284 is editing its L71 bullet (see the ledger). Their likely
  destination pages are clean too, except `skills/aitask-pick/_index.md`, which
  another session has dirty (Codex questions work, along with nine other
  `skills/` pages and `commands/codeagent.md`). **None of the dirty pages is a
  destination in this plan.** The shared-file gate still runs before every
  edit.
- **t2284 is `Implementing`.** It owns the `crash-recovery.md:71` bullet ("Your
  own session re-claiming…"), and it is editing that bullet now. While
  t2284's edit is uncommitted, the page is not touched (ledger). Once it is
  committed, its new bullet is audited like any other text. If the page is
  audited here, t2284 gets a note with the bullet's new location (Step 8e).
- **Note from t2258_4 (acknowledged, advisory):** `check_link_relevance`
  flags `crash-recovery.md:30` (`aitask_lock.sh` → commands/lock) and
  `parallel-development.md:46` (`/aitask-pick` → parallel-admission). Both
  are triaged below.
- **Facts moved in by t2258_3** stay on workflow or development pages, never
  on concept pages: the crash-recovery lock outcomes, `parallel-development`
  § Serialized Merge-Back (the intermediate summary of
  `development/merge-mutex.md`), and the framework-session links.
- **Inbound anchors** (they break silently if a heading is renamed):
  - `crash-recovery#lock-anomaly-fallback` ×2, `#multi-pc-reclaim`,
    `#when-the-holder-is-still-running` and `#when-the-recovery-path-fires`,
    all from `commands/lock.md`;
  - `freeze-and-restore-agents#what-unverified-means`, from
    `commands/setup-install.md` and `development/framework-session.md`;
  - `freeze-and-restore-agents#when-something-goes-wrong`, from
    `development/framework-session.md`;
  - `freeze-and-restore-agents#before-shutting-down`, from
    `installation/terminal-setup.md`;
  - `implementation-trails#where-a-trail-is-stored`, from
    `concepts/artifacts.md` and `skills/aitask-trail.md`;
  - `implementation-trails#creating-a-trail`, from `tuis/trails/how-to.md`;
  - `parallel-development#git-worktrees-for-isolation`, from
    `development/merge-mutex.md`.

  **Rule:** keep each of these headings, or retarget every inbound link in the
  same change. All the linking files are clean at planning. Re-run the grep
  before editing.
- **Public, not contributor-only (guide rule):**
  - `aitask_frozen.sh`: the site tells readers to run it, and its usage text
    lists `gone`, `reopen`, `companions`, `restore --all` and `reconcile`.
  - `aitask_pick_own.sh --help` documents its `LOCK_*` / `RECLAIM_*` output.

  Both contracts go to `advanced` reference pages.
- **No `ait ide` reference page exists.** The frozen-agent check that `ait ide`
  runs at startup belongs to the frozen-agent reference page.
- `record_gates` is set in `fast.yaml`. Its default is off.
  `crash-recovery` says "on by default for the `fast` profile". That means set
  in the shipped `fast` profile; reword it to say so.
- **No fresh-reader runs.** After the retags no page in the group is
  `main-concept`, so `--budget 0`.

## Inventory (measured at 86d4f4aba, before any edit)

rows = table rows, em = em dashes, bold = bold spans, status = `KEY:`
status-line tokens. Every page is a how-to (it sits under `workflows/`).
AP = Diátaxis anti-pattern.

| Page | Lines | rows/em/bold/status | depth before → after | Verdict | Violations |
|---|---|---|---|---|---|
| `freeze-and-restore-agents` | 316 | 17/38/56/0 | intermediate → intermediate | **restructure** | AP5: the steps sit among reference blocks: per-CLI restore eligibility (L74–95), the `ait ide` startup check (where agents land, which projects are acted on, companions, untracked records, the no-terminal case), the script command list, Restore-All rules, the unverified outcome table, failure shapes, reconcile and mark rules. Level: an internal path (`~/.config/aitasks/frozen/<id>/`, `capture.*`) and outcome tables. Prose: it is the guide's own avoid-list sample (staged contrast L35, run-up L58, deep saying L19, repeated openings L13, em-dash connectors L9–10), plus "yet" (L87, current-state). The R/P explanation is repeated from `tuis/frozenagent/how-to`. |
| `crash-recovery` | 188 | 10/48/50/9 | intermediate → intermediate | **restructure** | AP2/AP5: it teaches the lock mechanism (PID-anchor resolution order, the `/proc`→`ps`→`kill` liveness lookup, start-time tokens and kinds, macOS) inside a how-to. A 4-row verdict table and a 2-row signal table are outcome tables. Level: 9 status-line tokens (`RECLAIM_CRASH:` …) and internal mechanics (`git worktree list --porcelain`, the plan-marker heuristics). The End-to-End Example repeats the steps (how-to growth sign). Current-state violations: "predates the PID-anchor work" (L46), "Without this flow… the older wording" (L149), "is no longer needed… now means" (L176). Prose: 48 em dashes, 50 bold spans. |
| `implementation-trails` | 162 | 13/39/48/0 | advanced → advanced | **restructure** (moderate) | AP5: its three-paragraph "why" opener repeats `concepts/implementation-trails` (with a bold thesis and "until now", a current-state violation). The refresh-key cost table repeats `tuis/trails/reference#what-each-refresh-reads` and `tuis/board/reference#by-trail`. "Where a Trail Is Stored" is reference material owned by `skills/aitask-trail#storage`. "What a Trail Never Does" repeats `skills/aitask-trail#invariants`. Prose: 39 em dashes, 48 bold spans, "worth knowing", inflated "most of the value". Keep `advanced`: it matches its concept page, and the page names classification vocabularies. |
| `sitrep` | 133 | 9/22/45/0 | intermediate → intermediate | **restructure** (condense) | Fragmented into 12 `##` sections, not one procedure. Level: internal paths (`.aitask-sitrep/`, `raw/`, `cases/`). The shortcode table repeats `skills/aitask-sitrep#capabilities` and `tuis/sitrep/reference#requests`. The `ait sitrep case` five-command block and the `h` dialog's three outcomes are reference material (an outcome list). Prose: 45 bold spans, 22 em dashes. |
| `parallel-planning` | 76 | 0/17/11/0 | advanced → **intermediate** | minor | Nothing on it needs `advanced`: its reader picks and decomposes tasks (the `intermediate` persona). Prose: "zero risk", "double verification", bold-led bullets with em dashes, "This is the interactive part". Facts to check: "automatically verified" depends on the profile's `plan_preference_child`; the parent "auto-archives". |
| `parallel-development` | 75 | 0/9/12/0 | advanced → **intermediate** | minor | AP4/AP5: "How Concurrency Is Managed" explains internals (compare-and-swap, the `aitask-locks` / `aitask-ids` / `aitask-data` branches) that `concepts/git-branching-model` and `commands/lock#how-it-works` already state. Shorten it to plain bullets that link there. Keep § Serialized Merge-Back (t2258_3's summary). Relevance flag L46: the link text `/aitask-pick` points at the parallel-admission page; name the preflight in the link text. "zero risk" also needs fixing. |

**Retags:** `parallel-planning` and `parallel-development` drop to
`intermediate`. Every other page in the Parallel group is `intermediate`,
except `implementation-trails`, which keeps `advanced` with its concept page.
After the edit both pages contain only what `intermediate` allows: profile
keys (`create_worktree`, `output_branch`, `parallel_assessment`) and the
user's own task/plan directories.

## Steps

### Step 1: Shared-file gate (before every edit, source and destination)

Run `git diff --quiet HEAD -- <page>` and `git status --short -- <page>`. A
dirty page is not edited. It goes into the **skipped-page ledger** below
(path, reason, dirty state seen). When a dirty page is a destination, its
facts stay on the source page until close-out.

### Step 2: Restructure (parallel agents on disjoint file sets, one brief)

This is the sibling method that worked. A scratchpad `restructure_brief.md`
summarises the guide's rules for these pages:
- the level contracts;
- how-to shape: goal, numbered steps, outcome;
- the moved-fact table format;
- check every moved fact in the code;
- use `relref` for new links;
- keep the inbound-anchor headings;
- no table rows in `development/task-format.md`;
- never pipe generated files through `tee | head`.

Each agent returns its files changed, its moved-fact rows, its code-verified
corrections and its open points. I review every diff before Step 3.

**Agent A: `freeze-and-restore-agents.md`.** It may edit:
`tuis/frozenagent/reference.md` and `development/framework-session.md`.
- **The page keeps:**
  - a two-sentence intro (what freezing does and why);
  - "When to freeze": the Live/Parked/Frozen table, without the disk path and
    without the staged-contrast paragraph;
  - one numbered daily procedure: freeze (`f`), read (`G`, `r`, `m`, search,
    copy), come back (R restore / P re-pick, which one to choose, keys pressed
    in the viewer, a verified restore deletes the capture, so copy first),
    drop (`k`);
  - "Before shutting down" (anchor kept): `Z`, reboot, `ait ide`, the four
    answers as a short list, and one sentence on where agents land, linking
    to the reference;
  - "What "unverified" means" (anchor kept): 2–3 sentences, linking to the
    reference outcomes;
  - "When something goes wrong" (anchor kept): a failed restore keeps the
    capture; `cannot restore` → re-pick; run
    `./.aitask-scripts/aitask_frozen.sh reconcile` to settle stuck records;
  - "Limits": records never expire; the capture is the tail of the
    scrollback, set by `frozen.capture_max_lines`;
  - See also.
- **Moves:**
  - Per-CLI restore eligibility → `development/framework-session#which-cli-owns-the-session`.
    Most of it is already stated there. Add the facts that are missing (the
    Codex shell foreground-job rule with `-c tui.alternate_screen=never`, and
    naming the model from `-m` or the record), each checked in code. Drop
    "yet".
  - The `ait ide` frozen-agent check → new `tuis/frozenagent/reference.md`
    § "The `ait ide` frozen-agent check". It covers:
    - the listing;
    - the V/R/P/S answers;
    - "all questions first";
    - where each project's agents land;
    - which projects are acted on, with the three skip reasons;
    - companion top-up;
    - the two untracked-record states;
    - the no-terminal note;
    - `--no-frozen-check`.
  - The `aitask_frozen.sh` command forms (`gone`, `reopen`, `companions`,
    `restore --all [--repick]`, `reconcile`) and the Restore-All rules (runs
    sequentially, one failure never stops the batch, which records fail the
    first form, the `-2` suffix, a new session created like `ait ide` does)
    → new `development/framework-session.md` § "The freeze engine", checked
    against `aitask_frozen.sh` usage.
  - Unverified table, Codex first-turn hook, grace semantics →
    `tuis/frozenagent/reference#states-shown` / `#configuration` and
    `development/framework-session#restore-verification`. These are mostly
    already-stated; add any missing claim.
  - Failure shapes and the respawn/unmark/reconcile cadence →
    `development/framework-session#operation-leases` / `#cleanup-rules`.
  - Marks and the `P` filter counters: already stated in
    `tuis/monitor/reference.md` (L39, L142–144). They are linked from there,
    and agent A does **not** edit that page.
  - Disk path and capture files: already stated in
    `development/framework-session#where-the-state-lives`.
- **Prose:** rewrite using the guide's own Afters where its examples are
  quoted from this page.

**Agent B: `crash-recovery.md`.** It runs last, and only if the re-gate finds
the page clean (see the ledger). It may edit `commands/lock.md` and
`aidocs/gates/ledger-driven-reentry.md` (§ "Crash-recovery generalization"
only).
- **The page keeps:**
  - an intro: what happens after a crash;
  - one numbered procedure "Recover a task after a crash": re-pick; read the
    survey (example block kept, one plain line per field, no git mechanics);
    choose **Reclaim and continue** / **Pick a different task** (decline
    leaves the worktree alone); where it resumes (the three checkpoint
    bullets, short; `record_gates` reworded); the remote check before
    resuming (short).
  - "When the Recovery Path Fires" with its three `###` subsections, each
    1–3 plain sentences, no signal names (anchors kept).
  - "When the Holder Is Still Running" (anchor kept): plain words, with the
    refusals and what to do. It includes t2284's committed re-claim bullet,
    with its meaning kept and its claim checked in code.
  - Tips, trimmed: outside tmux / `AIT_AGENT_PID`; the board lock is
    anchored to the board; a planned shutdown → freeze; cross-host is the
    same procedure.
  - See also.
- **Moves → `commands/lock.md`** (advanced):
  - New `### The session anchor` under How It Works:
    - pid resolution order (`AIT_AGENT_PID` must exist; `$TMUX_PANE` checked
      against its own server; else `pid: -`, no further fallback);
    - the liveness lookup (`/proc`, `ps`, `kill`; gone only on "No such
      process"; "not permitted" = exists; `hidepid` → unknown);
    - the start-time token and `pid_starttime_kind` (`proc`, `bsdinfo`,
      `ps`, the one-second `ps` rule, crash detection unaffected);
    - the dead/alive/unknown/no-anchor verdict table;
    - `pid: 0` from `aitask_backfill_pid_anchor.sh`: optional, and no signal
      change.
  - Extend `### When a Pick Meets a Held Lock`:
    - the signal names per row (`RECLAIM_CRASH`, `LOCK_RECLAIM`,
      `RECLAIM_STATUS`, `LOCK_LIVE_HOLDER`, `LOCK_UNVERIFIABLE_HOLDER`) with
      their field formats, checked against `aitask_pick_own.sh --help` and
      task-workflow Step 4;
    - "only a provably dead anchor is reported as a crash";
    - the three prompts' question wording and the shared option list;
    - "refusals happen before lock/status/commit";
    - `/aitask-pickrem` aborts rather than forcing.
  - Retarget lock.md's links into crash-recovery only if an anchor changes
    (none planned).
  - Survey-line derivation is contributor-only, and it **moves to
    `aidocs/gates/ledger-driven-reentry.md` § "Crash-recovery generalization"**.
    That is the existing engineering doc for the crash-recovery survey (clean
    at planning; it already says the survey reads the gate ledger first).
    Extend that section with:
    - worktree resolution from the `branch refs/heads/aitask/<task_name>`
      entry of `git worktree list --porcelain`, and the two situations behind
      `(none — current branch, or fork not reached)`;
    - the file counts from `git status --porcelain` and
      `git diff --stat HEAD` against the resolved worktree;
    - the plan-file fallback marker (a "Final Implementation Notes" stub,
      `- [x]` steps, "Post-Review Changes"), used when no checkpoints were
      recorded.

    Check each fact against `.claude/skills/task-workflow/crash-recovery.md`
    and `aitask_gate.sh status` first. Each fact gets a `moved` row naming
    that destination, never `dropped`. `aidocs/gates/ledger-driven-reentry.md`
    goes through the shared-file gate like every other destination.
  - "End-to-End Example": merged into the procedure (its facts are already
    in the steps).
  - Current-state sentences: rewritten positively.
- **Relevance flag L30:** the sentence moves to `commands/lock.md`. Its
  `aitask_lock.sh` link text becomes `ait lock`, or the link is dropped
  because it is on its own page.

**Agent C: `implementation-trails.md` + `sitrep.md`.** It may edit:
`skills/aitask-trail.md`, `tuis/trails/reference.md`,
`tuis/board/reference.md` (By-Trail region only), `concepts/artifacts.md`
(link retarget only), `tuis/sitrep/reference.md`, `skills/aitask-sitrep.md`
and `tuis/monitor/reference.md` (the `h` row region only).
- **implementation-trails keeps:**
  - a one-paragraph intro linking the concept page;
  - "What a Trail Records": the glyph legend, observations and exclusions;
    the maintainer HTML comment stays (source-only, never rendered);
  - "Creating a Trail" as steps (anchor kept), with Lite and Deep;
  - "Reading a Trail on the Board" as steps;
  - "Keeping a Trail Current": the stale badge, press `d` first, `R`
    re-authors, one line on `S`, link to the reference for the rest;
  - "Feeding a Work Report" as steps;
  - "Where a Trail Is Stored" (anchor kept): 2–3 sentences, linking to
    `skills/aitask-trail#storage`;
  - a short "never does" list that links to the invariants;
  - Tips, trimmed;
  - the `**Next:**` footer.
- **implementation-trails moves:**
  - The owner, discovery (active and archived), fold copying and
    one-document-several-views rules → `skills/aitask-trail#storage`.
  - The refresh-cost table → already-stated at
    `tuis/trails/reference#what-each-refresh-reads` and
    `tuis/board/reference#by-trail`; add only the missing claims.
  - The `M` details (always reviews the list, keeps wave order, names
    skipped items, ghosts cannot move) → `tuis/board/reference#by-trail`, if
    not already there.
  - Drop "until now".
- **sitrep keeps** one flow:
  1. open (`ait sitrep`, one window per repository, the three panes, `S`
     from the TUIs, outside tmux → `ait codeagent invoke sitrep`);
  2. what happens at start;
  3. read the list;
  4. triage (`t` / `>t`), including output the harvest could not read
     (anchor kept), with `ait sitrep case list` and `replay` as the two
     commands a user needs, linking to the rest;
  5. ask;
  6. dismiss;
  7. close finished agents with `h` (the outcomes in one plain sentence each;
     no close is offered when nothing was certified).

  Plus "Where the list lives" in plain words (local to this checkout, never
  committed, `R` restores it from the backup), the shortcodes as one sentence
  linking to `skills/aitask-sitrep#capabilities`, and See also.
- **sitrep moves:**
  - `.aitask-sitrep/`, `raw/`, `cases/`, the locked writer and rolling
    backup → `tuis/sitrep/reference.md` (the "Launch and environment" or a
    new "Where the list is stored" section; check `aidocs/framework/sitrep.md`
    for the contributor-only part).
  - The `ait sitrep case` command list → `tuis/sitrep/reference.md` or
    `skills/aitask-sitrep.md`, whichever already documents `case` (check
    first).
  - The `h` dialog outcomes → `tuis/monitor/reference.md` `h` row, if not
    stated.
  - The shortcode table → already-stated at `skills/aitask-sitrep#capabilities`.

**Me: `parallel-planning.md`, `parallel-development.md`,
`workflows/_index.md`.**
- parallel-planning:
  - fix the prose;
  - check "automatically verified" against `plan_preference_child` in the
    shipped profiles and say "verified, or offered for verification,
    depending on the profile" as the code says;
  - check auto-archive;
  - retag to `intermediate`.
- parallel-development:
  - shorten "How Concurrency Is Managed" to plain bullets with links
    (already-stated rows);
  - keep Serialized Merge-Back and the `#git-worktrees-for-isolation` heading;
  - triage relevance L46 (link text "parallel-admission preflight");
  - fix "zero risk";
  - retag to `intermediate`.
- `_index.md`: change a Parallel bullet only if a page's description changes.
  Keep each page's position.

### Step 3: Feed lessons into the guide (last planned guide change)

Add short additions to existing sections, only for what this group showed.
Candidates:
- a how-to page that teaches the mechanism behind its prompt (crash-recovery);
- a workflow page that repeats its concept page's "why" (trails);
- a duplicated key or shortcode table (sitrep, trails).

Keep the `## Reader levels` interface lines byte-identical and each prose-rule
bullet on a single line. Run `bash tests/test_docs_review_contract.sh`. The
guide lives on the task-data branch: commit it by path with
`aitask_task_commit.sh`.

### Step 4: Review under the final guide

An independent agent runs `/aitask-docs-review <every edited or created page>
--caller audit --budget 0`, covering the six pages plus every destination
page (changed regions for the long ones). Fix the findings within the
skill's invariants. A cut fact gets a moved-fact row. Re-review each page a
fix changed. Record `level=… prose=… reader=…` and unresolved findings per
page here.

### Step 5: depth

Every leaf page in the group has `depth:`. Record
`grep -L '^depth:' website/content/docs/workflows/{freeze-and-restore-agents,crash-recovery,implementation-trails,sitrep,parallel-planning,parallel-development}.md`
(expected empty) and the depths of the edited destination pages.

### Step 6: Links

- `cd website && python3 check_links.py --build`: must exit 0.
- `python3 check_link_relevance.py`: open every reported target this child
  added or retargeted, plus the two flagged lines (crash-recovery:30 and
  parallel-development:46), and record a verdict for each.
- `bash tests/test_website_doc_lists.sh` and
  `bash tests/test_docs_vocabulary_coverage.sh`.

### Post-phase (risk mitigations)

1. [moved_fact_survival_check] The claim-level survival check, before the
   commit (the task's method step 8):
   a. A scratchpad `removed_blocks.py` splits `git show HEAD:<page>` and the
      working text of every page text was cut from into blocks (paragraph,
      list item, table row, admonition, code block). It lists every HEAD
      block missing byte-for-byte from the working version, and writes its
      files directly.
   b. One fresh sub-agent per source page (not the editor) gets the removed
      blocks verbatim, plus the full current text of the source and every
      destination its moved-fact rows name. It classifies every claim (rule,
      condition, exception, consequence, scope, default) as `preserved`
      (quote + page#section), `weakened` or `missing`.
   c. Fix every `weakened` / `missing` claim, or record it `corrected` (code
      evidence) or `dropped(reason)`.
   d. Re-run on the fixed claims once. Record per page: claims, preserved,
      fixed, corrected, dropped, and the run-2 result.
   e. A page changed in (c) goes back through Steps 4 and 6.

### Step 7: Ledger close-out (with a mandatory late-audit loop)

Re-check each skipped-page ledger entry against HEAD:
- **Still dirty** → create a child of t2258 with `--no-sibling-dep`, named
  `audit_deferred_pages_workflows_parallel_local`. It carries the page's
  inventory row and its restructure design from this plan.
- **Now clean** → audit it here, through the **late-audit loop**. No page
  audited at close-out may reach the commit on the strength of checks that
  ran before it was edited. For the late page **and every destination its
  restructure touched** (for crash-recovery: `commands/lock.md` and
  `aidocs/gates/ledger-driven-reentry.md`), run in order:
  1. Step 1 gate on the page and each destination, then Step 2's
     restructure;
  2. Step 4 review (`/aitask-docs-review … --caller audit --budget 0`, by an
     independent agent) on the late page and its edited destinations; fix
     the findings and re-review the fixed pages;
  3. Step 5 depth check on the late page;
  4. Step 6 links: `check_links.py --build` re-run over the whole site, and
     `check_link_relevance.py` with every target the late edit added or
     retargeted opened;
  5. the post-phase `moved_fact_survival_check`, runs 1 and 2, on the late
     page's removed blocks against its destinations;
  6. a page changed by a fix in 2 or 5 goes back through 2 and 4.

  If a guide lesson from the late page changes the guide, re-run Step 4 on
  every page edited in this child, as Step 4 requires.

**Commit gate:** the Step 9 commit does not run until this plan records, for
every page audited at close-out, its review line (`level=… prose=…
reader=…`), its link-check result and its survival counts. A ledger page
without these records is not committed. Either finish the loop, or undo only this child's
edits to that page and its destinations by hand, with Edit and never
`git restore` in this shared worktree, so that it falls back to the
follow-up child.

Final Implementation Notes record each outcome (`audited`, with the loop's
results, or `follow-up t2258_<n>`), or "ledger empty".

## Skipped-page ledger

| Page | Reason | Dirty state seen |
|---|---|---|
| `workflows/crash-recovery.md` | t2284 (`Implementing`) has an uncommitted edit, seen at planning | One-line diff at L71. The re-claim bullet now says the pick "still asks the reclaim question (the anomaly prompt), so a re-pick is confirmed rather than silent" |

**Handling:**
- Agent B runs **last**, after A, C and my pages.
- Re-gate `crash-recovery.md` (and `commands/lock.md`) immediately before it
  starts:
  - **clean**, because t2284 committed → audit it here. t2284's new bullet is
    then ordinary text: audit it like the rest, but check its claim against
    `aitask_pick_own.sh` before rewording, and keep its meaning.
  - **still dirty** → do not edit it. The Step 7 close-out re-checks it once
    more. If it is still dirty then, create
    `audit_deferred_pages_workflows_parallel_local` (child of t2258,
    `--no-sibling-dep`) carrying the crash-recovery inventory row and Agent
    B's restructure design from this plan.
- Agent B's `commands/lock.md` additions depend on that page's cuts, so they
  move with it.

## Moved-fact table

(filled in Step 2: source#section → fact → destination#anchor →
`moved` / `already-stated` / `corrected` / `dropped(reason)`)

## Verification

- This plan holds the inventory, the moved-fact table, the survival-check
  counts and the ledger outcomes.
- `check_links.py --build` exits 0. `test_docs_review_contract.sh`,
  `test_website_doc_lists.sh` and `test_docs_vocabulary_coverage.sh` pass.
- Every leaf page in the group has `depth:`.
- `crash-recovery.md` is never edited while it is dirty from t2284: check the
  gate output recorded before Agent B. If it is still dirty at close-out, the
  follow-up child exists.
- Every inbound anchor listed above still resolves (link check).
- Each page audited at close-out has its own recorded review line, link
  result and survival counts (the Step 7 commit gate).
- The survey derivation facts have `moved` rows to
  `aidocs/gates/ledger-driven-reentry.md`, and none is `dropped`.

## Post-implementation

Step 9:
- review;
- commit the website files as
  `documentation: Audit and restructure the Parallel (local) workflow pages (t2258_9)`;
- commit the guide and plan by path with `aitask_task_commit.sh`;
- archive.

Step 8e notes, sent when the facts hold at the end:
- t2284: the new line of the re-claim bullet;
- t2258_5: the TUI reference pages that received facts (frozenagent, trails,
  board, sitrep, monitor);
- t2258_6: `commands/lock.md` § The session anchor and the extended outcome
  table, plus `skills/aitask-trail` / `skills/aitask-sitrep` additions;
- t2258_7: `development/framework-session.md` § The freeze engine.

## Risk

### Code-health risk: medium
- A restructure can lose a rule, condition or exception while about 400
  lines of reference detail move onto six other pages · severity: low
  (residual, addressed by the claim-level check) · → mitigation: inline
  post-phase moved_fact_survival_check
- A page audited late at close-out (crash-recovery, once t2284 commits)
  could skip the review, link and survival checks that ran earlier. The
  Step 7 late-audit loop and commit gate prevent this · severity: low ·
  → mitigation: none
- A renamed heading breaks an inbound anchor silently (11 inbound anchors).
  This is bounded by the keep-or-retarget rule and the link check ·
  severity: low · → mitigation: none
- The edits land on pages later siblings own (t2258_5/6/7). This is bounded
  by the shared-file gate and the Step 8e notes · severity: low ·
  → mitigation: none

### Goal-achievement risk: medium
- Moved lock and freeze facts may be stale. These pages are full of edge
  rules, and t2258_4 found about 25 fact errors in its group. Copying a wrong
  fact to an `advanced` reference page makes it look authoritative. Each
  moved fact is checked in code and recorded `corrected` when wrong ·
  severity: medium · → mitigation: inline post-phase moved_fact_survival_check
- The two retags to `intermediate` are a judgement call. They rest on the
  guide's "depth by who meets the idea", and the user reviews them at plan
  approval · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: moved_fact_survival_check | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health restructure fact loss; goal-achievement stale moved facts | desc: claim-level comparison of every removed block with its destinations by an independent sub-agent, before commit
