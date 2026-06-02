---
Task: t573_import_initial_proposal_in_brainstrom.md
Base branch: main
plan_verified: []
---

# t573 — Import initial proposal when initializing a brainstorm session

## Context

Today, `ait brainstorm init <task>` always seeds the root node `n000_init`
with the **verbatim text of the task file** (see
`.aitask-scripts/brainstorm/brainstorm_session.py:94-109`). The root node has
no dimensions extracted, no section markers, and no implementation metadata —
all five brainstorm operations (explore, compare, hybridize, detail, patch)
start from this blank slate.

The user frequently has a pre-existing design proposal (a markdown file they
wrote or received) that they want to use as the **starting point** of an
exploration. Today they have to manually paste its content into the task
description, and the content still wouldn't be parsed into sections /
dimensions.

**Goal:** at init time, let the user point to an external markdown file; a
dedicated code agent reformats it into a proper `n000_init` node with
section-tagged proposal markdown **and** flat YAML dimension metadata, without
touching the original file. Downstream operations (explore, detail, etc.)
then work on a properly structured root node from step zero.

## Scope — what changes

1. A new **`initializer`** brainstorm agent type with its own template and
   registration function (mirrors the existing five: explorer, comparator,
   synthesizer, detailer, patcher).
2. `init_session()` gains an optional `initial_proposal_file` parameter;
   when set, `n000_init` is seeded as a **placeholder** awaiting replacement,
   and the imported file path is recorded in the session metadata.
3. A new ingestion helper `apply_initializer_output()` parses the agent's
   `_output.md` (delimited `NODE_YAML_START/END`, `PROPOSAL_START/END`) and
   rewrites `br_nodes/n000_init.yaml` + `br_proposals/n000_init.md` with the
   agent's structured result.
4. CLI: `ait brainstorm init <task> --proposal-file <path>` — validates the
   file, threads it through, registers the initializer agent, launches the
   runner in **interactive** launch mode so the user can watch the agent in
   a tmux split, and prints a line the TUI can poll on.
5. TUI: `InitSessionModal` grows a third primary button "Import Proposal…"
   which opens a lightweight file-picker (reuses `DirectoryTree` pattern
   from `.aitask-scripts/codebrowser/file_tree.py`). The TUI then shells to
   the same CLI with `--proposal-file`, spawns the interactive runner in
   tmux, and re-reads `n000_init` from disk when the agent reports
   `Completed`.
6. Design docs (`aidocs/brainstorming/brainstorm_engine_architecture.md`)
   and seed configs (`seed/codeagent_config.seed.json` and the live
   `aitasks/metadata/codeagent_config.json`) learn about the new agent type.

Because this touches five distinct layers (template, Python session, CLI,
TUI, docs+config) and introduces a new agent type, it is proposed as a
**parent with child tasks** rather than a single-task implementation.

## Approach — recommended architecture

### Why a *new* agent type (not a reused explorer)

- `explorer` takes a **baseline node** and a **mandate**; it assumes the
  baseline is already well-formed and only produces a *variant*. The init
  use-case has no baseline — the input is an unstructured markdown file.
- `explorer`'s required output sections (Overview / Architecture / Data Flow
  / Components / Assumptions / Tradeoffs) are one possible target shape,
  but the initializer must also **decide when the input doesn't map to those
  six sections** and emit a domain-appropriate structure.
- A dedicated `initializer` template also lets us ask for a conservative
  "don't invent dimensions you can't justify from the text" mandate, which
  doesn't belong in explorer's work2do.

### Why the source file is recorded as a `reference_file`

The user explicitly said *"don't touch original file"*. Persisting the
absolute path in `reference_files` on `n000_init` (in addition to baking the
path into `br_session.yaml` for session-level traceability) keeps the source
discoverable for downstream agents (explorer / detailer) that already know
how to consume `reference_files`.

### Why interactive launch mode

The user answered "Interactive (tmux split), user can observe". The existing
`detailer` agent already defaults to `launch_mode: interactive`
(`.aitask-scripts/brainstorm/brainstorm_crew.py:48`), so we follow that
precedent and set `initializer` → `interactive` in `BRAINSTORM_AGENT_TYPES`.

## Child task breakdown

The split below matches the five-layer touch list and keeps each child
independently reviewable.

### t573_1 — `initializer` agent type + ingestion helper

