---
Task: t803_gate_agent_specific_blocks_in_skills_via_jinja.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: t803 — Gate agent-specific blocks in skills via Jinja

## Context

When `aitask-wrap` is invoked under Codex CLI, Gemini CLI, or OpenCode, **Step 1b "Check for Recent Claude Plans"** (`.claude/skills/aitask-wrap/SKILL.md:83-119`) scans `ls -t ~/.claude/plans/*.md` — a directory that only Claude Code populates. The current `.agents/skills/aitask-wrap/SKILL.md` and `.opencode/skills/aitask-wrap/SKILL.md` are thin **delegation wrappers** that tell the agent to "follow the Claude SKILL.md," so the Claude-only step runs unconditionally on every agent.

The t777 templated stub-skill infrastructure (renderer + walker + per-profile siblings + 4-agent stubs) is now in place. The fix is to convert `aitask-wrap` to that pattern and wrap Step 1b in `{% if agent == "claude" %}`, so non-Claude renders simply do not contain the step. This is the first skill in the repository to use an `{% if agent %}` Jinja gate — Part B of the task explicitly catalogs other shared skills that contain runtime "If running in Claude Code" prose so they can follow once their host skills are templated.

The renderer already exposes `agent` to Jinja (`.aitask-scripts/lib/skill_template.py:105`: `env.render_str(..., agent=agent_name)`), so this is purely an authoring change plus a tests/goldens update.

## Scope summary

- **Part A** — Convert `.claude/skills/aitask-wrap/` to the templated stub-skill pattern (parallel to t777_6 / t777_8 / t777_10–15). 4 stubs + 1 `.j2` template + 6 goldens (3 profiles × claude+codex, since Claude render diverges from non-Claude due to the new `{% if agent %}` gate) + 1 regression test.
- **Part B** — Audit document at `aidocs/agent_runtime_guards_audit.md` enumerating remaining "If running in Claude Code" runtime guards across `.claude/skills/`, noting host-skill templating status, and flagging the cross-skill coordination required before they can move to Jinja gates.

`aitask-wrap` has **no profile-driven branching** today (Step 0–6 are identical across the 3 profiles); the rendered output therefore varies only on `agent`, not on `profile`. We still emit one rendered variant per profile (architectural uniformity — profile name is baked into the frontmatter `name:` field per the existing `aitask-fold-{{ profile.name }}` convention).

## Part A — Convert `aitask-wrap` to templated stub-skill pattern

### A1. Author `.claude/skills/aitask-wrap/SKILL.md.j2`

Source: copy the current `.claude/skills/aitask-wrap/SKILL.md` body verbatim, then apply:

1. **Frontmatter** — change `name:` to use the profile-suffix convention:
   ```yaml
   ---
   name: aitask-wrap-{{ profile.name }}
   description: Wrap uncommitted changes into an aitask with retroactive documentation and traceability.
   ---
   ```
   (Pattern from `.claude/skills/aitask-fold/SKILL.md.j2:1-4`.)

2. **Gate Step 1b** (currently lines 83-119) — wrap the **entire** `### Step 1b: Check for Recent Claude Plans` heading + body in:
   ```jinja
   {% if agent == "claude" %}
   ### Step 1b: Check for Recent Claude Plans
   ...current body...
   {% endif %}
   ```
   The "Integration with other steps" sub-block at lines 116-119 also stays inside the gate (it references `selected_plans` which only exist on the Claude path).

