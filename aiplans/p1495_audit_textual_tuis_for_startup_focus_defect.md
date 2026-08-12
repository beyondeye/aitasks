---
Task: t1495_audit_textual_tuis_for_startup_focus_defect.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1495 — Audit the four Textual TUIs for the t1491 startup-focus defect

## Context

`Screen._update_auto_focus` runs inside `Screen._compose` — **before** the app's
`on_mount` — and focuses the first focusable widget matching the resolved
selector. `App.AUTO_FOCUS` defaults to `"*"`, and `Screen.AUTO_FOCUS = None`
means *inherit the app's*, so it disables nothing. When the winner is a text
`Input`, every **non-`priority`** single-key binding is swallowed as text —
in t1491 that included `q`, so the board could not be quit and the incident was
misfiled as a *relaunch* bug.

t1491 fixed the board. t1495 was spawned from its Step 8b review with the
observation that `monitor`, `codebrowser`, `brainstorm` and `settings` set no
`AUTO_FOCUS` either, and that the exposure was **not verified per-TUI**. This
plan does that verification in a real pty, fixes what it finds, and records the
result durably.

**A headless test cannot substitute for the audit.** Measured on the board at
Textual 8.2.7, same fixture and size, a real terminal picked `Input#search_box`
while `App.run_test` picked `HorizontalScroll#board_container`, where `q` worked
fine. The pty is the only ground truth for which widget wins.

**Scope decisions taken with the user before planning:**

- The audit stays at the four TUIs the task names. Six further unguarded `App`
  subclasses were found (`minimonitor`, `syncer`, `chatlink`, `applink`,
  `diffviewer`, `agentcrew_dashboard`) — none sets `AUTO_FOCUS` — but several
  need bespoke state (a paired applink, a live crew, a brainstorm session) before
  they will boot. They are recorded as **unaudited** and handed to a follow-up.
- The milder "no real focus anchor at boot" gap (focus lands on a scroll
  container or a tab bar, so keys work but no row is selected) is **recorded, not
  fixed**. t1495 is a bug task about swallowed bindings, and `monitor_app.py`
  currently carries 37 uncommitted lines from a concurrent `t1493` session.

**Effort note:** the task carries `effort: low`. A live-pty audit of four TUIs
plus a two-layer fix and two new pins is closer to *medium*. Nothing is being
cut — this is flagged so the estimate is not read as a scope commitment.

## Pre-implementation finding (DOM analysis — to be confirmed, not assumed)

Static reading of the four composes, with `can_focus` verified by introspection
at Textual 8.2.7 (`VerticalScroll=True`, `Tabs=True`, `DirectoryTree=True`,
`Input=True`; `Container`/`Static`/`Header`/`Footer`/`TabbedContent=False`):

| TUI | first focusable in DOM order | swallows letters? |
|---|---|---|
| monitor (`monitor_app.py:649`) | `VerticalScroll#pane-list` | no |
| brainstorm (`brainstorm_app.py:2247`) | `Tabs` inside `TabbedContent#brainstorm_tabs` | no |
| settings (`settings_app.py:1584`) | `Tabs` inside `TabbedContent` | no |
| codebrowser — git repo (`codebrowser_app.py:676`) | `RecentFilesList#recent_files` | no |
| **codebrowser — non-git fallback (`codebrowser_app.py:677-679`)** | **`Input#file_search_input`** | **yes** |

The codebrowser's `compose()` has two branches: `get_project_root()` raising
`RuntimeError` yields a bare `Container#left_sidebar` holding a single `Static`,
neither focusable — so `Input#file_search_input` (`file_search.py:177`) becomes
the first focusable widget on the screen. That is the exact t1491 shape. The
sidebar never collapses (`SIDEBAR_WIDTH_BY_TIER = {WIDE:35, NORMAL:28,
NARROW:22}`), so terminal width does not open a second path to it.

Phase 1 exists to **confirm or refute this table live**. If the trace disagrees,
Phases 2–4 follow the trace, not this table.

## Phase 1 — Live audit (AC 1)

Scratchpad-only harness; nothing here is committed.

### Pre-phase (risk mitigations)

