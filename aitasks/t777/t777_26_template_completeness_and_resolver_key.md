---
priority: high
effort: medium
depends: [t777_25]
issue_type: bug
status: Ready
labels: [aitask_pick, stub_skill_pattern, template]
created_at: 2026-05-18 21:40
updated_at: 2026-05-18 21:40
---

## Context

User-driven discovery while testing aitask-pickn live (t777_24 manual
verification of t777_6 pilot). Two distinct bugs surfaced from a single
run log of `/aitask-pickn 741`:

```
Bash(./.aitask-scripts/aitask_skill_resolve_profile.sh aitask-pickn)
  default                                  ← STUB resolves "aitask-pickn"
Bash(./ait skill render aitask-pickn --profile default --agent claude)
  (rendered output)
...
[inside rendered body, Step 0a fires:]
Bash(./.aitask-scripts/aitask_scan_profiles.sh && cat userconfig.yaml ...)
Using default profile for pick: fast — skip_task_confirmation enabled.
                                  ↑ BODY resolves "pick" → fast
```

## Bug A — Resolver key mismatch (stub vs body)

The stub calls `aitask_skill_resolve_profile.sh aitask-pickn`. The body's
Step 0a calls `aitask_skill_resolve_profile.sh` (or its sub-procedure
equivalent) with `pick`. They look up DIFFERENT keys in userconfig's
`default_profiles:` block:

- `default_profiles.aitask-pickn` — what the stub queries
- `default_profiles.pick` — what the body queries (per the
  task-workflow short_name convention)

Result: the stub resolves to `default`, the body resolves to `fast`.
The user sees the wrong rendered variant loaded (default), then the
body silently overrides to `fast` mid-flow.

After t777_6 Phase 5 atomic rename, the stub will query
`default_profiles.aitask-pick` — still different from `pick`.

**Fix options:**

1. Stubs use the **short name** (`pick`) for resolver lookup —
   not `aitask-pick`. Requires the converter to know each skill's short
   name. Add this to `stub-skill-pattern.md` §3f authoring checklist.
2. Resolver script tries the full name first, falls back to stripping
   `aitask-` prefix. Hides the convention from converters, less
   explicit.
3. `default_profiles:` keys use the full skill name (`aitask-pick:
   fast`). Migration cost on every userconfig.yaml in the wild.

Recommend (1) — explicit, matches the existing `skill_name` context
variable in `task-workflow/SKILL.md`.

## Bug B — Template completeness (Step 0a/3b should not exist in rendered output)

The entire point of the templating model is to bake the profile in at
render time, so the rendered body never re-resolves at runtime. Yet
the current aitask-pickn template still includes:

- **Step 0a** "Select Execution Profile" — full procedure that
  re-runs `aitask_scan_profiles.sh` and reads userconfig at runtime.
- **Step 0** "Extract `--profile` argument" — argument parsing for an
  override that the stub already stripped.
- Inside task-workflown's rendered closure, **Step 3b** "refresh
  execution profile" — re-reads the profile YAML mid-workflow.

All three are dead weight in the rendered variant. Worse, Step 0a's
runtime resolution can DISAGREE with what the rendered variant
represents (Bug A above), causing silent profile override confusion
visible in the user's log.

**Fix options:**

1. **Wrap Step 0/0a in `{% if not profile %}…{% endif %}`** so they
   render only when no profile is baked in (i.e., never — every render
   has a profile). The wrap effectively removes Step 0/0a from every
   rendered variant.
2. **Hard-code `active_profile` and `active_profile_filename`** in the
   Step 3 hand-off section as render-time constants:
   ```
   - **active_profile**: { name: {{ profile.name }}, ... }
   - **active_profile_filename**: {{ profile.name }}.yaml
   ```
3. **Wrap Step 3b in task-workflown** the same way — if `profile`
   binding exists (it always will at render time), the body skips the
   "refresh profile" branch.

All three apply together. (1)+(2) live in `aitask-pickn/SKILL.md.j2`;
(3) lives in `task-workflown/SKILL.md`.

## Scope

1. Audit Step 0 (argument extract), Step 0a (profile select), and the
   Step 3 hand-off block in `aitask-pickn/SKILL.md.j2`. Replace each
   with render-time constants or wrap in `{% if not profile %}` so they
   vanish from rendered output.
2. Audit Step 3b (refresh execution profile) in
   `task-workflown/SKILL.md`. Wrap so it never fires in a rendered
   variant.
3. Update the stub Step 1 (resolve active profile) to use the
   task-workflow short name (`pick` for `aitask-pick(n)`), not the full
   slash command name. Document the convention in
   `aidocs/stub-skill-pattern.md` §3f.
4. Regenerate goldens for all 12 (profile × agent) aitask-pickn combos
   AND the 5 wrapped task-workflown files × 3 profiles.
5. Update `tests/test_skill_render_aitask_pickn.sh` assertions: NEW
   ones to assert the rendered body has NO mention of `aitask_scan_profiles`,
   `Execute the Execution Profile Selection Procedure`, or "Step 0a:
   Select Execution Profile" — anywhere.
6. Update `tests/test_skill_render_task_workflown.sh` similarly for
   Step 3b.

## Key Files to Modify

- `.claude/skills/aitask-pickn/SKILL.md.j2` (wraps for Step 0/0a, Step 3
  hand-off constants)
- `.claude/skills/task-workflown/SKILL.md` (Step 3b wrap)
- `.claude/skills/aitask-pickn/SKILL.md` (stub Step 1 — short name)
- `.agents/skills/aitask-pickn/SKILL.md` (same)
- `.gemini/commands/aitask-pickn.toml` (same)
- `.opencode/commands/aitask-pickn.md` (same)
- `aidocs/stub-skill-pattern.md` §3f (short-name convention)
- `tests/test_skill_render_aitask_pickn.sh` + 12 goldens
- `tests/test_skill_render_task_workflown.sh` + 15 goldens

## Verification

1. Manually run `/aitask-pickn 16` in a fresh session. The rendered
   body must NOT call `aitask_scan_profiles.sh` or `Execute the
   Execution Profile Selection Procedure` — verify in the conversation
   tool-call log.
2. `bash tests/test_skill_render_aitask_pickn.sh` passes with new
   assertions.
3. `bash tests/test_skill_render_task_workflown.sh` passes with new
   assertions.
4. `./.aitask-scripts/aitask_skill_verify.sh` passes.
5. Live `/aitask-pickn --profile default 16` and
   `/aitask-pickn --profile fast 16` both behave correctly with NO
   inside-body profile re-resolution.

## Notes

- This task is the natural completion of the templating model started
  in t777_22 (renderer) and t777_7 (procedure wraps). The pilot t777_6
  caught these gaps; this task closes them.
- Lands BEFORE t777_24 re-verification (the verification checklist is
  the regression gate).
- Sequence: t777_25 (direct-helper paths) → t777_26 (this task,
  template completeness + resolver-key fix) → t777_24 (verify) →
  t777_6 Phase 5.