3. **Reference paths** — leave the `../task-workflow/...` relative references unchanged. They resolve correctly when read from `.claude/skills/aitask-wrap-<profile>-/SKILL.md` to `.claude/skills/task-workflow-<profile>-/<file>.md` — same parent dir, sibling per-profile directories. (Confirmed by reading existing rendered siblings of aitask-fold under the same scheme.) **Edge case to verify during implementation:** the renderer's ref-rewrite engine (`skill_template.py:148-215`) only auto-rewrites full-path refs (`.claude/skills/task-workflow/planning.md`) and skill-relative refs (`task-workflow/planning.md`). Plain `../task-workflow/foo.md` refs are not rewritten — they remain as-written and resolve relative to the rendered file's directory. Since both `aitask-wrap-<profile>-/` and `task-workflow-<profile>-/` are siblings under `.claude/skills/` (and the corresponding agent root for codex/gemini/opencode), `../task-workflow-<profile>-/foo.md` would be the literal correct path. **However**, the current SKILL.md uses `../task-workflow/foo.md` (no profile suffix). For the rendered variant to find the right procedure, we must either:
   - (a) Rewrite refs to full-path form (`.claude/skills/task-workflow/agent-attribution.md`) so the walker auto-rewrites them to `<root>/skills/task-workflow-<profile>-/agent-attribution.md`, OR
   - (b) Keep `../task-workflow/` and rely on the agent reading whatever is at that literal path — which is the **non-rendered** source procedure (containing `{% if profile.… %}` markers etc.).
   
   Option (a) is correct and matches what other templated skills do (`.claude/skills/aitask-fold/SKILL.md.j2` references `.claude/skills/task-workflow/related-task-discovery.md` in full-path form on line 42). **All `../task-workflow/` references in the current SKILL.md must be rewritten to full-path form during the `.j2` authoring step**:
   - `../task-workflow/task-creation-batch.md` (Step 4a) → `.claude/skills/task-workflow/task-creation-batch.md`
   - `../task-workflow/agent-attribution.md` (Step 4a) → `.claude/skills/task-workflow/agent-attribution.md`
   - `../task-workflow/code-agent-commit-attribution.md` (Step 4c) → `.claude/skills/task-workflow/code-agent-commit-attribution.md`
   - `../task-workflow/issue-update.md` (Step 4d) → `.claude/skills/task-workflow/issue-update.md`
   - `.claude/skills/task-workflow/satisfaction-feedback.md` (Step 6) — already full-path, fine as-is

4. **No other changes** — `aitask-wrap` has no profile-driven conditionals to introduce. Profile is referenced only in the frontmatter `name:` field.

### A2. Replace the 4 stubs

Use the canonical bodies from `aidocs/stub-skill-pattern.md §3a/§3c/§3d` (already adopted by `.claude/skills/aitask-fold/SKILL.md`, `.agents/skills/aitask-fold/SKILL.md`, `.gemini/commands/aitask-fold.toml`, `.opencode/commands/aitask-fold.md`):

| Surface | Path | Resolver-key arg | `--agent` literal | Read-target root |
|---------|------|------------------|--------------------|-------------------|
| Claude  | `.claude/skills/aitask-wrap/SKILL.md` (overwrite existing) | `wrap` | `claude` | `.claude/skills/aitask-wrap-<profile>-/` |
| Codex   | `.agents/skills/aitask-wrap/SKILL.md` (overwrite existing delegate) | `wrap` | `codex` | `.agents/skills/aitask-wrap-<profile>-/` |
| Gemini  | `.gemini/commands/aitask-wrap.toml` (NEW file) | `wrap` | `gemini` | `.gemini/skills/aitask-wrap-<profile>-/` |
| OpenCode | `.opencode/commands/aitask-wrap.md` (NEW file) | `wrap` | `opencode` | `.opencode/skills/aitask-wrap-<profile>-/` |

Existing `.opencode/skills/aitask-wrap/SKILL.md` (current delegation wrapper) — delete after confirming nothing references it directly. The OpenCode entry point under the new pattern is `.opencode/commands/aitask-wrap.md`, not `.opencode/skills/aitask-wrap/SKILL.md`.

Resolver key `wrap` follows the convention used by `fold`, `pick`, `explore`, etc. (`aitask-` prefix stripped). Verified by reading `aitask_skill_resolve_profile.sh:1-50` — the script accepts any short name and looks it up under `default_profiles.<skill>` in userconfig/project_config.

