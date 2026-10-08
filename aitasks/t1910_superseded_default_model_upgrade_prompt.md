---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [codeagent, models, model_selection, install_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-07 08:46
updated_at: 2026-10-08 15:51
---

## Goal

When a framework release adds a new Claude Code / Codex (/ OpenCode) model and
promotes it as the default for one or more code-agent operations, a user who
upgrades should be **offered** the new default — but only for operations whose
currently configured model is one the new model *supersedes*. One confirm
question per superseded model ("Your defaults for `pick`, `explore`, `learn`
use `claudecode/opus5`, which is superseded by `claudecode/opus5_5`. Switch?").
Operations deliberately set to a non-superseded model are never touched.

This is explicitly **not** "overwrite user defaults with the new framework
defaults" — that would discard deliberate choices.

## Current state (exploration findings)

- `ait upgrade` (`.aitask-scripts/aitask_upgrade.sh`) downloads the target
  version's `install.sh` and runs it with `--force`. `install_seed_codeagent_config`
  calls `merge_seed json` → `aitask_install_merge.py merge_json`, which
  deep-merges with **dest winning**: only missing op keys are added. An old
  default value (e.g. `claudecode/opus4_8`) therefore persists forever.
- `install_seed_models` uses `merge_json_models`: existing dest model entries are
  preserved **unchanged**; only seed-only entries are appended. Consequence: a
  new framework-owned field (e.g. `superseded_by`) added to an *existing* model
  entry in `seed/models_*.json` would never reach the user's
  `aitasks/metadata/models_*.json`. Either the merge must refresh
  framework-owned fields, or supersession data must live somewhere that is
  framework-owned (overwritten each install), or the check must read `seed/`
  before `install.sh` runs `rm -rf "$INSTALL_DIR/seed"`.
- Model entries carry only `name, cli_id, notes, verified, verifiedstats`
  (OpenCode adds `status: active|unavailable`, consumed by
  `aitask_codeagent.sh` list-models and `lib/agent_model_picker.py`). No
  supersession / lineage metadata exists anywhere.
- Default resolution (`aitask_codeagent.sh resolve_agent_string`):
  1. `--agent-string` flag
  2. `aitasks/metadata/codeagent_config.local.json` (per-user, gitignored)
  3. `aitasks/metadata/codeagent_config.json` (per-project, git-tracked)
  4. `DEFAULT_AGENT_STRING` in `.aitask-scripts/lib/agent_string.sh`
     (framework code — overwritten on upgrade, already fine).
  Layers 2 and 3 are both user-editable and both must be checked. The project
  config can hold op keys the seed does not (e.g. the `brainstorm-*` ops), so
  the check must scan **all** keys under `.defaults`, not just seed keys.
- `aitask_add_model.sh promote-config` (driven by the `aitask-add-model` skill)
  patches `.defaults[op]` in this repo's config + seed but records **nothing**
  about the model it replaced — the information needed to build a supersession
  chain is lost at promote time.
- `install.sh` already gates its interactive prompts on `[[ -t 0 ]]`; the
  `curl | bash` / non-tty path must not block.
- `aitask_setup.sh` (`ait setup`) also copies `codeagent_config.json` /
  `models_*.json` from seed on fresh setups (~line 2214).

## Proposed design (to be validated in planning)

1. **Supersession metadata.** Record "model A is superseded by model B" per
   agent. Options to decide in planning:
   - a `superseded_by: "<agent>/<name>"` field on the older entry in
     `models_<agent>.json` **plus** a merge change so framework-owned fields of
     existing entries are refreshed on upgrade; or
   - a separate framework-owned file (e.g. `seed/model_supersessions.json` →
     installed/overwritten, never merged) mapping old → new.
   Supersession is a chain: resolve to the terminal (newest) model, and guard
   against cycles. Cross-agent supersession is out of scope unless trivial.
2. **Record at promote time.** `aitask_add_model.sh promote-config` (and the
   `aitask-add-model` skill's promote mode) captures the model(s) previously
   assigned to the promoted ops and writes the supersession entry. Variants such
   as `_1m` context siblings need an explicit rule (e.g. `opus5_1m` →
   `opus5_5_1m`, not → `opus5_5`).
3. **Backfill** the historical chain from git history of
   `seed/codeagent_config.json` (commits t1241, t1242, t1865, t1866, t1886):
   e.g. opus4_x → opus5 → opus5_5, sonnet4_6 → sonnet5 → sonnet5_5, codex
   GPT-6 → gpt6_1_sol for shadow/discuss. Verify each against the commit, do not
   infer.
4. **Check + prompt.** A new helper (e.g. `aitask_model_supersession.sh` or a
   `ait codeagent check-superseded` verb) that, for each of the two config
   layers, groups ops by superseded model and asks one confirm per model:
   switch all listed ops / keep. Writes only the accepted keys. Run it:
   - at the end of the upgrade flow (after the seed model/config installers,
     before `seed/` is deleted if it needs seed data), tty-gated;
   - non-tty: print a report and the command to re-run interactively;
   - also runnable on demand (and possibly from `ait setup`).
5. **Respect "keep".** A declined supersession must not be re-asked on every
   upgrade (e.g. record the acknowledged pair in the local layer, or ask again
   only when the chain's terminal model changes). Decide in planning.
6. **Commit behaviour.** `codeagent_config.json` is git-tracked: an accepted
   switch must be committed the way install.sh commits framework files (or left
   for the user with a clear message); the `.local.json` layer is gitignored.

## Out of scope / follow-ups to suggest

- Settings TUI surfacing of superseded defaults (`settings_app.py`,
  `lib/agent_model_picker.py`) — possible later task.
- Per CLAUDE.md: once the Claude `aitask-add-model` skill changes, suggest
  separate tasks to port it to the Codex / OpenCode skill trees.

## Verification

- Unit tests for chain resolution (multi-hop, cycle, unknown model, `_1m`
  variants) and for the merge/installation path actually delivering the
  supersession data to an existing user install.
- Test that a non-superseded custom default is never offered a switch, that a
  superseded default in **both** layers is offered per layer, that "keep" is
  not re-asked, and that the non-tty path does not block.
- Docs: update the website page covering `ait upgrade` / code-agent model
  configuration, and the `aitask-add-model` skill description of promote mode.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-08T12:51:35Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-08T13:58:23Z status=pass attempt=1 type=human
