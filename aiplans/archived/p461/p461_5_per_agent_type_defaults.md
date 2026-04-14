---
Task: t461_5_per_agent_type_defaults.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/t461/t461_6_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md, aiplans/archived/p461/p461_2_*.md, aiplans/archived/p461/p461_3_*.md, aiplans/archived/p461/p461_4_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_5 — Per-agent-type `launch_mode` defaults

## Context

Siblings t461_1–t461_4 added the end-to-end plumbing for a per-agent
`launch_mode` (headless|interactive): addwork accepts `--launch-mode`,
setmode can mutate it, the runner resolves it when launching, the
brainstorm wizard exposes a toggle, and the status tab lets users edit
it post-creation. What's missing is the **per-agent-type default layer**:
every brainstorm agent currently starts `headless` unless the user
explicitly toggles or edits. The `detailer` in particular produces a
long inner-loop plan the user wants to watch live, so making the user
remember to flip the toggle every time is tedious.

This task adds the missing layer so that `_crew_meta.yaml` carries a
`launch_mode` per agent type, the runner already reads it (t461_1 wired
the lookup), and the wizard's initial value reflects the type default.

## Current state (verified 2026-04-14)

1. **Runner resolution — DONE (t461_1).**
   `agentcrew_runner.py:419-427` already has the exact fallback chain:
   ```python
   type_config = agent_types_config.get(atype, {})
   # Resolve launch mode: per-agent yaml > per-type config (t461_5) > framework default
   launch_mode = (
       agent_data.get("launch_mode")
       or type_config.get("launch_mode")
       or "headless"
   )
   ```
   Nothing to change here — verified in place.

2. **`aitask_crew_init.sh` emitter — HARDCODED, no launch_mode.**
   Lines 82-87 validate `--add-type` as `type_id:agent_string` (first
   colon only). Lines 115-122 build the YAML block with `agent_string`
   and `max_parallel: 0` hardcoded. No `launch_mode` field.

3. **`aitask_brainstorm_init.sh` — PASSES no launch_mode.**
   Lines 111-121 call `aitask_crew_init.sh --add-type` with only
   `type:agent_string`. Helper `_get_brainstorm_agent_string` (lines
   88-107) resolves `agent_string` via `codeagent_config.json`; no
   parallel helper for launch_mode.

4. **`BRAINSTORM_AGENT_TYPES` — MISSING launch_mode keys.**
   `brainstorm/brainstorm_crew.py:39-45` has only `agent_string` and
   `max_parallel` per entry. `get_agent_types()` (lines 48-71) overlays
   `agent_string` from `codeagent_config.json` but doesn't touch
   `launch_mode`.

5. **`_run_addwork()` redundancy filter — NOT YET USING TYPE DEFAULT.**
   `brainstorm/brainstorm_crew.py:111-112` currently emits
   `--launch-mode interactive` whenever the wizard asks for
   interactive, regardless of the per-type default. Headless requests
   are silently omitted. A proper redundancy filter should compare the
   wizard value against the per-type default and emit only on mismatch
   — so a "detailer + interactive" call (which matches the type
   default) does not write a redundant override into the status yaml.

6. **Wizard default helper — ALREADY READS FROM `BRAINSTORM_AGENT_TYPES`.**
   `brainstorm_app.py:122-127` defines:
   ```python
   def _brainstorm_launch_mode_default(wizard_op: str) -> str:
       from brainstorm.brainstorm_crew import BRAINSTORM_AGENT_TYPES
       agent_type = _WIZARD_OP_TO_AGENT_TYPE.get(wizard_op, "")
       return BRAINSTORM_AGENT_TYPES.get(agent_type, {}).get(
           "launch_mode", "headless"
       )
   ```
   It gracefully degrades to `"headless"` today. As soon as t461_5
   populates `launch_mode` in the dict, `detailer` will start returning
   `"interactive"` automatically. No change needed here.

## Files to modify

1. `.aitask-scripts/brainstorm/brainstorm_crew.py` — add `launch_mode`
   to `BRAINSTORM_AGENT_TYPES` entries; fix `_run_addwork()` redundancy
   filter.
2. `.aitask-scripts/aitask_crew_init.sh` — accept optional third
   colon-separated field on `--add-type` (`type_id:agent_string:mode`),
   validate it, emit `launch_mode` into the YAML block.
3. `.aitask-scripts/aitask_brainstorm_init.sh` — add
   `_get_brainstorm_launch_mode()` helper that reads from
   `BRAINSTORM_AGENT_TYPES` via a Python one-liner, then extend the
   five `--add-type` args to include launch_mode per type.

## Implementation steps

### Step 1 — Populate `BRAINSTORM_AGENT_TYPES`

In `.aitask-scripts/brainstorm/brainstorm_crew.py:39-45`, add
`launch_mode` per entry:

```python
BRAINSTORM_AGENT_TYPES = {
    "explorer":    {"agent_string": "claudecode/opus4_6",   "max_parallel": 2, "launch_mode": "headless"},
    "comparator":  {"agent_string": "claudecode/sonnet4_6", "max_parallel": 1, "launch_mode": "headless"},
    "synthesizer": {"agent_string": "claudecode/opus4_6",   "max_parallel": 1, "launch_mode": "headless"},
    "detailer":    {"agent_string": "claudecode/opus4_6",   "max_parallel": 1, "launch_mode": "interactive"},
    "patcher":     {"agent_string": "claudecode/sonnet4_6", "max_parallel": 1, "launch_mode": "headless"},
}
```

Rationale: detailer is the "inner loop" of brainstorm — it produces the
long plan the user wants to watch live. Others run in parallel and
would clutter tmux with windows.

No change needed to `get_agent_types()` — its deep-copy already carries
the new key through. `launch_mode` is not config-overridable via
`codeagent_config.json` in this iteration (scope: minimal, see
follow-up task t461_7).

### Step 2 — Redundancy filter in `_run_addwork()`

In `.aitask-scripts/brainstorm/brainstorm_crew.py`, replace lines
111-112 with a redundancy filter that emits `--launch-mode` only when
the wizard value differs from the per-type default:

```python
type_default = BRAINSTORM_AGENT_TYPES.get(agent_type, {}).get(
    "launch_mode", "headless"
)
if launch_mode != type_default:
    cmd.extend(["--launch-mode", launch_mode])
```

Effect:
- Wizard "interactive" + detailer (type default interactive) → no
  `--launch-mode` flag → status yaml has no per-agent override → runner
  falls through to type config → launches interactive. Clean.
- Wizard "headless" + detailer → `--launch-mode headless` emitted →
  override stored on the agent → runner respects it.
- Wizard "interactive" + explorer (type default headless) →
  `--launch-mode interactive` emitted → override stored → interactive.

### Step 3 — Extend `--add-type` parsing in `aitask_crew_init.sh`

**3a. Update validation regex** at line 84. Allow optional third
colon-separated field:
```bash
if ! [[ "$at" =~ ^[a-z0-9_]+:[^:]+(:(headless|interactive))?$ ]]; then
    die "Invalid --add-type format '$at': expected type_id:agent_string[:launch_mode] (e.g., impl:claudecode/opus4_6 or detailer:claudecode/opus4_6:interactive)"
fi
```

**3b. Update the emitter loop** at lines 115-122 to parse three fields
and emit `launch_mode` when present:
```bash
for at in "${ADD_TYPES[@]}"; do
    IFS=':' read -r local_type_id local_agent_string local_launch_mode <<< "$at"
    AGENT_TYPES_YAML="${AGENT_TYPES_YAML}  ${local_type_id}:
    agent_string: ${local_agent_string}
    max_parallel: 0
"
    if [[ -n "${local_launch_mode:-}" ]]; then
        AGENT_TYPES_YAML="${AGENT_TYPES_YAML}    launch_mode: ${local_launch_mode}
"
    fi
done
```

Note: `IFS=':' read -r` splits agent_string on any colon. Current
agent strings use `/` (e.g., `claudecode/opus4_6`) so this is safe. If
a future agent string grows a colon, callers must not pass the third
field via `--add-type` — use separate plumbing.

**3c. Update the help text** at line 50 to show the extended format:
```bash
ait crew init --id sprint1 --add-type impl:claudecode/opus4_6 --add-type review:claudecode/sonnet4_6:interactive --batch
```

### Step 4 — Pass launch_mode from `aitask_brainstorm_init.sh`

**4a. Add a helper** after `_get_brainstorm_agent_string` (around line
108), mirroring its shape but reading directly from
`BRAINSTORM_AGENT_TYPES` as the source of truth:
```bash
_get_brainstorm_launch_mode() {
    local agent_type="$1"
    "$PYTHON" -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from brainstorm.brainstorm_crew import BRAINSTORM_AGENT_TYPES
print(BRAINSTORM_AGENT_TYPES.get('$agent_type', {}).get('launch_mode', 'headless'))
" 2>/dev/null || echo "headless"
}
```

