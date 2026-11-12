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

(source#section → fact → destination#anchor →
`moved` / `already-stated` / `corrected` / `dropped(reason)`)

### `parallel-planning.md` + `parallel-development.md` (edited in this session)

| Source#section | Fact | Destination | Outcome |
|---|---|---|---|
| parallel-planning#why-this-is-safe | "the existing plan is automatically verified against the current codebase before any code is written… double verification" | same page, rewritten | **corrected**: it depends on the profile. `fast.yaml:7` `plan_preference_child: verify` verifies unless a fresh entry under 24h exists (`aitask_plan_verified.sh decide … 1 24`). `default.yaml` sets no preference, so the agent asks (planning.md §6.0). `remote.yaml:8` is `use_current`. The remote drift check runs on every profile before Step 7. |
| parallel-planning#how-it-works (step 5) | "Each child's plan is verified against the current codebase before implementation begins" | same page, Steps 5 | **corrected** (as above): the profile-dependent wording lives in "Why this is safe" |
| parallel-planning#deferring | "offers to use it as-is, so the planning phase is skipped" | same page | **corrected**: §6.0 shows "Approved plan from … awaiting implementation", then applies the profile's plan preference (`fast` parent `use_current` skips; `default` asks) |
| parallel-planning#deferring | "if the branch you are building on has moved, you are told… and the marker is dropped" | same page | **corrected**: "Continue anyway" at the drift check keeps the marker; choosing to stop and re-verify clears it (plan-approved-stop.md:92-124, stop reasons `drift` / `drift_check_failed` / `parallel_admission`), as does any "Create plan from scratch" (planning.md §6.0-marker) |
| parallel-planning#what-you-get | the parent "auto-archives when all children complete" | same page | already true: `aitask_archive.sh:770-776` archives the parent when `children_to_implement` is empty |
| parallel-development#how-concurrency-is-managed | locks on the `aitask-locks` branch with compare-and-swap semantics | `commands/lock#how-it-works` ("Atomicity is achieved via git's push rejection on non-fast-forward updates… retries (up to 5 attempts)") and `concepts/git-branching-model` (`aitask-locks` row) | already-stated (linked) |
| same | atomic ID counter on `aitask-ids` | `concepts/git-branching-model` ("`aitask-ids` · Reservation log used to allocate fresh task IDs without collisions") | already-stated (linked); the plain bullet is kept |
| same | optional `aitask-data` branch, worktree at `.aitask-data/`, synced via `./ait git push/pull` | `concepts/git-branching-model` (`aitask-data` row, `./ait git` paragraph) | already-stated (linked); `./ait git push/pull` kept on the page |
| parallel-development#serialized-merge-back | `create_worktree: false`: "shared-checkout mode is unaffected" | same page | kept, reworded ("work in the shared checkout is not held back") |
| parallel-development#best-practices | "Run `git pull` before starting `/aitask-pick` to see the latest task status" | same page | **corrected**: `/aitask-pick` Step 0c runs `aitask_pick_own.sh --sync` before listing; `git pull` is only needed for the code branch |
| parallel-development#parallel-planning | "zero risk of conflicts" | same page | reworded: the page states the fact (no source code is changed) |
| parallel-development:46 | relevance flag: link text `/aitask-pick` → parallel-admission | same page | link text is now "parallel-admission preflight" |

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

### Restructure report, Agent A: `freeze-and-restore-agents.md`

**Files:**
- `workflows/freeze-and-restore-agents.md`: 316 → 161;
- `tuis/frozenagent/reference.md`: 124 → 239, adding § "The `ait ide`
  frozen-agent check" with six subsections, and the `capture_max_lines` row
  now says "cap plus one pane height";
- `development/framework-session.md`: 115 → 151, adding § "The freeze engine"
  and § "Restore-All", three paragraphs under "Which CLI owns the session",
  and corrected cleanup-rules cadence. The L64 link now targets
  `#the-freeze-engine`.

The gate was clean on all three files before the first edit. The three
inbound-anchor headings are byte-identical, and no destination heading was
renamed.

wf = workflow page, fs = development/framework-session, fa-ref = tuis/frozenagent/reference.

