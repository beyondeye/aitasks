---
priority: medium
effort: medium
depends: [1597]
issue_type: bug
status: Implementing
labels: [verification, bug]
assigned_to: dario-e@beyond-eye.com
anchor: 1595
followup_kind: verification_failure
created_at: 2026-09-01 17:11
updated_at: 2026-09-01 17:19
---

## Failed verification item from t1597

> TODO: verify .aitask-scripts/settings/settings_app.py end-to-end in tmux - the new resource_admission_command row renders in `ait settings` -> Project Config, edits with the plain string editor, and saves back to project_config.yaml losslessly

### Source

- **Manual-verification task:** `aitasks/t1670_manual_verification_pre_implementation_resource_admission_ho.md` (item #7)
- **Origin feature task:** t1597
- **Origin archived plan:** `aiplans/archived/p1597_pre_implementation_resource_admission_hook.md`

### Commits that introduced the failing behavior

- 68af4d67a enhancement: Add a pluggable pre-implementation resource admission hook (t1597)

### Files touched by those commits

- .agents/skills/task-workflow-remote-codex-/plan-approved-stop.md
- .agents/skills/task-workflow-remote-codex-/resource-admission.md
- .agents/skills/task-workflow-remote-codex-/SKILL.md
- aidocs/gates/ledger-driven-reentry.md
- .aitask-scripts/aitask_resource_admission.sh
- .aitask-scripts/lib/gate_verifier_lib.sh
- .aitask-scripts/settings/settings_app.py
- .claude/settings.local.json
- .claude/skills/task-workflow/plan-approved-stop.md
- .claude/skills/task-workflow-remote-/plan-approved-stop.md
- .claude/skills/task-workflow-remote-/resource-admission.md
- .claude/skills/task-workflow-remote-/SKILL.md
- .claude/skills/task-workflow/resource-admission.md
- .claude/skills/task-workflow/SKILL.md
- .codex/rules/default.rules
- .opencode/skills/task-workflow-remote-/plan-approved-stop.md
- .opencode/skills/task-workflow-remote-/resource-admission.md
- .opencode/skills/task-workflow-remote-/SKILL.md
- seed/claude_settings.local.json
- seed/codex_rules.default.rules
- seed/opencode_config.seed.json
- seed/project_config.yaml
- tests/golden/procs/task-workflow/plan-approved-stop-default.md
- tests/golden/procs/task-workflow/plan-approved-stop-fast.md
- tests/golden/procs/task-workflow/plan-approved-stop-remote.md
- tests/golden/procs/task-workflow/resource-admission-default.md
- tests/golden/procs/task-workflow/SKILL-default.md
- tests/golden/procs/task-workflow/SKILL-fast.md
- tests/golden/procs/task-workflow/SKILL-remote.md
- tests/test_gate_verifiers.sh
- tests/test_plan_approved_marker_contract.sh
- tests/test_resource_admission.sh
- tests/test_resource_admission_stop.sh
- tests/test_skill_render_task_workflow.sh
- website/content/docs/skills/aitask-pick/build-verification.md
- website/content/docs/skills/aitask-pick/_index.md
- website/content/docs/skills/aitask-pick/resource-admission.md

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1670 item #7.

## Diagnosis (from the t1670 auto-verification run)

The row renders and edits correctly. **The save is lossy**, and it fails open.

### What works

- The `resource_admission_command` row renders in `ait settings` → Project Config,
  between `lint_command` and `learn_skill_authoring_guide`, with the schema summary.
- Enter opens `EditStringScreen` (the plain string editor), not the multi-line
  `EditVerifyBuildScreen` — correct, since the key is outside the
  `("verify_build", "test_command", "lint_command")` preset trio.
- The in-memory row updates and "Project config saved" is reported.

### The defect

`.aitask-scripts/settings/settings_app.py:2591`:

```python
data[key] = yaml.safe_load(raw_value)
```

The user-typed command string is re-parsed **as a YAML document**. Any value
containing `: ` (colon-space) therefore parses to a **dict**, not a string:

```
input : sh -c "echo ADMISSION_REASON: no memory; exit 2"
parsed: {'sh -c "echo ADMISSION_REASON': 'no memory; exit 2"'}
```

`safe_dump` then writes that nested mapping:

```yaml
resource_admission_command:
  sh -c "echo ADMISSION_REASON: no memory; exit 2"
```

which reloads as a dict. `project_config_values()` finds no scalar, so
`aitask_resource_admission.sh` reports:

```
VERDICT:admit
REASON:none_configured
```

**exit 0 — a silent admit.** The user configured a hook, the TUI confirmed the
save, and the framework then behaves as if no hook existed. Per
`resource-admission.md` step 2, `none_configured` displays *nothing at all*, so
there is no signal anywhere. This inverts the feature's stated fail-closed
posture ("a host that cannot be probed is exactly the one that runs out of
memory mid-verification") into a fail-open one.

### Why this key makes it acute

The trigger is a `: ` in the value, and this feature's own documented reason
convention — an `ADMISSION_REASON: <text>` line, restated in the schema `detail`
text added by t1597 — makes a colon-space the *normal* case for this key.
Colon-free values (`./tools/check_memory.sh`, `sh -c "exit 2"`) round-trip fine.

### Reproduction

1. `cd` to a tree with `aitasks/metadata/project_config.yaml`; run `ait settings`.
2. `c` → Project Config → focus `resource_admission_command` → Enter.
3. Type `sh -c "echo ADMISSION_REASON: no memory; exit 2"` → Enter → Save Project Config.
4. `grep -A1 resource_admission_command aitasks/metadata/project_config.yaml`
   → the value sits on an unquoted continuation line.
5. `./.aitask-scripts/aitask_resource_admission.sh --task-id <id>`
   → `REASON:none_configured`, exit 0.

### Scope note

Line 2591 is **pre-existing**, not added by t1597, and applies to every
string-typed project-config key. t1597 is what made it reachable and harmful.
A fix should keep string-typed schema keys as strings rather than re-parsing
them, and must not regress `verify_build`'s list form. Consider also whether
the helper should distinguish "key present but not a scalar" from
"key absent" instead of collapsing both to `none_configured` — the exit-3
`not_scalar` path already exists for the list form and does not fire for a dict.

### Second, lesser finding (same run, separate from item 7)

Saving the Project Config tab rewrites the file with `yaml.safe_dump` and
**strips every comment** — the scratch fixture went from 71 lines to 28. This is
pre-existing settings-TUI behaviour and unrelated to the admission hook, but it
means any project whose `project_config.yaml` carries the seeded explanatory
comments loses them on the first save from the TUI. Worth its own task if not
already known.
