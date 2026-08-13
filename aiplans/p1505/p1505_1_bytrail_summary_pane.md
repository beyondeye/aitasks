---
Task: t1505_1_bytrail_summary_pane.md
Parent Task: aitasks/t1505_lite_trail_mode_and_trail_summary_pane.md
Sibling Tasks: aitasks/t1505/t1505_2_trail_detail_modal_entry_first.md, aitasks/t1505/t1505_3_trail_narrative_overview_field.md, aitasks/t1505/t1505_4_trail_skill_lite_default.md
Archived Sibling Plans: aiplans/archived/p1505/p1505_*_*.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-13 14:37
---

# p1505_1 — By-Trail summary pane

Adds a fixed-height pane at the bottom of the By-Trail view showing the trail's
free-form summary, plus a key that expands it into a modal. Riskiest surface of
t1505 and deliberately sequenced first.

## Context

`/aitask-trail`'s prose rationale currently lives only inside `TrailDetailScreen`,
one card at a time. The user's real question — "which task should I pick next, and
why?" — is answered by the trail-*level* summary, which should be readable **while
scanning the cards**, not behind a modal. This child adds that surface.

It is sequenced first because it is the riskiest part of t1505: Textual layout work
whose documented failure mode (t1278) is **invisible** to `display` / `visible`
assertions.

## Verification pass (2026-08-13) — corrections to the previous plan

This plan was re-verified against the current `main` (`91a93e8b8`). What the earlier
draft got right, and what it got wrong:

**Confirmed sound (verified first-hand, not taken on trust):**

- Textual's `Footer` sets `dock: bottom; height: 1`, and `MultiRowFooter`
  (`lib/multirow_footer.py:222`) overrides only `layout`/`height` — it never unsets
  the dock. The "never dock the pane" constraint is real.
- `#board_container` has **no** CSS rule of its own; it resolves to `height: 1fr`
  from `ScrollableContainer`'s `DEFAULT_CSS`. A fixed-height flow sibling therefore
  takes its rows and the columns keep the rest, exactly as assumed.
- `v` is **not** bound at App level. The `v`/`u` keys belong to `TaskDetailScreen`
  (`_shortcuts_scope = "board.detail"`) — at lines **5809** (`u`) and **5823** (`v`),
  not 5819/5833.
- `narrative` is `additionalProperties: false` with keys `problem_statement`,
  `recommendation_summary`, `method_note`, `caveats`. There is **no `overview`** yet
  (t1505_3 adds it), so the fallback is the only live path today.
- `rendering_hints` is open (`additionalProperties: {string|number|boolean}`), and
  `aitask_board.py` reads it **nowhere** — the depth label is entirely new work.
- The render-level assertion helper the pre-phase needs **already exists**:
  `_screen_rows(app)` at `tests/test_board_bytrail_view.py:101`, built on
  `app.screen._compositor.render_strips(app.screen.size)`. Its docstring already
  cites t1278. Do not invent a new idiom.

**Corrections — the previous plan was wrong on these:**

| Claim in the old plan | Reality |
|---|---|
| class `AitaskBoard` | **`KanbanApp`** (`:7253`). No `AitaskBoard` exists. |
| board `DEFAULT_CSS` ~7290-7400 | the attribute is **`CSS`**, at **7263–7541** |
| `compose()` ~7964 | **7954** |
| `BINDINGS` ~7560-7655 | **7547–7643** |
| t1278 comment at `:7362` | comment block **7347–7363** |
| trail helper block 609-1020 | **609–1032** |
| `TrailDetailScreen` ~3825 | **3815** |
| `_trail_drift_text` ~3392 | **3382** |
| `v`/`u` at 5819/5833 | **5823** / **5809** |
| "t1468_5 does not edit `aitask_board.py`" | it **did** (import + `_followup_marker`). It has since **landed** (`b25bb4893`), so the tree is clean and this is no longer a constraint. |

**New trap found in verification:** `VerticalScroll` also defaults to `height: 1fr`.
The pane's explicit `height` is therefore **load-bearing, not cosmetic** — omit it
and the pane silently splits the vertical space 50/50 with the columns instead of
erroring.

