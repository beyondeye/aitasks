---
Task: t1666_document_artifacts_xdeps_fields_and_fix_issue_type_vocabular.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1666 — Document `artifacts`/`xdeps` fields and fix the `issue_type` vocabulary

## Context

The task frontmatter schema has grown past what the canonical website reference
records, and the `issue_type` vocabulary is spelled out by hand in a dozen
places that have drifted apart.

Review of the first draft raised three blocking concerns. All three were
verified and are valid; one of them exposed a **fourth undocumented field** the
task's own exploration missed. What follows is the corrected plan.

### Finding A — four fields are undocumented, not three

Deriving the field set from the **writers** rather than the corpus:

| source | fields |
|---|---|
| `aitask_update.sh` / `aitask_create.sh` `echo "<field>: "` emissions | 36 |
| `aitask_archive.sh` | `completed_at` |
| `frontmatter_patch.py` callers (`ait artifact`, `ait attach`) | `artifacts`, `attachments` |

Union = 40 writable fields, minus the draft-envelope keys `draft` / `parent`
that `aitask_create.sh` writes into `aitasks/new/` and that never reach a task
file. Diffed against the 36 rows in `task-format.md`:

- **writable but undocumented:** `artifacts`, `xdeprepo`, `xdeps`, **`attachments`**
- **documented but no writer:** *none*

`attachments` is written by `ait attach add`, has **zero instances on disk**, and
appears nowhere in `website/content/docs`. It is the exact fail-open the task
warned about, sitting in the repo today: a corpus-derived guard is green while
the table is already wrong. It also falsifies the task's claim that `artifacts`
is "the header's only nested field" — there are two nested fields.

### Finding B — `manual_verification` was added to `task_types.txt` without propagation

Both `aitasks/metadata/task_types.txt` and `seed/task_types.txt` ship 10 types;
every enumerating doc/skill site still lists 9, and two list 8.
`task-format.md` is self-contradictory as a result: its `followup_kind` row
requires `issue_type: manual_verification`, a value its `issue_type` row says
does not exist. `aidocs/issue_type_vocabulary_duplication.md` already documents
the propagation checklist that was skipped.

### Finding C — the `-remote-` rendered closures are tracked

The first draft asserted all `*-/` variants are gitignored. `.gitignore:55`
does ignore `.claude/skills/*-/`, but **`-remote-` closures are committed
anyway** across all three agent trees (tracked files override gitignore).
Six tracked rendered files carry the enumeration:

```
.claude/skills/task-workflow-remote-/{SKILL.md,task-creation-batch.md}
.agents/skills/task-workflow-remote-codex-/{SKILL.md,task-creation-batch.md}
.opencode/skills/task-workflow-remote-/{SKILL.md,task-creation-batch.md}
```

Editing only `.claude/skills/task-workflow/` would ship a stale enumerating
surface and miss the acceptance criterion. `-default-` / `-fast-` genuinely are
gitignored.

## Decisions taken (the task asked for these explicitly)

- **`manual_verification:` is NOT a valid commit-message type.** Evidence: 0 of
  the last 3000 commits use it; `manual-verification.md` commits its own state
  as `ait: Record verification state for t<id>`; any code change a failed
  checklist item triggers lands on a spawned follow-up under that follow-up's
  own type. Commit-type sites stay 9-valued **with the reason stated in place**.
- **Workflow-written flags stay undocumented, as a recorded policy.**
  `--active-gates`, `--active-gates-profile`, `--clear-active-gates`,
  `--plan-approved-at`, `--risk-code-health`, `--risk-goal-achievement`,
  `--risk-mitigation-tasks` are the complete set absent site-wide (verified by
  diffing `ait create/update --help` against `website/content/docs`). Their
  *fields* are already documented and marked "Framework-derived — never
  hand-edit" / "Written and cleared by the workflow only", so the flags are
  internal write surfaces with no user-facing contract. One sentence in
  `task-format.md` will say so. Contrast `--verification-baseline` and
  `--boardgroup`, which **are** named inside their field rows because a human
  may legitimately set them — that existing convention is what makes the
  omission deliberate rather than accidental.
