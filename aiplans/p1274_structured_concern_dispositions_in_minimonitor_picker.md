---
Task: t1274_structured_concern_dispositions_in_minimonitor_picker.md
Worktree: (none — current-branch mode)
Branch: (none — current-branch mode)
Base branch: main
Output branch: main
---

# t1274 — Structured concern dispositions in the minimonitor picker

## Context

The shadow agent's implementation review classifies every finding with a
**disposition** — `blocking`, `follow-up`, or `informational`. Today that
classification reaches minimonitor's concern picker only as free prose at the
tail of the concern *body*:

```
- [medium | accepted risk] Automated verification still does not execute a real
  Step-9 merge ... Disposition: informational. Verified: CONFIRMED.
```

`impl-challenge.md:345-350` documents the consequence as an accepted "UX
boundary": *"an `informational` item looks like any other row in the picker,
distinguished only by its body text."* A finding the shadow is explicitly **not**
asking the user to act on sits in the same flat list as one that must be
addressed.

The user separately reported that picker rows are frequently shown **without a
title**. That is now root-caused (below) and is a *layout* bug, not a parser bug.

**Design decisions already taken with the user:**
- Disposition is **derived from the existing body prose**, not added as a new
  marker field. The marker bracket is already the documented t1167 failure
  surface (an item is *dropped* when `[priority | region]` hard-wraps beyond a
  3-row recovery envelope); widening it would make that worse. Deriving also
  means every block the shadow emits **today**, and every already-captured
  block, works without a producer change.
- The picker **partitions** into "Needs addressing" / "Informational" sections,
  informational rows dimmed and excluded from select-all.

---

## Root cause of the untitled rows (measured, not hypothesised)

Driving the real `ConcernPickerModal` in a 40×24 viewport — the minimonitor
companion-pane width — the laid-out `_ConcernRow` gets **28 usable columns**
(40 → dialog `width: 90%`/`min-width: 30` → `padding: 1 2` → row `padding: 0 1`).
The row is `height: 1` and renders one string, `☐  BADGE region  body`. Rich's
fold at that width does not gracefully truncate the tail — it drops the
overflowing segment **whole**:

| region | rendered row at 40 cols |
|---|---|
| `accepted risk` (13) | `☐  MED accepted risk  Second` |
| `render-test.sh:305` (18) | `☐  HIGH render-test.sh:305` — body gone |
| `authoring-conv.md:103` (21) | `☐  HIGH` — **title and body both gone** |
| `aiplans/archived/…:565` (53) | `☐  HIGH` — **title and body both gone** |

So any region beyond ~19 characters renders as a bare priority badge. Both
21-char and 53-char examples above are **real regions captured from live shadow
panes**, and 21 chars is fully compliant with the producer's ≤30-char rule. That
is the "shown without a title" report, it explains "it happens many times", and
it is not fixable by tightening the producers.

**Fix: a two-line row in the narrow variant** — line 1 `☐ BADGE region`, line 2
the indented body. Prototyped against the real modal at 40×24; all four regions
above then render with both title and body visible.

---

## Part 1 — Derive the disposition and partition the picker

### 1.1 `.aitask-scripts/monitor/concern_parser.py`

**Extend `Concern` (`:116-119`)** with two derived fields, both defaulted so
existing positional construction (`Concern("high", "region", "body")`, used
throughout the tests) keeps working:

```python
class Concern(NamedTuple):
    priority: str          # {"high", "medium", "low"}
    region: str            # free-text plan-region / axis label
    body: str              # CANONICAL — exactly what the producer emitted
    disposition: str = ""  # "blocking" | "follow-up" | "informational" | "" (unspecified)
    verdict: str = ""      # "CONFIRMED" | "PLAUSIBLE" | "REFUTED" | "" (absent)

    def display_body(self) -> str:
        """`body` minus the terminal trailer span (see below)."""
```

**`body` stays byte-identical to what the producer emitted.** Load-bearing:
`build_clipboard_payload` (`:365-378`) re-renders `- [{priority} | {region}]
{body}`, so stripping the trailer would delete the disposition from what is
forwarded to the followed agent. The trailer is removed **only for display**.
Consequence: `build_clipboard_payload` needs no change, and the two existing
round-trip tests (`test_disposition_verdict_trailer_round_trips`,
`test_informational_disposition_trailer_round_trips`) pass unmodified.