| Source#section | Fact | Destination | Outcome |
|---|---|---|---|
| wf#intro | 10–20 panes; the last screen is what you want; the process holds memory | wf#intro | condensed; facts kept |
| wf#intro | the viewer is a small app reading a file | tuis/frozenagent/_index | already-stated; the saying is dropped |
| wf#when-to-freeze | disk path `~/.config/aitasks/frozen/` | fs#where-the-state-lives | already-stated ("It goes to `~/.config/aitasks/frozen/<id>/` (mode `0700`) as two files") |
| wf#when-to-freeze | park vs freeze paragraph | wf#when-to-freeze | rewritten with the guide's After |
| wf#the-daily-loop | f, confirm, same pane, window name | wf step 1 | kept |
| wf#the-daily-loop | G/r/m, search, select, copy, clipboard from a hidden pane | wf step 2 | kept |
| wf#the-daily-loop | R/P choice and its cost | wf step 4 | kept |
| wf#the-daily-loop | keys belong to the viewer; s / Tab; monitor keys unchanged | wf step 5 | kept |
| wf#the-daily-loop | per-CLI eligibility (session id, CLI identity, raw default, refusal) | fs#which-cli-owns-the-session | already-stated (L76–78) |
| wf#the-daily-loop | OpenCode cannot resume | fs#which-cli-owns-the-session; wf step 4 | moved (`resume_unsupported:opencode`, agent_restore.py:328) |
| wf#the-daily-loop | daemon-routed hand-started Codex records no session | fs#when-it-records | already-stated; "yet" dropped |
| wf#the-daily-loop | Codex at a shell prompt: foreground job only, `-c tui.alternate_screen=never` | fs#which-cli-owns-the-session | moved (agent_sessions.py:2290ff, agent_string.sh:55–78) |
| wf#the-daily-loop | Codex model from `-m`, else the record, else re-pick | fs#which-cli-owns-the-session | moved (agent_freeze.py:503–533, agent_sessions.py:2407); added: an unknown `-m` model records no session |
| wf#the-daily-loop | a verified restore deletes the capture, so copy first | wf step 3 | kept |
| wf#the-daily-loop | k drops, after a confirmation | wf step 6 | kept |
| wf#before-shutting-down | Z scope and count | wf | kept |
| wf#before-shutting-down | listing contents | fa-ref#the-listing | moved |
| wf#before-shutting-down | V/R/P/S table | wf list + fa-ref#the-answers | moved (the table goes to the reference) |
| wf#before-shutting-down | all questions first | wf + fa-ref#the-answers | kept + moved, with the reason (ide_frozen_offer.sh:272) |
| wf#before-shutting-down | landing sessions, `--session`, session creation, failure isolation, naming, `j` | fa-ref#where-the-agents-land | moved |
| wf#before-shutting-down | which projects are acted on, plus skip reasons | fa-ref#which-projects-are-acted-on | moved, **corrected** (below) |
| wf#before-shutting-down | companion top-up | fa-ref#companions | moved; added "also when nothing is listed" (ide_frozen_offer.sh:153, 193) |
| wf#before-shutting-down | untracked viewer / survivor records; refusals; close the window | fa-ref#the-listing, #the-answers; wf#when-something-goes-wrong | moved (agent_restore.py:976, agent_freeze.py:1724, agent_reopen.py:718) |
| wf#before-shutting-down | no-terminal note | fa-ref#without-a-terminal | moved |
| wf#before-shutting-down | `--no-frozen-check` | fa-ref#the-ait-ide-frozen-agent-check | moved |
| wf#before-shutting-down | `gone` / `reopen` / `companions` script block | fs#the-freeze-engine | moved (checked against `aitask_frozen.sh` usage) |
| wf#before-shutting-down | `ait frozenagent` list mode, R/P on the row | wf | kept |
| wf#before-shutting-down | `restore --all [--repick]` | fs#the-freeze-engine, #restore-all | moved |
| wf#before-shutting-down | Restore-All rules (sequential, one failure never stops the batch, which records fail the first form, the `-2` suffix, session creation) | fs#restore-all | moved (agent_restore.py:1290–1316, 950–960, 850; agent_launch_utils.py:2337) |
| wf#what-unverified-means | outcome table | fa-ref#states-shown | already-stated |
| wf#what-unverified-means | causes | wf + fs#restore-verification | kept / already-stated |
| wf#what-unverified-means | Codex hook at the first turn; a late hook upgrades the restore | fs#restore-verification | already-stated |
| wf#what-unverified-means | the grace is a waiting period | fa-ref#configuration | already-stated ("It sets a waiting period, not an outcome.") |
| wf#when-something-goes-wrong | `restore failed:` / `last restore failed:` | wf + fa-ref#states-shown | kept / already-stated |
| wf#when-something-goes-wrong | `cannot restore:` reasons | wf | kept |
| wf#when-something-goes-wrong | `restore did not start` | wf + how-to#bring-an-agent-back | kept, **corrected** placement (below) |
| wf#when-something-goes-wrong | respawn a dead stand-in, settle transitional records, unmark a stuck agent | fs#the-freeze-engine | moved (agent_freeze.py:1280–1286, 1446ff) |
| wf#when-something-goes-wrong | reconcile cadence | fs#the-freeze-engine, #cleanup-rules | moved, **corrected** (below) |
| wf#when-something-goes-wrong | there is no `ait frozen` command | fs#the-freeze-engine | moved |
| wf#when-something-goes-wrong | a session name held by another project | wf + how-to#bring-an-agent-back | kept / already-stated |
| wf#marks-and-frozen-agents | mark plus cyan F; the column never shifts | wf table + tuis/monitor/how-to L70 | kept / already-stated |
| wf#marks-and-frozen-agents | the `P` filter over both; separate counters; counted once as frozen; Np/Nf | tuis/monitor/reference L39, L141–145 | already-stated |
| wf#marks-and-frozen-agents | Space still cycles a frozen agent's mark | tuis/monitor/reference L38 (Space row, no exception) | implicit only; open point for review |
| wf#limits | no expiry; missing capture → retired; `ait frozenagent` lists all | wf#limits + fs#cleanup-rules | kept / already-stated |
| wf#limits | `capture.ansi` / `capture.txt` | fs#where-the-state-lives | already-stated |
| wf#limits | depth semantics: cap plus one pane height | fa-ref#configuration | moved (agent_freeze.py:204, `capture-pane -S -<cap>` with no `-E`) |

