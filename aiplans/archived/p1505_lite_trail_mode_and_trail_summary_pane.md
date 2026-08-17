---
Task: t1505_lite_trail_mode_and_trail_summary_pane.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
Output branch: main
---

# t1505 — Lite trail mode and trail summary pane

## Context

`/aitask-trail` produces the right artifact and `ait board`'s By-Trail screen is
the right surface for "what lands next, and why", but a run is so expensive that
the feature goes unused. The same question gets asked conversationally instead
and answered in 1–2 minutes — with prose that is *easier to read* than the
structured trail. The conversational answer's only real defects are that it dies
with the agent session and that keeping an agent open to hold it costs hundreds
of MB.

Measured, in this repo:

| fact | value |
|---|---|
| `aitask_trail_gather.sh drift` | **0.85s** — the deterministic half is not the cost |
| `SKILL.md.j2` | 427 lines / 22KB of mandatory analysis instructions |
| `art:trail-gates-framework-landing` | 166,868 B — 8 waves, 40 entries, 19 obs, 56 evidence, 52 relations |
| `art:trail-shadow-review-loop` | 138,879 B for **10 entries** — evidence 33.5KB + observations 28.5KB + narrative 9.2KB |

All the latency is model-side analysis and JSON authoring, and the output size is
driven by sections that are *optional in the schema*.

Separately, `TrailDetailScreen._sections()` (`aitask_board.py:3858`) renders the
whole trail narrative **plus all 19 observations, all exclusions and all 56
evidence lines on every card**. The entry-specific part is a handful of lines;
everything after it is byte-identical card to card — the "wall of text we never
see one against the other".

**Intended outcome:** a fast trail flow that is the default, a free-form
non-binding prose summary carried in the trail data, and that summary visible
both at the end of a run and in a pane at the bottom of the By-Trail screen — so
"which task next?" is answerable without a board round-trip and without an agent
session held open.

## Decisions (confirmed with the user)

1. **Lite is the default**; the current heavyweight analysis stays available
   behind an explicit `--deep`.
2. **New optional `narrative.overview`** field, with the pane falling back to the
   already-required `narrative.recommendation_summary` when absent.
3. **Bottom pane: fixed small height + expand key** — always visible in By-Trail,
   scrollable in place, with a key that opens the full summary in a modal.
4. **Split into child tasks**, with the schema/skill children gated behind
   t1468_5.

## Coordination with t1468_5 (in flight — reshapes two of the four children)

**t1468_5** (`followup_kind remaining read surfaces`, status `Implementing`) is
editing the same trail surfaces right now, and it makes a decision this plan must
be rebased onto rather than contradict:

- It **bumps `schema_version` `const` to `"1.1.0"`** and sets
  `SCHEMA_NORMALIZATION_LOCK = {"1.1.0": "1.0.0"}` (`NORMALIZATION_VERSION` stays
  `1.0.0`). The trail is **single-version by design** — `load_schema` reads exactly
  one `const`, and `trail_gather.py:107-109` states the intent: *old-schema trails
  fail validation, never a false STALE*. Dual-accept was considered and rejected.
- It **accepts** that this invalidates every stored 1.0.0 trail until refreshed —
  both live artifacts and `implementation_trail_examples/cross_topic_multiple_trails.json`.
- It edits **both schema copies**, `trail_gather.py`'s `MEMBER:` record,
  `.claude/skills/aitask-trail/SKILL.md.j2`, and the goldens
  `tests/golden/skills/aitask-trail/SKILL-*-claude.md`.

**Consequences for this task** (this corrects a premise the exploration reached
before t1468_5 was in view):

- The rule for t1505 is **not** "never bump the const" — that bump is t1468_5's,
  already decided and justified. t1505 adds an **additive property on top of
  1.1.0** and does not bump again.
