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