1. `[positive_control_focus_trace]` Before trusting any TUI's trace, point the
   probe at the **board**, whose auto-focus behaviour is already known and pinned
   (`BoardScreen.AUTO_FOCUS = ""`; `_claim_startup_focus` anchors a `TaskCard`).
   Launch `./ait board` in the fixture with `AIT_FOCUS_TRACE` set and require
   **both**: a `_update_auto_focus` line whose resolved `selector` is `""`, and a
   later `set_focus` line naming a `TaskCard`. If the board's trace file is empty
   or absent, the harness is broken — `sitecustomize` never fired — and **no
   TUI's "no auto-focus pick" result may be reported as a clean verdict** until
   the probe is repaired. Only after this control passes does Phase 1 step 4
   below produce verdicts.

Then the audit proper:

1. Write `sitecustomize.py` into a scratch dir. When `AIT_FOCUS_TRACE` is set it
   wraps `textual.screen.Screen._update_auto_focus` to append one JSON line per
   call — elapsed time, screen class, the **resolved** selector
   (`app.AUTO_FOCUS if screen.AUTO_FOCUS is None else screen.AUTO_FOCUS`), and
   the widget left focused — and wraps `Screen.set_focus` to log every later
   focus change. `sitecustomize` is imported by `site` at interpreter startup, so
   the real entry point (`exec "$PYTHON" .../<tui>_app.py`) is preserved; the
   probe is injected purely via `PYTHONPATH`.

2. Per TUI, build an isolated fixture following
   `tests/test_board_startup_focus_live.py:140-180`: a temp dir with a **copy of
   `ait`** and a **symlink** to `.aitask-scripts` (never `cp -r` — a copied tree
   is a snapshot and silently runs stale code), plus `aitasks/metadata/` with
   `project_config.yaml` and `gates.yaml`. Launch on a throwaway
   `tmux -L ait_t1495_<pid>` socket with `AITASKS_TMUX_SOCKET`, `PYTHONPATH` and
   `AIT_FOCUS_TRACE` exported into the **session environment** so `send-keys`
   commands inherit them. Never redirect the TUI's stderr — Textual writes frames
   there and the pane would capture blank.

   - `settings` → `./ait settings`
   - `monitor` → `./ait monitor` (needs `project_config.yaml` for session
     discovery)
   - `codebrowser` → `./ait codebrowser`, **twice**: once with `git init` in the
     fixture, once without, to cover both compose branches
   - `brainstorm` → `./ait brainstorm <n>` **with a valid session on disk** — see
     the brainstorm note below. Do **not** audit it on a session-less fixture.

3. **brainstorm needs a real session, or it cannot be behaviourally audited at
   all.** With no session, `on_mount` pushes `InitSessionModal`
   (`brainstorm_app.py:3183-3191`), and its cancel path `_on_init_result(None)`
   calls **`self.exit()`** (`:5403-5406`). So on a session-less fixture: the
   focused control is the modal's `Button#btn_init_blank`, not the dashboard's
   first focusable; `escape` quits the app outright; and the pane therefore
   returns to the shell for a reason that has nothing to do with `q` reaching
   its binding. A quit check there measures the modal and can read as a pass
   while the default screen was never exercised.

   *Primary path:* seed a minimal session directly on disk so `session_exists()`
   is true and `_load_existing_session()` runs — `.aitask-crews/crew-brainstorm-<n>/`
   containing `br_session.yaml`, `br_graph_state.yaml`, `br_groups.yaml` and
   `br_nodes/` (`brainstorm_session.py:53-56, 201-219`; `crew_worktree()` is a
   plain path, so no `ait crew init` git worktree is required). Shapes come from
   `init_session` and `brainstorm_dag`.

   *Fallback,* only if the dashboard will not load that fixture: report
   brainstorm's verdict from the **trace alone** — `_update_auto_focus` fires
   inside `Screen._compose`, strictly before `on_mount` pushes anything, so the
   default screen's pick is captured regardless. Record explicitly that the
   behavioural signal was **withheld, not passed**, and why. The modal's own
   focus pick may be recorded as a separate observation; it must never enter the
   brainstorm verdict.

4. For each: read the trace, then send the **bare quit key with no prior
   Tab/Esc/click** and poll `#{pane_current_command}` until it leaves the
   interpreter. Two independent signals — the trace (which widget won) and the
   behaviour (did `q` reach its binding) — so a wrong reading of one is caught by
   the other. The behavioural signal is only admissible when the **default
   screen** is the active screen at the moment the key is sent; if a modal is on
   top, the reading is about the modal and is discarded (see step 3).

   Note the asymmetry, so a passing quit is not over-read: `q` quitting proves
   *no widget swallowed it*, which is also true when **nothing** is focused. It
   confirms the absence of the t1491 defect; it does not confirm that a sensible
   widget holds focus. The trace is what distinguishes those two.