**Code-verified corrections:**
1. **Skip reasons: four, plus a catch-all, not three.**
   `agent_reopen.py:301–307` defines `missing`, `unregistered`, `unverified`
   and `inaccessible`. `ide_frozen_offer.sh` adds "project directory
   unreadable" and "project could not be verified".
2. **Reconcile does not run after every freeze and restore.** It runs from
   the `reconcile` verb (agent_freeze.py:1983) and from the monitor
   maintenance pass (monitor_shared.py:1719), which starts at 60 s and then
   repeats every 600 s (monitor_shared.py:496, 511). The fs cleanup rules
   were corrected. The monitor_shared.py:1675 docstring carries the same
   false claim (code; not touched here).
3. **`restore did not start`** is the pre-begin case (agent_sessions.py:1779):
   nothing was dispatched and the record is unchanged. It is not a stuck
   record, so it gets its own bullet.

**Open points:**
- No page states outright that Space cycles a frozen agent's mark.
- Stale code comments: `aitask_session_hook.sh` says the freeze-time Codex
  capture is "Linux only", and the monitor_shared.py:1675 docstring makes
  the reconcile claim.

### Restructure report, Agent C: `implementation-trails.md` + `sitrep.md`

**Files:**
- `workflows/implementation-trails.md`: 162 → 110;
- `workflows/sitrep.md`: 133 → 67;
- `skills/aitask-trail.md`: 96 → 103 (#storage only);
- `tuis/board/reference.md`: 803 → 806 (By-Trail region only);
- `tuis/sitrep/reference.md`: 324 → 382 (a Timing bullet, new § "Where the
  list is stored" and § "Unparsed-output cases");
- `tuis/monitor/reference.md` (`h` row only).

Not changed: `tuis/trails/reference.md`, `concepts/artifacts.md` and
`skills/aitask-sitrep.md`. The gate was clean on every allowed file at both
checks. The inbound-anchor headings are byte-identical. The sitrep page's
`##` sections are merged into one `## Keeping the list` procedure; none of
the removed headings had an inbound link (grep).

| Source#section | Fact | Destination | Outcome |
|---|---|---|---|
| trails#intro | the "why" (analysis lost in scrollback) | concepts/implementation-trails#why-it-exists | already-stated ("Without a trail, that answer stays in a terminal session and is lost when the window closes.") |
| trails#intro | "until now" | — | dropped (current-state rule) |
| trails#what-a-trail-records | "Distinguishing … is most of the value" | same | rewritten without the inflation |
| trails#creating-a-trail | `T` in By-Topic resolves to the lane's topic root | page step 1 + board/reference#by-trail | moved (aitask_board.py:4955-4985) |
| trails#creating-a-trail | run summary contents | skills/aitask-trail#the-run-summary | already-stated |
| trails#lite-and-deep | an unlabelled trail means "depth not recorded" | board/reference#by-trail | already-stated |
| trails#lite-and-deep | omitting the flag means lite, incl. the board's re-author | step 2 | kept, **corrected** wording (the board passes no `--deep`; board_trail_screen.py:984, :1803) |
| trails#reading | a completed member is struck through | board/reference#by-trail | moved ("marked `✔` and struck through", board_trail_view.py:86-87, 316) |
| trails#reading | `ait trails` tabs; `m`/`M`/`S` board-only; separate selections | board/reference#by-trail | already-stated |
| trails#reading | detail screen; `a` reveal | board/reference#by-trail | already-stated |
| trails#keeping-current | refresh-cost table | board/reference#by-trail + tuis/trails/reference#what-each-refresh-reads | already-stated |
| trails#keeping-current | drift: a new related task appears | board/reference#by-trail | moved (`new_related_task`, trail_gather.py:111-118, 217-221) |
| trails#keeping-current | targeted refresh; earlier versions retrievable | skills/aitask-trail#modes, #storage | already-stated |
| trails#keeping-current | moving cards never stales a trail | board/reference#moving-a-wave-into-a-column | already-stated |
| trails#feeding-a-work-report | `M` review, wave order, named skips, ghosts | board/reference#moving-a-wave-into-a-column | already-stated |
| trails#where-a-trail-is-stored | owner rules | skills/aitask-trail#storage | moved (SKILL.md.j2:68-77, 385-392); added: the owner must be a live local task |
| trails#where-a-trail-is-stored | discovery active+archived; archived-owner note; staleness ≠ owner | skills/aitask-trail#storage | moved (trail_discovery.py:333-385; board_trail_screen.py:877-880) |
| trails#where-a-trail-is-stored | fold copies `artifacts:`; listed once | skills/aitask-trail#storage | moved, **corrected** order (trail_discovery.py:126-136) |
| trails#where-a-trail-is-stored | one document, several views | skills/aitask-trail#storage | moved |
| trails#never-does | no metadata rewrite; no fabrication; one confirmed write | skills/aitask-trail#invariants | already-stated |
| trails#never-does | gates/deps/archival never read a trail | page (kept) | verified: no trail reads in aitask_gate.sh, lib/gate_*.py, aitask_archive.sh |
| trails#tips | reach for a trail when ordering is hard; start lite; refresh first | concept #how-to-use; page steps | already-stated |
| sitrep#where-the-list-lives | `.aitask-sitrep/`, `raw/`, `cases/`, locked writer, rolling backup | tuis/sitrep/reference#where-the-list-is-stored | moved, extended (aitask_sitrep_todo.sh:16-23, 61-63; sitrep_todo.py:14-36; aitask_setup.sh:3347) |
| sitrep#output-the-harvest-could-not-read | five `ait sitrep case` commands | tuis/sitrep/reference#unparsed-output-cases | moved (page keeps `list`, `replay`); added `review`, flags, statuses (sitrep_corpus.py:47-90) |
| same | exported fixtures must be redacted | tuis/sitrep/reference#unparsed-output-cases | moved (sitrep_corpus.py:862) |
| same | failure causes | page | **corrected** (below) |
| sitrep#shortcodes | 7-row table | skills/aitask-sitrep#capabilities | already-stated |
| sitrep#shortcodes | show/collect/dismiss/restore are TUI keys | skills/aitask-sitrep#done-in-the-sitrep-tui-not-here | already-stated |
| sitrep#closing | `h` dialog outcomes | tuis/monitor/reference `h` row | moved with exact strings (sitrep_close.py:197-215, 414-423) |
| sitrep#closing | frozen sweep "every few minutes" | tuis/sitrep/reference#timing + page | **corrected** (below) |
| sitrep (other sections) | all facts | the 7-step procedure | kept |

**Code-verified corrections:**
1. **The work report step said `w` works from By-Trail.** `w` is hidden in
   By-Trail (aitask_board.py:2609-2614). The step now switches to a kanban
   view first.
2. **The `h` dialog has a fourth outcome.** "Nothing to harvest (<reason>)"
   is a success that still offers a close (sitrep_close.py:197-215).
3. **The monitor `h` row** said a live `agent-sitrep` window "is closed
   without being harvested". The report is `skipped`, and the dialog offers
   Close agent / Keep (sitrep_close.py:520-523, 186-187, 418-422).
4. **The frozen-capture sweep** runs in the monitor and the minimonitor, every
   600 s after a 60 s grace, then re-checks
   (monitor_shared.py:496, 511, 687-688, 726).
5. **The board's `T`/`R`** launch the skill without `--deep`.
6. **Fold dedupe order:** active unfolded, then active folded, then archived.
7. **Staleness** also comes from a new related task (`new_related_task`).
8. **Unparsed-output causes:**
   - "rendered without its fence" is replaced by "not in a form the harvest
     recognizes", since joined unfenced banners are accepted
     (`ACCEPT_JOINED_BANNER`);
   - `created_unparsed` is added.

**Open points:**
- The monitor `h` row is long for a table cell (t2258_5).
- Not verified, and not moved: that `ait artifact create` refuses while the
  owner file is dirty (an existing skill sentence), and the board's "`d`
  about half a second".

## Step 3 result: guide lesson

One addition to the "Page types" growth-signs paragraph of
`doc_update_guide.md`, covering two more signs:
- an opening that argues again for a feature whose concept page already says
  why it exists (seen on implementation-trails);
- a table of keys, shortcodes or refresh costs that a TUI or skill reference
  already lists (seen on sitrep and implementation-trails).

`test_docs_review_contract.sh` passes 71/71. Committed by path on the
task-data branch.

## Step 5 result: depth (run 1)

`grep -L '^depth:'` over the six group pages is empty. Depths:
freeze-and-restore-agents, sitrep, parallel-planning and parallel-development
are `intermediate`; implementation-trails is `advanced`. The edited
destinations (frozenagent/reference, development/framework-session,
skills/aitask-trail, board/reference, sitrep/reference, monitor/reference)
are all `advanced`.

## Step 6 result: links (run 1, before the fix pass)

- `check_links.py --build`: `SWEEP: PASSED`, exit 0.
- `check_link_relevance.py`: 7 reported, 0 unresolved, 0 anchors not found.
  - The parallel-development:46 flag is gone (the link text now names the
    preflight).
  - `crash-recovery:30` remains, on the deferred page (ledger).
  - The other six are pre-existing, in other sections (concepts/gates:66,
    development/_index:117, development/gates:124 and :177,
    tuis/monitor/how-to:242, workflows/risk-evaluation:38). None is a link
    this child added or retargeted.
- `test_website_doc_lists.sh` passes 63/63, and
  `test_docs_vocabulary_coverage.sh` passes 32/32.

## Step 4 result: review round 1 (`/aitask-docs-review … --caller audit --budget 0`, independent agent)

`BUDGET_USED:0`. Every page reports `reader=not-run(not-beginner)`.

| Page | level | prose | unresolved |
|---|---|---|---|
| workflows/freeze-and-restore-agents | 3 | 3 | 0 |
| workflows/implementation-trails | 3 (one advisory retag) | 6 | 1 (tautology intent) |
| workflows/sitrep | 2 | 5 | 1 (banner link target) |
| workflows/parallel-planning | ok | 3 | 0 |
| workflows/parallel-development | ok | 6 | 1 (test-suite wording) |
| tuis/frozenagent/reference (changed) | ok | 2 | 0 |
| development/framework-session (changed) | ok | 2 | 0 |
| skills/aitask-trail (changed) | ok | 2 | 0 |
| tuis/board/reference (changed) | ok | ok | 0 |
| tuis/sitrep/reference (changed) | ok | 1 | 0 |
| tuis/monitor/reference (changed) | ok | ok | 0 |

**Facts that may be wrong (reviewer):**
1. On freeze, after a failed restore a *new* viewer takes the pane, and its
   header reads `last restore failed:` (frozenagent_app.py:598-611). The
   same wording appears in tuis/frozenagent/how-to and _index.
2. On sitrep, "never picks a task" is true of the agent only: the TUI's `p`
   launches `/aitask-pick`.
3. On parallel-development, the preflight is off in all shipped profiles,
   and `parallel_assessment` is a separate pre-claim assessment.
4. On framework-session, `reconcile` always exits 0, and some commands print
   summary lines.

**Declined:** the advisory retag of implementation-trails to
`intermediate`. The approved plan keeps it `advanced`, matching its concept
page.

## Post-phase result: moved_fact_survival_check, run 1 (independent agents, one per source)

| Source | claims | preserved | weakened | missing | corrected (agree/disagree) | rhetoric |
|---|---|---|---|---|---|---|
| freeze-and-restore-agents | 135 | 131 | 1 | 0 | 3 (3/0) | 7 |
| implementation-trails | 110 | 106 | 0 | 1 | 3 (3/0) | 9 |
| sitrep | 110 | 107 | 0 | 0 | 3 (3/0) | 2 |
| parallel-planning | 37 | 31 | 0 | 0 | 6 (5/1) | 2 |
| parallel-development | 45 | 44 | 0 | 0 | 1 (1/0) | 1 |

**Gaps:**
- freeze: the survivor record is "never mistaken for a viewer" (weakened).
- trails:
  - the dependency-graph/board framing (missing);
  - two old inaccuracies carried through: every entry has evidence links,
    which is deep only; and scope widening, which is deep only.
- parallel-planning: "Whatever the profile" over-claims (disputed).
  **Fixed in-session:** now "With the shipped profiles", with the
  `ASK_STALE` and default-profile nuances. The moved-fact row's "only" was
  corrected.
- sitrep: minor wording ("full monitor's title bar").

The fixes for every other gap and every review finding go to one fix agent
(scratchpad `fix_brief.md`).

## Fix pass (review round 1 + survival run 1): report summary

One fix agent, scratchpad `fix_brief.md`, verified each fact in the code
first. Every finding was applied. ST-P1 was done on the workflow page, but
the sitrep reference still says "collect-and-re-check" in places (open
point for t2258_5).

**Files:**
- freeze 162 → 174, trails 110 → 84, sitrep 67 → 61, parallel-planning 54,
  parallel-development 64;
- frozenagent/reference 239 → 240, development/framework-session 151 → 153,
  skills/aitask-trail 103, board/reference 806 → 828 (the glyph table moved
  into By-Trail as "**Classification glyphs.**"), sitrep/reference
  382 → 400, monitor/reference (`h` row);
- fact-only: frozenagent/how-to and frozenagent/_index;
- new `aidocs/framework/testing_conventions.md` § "The suite inside a task
  worktree".

| Source#section | Fact | Destination | Outcome |
|---|---|---|---|
| freeze#when-to-freeze (table) | parked shows `P` | monitor/reference#pane-interaction | already-stated ("unmarked → prioritized (`★`) → parked (`P`) → unmarked") |
| freeze#when-to-freeze (table) | `N parked` / `N frozen` counters | monitor/reference#multi-session-view | already-stated |
| freeze#when-to-freeze (table) | frozen shows its mark plus a cyan `F` | minimonitor/how-to:56 | already-stated ("a frozen card shows the mark plus a cyan **F**"); not on the monitor reference (open point, t2258_5) |
| freeze#when-to-freeze | "Parking hides an agent… readable" | same page, table rows | already-stated |
| freeze step 2 | keys r, m, /, n, shift+↑/↓, mouse | frozenagent/reference#keybindings | already-stated (rows quoted by the agent) |
| freeze#what-unverified-means | `restored` / `restored, unverified — capture kept` strings | frozenagent/reference#states-shown | already-stated |
| freeze#when-something-goes-wrong | "viewer comes back… `restore failed:`" | — | **corrected**: a new viewer takes the pane and shows `last restore failed: …` (frozenagent_app.py:598-611; agent_sessions.py:1796-1801); also fixed in frozenagent how-to, _index and reference |
| freeze#when-something-goes-wrong | `cannot restore:`, `restore did not start`, `restore still <state> after the grace` | frozenagent/reference#states-shown | already-stated |
| fs#cleanup-rules | reconcile schedule; "the coordinator reconciles after every operation" | fs#the-freeze-engine | **corrected**: the coordinator never runs reconcile; only the monitor tick (monitor_shared.py:1719) and a hand run (agent_freeze.py:1983) do |
| fs#the-freeze-engine | exit status 0/1 for every command | same | **corrected**: `reconcile` always exits 0 (agent_freeze.py:1983-1986); summary lines `RESTORE_ALL:` (agent_restore.py:1347), `GONE_COUNT:` (agent_reopen.py:404, 867), `COMPANION_COUNT:` (:443), `FREEZE_ELIGIBLE:` (agent_freeze.py:1943-1947) |
| trails#what-a-trail-records | glyph/classification table + drift comment | board/reference#by-trail ("Classification glyphs.") | moved (board_trail_view.py:88-94; schema :383-390) |
| trails#what-a-trail-records | "both look like 'do that one first'" | — | dropped (staged framing, not accurate); the distinction is kept in prose |
| trails#what-a-trail-records | "recommendations recorded as recommendations" | same page | **corrected**: relations are marked fact or advisory (SKILL.md.j2:896-898) |
| trails#intro s2 | section preview | same page, steps | already-stated |
| trails#tips | let the summary answer | trails reading step 3 | already-stated; "written when the reasoning was fresh" dropped (rhetoric) |
| trails#tips | trails are durable, reports are drafts | trails#feeding-a-work-report | moved |
| trails (last para) | a task may appear in several trails | trails#where-a-trail-is-stored | already-stated |
| trails | every entry has evidence links | same page | **corrected**: only in a deep trail (SKILL.md.j2:419) |
| trails step 3 + skill step 4 | the agent proposes widening the scope | same pages | **corrected**: deep only; lite names the work in its overview (SKILL.md.j2:422-426, 448-452) |
| skill#storage | "about the owner, not about freshness" | — | dropped (staged contrast); the fact is kept |
| sitrep#output-the-harvest-could-not-read | full cause list | sitrep/reference#unparsed-output-cases | moved, with reason codes (sitrep_harvest.py:173-175, 510-546) |
| same | "local record that parser fixes can be checked against" | sitrep/reference#unparsed-output-cases | moved |
| sitrep step 7 | four outcome bullets | same step (two sentences) + monitor `h` row | moved |
| sitrep | shortcode paragraph | sitrep step 2 | moved |
| sitrep | "never picks a task" | same page | **corrected**: the agent never picks; the TUI's `p` opens a launch dialog for `/aitask-pick` (sitrep_tui_actions.py:92, 1031-1061) |
| sitrep step 7 | "shadow or notes panes" | same + monitor `h` row | **corrected**: bound helper panes are shadow and scratchpad (monitor_core.py:1142-1176, 4338-4365) |
| pd#git-worktrees | "and the test suite behave the same" | aidocs/framework/testing_conventions.md § "The suite inside a task worktree" | moved (aitask_init_data.sh:79-85) |
| pd#choosing-what-to-run-alongside | the preflight runs before implementation; `parallel_assessment` extends it | same page | **corrected**: all shipped profiles set `parallel_admission: "off"` (an omitted key means `warn`); `parallel_assessment` is a separate pre-claim assessment (profiles.md:50-51) |
| pd | "Task numbers are allocated centrally" | same page | made concrete (aitask_claim_id.sh:3, 29) |

**Coordinator touch-ups after the fix pass:**
- removed the bold lead-ins on parallel-planning;
- sitrep "red banner" → "red warning naming the file" (one meaning per term
  on the page);
- fs:72 "is restored by re-picking" → "can only be brought back by
  re-picking".

**Links after the fix pass:**
- `check_links.py --build`: PASSED.
- Relevance: 8 reported. One is new: freeze:114 `frozen.restore_ack_grace` →
  frozenagent/reference#configuration. I opened it: the section documents
  `restore_ack_grace` under the `frozen:` block, so it is relevant (false
  positive).
- The rest are unchanged (pre-existing, other sections, plus the deferred
  crash-recovery:30).

## Survival check run 2 (on the fixes and the fix-pass cuts, independent agent)

| Scope | Items | Preserved | Corrected (agree/disagree) | Weakened | Missing |
|---|---|---|---|---|---|
| Fix-pass table rows | 29 | 19 (+2 dropped-ok rhetoric) | 8 (8/0) + 1 mislabelled (fixed above) | 0 | 0 |
| Run-1 gaps | 4 | 4 confirmed fixed | — | 0 | 0 |
| Blocks removed from destination pages | 61 claims | 52 | 9 (9/0) | 0 | 0 |
| New source blocks since run 1 | 9 claims | 9 | — | 0 | 0 |

Nits applied after review round 2: trails Enter "evidence" is now qualified
as deep only, and parallel-planning:52 is qualified with "With the shipped
profiles". The stale code docstrings (agent_freeze.py:13 and
monitor_shared.py:1675-1676) go to Upstream defects.

## Step 4 result: review round 2 (independent agent, after the fix pass)

| Page | level | prose | after the coordinator's fixes |
|---|---|---|---|
| workflows/freeze-and-restore-agents | ok | 3 | all 3 applied (repeated failed-restore sentence cut; Limits now says the capture leaves out old output; the Space table cell is "press `Space` once") |
| workflows/implementation-trails | ok | 2 | both applied. The opening no longer re-argues the feature; the dependencies/board framing **moved** to `concepts/implementation-trails#why-it-exists` (gate clean); "draft the report again" |
| workflows/sitrep | ok | ok | — |
| workflows/parallel-planning | ok | ok | survival-run-2 nit applied ("With the shipped profiles" at :52) |
| workflows/parallel-development | ok | 2 | both applied ("The merge mutex serializes that step"; "the agent can be restored, or its task picked again") |
| tuis/frozenagent/_index (changed) | 1, pre-existing (an outcome table at main-concept; t2258_5) | 1 | contradiction fixed ("keeps the capture and puts a new viewer back in the pane") |
| tuis/frozenagent/how-to (changed) | ok | 1 | stale "viewer comes back" fixed |
| tuis/frozenagent/reference (changed) | ok | 1 | `capture_max_lines` row reworded |
| development/framework-session (changed) | ok | ok | — |
| skills/aitask-trail (changed) | ok | 1 | fold order made unambiguous |
| tuis/board, sitrep, monitor references (changed) | ok | ok | — |
| aidocs/framework/testing_conventions | facts ok | — | — |

Every unresolved item from round 2 used the reviewer's own suggested text,
so no third review round was run. The trails Enter "evidence" sentence is now
qualified as deep only (survival run 2 nit). The link check after these
edits passed.

**Not chased (owner t2258_5):**
- `tuis/frozenagent/_index.md`'s outcome-string table at `main-concept` is
  pre-existing.
- `tuis/sitrep/reference.md` still says "collect-and-re-check" in places.
- The frozen `F` glyph is not on `tuis/monitor/reference.md`.
- `tuis/frozenagent/how-to.md:105` uses `restore failed: respawn:…`
  (unproven which viewer shows it).

## Step 7: ledger close-out

- `workflows/crash-recovery.md` was **still dirty** at close-out (2026-11-12,
  after review round 2). The one-line t2284 diff at L71 was unchanged, and
  t2284 was still `Implementing`. It was never edited by this task: every
  gate check, from planning through close-out, saw it dirty. Agent B never
  ran, so `commands/lock.md` and `aidocs/gates/ledger-driven-reentry.md`
  were not touched either.
- **Outcome: follow-up t2258_14** (`audit_deferred_pages_workflows_parallel_local`,
  child of t2258, `--no-sibling-dep`, `depends: [2284]`). It carries the
  inventory row, the full Agent B restructure design, the inbound-anchor
  list and the binding method.
- The late-audit loop did not apply, because no ledger page was audited at
  close-out.

## Post-Review Changes

### Change Request 1 (2026-11-12 20:30)
- **Requested by user:** the new `aidocs/framework/testing_conventions.md`
  § "The suite inside a task worktree" stated the worktree data links
  unconditionally. The source paragraph (`workflows/parallel-development.md`)
  limited them to projects that keep task data on a separate branch, and in
  legacy mode `aitask_init_data.sh` returns `LEGACY_MODE` without creating
  links.
- **Verified:** `aitask_init_data.sh:141-146` prints `LEGACY_MODE` and exits
  0 when `aitasks/` is a real directory in the main checkout ("task data is
  tracked on the code branch, so the worktree checkout already has it").
- **Changes made:** the section now opens with "On a project that keeps task
  data on a separate branch". It adds the legacy-mode case: the task data is
  already in the checkout, the helper links nothing, and a legacy worktree
  without the links is not broken. The survival row for PD-P5 stays `moved`;
  it is now `moved` with the scope restored.
- **Files affected:** `aidocs/framework/testing_conventions.md`.

## Final Implementation Notes
- **Actual work done:**
  - **Inventory and verdicts:** all six pages of the Parallel group (local
    part), measured at 86d4f4aba.
  - **Three restructures, each into one how-to procedure:**
    - `freeze-and-restore-agents` (316 → about 168 lines). The `ait ide`
      check went to a new `tuis/frozenagent/reference` § "The `ait ide`
      frozen-agent check"; the `aitask_frozen.sh` contract to a new
      `development/framework-session` § "The freeze engine" /
      § "Restore-All"; the CLI eligibility facts to fs#which-cli-owns-the-session.
    - `implementation-trails` (162 → 84, stays `advanced`). The storage
      rules went to `skills/aitask-trail#storage`, the glyph table and its
      drift comment to `tuis/board/reference#by-trail`, and the dependency/board
      framing to `concepts/implementation-trails#why-it-exists`.
    - `sitrep` (133 → 61). The store layout and the case commands went to
      `tuis/sitrep/reference`, and the `h` dialog strings to the
      `tuis/monitor/reference` `h` row.
  - **Two minor pages retagged `advanced` → `intermediate`:**
    `parallel-planning` and `parallel-development`.
  - **Fact-only fixes** on `tuis/frozenagent/how-to` and `_index`, which
    contradicted the corrected failed-restore behaviour.
  - **One contributor fact** went to `aidocs/framework/testing_conventions.md`
    § "The suite inside a task worktree", scoped to separate-data-branch
    projects after the user's review.
  - **One guide lesson**, committed on the task-data branch.
  - **Checks:** two review rounds and two claim-level survival runs, ending
    at 0 weakened / 0 missing. Links pass, as do doc lists 63/63, vocabulary
    32/32 and the docs-review contract 71/71. Every leaf page has `depth`.
- **Deviations from plan:**
  - `crash-recovery.md` (Agent B) was never restructured. It was dirty from
    t2284 at planning and still at close-out, so it went to follow-up
    t2258_14, as the ledger rule requires. `commands/lock.md` and
    `aidocs/gates/ledger-driven-reentry.md` were therefore not touched.
  - The trails glyph table moved to `tuis/board/reference` (review round 1),
    not kept on the workflow page as planned.
  - `concepts/implementation-trails.md` got one sentence that review round 2
    asked to move there from the workflow page's opening (gated clean). It
    was not in the plan's file list.
  - The frozenagent `how-to` and `_index` were fact-fixed, which was not
    planned (gated clean; full audit stays with t2258_5).
  - No third review round: round-2 findings were applied using the
    reviewer's own text, then link-checked.
- **Issues encountered:**
  - `crash-recovery.md` became dirty during planning (t2284's L71 edit),
    which led to the plan revision adding the ledger entry and the
    late-audit loop.
  - The fix-pass agent mislabelled one moved-fact row (reconcile schedule:
    "already-stated" when it was a correction). Survival run 2 caught it,
    and the row was fixed.
- **Key decisions:**
  - `implementation-trails` keeps `advanced`, matching its concept page. The
    reviewer's advisory retag was declined.
  - `aitask_frozen.sh` is public architecture, because the site tells users
    to run `reconcile`. Its contract is on `development/framework-session`.
  - Outcome strings at `intermediate` are described in words; the exact
    strings stay on the `advanced` reference pages.
- **Code-verified corrections (about 30, with file:line in the restructure
  and fix-pass reports above).** The main ones:
  - reconcile never runs after freeze or restore, only on the monitor tick
    and by hand;
  - a failed restore brings a new viewer, whose header shows
    `last restore failed:`;
  - there are four skip reasons plus a catch-all, not three;
  - `reconcile` always exits 0;
  - `w` is hidden in By-Trail;
  - lite trails have no per-entry evidence and no scope-widening proposal;
  - the parallel-admission preflight is off in every shipped profile, and
    `parallel_assessment` is separate;
  - plan verification depends on the profile;
  - `/aitask-pick` syncs task data itself;
  - the `h` dialog has a fourth outcome;
  - the sitrep TUI's `p` launches a pick.
- **Ledger outcomes:** `workflows/crash-recovery.md` → follow-up t2258_14
  (still dirty from t2284 at close-out, never edited here).
- **Upstream defects identified:**
  - `.aitask-scripts/lib/agent_freeze.py:13` — the module docstring says
    reconcile is "run after every freeze", but no freeze or restore path
    calls it (only the CLI verb and `monitor_shared.py:1719` do).
  - `.aitask-scripts/monitor/monitor_shared.py:1675-1678` — the docstring
    says "the coordinator runs it after every freeze/restore"; the same
    false claim.
  - `.aitask-scripts/aitask_session_hook.sh:67` — the comment says the
    freeze-time Codex session capture is "Linux only", but
    `lib/agent_sessions.py` (t2048) and the docs cover Linux and macOS.
  - `.aitask-scripts/lib/implementation_trail.schema.json:95` — the
    `digest` description lists "boardcol/boardidx presence", but the digest
    in `lib/trail_gather.py:487-495` does not include them (the docs are
    right; the schema text is stale).
- **Notes for sibling tasks:**
  - **The method worked again:**
    - parallel restructure agents on disjoint file sets with one brief;
    - an independent review round and per-source survival agents in
      parallel;
    - one fix agent;
    - round 2 of both.

    `scratchpad/removed_blocks.py` (block splitter, whitespace-collapsed
    exact match) is described in the post-phase. Re-create it from that
    description.
  - **A page can turn dirty mid-planning.** Re-gate right before each
    agent, and plan the late-audit loop up front.
  - **Expect wrong facts in "when it runs" claims** (reconcile, sweeps,
    preflights) and in claims about profile defaults. Check the shipped
    profiles, not only the profile docs.
  - **Leftovers by owner:**
    - **t2258_5:**
      - frozenagent `_index` outcome table at `main-concept`;
      - `tuis/sitrep/reference` still says "collect-and-re-check";
      - the frozen `F` glyph is not on the monitor reference;
      - the monitor `h` row is long for a table cell;
      - frozenagent how-to:105 `restore failed: respawn:…`.
    - **t2258_6:** `skills/aitask-pick/execution-profiles.md` does not
      document `remote_drift_check` (`task-workflow/profiles.md:49` does).
    - **t2258_14:** crash-recovery, carrying Agent B's full design.
