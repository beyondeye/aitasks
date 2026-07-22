---
Task: t1208_fix_verification_checklist_em_dash_truncation.md
Base branch: main
plan_verified: []
---

# t1208 — Fix verification-checklist em-dash truncation

## Context

`_strip_annotation` in `.aitask-scripts/aitask_verification_parse.py:118-121`
splits an item's text on the **first** occurrence of `SUFFIX_SPLIT`
(`" — "` — space, U+2014, space) anywhere in the line:

```python
SUFFIX_SPLIT = " — "

def _strip_annotation(text: str) -> str:
    if SUFFIX_SPLIT in text:
        return text.split(SUFFIX_SPLIT, 1)[0].rstrip()
    return text
```

It exists to remove a previously written `" — PASS 2026-07-21 17:43 <note>"`
annotation before writing a new one, but the delimiter is not anchored to the
annotation boundary. So **any checklist item whose own prose contains an
em-dash loses everything after it** on the first
`aitask_verification_parse.sh set` — permanently, because `cmd_set` rewrites
the file in place. This hit t1202's auto-verification live: two of six items
were truncated mid-sentence and had to be restored by hand from `8f23b114e`.
Without that recovery the archived task file — the durable record of *what was
verified* — would have silently misstated the acceptance criteria.

`_is_section_header` (line 133) calls the same helper, so a section-header
bullet whose prose contains an em-dash is also misclassified (it loses its
trailing `:` and stops being recognized as a header, which silently renumbers
every item below it).

A **second surface has the identical defect**:
`.aitask-scripts/aitask_verification_followup.sh:114` does
`item_text="${item_text%% — *}"` (bash `%%` = longest suffix = strip from the
*first* em-dash). That truncates the failing item's prose in the generated
follow-up bug task's description. It is not file-destructive, but it is the
same bug and is fixed here rather than left to drift.

Intended outcome: item prose is never destroyed, annotations still never
stack, header classification is correct, and the strip rule is single-sourced.

## Approach

Anchor the strip to the real annotation *shape* and scan for it **from the
right**, so only a genuine trailing annotation is removed.

### 1. `.aitask-scripts/aitask_verification_parse.py`

Add an annotation-shape regex next to `SUFFIX_SPLIT`, **derived** from the
existing `VALID_SET_STATES` set (which is what `cmd_set` uppercases into the
annotation at line 244) so the two cannot drift apart:

```python
_STATE_ALT = "|".join(sorted(s.upper() for s in VALID_SET_STATES))
# Matches an annotation body: "PASS 2026-07-21 17:43" optionally followed by a note.
ANNOTATION_RE = re.compile(
    rf"^(?:{_STATE_ALT}) \d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}(?: |$)"
)
```

Replace `_strip_annotation` with a right-to-left scan that strips at the
**last** ` — ` which actually begins an annotation:

```python
def _strip_annotation(text: str) -> str:
    """Strip a trailing ``" — STATE YYYY-MM-DD HH:MM [note]"`` annotation.

    Anchored to the annotation shape and scanned from the right, so item prose
    containing its own em-dash survives (t1208). ``cmd_set`` neutralizes the
    delimiter inside notes, so the rightmost match is the real boundary.
    """
    idx = text.rfind(SUFFIX_SPLIT)
    while idx != -1:
        if ANNOTATION_RE.match(text[idx + len(SUFFIX_SPLIT) :]):
            return text[:idx].rstrip()
        idx = text.rfind(SUFFIX_SPLIT, 0, idx)
    return text
```

Both existing callers (`cmd_set` line 241, `_is_section_header` line 133) are
fixed by this single change — no call-site edits needed.

**Neutralize the delimiter inside notes (structural half of the fix).** The
scan alone is not enough: notes are free-form, so a note that itself contains
`" — STATE YYYY-MM-DD HH:MM"` creates a second annotation-shaped segment and
makes the boundary undecidable. Verified concretely — for

```
item — PASS 2026-07-21 17:43 note says — FAIL 2026-01-01 10:00 from docs
```

the rightmost scan strips at the *note's* `— FAIL …` and returns
`"item — PASS 2026-07-21 17:43 note says"`, so old annotation content stacks
into the prose. Fix it at the write site in `cmd_set` (line 243), making the
delimiter structurally unique to the annotation itself:

```python
# Notes are free-form. A note containing the delimiter would create a second
# annotation-shaped segment and make the boundary undecidable on the next
# set, so neutralize it at write time (t1208).
note_text = (args.note or "").replace(SUFFIX_SPLIT, " -- ")
note = f" {note_text}" if note_text else ""
```

