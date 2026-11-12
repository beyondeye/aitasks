---
priority: medium
effort: medium
depends: [2284]
issue_type: documentation
status: Ready
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
anchor: 2258
created_at: 2026-11-12 20:18
updated_at: 2026-11-12 20:18
---

## Context

Child of t2258 (reader levels and readable prose for the website docs),
created by t2258_9 (Workflows audit, Parallel group, local part) at its
ledger close-out on 2026-11-12. t2258_9 could not audit
`website/content/docs/workflows/crash-recovery.md`, because another session
had an uncommitted edit on it for the whole of t2258_9's run. The binding
audit method says a page that is dirty from another session is not edited,
and is handed to a tracked follow-up instead.

Skipped-page ledger entry, as recorded in t2258_9's plan:

| Page | Reason | Dirty state seen |
|---|---|---|
| `workflows/crash-recovery.md` | t2284 (`Implementing`) had an uncommitted edit at planning and still at close-out | a one-line diff at L71: the "Your own session re-claiming" bullet now says the pick "still asks the reclaim question (the anomaly prompt), so a re-pick is confirmed rather than silent" |

**Before starting:**
- Check that t2284 has committed (or archived) its edit, and that the page
  is clean (`git diff --quiet HEAD -- <page>`, `git status --short -- <page>`).
- If it is still dirty, stop: do not edit over another session's change.
- Once it is clean, t2284's bullet is ordinary text. Audit it like the rest,
  but check its claim against `aitask_pick_own.sh` first and keep its
  meaning.

## Read first

- The parent task `aitasks/t2258_doc_audience_levels_and_readable_prose.md`
  and its plan (§ "Common audit method").
- The archived plan of t2258_9 (`aiplans/archived/p2258/p2258_9_*.md`). Its
  "Agent B" section is the approved restructure design for this page (copied
  below). Read the method, its moved-fact table format and its fix-pass
  lessons there.
- `aitasks/metadata/doc_update_guide.md`: Reader levels, Page types, How a
  subject spans levels, Prose rules.
- `.claude/skills/aitask-docs-review/SKILL.md`.

## Inventory row (measured at 86d4f4aba)

| Page | Lines | depth before → after | Verdict | Violations |
|---|---|---|---|---|
| `crash-recovery` | 188 | intermediate → intermediate | **restructure** | AP2/AP5: it teaches the lock mechanism (PID-anchor resolution order, the `/proc`→`ps`→`kill` liveness lookup, start-time tokens and kinds, macOS) inside a how-to. A 4-row verdict table and a 2-row signal table are outcome tables. Level: 9 status-line tokens (`RECLAIM_CRASH:` …) and internal mechanics (`git worktree list --porcelain`, the plan-marker heuristics). The End-to-End Example repeats the steps. Current-state violations: "predates the PID-anchor work" (L46), "Without this flow… the older wording" (L149), "is no longer needed… now means" (L176). Prose: 48 em dashes, 50 bold spans. `record_gates` is described as "on by default for the fast profile": it is set in the shipped `fast.yaml`, and its default is off. Relevance flag: L30 `aitask_lock.sh` → commands/lock. |

## Restructure design (approved in t2258_9's plan, "Agent B")

Allowed edits: `workflows/crash-recovery.md`, `commands/lock.md`, and
`aidocs/gates/ledger-driven-reentry.md` (§ "Crash-recovery generalization"
only). Run the shared-file gate on each before editing.

**Inbound anchors to keep** (all linked from `commands/lock.md`):
`#lock-anomaly-fallback`, `#multi-pc-reclaim`,
`#when-the-holder-is-still-running` and `#when-the-recovery-path-fires`.

**The page keeps:**
- an intro: what happens after a crash;
- one numbered procedure "Recover a task after a crash": re-pick; read the
  survey (example block kept, one plain line per field, no git mechanics);
  choose **Reclaim and continue** / **Pick a different task** (decline
  leaves the worktree alone); where it resumes (the three checkpoint
  bullets, short; `record_gates` reworded); the remote check before
  resuming (short);
