---
Task: t1636_1_concern_dimension_vocabulary_module.md
Parent Task: aitasks/t1636_shadow_concern_impact_vector_model.md
Sibling Tasks: aitasks/t1636/t1636_2_concern_parser_impact_trailer.md, aitasks/t1636/t1636_3_producers_emit_impact_trailer.md, aitasks/t1636/t1636_4_picker_trade_profile_rendering.md, aitasks/t1636/t1636_5_delta_scoped_auto_recheck.md, aitasks/t1636/t1636_6_manual_verification_shadow_concern_impact_vector_model.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-30 16:00
---

# p1636_1 — Dimension vocabulary module + format spec (SSOT)

Creates the single source of truth every other t1636 child builds on: the
closed quality-dimension vocabulary, magnitude semantics, `derive_priority`,
and the `concern-format.md` spec section — plus the doc↔module drift guard.

Parent plan `aiplans/p1636_shadow_concern_impact_vector_model.md` settles the
design (7 dims, maintainability/simplicity split, grammar, priority mapping);
this plan implements, it does not re-decide.

## Context

The shadow agent's review procedures classify every concern on an undefined
`high/medium/low` scale — no rubric states *what* is high, so the reader cannot
tell on which dimension. t1636 replaces that scalar with a signed **impact
vector** over one closed quality-dimension vocabulary
(`Improves: robustness(high). Worsens: simplicity(low). Effort: low.`), where
the mandatory Worsens side forces a reviewer to price its own suggestion — the
anti-overengineering mechanism.

This child creates the vocabulary itself. Nothing consumes it yet: t1636_2
(parser), t1636_3 (producers) and t1636_4 (picker) all import from it, so every
downstream child is blocked on the names, labels, magnitude semantics and
`derive_priority` mapping this task fixes.

## Plan verification (2026-08-30)

Re-checked against the current tree; every assumption holds.

- `.aitask-scripts/monitor/concern_dimensions.py` does not exist. ✅
- `lib/followup_kinds.py:33` — `FOLLOWUP_KINDS` dict → `frozenset` (`:51`) →
  `*_for()` accessors → `followup_kinds_pipe()`. Pattern intact. ✅
- `concern_parser.py` is pure; its only sibling import is the try/except
  relative/flat `ansi_utils` pair at **lines 104–107** (plan said `:104`).
  `.aitask-scripts/monitor/__init__.py` exists, so both import shapes work; a
  new pure sibling in `monitor/` needs no `sys.path` work. ✅
- `concern-format.md` — `### Derived fields: \`disposition\` and \`verdict\``
  spans **156–185**, followed by `### Capture-join contract` at 186. The new
  section goes between them. The file carries **no Jinja**, and
  `.claude/skills/aitask-shadow-fast-/concern-format.md` is byte-identical to
  the authoring source — so a guard anchored at the source is sufficient here
  (unlike the producer docs t1636_3 touches, which *are* rewritten on render).
  ✅
- `tests/test_concern_parser.py::TestShadowDocsNotParserLive` globs **every**
  `*.md` in `.claude/skills/aitask-shadow/`, so the new section is swept by
  both `has_concern_block` and `contains_any_concern_block` for free. ✅
- `tests/test_shadow_disposition_surfaces.py` supplies the reusable drift-guard
  primitives: `normalize()` (whitespace-collapse, so wrapped prose is
  matchable) and `extract_section()` — which **raises** unless the heading
  anchor matches exactly one line. ✅
- **≤5-cell label bound re-derived against real code**, not taken on faith:
  `monitor_shared.py:2649` `_NARROW_PREFIX_COLS = 8`, and `_ConcernRow.render`
  (`:2807`) emits the narrow continuation line as `"\n   {body}"` — a 3-space
  indent. A third vector line at 24 columns therefore has `24 − 3 = 21` cells,
  and `2·(1+W+1) + 2 + 4 ≤ 21 → W ≤ 5`. Matches p1636_4 step 3's worst case
  `▲maint? ▼simpl? E:hi` = 20. ✅
- **None of the seven dimension names occurs anywhere in `concern-format.md`
  today** (grep count 0 for each). The new section's prose introduces all of
  them outside the table, which is what makes a section-wide *membership* drift
  check concretely satisfiable with the table deleted — hence the row-tuple
  contract in step 3 rather than name membership. ✅
- Markdown tables are already the house style in this doc
  (`:228`, `:291`, `:370`), with backtick-quoted identifier cells. ✅
- Parent decisions 1/2/5/6 read directly; the steps below are faithful to them.
  The parent's four pre-phase mitigations all target children 2/3/4 — **none
  lands in this child**. ✅

## Steps

### Pre-phase (risk mitigations)

**P1. `guard_must_be_able_to_fail`** — the label-width bound is this module's
only structural defense of t1636_4's packing budget, so write it as a guard
that *can* fire:

- an unconditional module-level check that **raises** (`raise ValueError(...)`)
  — never a bare `assert`, which `python -O` strips, leaving a guard that
  silently checks nothing;
- it validates **two** properties, because the bound is stated in *terminal
  cells* while `len()` counts *characters*: every label is `str.isascii()`
  **and** `len(label) <= 5`. Pinning ASCII is what makes `len()` an exact cell
  count rather than an assumption;
- the comment above it derives the bound and **names the two constants it
  depends on** — `monitor_shared._NARROW_PREFIX_COLS` (8) and the 3-space
  narrow-row indent in `_ConcernRow.render` — so t1636_4 can find and re-check
  this if the row geometry moves;
- `tests/test_concern_dimensions.py` proves the guard fires: rebuild the check
  over a synthetic table containing a 6-char label and a non-ASCII label, and
  assert each raises. (Extract the check as a module-level function taking a
  table, so the test drives the real predicate rather than a replica.)

**P2. `drift_guard_cannot_pass_vacuously`** — a doc↔code enumeration guard's
characteristic failure is passing against the wrong text, in two ways that must
both be closed:

- **Wrong slice.** A renamed or duplicated heading leaves the guard reading an
  empty or unintended section. Reuse the house tripwire rather than writing a
  new matcher: import/adapt `extract_section()` and `normalize()` from
  `tests/test_shadow_disposition_surfaces.py`, keep its
  "matched N lines (expected exactly 1)" `AssertionError`, and assert the
  extracted section is **non-empty** before comparing.
- **Wrong granularity.** A name-membership check over the section is
  structurally too weak here (see step 3): it is blind to `label` and `rubric`
  drift, and it can be satisfied by the section's own prose after the table is
  deleted. The guard must parse the **table rows** and compare ordered
  `(dimension, label, rubric)` tuples against `CONCERN_DIMENSIONS`, with a
  second tripwire asserting the section contains exactly one table.

Both are proved by negative controls that drive the real predicate (step 3).

### Main implementation

1. **Write `.aitask-scripts/monitor/concern_dimensions.py`**, modelled on
   `lib/followup_kinds.py` (dict = canonical order, derived frozenset,
   accessors, module docstring explaining why the vocabulary is closed and
   framework-semantic — users must not extend it, unlike `labels.txt`):

   - `CONCERN_DIMENSIONS: dict[str, tuple[str, str]]` — name → (short label,
     one-line rubric). **Declaration order is the canonical order:**

     | dimension | label | rubric |
     |---|---|---|
     | `goal` | `goal` | the task's AC / the user's stated intent is delivered |
     | `correctness` | `corr` | right behavior on reachable inputs |
     | `robustness` | `robus` | stability under failure / concurrency / hostile input (includes security) |
     | `performance` | `perf` | latency, throughput, resource cost |
     | `verification` | `verif` | testability; proof the change works |
     | `maintainability` | `maint` | readability, duplication, conventions; ease of safe change |
     | `simplicity` | `simpl` | amount of mechanism; the classic worsen-side |

   - `VALID_DIMENSIONS: frozenset`, `dimensions_pipe()` (sorted alternation for
     the regex builder t1636_2 needs — mirrors `followup_kinds_pipe()`),
     `label_for()`, `rubric_for()`.
   - `MAGNITUDES = ("high", "medium", "low")` and `normalize_magnitude(raw)`:
     recognised case-insensitively → canonical; unrecognised, absent, empty or
     non-string → `""` (unspecified) — **never `low`**. Docstring records why:
     degrading an unknown magnitude to `low` on the *worsen* side understates a
     cost, which is the unsafe direction for an anti-overengineering mechanism.
   - `OBLIGATION_DIMENSIONS = frozenset({"goal", "correctness"})` — the
     categorical core used by the disposition grounding. Docstring records that
     `robustness` / `performance` become obligation-touching **only when the
     task's AC or plan obligates them** — a per-task judgement made by the
     producing agent, which is why this module records only the categorical
     core and not a predicate.
   - `derive_priority(improves) -> str` — the single canonical marker-priority
     mapping (parent decision 2): max over improve entries whose magnitude is
     **known**, ordered `high` > `medium` > `low`; `None` (sentence absent),
     `()`, or an entry list with no known magnitudes → `"low"`. Reads each
     entry by **index** (`entry[1]`); t1636_2's `ImpactEntry` is a `NamedTuple`,
     so index access covers both it and the `(name, magnitude)` tuples this
     module is tested with — no duck-typing branch needed.
   - The P1 width guard.
   - **Pure module:** no I/O, no `sys.path` insertion, no tmux, no imports
     outside the stdlib — it is imported by the contractually pure
     `concern_parser.py` as a sibling.

