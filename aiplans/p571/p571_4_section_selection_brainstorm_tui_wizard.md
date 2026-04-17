---
Task: t571_4_section_selection_brainstorm_tui_wizard.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_1_*.md, aitasks/t571/t571_2_*.md, aitasks/t571/t571_3_*.md, aitasks/t571/t571_5_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-17 11:19
---

# Plan: t571_4 — Section Selection in Brainstorm TUI Wizard

## Context

The brainstorm TUI runs a 3- or 4-step wizard per design operation (explore, compare, hybridize, detail, patch). Previous siblings added:

- `brainstorm_sections.py` (t571_1): `parse_sections(text) -> ParsedContent` with `ContentSection(name, dimensions, content, start_line, end_line)`.
- Templates (t571_2) that emit section-wrapped content.
- `brainstorm_crew.py` (t571_3): `register_explorer`, `register_comparator`, `register_detailer`, `register_patcher` all accept `target_sections: list[str] | None = None`; the matching `_assemble_input_*` helpers filter the agent's `_input.md` accordingly.

What's still missing is the UI: users cannot choose sections when launching an operation. This plan adds an optional **section-selection step** to the wizard. When the node's proposal/plan has structured sections, the wizard inserts the new step between node selection and config (explore/patch) or between node selection and confirm (detail). When there are no sections, the wizard is unchanged. Compare appends section checkboxes to its existing combined config step (MVP: union of all candidate nodes' sections).

## Pre-Implementation: Scaffold two sibling/follow-up tasks

Before any code changes to `brainstorm_app.py`, create two new tasks via `aitask_create.sh --batch`. The verification steps for this task will live in the first one; the second is a design/impl follow-up for a generalized manual-verification module.

### PI-1. Manual Verification sibling — `t571_7_manual_verification_structured_brainstorming`

- Child of t571, issue_type `test`, priority `medium`, effort `medium`, labels `[brainstorming, ait_brainstorm, manual, verification]`.
- `depends: [t571_4, t571_5]` — can only be executed after both TUI-heavy siblings land.
- Initial description: the full **Verification** checklist below (all 8 numbered steps), with a note that the list will be appended to as t571_5 completes, documenting its manual checks too.
- Include an **Aggregation Convention** section at the top of the task body:
  > This task aggregates manual verification steps for every sibling of t571 that requires in-person TUI or end-to-end verification. When a future sibling task (e.g., t571_5) finishes implementation, its own verification checklist is appended here under its own `## t571_<N>` heading, dependencies are updated, and the original sibling's "Verification" section points here instead of repeating the steps inline.

This single convention replaces inline "Verification" sections in t571_4 and t571_5 and makes the verification burden visible and pickable as its own task.

### PI-2. Follow-up meta-task — `task-workflow manual-verification module`

- New **parent** task (not a child of t571). Name e.g. `manual_verification_module_for_task_workflow`.
- issue_type `feature`, priority `medium`, effort `high`, labels `[task_workflow, framework, skill]`.
- Description captures the user's stated vision:
  - A new "module" (skill or workflow branch) for `/aitask-pick` that activates when the picked task has `issue_type: manual_verification` or a frontmatter flag like `requires_manual_verification: true`.
  - The wizard presents each verification step as a checkable item (unchecked / passed / failed / skipped), persists state to the task file, and refuses to archive until every item has a terminal state.
  - On a failed item the module prompts to auto-create a **follow-up bug task** pre-populated with:
    - The originating feature task ID and the commit(s) that introduced the verified code
    - Direct links to the implementing source files (from the feature task's plan `Final Implementation Notes`)
    - The exact manual step that failed (copy-pasted)
    - A back-reference from the feature task's archived plan to the new follow-up task
  - Shared "verification aggregate" tasks (like PI-1) are first-class: the module recognizes `verifies: [t571_4, t571_5]` frontmatter and routes check-off state per feature task.
  - Out of scope for the follow-up (noted explicitly): automated Pilot/TUI testing orchestration — that belongs in aitask-qa.
- Reference this plan (`aiplans/p571/p571_4_…md`) and the PI-1 sibling as the motivating use case.

### Batch creation commands

Follow the **Batch Task Creation Procedure** (`task-creation-batch.md`). Sketch:

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --parent 571 \
  --name manual_verification_structured_brainstorming \
  --priority medium --effort medium --issue-type test \
  --labels brainstorming,ait_brainstorm,manual,verification \
  --depends t571_4,t571_5 \
  --desc-file /tmp/t571_7_desc.md \
  --commit

./.aitask-scripts/aitask_create.sh --batch \
  --name manual_verification_module_for_task_workflow \
  --priority medium --effort high --issue-type feature \
  --labels task_workflow,framework,skill \
  --desc-file /tmp/metaverify_desc.md \
  --commit
```

After both commits land, proceed to the code changes in the following sections.

## Scope: Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` (only file changed)

No new files. No changes required in `brainstorm_sections.py`, `brainstorm_crew.py`, `brainstorm_dag.py`, or any template.

## Verified Codebase State (April 2026)

- `_NODE_SELECT_OPS = {"explore", "detail", "patch"}` at line 112
- `_WIZARD_OP_TO_AGENT_TYPE` mapping at lines 114–120 (plan's earlier mention of `_OP_TO_TYPE` was a misnomer)
- Wizard state init lines 1121–1124: `_wizard_step`, `_wizard_total_steps: int = 3`, `_wizard_op: str`, `_wizard_config: dict`
- `_actions_show_node_select` at 2225, `_actions_show_config` at 2270, `_actions_show_confirm` at 2428
- `_actions_collect_config` at 2369, `_build_summary` at 2481
- `_on_actions_next` at 2540, `_on_actions_back` at 2530
- `_run_design_op` at 2651; for `explore` it calls `register_explorer` inside a parallel `for i in range(count)` loop
- `_config_compare` at 2308 mounts node and dimension checkboxes in a **single** step (nodes are not yet selected when UI is composed)
- No `target_sections`, `_wizard_has_sections`, or `brainstorm_sections` import exists in the file

Imports from sibling brainstorm modules already use the `from brainstorm.<mod> import …` form (sys.path setup done early in the file).

## Implementation Steps

### 1. Import parser

Add next to the other `from brainstorm.brainstorm_* import …` lines (~40):

```python
from brainstorm.brainstorm_sections import parse_sections
```

### 2. Helpers `_node_sections` and `_node_has_sections`

Insert near `_get_all_dimension_keys` (after line 2367):

```python
def _node_sections(self, node_id: str) -> list:
    plan = read_plan(self.session_path, node_id)
    if plan:
        secs = parse_sections(plan).sections
        if secs:
            return secs
    proposal = read_proposal(self.session_path, node_id)
    if proposal:
        return parse_sections(proposal).sections
    return []

def _node_has_sections(self, node_id: str) -> bool:
    return bool(self._node_sections(node_id))
```

### 3. Wizard state additions

In `__init__` (after line 1124) add:

```python
self._wizard_has_sections: bool = False
```

Reset to `False` anywhere the wizard is restarted (find the method that shows step 1 / resets `_wizard_total_steps`) so a fresh launch starts without section state leaking.

### 4. New step: `_actions_show_section_select`

Insert after `_actions_show_node_select` (~line 2269). Always assigns `_wizard_step = 3` (section step slot for node-select ops) and bumps `_wizard_total_steps` so downstream step indicators render correctly:

```python
def _actions_show_section_select(self) -> None:
    node = self._wizard_config.get("_selected_node", "")
    secs = self._node_sections(node)
    self._wizard_has_sections = True
    if self._wizard_op in ("explore", "patch"):
        self._wizard_total_steps = 5
    elif self._wizard_op == "detail":
        self._wizard_total_steps = 4
    self._wizard_step = 3

    container = self.query_one("#actions_content", VerticalScroll)
    container.remove_children()
    total = self._wizard_total_steps
    container.mount(Label(
        f"Step 3 of {total} — Select Sections for {node}",
        classes="actions_step_indicator",
    ))
    container.mount(Label(
        "[dim]Leave all unchecked to target the whole document.[/]"
    ))
    for s in secs:
        dims = f" [dim][{', '.join(s.dimensions)}][/]" if s.dimensions else ""
        container.mount(Checkbox(f"{s.name}{dims}", classes="chk_section"))
    container.mount(Button(
        "Next ▶", variant="primary", classes="btn_actions_next"
    ))
```

Section name is the first whitespace-separated token of the label (dimension tags follow); see step 5 for parsing.

### 5. Collector `_collect_target_sections`

Add next to `_actions_collect_config`:

```python
def _collect_target_sections(self) -> None:
    container = self.query_one("#actions_content", VerticalScroll)
    names: list[str] = []
    for cb in container.query("Checkbox.chk_section"):
        if cb.value:
            lbl = str(cb.label).split(" ", 1)[0]
            names.append(lbl)
    self._wizard_config["target_sections"] = names or None
```

### 6. Wire section step into `_on_actions_next` (line 2540)

Replace the existing `self._wizard_step == 2` branch body for `_NODE_SELECT_OPS`:

```python
if self._wizard_step == 2:
    if self._wizard_op in _NODE_SELECT_OPS:
        node = self._wizard_config.get("_selected_node")
        if not node:
            self.notify("Select a node first", severity="warning")
            return
        if self._node_has_sections(node):
            self._actions_show_section_select()
            return
        if self._wizard_op == "detail":
            self._wizard_config["node"] = node
            self._actions_show_confirm()
        else:
            self._actions_show_config()
    elif self._actions_collect_config():
        self._actions_show_confirm()
    return
```

Add a new branch immediately after for section-step → next:

```python
if (
    self._wizard_step == 3
    and self._wizard_has_sections
    and self._wizard_op in _NODE_SELECT_OPS
):
    self._collect_target_sections()
    if self._wizard_op == "detail":
        self._wizard_config["node"] = self._wizard_config["_selected_node"]
        self._actions_show_confirm()
    else:
        self._actions_show_config()
    return
```

Leave the existing `elif self._wizard_step == 3 and self._wizard_op in ("explore", "patch"):` (config-step transition) alone — it still fires for the no-sections path.

### 7. Adjust `_actions_show_config` for dynamic step number

In `_actions_show_config` (line 2270), replace any hardcoded `self._wizard_step = 3` for explore/patch with a computed value so the step label is correct whether or not a section step precedes it:

```python
if self._wizard_op in ("explore", "patch"):
    self._wizard_step = self._wizard_total_steps - 1
```

For detail/compare the step assignment is unchanged.

### 8. Back navigation `_on_actions_back` (line 2530)

Make it step-aware:

```python
step = self._wizard_step
total = self._wizard_total_steps

if step == total:  # confirm
    if self._wizard_op in ("explore", "patch"):
        self._actions_show_config()
    elif self._wizard_op == "detail":
        if self._wizard_has_sections:
            self._actions_show_section_select()
        else:
            self._actions_show_node_select()
    else:  # compare / hybridize
        self._actions_show_config()
elif (
    step == total - 1
    and self._wizard_op in ("explore", "patch")
    and self._wizard_has_sections
):
    self._actions_show_section_select()
elif step == 3 and self._wizard_has_sections:
    self._actions_show_node_select()
else:
    # fall back to existing behavior
    self._actions_show_node_select()
```

Preserve any existing Esc binding that calls this method.

### 9. Summary line in `_build_summary` (line 2481)

After the existing lines for the relevant op, append:

```python
ts = cfg.get("target_sections")
if ts:
    lines.append(f"[bold]Sections:[/] {', '.join(ts)}")
```

Add once at the end of the method (not per branch) since `cfg.get` is safe for ops that never set it.

### 10. Thread `target_sections` through `_run_design_op` (line 2651)

At the top of the `try:` block:

```python
target_sections = cfg.get("target_sections")
```

Pass `target_sections=target_sections` into:

- `register_explorer(...)` — **inside the `for i in range(count)` loop**, same value for every parallel agent
- `register_comparator(...)`
- `register_detailer(...)`
- `register_patcher(...)`

Do NOT add it to `register_synthesizer` (hybridize) — synthesizer merges full nodes and does not support targeting.

### 11. Compare: dynamic section checkboxes in `_config_compare` (line 2308)

Compare's section list is **dynamic**: it re-renders whenever the user toggles a node checkbox, showing the **intersection** of sections across the currently-checked nodes (these are the sections that actually make sense to compare). Previously-checked section values are preserved across re-renders.

#### 11a. Mount a dedicated sections container

Modify `_config_compare` to append a labeled, persistent container at the end:

```python
container.mount(Label("[bold]Target Sections (optional)[/]",
                      id="cmp_sections_label"))
container.mount(Container(id="cmp_sections_box"))

container.mount(Button("Next ▶", variant="primary",
                       classes="btn_actions_next"))
```

The label and the box are mounted unconditionally; when no intersection exists, the box stays empty with a helper hint (handled by the refresh method).

Store a dict on the wizard state for preserved checkbox values:

```python
# in __init__ near other wizard state
self._cmp_section_checks: dict[str, bool] = {}
```

Reset it when the wizard is reset / step 1 is shown (same reset site as `_wizard_has_sections`).

#### 11b. Refresh helper

Add a method that (re)mounts the section checkboxes based on currently checked nodes:

```python
def _refresh_compare_sections(self) -> None:
    box = self.query_one("#cmp_sections_box", Container)
    # Persist current values before tearing down
    for cb in box.query("Checkbox.chk_section"):
        self._cmp_section_checks[str(cb.label)] = bool(cb.value)
    box.remove_children()

    # Determine checked node ids
    checked: list[str] = []
    for cb in self.query("Checkbox.chk_node"):
        if cb.value:
            checked.append(str(cb.label))

    if len(checked) < 1:
        box.mount(Label("[dim]Select nodes to see comparable sections.[/]"))
        return

    # Intersection of section names across checked nodes
    name_sets: list[set[str]] = []
    for nid in checked:
        name_sets.append({s.name for s in self._node_sections(nid)})
    inter = set.intersection(*name_sets) if name_sets else set()

    if not inter:
        box.mount(Label(
            "[dim]No sections are present in all selected nodes.[/]"
        ))
        return

    for name in sorted(inter):
        value = self._cmp_section_checks.get(name, False)
        box.mount(Checkbox(name, value=value, classes="chk_section"))
```

Call `self._refresh_compare_sections()` at the end of `_config_compare` so the initial state is rendered (empty hint because no nodes are checked yet).

#### 11c. Handler — re-render on node checkbox changes

Add at class level (outside other methods, alongside other `@on` handlers):

```python
@on(Checkbox.Changed, ".chk_node")
def _on_cmp_node_changed(self, event: Checkbox.Changed) -> None:
    # Only active during compare config step
    if self._wizard_op != "compare":
        return
    self._refresh_compare_sections()
```

The guard prevents firing during other steps that might have `.chk_node` checkboxes (node-select step for explore/detail/patch uses a different class `chk_node_sel` or similar — verify during implementation; if the same class is reused, narrow the guard to `self._wizard_step == 2 and self._wizard_op == "compare"`).

#### 11d. Collect on Next

In `_actions_collect_config`, in the compare branch (~line 2390), append:

```python
box = self.query_one("#cmp_sections_box", Container)
sec_cbs = box.query("Checkbox.chk_section")
sel = [str(cb.label) for cb in sec_cbs if cb.value]
config["target_sections"] = sel or None
```

Labels in compare are bare section names (no dim-tag suffix), so no split is required.

## Key Decisions and Tradeoffs

- **Compare uses dynamic intersection.** When the user toggles node checkboxes, the section list re-renders to show only sections shared by all currently-checked nodes (the ones actually meaningful to compare). Previously-checked section states are preserved across re-renders via a dict on wizard state. Rationale: prevents the user from selecting sections that don't exist in the picked subset, which would otherwise silently degrade to an empty filter.
- **Fixed step-3 slot for section selection.** Keeps the transition logic readable: if `_wizard_has_sections` is set and we're at step 3, it's the section step. Explore/patch config becomes step 4, confirm step 5; detail confirm becomes step 4. No-sections flows are completely unchanged.
- **Section name encoded as first token of the checkbox label.** Avoids carrying a sidecar dict. Section names in this codebase are identifiers (no internal spaces); the helper strips the dim-tag suffix defensively. If section names ever grow spaces, switch to per-checkbox `id=`.
- **Top-level import of `parse_sections`.** It's small and always used on the section screen; matches file-wide style.
- **No changes to synthesizer.** Hybridize/merge operates on whole nodes; scoping to sections would need separate UX, out of scope.

## Automated Tests

Add a new test file `tests/test_brainstorm_wizard_sections.py` following the existing unittest pattern (see `tests/test_brainstorm_sections.py` and `tests/test_brainstorm_crew.py`). Two groups: **pure-logic** (fast, no TUI) and **Pilot-driven** (Textual's async `run_test()` harness — runs the real app in-memory without a terminal). These cover everything that can be verified headlessly; the remaining in-person checks live in the PI-1 sibling task (see Pre-Implementation above).

### 12a. Refactor for testability

Extract the intersection and label logic into pure module-level functions in `brainstorm_app.py` so they can be tested without instantiating the app:

```python
def _sections_intersection(node_sections: dict[str, list[str]]) -> list[str]:
    """Return sorted section names present in every node in the mapping."""
    if not node_sections:
        return []
    sets = [set(names) for names in node_sections.values()]
    return sorted(set.intersection(*sets))


def _parse_section_label(label: str) -> str:
    """Extract the section name from a checkbox label (may include '[dims]' suffix)."""
    return label.split(" ", 1)[0]
```

The instance methods `_refresh_compare_sections` and `_collect_target_sections` call these helpers. This lets us test the tricky parts purely.

### 12b. Pure-logic unit tests

```python
class SectionsIntersectionTests(unittest.TestCase):
    def test_empty_mapping_returns_empty(self):
        self.assertEqual(_sections_intersection({}), [])

    def test_single_node_returns_its_sections(self):
        self.assertEqual(
            _sections_intersection({"alpha": ["auth", "storage"]}),
            ["auth", "storage"],
        )

    def test_intersection_drops_unique(self):
        self.assertEqual(
            _sections_intersection({
                "alpha": ["auth", "storage", "telemetry"],
                "beta":  ["auth", "storage"],
            }),
            ["auth", "storage"],
        )

    def test_intersection_three_nodes(self):
        self.assertEqual(
            _sections_intersection({
                "alpha": ["auth", "storage", "telemetry"],
                "beta":  ["auth", "storage"],
                "gamma": ["auth", "ui"],
            }),
            ["auth"],
        )

    def test_empty_overlap_returns_empty(self):
        self.assertEqual(
            _sections_intersection({"a": ["x"], "b": ["y"]}),
            [],
        )


class ParseSectionLabelTests(unittest.TestCase):
    def test_bare_name(self):
        self.assertEqual(_parse_section_label("auth"), "auth")

    def test_strips_dim_suffix(self):
        self.assertEqual(
            _parse_section_label("auth [dim][component_auth][/]"), "auth"
        )
```

Plus a focused test for `_node_sections` that builds a tempdir session with known proposal/plan files (pattern already used by `test_brainstorm_crew.py`):

```python
class NodeSectionsTests(BrainstormSessionTestBase):
    def test_plan_preferred_over_proposal(self):
        self._write_proposal("n1", PROPOSAL_NO_SECTIONS)
        self._write_plan("n1", PLAN_WITH_SECTIONS)
        app = self._make_app_under_test()
        sections = app._node_sections("n1")
        self.assertEqual([s.name for s in sections], ["auth", "storage"])

    def test_falls_back_to_proposal_when_plan_missing(self):
        self._write_proposal("n1", PROPOSAL_WITH_SECTIONS)
        app = self._make_app_under_test()
        sections = app._node_sections("n1")
        self.assertGreater(len(sections), 0)

    def test_returns_empty_when_neither_has_sections(self):
        self._write_proposal("n1", PROPOSAL_NO_SECTIONS)
        app = self._make_app_under_test()
        self.assertEqual(app._node_sections("n1"), [])
```

`_make_app_under_test()` instantiates `BrainstormApp` without running it (no `.run()`) and points `session_path` at the temp dir — no Textual context is required for the helper, since it only calls `read_plan`/`read_proposal` and `parse_sections`.

### 12c. Pilot-driven wizard tests (Textual `run_test()`)

Textual ships an async test harness (`App.run_test()` returning a `Pilot`) that drives a real app in-memory. Pattern:

```python
class WizardSectionStepTests(unittest.IsolatedAsyncioTestCase):
    async def test_explore_shows_section_step_when_sections_present(self):
        async with BrainstormApp(task_num=self.task_num).run_test() as pilot:
            # Select Explore
            await pilot.click("#op_explore")
            await pilot.click(".btn_actions_next")
            # Step 2: pick a node that has sections
            await pilot.click("Checkbox#node_radio_n1")
            await pilot.click(".btn_actions_next")
            # Step 3 must be section select, not config
            header = pilot.app.query_one(".actions_step_indicator", Label)
            self.assertIn("Select Sections", str(header.renderable))
            self.assertEqual(pilot.app._wizard_total_steps, 5)

    async def test_explore_skips_section_step_when_no_sections(self):
        # node "n0" written without section markers
        async with BrainstormApp(task_num=self.task_num).run_test() as pilot:
            ...  # select explore, pick n0, Next
            # Step 3 is config (no section step inserted)
            self.assertEqual(pilot.app._wizard_total_steps, 4)

    async def test_compare_section_list_updates_on_node_toggle(self):
        async with BrainstormApp(task_num=self.task_num).run_test() as pilot:
            # Navigate to compare config step
            await pilot.click("#op_compare")
            await pilot.click(".btn_actions_next")
            # Initially no nodes checked -> helper hint
            box = pilot.app.query_one("#cmp_sections_box")
            self.assertEqual(len(box.query("Checkbox.chk_section")), 0)
            # Check alpha (has auth, storage, telemetry)
            await pilot.click("Checkbox.chk_node:nth-of-type(1)")
            names_1 = sorted(str(cb.label)
                             for cb in box.query("Checkbox.chk_section"))
            self.assertEqual(names_1, ["auth", "storage", "telemetry"])
            # Also check beta (has auth, storage)
            await pilot.click("Checkbox.chk_node:nth-of-type(2)")
            names_2 = sorted(str(cb.label)
                             for cb in box.query("Checkbox.chk_section"))
            self.assertEqual(names_2, ["auth", "storage"])  # telemetry drops

    async def test_compare_preserves_checkbox_state_across_refresh(self):
        async with BrainstormApp(task_num=self.task_num).run_test() as pilot:
            # Check alpha+beta, tick the "auth" section
            ...
            # Add gamma (intersection becomes only "auth")
            ...
            # Confirm "auth" checkbox is still checked after remount
            auth_cb = pilot.app.query_one("#cmp_sections_box").query(
                "Checkbox.chk_section"
            )[0]
            self.assertTrue(auth_cb.value)

    async def test_selected_sections_reach_register_function(self):
        # Monkeypatch register_explorer to capture call args
        captured = {}
        def fake_register_explorer(*a, **kw):
            captured.update(kw)
            return "mock-agent-id"
        import brainstorm.brainstorm_app as app_mod
        app_mod.register_explorer = fake_register_explorer

        async with BrainstormApp(task_num=self.task_num).run_test() as pilot:
            # Explore → node n1 (has sections) → check "auth" → Next → Next (confirm) → Launch
            ...
        self.assertEqual(captured.get("target_sections"), ["auth"])
```

### 12d. Test fixture setup

A shared `BrainstormSessionTestBase` provides:
- `setUp` / `tearDown` tempdir-based session patched into `AGENTCREW_DIR` (same pattern as `test_brainstorm_crew.py`)
- Helpers `_write_proposal(node_id, text)`, `_write_plan(node_id, text)`, `_make_app_under_test()`
- Fixture content: three pre-seeded nodes `alpha`, `beta`, `gamma` with the section distributions from the plan's worked example (auth/storage/telemetry, auth/storage, auth/ui respectively)

### 12e. Manual verification → PI-1 sibling task

Everything that Pilot cannot easily assert (visual labels, step-counter text, the end-to-end `_input.md` on disk, real agent launch behavior) is captured in the **PI-1 sibling task `t571_7_manual_verification_structured_brainstorming`** — created before implementation starts. This task file holds the full step-by-step checklist (the **Verification** section below is sourced there, not repeated inline in t571_4's task file post-implementation).

### 12f. Running the tests

```bash
python -m unittest tests.test_brainstorm_wizard_sections -v
```

The file is self-contained and follows the existing project convention (no pytest, unittest only). "Semi-automated" = pure-logic + Pilot tests run headlessly in CI; the manual checklist covers the last-mile visual checks.

## Verification (seeded into PI-1 sibling task `t571_7`)

The full checklist below is the initial body of the manual-verification sibling task created in **PI-1**. It is NOT repeated inline in t571_4's task file after implementation — the feature task's own "Verification" section is replaced with a one-line pointer to `t571_7`.

1. Launch `ait brainstorm` on a task whose current node has NO section markers — verify every op's wizard flows exactly as today (step counts 3 or 4, no section screen).
2. Create or pick a node whose plan/proposal uses `<!-- section: name [dimensions: …] -->` markers. Pick Explore:
   - Wizard shows "Step 3 of 5 — Select Sections for …" with one checkbox per section, dim tags italicized.
   - Next with no boxes checked → step 4 config → step 5 confirm shows no "Sections:" line; launched explorer's `_input.md` has no `## Targeted Section Content` block.
   - Next with two boxes checked → confirm shows `Sections: a, b`; launched explorer's `_input.md` includes only those sections.
3. Same with Detail: step 3 sections → step 4 confirm.
4. Same with Patch: step 3 sections → step 4 config → step 5 confirm.
5. Back button from confirm, section, and config each return to the previous step.
6. Compare with three nodes whose sections overlap partially (alpha=[auth,storage,telemetry], beta=[auth,storage], gamma=[auth,ui]). Verify:
   a. With no nodes checked, the sections box shows "Select nodes to see comparable sections."
   b. Check alpha only → sections list shows `auth, storage, telemetry`.
   c. Also check beta → sections list updates to `auth, storage` (telemetry drops).
   d. Also check gamma → sections list updates to `auth` (intersection of all three).
   e. Uncheck gamma → list returns to `auth, storage`; any checkbox values the user had previously set on `auth` or `storage` are preserved.
   f. Confirm step shows `Sections: …`; launched comparator's `_input.md` `## Section Focus` contains only the checked section names.
7. Hybridize on two nodes with sections: NO section UI appears (synthesizer is not section-aware).
8. Run with parallel explore count = 3 and one section selected: all three spawned explorers share the same `target_sections`.

### Aggregation note for future siblings

When t571_5 (shared section viewer) is implemented, its own in-person checklist is appended to `t571_7` under a `## t571_5` heading — not duplicated in t571_5's own task file. The feature sibling's "Verification" section becomes `See t571_7`. Future parent tasks in this codebase that spawn multiple TUI-touching children should adopt the same convention: create one `t<parent>_<last>_manual_verification_*` sibling that aggregates all in-person checks across the family.

## Step 9: Post-Implementation

Follow Step 9 from the shared task-workflow for archival, merge, and cleanup.
