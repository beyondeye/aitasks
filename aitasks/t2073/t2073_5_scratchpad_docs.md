---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [website, scratchpad]
gates: [risk_evaluated]
anchor: 2073
created_at: 2026-10-20 10:32
updated_at: 2026-10-20 10:32
---

## Context

Child of t2073 (minimonitor scratchpad pane). It writes the user-facing website
documentation for the scratchpad once the feature has landed (t2073_1–t2073_4).
Follow `aidocs/framework/documentation_conventions.md`: describe the current state
only, with no version history. Before writing, read the landed code and the archived
child plans (`aiplans/archived/p2073/`), and document what the code does, not what the
plans intended. For example: the exact key (`o`), the config key names and defaults,
the header states, and the autosave loss window (last 3 s of edits plus one in-flight
save).

## Key Files to Modify

- NEW `website/content/docs/tuis/scratchpad/_index.md`, `how-to.md`, `reference.md`.
  Use the frontmatter shape of `tuis/frozenagent/` (`_index` weight around 18,
  `how-to` weight 20 "How-To", `reference` weight 30 "Reference"). Content to cover:
  - what it is;
  - opening it with minimonitor `o`;
  - placement and the `tmux.scratchpad_position` / `tmux.scratchpad_height` config;
  - editing, copy and paste keys (ctrl+s, ctrl+q, ctrl+c copy via the tmux buffer
    and OSC 52, ctrl+v and terminal paste);
  - where notes are stored (`.aitask-scratchpad/<id>/notes.md`, gitignored);
  - persistence for aitask agents (`agent-pick|qa|resume-<id>`) across killing and
    re-picking the agent;
  - unsaved pads for other agents;
  - dropping at archival, including folded tasks;
  - autosave and the loss window;
  - one pad per task, with a read-only view when a second one opens;
  - it closes with its agent and survives freeze and restore.
- `website/content/docs/tuis/minimonitor/how-to.md`: a "How to Open a Scratchpad"
  section next to "How to Launch a Shadow Agent", plus the "Key Bindings Quick
  Reference" entry. In `minimonitor/_index.md`, mention the key.
- `website/content/docs/tuis/_index.md`: add to the "Available TUIs" list.
- `website/content/docs/commands/_index.md`: add a TUI table row and a usage example
  line.
- `website/content/docs/tuis/monitor/reference.md`: add the two keys to the tmux
  Configuration table (~:199-210).
- `website/content/docs/tuis/frozenagent/how-to.md`: a short note that a bound
  scratchpad stays open across freeze and restore.

## Verification Steps

- `cd website && hugo build --gc --minify`
- `cd website && python3 check_links.py --build` (mandatory)
- Optionally `python3 check_link_relevance.py` for the new links.