**Anchored terminal-trailer grammar.** The trailer is metadata that terminates
the body, so it is matched only as a terminal run — never anywhere in the prose:

```python
_TRAILER_SENTENCE = r"(?:Disposition:\s*(?:blocking|follow[- ]?up|informational)|Verified:\s*(?:CONFIRMED|PLAUSIBLE|REFUTED))\.?"
_TRAILER_SPAN = re.compile(rf"(?:\s*{_TRAILER_SENTENCE})+\s*$", re.IGNORECASE)
```

- Find the span with `_TRAILER_SPAN.search(body)`; record `span.start()`.
- Classify **only from within that span** (so a body that quotes or discusses
  `Disposition: informational.` mid-prose is not misclassified), and strip
  **exactly** that span for `display_body()` (so real prose is never removed).
- Order-independent: `Disposition: X. Verified: Y.` and the reverse both match.
- Any non-trailer text after the last sentence means there is no terminal
  trailer: nothing is classified and nothing is stripped.
- Absent / unknown → `""`. **Unspecified is not informational** — it sorts into
  "Needs addressing", so the three `plan-*` producers (no disposition concept at
  all) and every older block are unaffected.

Add the classification rule as one module-level helper so the UI never re-derives
it:

```python
def needs_addressing(concern: Concern) -> bool:
    """False only for an explicitly `informational` concern."""
    return concern.disposition != "informational"
```

### 1.2 `.aitask-scripts/monitor/monitor_shared.py`

**`_ConcernRow` (`:527-606`)**
- Accept `narrow: bool = False` and `original_index: int` (see 1.3).
- Narrow variant: `height: 2`; `render()` returns
  `☐ BADGE region` + `\n` + `   body`. Wide variant keeps the current single
  line. The region is capped against the **measured** `self.size.width` (not a
  fixed 24), ellipsized, so it can never crowd out line 1's own content.
- `render()` uses `self._concern.display_body()`, never `.body`.
- Informational rows get a `.informational` class (dim).
- Empty region renders `(no region)` in dim italic rather than the current bare
  `—` (`:576`).

**`ConcernPickerModal` (`:609-689`)**
- `compose()` partitions with `needs_addressing`, preserving input order within
  each partition, and emits a `Static` section header before each **non-empty**
  group ("Needs addressing" / "Informational"). A single-partition block emits
  **no** headers — a plan-review block looks exactly as it does today.
- **Unrecovered-marker banner:** when the block contained marker-looking lines
  the parser could not turn into concerns (see Part 2), show
  `⚠ N line(s) in this block could not be parsed` above the list, in the same
  style as the existing `#concern-stale` banner.
- `action_toggle_all` (`a`) operates only on needs-addressing rows, falling back
  to all rows when that partition is empty. `action_copy_all` (`A`) is untouched
  — it still dismisses with every concern.
- `#concern-context` names the split when both partitions exist
  (`2 to address · 1 informational · select to forward`); `#concern-help` says
  `a` = all actionable.
