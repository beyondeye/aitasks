---
Task: t1210_7_manual_verification_implementation_trails.md
Parent Task: aitasks/t1210_brainstorm_durable_implementation_trail_skill_and_board_repo.md
Sibling Tasks: (all archived)
Archived Sibling Plans: aiplans/archived/p1210/p1210_1_trail_schema_library_and_validator.md, aiplans/archived/p1210/p1210_2_trail_gatherer_and_drift_helper.md, aiplans/archived/p1210/p1210_3_aitask_trail_skill.md, aiplans/archived/p1210/p1210_4_board_bytrail_view.md, aiplans/archived/p1210/p1210_5_trail_move_to_column_commands.md, aiplans/archived/p1210/p1210_6_implementation_trail_docs.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1210_7 — Manual verification auto-execution record

Autonomous auto-verification run (strategy: `autonomous`) of the Implementation
Trails checklist. This file is the retroactive record of what was actually run.

**Outcome: 8 pass, 2 defer, 0 fail, 0 pending.**

Everything was exercised against the **real repository state** — the four trails
already stored in `.aitask-data/artifacts/` — never a fixture replica. Every
mutation made to reach a verdict was reverted and the revert verified.

## Execution Log

### Item 1 — interactive create via /aitask-trail

- Item text: Create a trail interactively via `/aitask-trail` on a real task: scope question offered, proposal rendered with full narrative, single confirmed write; `ait artifact ls <owner>` shows the `art:trail-*` handle
- Approach: **not automatable** — no execution attempted
- Verdict: **defer**
- Reason: the assertions *are* the human-in-the-loop UX (scope question, single
  **confirmed** write). Observing them autonomously would also mean creating a
  real trail artifact on a real task. Separately, **t1644** (`status:
  Implementing`, anchor 1210) is rewriting exactly this run-summary surface, so
  a verdict today would pin a surface about to change.
- Indirect evidence: four trails exist, all created through this flow, and their
  stored JSON carries the full `narrative` / `observations` / `exclusions`
  structure.

### Item 2 — refresh flow

- Item text: Archive one member task, run `/aitask-trail --refresh <handle>`; drift reasons named, diff-style summary shown, new version in `ait artifact versions`
- Approach: **not automatable** — no execution attempted
- Verdict: **defer**
- Reason: requires archiving a real member task plus a confirmed interactive
  write; the assertions are again interactive rendering. Same t1644 caveat.
- Indirect evidence: `art:trail-shadow-review-loop` already carries **6 recorded
  versions** (one create + five refreshes), and its `freshness` block holds named
  `drift_reasons` and a `refresh_recommended_because`.

### Item 3 — drift check is read-only; boardidx move is not drift

