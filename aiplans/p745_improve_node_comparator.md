---
Task: t745_improve_node_comparator.md
Base branch: main
plan_verified: []
---

# Plan — t745: Improve node comparator in ait brainstorm

## Context

The Compare tab in the `ait brainstorm` TUI lets users pick two (or more) nodes and inspect their dimension matrices side-by-side, with similarity-based color coding. Five issues have accumulated:

1. Once a comparison is shown, there is no visible shortcut to regenerate it with different nodes — `c` re-opens the modal but is invisible because the Compare tab footer still advertises only global tab-switching keys.
2. The brainstorm Footer currently advertises tab-switching shortcuts (`d` Dashboard / `g` Graph / `c` Compare / `a` Actions / `s` Status) but never the per-tab actions; users have to read the source to discover what the active tab can do.
3. Equal-valued dimensions print the full value redundantly in both node columns, so the visually interesting (differing) rows are hard to spot in long matrices like `brainstorm-635`.
4. Differing values are dumped raw and only colored at the row level; users cannot see *what* differs without external tooling.
5. The existing diffviewer TUI is not integrated. Shift+D currently shells out to plain `subprocess.Popen(["diff", ...])`, which can't even render in the TUI's terminal pane.

The task description explicitly asks for this work to be split into child tasks. Per `aiplans/p634/p634_3` and CLAUDE.md, brainstorm follows the single-tmux-session model, so the diffviewer integration should happen inside the brainstorm app via `push_screen` — not by spawning a sibling tmux window.

---

## Approach overview

Split into **4 implementation children + 1 aggregate manual-verification sibling**. The first child is foundational (context-aware footer infrastructure) and unblocks the remaining UI work.

| Child | Title | Depends on |
|---|---|---|
| t745_1 | Context-aware footer + embedded tab-label shortcuts | — |
| t745_2 | Compare tab regenerate shortcut | t745_1 |
| t745_3 | Compact equal-value rows + inline word-level diff for differing values | t745_1 |
| t745_4 | Replace `subprocess diff` with pushed `DiffViewerScreen` | t745_1 |
| t745_5 | Aggregate manual verification | t745_1, t745_2, t745_3, t745_4 |

User-confirmed design decisions:
- **Regenerate** = re-open `CompareNodeSelectModal`. (Not "refresh same nodes".)
- **Equal dims** = render the row with a single shared cell pattern (value once, the other node cell gets a "← same" marker since `DataTable` does not support real cell-spanning).
- **Diff TUI integration** = push `DiffViewerScreen` inside brainstorm; no new tmux window.
- **Differing values** = inline word-level diff per cell using diffviewer's existing `_word_diff_texts` helper (promoted to public API).

---

## Critical files (full plan touchpoints)

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `BrainstormApp.BINDINGS` (lines 1512–1523) — tab bindings to be `show=False`'d
  - `compose()` (1578–1614) — Compare hint label needs updated text
  - `on_key()` Shift+D handler (1778–1795) — to be replaced by a proper Binding + action
  - `_build_compare_matrix()` (2869–2922) — render-time changes for issues 3 & 4
  - `_add_similarity_row()` (2924+) — should still run; verify it still works against the updated row layout
- `.aitask-scripts/diffviewer/diff_display.py` — promote `_word_diff_texts` → `word_diff_texts` (keep backward-compat alias).
- `.aitask-scripts/diffviewer/diff_viewer_screen.py` — `DiffViewerScreen(main_path, other_paths, mode)` is reused as-is via push_screen.
- `.aitask-scripts/board/aitask_board.py` (lines 3333–3380) — reference pattern for `check_action()`-based context-aware footer; do **not** modify.
- Tests: `tests/test_brainstorm_*.sh` — extend or add as appropriate.

---

## t745_1 — Context-aware footer + tab-label embedded shortcuts in BrainstormApp

**Goal.** Hide tab-switching keys from the footer and surface only bindings relevant to the active tab. Communicate tab shortcuts directly inside each tab's visible label using parentheses convention: `(D)ashboard`, `(G)raph`, `(C)ompare`, `(A)ctions`, `(S)tatus`. Provides infrastructure for t745_2 / t745_4 to declare bindings that auto-show on the Compare tab.

**Implementation.**

