---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [task_workflow, execution_profiles, claudeskills]
gates: [risk_evaluated]
created_at: 2026-10-06 23:13
updated_at: 2026-10-06 23:13
---

## Goal

Make the satisfaction-feedback step optional, driven by the execution-profile key
`enableFeedbackQuestions`, and **render it away entirely** from the per-profile
skill output when the key is `false`. Then make **feedback disabled the default
in the `fast` profile**.

## Current state (explored)

- The key already exists: `fast` sets `enableFeedbackQuestions: true`
  (`aitasks/metadata/profiles/fast.yaml:12`, `seed/profiles/fast.yaml:10`),
  `remote` sets `false`, `default` omits it (absent = `true`).
- `.claude/skills/task-workflow/satisfaction-feedback.md` already gates on it via
  Jinja, but **only substep 1 of Step 1** (a "skip the remainder" line). A
  `false` profile still renders the full procedure: the NON-SKIPPABLE banner,
  the rating `AskUserQuestion`, and the verified-score update — the agent is told
  to skip it, but it is all still in the rendered text.

## Usage stats must survive (decided)

Step 0 of the same procedure is the **only** data path that bumps `usagestats`
(`aitask_usage_update.sh --skill <name>`) — nothing else in `.claude/skills/` or
`.aitask-scripts/` calls it. It is independent of `enableFeedbackQuestions` in
value (`remote` still bumps it), but it is collected *at the feedback call site*.
Decision: when feedback is disabled, **keep the usage bump** — only the rating
prompt and the verified-score update disappear.

Suggested shape (planning may refine): split usage recording from the feedback
question so call sites always render a usage-recording step, and render the
feedback part (rating question + `aitask_verified_update.sh`) only when the
profile enables it. Keep the `usage_collected` / `feedback_collected` guard
semantics and the `detected_agent_string` reuse.

## Touchpoints

Rendered task-workflow (`.claude/skills/task-workflow/`):
- `satisfaction-feedback.md` — the procedure itself (Jinja-gate the feedback part;
  disabled profile renders no prompt, no score update, no NON-SKIPPABLE banner)
- `SKILL.md` — Step 9b (~:1072), the child "Stop here" exit (~:436), context
  variable table (`feedback_collected`, `usage_collected`, `detected_agent_string`
  ~:24-26), Procedures index (~:1086-1088), the push-after-archival → Step 9b
  reference (~:1002)
- `planning.md:350` and `cross-repo-child-assignment.md:163` — "Stop here" exits
- `profiles.md:42/219/283` — schema row, example, and the "defaults to true"
  note; document that `false` renders the feedback part away while usage is
  still recorded

Templated callers outside task-workflow:
- `.aitask-scripts/skill_templates/_auto_continue_block.j2` (`feedback_skill_name`,
  used by `aitask-explore/SKILL.md.j2:323` and `aitask-revert/SKILL.md.j2`)
- `aitask-wrap/SKILL.md.j2` (Step 6), `aitask-qa/SKILL.md.j2` (Step 7) and
  `aitask-qa/test-plan-proposal.md:81`

**Static (non-rendered) skills read the raw source**
`.claude/skills/task-workflow/satisfaction-feedback.md` at runtime: add-model,
changelog, docs-gap, explain, refresh-code-models, reviewguide-classify,
reviewguide-import, reviewguide-merge, web-merge, work-report. The key-absent
(`{% else %}`) runtime-check branch must stay valid for them — do not make the
raw source unusable without a profile.

Profiles:
- `aitasks/metadata/profiles/fast.yaml` and `seed/profiles/fast.yaml` →
  `enableFeedbackQuestions: false`

## Tests / goldens

- `tests/test_skill_parity_runtime_vs_rendered.sh:145-148` (the fast row
  currently expects "Profile 'fast' sets `enableFeedbackQuestions: true`")
- `tests/test_skill_render_task_workflow.sh:334`
- `tests/golden/procs/task-workflow/satisfaction-feedback-*.md` and any skill
  goldens that embed the call sites (incl.
  `tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md:550`)
- Add a render assertion that a `false` profile's rendered output contains no
  rating question / `aitask_verified_update.sh`, yet still contains the
  `aitask_usage_update.sh` call
- Run `./.aitask-scripts/aitask_skill_verify.sh` and regenerate goldens in the
  same commit (see "Regenerate goldens after any `.md.j2` or closure edit" in
  `aidocs/framework/skill_authoring_conventions.md`)

## Coordination

- `t1357_3` (step 4, "Step 9b capture hook") plans to pass `--task-id` to the same
  `aitask_usage_update.sh` call in Step 9b. If this task moves or renames that
  call, send t1357_3 a note (`/aitask-note`) with the new location.

## Follow-ups

Per CLAUDE.md, the Claude Code version is changed first; suggest separate
aitasks to port the change to Codex CLI (`.agents/skills/`) and OpenCode
(`.opencode/skills/`, `.opencode/commands/`) variants.
