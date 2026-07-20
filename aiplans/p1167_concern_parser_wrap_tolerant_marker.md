---
Task: t1167_concern_parser_wrap_tolerant_marker.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t1167 — Wrap-tolerant concern marker matching

## Context

`.aitask-scripts/monitor/concern_parser.py` extracts the shadow agent's
structured concern block from a captured tmux pane so minimonitor can offer the
concern picker. Its item regex `_ITEM` (line 57) requires the **complete**
`[priority | region]` bracket on a single captured row.

Agent TUIs that render markdown themselves (observed live: Codex CLI at ~55
columns) hard-wrap long rows with **literal newlines**, which `tmux capture-pane
-J` cannot rejoin. When the wrap lands *inside the bracket*, no row matches
`_ITEM` and the whole item is **silently dropped** — `has_concern_block` returns
`False`, the auto-offer never fires, and the user sees "no concerns" instead of
the shadow's review.

Live repro from t1158's own Step 8 review: a 48-char full-path region rendered as

```
- [medium | .claude/skills/aitask-shadow/impl-review-
angles.md:12] The angle list is not…
```

→ `has_concern_block: False`, `parse_concerns: 0`.

t1158 added a producer-side mitigation (short-region rule, ≤ ~30 chars) but that
is a prompt-level instruction and cannot be enforced. The parser must tolerate
the split itself. Body wraps are already handled by the continuation-join
design — **only a wrap inside the bracket is fatal**, so that is the entire scope
of this fix.

**Scope honesty:** this makes the parser wrap-tolerant *within a documented
envelope*, not structurally immune — see "Join bound" below for why that
envelope is the supported one.

## Approach

Bounded wrap-tolerant marker matching inside `_parse_items`, using **lookahead
with commit-on-success** so a failed join consumes nothing and the existing
continuation semantics are untouched.

### 1. `.aitask-scripts/monitor/concern_parser.py`

Add near `_ITEM`:

```python
# A row that *starts* like an item marker. Used only to detect a marker whose
# bracket was split across rows by an agent TUI's own hard-wrap (t1167).
_MARKER_START = re.compile(r"^\s*-\s+\[")

# Max continuation rows joined to close a split bracket (marker spans at most
# _MAX_MARKER_JOIN_ROWS + 1 rows). See "Join bound" in the plan for the
# envelope this covers; over-joining is the only new risk this introduces.
_MAX_MARKER_JOIN_ROWS = 2
```

#### Join bound — why 2

A marker spans at most `_MAX_MARKER_JOIN_ROWS + 1 = 3` rows. At the ~55-column
width where the failure was observed that is ~165 characters of marker, i.e. a
region of roughly **150 chars — ~5× the producer's 30-char rule** and ~3× the
53-char region that actually broke. The observed live failure is a **2-row**
marker, comfortably inside the bound; the task's suggested envelope was 2–3
rows.

So the bound is deliberately *generous*, not tight: it exists only to absorb
producer violations of the short-region rule, while staying tight enough that
over-joining stays implausible. A split wider than 3 rows is still dropped, and
that is the accepted, documented limit — the producer rule remains the primary
defense.

This is pinned by tests rather than left implicit: an **at-bound** marker
(exactly 3 rows) must parse, and an **over-bound** marker (4 rows) must not. If
someone later changes the constant, those two tests force the decision to be
deliberate.

Rewrite `_parse_items`'s loop as an index walk (it currently iterates
`region.splitlines()` directly):

```python
def _parse_items(region: str) -> list[Concern]:
    items: list[list] = []
    lines = region.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _ITEM.match(line)
        consumed = 1
        if m is None and _MARKER_START.match(line) and "]" not in line:
            m, consumed = _join_split_marker(lines, i)
        if m:
            items.append([m.group("priority"), m.group("region"), [m.group("body")]])
        elif line.strip() and items:
            items[-1][2].append(line)
        i += consumed
    ...  # body-join tail unchanged
```

And the helper:

```python
def _join_split_marker(lines: list[str], start: int):
    """Try to close a bracket split across rows by an agent TUI's hard-wrap.

    Returns ``(match, rows_consumed)`` on success, ``(None, 1)`` otherwise —
    on failure nothing is consumed, so the rows fall through to the normal
    continuation handling.
    """
    joined = lines[start]
    for k in range(1, _MAX_MARKER_JOIN_ROWS + 1):
        nxt_idx = start + k
        if nxt_idx >= len(lines):
            break
        nxt = lines[nxt_idx]
        # A real continuation never carries "- [" — that is a new item, so stop
        # rather than swallow it (preserves the collision-hardening guarantee).
        if _MARKER_START.match(nxt):
            break
        joined += _join_sep(joined) + nxt.lstrip()
        if "]" in nxt:
            m = _ITEM.match(joined)
            if m:
                return m, k + 1
            break
    return None, 1
```

