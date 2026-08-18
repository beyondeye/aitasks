---
Task: t1557_tighten_claude_proceed_pattern_to_whole_line.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1557 — Tighten `claude_proceed` to a whole-line anchor

## Context

Claude Code's tool-permission dialog renders option 1 as **editable** (`Tab`
amends it). `monitor/prompt_patterns.py`'s `claude_proceed` matches
`Do you want to proceed?` **anywhere on a line**, so a user who types that
phrase into the amend box puts a second copy of it inside the bottom-6-line
detection window (`_prompt_detection_text`). The reported kind then flips
mid-dialog (`claude_help_bar` → `claude_proceed`), and
`classify_followed_change` short-circuits to `WORK` on `prev_kind != curr_kind`
— firing a spurious auto-recheck round of the review loop while the user is
still typing.

t1540 closed the identical hole one layer down: the review-loop **boundary**
(`review_loop._CLAUDE_PERMISSION_RE`) is already a whole-line anchor
(`^\s*Do you want to proceed\?\s*$`) precisely so user-typed text cannot
relocate it. The **prompt pattern that selects the kind** was left as a
substring, so the two layers disagree. This task makes them agree.

### Measured, reproduced against the shipped fixtures

Run against `tests/review_loop_fixtures.py` with the real
`_prompt_detection_text` window (last 6 lines of the stripped capture):

| fixture | whole-line match in window | substring match in window |
|---|---|---|
| `CLAUDE_PERMISSION_SHORT_SEL1/SEL2/LATER_RAW` (120x6) | **yes** | yes |
| `CLAUDE_AMEND_TYPED_PHRASE/SEL1/SEL2_RAW` (typed copy) | **no** | yes |
| `CLAUDE_PERMISSION_SEL1/SEL2/LATER_RAW` (120x30) | no | no |
| `CLAUDE_PERMISSION_COMPACT_*_RAW` (120x14) | no | no |

The tightening keeps every legitimate match and drops only the typed one. The
end-to-end verdict, measured through the production classifier on the untyped→typed
transition (see the test design below):

| | reported kinds | `classify_followed_change` |
|---|---|---|
| today (substring) | `claude_help_bar` → `claude_proceed` | **`work`** |
| today, kind pinned | `claude_help_bar` → `claude_help_bar` | `selection_only` |
| after (whole line) | `claude_help_bar` → `claude_help_bar` | `selection_only` |