Files:
- **NEW** `.aitask-scripts/brainstorm/templates/initializer.md` — agent
  prompt. Phase 1: read the imported file and the raw task file. Phase 2:
  classify the content (proposal vs. raw spec vs. mixed), decide on section
  structure. Phase 3: emit `NODE_YAML_START…END` (flat YAML with at minimum
  `node_id: n000_init`, `parents: []`, `description`, `proposal_file`,
  `created_by_group: bootstrap`, `reference_files: [<imported_path>]` plus
  any `requirements_*` / `assumption_*` / `component_*` / `tradeoff_*` keys
  it can justify from the text). Phase 4: emit `PROPOSAL_START…END` with
  section markers.
- `.aitask-scripts/brainstorm/brainstorm_crew.py` —
  - Add `"initializer": {"max_parallel": 1, "launch_mode": "interactive"}`
    to `BRAINSTORM_AGENT_TYPES` (line 44-50).
  - Add `_assemble_input_initializer(session_path, imported_path,
    task_file)` → reads imported file + task file, emits `_input.md` with
    paths + raw content + section-format include directive.
  - Add `register_initializer(session_dir, crew_id, imported_path,
    task_file, group_name="bootstrap", launch_mode="interactive") -> str`.
- `.aitask-scripts/brainstorm/brainstorm_session.py` —
  - `init_session(..., initial_proposal_file: str | None = None)`: when set,
    seed `n000_init` with a **placeholder** body (e.g. `"Awaiting
    initializer agent output for <filename>"`), write
    `initial_proposal_file` into `br_session.yaml`, and set session
    `status: init` (unchanged — finalize still flips to `active`).
  - New `apply_initializer_output(task_num) -> None`: locates the
    `initializer_bootstrap_output.md` in the crew worktree, parses the four
    delimiter blocks, validates with `validate_node()` + `validate_sections()`
    from existing modules, overwrites `br_nodes/n000_init.yaml` and
    `br_proposals/n000_init.md`. Raises `ValueError` on malformed output.
- **NEW** `tests/test_apply_initializer_output.sh` — bash test with a
  fixture output file; asserts node YAML and proposal MD are rewritten and
  `validate_node()` returns empty errors.

### t573_2 — CLI: `ait brainstorm init --proposal-file`

Files:
- `.aitask-scripts/aitask_brainstorm_init.sh` — add `--proposal-file <path>`
  arg; validate the file exists, is readable, is not empty, has `.md` or
  `.markdown` extension (warn-only). Pass through to `brainstorm_cli.py`.
- `.aitask-scripts/brainstorm/brainstorm_cli.py` —
  - `cmd_init`: accept `--proposal-file`; call `init_session(...,
    initial_proposal_file=...)`.
  - After session init succeeds and when `--proposal-file` was set: call
    `register_initializer(...)` then print
    `INITIALIZER_AGENT:<agent_name>` on stdout.
- `.aitask-scripts/aitask_brainstorm_init.sh` — if the CLI printed
  `INITIALIZER_AGENT:` and `--proposal-file` was given: start the runner
  (`ait crew run --id brainstorm-<task> --detach`) so the interactive agent
  actually fires; print a one-line hint telling the user they can attach
  via `ait crew attach` or `ait brainstorm <task>`.

### t573_3 — TUI init modal: file picker + auto-launch + re-render

Files:
- `.aitask-scripts/brainstorm/brainstorm_app.py`:
  - `InitSessionModal`: replace the two-button row with three buttons
    "Initialize Blank" / "Import Proposal…" / "Cancel". `dismiss()` now
    returns one of `"blank" | "import:<abs_path>" | None`.
  - New `ImportProposalFilePicker(ModalScreen)` — Textual `DirectoryTree`
    rooted at cwd; `Enter` on a `.md` file dismisses with the absolute path,
    `escape` dismisses with `None`. Reuses styling patterns from the
    existing modals.
  - `_on_init_result`: branches on the three return values; the import path
    shells to `ait brainstorm init <task> --proposal-file <path>` and then
    polls the crew worktree until the initializer agent reaches
    `Completed` (use existing `list_agent_files` + a `set_interval`). On
    `Completed`: call `apply_initializer_output(task_num)` then
    `_load_existing_session()` to refresh the DAG pane.
  - On `Error` / `Aborted` status: `self.notify(..., severity="error")`
    and fall back to `_load_existing_session()` (the placeholder n000_init
    is still valid; user can manually retry).

