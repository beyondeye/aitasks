---
Task: t1580_minimonitor_own_header_shows_session.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1580 — minimonitor own-agent header names its tmux session

## Context

In `ait minimonitor`, the docked top panel identifying the followed agent renders
only `── this agent ──` (or `── this window ──`). Every *other* agent on screen is
grouped by a `format_session_divider(session_name)` rule, so the followed agent is
the one entry with no repo context — in a multi-repo tmux setup the user can see
which repo each *listed* agent is in, but not their own.

The fix appends the tmux session name to that header line:
`── this agent · aitasks ──`.

**Value source — decided.** The header shows the **tmux session name**
(`own_snap.pane.session_name`, falling back to `self._session`), i.e. literally
the same string `format_session_divider` draws for every other agent, rather
than `basename(project_root)` via `_root_for_snap`.

That choice has one hole: the literal `"aitasks"` is what every unconfigured
repo reports (see `_read_default_session` in
`.aitask-scripts/lib/agent_launch_utils.py`) *and* a name a repo may configure
deliberately, so it identifies no repo. Steps 1–5 ship with the hole; inline
post-phase 2 closes it by substituting the project basename for exactly that
name. The residual — two repos that both configure the same non-default session
name, or two project roots sharing a basename — stays open by design and is
recorded in `## Risk`.

**Shown unconditionally**, not gated on `monitor.multi_session`: the divider only
renders in multi-session mode, so in single-session mode this header is the only
repo signal on screen (the session bar ships hidden since t1566).

**Both states get it** — `this agent` and `this window` alike; the header is
built from one expression, so there is no second path to keep in sync.

## Why the header line, and why it costs no rows

`.mini-own-header` is `height: 1`, and `_OWN_PANEL_MAX_ROWS`
(`minimonitor_app.py:465`) budgets it as exactly 1 row regardless of its text. So
`_OWN_PANEL_MAX_ROWS` / `_MAX_CHROME_ROWS` / the 40x12 pane-list floor are all
unchanged — only the comment naming the header's content needs updating.

`height: 1` is also the hazard: an over-long line is **clipped**, not wrapped, so
the trailing `──` silently vanishes and the rule reads as broken. That is what
the width budget below exists to prevent — and it must hold at *any* width,
because `tmux.minimonitor.width` reaches `_target_width` as a bare
`int(mm_cfg["width"])` with no clamp (`minimonitor_app.py:4206`).

**Scope note, so this does not over-claim:** the budget below makes the *header*
width-safe at every width. The rest of the panel is not — `_own_agent_identity_text`
floors its wrap at `max(8, target_width - 4)` (line 1714), which stops shrinking
below 8 and can still overflow a pane narrower than ~10 columns. That is
pre-existing, belongs to the t1351 row-width audit, and is untouched here.

## Implementation

### 1. `.aitask-scripts/monitor/minimonitor_app.py` — add the formatter

Add `escape` to the imports beside the existing `rich` import at line 90:

```python
from rich.cells import cell_len, set_cell_size  # noqa: E402
from rich.markup import escape  # noqa: E402
```

Add two constants and one pure function in the **row-width budget block**
(after `_clip`, ~line 190), so the arithmetic sits with `_row_budget` /
`_detail_budget` / `_clip` rather than in a second place:

