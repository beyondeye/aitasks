---
Task: t573_1_initializer_agent_and_ingestion.md
Parent Task: aitasks/t573_import_initial_proposal_in_brainstrom.md
Sibling Tasks: aitasks/t573/t573_2_*.md, aitasks/t573/t573_3_*.md, aitasks/t573/t573_4_*.md, aitasks/t573/t573_5_*.md
Archived Sibling Plans: aiplans/archived/p573/p573_*_*.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-23 11:36
---

# t573_1 — `initializer` agent type + `apply_initializer_output()` ingestion helper

## Context

Parent plan: `aiplans/p573_import_initial_proposal_in_brainstrom.md`. This
is the **first** child and must land before t573_2 (CLI) or t573_3 (TUI).
Nothing in the repo today parses agent `_output.md` delimiters — the
explorer/synthesizer templates already emit the `NODE_YAML_START/END`
blocks, but no Python parser consumes them. This child establishes the
pattern.

Verified against the current codebase (2026-04-23): all referenced
modules, helpers, constants, and templates are in place.
`BRAINSTORM_AGENT_TYPES` has 5 entries (`explorer`, `comparator`,
`synthesizer`, `detailer`, `patcher`); no `initializer` yet. No
`apply_*_output()` helper exists yet in `brainstorm_session.py`.

## Implementation steps

### 1. Agent template

Create `.aitask-scripts/brainstorm/templates/initializer.md`, modelled on
`templates/explorer.md` (187 lines, Phase 1..Phase 4 structure with
`report_alive`, `update_progress`, `check_commands` checkpoints).

Required shape:

```markdown
# Task: Initializer

You are the Initializer for the brainstorm engine. You bootstrap the root
node `n000_init` from an imported markdown proposal, reformatting it into
a structured node (sectioned proposal + flat-YAML dimension metadata).

## Input

Read your `_input.md` file. It contains:
1. The path of an imported markdown proposal (`imported_path`).
2. The path of the originating aitask file (`task_file`).
3. Your mandate: reformat the imported content into the brainstorm node
   format without editing the source.

## Output

<!-- include: _section_format.md -->

Write exactly one file — your `_output.md` — with four delimited blocks:

--- NODE_YAML_START ---
<flat YAML node metadata>
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<sectioned proposal markdown>
--- PROPOSAL_END ---

### Required NODE_YAML fields

- `node_id: n000_init`
- `parents: []`
- `description`: one-line summary of the imported proposal (<= 120 chars).
- `proposal_file: br_proposals/n000_init.md`
- `created_by_group: bootstrap`
- `reference_files`: list containing at minimum the `imported_path`.
- Any `requirements_*` / `assumption_*` / `component_*` / `tradeoff_*`
  dimension fields you can justify from the source text. Do NOT invent
  dimensions that are not supported by the text — it is OK to emit zero
  of a given prefix.

### Required PROPOSAL structure

Wrap the body in `<!-- section: ... -->` / `<!-- /section: ... -->`
markers. If the imported content fits the standard shape, use
`overview`, `architecture`, `data_flow`, `components`, `assumptions`,
`tradeoffs` (same as explorer). Otherwise pick section names that match
the imported document's natural structure.

## Rules

1. Do NOT modify the file at `imported_path`. It is read-only.
2. Preserve the substantive content — you are reformatting, not
   rewriting.
3. Every assumption in the source must appear in the output (in an
   `assumptions` section and, where appropriate, as an `assumption_*`
   dimension key).
```

Follow explorer.md's Phase 1..Phase 4 checkpoint idiom
(`report_alive`, `update_progress`, `check_commands`).

### 2. `BRAINSTORM_AGENT_TYPES`

Edit `.aitask-scripts/brainstorm/brainstorm_crew.py` (dict at ~lines
44-50). Append:

```python
"initializer": {"max_parallel": 1, "launch_mode": "interactive"},
```

### 3. `_assemble_input_initializer`

Add alongside the other `_assemble_input_*` helpers (`explorer` at line
194, `comparator` at 270, `synthesizer` at 298, `detailer` at 348,
`patcher` at 397). Signature:

```python
def _assemble_input_initializer(
    session_path: Path,
    imported_path: str,
    task_file: str,
) -> str:
```

Emit a markdown document with three top-level sections:

- `## Imported Proposal` — path + "Read this file. Do not modify it."
- `## Originating Task` — path.
- `## Mandate` — fixed bootstrap instruction mirroring the template
  preamble.

Do NOT include the dimension-keys / active-dimensions blocks used by
explorer — `n000_init` starts dimensionless.