#### Join separator — an explicitly best-effort reconstruction

The observed renderer breaks at word *and* intra-token (hyphen) boundaries: an
intra-token break loses nothing, a space break consumes the space. `_join_sep`
returns `""` when the accumulated fragment ends with `-` or `/` (intra-token —
reconstructs a path exactly) and `" "` otherwise.

**This is a heuristic and the contract says so.** A capture cannot distinguish
"the renderer consumed a space here" from "the token continues here", so region
reconstruction is defined as **best-effort on a display label**. The
load-bearing guarantee is only that *the item is no longer dropped*; `priority`
and `body` are unaffected, and `region` is never used as a key — it is rendered
in the picker. The docstring and `concern-format.md` will state this in exactly
those terms, so the heuristic is a documented approximation rather than an
accidental contract.

The rule is optimized for the one failure mode actually observed (paths). Its
known imperfect case is a **prose** region containing a spaced slash, e.g. a
region `foo / bar` broken immediately after the slash, which rejoins as
`foo /bar`. That is accepted, cosmetic, and tested as such — pinning it means a
future reader sees it was a decision, not a bug.

Tests split these apart explicitly:

| Case | Break after | Expected region |
|---|---|---|
| path, intra-token | `impl-review-` | `…/impl-review-angles.md:12` (exact) |
| prose, word boundary | `ownership` | `Step 7 ownership guard` (exact) |
| prose, spaced slash | `foo /` | `foo /bar` (accepted cosmetic loss) |

*(Note on notation: rows of a split marker are shown in this plan as separate
lines inside code blocks, never joined with a `/` — `/` is a meaningful
character in the join rule and must not double as break notation.)*

### 2. `tests/test_concern_parser.py`

Add a `TestSplitMarkerJoin` class:

- **Live-capture fixture** — the real Codex-rendered split above:
  `parse_concerns` yields 1 concern with region
  `.claude/skills/aitask-shadow/impl-review-angles.md:12` reconstructed exactly,
  and `has_concern_block` is `True` (the auto-offer fires).
- **Word-boundary split** — a marker broken after `ownership`:

  ```
  - [high | Step 7 ownership
  guard] The guard double-commits.
  ```

  → region `Step 7 ownership guard`.
- **Prose spaced-slash split** — a marker broken after `foo /` → region
  `foo /bar`. Asserted as the *accepted* best-effort outcome, with a comment
  naming it a documented cosmetic loss (not a latent bug).
- **At-bound marker** — a marker spanning exactly `_MAX_MARKER_JOIN_ROWS + 1`
  (3) rows parses to 1 concern. Pins the bound as intentional.
- **Negative control (over-bound)** — a marker spanning 4 rows yields 0
  concerns and `has_concern_block` is `False`. Together with the at-bound case
  this makes the envelope an asserted contract.
- **Negative control (unclosed)** — a `- [` row with no closing `]` at all
  yields 0 concerns and `has_concern_block` is `False`.
- **Negative control (no-consume)** — an unclosed `- [` row immediately followed
  by a *valid* marker row: the valid item still parses (the failed join
  swallowed nothing).
- **Body-wrap unaffected** — an existing-style multi-row body still round-trips
  (regression guard on the rewritten loop).

### 3. `.claude/skills/aitask-shadow/concern-format.md`

Rewrite the parser-contract sentence at lines 55–60. Current text asserts the
complete marker must be on one captured line; replace with a statement of the
**envelope and its limits**:

- the parser rejoins a bracket split across up to 2 following rows (3 rows
  total), with the covered-region arithmetic;
- a split wider than that is **still dropped** — the bound is the documented
  limit, not an implementation detail;
- region reconstruction across a join is **best-effort** (the spaced-slash case
  named), while `priority` and `body` are exact;
- the short-region producer rule (≤ ~30 chars) **stays** and remains the primary
  defense — it keeps the region exact and avoids relying on the bound at all.

Also extend the `concern_parser.py` module docstring (lines 26–31) to note the
bounded tolerance alongside the mandatory `- ` guard.

## Risk

### Code-health risk: low
- Bounded join could over-join and swallow a legitimate continuation row into a
  marker · severity: low · → mitigation: covered in-task by the two negative
  controls, the `_MARKER_START` stop-guard, and commit-on-success (a failed join
  consumes nothing)
