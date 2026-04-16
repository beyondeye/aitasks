---
Task: t579_5_externalize_model_defaults.md
Parent Task: aitasks/t579_support_for_opus_4_7.md
Sibling Tasks: aitasks/t579/t579_2_*.md, aitasks/t579/t579_3_*.md, aitasks/t579/t579_4_*.md
Archived Sibling Plans: aiplans/archived/p579/p579_*_*.md
Worktree: (none — profile fast sets create_worktree: false)
Branch: main
Base branch: main
---

# Plan: t579_5 — Externalize brainstorm agent defaults

## Context

Prerequisite refactor for t579_2 (which ships the `aitask-add-model` skill).
Without this, promote-mode has to patch 4 source-code locations for
brainstorm ops. After this refactor, promote-mode writes only
`aitasks/metadata/codeagent_config.json` (+ seed) for brainstorm ops.
`aitask_codeagent.sh:21` `DEFAULT_AGENT_STRING` intentionally stays as the
single last-resort global fallback (one anchored line the skill can still
patch trivially in promote-mode).

Current duplication map (from `aidocs/model_reference_locations.md`):
- `brainstorm_crew.py:44-50` — `BRAINSTORM_AGENT_TYPES` dict with
  `agent_string` values duplicated from config
- `crew_meta_template.yaml:6-20` — same values repeated as a
  **reference template** per the file's own top comment
- `aitask_brainstorm_init.sh:126-130` — same values repeated as fallback
  args to `_get_brainstorm_agent_string`

All three sets are static mirrors of the values already in
`codeagent_config.json`'s `brainstorm-<type>` keys. Goal: make the config
the sole source of truth for `agent_string` while leaving non-config
resource fields (`max_parallel`) hardcoded.

## Scope

### 1. `.aitask-scripts/brainstorm/brainstorm_crew.py`

Current dict (lines 44-50):
```python
BRAINSTORM_AGENT_TYPES = {
    "explorer": {"agent_string": "claudecode/opus4_6", "max_parallel": 2, "launch_mode": "headless"},
    "comparator": {"agent_string": "claudecode/sonnet4_6", "max_parallel": 1, "launch_mode": "headless"},
    ...
}
```

Target dict (no `agent_string`):
```python
BRAINSTORM_AGENT_TYPES = {
    "explorer": {"max_parallel": 2, "launch_mode": "headless"},
    "comparator": {"max_parallel": 1, "launch_mode": "headless"},
    "synthesizer": {"max_parallel": 1, "launch_mode": "headless"},
    "detailer": {"max_parallel": 1, "launch_mode": "interactive"},
    "patcher": {"max_parallel": 1, "launch_mode": "headless"},
}
```

Rewrite `get_agent_types()` (lines 52-88):
- Keep `load_layered_config` call.
- For each agent type, `agent_string` MUST come from
  `config["defaults"]["brainstorm-<type>"]`. If the key is missing or the
  config file is unreadable, raise `RuntimeError` with a clear message
  (e.g., `"missing codeagent_config.json default for brainstorm-explorer; run 'ait setup' or add the key manually"`).
- `launch_mode`: unchanged (hardcoded default overridable by config key
  `brainstorm-<type>-launch-mode`).
- Update the docstring to describe the new contract.

### 2. `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml`

Confirm non-consumption first:
```bash
grep -rn 'crew_meta_template' .aitask-scripts/ tests/ website/ aidocs/
```
Expect only the Python `TEMPLATE_DIR = Path(__file__).parent / "templates"`
reference and the file's self-referential comment. If nothing reads the
YAML at runtime, **delete the file** and remove the `TEMPLATE_DIR` reference
if it becomes unused. If the template is referenced elsewhere (e.g. by
`aitask_crew_init.sh` or docs), strip the five `agent_string:` lines and
leave a schema-only template with a note pointing at `codeagent_config.json`.

### 3. `.aitask-scripts/aitask_brainstorm_init.sh`

Change lines 126-130 from:
```bash
--add-type "explorer:$(_get_brainstorm_agent_string explorer claudecode/opus4_6):$(_get_brainstorm_launch_mode explorer)" \
--add-type "comparator:$(_get_brainstorm_agent_string comparator claudecode/sonnet4_6):$(_get_brainstorm_launch_mode comparator)" \
...
```
To:
```bash
--add-type "explorer:$(_get_brainstorm_agent_string explorer):$(_get_brainstorm_launch_mode explorer)" \
--add-type "comparator:$(_get_brainstorm_agent_string comparator):$(_get_brainstorm_launch_mode comparator)" \
...
```

Update `_get_brainstorm_agent_string` (earlier in the same file) so the
second argument becomes optional; if both config lookup and fallback are
empty, `die` with a clear error. (Keep backwards-compat: if a fallback is
still passed, it still works.)

### 4. `tests/test_brainstorm_crew.py`

Update the 6-7 assertion sites that pin specific `agent_string` values
(lines 376, 380, 389, 392-394, 405, 458):
- Where tests currently assert `BRAINSTORM_AGENT_TYPES["explorer"]["agent_string"] == "claudecode/opus4_6"`, update to assert the field is ABSENT from the dict.
- Where tests currently assert `get_agent_types()["explorer"]["agent_string"] == "claudecode/opus4_6"`, change to use a fixture `codeagent_config.json` with known values and assert `== <fixture value>`.
- Add a new case: `get_agent_types()` raises `RuntimeError` when the
  config is missing a `brainstorm-<type>` key.

## Implementation Order

1. Audit `crew_meta_template.yaml` usage. Record findings in this file's
   Final Implementation Notes.
2. Edit `brainstorm_crew.py` (dict + `get_agent_types()`).
3. Delete or strip `crew_meta_template.yaml` based on step 1 result.
4. Edit `aitask_brainstorm_init.sh` (lines 126-130 + helper function).
5. Update `tests/test_brainstorm_crew.py` assertions and add the
   config-missing case.
6. Run verification commands (next section).

## Verification

1. `shellcheck .aitask-scripts/aitask_brainstorm_init.sh` exits 0
2. `python tests/test_brainstorm_crew.py` (or its configured runner)
   passes — all updated assertions pass, new config-missing case passes
3. `grep -rn 'claudecode/opus4_6\|claudecode/sonnet4_6' \
     .aitask-scripts/brainstorm/ .aitask-scripts/aitask_brainstorm_init.sh` —
   no code matches (comments/docstrings acceptable)
4. `grep -n 'DEFAULT_AGENT_STRING' .aitask-scripts/aitask_codeagent.sh` —
   still present on line 21 (intentionally retained)
5. `./ait crew init --help` still shows the same user-facing interface
6. End-to-end smoke: pick a trivial task, run brainstorm init, and
   confirm the resulting crew's agent_strings match
   `aitasks/metadata/codeagent_config.json`'s `brainstorm-<type>` values
7. Resolve sanity: `./ait codeagent resolve brainstorm-explorer` still
   returns `claudecode/opus4_6` (or whatever config currently says) —
   no regression in the resolve path

## Commit

Single source-code commit (no metadata touched):
```
refactor: Externalize brainstorm agent defaults to codeagent_config.json (t579_5)
```

## Step 9 (Post-Implementation)

Archive via `./.aitask-scripts/aitask_archive.sh 579_5`. The archived
plan's "Final Implementation Notes" becomes the reference for t579_2's
simplified skill scope (one less subcommand, one less set of tests,
smaller manual-review list).
