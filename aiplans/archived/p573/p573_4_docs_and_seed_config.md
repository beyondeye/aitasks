---
Task: t573_4_docs_and_seed_config.md
Parent Task: aitasks/t573_import_initial_proposal_in_brainstrom.md
Sibling Tasks: aitasks/t573/t573_1_*.md, aitasks/t573/t573_2_*.md, aitasks/t573/t573_3_*.md
Archived Sibling Plans: aiplans/archived/p573/p573_*_*.md
Worktree: (none — fast profile works on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-23 18:04
---

# t573_4 — Docs for the `initializer` agent type

## Context

Final docs child for t573 — keeps the design documentation in sync
with the `initializer` agent type introduced by the three preceding
siblings. The parent goal is a `ait brainstorm init --proposal-file`
path (CLI and TUI) that reformats an imported markdown file into a
structured `n000_init` root node via a single-purpose `initializer`
agent.

## Verification-pass findings (vs. original plan)

Original plan had 4 steps. On re-verification against the current
codebase (state at 2026-04-23), steps 1, 2, and 4 collapse to
no-ops or invariant violations. Only step 3 (design doc) carries
substantive work, and that scope is expanded to cover several
additional 5-agent-type references the original plan didn't name.

| Original step | Status | Reason |
|---|---|---|
| 1. Runtime config — add `brainstorm-initializer` to `aitasks/metadata/codeagent_config.json` | **Already done by t573_1** | Key is present at line 14 with value `"claudecode/sonnet4_6"`. See `aiplans/archived/p573/p573_1_…md:396-397` (Final Implementation Notes). |
| 2. Seed config — mirror key to `seed/codeagent_config.seed.json` | **Drop — violates invariant** | The seed file is `seed/codeagent_config.json` (no `.seed.json` variant exists). Invariant from `tests/test_add_model.sh:181` and p573_1 notes (lines 420-424): `seed/codeagent_config.json` intentionally contains **no** `brainstorm-*` keys — those are supplied to runtime configs via `ait setup`. Adding the key would fail `test_add_model.sh`. |
| 4. Sanity-check `--add-type initializer` in `aitask_brainstorm_init.sh` | **Pre-verified** | Present at line 159 (plan referenced stale line range 128-134). No action. |

Step 3 (design doc) remains — expanded in scope below.

## Implementation steps

### 1. Update `aidocs/brainstorming/brainstorm_engine_architecture.md`

Five edits, all written in positive/current-state prose per CLAUDE.md
Documentation Writing section (no "previously" / "now" / "used to be"
framing).

**1a. High-level architecture ASCII art (lines 62-63)** — extend the
agent-type list inside the AgentCrew Orchestration Layer box to
include `initializer`. Current:

```
│   Agent types: explorer, comparator, synthesizer,        │
│                detailer, patcher                          │
```

Target:

```
│   Agent types: explorer, comparator, synthesizer,        │
│                detailer, patcher, initializer            │
```

Preserve the right-hand `│` column alignment (width-match against
the longest existing row).

**1b. Source Code Layout table (line 162)** — update the
`brainstorm_crew.py` row to list `register_initializer` in the
register-function list:

Current: `Agent registration (register_explorer, register_comparator, register_synthesizer, register_detailer, register_patcher) and _assemble_input_* helpers`

Target: same list with `, register_initializer` appended before the
closing `)`.

**1c. Templates directory row (line 164)** — update the
`templates/` row so the file list includes `initializer.md`:

Current: `(explorer.md, comparator.md, synthesizer.md, detailer.md, patcher.md) plus the shared include _section_format.md`

Target: same list with `, initializer.md` inserted (before the
shared-include phrase).

**1d. §5 — Agent Type Definitions YAML block (lines 555-577)** —
append an `initializer:` entry to the YAML example so it shows all
six types. The values must match the runtime-config defaults already
in `aitasks/metadata/codeagent_config.json` and the programmatic
defaults in `BRAINSTORM_AGENT_TYPES` (see
`.aitask-scripts/brainstorm/brainstorm_crew.py`):

```yaml
  initializer:
    agent_string: claudecode/sonnet4_6   # Structured markdown reformat, interactive handoff
    max_parallel: 1                       # One initializer per session (singleton)
    launch_mode: interactive              # Runs in an interactive subagent so the user watches the reformat live
```

Also append a short paragraph after the block noting the singleton
semantics (agent name is the fixed literal `initializer_bootstrap`,
no `_group_seq` increment) to parallel the existing text about
`explorer_001a` / `explorer_001b` naming. Cross-reference the §7
subsection added in 1e.

**1e. §7 Orchestration Flow — new subsection "7.1a Initialize with
an imported proposal"** — insert immediately after §7.1
(Initialization) and before §7.2 (Explore). Structure mirrors §7.2
(Trigger / What happens / Inputs / Outputs / What the user decides
next). Content to cover:

- **Trigger:** user invokes `ait brainstorm init <task_num> --proposal-file <path>` (CLI) or clicks "Import Proposal…" in the `InitSessionModal` three-button TUI (Blank / Import Proposal… / Cancel).
- **What happens:**
  1. `cmd_init` runs the same crew-init sequence as §7.1.
  2. Session seeds `br_proposals/n000_init.md` with the placeholder `Awaiting initializer agent output for <basename>.` (see p573_2 plan line 521-525).
  3. `register_initializer(...)` registers a single agent of type `initializer` in a bootstrap operation group, agent name fixed to `initializer_bootstrap` (no `_group_seq`).
  4. Agent consumes the imported file + task spec, produces a sectioned proposal plus flat YAML node metadata in `_output.md`.
  5. `apply_initializer_output(task_num)` parses `_output.md`, overwrites `n000_init.md` and `n000_init.yaml`, and seeds `active_dimensions` from the extracted metadata.
- **Canonical stdout markers (stable, consumed by the TUI poll loop):** `SESSION_PATH:<abs path>`, `INITIALIZER_AGENT:initializer_bootstrap`, `RUNNER_STARTED:brainstorm-<N>`. Canonical stderr marker: `RUNNER_START_FAILED:brainstorm-<N>`. (Per p573_2 Final Implementation Notes — renaming these breaks the TUI silently.)
- **Inputs:** task number, task file path, user email, imported markdown file path.
- **Outputs:** same as §7.1 plus a fully-populated `n000_init` node (proposal + YAML) instead of the empty placeholder.
- **What the user decides next:** explore from the initialized node, or edit the initial proposal manually before further operations.

Mention that sessions initialized via the blank path (§7.1) still
produce the unpopulated placeholder `n000_init` — both entry points
remain first-class.

## Out-of-scope (do not touch)

- `aitasks/metadata/codeagent_config.json` — already has the key (t573_1).
- `seed/codeagent_config.json` — invariant forbids `brainstorm-*` keys.
- `.aitask-scripts/settings/settings_app.py` `OPERATION_DESCRIPTIONS` — already has `brainstorm-initializer` and `brainstorm-initializer-launch-mode` entries (t573_1, lines 141 + 147).
- `.aitask-scripts/aitask_brainstorm_init.sh` — `--add-type initializer` already wired at line 159 (t573_2).
- Manual-verification sibling behaviour — that's t573_5 (separate task).

## Verification

- `grep -c "initializer" aidocs/brainstorming/brainstorm_engine_architecture.md` returns ≥6 (ASCII art + register list + templates list + §5 YAML block + §5 singleton paragraph + §7.1a subsection header — plus any in-body references).
- `grep -En "previously|used to be|no longer|formerly|earlier this" aidocs/brainstorming/brainstorm_engine_architecture.md` returns no new matches in the diff.
- `python3 -c "import json; d=json.load(open('aitasks/metadata/codeagent_config.json')); print(d['defaults']['brainstorm-initializer'])"` prints `claudecode/sonnet4_6` (regression assertion, no change expected).
- `python3 -c "import json; d=json.load(open('seed/codeagent_config.json')); assert 'brainstorm-initializer' not in d.get('defaults', {}), 'seed must not contain brainstorm-* keys'"` exits 0 (invariant assertion).
- `bash tests/test_add_model.sh` passes (existing test; should be unaffected but run as a regression check because it asserts the seed invariant).
- `./ait git diff aidocs/brainstorming/brainstorm_engine_architecture.md` — review for tone (current-state only) and that the ASCII-art column alignment is preserved.

## Notes for sibling tasks

- None. After this child, t573_5 (manual-verification sibling) is the
  last remaining task on t573.

## Step 9 (Post-Implementation)

Follow the shared Step 9 (commit on current branch, plan-file
commit via `./ait git`, then `aitask_archive.sh 573_4`, then push).
No branch/worktree cleanup — fast profile keeps work on `main`.

## Final Implementation Notes

- **Actual work done:** Five edits to `aidocs/brainstorming/brainstorm_engine_architecture.md`:
  - ASCII-art agent-type list (§1 High-Level Architecture) — appended `initializer` to line 63, preserving the existing 61-char visual width.
  - Source-code-layout table row for `brainstorm_crew.py` (§2) — added `register_initializer` to the `register_*` list.
  - Source-code-layout table row for `templates/` (§2) — added `initializer.md` to the template file list.
  - §5 Agent Type Definitions YAML block — appended an `initializer:` entry with `agent_string: claudecode/sonnet4_6`, `max_parallel: 1`, `launch_mode: interactive`, plus a fifth naming-convention bullet documenting the fixed-literal `initializer_bootstrap` agent name and cross-referencing §7.1a.
  - §7 Orchestration Flow — added a new subsection `### 7.1a Initialize with an imported proposal` between §7.1 and §7.2, covering the CLI and TUI trigger paths, the placeholder → initializer → `apply_initializer_output()` sequence, canonical stdout/stderr markers, inputs/outputs, and "what the user decides next." Also added one-sentence cross-references from §7.1 to §7.1a so blank and imported-proposal paths are mutually signposted.

- **Deviations from plan — scope correction during verify pass:** Original plan's step 1 (runtime config) was already done by t573_1 — skipped. Original plan's step 2 (seed config) would have violated the invariant asserted by `tests/test_add_model.sh:181` (seed file must not gain `brainstorm-*` keys) — dropped with a rationale table at the top of this plan. Original plan referenced `seed/codeagent_config.seed.json`; that path does not exist — the actual seed file is `seed/codeagent_config.json`. Original plan's sanity check on the `--add-type initializer` line referenced lines 128-134 of `aitask_brainstorm_init.sh`; the line is actually at 159 — pre-verified before ExitPlanMode, no code touched. The verify pass expanded the docs scope to cover four more 5-agent-type references the original plan didn't name (table row at line 162, template list at line 164, YAML block at lines 555-577, and a cross-reference from §7.1).

- **Issues encountered:** None. All edits landed in one Edit pass per block. No test regressions.

- **Key decisions:**
  - Documented the singleton semantics (`initializer_bootstrap`, no `<group_sequence>`) in the §5 naming-convention bullet list, parallel to the existing `explorer_001a` / `comparator_002` / `synthesizer_003` bullets — keeps the pattern discoverable at the same section level as the other five types.
  - Kept the §7.1 / §7.1a split (instead of rewriting §7.1 as one unified subsection) so the blank-init and imported-proposal paths remain distinct first-class entry points, matching the TUI's three-button modal.
  - Used 61-char width on the updated ASCII-art line 63 to match its prior width (the neighbouring box is already visually inconsistent — some lines 60, some 61 — so minimum-change was the right call; a pure-alignment fix is out of scope).

- **Verification results:**
  - `grep -c "initializer" aidocs/brainstorming/brainstorm_engine_architecture.md` → 11 (target ≥6).
  - `grep -En "previously|used to be|no longer|formerly|earlier this" aidocs/brainstorming/brainstorm_engine_architecture.md` → 2 pre-existing matches (line 257: "no longer relevant" describing runtime dimension pruning; line 1033: "previously-checked" describing UI state) — neither introduced by this change and neither historical-framing of the doc itself.
  - `python3 -c "…codeagent_config.json…brainstorm-initializer"` → `claudecode/sonnet4_6` (runtime assertion).
  - `python3 -c "…seed/codeagent_config.json…assert 'brainstorm-initializer' not in …"` → exit 0 (invariant assertion).
  - `bash tests/test_add_model.sh` → 30/30 PASS.

- **Notes for sibling tasks (t573_5 only):**
  - Manual-verification sibling should cover the TUI-side import-proposal flow end-to-end (Import Proposal… → file picker → agent launch → placeholder swap → n000_init populated) in addition to the CLI flow. The canonical stdout/stderr markers documented in §7.1a are load-bearing for the TUI poll loop — any marker rename is a silent-break risk and belongs in the manual-verification checklist.
