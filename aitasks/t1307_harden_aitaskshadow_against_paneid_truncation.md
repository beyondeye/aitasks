---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Implementing
labels: [shadow, skills, robustness]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-28 18:30
updated_at: 2026-07-28 18:44
---

Harden the `aitask-shadow` skill against model-side truncation of the
`<followed_pane_id>` argument.

## Symptom (observed 2026-07-28)

A shadow companion was launched by minimonitor for the codeagent working on
thinking_app task t57_5. The launch command reaching the shadow agent was
correct — the pane verbatim showed:

```
› $aitask-shadow %237 57_5
```

and the minimonitor's lifecycle stamp on the shadow pane was correct
(`@aitask_shadow_target=%237`). But the shadow agent (Codex CLI running
`gpt-5.6-terra`) transcribed the pane id `%237` down to `%7` — dropping the
middle digits — when it built its first tool call:

```
• … inspect the captured output for pane 7 …
• Ran ./.aitask-scripts/aitask_shadow_capture.sh %7
  └ can't find pane: %7
```

It then self-recovered (listed panes, matched "%237 (not %7)", re-ran the
capture against %237) and produced valid advisory concerns, so no harm
resulted this time. The recovery is not guaranteed, though — a truncated id
that happens to collide with a *live but wrong* pane would silently shadow the
wrong agent.

## Root cause

This is model-side argument mangling, not a wiring bug: the launcher
(`aitask_minimonitor` / minimonitor `_spawn_shadow`), the argument passing, and
the `@aitask_shadow_target` stamp all carried `%237` correctly. The Codex model
simply mis-copied the id when constructing the shell command.

A likely contributing factor: the skill's argument documentation uses a
single-digit example pane id, which anchors the model toward short ids:

- `.claude/skills/aitask-shadow/SKILL.md:26` — "the tmux pane id (e.g. `%5`) of
  the agent you …"

## Proposed hardening

1. Change the pane-id example from a single-digit id (`%5`) to a realistic
   multi-digit id (e.g. `%237`) so the model is not primed toward a short shape.
2. Add an explicit instruction next to the capture step (around the
   `aitask_shadow_capture.sh <followed_pane_id>` line, SKILL.md:68) telling the
   agent to pass `<followed_pane_id>` **verbatim** — never abbreviate, reformat,
   or re-derive it — and, if the capture fails with "can't find pane", to
   re-resolve via `tmux list-panes` rather than guessing (codify the recovery
   the model improvised this time).

## Edit surface / notes

- The `%5` example and the capture instructions appear in the shadow SKILL and
  its agent variants: `.claude/skills/aitask-shadow/SKILL.md`,
  `.opencode/skills/aitask-shadow/SKILL.md`, `.agents/skills/aitask-shadow/SKILL.md`.
  Check whether these are hand-maintained copies or rendered from a shared
  source/template, and apply the change at the source so all variants stay in
  sync (the downstream installs — e.g. thinking_app — are framework-synced from
  this repo).
- Keep the change documentation-only (no script/logic change); the capture
  script already errors cleanly on a missing pane.
