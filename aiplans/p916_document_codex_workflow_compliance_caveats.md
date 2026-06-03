---
Task: t916_document_codex_workflow_compliance_caveats.md
Worktree: (current branch — no worktree)
Branch: (current)
Base branch: main
---

# Plan: Document Codex CLI workflow-compliance caveats

## Context

`website/content/docs/installation/known-issues.md` ("Known Agent Issues")
currently frames the only Codex CLI checkpoint problem as *tool availability* —
its `#### Interactive checkpoints` note claims that once `ait setup` enables
`default_mode_request_user_input`, interactive checkpoints "work throughout the
`aitask-*` workflow, including post-implementation finalization." Field
experience contradicts that optimism, but the real root cause turned out to be
**reasoning effort**, not a fundamental Codex compliance defect:

- At **low/medium effort**, Codex may silently skip required non-skippable
  workflow steps and treat the archive as the end of the workflow.
- Raising reasoning effort to **at least high** makes most of these issues go
  away. When the effort setting is changed, Codex also asks whether to override
  the current plan-mode effort setting — accept so plan-mode steps run at high
  effort too.
- A **residual** problem remains even at high effort: Codex may occasionally
  stop mid-workflow before a final step (e.g. the satisfaction rating). This is
  **not unique to Codex** — Claude can do the same — and the fix is general:
  nudge the agent to "continue the workflow" / "finish the workflow".

This task corrects the page to (a) keep the correct availability fact but drop
the over-claim, (b) document the reasoning-effort recommendation as the primary
mitigation, (c) distinguish legitimate profile-driven skips from compliance
failures, and (d) add the general nudge recommendation as parallel lines in the
Codex CLI **and** Claude Code sections (per user's chosen layout).

## Scope of change

Single file: `website/content/docs/installation/known-issues.md`. Edits in the
`## Claude Code` and `## Codex CLI` sections only.

### 1. `## Codex CLI` → soften `#### Interactive checkpoints` (keep availability fact)

The availability fact (`default_mode_request_user_input` makes
`request_user_input` available in Codex's default mode) is correct and stays.
Remove only the over-claim that checkpoints reliably "work throughout the
workflow, including post-implementation finalization" — that is what the new
subsection corrects. Reword to availability-only and point forward. Keep the
existing `> ait codeagent invoke` blockquote unchanged.

Current (line 23):
> Interactive workflow checkpoints — task confirmation, plan approval, and commit review — work throughout the `aitask-*` workflow, including post-implementation finalization (commit, archive).

Replace with, e.g.:
> This makes interactive workflow checkpoints — task confirmation, plan approval, and commit review — *available* in Codex's default mode. Availability is necessary but not sufficient for reliable compliance: see [Reasoning effort and workflow compliance](#reasoning-effort-and-workflow-compliance) below.

### 2. `## Codex CLI` → add `#### Reasoning effort and workflow compliance`

Inserted after `#### Interactive checkpoints`, before `#### Model
self-identification is unreliable`. Content (current-state only, no version
history):

- **Set reasoning effort to at least `high`** for reliable workflow compliance.
  At lower effort, Codex may silently skip required non-skippable workflow steps
  and may treat the archive as the end of the workflow. Raising effort to high
  resolves most of these. (The page intentionally does not enumerate which
  steps — the symptom is general workflow non-compliance, not a fixed list.)
- **Plan mode:** when you change the effort setting, Codex asks whether to also
  override the current plan-mode effort setting. Accept it so the planning
  phase runs at high effort too.
- **Distinguish legitimate profile-driven skips:** execution profiles such as
  `fast` deliberately pre-answer some prompts (task confirmation, email,
  worktree creation). Those skips are expected and correct — the caveat above is
  only about gates the profile does *not* cover.
- **Residual nudge:** even at high effort, Codex may occasionally stop
  mid-workflow before a final step (e.g. the satisfaction rating). This is not
  unique to Codex. If it happens, prompt it to *"continue the workflow"* /
  *"finish the workflow"* to complete the remaining non-skippable steps.

### 3. `## Claude Code` → add parallel nudge line to `#### Medium-effort models can miss workflow steps`

The existing note already covers the effort theme for Claude. Append a short
parallel line: if the agent stops mid-workflow before a final step (e.g. the
satisfaction rating), nudge it to *"continue the workflow"* / *"finish the
workflow"*. This keeps the general recommendation visible in both sections
without a new top-level note.

### 4. Coherence checks

- `## References` and the `commands/codeagent` relref already present remain
  valid — verify the new in-page anchor
  `#reasoning-effort-and-workflow-compliance` resolves (Hugo/Docsy
  auto-generates it from the `####` heading).

## Files to modify

- `website/content/docs/installation/known-issues.md` — the only file.

## Verification

- Re-read the edited `## Codex CLI` and `## Claude Code` sections: confirm
  (a) the availability fact is retained but the "throughout the workflow"
  over-claim is gone; (b) reasoning effort ≥ high is the primary recommendation,
  described generally (no enumeration of specific skipped steps); (c) the
  plan-mode effort-override prompt is documented; (d) profile-driven skips are
  explicitly distinguished; (e) the residual "nudge to continue/finish" appears
  in both the Codex and Claude Code sections; (f) no version-history prose.
- Optional local build to confirm anchors/links resolve:
  `cd website && hugo build --gc --minify` (or `./serve.sh` and visit the page).
  Markdown-only change — low risk of build breakage.

## Post-Implementation

Follow **Step 9 (Post-Implementation)** of the shared workflow: review/commit
(Step 8), then archive via `./.aitask-scripts/aitask_archive.sh 916` and push.

## Risk

### Code-health risk: low
- None identified. The change is confined to one Markdown documentation file in
  `website/content/docs/`; it touches no code, scripts, or load-bearing paths,
  and follows the existing page's heading/subsection conventions.

### Goal-achievement risk: low
- None identified. The corrected scope (effort-setting primary fix, residual
  general nudge, profile-driven-skip distinction) and the target file/sections
  are unambiguous; all acceptance criteria map directly to concrete edits above.
