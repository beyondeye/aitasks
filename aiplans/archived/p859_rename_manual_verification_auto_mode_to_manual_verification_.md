---
Task: t859_rename_manual_verification_auto_mode_to_manual_verification_.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main (current)
Base branch: main
---

# t859 — Rename `manual_verification_auto_mode` → `manual_verification_mode`

## Context

t851 (archived brainstorm,
`aiplans/archived/p851_brainstorm_better_names_for_manual_verification_auto_mode.md`)
produced a user-confirmed proposal to rename the
`manual_verification_auto_mode` profile key, rename two of its values, and
drop one value entirely. t851 deferred the actual rename to this follow-up.
Renaming now — before t846's user-facing docs land and before external users
reference these names in their profile YAMLs — is far cheaper than renaming
later. t846 (docs) is blocked on this task (`depends: [843, 851, 859]`).

The rename (verbatim from the t851 decision):

| Old key/value | New key/value |
|---|---|
| key `manual_verification_auto_mode` | `manual_verification_mode` |
| `ask` *(default)* | `ask` (unchanged) |
| `never` | `manual` |
| `autonomous` | `autonomous` (unchanged) |
| `prebuilt_approve` | `autonomous_with_plan` |
| `prebuilt_autorun` | **dropped entirely** (no safe use case for unapproved planned execution) |

## Findings from exploration (shape the scope)

1. **Only `default.yaml` uses the key** among profile YAMLs (`fast.yaml`,
   `remote.yaml`, `local/` have none). It sets `autonomous`.
2. **Rendered `*-<profile>-` variant dirs are gitignored & untracked**
   (`git check-ignore` confirms). They self-refresh on skill invocation and
   via the settings/board save hooks → `aitask_skill_rerender.sh`. So
   **nothing under `.claude/skills/task-workflow-<profile>-/`,
   `.agents/skills/...codex-/`, or `.opencode/skills/...` needs committing.**
   This also makes the task's "Cross-agent skill ports" follow-up **moot**:
   codex/opencode variants render from the *single* Claude authoring source
   (`agent_authoring_template` is agent-independent), so re-rendering — not a
   separate authored port — propagates the change. No cross-agent follow-up
   task is needed.
3. **Goldens** (tracked, under `tests/golden/procs/task-workflow/`) are the
   real committed artifacts. Only `manual-verification.md` is golden-tested
   among the files I edit; `profiles.md` is not golden-tested (profile-
   invariant, no Jinja conditional).
4. **Baseline test state: 2 pre-existing failures** in
   `tests/test_skill_render_task_workflow.sh`:
   - `manual-verification-default` — stale because `default.yaml` sets
     `autonomous`; the golden still shows the key-absent `{% else %}` branch.
     My edit regenerates this golden anyway (in scope).
   - `manual-verification-followup-default` — stale because `default.yaml`
     sets `manual_verification_followup_mode: never`; unrelated to this
     rename. **Decision (user-confirmed): regenerate it too** so the suite
     ends green; document as an incidental pre-existing fix.

## Migration edits

### 1. `aitasks/metadata/profiles/default.yaml` (line 4)
`manual_verification_auto_mode: autonomous` → `manual_verification_mode: autonomous`

### 2. `.aitask-scripts/lib/profile_editor.py` (3 sites)
- **`PROFILE_SCHEMA`** (~line 61): rename key; new enum
  `["ask", "manual", "autonomous", "autonomous_with_plan"]` (drops
  `prebuilt_autorun`, renames `never`→`manual`, `prebuilt_approve`→
  `autonomous_with_plan`).
- **`PROFILE_FIELD_INFO`** (~line 191): rename key; replace short + detailed
  strings with the t851 §"New editor strings" drafts:
  - Short: `Manual verification mode: how (or whether) to auto-run the checklist`
  - Detailed (verbatim from t851 plan): the `ask / manual / autonomous /
    autonomous_with_plan` block with `(unset) — same as \`ask\``.
- **`PROFILE_FIELD_GROUPS`** "Manual Verification" entry (~line 315):
  `"manual_verification_auto_mode"` → `"manual_verification_mode"`.

### 3. `.claude/skills/task-workflow/profiles.md` (line 40)
Rewrite the schema-table row: rename key, drop `prebuilt_autorun`, rename
`never`→`manual` / `prebuilt_approve`→`autonomous_with_plan` in the value
list and description column.

### 4. `.claude/skills/task-workflow/manual-verification.md` (Jinja, lines 50–102)
- Comment markers (50, 102) + all `profile.manual_verification_auto_mode`
  refs (50, 70) → `manual_verification_mode`.
- Line 51 `== "never"` → `== "manual"`; update displayed literal.
- Lines 54–58 `== "autonomous"` block: value name unchanged, but update the
  displayed `manual_verification_mode: autonomous` literal in the message.
- Lines 59–63 `== "prebuilt_approve"` → `== "autonomous_with_plan"`; update
  displayed literal. Procedure semantics unchanged (`strategy = "prebuilt"`,
  `approval_required = true`).
- **Lines 64–68 `== "prebuilt_autorun"` branch — DELETE entirely.**
- Line 69 else-branch comment → `{# manual_verification_mode == "ask" or any other value #}`.
- The key-absent `{% else %}` AskUserQuestion block (73–101) is unchanged
  (it never names the key in output).

### 5. `aitasks/t846_..._manual_verification_auto_mode.md` — **no edit**
Confirmed: t846's actionable body already uses the new names; its lines
27–34 correctly frame the old key as the pre-t859 state. Per t851 §5
option (a), leave the file (and its filename) alone.

