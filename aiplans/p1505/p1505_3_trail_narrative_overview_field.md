---
Task: t1505_3_trail_narrative_overview_field.md
Parent Task: aitasks/t1505_lite_trail_mode_and_trail_summary_pane.md
Sibling Tasks: aitasks/t1505/t1505_4_trail_skill_lite_default.md, aitasks/t1505/t1505_5_manual_verification_lite_trail_mode_and_trail_summary_pane.md
Archived Sibling Plans: aiplans/archived/p1505/p1505_1_bytrail_summary_pane.md, aiplans/archived/p1505/p1505_2_trail_detail_modal_entry_first.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-16 10:18
---

# p1505_3 — `narrative.overview` schema field

## Context

The By-Trail board screen needs a free-form, non-binding prose summary to show
in its summary pane, and the lite `/aitask-trail` flow needs somewhere to write
one. This child adds exactly one thing: the optional schema property
`narrative.overview`. It is the missing middle piece between two siblings —
**t1505_1 (landed)** already renders `overview` and **t1505_4 (pending)** will
write it.

The consumer is already live and waiting: `trail_summary_text()`
(`.aitask-scripts/board/aitask_board.py:800-822`) reads
`("overview", "recommendation_summary")` in that order, first non-blank wins,
and its docstring says outright *"Until t1505_3 lands, `overview` is absent from
the schema and the fallback is the only live path."* The detail modal
(`aitask_board.py:4143-4153`) renders `overview` as its own labelled line. So
this task turns an already-built fallback path into the primary one.

The field must be **advisory and non-binding**: no consumer may derive
membership, ordering or classification from it. That constraint is what makes it
safe to add to a document whose other fields are binding, so it is documented in
the contract, not only in the task file.

## Step 0a — Persist this plan FIRST (do not skip)

`aiplans/p1505/p1505_3_trail_narrative_overview_field.md` **already exists** and
is stale: it still directs the reader to `bash tests/test_trail_schema.py` and to
a live-artifact `drift` check that is blocked behind t1508. That file — not this
internal one — is what survives into archival, review and any future re-plan, so
it must be replaced before implementation starts.

Because this is the **verify path with a pre-existing external plan**, the Step 6
externalization **must pass `--force`**. Without it the helper short-circuits with
`PLAN_EXISTS` and every correction below silently fails to reach `aiplans/`
(`plan-externalization.md:95` states this case verbatim). Expected result:
`OVERWRITTEN:aiplans/p1505/p1505_3_trail_narrative_overview_field.md:<source>`.

Then, still **before** the `./ait git add` (verify-path requirement):

```bash
./.aitask-scripts/aitask_plan_verified.sh append \
  aiplans/p1505/p1505_3_trail_narrative_overview_field.md "<agent_string>"
```

`decide` currently reports `TOTAL:0 / LAST:NONE`, so this is the plan's first
verification entry.

## Step 0b — Rebase check: DONE, results below

This plan was originally written against the pre-t1468_5 tree. Re-derived
2026-08-16; **t1468_5 has landed and is archived**, so the plan applies on top of
the current state:

| check | result |
|---|---|
| `schema_version` `const` in both copies | **`"1.1.0"`** (already bumped — do NOT bump again) |
| `diff` between the two schema copies | **empty** (byte-identical) |
| `test_wrong_schema_version` | asserts `"2.0.0"` is rejected; `SUPERSEDED_SCHEMA_VERSION = "1.0.0"` pinned separately by `test_superseded_schema_version_rejected_cleanly` — neither needs touching |
| `tests/test_trail_schema.py` baseline | 59 tests, **OK** |
| `tests/test_implementation_trail_design.py` baseline | 23 tests, **OK** |
| `aidocs/implementation_trail_examples/*.json` | all three already at `1.1.0` — usable as a valid baseline corpus |

**Two corrections to the task file's stated facts** (it drifted since it was
written):

1. The byte-identity test is at `tests/test_trail_schema.py:69`, not `:63`.
2. `bash tests/test_trail_schema.py` **does not work** — it is a Python module;
   `bash` mangles it into `syntax error near unexpected token '('` and exits 2,
   which reads as a failure regardless of the code. Use `python3`. Same for
   `tests/test_implementation_trail_design.py`.

## The whitespace hole — why the property is not just `minLength: 1`

