---
Task: t1150_explore_skill_output_invisible_fable5.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: t1150 — Explore-skill output invisible under Fable 5

## Context

Running `aitask-explore` in Claude Code with the **Fable 5** model, the user never
sees the exploration-result summaries — only the `AskUserQuestion` widgets appear.
Observed live 2026-07-15 (session `4d3526ee-ac00-4cf0-88dc-942f138f348b`): three
consecutive summary attempts were invisible; the user's own replies in that session
("I don't see the result of the exploration") confirm it.

## Root cause (established during planning, with transcript evidence)

**Fable 5 routes long-form assistant prose into a `narration` block (a
thinking-family channel) instead of a plain `text` block, and Claude Code does not
render narration durably** (it is persisted signature-only in the session jsonl —
plaintext empty). The AskUserQuestion correlation is incidental: narration is used
for "commentary around tool use", which is exactly what a summary-before-question
is.

Evidence:
1. **Affected session `4d3526ee`:** all three invisible-summary turns have shape
   `thinking('') + narration('') + tool_use(AskUserQuestion)` — **zero text
   blocks**. Decoded block signatures contain `claude-fable-5` plus the block-type
   strings `thinking` / `narration`. `output_tokens=1885` vs ~150 tokens of visible
   tool_use ⇒ ~1700 tokens vanished into non-rendered blocks.
2. **Contrast:** Opus 4.8 turns in the same session emitted a plain `text` block
   before AskUserQuestion — visible.
3. **Live repro (this planning session, running Fable 5):** a deliberately-composed
   multi-paragraph body text + same-turn AskUserQuestion → transcript shows the
   prose became a narration block (no text block); user confirmed "Not visible at
   all". A turn-final text-only response (no tool call) → user confirmed fully
   visible.

Visibility matrix (Fable 5 + Claude Code):

| Turn shape | Visible? |
|---|---|
| text → end turn (no tool call) | yes |
| AskUserQuestion widget payload (question/options) | yes |
| prose → AskUserQuestion same turn | no (routed to narration) |
| short text → Bash same turn | sometimes (nondeterministic) |

Related (but distinct) upstream issues: anthropics/claude-code #30422 (widget
truncates last line of preceding text), #23862 (widget covers preceding output),
#65841 (widget never renders).

## Approach (user chose: upstream report + skill-side hardening)

The only *structurally guaranteed* visible carriers are (a) turn-final text and
(b) the AskUserQuestion widget payload itself. A skill flow cannot end the turn
mid-procedure, so the mitigation is: **decision-critical summaries must be
embedded in the AskUserQuestion `question` text (condensed) — the preceding prose
stays as best-effort duplication, not the carrier.**

### 1. Harden `aitask-explore` (source of truth: `.claude/skills/aitask-explore/SKILL.md.j2`)

- **Step 2 exploration loop (items 2–3, ~lines 120–127):** keep item 2 ("Present a
  brief summary…") but add a **Visibility rule** and change item 3 so the
  AskUserQuestion `question` field *begins with the condensed findings summary*
  (3–6 bullet lines) followed by "How would you like to proceed?". Rationale note:
  same-turn prose before an AskUserQuestion is not rendered under some
  model/client combinations (Fable 5 narration channel — t1150); the widget
  payload is the reliable carrier.
- **Step 2 Notes (~line 137):** amend "Present findings as a concise bulleted
  summary after each round" with "— duplicated into the question text per the
  visibility rule".
- **Step 3 task creation (~lines 163–178):** instruct that the
  `## Exploration Summary` block be included at the top of the confirm
  AskUserQuestion `question` text (before "Here's the proposed task…"), not only
  as preceding prose.

### 2. Add the generic convention (`aidocs/framework/skill_authoring_conventions.md`)

New short section, e.g. **"AskUserQuestion visibility rule"**: any content the
user needs in order to answer an `AskUserQuestion` MUST be inside the widget
payload (question text / option labels / descriptions). Assistant prose emitted in
the same turn may be routed to a non-rendered narration channel (observed: Claude
Code + Fable 5, t1150). Preceding prose is allowed but only as duplication.

### 3. Regenerate goldens + verify (same commit as the j2 edit)

- Regenerate `tests/golden/skills/aitask-explore/SKILL-{default,fast,remote}-claude.md`
  using the documented loop (skill_authoring_conventions.md §"Regenerate goldens…",
  `skill_template.py` render, claude-only dimensionality — no `{% if agent %}`
  gate is added).
- Run `bash tests/test_skill_render_aitask_explore.sh` and
  `./.aitask-scripts/aitask_skill_verify.sh`; review the golden diff (must match
  the wording edit only).
- Cross-agent trees: the change is in the shared `.md.j2` closure → auto-renders;
  no port tasks needed (no agent-specific surface changed).

### 4. Upstream report (file with `gh`, after user confirms the draft)

- Draft issue for `anthropics/claude-code`: title ≈ "Fable 5: assistant prose
  before a tool call is emitted as non-rendered `narration` blocks — summaries
  preceding AskUserQuestion are invisible". Body: minimal repro (any text +
  same-turn AskUserQuestion under `claude-fable-5`), transcript block-shape
  evidence, visibility matrix, links to #30422/#23862/#65841 as related-but-distinct.