**Other anchors:** `check_action` `:7705` · `_refresh_subtitle` `:8106` ·
`_trail_banner` `:8075` · `refresh_board` `:8258` (bytrail branch `:8311`) ·
`_set_base_filter` `:8958` · `_render_bytrail` `:10160`.

## Implementation steps

### Pre-phase (risk mitigations)

1. **[characterize_board_compose_layout]** Before mounting anything, add a
   characterization test to `tests/test_board_bytrail_view.py` that pins the
   **composited** footer row and the `#board_container` geometry at a small terminal
   size with the board in By-Trail.

   - Extend `ByTrailTestBase` (`:83`) and drive the view with
     `_enter_synthetic_bytrail` (`:167`) — it stubs `_start_trail_drift`, which also
     avoids t1487's in-flight-worker teardown hazard.
   - Assert with `_screen_rows(app)` (`:101`), **not** `widget.display` /
     `widget.visible`. Rationale, recorded in the board's own CSS at
     `aitask_board.py:7347-7363` (t1278): two same-edge docked siblings land at the
     **same offset**; one paints over the other while both still report
     `display=True`, `visible=True` and a correct region. That defect hid every
     `sub_title` write for the app's entire history.
   - Model it on the existing `BannerRenderTests`
     (`tests/test_board_bytrail_view.py:2328`), whose
     `test_header_row_costs_no_board_height_and_keeps_a_separator` (`:2520`) already
     pins `#board_container.region == (0, 4)` at `size=(120, 20)`.
   - **Run it before step 1 and confirm it passes against the unmodified board.** A
     characterization test that was never green on the old code pins nothing.

2. **[label_trail_depth]** Surface `rendering_hints.depth` on the By-Trail banner so
   a lite artifact is never silently mistaken for a deep one.

   - Write it in `_trail_banner` (`:8075`) / `_refresh_subtitle` (`:8106`) — the
     documented single writer — not at a new site.
   - **An absent hint renders nothing. Never default to "deep":** every trail written
     before t1505_4 has no hint, and defaulting would state a falsehood about them.
     Pin the absence *explicitly* — a missing label and a "deep" label must not be
     conflated by a test that merely asserts "no crash".
   - **Exact shed rule — additive-if-it-fits, today's ladder otherwise.**
     `_trail_banner` is a four-rung width-budget shedder whose contract (t1278) is
     that the *volatile* freshness marker is the last survivor. Its current ladder is
     `full → elide title → drop title → marker alone`.

     Do **not** thread `depth_note` through those rungs as an `owner_note` sibling.
     That was the previous draft's instruction and it is wrong twice: it makes the
     **title shed earlier than it does today** for every trail carrying a hint, and it
     defines **no rung at which depth alone is dropped** — depth would survive to
     rung 3 and then vanish in the same cliff that drops the title. Instead:

     1. Compute `full_with_depth = f'By-Trail: "{title}"{suffix}{owner_note}{depth_note}'`.
        If the measured budget admits it, return it.
     2. Otherwise fall through to **today's ladder, unchanged and depth-free**.

     Depth is then strictly additive: it renders only when there is room, it is the
     first signal shed, and the freshness marker is still last.

   - **Negative control (no-regression):** with `rendering_hints.depth` absent, the
     banner must be **byte-identical to today's output at every width in the test's
     ladder**. That is what proves the change cannot regress the 100% of existing
     trails that carry no hint.
   - Pin the exact transitions: wide → depth shown; one step narrower → depth absent
     with title **and** marker intact; very narrow → marker alone.

### 1. Pure resolver

In the `# --- Implementation trails (By-Trail view, t1210_4) ---` block
(`aitask_board.py:609-1032`), next to `canonical_trail_ref` (`:704`),
`build_trail_lanes` (`:719`) and `trail_entry_refs` (`:783`):

```python
def trail_summary_text(doc) -> str:
    """The trail's free-form summary for the By-Trail pane.

    Prefers `narrative.overview` (t1505_3's advisory prose field) and falls back
    to the always-required `narrative.recommendation_summary`, so a trail written
    before that field existed still shows something useful. Returns "" when
    neither carries text — the caller hides the pane rather than showing an empty
    frame."""
```

