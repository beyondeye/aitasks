---
Task: t777_1_minijinja_dep_renderer_paths_resolver.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_10_convert_aitask_fold.md, aitasks/t777/t777_11_convert_aitask_qa.md, aitasks/t777/t777_12_convert_aitask_pr_import.md, aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_2_aitask_skill_render_subcommand.md, aitasks/t777/t777_3_stub_skill_design_and_gitignore.md, aitasks/t777/t777_4_aitask_skill_verify_and_precommit.md, aitasks/t777/t777_5_aitask_skillrun_wrapper_dispatcher.md, aitasks/t777/t777_6_convert_aitask_pick_template_and_stubs.md, aitasks/t777/t777_7_convert_task_workflow_shared_procs.md, aitasks/t777/t777_8_convert_aitask_explore.md, aitasks/t777/t777_9_convert_aitask_review.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-17 12:45
---

# Plan: t777_1 — `minijinja` dep + renderer + paths + resolver (VERIFIED)

This is a **verify-mode** plan. The external plan file already exists at `aiplans/p777/p777_1_minijinja_dep_renderer_paths_resolver.md` and the task description at `aitasks/t777/t777_1_minijinja_dep_renderer_paths_resolver.md` contains the file-by-file implementation guide. Both remain canonical. This document records the verification outcome plus two refinements (gemini path resolution and explicit whitelist deliverable for the new helper).

## Context

t777 is a multi-child redesign that replaces the runtime "ask LLM to honor execution-profile variables" model with **pre-render**: each skill is a Jinja-style template, and the active execution profile is injected at render-time so the agent reads a flat, control-flow-fixed skill body. This child (t777_1) is the foundation — it adds the templating dep + 3 shared helpers that every later child (t777_2 through t777_20) imports. No user-visible behavior changes after this task lands.

## Verification Findings (2026-05-17)

- **All four planned new files are absent**: `.aitask-scripts/lib/skill_template.py`, `.aitask-scripts/lib/agent_skills_paths.sh`, `.aitask-scripts/aitask_skill_resolve_profile.sh`, `tests/test_skill_template.sh`. Clean slate.
- **Pip install lines confirmed**: `.aitask-scripts/aitask_setup.sh:655` (CPython) and `.aitask-scripts/aitask_setup.sh:574` (PyPy). Both currently install `'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3'`. No other pip install lines in setup.
- **`python_resolve.sh` pattern**: `_AIT_PYTHON_RESOLVE_LOADED` guard at lines 26-27, `#!/usr/bin/env bash`, sources `terminal_compat.sh` from same dir.
- **`aitask_scan_profiles.sh`**: parses each YAML by grepping `^name:` and `^description:` (no full YAML load); supports `local/*` overrides via `PROFILES_DIR/local/*.yaml` with user-layer winning per filename.
- **`load_yaml_config(path, defaults=None) -> dict`** at `lib/config_utils.py:133`. Returns defaults silently when file missing; deep-merges otherwise.
- **Profile precedence chain** in `task-workflow/execution-profile-selection.md`: override → userconfig → project_config → "default" — matches the plan.
- **Agent skill dirs**: `.claude/skills`, `.codex/`, `.agents/skills`, `.gemini/skills`, `.gemini/commands`, `.opencode/skills` all exist. CLAUDE.md is internally contradictory on the gemini canonical path → **user decision: `agent_skill_root gemini` returns `.gemini/skills`** (per-agent-root model; consistent with the "Gemini CLI" section of CLAUDE.md).
- **Test conventions** (`tests/test_claim_id.sh`): inline `assert_eq` / `assert_contains` helpers, `PASS`/`FAIL`/`TOTAL` counters, no external sourcing.
- **Bash shebang**: all sampled scripts use `#!/usr/bin/env bash` — follow same.

## Refinements to External Plan

1. **`agent_skills_paths.sh`** — Replace the comment table in the original plan with the verified mapping:
   ```bash
   case "$1" in
       claude)   echo ".claude/skills" ;;
       codex)    echo ".agents/skills" ;;
       gemini)   echo ".gemini/skills" ;;   # per CLAUDE.md "Gemini CLI" section
       opencode) echo ".opencode/skills" ;;
       *)        echo "Unknown agent: $1" >&2; return 1 ;;
   esac
   ```
   No "verify at impl time" comment — the decision is made.

2. **5-touchpoint whitelist deliverable** for `aitask_skill_resolve_profile.sh` (per CLAUDE.md "Adding a New Helper Script"). The other two new files are sourceable lib / Python module, not invokable scripts, so they need no whitelisting. Touchpoints (add `aitask_skill_resolve_profile.sh` entries mirroring the existing `aitask_claim_id.sh` style):

   | File | Entry |
   |---|---|
   | `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_skill_resolve_profile.sh:*)"` in `permissions.allow` |
   | `.gemini/policies/aitasks-whitelist.toml` | `[[rule]]` block: `commandPrefix = "./.aitask-scripts/aitask_skill_resolve_profile.sh"`, `decision = "allow"`, `priority = 100` |
   | `seed/claude_settings.local.json` | mirror of Claude entry |
   | `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of Gemini entry |
   | `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_skill_resolve_profile.sh *": "allow"` |

   (Codex `.codex/config.toml` is prompt/forbidden-only, no allow decision — skip.)