- The `recommendation_summary` fallback is still worth having, but **not** for the
  reason originally given: after t1468_5 the two live artifacts are invalid until
  refreshed, so the fallback is not a no-migration story for them. It earns its
  place by covering any deep-flow trail written without an `overview`.
- **Schema and skill children must wait for t1468_5** (same files, same goldens).
  The two board children touch only `aitask_board.py`'s trail UI, which t1468_5
  does not edit — its three surfaces are the work report, minimonitor/applink and
  the trail schema/gatherer/skill — so they proceed independently and are
  sequenced first.

## Hard constraints

- **Do not bump `schema_version` again.** After t1468_5 the const is `"1.1.0"`;
  the new field is additive and **not** added to `narrative.required`, so no
  further bump and no further invalidation of stored trails.
- **The pane must not be docked.** On the board's main screen the only docked
  widgets are `Header` (top) and `MultiRowFooter`, which inherits `dock: bottom`
  from Textual's `Footer` and never unsets it. The board's own CSS comment at
  `aitask_board.py:7362` records t1278: two same-edge docked siblings land at the
  **same offset** and one silently paints over the other while both still report
  `display=True`, `visible=True` and a correct region. The pane is a normal flow
  child yielded after `#board_container`.
- **The summary is advisory.** No consumer may derive membership, ordering or
  classification from it. Waves/entries stay the binding structure.
- **A lite trail must render identically to a full one in By-Trail** — the board
  reads `observations`/`exclusions` defensively (`doc.get(...) or []`) and lanes
  are built only from waves → entries → `task`/`classification`/`snapshot`. This
  has to be pinned by a test, not assumed.

## Decomposition — 4 children

Ordered so the **unblocked** board work runs first and the t1468_5-blocked
schema/skill work follows:

| child | surface | depends |
|---|---|---|
| t1505_1 | By-Trail summary pane (riskiest) | — |
| t1505_2 | Detail-modal wall-of-text fix + design §9/§15 | t1505_1 (same file) |
| t1505_3 | `narrative.overview` schema field + design §6 | **t1468_5** |
| t1505_4 | Skill: lite by default, `--deep`, end-of-run print | t1505_3 |

t1505_1 is written to prefer `narrative.overview` and fall back to
`recommendation_summary`, so it is correct both before and after t1505_3 lands —
reading an absent key is just the fallback path, not a failure.

### t1505_1 — By-Trail summary pane (riskiest surface — spike first, unblocked)
Textual layout work with a documented failure mode that is invisible to
`display`/`visible` assertions.

- Pure resolver, import-testable, next to the other trail helpers:
  `trail_summary_text(doc) -> str` — `narrative.overview` when non-empty, else
  `narrative.recommendation_summary`, else `""`.
- `TrailSummaryPane` (a `VerticalScroll` holding a `Static`), id `#trail_summary`,
  yielded in `AitaskBoard.compose()` (`aitask_board.py:7964`) **after**
  `#board_container` and **before** the footer. CSS: fixed `height` (~6 rows) and
  a top border; **never `dock: bottom`**.
- Visibility: `display = (base_filter == "bytrail" and summary text is non-empty)`.
  Driven from the same seam that already owns view state (`refresh_board`'s
  `bytrail` branch / `_render_bytrail` / `_refresh_subtitle`), so leaving By-Trail
  restores the full-height column area — the same single-writer discipline
  `_refresh_subtitle` documents.
- `Binding("v", "trail_summary_expand", "Summary")` — `v` and `u` are free at App
  level (the ones at `aitask_board.py:5819`/`5833` belong to the `board.detail`
  scope). Gated in `check_action` to By-Trail with a non-empty summary, and
  **re-checked inside `action_trail_summary_expand`** (a binding gate is not an
  action guard). Key resolved through `resolve_key("board", …)` like the other
  trail actions.