Pure and import-testable: no widget, no app state — matching the other helpers in
that block. Whitespace-only counts as empty at **every** level (`doc`, `narrative`,
each field).

### 2. `TrailSummaryPane`

A `VerticalScroll` (id `#trail_summary`) holding a `Static`, yielded in
`KanbanApp.compose()` (`:7954`) **after** `yield HorizontalScroll(id="board_container")`
and **before** the `MultiRowFooter`. CSS goes in `KanbanApp.CSS` (`:7263-7541`),
beside the other `#`-id rules:

```
#trail_summary { height: 6; border-top: hkey $secondary-background; padding: 0 1; }
```

**Never `dock: bottom`** — the footer already claims that edge, and that is the exact
t1278 collision the pre-phase guards. **The explicit `height` is mandatory:**
`VerticalScroll` inherits `height: 1fr` from `ScrollableContainer`, so without it the
pane and the columns split the space evenly.

**The body must not render its text as markup.** `Static` defaults to
`markup=True`, and trail prose is free-form, so brackets in it are *content*.
Textual's `Content` parser silently **deletes** an unrecognised tag — a literal
`[blocked]` or `[risk_mitigation]` (a real `followup_kind` in this repo) disappears
with no error — and a bracketed URL such as `[link=https://example.dev]docs[/link]`
raises `MarkupError`. That exception would escape from `_refresh_trail_summary` into
`_refresh_subtitle`, taking the **banner and the whole By-Trail refresh** down at the
moment the user selects that trail, not just the pane. Construct the body with
`markup=False` **and** write it through `Text(...)` (step 3): either alone suffices,
both together mean no later caller can reintroduce it.

### 3. Visibility **and content** — one owner

Add a single helper and call it from **`_refresh_subtitle` (`:8106`)**, the documented
single writer for By-Trail chrome:

```python
def _refresh_trail_summary(self) -> str:
    """Single owner of the By-Trail summary pane.

    Resolves the summary ONCE and writes content and visibility together,
    returning the resolved text so the expand modal renders exactly what the
    pane shows."""
    text = ("" if self.base_filter != "bytrail"
            else trail_summary_text(self._trail_doc))
    # write Static content AND pane.display from this one value
    return text
```

**Content and visibility must move together — this is the correctness core of the
step, not a tidiness preference.** `self._trail_doc` is rewritten at **two** seams:

| seam | line | trigger |
|---|---|---|
| `_activate_trail` | `:10309` | `s` — selecting a different trail |
| `_on_trail_reload` | `:10372` | artifact reload / `R` version watch |

Both already end with `self._refresh_subtitle()`. So if the pane's `display` were
refreshed there while its `Static` content were written anywhere else (at `compose`
time, or in `_render_bytrail`), **selecting trail B would repaint the banner while the
pane kept showing trail A's summary** — or a blank frame. Routing both through one
helper at the existing convergence point (12 call sites: view switches, drift
callbacks, settings changes, resizes, and all four exits of `_render_bytrail`) closes
that by construction rather than by discipline.

The helper writes the body as `Text(text)`, never a bare `str` — see the free-form
prose note in step 2. `TrailSummaryScreen` renders through `Text(...)` for the same
reason, so both surfaces treat brackets as content.

`action_trail_summary_expand` must build `TrailSummaryScreen` from this helper's
**return value** — never re-derive from `self._trail_doc` — so the modal and the pane
cannot disagree.

Extend `_refresh_subtitle`'s docstring: it now owns By-Trail chrome (subtitle **and**
summary pane), not just the subtitle.

**Leaving By-Trail must restore the full-height column area** — `display = False`
whenever `base_filter != "bytrail"`, guaranteed by the same helper.

### 4. Expand key

```python
Binding("v", "trail_summary_expand", "Summary"),
```

into `KanbanApp.BINDINGS` (`:7547-7643`). `v` is free at App level (verified). Resolve
through `resolve_key("board", …)` like the other trail actions
(`aitask_board.py:8238`, `:9089`).

