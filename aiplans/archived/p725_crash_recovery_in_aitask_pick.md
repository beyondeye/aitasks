---
Task: t725_crash_recovery_in_aitask_pick.md
Base branch: main
plan_verified: []
---

# Plan: t725 — Document Crash Recovery Workflow

## Context

Task 723 shipped a crash-recovery feature in `/aitask-pick`: when tmux (or
the host shell) crashes mid-implementation and the user re-picks the task,
the workflow now detects the dead-PID anchor and routes through a dedicated
`crash-recovery.md` procedure (multi-PC reclaim + same-host crash + lock
anomaly fallback). The procedure surveys uncommitted in-progress work and
asks the user to **Reclaim and continue** or **Pick a different task**.

Task 723 is implemented and archived but the website documentation was
never updated. There is no user-facing description of what crash recovery
is, when it fires, what the survey block looks like, or what the
Reclaim/Decline decision means. This task adds that page.

User direction (collected at planning):

- **Scenario emphasis:** Document `RECLAIM_CRASH` (same-host crash, the
  common case the user actually hits when tmux dies) as the headline.
  Mention the other two recovery paths as side notes — they exist and use
  the same prompt UX, but they are not the focus.
- **Page layout:** New `workflows/crash-recovery.md` page only. Add small
  cross-link references from `concepts/locks.md` and the
  `skills/aitask-pick/_index.md` Step 4 narration so the new page is
  discoverable from the obvious entry points. No content migration into
  those existing pages.
- **Survey detail:** Show a real example "Prior in-progress work" block
  with a per-line explanation of what it tells the user.

---

## Files to modify / create

### Create
- `website/content/docs/workflows/crash-recovery.md` (new) — the workflow
  page. Weight `42` (sits in the **Parallel** group right after
  `parallel-development.md` (weight 40) and before `parallel-planning.md`
  (weight 45)).

### Modify
- `website/content/docs/workflows/_index.md` — add the new page to the
  **Parallel** group bullet list.
- `website/content/docs/concepts/locks.md` — add one bullet under
  `## See also` linking to the new workflow page (no body changes).
- `website/content/docs/skills/aitask-pick/_index.md` — extend the Step 4
  bullet ("Assignment") with one short clause cross-linking the new page
  for the reclaim case. No restructuring.

---

## Step 1 — Write `workflows/crash-recovery.md`

**Frontmatter:**

```yaml
---
title: "Crash Recovery"
linkTitle: "Crash Recovery"
weight: 42
description: "Resume a task whose prior agent died mid-implementation, with a survey of leftover work before deciding to reclaim or drop"
depth: [intermediate]
---
```

**Top intro paragraph (one short paragraph):**

State the core flow in plain English: tmux/host-shell crashes, agent dies,
task stays `Implementing` with a held lock, user re-runs `/aitask-pick
<N>`, the workflow notices the prior PID is gone, surveys uncommitted work
in the worktree, and asks the user to reclaim or drop. Mention the
underlying mechanism in one clause (PID anchor in lock metadata, sharp
binary "alive vs dead" signal) and link to `concepts/locks` for the lock
itself.

**Sections:**

### `## When the Recovery Path Fires`

Three triggers, focus on the headline case:

1. **Same-host crash (headline).** Lock recorded `pid:` and
   `pid_starttime:` when claimed. On re-pick, `aitask_pick_own.sh` checks
   the prior PID via `kill -0` and (Linux only) starttime. PID gone or
   starttime mismatch (PID-recycling defense) on the same hostname → emits
   `RECLAIM_CRASH:`. This is the case the user actually hits when tmux
   crashes.
2. **Multi-PC reclaim (side note).** You started a task on PC_A, switched
   to PC_B, ran `/aitask-pick` on the same task ID. Hostname differs from
   the recorded one → emits `LOCK_RECLAIM:`. Same Reclaim/Decline UX,
   different prompt wording. Predates t723; lives in the same procedure now.
3. **Lock anomaly fallback (side note).** No PID anchor in the lock (legacy
   pre-t723 lock that was never backfilled), or lock missing entirely while
   the task is `Implementing` and `assigned_to` matches the user → emits
   `RECLAIM_STATUS:`. Same UX, different wording. After deploying t723,
   running `./.aitask-scripts/aitask_backfill_pid_anchor.sh` once retroactively
   tags pre-anchor locks with a `pid: 0` sentinel so future re-picks route
   through the headline `RECLAIM_CRASH:` path.

### `## The In-Progress Work Survey`

Explain that before prompting, the procedure surveys uncommitted work in
the worktree (or current branch if no separate worktree) so the user can
make an informed decision.

Show an example block:

```
Prior in-progress work:
- Worktree: aiwork/t42_add_login
- 5 modified, 2 staged, 1 untracked
- Plan: Steps 1-3 complete, "Final Implementation Notes" not yet written
```

Per-line explanation:

- **Worktree line.** Resolved from `git worktree list --porcelain`. Falls
  back to `(current branch)` when no separate `aitask/<task_name>` worktree
  exists.
