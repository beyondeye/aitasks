---
priority: high
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [aitask_pick, stub_skill_pattern]
created_at: 2026-05-18 19:14
updated_at: 2026-05-18 19:14
---

## Context

While running t777_6 manual verification, the user discovered the new stubs
call `./ait skill render <skill> --profile <p> --agent <a>` (the
dispatcher form), but other skill bash invocations across the framework
use the direct path `.aitask-scripts/aitask_*.sh` (already whitelisted in
`.claude/settings.local.json`). The dispatcher form forces a new
allowlist entry for every stub user — friction with no payoff because:

1. The stubs are not user-facing (the user types `/aitask-pick`, not
   `ait skill render aitask-pick ...`).
2. The `ait skill` and `ait skillrun` dispatcher subcommands exist only
   to wrap the underlying helper scripts. They add no value over a
   direct path call.
3. Most existing skills call `.aitask-scripts/aitask_*.sh` directly.

## Scope

1. **Update canonical stub bodies in `aidocs/stub-skill-pattern.md`:**
   - §3b (Claude/Codex SKILL.md form): change Step 2 from
     `./ait skill render ...` → `./.aitask-scripts/aitask_skill_render.sh ...`
   - §3c (Gemini TOML): same change.
   - §3d (OpenCode MD): same change.
   - Verify Step 1 (`aitask_skill_resolve_profile.sh`) — already a direct
     path, no change needed.

2. **Update the 4 existing aitask-pickn stubs** to use direct paths:
   - `.claude/skills/aitask-pickn/SKILL.md`
   - `.agents/skills/aitask-pickn/SKILL.md`
   - `.gemini/commands/aitask-pickn.toml`
   - `.opencode/commands/aitask-pickn.md`

3. **Update test `tests/test_skill_render_aitask_pickn.sh`** Test 5
   assertions to match the new direct-path invocation form.

4. **Update goldens** under `tests/golden/skills/aitask-pickn/` if
   anything in the rendered output references the dispatcher form (the
   renderer itself reads the source `.md.j2`; the dispatcher form does
   NOT appear in entry-point rendered output, only in the stubs).

5. **Decision: remove `ait skill` and `ait skillrun` subcommands?**
   - `ait skillrun` (t777_5) is the universal launcher used by Python
     TUIs (e.g., AgentCommandScreen) and is t777_5's core deliverable.
     Removing it breaks t777_17 (per-run profile edit in
     AgentCommandScreen) which depends on it. KEEP `ait skillrun`.
   - `ait skill render` / `ait skill verify` are convenience wrappers.
     Two options:
     (a) Keep them but stop using them from stubs (this task's primary
         fix). Low-effort, preserves both invocation surfaces.
     (b) Delete them entirely. Need to grep for callers
         (`grep -rn "ait skill " .` excluding `ait skillrun`) — any test
         scripts, doc references, or TUI calls must migrate. Higher
         effort, narrower surface.
   - Recommend (a) initially; defer (b) to a follow-up if no callers
     remain after a few months.

6. **Update `t777_8..t777_15` plans** (and `t777_18` docs task) to use
   the direct-path form when they convert remaining skills.

## Key Files to Modify

- `aidocs/stub-skill-pattern.md` (§3b/§3c/§3d Step 2)
- `.claude/skills/aitask-pickn/SKILL.md` (Step 2 line)
- `.agents/skills/aitask-pickn/SKILL.md` (Step 2 line)
- `.gemini/commands/aitask-pickn.toml` (Step 2 line)
- `.opencode/commands/aitask-pickn.md` (Step 2 line)
- `tests/test_skill_render_aitask_pickn.sh` (assertions)

## Verification

1. `bash tests/test_skill_render_aitask_pickn.sh` passes.
2. `./.aitask-scripts/aitask_skill_verify.sh` passes (direct invocation).
3. Live `/aitask-pickn 16` runs without prompting for `./ait skill`
   permission (uses already-whitelisted `.aitask-scripts/aitask_skill_render.sh:*`).
4. Live `/aitask-pickn 16` should not need any new entries in
   `.claude/settings.local.json`.

## Notes

- This task lands BEFORE t777_6's atomic rename (Phase 5) since it
  modifies aitask-pickn artifacts. Sequence:
  1. t777_24 manual verification of current state (in-flight)
  2. t777_25 (this task) — refactor stubs to direct-path form
  3. t777_24 re-verification (or amend t777_24's checklist mid-run)
  4. t777_6 Phase 5 atomic rename
  5. t777_6 Phase 6 docs append (now references direct-path form)