- Gate in `check_action` (`:7705`) to By-Trail with a non-empty summary, alongside the
  existing `trail_*` gating at `:7798-7815`.
- **Re-check the same condition inside `action_trail_summary_expand`.** A binding gate
  is not an action guard: the action stays reachable via the command palette, a remap,
  or a race with a view switch.
- `show=True` with the short label `Summary`, per the footer convention in
  `aidocs/framework/tui_conventions.md` ("TUI footer must surface every operation").
  `MultiRowFooter` reflows, so there is no room argument for hiding it.
- `TrailSummaryScreen(ModalScreen)`: full text in a `VerticalScroll`, `escape` to
  close, modeled on `TrailDetailScreen` (`:3815`) — own `DEFAULT_CSS`, a plain
  `escape` binding, `Container` + `VerticalScroll` + `Static`, dismiss on button and
  `action_cancel`. It declares **no** `_shortcuts_scope`, exactly like
  `TrailDetailScreen`, so `lib/shortcut_scopes.py` needs no manifest edit.

### Post-phase (risk mitigations)

1. **[self_supplying_live_artifact]** The live-terminal check needs a *valid* trail,
   and both stored handles are currently invalid — reproduced during verification:

   ```
   $ ./.aitask-scripts/aitask_trail_gather.sh drift --trail art:trail-shadow-review-loop
   INVALID:$.schema_version|const|expected '1.1.0', got '1.0.0'
   ERROR:invalid_trail:1
   ```

   That is **t1468_5's landed schema bump**, not a t1505 defect, and t1468_7 owns the
   refresh. Do not block on it and do not record it as a regression. Instead,
   self-supply: `aidocs/implementation_trail_examples/gate_framework.json` is already
   at `1.1.0` and carries a 407-character `recommendation_summary` with **no**
   `rendering_hints` — i.e. it exercises the fallback path *and* the absent-depth-hint
   path. Register a copy as a local artifact and run the live check against that
   handle.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the **last** line
  (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`, on stderr). Piping discards the
  exit status; use `set -o pipefail` or `${PIPESTATUS[0]}`.
- **Resolver unit tests:** `overview` preferred over `recommendation_summary`;
  fallback when `overview` is absent; `""` when both are missing; whitespace-only
  treated as empty at each level.
- **Pilot tests:** pane present in By-Trail; **absent** in `all` and `bytopic`; absent
  in By-Trail when the summary is empty; and present-then-absent across a round trip
  into `all` and back (the single-writer guarantee).
- **Render-level:** the footer's first row is still composited and readable, and
  `#board_container` still starts at y=4, with the pane mounted at a small terminal
  size. This is the assertion the pre-phase pins — a `display`/`visible` check is
  **not** a substitute.
- **Trail switch / reload freshness (A→B) — the test that catches a stale pane.**
  Presence-only assertions ("a pane exists", "`v` opens a modal") pass against a pane
  still showing the previous trail, so they are not sufficient. Build two synthetic
  docs with **distinct** summaries, then exercise *both* doc-rewrite seams:
  - the switch path — `_activate_trail` (`:10309`) from A to B;
  - the reload path — `_on_trail_reload` (`:10372`) delivering B's doc for the active
    handle.

  After each, assert the **composited** pane rows (`_screen_rows`) contain B's text
  **and no longer contain A's**, and that opening the modal shows B's body — also free
  of A's text. Assert the disappearance explicitly; a test that only checks for B's
  presence passes on a pane rendering both.
- **Free-form prose is literal, in BOTH surfaces:** a summary containing
  `[blocked]` / `[risk_mitigation]` renders those brackets verbatim in the pane and
  in the modal (not swallowed as markup), and a summary containing a bracketed URL
  does not raise — the banner still refreshes, proving the exception cannot escape
  into `_refresh_subtitle`.
- **Fallback transition:** A carrying only `recommendation_summary` → B carrying
  `overview`, asserting the pane switches to B's `overview` text (the resolver's
  preference order observed end-to-end, not just in the unit test).
