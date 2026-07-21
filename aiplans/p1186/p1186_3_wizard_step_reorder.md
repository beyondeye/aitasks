---
Task: t1186_3_wizard_step_reorder.md
Parent Task: aitasks/t1186_chatlink_wizard_allowlist_live_pickers.md
Sibling Tasks: aitasks/t1186/t1186_1_authorization_modes.md, aitasks/t1186/t1186_2_discord_fetch_surface.md, aitasks/t1186/t1186_4_allowlist_picker_ui.md
Archived Sibling Plans: aiplans/archived/p1186/p1186_*_*.md
Worktree: (profile 'fast' — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-07-21 11:14
---

# p1186_3 — Wizard step reorder (derived numbering + declared seams)

## Context

Third sequential slice of t1186 (chatlink wizard live allowlist pickers). The
wizard's allowlist step must become a *live picker* over Discord members and
roles (t1186_4), but the bot token — the precondition for any fetch — is
currently entered at step 5, three steps *after* the allowlist at step 2. The
fetch is impossible where the picker needs to live.

This child does the structural move and removes the two couplings that make
`_STEPS` reordering fragile:

1. Each screen hardcodes its own `"Step N/7"` title literal, so any reorder
   silently desynchronizes the visible numbering from the actual position.
2. `make_step()` hardcodes `if cls in (TokenScreen, LiveCheckScreen,
   SummaryScreen)` to decide which screens receive the `seams` argument, so
   the factory must be edited whenever the seam-needing set changes (t1186_4
   adds `AllowlistScreen` to it).

Outcome: `_STEPS` becomes the single source of truth for both order and
numbering, seam needs are declared on the screen class, and the token + live
check precede the allowlist so t1186_4 can fetch.

## Current state (re-verified 2026-07-21 against live source)

All line refs below were re-checked this session. **Neither landed sibling
touched the wizard**: t1186_1 (`868d01455`) changed `config.py` / `policy.py` /
`preflight.py` / docs / tests; t1186_2 (`90a6cee7c`) added
`chatlink/allowlist_fetch.py` + `discord_adapter.py` helpers. `wizard.py`
(698 lines) and `tests/test_chatlink_tui.sh` (572 lines) are byte-identical to
when this plan was written, so every original line ref still holds.

- `_STEPS` — `wizard.py:697-698`, currently `IntakeChannelScreen,
  AllowlistScreen, DenyRepoScreen, CeilingsScreen, TokenScreen,
  LiveCheckScreen, SummaryScreen`.
- `make_step(idx)` — `wizard.py:674-679`, hardcoded seam-class tuple at `:677`.
- Navigation `start_wizard()` — `:665-694`, purely index-based
  (`BACK`/`NEXT`/`DONE` sentinels `:48-50`). Reordering is mechanically safe.
- `step_title` literals, one per class: `:224-225`, `:256`, `:291`, `:312`,
  `:346`, `:385`, `:510`. Base `_WizardStep.compose()` renders
  `self.step_title` into `Label(id="wizard_title")` at `:181`.
- `_WizardStep.__init__` — `:174-177` (`state`, keyword-only `first`).
- **Safety of the move (verified):** `LiveCheckScreen` reads only
  `state["provider"]` (`:401`, `:411`), `state["token"]` (`:413`),
  `workspace_id` / `conversation_id` / `thread_id` (`:423-425`) — all set by
  steps 1-2 under the new order. `initial_state()` (`:97-122`) pre-fills every
  key anyway, so no `KeyError` is reachable regardless of order.
- **No external consumers:** grep confirms the seven screen classes,
  `step_title`, `_STEPS` and `make_step` are referenced *only* by `wizard.py`
  and the `isinstance` assertions in `tests/test_chatlink_tui.sh`.
  `tests/test_chatlink_wizard.sh` never imports `chatlink.wizard` (it covers
  the Textual-free helpers), so it is untouched by this change.
- **No doc pins the numbering:** no `Step N/7` string exists anywhere in
  `aidocs/`, `website/content/`, or `seed/`. The two prose references to the
  live-validation step describe it as "after token entry"
  (`website/content/docs/workflows/bug-report-intake.md:311`,
  `aidocs/chat/discord_bot_setup.md:74`) — still true after the reorder.
- **Baseline:** `bash tests/test_chatlink_tui.sh` → `PASS: 66, FAIL: 0`
  (run this session).

## New step order

`IntakeChannelScreen(1), TokenScreen(2), LiveCheckScreen(3), AllowlistScreen(4),
DenyRepoScreen(5), CeilingsScreen(6), SummaryScreen(7)`

## Steps

### 1. Derived numbering (`.aitask-scripts/chatlink/wizard.py`)

On `_WizardStep` (`:171-177`):

- Replace the `step_title = ""` class attr with `step_name = ""` (title text
  **without** numbering).
- Extend `__init__` with keyword-only `step_no: int = 0`, `step_total: int = 0`,
  stored on the instance.
- In `compose()` (`:181`), render the derived string instead of the literal:

  ```python
  yield Label(f"Step {self.step_no}/{self.step_total} — {self.step_name}",
              id="wizard_title")
  ```

Convert all 7 literals to `step_name`, keeping the descriptive text verbatim and
dropping only the `"Step N/7 — "` prefix. `AllowlistScreen` keeps its current
wording ("Who may open a bug report (deny-by-default)") — t1186_4 revises it
alongside the authorization-mode UI.

`_ReplaceConfirmScreen` (`:459`) is a bare `ModalScreen` outside `_STEPS` and is
left alone — it carries no numbering.

### 2. Declared seams (`wizard.py`)

- Add `needs_seams: bool = False` to `_WizardStep`; set `needs_seams = True` on
  `TokenScreen`, `LiveCheckScreen`, `SummaryScreen`. (t1186_4 adds it to
  `AllowlistScreen` — this is the extension point that makes that a one-line
  change.)
- Rewrite `make_step()` (`:674-679`) to branch on the class attribute and derive
  the numbering from the index — deleting the hardcoded tuple:

  ```python
  def make_step(idx: int) -> _WizardStep:
      cls = _STEPS[idx]
      kwargs = dict(first=idx == 0, step_no=idx + 1,
                    step_total=len(_STEPS))
      if cls.needs_seams:
          return cls(state, seams, **kwargs)
      return cls(state, **kwargs)
  ```

  A future screen that needs seams but forgets the flag fails loudly with a
  `TypeError` on push (missing positional `seams`) — same failure mode as the
  old tuple, no silent degradation.

### 3. Reorder `_STEPS` (`wizard.py:697-698`)

```python
_STEPS = (IntakeChannelScreen, TokenScreen, LiveCheckScreen,
          AllowlistScreen, DenyRepoScreen, CeilingsScreen, SummaryScreen)
```

Also update the module docstring's flow summary (`wizard.py:3-4`), which still
reads "intake channel → allowlist → deny mode / repo name → ceilings → token →
summary".

### 4. Test walkthrough resequence (`tests/test_chatlink_tui.sh`)

Reorder the Pilot input sequences and `isinstance` progression assertions to
match. The three walk apps change as follows.

**`app2` — abort mid-wizard (`:278-299`):** after the intake `enter`, the next
screen is `TokenScreen`, not `AllowlistScreen` (`:290-291`). Rename the check to
"intake advances to token". Escape-abort and the two zero-write assertions are
unchanged.

**`app3` — full walk (`:302-512`):** new visit order —

1. intake inline-validation error (unchanged, `:311-319`)
2. valid intake → `TokenScreen`; **new assertion:** `#wizard_title` renders
   `"Step 2/7"`
3. Back → intake with `#wiz_workspace == "111"` retained (unchanged intent),
   `enter` → back to token
4. empty token keeps the modal open with "no token stored yet" (moved up from
   `:377-385`; still correct because `app2` aborted without writing a token),
   then `"secret-token-123"` → `LiveCheckScreen`
5. live seam not called before validate; Continue → **`AllowlistScreen`**
   (was `SummaryScreen`, `:397-399`); **new assertion:** `#wizard_title` renders
   `"Step 4/7"` — a second index proves the numbering is derived from position
   rather than a relabeled constant
6. Back → `LiveCheckScreen`, run the injected live runner, assert the rendered
   rows and `wiz_live["args"] == ("secret-token-123", "111", "222", None)`
   (unchanged), then Continue → `AllowlistScreen` (advisory-only proof)
7. allowlist empty-empty warns once, second `enter` → `DenyRepoScreen`
8. repo_name → `CeilingsScreen`; out-of-range ceiling error, then `1024` →
   `SummaryScreen`
9. everything from the summary assertions onward (`:425-512`: save/token-failure/
   retry/0600/`repo_name` DELETE/preflight rows/commit hint/Close) is unchanged

   Keep the existing `asyncio.sleep(0.4)` guards around consecutive
   `#btn_wiz_next` clicks — they step past Textual's ~0.3s Button
   active-effect window and are unrelated to ordering.

**`app4` — mid-run dismiss guard (`:518-562`):** the walk to the live step
collapses to two `enter`s (intake conversation → token, empty token keeps the
stored one), dropping the now-later user_ids / repo_name / sandbox_pids presses.
Continue-mid-run then lands on `AllowlistScreen`; retarget both post-release
assertions (`:552-559`) to `AllowlistScreen`. The guard under test is unchanged
(a late `call_from_thread(_apply_results)` hits the `is_attached` check on a
dismissed screen), and the closing `escape` still aborts with no writes.

Update the file-header comment (`:9-14`) to name the new step order.

## Verification

- `bash tests/test_chatlink_tui.sh` → green, **`PASS: 68, FAIL: 0`** (baseline
  66 + the two derived-numbering assertions). A count below 68 means a check was
  dropped rather than resequenced. All pre-existing behaviors must still pass
  under the new order: escape-abort zero-writes, wizard restart, Back-retains-
  state, empty-allowlist double-Next, live-check spy (not called before
  validate; skip path; advisory failure; `app4` mid-run dismiss generation
  guard), save / replace-confirm / token-write-failure / retry paths.
- `bash tests/test_chatlink_wizard.sh` → green (headless helpers untouched;
  confirms the change did not leak into the Textual-free surface).
- `PYTHONPATH=.aitask-scripts python -m chatlink.chatlink_app --smoke` exits 0
  (also covered as step 1 of the TUI test).
- Manual sanity: a wizard walk shows derived numbering on every screen with no
  `N/7` drift — the aggregate manual-verification sibling t1186_5 owns the live
  walkthrough (its checklist already names this exact order).

Post-implementation per task-workflow Step 9; archive via
`aitask_archive.sh 1186_3`.

## Risk

### Code-health risk: low

- `step_no` / `step_total` default to `0`, so a screen constructed outside
  `make_step()` would render `"Step 0/0 — …"`. No such call site exists today
  (grep-verified: the classes appear only in `wizard.py` and `isinstance`
  assertions), and the defaults exist only to keep the subclass `**kwargs`
  pass-through simple · severity: low · → mitigation: none planned (declined —
  no reachable call site)
- Resequencing ~90 lines of the Pilot walkthrough (active-effect sleeps, the
  blocking-worker generation guard in `app4`) could weaken a check silently
  instead of failing loudly · severity: low · → mitigation: pinned by the
  explicit `PASS: 68` count in Verification, not a follow-up task

### Goal-achievement risk: low

- None identified. The deliverable is fully enumerated (new `_STEPS` order,
  derived numbering, class-declared seams), every line ref was re-verified
  against live source this session, the ordering-safety precondition
  (`LiveCheckScreen` reads only step-1/2 state) was checked directly, and the
  downstream consumer t1186_4 already pins the exact contract names
  (`needs_seams`, derived numbering) in `aiplans/p1186/p1186_4_allowlist_picker_ui.md:15,28`.