```python
# -- Own-panel header budget --------------------------------------------------
#
# `.mini-own-header` is `padding: 0 1` on a panel with `padding: 0`, so the rule
# gets `target_width - 2` cells — and it is `height: 1`, which CLIPS rather than
# wraps. An over-long header therefore loses its trailing `──` and reads as
# broken, which is why this is a budget and not a format string.
_OWN_HEADER_PADDING = 2       # `.mini-own-header` padding: 0 1
_OWN_HEADER_SEP = " · "
_MIN_SESSION_CELLS = 4        # below this a clipped session name says nothing


def _own_header_text(label: str, session: str, target_width: int) -> str:
    """``── this agent · <session> ──``, sized to ONE row at ``target_width``.

    Returns Textual markup carrying a single ``[dim]`` span over the whole rule
    — deliberately NOT ``format_session_divider``'s cyan, which stays reserved
    for the pane list's repo boundaries. ``test_own_panel_header_stays_dim`` in
    ``tests/test_monitor_session_divider.py`` is the negative control that says
    so.

    Budgeted in **cells** off ``target_width``, never off the literal 40:
    ``tmux.minimonitor.width`` is read as ``int(mm_cfg["width"])`` with no
    clamp (line 4206), so this must hold at ANY width, not merely at plausible
    ones.

    A three-rung shedding ladder, decoration first — the same shape
    ``format_gate_phase_row`` uses when its row will not fit:

        1. ``── <label> · <session> ──``  full form
        2. ``── <label> ──``              session segment dropped whole
        3. ``<label>``                    rule glyphs dropped, label clipped

    Rung 2 alone is not enough: ``── this window ──`` is 17 cells, so any width
    below 19 would still overflow, and ``.mini-own-header`` is ``height: 1``,
    which CLIPS rather than wraps — the trailing ``──`` would vanish and the
    rule would read as broken, which is the exact failure this function exists
    to prevent. **Post-condition, on every rung:** the rendered plain text is
    ``<= max(0, target_width - 2)`` cells.

    The session name is tmux-side user input, so it is escaped: an unescaped
    ``[/]`` would close the ``[dim]`` span early and an unescaped ``[dim]``
    would be eaten outright. Escaped AFTER truncation, so the backslashes never
    count against the budget (they vanish again in the rendered plain text).
    ``label`` is framework-controlled — deliberately NOT escaped, per the same
    rule the post-phase applies to ``format_section_header``.
    """
    usable = max(0, target_width - _OWN_HEADER_PADDING)
    bare = f"── {label} ──"
    room = usable - cell_len(bare) - cell_len(_OWN_HEADER_SEP)
    if session and room >= _MIN_SESSION_CELLS:
        body = f"── {label}{_OWN_HEADER_SEP}{escape(_clip(session, room))} ──"
    elif cell_len(bare) <= usable:
        body = bare
    else:
        body = _clip(label, usable)
    return f"[dim]{body}[/]"
```

`_clip` (line 174) is reused rather than reimplemented — it is already the
module's cell-aware terminator and already guarantees `<= budget` cells for
degenerate budgets (including 0 and 1, so rung 3 needs no extra floor).
`_MIN_SESSION_CELLS` mirrors the existing `_MIN_PHASE_CELLS` (line 143), same
value and same rationale.

### 2. `minimonitor_app.py` — call it from `_maybe_build_own_agent_panel`

At line ~1870, alongside the existing `label` resolution:

```python
        label = "this agent" if is_agent else "this window"
        # The repo signal for the followed agent, mirroring the pane list's
        # `format_session_divider` rows (t1580). Shown unconditionally, not
        # gated on multi_session: the divider is multi-session-only, so in
        # single-session mode this is the only repo signal on screen.
        session = own_snap.pane.session_name or getattr(self, "_session", "") or ""
```

and at line 1882 replace the mounted header:

```python
            Static(_own_header_text(label, session, self._target_width),
                   classes="mini-own-header"),
```

Nothing else in the method changes; the panel stays one-shot.

### 3. `minimonitor_app.py` — refresh the row-budget comment (line 466)

`_OWN_PANEL_MAX_ROWS`'s first term currently reads
`1 # "── this agent ──" header (.mini-own-header, height: 1)`. Update it so the
constant does not become a stale second description of the header:

```python
    1      # "── this agent · <session> ──" header — `.mini-own-header` is
           # `height: 1`, so the session name costs no row; _own_header_text
           # budgets it to fit at every target_width instead (t1580)
```

### 4. `tests/test_minimonitor_own_header_session.py` — new module

Pure-function tests on `_own_header_text` (no App boot), pinning the rendered
content and the truncation boundary:

- full fit at 40 columns → `── this agent · probe-session ──`, and the
  `this window` variant likewise;
