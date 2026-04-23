---
Task: t573_1_initializer_agent_and_ingestion.md
Parent Task: aitasks/t573_import_initial_proposal_in_brainstrom.md
Sibling Tasks: aitasks/t573/t573_2_*.md, aitasks/t573/t573_3_*.md, aitasks/t573/t573_4_*.md
Archived Sibling Plans: aiplans/archived/p573/p573_*_*.md
Worktree: (none — default profile works on current branch)
Branch: main
Base branch: main
---

# t573_1 — `initializer` agent type + `apply_initializer_output()` ingestion helper

## Context

Parent plan: `aiplans/p573_import_initial_proposal_in_brainstrom.md`. This
is the **first** child and must land before t573_2 (CLI) or t573_3 (TUI).
Nothing in the repo today parses agent `_output.md` delimiters; this child
establishes the pattern.

## Implementation steps

### 1. Agent template

Create `.aitask-scripts/brainstorm/templates/initializer.md`, modelled on
`templates/explorer.md`.

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

```
--- NODE_YAML_START ---
<flat YAML node metadata>
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<sectioned proposal markdown>
--- PROPOSAL_END ---
```

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

Edit `.aitask-scripts/brainstorm/brainstorm_crew.py:44-50`. Append:

```python
"initializer": {"max_parallel": 1, "launch_mode": "interactive"},
```

### 3. `_assemble_input_initializer`

Add near the other `_assemble_input_*` helpers
(`brainstorm_crew.py:194-434`). Signature:

```python
def _assemble_input_initializer(
    session_path: Path,
    imported_path: str,
    task_file: str,
) -> str:
```

Emit a markdown document with three top-level sections:
`## Imported Proposal` (path + "Read this file. Do not modify it."),
`## Originating Task` (path), and `## Mandate` (fixed bootstrap
instruction mirroring the template preamble). Do NOT include the
dimension-keys / active-dimensions blocks used by explorer — n000_init
starts dimensionless.

### 4. `register_initializer`

Add alongside `register_patcher` (`brainstorm_crew.py:608-646`).
Signature:

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
```

Agent name: `f"initializer_bootstrap{agent_suffix}"`. work2do template
path: `TEMPLATE_DIR / "initializer.md"`. Call `_run_addwork(...)` with
type `"initializer"`. Then `_write_agent_input(session_dir, agent_name,
input_content)`. Return the agent name.

### 5. `init_session` extension

Edit `.aitask-scripts/brainstorm/brainstorm_session.py`:

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
2. Resolve to absolute path.
3. Include `initial_proposal_file` key in the `session_data` dict
   written to `br_session.yaml`.
4. Derive placeholder body:
   ```python
   basename = os.path.basename(initial_proposal_file)
   placeholder = f"Awaiting initializer agent output for `{basename}`.\n"
   brief = f"Imported proposal (awaiting reformat): {basename}"
   ```
5. Pass `reference_files=[abs_path]` to `create_node(...)` for
   `n000_init`.

When `initial_proposal_file` is None, the existing behaviour must be
byte-for-byte identical. Add a unit-equivalent assertion in the bash
test.

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

Helper:

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

Import `write_yaml` via the existing path used by
`save_session` (the top-level import already pulls in
`agentcrew.agentcrew_utils.read_yaml` — add `write_yaml` alongside).

### 7. Bash test

Create `tests/test_apply_initializer_output.sh`. Skeleton:

```bash
#!/usr/bin/env bash
set -euo pipefail
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/.." && pwd)"
source "$THIS_DIR/test_helpers.sh"

TMP_CREW="$(mktemp -d)"
mkdir -p "$TMP_CREW/br_nodes" "$TMP_CREW/br_proposals"

# Fixture output
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
import os, sys
sys.path.insert(0, ".aitask-scripts")
from brainstorm import brainstorm_session as bs
# Monkey-patch crew_worktree so we can point to our fixture.
bs.crew_worktree = lambda n: $(python3 -c "import pathlib, json; print(json.dumps('$TMP_CREW'))") and __import__('pathlib').Path("$TMP_CREW")
bs.apply_initializer_output("fixture")
EOF_PY
popd >/dev/null

assert_file_exists "$TMP_CREW/br_nodes/n000_init.yaml"
assert_file_exists "$TMP_CREW/br_proposals/n000_init.md"
grep -q "section: overview" "$TMP_CREW/br_proposals/n000_init.md" || { echo "section missing"; exit 1; }

rm -rf "$TMP_CREW"
echo "PASS: apply_initializer_output"
```

(Exact helper names and monkey-patch idiom should be lined up with
`tests/test_helpers.sh`; adapt as needed. The assertion API lives in
that helper file — read it before finalizing.)

## Verification

- `bash tests/test_apply_initializer_output.sh` prints
  `PASS: apply_initializer_output`.
- `shellcheck tests/test_apply_initializer_output.sh` clean.
- `python3 -c "from brainstorm.brainstorm_crew import
  BRAINSTORM_AGENT_TYPES; print(BRAINSTORM_AGENT_TYPES['initializer'])"`
  (with appropriate PYTHONPATH) prints `{'max_parallel': 1,
  'launch_mode': 'interactive'}`.
- Manual smoke: call `init_session('fresh', 'aitasks/tXXX.md', '',
  '', initial_proposal_file='/tmp/foo.md')` and confirm
  `br_session.yaml` has `initial_proposal_file` set and
  `br_proposals/n000_init.md` contains the placeholder text.

## Notes for sibling tasks

- `initializer_bootstrap` is the canonical agent name. t573_2 prints
  this verbatim in its `INITIALIZER_AGENT:` stdout line; t573_3 polls
  for `<worktree>/initializer_bootstrap_status.yaml`.
- The fixture output file in the test is the authoritative example of
  the expected delimiter format — keep it in sync with the template in
  `templates/initializer.md` if either changes.
