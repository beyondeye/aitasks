---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [installation, install_scripts, model_selection]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt5_5
created_at: 2026-06-12 18:14
updated_at: 2026-06-14 09:48
---

## Problem

Newly registered code-agent models in `seed/models_*.json` never reach **existing**
projects on `ait upgrade`. Example: Fable 5 (`claude-fable-5`, registered in seed by
t966, shipped in v0.24.0) is absent from a downstream project's
`aitasks/metadata/models_claudecode.json` even after that project upgraded to
v0.24.0. The model then resolves as `AGENT_STRING_FALLBACK:claudecode/claude-fable-5`
in plan-verified / attribution flows, and per-model verified stats can't accumulate
under the proper `fable5` name.

## Root cause

- `ait upgrade` → `aitask_upgrade.sh` runs `install.sh --force` (FORCE=true), which
  calls `install_seed_models()` → `merge_seed json seed/models_*.json
  aitasks/metadata/models_*.json` (install.sh ~line 441-456).
- `merge_seed` (install.sh ~line 255) delegates to
  `.aitask-scripts/aitask_install_merge.py json <src> <dest>`.
- `aitask_install_merge.py` `merge_json()` does a `deep_merge` with **dest winning**
  and, per its own docstring, "Lists are treated atomically — not merged
  element-wise". The models files have shape `{"models": [ {name, cli_id, ...} ]}`.
  Both src and dest always have the `models` key, so the dest list wins wholesale and
  **new seed entries are silently dropped**.
- Fresh installs are unaffected (dest missing → plain copy). Only upgrades of
  existing projects lose new models.

## Fix

Teach the install merge to union the `models` arrays by key:

- Add a keyed-list merge mode (e.g. `json-models` in `aitask_install_merge.py`
  MODES, or special-case the `models` key in `merge_json`): entries are identified
  by `name` (fall back to `cli_id`); existing dest entries win unchanged (this
  preserves per-project `verified` / `verifiedstats` data); seed entries whose key
  is absent from dest are appended (preserving seed order for the new ones).
- Wire it up in `install.sh install_seed_models()` (and keep
  `install_seed_codeagent_config()` on plain `json` merge — its `defaults` dict
  merge semantics are correct as-is; promoting a new default model remains an
  explicit/manual decision).
- Consider the same treatment for any other seed JSON whose payload is a
  keyed list (audit `merge_seed` call sites).

## Verification

- Unit-style test: dest with old models + local verifiedstats, src with one new
  model → merged file contains the union, dest entries byte-identical in content,
  new entry appended.
- End-to-end: in a project whose `models_claudecode.json` lacks `fable5`, run
  `ait upgrade` (or `install.sh --force --dir <proj>`) and confirm `fable5`
  appears while existing `verified`/`verifiedstats` values are untouched.
- Regression: re-run upgrade — idempotent (no duplicates).