- **boundary, both sides**: the longest session that fits whole is asserted to
  survive unchanged, and that name plus one character is asserted to come back
  ellipsized — pinned as a *computed* boundary
  (`40 - 2 - cell_len("── this agent ──") - 3`) so the constant and the
  assertion cannot drift apart;
- **the post-condition, as a property sweep**: for every width in
  `range(1, 61)`, both labels, and session names of length 0 / 8 / 200,
  `cell_len(rich.markup.render(result).plain) <= max(0, width - 2)`. Measured on
  the *rendered plain text*, not the markup string, so the escape backslashes
  are not miscounted. This sweep is what catches a shedding rung that overflows
  — a fixed `(40, 30, 26, 22)` list cannot, because both sub-rule thresholds
  sit below 22;
- **both rung thresholds pinned explicitly**, since the two labels differ:
  `this agent` (bare rule = 16 cells) keeps `── this agent ──` at width 18 and
  sheds to a bare `this agent` at 17; `this window` (17 cells) keeps its rule at
  19 and sheds at 18. At and above the threshold the result is asserted to end
  in `──`; below it, asserted **not** to contain `──` at all — a half-rule is
  the failure mode, so "no rule" must be distinguished from "clipped rule";
- degradation of the session segment: at 22 columns (`room == 1`) it is dropped
  and the result is asserted **equal to** the bare `── this agent ──`. Equality,
  not a "fits" check — at that width a `· …` stub would also fit, so only
  equality distinguishes "dropped" from "truncated to nothing". Pin the first
  width at which the segment reappears (25, where `room == 4`) alongside it;
- empty session → bare label;
- a session named `[dim]x[/]` renders as literal text: assert it round-trips
  through `Static(...).render().plain` with the brackets intact and exactly one
  `dim` span (the unescaped version raises `MarkupError` or eats the rule);
- a CJK session name is truncated on **cells**, not code points.

Plus two widget-level cases driving the real `_maybe_build_own_agent_panel`
through the same `__new__`-stub pattern the sibling modules use, asserting the
session reaches the mounted header in both the `this agent` and `this window`
states.

### 5. `tests/test_minimonitor_top_chrome_render.py` — one live-render case

Add to `OwnPanelSizingTests`, reusing `_ChromeFixture` (whose `_app` already
passes `target_width=size[0]`, and whose fixture session is `probe-session`):

```python
def test_own_header_names_the_session_without_clipping_at_any_width(self):
```

For each of `(40, 30, 26, 22, 19, 18, 12)` read the composited row at
`regions["#mini-own-agent"].y` and assert:

- at 40, `probe-session` is on that row;
- at every width **at or above** the label's rule threshold (19 for
  `this window`, 18 for `this agent`), the row `rstrip()`-ends with `──` — the
  direct observation that the rule is not clipped;
- at every width **below** it (18/12 and 17/12 respectively), the row contains
  no `──` at all and still carries the label text — proving the third rung sheds
  the glyphs rather than leaving half a rule on screen.

The widths below 22 are the point: they are where the pure-function sweep says
the rungs change, and this is the only place the CSS padding, the configured
width and the formatter's budget are proven to agree on real composited output.
Run it for both labels (the fixture's `window=` argument selects the category
via `_own_snapshot`, so the `this window` case needs an `OTHER`-category
snapshot).

### Post-phase (risk mitigations)

Both confirmed mitigations are inline post-phases: they run **after** steps 1–5
above are implemented and green, so the main change is never blocked on them and
each can be reverted independently.