- Modal `TrailSummaryScreen` renders the full text scrollable, `escape` to close.
- Inline mitigation `label_trail_depth`: show the trail's depth
  (`rendering_hints.depth`) on the trail banner/selector, so a lite artifact is
  never mistaken for a deep one. Absent hint → render nothing, not "deep".
- Tests (`tests/test_board_bytrail_view.py`, extending `ByTrailTestBase`):
  resolver unit tests incl. the fallback and the empty case; a pilot test that the
  pane is present in By-Trail and absent in `all`/`bytopic`; a **render-level**
  assertion that the footer's first row is still composited and readable with the
  pane mounted at a small terminal size (the docked-sibling collision cannot be
  caught by `display`/`visible`); an expand-key test incl. the negative control
  that `v` does nothing outside By-Trail.

### t1505_2 — detail modal wall-of-text fix + docs  *(unblocked; depends on t1505_1, same file)*
- Restructure `TrailDetailScreen._sections()` (`aitask_board.py:3858`) so the
  focused entry leads and the trail-global bulk no longer repeats on every card:
  entry → its wave → drift reasons for *this* entry → trail narrative (including
  `overview`) → only the observations whose `affects` names this entry, and only
  the evidence its `evidence_refs` resolve to, each with a count of what was
  withheld and a key to show everything.
- A lite trail has no observations/evidence beyond the one gatherer record — the
  modal must read as complete, not broken, in that case (an empty section that
  silently renders nothing reads as a bug).
- Design doc §9 (By-Trail view: the new pane + the modal's entry-first
  projection) and §15 (wireframes).

### t1505_3 — `narrative.overview` schema field  *(depends on t1468_5)*
Foundation for the skill. Small and low-risk, but it edits the two files t1468_5
is currently rewriting, so it must land after it.

- **Rebase check before editing** (t1468_5 will have moved these files): re-read
  both schema copies and `test_trail_schema.py`'s `test_wrong_schema_version`
  first, confirm the const is `1.1.0` and the two copies still `diff`-clean, and
  add the property on top of that state rather than the state described here.
- Add to `narrative.properties` in **`aidocs/implementation_trail.schema.json`**
  (the canonical copy):

  ```json
  "overview": {
    "description": "Free-form prose summary of the findings and the motivation for the proposed wave/task order. Advisory and NON-BINDING: renderers display it verbatim; no consumer derives membership, ordering or classification from it.",
    "type": "string",
    "minLength": 1
  }
  ```

  Not added to `narrative.required`. `schema_version` const left at whatever
  t1468_5 established (`"1.1.0"`) — **not** bumped again.
- Copy **byte-identically** to `.aitask-scripts/lib/implementation_trail.schema.json`
  — `tests/test_trail_schema.py:63` pins the two files to byte equality.
- No `trail_schema.py` interpreter change: `type` and `minLength` are already in
  `SUPPORTED_KEYWORDS`. Confirm rather than assume — an unsupported keyword is a
  `RuntimeError` tripwire by design.
- Tests in `tests/test_trail_schema.py`: doc **with** `overview` validates; doc
  **without** it validates (back-compat, the load-bearing case); `overview: ""`
  fails `minLength`; `overview: 123` fails `type`. Each assertion names the
  expected failing path/rule rather than just "invalid".
- Verify through the real entry point:
  `./.aitask-scripts/aitask_trail_gather.sh drift --trail <handle>` — expect a
  `CURRENT`/`STALE` verdict, never `ERROR:invalid_trail`. Note that t1468_5 already
  requires a refresh of the two stored trails; a trail still at 1.0.0 is *expected*
  to be rejected, and that rejection is not this child's regression.
- Design doc §6 (schema walkthrough) documents the field and its advisory status.
- `aidocs/implementation_trail_examples/*.json` need no change **for this field**
  (additive); t1468_5 separately regenerates `cross_topic_multiple_trails.json` for
  its bump. `test_implementation_trail_design.py` pins no narrative property set,
  so nothing there needs relaxing.

