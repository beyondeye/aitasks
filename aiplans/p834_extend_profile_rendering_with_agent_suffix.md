---
Task: t834_extend_profile_rendering_with_agent_suffix.md
Base branch: main
plan_verified: []
---

# t834 — Extend profile rendering with agent suffix

## Context

A new code agent **agy** (tracked in t814) will be added to the framework
later. Its rendered SKILL.md files target the same physical root as Codex CLI
(`.agents/skills/<skill>/SKILL.md`). Today the framework renders per-(skill,
profile, agent) variants into `<root>/skills/<skill>-<profile>-/SKILL.md` (one
trailing hyphen — load-bearing for the `*-/` gitignore glob). With two agents
writing into the same root, the existing naming would collide: codex's render
would overwrite agy's and vice versa.

The user explicitly chose to extend the existing prerendered-execution-profile
mechanism rather than introduce runtime `{% if agent == "…" %}` checks inside
shared skill bodies (memory: `feedback_shared_skill_path_extend_suffix`). t834
is a prerequisite refactor for t814.

**Design decision (confirmed during planning):**
- Add the agent suffix only to agents whose physical skills root is shared
  with another agent (today: codex; soon: agy). Other agents (claude, gemini,
  opencode) keep the current single-suffix scheme unchanged.
- The "shared root" set is declared as an **explicit per-agent property** in
  `agent_skills_paths.sh` (kept in sync alongside the root mapping), not
  derived at runtime from root collisions.

## Target naming

| Agent | Today | After t834 |
|-------|-------|------------|
| claude | `.claude/skills/aitask-pick-fast-/SKILL.md` | unchanged |
| codex | `.agents/skills/aitask-pick-fast-/SKILL.md` | `.agents/skills/aitask-pick-fast-codex-/SKILL.md` |
| gemini | `.gemini/skills/aitask-pick-fast-/SKILL.md` | unchanged |
| opencode | `.opencode/skills/aitask-pick-fast-/SKILL.md` | unchanged |
| agy (t814) | n/a | `.agents/skills/aitask-pick-fast-agy-/SKILL.md` |

The trailing hyphen is preserved in every case so `*-/` gitignore globs keep
working.

## Implementation

### 1. `agent_skills_paths.sh` — declare shared-root set + emit new path

Edit `.aitask-scripts/lib/agent_skills_paths.sh`.

- Add helper `agent_shared_skills_root <agent>` that echoes `true`/`false`.
  Per-agent value (case statement, parallels `agent_skill_root`):
  - claude → `false`
  - codex → `true`
  - gemini → `false`
  - opencode → `false`
- Extend `agent_skill_dir <agent> <skill> [profile]`: when `profile` is
  non-empty AND `agent_shared_skills_root "$agent"` is `true`, emit
  `<root>/${skill}-${profile}-${agent}-`. Otherwise unchanged.
- Update the top-of-file comment block documenting the rendered-dir naming
  convention to describe the agent suffix.

### 2. `lib/skill_template.py` — mirror the shared-root predicate in Python

Edit `.aitask-scripts/lib/skill_template.py`.

- Add `AGENT_SHARED_SKILLS_ROOT = {"claude": False, "codex": True, "gemini": False, "opencode": False}`
  next to `AGENT_ROOTS`. Single source of truth in Python; tests can introspect.
- New helper `_render_dir_name(skill, profile_name, agent) -> str`:
  returns `f"{skill}-{profile_name}-{agent}-"` when shared, else
  `f"{skill}-{profile_name}-"`.