- **A guard lands with this change, not as a follow-up**, and its field source
  of truth is the **writers**, not the corpus (Finding A).

## Scope note (no silent AC deviation)

The task's ACs name three fields. This plan documents **four** — `attachments`
is added because the writer-derived guard would otherwise fail on correct
state, and because it is genuinely undocumented. The `artifacts`-is-the-only-
nested-field claim in the task body is corrected in passing.

## Three expected sets, all derived from one file

Every enumerating site is classified against `aitasks/metadata/task_types.txt`:

| class | set | why |
|---|---|---|
| `FULL` | all 10 | mirrors the vocabulary |
| `NO_MV` | 10 − `manual_verification` (9) | commit types, and wrap's suggestion list — a wrap always describes committed code changes |
| `DETECTED` | 8 (`FULL` − `manual_verification` − `enhancement`) | `github_detect_type()` maps issue labels to only these; it can never emit `enhancement` either |

## Changes

### Pre-phase (risk mitigations)

**`baseline_generated_surfaces`** — before touching any source, run the golden
regeneration, `aitask_skill_rerender.sh` for all three profiles, and the three
instruction-mirror regenerations **with no source edit**, and confirm each
produces a zero diff. This separates "my vocabulary edit changed this generated
file" from "this generated file was already stale", so the review diff is
readable as a pure consequence of the source edit. A non-empty baseline diff is
a stop-and-report, not something to fold into this task's commit.

### 1. `website/content/docs/development/task-format.md`

- Add **four** rows to the Frontmatter Fields table:
  - `xdeprepo` / `xdeps` — set by `--xdeprepo` / `--xdeps` on both `ait create`
    and `ait update`; `xdeps` requires `xdeprepo`. Link to
    `{{< relref "/docs/workflows/cross_project_dependencies" >}}`.
  - `artifacts` — nested list of mappings, written by `ait artifact`. Entry keys
    are **`handle`, `kind`, and optional `name`** only
    (`.aitask-scripts/aitask_artifact.sh:270`) — *not* the full nine-key
    `FIELD_ORDER` in `frontmatter_patch.py:47`, which is a shared emission
    ordering across both nested fields.
  - `attachments` — nested list of mappings, written by `ait attach add`. Entry
    keys `hash`, `name`, `mime`, `size`, `added_at`, `backend`
    (`aitask_attach.sh:270`).
- Because the table is otherwise flat-scalar/flat-list shaped, add **one worked
  YAML example below the table** covering both nested fields, rather than
  cramming a block into a cell.
- `issue_type` row → `FULL`. This also removes the self-contradiction with the
  `followup_kind` row; no edit to that row needed.
- Add `--also-blocks-dependents` to the `also_blocks_dependents` row (the row
  exists; only the flag was missing).
- Fix the **Customizing Task Types** fenced block near the end of the file: it
  lists **8** defaults, missing both `enhancement` and `manual_verification`.
  → `FULL`.
- Add the one-sentence workflow-written-flag policy near the framework-derived
  field rows.

### 2. Remaining website pages

| file | site | class |
|---|---|---|
| `commands/task-management.md:19` | create interactive "Issue type" bullet | `FULL` |
| `commands/task-management.md` create + update flag tables | add `--also-blocks-dependents` row to both | — |
| `tuis/board/how-to.md:158` | "Type:" cycle-field defaults | `FULL` |
| `tuis/board/reference.md:449` | `issue_type` editable-field row | `FULL` |
| `workflows/issue-tracker.md:14` | label auto-detection list | `DETECTED` — **remove `enhancement`**, do not add `manual_verification`; reword to name the `feature` fallback |

### 3. `concepts/tasks.md`

It already links to the full table, so only the 8-field snapshot needs work:
replace the enumeration with a characterisation of the schema plus the existing
relref, so it cannot go stale again.

### 4. Agent-instruction surfaces

- `seed/aitasks_agent_instructions.seed.md` — frontmatter YAML `issue_type:`
  line → `FULL`; commit-type paragraph → `NO_MV` + reason sentence.