2. **Add the spec section to `.claude/skills/aitask-shadow/concern-format.md`**,
   inserted after `### Derived fields: \`disposition\` and \`verdict\`` (ends
   line 185) and before `### Capture-join contract` (line 186), titled
   `### Derived fields: the impact vector (Improves / Worsens / Effort)`.
   Content:

   - **the dimension table** — a three-column markdown table
     (`| dimension | label | rubric |`, the house style already used at
     `concern-format.md:228/291/370`), carrying **all three fields verbatim from
     `CONCERN_DIMENSIONS`, in declaration order**. The label column is included
     deliberately: it makes the doc a complete mirror of the module (the parent
     asked for an enumeration "matching the module"), and it gives the drift
     guard a row shape to compare rather than a bag of names. Cells are
     backtick-quoted for `dimension` and `label`, plain prose for `rubric`;
   - **the grammar**: closed dimension names; entries are `name` or
     `name(magnitude)`; magnitudes `high|medium|low` case-insensitive, unknown
     → unspecified, and the dimension is **never dropped**;
   - **the mandatory-Worsens rule**: every vector-bearing concern prices its own
     suggestion. `Worsens: nothing.` is a *priced* empty set and is a **different
     state** from an absent `Worsens:` sentence (parent decision 5) — the
     anti-overengineering mechanism lives in whether the reviewer did the
     pricing at all;
   - **magnitudes advisory, dimensions load-bearing** — LLM magnitude
     calibration is noisy; a named dimension still beats an unnamed scalar;
   - **`Effort:` is a separate one-time-cost scalar**, never a vector dimension:
     quality deltas are permanent properties of the codebase, effort is
     transient — mixing them corrupts both;
   - **the disposition grounding rubric**: `blocking` = the improve side touches
     an obligation dimension per the task's AC / plan goal; `follow-up` =
     net-positive but non-obligated; `informational` = no proposed delta, or
     already settled. Cross-reference `impl-review-angles.md` as the rubric's
     authoritative home (t1636_3 grounds it there). **All three values must
     appear together in this section** — `test_shadow_disposition_surfaces.py`'s
     whole-surface sweep fails any window naming `blocking` + `follow-up`
     without `informational`, and that sweep already covers `ALL_SURFACES`;
     concern-format.md is not in that list today, but the co-occurrence rule is
     the house convention and the section should satisfy it anyway;
   - **the priority mapping**: `derive_priority`, plus the producer rule that a
     vector-bearing concern's marker priority equals it.

   **t1123 discipline (load-bearing):** this doc is read at runtime into the
   shadow pane and minimonitor parses that pane. Never write a contiguous
   `===AITASK-CONCERNS===` → `- [..]` items → `===END-CONCERNS===` block —
   follow the file's existing inline-sentinel style (name the sentinels in
   prose, show item lines separately). Example trailers are safe: they carry no
   fences. Verified by the existing
   `TestShadowDocsNotParserLive::test_no_doc_embeds_any_contiguous_block`,
   which globs every `*.md` in the shadow dir.