**4b. Update the `aitask_crew_init.sh` call** at lines 111-121 to
append launch_mode per type:
```bash
crew_output=$(bash "$SCRIPT_DIR/aitask_crew_init.sh" \
    --id "brainstorm-${TASK_NUM}" \
    --name "Brainstorm t${TASK_NUM}" \
    --add-type "explorer:$(_get_brainstorm_agent_string explorer claudecode/opus4_6):$(_get_brainstorm_launch_mode explorer)" \
    --add-type "comparator:$(_get_brainstorm_agent_string comparator claudecode/sonnet4_6):$(_get_brainstorm_launch_mode comparator)" \
    --add-type "synthesizer:$(_get_brainstorm_agent_string synthesizer claudecode/opus4_6):$(_get_brainstorm_launch_mode synthesizer)" \
    --add-type "detailer:$(_get_brainstorm_agent_string detailer claudecode/opus4_6):$(_get_brainstorm_launch_mode detailer)" \
    --add-type "patcher:$(_get_brainstorm_agent_string patcher claudecode/sonnet4_6):$(_get_brainstorm_launch_mode patcher)" \
    --batch 2>&1) || {
    die "Failed to create crew: $crew_output"
}
```

### Step 5 — Unit/integration check (quick)

`tests/` already has `test_launch_mode_field.sh` (added by t461_1) and
`test_crew_setmode.sh` (t461_2). Neither covers the `aitask_crew_init.sh`
emitter extension. Run `shellcheck` and the existing tests; defer
dedicated coverage to `/aitask-qa` afterwards.

## Verification

1. **Fresh brainstorm crew**:
   ```bash
   ./ait brainstorm init <some_test_task>
   cat .aitask-crews/crew-brainstorm-<task>/_crew_meta.yaml
   ```
   Confirm `agent_types.detailer.launch_mode: interactive` and
   `agent_types.explorer.launch_mode: headless`.

2. **Detail op without toggle**: Launch a `detail` op in the brainstorm
   TUI, leave the wizard toggle at its default. Confirm:
   - The agent launches in a tmux window named `agent-detailer_NNN`
     (not headless).
   - The agent's `_status.yaml` does NOT contain a `launch_mode` key
     (the redundancy filter dropped it because the wizard value matches
     the type default).

3. **Explore op without toggle**: Launch an `explore` op. Confirm all
   explorer agents launch headless (no tmux window), and their status
   yamls have no `launch_mode` key.

4. **Override per-agent**: Toggle the wizard OFF for a `detail` op.
   Launch. Confirm the detailer launches headless (per-agent override
   wins). The status yaml MUST contain `launch_mode: headless` since
   the wizard value differs from the type default.

5. **Override other direction**: Toggle the wizard ON for an `explore`
   op. Launch. Confirm explorers launch interactively. Status yaml has
   `launch_mode: interactive`.

6. **Shellcheck**: `shellcheck .aitask-scripts/aitask_crew_init.sh
   .aitask-scripts/aitask_brainstorm_init.sh` must pass.

7. **Existing tests**: Re-run `bash tests/test_launch_mode_field.sh`
   and `bash tests/test_crew_setmode.sh` — both must still pass.

## Dependencies

- t461_1 (archived) — runner resolution line: DONE.
- t461_2 (archived) — `crew setmode` CLI: DONE.
- t461_3 (archived) — wizard toggle + `_brainstorm_launch_mode_default()`:
  DONE. Will automatically start returning `"interactive"` for
  detailer once Step 1 lands.
- t461_4 (archived) — status-tab edit: DONE.

## Out of scope (follow-up task t461_7)

The `ait settings` TUI currently exposes brainstorm agent-string
defaults via per-type ConfigRows (project/user layered, reads
`codeagent_config.json` under `defaults.brainstorm-*`). Adding a
matching row for `launch_mode` per type would let users edit defaults
without touching code — a natural UX extension.

This is **deferred to a follow-up child task t461_7** to keep t461_5
minimal. During archival of t461_5, create `t461_7` via the Batch Task
Creation Procedure with a description that references:
- The settings TUI pattern in `.aitask-scripts/settings/settings_app.py`
  around lines 1850-1892 (project/user ConfigRow pair + AgentModelPicker
  modal for editing).
- The config overlay storage approach: add flat keys
  `brainstorm-<type>-launch-mode` to `codeagent_config.json` under
  `defaults`, parallel to existing `brainstorm-<type>` keys.
- Teach `get_agent_types()` in `brainstorm/brainstorm_crew.py` to
  overlay `launch_mode` from those config keys (lines 48-71).
- Teach `_get_brainstorm_launch_mode()` in
  `aitask_brainstorm_init.sh` to also read from config (so the crew
  yaml picks up user overrides at init time).
- A small modal for headless/interactive selection (or reuse
  CycleField pattern from t461_3).

## Notes for sibling tasks (t461_6, t461_7)

- `t461_6` (ANSI log viewer) is independent of this task.
- `t461_7` (TUI exposure — to be created during t461_5 archival) will
  build on the dict + config plumbing this task lays down.
- **Schema stability**: `launch_mode` is now a documented per-type
  key in `_crew_meta.yaml`. If a future agent type is added to
  `BRAINSTORM_AGENT_TYPES`, include a `launch_mode` value (missing =
  `headless` fallback but explicit is better).