- Regenerate the three generated mirrors (`AGENTS.md`, `.codex/instructions.md`,
  `.opencode/instructions.md`) by **driving the generator**, per
  `aidocs/framework/aitasks_extension_points.md` — never by copying from
  `AGENTS.md`, which carries the shared layer only and would destroy each
  mirror's per-agent tail:
  ```bash
  source .aitask-scripts/aitask_setup.sh --source-only
  content="$(assemble_aitasks_instructions . codex)"
  insert_aitasks_instructions .codex/instructions.md "$content"
  # …same for opencode; AGENTS.md via update_agentsmd
  ```
- `CLAUDE.md:139` → `FULL`; `CLAUDE.md:208` → `NO_MV` + the same reason sentence.
  Hand-maintained — edit directly, never regenerate.

### 5. Skill sources **and the tracked `-remote-` closures** (Finding C)

Hand-edited sources:

| file | class |
|---|---|
| `.claude/skills/task-workflow/SKILL.md:704` (commit rule) | `NO_MV` + reason |
| `.claude/skills/task-workflow/task-creation-batch.md:14` | `FULL` |
| `.claude/skills/aitask-wrap/SKILL.md.j2:77` | `NO_MV` + reason |
| `.claude/skills/aitask-docs-gap/SKILL.md:75` | `FULL` |
| `.claude/skills/aitask-changelog/SKILL.md:57` | `FULL` (currently 8 — also missing `enhancement`) |

`docs-gap` and `changelog` both describe values `aitask_changelog.sh --gather`
can emit for an archived task, so an archived `manual_verification` task makes
them `FULL`.

Then, in the **same commit**:

1. `./.aitask-scripts/aitask_skill_rerender.sh <profile>` for `default`, `fast`
   and `remote` (it takes a profile argument — a bare call is wrong). The
   `remote` pass is what refreshes the six tracked closure files.
2. Regenerate `tests/golden/procs/task-workflow/` and
   `tests/golden/skills/aitask-wrap/` via
   `.aitask-scripts/lib/skill_template.py`, per
   `aidocs/framework/skill_authoring_conventions.md`.
3. Review both diffs — they must contain only vocabulary lines.

Completeness check, over **tracked files only**:

```bash
git ls-files | xargs grep -ln 'enhancement`, `chore\|chore, documentation' 2>/dev/null
```

### 6. New guard — `tests/test_docs_vocabulary_coverage.sh`

Self-contained, `tests/lib/asserts.sh` helpers, PASS/FAIL footer. Test bodies
stay out of `( … )` subshells, so the file-backed counters are not needed.

- **A. Vocabulary sync.** `seed/task_types.txt` ≡ `aitasks/metadata/task_types.txt`.

