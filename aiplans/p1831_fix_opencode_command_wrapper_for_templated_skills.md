---
Task: t1831_fix_opencode_command_wrapper_for_templated_skills.md
Base branch: main
Output branch: main
---

# t1831 — profile-aware `render_opencode_command` for templated skills

## Context

`aitask_audit_wrappers.sh apply-wrapper opencode-command <skill>` always emits the
legacy static command (`@`-include of `.claude/skills/<skill>/SKILL.md`). For a
templated skill (has `SKILL.md.j2`) that pulls in the *Claude* stub, which renders
`--agent claude` and dispatches to the wrong agent's variant. `render_agents_skill`
and `render_opencode_skill` already branch on `_skill_is_templated`; the command
renderer does not. t1823_2 had to write `.opencode/commands/aitask-brainstorm-discuss.md`
by hand.

Findings from exploration (read-only):
- All 14 committed templated-skill commands (`.opencode/commands/aitask-{pick,shadow,trail,...}.md`)
  have a body identical to `render_opencode_skill`'s templated body; their frontmatter
  carries only `description:` (no `name:`).
- 11/14 match that shape byte-for-byte. `aitask-pick`, `aitask-pickrem` and
  `aitask-pickweb` have a description with the backticks stripped. That is a
  pre-existing header difference, not a dispatch defect, and is out of scope.
- `aitask_skill_verify.sh`'s stub-surface check (the `opencode-cmd` surface) greps
  for `aitask_skill_resolve_profile.sh <key>`, `aitask_skill_render.sh <skill>` and
  `.opencode/skills/<skill>-<profile>-/SKILL.md`. The legacy form has none of these,
  so verify **would** have rejected a generated legacy command for a templated skill.
  The task asked about this. The test below confirms it with a negative control.

## Implementation

### 1. `.aitask-scripts/aitask_audit_wrappers.sh` — `render_opencode_command`

Add a `_skill_is_templated` branch before the legacy heredoc, emitting the committed
shape (resolver key `${skill#aitask-}`, the same derivation the sibling renderers use):

```bash
render_opencode_command() {
    local skill="$1" description="$2"

    if _skill_is_templated "$skill"; then
        local resolver_key="${skill#aitask-}"
        cat <<EOF
---
description: ${description}
---

@.opencode/skills/opencode_planmode_prereqs.md
@.opencode/skills/opencode_tool_mapping.md

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse \$ARGUMENTS for \`--profile <name>\`.
   ... (identical to render_opencode_skill's templated body)
EOF
        return
    fi
    # legacy heredoc unchanged
}
```

The body stays a literal heredoc and is not shared through a helper, which matches
the file's existing style (each renderer owns its heredoc). The new test pins the
duplicated body to the skill-dir renderer.

### 2. New test `tests/test_audit_wrappers_render_opencode_command.sh`

This is a self-contained bash test (scratch cwd + `tests/lib/asserts.sh`, pattern from
`tests/test_learn_wrappers.sh`), with no subshell bodies. Cases:
- **T1 exact:** `render-wrapper opencode-command aitask-shadow` is byte-identical to
  `.opencode/commands/aitask-shadow.md`. Repeat for `aitask-brainstorm-discuss`.
- **T2 all templated skills, body:** for every `.claude/skills/*/SKILL.md.j2`, the
  rendered command body (after the frontmatter) equals the committed command's body.
  It also contains `--agent opencode` and does not contain `@.claude/skills/`.
- **T3 non-templated negative control:** for a non-templated skill (e.g. `aitask-create`),
  the output still carries the legacy `@.claude/skills/aitask-create/SKILL.md` include.
  This shows the branch keys on templating and does not apply to everything.
- **T4 verify catches the legacy form:** apply the same three greps that
  `aitask_skill_verify.sh` uses to the *legacy* render of a templated skill. Produce
  that render by calling the non-templated path on a temp fixture, or simply by
  asserting that the legacy text lacks the resolver/render/read-path markers. At least
  one marker must be missing. This records the answer to the task's verify question.

## Verification

- `bash tests/test_audit_wrappers_render_opencode_command.sh`: all PASS.
- Red proof: temporarily view the pre-fix output with `git stash`-free means. Run
  T2's assertion against the legacy heredoc text in T4 rather than reverting code.
- `bash tests/test_opencode_setup.sh` and `./.aitask-scripts/aitask_skill_verify.sh`
  still pass.
- `shellcheck .aitask-scripts/aitask_audit_wrappers.sh`.

## Step 9

Commit as `bug: ... (t1831)`, then run the standard archival via task-workflow Step 9.

## Risk

### Code-health risk: low
None identified. One renderer gains a branch that mirrors two sibling branches, and the
legacy path is unchanged and covered by a negative control.

### Goal-achievement risk: low
None identified. The generated output is pinned byte-for-byte to committed,
known-good commands.
