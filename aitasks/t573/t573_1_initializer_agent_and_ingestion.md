---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ait_brainstorm]
created_at: 2026-04-23 10:59
updated_at: 2026-04-23 10:59
---

## Context

Parent task t573 wants `ait brainstorm init` to optionally accept an
external markdown file and reformat it into a structured `n000_init` node
(sectioned proposal + flat-YAML dimensions). This child builds the backend
plumbing: a new brainstorm **agent type** and the Python hook that
**ingests its output** back into the session. No CLI / TUI changes live
here (those are t573_2 and t573_3).

See parent plan `aiplans/p573_import_initial_proposal_in_brainstrom.md`
for the end-to-end design. Note that as of today no brainstorm agent
output is ingested programmatically — explorer/synthesizer templates
already emit `NODE_YAML_START/END` delimiters, but nothing parses them.
`apply_initializer_output()` added here is the first such parser and
establishes the pattern for future ingestion.

## Key Files to Modify

- **NEW** `.aitask-scripts/brainstorm/templates/initializer.md` — agent
  work2do template.
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — add `initializer`
  agent type to `BRAINSTORM_AGENT_TYPES`, add
  `_assemble_input_initializer(...)` and `register_initializer(...)`.
- `.aitask-scripts/brainstorm/brainstorm_session.py` —
  - Extend `init_session(...)` with `initial_proposal_file: str | None = None`.
    When non-null, seed `n000_init` with a placeholder proposal body
    (e.g. "Awaiting initializer agent output for `<basename>`"), record
    the path in `br_session.yaml` under a new `initial_proposal_file`
    key, and mark `reference_files: [<path>]` on n000_init.
  - New `apply_initializer_output(task_num: int | str) -> None` that:
    1. Locates `<worktree>/initializer_bootstrap_output.md`.
    2. Parses four delimited blocks: `NODE_YAML_START/END`,
       `PROPOSAL_START/END`.
    3. Validates the YAML dict with `validate_node()` and the proposal
       with `validate_sections(parse_sections(...))`.
    4. Overwrites `br_nodes/n000_init.yaml` and
       `br_proposals/n000_init.md`.
    5. Raises `ValueError("initializer output malformed: ...")` on any
       parse/validation failure, leaving existing files untouched.
- **NEW** `tests/test_apply_initializer_output.sh` — fixture-driven bash
  test.

## Reference Files for Patterns

- Existing agent templates — `.aitask-scripts/brainstorm/templates/explorer.md`
  (required-section shape, `<!-- include: _section_format.md -->` idiom,
  four-phase Phase1..Phase4 structure).
- Existing `_assemble_input_*` helpers —
  `.aitask-scripts/brainstorm/brainstorm_crew.py:194-434`.
- Existing `register_*` functions —
  `.aitask-scripts/brainstorm/brainstorm_crew.py:441-646`. The
  `register_initializer` signature should follow `register_detailer`
  closely (single target node, interactive default).
- Dimension + section validators —
  `.aitask-scripts/brainstorm/brainstorm_schemas.py:55-123` and
  `.aitask-scripts/brainstorm/brainstorm_sections.py:124-152`.
- Node create/write helpers —
  `.aitask-scripts/brainstorm/brainstorm_dag.py:33-98`
  (`create_node`, `update_node` for the rewrite path;
  `write_yaml` from `agentcrew.agentcrew_utils` for the direct YAML
  overwrite).
- Existing bash test example — `tests/test_claim_id.sh` (layout,
  `assert_eq` / `assert_contains` helpers).

## Implementation Plan

1. **Template** — write `.aitask-scripts/brainstorm/templates/initializer.md`
   modelled on `explorer.md`:
   - Phase 1: read `initial_proposal_path` and task file.
   - Phase 2: classify structure, decide section names.
   - Phase 3: emit flat YAML with `node_id: n000_init`, `parents: []`,
     `description`, `proposal_file: br_proposals/n000_init.md`,
     `created_by_group: bootstrap`, `reference_files: [<imported_path>]`
     and any `requirements_*` / `assumption_*` / `component_*` /
     `tradeoff_*` fields justified by the source text.
   - Phase 4: emit sectioned proposal. Include the shared include
     `<!-- include: _section_format.md -->`.
   - The agent must write ALL output to `_output.md` with the four
     delimiters (mirroring explorer/synthesizer conventions).