- **B. Per-site enumeration — extract, then compare sets** (addresses the
  review's second concern). A naive "no excluded member appears anywhere in the
  slice" assertion is unusable here: every `NO_MV` site must *state why*
  `manual_verification` is excluded, so the rationale sentence contains the
  excluded identifier and would fail a correct document. Instead each `SITES`
  row declares `path | anchor | shape | class`, and the check **extracts the
  enumeration span itself** before comparing:

  | shape | extraction |
  |---|---|
  | `pipe` | text after `issue_type: ` to EOL, split on `\|` |
  | `table_cell` | the row's second `\|`-delimited cell, split on `,`, strip backticks |
  | `backtick_list` | the maximal run of `` `word` `` items joined by `, ` / `, or `, split |
  | `plain_paren` | text inside the `( … )`, split on `,` |
  | `fenced_lines` | the fenced block under the anchor, one value per line |

  Compare the extracted **set** to the expected set in **both directions**
  (nothing missing, nothing extra). Prose outside the captured span — including
  the rationale sentence — is invisible to the assertion, so correct wording
  passes and the check still cannot be satisfied by merely mentioning a value
  nearby.

- **C. Anchor tripwire.** Each anchor must match **exactly one** location, and
  each extraction must yield a non-empty set, else fail loudly. Without both, a
  renamed heading or a reworded list silently reduces the guard to checking
  nothing.

- **D. Field coverage — writer-derived, bidirectional** (addresses the review's
  first concern). Build the required set from the writers, exactly as in
  Finding A: `echo "<field>: "` emissions in `aitask_update.sh` and
  `aitask_create.sh`, plus `completed_at` from `aitask_archive.sh`, plus the
  field argument passed to `frontmatter_patch.py` by its callers
  (`ait artifact`, `ait attach`). Subtract the named draft-envelope keys
  `draft` / `parent`, each with its reason recorded in the test. Assert the
  writer set and the table's row set are **equal**. The corpus scan over
  `aitasks/**/*.md` stays, demoted to supplemental evidence: a key on disk that
  no writer emits is reported as a distinct diagnostic (hand-edited or
  retired field) rather than silently ignored.

  Bidirectional equality is safe here and one-way was not: measured today,
  `documented but no writer` is empty. `attachments` — the zero-instance
  field — is what makes the writer source strictly stronger than the corpus.

- **Negative controls** for A–D, driven through a temp fixture copy: drop a
  value from one site, rename an anchor, reword a list so extraction yields
  empty, add a writer emission for a field with no table row, and delete a
  table row for a zero-instance field (`attachments` — the explicit
  zero-instance case the review asked for). Each must flip its assertion to
  FAIL before the fixture is restored.

**What this guard does not buy** — stated in the test header and in
`aidocs/issue_type_vocabulary_duplication.md`: D sees a field only once a
**writer** exists for it. A field written by a path the extraction does not
know about (a new script, or a caller of `frontmatter_patch.py` added later) is
still invisible. That residual gap is narrowed, not closed, by asserting the
set of `frontmatter_patch.py` callers is itself the one the test expects — so a
new caller fails the guard rather than slipping past it.

### 7. `aidocs/issue_type_vocabulary_duplication.md`

Refresh the checklist to match reality: mark `-default-` / `-fast-` trees as
gitignored **and `-remote-` as tracked** (Finding C), add the goldens, add
`aitask-docs-gap` and `aitask-changelog`, record the three classes and why
`NO_MV` / `DETECTED` exist, and point at the new guard as the enforcement
mechanism.

## Verification

1. `bash tests/test_docs_vocabulary_coverage.sh` — green, with each negative
   control demonstrated to fail before the fixture is restored.
2. `bash tests/test_agent_instructions.sh` — T25–T27 pin the three generated
   mirrors byte-for-byte against the live seed.
3. `bash tests/test_skill_render_task_workflow.sh` and
   `bash tests/test_skill_render_aitask_wrap.sh` — golden equality after regen.
4. `./.aitask-scripts/aitask_skill_verify.sh`
5. `cd website && hugo build --gc --minify` — and, because a dead `#fragment`
   does **not** fail the build, check any new/changed relref anchor by hand
   against the rendered `id=` (Hugo `--minify` unquotes ids).
6. `git ls-files | xargs grep -ln …` (change 5) returns only files carrying a
   deliberately non-`FULL` class.

## Risk

### Code-health risk: medium
- Wide blast radius across generated surfaces — 12 tracked goldens, 6 tracked
  `-remote-` closure files, 3 generated instruction mirrors. A regeneration that
  sweeps in pre-existing drift would make the commit unreviewable. · severity:
  medium · → mitigation: inline pre-phase `baseline_generated_surfaces`
- The guard could pass vacuously (a renamed heading, or a reworded list whose
  extraction yields empty) or be over-tight against legitimate rationale prose.
  · severity: medium · → mitigation: inline post-phase
  `guard_tripwire_and_negative_controls`
- Every other edit is prose in documentation, skill, and seed files with no
  runtime behaviour; the only executable artifact added is the guard.
  · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- Every finding was re-verified against the live repo during planning, and the
  verification found four sites and one field the task text missed, so coverage
  is established rather than assumed. Both open decisions were answered by the
  user, and the three review concerns are addressed above. · severity: low ·
  → mitigation: none needed

### Planned mitigations
- timing: pre-phase | name: baseline_generated_surfaces | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: generated-surface blast radius | desc: Regenerate goldens, all three rerender profiles and the three mirrors with no source edit and confirm a zero diff before editing anything.
- timing: post-phase | name: guard_tripwire_and_negative_controls | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: guard vacuity | desc: Prove each guard assertion can fail via a temp-fixture negative control, including the zero-instance field case, and that every anchor matches exactly one location.

Both are **inline** dispositions — steps of this plan, not spawned tasks — so
approving this plan confirms them and nothing is created.

### Post-phase (risk mitigations)

**`guard_tripwire_and_negative_controls`** — the negative-control and
anchor-tripwire work described in change 6; run it last, after the guard is
green, and demonstrate each assertion flipping to FAIL before restoring the
fixture.

## Step 9

Post-implementation cleanup, archival, and merge follow the shared
`task-workflow` Step 9.

## Final Implementation Notes

- **Actual work done:** All seven planned changes landed, across 35 modified
  files plus two new ones. The canonical table gained four rows (`xdeprepo`,
  `xdeps`, `artifacts`, `attachments`), a worked nested-field example with its
  own heading, the `--also-blocks-dependents` flag on the
  `also_blocks_dependents` row, and a "Fields the workflow writes for you"
  subsection recording the workflow-written-flag policy. Its "Customizing Task
  Types" block went from 8 defaults to 10. Five more website pages, `CLAUDE.md`,
  the seed, the three generated instruction mirrors, five skill sources, the six
  tracked `-remote-` closures and twelve goldens were brought into line. The new
  guard is `tests/test_docs_vocabulary_coverage.sh` driving
  `tests/lib/docs_vocabulary_scan.py`.

- **Deviations from plan:** Two, both additive and both flagged before
  implementation rather than discovered after.
  - **`attachments` is a fourth undocumented field.** The task's ACs named
    three. Deriving the field set from the *writers* rather than the corpus (see
    Key decisions) surfaced `attachments`, written by `ait attach add`, with zero
    on-disk instances and no coverage anywhere in `website/content/docs`. It is
    documented here. This also falsifies the task body's claim that `artifacts`
    is "the header's only nested field" — there are two.
  - **`.claude/skills/aitask-changelog/SKILL.md:57` is a tenth enumerating
    site** the task's exploration missed, and it was the worst of them: 8 values,
    missing both `enhancement` and `manual_verification`. Corrected to `FULL`.

  One correction to the task body rather than a deviation: `artifacts` entries
  carry only `handle`, `kind` and optional `name`
  (`aitask_artifact.sh:270`), not the nine-key `FIELD_ORDER` in
  `frontmatter_patch.py:47` — that list is a shared *emission ordering* spanning
  both nested fields, and `attachments` uses a different six of its keys.

- **Issues encountered:**
  - **A concurrent session held 7 of the 26 target files.** The pre-phase
    `baseline_generated_surfaces` mitigation caught it on its first run: a
    resource-admission feature (t1597) was mid-flight across
    `task-workflow/SKILL.md`, its three `-remote-` closures and its three
    goldens. Committing those paths would have swept that work into this task's
    commit. Reported and paused rather than working around it; the user landed
    t1597, the tree went clean, and the baseline was re-run from scratch and
    came back zero-diff across all four generated surfaces. Every line in the
    final generated diff is therefore provably attributable to this task.
  - **Three extraction bugs in the first scanner draft**, all found by running
    it rather than by inspection: `plain_paren` did not strip an in-place
    `defaults:` introducer; `backtick_list` did not handle a **line-wrapped**
    enumeration (`CLAUDE.md` and the seed both wrap theirs); and the
    `frontmatter_patch.py` caller detection matched a passing mention in an
    `aitask_board.py` docstring. Fixed by adding a `_join_wrapped` helper, a
    label-prefix strip, and requiring an actual `append|remove|set` invocation.

- **Key decisions:**
  - **The guard's field source of truth is the writers, not the corpus.** A
    corpus-derived required-set fails open on exactly the case this task exists
    to prevent: a field that exists in code but has not yet been written to any
    task file has zero instances, so the check stays green while the table is
    already wrong. `attachments` was that case, live in the repo. The writer set
    is the `echo "<field>: "` emissions of `aitask_update.sh` / `aitask_create.sh`,
    plus `completed_at` from `aitask_archive.sh`, plus the field argument passed
    to `frontmatter_patch.py` by its callers, minus the named draft-envelope keys
    `draft` / `parent`. Because "documented but no writer" is empty, the
    assertion is **bidirectional** — strictly stronger than the one-way check a
    corpus source would have forced. The corpus scan survives, demoted to a
    separate supplemental diagnostic (`E/corpus`).
  - **Per-site checks extract the enumeration, then compare sets.** A "no
    excluded value appears in the slice" assertion is unusable here, because
    every `NO_MV` site must *state why* `manual_verification` is absent and the
    rationale sentence necessarily contains the token. Five declared shapes
    (`pipe`, `pipe_wrapped`, `table_cell`, `backtick_list`, `plain_paren`,
    `fenced_lines`) carve out the enumeration span; prose outside it is
    invisible. Test 5 and Test 6 together pin both halves: adding the value to
    the *enumeration* fails, naming it in the *rationale* does not.
  - **`manual_verification:` is not a valid commit type.** Evidence: 0 of the
    last 3000 commits use it; a manual-verification task records its outcome as
    `ait: Record verification state for t<id>`; any code change a failed
    checklist item triggers lands on a spawned follow-up under that follow-up's
    own type. The two commit-type sites and `aitask-wrap`'s suggestion list stay
    9-valued (`NO_MV`) with the reason stated in place, and the reason is encoded
    in `NO_MV_EXCLUDES` so it is enforced, not just asserted.
  - **`issue-tracker.md` is `DETECTED` (8), not `FULL`.** It describes what
    `github_detect_type()` can infer from an issue label. That function emits
    bug/refactor/test/style/chore/documentation/performance and otherwise falls
    back to `feature` — so the page was **over**-claiming `enhancement`, a
    second error in the opposite direction from the one the task reported.
    `enhancement` was removed and the `feature` fallback named.
  - **Workflow-written flags stay undocumented, as recorded policy.** The seven
    absent flags all write fields already marked "Framework-derived — never
    hand-edit" or "written by the workflow only". Where a field *is* meant to be
    set by a person the flag is named in its own row (`verification_baseline`,
    `boardgroup`), and that contrast is now stated explicitly so the omission
    reads as a decision.
  - **The tracked `-remote-` closures are guard sites.** `.gitignore` excludes
    `.claude/skills/*-/`, but the `-remote-` trees are committed anyway and ship
    to users. Listing their six enumerating files in `SITES` turns "edited the
    source, forgot `aitask_skill_rerender.sh remote`" into a failing test.
  - **Goldens are deliberately *not* guard sites.** They are byte-compared
    against a live render by `tests/test_skill_render_*.sh`, so they cannot drift
    from their sources independently; adding them would only double-report.

- **What the guard does not buy** (recorded in the scanner header and in
  `aidocs/issue_type_vocabulary_duplication.md`): a field is visible only once a
  writer the scanner knows about can emit it. A brand-new script writing
  frontmatter directly stays invisible. The gap is narrowed, not closed, by
  asserting `PATCH_CALLERS` is exactly the set of `frontmatter_patch.py` callers
  that exist — so adding a nested-field writer fails the guard instead of
  slipping past it. For a genuinely new field, the checklist in
  `aidocs/framework/aitasks_extension_points.md` §5 remains the mechanism.

- **Verification:** new guard 25/25 (10 negative controls, each proven to flip
  its own check to FAIL against an unmutated-and-passing fixture baseline);
  `test_agent_instructions.sh` 146/146; `test_skill_render_task_workflow.sh`
  204/204; `test_skill_render_aitask_wrap.sh` 96/96;
  `test_skill_render{,_uniform}.sh`, `_rerender`, `_verify`, `_parity`,
  `_dispatch_contract`, `change_surface`, `serial_carveout` all pass;
  `aitask_skill_verify.sh` clean; `hugo build --gc --minify` 240 pages with
  `id=nested-fields-artifacts-and-attachments` confirmed by hand in the built
  HTML (a dead `#fragment` does not fail the build).

- **Upstream defects identified:** None
