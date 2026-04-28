---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Implementing
labels: [installation, install_scripts, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-28 11:05
updated_at: 2026-04-28 11:45
boardcol: now
boardidx: 30
---

Spawned alongside t691 (audit and port aitask wrappers across code agents). Analyze whether framework-development-only skills and their helper scripts should be filtered out of the distribution tarball produced by `install.sh`.

## Motivation

`aitask-add-model` and the new `aitask-audit-wrappers` (introduced in t691) are useful only to people developing the aitasks framework itself, not to users who adopt it via the install tarball. Today every `.claude/skills/aitask-*` ships with the framework regardless of whether end users will ever invoke it. As more dev-only skills and helpers accumulate, the distribution becomes noisier and slower to install, and the surface area for permission prompts grows.

This task is **analysis-only**. It produces a recommendation and (if a clear winner emerges) follow-up implementation task(s). It does NOT itself modify `install.sh`.

## Scope of the analysis

1. **Inventory dev-only artifacts.** List candidate dev-only artifacts under each of:
   - `.claude/skills/`
   - `.aitask-scripts/` (helper scripts called only by dev-only skills)
   - `.agents/skills/`
   - `.opencode/skills/`
   - `.opencode/commands/`
   - `.gemini/commands/`
   - Seed/whitelist entries in `seed/` that exist solely for dev-only artifacts
   
   Confirmed dev-only as of 2026-04-28: `aitask-add-model`, `aitask-audit-wrappers`. Investigate whether others (`aitask-changelog`?, `aitask-refresh-code-models`?) should also be classified as dev-only.

2. **Define the dev-only criterion.** Pick a single mechanism and justify it:
   - Explicit metadata flag in SKILL.md frontmatter (e.g. `audience: developers` or `distribution: dev-only`).
   - Naming convention (e.g. `aitask-dev-*` prefix — but renaming existing skills is a breaking change).
   - Exclusion list in `install.sh` (simple, auditable, but easy to drift).
   - Separate `dev/` directory in source-of-truth — e.g. `.claude/skills/dev/aitask-add-model/`.

3. **Survey current packaging.** Read `install.sh`, especially the file-copy phases and the `rm -rf seed/` at the end. Note what t624/t628 already established about which seed files reach the user's install. The audit should also cover the gemini policy / opencode config / claude settings whitelists — entries for dev-only helpers should not be carried over to a user install.

4. **Propose a filtering approach.** With trade-offs for each option:
   - Silent omission (clean user install, but advanced users lose access).
   - Opt-in flag for power users (`install.sh --include-dev-tools`).
   - Separate dev-tarball or branch (more maintenance burden).
   - Hybrid (omit by default, expose `ait setup --dev` to add them post-install).

5. **Identify what does NOT belong in scope.**
   - Anything that needs the audit-wrappers skill to function (it is itself dev-only).
   - Test files in `tests/` — not part of the user install, already filtered.

## Deliverable

A written analysis (markdown) saved as the `Final Implementation Notes` of this task's plan, with:
- Inventory table of dev-only artifacts (per the criteria chosen).
- Recommended filtering mechanism with trade-off summary.
- List of follow-up implementation tasks needed (separate from this task), each scoped tightly enough to slot into the next round of /aitask-pick.

If during the analysis a small implementation lands inevitably (e.g. adding a single `audience:` field), that is acceptable; otherwise this task stays analysis-only and the follow-up tasks are created via `aitask_create.sh --batch --commit`.

## References

- `install.sh` — current distribution pipeline.
- `.aitask-scripts/aitask_setup.sh` — the post-install setup phase.
- t624 archived plan — fresh-install gap closure context.
- t628 archived plan — install_seed_project_config bug recap.
- t691 (parent/sibling) — introduces `aitask-audit-wrappers`, the second confirmed dev-only skill.
- CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" — defines source of truth + per-agent ports.
