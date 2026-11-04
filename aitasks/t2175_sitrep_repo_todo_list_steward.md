---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [ait_monitor, aitask_monitormini, sitrep]
children_to_implement: [t2175_5, t2175_6]
created_at: 2026-10-31 19:58
updated_at: 2026-11-04 15:26
---

# Sitrep: a per-repo, persisted todo list with pointer-based context

## Problem
Finished or frozen code-agent windows are kept open only for the follow-up
information in their final output (follow-up tasks, "push main", "deploy dev",
an implementation trail's next steps, unpicked tasks an exploration created).
The output goes stale, the user re-asks "what is the status now" in each window
and loses track of which question went to which window. Closing the window
destroys the information (`aitask_frozen.sh drop` deletes the capture).

## Feature
**Sitrep** is a per-repo, advisory-only steward agent that runs in its own
window (with a minimonitor companion) and owns ONE persisted todo list for the
repo: what is going on and what is pending, so finished agents can be closed.
Analogous to the shadow agent (`aidocs/framework/shadow_agent.md`) but scoped
to a whole repo, not one followed agent.

## Decisions (settled with the user)
- Storage: per-repo, gitignored directory `.aitask-sitrep/` (like
  `.aitask-shadow/`), persisted on disk, never committed. NOT agent memory.
- Harvest: automatic at agent freeze and at the workflow-end banner; closing an
  agent runs harvest first and `drop` refuses if harvest fails.
- Authority: advisory only. Never picks, pushes, edits code or sends keystrokes.
- Scope: one sitrep per repo (project root). Frozen and live agents from any
  tmux session are included; the frozen-agent store
  (`~/.config/aitasks/agent_sessions.json`, captures in
  `~/.config/aitasks/frozen/<id>/capture.txt`) is global, so group by root.
- Trail status: report and offer. Sitrep resolves the trail's tasks and says
  whether the trail is stale; refreshing it is `aitask-trail refresh`, run on
  user confirmation. Sitrep never writes the trail itself.
- Pick suggestions reuse `aitask-backlog-roadmap`; do not reimplement ranking.

## Sources feeding the list (three kinds)
1. **Wrap-up**: a finished pick agent's final output (the workflow-end banner:
   `outcome:`, `pushed:`, `follow-ups created:` plus the free prose above it).
2. **Trail**: existing trail artifacts (`ait artifact`, `aitask-trail`).
3. **Exploration**: tasks created by a finished `aitask-explore` agent that
   have not been picked; each stays listed until picked, folded, archived or
   dismissed. VERIFY whether task files record their creating skill; if not,
   take the ids from the explore agent's final output.

## The file: `.aitask-sitrep/todo.md`
Markdown (agent-readable verbatim), two parts, written ONLY through one locked
helper (mutex + atomic write + rolling backup, modelled on
`aitask_shadow_rejected.sh`).

**Part 1: Todo.** Short, refreshed by script. Situation text per theme, then
items grouped Pick now / Next / Waiting / Recently done. Item line: id, kind
(`task|action|question|watch`), state (`open|done|dismissed|unknown`), title,
`checked_at`. Agent-derived items are marked as such.

**Part 2: Context.** One entry per item. A MAP, NOT A SUMMARY, so it cannot go
stale. Holds only (a) stable background: what the item is and why it exists in
1-2 sentences, origin agent/task/commit/date, theme; (b) sources: task and plan
paths, trail handle, capture file + line range, commit shas, related items.
Does NOT hold status, what is next, counts, overlap with in-flight work, or
summaries of task/plan content; those live in Part 1 or are derived on demand
by following a pointer. Q&A is kept in a separate dated log, never in context.

## Rules for the whole feature
- The file is a source of truth (dismissals, agent-derived items and Q&A are not
  rebuildable): atomic writes, locked single writer, rolling backup.
- Unverifiable state shows as `unknown`, never as done.
- Task items link to the task file and show its live state; they never copy its
  content (Sitrep must not become a second board).
- Cross-repo follow-ups (`aitasks#t2171`) are recorded as references and marked
  unverified unless the project registry resolves them.
- Answers come from the sources, not remembered summaries; the agent warns when
  answering from a stale `checked_at`.

## Children (strict order; each unblocks the next)
1. todo.md format, locked writer, backup
2. Harvest parser (items + context entries from finished agents)
3. Deterministic refresh (Part 1 only)
4. The sitrep skill and window (+ minimonitor companion)
5. Monitor key: harvest-and-close

Other code-agent ports of the skill (codex, opencode) are separate follow-up
tasks after the Claude Code version, per CLAUDE.md.