2. **`BRAINSTORM_AGENT_TYPES`** — add `"initializer": {"max_parallel": 1,
   "launch_mode": "interactive"}` at the end of the dict at
   `brainstorm_crew.py:44-50`.

3. **`_assemble_input_initializer(session_path, imported_path,
   task_file)`** — mirrors `_assemble_input_explorer` but with:
   - `## Imported Proposal` section pointing to `imported_path`.
   - `## Task File` section pointing to the resolved task file path.
   - `## Mandate` section with a fixed bootstrap-style instruction.
   - NO active-dimensions / no baseline-node blocks (n000_init is the
     target, not a baseline).

4. **`register_initializer(session_dir, crew_id, imported_path,
   task_file, group_name="bootstrap", agent_suffix="",
   launch_mode=DEFAULT_LAUNCH_MODE) -> str`** — agent name is
   `initializer_bootstrap`. Calls `_run_addwork` with type `initializer`,
   then `_write_agent_input` with the assembled content. Returns agent
   name.

5. **`init_session` update** — accept optional `initial_proposal_file`;
   when set:
   - Validate the file exists (raise `FileNotFoundError` otherwise).
   - Write `initial_proposal_file: <abs_path>` into `br_session.yaml`.
   - Build placeholder proposal body:
     `"Awaiting initializer agent output for "
     + os.path.basename(initial_proposal_file)`.
   - Pass `reference_files=[abs_path]` into `create_node(...)` for
     `n000_init`.
   - Keep `description` as a short placeholder too:
     `"Imported proposal (awaiting reformat): <basename>"`.

6. **`apply_initializer_output(task_num)`** — new function at the end of
   `brainstorm_session.py`. Implementation sketch:
   ```python
   wt = crew_worktree(task_num)
   out_path = wt / "initializer_bootstrap_output.md"
   text = out_path.read_text(encoding="utf-8")
   node_yaml_text = _extract_block(text, "NODE_YAML_START", "NODE_YAML_END")
   proposal_text  = _extract_block(text, "PROPOSAL_START",  "PROPOSAL_END")
   node_data = yaml.safe_load(node_yaml_text)
   errs = validate_node(node_data)
   if errs: raise ValueError(f"initializer node YAML invalid: {errs}")
   parsed = parse_sections(proposal_text)
   serrs = validate_sections(parsed)
   if serrs: raise ValueError(f"initializer proposal invalid: {serrs}")
   write_yaml(str(wt / NODES_DIR / "n000_init.yaml"), node_data)
   (wt / PROPOSALS_DIR / "n000_init.md").write_text(proposal_text, encoding="utf-8")
   ```

7. **Bash test `tests/test_apply_initializer_output.sh`** — builds a
   fake session dir with the required directory layout, drops a
   fixture `initializer_bootstrap_output.md` into it, invokes
   `apply_initializer_output` via `python3 -c`, then asserts the
   rewritten `n000_init.yaml` / `n000_init.md` pass `validate_node`
   and `validate_sections` respectively.

## Verification

- `bash tests/test_apply_initializer_output.sh` passes.
- `shellcheck .aitask-scripts/aitask_*.sh` still clean (no new
  shell script except the test fixture).
- `python3 -c "from brainstorm.brainstorm_crew import get_agent_types;
  print(get_agent_types().get('initializer'))"` (run with appropriate
  PYTHONPATH) prints the expected dict with `launch_mode:
  interactive`.
- Manual: create a throw-away session, invoke
  `init_session(task_num, task_file, email, spec='', initial_proposal_file='/tmp/foo.md')`;
  verify `br_session.yaml` has `initial_proposal_file` and
  `br_proposals/n000_init.md` has the placeholder content.