- **Expand key:** `v` opens the modal in By-Trail. **Negative control:** `v` in the
  `all` view does nothing, *and* `action_trail_summary_expand` called directly outside
  By-Trail is a no-op (the action guard, not just the binding gate).
- **Depth label:** rendered when `rendering_hints.depth` is present; **nothing**
  rendered when absent — asserted explicitly. Plus the narrow-width test that the
  depth note sheds before the freshness marker.
- **Live check in a real terminal** (not only `run_test` — `Screen._update_auto_focus`
  and compositing can diverge between the two drivers, per
  `aidocs/framework/tui_conventions.md` "Verify in a real pty"): enter By-Trail on the
  self-supplied handle, confirm the pane renders below the columns with the footer
  fully visible, `v` opens the modal, and leaving the view restores the full column
  height.

**Test-hygiene note (t1487):** any new pilot test must stub the trail worker — use
`_enter_synthetic_bytrail`. A Textual `@work` worker left in flight makes `run_test`
fail the *enclosing* test with a traceback nowhere near its assertions.

**Scope note:** `narrative.overview` (t1505_3) and `rendering_hints.depth` (t1505_4)
do not exist yet. Both new code paths are therefore correct-by-construction today
(fallback / render-nothing) and unit-tested against synthetic docs; their preferred
branches go live when those siblings land. This is intended, not a gap.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared task
workflow.

## Final Implementation Notes

- **Actual work done:** All four planned steps plus both pre-phase and the post-phase
  mitigation landed as designed. `trail_summary_text` (pure resolver) sits in the
  trail-helper block; `#trail_summary` is a flow child yielded between
  `#board_container` and `MultiRowFooter` with `height: 6`; `_refresh_trail_summary()`
  is the single owner of the pane's text + visibility and is driven from
  `_refresh_subtitle`; `v` → `TrailSummaryScreen`, gated in `check_action` and
  re-guarded inside the action. `_trail_depth_note()` + a fourth `_trail_banner`
  parameter implement `label_trail_depth`. 28 tests added across 5 classes.

- **Deviations from plan:** None in approach. Two additions the plan did not
  anticipate, both forced by evidence found while implementing:
  1. `Static(markup=False)` + `body.update(Text(...))` for the pane body (see
     Post-Review Changes below).
  2. The *characterization* test could not be the guard the plan assumed — see the
     next bullet.

- **Issues encountered:**
  - **The pre-phase characterization test did not discriminate, and the negative
    control is what revealed it.** The plan (and the parent task) assumed a docked
    pane would eat the *footer*. It does not: the footer is docked and wins the paint,
    so injecting `dock: bottom` left every footer assertion green while the **pane**
    silently lost its last two rows to the footer (pane `y=14..20` vs footer `y=18`).
    A characterization test written before the pane exists cannot assert on the pane,
    so the real guard had to move into the pane's own suite as
    `test_pane_does_not_overlap_the_footer` (`pane.bottom <= footer.y`, plus a
    render-level check that no footer key label appears on a pane row). That test was
    confirmed red under the injected dock. The three characterization tests were kept
    — they were green pre-change and still pin the footer/board-geometry invariant —
    but they are **not** the docked-sibling guard the plan claimed. Anyone extending
    this should note the general lesson: identify which widget *loses* the collision
    before writing the assertion.
  - `_on_trail_reload` / `_activate_trail` both already funnel into
    `_refresh_subtitle`, so the single-owner hook needed exactly one call site, as
    planned.
  - A round-trip through `ait artifact create` + `ait artifact rm` left a dangling
    empty `artifacts:` key in the task frontmatter (see Upstream defects).
  - One self-inflicted test bug: the "restores full column height" assertion compared
    the `all` view's baseline against the `bytopic` view's chrome. Fixed by returning
    to `all` before asserting.