- "When the Recovery Path Fires" with its three `###` subsections, each 1–3
  plain sentences, no signal names;
- "When the Holder Is Still Running": plain words, the refusals and what to
  do, including t2284's re-claim bullet;
- Tips, trimmed: outside tmux / `AIT_AGENT_PID`; the board lock is anchored
  to the board; a planned shutdown → freeze; cross-host is the same
  procedure;
- See also.

**Moves → `commands/lock.md` (advanced):**
- New `### The session anchor` under How It Works:
  - pid resolution order (`AIT_AGENT_PID` must exist; `$TMUX_PANE` checked
    against its own server; else `pid: -`, no further fallback);
  - the liveness lookup (`/proc`, `ps`, `kill`; gone only on "No such
    process"; "not permitted" = exists; `hidepid` → unknown);
  - the start-time token and `pid_starttime_kind` (`proc`, `bsdinfo`, `ps`,
    the one-second `ps` rule, crash detection unaffected);
  - the dead/alive/unknown/no-anchor verdict table;
  - `pid: 0` from `aitask_backfill_pid_anchor.sh`: optional, and no signal
    change.
- Extend `### When a Pick Meets a Held Lock`:
  - the signal names per row (`RECLAIM_CRASH`, `LOCK_RECLAIM`,
    `RECLAIM_STATUS`, `LOCK_LIVE_HOLDER`, `LOCK_UNVERIFIABLE_HOLDER`) with
    their field formats, checked against `aitask_pick_own.sh --help` and
    task-workflow Step 4;
  - only a provably dead anchor is reported as a crash;
  - the three prompts' question wording and the shared option list;
  - refusals happen before lock/status/commit;
  - `/aitask-pickrem` aborts rather than forcing.

**Moves → `aidocs/gates/ledger-driven-reentry.md` § "Crash-recovery
generalization"** (contributor-only survey derivation; record `moved`,
never `dropped`):
- worktree resolution from the `branch refs/heads/aitask/<task_name>` entry
  of `git worktree list --porcelain`, and the two situations behind
  `(none — current branch, or fork not reached)`;
- the file counts from `git status --porcelain` / `git diff --stat HEAD`;
- the plan-file fallback marker, used when no checkpoints were recorded.

Check each against `.claude/skills/task-workflow/crash-recovery.md` and
`aitask_gate.sh status`.

**Also:**
- merge the End-to-End Example into the procedure;
- rewrite the current-state sentences positively;
- relevance flag L30: the sentence moves to `commands/lock.md`, so drop or
  rename its `aitask_lock.sh` link text.

## Method (binding; same as t2258_9)

1. Shared-file gate before each edit.
2. Every moved fact is checked in code and recorded:
   source#section → fact → destination#anchor → `moved` / `already-stated` /
   `corrected` / `dropped(reason)`.
3. `/aitask-docs-review <edited pages> --caller audit --budget 0` by an
   independent agent; fix and re-review.
4. `cd website && python3 check_links.py --build` (mandatory) and
   `python3 check_link_relevance.py`; open every target this task added or
   retargeted.
5. Claim-level survival check (an independent agent classifies every claim
   of every removed block as preserved / weakened / missing against its
   destinations), runs 1 and 2, before the commit.
6. Every leaf page keeps `depth:`.

## Coordination

- Notes: t2258_6 owns `commands/lock.md`'s later audit, and t2258_8
  reconciles this ledger. Send each a note when this lands.
- Do not move facts back onto `concepts/locks.md` (t2258_3's moved facts
  stay on workflow, command or development pages).

## Verification

- The plan holds the moved-fact table, the review lines, the link results
  and the survival counts.
- `check_links.py --build` exits 0.
- `crash-recovery.md` has `depth: [intermediate]`.