### t573_4 — Docs, seed config, and config plumbing

Files:
- `aidocs/brainstorming/brainstorm_engine_architecture.md`: document the
  sixth agent type in §5 and the import-file init flow in §7; update the
  "High-Level Architecture" ASCII art to include `initializer`.
- `aitasks/metadata/codeagent_config.json`: add
  `"brainstorm-initializer": "<same default as explorer>"` under
  `defaults`. This is required because `get_agent_types()` in
  `brainstorm_crew.py:72-86` raises if any `brainstorm-<type>` key is
  missing.
- `seed/codeagent_config.seed.json` — mirror of above for new projects
  bootstrapped via `ait setup`.
- `aitask_brainstorm_init.sh` already enumerates all agent types when
  creating the crew (line 128-134); add the `--add-type` line for
  `initializer` so `ait crew init` registers its config up-front.

### t573_5 — Manual verification (aggregate, `issue_type: manual_verification`)

Scope: this child has no code changes; it is a checklist run after
t573_1..4 are merged.

Checklist items (seeded from children's `## Verification` sections):
- [t573_1] Unit test `tests/test_apply_initializer_output.sh` passes.
- [t573_1] With a hand-crafted fixture `_output.md` and a placeholder
  session, `apply_initializer_output()` leaves `n000_init` valid
  (`validate_node` returns `[]`, `validate_sections` returns `[]`).
- [t573_2] `ait brainstorm init 42 --proposal-file bogus` fails with a
  clear error before touching any git state.
- [t573_2] `ait brainstorm init 42 --proposal-file real.md` creates the
  crew, seeds the placeholder node, registers the initializer agent, and
  prints `INITIALIZER_AGENT:initializer_bootstrap`. Crew runner starts.
- [t573_3] Inside TUI (`ait brainstorm 42`) for a task with no session:
  modal shows three buttons. "Import Proposal…" opens the file-picker,
  selecting a `.md` file starts the flow, the TUI blocks with a spinner
  until the agent completes, then the DAG view repopulates with a proper
  `n000_init` node having visible dimensions.
- [t573_3] Imported source file is **unmodified** on disk after the flow
  (mtime unchanged, byte-for-byte identical).
- Cross-cutting: `grep -rn "initializer" aidocs/brainstorming/` yields
  updated documentation; `ait crew init --help` mentions no new flags
  (we're extending brainstorm init, not crew init).

## Key existing code to reuse

- Node/section validators — `validate_node()`, `validate_sections()` in
  `.aitask-scripts/brainstorm/brainstorm_schemas.py` and
  `.aitask-scripts/brainstorm/brainstorm_sections.py`.
- Section format include — `.aitask-scripts/brainstorm/templates/_section_format.md`
  (already referenced by explorer/detailer templates via `<!-- include: -->`).
- Directory tree widget — pattern in
  `.aitask-scripts/codebrowser/file_tree.py:ProjectFileTree`.
- Launch-mode constants — `VALID_LAUNCH_MODES`, `DEFAULT_LAUNCH_MODE` from
  `.aitask-scripts/lib/launch_modes.py`.
- Subprocess-plus-parse pattern — `_run_init()` in `brainstorm_app.py:3050`.

## Risks / open items

1. **Output parsing has no precedent.** Explorer/synthesizer templates
   already emit `NODE_YAML_START/END` delimiters but **nothing in the repo
   parses them today** — agent outputs currently live at `_output.md` and
   are consumed only visually. `apply_initializer_output()` in t573_1 is
   the first such parser; if it proves useful, explorer/synthesizer output
   ingestion is a natural follow-up (not in scope for t573).
2. **Interactive launch in a non-tmux env.** `register_initializer` sets
   `launch_mode=interactive`; `is_tmux_available()` already guards fall-back
   to headless in the existing agent dispatch path. The TUI still needs to
   handle the headless fallback (poll + notify), which is covered in t573_3.
3. **Agent failure mode.** If the initializer agent errors out, `n000_init`
   stays on the placeholder. Manual verification covers the visual signal
   ("Error" severity notification + session remains usable). No silent data
   loss because the source file is untouched.

## Follow-up: Adding a new frontmatter/script touchpoint

This task adds no new frontmatter field and no new helper script, so the
5-touchpoint whitelist checklist in `CLAUDE.md` does not apply.

## Verification

See the checklist in **t573_5** above. The parent task is considered done
when all five children are archived and the manual-verification run passes.
