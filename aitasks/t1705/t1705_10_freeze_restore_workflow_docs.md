---
priority: medium
effort: medium
depends: [t1705_9]
issue_type: documentation
status: Ready
labels: [documentation, website, docs, workflows, concepts, ait_setup, codeagent]
gates: [risk_evaluated]
anchor: 1705
created_at: 2026-09-04 16:13
updated_at: 2026-09-04 16:13
---

## Context

Tenth child of t1705 (frozen code agents). **Workflow and concept
documentation** — requested explicitly by the user at planning: the freeze
feature documented "as a workflow", not only as TUI reference. t1705_9
documents the TUI surfaces; this child documents *when and why* a user
freezes, restores, re-picks or drops, the **framework session** concept
behind it, and what `ait setup` installs to make it work. Current-state
prose only (`aidocs/framework/documentation_conventions.md`); the manual
list in `website/content/docs/workflows/_index.md` must be edited by hand
(memory: `_index.md` is manual). Read the landed code and the t1705_9 pages
before writing — never the plan — for keys, messages and exact behaviour.

## Pages

1. **New** `website/content/docs/workflows/freeze-and-restore-agents.md`
   (front matter like `workflows/parallel-development.md`): `## When to
   freeze` — the three states side by side (live / parked / frozen: process,
   capture, cost, what you keep, how you come back) as a table; the
   "10–20 agents, most kept only for reference" motivation; `## The daily
   loop` — freeze a finished agent from minimonitor (`z`), read it later in
   its own pane (the layout is unchanged: viewer left, companion right),
   search / copy the spawned-task list or the summary, restore vs re-pick
   (**re-pick is usually cheaper** — say why: a fresh context with the task
   file vs replaying a long transcript), drop when done; `## Before shutting
   down` — Freeze-All (`Z`), and Restore-All after the tmux server comes
   back (window re-creation, `-2` suffixes); `## What "unverified" means` —
   the hook-verified vs liveness-only acknowledgement, why the capture is
   kept in the second case, when it happens (hooks not installed, Codex
   without hook support if t1705_1 found so); `## When something goes
   wrong` — restore fails (agent exits, wrong session, binary missing):
   the viewer comes back and the capture is intact; a frozen stand-in that
   died (the stand-in is respawned automatically by reconcile); records
   for windows that no longer exist; `ait frozen reconcile` / the
   maintenance tick; `## Marks and frozen agents` — coexistence with
   priority/parked; `## Limits` — no age-based expiry, disk usage under
   `~/.config/aitasks/frozen/`, the capture cap.
2. **Edit** `website/content/docs/workflows/_index.md` — add
   `- [Freeze and Restore Agents](freeze-and-restore-agents/) — …` to the
   right group (beside Parallel Development / Crash Recovery).
3. **New** `website/content/docs/concepts/framework-session.md` — the
   store (`~/.config/aitasks/agent_sessions.json`, one record per agent
   across projects, 0600), record identity (`root` + window + slot; pane
   ids are location, not identity), the state diagram (live → freezing →
   frozen → restoring → live / aborting → frozen) as a mermaid or ASCII
   block, operation leases and why reconcile waits for them, the
   SessionStart hook and `@aitask_record`, purge rules (`dead_window`,
   `dead_pane`, `capture_missing`), and the env override
   (`AITASKS_AGENT_SESSIONS_FILE`, `AITASKS_FROZEN_DIR`). Link from
   `concepts/_index.md` and from `concepts/agent-memory.md` /
   `concepts/locks.md` where they list per-user state.
4. **Edit** the setup / installation page(s) (`website/content/docs/getting-started/`
   or wherever `ait setup` is documented — locate with `grep -rl 'ait setup'
   website/content/docs`) — a "Session hooks" section: what is written to
   `.claude/settings.json` and `.codex/config.toml`, that user hooks are
   preserved and setup is idempotent, that TOML comments are dropped by the
   merge, how to opt out (delete the entry; setup re-adds only if absent —
   verify the real behaviour in `aitask_setup.sh` before claiming it).
5. **Cross-links**: `tuis/frozenagent/_index.md` (t1705_9) → this workflow
   page; `workflows/parallel-development.md` and `crash-recovery.md` gain a
   one-line pointer where they discuss many agents / lost sessions.

## Reference patterns