The task file's proposed description claims renderers *"display it verbatim"*.
That is **not true of either shipped renderer**, and the two disagree with each
other on the degenerate case:

| document | summary pane (`trail_summary_text:818-822`) | detail modal (`line():4092-4098`) |
|---|---|---|
| `overview: "   \n  "` | blank after `.strip()` → **treated as absent**, shows `recommendation_summary` | value is not one of `None/""/[]/{}"` → renders **`overview:` with blank content** |
| `overview: "  padded  "` | returns `value.strip()` → **trimmed**, not verbatim | renders raw, with the padding |

So a schema-valid `overview` could render three different ways across two
surfaces. Both halves are fixed here:

- **The degenerate case is rejected at the schema boundary** — `"pattern": "\\S"`
  (requires at least one non-whitespace character; the interpreter's `pattern`
  uses `re.search`, `trail_schema.py:213`, so a bare `\S` is the right shape).
  This makes the renderer divergence **unreachable for valid documents**: the
  By-Trail path fails closed on schema-invalid docs, so such a document never
  reaches either renderer. Fixing it structurally beats documenting two
  behaviors, and it is **free right now** — `overview` is a brand-new optional
  property, so no stored document can be invalidated by the stricter rule. This
  is the only moment when tightening costs nothing.
- **The surviving claim is qualified rather than overstated** — surrounding
  whitespace is legal but *not significant*; the description says renderers
  display the field's **content**, not that they display it byte-for-byte.

`pattern` is used 5× in this schema today, all on structured identifiers, never
on prose (12 prose fields carry bare `minLength: 1`). That looseness is legacy —
tightening those would invalidate stored documents. `overview` carries no such
constraint, so it is written correctly from the start rather than inheriting the
hole. **No board change is in scope**; the schema boundary closes the divergence.

## Implementation steps

### 1. Add the property to both schema copies

Insert into `properties.narrative.properties` — which is
`additionalProperties: false` with `required: ["problem_statement",
"recommendation_summary"]` — **after `recommendation_summary`, before
`method_note`** (`aidocs/implementation_trail.schema.json:180`). Key order is not
semantically meaningful, but this matches the order the detail modal renders
(`problem` → `recommendation` → `overview` → `method note` → `caveats`) and keeps
the summary-family fields adjacent:

```json
        "overview": {
          "description": "Free-form prose summary of the findings and the motivation for the proposed wave/task order. Advisory and NON-BINDING: no consumer derives membership, ordering or classification from it. Renderers display its content; surrounding whitespace is not significant, and a value carrying no non-whitespace character is rejected rather than rendered blank.",
          "type": "string",
          "minLength": 1,
          "pattern": "\\S"
        },
```

Match the file's local style: two-space indent steps, one keyword per line.

- **Not** added to `narrative.required` — every existing document must stay
  valid; that is the whole point of doing this additively.
- **Do not bump `schema_version`.** t1468_5's bump to `1.1.0` already invalidated
  every stored 1.0.0 trail; a second bump would invalidate them again for a
  purely additive property. Leave the const exactly as t1468_5 set it (and leave
  `$id`, which encodes `1.1.0`, alone).

### 2. Keep the two copies byte-identical

`.aitask-scripts/lib/implementation_trail.schema.json` is the runtime copy that
actually validates (`aidocs/` does not ship to installed projects).
`SchemaCopyDrift.test_lib_schema_byte_identical_to_aidocs_contract`
(`tests/test_trail_schema.py:69`) pins byte equality. **Copy the file** rather
than hand-editing twice, then re-run `diff`.

### 3. Validator — expected no change

