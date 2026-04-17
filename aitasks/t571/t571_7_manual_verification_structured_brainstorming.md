---
priority: medium
effort: medium
depends: [t571_6]
issue_type: test
status: Ready
labels: [brainstorming, ait_brainstorm, manual, verification]
created_at: 2026-04-17 11:20
updated_at: 2026-04-17 11:20
---

## Purpose

This task aggregates **all manual (in-person) verification steps** for every sibling of t571 that requires live TUI or end-to-end checks. It exists because pure-logic and Textual Pilot tests can only cover so much — visual labels, real agent launches, `_input.md` contents on disk, and multi-screen navigation need a human at the keyboard.

**Depends on:** t571_4 (wizard section-select step) and t571_5 (shared section viewer integration). Cannot be executed until both have landed.

## Aggregation Convention

When a sibling under t571 that involves the brainstorm TUI completes its implementation, its verification checklist is appended to this file under a `## t<parent>_<N>` heading — **not repeated inline in that sibling's own task file**. The sibling task's "Verification" section becomes a one-line pointer: `See t571_7`. Dependencies on this task are updated at the same time.

Future parent tasks in this codebase that spawn multiple TUI-touching children should adopt the same convention: create one `t<parent>_<last>_manual_verification_*` sibling that aggregates all in-person checks across the family. This makes manual-verification work visible, estimatable, and pickable.

A follow-up task (see `manual_verification_module_for_task_workflow`) is planned to formalize this pattern into a dedicated `/aitask-pick` module that tracks per-item check-off state, refuses archival until every item has a terminal state, and auto-creates follow-up bug tasks with full source references when a check fails.

---

## t571_4 — Section selection in brainstorm wizard

Prerequisite: a brainstorm session whose current node tree includes nodes with section-structured proposals/plans (using `<!-- section: name [dimensions: …] -->` markers). Create such content if none exists by running an explorer with the new section-aware template (from t571_2), or hand-author a proposal/plan file with section markers.

1. **No-sections path is unchanged.** Launch `ait brainstorm` on a task whose current node has NO section markers. For every op (explore, compare, hybridize, detail, patch), verify the wizard flows exactly as before: step counts 3 or 4; no section screen appears.

2. **Explore with sections.** Pick a node that has sections. Select Explore.
   - Wizard shows "Step 3 of 5 — Select Sections for <node>" with one checkbox per section; dim tags italicized after each name.
   - Click Next with no boxes checked → step 4 config → step 5 confirm shows no "Sections:" line. Launch; the explorer's `_input.md` on disk has no `## Targeted Section Content` block.
   - Repeat: check two boxes → confirm shows `Sections: a, b`. Launch; `_input.md` includes only those sections under `## Targeted Section Content` (and `## Targeted Plan Section Content` if plan sections were chosen).

3. **Detail with sections.** Same node → Detail: step 3 sections → step 4 confirm. Launch and verify the detailer's `_input.md` `## Target Sections` block.

4. **Patch with sections.** Same node → Patch: step 3 sections → step 4 config → step 5 confirm. Launch and verify the patcher's `_input.md` `## Target Sections` block.

5. **Back navigation.** From each of confirm, section, and config steps, press the Back button. Each returns to the correct previous step. From section step back → node select. From config (explore/patch) back → section select (if sections) else node select.

6. **Compare — dynamic intersection.** Set up three nodes whose sections overlap partially:
   - alpha: [auth, storage, telemetry]
   - beta:  [auth, storage]
   - gamma: [auth, ui]
   
   Select Compare. Verify in order:
   a. With no nodes checked, the sections box shows "Select nodes to see comparable sections."
   b. Check alpha only → sections list shows `auth, storage, telemetry`.
   c. Also check beta → sections list updates to `auth, storage` (telemetry drops).
   d. Also check gamma → sections list updates to `auth` (intersection of all three).
   e. Uncheck gamma → list returns to `auth, storage`; any checkbox values the user had previously set on `auth` or `storage` are PRESERVED.
   f. Tick `auth`. Proceed to confirm → summary shows `Sections: auth`. Launch and verify the comparator's `_input.md` `## Section Focus` contains only `auth`.

7. **Hybridize excluded.** On two nodes with sections, select Hybridize. Confirm NO section UI appears at any step — synthesizer is not section-aware.

8. **Parallel explore threading.** Select Explore with parallel count = 3 and one section checked. Launch. Verify all three spawned explorers receive the same `target_sections` (inspect each `_input.md`).

**Implementation reference:** `aiplans/archived/p571/p571_4_section_selection_brainstorm_tui_wizard.md` (once archived) contains the Final Implementation Notes, actual commit hashes, and any deviations from this checklist.

---

## (Placeholder) t571_5 — Shared section viewer TUI integration

**To be filled in when t571_5 completes.** The sibling's "Verification" section will be moved here and cross-referenced. Expected checks (per t571_5 task description):
- Codebrowser detail pane shows section minimap for tasks with section-structured plans
- Clicking a minimap row scrolls the markdown to that section
- `p` keybinding opens `SectionViewerScreen` full-screen modal
- Brainstorm `NodeDetailModal` Plan/Proposal tabs show minimaps
- Board `TaskDetailScreen` plan view shows minimap and full-screen viewer keybinding
- Graceful fallback for plans with no sections (no minimap, normal markdown)