### A3. Goldens

Goldens directory: `tests/golden/skills/aitask-wrap/` (NEW).

Dimensions — because Step 1b is `{% if agent == "claude" %}`-gated, agent renders are NOT byte-identical. We need:

- `SKILL-default-claude.md`
- `SKILL-fast-claude.md`
- `SKILL-remote-claude.md`
- `SKILL-default-codex.md` (canonical non-Claude — codex/gemini/opencode all byte-identical to each other after the gate, since no other agent-conditional content exists)
- `SKILL-fast-codex.md`
- `SKILL-remote-codex.md`

6 goldens total. Per `aidocs/stub-skill-pattern.md:248-257`: "the pruned goldens are re-added surgically for that skill" — this is the case.

**Regeneration command** (per `aidocs/skill_authoring_conventions.md` regenerate rule):
```bash
PYTHON="$(./.aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  for agent in claude codex; do
    $PYTHON .aitask-scripts/lib/skill_template.py \
      .claude/skills/aitask-wrap/SKILL.md.j2 \
      aitasks/metadata/profiles/$profile.yaml \
      $agent \
      > tests/golden/skills/aitask-wrap/SKILL-${profile}-${agent}.md
  done
done
```
(Same shape as the inferred regen pattern from `test_skill_render_aitask_fold.sh:86`.)

### A4. Regression test

Create `tests/test_skill_render_aitask_wrap.sh` modeled directly on `tests/test_skill_render_aitask_fold.sh` (197 lines, copy-and-adapt). Key adaptations:

- `PROFILES=(default fast remote)`, `AGENTS=(claude codex gemini opencode)` — unchanged
- **Test 1** — diff per (profile, claude) AND per (profile, codex) against the 6 goldens. (Drop the claude-only canonical assumption that aitask-fold uses.)
- **Test 1b (renamed/repurposed)** — assert agent **divergence** for the gated step:
  - Claude render of each profile MUST contain `Step 1b: Check for Recent Claude Plans` AND `~/.claude/plans`.
  - codex/gemini/opencode renders of each profile MUST NOT contain those strings.
  - codex/gemini/opencode renders of the same profile MUST be byte-identical to each other (post-gate, no further agent-conditional content).