`SUPPORTED_KEYWORDS` (`.aitask-scripts/lib/trail_schema.py:111-115`) already
contains `type`, `minLength` **and `pattern`**, so no interpreter change is
needed. **Verify rather than assume**: the interpreter raises `RuntimeError` on
any unknown keyword *by design* (`:186-190`, "extend the trail_schema.py
interpreter"), so that schema evolution can never silently under-validate. A
`RuntimeError` here would mean the tripwire fired and the interpreter genuinely
needs extending.

Error shapes this yields for free (object children build `child_path = "%s.%s"`,
`:239`; root path is `"$"`, `:422`):

- `overview: ""` → **two** issues: `minLength` (`"length 0 < 1"`) **and**
  `pattern` (`"'' does not match \\S"`). Assert with `assertIn` on the rule set —
  do **not** assert an exact one-element rule set.
- `overview: "   \n  "` → `pattern` only (length 5 passes `minLength`).
- `overview: 123` → `type` only. `minLength`/`pattern` are checked inside
  `isinstance(value, str)` (`:212`), so a non-string produces the `type` issue
  alone.

### 4. Tests (`tests/test_trail_schema.py`)

Add a `NarrativeOverviewProperty` class modelled on the existing
`FollowupKindSnapshotProperty` (`:75`), using the file's own helpers — `fixture()`
(fresh `json.load` per call, so every mutation is already an independent deep
copy), `issues_for()`, `rules()`, and the `assert_rule(doc, rule, path_fragment)`
style at `:218-227`:

| case | expectation |
|---|---|
| `overview = "…"` present | validates, no issues |
| unmutated fixture (absent) | validates — the load-bearing back-compat case |
| not in `narrative.required` | read `AIDOCS_SCHEMA` directly (mirrors `test_property_is_optional`, `:142`) |
| `overview = ""` | `assert_rule(doc, "minLength", "narrative.overview")` |
| `overview = "   \n  "` | `assert_rule(doc, "pattern", "narrative.overview")` — the degenerate-case guard |
| `overview = "  padded  "` | **validates** — surrounding whitespace is legal; trimming is a render concern, not a validity one |
| `overview = 123` | `assert_rule(doc, "type", "narrative.overview")` |

Every failing assertion names the rule **and** the path, not merely "invalid".

### 5. Pin the render behavior the contract now claims

The description says renderers display the field's *content* with whitespace
insignificant. Pin that on the resolver rather than leaving it as prose — a
minimal, deliberate extension of this task's file list, justified because it is
the claim this task authors and the resolver already shipped with t1505_1. In
`tests/test_board_bytrail_view.py`, beside the existing
`test_blank_overview_falls_through_rather_than_winning` (`:3430`):

- `trail_summary_text({"narrative": {"overview": "  padded  "}})` == `"padded"`
  — surrounding whitespace is not significant.

The whitespace-only fallback case is already covered at `:3430`; it stays valid
as defence-in-depth even though the schema now rejects such a document.

### 6. Docs

`aidocs/implementation_trail_design.md` §6 (schema walkthrough), the narrative
bullet at **`:195-196`**:

```
- **Narrative** — required `problem_statement` and `recommendation_summary`,
  plus `method_note` (what was and was not verified) and global `caveats`.
```

Extend it to name `overview`, **state its advisory status** (no consumer derives
membership, ordering or classification from it) **and the whitespace
qualification** (content is displayed; a value with no non-whitespace character
is rejected). Stay consistent with the already-written §9 By-Trail prose at
`:336-339`, which already describes the pane reading `narrative.overview` with
the `recommendation_summary` fallback.

## Out of scope — explicit handoffs

- **`.claude/skills/aitask-trail/SKILL.md.j2`** (`:199-200`) tells the writer to
  produce "the document narrative (problem_statement, recommendation_summary,
  method_note)" and does not mention `overview`. That edit — plus its rendered
  variants across three profiles / three agents and the `tests/golden/skills/`
  regeneration — belongs to **t1505_4**, which owns the lite writer flow. Do not
  touch the `.j2` here; doing so would take on the rerender/goldens obligation
  for a field this task does not yet write.
- **Refreshing the two live artifacts to 1.1.0** belongs to **t1508**
  (`refresh_and_verify_live_trails`, Ready, high, `depends: []`).

## Verification

Run from the repo root.

0. **The durable plan was actually replaced** — Step 0a's externalization
   reported `OVERWRITTEN:`, and all three checks below exit **0**:
   ```bash
   P=aiplans/p1505/p1505_3_trail_narrative_overview_field.md
   grep -qF 'python3 tests/test_trail_schema.py' "$P"   # corrected command present
   grep -qF '"pattern": "\S"' "$P"                      # whitespace-hole fix present
   grep -q '^plan_verified:' "$P"                       # verify-path entry appended
   ```
   **Use positive checks only.** An "absence of the stale command" check is
   *unsatisfiable here*: this plan deliberately quotes
   `bash tests/test_trail_schema.py` in Step 0b to explain why it is wrong, so
   `! grep -qF …` can never pass and would fail good work. Pick markers unique
   to the revised plan instead. (Verified at externalization time: the two
   positive greps above and `^plan_verified:` all returned 0.)

   **Do not use `grep -c … # expect 0`**: `grep -c` prints `0` but *exits 1* when
   it selects no lines, so the intended success condition reads as a failure
   under `set -e` or any exit-status-aware verification. `! grep -qF` inverts to
   a true 0 exit. `-F` keeps the needle a fixed string, and the positive check
   greps the corrected command itself rather than a common word like `pattern`,
   which appears throughout this plan's prose and would pass against the stale
   file too.
