---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1595
followup_kind: risk_mitigation
created_at: 2026-08-25 18:30
updated_at: 2026-08-25 18:35
---

## Origin

Risk-mitigation ("after") follow-up for t1607, created at Step 8d after implementation landed.

## Risk addressed

Guard unreachable on already-configured and legacy-mode projects. From t1607's plan `## Risk` →
goal-achievement risk:

> The guard is **unreachable in this repo and in every already-configured project**:
> `update_claudemd_git_section` is called only from `setup_data_branch` Step 8
> (`aitask_setup.sh:1661`), which early-returns when `.aitask-data/.git` exists and when the
> user declines the data branch. So the fix is verified by direct function invocation and
> fixtures, not by running `ait setup`, and the underlying lifecycle defect (CLAUDE.md never
> refreshed on re-runs, never written at all in legacy mode — unlike `AGENTS.md`, regenerated
> unconditionally by `update_agentsmd` from `setup_code_agents`) survives this task.
> · severity: medium

## Goal

Move `update_claudemd_git_section` out of `setup_data_branch` Step 8 to beside `update_agentsmd`
in `setup_code_agents`, so `CLAUDE.md` is regenerated on every `ait setup` — the same lifecycle
`AGENTS.md` already has — with coverage for re-runs and legacy mode.

## Evidence (verified during t1607)

- `.aitask-scripts/aitask_setup.sh:1660-1661` — `# --- Step 8: Update CLAUDE.md ---` followed by
  an unconditional `update_claudemd_git_section "$project_dir"`, but **inside** `setup_data_branch()`.
- `setup_data_branch()` early-returns before ever reaching Step 8 in three cases:
  - not a git repo (`:1390-1392`);
  - **`.aitask-data/.git` already exists** (`:1395-1398`) — the common case on every re-run, and
    why this repo's own `CLAUDE.md` is markerless;
  - the user declines the data-branch prompt (`:1435-1440`) — i.e. legacy mode, where the block
    is never written at all.
- By contrast `update_agentsmd` is called from `setup_code_agents` (`:2535`) unconditionally,
  which is why `AGENTS.md` stays current while `CLAUDE.md` does not.

## Scope notes

- t1607 restored the hand-maintained skip guard in `update_claudemd_git_section`
  (`CLAUDEMD_HAND_MAINTAINED_SENTINEL`); that guard is correct but currently near-unreachable.
  This task makes it reachable. Do not undo it — see `tests/test_agent_instructions.sh`
  T12b/T12c/T12d/T38/T39 and `aidocs/framework/aitasks_extension_points.md`.
- Check the commit path when moving the call: `setup_data_branch` Step 9 (`:1662-1683`) adds
  `CLAUDE.md` explicitly. Outside that function, `_ait_framework_paths` (`:2962`) already lists
  `CLAUDE.md`, so `commit_framework_files` should cover it — verify rather than assume.
- Verify the ordering of `setup_data_branch` vs `setup_code_agents` in `main()` still leaves
  `CLAUDE.md` committed exactly once.

## Verification

- New/extended coverage in `tests/test_agent_instructions.sh` or `tests/test_data_branch_setup.sh`:
  - `ait setup` re-run on an already-configured project refreshes a marker-managed `CLAUDE.md`.
  - legacy mode (data branch declined) still writes the block on first setup.
  - the t1607 hand-maintained guard still fires on both paths (T12b's assertions must stay green).
- `bash tests/test_agent_instructions.sh` and `bash tests/test_data_branch_setup.sh`.
- `shellcheck .aitask-scripts/aitask_setup.sh`.
