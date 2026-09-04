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