1. **Schema copies identical** — must print nothing:
   ```bash
   diff aidocs/implementation_trail.schema.json .aitask-scripts/lib/implementation_trail.schema.json
   ```
2. **Unit tests** (note `python3`, not `bash`):
   ```bash
   python3 tests/test_trail_schema.py                  # baseline 59 → 59 + new cases, OK
   python3 tests/test_implementation_trail_design.py   # baseline 23, OK, no relaxation needed
   python3 tests/test_board_bytrail_view.py            # incl. the new whitespace-insignificance case
   ```
   `test_implementation_trail_design.py` needs no change: its only set-shaped
   assertion is root-level and subset-directional (`test_no_root_keys_outside_schema`,
   `:84-91`), and `test_narrative_is_first_class` (`:157-169`) only checks the two
   required fields are non-empty. Confirm that still holds rather than assuming it.
3. **Real entry point — the outermost surface**, the `validate` CLI at
   `.aitask-scripts/lib/trail_schema.py:618-629` (the same surface the existing
   CLI test class at `:588-630` drives). Copy a 1.1.0 corpus fixture to the
   scratch dir, mutate `narrative.overview`, and run:
   ```bash
   python3 .aitask-scripts/lib/trail_schema.py validate <file>
   ```
   | document | expected stdout | rc |
   |---|---|---|
   | fixture + `"overview": "…"` | `VALID:trail-gate-framework-landing` | 0 |
   | fixture + `"overview": "  padded  "` | `VALID:trail-gate-framework-landing` | 0 |
   | fixture + `"overview": ""` | `INVALID:$.narrative.overview\|minLength\|…` **and** `…\|pattern\|…` | 1 |
   | fixture + `"overview": "   "` | `INVALID:$.narrative.overview\|pattern\|…` | 1 |
   | fixture + `"overview": 123` | `INVALID:$.narrative.overview\|type\|expected string, got int` | 1 |

   **Negative control (do this BEFORE the schema edit):** the first row must
   *fail* against the unedited schema with rule `additionalProperties` — proving
   the check discriminates on this change rather than passing for an unrelated
   reason. A passing negative control means the verification is not testing
   what it claims to.
4. **Whole suite** — read **only the last line**
   (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); piping discards the exit
   status, so use `${PIPESTATUS[0]}` or `set -o pipefail` if you pipe:
   ```bash
   bash tests/run_all_python_tests.sh --test-dir tests
   ```

### Expected non-failures — do not read these as regressions

- `./.aitask-scripts/aitask_trail_gather.sh drift --trail art:trail-gates-framework-landing`
  (and `art:trail-shadow-review-loop`) return
  `INVALID:$.schema_version|const|expected '1.1.0', got '1.0.0'` +
  `ERROR:invalid_trail:1`. **Both live artifacts are still stored at 1.0.0**;
  that rejection belongs to t1468_5's bump and **t1508** owns the refresh. The
  original plan listed a live-artifact `drift` call as this task's real-entry-point
  verification — that check is **unsatisfiable** until t1508 lands and has been
  replaced by the `validate` CLI against a 1.1.0 corpus fixture (step 3 above).
- `drift --trail <corpus fixture path>` returns `ERROR:undriftable_input:…` — the
  fixtures' gather inputs (board state snapshot, an old test-suite run) are not
  re-derivable. `drift` is therefore not a validation surface for fixtures either;
  reaching that error does prove validation passed, but the `validate` CLI says so
  directly.
- `aidocs/implementation_trail_examples/*.json` need **no** change for this field.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.

## Risk

Levels describe the plan **as now written**, after this verification pass
resolved the three defects listed under goal-achievement.

### Code-health risk: low