- `_parse_items` loop rewrite (iterator → index walk) touches the shared code
  path of all four public entry points · severity: low · → mitigation: covered
  in-task by the existing 318-line suite plus the body-wrap regression guard
- The join bound leaves a residual dropped-item case (marker split across >3
  rows), and region reconstruction is heuristic · severity: low · → mitigation:
  both are accepted, documented limits rather than latent bugs — pinned by the
  at-bound/over-bound pair and the spaced-slash case, and backed by the
  unchanged short-region producer rule

### Goal-achievement risk: low
- None identified. The failure is reproduced, the fix is local to one pure
  function, and the acceptance signal (`has_concern_block: True`, 1 concern on
  the live capture) is directly asserted.

`risk_mitigations_planned = false` — both identified risks are mitigated inside
this task by the named tests; no before/after follow-up task is warranted.

## Verification

```bash
python3 -m pytest tests/test_concern_parser.py -v
bash tests/run_all_python_tests.sh
```

All existing tests must still pass; the new `TestSplitMarkerJoin` cases must
pass, with the live-capture fixture asserting both `parse_concerns` length 1 and
`has_concern_block is True`.

## Step 9 (Post-Implementation)

Current-branch profile — no worktree/branch cleanup. Run the gate orchestrator
(`risk_evaluated` is the active gate), then archive via
`./.aitask-scripts/aitask_archive.sh 1167`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, in three files.
  `concern_parser.py` gained `_MARKER_START`, `_MAX_MARKER_JOIN_ROWS = 2`,
  `_join_sep()` and `_join_split_marker()`, and `_parse_items` was rewritten
  from a `for` over `splitlines()` to an index walk so a join can consume more
  than one row. `tests/test_concern_parser.py` gained `TestSplitMarkerJoin`
  (8 tests). `concern-format.md`'s `region` bullet was rewritten into a
  "split-marker hazard and its bounded recovery" subsection.

- **Deviations from plan:** None. The plan was revised *before* approval in
  response to two shadow-review concerns (see below), and implementation
  followed the revised plan verbatim.

- **Issues encountered:**
  - `python3 -m pytest` is unavailable in this environment (`.aitask/venv` has
    no pytest); used `python3 -m unittest tests.test_concern_parser` instead.
    The plan's Verification block should be read accordingly.
  - The aggregate runner (`tests/run_all_python_tests.sh`, 1765 tests) reports
    4 failures + 1 error in `test_tui_switcher_agent_launch`. These are
    **pre-existing and unrelated**: the file passes 14/14 standalone, and the
    failures are `assertIsInstance` mismatches caused by the same module being
    imported under two `sys.path` identities in one process. This diff touches
    neither the switcher nor its imports.
  - The main-branch index carried **5 pre-staged files from a concurrent
    session** (`.agents/skills/codex_tool_mapping.md`, three
    `.claude/skills/aitask-shadow/*` files, `website/.../shadow-agent.md`).
    Committed with an explicit pathspec (`git commit -- <my three paths>`) so
    the other session's staged work was neither committed nor unstaged.

- **Key decisions:**
  - **Bound = 2 joined rows (3-row marker).** Justified by arithmetic rather
    than taste: ~165 chars of marker at 55 columns ≈ a 150-char region, ~5× the
    producer's 30-char rule and ~3× the 53-char region that actually broke. Made
    an asserted contract by an at-bound (parses) / over-bound (does not) test
    pair, so changing the constant forces a deliberate decision.
  - **Region reconstruction is explicitly best-effort.** A capture cannot
    distinguish a renderer-consumed space from a continuing token, so `_join_sep`
    treats a trailing `-`/`/` as intra-token (exact for paths — the only failure
    mode seen live) and restores a space otherwise. `priority` and `body` stay
    exact. The known cosmetic loss (prose region broken after a spaced slash →
    `foo /bar`) is asserted in a test so it reads as a decision, not a bug.
  - **Commit-on-success lookahead** rather than a consuming scan: a failed join
    consumes nothing, and the scan stops at any row beginning a marker. This is
    what preserves the existing collision-hardening guarantee, and it is covered
    by two negative controls.
  - **Scope kept to the parser.** The producer-side short-region rule from t1158
    stays in force and is now documented as the *primary* defense; this fix is
    the structural backstop, not a replacement.

- **Upstream defects identified:** None.

  (The `test_tui_switcher_agent_launch` aggregate-runner failures above are a
  test-harness/import-isolation artifact, not a defect in another module's
  behavior, so they are not listed here. They are a test-infrastructure gap and
  belong to `/aitask-qa` if pursued.)
