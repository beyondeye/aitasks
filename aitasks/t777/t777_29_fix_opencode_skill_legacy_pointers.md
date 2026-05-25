---
priority: medium
effort: medium
depends: [t777_28]
issue_type: refactor
status: Implementing
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-25 10:29
updated_at: 2026-05-25 10:55
---

## Context

Discovered during t777_15 (pickweb conversion) verification. Every previously-templated skill has a vestigial pre-templating-era "Source of Truth" wrapper at `.opencode/skills/<skill>/SKILL.md` that still points to `.claude/skills/<skill>/SKILL.md`. That target has since become the §3b Claude stub (not a workflow), so following the pointer routes OpenCode through Claude's rendered tree (wrong agent root) instead of OpenCode's.

The §3d stub at `.opencode/commands/<skill>.md` is correct and is what slash invocations fire. The leftover only matters for OpenCode's description-based skill auto-discovery (declared in `.opencode/instructions.md`), but it ships broken pointers and re-runs of `/aitask-audit-wrappers` regenerate them.

Affected skills (all with `.opencode/skills/<skill>/SKILL.md` still containing the legacy "Source of Truth" phrase):
- aitask-pick
- aitask-pickrem
- aitask-explore
- aitask-review
- aitask-fold
- aitask-qa
- aitask-pr-import
- aitask-revert

pickweb (t777_15) handles its own case correctly: replaces the file with a §3d-style stub mirroring `.opencode/commands/aitask-pickweb.md`. This task generalizes the fix to the 7 prior leftovers and patches the wrapper auditor.

## Key Files to Modify

- `.opencode/skills/aitask-pick/SKILL.md` — rewrite to §3d-style stub matching `.opencode/commands/aitask-pick.md`
- `.opencode/skills/aitask-pickrem/SKILL.md` — same
- `.opencode/skills/aitask-explore/SKILL.md` — same
- `.opencode/skills/aitask-review/SKILL.md` — same
- `.opencode/skills/aitask-fold/SKILL.md` — same
- `.opencode/skills/aitask-qa/SKILL.md` — same
- `.opencode/skills/aitask-pr-import/SKILL.md` — same
- `.opencode/skills/aitask-revert/SKILL.md` — same
- `.aitask-scripts/aitask_audit_wrappers.sh` — update `render_opencode_skill` (around line 180) to detect templated skills (presence of `SKILL.md.j2` in `.claude/skills/<skill>/`) and emit a §3d-style stub for those skills instead of the legacy pointer
- `.aitask-scripts/aitask_skill_verify.sh` — drop the per-skill cases in `_resolver_key_for` for templated skills and replace with prerender-marker-based detection (current TODO at line 78); track each new templated skill via a marker file or template registry rather than hardcoded switch arms

## Reference Files for Patterns

- `.opencode/commands/aitask-pickrem.md` — canonical §3d stub the new skill-file should mirror
- `.opencode/skills/aitask-pickweb/SKILL.md` (after t777_15) — first instance of the corrected pattern; copy this body verbatim and substitute the skill name + resolver short name
- `aidocs/stub-skill-pattern.md` §3d, §3g — spec
- `tests/test_skill_render_aitask_pickweb.sh` Test 9 — the assertion pattern that catches the legacy "Source of Truth" phrase; replicate per skill

## Implementation Plan

1. For each of the 8 affected skills, replace `.opencode/skills/<skill>/SKILL.md` with a §3d-style stub:
   - Frontmatter: `name: <skill>`, `description: <copied from the matching command file>`
   - Body: identical to `.opencode/commands/<skill>.md` except the frontmatter has `name:` (skills require it, commands don't)
   - Uses `--agent opencode` and `$ARGUMENTS`
   - Conditional-Read pattern ("Render only if needed") for pickrem and pickweb (already pre-rendered); plain non-conditional render call for the others
2. Update `aitask_audit_wrappers.sh::render_opencode_skill` (line 180) to detect templated skills (a corresponding `.claude/skills/<skill>/SKILL.md.j2` exists) and switch to a §3d-style template output. Non-templated skills keep the legacy "Source of Truth" pointer pattern.
3. Update `aitask_skill_verify.sh::_resolver_key_for` to use a prerender marker rather than a per-skill hardcoded switch — remove the TODO at line 78 and the duplicate at the pickweb entry. Options:
   - Read the skill's stub file directly and extract the resolver key from the actual `aitask_skill_resolve_profile.sh <key>` line.
   - Add a sidecar file like `.claude/skills/<skill>/resolver_key.txt`.
   - Default to `${skill#aitask-}` and let templated skills opt in.
4. Add a regression test (`tests/test_opencode_skill_legacy_pointers.sh`) that iterates over all templated skills (those with a `.claude/skills/<skill>/SKILL.md.j2`) and asserts:
   - `.opencode/skills/<skill>/SKILL.md` exists
   - Its body does NOT contain the literal "Source of Truth" phrase
   - Its body contains `aitask_skill_resolve_profile.sh <short_name>`
5. Optionally extend the same regression to assert the Codex `.agents/skills/<skill>/SKILL.md` matches the Claude `.claude/skills/<skill>/SKILL.md` byte-for-byte (they should — they're both §3b stubs differing only in `--agent` and the Read target root).

## Verification Steps

1. `bash tests/test_opencode_skill_legacy_pointers.sh` → PASS for all 8 templated skills (pickweb's §3d-style stub from t777_15 should be the 9th and also PASS).
2. `./.aitask-scripts/aitask_skill_verify.sh` → no new failures.
3. Re-run `/aitask-audit-wrappers --phase=skills` — should NOT regenerate the legacy "Source of Truth" pointer for any templated skill.
4. Manual end-to-end: in OpenCode, the skill auto-load surface for any templated skill resolves to the same renderer dispatch as the slash command.

## Notes

- pickweb (t777_15) is intentionally NOT in the 8-skill list above; it ships its own §3d-style stub as part of that task.
- The Codex `.agents/skills/<skill>/SKILL.md` surface is NOT affected because t777_14/etc. correctly wrote the §3b stub there (Codex uses `<root>/skills/<skill>/SKILL.md` as the authoring surface; OpenCode uses `<root>/commands/<skill>.md`).
- `aitask_audit_wrappers.sh::render_agents_skill` (line 154) also still emits a pre-templating "Source of Truth" pattern — for non-templated skills only, since templated skills already have their §3b stub manually authored. Consider symmetric detection there too, though it's lower-stakes because audit-wrappers refuses to overwrite existing files by default (line 252).