With that, the same input is written as
`item — PASS 2026-07-21 17:43 note says -- FAIL 2026-01-01 10:00 from docs`
and the next `set` strips back to exactly `"item"`.

**Accepted residual ambiguity.** Two cases remain undecidable from the line
alone, both documented in the helper's docstring and pinned by tests rather
than silently tolerated:

1. *Item prose that itself ends with an annotation-shaped segment* (e.g. an
   item literally quoting `— PASS 2026-01-01 10:00`) is indistinguishable from
   a real annotation; the first `set` will strip it. No rule can separate these
   without an out-of-band marker, and re-delimiting the annotation would break
   every already-annotated file on disk.
2. *Lines written by the old code* whose notes already contain an unsanitized
   delimiter degrade to one residual layer (as in the worked example above)
   rather than being fully cleaned. Repeated stripping would fix those but is
   equivalent to leftmost-match, which destroys legitimate prose — the exact
   defect this task exists to fix. Prose preservation wins.

Then add a `--strip-annotations` flag to the `parse` subcommand so the shell
side can reuse the canonical rule instead of reimplementing it:

- `build_parser()`: `p_parse.add_argument("--strip-annotations", action="store_true", help="emit item text with any trailing annotation removed")`
- `cmd_parse()`: when the flag is set, emit `_strip_annotation(text)` instead
  of `text`. Default output is unchanged (raw text, annotation included) —
  the manual-verification skill shows it to the user so they can see prior
  state.

### 2. `.aitask-scripts/aitask_verification_followup.sh`

Pass the flag through and delete the local reimplementation (lines 113-114):

```diff
-    item_line=$("$SCRIPT_DIR/aitask_verification_parse.sh" parse "$from_file" \
+    item_line=$("$SCRIPT_DIR/aitask_verification_parse.sh" parse --strip-annotations "$from_file" \
         | awk -F: -v idx="$ITEM_INDEX" '$1 == "ITEM" && $2 == idx { print; exit }')
@@
     item_text=$(echo "$item_line" | cut -d: -f5-)
-    # Strip any existing " — STATE ..." annotation from a prior set.
-    item_text="${item_text%% — *}"
```

### 3. `aitasks/t1208_*.md` — record the scope decision

Add the followup-surface line to the task's acceptance criteria before
implementing (the AC as written names only `aitask_verification_parse.py`):

```
- [ ] `aitask_verification_followup.sh` reuses the same anchored strip (via
      `parse --strip-annotations`) instead of its own `${var%% — *}`, and a
      failing item whose prose contains an em-dash keeps its full text in the
      generated follow-up task description.
- [ ] A `--note` containing the annotation delimiter cannot shadow the real
      annotation boundary on a subsequent `set` (no stale annotation text left
      behind as prose).
```

## Rejected alternative

Re-implementing the anchored regex in bash inside
`aitask_verification_followup.sh` (a `[[ =~ ]]` match) avoids touching the
Python CLI, but leaves two copies of the strip rule that must be kept in sync —
which is exactly how this defect reached two files. The `--strip-annotations`
flag adds no extra subprocess (the script already invokes `parse`).

## Tests

**`tests/test_verification_parse.py`** — new `TestStripAnnotation` class
exercising `vp._strip_annotation` directly, plus `set`-level cases:

| Case | Expectation |
|---|---|
| `"plain text"` | unchanged |
| `"item — PASS 2026-07-21 17:43"` | `"item"` |
| `"prose — with dash — PASS 2026-07-21 17:43 note"` | `"prose — with dash"` |
| `"item — PASS but no timestamp"` (annotation-shaped prose, no stamp) | unchanged |
| `"see — PASS 2026-01-01 10:00 in docs — FAIL 2026-07-21 18:00 n"` | `"see — PASS 2026-01-01 10:00 in docs"` (rightmost wins) |
| `"item — PASS 2026-07-21 17:43 note — FAIL 2026-01-01 10:00 x"` | `"item — PASS 2026-07-21 17:43 note"` — **pins accepted residual (2)**: a legacy unsanitized note degrades to one layer, it is not fully cleaned |

Plus, in `TestSetSubcommand`:
- `test_note_delimiter_neutralized` — `set 1 pass --note "note says — FAIL 2026-01-01 10:00 from docs"` writes the note with ` -- `, the line contains exactly two em-dashes, and a following `set 1 fail` strips back to the bare prose with no `PASS`/`note says` residue. This is the guard for the note-shadowing case.
- `test_annotation_shaped_prose_is_stripped_on_first_set` — pins accepted
  residual (1) explicitly, so the behavior is a decision on record rather than
  an untested edge.