## Rendered / golden regeneration

Regenerate the affected goldens by re-rendering the source with
`skill_template.py` (same invocation the test uses, `claude` agent):

```bash
source .aitask-scripts/lib/python_resolve.sh; PY="$(require_ait_python)"
G=tests/golden/procs/task-workflow
WF=.claude/skills/task-workflow
for p in default fast remote; do
  "$PY" .aitask-scripts/lib/skill_template.py "$WF/manual-verification.md" \
    aitasks/metadata/profiles/$p.yaml claude > "$G/manual-verification-$p.md"
done
# Incidental pre-existing fix (user-approved): followup-default
"$PY" .aitask-scripts/lib/skill_template.py "$WF/manual-verification-followup.md" \
  aitasks/metadata/profiles/default.yaml claude > "$G/manual-verification-followup-default.md"
```

Expected git diff: only `manual-verification-default.md` (rename in the
autonomous branch + the baseline else→autonomous correction) and
`manual-verification-followup-default.md` (baseline correction) change;
`-fast`/`-remote` re-render byte-identical.

Optionally run `./.aitask-scripts/aitask_skill_rerender.sh default` (and
`fast`/`remote`) to refresh the local gitignored variant dirs so a live
session reflects the rename immediately — not committed, purely local
hygiene.

## Verification

1. `bash tests/test_skill_render_task_workflow.sh` → **0 failures** (was 2).
2. `./.aitask-scripts/aitask_skill_verify.sh` → passes clean.
3. `grep -rn 'manual_verification_auto_mode\|prebuilt_approve\|prebuilt_autorun' .claude/skills/task-workflow/ .aitask-scripts/ aitasks/metadata/`
   → no matches (rendered gitignored variants excluded; archived plans/tasks
   excluded).
4. `python3 -c "import ast; ast.parse(open('.aitask-scripts/lib/profile_editor.py').read())"`
   (or import) → no syntax error.
5. Manual (optional, noted for Step 8c follow-up candidate): `ait settings`
   → `default` profile → Manual Verification group → confirm new key +
   4 values + explainer render with no orphan `prebuilt_autorun`.

## Post-implementation (Step 9)

Single-task parent, working on `main`. Commit code/source files with
`refactor: ... (t859)`; commit the plan file via `./ait git`. Step 8b
(upstream defect) — note the golden-staleness root cause. Step 8c — manual
`ait settings` render check is a good manual-verification follow-up
candidate. No cross-agent port follow-up needed (see Finding 2).

## Final Implementation Notes

- **Actual work done:** Renamed the key `manual_verification_auto_mode` →
  `manual_verification_mode` and its values (`never`→`manual`,
  `prebuilt_approve`→`autonomous_with_plan`, `prebuilt_autorun` dropped)
  across the 4 source sites: `default.yaml`, `profile_editor.py`
  (`PROFILE_SCHEMA` enum, `PROFILE_FIELD_INFO` short+detailed strings
  swapped for the t851 drafts, `PROFILE_FIELD_GROUPS`),
  `task-workflow/profiles.md` (schema row), and
  `task-workflow/manual-verification.md` (Jinja: renamed key/markers,
  `manual` branch, `autonomous_with_plan` branch, deleted the
  `prebuilt_autorun` branch). Regenerated the two affected goldens
  (`manual-verification-default`, plus the incidental
  `manual-verification-followup-default`) and corrected one parity fixture.
- **Deviations from plan:** (1) The parity test
  `tests/test_skill_parity_runtime_vs_rendered.sh:168` was also stale (same
  root cause as the followup golden — `default.yaml` carries
  `manual_verification_followup_mode: never` but the `default` fixture
  expected the key-absent prose). Corrected it to expect the resolved
  `never` branch, consistent with the user-approved followup-golden fix.
  (2) The `default.yaml` rename was committed by a **concurrent `ait`
  process** (commit `9b8bc95c` "ait: Start work on t855") that swept the
  uncommitted working-tree change into its status-update commit on the
  shared `aitask-data` branch. The change is correctly in the committed
  tree; only its commit attribution differs. No re-commit needed.
- **Issues encountered:** Tracked vs gitignored rendered variants: the
  `-default-`/`-fast-` `*-<profile>-` dirs are gitignored (self-refresh on
  invocation), but the headless `-remote-` variants ARE tracked — running
  `aitask_skill_rerender.sh remote` updated the 3 tracked `-remote-`
  `profiles.md` copies (claude/codex/opencode), which are part of the
  commit. Re-rendering all three profiles also cleared the
  `aitask_skill_verify.sh` parity check.
- **Key decisions:** Confirmed the task's "Cross-agent skill ports"
  follow-up is moot — codex/opencode variants render from the single Claude
  authoring source via `aitask_skill_rerender.sh`, not separately authored,
  so no cross-agent follow-up task is needed.
- **Upstream defects identified:**
  - `tests/test_skill_parity_runtime_vs_rendered.sh:168` & goldens
    `manual-verification-followup-default.md` — were stale from the
    t843/t849 era (added `manual_verification_followup_mode: never` /
    `manual_verification_auto_mode: autonomous` to `default.yaml` without
    regenerating goldens/fixtures). Fixed incidentally here.
  - `aitasks/metadata/profiles/default.yaml` — the `default` profile is
    described as "all questions asked normally" yet sets
    `manual_verification_followup_mode: never` and
    `manual_verification_mode: autonomous`, both of which *suppress*
    prompts. Possible design inconsistency worth a separate review (NOT a
    code bug seeded by this task; out of t859 scope).
