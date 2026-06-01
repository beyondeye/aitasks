---
priority: high
effort: high
depends: [t891_1]
issue_type: refactor
status: Ready
labels: [ait_brainstorm, brainstom_modules, remove_support]
created_at: 2026-06-01 10:52
updated_at: 2026-06-01 10:52
---

# t891_2 — Ops/agents removal: retire detail/patch + detailer/patcher

> **⚠️ DEFERRED — gated on the t756 chain (auto-depends on t891_1, which depends
> on 756).** Do NOT implement until t756 lands. By execution time the module
> operations (`module_decompose`, `module_sync` + wizards) already exist, built
> using `detail`/`patch` as the model — so this is pure removal of the
> now-redundant plan layer, not a port. **Re-verify every code anchor below
> against the as-landed codebase** — file:line anchors are a 2026-06-01
> pre-modules snapshot and WILL drift. Anchors are given by symbol/op name;
> locate by name, not by line.

## Context

Retire the `detail` and `patch` brainstorm operations and the detailer/patcher
agents that back them. This is the first of three code-removal children. Order
matters: it auto-depends on t891_1 (docs) and is itself depended on by t891_3
(schema/TUI) and t891_4 (finalize) — the chain is sequential to avoid conflicts
in the overlapping brainstorm modules. `ait brainstorm` is unshipped → remove
outright, no back-compat.

## Key files to modify (locate symbols by name; verify they still exist)

- `.aitask-scripts/brainstorm/brainstorm_schemas.py`
  - `GROUP_OPERATIONS` — remove `"detail"` and `"patch"` entries.
- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `_NODE_SELECT_OPS` — remove `detail`/`patch`.
  - `_WIZARD_OP_TO_AGENT_TYPE` — remove `detail→detailer`, `patch→patcher`.
  - `_DESIGN_OPS` — remove the `detail`/`patch` tuples.
  - `_OPERATION_HELP` — remove the `detail` and `patch` help entries.
  - `_execute_design_op` — remove the `detail` and `patch` dispatch branches
    (the `register_detailer()` / `register_patcher()` calls and the
    `_register_detailer_target` / `_register_patcher_source` wiring).
  - Poll/auto-apply infra: `_ensure_detailer_poll_timer`, `_stop_detailer_poll_timer`,
    `_poll_detailers`, `_try_apply_detailer_if_needed`, `_scan_existing_detailers`,
    and the patcher equivalents (`_ensure/_stop_patcher_poll_timer`,
    `_poll_patchers`, `_try_apply_patcher_if_needed`); plus the instance state
    (`_detailer_targets`, `_detailer_poll_timer`, `_patcher_sources`,
    `_patcher_poll_timer`) and their initializations.
  - The detail-specific wizard confirm step and any `_wizard_op == "detail"` /
    `== "patch"` branches (NOTE: the patch-wizard `_node_has_plan` gating is
    removed in t891_3 — coordinate; removing the patch op here makes that gate
    dead).
- `.aitask-scripts/brainstorm/brainstorm_crew.py`
  - `register_detailer`, `register_patcher`, `_assemble_input_detailer`,
    `_assemble_input_patcher`; the `detailer`/`patcher` keys in
    `BRAINSTORM_AGENT_TYPES`. Leave the `compare`/comparator path; if it reads a
    plan via `read_plan`, drop only that now-dead read (the `read_plan` symbol
    itself is removed in t891_3).
- `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `apply_detailer_output`, `apply_patcher_output`, and their helpers
    (`_detailer_needs_apply`, `_patcher_needs_apply`, `_parse_patcher_output`,
    `_write_patcher_plan_file`) and the `_DETAILER_DELIMITERS` /
    `_PATCHER_DELIMITERS` constants.
- `.aitask-scripts/brainstorm/brainstorm_dag_display.py`
  - `OP_BADGE_STYLES` — remove the `detail`/`patch` op-badge styles.
- Delete entirely: `.aitask-scripts/aitask_brainstorm_apply_detailer.sh`,
  `.aitask-scripts/aitask_brainstorm_apply_patcher.sh`,
  `.aitask-scripts/brainstorm/templates/detailer.md`,
  `.aitask-scripts/brainstorm/templates/patcher.md`.

## Must preserve (do NOT remove)

- The section-marker / dimension-link machinery reworked by t873 (shared with
  proposals).
- `explore`, `compare`, `synthesize` ops and their agents.
- The `plan_file` field / `read_plan` / `PLANS_DIR` / Plan-tab / badge removal is
  **t891_3's** job — don't pre-empt it; just remove the detail/patch *consumers*.

## Implementation plan

1. Re-verify the symbol inventory against the as-landed code (modules added by
   t756 may have shifted line numbers and possibly added module-op badge styles —
   leave those).
2. Remove ops from `GROUP_OPERATIONS` first, then the dispatch/wizard/poll infra
   in `brainstorm_app.py`, then the crew registrations, then the session apply
   functions, then badges/templates/helper scripts.
3. Run a grep for residual `detail`/`patch`/`detailer`/`patcher` references and
   clean dead imports.

## Verification

- `grep -rn "detailer\|patcher\|\"detail\"\|\"patch\"" .aitask-scripts/brainstorm/`
  returns only intentional matches (e.g. unrelated substrings), no live wiring.
- `python -c "import ast,glob; [ast.parse(open(f).read()) for f in glob.glob('.aitask-scripts/brainstorm/*.py')]"`
  parses cleanly (no NameErrors from removed symbols — also run the brainstorm
  test suite if present).
- Launch `ait brainstorm` (manual): the operation menu no longer offers Detail or
  Patch; explore/compare/synthesize still work; no poll-timer errors in logs.
- The deleted shell scripts and templates are gone; `aitask_skill_verify.sh`
  (if it covers them) passes.