- **Key decisions:**
  - **Depth is additive-if-it-fits rather than threaded through `_trail_banner`'s shed
    ladder.** Threading it would have made the title shed earlier for every
    hint-carrying trail and left no rung dropping depth alone. As implemented, the
    existing four rungs are byte-identical for hint-less trails — pinned by
    `test_banner_is_unchanged_when_no_hint_is_present`, which compares the live
    subtitle against the ladder called with no depth at six widths.
  - **Pane is `can_focus = False`.** The board anchors startup focus on a `TaskCard`
    (t1491) and every navigation query is `TaskCard:focus`; a focusable container
    would join the tab order. The read-everything path is `v`.
  - **An unrecognised `rendering_hints.depth` renders nothing** rather than being
    echoed — the header is a fixed width budget, not a place for arbitrary artifact
    strings.
  - **The live-check artifact was removed after use** rather than left on the task.
    To recreate: copy `aidocs/implementation_trail_examples/gate_framework.json`, set a
    distinct `trail_id`/`title`, add `rendering_hints: {"depth": "lite"}`, then
    `ait artifact create <task> <file> --kind implementation_trail --handle art:<id>`.
    Note `aitask_trail_gather.sh drift` reports `ERROR:undriftable_input` on that
    document — that is a *drift-input* verdict, not a schema failure;
    `trail_schema.validate_trail` returns no issues.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_artifact.sh` — `ait artifact rm` leaves a dangling empty
    `artifacts:` key in the task's frontmatter after removing the task's only
    artifact, instead of removing the key. Harmless to the board today (every reader
    goes through `meta.get("artifacts") or []`) but it is residue a create/remove
    round trip should not leave, and it makes a task look like it still owns
    artifacts. Observed on `aitasks/t1505/t1505_1_bytrail_summary_pane.md` and cleaned
    up by hand in this task.

- **Notes for sibling tasks:**
  - **t1505_2** edits `TrailDetailScreen._sections()` in the same file. `narrative`
    is read *only* there (now plus `trail_summary_text`); when it surfaces `overview`
    in the modal, reuse `trail_summary_text` rather than re-deriving the
    overview→recommendation_summary preference.
  - **Free-form trail prose must never be rendered as Rich markup.** Textual's
    `Static` defaults to `markup=True`, silently deletes unrecognised tags, and raises
    `MarkupError` on a bracketed URL. Any new surface rendering `narrative` /
    `rationale` / `observations` text needs `markup=False` or `Text(...)`. This bites
    t1505_2 directly — `_sections()` builds a `Text`, so it is safe today, but any new
    `Static(str)` there would not be.
  - **t1505_3** adds `narrative.overview`. `trail_summary_text` already prefers it, so
    no board change is needed when it lands — `test_switch_observes_the_overview_
    preference_end_to_end` already covers the preference end-to-end against a
    synthetic doc.
  - **t1505_4** writes `rendering_hints.depth`. The banner label already consumes it;
    only `"lite"` and `"deep"` are recognised, so the skill must write exactly those.
  - The two stored trail handles return `ERROR:invalid_trail` until t1468_7 refreshes
    them to 1.1.0. Confirmed live during this task (the selector shows both as
    "unreadable"). That is expected and is not a t1505 regression.

## Post-Review Changes

### Change Request 1 (2026-08-13 16:20)

- **Requested by user:** `#trail_summary_body` was constructed as `Static("")`, whose
  default `markup=True` parses every raw string later passed to
  `_refresh_trail_summary`. Free-form trail prose containing `[blocked]` would be
  silently consumed, and a bracketed link would raise `MarkupError` and break the
  pane/banner refresh. `TrailSummaryScreen` already avoided this via `Text(...)`.
  Asked to render the body literally and to pin bracketed text in both surfaces.
- **Verified before fixing (concern CONFIRMED, and slightly worse than reported):**
  `Static.__init__` defaults `markup=True`; through Textual's `Content` parser
  `"[blocked] gate not satisfied"` → `" gate not satisfied"` and
  `"note [risk_mitigation] applies"` → `"note  applies"` (silent content loss, and
  `risk_mitigation` is a live `followup_kind` in this repo), while
  `"see [link=https://x.dev]docs[/link]"` raises
  `MarkupError: Expected markup value`. Because the body is written from
  `_refresh_trail_summary`, which `_refresh_subtitle` drives, that exception escapes
  into the **banner and the whole By-Trail refresh**, not just the pane.