- Approach: CLI invocation + byte-level equality + **negative control**
- Action run:
  - `ait artifact get art:trail-shadow-review-loop --out <tmp>` (fetched blob
    sha256 equals the manifest's `current`, proving it is the stored bytes)
  - `aitask_trail_gather.sh drift --trail <tmp>` **twice**
  - store hash: `find .aitask-data/attachments/blobs .aitask-data/artifacts/manifests -type f | sort | xargs sha256sum | sha256sum` before and after
  - boardidx-only edit on member `t1503` (`1094` → `999999`), re-ran drift
  - negative control: `status: Ready` → `Postponed` on the same task, re-ran drift
- Output (trimmed):
  - both drift runs: `CURRENT` / `DIGEST:fe9b43e63208bff5` — byte-identical output
  - store digest `1c3c25b66067e51c…` unchanged across both runs
  - after boardidx-only change: still `CURRENT`, **same digest**
  - after status change: `STALE` / `DRIFT:status_changed|aitasks#1503|status 'Ready' -> 'Postponed'`
- Verdict: **pass**. The negative control fires, so the check discriminates
  rather than passing vacuously. `t1503` restored byte-identical, `git status`
  clean.

### Item 4 — By-Trail view

- Approach: TUI interaction (live board in a detached tmux session, 220×55)
- Action run: `z` → By-Trail; `s` → trail picker; opened **two** trails; `d` → freshness recheck; `tmux capture-pane -e` for SGR-level assertions
- Output (trimmed):
  - picker listed all four trails with owner, kind, freshness and cross-trail
    overlap (`└ also references: …`)
  - *Shadow review-loop automation* → 11 wave columns; *Gate framework landing
    order* → 5 — each with its own `W<n> · <title>` and entry count
  - badges carried all five classifications with confidence, e.g.
    `◆ hard_prerequisite · conf: high`, `▲ preferred_predecessor · conf: medium`,
    `● core · conf: high`, `⇄ coordination_only · conf: high`, `○ optional · conf: medium`
  - **completion strike-through pinned at the SGR level**: landed entries
    (`aitasks#1294`, `#1289`, `#1427`, `#1159_1`) render inside an `ESC[9m` run;
    live entries (`t1159`, `t1564`, `t1506`) do not
  - stale banner: after flipping member `t1503` to `Postponed` and pressing `d`,
    the header read `(⚠ stale: 1)` — one reason, matching the one change
- Verdict: **pass**. `t1503` restored; header returned to clean.

### Item 5 — error states, fail-closed + versions fallback

- Approach: reversible rename of store files, board restarted for fresh discovery
- Action run: renamed the current blob aside, restarted board, opened the trail;
  restored; then renamed the **manifest** aside and repeated; restored
- Output (trimmed):
  - blob missing → picker row degraded to `owner t1118 · ? · ✗ unreadable · ?`
    (kind and timestamp degrade rather than being fabricated) while the other
    three stayed `✓ current (recorded)`
  - opening it → header `— trail unavailable`, body:
    `Trail art:trail-mobile-shadow-driving could not be loaded (fail-closed):`
    `artifact unresolved: … blob not found for sha256:33bc6271… (local backend; not in cache or store)`
    then **`Recorded versions (ait artifact versions art:trail-mobile-shadow-driving):`**
    with `*` on current, and `Press s to select another trail.`
  - manifest missing → same fail-closed card, `no manifest for art:…`, and
    **no** versions list — correct, since the manifest *is* the version list
- Verdict: **pass**. Both restored; blob sha256 matches original, zero stray
  `.aitask-verify-bak` files, all four handles resolve.

### Item 6 — launch seams

- Approach: TUI interaction; screens opened and **cancelled**, never launched
- Output (trimmed) — all three opened `AgentCommandScreen` titled *Implementation Trail*:
  - task card (focused `t1405`) → `claude --model claude-opus-5 /aitask-trail\ 1405`
  - By-Topic **lane header** (lane `t635`, focused card was `t1393`) →
    `/aitask-trail\ 635` — the topic **root**, not the focused card, as documented
  - By-Trail view (gates trail open) → `/aitask-trail\ --refresh\ art:trail-gates-framework-landing`
- Verdict: **pass**. Arguments are shell-escaped at the command line.

### Item 7 — move commands

- Approach: TUI interaction against the gates trail; full before/after snapshot
- Output (trimmed):
  - **`m`** on focused `t1417` → column picker that correctly **omits the card's
    current column** (`bug fixes`); moved **only** `t1417` to `tests`, the other
    four untouched
  - **`M`** on **W1** (17 entries: 5 live parents + 12 ghosts) → review list
    holding exactly the 5, pre-checked, each labelled `[Unsorted / Inbox]`, in
    wave order; after confirming into `bug fixes`:
    `t1417→1024, t1438→2048, t1437→3072, t1473→4096, t1534→5120` —
    strictly increasing in **wave order** `1417, 1438, 1437, 1473, 1534`
  - ghost exclusion, visible reason: toast
    `Skipping 12 ghost: aitasks#635_27, aitasks#1264, …`
  - child exclusion on an all-child wave (W4): toast
    `Nothing movable in this wave — 3 child: aitasks#635_31, …`
  - `M` is additionally binding-gated off while a ghost is focused (footer drops
    `M Move Wave`)
- Verdict: **pass**. All five files restored from snapshot; a full tree re-diff
  showed the only remaining difference was `t1644`, which belongs to a
  concurrent session and was deliberately left alone.

### Item 8 — passive report bridge

- Approach: CLI invocation of the seam the board's `w` flow consumes
- Action run: `aitask_work_report_gather.sh --columns bug_fixes` immediately after the `M`
- Output (trimmed):
  ```
  COLUMN:bug_fixes|bug fixes
  TASK:bug_fixes|1417|1024|Ready|low|low|0|1|risk_mitigation|…
  TASK:bug_fixes|1438|2048|…
  TASK:bug_fixes|1437|3072|…
  TASK:bug_fixes|1473|4096|…
  TASK:bug_fixes|1534|5120|…
  ```
- Verdict: **pass**. Exactly the five moved tasks, in board order, no extras and
  none missing; the report reads the column only and never consults the trail
  artifact. After restore the same command returns `NO_TASKS`.

### Item 9 — docs render, five classification glyphs

- Approach: **real browser render** (Chromium 151 headless against `hugo server`)
- Action run: `hugo server --port 1399`; `chromium --headless --screenshot` of
  `/docs/workflows/implementation-trails/`; `magick` crop + 3× magnification of
  the Glyph column; overflow measured through the DevTools protocol
- Output (trimmed): all five render as **distinct, correct** characters — filled
  diamond, filled triangle, filled circle, two-arrow, hollow circle — **no tofu
  boxes**. Table unclipped with no horizontal overflow at 1024 / 1280 / 1440
  (table 557 / 627 / 712 px inside a 697 / 783 / 890 px column).
- Verdict: **pass**

### Item 10 — docs navigation

- Approach: CDP-driven navigation (Node 25 built-in `WebSocket`, no deps) with a
  negative control
- Output (trimmed):
  - `/docs/tuis/board/reference/#moving-a-wave-into-a-column` →
    `scrollY=11211`, target `H5` **88 px** from the viewport top, `inViewport: true`
  - negative control (same page, **no** fragment) → `scrollY=0`, target
    `11299 px` below the fold, `inViewport: false` — so the scroll is
    fragment-driven, not a default
  - workflow-page links resolve to real pages: `work-report` →
    *Reporting Work to Managers*; `topic-anchoring` → *Topic anchoring*
    (HTTP 200, correct `h1`)
- Verdict: **pass**

## Cleanup

Performed:

- `t1503`, and the five W1 members (`t1417`, `t1438`, `t1437`, `t1473`,
  `t1534`), restored from snapshot and confirmed byte-identical
- artifact blob and manifest for `art:trail-mobile-shadow-driving` restored;
  zero `*.aitask-verify-bak` files remain
- tmux session `av1210` killed; `hugo server` and the headless Chromium
  (CDP port 9333) terminated
- scratch files confined to the session scratchpad — nothing written under
  `aitasks/` or `aiplans/` except this record and the checklist itself

## Follow-up

Items 1 and 2 are deferred, not failed. Re-run them interactively once **t1644**
(`trail interactive run summary and website docs`) lands, since that task is
rewriting the run-summary surface item 1 asserts on.
