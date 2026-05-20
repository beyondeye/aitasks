---
Task: t807_synthetize_or_hybridize.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t807 — Unify `hybridize` → `synthesize` naming in the brainstorm TUI

## Context

In the `ait brainstorm` TUI, one DAG operation merges multiple proposal nodes
into one. It is inconsistently named: the **operation** is keyed `hybridize`
(op key, wizard, conditionals, DAG badge color, UI label "Hybridize", "hybrid
node" prose), while the **agent** that performs it — plus every config/settings
key — is already `synthesizer` (`synthesizer.md` template, `register_synthesizer`,
`brainstorm-synthesizer` in `codeagent_config.json`).

**Decisions (confirmed with the user):**
- Adopt **`synthesize`** as the uniform term (correct spelling — not the archaic
  "synthetize"). This makes a clean verb/noun pair: op `synthesize` + agent
  `synthesizer`. It is also the lowest-churn choice — the agent, template, and
  user-facing config keys already use the `synthes-` family and stay untouched.
- A third term, `merge`, was considered and rejected: it collides with the
  framework's existing git-merge / folded-task "merged" vocabulary.
- **Backward compatibility:** in-flight brainstorm sessions on disk persist
  `operation: hybridize` / `created_by_group: hybridize_NNN` in `.aitask-crews/`
  worktrees. These must keep rendering — implement a normalization alias rather
  than a clean break.

The task file name (`t807_synthetize_or_hybridize.md`) keeps its misspelling;
it is archived as-is on completion and not renamed.

## Backward-compat design (verified against read sites)

Persisted group keys (`hybridize_003`) and `created_by_group` values are opaque
identifiers at read time — only `_group_seq()` parses them, and it extracts just
the numeric suffix (`brainstorm_crew.py`). `GROUP_OPERATIONS` is used **only** by
`tests/test_brainstorm_dag_op_badge.py`; there is no runtime group validator, so
a legacy `operation: hybridize` is never rejected. **No data migration needed.**

The only thing needing a compat shim is the `operation` *field value*, which two
dicts key on: `_OP_INPUT_SECTION` (`brainstorm_op_refs.py`) and `OP_BADGE_STYLES`
(`brainstorm_dag_display.py`). Add one normalization helper applied at both
read-from-disk boundaries, plus keep `hybridize` as a defensive alias key in both
dicts.

New helper in `.aitask-scripts/brainstorm/brainstorm_schemas.py` (next to
`GROUP_OPERATIONS`):

```python
# Legacy operation names kept readable for in-flight sessions on disk.
# t807 renamed the DAG op "hybridize" -> "synthesize" (agent stays
# "synthesizer"). Old br_groups.yaml entries / created_by_group values
# still carry "hybridize"; canonical_op() normalizes them at read time.
_LEGACY_OP_ALIASES = {"hybridize": "synthesize"}


def canonical_op(op: str) -> str:
    """Normalize a persisted operation name to its current canonical form.

    Legacy in-flight brainstorm sessions persist ``operation: hybridize``;
    this maps it to ``synthesize``. Current / unknown values pass through.
    """
    return _LEGACY_OP_ALIASES.get(op, op)
```

## File-by-file changes

### A. `.aitask-scripts/brainstorm/brainstorm_schemas.py`
- Line 56: `GROUP_OPERATIONS` — `"hybridize"` → `"synthesize"`.
- Add `_LEGACY_OP_ALIASES` + `canonical_op()` (code above).

### B. `.aitask-scripts/brainstorm/brainstorm_session.py`
- Lines 577-578 `role_to_group` in `_agent_to_group_name`: `"synthesizer": "hybridize"`
  → `"synthesizer": "synthesize"`. **Load-bearing** — sets `created_by_group` on
  every new synthesizer node (line 926); must match `_next_group_name("synthesize")`
  → `synthesize_NNN`. Update the docstring if it mentions hybridize.
- Line 1062 docstring: "new hybrid" → "new synthesized node".

### C. `.aitask-scripts/brainstorm/brainstorm_app.py`
- Line 136 `_WIZARD_OP_TO_AGENT_TYPE`: key `"hybridize"` → `"synthesize"` (value
  stays `"synthesizer"`).
- Line 177 `_DESIGN_OPS`: `("synthesize", "Synthesize", "Merge multiple nodes into a synthesis")`.
- Lines 282-308 `_OPERATION_HELP`: key `"hybridize"` → `"synthesize"`; `title` →
  `"Synthesize — Architecture Synthesizer"`; summary reword "single hybrid node"
  → "single synthesized node", "The hybrid lists" → "The synthesized node lists".
- Line 2671 comment "single hybrid node" → "single synthesized node".
- Conditionals — `"hybridize"` → `"synthesize"` at lines 2891, 2949, 3434, 5072,
  5081, 5292, 5398, 5451, 5638.
- Lines 5082 + 5163: rename `_config_hybridize` → `_config_synthesize`
  (definition + call site); update its docstring.
- Widget id `hyb_nodes` → `syn_nodes` at lines 3435, 5170, 5435 — rename all
  three together (internal Textual id, never persisted).

### D. `.aitask-scripts/brainstorm/brainstorm_dag_display.py`
- Lines 56-63 `OP_BADGE_STYLES`: rename `"hybridize"` → `"synthesize"`; add a
  defensive `"hybridize": Style(color="#FF79C6")` alias with a `# legacy alias (t807)`
  comment.
- Line 106 (`_build_graph`): wrap the operation read with `canonical_op(...)`;
  add `from brainstorm.brainstorm_schemas import canonical_op`.

### E. `.aitask-scripts/brainstorm/brainstorm_op_refs.py`
- Line 18 `_OP_INPUT_SECTION`: rename `"hybridize"` → `"synthesize"`; add a
  defensive `"hybridize": "Merge Rules"` alias with a `# legacy alias (t807)`
  comment.
- Line 96 `list_op_inputs()`: wrap `op` with `canonical_op()`; add the import.

### F. `.aitask-scripts/brainstorm/brainstorm_crew.py`
- Line 605 docstring example `"hybridize_001"` → `"synthesize_001"`.

### G. `.aitask-scripts/brainstorm/brainstorm_dag.py`
- Line 173 comment "(hybridization)" → "(synthesis)".

### H. `.aitask-scripts/aitask_brainstorm_apply_synthesizer.sh`
- Line 6 comment "new hybrid node" → "new synthesized node".

### I. `.aitask-scripts/brainstorm/templates/synthesizer.md`
- Prose only — lines 51, 68, 69, 130: "the hybrid" → "the synthesized node".
- **Do NOT** rename the `## Merge Rules` section header. It is written by
  `_assemble_input_synthesizer()` (`brainstorm_crew.py`) and read back via
  `_OP_INPUT_SECTION`/`_extract_md_section`; renaming it is a separate
  input-contract change, out of scope for t807. (Not a `.j2` template and not
  part of any skill closure — no `aitask_skill_verify.sh` / golden regeneration.)

### J. Tests
- `tests/test_brainstorm_op_refs.py:182`: `"hybridize"` → `"synthesize"`. Read the
  surrounding assertion first — if it snapshots the whole `_OP_INPUT_SECTION` dict,
  include the `hybridize` alias key in the expected dict or switch to per-key asserts.
- `tests/test_brainstorm_apply_synthesizer.py`: flip `created_by_group="hybridize_001"`
  fixtures and the line 281 assertion to `synthesize_001`; update the line 272
  comment. Rename cosmetic fixture node ids `n002_hybrid`/`n003_hybrid` →
  `n002_synth`/`n003_synth` (default arg + all call sites).
- `tests/test_brainstorm_crew.py` / `tests/test_brainstorm_dag.py`: rename cosmetic
  `n003_hybrid` fixture ids → `n003_synth`.
- **New regression test** in `tests/test_brainstorm_op_refs.py`:
  ```python
  def test_legacy_hybridize_operation_still_resolves(self):
      # Backward-compat (t807): in-flight sessions persist
      # operation: hybridize; it must still resolve to Merge Rules.
      legacy = list_op_inputs({"operation": "hybridize",
                               "agents": ["synthesizer_001"]})
      current = list_op_inputs({"operation": "synthesize",
                                "agents": ["synthesizer_001"]})
      self.assertEqual(legacy[0].section, "Merge Rules")
      self.assertEqual(legacy[0].section, current[0].section)
  ```
- **New `canonical_op` unit test** (in `tests/test_brainstorm_op_refs.py`):
  assert `canonical_op("hybridize") == "synthesize"`, `canonical_op("synthesize")
  == "synthesize"`, `canonical_op("explore") == "explore"`.

### K. Docs (`aidocs/` — design docs describe current state, so update)
- `aidocs/brainstorming/brainstorm_engine_architecture.md`: section 7.4 "Hybridize"
  → "Synthesize"; `hybridize_NNN` group examples → `synthesize_NNN`; "hybrid"
  prose → "synthesized"; add a one-line note that legacy `hybridize` data is
  normalized via `canonical_op`.
- `aidocs/agentcrew/agentcrew_architecture.md:333`: update the term.
- `aidocs/brainstorming/module_decomposition_design.md` (lines 18, 138, 163, 361,
  384, 560): update references.
- Leave `aidocs/brainstorming/building_an_iterative_ai_design_system.md` as-is —
  an early design-exploration narrative, not a current-state spec.
- `aidocs/tui_conventions.md`: no change — the `ctrl+shift+y retry_synthesizer_apply`
  binding references the *agent* `synthesizer`, which is unchanged.

### L. Do NOT touch
`CHANGELOG.md`, `CHANGELOG_HUMANIZED.md`, `website/content/blog/*` — historical
release notes.

## Verification

Run from the repo root with the ait Python:
- `python tests/test_brainstorm_op_refs.py` — `_OP_INPUT_SECTION` rename, alias,
  new `canonical_op` + legacy-resolve tests.
- `python tests/test_brainstorm_apply_synthesizer.py` — confirms the
  `_agent_to_group_name` change (`created_by_group: synthesize_NNN`).
- `python tests/test_brainstorm_crew.py`, `python tests/test_brainstorm_dag.py`,
  `python tests/test_brainstorm_dag_op_badge.py` — badge map + `GROUP_OPERATIONS`.
- Broad: `python -m pytest tests/test_brainstorm_*.py`.
- `shellcheck .aitask-scripts/aitask_brainstorm_apply_synthesizer.sh`.

Manual TUI check (`ait brainstorm`):
1. Operation wizard Step 1 lists "Synthesize"; `?` help modal shows the new title.
2. Run a synthesize op; new node badge shows `[synthesize]` (magenta);
   `br_groups.yaml` has `operation: synthesize` + key `synthesize_NNN`; node YAML
   `created_by_group: synthesize_NNN`.
3. Against a scratch worktree with a hand-crafted `operation: hybridize` group,
   the graph badge still renders `[synthesize]` magenta (not italic "unknown")
   and the operation-detail modal still shows the Merge Rules input section.

## Risks

1. **Lockstep (highest):** `_agent_to_group_name` (session.py `role_to_group`)
   and `_next_group_name` (wizard op key) must both yield `synthesize_NNN`. Change
   both together. (If they drift, `resolve_node_group`'s `nodes_created` fallback
   still works, but it is sloppy.)
2. `test_brainstorm_apply_synthesizer.py:281` hard-asserts the literal group name —
   fails until updated. Expected.
3. Canonicalizing in `brainstorm_dag_display.py` means a legacy `hybridize` node
   renders `[synthesize]` — intentional per the uniform-naming goal; the badge no
   longer literally mirrors on-disk data. Noted in the PR.
4. Whole-dict snapshot test on `_OP_INPUT_SECTION` would break on the added alias
   key — include the alias in expected, or assert per-key.

## Step 9 — Post-Implementation
On the current branch (no worktree): commit code + plan separately, then archive
via `./.aitask-scripts/aitask_archive.sh 807` and `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Renamed the brainstorm DAG merge operation `hybridize` →
  `synthesize` across code, tests, and `aidocs/` design docs, exactly as planned.
  17 files changed. The agent role / template / config keys were already in the
  `synthes-` family and stayed untouched, so the op key + agent name are now a
  consistent verb/noun pair. Added `canonical_op()` + `_LEGACY_OP_ALIASES` in
  `brainstorm_schemas.py` and applied it at the two read-from-disk boundaries
  (`brainstorm_op_refs.list_op_inputs`, `brainstorm_dag_display._build_graph`),
  plus kept `hybridize` as a defensive alias key in `_OP_INPUT_SECTION` and
  `OP_BADGE_STYLES` — so legacy in-flight sessions with `operation: hybridize`
  still resolve the Merge Rules section and render the magenta badge.
- **Deviations from plan:** One deliberate deviation — the plan said to *leave*
  illustrative node-id examples (`n003_hybrid_db`, `n003_hybrid`) in the docs and
  test fixtures. They were instead **renamed** to `n003_synth_db` / `n003_synth`
  for true terminology uniformity (the task's explicit goal); a half-renamed doc
  would have been worse. `## Merge Rules` (the synthesizer input-contract section
  header) was kept as planned — renaming it is a separate input-contract change.
- **Issues encountered:** None functional. Tooling note: the `Edit` tool rejects
  edits to a file only partially read via `Read` — large files (e.g.
  `brainstorm_engine_architecture.md`, 1863 lines) had to be read fully first.
- **Key decisions:** `synthesize` chosen over `hybridize`/`merge` (user-confirmed);
  backward-compat alias chosen over a clean break (user-confirmed). Box-drawing
  diagram line in the architecture doc had a trailing space trimmed to preserve
  alignment after `hybridize`(9)→`synthesize`(10).
- **Upstream defects identified:** `tests/test_brainstorm_apply_patcher_cli.sh` —
  the `FAIL: graph state not advanced` sub-check fails on the pristine tree (HEAD
  8e483a4e), independent of t807. The patcher CLI apply path does not advance
  `br_graph_state.yaml`'s head. Out of scope for t807 but worth a separate bug
  task.
- **Build verification:** all 9 brainstorm Python test files pass; the 7 changed
  brainstorm modules compile; `shellcheck` clean (info-level SC1091 only); the
  3 brainstorm shell tests run, with only the pre-existing patcher-CLI failure
  noted above.