- The two schema copies could drift if hand-edited twice instead of copied · severity: low · → mitigation: none needed — `SchemaCopyDrift.test_lib_schema_byte_identical_to_aidocs_contract` (`tests/test_trail_schema.py:69`) already fails on any drift, and step 2 mandates copying.
- The change is a single optional, non-required property in an `additionalProperties: false` object, with no validator change and no `const` movement; blast radius is 2 schema files + 2 test files + 1 doc bullet, and the only code consumer (`aitask_board.py:800-822`, `:4143-4153`) already handles present, absent and blank cases · severity: low · → mitigation: none needed.
- `pattern: "\\S"` makes `overview` stricter than the 12 legacy prose fields that carry bare `minLength: 1`, an internal inconsistency in the schema · severity: low · → mitigation: none needed — deliberate and recorded in "The whitespace hole" above; the legacy fields cannot be tightened without invalidating stored documents, whereas a brand-new optional property can be correct from the start.

### Goal-achievement risk: low

- **(resolved)** The plan as originally written verified through commands that could not report the truth — `bash` on a Python module (always exits 2) and a live-artifact `drift` call blocked behind t1508 · severity: low · → mitigation: none needed — the Verification section now uses `python3`, drives the `validate` CLI against a 1.1.0 corpus fixture, and carries an explicit negative control.
- **(resolved)** The contract prose claimed renderers display `overview` "verbatim" while both shipped renderers disagree with each other on whitespace-only values and the pane trims valid ones · severity: low · → mitigation: none needed — the degenerate case is now rejected at the schema boundary (`pattern: "\\S"`), the surviving whitespace-insignificance is stated honestly in the description and §6, and step 5 pins it with a test.
- **(resolved)** The corrections would have been lost: the durable `aiplans/` copy is stale and the externalize helper short-circuits with `PLAN_EXISTS` unless `--force` is passed · severity: low · → mitigation: none needed — Step 0a mandates `--force` and Verification step 0 checks the replacement actually happened.
- Scope boundary with t1505_4 (the `.j2` writer prose) and t1508 (artifact refresh) could be misread as part of this child, widening it · severity: low · → mitigation: none needed — recorded explicitly in "Out of scope — explicit handoffs".

No mitigations are proposed: every identified risk is already covered by an
existing enforced guard or resolved within this plan.

## Post-Review Changes

### Change Request 1 (2026-08-16 10:47)

- **Requested by user:** Two review findings. (a) `aidocs/implementation_trail_design.md:204`
  documented the constraint as `pattern: "\S"`, but the schema source must
  escape the backslash — a maintainer copying the documented form into JSON
  gets an invalid escape. (b) `trail_summary_text()`'s docstring still said
  "Until t1505_3 lands, `overview` is absent from the schema", which this task
  makes false.
- **Verified:** Both confirmed. `json.loads('{"pattern": "\S"}')` raises
  `JSONDecodeError: Invalid \escape` — the documented form does not merely
  yield the wrong regex, it fails to parse. Line 204 was the doc's only inline
  schema-regex literal, so no existing convention constrained the fix.
- **Changes made:** (a) §6 now reads `"pattern": "\\S"` and names the decoded
  regex `\S`, noting that a single backslash is not a legal JSON escape;
  round-trip verified — the documented literal parses to exactly the value
  stored in the schema and rejects whitespace-only. (b) The docstring's
  temporal sentence was replaced with the current truth: `overview` is optional,
  so the fallback stays live for any trail without one.
- **Files affected:** `aidocs/implementation_trail_design.md`,
  `.aitask-scripts/board/aitask_board.py`.

## Final Implementation Notes

- **Actual work done:** Exactly the planned change. `narrative.overview` added
  to both schema copies as an optional `type: string` with `minLength: 1` and
  `pattern: "\\S"`; `schema_version` const, `$id` and `narrative.required` left
  untouched; copies kept byte-identical by copying rather than double-editing.
  Seven new schema cases in a `NarrativeOverviewProperty` class
  (`tests/test_trail_schema.py`, 59 → 66 tests), one resolver case in
  `tests/test_board_bytrail_view.py` pinning whitespace-insignificance, and the
  §6 narrative bullet in `aidocs/implementation_trail_design.md`.
  `.aitask-scripts/lib/trail_schema.py` needed no change — confirmed, not
  assumed: `pattern` was already in `SUPPORTED_KEYWORDS` and the unknown-keyword
  `RuntimeError` tripwire never fired.