- `website/content/docs/workflows/parallel-development.md`,
  `crash-recovery.md`, `shadow-agent.md` — voice and structure.
- `website/content/docs/concepts/locks.md`, `agent-memory.md` — concept
  page shape for per-user on-disk state.
- `aidocs/framework/documentation_conventions.md`; `website/check_links.py`.

## Verification

```bash
cd website && hugo build --gc --minify && python3 check_links.py --build
grep -n 'freeze-and-restore-agents' website/content/docs/workflows/_index.md website/content/docs/tuis/frozenagent/_index.md
grep -n 'framework-session' website/content/docs/concepts/_index.md
```
No code, no tmux.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1705_8** id=2026-09-09T18:30:27Z.67bdf9e529c168862ec9dce2 from=t1705_8 at=2026-09-09T18:30:27Z base=80d5ea53221cf89bcf0fbf4bd14e1ae23f9297b0 base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | t1705_8's acceptance suite measured several user-visible behaviours end to end
> | against a real viewer. Four are easy to document wrongly. Advisory only --
> | verify against the tree before relying on any of it.
> | 
> | 1. **`hook` and `liveness` restores are NOT the same outcome, and the
> |    difference is user-visible.** `RESTORED:<id>|hook` means the resumed agent's
> |    SessionStart hook acknowledged the record: the session id was verified and
> |    THE CAPTURE FILES ARE DELETED. `RESTORED:<id>|liveness` means nothing ever
> |    acknowledged; the coordinator waited out `restore_ack_grace` and confirmed on
> |    the launched pid alone, so the restore is unverified and THE CAPTURE IS
> |    KEPT. Both are successes; only one is verified. Do not describe restore as a
> |    single outcome.
> | 
> | 2. **There are two `drop` verbs and they are not interchangeable.**
> |    `aitask_agent_sessions.sh drop <id>` is the tmux-free store: it removes the
> |    record and the capture files and LEAVES THE STAND-IN PANE RUNNING with all
> |    its stamps ("THIS MODULE NEVER TOUCHES TMUX"). `aitask_frozen.sh drop <id>`
> |    is the engine: it also retires the pane. Both are asserted separately
> |    (acceptance cases 10a / 10b) because they are genuinely different contracts.
> | 
> | 3. **The `frozen:` block in `project_config.yaml` does not accept every knob.**
> |    `capture_max_lines` and `restore_ack_grace` ARE read from it;
> |    `stale_op_grace` is **not** -- `agent_sessions._stale_op_grace()` reads only
> |    `AITASKS_STALE_OP_GRACE`, and only under `AITASKS_TEST_MODE=1`. Documenting a
> |    configurable `frozen.stale_op_grace` would document a silent no-op. Note also
> |    that a positive `AITASKS_RESTORE_ACK_GRACE` (test mode) short-circuits BEFORE
> |    the config is opened, so the env wins where both are set.
> | 
> | 4. **`capture_max_lines` is scrollback DEPTH, not a total line count.** The
> |    engine passes `capture-pane -S -<cap>`, which starts `cap` lines back in
> |    history and runs through the bottom of the visible pane, so the stored
> |    capture holds roughly `cap + pane_height` lines. Measured: cap 120 produced a
> |    132-line capture in an 12-row pane. Saying "captures at most N lines" is
> |    wrong by a pane height.
> | 
> | Also worth a mention if the docs cover restoring after a tmux restart: that
> | route currently fails (t1773) -- a frozen record whose window was closed cannot
> | be restored, because restore branches on the recorded `pane_id` instead of
> | checking the pane. Nothing is lost, but do not document it as working until
> | t1773 lands.

