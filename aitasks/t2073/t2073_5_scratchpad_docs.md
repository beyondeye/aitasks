---
priority: medium
effort: medium
depends: [t2073_4]
issue_type: documentation
status: Implementing
labels: [website, scratchpad]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2073
created_at: 2026-10-20 10:32
updated_at: 2026-10-21 08:50
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2073_1** id=2026-10-20T09:26:38Z.e2d6a2801d7b97930ea15dc0 from=t2073_1 from_verified=yes at=2026-10-20T09:26:38Z base=d70250f708143ce51667dd1491ae34f6919a4df5 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2073_1 (the store helper, landed as d70250f70); consuming it is your call.
> | 
> | Your task body (~line 22) gives the autosave loss window as "last 3 s of edits plus one in-flight save". That is narrower than what the design delivers:
> | 
> | - Saves are serialized, so edits made while a save is pending queue behind it. A stalled save therefore extends the window: a save that captured at 3 s and returned at 20 s does not cover an edit typed at 4 s.
> | - The helper's 5 s figure is a lock-wait budget only. No save duration is bounded.
> | 
> | The docs should use the content-based wording now in the shared paragraph of the parent plan and p2073_{2,3,4,5} (your plan: 0df4add1b):
> | "On a hard kill, changes not included in the latest successfully saved buffer may be lost, including edits queued during a pending save. Autosave targets starting within roughly three seconds when no save is pending; this is not a maximum loss window."
> | 
> | Also note that a write can commit before its response is read, so docs should say "may be lost", not "will be lost". Per your task's rule, document what the code does: check t2073_2's archived plan for the app's final wording before writing.

> **👁 note:read** id=2026-10-21T05:49:56Z.02e10fc47bf8430e431615d9 by=t2073_5 at=2026-10-21T05:49:56Z mode=explicit ids=2026-10-20T09:26:38Z.e2d6a2801d7b97930ea15dc0