- **Test 2** — drop (no profile-conditional `auto_continue` or similar logic in aitask-wrap).
- **Test 3** — keep (no Jinja markers leak across all 4 agents).
- **Test 3b** — keep (rendered body must not contain forbidden runtime profile-resolution tokens).
- **Test 4** — keep (per-agent walk-write reference rewrites under each agent root — adapted: `aitask-wrap` doesn't reference task-workflow heavily, so adapt the assertions to whichever full-path refs survive — see A1 step 3).
- **Test 5** — keep verbatim (4 stub markers; resolver key `wrap`; per-agent stub paths and literals).

### A5. Existing-stub cleanup

- `.opencode/skills/aitask-wrap/` — delete the directory (its `SKILL.md` was a delegation wrapper; under the new pattern the entry point lives at `.opencode/commands/aitask-wrap.md`). Per `aidocs/stub-skill-pattern.md §3g`: OpenCode auto-discovers command wrappers, not skills, so this directory becomes vestigial.
- `.agents/skills/aitask-wrap/SKILL.md` — overwrite with the canonical Codex stub (was a delegation wrapper, now the dispatcher stub).
- `.claude/skills/aitask-wrap/SKILL.md` — overwrite with the canonical Claude stub.

### A6. Verification

```bash
./.aitask-scripts/aitask_skill_verify.sh
bash tests/test_skill_render_aitask_wrap.sh
```

Manual spot-check: render and diff to confirm the gate works:
```bash
./.aitask-scripts/aitask_skill_render.sh aitask-wrap --profile default --agent claude --force
./.aitask-scripts/aitask_skill_render.sh aitask-wrap --profile default --agent codex --force
diff .claude/skills/aitask-wrap-default-/SKILL.md .agents/skills/aitask-wrap-default-/SKILL.md
# expect: lines containing "Step 1b" / "~/.claude/plans" present only in the Claude file
```

## Part B — Audit document for remaining runtime guards

Create `aidocs/agent_runtime_guards_audit.md` cataloging "If running in Claude Code" / `~/.claude/plans` references in shared skill content that should eventually move to `{% if agent == "claude" %}` Jinja gates.

### Confirmed inventory (from `grep -rn "If running in Claude Code\|~/.claude/plans" .claude/skills/`)

| File | Line | Guard wraps | Host-skill templated? | Cross-skill impact |
|------|------|-------------|------------------------|---------------------|
| `.claude/skills/task-workflow/SKILL.md` | ~310 | "Verify the plan file exists externally (Claude Code only)" — gates the Plan Externalization safety fallback in Step 8 (commit branch) | Task-workflow has no entry-point `.j2`, but its procedures are evaluated by Jinja when rendered into other skills' closures. | **High** — task-workflow is in the closure of every skill that hands off to it (aitask-pick, aitask-explore, aitask-fold, aitask-review, aitask-qa, aitask-pr-import, aitask-revert, aitask-pickrem, aitask-pickweb). Moving this to a Jinja gate breaks Test 1b agent-invariance in EVERY one of those skills until they each grow per-agent goldens. |
| `.claude/skills/task-workflow/planning.md` | ~292 | "If running in Claude Code, execute the Plan Externalization Procedure ..." — gates the Step 6 plan-externalization step | Same as above. | **High** — same cascade. |
| `.claude/skills/task-workflow/plan-externalization.md` | entire file | Whole procedure is Claude-Code-only (`~/.claude/plans/<random>.md` semantics). | Same as above. | The file body itself does not need gating — only its **callsites** in SKILL.md / planning.md do. Non-Claude agents that read the gated callsite simply never reach this file. |

### Recommended follow-up tasks (suggest to user; do NOT create automatically)

- **t<next>** — "Convert task-workflow runtime guards to Jinja gates." Bundled change: gate the two callsites listed above + relax `Test 1b` (agent invariance) → `Test 1b` (agent-equivalence except for the gated block) across all calling skills' regression tests + regenerate per-agent goldens for each of the 9 affected skills. Justify as a single bundled PR per the `feedback_stage_under_parallel_name` and "small focused PRs" guidance — the change is one coherent semantic step.

### Out of scope for t803

Per the task description's Out-of-scope: removing `~/.claude/plans/` scanning itself or extracting it into a script encapsulation is deferred. The audit document records this as a possible future follow-up but takes no action.

## File-by-file change list

### New files

- `.claude/skills/aitask-wrap/SKILL.md.j2` (authoring template)
- `.gemini/commands/aitask-wrap.toml` (Gemini stub)
- `.opencode/commands/aitask-wrap.md` (OpenCode stub)
- `tests/golden/skills/aitask-wrap/SKILL-default-claude.md`
- `tests/golden/skills/aitask-wrap/SKILL-fast-claude.md`
- `tests/golden/skills/aitask-wrap/SKILL-remote-claude.md`
- `tests/golden/skills/aitask-wrap/SKILL-default-codex.md`
- `tests/golden/skills/aitask-wrap/SKILL-fast-codex.md`
- `tests/golden/skills/aitask-wrap/SKILL-remote-codex.md`
- `tests/test_skill_render_aitask_wrap.sh`
- `aidocs/agent_runtime_guards_audit.md`

### Modified files

- `.claude/skills/aitask-wrap/SKILL.md` (was unified body, becomes Claude stub)
- `.agents/skills/aitask-wrap/SKILL.md` (was delegation wrapper, becomes Codex stub)

### Deleted files / directories

- `.opencode/skills/aitask-wrap/SKILL.md` (delegation wrapper superseded by `.opencode/commands/aitask-wrap.md`)
- `.opencode/skills/aitask-wrap/` (now-empty directory)

## Verification

1. **Test suite:**
   ```bash
   bash tests/test_skill_render_aitask_wrap.sh
   ./.aitask-scripts/aitask_skill_verify.sh
   ```
   Both must pass without any FAIL lines.

2. **Existing tests must remain passing** (since `aitask-wrap` is added as a new templated skill, no other test should regress):
   ```bash
   bash tests/test_skill_render_aitask_fold.sh
   bash tests/test_skill_render_aitask_pick.sh
   bash tests/test_skill_render_task_workflow.sh
   bash tests/test_skill_render_uniform.sh
   bash tests/test_skill_rerender.sh
   ```

3. **Per-agent semantic spot-check:**
   ```bash
   ./.aitask-scripts/aitask_skill_render.sh aitask-wrap --profile default --agent claude --force
   ./.aitask-scripts/aitask_skill_render.sh aitask-wrap --profile default --agent codex --force
   grep -c "Step 1b: Check for Recent Claude Plans" .claude/skills/aitask-wrap-default-/SKILL.md  # expect 1
   grep -c "Step 1b: Check for Recent Claude Plans" .agents/skills/aitask-wrap-default-/SKILL.md  # expect 0
   grep -c "~/.claude/plans"                          .claude/skills/aitask-wrap-default-/SKILL.md  # expect ≥1
   grep -c "~/.claude/plans"                          .agents/skills/aitask-wrap-default-/SKILL.md  # expect 0
   ```

4. **Stub spot-check:**
   - All 4 stubs contain `aitask_skill_resolve_profile.sh wrap` (short name, not `aitask-wrap`)
   - Each stub's `--agent <literal>` matches its surface (`claude` / `codex` / `gemini` / `opencode`)
   - Read-target line in each stub matches its agent root (`.claude/skills/...`, `.agents/skills/...`, `.gemini/skills/...`, `.opencode/skills/...`)

5. **Audit document review** — `aidocs/agent_runtime_guards_audit.md` enumerates the 3 occurrences identified, names the cross-skill cascade impact, and proposes a single bundled follow-up task.

## Reference to Step 9 (Post-Implementation)

After implementation and successful verification, follow task-workflow Step 9: commit code separately from plan (per CLAUDE.md "Git Operations on Task/Plan Files"), push, and run `./.aitask-scripts/aitask_archive.sh 803`.

## Risks and notes

- **The renderer evaluates Jinja on procedure files in the closure** (`skill_template.py:305` renders every file through `render_str`). The current `task-workflow/planning.md` and `task-workflow/SKILL.md` already contain `{% if profile.… %}` constructs that evaluate at render time — so introducing `{% if agent == "claude" %}` *in those files* would work technically, but cascades into Test 1b breakage across 9 skills. Hence Part B records this rather than acting on it.
- **Stub `description:` line** for the new templated `aitask-wrap` — per the rule "**Don't add backwards-compatibility hacks**" (CLAUDE.md), the stub description should match the `.j2` description verbatim. Per existing precedent (`.claude/skills/aitask-fold/SKILL.md:3` vs `.claude/skills/aitask-fold/SKILL.md.j2:3`), both are the same human-readable string.
- **Gemini stub format** — Gemini stubs are `.toml` files with a `prompt = """..."""` block (verified from `.gemini/commands/aitask-fold.toml`). Copy that exact shape, swap `fold` → `wrap` and target paths accordingly.
- **OpenCode command vs skill directory** — under the templated pattern, OpenCode reads command wrappers from `.opencode/commands/` and the rendered variant from `.opencode/skills/<skill>-<profile>-/`. The current `.opencode/skills/aitask-wrap/SKILL.md` delegation wrapper is replaced by `.opencode/commands/aitask-wrap.md` — confirm via existing patterns (e.g., `.opencode/commands/aitask-fold.md` exists, but `.opencode/skills/aitask-fold/` doesn't) before deleting `.opencode/skills/aitask-wrap/`.