5. Record the results as the audit table used by Phases 2–4.

## Phase 2 — Fix (AC 2)

Expected to touch **only** `.aitask-scripts/codebrowser/codebrowser_app.py`,
applying the t1491 two-layer shape.

**Layer 1 — disable auto-focus on the default screen.** Add `Screen` to the
`textual.screen` import (`:48`, currently `ModalScreen` only) and a screen class
beside `CodeBrowserApp` (`:303`):

```python
class CodeBrowserScreen(Screen):
    """The codebrowser's default screen, with auto-focus disabled (t1495).

    `""`, not `None`: `None` inherits `App.AUTO_FOCUS` ("*") and disables
    nothing. Scoped to this screen so pushed modals keep the app-level "*"
    and still focus their first control.

    Without it, the non-git-repo compose branch (`compose`, the `RuntimeError`
    fallback) leaves `Input#file_search_input` as the first focusable widget,
    and every non-`priority` letter binding — `q` included — arrives as search
    text (t1491's shape).
    """

    AUTO_FOCUS = ""
```

and on the app:

```python
    def get_default_screen(self) -> Screen:
        return CodeBrowserScreen()
```

**Layer 2 — positive claim.** `_claim_startup_focus()`, deferred from `on_mount`
via `call_after_refresh` (the sidebar's children mount asynchronously, so their
anchors are not queryable synchronously). It **reuses the existing canonical
anchor helper** `_focus_recent_or_tree(recent, file_tree, code_viewer)`
(`codebrowser_app.py:1258-1271`) rather than reimplementing the preference order
that `action_toggle_focus` already owns.

Two guards the board's version does not need:

- **Skip when an explicit initial focus is pending.** `on_mount` already queues
  `call_after_refresh(self._apply_focus, pending)` for the `--focus file:line`
  feature; a claim queued after it would override the caller's request. The
  claim runs only in the `else` branch.
- **All-None guard.** `_focus_recent_or_tree` ends in `code_viewer.focus()`, so
  it must not be called when the query for `#code_viewer` also failed — fall back
  to `screen.set_focus(None)`. An unfocused screen routes keys straight to the
  App bindings, so `q` still quits.

**Known consequence in the non-git branch, accepted deliberately.** There the
claim lands on `CodeViewer`, and `action_toggle_focus` self-loops back to it
(`_focus_recent_or_tree(None, None, code_viewer)` with no sidebar targets), so
`#file_search_input` becomes unreachable by keyboard. Pre-fix it was reachable
exactly once — at boot, by the very accident this task removes — and Tabbing away
already stranded it, so the dead-end is **pre-existing**, not introduced here.
What the fix changes is only that the accidental first focus is gone.

Nothing functional is lost: in that branch `on_mount`'s `set_files` call sits
inside a `try` that queries `#file_tree` first (`:646-651`), so it raises,
`_all_files` stays `[]`, and the box can match nothing however it is focused.
Trading a focusable-but-inert box that swallowed `q` for an unfocusable inert box
is a strict improvement.

The Tab dead-end and the never-populated search list are nonetheless a real
pre-existing defect in a different code path. Record both in the Final
Implementation Notes' **Upstream defects identified** bullet so Step 8b offers
the follow-up:

- `codebrowser_app.py:1258-1271` — `_focus_recent_or_tree` collapses the focus
  cycle to a self-loop whenever neither `#recent_files` nor `#file_tree` is
  mounted, stranding `#file_search_input` and `#detail_pane`.
- `codebrowser_app.py:646-651` — the `set_files` seeding is inside a `try` keyed
  on `#file_tree`, so the non-git branch renders a search box that can never
  match anything.

Expanding this task to repair either was considered and rejected: both predate
the fix, neither blocks AC 1–3, and widening a `risk_evaluated` bug task into UX
repair is exactly what the follow-up mechanism exists for.

For each TUI the audit clears, no code changes — the reason is recorded in
Phase 4 instead.

## Phase 3 — Pins (AC 3)

**What each pin can and cannot see** — this is the part it is easy to get wrong,
so it is stated before the tests:

- The live test can only fail when **both** layers are absent. Removing layer 1
  alone does not fail it: the deferred claim lands ~130ms in, long before any key
  a tmux test can deliver, so it moves focus off the Input first. Removing
  layer 2 alone does not fail it either: with `AUTO_FOCUS = ""` and no claim the
  screen is simply **unfocused**, and an unfocused screen routes keys straight to
  the App bindings — `q` still quits. That is the board's own documented
  reasoning (`aitask_board.py:9166-9170`).
- Therefore the live test pins the **composite, user-visible defect** (a fresh
  codebrowser that cannot be quit), and **each layer is pinned individually in
  the headless module**. Layer 2 is headless-pinnable precisely because the claim
  is our own deterministic `on_mount` code, not an `AUTO_FOCUS` selection — the
  driver divergence that forced t1491's live pin does not apply to it.

**`tests/test_codebrowser_startup_focus_live.py`** (new) — pins the composite
defect, modelled on `tests/test_board_startup_focus_live.py`:

- Fixture is the **non-git** variant (a temp dir with no `.git`), which is the
  branch where the Input is first focusable.
- `@unittest.skipUnless(shutil.which("tmux"), ...)`; `SkipTest` only for
  environment unavailability. Once a pane exists, a codebrowser that will not
  quit is a **FAILURE**, not a skip.
- Launch, wait for the branch's own boot marker in `capture-pane` — the literal
  `Error: not inside a git repository` that this branch renders
  (`codebrowser_app.py:679`) — then send bare `q` and poll
  `#{pane_current_command}` until it leaves the interpreter within budget.
- The failure message carries the search row, not just a timeout: "still python"
  says it did not quit, while the row showing `q` sitting where
  `Search files...` should be says *why*.
- Add the basename to `SERIAL_CARVE_OUT` at `tests/run_all_python_tests.sh:84`
  (the boot budget becomes a flake under a loaded worker pool).

**`tests/test_codebrowser_startup_focus.py`** (new) — pins **both layers
separately**, modelled on `tests/test_board_startup_focus.py`. The startup-focus
tests run against **both** a git and a non-git fixture; the Tab-cycle tests are
per-fixture, because the two branches have genuinely different cycles (see
below). Do not blanket-parametrise every test over both fixtures — that is what
produced the wrong Tab assertion in the first draft:

- **Layer 1 (structural)** — `test_the_screen_resolves_to_no_auto_focus_selector`:
  the default screen is a `CodeBrowserScreen` and the selector Textual would
  apply resolves **falsy**, asserted through the resolution rule
  (`app.AUTO_FOCUS if screen.AUTO_FOCUS is None else screen.AUTO_FOCUS`) rather
  than against the literal `""` — that catches both `AUTO_FOCUS = None`
  (which *inherits*, disabling nothing) and a change to `App.AUTO_FOCUS`.
- **Layer 2 (positive claim)** — `test_startup_focus_is_a_browse_anchor`: after
  boot settles, `app.screen.focused` **is not `None`**, and is the anchor that
  fixture's branch actually yields — asserted **per fixture**, not as a union
  over both (a union would pass if the git branch anchored on `CodeViewer`,
  which would mean the sidebar claim silently stopped working):
  - git fixture → `RecentFileItem` when the recent-files store has entries, else
    `RecentFilesList` itself — the two outcomes of `_focus_recent_or_tree`'s
    first-focusable-child loop. Seed the store deterministically so exactly one
    of these is expected, rather than accepting either.
  - non-git fixture → `CodeViewer`.

  The explicit not-`None` assertion is the load-bearing part: without it,
  deleting the claim leaves focus `None` and an `assertNotIsInstance(..., Input)`
  check would still pass.
- `test_the_search_input_never_holds_focus_during_boot` — `#file_search_input`
  never holds focus on **any** of 8 successive `pilot.pause()` cycles, not just
  at settle.
- `test_tab_cycle_still_reaches_the_search_box` — **git fixture only.** The
  documented cycle is `recent_files → file_tree → search → code_viewer → detail`
  (`action_toggle_focus` docstring, `:1183`), so from the boot anchor on
  `#recent_files` it takes **two** Tab presses to reach `#file_search_input`, not
  one. (One is the board's number, where the anchor is a card; copying it here
  would assert the wrong thing.) Then type a character and press Escape, which
  clears the search — `action_handle_escape_key` only intercepts when the input
  has focus **and** a non-empty value (`:653-668`).
- `test_tab_is_a_self_loop_without_a_sidebar` — **non-git fixture.** Pins the
  cycle that actually exists there rather than asserting a reachability the
  branch does not have: from the `CodeViewer` anchor, Tab lands on `CodeViewer`
  again, because `action_toggle_focus` falls through to
  `_focus_recent_or_tree(None, None, code_viewer)`. See the note below — this is
  recorded behaviour, not an endorsed design.

**Negative control** — one mutation at a time, each naming the test that must
fail. A negative control that **passes** means the pin is wrong, not that the
code is fine:

| mutation | must fail |
|---|---|
| delete the `call_after_refresh(self._claim_startup_focus)` call | headless `test_startup_focus_is_a_browse_anchor` (focus becomes `None`) |
| `CodeBrowserScreen.AUTO_FOCUS = None` | headless `test_the_screen_resolves_to_no_auto_focus_selector` |
| revert **both** layers | the live test — and only then |

**Open empirical question, to be answered and recorded, not assumed.** In the
non-git branch the only focusable widgets are the Input, a hidden `OptionList`,
`CodeViewer` and a hidden `DetailPane` — a much smaller set than the board's. It
is therefore plausible that `App.run_test` also picks `Input#file_search_input`
here, in which case `test_the_search_input_never_holds_focus_during_boot` would
fail pre-fix headless, unlike t1491's experience on the board. Determine this by
running the headless module against the unfixed code **before** applying Phase 2,
and record the answer in the Final Implementation Notes either way. The live pin
ships regardless — AC 3 requires it, and the real terminal is the ground truth.

## Phase 4 — Record the audit (AC 2)

`aidocs/framework/tui_conventions.md` gains a **Startup focus (`AUTO_FOCUS`)**
section — a plan gets archived, and the next person to add a TUI needs this at
the point they are working, which is where `CLAUDE.md` already sends them:

- the rule (`_update_auto_focus` runs in `_compose`, before `on_mount`; `None`
  inherits, `""` disables; only `priority` bindings survive a focused `Input`);
- the two-layer fix, naming the board and codebrowser implementations;
- the driver-divergence warning: a headless pin cannot fail on this;
- the audit table — per app, what won focus, verified-live or unaudited, and the
  reason each cleared app is not affected;
- the six unaudited apps, listed explicitly as unaudited rather than as clear.

At **Step 8b/8c**, spawn the agreed follow-up task covering the live audit of
those six.

### Post-phase (risk mitigations)

1. `[sweep_codebrowser_focus_tests]` Run the whole codebrowser test surface
   (`bash tests/run_all_python_tests.sh --test-dir tests` plus every
   `tests/test_codebrowser*.py` / `tests/test_file_search*.py` /
   `tests/test_file_tree*.py` individually) and read **each** failure for the
   "fixture assumed nothing was focused at boot" shape — a `check_action` False
   branch reached for free, or an idle style sampled from an unfocused widget.
   Repair those by arranging the state explicitly (`app.screen.set_focus(None)`
   in the test's setup), never by weakening the assertion: the failing assertion
   is usually the fixture's, not the invariant's. Record every test touched and
   why in the Final Implementation Notes.
2. `[verify_initial_focus_flag]` Prove the `else` guard that keeps
   `_claim_startup_focus` from stealing the `--focus file:line` target. Drive the
   `initial_focus` entry path (the `CodeBrowserApp(initial_focus=...)` kwarg and
   the `AIT_CODEBROWSER_FOCUS` env-var path consumed by
   `_consume_and_apply_focus`) and assert the requested file/line still holds
   focus after boot settles. A headless `run_test` assertion is adequate here —
   this is an ordering contract between two `call_after_refresh` callbacks, not
   an `AUTO_FOCUS` driver behaviour — and it must fail if the `else` is changed
   back to an unconditional claim.

## Verification

1. `bash tests/run_all_python_tests.sh --test-dir tests` — read **only** the last
   line (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); an earlier
   `Results: N passed` line belongs to one module. Do not pipe to `tail` without
   `pipefail` — the status is lost.
2. The two new modules run green individually, and the live one runs in the
   serial phase.
3. Each negative control above fails by its named test — and, for the two
   single-layer mutations, the live test is confirmed to still **pass**, since a
   live failure there would mean the mutation broke something other than the
   layer under test. Revert each mutation before the next.
4. Manual, in a real pty: `./ait codebrowser` from a non-git directory, press
   `q` with no prior key — it must quit. Repeat inside the repo.
5. `shellcheck` is not needed (no shell scripts change).

## Step 9 — Post-implementation

Merge to `main` per the plan header, then archive t1495 and this plan.

## Risk

### Code-health risk: medium

- Changing startup focus breaks sibling codebrowser tests that used "nothing is
  focused at boot" as a cheap way to reach a `check_action` False branch or to
  sample an idle style — this is what happened in t1491. Those are fixture
  assumptions, not invariants, and the wrong repair is to weaken the assertion ·
  severity: medium (residual — addressed by inline post-phase
  sweep_codebrowser_focus_tests) · → mitigation: inline post-phase
  sweep_codebrowser_focus_tests
- The positive claim can fight the existing `--focus file:line` path: `on_mount`
  already queues `call_after_refresh(self._apply_focus, pending)`, and a claim
  queued after it silently overrides the caller's requested target. The plan
  guards this with an `else` branch, but the guard itself is unproven ·
  severity: low (residual — addressed by inline post-phase
  verify_initial_focus_flag) · → mitigation: inline post-phase
  verify_initial_focus_flag

### Goal-achievement risk: medium

- The `sitecustomize` trace may never fire (PYTHONPATH not inherited through the
  launcher's `exec`, `site` disabled, or a venv `sitecustomize` shadowing it). A
  silent no-trace reads **exactly** like "auto-focus never picked anything",
  which would produce a false "not affected" verdict for all four TUIs and make
  the whole audit vacuous · severity: low (residual — addressed by inline
  pre-phase positive_control_focus_trace, which makes "harness broken"
  distinguishable from "nothing was picked") · → mitigation: inline pre-phase
  positive_control_focus_trace
- `brainstorm` may not boot into its dashboard in a synthetic fixture: with no
  session `on_mount` pushes `InitSessionModal`, whose cancel path calls
  `self.exit()`. A behavioural reading there measures the modal and can look
  like a pass while the default screen was never exercised · severity: medium ·
  → mitigation: none — Phase 1 step 2b makes a seeded on-disk session the
  primary path and, on fallback, admits only the trace while recording the
  behavioural signal as **withheld rather than passed**
- The fix makes `#file_search_input` keyboard-unreachable in the non-git branch:
  the claim anchors `CodeViewer` and `action_toggle_focus` self-loops back to it
  with no sidebar targets to cycle through · severity: low (residual — the
  widget is inert there anyway, `set_files` never runs, and the dead-end
  pre-dates the fix; Phase 2 records both as upstream defects for the Step 8b
  follow-up rather than widening this task) · → mitigation: none — accepted and
  documented in Phase 2
- A pin can be written that cannot fail on the layer it claims to cover: with
  `AUTO_FOCUS = ""` in place, deleting the positive claim leaves the screen
  unfocused, and an unfocused screen still routes `q` to the App binding — so a
  live quit test passes with layer 2 absent · severity: low (residual — the
  Phase 3 negative-control table now assigns each layer to the test that can
  actually fail on it, and the layer-2 test asserts focus is not `None`) ·
  → mitigation: none — corrected in Phase 3 during plan review

### Planned mitigations

- timing: pre-phase | name: positive_control_focus_trace | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a silent no-trace is indistinguishable from "no auto-focus pick" | desc: Run the probe against the board, whose auto-focus behaviour is already known and pinned, and require a non-empty trace before any TUI verdict is accepted
- timing: post-phase | name: sweep_codebrowser_focus_tests | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — sibling tests that relied on "nothing focused at boot" | desc: Run the full codebrowser test surface after the fix and repair fixture-assumption failures by arranging state explicitly, never by weakening assertions
- timing: post-phase | name: verify_initial_focus_flag | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the startup claim could override the requested --focus target | desc: Drive the initial_focus entry path after the fix and assert the requested file/line still holds focus once boot settles

**Post-inline reassessment (single pass).** Re-assessed against the augmented
plan. Both dimension levels are **unchanged at medium**, and deliberately so:
the three inline phases reduce each bullet's residual severity, but code-health
keeps a real bounded concern the sweep can only *detect* — `get_default_screen`
changes app-wide screen construction under two mixins (`TuiSwitcherMixin`,
`ShortcutsMixin`) and twelve modal screens, and that interaction is not verified
until the sweep runs. Goal-achievement keeps `brainstorm`'s fixture coverage as
"covered but not airtight". No new risks were introduced by the inline phases.

## Constraint: concurrent session on `monitor_app.py`

`t1493` is `Implementing`, locked since 11:20, with 37 uncommitted lines in
`.aitask-scripts/monitor/monitor_app.py` (plus five other monitor/shadow files
and six test files). Under this plan the monitor is **not** edited, so there is
no conflict — but every commit here must stage **explicit paths only**. Never
`git add -A`, and never `git add` a path that also carries t1493's hunks.
