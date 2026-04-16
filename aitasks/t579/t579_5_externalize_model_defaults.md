---
priority: high
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [codeagent, ait_settings, model_selection]
created_at: 2026-04-17 00:25
updated_at: 2026-04-17 00:25
---

## Context

Prerequisite refactor for t579_2 (which ships the `aitask-add-model` skill).
Without this, the skill's `promote-mode` must patch four source-code locations
because operational defaults are duplicated between
`aitasks/metadata/codeagent_config.json` and hardcoded fallbacks in Python,
YAML, and bash. After this refactor, promote-mode writes only
`codeagent_config.json` (+ seed) for brainstorm ops. One bash fallback
(`aitask_codeagent.sh:21` `DEFAULT_AGENT_STRING`) is intentionally retained
as the single last-resort global default (also patched by the skill in
promote-mode — one file, one anchored line).

Parent plan: `aiplans/p579_support_for_opus_4_7.md`. Design reference:
`aidocs/model_reference_locations.md` (deliverable of t579_1).

## Key Files to Modify

1. `.aitask-scripts/brainstorm/brainstorm_crew.py` (lines 44-88)
   - Remove `"agent_string"` keys from the hardcoded `BRAINSTORM_AGENT_TYPES`
     dict. Keep only `max_parallel` and `launch_mode` (those are resource-
     tuning defaults, not "default model" choices).
   - Update `get_agent_types()`: `agent_string` MUST come from
     `codeagent_config.json` under the `brainstorm-<type>` key. If missing,
     raise a clear error (or return an empty/sentinel value and let callers
     fail loudly). No silent fallback to a hardcoded model.

2. `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml`
   - Replace the five hardcoded `agent_string:` values with a placeholder
     comment or structural-only schema. Simplest approach: delete the
     `agent_string:` lines entirely and rely on the runtime to populate them
     from config. The file comment already states "This file is a reference
     template — the init script registers types via --add-type flags to ait
     crew init, reading overrides from codeagent_config.json."
   - If the file is never consumed at runtime (confirm via grep), consider
     deleting it entirely and updating any references.

3. `.aitask-scripts/aitask_brainstorm_init.sh` (lines 126-130)
   - Drop the hardcoded `claudecode/opus4_6` / `claudecode/sonnet4_6` second
     argument to `_get_brainstorm_agent_string`. Change to empty-string
     fallback, or remove the `<default>` parameter from
     `_get_brainstorm_agent_string` and error if config misses the key.

4. `tests/test_brainstorm_crew.py` (lines 376, 380, 389, 392-394, 405, 458)
   - Update assertions that pin the hardcoded `BRAINSTORM_AGENT_TYPES`
     `agent_string` values. After refactor, the dict won't have
     `agent_string` — tests should verify values come from config.
   - Add a case: "config missing `brainstorm-<type>` key" → function errors
     (or returns sentinel) rather than silently using a default model.

## Files NOT Changed

- `.aitask-scripts/aitask_codeagent.sh:21+663` — `DEFAULT_AGENT_STRING`
  stays as the global last-resort fallback. Still patched by the future
  skill in promote-mode (single bash line + its human-readable mirror).
- `aitasks/metadata/codeagent_config.json` — no schema change. All the
  required keys (`brainstorm-explorer`, etc.) already exist. `max_parallel`
  stays hardcoded per-type in the Python dict.
- Any `models_*.json` — model registry is untouched.

## Reference Files for Patterns

- `.aitask-scripts/lib/config_utils.py` — `load_layered_config` is what
  `get_agent_types()` already uses.
- `tests/test_brainstorm_crew.py` existing assertions — the pattern to
  update.
- `CLAUDE.md` Shell Conventions — sed/grep/wc/mktemp portability.

## Implementation Plan

### 1. Audit template + init flow
   Quick grep to confirm `crew_meta_template.yaml` is truly unused at
   runtime (referenced only by docs/comments). If unused, plan its deletion
   and any required doc updates.

### 2. Edit `brainstorm_crew.py`
   - Strip `agent_string` from the 5 entries in `BRAINSTORM_AGENT_TYPES`.
   - Rewrite `get_agent_types()` body:
     - Load config (as today)
     - For each agent type, require `brainstorm-<type>` key in
       `config["defaults"]`. If missing, either raise a clear exception OR
       return a dict entry without `agent_string` (document choice in the
       docstring).
     - `launch_mode`: unchanged (hardcoded dict default overridable by
       config key `brainstorm-<type>-launch-mode`).

### 3. Strip/delete `crew_meta_template.yaml`
   Preferred: delete and remove references. If kept, strip
   `agent_string:` lines so the file is structural-only.

### 4. Edit `aitask_brainstorm_init.sh` lines 126-130
   - Change each `--add-type` line so it no longer passes a hardcoded
     fallback to `_get_brainstorm_agent_string`.
   - Update `_get_brainstorm_agent_string` (lines earlier in the file) to
     error out / exit non-zero if config lookup returns empty AND no
     fallback is provided.

### 5. Update `tests/test_brainstorm_crew.py`
   - Replace assertions pinning hardcoded `agent_string` values with
     config-lookup assertions (use a fixture `codeagent_config.json` with
     known values).
   - Add new case: "missing config key raises/errors clearly".

### 6. Verification
   - `bash tests/test_brainstorm_crew.py` (or `python tests/test_brainstorm_crew.py`)
     passes with the updated assertions.
   - `shellcheck .aitask-scripts/aitask_brainstorm_init.sh` passes.
   - Manual smoke: `ait crew init --help` still shows the same interface.
   - Manual smoke: invoke brainstorm init on a trivial task and confirm
     the crew registers types with the config-resolved agent strings.

## Verification Steps

1. `shellcheck .aitask-scripts/aitask_brainstorm_init.sh` exits 0
2. `bash tests/test_brainstorm_crew.py` passes (or equivalent runner)
3. `grep -rn 'claudecode/opus4_6' .aitask-scripts/brainstorm/ \
     .aitask-scripts/aitask_brainstorm_init.sh` — no matches remain
   (only comments/docstrings acceptable)
4. `grep -rn 'claudecode/sonnet4_6' .aitask-scripts/brainstorm/ \
     .aitask-scripts/aitask_brainstorm_init.sh` — no matches remain
5. `grep -n 'DEFAULT_AGENT_STRING' .aitask-scripts/aitask_codeagent.sh`
   — still present on line 21 (intentionally retained)
6. `./ait crew init --help` still shows the same user-facing interface
7. Running brainstorm init end-to-end on a trivial task succeeds and the
   resulting crew's agent_strings match `codeagent_config.json`

## Commit

Single commit (all source code):
```
refactor: Externalize brainstorm agent defaults to codeagent_config.json (t579_5)
```

## Step 9 (Post-Implementation)

Archive via `./.aitask-scripts/aitask_archive.sh 579_5`. The archived plan
serves as the reference for t579_2 (which builds on this refactor's
simpler default-handling model).