### 4. `register_initializer`

Add alongside `register_detailer` (line 567) and `register_patcher`
(line 608). Mirror the `register_detailer` body:

```python
def register_initializer(
    session_dir: Path,
    crew_id: str,
    imported_path: str,
    task_file: str,
    group_name: str = "bootstrap",
    agent_suffix: str = "",
    launch_mode: str = DEFAULT_LAUNCH_MODE,
) -> str:
    agent_name = f"initializer_bootstrap{agent_suffix}"
    input_content = _assemble_input_initializer(
        session_dir, imported_path, task_file
    )
    work2do_path = TEMPLATE_DIR / "initializer.md"
    _run_addwork(
        crew_id, agent_name, "initializer", group_name,
        work2do_path, launch_mode=launch_mode,
    )
    _write_agent_input(session_dir, agent_name, input_content)
    return agent_name
```

Note: `register_initializer` does NOT use `_group_seq` — the agent
name is fixed (`initializer_bootstrap`), unlike
`detailer_<seq>` / `patcher_<seq>` which increment per group.

### 5. `init_session` extension

Edit `.aitask-scripts/brainstorm/brainstorm_session.py`. Current
signature (lines 40-45):

```python
def init_session(task_num, task_file, user_email, initial_spec) -> Path:
```

Extend to:

```python
def init_session(
    task_num: int | str,
    task_file: str,
    user_email: str,
    initial_spec: str,
    initial_proposal_file: str | None = None,
) -> Path:
```

Behaviour when `initial_proposal_file` is set:

1. Validate existence (`Path(initial_proposal_file).is_file()` —
   raise `FileNotFoundError` otherwise).
2. Resolve to absolute path (`str(Path(initial_proposal_file).resolve())`).
3. Include `initial_proposal_file` key in the `session_data` dict
   written to `br_session.yaml` (lines 68-79).
4. Derive placeholder body:
   ```python
   basename = os.path.basename(initial_proposal_file)
   placeholder = f"Awaiting initializer agent output for `{basename}`.\n"
   brief = f"Imported proposal (awaiting reformat): {basename}"
   ```
5. Pass `reference_files=[abs_path]` to `create_node(...)` for
   `n000_init` (existing call at lines 99-107; `create_node` already
   accepts `reference_files: list[str] | None = None`).
6. Use `brief` as the `description` and `placeholder` as the
   `proposal_content`.

When `initial_proposal_file` is None, the existing behaviour must be
byte-for-byte identical — the bash test asserts this.

### 6. `apply_initializer_output`

Append to `brainstorm_session.py`:

```python
def apply_initializer_output(task_num: int | str) -> None:
    """Parse the initializer agent's _output.md and overwrite n000_init."""
    wt = crew_worktree(task_num)
    out_path = wt / "initializer_bootstrap_output.md"
    if not out_path.is_file():
        raise FileNotFoundError(f"No initializer output at {out_path}")

    text = out_path.read_text(encoding="utf-8")
    node_yaml_text = _extract_block(text, "NODE_YAML_START", "NODE_YAML_END")
    proposal_text  = _extract_block(text, "PROPOSAL_START", "PROPOSAL_END")

    import yaml
    from .brainstorm_schemas import validate_node
    from .brainstorm_sections import parse_sections, validate_sections

    node_data = yaml.safe_load(node_yaml_text)
    if not isinstance(node_data, dict):
        raise ValueError("initializer NODE_YAML block did not parse as a dict")
    errs = validate_node(node_data)
    if errs:
        raise ValueError(f"initializer node YAML invalid: {errs}")

    parsed = parse_sections(proposal_text)
    serrs = validate_sections(parsed)
    if serrs:
        raise ValueError(f"initializer proposal invalid: {serrs}")

    write_yaml(str(wt / NODES_DIR / "n000_init.yaml"), node_data)
    (wt / PROPOSALS_DIR / "n000_init.md").write_text(proposal_text, encoding="utf-8")
```

Helper (also appended):

```python
def _extract_block(text: str, start: str, end: str) -> str:
    start_tag = f"--- {start} ---"
    end_tag   = f"--- {end} ---"
    si = text.find(start_tag)
    ei = text.find(end_tag, si + len(start_tag)) if si >= 0 else -1
    if si < 0 or ei < 0:
        raise ValueError(f"missing delimiter: {start}/{end}")
    return text[si + len(start_tag):ei].strip("\n")
```