1. `[escape_session_divider_label]` — **`.aitask-scripts/monitor/monitor_shared.py`**:
   wrap the label in `format_session_divider` (line 250) with the `escape`
   already imported at line 55:
   ```python
   return f"[{SESSION_DIVIDER_STYLE}]── {escape(label)} ──[/]"
   ```
   The label is a tmux session name — user-controlled — so an unescaped `[/]`
   raises `MarkupError` and takes the pane list down, exactly as the comment at
   `monitor_shared.py:2117` already records for the board-column row. Add a
   docstring line stating that. **Do not** escape `format_section_header`: its
   only caller passes `f"other ({len(others)})"`
   (`minimonitor_app.py:1966`), which is framework-generated — note that in its
   docstring so the asymmetry is deliberate and recorded rather than an
   oversight.
   Test in `tests/test_monitor_session_divider.py`: a session named `[dim]x[/]`
   renders literally in the divider row, asserted through `render().plain` for
   **both** TUIs (the module already covers minimonitor and the full monitor).
   *Negative control:* revert the `escape(...)` and that test must fail.

2. `[own_header_disambiguates_generic_session]` — close the accepted
   goal-achievement gap: the session name stays the primary value, but when it
   is the **ambiguous** literal `aitasks` it identifies no repo and the project
   basename is substituted.

   **Decided rule: substitute for every literal `aitasks`, regardless of
   provenance.** Runtime carries none — `snap.pane.session_name` is just a tmux
   name, and `_read_default_session` returns `"aitasks"` both when the field is
   absent and when a repo sets `default_session: aitasks` explicitly (which
   `seed/project_config.yaml:316` documents as an example, so it is a real
   configuration, not a corner case). *Rejected alternative:* read the owning
   project's `tmux.default_session` to honour an explicit choice. It costs a
   config read per panel build to preserve a label that is **still** ambiguous —
   an explicitly-chosen `aitasks` collides with every unconfigured repo exactly
   as the implicit one does. Distinguishing the two would buy a worse label at a
   higher cost, so the predicate is "this name cannot identify a repo", not
   "this repo is unconfigured".

   a. **`.aitask-scripts/lib/agent_launch_utils.py`**: promote the literal to a
      named constant and use it at both existing return sites in
      `_read_default_session` (lines 663 and 692) — no behavior change, one
      canonical spelling:
      ```python
      #: Session name every unconfigured repo falls back to, so it is NOT
      #: unique across repos — see `AitasksSession.key`.
      DEFAULT_TMUX_SESSION = "aitasks"
      ```
      Cross-reference it from the `AitasksSession.key` docstring (line ~152),
      which already explains the collision using the bare literal.
      Known second spelling, left alone: `applink/server.py:39` defines its own
      `DEFAULT_SESSION = "aitasks"`. Out of this task's blast radius (separate
      subsystem, own tests) — add a one-line comment there pointing at the
      canonical constant, no behavior change.

   b. **`minimonitor_app.py`**: import `DEFAULT_TMUX_SESSION` from
      `agent_launch_utils` (the existing import block at line 76), and add class
      floors beside `_target_width` (line 527) so the `__new__`-built stubs the
      five sibling test modules use can reach `_root_for_snap`:
      ```python
      # CLASS attributes for the same reason as `_target_width` above: several
      # test modules build the app with `MiniMonitorApp.__new__(...)` and
      # hand-set only what they touch. `__init__` still sets the real values —
      # these are only the floor under them (t1580).
      _monitor: "TmuxMonitor | None" = None
      _project_root: Path | None = None
      ```
      `_root_for_snap`'s `-> Path` annotation is **left as-is**: it has four
      production callers (lines 2262, 2341, 2709, 2751) that all run after
      `__init__` and genuinely cannot take a `None`, so widening it would push a
      null-check onto all four to serve a test-construction floor. The one
      caller that tolerates the stub's `None` is the new resolver, whose
      fail-soft contract covers it explicitly.

   c. **`minimonitor_app.py`**: name the predicate rather than inlining the
      comparison, so the rule above lives in the code and not only in this plan:
      ```python
      def _session_is_ambiguous(session: str) -> bool:
          """True when a tmux session name cannot identify a repo.

          `DEFAULT_TMUX_SESSION` is what every unconfigured repo reports AND a
          name a repo may configure deliberately (`seed/project_config.yaml`
          documents it as an example). Runtime carries no provenance to tell
          those apart — and does not need to: the name collides across repos
          either way, so it is never a repo signal. Naming the predicate for
          what it tests, rather than writing `== DEFAULT_TMUX_SESSION` inline,
          is what keeps this from reading as an unconfigured-repo check.
          """
          return session == DEFAULT_TMUX_SESSION
      ```

   d. **`minimonitor_app.py`**: replace the inline `session = ...` expression
      from step 2 with a method, and call it from
      `_maybe_build_own_agent_panel`:
      ```python
      def _own_header_session(self, snap) -> str:
          """Repo label for the own-panel header: the tmux session name, with
          the project basename substituted when that name is ambiguous.

          The session name is what the pane list's dividers show, so it is the
          primary — the followed agent should read like a list entry (t1580).
          When `_session_is_ambiguous`, `basename(project_root)` is the value
          that distinguishes (see `AitasksSession.key`). Substituted rather
          than appended: this row has one line, and
          `── this agent · aitasks (aitasks_mobile) ──` does not fit a
          40-column pane.

          Fails soft, like `_own_phase_text`: any resolution problem yields the
          session name unchanged rather than a wrong or empty label.
          """
          session = snap.pane.session_name or getattr(self, "_session", "") or ""
          if not _session_is_ambiguous(session):
              return session
          root = self._root_for_snap(snap)
          return root.name if root is not None and root.name else session
      ```
      Reuses `_root_for_snap` — the module's existing session→project seam
      (`monitor.get_session_to_project_mapping()`) — rather than re-deriving the
      mapping, which matters because in multi-session mode the followed pane may
      belong to a different project than `self._project_root`.

   e. Tests in `tests/test_minimonitor_own_header_session.py`:
      - a session name **other than** `aitasks` passes through untouched, and
        the session→project mapping is asserted **never consulted** for it (spy
        on `get_session_to_project_mapping`);
      - a session equal to `DEFAULT_TMUX_SESSION` renders the project basename;
      - **the decided rule, pinned as its own case**: a repo whose
        `project_config.yaml` explicitly sets `default_session: aitasks` is
        substituted *too*. This is the behavior the alternative rule would have
        changed, so it is asserted deliberately rather than left as an untested
        corollary of the case above;
      - a pane whose session maps to a *different* root than
        `self._project_root` renders that root's basename, not the local one;
      - each fail-soft path (no `_monitor`, session absent from the mapping,
        root with an empty name) falls back to the session name rather than
        raising or emptying the label;
      - the substituted value flows through the same `_own_header_text` budget:
        one case pinning that a long project basename truncates identically.

      *Negative control:* drop the `not _session_is_ambiguous(...)` early return
      and the "other than `aitasks` passes through untouched" case must fail.

