# Adding a New Code Agent to the aitasks Framework

End-to-end checklist for wiring a new code agent (Claude Code, Codex CLI,
Gemini CLI, OpenCode, agy, …) into the aitasks framework. Each section
covers one architectural concern. Sections are independent and can be
addressed in any order, but the order presented here is the path of least
friction (no rework, no temporary inconsistency).

> **Scope.** This doc covers what is needed *inside the aitasks framework*
> to make a new agent first-class: skill discovery, rendering, command
> wrappers, prompt-pattern detection, model-stats config, etc. It does
> **not** cover installing the agent's CLI itself (that lives in the
> agent vendor's docs).

## Index

- [1. Writing skills for agents that share `.agents/skills/`](#1-writing-skills-for-agents-that-share-agentsskills)

*(More sections to be added as the migration playbook expands: command
wrappers, prompt-pattern detection for `ait monitor`, agent-string
resolver, model-stats config, tool-mapping prereq files, whitelist /
permission setup, etc.)*

---

## 1. Writing skills for agents that share `.agents/skills/`

Some agents target the same **physical skills directory** as another
existing agent. Today that is Codex CLI (`.agents/skills/`); when agy
lands (t814) it will share that root too. Without disambiguation, two
agents writing their rendered SKILL.md into the same directory would
overwrite each other.

The framework solves this by adding an **agent-id segment** to the
rendered-dir name for any agent declared as `shared_skills_root: true`.
Non-shared agents (claude, gemini, opencode) keep the simpler
`<skill>-<profile>-/` form unchanged.

### 1a. Rendered-path naming

| Agent | `agent_skill_root` | Shared? | Rendered SKILL.md path |
|-------|-------------------|---------|-----------------------|
| claude | `.claude/skills` | no | `.claude/skills/<skill>-<profile>-/SKILL.md` |
| codex | `.agents/skills` | **yes** | `.agents/skills/<skill>-<profile>-codex-/SKILL.md` |
| gemini | `.gemini/skills` | no | `.gemini/skills/<skill>-<profile>-/SKILL.md` |
| opencode | `.opencode/skills` | no | `.opencode/skills/<skill>-<profile>-/SKILL.md` |
| *new shared-root agent* | (same as another) | **yes** | `<root>/<skill>-<profile>-<agent>-/SKILL.md` |

The trailing hyphen is preserved on both forms so the single `*-/`
gitignore glob per agent root still matches every rendered dir.

### 1b. Declare the shared-root flag

The "shared root" set is an **explicit per-agent property** (kept in
sync alongside `agent_skill_root` so adding a new agent is a single
diff in each file).

1. **Bash** — `.aitask-scripts/lib/agent_skills_paths.sh`: add the new
   agent to both `agent_skill_root()` and `agent_shared_skills_root()`.

   ```bash
   agent_skill_root() {
       case "$1" in
           claude)   echo ".claude/skills" ;;
           codex)    echo ".agents/skills" ;;
           agy)      echo ".agents/skills" ;;        # NEW
           gemini)   echo ".gemini/skills" ;;
           opencode) echo ".opencode/skills" ;;
           *)        echo "agent_skill_root: unknown agent: $1" >&2; return 1 ;;
       esac
   }

   agent_shared_skills_root() {
       case "$1" in
           claude)   echo "false" ;;
           codex)    echo "true"  ;;
           agy)      echo "true"  ;;                 # NEW (shares .agents/skills)
           gemini)   echo "false" ;;
           opencode) echo "false" ;;
           *)        echo "agent_shared_skills_root: unknown agent: $1" >&2; return 1 ;;
       esac
   }
   ```

2. **Python** — `.aitask-scripts/lib/skill_template.py`: add the
   matching entries to `AGENT_ROOTS` and `AGENT_SHARED_SKILLS_ROOT`.

   ```python
   AGENT_ROOTS = {
       "claude":   ".claude/skills",
       "codex":    ".agents/skills",
       "agy":      ".agents/skills",      # NEW
       "gemini":   ".gemini/skills",
       "opencode": ".opencode/skills",
   }
   AGENT_SHARED_SKILLS_ROOT = {
       "claude":   False,
       "codex":    True,
       "agy":      True,                  # NEW
       "gemini":   False,
       "opencode": False,
   }
   ```

`_render_dir_name(skill, profile_name, agent)` consults
`AGENT_SHARED_SKILLS_ROOT` and automatically emits
`<skill>-<profile>-<agent>-` for shared-root agents,
`<skill>-<profile>-` otherwise — no other code path needs to special-case
the new agent.

### 1c. Update the renderer driver loop

`.aitask-scripts/aitask_skill_rerender.sh` iterates a hardcoded list of
agents. Add the new agent name to the `for agent in claude codex …`
loop. The script already picks the correct find-glob and suffix-strip
based on `agent_shared_skills_root` — no further changes inside the
loop body.

```bash
for agent in claude codex agy gemini opencode; do   # NEW agent inserted
    ...
done
```

### 1d. Write the per-agent stub

Each skill needs a committed stub at the agent's authoring location
(see `aidocs/stub-skill-pattern.md` §3g for the per-agent surface
table). For shared-root agents the stub MUST point at the
agent-suffixed Read path:

```markdown
3. **Dispatch via Read-and-follow.** Read the file at
   `.agents/skills/<skill>-<profile>-<agent>-/SKILL.md` and execute its
   instructions ...
```

For example, the agy stub at `.agents/skills/<skill>/SKILL.md` reads
from `.agents/skills/<skill>-<profile>-agy-/SKILL.md` and renders with
`--agent agy`. This keeps each agent's runtime invocation independent
of its sibling agents that share the same physical root.

> **Don't substitute runtime checks for prerendering.** It is tempting
> to write a single shared stub body with `{% if agent == "agy" %}` /
> `{% if agent == "codex" %}` branches. The framework explicitly
> rejected that approach during t812 planning (see the
> `feedback_shared_skill_path_extend_suffix` memory). The per-agent
> prerender is load-bearing — it is how each agent gets agent-specific
> tool names, paths, and workflow branches without conditional bloat in
> skill bodies. Extend the prerender mechanism; do not collapse to
> runtime checks.

### 1e. Pre-rendered headless variants (if applicable)

Skills that ship as headless (`prerender_for_headless: true` in the
`.j2`, paired with a `headless: true` profile — today: `aitask-pickrem`
and `aitask-pickweb` with the `remote` profile) get their rendered
output committed to git so they work on machines where `ait setup` has
not run.

When you add a new shared-root agent:

1. Render each headless `(skill, profile)` pair for the new agent
   ```bash
   ./.aitask-scripts/aitask_skill_render.sh aitask-pickrem --profile remote --agent <agent> --force
   ./.aitask-scripts/aitask_skill_render.sh aitask-pickweb --profile remote --agent <agent> --force
   ```
   The walker also writes the transitive `task-workflow-remote-<agent>-/`
   closure.

2. Add the new agent-suffixed dirs to `.gitignore`'s negation block:
   ```
   !.agents/skills/aitask-pickrem-remote-<agent>-/
   !.agents/skills/aitask-pickweb-remote-<agent>-/
   !.agents/skills/task-workflow-remote-<agent>-/
   ```

3. Commit the new directories.

`aitask_skill_verify.sh`'s `PRERENDER_FAIL` check composes the expected
path via `agent_skill_dir`, so the new agent is automatically validated
once it appears in `agent_skills_paths.sh`.

### 1f. Regenerate tests and goldens

Per `aidocs/skill_authoring_conventions.md`, any change touching the
rendering pipeline must regenerate goldens in the **same commit** as the
source edit. Specifically:

- Walk-write goldens (Test 4 in each `tests/test_skill_render_*.sh`)
  capture the per-agent reference rewriting — adding a new agent means
  these tests need a new `assert_contains` line for the new agent's
  rewritten ref path (e.g.,
  `.agents/skills/task-workflow-fast-<agent>-/SKILL.md`).
- `tests/test_skill_template.sh` has explicit assertions for
  `agent_skill_dir`, `agent_shared_skills_root`, and `rewrite_ref` per
  agent — extend them with the new agent's expected values.
- Pre-rewrite goldens in `tests/fixtures/skills/**` are agent-invariant
  and do NOT change.

Run before committing:

```bash
./.aitask-scripts/aitask_skill_verify.sh
bash tests/test_skill_template.sh
bash tests/test_skill_render_uniform.sh
for t in tests/test_skill_render_aitask_*.sh tests/test_skill_render_task_workflow.sh; do bash "$t"; done
bash tests/test_skill_rerender.sh
bash tests/test_skill_verify.sh
bash tests/test_skill_parity_runtime_vs_rendered.sh
```

### 1g. Canonical reference

The full canonical pattern for stubs lives in
`aidocs/stub-skill-pattern.md` — read it for the stub body templates per
agent surface, the resolver-key convention, the argument-forwarding
contract, and the reference-resolution rules for `.j2` cross-skill
refs. This section is the *adding-a-new-agent* checklist; that doc is
the *what each stub must look like* spec.

---
