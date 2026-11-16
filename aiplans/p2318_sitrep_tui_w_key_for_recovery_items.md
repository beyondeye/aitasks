---
Task: t2318_sitrep_tui_w_key_for_recovery_items.md
Base branch: main
Output branch: main
---

# t2318 — sitrep TUI `w` key for crash-recovery items

## Context

t2299_4 made `crashed-agents` a **virtual theme** in the `/aitask-sitrep` skill:
every crash-recovery item (`ref=recover:t<N>`) belongs to it, although the crash
detector writes recovery contexts with no `theme:` line. The skill's `>w <theme>`
check already accepts `crashed-agents` whenever `list` shows a `recover:` item,
in any state.

The TUI does not know this. `item_theme()`
(`.aitask-scripts/sitrep_tui/sitrep_tui_requests.py:80`) reads only the context
theme, so it returns `""` for a recovery item. That hides the `w` binding
(`sitrep_tui_actions.py:690-691`) and makes `build_request` refuse `>w {theme}`.
The user has to type `>w crashed-agents` by hand.

Goal: `w` on a recovery item types `>w crashed-agents`, through the existing
guarded delivery. This is a read-side mapping only. Nothing writes a theme into
recovery contexts.

Working on the current branch (profile `fast`). No worktree.

## Implementation

### 1. `.aitask-scripts/sitrep_tui/sitrep_tui_requests.py`

- Add a module constant beside `AGENT_REQUESTS`:
  ```python
  #: The skill's virtual theme for every crash-recovery item (`recover:` ref).
  #: Recovery contexts name no theme (the detector owns them); this is a
  #: read-side mapping only. Pinned against the skill text by
  #: tests/test_sitrep_tui_requests.py.
  RECOVERY_THEME = "crashed-agents"
  ```
- Rewrite `item_theme()`:
  ```python
  def item_theme(store, item) -> str:
      """The item's context theme when it is a valid theme token; else, for a
      crash-recovery item, the virtual RECOVERY_THEME; else ``""``.
      An explicit context theme always wins."""
      if item is None:
          return ""
      ctx = store.contexts.get(item.num) if store is not None else None
      theme = getattr(ctx, "theme", "") if ctx is not None else ""
      if theme and st.THEME_RE.match(theme):
          return theme
      return RECOVERY_THEME if st.parse_recover_ref(item.ref or "") else ""
  ```
  The recovery fallback needs only the item's ref, so it also works with no
  store. A non-recovery item with no store still gives `""`, as it does today.
  The `w` binding takes no state filter, matching the skill's "in any state".
- `AGENT_REQUESTS` stays the same (`>w {theme}`), so contract section `r` needs
  no change.

### 2. `.aitask-scripts/sitrep_tui/sitrep_tui_actions.py`

- Code: no change. `check_action` already calls `bool(reqs.item_theme(...))`.
- Module docstring, line 18: "situation text (`w`, items with a theme)" →
  "situation text (`w`, items with a theme, and crash-recovery items as
  `crashed-agents`)".

### 3. Tests: `tests/test_sitrep_tui_requests.py`

- `BuildRequestTests`. Add an item helper that takes `ref`, and a small
  `TodoStore` / `ContextEntry` fixture:
  - a recovery item (`ref="recover:t42"`, kind `task`) with no context theme:
    `item_theme` is `crashed-agents` and `build_request` gives `>w crashed-agents`,
    with the store and without it;
  - negative control: a non-recovery item (`ref="t42"`) with no theme gives `""`
    and an empty request (the existing "no theme" assertion stays too);
  - a recovery item whose context has an explicit valid theme keeps it
    (`>w sitrep`);
  - a recovery item whose context theme is invalid (fails `THEME_RE`) falls back
    to `crashed-agents`.
- A skill-pin test: read `.claude/skills/aitask-sitrep/SKILL.md.j2` and assert
  it contains ``f"**`{reqs.RECOVERY_THEME}` is the theme of every crash-recovery item**"``.
- A binding test (a `_ReqCase` subclass): create a recovery item through the
  real writer, the way `RecoverPickTests.recover_item` does
  (`tests/test_sitrep_tui_actions.py`; reuse it as a helper or replicate its
  `recovery-apply` call). With the agent running, assert `request_situation` is
  shown on the main list and on details. Press `w` and assert
  `deliver.lines == [">w crashed-agents"]`. Check whether
  `RecoverPickTests.recover_item` can be called from a `_ReqCase` (both derive
  from `ta._Case`). If it can, mix it in or call it as a function; do not copy it.

### 4. Skill text: `.claude/skills/aitask-sitrep/SKILL.md.j2` (~line 428)

Replace "The TUI never types it itself, since recovery contexts name no theme:
the user types it." with "The TUI's `w` key types `>w crashed-agents` for a
recovery item." Then regenerate
`tests/golden/skills/aitask-sitrep/SKILL-{default,fast,remote}-claude.md` with
the loop from `aidocs/framework/skill_authoring_conventions.md` ("Regenerate
command"), and check that the golden diff is only this sentence.

### 5. Docs (the "w does not apply" statements)

- `aidocs/framework/sitrep.md:297`, `w` row → "the item's context names a
  theme, or the item is a crash-recovery item (`recover:` ref), which maps to
  the skill's virtual `crashed-agents` theme (`RECOVERY_THEME`; read-side only,
  the detector still writes no theme)". The task also mentions a TUI Actions
  note ("`w` unavailable on recovery items"). Grep found no such text, so
  nothing changes there. Line 694's paragraph stays accurate. Optionally add
  "the TUI's `w` types it on a recovery item".
- `website/content/docs/tuis/sitrep/reference.md:41`: the condition becomes "The
  agent runs, and the item's context names a work area (theme), or the item is a
  crashed-agent item: then it types `>w crashed-agents`".
- `website/content/docs/tuis/sitrep/how-to.md:69` → "For a summary of all the
  crashed-agent items, press **w** on any of them (it types `>w crashed-agents`
  to the agent)."
- `website/content/docs/workflows/sitrep.md:60`, step 4 → "Press `w` on any of
  these items in the TUI, or type `>w` or `>w crashed-agents` to the agent, for
  a short summary of all the crashed work."
- Final grep: `grep -rn "crashed-agents\|w\` key" aidocs website/content .claude/skills/aitask-sitrep`
  finds no stale "does not apply" / "never types" claim.

### 6. Follow-up note

The skill text changes, so offer a note to t2199 (the codex/opencode port of the
sitrep skill) at Step 8e: "the `>w` request check no longer says the user types
`crashed-agents`; the TUI's `w` key does".

## Verification

- `python3 tests/test_sitrep_tui_requests.py`
- `python3 tests/test_sitrep_tui_actions.py` (regression)
- `bash tests/test_sitrep_skill_contract.sh`
- `bash tests/test_skill_render_aitask_sitrep.sh`
- `./.aitask-scripts/aitask_skill_verify.sh`
- `cd website && python3 check_links.py --build`

## Step 9 reference

After review and commit: Step 9 (Post-Implementation), archive the task and
plan (current-branch mode, nothing to merge).

## Risk

### Code-health risk: low
None identified. The change is one pure function plus one constant. The binding
gate and the request template stay the same. The edits stay inside the sitrep TUI
module, its test, one skill sentence (with goldens) and four doc lines.

### Goal-achievement risk: low
None identified. The skill already accepts `>w crashed-agents` whenever a
`recover:` item is listed, in any state, so the line the TUI now types always
passes the skill's request check. An explicit context theme still wins.