- **File counts line.** Derived from `git status --porcelain` and `git
  diff --stat HEAD` against the resolved worktree. The split surfaces "you
  have 2 staged commits ready, 5 changes still unstaged, 1 untracked file"
  at a glance.
- **Plan line.** Tail of `aiplans/p<N>_<name>.md` (or
  `aiplans/p<parent>/p<parent>_<child>_<name>.md`) — the procedure looks for
  the most-recent marker: a "Final Implementation Notes" stub, checked-step
  markers (`- [x]`), or a "Post-Review Changes" section. Gives a one-line
  sense of how far the prior agent got.

When the survey finds nothing, the block reads `Prior in-progress work:
none detected` — happens when the prior agent crashed before making any
changes, or the worktree was already cleaned up.

### `## The Reclaim / Decline Prompt`

Show the three case-specific question wordings (verbatim from
`crash-recovery.md`), with the survey block embedded:

- `RECLAIM_CRASH` — *"Previous agent on this machine appears to have
  crashed (PID `<pid>` no longer running since `<locked_at>`). … Resume
  with prior work intact?"*
- `LOCK_RECLAIM` — *"Task t<N> is already in `Implementing`, claimed by
  you on `<prev_hostname>` since `<locked_at>` (current host:
  `<current_hostname>`). … Reclaim and continue here?"*
- `RECLAIM_STATUS` — *"Task t<N> shows status `Implementing` already
  assigned to you, but no PID anchor matches your environment. … Reclaim
  and continue here?"*

Then the two options (consistent across signals), header `Reclaim`:

- **Reclaim and continue** — Resume work in place. The lock is now held on
  this host. Prior in-progress changes remain intact in the worktree (or
  current branch). The picker continues into Step 5/6 as if the original
  pick never crashed.
- **Pick a different task** — Release the lock, revert the task to
  `Ready`, clear `assigned_to`, commit and push. Control returns to the
  calling skill's selection. Prior uncommitted changes in the worktree
  are **not** discarded — the user is responsible for stashing or removing
  them out-of-band. Mention this clearly: declining only resets the
  task's metadata, not its working tree.

### `## End-to-End Example`

Walk through the headline RECLAIM_CRASH case as a single example narrative:

1. Picker runs `/aitask-pick 42`, claims the lock, enters plan mode,
   starts implementing in `aiwork/t42_add_login`.
2. tmux crashes (or `tmux kill-server`, or the laptop loses power). The
   bash/Claude PID dies. Task `t42` is still `status: Implementing`,
   lock still pinned to this host with `pid: <dead-pid>`.
3. User opens a fresh terminal, re-runs `/aitask-pick 42`. The picker
   parses the lock, runs `kill -0 <dead-pid>` → ESRCH → emits
   `RECLAIM_CRASH:`.
4. The Crash Recovery procedure surveys the worktree, prints the
   "Prior in-progress work" block (3 modified files, partial plan
   progress), asks the case-specific prompt.
5. User picks **Reclaim and continue**. Workflow proceeds to Step 5 with
   the lock now anchored to the new agent's PID; prior changes are
   intact and visible to the resumed agent.

### `## Tips`

- **Backfill once after upgrading past t723.** Pre-existing
  `Implementing` locks written before t723 lack `pid:`/`pid_starttime:`.
  Running `./.aitask-scripts/aitask_backfill_pid_anchor.sh` once tags them
  with the `pid: 0` sentinel so future re-picks route through
  `RECLAIM_CRASH:` rather than the legacy `RECLAIM_STATUS:` fallback.
- **Decline does not touch your worktree.** "Pick a different task"
  reverts task metadata and releases the lock. Uncommitted files in the
  worktree (and the worktree itself) are left alone — clean them up
  manually if you don't want to come back to them.
- **macOS portability.** PID-recycling defense via `pid_starttime` is
  Linux-only (`/proc/<pid>/stat` field 22). On macOS the recovery falls
  back to PID liveness alone (`kill -0`) — the rare PID-recycling case
  is a documented minor edge there.
- **Cross-host case is the same procedure.** Multi-PC reclaim
  (`LOCK_RECLAIM:`) is handled by the same Crash Recovery procedure with
  different prompt wording. The decision UX (Reclaim / Decline) is
  identical.

### `## See also`

- [Concepts: Locks](../../concepts/locks/) — the lock branch and
  `aitask_lock.sh` plumbing the recovery reads from
- [Parallel Development](../parallel-development/) — broader concurrency
  picture this fits into
- [Manual Verification](../manual-verification/) — sibling workflow page
  format used as a template

---

## Step 2 — Cross-link from `workflows/_index.md`

Edit the **Parallel** group bullet list. Insert after the existing
`Parallel Planning` bullet, before `Claude Code Web`:

```markdown
- [Crash Recovery](crash-recovery/) — Resume a task whose prior agent
  died mid-implementation, with a survey of leftover work before deciding
  to reclaim or drop.
```

Why between parallel-planning and claude-web: weight 42 places it visually
in the parallel cluster; the bullet order in `_index.md` mirrors weights.

---

## Step 3 — Cross-link from `concepts/locks.md`

Append a single bullet at the bottom of `## See also`:

```markdown
- [Workflows: Crash Recovery]({{< relref "/docs/workflows/crash-recovery" >}}) —
  Reclaim a task whose prior agent crashed mid-implementation
```

No body changes to `locks.md`.

---

## Step 4 — Cross-link from `skills/aitask-pick/_index.md`

In the **Step-by-Step** numbered list, item 5 (`Assignment` — current
text starts "Tracks who is working on the task via email…"), append one
short clause at the end:

> If the task was already `Implementing` and assigned to you (e.g., a
> prior agent crashed mid-implementation), routes through the
> [Crash Recovery](../../workflows/crash-recovery/) flow before continuing.

No restructuring of the surrounding bullets.

---

## Verification

This is a documentation-only task. Verification is a local Hugo build
with the new page rendering correctly:

1. `cd website && ./serve.sh` (or `hugo build --gc --minify`).
2. Navigate to `/docs/workflows/` and confirm "Crash Recovery" appears in
   the Parallel group bullet list.
3. Open `/docs/workflows/crash-recovery/` directly and verify:
   - Frontmatter renders (title in sidebar, description in page header).
   - All four section headers render (`When the Recovery Path Fires`,
     `The In-Progress Work Survey`, `The Reclaim / Decline Prompt`,
     `End-to-End Example`, `Tips`, `See also`).
   - Code blocks render (the example survey block, the prompt wordings).
4. Open `/docs/concepts/locks/` and confirm the new "See also" bullet
   resolves correctly to the workflow page.
5. Open `/docs/skills/aitask-pick/` and confirm the Step 5 ("Assignment")
   bullet now ends with the new clause and the link resolves.
6. Spot-check internal links in the new page (`{{< relref ... >}}` and
   relative `../` paths) by clicking each one in the local server.

Optional: run `hugo --gc --minify --printPathWarnings` and confirm no
broken-link warnings are added by this change.

---

## Out of scope

- Documenting `aitask_lock.sh --check` / `--force-unlock` UX (already
  covered by `commands/lock`).
- Backfill helper user-guide page (mentioned inline in Tips; standalone
  page would be over-investment for a one-shot helper).
- Adding the workflow page to `concepts/task-lifecycle.md` (lifecycle is
  about task states; this is about pick-flow recovery — different axis).
- Internationalization / multi-language. Hugo site is English-only today.

---

## Final Implementation Notes

- **Actual work done:** Shipped exactly as planned. New page `website/content/docs/workflows/crash-recovery.md` (~95 lines including frontmatter): RECLAIM_CRASH as the headline case with `## Same-host crash (headline case)`, LOCK_RECLAIM and RECLAIM_STATUS as side notes under the same H2, full "In-Progress Work Survey" section with concrete example block + per-line explanation (worktree, file counts, plan progress), three case-specific question wordings extracted verbatim from `crash-recovery.md`, the two Reclaim/Decline options with the explicit "decline does not touch your worktree" caveat, an end-to-end narrative, four tips (backfill helper, decline-vs-worktree, macOS portability, cross-host shares the procedure), See also block. Three cross-link edits: `workflows/_index.md` Parallel-group bullet (between parallel-development and parallel-planning, mirroring weight 42), `concepts/locks.md` See-also bullet (using `{{< relref >}}` form to match the rest of the page), `skills/aitask-pick/_index.md` Step 5 narration (single trailing clause, no restructuring).

- **Deviations from plan:** None of substance. One minor structural tightening during writing: split "When the Recovery Path Fires" into three H3 subsections instead of a flat numbered list, so each scenario has its own anchor + TOC entry. The TOC rendered in the build confirmed this read better than a numbered paragraph.

- **Issues encountered:** None. Hugo build passed first try (182 pages, +1 from 181). Pre-existing `.Site.AllPages` deprecation warning is unrelated to this change.

- **Key decisions:**
  - **Weight 42** chosen for the new page so it sits visually between `parallel-development.md` (40) and `parallel-planning.md` (45) in the Parallel group — matches the bullet ordering in `_index.md`.
  - **Cross-link form per file:** locks.md already uses `{{< relref "/docs/..." >}}` for See-also entries, so the new bullet matches; workflows/_index.md and skills/aitask-pick/_index.md use relative paths (`crash-recovery/`, `../../workflows/crash-recovery/`) matching their existing siblings. Mixing forms would have been a needless inconsistency.
  - **Side-note treatment for LOCK_RECLAIM / RECLAIM_STATUS** per user direction during planning: each gets its own H3 under "When the Recovery Path Fires" but the body of the page (survey, prompt UX, end-to-end example) focuses on the same-host crash case. The three question wordings are still listed verbatim in "The Reclaim / Decline Prompt" so users hitting the side-note paths can confirm they are looking at the same procedure.
  - **No new content in `concepts/locks.md` or `skills/aitask-pick/_index.md`** beyond cross-link bullets — per user choice (option 1 of the layout question), the new workflow page is the canonical location.
  - **"Decline does not touch your worktree"** called out twice (once in the option description, once in Tips) because a user who picks "Pick a different task" expecting it to clean up the worktree could lose orientation. The repetition is deliberate.

- **Upstream defects identified:** None