## Verification

```bash
python3 tests/test_minimonitor_own_header_session.py     # new
python3 tests/test_monitor_session_divider.py            # dim negative control
                                                         # + escaped divider
python3 tests/test_minimonitor_other_section.py          # this agent/this window
python3 tests/test_minimonitor_top_chrome_render.py      # chrome budget + new case
python3 tests/test_minimonitor_own_mark.py               # panel build stub
python3 tests/test_minimonitor_scroll_preservation.py    # panel build stub
```

The post-phases reach beyond minimonitor, so also run the surfaces they touch:

```bash
bash tests/run_all_python_tests.sh --test-dir tests      # full python suite
```


**Negative controls (run manually, each must FAIL the named test).** Each names
the *specific* assertion it trips, because these guards protect different things
and a mutation that overflows is not the same as one that degrades badly:

1. Drop the `room >= _MIN_SESSION_CELLS` conjunct → the **width-22
   "session segment dropped, bare rule intact"** case must fail. It renders
   `── this agent · … ──` instead — which is 20 cells and therefore *fits*, so
   this mutation is invisible to the width sweep. Legibility is what
   `_MIN_SESSION_CELLS` buys, and only an equality assertion against the bare
   label can see it.
2. Delete the `elif cell_len(bare) <= usable` rung, so rung 1's failure falls
   straight through to `bare` → the **width-18 `this window`** case must fail
   (17 cells into 16, rule clipped), and the property sweep must fail with it.
   This is the mutation that reintroduces the reported defect.
