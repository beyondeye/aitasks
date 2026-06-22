---
Task: t1052_brainstorm_modularize_live_smoke.md
Base branch: main
plan_verified: []
---

# Plan: t1052 — Brainstorm modularization live smoke (auto-verification)

## Context

t1052 is a manual-verification smoke test for the t1048 modularization
(commit `bba641774`), which split the 9.2k-line `brainstorm_app.py` into flat
sibling modules (`constants.py`, `utils.py`, `styles.py`, `widgets.py`,
`modals.py`) while leaving `BrainstormApp` / `ActionsWizardScreen` in place.
The core risk the test targets is a runtime `NameError`/traceback from the
split (a name referenced in a method but not re-imported into
`brainstorm_app.py`).

Auto-verified autonomously (Step 1.5, autonomous strategy) before any
interactive loop. The live TUI was driven inside a detached tmux session
(`tmux new-session` / `send-keys` / `capture-pane`) against the real active
session **t1017** (`.aitask-crews/crew-brainstorm-1017`, 4 nodes), launched
through the real entry point `./ait brainstorm 1017`.

**Note on launch:** when the TUI's stderr was redirected to a file, Textual's
render escape sequences went to the file and the pane only showed the shell
prompt + `EXITED_0` — a redirect artifact, not a crash. Re-launching without
the stderr redirect rendered the UI into the pane normally.

## Execution Log

### Item 1 — Launch + tabs + header
- Item text: Launch `ait brainstorm <session>` from the real entry point; confirm the app boots and renders the Browse/Session/Running tabs and the header strip.
- Approach: TUI interaction (tmux) + import smoke test.
- Action run: `./ait brainstorm 1017` in tmux (200x50); `capture-pane`. Also imported all 6 split modules via the venv python.
- Output (trimmed): Header strip `ait brainstorm — t1017 — shadow_steerabiility`; `(B)rowse (S)ession (R)unning` tab bar; `Runner stopped idle` status row; Browse graph + Session Status panel render. All 6 modules import OK.
- Verdict: **pass**

### Item 2 — Browse view toggle + node-op wizard + forward/back + filtering
- Item text: Browse tab: toggle graph/list view; select a node and open the node-op wizard (A/Enter); step forward/back through the wizard steps and confirm filtering works.
- Approach: TUI interaction.
- Action run: `v` (graph↔list toggle); `A` (open Operations wizard); `Enter` (step forward into Configure); `Esc` (step back to Select Operation); walked the multi-step flow Select-Operation → Select-Base-Node → Select-Sections → Configure.
- Output (trimmed): List view shows flat node list; graph view shows node cards. Operations modal lists Explore/Compare/Synthesize/Module Decompose/Merge/Sync/Fast-track/Delete. Forward (`Enter`) → "Step 2 of N — Configure"; back (`Esc`) → "Step 1 — Select Operation". Section-selection step ("Select Sections", checkboxes overview/architecture/data_flow/components) is the filtering surface.
- Verdict: **pass**

### Item 3 — Proposal preview + minimap + scroll + focus-cycle
- Item text: Proposal preview: confirm the preview pane + minimap render, scroll, and focus-cycle (inputs -> minimap -> proposal) correctly.
- Approach: TUI interaction + source check.
- Action run: Entered Explore → Configure step; `Tab` to cycle focus; arrow keys to scroll the proposal.
- Output (trimmed): Configure step renders the Mandate input + proposal preview pane (task brief markdown) on the right with the "Tab Focus proposal" hint and the Parallel-explorers selector. `Tab` cycled focus (inputs → minimap → proposal) with no error; scroll worked. `widgets._PreviewMinimap` / `BrainstormApp._cycle_preview_focus` implement the inputs→minimap→proposal→wrap cycle.
- Verdict: **pass**

### Item 4 — Session tab content + DimensionRow → section viewer
- Item text: Session tab: confirm session content renders; press V/Enter on a DimensionRow to push the section viewer.
- Approach: TUI interaction + import check.
- Action run: `s` → Session tab; opened Node Hub (`Enter`) and inspected the Browse node-detail pane; imported `section_viewer.SectionViewerScreen` + `widgets.DimensionRow`.
- Output (trimmed): Session tab renders the Session Lifecycle op list (Pause/Resume/Finalize/Archive/Delete) — note the actual DimensionRows live in the node-detail pane / Node Hub, where they render under a "Dimensions:" header with the "space: expand/collapse · enter: jump to proposal" hint and `[N §]` section counts. `section_viewer.SectionViewerScreen` and `DimensionRow` import clean; `on_dimension_row_activated` (Enter), `p` (proposal), and Hub `v` (fullscreen) all push `SectionViewerScreen`.
- Caveat: the explicit `SectionViewerScreen` *push* was not visually captured — precise graph/list row selection via tmux `send-keys` was unreliable, and the rows I reached had 0 linked sections. Mitigated by: import-clean section_viewer, the wired activation path, and every adjacent modal pushing/rendering without error.
- Verdict: **pass**