- `test_em_dash_in_prose_survives_set` — AC 1. Item
  `- [ ] Advanced is the tier — say 'advanced review' for it.` → after
  `set 1 pass` the full prose is intact and the line has exactly two em-dashes
  (one prose + one separator).
- `test_reset_with_em_dash_prose_replaces_annotation` — AC 2. Same item, `set`
  twice (pass/note_alpha then fail/note_beta): prose intact, exactly one
  annotation, only `note_beta` survives, `note_alpha`/`PASS` gone.
- `test_parse_strip_annotations_flag` — `parse` emits raw text by default and
  annotation-stripped text with `--strip-annotations`, with prose em-dashes
  preserved in both.

**`tests/test_verification_section_headers.py`** — AC 3 + AC 4:
- `test_header_with_em_dash_in_prose_is_recognized` —
  `- [ ] group — the tuple case:` followed by two deeper-indented children is
  filtered out as a header (2 items, not 3).
- `test_annotated_header_with_em_dash_in_prose_is_recognized` — same bullet
  already carrying `— PASS 2026-04-21 08:00`, still classified as a header.
- Existing `test_pre_marked_header_still_recognized` must keep passing
  (regression guard for the annotated-header path).

**`tests/test_verification_followup.sh`** — one new case: a failing item whose
prose contains an em-dash and which carries an annotation; assert the created
follow-up task description contains the **full** prose and **not** the
`— FAIL <stamp>` annotation.

## Risk

### Code-health risk: low

- `_strip_annotation` is shared by `_is_section_header`, so a bullet that ends
  in `:` and contains an em-dash flips from "leaf item" to "section header",
  which renumbers the items below it. That is the intended fix (AC 4), but an
  in-flight checklist would see its indices shift mid-session. Verified
  concretely: a repo-wide grep over `aitasks/*.md` and `aitasks/*/*.md` for
  checklist bullets containing an em-dash and ending in `:` returns **zero**
  hits, so no live checklist is affected. · severity: low · → mitigation: none needed
- Blast radius is two files and one pure helper; both existing callers are
  fixed by the single helper change, and `VALID_SET_STATES`-derived alternation
  removes the state-list duplication a hardcoded regex would add. · severity: low · → mitigation: none needed
- Note sanitization rewrites `" — "` to `" -- "` inside a user- or
  agent-supplied `--note`, so note text is no longer byte-verbatim. This is a
  deliberate trade (an unbounded free-form note is what makes the boundary
  undecidable), it is confined to the delimiter sequence, and it is pinned by
  `test_note_delimiter_neutralized`. · severity: low · → mitigation: none needed

### Goal-achievement risk: low

- The four acceptance criteria are concrete and directly testable; each maps to
  a named test above, and the live t1202 truncation is reproduced verbatim as a
  fixture. · severity: low · → mitigation: none needed

## Verification

**Required proof** (all must pass; these are the gate):

1. `bash tests/run_all_python_tests.sh -k "verification"` — green across
   `test_verification_parse.py` and `test_verification_section_headers.py`,
   including the pre-existing `test_second_set_strips_prior_suffix`,
   `test_hyphens_not_stripped`, and `test_pre_marked_header_still_recognized`.
   Read the `-v` listing and confirm **every newly added test name appears in
   it** — a test that is silently not collected proves nothing.
2. `bash tests/test_verification_followup.sh` — all cases pass, including the
   new em-dash case.
3. `shellcheck .aitask-scripts/aitask_verification_followup.sh`.
4. End-to-end on a scratch task file under the session scratchpad: seed a
   checklist containing the two real t1202 items (with their em-dashes), run
   `set 2 pass --note "auto: ok"` then `set 2 fail --note "auto: regressed"`,
   and diff — prose byte-identical, one annotation, latest only.

**Optional sanity check** (only if the working tree is otherwise clean): edit
`_strip_annotation` back to the old one-liner in place, re-run step 1, confirm
it exits non-zero, then restore from a `cp` backup. Deliberately *not* the
required proof — it depends on isolating one helper inside an actively edited
tree, and `git stash` must not be used here (a shared checkout can lose
in-flight edits).

5. Step 9 (Post-Implementation): merge approval, `ait gates run 1208` for the
   `risk_evaluated` gate, then archival.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, both halves of the fix.
  `_strip_annotation` in `.aitask-scripts/aitask_verification_parse.py` now
  matches the annotation *shape* via `ANNOTATION_RE` — built from
  `VALID_SET_STATES` so it cannot drift from what `cmd_set` can write — and
  scans right-to-left, returning the prose before the last ` — ` that actually
  begins an annotation. `cmd_set` neutralizes `" — "` → `" -- "` inside the
  note at write time. A `parse --strip-annotations` flag was added (default
  output unchanged), and `.aitask-scripts/aitask_verification_followup.sh` now
  uses it instead of its own `${item_text%% — *}`, so the strip rule is
  single-sourced. Tests: +13 in `tests/test_verification_parse.py`
  (`TestStripAnnotation` unit cases and `TestEmDashProse` `set`-level cases
  built on the verbatim t1202 items), +2 in
  `tests/test_verification_section_headers.py`, +1 case in
  `tests/test_verification_followup.sh` (`write_mv_task` gained an optional
  third arg for the item line; existing callers unchanged).