- **Mode validation regex**: `^(headless|interactive)$` is now
  enforced in FOUR places — `aitask_crew_addwork.sh`,
  `aitask_crew_setmode.sh`, `agentcrew_runner.py`, and now
  `aitask_crew_init.sh`. Keep in lock-step.

## Step 9 (Post-Implementation)

Follow the standard task-workflow Step 9: review → commit code changes
(plain `git`) → commit plan file (`./ait git`) → ask before merging →
run archive script → push. Use commit prefix `feature:` since
`issue_type: feature`.

## Final Implementation Notes

- **Actual work done:** All four implementation steps landed exactly
  as planned. `BRAINSTORM_AGENT_TYPES` now carries `launch_mode` per
  entry (detailer=interactive, others=headless).
  `brainstorm_crew.py:_run_addwork()` uses a type-default redundancy
  filter so `--launch-mode` is emitted only when the wizard value
  differs from the per-type default. `aitask_crew_init.sh` accepts
  the extended `type_id:agent_string[:launch_mode]` format on
  `--add-type`, validates the optional mode, and emits it into the
  YAML block when present. `aitask_brainstorm_init.sh` grew a
  `_get_brainstorm_launch_mode()` helper that reads directly from
  `BRAINSTORM_AGENT_TYPES` via Python (source of truth), and all
  five `--add-type` calls pass the resolved launch_mode as the third
  field.
- **Deviations from plan:** None. No scope changes, no skipped steps.
- **Issues encountered:** None during implementation. During the
  verification phase I discovered pre-existing uncommitted changes
  in `.aitask-scripts/aitask_update.sh` and
  `.aitask-scripts/lib/task_utils.sh` (an in-progress `file_references`
  field feature) — these are unrelated to t461_5 and were left
  untouched. The t461_5 commit deliberately staged only the three
  files modified by this task.
- **Key decisions:**
  - **Config-overlay deferred to follow-up**: `launch_mode` is NOT
    read from `codeagent_config.json` in this iteration. Only
    `agent_string` remains config-overridable for now. Making
    `launch_mode` config-overridable (and exposing it in the
    settings TUI) is deferred to t461_7.
  - **Three-field colon format for `--add-type`**: Chose this over a
    new `--agent-types-file <yaml>` flag or a separate
    `--type-launch-mode` flag because it keeps brainstorm's single
    call site clean and the format stays readable. Agent strings use
    `/` (not `:`) as the internal separator, so a three-field
    colon split is unambiguous. Documented as a caller constraint
    in the plan (no colons allowed in `agent_string` if the third
    field is used).
  - **Source of truth for shell→Python bridge**: The new
    `_get_brainstorm_launch_mode()` helper reads directly from the
    Python `BRAINSTORM_AGENT_TYPES` dict (not a duplicated shell
    mapping). This keeps one source of truth and mirrors the
    existing pattern of `_get_brainstorm_agent_string` shelling to
    Python. The helper falls back to `"headless"` on any Python
    import failure, matching `agent_data.get(...) or ... or "headless"`
    runtime fallback.
- **Notes for sibling tasks:**
  - `t461_7` (TUI exposure, to be created) should add flat keys
    `brainstorm-<type>-launch-mode` in `codeagent_config.json` under
    `defaults`, teach `get_agent_types()` in `brainstorm_crew.py`
    (around line 48-71) to overlay these keys, and teach
    `_get_brainstorm_launch_mode()` in `aitask_brainstorm_init.sh`
    to also consult the config layer (probably by rewriting the
    helper to shell into `get_agent_types()` instead of directly
    reading `BRAINSTORM_AGENT_TYPES`).
  - The `^(headless|interactive)$` regex now lives in FOUR places:
    `aitask_crew_addwork.sh`, `aitask_crew_setmode.sh`,
    `agentcrew_runner.py`, and **newly**
    `aitask_crew_init.sh` (in the `--add-type` validator). Any
    future third mode (e.g., `monitored`) must update all four.
  - The `IFS=':' read -r` split in the init emitter is safe today
    because all known `agent_string` values use `/` as internal
    separator. If a future agent string grows a colon, callers must
    not use the third `--add-type` field — add a separate flag
    instead of breaking the current format.
- **Build verification:** `shellcheck --severity=warning` clean on
  both `aitask_crew_init.sh` and `aitask_brainstorm_init.sh`.
  `tests/test_launch_mode_field.sh` (7/7 PASS) and
  `tests/test_crew_setmode.sh` (21/21 PASS) still pass. Direct
  invocation of `aitask_crew_init.sh` with mixed
  `--add-type` forms (with and without third field) produced the
  expected `_crew_meta.yaml` structure (launch_mode emitted only
  for types that specified it).
