---
Task: t743_brainstorm_apply_patcher_output.md
Worktree: (current branch — fast profile, no worktree)
Branch: main
Base branch: main
---

# t743 — Implement `apply_patcher_output()` for the brainstorm patcher agent

## Context

The brainstorm engine has only one fully wired apply-flow: the initializer
(`apply_initializer_output` in `brainstorm_session.py:336` + TUI hook at
`brainstorm_app.py:2104` + timer at `:3742` + CLI wrapper
`aitask_brainstorm_apply_initializer.sh`). The other agent types (explorer,
synthesizer, detailer, **patcher**) write `_output.md` files but nothing
parses or integrates them. This was discovered when `patcher_001` for crew
`brainstorm-635` ran successfully — the three-part output is on disk at
`.aitask-crews/crew-brainstorm-635/patcher_001_output.md` — but the runner
stopped without materializing the patched plan. The session is stuck at
`current_head: n000_init` with `next_node_id: 1` despite the patcher having
already produced a valid `n001_infra_only` node spec.

The patcher is the most complex of the four missing apply-paths because its
output has **three** delimiter blocks (vs the initializer's two and the
detailer's one) and **two branches** (NO_IMPACT vs IMPACT_FLAG). Sibling
tasks t739 (apply-explorer), t740 (apply-synthesizer), and t741
(apply-detailer) cover the others; they'll mostly mirror this one's pattern.

The end-to-end goal is: when a patcher group completes, the patched plan is
auto-written to `br_plans/<new>_plan.md`, a new node is created with the
agent-supplied metadata, the graph head advances, and IMPACT_FLAG cases
surface a persistent warning banner so the user knows an Explorer
regeneration is recommended. A CLI fallback (`ait brainstorm apply-patcher
<task> <agent> <source>`) lets the user unblock stuck sessions like
brainstorm-635 without re-running the agent.

## Files to modify / create

| File | Change |
|---|---|
| `.aitask-scripts/brainstorm/brainstorm_session.py` | Add `apply_patcher_output()` + `_patcher_needs_apply()` + `_PATCHER_DELIMITERS` constant |
| `.aitask-scripts/brainstorm/brainstorm_app.py` | Add `_patcher_sources` tracking, `_try_apply_patcher_if_needed()`, `_poll_patchers` timer, IMPACT banner widget, manual-retry binding |
| `.aitask-scripts/aitask_brainstorm_apply_patcher.sh` | New CLI wrapper (mirror `aitask_brainstorm_apply_initializer.sh`) |
| `ait` | Route `apply-patcher` subcommand; update help text and unknown-subcommand error list |
| `.claude/settings.local.json` | Add Bash allow rule for new helper |
| `.gemini/policies/aitasks-whitelist.toml` | Add `[[rule]]` block for new helper |
| `seed/claude_settings.local.json` | Mirror runtime claude entry |
| `seed/geminicli_policies/aitasks-whitelist.toml` | Mirror runtime gemini entry |
| `seed/opencode_config.seed.json` | Add `"./.aitask-scripts/aitask_brainstorm_apply_patcher.sh *": "allow"` |
| `tests/test_brainstorm_apply_patcher.py` | New unit test suite |
| `tests/test_brainstorm_apply_patcher_cli.sh` | New CLI round-trip test |

`templates/patcher.md` already specifies the three-block delimiter format —
verified during exploration; no change needed.

## Design

### 1. Engine function: `apply_patcher_output()`

In `brainstorm_session.py`, after `apply_initializer_output`:

```python
_PATCHER_DELIMITERS = (
    "PATCHED_PLAN_START", "PATCHED_PLAN_END",
    "IMPACT_START", "IMPACT_END",
    "METADATA_START", "METADATA_END",
)

# fields the agent emits as METADATA structural fields — NOT dimension fields
_PATCHER_NON_DIMENSION_FIELDS = {
    "node_id", "parents", "description", "proposal_file",
    "created_at", "created_by_group", "reference_files", "plan_file",
}


def _patcher_needs_apply(task_num, agent_name) -> bool:
    """True iff <agent_name>_output.md contains all six delimiter tokens
    AND the new_node_id parsed from the metadata block does NOT already
    exist in br_nodes/. Guards against the registration-time placeholder
    file and against double-apply on TUI restart."""


def apply_patcher_output(
    task_num: int | str,
    agent_name: str,
    source_node_id: str,
) -> tuple[str, str, str]:
    """Parse <agent_name>_output.md and integrate the patched plan as a
    new node parented on source_node_id.

    Returns:
        (new_node_id, impact_type, impact_details)
        impact_type ∈ {"NO_IMPACT", "IMPACT_FLAG"}
        impact_details: the IMPACT block content (justification or
                        affected-dimensions text), stripped.

    Raises:
        FileNotFoundError: output file missing OR source proposal missing
        ValueError: any delimiter missing, metadata invalid, IMPACT block
                    contains neither/both flags, or new_node_id already
                    exists as a node (refusing to overwrite)
    """
```

**Implementation steps inside the function:**

1. `wt = crew_worktree(task_num)`; `out_path = wt / f"{agent_name}_output.md"` — `FileNotFoundError` if missing.
2. Read text; extract three blocks via existing `_extract_block(text, "PATCHED_PLAN_START", "PATCHED_PLAN_END")`, etc. — `_extract_block` already raises `ValueError("missing delimiter: ...")` on failure.
3. Parse metadata via `_tolerant_yaml_load(metadata_text)`; on `yaml.YAMLError` write `<agent_name>_apply_error.log` and re-raise (mirror `apply_initializer_output`).
4. Auto-fill missing system-generable fields (mirror initializer's pattern):
   - `created_at` ← `datetime.now().strftime("%Y-%m-%d %H:%M")` if missing
   - `created_by_group` ← derived from `agent_name` (e.g. `patcher_001` → `patch_001`) if missing
5. Validate via `validate_node(node_data)` — raise `ValueError` on errors.
6. Extract `new_node_id = node_data["node_id"]`. Refuse to overwrite: if `(wt / NODES_DIR / f"{new_node_id}.yaml").exists()`, raise `ValueError(f"node {new_node_id} already exists")`.
7. **Parse IMPACT block:** strip; detect `**NO_IMPACT**` vs `**IMPACT_FLAG**`. If neither / both present, raise `ValueError("IMPACT block must contain exactly one of NO_IMPACT or IMPACT_FLAG")`. `impact_details` = the block text (kept as-is for banner display).
8. **Read source proposal** via `read_proposal(wt, source_node_id)` — propagates `FileNotFoundError` if source node has no proposal.
9. **Build dimensions dict** = `{k: v for k, v in node_data.items() if k not in _PATCHER_NON_DIMENSION_FIELDS}`. (Filters out `proposal_file` from the parsed metadata so `create_node` can authoritatively set it to `br_proposals/<new_node_id>.md` — guarantees the `validate_node` invariant `node_id ∈ proposal_file`.)
10. **Create the node:**
    ```python
    create_node(
        session_path=wt,
        node_id=new_node_id,
        parents=node_data["parents"],
        description=node_data["description"],
        dimensions=dimensions,
        proposal_content=source_proposal_text,
        group_name=node_data["created_by_group"],
        reference_files=node_data.get("reference_files"),
    )
    ```
11. **Write the patched plan** to `wt / PLANS_DIR / f"{new_node_id}_plan.md"`.
12. **Set `plan_file` on the new node** via `update_node(wt, new_node_id, {"plan_file": f"{PLANS_DIR}/{new_node_id}_plan.md"})`.
13. **Advance graph state:** `set_head(wt, new_node_id)` then `next_node_id(wt)`.
14. Return `(new_node_id, impact_type, impact_details)`.

**Error log:** wrap the body in `try/except` so any exception writes `<agent_name>_apply_error.log` (with timestamp + traceback summary, mirroring the initializer's error-log format) before re-raising.

### 2. CLI wrapper: `aitask_brainstorm_apply_patcher.sh`

Mirror `aitask_brainstorm_apply_initializer.sh` exactly:

```bash
#!/usr/bin/env bash
# Usage: ait brainstorm apply-patcher <task_num> <agent_name> <source_node_id>
# Output:
#   APPLIED:<new_node_id>:<impact_type>     Apply succeeded
#   APPLY_FAILED:<error>                     stderr; see <agent>_apply_error.log
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/aitask_path.sh"
source "$SCRIPT_DIR/lib/python_resolve.sh"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
PYTHON="$(require_ait_python)"
"$PYTHON" -c "import yaml" 2>/dev/null || die "Missing pyyaml. Run 'ait setup'."

[[ $# -eq 3 ]] || { echo "Usage: ait brainstorm apply-patcher <task_num> <agent_name> <source_node_id>" >&2; exit 2; }
NUM="$1"; AGENT="$2"; SOURCE="$3"

cd "$SCRIPT_DIR/.."
exec "$PYTHON" - "$NUM" "$AGENT" "$SOURCE" <<'PY'
import sys
sys.path.insert(0, '.aitask-scripts')
from brainstorm.brainstorm_session import apply_patcher_output
num, agent, source = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    new_id, impact, _details = apply_patcher_output(num, agent, source)
    print(f'APPLIED:{new_id}:{impact}')
except Exception as exc:
    print(f'APPLY_FAILED:{exc}', file=sys.stderr)
    sys.exit(1)
PY
```

### 3. `ait` dispatcher route

In `ait`, brainstorm subcase (line 239+), insert one line under
`apply-initializer`:

```bash
apply-patcher) exec "$SCRIPTS_DIR/aitask_brainstorm_apply_patcher.sh" "$@" ;;
```

Update the help text (line 255) to mention `apply-patcher`, and append it to
the unknown-subcommand error list (line 262).

### 4. TUI auto-apply hook in `brainstorm_app.py`

**State on the App:**

```python
self._patcher_sources: dict[str, str] = {}      # agent_name -> source_node_id
self._applying_patcher: set[str] = set()         # re-entrance guard per agent
self._patcher_apply_errors: dict[str, str] = {}  # agent_name -> error msg
self._patcher_poll_timer = None
```

**Source-node tracking (register-time):**

In `_run_step2_workflow` (line ~3491), the `elif op == "patch":` branch.
After `register_patcher(...)` returns `agent`, hop back to the main thread:

```python
self.call_from_thread(
    self._patcher_sources.__setitem__, agent, cfg["node"]
)
```

**Restart recovery (`_load_existing_session`):**

After session load, scan `patcher_*_status.yaml`. For each file whose
`status == "Completed"` and whose entry isn't already in
`self._patcher_sources`, parse the agent's `_input.md` to recover
`source_node_id` (the line `- Metadata: <session>/br_nodes/<source>.yaml`
written by `_assemble_input_patcher`). Skip silently if parsing fails — the
user can run the CLI fallback. Then start `_patcher_poll_timer` (5 s
interval) calling `_poll_patchers`.

```python
import re
_META_RE = re.compile(r"-\s*Metadata:\s*\S+/br_nodes/(\w+)\.yaml")
```

**`_poll_patchers()` timer tick:**

Iterate `self._patcher_sources.items()`. For each `(agent, source)`:

- Skip if already in `self._applying_patcher`.
- Read `<agent>_status.yaml`; skip if `status != "Completed"`.
- If `_patcher_needs_apply(self.task_num, agent)` returns `False`, drop from
  `self._patcher_sources` (already-applied — idempotent skip on restart).
- Else call `self._try_apply_patcher_if_needed(agent, source)`.

Stop the timer when the dict is empty.

**`_try_apply_patcher_if_needed(agent_name, source_node_id, force=False)`:**

```python
def _try_apply_patcher_if_needed(self, agent_name, source_node_id, force=False):
    if agent_name in self._applying_patcher:
        return
    from brainstorm.brainstorm_session import (
        apply_patcher_output, _patcher_needs_apply,
    )
    if not force and not _patcher_needs_apply(self.task_num, agent_name):
        return
    self._applying_patcher.add(agent_name)
    try:
        new_id, impact, details = apply_patcher_output(
            self.task_num, agent_name, source_node_id,
        )
    except Exception as exc:
        self._patcher_apply_errors[agent_name] = str(exc)
        self._set_impact_banner(
            f"Patcher apply failed ({agent_name}): {exc} — "
            f"run `ait brainstorm apply-patcher {self.task_num} "
            f"{agent_name} {source_node_id}` to retry"
        )
    else:
        self._patcher_apply_errors.pop(agent_name, None)
        self._patcher_sources.pop(agent_name, None)
        if impact == "IMPACT_FLAG":
            # Persistent warning — patcher detected architectural impact.
            self._set_impact_banner(
                f"Patcher {agent_name} → {new_id}: IMPACT_FLAG — "
                f"Explorer regeneration recommended.\n{details}"
            )
        else:
            self._clear_impact_banner()
            self.notify(f"Patched plan applied → {new_id}.")
        self._load_existing_session()
    finally:
        self._applying_patcher.discard(agent_name)
```

**Banner widget:** add an `#impact_banner` `Static` to `compose()` next to
the existing `#initializer_apply_banner` (same CSS class so styling is
shared). Methods `_set_impact_banner(msg)` / `_clear_impact_banner()` mirror
the initializer banner's `_set_apply_banner` / `_clear_apply_banner`.

**Manual-retry binding:** add `("ctrl+shift+r", "retry_patcher_apply", ...)`.
The action retries the most-recent failed patcher (the only one in
`self._patcher_apply_errors`, or — if multiple — the most-recently failed by
`patcher_*_status.yaml` mtime). If none failed, no-op.

### 5. Whitelisting (5 touchpoints — mandatory per CLAUDE.md)

| File | Insert |
|---|---|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_brainstorm_apply_patcher.sh:*)"` in `permissions.allow` (alongside the existing `apply_initializer` entry) |
| `.gemini/policies/aitasks-whitelist.toml` | New `[[rule]]` block: `toolName = "run_shell_command"`, `commandPrefix = "./.aitask-scripts/aitask_brainstorm_apply_patcher.sh"`, `decision = "allow"`, `priority = 100` |
| `seed/claude_settings.local.json` | Mirror runtime claude entry |
| `seed/geminicli_policies/aitasks-whitelist.toml` | Mirror runtime gemini entry |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_brainstorm_apply_patcher.sh *": "allow"` |

Codex is exempt (per CLAUDE.md "Codex exception").

### 6. Tests

**`tests/test_brainstorm_apply_patcher.py`** (Python unittest, mirrors
`test_brainstorm_session.py`):

Helper `_seed_patcher(wt, *, output_text, source_node_yaml,
source_proposal_text)` to build a fake crew worktree.

Cases:

- `test_no_impact_apply_creates_node_and_advances_head` — full happy path with
  `**NO_IMPACT**`. Asserts `new_node_id` returned, node yaml exists with
  expected dimensions + auto-set `proposal_file`, plan file written, head
  advanced, `next_node_id` incremented, return tuple correct, IMPACT details
  carried through.
- `test_impact_flag_apply_returns_details` — IMPACT_FLAG case; asserts
  details text passes through unchanged for banner display.
- `test_missing_output_raises_filenotfound`.
- `test_missing_delimiter_raises_valueerror` — drop METADATA_END.
- `test_missing_source_proposal_raises_filenotfound` — source node has no
  proposal markdown.
- `test_neither_or_both_impact_flags_raises_valueerror` — IMPACT block
  contains "no marker" / contains both.
- `test_existing_new_node_id_refuses_overwrite` — pre-create
  `br_nodes/n001_infra_only.yaml`; expect ValueError.
- `test_missing_created_at_is_auto_filled` — like initializer's analogous
  test.
- `test_missing_created_by_group_defaults_from_agent_name` — `patcher_001` →
  `patch_001`.
- `test_reference_files_preserved_when_present` and
  `test_reference_files_absent_when_omitted`.
- `test_invalid_yaml_writes_error_log` — assert
  `<agent>_apply_error.log` is created on `yaml.YAMLError`.

**`tests/test_brainstorm_apply_patcher_cli.sh`** (bash, mirrors
`test_brainstorm_init_proposal_file.sh` style):

- Build a temp crew worktree + valid output + n000 source node + proposal.
- Invoke `./.aitask-scripts/aitask_brainstorm_apply_patcher.sh <num> <agent>
  <source>`.
- Assert exit 0 and stdout matches `^APPLIED:n[0-9]{3}_.*:NO_IMPACT$`.
- Assert resulting `br_nodes/n001_*.yaml`, `br_plans/n001_*_plan.md`, and
  graph state head/next_node_id are correct.
- Negative: missing source proposal → exit 1, stderr starts with
  `APPLY_FAILED:`.

`_patcher_needs_apply` is also covered indirectly via the `tests/test_brainstorm_apply_patcher.py` cases (existing-node refusal).

## Out-of-scope follow-ups

- Generalizing initializer + patcher (and future explorer/synthesizer/detailer)
  apply hooks into a unified poller — premature until at least three apply
  paths are wired. Sibling tasks t739/t740/t741 land first; revisit after.
- Wiring `br_groups.yaml` updates to track patcher-created nodes — orthogonal
  to apply, currently unused.
- Re-running stuck `brainstorm-635` is a manual one-shot using the new
  CLI wrapper (per task description); no automation needed.

## Verification plan

1. **Unit tests:**
   ```bash
   bash tests/test_brainstorm_apply_patcher_cli.sh
   python3 -m unittest tests.test_brainstorm_apply_patcher
   ```
   Plus regression: `python3 -m unittest tests.test_brainstorm_session` to
   ensure no shared-helper regression.

2. **Lint:** `shellcheck .aitask-scripts/aitask_brainstorm_apply_patcher.sh`

3. **Real-session smoke test (the brainstorm-635 unblock):**
   ```bash
   ait brainstorm apply-patcher 635 patcher_001 n000_init
   ```
   Expected stdout: `APPLIED:n001_infra_only:NO_IMPACT`. Then:
   ```bash
   cat .aitask-crews/crew-brainstorm-635/br_graph_state.yaml
   ls .aitask-crews/crew-brainstorm-635/br_nodes/
   ls .aitask-crews/crew-brainstorm-635/br_plans/
   ```
   should show `current_head: n001_infra_only`, `next_node_id: 2`, both
   node yaml files, and the new `n001_infra_only_plan.md`.

4. **TUI smoke test (manual):** open the t635 brainstorm TUI
   (`ait brainstorm 635`); confirm DAG view now shows two nodes and the
   IMPACT banner is absent (NO_IMPACT case). Idempotency: calling the CLI
   wrapper a second time must surface `APPLY_FAILED: node n001_infra_only
   already exists`.

5. **Step 9 (Post-Implementation):** follow the standard task-workflow
   archive flow on the current branch (no worktree, fast profile). Plan
   file → `aiplans/p743_brainstorm_apply_patcher_output.md`.