3. Drop `escape(...)` → the `[dim]x[/]` case must fail (`MarkupError` or a
   swallowed rule).
4. Swap `cell_len`/`_clip` for `len`/slicing → the CJK case must fail.
5. Drop the `not _session_is_ambiguous(...)` early return → the post-phase
   "session other than `aitasks` passes through untouched" case must fail.

**Live check** (the AC is a rendered surface): run `ait minimonitor` in a tmux
window and confirm the docked header reads `── this agent · <session> ──`; resize
the companion pane narrow and confirm the name truncates with `…` and then
disappears, with `── this agent ──` staying intact throughout.

Step 9 (Post-Implementation) handles cleanup, archival and merge as usual.

## Risk

Levels below are the **re-assessment against the augmented plan** (both
mitigations inlined), not the pre-inline ones. Inlining moved code-health
`low → medium` (blast radius grew from one file to three, and a shared two-TUI
seam now changes) and goal-achievement `medium → low` (post-phase 2 closes the
coverage gap that drove it).

### Code-health risk: medium
- `format_session_divider` (`monitor/monitor_shared.py:250`) interpolates the
  same session name into markup **unescaped**, in both TUIs. Steps 1–5 escape
  the own header but leave the sibling rule as-is, so the two would differ in a
  way nothing records · severity: low · → mitigation: inline post-phase
  escape_session_divider_label
