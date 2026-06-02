---
Task: t909_task_workflow_risk_eval_on_verify_path.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# t909 — Risk Evaluation reliably runs on the plan verify path

## Context

**Why:** On the **verify path** of the task-workflow skill's Step 6 planning, the
end-of-planning **Risk Evaluation Procedure** (`risk-evaluation.md`) and the
**Risk-Mitigation design** step (`risk-mitigation-followup.md` Part 1) are
silently skipped. The two steps live at the *bottom* of `planning.md` §6.1 and
read as part of the **create-new** narrative. The verify-path entry note near the
*top* of §6.1 is self-contained and ends with "…confirm it is still sound **and
exit plan mode**" — so a reader who arrives via the verify path (child task with
`plan_preference_child: verify`, `DECISION:VERIFY`, `ASK_STALE → Verify now`, or
the interactive "Verify plan" option) reads the plan, re-checks it, and exits
plan mode **before ever reaching** the risk steps.

**Consequence:** If the existing plan has no `## Risk` section, the verify path
exits without authoring one. Step 7's `--risk-code-health` / `--risk-goal-achievement`
frontmatter write and Step 8d's "after" mitigation creation then silently no-op
(they parse a `## Risk` section that was never written). Observed live during the
`/aitask-pick 756_4` session (2026-06-02) — caught only because the user asked.

**Outcome:** Make the end-of-planning Risk Evaluation + Risk-Mitigation design a
clearly **shared, NON-SKIPPABLE terminal step** reached by *every* path that calls
`ExitPlanMode` (create-new AND verify AND ASK_STALE→verify), plus a deterministic
guard that catches a skipped section before the Checkpoint. This follows the
`feedback_prefer_source_enforcement_over_memory` principle — enforce in source
with explicit markers, not reader inference.

## Source-of-truth & gating facts (verified)

- Source of truth: closure `.md` `/.claude/skills/task-workflow/planning.md`
  (Jinja-templated; rendered into `task-workflow-<profile>-/planning.md`, which
  are gitignored `*-/` dirs re-rendered on demand — **not** hand-edited).
- The risk steps are gated by `{%- if profile.risk_evaluation is defined and
  profile.risk_evaluation %}`. **Only `aitasks/metadata/profiles/fast.yaml` sets
  `risk_evaluation: true`** among committed profiles. `default`/`remote` leave the
  key absent → risk steps render as nothing there.
- The "Create a detailed… plan" bullet at the create-new tail is an `{% include
  "_planning_plan_contract.md" %}` from `.aitask-scripts/skill_templates/`.
- Goldens: `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md`.
  Only **`planning-fast.md`** carries the risk steps today; the others must stay
  byte-identical after this change.
- Test 5 in `tests/test_skill_render_task_workflow.sh` asserts the literal strings
  `Risk evaluation (end of planning)` and `Risk-mitigation design (end of
  planning)` render under a synthetic `risk_evaluation: true` profile and are
  **absent** under `default`. Both literal headings are preserved by this change.

## Approach

All three edits target `.claude/skills/task-workflow/planning.md` and are wrapped
so they render **only** when `profile.risk_evaluation` is truthy. This keeps the
blast radius to the `fast` golden alone — `default`/`remote` renders are unchanged.

### Edit A — Reroute the verify-path entry note (§6.1, ~line 163)

Today the note terminates the verify path at `ExitPlanMode`. Change its tail to a
profile-gated branch so, when risk evaluation is enabled, it routes into the shared
terminal step instead of exiting; when disabled, behaviour is byte-identical to
today.

Current tail: `…Update the plan if needed, or confirm it is still sound and exit plan mode.`

New (replace `and exit plan mode.` only):
```
…Update the plan if needed, or confirm it is still sound.{% if profile.risk_evaluation is defined and profile.risk_evaluation %} Then — **do not `ExitPlanMode` yet** — run the shared **End-of-planning terminal step** at the bottom of this §6.1 (Risk Evaluation + Risk-Mitigation design). It is **NON-SKIPPABLE on the verify path exactly as on the create-new path**: even when the existing plan already has a `## Risk` section, re-run the Risk Evaluation Procedure to re-check it against the (possibly changed) plan and update it in place. Only after it completes, `ExitPlanMode`.{% else %} and exit plan mode.{% endif %}
```
→ `default`/`remote` render `…confirm it is still sound and exit plan mode.` —
identical to today.

### Edit B — Mark the risk steps as the shared NON-SKIPPABLE terminal step (§6.1 tail, ~lines 305–311)

Wrap the two existing gated bullets with an explicit heading + framing paragraph
(inside the same `{% if %}`), so the cross-reference from Edit A resolves to a
visible anchor and the steps no longer read as create-new-only. The two bold
labels `Risk evaluation (end of planning):` / `Risk-mitigation design (end of
planning):` are kept verbatim (Test 5). Body text gains "(or re-verified)" /
"appends (or updates)" wording so it reads correctly on the verify path.

Inserted just after the `{%- if … risk_evaluation %}` opens, before the two bullets:
```
#### End-of-planning terminal step (NON-SKIPPABLE — runs on EVERY plan path)