1. **Embed shortcut in tab labels.** In `compose()` (lines 1586–1614), update each `TabPane(...)` first arg:
   - `TabPane("Dashboard", id="tab_dashboard")` → `TabPane("(D)ashboard", id="tab_dashboard")`
   - `TabPane("Graph", id="tab_dag")` → `TabPane("(G)raph", id="tab_dag")`
   - `TabPane("Compare", id="tab_compare")` → `TabPane("(C)ompare", id="tab_compare")`
   - `TabPane("Actions", id="tab_actions")` → `TabPane("(A)ctions", id="tab_actions")`
   - `TabPane("Status", id="tab_status")` → `TabPane("(S)tatus", id="tab_status")`
2. In `BrainstormApp.BINDINGS` (lines 1512–1523), set `show=False` on the five tab bindings (`d`, `g`, `c`, `a`, `s`). Quit (`q`) stays visible. The tab-label parentheses now communicate the shortcut, so the footer entry becomes redundant.
3. Add a `check_action(self, action: str, parameters) -> bool | None` method on `BrainstormApp`, modeled on `aitask_board.py:3333`. It uses `self.query_one(TabbedContent).active` to decide visibility for tab-scoped bindings introduced in t745_2 / t745_4.
4. Establish a small registry — e.g. a class-level dict `_TAB_SCOPED_ACTIONS = {"compare_regenerate": "tab_compare", "compare_diff": "tab_compare"}` — so future tab-scoped bindings only need a one-line registry entry. `check_action` returns `None` (hidden) when the action's required tab is not active, `True` otherwise. (For t745_1 itself, the registry can ship empty; t745_2 / t745_4 add entries.)
5. Reuse: do not invent a new pattern — match `aitask_board.py`'s `check_action` style verbatim.

**Verification.** Launch `ait brainstorm 635` (or any active session). The five tabs at the top now read `(D)ashboard | (G)raph | (C)ompare | (A)ctions | (S)tatus`. Footer no longer shows `d g c a s`. Pressing each letter still switches to the corresponding tab (binding kept, just `show=False`). `q` (Quit) and the TUI switcher (`j`) remain visible.

---

## t745_2 — Compare tab regenerate shortcut

**Goal.** A discoverable `r` key on the Compare tab re-opens `CompareNodeSelectModal`, replacing the current comparison. Visible in footer only on the Compare tab.

**Implementation.**

1. Add `Binding("r", "compare_regenerate", "Regenerate")` to `BrainstormApp.BINDINGS`.
2. Register `compare_regenerate` in `_TAB_SCOPED_ACTIONS` from t745_1 with required tab `tab_compare`.
3. Add `action_compare_regenerate(self)` that pushes `CompareNodeSelectModal` (the same path `action_tab_compare` already uses on second press — see lines 1926–1941; refactor to share a single helper to avoid duplication).
4. Update the Compare tab hint Label text (line 1602) from `"Press 'c' to select nodes for comparison, 'D' to diff"` to something like `"Press 'r' to (re)select nodes, 'D' to open full diff"`.
5. Cache invalidation: simply replacing `_compare_nodes` is fine — `_build_compare_matrix` already calls `container.remove_children()` first.

**Verification.** Open Compare tab → footer shows `r Regenerate D Diff q Quit` (ordering may differ). Pick two nodes via initial flow. Press `r` → modal reopens. Pick different nodes → table replaces. Switch to Dashboard → `r` no longer in footer.

---

## t745_3 — Compact equal-value rows + inline word-level diff for differing values

**Goal.** Make the dimension table readable at a glance: equal rows collapse to one visible value, differing rows highlight what changed.

**Implementation.**

1. **Promote `_word_diff_texts`** in `.aitask-scripts/diffviewer/diff_display.py:118` to a public name `word_diff_texts`, leaving the underscore-prefixed name as an alias for back-compat. Re-export from `.aitask-scripts/diffviewer/__init__.py` (create if absent).
2. **Modify `_build_compare_matrix()`** (lines 2898–2916):
   - When `len(unique) == 1` (equal): render row as `[dim_key, Text(value, style="green"), Text("← same", style="dim green")]` for the 2-node case. For 3+ nodes, fall back to the current behavior (out of scope for this task — note in plan file).
   - When values differ AND exactly 2 nodes: call `word_diff_texts(v1, v2, TAG_STYLES["replace"], TAG_STYLES["replace"], TAG_STYLES["replace_dim"], TAG_STYLES["replace_dim"])` from `diffviewer.diff_display`, mount the returned `Text` objects in cells 1 and 2.
   - When values differ AND 3+ nodes: keep current red/yellow row coloring (inline word-diff for >2 nodes is a separate concern; document in Final Implementation Notes).