- Replace the three sites that today hardcode `f"{skill}-{profile_name}-"`:
  - `_target_path_for` (line 145): use `_render_dir_name`.
  - `walk_closure` entry-target composition (line 287): use `_render_dir_name`.
  - `rewrite_ref` full-path / skill-relative rewriting (line 213-214):
    use `_render_dir_name` keyed on the **target** `agent` (the rewrite
    target's directory, not the source).

### 3. `aitask_skill_rerender.sh` — per-agent glob + suffix-strip

Edit `.aitask-scripts/aitask_skill_rerender.sh`.

The current `find … -name "*-${profile}-"` glob will not match
`*-${profile}-codex-` dirs once codex starts emitting them. Refactor the
agent loop so that for each agent the glob and suffix-strip pattern reflect
whether the agent shares its root:

- If `agent_shared_skills_root "$agent"` is `true`: glob is
  `"*-${profile}-${agent}-"`; suffix-strip is `${base%-"${profile}"-"${agent}"-}`.
- Otherwise: unchanged.

### 4. `aitask_skill_verify.sh` — per-agent stub path + headless prerender path

Edit `.aitask-scripts/aitask_skill_verify.sh`.

- **Stub trailing-hyphen Read-path assertion** (line 135-139): the literal
  substring being asserted depends on the target agent. Compute the expected
  substring per agent: `"${skill}-<profile>-<agent>-/SKILL.md"` for
  shared-root agents, `"${skill}-<profile>-/SKILL.md"` otherwise.
- **Headless prerender check** (line 154): replace the hardcoded
  `$root/$skill-remote-/SKILL.md` with a per-agent path computed via
  `agent_skill_dir` (which now handles the suffix). For codex/agy that's
  `.agents/skills/$skill-remote-codex-/SKILL.md` / `…-agy-`; others unchanged.

### 5. Update codex stub files (only Codex stubs change)

For every committed `.agents/skills/<skill>/SKILL.md` stub authored under the
stub-skill pattern (10 skills currently: aitask-pick, aitask-pickrem,
aitask-pickweb, aitask-explore, aitask-review, aitask-qa, aitask-fold,
aitask-pr-import, aitask-revert, aitask-wrap, plus `task-workflow` if it has
one), update the Step-3 Read path:

```
.agents/skills/<skill>-<profile>-/SKILL.md  →  .agents/skills/<skill>-<profile>-codex-/SKILL.md
```

Claude / Gemini / OpenCode stubs are NOT touched (their roots are not shared).

### 6. `.gitignore` — update committed-headless negations for codex root only

Rename the `.agents/skills/*-remote-/` entries to `*-remote-codex-/`:

```
!.agents/skills/aitask-pickrem-remote-codex-/
!.agents/skills/aitask-pickweb-remote-codex-/
!.agents/skills/task-workflow-remote-codex-/
```

The other agent roots' negations stay unchanged. Add the TODO bullet noting
that agy (t814) will append parallel `-agy-` negations when it lands.

### 7. Re-render and re-commit pre-rendered codex variants

Delete the existing committed `.agents/skills/<skill>-remote-/` directories
(pickrem, pickweb, task-workflow), re-render their codex variants under the
new naming, and commit the new locations:

```bash
./.aitask-scripts/aitask_skill_render.sh aitask-pickrem --profile remote --agent codex --force
./.aitask-scripts/aitask_skill_render.sh aitask-pickweb --profile remote --agent codex --force
# task-workflow is reached transitively but render directly too if needed
```

The verify script's headless check then validates the new path.

### 8. Update `aidocs/stub-skill-pattern.md`

- §3a / §3b: note the agent-suffix variation for shared-root agents.
- §3g Per-agent surface table: change the codex row's "Rendered variant
  location" cell to `.agents/skills/<skill>-<profile>-codex-/SKILL.md`. Add
  a footnote pointing at `agent_shared_skills_root` as the single source of
  truth for which agents emit the suffix.
- §3i Reference resolution: rewrite rule becomes "<target_root>/<dir>-<profile>[-<agent>]-/<file>.md
  where the `-<agent>` segment appears only when target_root is shared".

### 9. Update tests

For every test that asserts codex-agent paths under the old scheme:

- `tests/test_skill_template.sh` lines 265, 268, 271 (multi-agent walk-write
  assertion against `.agents/skills/task-workflow-fast-/planning.md`): update
  the codex expectation to `.agents/skills/task-workflow-fast-codex-/planning.md`.
- `tests/test_skill_rerender.sh`: update assertions that depend on the codex
  rendered-dir name.
- `tests/test_skill_render_*.sh` per-skill render tests: any walk-write
  assertion under `.agents/skills/<skill>-<profile>-/…` updates to include
  `-codex-`. Each test file follows the same pattern; grep for `.agents/skills/`
  and update only those lines.
- `tests/test_skill_verify.sh`: align with the new stub-pattern check.

`test_skill_render_uniform.sh` uses `--agent claude` for its synthetic
fixtures, so the trailing-hyphen pattern stays `-fast-`. No changes there.

The pre-rewrite goldens in `tests/fixtures/skills/**` are agent-invariant
(captured before reference rewriting) and don't change.

### 10. Regenerate goldens

After source edits, run the per-skill render tests with the
golden-regeneration mode (per `aidocs/skill_authoring_conventions.md`
"Regenerate goldens after any `.md.j2` or closure edit"). Same-commit rule:
goldens must land in the same commit as the source edit. Specifically the
walk-write goldens that capture codex-agent rewrites need to be regenerated.

## Out of scope

- Adding the agy agent itself (t814).
- Removing geminicli (t812).
- Changing claude/gemini/opencode rendered-dir naming.
- Auto-deriving the shared-root set from `agent_skill_root` collisions.

## Verification

End-to-end pass after all edits:

1. `./.aitask-scripts/aitask_skill_verify.sh` — stub-pattern + render + walk-check + headless prerender all pass.
2. `bash tests/test_skill_template.sh` — unit tests for path composition.
3. `bash tests/test_skill_render_uniform.sh` — synthetic dep-walker tests.
4. Each `bash tests/test_skill_render_*.sh` (aitask-pick, aitask-explore, etc.) — golden comparison.
5. `bash tests/test_skill_rerender.sh` — rerender glob still works.
6. `bash tests/test_skill_verify.sh` — verify-script test.
7. `bash tests/test_skill_parity_runtime_vs_rendered.sh` — parity unchanged (pre-rewrite goldens are agent-invariant).
8. Manual spot check: render aitask-pick for codex profile fast and inspect that
   - the file lands at `.agents/skills/aitask-pick-fast-codex-/SKILL.md`,
   - internal full-path refs point at `.agents/skills/<other_skill>-fast-codex-/<file>.md` (with the `-codex-` segment),
   - and the same render for claude / gemini / opencode is unchanged.
9. Manual spot check: re-render the pre-committed codex remote variants
   (`aitask-pickrem-remote-codex-/`, `aitask-pickweb-remote-codex-/`,
   `task-workflow-remote-codex-/`) and confirm `.gitignore` correctly
   un-ignores them while the old `*-remote-/` paths now do not exist on disk.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: merge approval, branch cleanup, archival,
and push. No special considerations beyond regenerating goldens in the
same commit as the source change.