> **✉ note:t1705_9** id=2026-09-10T09:04:57Z.c3ed18370a74314077320714 from=t1705_9 from_verified=yes at=2026-09-10T09:04:57Z base=80d5ea53221cf89bcf0fbf4bd14e1ae23f9297b0 base_branch=main dirty=yes host=Darios-Mac-mini.local
>
> | t1705_9 (TUI-surface docs) is landing. Five facts I verified against the tree
> | while writing those pages bear directly on your workflow/concept pages, and four
> | of them are easy to document wrongly. Advisory only — verify before relying on
> | any of it.
> | 
> | 1. RESTORE IS REFUSED OUTRIGHT FOR AN AGENT WITH NO RESUME SUPPORT.
> |    `agent_restore.py:345-348` returns
> |    `RESTORE_FAILED:<id>|resume_unsupported:opencode` for an opencode record,
> |    before touching the store. The underlying refusal is
> |    `aitask_codeagent.sh:599-606`, which exits 2 with
> |    `Error: RESUME_UNSUPPORTED:opencode` when `--resume-session` is passed.
> |    Claude Code (`--resume`) and Codex (`codex resume`) are both supported today;
> |    opencode is the one that is not. For an opencode agent, RE-PICK IS THE ONLY
> |    ROUTE BACK. Your "When something goes wrong" section is the right home for
> |    this — I deliberately left it out of the TUI-surface pages as per-agent
> |    recovery behaviour rather than TUI surface.
> | 
> | 2. THE TWO ROUTES BACK NEED DIFFERENT IDS, AND A RECORD MAY CARRY ONLY ONE.
> |    Re-pick needs a TASK id (`frozenagent_app.py:851-853` refuses without one:
> |    "This record has no task id — restore instead"). Restore needs a recorded
> |    SESSION id (`agent_restore.py:340-344`, commented "the reason `--repick`
> |    exists"). Worth stating as a pair; I got it backwards in a first draft.
> | 
> | 3. A SUCCESSFUL VERIFIED RESTORE *DELETES* THE CAPTURE — including in re-pick
> |    mode. `agent_sessions.py:798-807`: the hook-ack path sets `ack="hook"` and
> |    calls `remove_captures(rec.id)`, and both `resume` and `repick` reach it.
> |    The full matrix: verified restore -> deleted; verified re-pick -> deleted;
> |    liveness-only restore -> KEPT; failed restore -> KEPT; drop -> deleted.
> |    This matters for your "What 'unverified' means" section: the capture is kept
> |    precisely in the case nobody confirmed the session, and `restored, unverified
> |    — capture kept` is a SUCCESS, not a fault. `restore_verdict` notes it is the
> |    only outcome a codex record can reach, since its interactive TUI fires no
> |    SessionStart hook. Corollary worth telling users: choosing restore or re-pick
> |    is NOT a way to preserve a transcript — copy it out first.
> | 
> | 4. `capture_max_lines` IS SCROLLBACK *DEPTH*, NOT A TOTAL. `_capture()` passes
> |    `capture-pane -S -<cap>`, which starts `cap` lines back in history and runs
> |    through the bottom of the visible pane, so a stored capture holds roughly
> |    `cap + pane_height` lines. Default is 50000 (`agent_freeze.py:118`). "Captures
> |    at most N lines" is wrong by a pane height. The other side of the same fact,
> |    which your `## Limits` section may want: the capture is the TAIL of the
> |    scrollback, so a pane with more history than the cap has already lost its
> |    earliest output before the freeze runs.
> | 
> | 5. `frozen.stale_op_grace` IS NOT A CONFIG KNOB. `capture_max_lines` and
> |    `restore_ack_grace` ARE read from `frozen:` in
> |    `aitasks/metadata/project_config.yaml`; `stale_op_grace` is not —
> |    `agent_sessions._stale_op_grace()` (`:605-621`) reads only
> |    `AITASKS_STALE_OP_GRACE`, and only under `AITASKS_TEST_MODE=1`. Documenting a
> |    configurable `frozen.stale_op_grace` would document a silent no-op. Note also
> |    that no `frozen:` block ships in `seed/` or the live config, so both real keys
> |    are at their defaults unless a project adds one. And `restore_ack_grace` is a
> |    WAITING PERIOD, not an outcome lever: an agent that never acknowledges stays
> |    unverified however high it is set.
> | 
> | ALSO, AND THIS ONE IS MOMENT-RELATIVE — treat it as a pointer to check, not a
> | fact. As of the time of writing, `restoring a frozen record whose window was
> | closed` does not work: `_reconcile_frozen` returns `KEEP:<id>|pane_gone` and
> | `agent_restore._restore` branches on the RECORDED `pane_id`, so it respawns a
> | dead pane. `tests/test_frozen_agents_acceptance.sh` case 6b asserts only the
> | fail-safe half (record and capture survive) and names it as t1773; case 6a — a
> | record whose `pane_id` is empty — does restore into a new window. t1773 was
> | `status: Implementing` when I looked, so RE-CHECK ITS STATE before writing: do
> | not document the closed-window route as working while it is open, and do not
> | document it as broken if it has landed.
> | 
> | Separately and also moment-relative: t1766 (the frozenagent viewer's restore
> | deadline) appeared in my working tree as an uncommitted change from another
> | session while I was implementing. If it has landed by the time you write, the
> | viewer derives its watch deadline from `frozen.restore_ack_grace` like the
> | monitors do. I deliberately wrote the t1705_9 config section so it holds either
> | way rather than asserting a difference — you may want to do the same.

> **✉ note:t1773** id=2026-09-10T12:09:48Z.504dfefb9739218af831c9aa from=t1773 at=2026-09-10T12:09:48Z base=6190fff8f35b816c095905189a39e714eee4b81d base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | t1773 (code commit 6190fff8f) changed restore behaviour that the freeze/restore
> | workflow docs may describe. Tree-relative claims, dated by this note's base SHA:
> | 
> | - A frozen record whose window was closed, or whose tmux server was restarted,
> |   now restores into a NEW window with the recorded name. Previously it failed
> |   with `RESTORE_FAILED:<id>|respawn:respawn-pane refused for %N` and could never
> |   be restored through that path again.
> | - That new-window restore needs some tmux session with a pane under the record's
> |   project root. With none, restore still fails and rolls back, now as
> |   `no_session_for_root:<root>` (the root is named). Recovery is tracked in t1784.
> | - If tmux cannot be reached at all, restore now fails closed before any write:
> |   `RESTORE_FAILED:<id>|preflight:tmux unreachable`.
> | - The recorded pane id is a hint, not a target: the original pane is reused only
> |   if it still carries the record's `@aitask_frozen` stamp, checked and respawned
> |   in one tmux dispatch. `drop` and the stand-in respawn still use the older
> |   two-call pattern (t1783).
> | 
> | Advisory only — verify against the tree before documenting any of it.

> **✉ note:t1778** id=2026-09-10T18:36:47Z.45ef729dc66e52e8a78eaccc from=t1778 at=2026-09-10T18:36:47Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the overlapping
> | task, not an agent working on it, so it is unverified. Advisory only —
> | tree-relative claims are dated by this note's base SHA; `~` line numbers are
> | approximate. Verify before acting. This adds to the t1705_8 / t1705_9 / t1773
> | notes already in your inbox and does not repeat them.
> | 
> | 1. `ait frozen reconcile` (task body) does not exist. `ait` has only
> |    `frozenagent`; t1705_9 deliberately kept aitask_frozen.sh off the dispatcher
> |    (p1705_9 Final Notes: "No `ait frozen` row").
> | 
> | 2. Codex is settled: the hook fires only under `codex exec`, not in its TUI
> |    (aitask_setup.sh ~2883-2885), so an interactive codex restore always ends
> |    liveness/unverified.
> | 
> | 3. The opt-out is not "delete the entry". The Claude hook has its own [Y/n]
> |    prompt in setup (aitask_setup.sh ~2622-2664); a decline is not persisted
> |    (asked again on every `ait setup`); non-interactive runs auto-accept; the
> |    merge dedupes on (matcher, command). So a deleted entry comes back on the
> |    next accepted setup — the opt-out is answering n. "TOML comments are dropped
> |    by the merge" is plausible (tomllib.load at ~2735-2746) but unconfirmed.
> | 
> | 4. concepts/agent-memory.md and concepts/locks.md do not list per-user state
> |    (no `~/.config` or "per-user" hits), so the planned one-line pointers need
> |    new sentences or can be dropped. getting-started is a single
> |    getting-started.md file, not a directory.
> | 
> | 5. The plan's PINNED §D is partly superseded by amendments B1-B4
> |    (`respawn-pane -e`, not an env prefix). Document the amendments.
> | 
> | 6. OVERLAPS:
> |    - t1778 is now unblocked (t1773 and t1766 landed) and adds the closed-window
> |      / tmux-restart restore route and its `no_session_for_root` limit (t1784)
> |      to tuis/frozenagent/how-to.md. Your "When something goes wrong" section
> |      covers the same ground — write it once and link from the other.
> |    - t1687 (Concepts gap sweep) does not list a framework-session page, so
> |      concepts/framework-session.md is yours; concepts/_index.md is also edited
> |      by t1687, t1231_3 and t635_18.
> |    - parallel-development.md and crash-recovery.md also get family-worktree
> |      content from t1166_5 (different sections).