3. Verify `_add_similarity_row()` (line 2924+) still adds correctly given the new rendering — a row with `Text("← same", ...)` is still a valid DataTable row.

**Verification.** Open Compare tab on `crew-brainstorm-635/n000_init.yaml` vs `n001_infra_only.yaml`. Equal dimensions appear once with `← same` indicator on the second column. Differing dimensions show colored word-level diff highlights inside each cell. Similarity row at the bottom still renders.

**Out of scope (document in Final Implementation Notes):** 3+ node comparison rendering, structural-mode diff for very long values (>1k chars), pagination of long values.

---

## t745_4 — Replace subprocess diff with pushed DiffViewerScreen

**Goal.** Pressing `D` (Shift+D) on Compare tab opens the diffviewer **inside** brainstorm as a Textual screen — proper colors, navigation, mode switching — instead of a backgrounded `diff` process the user can't see.

**Implementation.**

1. Remove the `Shift+D` handler from `on_key()` at lines 1778–1795.
2. Add `Binding("D", "compare_diff", "Diff")` to `BrainstormApp.BINDINGS`. Register `compare_diff` as tab-scoped to `tab_compare` (see t745_1 registry).
3. Implement `action_compare_diff(self)`:
   ```python
   def action_compare_diff(self) -> None:
       if not getattr(self, "_compare_nodes", None) or len(self._compare_nodes) < 2:
           self.notify("Pick nodes to compare first (press 'r')", severity="warning")
           return
       n1, n2 = self._compare_nodes[:2]
       p1 = self.session_path / "br_proposals" / f"{n1}.md"
       p2 = self.session_path / "br_proposals" / f"{n2}.md"
       missing = [p for p in (p1, p2) if not p.is_file()]
       if missing:
           self.notify(f"Proposal file missing: {missing[0].name}", severity="warning")
           return
       from diffviewer.diff_viewer_screen import DiffViewerScreen
       self.push_screen(DiffViewerScreen(str(p1), [str(p2)], mode="classical"))
   ```
4. Verify the import path: `brainstorm_app.py` already imports siblings from `.aitask-scripts/`. The diffviewer module is a sibling directory. Confirm `sys.path` setup works at runtime by running `aitask_brainstorm.sh 635`. If the import fails because the sh-launcher only adds the brainstorm directory, fix by adding `.aitask-scripts/` to the path in the launcher (or use a relative import via package layout).
5. The `DiffViewerScreen` already uses `Escape` to dismiss (binding at line 75). On dismiss the user lands back on the Compare tab.

**Verification.** Open Compare tab, pick `n000` vs `n001` from `crew-brainstorm-635`, press `D`. The diffviewer screen pushes; mode-switch (`m`), unified (`u`), layout (`v`) all work. Press `Escape` → back on Compare tab with the matrix still visible.

---

## t745_5 — Aggregate manual verification

**Goal.** Single sibling that walks the user through a TUI checklist after the four implementation children land. Built per planning.md "Manual verification sibling" guidance.

**Items.** Pulled per-child from each child plan's `## Verification` section, prefixed `[t745_<n>]`. Stub: `TODO: define verification for t745_<n>` if a child plan lacks the section.

The seeder script at `.aitask-scripts/aitask_create_manual_verification.sh` will be invoked in Step 6.1 with `--verifies 745_1,745_2,745_3,745_4`.

---

## Execution order

1. Implement t745_1 first (foundational — no UI behavior change, but must land before others to avoid showing `d g c a s` while iterating).
2. t745_2, t745_3, t745_4 can be picked in any order after t745_1 — they touch independent code regions.
3. t745_5 (manual verification) is picked last, after archival of all four.

## Verification (parent-level)

- `bash tests/test_*.sh` for any updated brainstorm tests.
- `shellcheck .aitask-scripts/aitask_*.sh` (no shell scripts changed in this parent plan, but t745_4 may touch `aitask_brainstorm.sh` if path setup is needed).
- Manual TUI walkthrough via t745_5.
