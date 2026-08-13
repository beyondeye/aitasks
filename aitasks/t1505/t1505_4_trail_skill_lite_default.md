---
priority: high
effort: high
depends: [t1505_3]
issue_type: feature
status: Ready
labels: [skills, trails, artifacts, planning]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-08-13 12:28
updated_at: 2026-08-13 12:28
---

## Context

Parent: **t1505**. Read the parent plan
`aiplans/p1505_lite_trail_mode_and_trail_summary_pane.md`.

This child is the point of the whole parent task: make a trail cheap to produce,
by default, and print its summary at the end of the run so no board round-trip is
needed to decide what to pick next.

Depends on **t1505_3** (`narrative.overview`), and transitively on **t1468_5**,
which is editing this same template and its goldens right now.

## Why (measured)

The deterministic half is already fast — `aitask_trail_gather.sh drift` runs in
**0.85s**. Everything else is model-side analysis and JSON authoring, driven by a
427-line / 22KB template that mandates an evidence record per rationale, a
belt-and-braces `verifies` / `risk_mitigation_tasks` sweep on refresh, and
propose-and-confirm scope expansion.

The result is not proportional to trail size: `art:trail-shadow-review-loop` is
**138,879 bytes for 10 entries** — evidence 33.5KB + observations 28.5KB +
narrative 9.2KB. `art:trail-gates-framework-landing` is 166,868 bytes for 40.

Every one of those heavy sections — `observations`, `relations`, `exclusions` —
is **optional** in the schema, and the board reads them defensively
(`doc.get("observations") or []`). Lanes are built only from waves → entries →
`task`/`classification`/`snapshot`. So a lite trail is a first-class trail, not a
degraded one.

## Rebase check — FIRST step, before any edit

t1468_5 also edits `.claude/skills/aitask-trail/SKILL.md.j2` (to place
`followup_kind` into each generated `entry.snapshot`) and regoldens
`tests/golden/skills/aitask-trail/SKILL-*-claude.md`. Re-read the landed template
and goldens before editing. The lite contract below must **carry** t1468_5's
snapshot field, not drop it.

## Key files to modify

- `.claude/skills/aitask-trail/SKILL.md.j2` — the authoring template.
- `tests/golden/skills/aitask-trail/SKILL-*-claude.md` — regenerated, not
  hand-edited.
- `tests/test_trail_skill_contract.sh` — pins ~20 exact template phrases.

## Implementation plan

### 1. Depth selection

Step 0 (Parse Arguments) recognizes `--deep`. **Absence means lite** — lite is
the default for create and refresh, including the board's `R` key. Record the
depth in the document as `rendering_hints: {"depth": "lite"|"deep"}`.