**Imports check:** `write_yaml` and `read_yaml` are **already** imported
from `agentcrew.agentcrew_utils` in `brainstorm_session.py` (line 19) —
no new top-level imports needed. `NODES_DIR` and `PROPOSALS_DIR` are
already imported from `brainstorm_dag` (lines 21-29).

### 7. Bash test

Create `tests/test_apply_initializer_output.sh`. No shared
`tests/test_helpers.sh` exists in the repo — follow the inline-helpers
pattern used by `tests/test_claim_id.sh` (inline `assert_eq`,
`assert_contains`).

Skeleton:

```bash
#!/usr/bin/env bash
set -euo pipefail
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/.." && pwd)"

# Inline assertion helpers (match test_claim_id.sh style)
assert_file_exists() {
    local path="$1"
    if [[ ! -f "$path" ]]; then
        echo "FAIL: expected file to exist: $path"
        exit 1
    fi
}
assert_contains() {
    local haystack="$1" needle="$2"
    if [[ "$haystack" != *"$needle"* ]]; then
        echo "FAIL: expected '$haystack' to contain '$needle'"
        exit 1
    fi
}

TMP_CREW="$(mktemp -d)"
mkdir -p "$TMP_CREW/br_nodes" "$TMP_CREW/br_proposals"

# Fixture output (mirrors the delimiter format in templates/initializer.md)
cat > "$TMP_CREW/initializer_bootstrap_output.md" <<'EOF'
--- NODE_YAML_START ---
node_id: n000_init
parents: []
description: Example imported proposal
proposal_file: br_proposals/n000_init.md
created_at: 2026-04-23 00:00
created_by_group: bootstrap
reference_files:
  - /tmp/imported.md
assumption_latency: low
component_api: REST
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview -->
## Overview
An imported proposal.
<!-- /section: overview -->
--- PROPOSAL_END ---
EOF

pushd "$REPO_ROOT" >/dev/null
python3 - <<EOF_PY
import sys, pathlib
sys.path.insert(0, ".aitask-scripts")
from brainstorm import brainstorm_session as bs
# Monkey-patch crew_worktree so the fixture directory is used as the worktree.
bs.crew_worktree = lambda n: pathlib.Path("$TMP_CREW")
bs.apply_initializer_output("fixture")
EOF_PY
popd >/dev/null

assert_file_exists "$TMP_CREW/br_nodes/n000_init.yaml"
assert_file_exists "$TMP_CREW/br_proposals/n000_init.md"
body="$(cat "$TMP_CREW/br_proposals/n000_init.md")"
assert_contains "$body" "section: overview"

rm -rf "$TMP_CREW"
echo "PASS: apply_initializer_output"
```

Second test path (negative-case — malformed output raises
`ValueError`): append an `assert_exit_nonzero` block that drops a
truncated fixture (missing `PROPOSAL_END`) and expects the python
invocation to fail. Keep it in the same file to avoid test-harness
sprawl.

## Verification

- `bash tests/test_apply_initializer_output.sh` prints
  `PASS: apply_initializer_output`.
- `shellcheck tests/test_apply_initializer_output.sh` clean.
- `python3 -c "import sys; sys.path.insert(0, '.aitask-scripts');
  from brainstorm.brainstorm_crew import BRAINSTORM_AGENT_TYPES;
  print(BRAINSTORM_AGENT_TYPES['initializer'])"` prints
  `{'max_parallel': 1, 'launch_mode': 'interactive'}`.
- Manual smoke: in a throwaway session, call
  `init_session('fresh', 'aitasks/tXXX.md', '', '',
  initial_proposal_file='/tmp/foo.md')` and confirm
  `br_session.yaml` has `initial_proposal_file` set and
  `br_proposals/n000_init.md` contains the placeholder text.

## Notes for sibling tasks

- `initializer_bootstrap` is the canonical agent name. t573_2 prints
  this verbatim in its `INITIALIZER_AGENT:` stdout line; t573_3 polls
  for `<worktree>/initializer_bootstrap_status.yaml`.
- The fixture output file in the test is the authoritative example of
  the expected delimiter format — keep it in sync with the template
  in `templates/initializer.md` if either changes.
- Unlike `detailer_<seq>`/`patcher_<seq>`, the initializer agent does
  not use `_group_seq` — there is exactly one initializer per session,
  named `initializer_bootstrap`.

## Step 9 (Post-Implementation)

After user approval in Step 8, follow the shared workflow's Step 9
(archival via `./.aitask-scripts/aitask_archive.sh 573_1`). Plan file
will be archived to `aiplans/archived/p573/` and serve as the primary
reference for t573_2 / t573_3 / t573_4.