### t1505_4 — skill: lite by default, `--deep`, end-of-run print  *(depends on t1505_3, transitively on t1468_5)*
- **Rebase check before editing:** t1468_5 also edits `SKILL.md.j2` (to place
  `followup_kind` into each generated `entry.snapshot`) and regoldens
  `tests/golden/skills/aitask-trail/SKILL-*-claude.md`. Re-read the landed template
  and goldens first; the lite contract below must carry t1468_5's snapshot field,
  not drop it.
- `SKILL.md.j2` Step 0 recognizes `--deep`; **absence means lite**. The depth is
  recorded as `rendering_hints: {"depth": "lite"|"deep"}` — already legal
  (`rendering_hints` has schema-valued `additionalProperties: {string|number|boolean}`),
  so this needs no schema edit.
- **Lite authoring contract** (what it writes): waves with `title`/`purpose`;
  entries with `classification`, `confidence`, complete `snapshot` (including
  t1468_5's `followup_kind` when the gatherer reports one), and a short
  `rationale`; `narrative.problem_statement` + `recommendation_summary` +
  **`overview`** (the real prose answer) + `method_note`; `evidence` = exactly the
  one gatherer-snapshot record. **Omitted:** `observations`, `relations`,
  `exclusions`, and per-entry `evidence_refs`.
- **Lite skips:** the evidence-record-per-rationale requirement, the
  belt-and-braces `verifies` / `risk_mitigation_tasks` sweep (deep only), and
  propose-and-confirm scope expansion — out-of-scope prerequisites are *named in
  the `overview` prose* instead of restarting the analysis.
- **Lite keeps, unchanged:** exactly one artifact write per flow, the
  non-skippable confirmation before it, pre-write `drift --trail <tmpfile>`
  validation, the refresh stale-base re-read guard, the no-metadata-mutation
  invariant, and the anti-fabrication rules. Depth changes how much is analyzed,
  never whether the write is confirmed.
- **End-of-run print:** after the `HANDLE:` line, print the summary verbatim — on
  create, refresh **and** `--show`, so "what should I pick next?" is answered in
  the run's own output. State the depth alongside it (`label_trail_depth`).
- Board launch needs no plumbing: `_launch_trail([...])` →
  `ait codeagent invoke trail <args>` → `/aitask-trail <args>` already forwards
  free-form args (`aitask_codeagent.sh:476`).
- Regenerate goldens in the same commit:
  `./.aitask-scripts/aitask_skill_rerender.sh <profile>` for **each** of `default`,
  `fast`, `remote` (one profile per call), then
  `./.aitask-scripts/aitask_skill_verify.sh`. Stage the rerender output by explicit
  path — the sweep touches many generated targets.
- Update `tests/test_trail_skill_contract.sh` (it pins ~20 exact template phrases)
  and add pins for the depth contract: that lite is the default, that `--deep`
  restores the full analysis, and that the single-write confirmation is stated on
  **both** depth paths.
- **Producer test — both depths (NON-OPTIONAL).** Template-phrase pins and
  `assert_lite_shape` **cannot** catch the failure that matters here:
  t1468_5 makes `entry.snapshot.followup_kind` an **optional** property, so a
  rewritten writer that silently stops emitting it produces trails that are
  schema-valid at both depths *and* pass the lite-shape check. The absence is
  invisible to every check listed above.

  t1468_5 already builds exactly the right test (its verification step 6: "mark a
  fixture task with a known `followup_kind`, generate/refresh a trail from it, and
  assert the **stored** `entry.snapshot` contains that value. A schema-validity
  test alone passes on an absent producer"). **Extend that existing test to run at
  both depths** — do not write a parallel one. It must fail if either the lite or
  the deep writer drops the kind, and the negative control is a fixture task whose
  kind is absent, asserting the field is then absent rather than defaulted.
- Per CLAUDE.md, the Codex/OpenCode ports are a separate follow-up, not this task.

**Manual-verification sibling:** offered after the child plans are committed —
this is TUI-heavy work whose real acceptance (pane visible, footer intact, expand
key, modal readability at narrow widths) only a human can judge.

**It must supply its own trail.** t1468_5 deliberately invalidates both stored
artifacts until they are refreshed to 1.1.0, and the task that owns that refresh
is **t1468_7** (`manual_verification`, `verifies: [1468_3, 1468_4, 1468_5]`,
`depends: [t1468_6]`) — its checklist item reads "…report a clean invalid-trail
error (not a confusing STALE), and refresh successfully to 1.1.0". If t1505's
live acceptance simply opens By-Trail on the pre-existing handles before t1468_7
has run, it sees the fail-closed error card and reads as a t1505 defect when it is
not one. So:

- **Item 1 of the MV sibling generates a fresh trail** with the new lite flow on a
  real task, and every subsequent live check runs against *that* handle. This is
  self-supplying (no hard dependency on another task's schedule) and is strictly
  the better test: it exercises the new default path end-to-end and produces a
  1.1.0 artifact carrying an `overview`, which is exactly what the pane needs.
- **Coordination note, recorded in the MV task:** an `ERROR:invalid_trail` on
  `art:trail-gates-framework-landing` / `art:trail-shadow-review-loop` before
  t1468_7 runs is **expected**, not a t1505 regression — the same carve-out
  t1468_5 already wrote for t1470. Checks against those two handles are deferred
  until t1468_7 has refreshed them.
- Rejected alternative: making the MV sibling `depends: [1468_7]`. It would work,
  but it serializes t1505's completion behind an unrelated manual-verification
  chain (t1468_6 → t1468_7) for a dependency the self-supplying step removes
  entirely. Say the word and it becomes a hard dependency instead.

## Risk

Levels below are the **reassessed** ones, describing the plan *with* the four
confirmed inline mitigations and the t1468_5 sequencing incorporated.

### Code-health risk: medium
- The bottom pane adds a second flow child to the board's top-level `compose()`,
  which has one documented same-edge dock collision in its history (t1278); a
  wrong placement or a stray `dock:` is invisible to `display`/`visible`
  assertions and would silently eat the footer · severity: medium · → mitigation: inline pre-phase characterize_board_compose_layout
- `TrailDetailScreen._sections()` is edited while `tests/test_board_bytrail_view.py`
  (3,335 lines) pins current modal content; a restructure risks weakening rather
  than re-pointing those assertions · severity: medium · → mitigation: inline post-phase modal_assertion_tripwire
- Two copies of the schema must stay byte-identical, and the validator's
  interpreter raises on any keyword it does not know · severity: low · → mitigation: covered by the existing byte-equality pin (`tests/test_trail_schema.py:63`)
- Blast radius stays wide (schema ×2, validator, board ×2 surfaces, skill template
  + a generated-goldens sweep across three profiles), which is why the level stays
  `medium` even with the guards above · severity: medium · → mitigation: the 4-child split; each child lands and is reviewed independently

### Goal-achievement risk: medium
- "Lite" is defined by *instructions to a model*, not by a mechanism — nothing
  structurally prevents a lite run from doing the full analysis anyway. The inline
  check makes the *artifact shape* verifiable, but not the run's latency, so the
  residual risk is real and bounded rather than eliminated · severity: medium · → mitigation: inline post-phase assert_lite_shape
- Making lite the default silently changes what every existing invocation path
  produces, including the board's `R` key · severity: medium · → mitigation: inline pre-phase label_trail_depth
- Two children are gated on an in-flight task (t1468_5) whose schema/skill edits
  are not yet landed; their plans describe a pre-t1468_5 codebase and must be
  re-read against the landed state before editing · severity: medium · → mitigation: the explicit "rebase check before editing" first step in t1505_3 and t1505_4
- Rewriting the skill writer can silently drop `entry.snapshot.followup_kind`:
  the field is optional, so both depths stay schema-valid and `assert_lite_shape`
  still passes — the loss is invisible to every phrase- and shape-level check · severity: high · → mitigation: inline post-phase producer_test_both_depths
- The plan's live acceptance depends on usable trail artifacts, which t1468_5
  deliberately invalidates until t1468_7 refreshes them; a fixture-backed board
  test would pass while the real path is broken · severity: medium · → mitigation: inline post-phase self_supplying_live_trail

### Planned mitigations
- timing: pre-phase | name: characterize_board_compose_layout | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — silent footer collision when the pane is mounted | desc: In t1505_1, before mounting the pane, pin the footer's composited first row at a small terminal size so a dock/layout regression fails loudly.
- timing: pre-phase | name: label_trail_depth | type: feature | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a silent default change | desc: State the trail's depth on the board's banner/selector (t1505_1) and in the end-of-run output (t1505_4) so a lite artifact is never mistaken for a deep one.
- timing: post-phase | name: assert_lite_shape | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — "lite" is unenforced instructions | desc: In t1505_4, an executable check that a `depth: lite` document carries no observations/relations/exclusions and exactly one evidence record.
- timing: post-phase | name: modal_assertion_tripwire | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — re-pointed modal assertions could be silently undone | desc: In t1505_2, a tripwire that fails if the trail-global sections regress to rendering on every card.
- timing: post-phase | name: producer_test_both_depths | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a rewritten writer can silently drop the optional followup_kind at either depth | desc: In t1505_4, extend t1468_5's fixture-backed end-to-end producer test to run at both lite and deep, asserting the STORED entry.snapshot retains a known followup_kind, with an absent-kind negative control.
- timing: post-phase | name: self_supplying_live_trail | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — live acceptance needs a valid artifact t1468_5 invalidated | desc: Make the MV sibling's first item generate a fresh 1.1.0 trail via the new lite flow and run every live check against that handle, with a recorded carve-out that a pre-t1468_7 invalid-trail error on the two stored handles is expected.

Each inline mitigation is written into the named child's plan as an explicit
`### Pre-phase (risk mitigations)` / `### Post-phase (risk mitigations)` step
block when the child plans are authored. No mitigation tasks are spawned, so no
blocking edge is added to the parent.

## Verification

- `bash tests/test_trail_schema.py`; the board/trail Python modules via
  `bash tests/run_all_python_tests.sh --test-dir tests` — read only the **last**
  line (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); piping discards the
  status, so use `pipefail` or `${PIPESTATUS[0]}`.
- `bash tests/test_trail_skill_contract.sh`, `bash tests/test_skill_render_aitask_trail.sh`,
  `bash tests/test_codeagent_trail.sh`.
- The both-depths producer test (t1468_5's fixture test extended): a task with a
  known `followup_kind` still has it in the **stored** `entry.snapshot` after a
  lite run *and* after a `--deep` run.
- **Live acceptance runs against a freshly generated trail, not the two stored
  handles.** Run `/aitask-trail <task>` with no depth flag first; confirm it
  completes materially faster than `--deep`, that the artifact validates
  (`aitask_trail_gather.sh drift --trail <new handle>`), and that the summary is
  printed at the end of the run. Then, in a real terminal, open By-Trail (`z`) on
  **that** handle and confirm the pane renders below the columns with the footer
  fully visible, `v` opens the expand modal, and a card's modal is entry-led
  rather than a wall of text.
- The pre-existing `art:trail-gates-framework-landing` /
  `art:trail-shadow-review-loop` are checked **only after t1468_7** has refreshed
  them to 1.1.0; before that, their `ERROR:invalid_trail` is the expected outcome
  of t1468_5's bump and must not be recorded as a t1505 failure.
- `shellcheck .aitask-scripts/aitask_*.sh`.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.