3. **Write `tests/test_concern_dimensions.py`** (`sys.path.insert` of
   `.aitask-scripts/monitor`, the `test_concern_parser.py` bootstrap):

   - **module content** — exactly 7 dimensions in the settled order; labels
     match the table; `VALID_DIMENSIONS == set(CONCERN_DIMENSIONS)`;
     `dimensions_pipe()` is sorted and alternation-shaped;
     `OBLIGATION_DIMENSIONS ⊆ VALID_DIMENSIONS`;
   - **width guard** — P1's negative controls (6-char label, non-ASCII label);
   - **`normalize_magnitude`** — `"HIGH"`→`"high"`, `" Low "`→`"low"`,
     `"extreme"`→`""`, `None`/`""`/`123`→`""`;
   - **`derive_priority`** — `[("robustness","high")]`→`high`;
     `[("simplicity","low"),("goal","medium")]`→`medium` (max, not first);
     `[]`→`low`; `None`→`low`; `[("goal","")]` (all-unknown)→`low`; and an
     `ImpactEntry`-shaped `NamedTuple` input resolves identically to the plain
     tuple (pins the index-access contract t1636_2 depends on);
   - **doc↔module drift guard — row-tuple equality, not name membership.**
     Membership over the section is **not** a sufficient contract: the section's
     own prose will name `robustness` / `simplicity` (the grammar example),
     `goal` / `correctness` (the obligation core) and `performance` /
     `verification` / `maintainability` (the "obligated only when the AC
     obligates them" note), so a membership check could pass with the table
     **deleted** — and it would never see a changed `label` (a load-bearing
     picker render token, bounded by the ≤5-cell rule) or a drifted `rubric` at
     all. The guard therefore:
     1. extracts the section by heading anchor (P2's exactly-one-heading
        tripwire + non-empty assertion);
     2. finds the markdown tables within it and asserts there is **exactly
        one** — a second tripwire, so adding another table cannot silently
        redirect the parse;
     3. parses its body rows into ordered `(dimension, label, rubric)` tuples —
        split on `|`, drop the leading/trailing empties and the `|---|`
        separator row, strip surrounding backticks from the first two cells,
        whitespace-normalize the rubric (`re.sub(r"\s+", " ", …)`) so a
        re-wrapped table cell is not a false failure;
     4. asserts that ordered list equals
        `[(name, label, rubric) for name, (label, rubric) in
        CONCERN_DIMENSIONS.items()]` — one `assertEqual` over the whole
        sequence, which catches a changed label, a drifted rubric, a missing
        row, an extra row **and** a reordering (declaration order is canonical:
        the producers and the picker both use it).
   - **negative controls** — expose the parse+compare as a function over doc
     text so the controls drive the **real** predicate, and assert it **fails**
     on each of: an altered label; an altered rubric (one word changed); a
     missing dimension row; an extra dimension row; two rows swapped; and the
     **table deleted while every dimension name remains in the surrounding
     prose** — the control that proves the guard reads the table rather than
     the section. Plus a positive control: the real doc passes.

4. **Run** `./.aitask-scripts/aitask_skill_verify.sh` (concern-format.md is a
   shadow-doc surface) and the targeted tests.

## Verification

- `python3 -m pytest tests/test_concern_dimensions.py tests/test_concern_parser.py`
  — the parser suite must stay green **untouched**: this child adds no parser
  code, and `TestShadowDocsNotParserLive` is the t1123 check on the new doc
  section.
- `python3 -m pytest tests/test_shadow_disposition_surfaces.py` — the shadow
  doc-surface guards stay green after the concern-format.md edit.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read **only** the last
  line (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); an earlier
  `Results: N passed` line belongs to one script-style module, not the suite.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- Negative-control proof, run against the **real** doc (not only the synthetic
  fixtures): temporarily (a) delete one dimension row, (b) change one label,
  (c) reword one rubric, and (d) delete the whole table while leaving the
  section's prose intact — confirm the drift test fails in **each** case, then
  restore. (d) is the one that distinguishes this guard from the membership
  check it replaces.

## Risk

### Code-health risk: low

- The label-width bound is the module's only structural defense of t1636_4's
  21-cell packing budget, and its natural spelling (`assert`) is stripped under
  `python -O` while `len()` measures characters where the bound is stated in
  terminal cells — a guard that cannot fail, or that measures the wrong thing,
  is the same as no guard · severity: low · → mitigation: inline pre-phase
  `guard_must_be_able_to_fail`
- Otherwise contained: one new pure module with no runtime consumers yet, one
  appended doc section already swept by an existing guard, one new test file.
  No existing code path is modified · severity: low · → mitigation: none needed

### Goal-achievement risk: low

- The doc↔module drift guard **is** the deliverable, and this class of guard
  passes vacuously in two ways: a heading anchor that stops matching the section
  it should read, and a name-membership contract too coarse to see `label` /
  `rubric` drift or the table's deletion (the section's own prose names every
  dimension) · severity: medium · → mitigation: inline pre-phase
  `drift_guard_cannot_pass_vacuously`
- The ≤5-cell bound is derived from t1636_4's not-yet-written render geometry.
  Re-verified today against `_NARROW_PREFIX_COLS = 8` and the 3-space narrow
  indent, and the derivation is recorded in the guard's comment naming both
  constants, so a later geometry change is traceable · severity: low ·
  → mitigation: folded into `guard_must_be_able_to_fail`

### Planned mitigations

- timing: pre-phase | name: guard_must_be_able_to_fail | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — width guard cannot fail / measures characters not cells | desc: raise instead of assert, pin labels ASCII so len() is an exact cell count, derive the bound in a comment naming _NARROW_PREFIX_COLS and the 3-space indent, and test that the guard fires on a 6-char and a non-ASCII label
- timing: pre-phase | name: drift_guard_cannot_pass_vacuously | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — drift guard passes against an empty/wrong section, or at a granularity too coarse to see label/rubric drift or the table's deletion | desc: reuse extract_section()'s exactly-one-heading tripwire and normalize() from test_shadow_disposition_surfaces.py and assert the section is non-empty; then parse the section's single markdown table (exactly-one-table tripwire) into ordered (dimension, label, rubric) tuples and assertEqual against CONCERN_DIMENSIONS, with negative controls for altered label, altered rubric, missing row, extra row, swapped rows, and table-deleted-while-names-remain-in-prose

## Post-Implementation

Standard Step 9 (task-workflow): commit, archive task + this plan, `./ait git`
for task/plan files.