## Final Implementation Notes

- **Actual work done:** All 7 planned items landed as designed
  (template, agent-types entry, `_assemble_input_initializer`,
  `register_initializer`, `init_session(initial_proposal_file=…)`,
  `apply_initializer_output` + `_extract_block`, bash test).
  Both happy-path and negative-case (malformed output → `ValueError`)
  are covered by `tests/test_apply_initializer_output.sh` (8
  assertions PASS).

- **Deviations from plan — plan-gap fixes surfaced during
  implementation:** Adding a new entry to `BRAINSTORM_AGENT_TYPES`
  also required three touchpoints the plan did not enumerate. Without
  them, `get_agent_types()` raises `RuntimeError: Missing
  codeagent_config.json default for brainstorm-initializer` and the
  existing test suite fails. Fixed as part of this task:
    - `aitasks/metadata/codeagent_config.json` (tracked, shared):
      added `"brainstorm-initializer": "claudecode/sonnet4_6"`.
    - `.aitask-scripts/settings/settings_app.py`
      `OPERATION_DESCRIPTIONS`: added `brainstorm-initializer` and
      `brainstorm-initializer-launch-mode` descriptions so the
      settings TUI renders the new agent row.
    - `tests/test_brainstorm_crew.py`: added `brainstorm-initializer`
      to `FULL_DEFAULTS` and to the hardcoded expected-keys set in
      `test_agent_types_keys`.

- **Plan claim that didn't match reality:** The plan said `write_yaml`
  needed to be added alongside `read_yaml` in
  `brainstorm_session.py`'s import of `agentcrew.agentcrew_utils`.
  Both were already present (line 19). No-op — no change required.

- **Issues encountered:** None blocking. The initial
  `test_agent_types_keys` test had a hardcoded 5-element set that
  excluded `initializer`; updated to include it.

- **Key decisions:**
  - Default model for the new `brainstorm-initializer` config key:
    `claudecode/sonnet4_6` (matches `brainstorm-patcher` /
    `brainstorm-comparator` — interactive-mode reformat work, not
    architectural generation).
  - Seed file `seed/codeagent_config.json` is intentionally left
    untouched: it already lacks any `brainstorm-*` keys — those are
    added to runtime configs via `ait setup`, not seed. Follows the
    invariant covered by `tests/test_add_model.sh` line 181 ("seed
    does not gain brainstorm-explorer").
  - `register_initializer` does NOT use `_group_seq`. There is
    exactly one initializer per session (`initializer_bootstrap`),
    unlike `detailer_<seq>` / `patcher_<seq>` which increment per
    group. Plan already documented this.

- **Notes for sibling tasks (t573_2 / t573_3 / t573_4):**
  - The `brainstorm-initializer` config key is live in project
    config. Sibling tasks that touch `seed/codeagent_config.json`
    should leave the brainstorm section alone — the seed invariant
    is enforced by `tests/test_add_model.sh`.
  - `OPERATION_DESCRIPTIONS` now has the initializer row; the
    settings TUI (t573 does not touch it directly, but
    `aitask_board`/`settings_app` flows may) will render the
    new entry automatically.
  - When adding a 7th brainstorm agent type in the future,
    remember that `BRAINSTORM_AGENT_TYPES` + `codeagent_config.json`
    + `settings_app.py` `OPERATION_DESCRIPTIONS` + `FULL_DEFAULTS`
    in `test_brainstorm_crew.py` + `test_agent_types_keys` expected
    set all need to be updated together. Consider surfacing this
    4-touchpoint checklist in the module docstring or CLAUDE.md.
  - `initializer_bootstrap` remains the canonical agent name —
    t573_2's `INITIALIZER_AGENT:` stdout line and t573_3's status
    polling both depend on it being stable.
  - Delimiter format (`--- NODE_YAML_START ---` etc.) is shared
    between `templates/initializer.md` and the bash test fixture —
    keep them in sync if either changes.

- **Verification results:**
  - `bash tests/test_apply_initializer_output.sh` — 8/8 PASS
  - `python3 -m unittest discover -s tests -p 'test_brainstorm*.py'`
    — 104/104 PASS
  - `shellcheck tests/test_apply_initializer_output.sh` — clean
  - `get_agent_types()['initializer']` →
    `{'max_parallel': 1, 'launch_mode': 'interactive',
    'agent_string': 'claudecode/sonnet4_6'}` ✓
  - `init_session` smoke tests: backward-compat (no param), new
    path (with `initial_proposal_file`), error path
    (`FileNotFoundError` on missing file) all pass ✓
