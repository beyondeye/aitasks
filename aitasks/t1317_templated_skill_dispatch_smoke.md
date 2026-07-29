---
priority: high
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [shadow, execution_profiles]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1311
created_at: 2026-07-29 10:15
updated_at: 2026-07-29 10:19
---

## Origin

Risk-mitigation ("before") for t1311, created at Step 7 from the approved plan's
risk evaluation. t1311 depends on this task and will not be implemented until it
lands.

## Risk addressed

From t1311's `## Risk` section (code-health, severity high):

- "**Converting a live, minimonitor-spawned skill to the stub pattern is the
  dominant risk.** It rewrites four stub surfaces, deletes three 'Source of
  Truth' redirects, and newly pulls `aitask-shadow` into
  `aitask_skill_verify.sh`, `test_opencode_skill_legacy_pointers.sh`,
  `test_opencode_setup.sh` and golden coverage. A mistake breaks shadow launch
  from minimonitor for every agent."

And (code-health, severity medium):

- "Nine sub-procedures start being rendered into the Codex and OpenCode trees
  for the first time; they have never been executed there and the goldens only
  prove they render, not that they run."

## Goal

Add a **generic dispatch-contract smoke test** covering every templated skill ×
every agent surface, so that the stub → rendered-variant dispatch path is
guarded *before* t1311 converts `aitask-shadow` to that pattern.

The test must be written against the skills that are **already** templated, so
it lands independently of t1311, and must **discover** its subjects rather than
hardcode them — so `aitask-shadow` is covered automatically the moment t1311
converts it.

### What to assert

For each skill discovered by `find .claude/skills -name 'SKILL.md.j2'` (the same
discovery `aitask_skill_verify.sh:35-37` uses), and for each agent surface:

| Agent | Stub location | Rendered variant location |
|---|---|---|
| claude | `.claude/skills/<skill>/SKILL.md` | `.claude/skills/<skill>-<profile>-/SKILL.md` |
| codex | `.agents/skills/<skill>/SKILL.md` | `.agents/skills/<skill>-<profile>-codex-/SKILL.md` |
| opencode | `.opencode/skills/<skill>/SKILL.md` **and** `.opencode/commands/<skill>.md` | `.opencode/skills/<skill>-<profile>-/SKILL.md` |

1. **The stub exists** at each of the four surfaces above.
2. **The stub's Step-3 dispatch target is the correct rendered path** for that
   agent — parse the path out of the stub body rather than reconstructing it, so
   a stub that names the wrong directory (e.g. a codex stub missing the
   `-codex-` shared-root segment) fails.
3. **Rendering produces that exact path.** Run
   `./.aitask-scripts/aitask_skill_render.sh <skill> --profile <profile> --agent <agent>`
   and assert the file the stub names now exists.
4. **The rendered closure is complete** — every `.md` file in the authoring dir
   has a counterpart in the rendered dir, so a skill whose sub-procedures never
   reach the Codex/OpenCode trees fails loudly. This is the assertion that
   covers the "rendered but never executed there" risk.
5. **The stub's resolver key resolves** — `aitask_skill_resolve_profile.sh
   <resolver_key>` (parsed out of the stub body) exits 0 and prints a non-empty
   single line.

### Constraints

- Discovery-based, never a hardcoded skill list (a hardcoded list would not pick
  up `aitask-shadow` after t1311 and the mitigation would be inert).
- Follow `aidocs/framework/stub-skill-pattern.md` §3g for the per-agent surface
  table — it is the single source of truth for the rendered-path shapes; do not
  restate the mapping independently, derive the expectation from the stub.
- Render into the normal gitignored trailing-hyphen dirs; do not leave state
  behind that a later `aitask_skill_verify.sh` would trip over.
- **Prove the harness can fail** (negative control): temporarily point one stub's
  Step-3 target at a wrong path (or hide one closure file) and confirm the suite
  exits non-zero, then restore *by undoing the mutation only* — not via
  `git checkout`, which would also discard unrelated in-flight work.

## Acceptance criteria

1. A new test under `tests/` performs assertions 1-5 above for every templated
   skill × every agent surface, with subjects discovered at runtime.
2. The test passes against the current tree (all currently templated skills).
3. The negative control demonstrably makes the suite exit non-zero.
4. `shellcheck` clean if implemented in bash; runs under the standard runner if
   in Python.

## Blocks

- **t1311** (`shadow_impl_review_gate_premise_and_profile_tier_default`) — the
  shadow stub conversion. t1311's `depends:` names this task.