- **Changes made:** constructed the body as
  `Static("", id="trail_summary_body", markup=False)` and changed the write to
  `body.update(Text(text))` — belt-and-braces, so no later caller can reintroduce it.
  Added three tests: literal `[blocked]`/`[risk_mitigation]` in the pane, a bracketed
  URL that must not raise (asserting the banner still refreshed), and the modal's half
  of the same contract. The two pane tests were confirmed **red before the fix** (one
  on content loss, one on the real `MarkupError`); the modal test passed before and
  after, confirming that surface was already safe.
- **Also checked, not a defect:** the banner path renders the trail *title* literally
  — `HeaderTitle` does not parse markup — so no equivalent pre-existing hazard exists
  there and nothing outside the pane needed changing.
- **Files affected:** `.aitask-scripts/board/aitask_board.py`,
  `tests/test_board_bytrail_view.py`.

## Risk

### Code-health risk: medium
- Adds a second flow child to `KanbanApp.compose()`, which has exactly one documented same-edge collision in its history (t1278). A stray `dock:` — or a missing explicit `height`, since `VerticalScroll` inherits `1fr` — silently eats the footer or halves the column area, and both failures are invisible to `display`/`visible` assertions · severity: medium · → mitigation: inline pre-phase characterize_board_compose_layout
- `_trail_banner` (`:8075`) is a width-budget shedder whose entire contract is that the freshness marker survives narrowing; adding a fourth variable risks letting the depth note evict the marker at ordinary terminal widths · severity: medium · → mitigation: inline pre-phase label_trail_depth
- The pane has **two** mutable surfaces (visibility and text), and `self._trail_doc` is rewritten at two seams — `_activate_trail:10309` and `_on_trail_reload:10372`. Refreshing one surface without the other leaves the pane, or the expand modal, showing the *previous* trail's summary — a wrong answer that renders as a normal one, and that presence-only tests cannot see · severity: medium · → mitigation: structural — `_refresh_trail_summary()` resolves once and writes content + visibility + modal source together (step 3), pinned by the A→B switch/reload test
- Blast radius is narrow: one module plus one test file, with no schema, skill-template or goldens surface · severity: low · → mitigation: none needed

### Goal-achievement risk: medium
- The acceptance criterion "the footer is still fully visible" is only truly answerable in a real terminal, and this repo has a *measured* case of `run_test` and the real driver diverging (t1495, `aidocs/framework/tui_conventions.md`). A green headless suite is not evidence · severity: medium · → mitigation: live pty check in the Verification section
- That live check needs a valid trail artifact, and both stored handles return `ERROR:invalid_trail` until t1468_7 refreshes them (reproduced during verification). A fixture-backed board test would pass while the real path stayed unverified · severity: medium · → mitigation: inline post-phase self_supplying_live_artifact
- Both new read paths target fields that do not exist yet (`narrative.overview` → t1505_3, `rendering_hints.depth` → t1505_4), so only the fallback and render-nothing branches are exercisable end-to-end today · severity: low · → mitigation: intended and documented; the preferred branches are unit-tested against synthetic docs and go live when those siblings land

### Planned mitigations
- timing: pre-phase | name: characterize_board_compose_layout | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — silent footer/column collision when the pane is mounted | desc: Before mounting the pane, pin the composited footer row and #board_container geometry at a small terminal size via _screen_rows, confirmed green against the unmodified board first.
- timing: pre-phase | name: label_trail_depth | type: feature | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the _trail_banner shed contract; goal-achievement — a lite trail mistaken for deep | desc: Surface rendering_hints.depth on the By-Trail banner; an absent hint renders nothing, and a narrow-width test pins that the depth note sheds before the freshness marker.
- timing: post-phase | name: self_supplying_live_artifact | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — live acceptance needs a valid artifact t1468_5 invalidated | desc: Register a local 1.1.0 artifact from gate_framework.json and run the live terminal check against that handle, recording that ERROR:invalid_trail on the two stored handles is expected before t1468_7.