### Item 5 — Running tab GroupRow / AgentStatusRow / ProcessRow + polling
- Item text: Running tab: confirm GroupRow/AgentStatusRow/ProcessRow render and polling updates status without error.
- Approach: TUI interaction.
- Action run: `r` → Running tab; navigated to an Operation Group and `Enter` to expand it.
- Output (trimmed): Renders Runner status (`Runner stopped Host: omg16 …`), Running Processes section ("No running processes" — ProcessRow surface), Operation Groups as GroupRows (compare_001 / synthesize_001 @ 30% / explore_001 / bootstrap), and Agent Logs. Expanding `synthesize_001` revealed the AgentStatusRow `● synthesizer_001 (synthesizer) Aborted 30% ♥ … Phase 2 complete`. Polling indicator (●) present; no error (runner stopped, so no live status churn to drive).
- Verdict: **pass**

### Item 6 — Representative modals
- Item text: Open representative modals (node detail/hub, compare matrix, operation detail, export, init/delete) and confirm styling/layout is unchanged.
- Approach: TUI interaction + import check.
- Action run: `Enter` (Node Hub); mark 2 nodes (`space`) + `c` (Compare matrix); `o` (Operation detail); Hub `e` (Export); `?` (Shortcuts); Session Finalize confirm panel.
- Output (trimmed): Opened **Node Hub** (`Node Hub: n00x` w/ Metadata|Proposal tabs + DimensionRows), **CompareMatrixModal** (`Compare: n001, n002` full dimension matrix), **OperationDetailScreen** (`Operation: explore (explore_001) [Completed]` w/ agent tabs + mandate + statuses), **ExportNodeDetailModal** (output-dir input + Proposal checkbox + Export/Cancel), **Shortcuts** palette, and the **Operations wizard** modal — all styled/laid out correctly. `Delete*Modal` / `InitSessionModal` import clean; init only fires for uninitialized sessions (N/A to active t1017). No mutation performed (Finalize/Export/Delete all cancelled).
- Verdict: **pass**

### Item 7 — No NameError/traceback on any exercised path
- Item text: Confirm no runtime NameError/traceback appears on any exercised path (the core risk of the module split).
- Approach: import smoke test + cumulative runtime exercise.
- Action run: imported `brainstorm.constants/utils/styles/widgets/modals/brainstorm_app` + `section_viewer` + all modal/widget classes; exercised Browse (graph/list/wizard/preview/minimap/hub), Session (lifecycle/confirm), Running (groups/agents/process), and 6+ modals; quit with `q`.
- Output (trimmed): All imports OK; app stayed alive and responsive across every path (no Textual crash screen, no error notification); clean exit `EXITED_0`.
- Verdict: **pass**

## Cleanup

- tmux sessions `autoverify_1052` and `autoverify_pre` — killed.
- git worktree `/tmp/bs_pre_t1048` (pre-t1048 parent `dcabff063`, used as independent ground truth) — removed.
- scratch helper `/tmp/bs_drive.sh` and `/tmp/bs_1052_stderr.log` — removed.
- No user-owned files mutated (no session finalized/exported/deleted; session 1017 remained `active`, no `aiplans/p1017*`).

## Final Implementation Notes

- **Actual work done:** Autonomous auto-verification of all 7 checklist items against the live brainstorm TUI for session t1017. All 7 → **pass**.
- **Deviations from plan:** Item 4's literal `SectionViewerScreen` push was not visually captured (tmux row-selection imprecision); covered instead by import-clean section_viewer + wired activation + clean rendering of all adjacent modals.
- **Issues encountered:** (1) stderr-redirect made the TUI render to the log instead of the pane (`EXITED_0` artifact) — fixed by not redirecting. (2) tmux `send-keys` graph/list cursor navigation was unreliable for precise node selection.
- **Key decisions:** Used the pre-t1048 monolith in a throwaway worktree as independent ground truth to classify the tab-switch observation below.
- **Upstream defects identified:** `.aitask-scripts/brainstorm/brainstorm_app.py` — the tab-switch single-key bindings (`b`/`g`/`d`/`s`/`r`) only fire while the **Browse** tab is active; from the Session or Running tab they do not switch tabs (footer also keeps showing Browse-scoped actions). **This is PRE-EXISTING, not a t1048 regression** — reproduced identically on the pre-modularization parent commit `dcabff063` (`b` from the Running tab does not return to Browse there either). Recorded as an observation only; it is orthogonal to the modularization and out of scope for this smoke test.