**The short-pane regime must not break.** At ≤9 rows Claude truncates the option
list, lifting the real question into the window at index -5 as a whole line —
there `claude_proceed` is the *correct* reported kind (t1540's measurement).
Whole-line anchoring preserves that; the existing
`ClaudePermissionBoundaryTests.test_reported_kind_is_geometry_dependent_as_measured`
is the guard and must stay green.

---

## Implementation

### Pre-phase (risk mitigations)

1. `[characterize_ordered_state_negative_half]` Before touching the pattern,
   characterize the *other* consumer of `PROMPT_PATTERNS_BY_AGENT`:
   `review_loop._ordered_state` (line ~499) scans the **whole** captured tail,
   not the 6-line window, and any pattern hit there returns `SHADOW_DIALOG`.
   Narrowing `claude_proceed` narrows that negative half too.

   **Do not pin this through `shadow_prompt_ready` / `_claude_state` — that pin
   is vacuous, measured.** With *every* claude pattern removed, `_claude_state`
   still returns `'dialog'` for `CLAUDE_PERMISSION_COMPACT_SEL1_RAW`,
   `CLAUDE_PERMISSION_SHORT_SEL1_RAW` and `CLAUDE_AMEND_TYPED_SEL1_RAW`:
   `_composer_state`'s positive half returns `SHADOW_DIALOG` the moment it sees
   an option row (`review_loop.py:533`), before the pattern loop can matter. A
   positive-only assertion at that level passes for any pattern whatsoever.

   Probe the pattern loop where it is actually observable, at the seam the
   module documents for exactly this ("Signature preserved verbatim: the
   negative-control tests call it directly with mutated regexes"): call
   `rl._ordered_state(raw, agent="claude", positive=<forces SHADOW_READY>,
   working_re=<never matches>)`, so `SHADOW_DIALOG` can only come from a
   pattern hit. Assert **both** directions, on frames derived from the real
   `CLAUDE_AMEND_TYPED_SEL1_RAW` capture:

   | frame | before | after |
   |---|---|---|
   | the three real permission captures | `dialog` | `dialog` |
   | typed capture, real header line dropped (help bar kept) | `dialog` | `dialog` |
   | typed capture, header **and** help bar dropped — the typed copy is the only remaining occurrence | `dialog` | **`ready`** |

   The third row is the change, bounded and asserted rather than assumed; the
   second shows `claude_help_bar` still carries the frame once `claude_proceed`
   stops. Write the whole table green against the **unmodified** module first,
   then update the one cell the change moves — a characterization flip table,
   not an after-the-fact pin.

   Then add the production-level half: `_claude_state` returns `SHADOW_DIALOG`
   for all three real captures **and** for both derived variants, before and
   after. State in the docstring that this half is carried by the structural
   option-row check, not by the pattern — otherwise a later reader mistakes it
   for pattern coverage and rebuilds the vacuous pin.

### 1. `.aitask-scripts/monitor/prompt_patterns.py`

Add a module-level named constant next to `_TRUST_YES` / `_TRUST_NO` (house
style there is `[ \t]`, not `\s`, and the class-level flag is required because
matching runs against a multi-line blob):

```python
# The permission dialog's question, alone on its line. Shared verbatim with
# `review_loop._CLAUDE_PERMISSION_RE` — same dialog, same literal, and the two
# layers must not drift.
CLAUDE_PROCEED_LINE_RE = re.compile(r"(?m)^[ \t]*Do you want to proceed\?[ \t]*$")
```

Use it as `claude_proceed`'s regex (keep the pattern's position — it is listed
before `claude_help_bar` and matching is first-wins, which is what makes the
short-pane regime report `claude_proceed`). Extend the existing comment block
with:

- **why whole-line** — the option rows are editable, so a substring anchor lets
  user-typed text add a second in-window copy and flip the reported kind; the
  same reason, and the same technique, as `claude_trust_folder`'s "each option
  line holds nothing but its label";
- **KNOWN LIMIT** — a long amend text that *wraps* so the phrase lands alone on
  a continuation line would still match. Narrow (the wrap point must fall
  exactly before `Do`), unreproduced in the fixture set, and defending against
  it needs structural knowledge of the option rows. Documented, not guarded —
  the file's existing KNOWN LIMIT convention.

### 2. `.aitask-scripts/monitor/review_loop.py`

Import the constant in the existing relative/flat `try`/`except` import block
(lines 54/57, alongside `PROMPT_PATTERNS_BY_AGENT`) and replace the duplicated
literal at line 901:

```python
_CLAUDE_PERMISSION_RE = CLAUDE_PROCEED_LINE_RE
```

This changes `\s` → `[ \t]`, which is behaviour-identical here: `_boundary_index`
searches one already-split line at a time. Keep the existing comment block (it
explains *why* the boundary is whole-line) and add one line recording that the
literal now lives in `prompt_patterns.py` and is shared with the kind selector,
so the two layers cannot be edited apart.

### 3. `tests/test_review_loop.py`

**New class `TypedAmendCannotFlipTheReportedKindTests`.** The typed frames are
real captures; the "before typing" frame is derived from each by removing the
amend text from the option-1 row, so everything above the boundary is
byte-identical (the same derived-frame idiom the file already uses in
`test_non_dialog_change_under_the_kind_is_unknown`):

```python
_TYPED_ROW = "\x1b[38;5;153mYes, \x1b[39mDo you want to proceed?"
_PLAIN_ROW = "\x1b[38;5;153mYes\x1b[39m"
```

- `test_typed_copy_is_inside_the_detection_window` — premise control: the typed
  copy is in the last 6 lines and the real header is not, asserted via
  `mc._prompt_detection_text`. Without this the tests below could pass for the
  wrong reason.
- `test_typing_the_phrase_does_not_change_the_reported_kind` — for each of
  `CLAUDE_AMEND_TYPED_PHRASE/SEL1/SEL2_RAW`, `mc.classify_content(...)` reports
  the **same** kind as its untyped derivation, and that kind equals the one the
  real untyped capture `CLAUDE_PERMISSION_COMPACT_SEL1_RAW` reports at the same
  geometry (`claude_help_bar`) — cross-surface parity asserted surface-vs-surface,
  not against a re-implemented regex.
- `test_dialog_to_typed_transition_is_not_work` — the defect at its cause:
  `rl.classify_followed_change(untyped, kind(untyped), typed, kind(typed), True,
  "claude")` must be `SELECTION_ONLY`, never `WORK`, with the kinds taken from
  the **production** classifier rather than hand-supplied.
- `test_untyped_and_typed_frames_really_differ_when_stripped` — premise control,
  so `SELECTION_ONLY` cannot be a vacuous `NO_CHANGE`.

**Add to `ClaudePermissionBoundaryTests`** (beside the existing
`test_both_kinds_share_one_boundary_object`):

- `test_boundary_and_prompt_pattern_share_one_object` — `assertIs` between
  `rl._CLAUDE_PERMISSION_RE` and the `claude_proceed` entry's regex in
  `pp.PROMPT_PATTERNS_BY_AGENT["claude"]`. The drift guard for the shared
  constant.

### 4. `tests/test_prompt_detection.py`

This file owns `claude_proceed`'s pattern-level coverage. Add
`_check_claude_proceed_requires_a_whole_line()` and register it in `main()`'s
`tests` list:

- the phrase alone on a line still reports `claude_proceed` (the shipped
  behaviour, restated at this layer);
- an editable option row carrying it (`❯ 1. Yes, Do you want to proceed?`) alone
  reports **no kind** — nothing else in the claude group matches a bare option
  row, so this is deterministic;
- prose quoting it inline ("the dialog asks Do you want to proceed? before it
  runs") reports no kind — the same class of negative control the file already
  ships for `claude_trust_folder`.

Add item 12 to the module docstring's numbered list.

### 5. Docs

- `aidocs/framework/monitor_idle_and_prompt_detection.md` — the "Three rules for
  the regex itself" section uses `claude_proceed` as its worked example for
  bottom-anchoring; note there that it is now **whole-line anchored**, why (the
  editable option row), and that the literal is shared with the review-loop
  boundary.
- `aidocs/framework/shadow_agent.md` (§ "Claude's permission dialog is anchored
  since t1540") — record that the kind selector now uses the same whole-line
  literal as the boundary, so a typed amend can no longer flip the reported kind
  ahead of the boundary lookup.

### Post-phase (risk mitigations)

1. `[document_shared_literal_coupling]` In the same commit, state the coupling
   explicitly at both call sites and in `shadow_agent.md`: the boundary
   (block location) and the prompt pattern (kind selection) are different roles
   that share one literal because they describe one line of one dialog. Name the
   drift guard (`test_boundary_and_prompt_pattern_share_one_object`) so a future
   editor who needs them to diverge knows exactly what to unpick.

---

## Verification

```bash
python3 tests/test_review_loop.py          # new class + existing boundary suite
python3 tests/test_prompt_detection.py     # claude_proceed's pattern coverage
python3 tests/test_workflow_phase.py
python3 tests/test_monitor_shadow_status.py
python3 tests/test_minimonitor_concern_smoke.py
```

All five already pass under an in-memory simulation of this change (the patched
regex substituted into `PROMPT_PATTERNS_BY_AGENT`, `_CLAUDE_PERMISSION_RE` and
both `NATIVE_DIALOG_BOUNDARIES` rows), so no existing assertion is expected to
move.

**Negative control (required).** Revert `claude_proceed` alone to the substring
form `re.compile(r"Do you want to proceed\?")` — leaving the review-loop boundary
whole-line — and confirm that:

- `test_typing_the_phrase_does_not_change_the_reported_kind` fails (the typed
  frames report `claude_proceed`, the untyped ones `claude_help_bar`);
- `test_dialog_to_typed_transition_is_not_work` fails with `work`;
- `test_boundary_and_prompt_pattern_share_one_object` fails.

The mutation must reach those assertions specifically — not trip the premise
controls — so run them individually and record which id failed.

The pre-phase characterization needs its own negative control, and it must
target the `_ordered_state` seam rather than `_claude_state`: mutating
`claude_proceed` there must flip the third table row. Confirmed vacuity check —
emptying `PROMPT_PATTERNS_BY_AGENT["claude"]` entirely leaves every
`_claude_state` verdict at `'dialog'`, so a `_claude_state`-only assertion is
not a usable control for this pattern.

Then restore, and confirm the short-pane guard is still green:
`ClaudePermissionBoundaryTests.test_reported_kind_is_geometry_dependent_as_measured`
must still report `claude_proceed` for the three `CLAUDE_PERMISSION_SHORT_*`
fixtures.

## Post-implementation

Step 9 (Post-Implementation) handles cleanup, archival and merge as usual.

---

## Risk

### Code-health risk: low

- Narrowing `claude_proceed` also narrows `review_loop._ordered_state`'s
  `SHADOW_DIALOG` negative half, which scans the **whole** captured tail rather
  than the 6-line window: a pane whose only occurrence of the phrase is a
  mid-line copy stops contributing a pattern hit there. Measured to be
  production-invisible on every real and derived permission frame — the
  structural option-row check in `_composer_state` returns `SHADOW_DIALOG`
  first — but that is a measurement, so it gets a two-direction
  characterization rather than trust. · severity: low · → mitigation: inline pre-phase characterize_ordered_state_negative_half
- One compiled constant is shared by two different roles (review-loop block
  boundary vs. prompt-kind selection); a future need to diverge them has to
  unpick the sharing. · severity: low · → mitigation: inline post-phase document_shared_literal_coupling

### Goal-achievement risk: low

- Residual hole: whole-line anchoring does not defend against amend text that
  *wraps* so the phrase lands alone on a continuation line. Narrow, unreproduced
  in the fixture set, and out of scope — documented as a KNOWN LIMIT rather than
  guarded. · severity: low · → mitigation: inline post-phase document_shared_literal_coupling

### Planned mitigations
- timing: pre-phase | name: characterize_ordered_state_negative_half | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the narrowing also reaches `_ordered_state`'s whole-tail SHADOW_DIALOG scan | desc: two-direction characterization flip table at the `_ordered_state` seam (positive half forced READY so only the pattern loop can answer), written green against the unmodified module, plus a production-level `_claude_state` half labelled as structural not pattern coverage
- timing: post-phase | name: document_shared_literal_coupling | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared constant couples two roles; goal — residual wrapped-amend hole | desc: state the coupling and the residual limit at both call sites and in shadow_agent.md, naming the drift guard

---

## Final Implementation Notes

- **Actual work done:** `claude_proceed` is now whole-line anchored via a new
  shared constant `prompt_patterns.CLAUDE_PROCEED_LINE_RE`
  (`(?m)^[ \t]*Do you want to proceed\?[ \t]*$`), which `review_loop` imports as
  `_CLAUDE_PERMISSION_RE` in place of its duplicated literal — one compiled
  object now serves both the review-loop block boundary and the kind selector.
  Tests: `OrderedStateNegativeHalfTests` (the pre-phase characterization),
  `TypedAmendCannotFlipTheReportedKindTests` (the defect at its cause),
  `test_boundary_and_prompt_pattern_share_one_object` (drift guard), a
  `patched_claude_patterns` helper, and
  `_check_claude_proceed_requires_a_whole_line` in `test_prompt_detection.py`.
  Docs updated in `monitor_idle_and_prompt_detection.md` (a fourth regex rule)
  and `shadow_agent.md` (the shared-literal bullet).

- **Deviations from plan:** the plan named the pre-phase mitigation
  `pin_shadow_dialog_negative_half` and described a positive-only pin through
  `shadow_prompt_ready`; plan review established that such a pin is **vacuous**
  and it was re-scoped to `characterize_ordered_state_negative_half` before any
  code was written. Measured: with the claude pattern group emptied entirely,
  `_claude_state` still answers `SHADOW_DIALOG` on all three real permission
  captures, because `_composer_state`'s positive half returns `SHADOW_DIALOG` on
  sight of an option row (`review_loop.py:533`) before the pattern loop runs. The
  probe moved to `_ordered_state` with the positive half forced to
  `SHADOW_READY`, where the pattern loop is the only thing that can answer, and
  `test_claude_state_verdict_is_carried_by_structure` now records the vacuity so
  the weaker pin is not rebuilt.

  Step-8 review then narrowed the new test module's documentation: it claimed
  prose "merely quoting" the question reports no kind, which is false. Whole-line
  anchoring rejects only prose that puts something ELSE on the line; a line
  holding only the question — inside a fenced code block included — still
  matches, and irreducibly so, because at ≤9 rows the real header IS such a
  line. The claim was narrowed and the limit pinned as an accepted
  `claude_proceed` match, the same treatment
  `_check_trust_pattern_known_false_positive` gives the trust dialog's limit.

- **Issues encountered:** no pair of shipped fixtures could serve as the
  untyped→typed transition — the `CLAUDE_PERMISSION_COMPACT_*` and
  `CLAUDE_AMEND_TYPED_*` frames were captured from different commands, so their
  text ABOVE the boundary differs and they classify WORK for a legitimate
  reason. The "before typing" frame is therefore derived from each real typed
  capture by removing the amend text from its option-1 row (two styling variants:
  the selected row carries `❯` and its own escapes, the unselected one does not),
  which is the derived-frame idiom the file already uses. Kind parity is still
  asserted against the real `CLAUDE_PERMISSION_COMPACT_SEL1_RAW` capture, so the
  derivation never stands alone as ground truth.

- **Key decisions:** (1) Share one compiled object across the two layers rather
  than keep two literals with a text-comparison guard — they already drifted once
  (t1540 tightened the boundary and left the selector a substring), and identity
  sharing makes that impossible; the drift guard now asserts `assertIs`. (2) Use
  `[ \t]` rather than `\s` (house style in `prompt_patterns.py`, and
  behaviour-identical at `_boundary_index`, which searches one split line at a
  time). (3) Document rather than guard both known limits.

- **Verification performed:** full Python suite — 4915 passed, 2 skipped, plus
  the 5-test serial carve-out (`PYTHON SUITE: PASSED (runner=pytest, exit=0)`).
  The pre-phase characterization was written green against the unmodified module
  and failed on exactly one cell (`['claude_proceed'] != []`), which the change
  then flipped. Negative control: reverting `claude_proceed` alone to the
  substring form failed `test_typing_the_phrase_does_not_change_the_reported_kind`,
  `test_dialog_to_typed_transition_is_not_work` (`'work'`),
  `test_boundary_and_prompt_pattern_share_one_object`,
  `test_typed_copy_alone_no_longer_claims_a_dialog` and
  `_check_claude_proceed_requires_a_whole_line` (`'claude_proceed'`), while both
  premise controls and `test_reported_kind_is_geometry_dependent_as_measured`
  stayed green — the mutation reached the probed assertions rather than tripping
  an earlier one, and the ≤9-row regime is intact.

- **Upstream defects identified:** None