- **Deviations from plan:** None in substance. Two acceptance criteria were
  added to the task file before implementing (the followup surface and the
  note-shadowing guarantee), each marked as added during planning.

- **Issues encountered:** Plan review caught a real hole in the first draft:
  the rightmost-match rule alone still mis-set the boundary when a *note*
  contained annotation-shaped text — `item — PASS <s> note says — FAIL <s2>
  from docs` stripped at the note's `— FAIL` and left the stale `PASS …` text
  as prose, i.e. annotation stacking despite the stated guarantee. Verified by
  reproduction, then closed structurally with the note sanitization above,
  which is why the fix has two halves rather than one.

- **Key decisions:**
  - *Rightmost, not leftmost, valid match.* Leftmost (equivalently: strip
    repeatedly) would fully clean legacy stacked lines but destroys prose that
    merely quotes an annotation — the exact defect being fixed. Prose
    preservation wins; the trade is documented in the helper's docstring.
  - *Two residual ambiguities are accepted and pinned by tests* rather than
    silently tolerated: (1) prose that itself ends with an annotation-shaped
    segment is stripped on first `set`
    (`test_annotation_shaped_prose_is_stripped_on_first_set`); (2) a line
    written by the old code with an unsanitized note sheds only its last layer
    (`test_legacy_unsanitized_note_sheds_only_one_layer`).
  - *A `--strip-annotations` flag over a bash reimplementation*, so the two
    surfaces cannot drift apart again — which is how this defect reached two
    files in the first place.
  - *Note text is no longer byte-verbatim* (only the delimiter sequence is
    rewritten). No skill or website doc claims verbatim storage, so no doc
    change was needed.

- **Verification performed:** `test_verification_parse` +
  `test_verification_section_headers` → 54 pass, exit 0, with every new test
  name confirmed present in the `-v` listing (a test that is not collected
  pins nothing). `tests/test_verification_followup.sh` → 32/32. Both negative
  controls fire: reverting `_strip_annotation` to the old one-liner produces 9
  failures and exit 1; reverting the followup line produces 1 failure and exit
  1 — so each guarded regression genuinely makes the suite fail. End-to-end on
  a scratch file seeded with the two real t1202 items: after `set 2 pass` then
  `set 2 fail`, the prose is byte-identical to the seed and exactly one
  annotation remains. Related shell suites all green
  (`test_archive_verification_gate` 34/34, `test_create_manual_verification`
  12/12, `test_verification_followup_anchor` 10/10, `test_archive_carryover`
  13/13, `test_gate_guarded_archival` 31/31,
  `test_create_manual_verification_gates` 42/42). `shellcheck` reports only
  pre-existing info-level findings (SC1091/SC2012/SC2016) on untouched lines.

- **Build verification:** The full Python suite (`bash
  tests/run_all_python_tests.sh`, 1791 tests) reports 4 failures + 1 error,
  all in TUI switcher / agent-command modules. `test_tui_switcher_agent_launch`
  passes standalone (14/14), and a 320-test subset covering those modules also
  passes — the failures need the full discovery set, so they are a test
  isolation / module-identity artifact, not a product regression. Judged
  unrelated to this task: nothing under `.aitask-scripts/board/` or
  `.aitask-scripts/lib/` imports `aitask_verification_parse`, and this change
  added no new test *modules*, so discovery order is unchanged. Noted as an
  upstream defect below rather than fixed here. **Caveat, stated plainly:**
  pre-existence was inferred from those facts, not proven by a pristine
  full-suite run.

- **Upstream defects identified:**
  - `tests/run_all_python_tests.sh:26 — full-suite unittest discovery yields 4 failures + 1 error in TUI switcher / agent-command tests (e.g. tests/test_tui_switcher_agent_launch.py:250, "AgentCommandScreen() is not an instance of <class 'agent_command_screen.AgentCommandScreen'>") that pass in isolation; a module imported under two identities during discovery breaks isinstance checks, making the aggregate suite unusable as a gate.`
  - `tests/test_gate_orchestrator_registry.py:203 — calls sys.exit() at import time, so unittest discovery reports it as a collection ERROR and the aggregate run exits non-zero regardless of the code under test.`