- Confirm draft with the user before posting (outward-facing action).
- After filing: add label `upstream_defect_followup` to t1150
  (`aitask_update.sh --batch 1150 --labels …` preserving existing labels) and
  record the issue URL in the task description + this plan.
- **FILED:** https://github.com/anthropics/claude-code/issues/77849

### 5. Live acceptance (AC 3)

After the wording lands, run one live explore round under Fable 5 (fresh
`/aitask-explore` or scripted) and confirm the findings summary is visible inside
the question widget. Offer a standalone manual-verification follow-up at Step 8c
as backstop if the in-session check is not conclusive.

## Files to modify

- `.claude/skills/aitask-explore/SKILL.md.j2` — wording (Step 2 loop, Notes, Step 3)
- `aidocs/framework/skill_authoring_conventions.md` — new visibility-rule section
- `tests/golden/skills/aitask-explore/SKILL-{default,fast,remote}-claude.md` — regenerated
- `aitasks/t1150_explore_skill_output_invisible_fable5.md` — label + issue URL (via `ait git`)

## Verification

- `bash tests/test_skill_render_aitask_explore.sh` — green, golden diff reviewed
- `./.aitask-scripts/aitask_skill_verify.sh` — green
- Live Fable 5 explore round: summary visible in widget (AC 3)
- Upstream issue URL recorded (AC 2); root cause documented with transcript evidence (AC 1 — done in this plan)

## Step 9 (Post-Implementation)

Profile 'fast', current-branch work — no worktree/merge. Run gates
(`./ait gates run 1150` — task declares `risk_evaluated`), archive via
`aitask_archive.sh 1150`, push via `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Root cause established with transcript evidence during
  planning (Fable 5 emits pre-tool prose as non-rendered `narration` blocks —
  zero `text` blocks in affected turns; confirmed by a controlled live repro in
  the implementing session, itself running Fable 5). Hardened
  `.claude/skills/aitask-explore/SKILL.md.j2` (Step 2 loop visibility rule +
  Notes bullet + Step 3 summary-in-question). Added the generic
  "AskUserQuestion visibility rule" section to
  `aidocs/framework/skill_authoring_conventions.md`. Regenerated the 3 explore
  goldens. Filed upstream issue
  https://github.com/anthropics/claude-code/issues/77849; labeled t1150
  `upstream_defect_followup` and recorded the URL in the task. Live AC check
  passed: a widget-embedded 5-bullet summary was fully visible under Fable 5.
- **Deviations from plan:** None material. The live acceptance was performed
  in-session against the mitigation pattern (widget-embedded summary) rather
  than a full fresh `/aitask-explore` run — the pattern is exactly what the new
  wording mandates, and the user confirmed full visibility.
- **Issues encountered:** `aitask_skill_verify.sh` reports 2 PRERENDER_FAILs
  unrelated to this change (verified pre-existing by stashing this task's edits
  and re-running) — see upstream defects below. Working tree also contained
  foreign concurrent changes (`aitask_setup.sh`,
  `tests/test_applink_setup_gitignore.sh`); staged this task's 5 files
  explicitly.
- **Key decisions:** Chose the widget payload (question text) as the mitigation
  carrier — it is the only structurally guaranteed visible channel besides
  turn-final text (which cannot be used mid-procedure). Preceding prose is kept
  as best-effort duplication. No `{% if agent %}` gate added, so goldens stay
  claude-only per the dimensionality rule.
- **Upstream defects identified:**
  - `.opencode/skills/task-workflow-remote-/cross-repo-child-assignment.md:1 — committed prerender is stale relative to its `.claude/skills/task-workflow/` source (t1117 edited the source without rerendering); `aitask_skill_verify.sh` fails with 2 PRERENDER_FAIL (aitask-pickrem / aitask-pickweb, agent=opencode, profile=remote); fix is `aitask_skill_rerender.sh remote` + commit`

## Risk

### Code-health risk: low
- Markdown-only edits to one template + a convention doc; golden tests (`test_skill_render_aitask_explore.sh` Test 1) catch any unintended render drift · severity: low · → mitigation: none needed

### Goal-achievement risk: medium
- Mitigation relies on future sessions' instruction-following to embed summaries in the question text; the widget payload is structurally rendered, but a model could still under-fill it · severity: medium · → mitigation: askuserquestion_visibility_sweep
- Same invisible-prose hazard exists at other summary-before-question sites outside this task's scope (e.g. `risk-mitigation-followup.md` Part 1's "plain-text numbered list before the prompt", `manual-verification-followup.md` candidate list, review/qa finding summaries) · severity: medium · → mitigation: askuserquestion_visibility_sweep
- Upstream fix timeline (narration rendering in Claude Code) is outside our control; skill-side hardening is the hedge · severity: low · → mitigation: none (accepted)

### Planned mitigations
- timing: after | name: askuserquestion_visibility_sweep | type: chore | priority: medium | effort: medium | addresses: residual invisible-prose hazard at other summary-before-question sites (goal-achievement) | desc: Audit all skill/procedure surfaces for plain-text-summary-before-AskUserQuestion sites and embed decision-critical content in the widget payload per the new visibility-rule convention