- The header becomes width-safe at every width while its neighbouring rows in
  the same panel are not (`_own_agent_identity_text` floors its wrap at
  `max(8, target_width - 4)`, line 1714). Pre-existing and owned by the t1351
  row-width audit, but this plan makes the inconsistency sharper by fixing one
  row and not the other · severity: low · → mitigation: none (out of scope;
  named in the plan's Scope note so it is not mistaken for an oversight)
- Inlining both mitigations widens the change from one file to three —
  `minimonitor_app.py`, `monitor_shared.py` (a seam **both** TUIs' pane lists
  render through) and `agent_launch_utils.py` (a broadly imported lib). Each
  edit is small and behavior-preserving for ordinary inputs, and existing
  divider tests cover the shared seam, but a regression here is no longer
  contained to the minimonitor · severity: medium · → mitigation: post-phases
  are ordered last and are independently revertible; the full python suite is
  in Verification for exactly this

### Goal-achievement risk: low
- The chosen value source does not distinguish unconfigured repos: they all
  report the tmux session `"aitasks"`, so the header would not answer "which
  repo is my own agent in" — the stated problem — for those users · severity:
  medium · → mitigation: inline post-phase own_header_disambiguates_generic_session
- Residual after that mitigation: two *configured* repos can still choose the
  same `tmux.default_session`, and two project roots can share a basename. The
  header is then ambiguous again. Not addressed — `AitasksSession.key` already
  documents `project_root` as the only truly unique identity, and a path is too
  wide for a 40-column rule · severity: low · → mitigation: none (accepted)

### Planned mitigations
- timing: post-phase | name: escape_session_divider_label | type: bug | priority: medium | effort: low | inline_risk: low | added_complexity: high | addresses: code-health — unescaped session name in the shared divider seam | desc: escape the label in format_session_divider so a `[/]`-bearing tmux session name cannot raise MarkupError in either TUI's pane list
- timing: post-phase | name: own_header_disambiguates_generic_session | type: enhancement | priority: medium | effort: low | inline_risk: high | added_complexity: high | addresses: goal-achievement — the generic "aitasks" session identifies no repo | desc: substitute basename(project_root) for the session name in the own-panel header whenever the session name is the ambiguous literal "aitasks" (implicit fallback or explicit config alike), via the existing _root_for_snap seam

## Post-Review Changes

### Change Request 1 (2026-08-24 10:32)

- **Requested by user:** A Step-8 review finding, verified CONFIRMED. During
  implementation I added a `DefaultSessionConstantTests` case that imported
  `.aitask-scripts/applink/server.py` from
  `tests/test_minimonitor_own_header_session.py` and pinned applink's
  independent `DEFAULT_SESSION` equal to the launcher's `DEFAULT_TMUX_SESSION`.
  The approved plan (post-phase 2a) deliberately kept applink out of scope
  **except for a comment**. The guard exceeded that scope and, worse, would have
  *created* a cross-subsystem contract — turning an independent listener default
  into a shared one — as a side effect of a minimonitor header test, rather than
  recording a decision to have such a contract. Remedy offered: move the guard to
  an applink/launcher-focused module if the contract is intended, or retain the
  planned comment-only change. Disposition: follow-up.

- **Changes made:**
  1. Deleted `test_applink_keeps_the_same_value` and the
     `.aitask-scripts/applink` `sys.path` insertion from
     `tests/test_minimonitor_own_header_session.py`. The module no longer
     imports applink at all — it survives only as a docstring reference.
  2. **Kept** the sibling `test_read_default_session_returns_the_constant`. The
     finding was specifically about the cross-subsystem import; this case is
     entirely inside `agent_launch_utils`, pins that `_read_default_session`
     *derives* both returns from the constant rather than restating the literal,
     and is what stops the substitution rule from keying off a value the resolver
     no longer returns. Its class docstring now states why applink is
     deliberately excluded.
  3. Rewrote the `.aitask-scripts/applink/server.py:39` comment. It had been
     edited mid-implementation to claim the equality was test-enforced; it now
     says plainly that **nothing enforces it** and names the follow-up. A comment
     asserting an enforcement that does not exist is worse than no comment.
  4. Created **t1583** (`chore`, `followup-kind: review_finding`,
     `followup-of: 1580`) to answer the actual open question — are these one
     contract or two independent defaults? — before any guard is written. Its
     acceptance criteria require the decision to be recorded either way, and
     require any guard to live in an applink- or launcher-focused module.

- **Not changed:** the substance of post-phase 2a (the `DEFAULT_TMUX_SESSION`
  constant and the two rerouted `_read_default_session` returns) is untouched —
  it was in scope and approved.

- **Re-verified after the change:** `test_minimonitor_own_header_session.py`
  27 passed (was 28; one case removed).

## Final Implementation Notes

- **Actual work done:** Implemented as planned, in the planned order (steps 1–5
  landed and were green before either post-phase began).
  - `minimonitor_app.py`: `_own_header_text()` — a pure, module-level formatter
    beside `_row_budget` / `_detail_budget` / `_clip`, with `_OWN_HEADER_PADDING`
    / `_OWN_HEADER_SEP` / `_MIN_SESSION_CELLS`. Reuses the existing `_clip` for
    cell-aware truncation rather than reimplementing one. Call site in
    `_maybe_build_own_agent_panel`; `_OWN_PANEL_MAX_ROWS`'s first term re-worded
    so it does not become a stale description of the header.
  - Post-phase 1: `escape()` on `format_session_divider`'s label
    (`monitor_shared.py`), with the deliberate non-escaping of
    `format_section_header` documented on both functions.
  - Post-phase 2: `DEFAULT_TMUX_SESSION` in `agent_launch_utils.py` (both
    `_read_default_session` returns rerouted through it, `AitasksSession.key`
    cross-referenced); `_session_is_ambiguous()` + `_own_header_session()` in
    `minimonitor_app.py`; `_monitor` / `_project_root` class floors.
  - Tests: new `tests/test_minimonitor_own_header_session.py` (27 cases), +5 in
    `tests/test_monitor_session_divider.py`, +1 live composited case in
    `tests/test_minimonitor_top_chrome_render.py`.

- **Deviations from plan:**
  1. **The live-render sweep floors at 15, not 12.** The plan specified
     `(40, 30, 26, 22, 19, 18, 12)`. Measured: below width 15 this app's whole
     layout degenerates — `#mini-own-agent` is allotted fewer columns than the
     screen and the bottom-docked `#mini-key-hints` paints over row 0, so the
     frame at `region.y` carries hint text (`' tch'`, `' tab:agent'`) and can
     testify about no widget at all. Pre-existing and unrelated to this change.
     The sweep is now `(40, 30, 26, 22, 19, 18, 17, 15)`, which still straddles
     both rule thresholds live; widths 1–14 are covered where they *can* be
     answered, by the pure-formatter sweep. The floor and its reason are
     documented in the test docstring so it does not read as cherry-picking.
  2. **Threaded `own_category` through the chrome fixture.** `_own_snapshot`
     hardcoded `PaneCategory.AGENT`, so the `this window` label was unreachable
     from `_run`. Added an optional parameter to `_own_snapshot` / `_populate` /
     `_run`, all defaulting to the previous value — every pre-existing case is
     unchanged.
  3. **Added, then removed on review, an applink drift guard.** See Post-Review
     Changes → Change Request 1. Net effect on the plan: post-phase 2a's applink
     item is comment-only exactly as planned, and t1583 carries the open
     question.

- **Issues encountered:**
  - **A negative control in the approved plan was wrong, and re-reading caught
    it.** NC1 claimed that deleting the `_MIN_SESSION_CELLS` guard would fail the
    width-22 case by clipping. It would not: with the guard gone, width 22
    renders `── this agent · … ──` at exactly 20 cells, which *fits*. The
    mutation is invisible to any width assertion. The control now targets what
    the constant actually buys — legibility — via an equality assertion against
    the bare rule, and the controls are split by which guard each one trips.
  - The widget-level fixture initially built no panel:
    `_find_own_window_snapshot` matches `session_name in ("", self._session)`, so
    the snapshot's session and the app's are not independent. `app_session` is
    now an explicit parameter with a docstring saying why.
  - `main` advanced mid-session: the uncommitted `plan-externalization` work
    present at session start was landed by another session as t1578. Verified
    committed (not lost) before staging; disjoint from these files.

- **Key decisions:**
  - **Value source = tmux session name** (user-selected at planning), so the
    followed agent reads like a pane-list entry. Its hole — the ambiguous
    `aitasks` — is closed by post-phase 2 rather than by changing the source.
  - **The ambiguity predicate is "this name cannot identify a repo", NOT "this
    repo is unconfigured."** Runtime carries no provenance: `_read_default_session`
    returns `"aitasks"` both when the field is absent and when a repo sets
    `default_session: aitasks` deliberately (`seed/project_config.yaml:316`
    documents exactly that). Reading the owning config to honour an explicit
    choice was considered and rejected — it costs a config read per panel build
    to preserve a label that still collides with every unconfigured repo. The
    explicit-config case is pinned as its own test so the decision is not an
    untested corollary.
  - **Three-rung shedding ladder, not two.** Dropping only the session segment
    still overflows below width 19 for `this window`. Rung 3 drops the rule
    glyphs and keeps the label.
  - **`_root_for_snap`'s `-> Path` annotation was NOT widened** to `Path | None`.
    It has four production callers that all run after `__init__` and genuinely
    cannot take a None; widening it would push a null-check onto all four to
    serve a test-construction floor. `_own_header_session` is the single caller
    that tolerates the stub's None, under an explicit fail-soft contract.
  - **Escape after truncation**, so the backslashes are never charged to the
    cell budget; and measure budgets on rendered plain text, never on markup.

- **Upstream defects identified:**
  - `.aitask-scripts/monitor/minimonitor_app.py:1714 — _own_agent_identity_text` floors its wrap at `max(8, target_width - 4)`, which stops shrinking below 8 and overflows the row on a pane narrower than ~10 columns. Pre-existing; belongs to the t1351 row-width audit. Named in the plan's Scope note so that fixing the header and not its neighbour reads as a decision.
  - `.aitask-scripts/monitor/minimonitor_app.py:4206 — target_width` is read as a bare `int(mm_cfg["width"])` with no clamp or validation, so `tmux.minimonitor.width: 3` reaches the layout intact. The header now degrades safely at any width, but the rest of the panel does not, and widths below 15 break the app's layout outright (see Deviations 1).