`rendering_hints` already accepts this: its `additionalProperties` is
`{"type": ["string","number","boolean"]}`, so no schema edit is needed for the
marker. (t1505_1 reads it for the board's depth label.)

No launch plumbing is needed: `_launch_trail([...])` →
`ait codeagent invoke trail <args>` → `/aitask-trail <args>`
(`aitask_codeagent.sh:476`) already forwards free-form args.

### 2. The lite authoring contract

**Writes:** waves with `title` + `purpose`; entries with `classification`,
`confidence`, a complete `snapshot` (**including t1468_5's `followup_kind`
whenever the gatherer's `MEMBER:` record reports one**) and a short `rationale`;
`narrative.problem_statement` + `recommendation_summary` + **`overview`** (the
real prose answer — the thing the user actually reads) + `method_note`;
`evidence` = exactly the one gatherer-snapshot record (the schema requires
`minItems: 1`).

**Omits:** `observations`, `relations`, `exclusions`, per-entry `evidence_refs`.

**Skips:** the evidence-record-per-rationale requirement; the belt-and-braces
`verifies` / `risk_mitigation_tasks` sweep (deep only); propose-and-confirm scope
expansion — out-of-scope prerequisite work is **named in the `overview` prose**
instead of restarting the analysis over a new snapshot.

**Keeps, unchanged, at both depths:** exactly one artifact write per flow; the
non-skippable confirmation before it; pre-write validation via
`aitask_trail_gather.sh drift --trail <tmpfile>`; the refresh stale-base re-read
guard; the no-metadata-mutation invariant; the anti-fabrication rules. **Depth
changes how much is analyzed, never whether the write is confirmed.**

### 3. `overview` content

This is the deliverable the user judges the feature by. It should read like the
good conversational answer it replaces: which tasks to pick next and why, what
blocks what, what is in flight, what changed since last time — prose, not a
restatement of the wave table. The anti-fabrication rules still apply: no time
estimates, no progress claims, no commitments.

### 4. End-of-run print

After the `HANDLE:` line, print the summary **verbatim** — on create, on refresh,
and on `--show`. State the depth alongside it (`label_trail_depth`), so a lite
artifact is never mistaken for a deep one. This is what removes the board
round-trip from the loop.

### 5. Regenerate goldens in the same commit

```bash
./.aitask-scripts/aitask_skill_rerender.sh default
./.aitask-scripts/aitask_skill_rerender.sh fast
./.aitask-scripts/aitask_skill_rerender.sh remote
./.aitask-scripts/aitask_skill_verify.sh
```

One call per profile — the script takes a single profile name. **Stage the
rerender output by explicit path**: the sweep touches many generated targets, and
`git add -A` would pull in unrelated regenerated files.

### 6. Contract test

Update `tests/test_trail_skill_contract.sh` and add depth pins: that lite is the
default, that `--deep` restores the full analysis, and that the single-write
confirmation is stated on **both** depth paths.

## Post-phase (risk mitigations)

**`assert_lite_shape`.** An executable check that a `depth: lite` document really
carries no `observations`/`relations`/`exclusions` and exactly one `evidence`
record. Without it, "lite" is an aspiration expressed in prose to a model, with
nothing that fails when it is not honoured.

**`producer_test_both_depths` — the one that catches the silent regression.**
Phrase pins and `assert_lite_shape` **cannot** catch the failure that matters
here: t1468_5 makes `entry.snapshot.followup_kind` an **optional** property, so a
rewritten writer that quietly stops emitting it produces documents that are
schema-valid at both depths *and* pass the lite-shape check. The loss is invisible
to every other check in this task.

t1468_5 already builds the right test — its verification step 6: *"mark a fixture
task with a known `followup_kind`, generate/refresh a trail from it, and assert
the **stored** `entry.snapshot` contains that value. A schema-validity test alone
passes on an absent producer."* **Extend that existing test to run at both
depths** rather than writing a parallel one. It must fail if either the lite or
the deep writer drops the kind. Negative control: a fixture task with **no**
`followup_kind` asserts the field is then **absent**, not defaulted to some
placeholder.

## Verification steps

- `bash tests/test_trail_skill_contract.sh`
- `bash tests/test_skill_render_aitask_trail.sh`
- `bash tests/test_codeagent_trail.sh`
- `./.aitask-scripts/aitask_skill_verify.sh` clean.
- `bash tests/run_all_python_tests.sh` — read only the LAST line for the verdict.
- The both-depths producer test passes, and **is observed to fail** when the
  `followup_kind` emission is removed (a guard never seen failing is not a guard).
- **End-to-end, on a real task:** run `/aitask-trail <id>` with no depth flag.
  Confirm it completes materially faster than `--deep`; that the artifact
  validates (`aitask_trail_gather.sh drift --trail <new handle>`); that the
  summary is printed at the end of the run; and that the resulting trail renders
  correctly in the board's By-Trail view, including t1505_1's pane.
- Per CLAUDE.md, Codex CLI / OpenCode ports of this skill are a **separate
  follow-up task**, not part of this one — suggest it at completion.
