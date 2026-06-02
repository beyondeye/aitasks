# Agent-Specific Runtime Guards — Audit

This document catalogs remaining **runtime** "If running in Claude Code" / `~/.claude/plans` references in shared skill content that should eventually be replaced with Jinja `{% if agent == "claude" %}` gates so non-Claude renders simply omit the Claude-only block.

Scope: produced as the Part B deliverable for `t803_gate_agent_specific_blocks_in_skills_via_jinja`. Part A converted `aitask-wrap` to the templated stub-skill pattern and gated Step 1b — the first skill in the repo to use an `{% if agent %}` gate. This audit catalogs the remaining work and explains why the cleanup cannot land in t803.

## Methodology

Search command:

```bash
grep -rn "If running in Claude Code\|~/.claude/plans" .claude/skills/ \
  | grep -v "^.claude/skills/.*-/"     # exclude generated per-profile siblings
```

Only **source** files are considered (rendered `*-default-/`, `*-fast-/`, `*-remote-/` siblings are derived output and were excluded from the search above).

## Inventory

### A. Runtime guards (prose-level "If running in Claude Code")

| File | Line | Guard wraps |
|------|------|-------------|
| `.claude/skills/task-workflow/SKILL.md` | 332 | "**Verify the plan file exists externally (Claude Code only):** If running in Claude Code, execute the **Plan Externalization Procedure** ... Other code agents write plans directly to `aiplans/` and skip this check." — gates the Step 8 safety-fallback callsite |
| `.claude/skills/task-workflow/planning.md` | 289 | "**If running in Claude Code,** execute the **Plan Externalization Procedure** (see `plan-externalization.md`) immediately after `ExitPlanMode` ... Other code agents write plans directly to `aiplans/` and skip this step." — gates the proactive Step 6 externalize callsite |

Both files are part of the `task-workflow` skill closure. They are pulled into the render closure of every skill that hands off to `task-workflow/SKILL.md` from Step 3 (Task Status Checks) onward — i.e. `aitask-pick`, `aitask-explore`, `aitask-fold`, `aitask-review`, `aitask-qa`, `aitask-pr-import`, `aitask-revert`, `aitask-pickrem`, `aitask-pickweb`. Each of those skills carries a `test_skill_render_<skill>.sh` regression test, and most contain a **Test 1b agent-invariance assertion** (codex/gemini/opencode renders byte-identical to claude) that would fail the moment a Jinja `{% if agent %}` gate is introduced into a procedure file shared across these closures.

### B. Claude-only procedure files (body, not gating)

| File | Status |
|------|--------|
| `.claude/skills/task-workflow/plan-externalization.md` | Whole procedure is Claude-specific (`~/.claude/plans/<random>.md` semantics). The file itself is referenced **only** from the gated callsites in A above, so once those are gated correctly the file body needs no gating — non-Claude agents simply never read it. |

### C. Already-gated (no action)

| File | Line | Status |
|------|------|--------|
| `.claude/skills/aitask-wrap/SKILL.md.j2` | 84-122 | Step 1b is wrapped in `{% if agent == "claude" %}` (Part A of t803). The `~/.claude/plans` mention at line 89 is inside the gate; non-claude renders do not contain it. |

## Why not gate the task-workflow guards in t803

The renderer (`.aitask-scripts/lib/skill_template.py:305`) evaluates Jinja on every file in the render closure, including the plain `.md` procedure files under `.claude/skills/task-workflow/`. Adding `{% if agent == "claude" %}` to `planning.md:289` or `SKILL.md:332` would technically work — but the resulting agent-divergent output cascades into every skill whose closure transitively includes `task-workflow`:

- `aitask-pick` → `task-workflow/SKILL.md` (Step 3 handoff)
- `aitask-explore` → same handoff
- `aitask-fold` → same
- `aitask-review` → same
- `aitask-qa` → same
- `aitask-pr-import` → same
- `aitask-revert` → same
- `aitask-pickrem` → same
- `aitask-pickweb` → same

Each of those skills' `tests/test_skill_render_aitask_<name>.sh` runs **Test 1b** (agent-dimension invariance — see e.g. `tests/test_skill_render_aitask_fold.sh:91-105`). That test asserts the basic stdout render is byte-identical across all four agents. Introducing a real `{% if agent %}` gate inside `task-workflow/{SKILL.md,planning.md}` immediately breaks that assertion for all 9 callers at once.

The disciplined cleanup path — explicitly anticipated by `aidocs/framework/stub-skill-pattern.md:248-257` ("the pruned goldens are re-added surgically for that skill") — is to bundle the change into a single follow-up task that:

1. Gates the two callsites in `task-workflow/{SKILL.md, planning.md}` with `{% if agent == "claude" %}`.
2. For each of the 9 caller skills above:
   - Relaxes / re-purposes Test 1b from "agent invariance" to "agent-equivalence except for the Plan Externalization callsite" (or replaces invariance with per-agent goldens).
   - Adds 3 additional per-agent goldens (codex canonical for the 3 profiles) under `tests/golden/skills/<skill>/`, mirroring the precedent set by `aitask-wrap` (Part A).
3. Regenerates the existing claude goldens for each caller (the gated block now diverges).
4. Refreshes the `task-workflow-<profile>-/` rendered siblings (auto-handled by the renderer on next walk).

This is one coherent semantic step but ~10 files of test/golden churn — clearly a separate, focused PR rather than a side-effect of `aitask-wrap` conversion. `aitask-wrap` does not transitively include `task-workflow` in its closure (it is self-contained — see `.claude/skills/aitask-wrap/SKILL.md.j2`'s "Notes" section: "This skill is self-contained — no handoff to task-workflow since the work is already complete"), so Part A's gate stays isolated and does not force the cascade.

## Recommended follow-up task

> **Convert task-workflow runtime "If running in Claude Code" guards to Jinja gates.** Wrap the Plan Externalization callsites in `task-workflow/SKILL.md` (line ~332) and `task-workflow/planning.md` (line ~289) with `{% if agent == "claude" %}` / `{% endif %}`. Update the 9 caller skills' regression tests (`aitask-pick`, `aitask-explore`, `aitask-fold`, `aitask-review`, `aitask-qa`, `aitask-pr-import`, `aitask-revert`, `aitask-pickrem`, `aitask-pickweb`) to add per-agent codex goldens and re-purpose the Test 1b agent-invariance assertion accordingly. Regenerate all affected claude goldens in the same commit. Reference `aidocs/framework/stub-skill-pattern.md:248-257` for the precedent. Reference `aitask-wrap` (t803 Part A) for the per-agent golden + gate-divergence test pattern.

This audit deliberately stops short of creating the follow-up aitask automatically (per the task description "follow-up sibling tasks" — singular suggested follow-up, not auto-created in t803).

## Out of scope

Per the t803 task description:

- Removing the `~/.claude/plans/` scanning logic itself — the directory is useful for Claude Code users; the fix is gating, not removal.
- Refactoring `~/.claude/plans/` scanning into a separate script encapsulation — `.aitask-scripts/aitask_plan_externalize.sh` already encapsulates the externalize side. The aitask-wrap Step 1b scan (the `ls -t ~/.claude/plans/*.md` line) is a candidate for similar encapsulation if/when extended, but is out of scope here.