- **Deviations from plan:**
  - The plan said "no board change is in scope". That referred to *behavior*;
    a docstring in `.aitask-scripts/board/aitask_board.py:805` asserted
    `overview` was absent from the schema and became false the moment this
    change landed, so it was corrected in place. Zero behavior change. Two
    equivalent stale docstrings in `tests/test_board_bytrail_view.py` were
    corrected for the same reason. Final file count 6, not the planned 5.
  - Nothing else deviated; the schema JSON, the test matrix and the doc bullet
    all landed as designed.

- **Issues encountered:**
  - The verification pass found the plan's own checks unable to report the
    truth, and fixing them was most of the pre-implementation work: `bash` on a
    Python module always exits 2 regardless of the tests; the live-artifact
    `drift` check is unsatisfiable while t1508 is unstarted; and a
    `grep -c … # expect 0` absence check exits 1 on zero matches. The first
    replacement absence-check was *itself* unsatisfiable — the plan legitimately
    quotes the stale command in order to warn against it — so Verification
    step 0 was rewritten to use positive markers only.
  - A `5 passed in 13.53s` line was briefly misread as a narrowed collection.
    It is the **serial carve-out phase** (the three live-TUI modules); the
    combined verdict line is the only authoritative one, exactly as CLAUDE.md
    states. Runs with and without `--test-dir tests` produced identical results,
    so the narrowing was never a problem.

- **Key decisions:**
  - **`pattern: "\\S"` rather than bare `minLength: 1`.** The task's proposed
    description claimed renderers display `overview` "verbatim". Neither shipped
    renderer does, and the two disagree on the degenerate case:
    `trail_summary_text` treats whitespace-only as absent and falls back, while
    the detail modal's `line()` skips only exact `None/""/[]/{}"` and prints a
    labelled line with blank content. Closing that at the schema boundary makes
    the divergence unreachable (By-Trail fails closed on invalid documents)
    instead of documenting two behaviours. It cost nothing: a brand-new optional
    property invalidates no stored document, which is the only moment tightening
    is free.
  - **Accepted inconsistency:** this makes `overview` stricter than the 12
    legacy prose fields carrying bare `minLength: 1`. Those cannot be tightened
    without invalidating stored trails; a new field can be correct from the
    start.
  - **Contract prose qualified, not just tightened.** Trimming survives the
    pattern (`"  padded  "` is valid and renders trimmed), so the description
    and §6 say renderers display the field's *content* with surrounding
    whitespace insignificant — never "verbatim" — and a test pins it.
  - **Verification re-derived around t1508.** The real entry point is the
    `trail_schema.py validate` CLI against a 1.1.0 corpus fixture, not a live
    artifact. A negative control was run **before** the schema edit and
    correctly failed with
    `INVALID:$.narrative|additionalProperties|unknown key 'overview'`, proving
    the checks discriminate on this change.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t1505_4 (lite writer flow)** now has a schema slot to write into, but
    `.claude/skills/aitask-trail/SKILL.md.j2:199-200` still lists only
    `problem_statement, recommendation_summary, method_note` as the narrative
    the writer produces. That edit, plus its rendered variants across three
    profiles / three agents and the `tests/golden/skills/` regeneration, was
    deliberately left to t1505_4 so this task did not take on the
    rerender/goldens obligation. **Writers must not emit a whitespace-only
    `overview`** — it is now a hard validation failure
    (`INVALID:$.narrative.overview|pattern|…`), not a silently-ignored value.
  - **t1508 (live artifact refresh)** is unaffected by this change and still
    owns getting `art:trail-gates-framework-landing` and
    `art:trail-shadow-review-loop` off `1.0.0`. Until it lands, `drift` on
    either handle returns `ERROR:invalid_trail:1`; that is t1468_5's bump
    showing through, not a regression from this child.
  - **Fixture corpus** (`aidocs/implementation_trail_examples/*.json`) needed no
    change and still carries no `overview`, which is what keeps
    `test_absent_key_validates` a genuine back-compat control.
  - `drift --trail <path>` accepts a file path as well as an `art:` handle, but
    returns `ERROR:undriftable_input` for the corpus fixtures (their gather
    inputs are not re-derivable). For pure validation, use
    `python3 .aitask-scripts/lib/trail_schema.py validate <file>` — it prints
    `VALID:<trail_id>` or `INVALID:<path>|<rule>|<message>` and exits 0/1/2.