## Step Order (final)

1. **Add minijinja dep** — Edit `.aitask-scripts/aitask_setup.sh` lines 655 and 574; append `'minijinja>=2.0,<3'` to both pip install commands.
2. **Write `lib/skill_template.py`** per the snippet in the task description (`render_skill(template_path, profile, agent_name)`, strict-undefined wrapped, `keep_trailing_newline=True`, CLI `__main__` for `python skill_template.py <template> <profile.yaml> <agent>`).
3. **Write `lib/agent_skills_paths.sh`** per the snippet, with the verified path mapping above.
4. **Write `aitask_skill_resolve_profile.sh`** implementing the userconfig → project_config → "default" precedence. Mirror `aitask_scan_profiles.sh`'s grep-based YAML parsing (one-liner is fine — read `default_profiles.<skill>` and emit the value to stdout).
5. **Whitelist `aitask_skill_resolve_profile.sh`** in the 5 touchpoints listed above.
6. **Write `tests/test_skill_template.sh`** covering: renderer happy path, strict-undefined error wrapping, agent branching (`{% if agent == "claude" %}`), resolve-profile precedence (userconfig wins over project_config).

## Verification Steps (final)

1. `bash install.sh --dir /tmp/scratch777_1` succeeds (full install flow, not just helper-in-isolation — per CLAUDE.md "Test the full install flow for setup helpers"). Then `~/.aitask/venv/bin/python -c "import minijinja; print(minijinja.__version__)"` works inside that scratch install.
2. `~/.aitask/venv/bin/python .aitask-scripts/lib/skill_template.py <tmp.j2> <tmp.yaml> claude` renders expected output.
3. `source .aitask-scripts/lib/agent_skills_paths.sh; agent_skill_dir claude aitask-pick fast` echoes `.claude/skills/aitask-pick-fast`. Same for `agent_skill_dir gemini aitask-pick fast` → `.gemini/skills/aitask-pick-fast`.
4. `./.aitask-scripts/aitask_skill_resolve_profile.sh pick` echoes the resolved profile name (currently `fast` based on `userconfig.yaml`).
5. `bash tests/test_skill_template.sh` — all PASS.
6. `shellcheck .aitask-scripts/lib/agent_skills_paths.sh .aitask-scripts/aitask_skill_resolve_profile.sh` clean.
7. Confirm the 5 whitelist touchpoints by grepping each file for `aitask_skill_resolve_profile`.

## Critical Files

**Modify:**
- `.aitask-scripts/aitask_setup.sh` (2 pip install lines)
- `.claude/settings.local.json` (+ 1 permission)
- `.gemini/policies/aitasks-whitelist.toml` (+ 1 rule)
- `seed/claude_settings.local.json` (+ 1 permission)
- `seed/geminicli_policies/aitasks-whitelist.toml` (+ 1 rule)
- `seed/opencode_config.seed.json` (+ 1 permission)

**Create:**
- `.aitask-scripts/lib/skill_template.py`
- `.aitask-scripts/lib/agent_skills_paths.sh`
- `.aitask-scripts/aitask_skill_resolve_profile.sh`
- `tests/test_skill_template.sh`

## Pitfalls

- **minijinja ≠ Jinja2 100%** — Stick to `{{ var }}`, `{% if/else/endif %}`, `{% include %}`, `{% raw %}/{% endraw %}`. No `{% extends %}` with Python, smaller filter set.
- **Strict-undefined wrap message** — Must include both the offending key and the template filename so later children's template-authoring errors are debuggable.
- **YAML loading** — Resolver script may use grep-based parsing (consistent with `aitask_scan_profiles.sh`); skill_template.py uses `yaml.safe_load` directly.
- **Profile precedence** — Mirror `task-workflow/execution-profile-selection.md` exactly; do not invent a new order.
- **Full install flow** — Verify with `install.sh --dir /tmp/scratch777_1`, NOT just by running helpers in a hand-crafted scratch dir (per CLAUDE.md "Test the full install flow for setup helpers").
- **Per-skill profile subdirs** — Per existing user feedback (`feedback_skills_reread_during_execution.md`), runtime SKILL.md files are re-read by the agent during execution, so per-profile renders must live in dedicated subdirs (`<skill>-<profile>/`) — `agent_skill_dir` already implements this naming. Later children will build atop this.

## Post-Implementation (Step 9)

Standard child-task archival via `.aitask-scripts/aitask_archive.sh 777_1`. Plan file's "Final Implementation Notes" must include the verified per-agent path mapping and any deviations from this verification document — subsequent children (t777_2+) will read it as primary reference.