This is the shared terminus of **all** planning paths that reach `ExitPlanMode` —
create-new, verify, and `ASK_STALE → Verify now`. It is **not** specific to the
create-new narrative above. Whichever path you arrived by (including the verify
path, where you read and re-checked an existing plan), run **both** sub-steps
below **before** `ExitPlanMode`. An existing `## Risk` section does not exempt the
verify path — re-run the evaluation and update the section in place.
```
The `- Use `ExitPlanMode`…` line stays **outside** the gate (always rendered).

### Edit C — Risk-section guard before the Checkpoint ("Save Plan to External File" tail)

Add a gated, deterministic assertion that the externalized plan now contains a
`## Risk` section, exempting the cross-repo-parent case. Catches a skipped
terminal step before Step 7/8d silently no-op.

```
{%- if profile.risk_evaluation is defined and profile.risk_evaluation %}

**Risk-section guard (NON-SKIPPABLE — verifies the §6.1 terminal step ran):** If
`cross_repo_planned` is true, skip this guard (a cross-repo parent has no
single-task `## Risk` section). Otherwise, before proceeding to the Checkpoint,
confirm the externalized plan file contains a `## Risk` section:

```bash
grep -q '^## Risk' aiplans/<plan_file> && echo "RISK_OK" || echo "RISK_MISSING"
```

- `RISK_OK` → the end-of-planning Risk Evaluation ran; proceed to the Checkpoint.
- `RISK_MISSING` → the §6.1 End-of-planning terminal step was skipped on this path.
  Do **not** proceed. Re-enter plan mode (`EnterPlanMode`), run the **Risk
  Evaluation Procedure** and the **Risk-Mitigation design** step now, `ExitPlanMode`,
  and re-run **Save Plan to External File** so the `## Risk` section is persisted.
{%- endif %}
```
Placed immediately before the `## Checkpoint (after plan is saved)` header.

## Files modified

- `.claude/skills/task-workflow/planning.md` — Edits A, B, C (all gated by
  `profile.risk_evaluation`).
- `tests/golden/procs/task-workflow/planning-fast.md` — regenerated (only golden
  that changes). `planning-default.md` / `planning-remote.md` regenerate to
  byte-identical content (will verify with `git diff`).

## Regeneration & verification

1. Regenerate the three procedure goldens (canonical loop from
   `aidocs/framework/skill_authoring_conventions.md`):
   ```bash
   PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   for p in default fast remote; do
     "$PYTHON" .aitask-scripts/lib/skill_template.py \
       .claude/skills/task-workflow/planning.md \
       aitasks/metadata/profiles/$p.yaml claude \
       > tests/golden/procs/task-workflow/planning-$p.md
   done
   ```
2. `git diff --stat` the goldens → confirm **only** `planning-fast.md` changed,
   and its diff is exactly Edits A/B/C (review, don't rubber-stamp).
3. `bash tests/test_skill_render_task_workflow.sh` → all green (Test 1 goldens,
   Test 2b agent byte-identity, Test 5 risk-gate strings).
4. `./.aitask-scripts/aitask_skill_verify.sh` → passes (stub markers, render
   cleanliness, prerender freshness — planning headless prerender is pickrem-only,
   unaffected).
5. Trace each planning path (create-new, verify, ASK_STALE→verify) in the rendered
   `planning-fast.md` and confirm every one reaches the terminal step before the
   Checkpoint; confirm a verify-path render with no `## Risk` section is caught by
   the guard.

## Cross-agent follow-up (per CLAUDE.md)

Fix Claude Code first (this task). At Step 8 / follow-up, suggest sibling aitasks to
port the same restructure to the Codex CLI (`.agents/skills/task-workflow/`) and
OpenCode (`.opencode/skills/`) task-workflow trees — only if those trees carry the
same risk-evaluation gating.

## Step 9 (Post-Implementation)

Single-task parent on the current branch (no worktree). After approval + commit,
archive via `./.aitask-scripts/aitask_archive.sh 909`, then `./ait git push`.

## Risk

### Code-health risk: low
- Edits are documentation/procedure prose fully gated behind an existing
  `profile.risk_evaluation` conditional; `default`/`remote` renders are
  byte-unchanged and only the `fast` golden moves. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The fix relies on the reader following the new cross-reference; the Edit C
  `grep` guard is the deterministic backstop that converts a silent skip into a
  loud `RISK_MISSING` before Step 7/8d run. · severity: low · → mitigation: TBD