- Fix the stale docstring at `:612-613` ("Shared by the full monitor and
  minimonitor (both push it)") — only minimonitor pushes it today; t1216_3 is
  the Ready task that adds the monitor side.

### 1.3 Selection order must survive partitioning

Partitioning changes DOM order, and `Concern` is a `NamedTuple` — two identical
concerns compare equal, so recovering the original order by value or membership
is ambiguous (ticking one duplicate could forward both, or reorder them).

Each `_ConcernRow` therefore carries the **`original_index`** it was constructed
with, and `_selected_concerns()` (`:698-700`) returns
`[row.concern for row in sorted(selected_rows, key=lambda r: r.original_index)]`.
Identity is positional, never by value.

### 1.4 `.aitask-scripts/monitor/minimonitor_app.py`

In `_maybe_offer_concerns` (`:1354-1419`), make the auto-offer toast count the
split, e.g. `Shadow raised 2 concerns (+1 informational) — press 'c' to pick`.
The per-block de-dup key stays `build_clipboard_payload(concerns)` (unchanged
payload ⇒ unchanged de-dup behaviour).

---

## Part 2 — A marker-looking line is never lost silently

Beyond the layout root cause, three parser paths degrade silently today:

1. `- [medium] body` (no `|`) does not match `_ITEM` (`:89-91`). The row *does*
   contain `]`, so the split-marker recovery is skipped (`_parse_items` requires
   `"]" not in line`) and the row falls through to continuation handling: it is
   **appended to the previous concern's body**, or **dropped** when it is the
   first item.
2. `- [medium | ] body` parses with `region=""` → a bare dim `—`.
3. A marker split **beyond** the 3-row join envelope, or any other malformed
   bracket (`- [ | region] …`, an unclosed bracket), also falls through to
   continuation handling — silently corrupting the preceding concern's body.

### 2.1 Recover the region-less marker

Tried only after `_ITEM` fails and before the split-marker attempt:

```python
_ITEM_NO_REGION = re.compile(
    r"^\s*-\s+\[\s*(?P<priority>high|medium|low)\s*\]\s*(?P<body>.+)$", re.IGNORECASE)
```

The alternation is **deliberately the closed vocabulary**, not `\w+`. `_ITEM` can
afford `\w+` because the `|` separator already makes the shape unmistakable;
without it a permissive class would let an ordinary wrapped body line
(`- [see below] ...`) start a spurious concern and break the collision-hardening
guarantee the whole format rests on. Result: `region=""`, rendered
`(no region)` — neither dropped nor merged.

### 2.2 Report what still cannot be recovered (in scope, not deferred)

Case 3 stays deliberately unrecoverable — the bounded join envelope is a
documented t1167 decision and widening it is out of scope. What changes is that
it stops being **silent**. A continuation line can never begin `- [` (that is
the collision-hardening invariant), so any line inside the block region matching
`_MARKER_START` that was not consumed as part of a successful item is by
definition an unrecovered marker. Expose it as a new pure function beside the
existing entry points:

```python
def unrecovered_markers(text: str) -> list[str]:
    """Marker-looking lines in the newest block that yielded no concern."""
```

`action_pick_concerns` passes the count to the modal, which shows the banner from
1.2. This satisfies the task's "must degrade visibly" requirement within this
task; the `concern_block_parse_diagnostics` follow-up then adds the deeper
affordance (dumping the raw block for inspection).

### 2.3 Producer-side prevention: region mandatory and non-empty

One clause added to the `region` bullet of all four producers, plus a guard test
modelled exactly on the existing `TestProducerShortRegionRule`
(`tests/test_concern_parser.py:572-645`) — same derived-producer discovery via
the `PRODUCER_MARKER = "load-bearing for minimonitor's parser"` phrase, same
whitespace-flattening predicate, same three tests (set enumeration,
all-producers, negative control on synthetic text).

---

## Part 3 — Documentation

- **`.claude/skills/aitask-shadow/concern-format.md`** (the SSoT): `disposition` /
  `verdict` as **derived** fields with the anchored terminal-trailer grammar;
  body stays canonical so forwarding is lossless; the region-required rule; the
  region-less marker tolerance; `unrecovered_markers` as a fourth entry point in
  the strictness table; the picker's partition behaviour.
- **`impl-challenge.md`**: the `Disposition:` bullet (`:332-337`) currently says
  the trailer is "not a parser field" — it now is (derived, terminal-anchored).
  Rewrite the "UX boundary" paragraph (`:345-350`), which becomes false. **Keep
  the heading `## Also emit the structured concern block` exactly** —
  `tests/test_shadow_disposition_surfaces.py:56` anchors a guard to it, and that
  section must keep enumerating all three dispositions.
- **`plan-challenge.md` / `plan-assumptions.md` / `plan-diagnose-errors.md`**:
  region-required clause only. Do **not** introduce blocking/follow-up wording
  into these files — they have no disposition concept, and the proximity rule in
  `test_shadow_disposition_surfaces.py:80-94` flags a partial enumeration.
- **`aidocs/framework/shadow_agent.md:15`**: one line noting the picker
  partitions by disposition.
- **Website** (current-state prose only): `content/docs/workflows/shadow-agent.md`
  lines 89/91 and `content/docs/tuis/minimonitor/how-to.md:126,130`.

---

## Verification

```bash
python3 -m pytest tests/test_concern_parser.py tests/test_concern_picker_modal.py \
  tests/test_shadow_disposition_surfaces.py tests/test_minimonitor_concern_action.py -v
bash tests/run_all_python_tests.sh
```

**Layout (the root cause) — assert the laid-out viewport, not the string.**
A `render()` string containing the body proves nothing; the failure is that
Rich *drops* it during fold. Tests drive the real modal via
`app.run_test(size=(40, 24))` and read the composited screen
(`app.screen._compositor.render_strips()` → `strip.text`), asserting that for a
53-char region **and** for the real-world 21-char `authoring-conv.md:103`, both
the region prefix and a body substring appear on screen. A negative control
pins the current single-line behaviour as failing that assertion, so the test
is proven to discriminate.

**Parser:** every disposition value/case; `follow up`/`followup` normalization;
verdict extraction; trailer order-independence; **prose-mention-only body → no
classification and no stripping**; **text after the trailer → not a trailer**;
`body` unchanged and `build_clipboard_payload` output byte-identical to today;
`display_body()` strips exactly the trailer span and nothing when absent.

**Part 2:** `- [high] body` parses with `region=""`, is not merged into a
preceding concern, is not dropped as the first item; negative control that
`- [see below] text` stays a continuation; `unrecovered_markers` reports an
over-bound (4-row) split marker, a `- [ | region]` marker and an unclosed
bracket, and reports **nothing** for a well-formed block or ordinary
continuation lines.

**Modal:** section headers appear only when both partitions are non-empty;
informational rows dimmed, skipped by `a`, included by `A`; **duplicate-valued
concerns** — selecting only the second of two equal `Concern`s forwards exactly
one, in its original position; unrecovered-marker banner shown/hidden.

**Live check** (not coverable by tests): open minimonitor on a followed agent
whose shadow produced an implementation review with at least one `informational`
and one non-informational concern, press `c`, confirm the sections, dimming,
`a`-scope, two-line rows with visible titles, and that the pasted payload still
carries the `Disposition:` trailers.

## Risk

### Code-health risk: medium
- Loosening the item grammar with `_ITEM_NO_REGION` weakens the collision-hardening guarantee the whole format rests on (a wrapped body line must never be readable as a new item). Constraining the alternation to the closed `high|medium|low` vocabulary bounds it, but this is the one change that can corrupt an otherwise-correct block · severity: medium · → mitigation: TBD
- The picker modal is a shared widget (`monitor_shared.py`) that t1216_3 is about to consume from the full monitor; partitioning, a two-line narrow row and index-based selection change its compose tree, its geometry and its dismiss ordering while that task is still Ready · severity: medium · → mitigation: TBD
- Adding fields to the `Concern` NamedTuple and a `display_body()` split between "canonical body" and "shown body" introduces an easy-to-misuse distinction — a future caller reaching for `.body` on a display surface (or `display_body()` on the clipboard path) reintroduces the bug silently · severity: low · → mitigation: t1294

### Goal-achievement risk: low
- The untitled-row symptom is now reproduced and the fix verified against the real modal at 40×24, so the main delivery risk is retired. Residual: rows can still lose content at widths narrower than the 40 columns measured, and an over-bound split marker is still not *recovered* — only reported · severity: medium · → mitigation: t1293
- Deriving the disposition from prose depends on the shadow emitting the `Disposition: X.` trailer. Only `impl-challenge.md` mandates it; a review that omits it degrades every finding to "needs addressing" — safe, but with no visible split · severity: low · → mitigation: t1293

### Planned mitigations
- timing: after | name: t1293 (concern_block_parse_diagnostics) | type: enhancement | priority: medium | effort: low | addresses: goal-achievement — unrecovered markers are reported but not recoverable, and narrower widths are unverified | desc: Add a picker affordance to dump/inspect the raw concern block behind the unrecovered-marker banner, and extend the rendered-viewport layout tests below 40 columns
- timing: after | name: t1294 (concern_body_display_contract_guard) | type: test | priority: medium | effort: low | addresses: code-health — canonical body vs display body is easy to misuse | desc: Guard test pinning which surfaces read Concern.body (clipboard/forward payload) versus display_body() (row rendering), so the trailer cannot be silently stripped from a forward or left in a rendered row

## Post-Review Changes

### Change Request 1 (2026-07-28 09:05) — commit deferred behind t1216_1

- **Requested by user:** implementation is complete and green, but t1216_1
  (`shared shadow seam`, status `Implementing`) has **uncommitted** work in the
  same files. Let t1216_1 finish and commit first, then resume t1274, reconcile
  the shared files, rerun the tests, and commit t1274 as one coherent change.
- **Changes made:** none to the implementation. Nothing was committed. The full
  working-tree change for t1274 is backed up as a patch at
  `~/.aitask/t1274_wip.patch` (a concurrent session's `git stash` in the shared
  checkout would otherwise be able to wipe it).
- **Files entangled with t1216_1** — reconcile these on resume:
  - `.aitask-scripts/monitor/concern_parser.py` — theirs: `import hashlib`, the
    `ansi_utils` import shim, `_SENTINEL_SAFE_COLS`, `concern_block_signature`.
    **Shared hunk:** the module-docstring strictness table — they converted the
    bullet list to a table, I added the `unrecovered_markers` row to it.
  - `.aitask-scripts/monitor/monitor_shared.py` — theirs: `format_shadow_glyph`.
  - `.aitask-scripts/monitor/minimonitor_app.py` — theirs: the delegating seams
    to `monitor_core` (large deletions). Mine: the `concern_parser` import line,
    `unrecovered=` on the `ConcernPickerModal` push, the auto-offer toast count.
  - `.claude/skills/aitask-shadow/concern-format.md` — **shared hunk:** the
    "Where it lives" parser bullet (their `concern_block_signature` /
    `monitor_core` additions + my `unrecovered_markers` / `needs_addressing`).
  - `aidocs/framework/shadow_agent.md` — theirs: the
    `compute_shadow_staleness` paragraph under "Feedback freshness".
- **Untouched by t1274, purely theirs:** `monitor_core.py`, `tmux_monitor.py`,
  `ansi_utils.py` (untracked), `tests/test_shadow_seam.py` (untracked),
  `.claude/settings.local.json`.
- **On resume:** confirm `git log --format=%s -30 | grep '(t1216_1)'` shows
  their commit, re-run
  `python3 -m unittest tests.test_concern_parser tests.test_concern_picker_modal
  tests.test_minimonitor_concern_action tests.test_minimonitor_concern_smoke
  tests.test_shadow_seam tests.test_shadow_disposition_surfaces`, then commit
  t1274's files only.

### Change Request 2 (2026-07-28 12:20) — malformed-only block was still invisible

- **Requested by user (shadow concern, `[high | minimonitor_app.py:1316]`,
  Disposition: blocking, Verified: CONFIRMED):** a block containing *only*
  malformed markers stays invisible. `parse_concerns()` returns nothing, so
  `action_pick_concerns()` exits via "No concerns detected" **before**
  `unrecovered_markers()` is consulted, and the strict auto-offer
  (`has_concern_block`) is silent for the same reason. Surface an
  unparsed-marker warning before the empty return, and cover both the manual and
  auto-offer paths for a malformed-only complete block.
- **Verified:** valid, and reproduced. Both exits confirmed by reading the code
  and by the two new tests failing against the pre-fix behaviour.
- **Changes made:**
  - `minimonitor_app.py` — new module-level `_unparsed_msg(count)`.
    `action_pick_concerns` now consults `unrecovered_markers(text)` before the
    empty return and warns instead of reporting "no concerns".
    `_maybe_offer_concerns` does the same in its `not has_concern_block(text)`
    branch, after the truncation check, de-duped per shadow pane via a new
    `_unparsed_warned` set that is re-armed (discarded) whenever a parseable
    block arrives — same policy as `_truncation_warned`.
  - `tests/test_minimonitor_concern_action.py` — `_MALFORMED_ONLY_BLOCK`
    fixture, plus: hotkey warns rather than saying "no concerns"; auto-offer
    warns once per pane; the warning re-arms after a good block; a
    **negative control** that a pane with no block never warns. Also tightened
    `test_empty_parse_no_modal` to pin the genuinely-empty message.
  - Test stubs that build the app via `__new__`
    (`test_minimonitor_concern_action.py`, `test_minimonitor_concern_smoke.py`)
    mirror the new `_unparsed_warned` attribute.
  - `concern-format.md` and the minimonitor how-to page document the degenerate
    all-malformed case.
- **Discrimination proven:** with `_unparsed_msg` reverted to the bland string
  the two new tests fail (2); with `unrecovered_markers` stubbed blind, three
  fail. Restored ⇒ 0.

## Final Implementation Notes

- **Actual work done:** as planned, plus one addition from review (Change
  Request 2). `concern_parser.py`: `Concern` gained derived `disposition` /
  `verdict` fields and `display_body()`, plus `needs_addressing()`,
  `DISPOSITIONS`, `_ITEM_NO_REGION`, the `_scan_items` split and the
  `unrecovered_markers()` entry point. `monitor_shared.py`: two-line narrow
  `_ConcernRow` with a measured region cap, `(no region)` placeholder,
  `.informational` dimming, `original_index` selection identity, the
  disposition partition + section headers in `ConcernPickerModal`,
  disposition-scoped `a`, and the unrecovered-marker banner.
  `minimonitor_app.py`: passes the unrecovered count to the modal, counts the
  split in the auto-offer toast, and warns on a block that parsed to nothing.
  Docs: `concern-format.md` (SSoT), the four producers, `impl-challenge.md`'s
  now-false "UX boundary" paragraph, `aidocs/framework/shadow_agent.md`, and two
  website pages.
- **Deviations from plan:** none in approach. The plan's Part 2 assumed the
  untitled rows might not be reproducible; they were, before implementation
  started (see the "Root cause" section), which turned that part from a guess
  into a measured fix and let the goal-achievement risk drop to `low`.
- **Issues encountered:**
  - The planned "assert `render().plain`" approach is not sufficient here. The
    failure mode is that Rich *drops* an overflowing segment during fold, so the
    render string contains the body even when the screen does not. The layout
    tests therefore read the composited screen
    (`app.screen._compositor.render_strips()`), with a negative control pinning
    that the old single-line layout fails the same assertion.
  - `tests/test_minimonitor_concern_smoke.py` pinned the literal auto-offer
    string `"raised concerns"`, which the new count-bearing toast breaks. It now
    matches a shape regex (`OFFER_RE`) instead — the assertion was about the
    offer firing, not its wording.
  - The whole task was implemented in a checkout shared with t1216_1, whose
    uncommitted refactor touched the same five files (two with literally shared
    hunks). Per the user's decision the commit waited for t1216_1 to land
    (`466d6d9c0`); afterwards every remaining hunk was t1274's and the shared
    hunks resolved to pure additions. See Change Request 1.
  - The shared checkout's full suite reports 12 failures in
    `test_board_bytrail_view` / `test_syncer_rows`. These come from other
    sessions' uncommitted `aitask_board.py` / `syncer_app.py` work. Verified
    independently in a clean worktree at HEAD with only this task's patch
    applied: those suites plus all concern suites pass (399 tests, 0 failures).
- **Key decisions:**
  - Disposition is **derived from body prose**, not a new marker field. The
    marker bracket is the documented t1167 drop surface; widening it would make
    the known failure worse, and deriving works on blocks emitted before this
    existed.
  - `Concern.body` stays canonical and `display_body()` is display-only, so the
    forwarded payload is byte-identical and `build_clipboard_payload` needed no
    change. The mirror rule (clipboard uses `body`, rows use `display_body()`)
    is the subject of the `concern_body_display_contract_guard` follow-up.
  - The trailer grammar is **anchored to the end of the body**, so a concern that
    quotes or discusses a disposition mid-prose is neither misclassified nor has
    real prose stripped from its row.
  - `_ITEM_NO_REGION` uses the closed `high|medium|low` vocabulary rather than
    `\w+`: without the `|` separator a permissive class would let a wrapped body
    line start a spurious concern, breaking the collision-hardening invariant.
  - Unrecoverable markers are **reported, not recovered** — widening
    `_MAX_MARKER_JOIN_ROWS` stays the accepted t1167 limit.
  - Selection identity is **positional** (`original_index`), because `Concern` is
    a `NamedTuple` and two equal concerns cannot be told apart by value.
- **Upstream defects identified:** None
- **Test-harness note:** every new guard was proven to fail when its fix is
  patched out in memory (unanchored trailer, disabled region-less recovery,
  blinded `unrecovered_markers`, DOM-ordered selection, value-based selection,
  disposition-blind select-all, single-line narrow row, bland empty message).

## Step 9 (Post-Implementation)

Standard: merge approval into `main`, `./ait gates run 1274` (declares
`risk_evaluated`), then `./.aitask-scripts/aitask_archive.sh 1274`.
