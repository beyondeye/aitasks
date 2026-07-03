---
priority: medium
effort: medium
depends: [635_24, 635_30]
issue_type: feature
status: Ready
labels: [gates]
anchor: 635
created_at: 2026-07-03 12:41
updated_at: 2026-07-03 12:41
---

## Context

Extracted from **t635_29** (procedure_gate_generalization) at planning time — the
per-gate code-agent/model selection concern was split out because it composes with
two settings-TUI surfaces that are not yet landed, and building it first would
duplicate/collide with them. t635_29 keeps only the ripe core (async/headless
dispatch + agent-aware resolution).

Procedure-backed gates (`kind: procedure`, e.g. `docs_updated`) today run in the
**current session agent's** context. This task lets each proper gate be configured
to run under a **chosen code-agent + model** instead of the session default, with a
**settings-TUI** surface — general to all proper gates, not just procedure gates.

## Scope

1. **Per-gate agent/model in the registry.** Add a per-gate field (e.g.
   `agent_string: "claudecode/opus4_8"`, or split `agent:` / `model:`) to
   `aitasks/metadata/gates.yaml`; parse it in
   `.aitask-scripts/lib/gate_ledger.py` `read_registry`.
2. **Dispatch resolves + honors it.** The gate orchestrator / task-workflow dispatch
   resolves a gate's configured agent/model before running its verifier. Running a
   **different** agent than the session means spawning a sub-agent via the
   `aitask_skillrun.sh --agent-string <agent>/<model>` seam (heavy) — decide the
   attended-vs-headless mechanics at plan time. Note `agy` has **no** model flag
   ([[project_agy_cli_no_model_flag]]) — treat as unsupported / base-model only.
3. **Settings-TUI surface.** Add a per-gate agent/model editor reusing
   `AgentModelPickerScreen` (`.aitask-scripts/settings/agent_model_picker.py`).
   **Compose** with t635_24's profile/registry gate-config surface and t635_30's
   per-task `gates:` editor — do NOT duplicate; the three gate surfaces must share
   layout/entry points rather than collide.

## Depends / Coordination

- **t635_24** (settings-TUI profile/registry gate config) — the gate-config surface
  this per-gate agent/model editor composes into.
- **t635_30** (per-task `gates:` editing surface) — the per-task gate editor this
  must not duplicate in the settings TUI.
- Builds on **t635_29** (procedure-gate core: agent-aware dispatch resolution).
- Reference: `.aitask-scripts/agent_string.sh` (`get_cli_binary` / `get_model_flag`
  / `get_cli_model_id`), `models_<agent>.json`, `codeagent_config.json` defaults.

## Verification (define fully at pick time)

- A gate with a configured agent/model runs its verifier under that agent/model;
  absent config falls back to the session/operation default.
- Settings TUI edits the per-gate agent/model and persists to `gates.yaml`; the
  surface composes with the t635_24 / t635_30 gate surfaces (no duplicate panels).
- Unit tests for registry parse of the new field + resolution precedence.
