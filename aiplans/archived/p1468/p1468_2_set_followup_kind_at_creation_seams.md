---
Task: t1468_2_set_followup_kind_at_creation_seams.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_1_*.md, aitasks/t1468/t1468_3_*.md, aitasks/t1468/t1468_4_*.md, aitasks/t1468/t1468_5_*.md, aitasks/t1468/t1468_6_*.md, aitasks/t1468/t1468_7_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-10 23:26
---

# p1468_2 — Set `followup_kind` at every creation seam

## Context

t1468_1 landed the `followup_kind:` frontmatter field: `aitask_create.sh` accepts
`--followup-kind`, validates it against `lib/followup_kinds.py` (8 kinds, reject
never coerce, `die` → exit 1 before any file is written), and all three
serializers emit it. The shared creation contract already **documents** the
parameter (`task-creation-batch.md:20`).

Nothing **sets** it. The field exists and is inert: every auto-spawned follow-up
is still created without provenance, which is the actual pain the parent task
(t1468) describes — 44% of active tasks are follow-ups and 95 carry no marker.

This child closes that gap at all twelve creation seams, plus two topic-anchoring
fixes, and pins the coverage with tests that fail when a seam is missed.

**Re-verified against current source during this planning pass.** The stored plan
was accurate on the big shape but wrong in five specifics, all corrected below and
called out under *Plan corrections*.

---

## Plan corrections (verification findings)

1. **`aitask_verification_followup.sh` has no `create_args` array.** The stored
   plan says "all three build an args array; append the flag there". False — that
   helper uses an inline multi-line invocation (`:208-214`); its only array is
   `followup_args` (`:200-205`), which is *conditional on the origin resolving*.
   Putting the kind there would make provenance depend on anchor resolution.
2. **`aitask-docs-gap` is a static skill** — no `.j2`, no rendered `-<profile>-`
   variants exist. Its seam must be asserted against the **source** file; the
   stored plan's "grep the rendered variants, not the source" cannot apply there.
3. **Five additional `Batch Task Creation Procedure` call sites exist that create
   genuine new work** (`task-workflow/planning.md:245`, `aitask-explore`,
   `aitask-wrap`, `aitask-pr-import`, `aitask-revert`), plus doc-only references.
   The stored plan's guard — "fail if a call site exists that the table does not
   name" — would fail immediately against these. Resolved in §6a with an
   **execution-only** discovery predicate plus an explicit *no-kind* disposition
   per file; the narrow predicate drops all six mention-only files by itself, so
   no fuzzy "documentation reference" class is needed.
4. **`aitask_skill_rerender.sh` has no `--force`** (that flag is on
   `aitask_skill_render.sh`). Its absence is fine: the renderer's skip-if-fresh
   combines an mtime fast-path with a content-diff safety net.
5. **Rendered-variant assertions are not uniformly safe.** Only
   `task-workflow-remote-` is un-ignored in git (`.gitignore:66-68`);
   `aitask-review-remote-` and `aitask-qa-remote-` are **untracked** and absent on
   a fresh clone. An unguarded assert there breaks CI; a `[[ -f ]]`-guarded one is
   vacuous. Assertion targets are chosen per seam accordingly (§6).

Also confirmed: the MV cross-field invariant is one-directional, so all three
helper kinds are legal (`carry_over` on an `issue_type: manual_verification`
carry-over passes; only `followup_kind: manual_verification` constrains the type).

---

## Implementation steps

### Pre-phase (risk mitigations)

Runs **before** step 1. All four are inline, confirmed at planning. Each step is
labeled with its mitigation name.

1. `[negctrl_seam_table_red_first]` Write §6a's three disposition tables and the
   P1/P2/P3 exhaustiveness guard in their **final form** — hand-authored constant
   tables, run-time-derived call-site sets, diffed — and run the suite against
   unmodified source **before any seam is edited**. Confirm it goes **RED** on all
   twelve kind seams **and on the `upstream-followup.md` `followup_of` assertion**
   (that file carries no anchor parameter today, so a green there would mean the
   anchor check is not wired). Record every failing assertion's text in Final
   Implementation Notes. At the end the same assertions, **byte-unchanged**, must
   pass. A guard derived from the same grep it checks would go green today and
   prove nothing.

2. `[mv_anchor_failsafe_baseline]` Before touching
   `aitask_create_manual_verification.sh` (§4b), add an argv test driving it with
   an **unresolvable** `--related` value and assert creation still **succeeds**
   with no `--followup-of` in argv. Record the passing baseline. After the edit
   the same assertion must pass **unchanged** — that is what proves the
   conditional probe preserved the existing path rather than converting it to a
   `die`.

3. `[kind_independent_of_anchor_resolution]` In the same pre-phase, add the
   companion argv case for `aitask_verification_followup.sh`: unresolvable
   origin ⇒ `--followup-kind verification_failure` **present**, `--followup-of`
   **absent**. Written before §3 so it fails if the kind is mistakenly folded
   into the conditional `followup_args` array.

4. `[guarded_assert_nonvacuity_counter]` Build the non-vacuity counter into
   §6a's guarded rendered-variant assertions from the start: count the guarded
   assertions that actually executed and fail when that count is zero while the
   rendered dirs exist. Retrofitting it later leaves a window where the suite
   reports green on a fresh clone having asserted nothing.

### 1. The shared creation contract

`.claude/skills/task-workflow/task-creation-batch.md` is the **source** file. It
carries a `.md` extension but *is* Jinja-rendered by the closure dep-walker.

1.1 The `followup_kind` Input row already exists at `:20` (t1468_1). **Do not
duplicate it.**

1.2 Add the emission to `### Optional flags` (`:116-125`), the block documented as
"Append these flags before `--desc` or `--desc-file` when provided":

```bash
  --followup-kind "<followup_kind>" \
```

1.3 Add one clarifying sentence under that block. Verification found a real
ambiguity: `anchor` / `followup_of` are **rejected alongside `--parent`**, and the
QA seam already carries a note explaining that. `followup_kind` is orthogonal and
**is** legal with `--parent`. Without this note a caller reading the exclusion
rule will wrongly skip the kind on child creations.

### 2. The nine skill caller sites

The insertion shape differs per site — two are prose, six are bulleted parameter
lists, one is a raw command.

| caller | current site | shape | kind |
|---|---|---|---|
| `task-workflow/risk-mitigation-followup.md` Part 2 | `:385-392` | prose sentence ("Pass `followup_of: <task_id>` …") | `risk_mitigation` |
| `task-workflow/risk-mitigation-followup.md` Part 3 | `:508-516` | prose parenthetical at `:515` | `risk_mitigation` |
| `task-workflow/upstream-followup.md` | `:67-94` | bulleted list | `upstream_defect` |
| `aitask-qa/follow-up-task-creation.md` **child** | `:32-46` | bulleted list | `qa_test_gap` |
| `aitask-qa/follow-up-task-creation.md` **parent** | `:48-56` | bulleted list | `qa_test_gap` |
| `aitask-review/SKILL.md.j2` single | `:181-190` | bulleted list | `review_finding` |
| `aitask-review/SKILL.md.j2` parent | `:199-206` | bulleted list | `review_finding` |
| `aitask-review/SKILL.md.j2` children | `:213-222` | bulleted list | `review_finding` |
| `aitask-docs-gap/SKILL.md` | `:159-169` | raw inline command | `docs_gap` |

Notes that matter:

- **Both** QA branches and **all three** review sites. The easy mistake is doing
  one of each.
- On the QA **child** branch, add a short note that `followup_kind` is legal here
  even though `followup_of` is not (`:43-46` explains the exclusion) — otherwise
  the two adjacent rules read as contradictory.
- `aitask-review/SKILL.md.j2:179` already tells callers *not* to pass
  `followup_of` (a review has no single source task). Leave that alone —
  `followup_kind` is independent of anchoring.
- **`aitask-docs-gap` bypasses the shared procedure entirely**: it inlines
  `aitask_create.sh --batch --commit` with no `--gates` injection and no
  `followup_of` (it is a plain `SKILL.md` and cannot render Jinja). Add
  `--followup-kind docs_gap \` inline and leave a comment naming the divergence.
  **Do not** convert it to the shared template — that changes its gate-declaration
  behaviour and belongs in its own task.

### 3. The three shell helpers

| helper | site | insertion | kind |
|---|---|---|---|
| `aitask_create_manual_verification.sh` | `create_args` literal `:109-119` | inside the array literal, beside `--type manual_verification` | `manual_verification` |
| `aitask_archive.sh` `create_carryover_task()` | `create_args` literal `:602-607` | inside the literal, **before** the closing `--followup-of "$orig_id")` paren | `carry_over` |
| `aitask_verification_followup.sh` | inline command `:208-214` | a plain flag beside `--type bug` — **not** inside `followup_args` | `verification_failure` |

The third is the correction from §Plan corrections 1. `followup_args`
(`:200-205`) is populated only when the origin task resolves; folding the kind in
there would silently drop provenance for a commit-only origin.

`carry_over` — not `manual_verification` — for the archive carry-over, even though
it is created with `--type manual_verification`. The kind describes *how the task
came to exist*; the type describes *how it is worked*. The invariant permits this
(it constrains only the `manual_verification` **kind**).

None of the three needs to source `lib/followup_kinds_sh.sh`: each passes one
fixed literal, and `aitask_create.sh` validates at the single write seam.

### 4. Topic-anchoring fixes (both confirmed in this session)

**4a. `upstream-followup.md` passes no `--followup-of`** — which is why 58
follow-ups are topic roots that cannot cluster with their origin in the board's
By-Topic view. Add `followup_of: <task_id>` to its parameter list (`<task_id>` is
the inherited origin-task context variable, already used at `:76`).

**4b. `aitask_create_manual_verification.sh` has the identical gap** in its
standalone branch: `:120-125` passes `--parent` when set, else only
`--deps "$bare_related"` — no anchor, so every standalone MV follow-up is a topic
root. Add `--followup-of` to the **else** branch only (the `--parent` branch
auto-inherits the parent's anchor and would be *rejected* if both were passed).

**Fail safe.** `--followup-of` **dies** on an unresolvable id, and `RELATED` is a
loose reference. Copy the conditional probe from
`aitask_verification_followup.sh:200-205` verbatim in shape:

```bash
local origin_status
origin_status=$("$SCRIPT_DIR/aitask_query_files.sh" task-status "$bare_related" 2>/dev/null || true)
if [[ "$origin_status" == STATUS:* && "$origin_status" != STATUS:NOT_FOUND ]]; then
    create_args+=(--followup-of "$bare_related")
fi
```

An unresolvable origin must leave the task a topic root, exactly as today — never
turn a working creation into a `die`.

### 5. Regeneration and goldens

```bash
./.aitask-scripts/aitask_skill_rerender.sh default
./.aitask-scripts/aitask_skill_rerender.sh fast
./.aitask-scripts/aitask_skill_rerender.sh remote
```

Positional profile name; **one call per profile**; each loops `claude`, `codex`,
`opencode` internally. There is no `--force` on this driver and none is needed.

**Goldens.** Verification found the stored plan's golden step is partly a no-op:

- `tests/golden/procs/task-workflow/risk-mitigation-followup-default.md` — exists
  (this proc is in `WRAPPED_FILES_INVARIANT`, so **one** canonical golden, not
  three). Regenerate.
- `tests/golden/skills/aitask-review/SKILL-{default,fast,remote}-claude.md` —
  regenerate all three.
- `upstream-followup.md` and `aitask-qa/follow-up-task-creation.md` have **no
  goldens**; nothing to regenerate for them.
- **`task-creation-batch.md` has no golden at all**, and is in neither
  `WRAPPED_FILES_*` array — template drift in the shared creation contract is
  currently invisible to the golden suite. **Close that gap here** (user-approved):
  add `"task-creation-batch.md"` to `WRAPPED_FILES_VARYING`
  (`tests/test_skill_render_task_workflow.sh:55-63`) — it *is* profile-varying
  (fast injects `--gates "risk_evaluated"` into both command forms; default and
  remote do not) — and commit the three new goldens.

  **Four count sites go stale, not one.** The script's descriptive header states
  the coverage this change is meant to establish, so leaving it stale misstates
  it. Update all of them together:

  | site | current | new |
  |---|---|---|
  | `:4` header — wrapped-file tally | `13 wrapped .md files (7 profile-varying + 6 profile-invariant)` | `14 … (8 … + 6 …)` |
  | `:5` header — golden tally | `27 golden files` | `30 golden files` |
  | `:7-8` header — Coverage item 1 | `the 7 profile-varying wrapped files × 3 profiles` | `8` |
  | `:77` Test 1 echo banner | `golden diffs for 7 profile-varying wrapped files × 3 profiles` | `8` |

  Verify the new tallies by re-deriving them (`ls tests/golden/procs/task-workflow/ \| wc -l` → 30)
  rather than by arithmetic.

Regeneration command (no regolden script exists; this is the documented loop from
`aidocs/framework/skill_authoring_conventions.md:484-497`):

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/task-creation-batch.md \
    aitasks/metadata/profiles/$profile.yaml claude \
    > tests/golden/procs/task-workflow/task-creation-batch-${profile}.md
done
```

**Git tracking is asymmetric.** `.gitignore:47-49` ignores the rendered trees;
lines `66-68` un-ignore exactly three dirs — `.claude/skills/task-workflow-remote-/`,
`.agents/skills/task-workflow-remote-codex-/` (note the extra `-codex-` segment),
`.opencode/skills/task-workflow-remote-/`. Their contents are tracked and must be
committed. `aitask-review-remote-` / `aitask-qa-remote-` are **not** tracked.

**Stage with an explicit path allowlist.** The sweep touches dozens of files
across three trees; never `git add -A`. Check for foreign uncommitted work first —
a concurrent session was active in this tree during t1468_1.

Then `./.aitask-scripts/aitask_skill_verify.sh` (no flags — it takes none) must be
clean. Its headless-prerender freshness check is what catches a `task-workflow/`
edit that was never re-rendered to `remote`.

### 6. Tests

The rendering sweep proves nothing on its own: a seam that omits the flag still
renders consistently and keeps `aitask_skill_verify.sh` green. Two new
table-driven suites.

**6a. `tests/test_followup_kind_seams.sh` — content + exhaustiveness.**

**Execution-only discovery predicates.** A generic mention of "Batch Task Creation
Procedure" / `aitask_create.sh` also occurs in definitions, cross-references and
usage examples, so a mention-based scan both fires on legitimate documentation and
hides real seams behind a fuzzy `DOCREF` disposition. Three narrow,
**dispatch-shaped** predicates are used instead. Each was run against the current
tree and its hit set is pinned below; the test asserts the derived set equals the
table's key set, so a new seam *or* a predicate that stops matching fails loudly.

| # | scope | predicate (regex) | hits today |
|---|---|---|---|
| P1 | `.claude/skills/**/*.md{,.j2}`, rendered `-<profile>-` dirs excluded | `(Execute\|execute\|via) the \*\*Batch Task Creation Procedure\*\*` | **9** |
| P2 | same scope | `^\s*\./\.aitask-scripts/aitask_create\.sh .*--batch` (a real command line, not prose) | **4** |
| P3 | `.aitask-scripts/*.sh` | a **non-comment** line invoking `aitask_create\.sh` | **6** |

P1 eliminates all six mention-only files (`aitask-create/SKILL.md`,
`cross-repo-child-assignment.md`, `profiles.md`, `task-workflow/SKILL.md`,
`task-fold-content.md`, `task-creation-batch.md`) with no hand-maintained
exclusion list — **there is no `DOCREF` disposition**. P3 narrows 11 mention-level
files to the 6 that actually invoke.

**P1 table — dispatch sites (9, fully enumerated).** Two expectation columns,
because the anchor parameter is as load-bearing as the kind:

| file | `followup_kind` | `followup_of` |
|---|---|---|
| `task-workflow/risk-mitigation-followup.md` | `risk_mitigation` ×2 | present ×2 |
| `task-workflow/upstream-followup.md` | `upstream_defect` ×1 | **present ×1** (added by §4a) |
| `aitask-qa/follow-up-task-creation.md` | `qa_test_gap` ×2 | present **exactly ×1** — parent branch only; the child branch must **not** carry it (`:43-46`: rejected with `--parent`) |
| `aitask-review/SKILL.md.j2` | `review_finding` ×3 | **absent** — reviews are topic roots by design (`:179`) |
| `task-workflow/planning.md` | none | — |
| `aitask-explore/SKILL.md.j2` | none | — |
| `aitask-wrap/SKILL.md.j2` | none | — |
| `aitask-pr-import/SKILL.md.j2` | none | — |
| `aitask-revert/SKILL.md.j2` | none | — |

**P2 table — inline create commands (4, fully enumerated).**

| file | expectation |
|---|---|
| `aitask-docs-gap/SKILL.md` | `--followup-kind docs_gap` present |
| `task-workflow/task-creation-batch.md` | the **template** — must carry the `--followup-kind "<followup_kind>"` emission placeholder (§1.2) |
| `aitask-create/SKILL.md` | none — user-driven creation, genuine new work |
| `task-workflow/cross-repo-child-assignment.md` | none — cross-repo children are new work |

**P3 table — helper scripts (6, fully enumerated).**

| file | expectation |
|---|---|
| `aitask_archive.sh` | `--followup-kind carry_over` |
| `aitask_create_manual_verification.sh` | `--followup-kind manual_verification` |
| `aitask_verification_followup.sh` | `--followup-kind verification_failure` |
| `aitask_create.sh` | the sink itself — no emission expected |
| `aitask_issue_import.sh` | none — issue import is new work |
| `aitask_pr_import.sh` | none — PR import is new work |

Assertions:

1. **Positive, per kind-bearing row** — the source contains `followup_kind: <kind>`
   (or `--followup-kind <kind>` for P2/P3 command seams), asserted by **occurrence
   count**, not mere presence, so adding a site without the flag fails.
2. **Anchor expectations** — assert the `followup_of` counts in the P1 table
   exactly, including the two negative cases (`aitask-review` absent; the QA child
   branch absent). This is what stops an edit that adds the kind to
   `upstream-followup.md` but forgets the anchor from passing.
3. **Negative, per none-row** — the file contains **no** `followup_kind`
   reference, so a future edit cannot silently tag genuine new work.
4. **Exhaustiveness (must be able to fail).** Re-run P1/P2/P3 at test time and diff
   each derived set against its hand-authored table key set, failing by name in
   both directions. The tables are hand-written constants; the derived sets come
   from the tree — so the diff can genuinely fail. Also assert each derived set's
   size equals the pinned count above, so a predicate that silently stops matching
   is caught rather than yielding a vacuously-satisfied diff.
5. **Vocabulary coverage** — every kind in `lib/followup_kinds.py` is the
   expectation of at least one row across the three tables. Catches the field
   growing a ninth kind with no emitter.
6. **Rendered-output assertions, targeted per tracking status** (correction 5):
   - `task-workflow-remote-/{risk-mitigation-followup,upstream-followup,task-creation-batch}.md`
     in all three trees — **tracked, assert unconditionally**. For
     `upstream-followup.md` assert **both** `followup_kind: upstream_defect` and
     `followup_of: <task_id>`.
   - `tests/golden/skills/aitask-review/SKILL-*-claude.md` — **tracked goldens are
     rendered output**; assert `followup_kind: review_finding` ×3 in all three.
   - `task-workflow-fast-/` and the QA rendered variants — untracked; assert
     behind `[[ -f ]]`, following the house pattern at
     `tests/test_create_manual_verification_gates.sh:167-176`, and **count the
     guarded assertions that actually executed**, failing if the count is zero on
     a tree where the dirs exist. A guarded assert that silently skips proves
     nothing.

**6b. `tests/test_followup_kind_helper_argv.sh` — argv + real file.**

Copy the strict stub harness from `tests/test_archive_carryover.sh:32-70`
(`printf "%s\n" "$@" >> "$STUB_ARG_LOG"`). Add `--followup-kind` as a
value-taking flag to the stub's own parse loop, or it falls through to
`*) shift ;;`. Assert, per helper, the exact `--followup-kind <expected>` pair in
argv:

- `aitask_archive.sh` → `carry_over`
- `aitask_create_manual_verification.sh` → `manual_verification`
- `aitask_verification_followup.sh` → `verification_failure`

Plus `--followup-of` presence/absence for 4b: present when the related task
resolves, **absent** when it does not (the fail-safe case), and never alongside
`--parent`.

**Real-file assertion** (pattern: `tests/test_archive_carryover_anchor.sh`, which
drives the *real* `aitask_create.sh` in a scaffolded clone): add
`assert_contains "carry-over carries followup_kind" "followup_kind: carry_over" "$fm"`
beside its existing `anchor: 200` assertion at `:140`. Cheapest possible proof of
the real emit path — same fixture, same code path, one line.

**Upstream-specific anchor proof.** The §6a content checks pin what
`upstream-followup.md` *says*; this pins that what it says actually produces an
anchored task. In a scaffolded repo, create an origin task, then run the exact
shape the procedure now dispatches:

```bash
aitask_create.sh --batch --commit --type bug \
  --followup-of <origin_id> --followup-kind upstream_defect ...
```

and assert on the created file **both** `followup_kind: upstream_defect` **and**
`anchor: <origin topic root>` — the second is the assertion that fails if §4a is
dropped or mis-parameterised. Include the anchorless-origin case too: an origin
with no `anchor:` of its own must yield `anchor: <origin_id>`, not a missing key.

Both files: `set -u`, `PASS/FAIL/TOTAL` initialized locally, source
`tests/lib/asserts.sh` (`assert_eq`/`assert_contains`/`assert_not_contains`,
description-first signature), bash-3.2-safe (no `mapfile`, no `declare -A`).

### 7. Docs

No new frontmatter field, so no Layer-5 sweep. Two touch-ups only:

- `.claude/skills/aitask-create/SKILL.md:285-287` already points at the canonical
  contract for `followup_kind` — verify it still reads correctly after §1.3 and
  leave it as a pointer (do not restate semantics).
- If §4b changes observable MV-seeder behaviour, note the new anchoring in that
  script's header comment.

---

## Verification

1. **`negctrl_seam_table_red_first`** — the §6a exhaustiveness + positive
   assertions must go **RED** before any seam is edited (9 skill seams + 3 helper
   seams missing the kind, plus the missing `followup_of` on
   `upstream-followup.md`). Record the failing assertion text; after
   implementation the same assertions, **byte-unchanged**, must go GREEN.
1e. **Upstream anchor proof** — the §6b real-file case shows a task created with
   the shape `upstream-followup.md` dispatches lands an `anchor:` line, including
   the anchorless-origin case.
1b. **`mv_anchor_failsafe_baseline`** — the unresolvable-`--related` creation
   assertion passes **before** §4b and passes **unchanged** after.
1c. **`kind_independent_of_anchor_resolution`** — unresolvable origin yields the
   kind without `--followup-of`.
1d. **`guarded_assert_nonvacuity_counter`** — deliberately point the guarded
   assertions at a non-existent tree and confirm the suite **fails** on a zero
   count, rather than passing quietly.
2. `bash tests/test_followup_kind_seams.sh` — all pass.
3. `bash tests/test_followup_kind_helper_argv.sh` — all pass.
4. `bash tests/test_archive_carryover.sh` and
   `bash tests/test_archive_carryover_anchor.sh` — still green (the archive helper
   now passes an extra flag through their stubs).
5. `bash tests/test_create_manual_verification_gates.sh` — still green (it owns
   the `task-creation-batch.md` template→rendered→sink equivalence pin that §1.2
   touches).
6. `bash tests/test_skill_render_task_workflow.sh` — the three new
   `task-creation-batch-*.md` goldens pass and the counts are updated.
   **Expect 3 pre-existing failures** (`golden SKILL × {default,fast,remote}`):
   t1466 edited `task-workflow/SKILL.md` without regenerating its goldens, and
   repairing that is deliberately **out of scope here** (see Post-Review
   Changes 1). Assert the failure set is exactly those three and that the count
   of passing tests rose by 3.
7. `./.aitask-scripts/aitask_skill_verify.sh` — clean.
8. `bash tests/run_all_python_tests.sh` — read the **last** line for the verdict
   (`set -o pipefail` if piping).
9. `shellcheck .aitask-scripts/aitask_archive.sh
   .aitask-scripts/aitask_create_manual_verification.sh
   .aitask-scripts/aitask_verification_followup.sh` — no new findings.
10. **End-to-end**: drive the real carry-over path and confirm the created file
    carries `followup_kind: carry_over` (verification 4 covers this via the anchor
    test's real fixture).
11. **`git status` before staging** — confirm no foreign uncommitted work is
    swept in; stage by explicit path allowlist and confirm the three tracked
    `*-remote-*` copies are included.

---

## Risk

Levels below are the **reassessment after** the four inline mitigations were
folded into the plan. Both stay `medium`: the controls sharply improve
*detection* at each named hazard, but the blast radius across three agent trees
is intrinsic to the change, and completeness still rests on a hand-authored
disposition table that could omit a whole discovery-predicate class.

### Code-health risk: medium

- Adding `--followup-of` to `aitask_create_manual_verification.sh` (§4b) changes a
  currently-working creation path: `--followup-of` **dies** on an unresolvable id,
  so an unconditional addition would turn a successful standalone MV creation into
  a hard failure for any loose `--related` reference · severity: medium (residual —
  addressed by inline pre-phase `mv_anchor_failsafe_baseline`) · → mitigation:
  inline pre-phase mv_anchor_failsafe_baseline
- Wide, shallow blast radius: 1 shared contract, 5 skill files, 3 shell scripts,
  a rendered sweep across 3 profiles × 3 agent trees with 3 force-tracked
  prerenders, **7 golden files** (3 new `task-creation-batch-*`, 1 regenerated
  `risk-mitigation-followup-default`, 3 regenerated `aitask-review/SKILL-*`), and
  2 modified existing tests. No single control removes it · severity: medium ·
  → mitigation: none
- The `aitask_verification_followup.sh` edit sits immediately beside the
  `${followup_args[@]+"${followup_args[@]}"}` empty-safe expansion; a careless
  insertion into that array (rather than the inline command) makes provenance
  conditional on anchor resolution — silently, with no test failure unless
  specifically covered · severity: low (residual — addressed by inline pre-phase
  `kind_independent_of_anchor_resolution`) · → mitigation: inline pre-phase
  kind_independent_of_anchor_resolution

### Goal-achievement risk: medium

- The "exhaustive by construction" guard is the whole deliverable's safety net,
  and the natural way to write it — deriving the table from the same grep it
  checks — makes it **unable to fail**. It must be a hand-authored constant diffed
  against a run-time-derived set · severity: medium (residual — addressed by
  inline pre-phase `negctrl_seam_table_red_first`) · → mitigation: inline
  pre-phase negctrl_seam_table_red_first
- Rendered-variant assertions on untracked `-fast-` / `-default-` / QA paths are
  `[[ -f ]]`-guarded by necessity; on a fresh clone they all skip, so the suite
  can report green while proving nothing about rendered output · severity: medium
  (residual — addressed by inline pre-phase `guarded_assert_nonvacuity_counter`) ·
  → mitigation: inline pre-phase guarded_assert_nonvacuity_counter
- Twelve seams with four different insertion shapes (prose, bulleted list, array
  literal, inline command) — a mechanically-applied edit that looks right in five
  places can be wrong in the sixth · severity: low · → mitigation: none (covered
  by the per-seam occurrence-count assertions in §6a)

### Planned mitigations
- timing: pre-phase | name: negctrl_seam_table_red_first | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the exhaustiveness guard could be written unable to fail | desc: write the disposition table and exhaustiveness guard in final form and confirm RED across all twelve seams before any seam is edited, then require GREEN with the assertions byte-unchanged
- timing: pre-phase | name: mv_anchor_failsafe_baseline | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — adding --followup-of to the MV seeder could turn a working creation into a die | desc: pin that standalone MV creation with an unresolvable --related succeeds today and require the same assertion to pass unchanged after the conditional probe is added
- timing: pre-phase | name: kind_independent_of_anchor_resolution | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — folding the kind into the conditional followup_args array makes provenance depend on anchor resolution | desc: argv case driving aitask_verification_followup.sh with an unresolvable origin, asserting the kind is present while --followup-of is absent
- timing: pre-phase | name: guarded_assert_nonvacuity_counter | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — guarded rendered-variant assertions all skip on a fresh clone | desc: build a non-vacuity counter into the guarded rendered assertions so a zero-executed run fails loudly instead of reporting green

---

## Post-Review Changes

### Change Request 1 (2026-08-11 00:05)
- **Requested by user:** Three concerns raised at the Step-8 review, all
  verified as valid before acting.
  1. **[high · commit scope]** The unstaged composite had grown
     `.aitask-scripts/board/aitask_board.py` and
     `tests/test_board_persistence_seam.py` — neither named by this task or
     plan. Committing them here would merge unrelated board work into t1468_2's
     history.
  2. **[high · commit scope]** The diff refreshed
     `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md` to cure
     stale t1466 goldens, although t1468_2 neither changes
     `task-workflow/SKILL.md` nor plans those files. Repairing a pre-existing
     regression fixture inside this task obscures provenance.
  3. **[low · test hygiene]** `derive_p3()` in `tests/test_followup_kind_seams.sh`
     emitted `grep: write error: Broken pipe` on stderr: `grep -v … | grep -q …`
     lets the downstream `grep -q` exit at its first match and close the pipe.
     The pipeline still returned success, so the noise hid under a green result.
- **Verdict:** all three CONFIRMED.
  1. Confirmed foreign: the two files appeared in `git status` *after* this
     session's pre-rerender cleanliness check, and their own added comments name
     t1480 (`# --- t1480: the USER config layer ---`, `t1480 retired a dead one`).
     A concurrent session is active in this tree.
  2. Confirmed pre-existing, not caused here: this tree's
     `task-workflow/SKILL.md` is **byte-identical to HEAD**, and rendering
     *HEAD's own copy* still differs from the committed golden — so the staleness
     exists at HEAD independently of t1468_2. `git log` confirms the source last
     changed in `4f8d0387e` (t1466) while the goldens last changed in
     `4ba78d1c7` (t1272).
  3. Confirmed by capturing stderr separately: the run wrote a non-empty stderr
     stream while exiting 0.
- **Changes made:**
  1. No file change needed — the staging discipline this plan already mandates
     (explicit path allowlist, never `git add -A`) covers it. The two t1480
     files are left untouched and unstaged, and the allowlist is enumerated
     explicitly at commit time.
  2. Reverted the three `SKILL-*.md` goldens to HEAD with a path-scoped
     `git checkout --`. The repair is **out of scope** for t1468_2 and is
     recorded as an upstream defect instead, so it can be fixed under its own
     tracking. Verification step 6 was rewritten to expect exactly those three
     pre-existing failures rather than a fully green suite — an honest
     expectation beats a green one bought with someone else's fix.
  3. Replaced the two-stage pipeline in `derive_p3()` with a single `awk`
     predicate (skip comment lines, match an `aitask_create.sh` invocation),
     which has no downstream reader to close the pipe.
- **Verification after the changes:** `tests/test_followup_kind_seams.sh` is
  **55/55** with the derived P3 set unchanged and **0 bytes on stderr**;
  `tests/test_skill_render_task_workflow.sh` is 184 tests / 181 passed with the
  failure set exactly `golden SKILL × {default,fast,remote}` — the three
  pre-existing ones — and the three new `task-creation-batch-*` goldens passing.
- **Files affected:** `tests/test_followup_kind_seams.sh` (awk predicate),
  `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md` (reverted),
  this plan (verification step 6 + this section).

## Final Implementation Notes

- **Actual work done:** All twelve creation seams now set `followup_kind`, plus
  the two topic-anchoring fixes and the golden-coverage gap. 20 files changed
  (9 source, 3 shell helpers → counted within, 6 rendered/golden, 6 tests), 1
  test file added.
  - **Shared contract** (`task-creation-batch.md`): `--followup-kind
    "<followup_kind>"` added to `### Optional flags`, plus a note that the kind
    is orthogonal to anchoring and — unlike `anchor` / `followup_of` — **is**
    legal alongside `--parent`. Verification found that ambiguity was real: the
    QA child branch carries an exclusion note that reads as covering the kind
    too.
  - **Nine skill seams:** risk-mitigation-followup ×2 (prose), upstream-followup
    (+ `followup_of`), aitask-qa ×2 branches, aitask-review ×3 sites,
    aitask-docs-gap (inline, with a comment naming the divergence).
  - **Three shell helpers:** `aitask_archive.sh` → `carry_over`,
    `aitask_create_manual_verification.sh` → `manual_verification` (+ the
    probe-guarded `--followup-of` on the standalone branch),
    `aitask_verification_followup.sh` → `verification_failure`.
  - **Golden coverage:** `task-creation-batch.md` added to
    `WRAPPED_FILES_VARYING` with three new goldens; all four stale count sites
    updated (14 wrapped / 8 varying / 30 goldens).
- **Deviations from plan:**
  - **The argv suite became real-file assertions in the three existing helper
    tests, not a new `tests/test_followup_kind_helper_argv.sh`.** Verification
    found each helper already has a real-file anchor test with exactly the right
    fixture (`test_create_manual_verification.sh`,
    `test_verification_followup_anchor.sh`, `test_archive_carryover_anchor.sh`),
    including a resolvable/unresolvable-origin pair. Asserting the emitted
    frontmatter there is strictly stronger than asserting argv against a stub,
    and avoids duplicating three scaffolds. The exhaustiveness table still lives
    in one place (`test_followup_kind_seams.sh`), which is what the AC asks for.
  - **The upstream anchor proof went into `tests/test_anchor_create.sh`** (which
    owns `--followup-of` semantics) rather than the new file.
  - **`aitask-review`'s `followup_of` expectation is 1, not 0.** The plan
    reasoned "reviews are topic roots by design ⇒ absent", but the file carries
    a conditional-guidance line ("Only pass `followup_of: <reviewed_task_id>`
    when the review clearly stems from one specific task"). The count is pinned
    at its true value with a comment explaining it is guidance, not a dispatch
    parameter.
  - **Assertions normalise backticks.** The seam files disagree on markdown
    house style — upstream-followup backticks its parameter *keys*, aitask-qa
    and aitask-review backtick only *values*, risk-mitigation-followup wraps the
    whole pair. Stripping backticks before matching keeps the assertion about
    the parameter being passed rather than each file's formatting.
- **Issues encountered:**
  - **A concurrent session is active in this tree.** `main` advanced twice
    mid-session (t1479 landed while planning), and
    `.aitask-scripts/board/aitask_board.py` +
    `tests/test_board_persistence_seam.py` (t1480) appeared as unstaged
    modifications *after* the pre-rerender cleanliness check. Both were left
    untouched and excluded from staging via an explicit path allowlist.
  - **`tests/test_create_manual_verification.sh` had to copy
    `aitask_query_files.sh`** into its scaffold: the new `--followup-of` probe
    shells out to it, and the probe fails safe, so a missing script would have
    silently produced "no anchor" instead of a visible error.
- **Key decisions:**
  - **Provenance is unconditional; anchoring is not.** In
    `aitask_verification_followup.sh` the kind is a plain flag on the inline
    command, deliberately *not* folded into the origin-conditional
    `followup_args` array — otherwise a commit-only origin would silently lose
    provenance. Pinned by an assertion in the unresolvable-origin branch.
  - **The MV seeder's new anchor is probe-guarded.** `--followup-of` *dies* on
    an unresolvable id and `--related` is a loose reference, so an unconditional
    flag would have converted a working creation into a hard failure.
  - **Discovery is execution-only.** Three narrow dispatch-shaped predicates
    (P1/P2/P3) replace mention-based scanning, which dropped all six
    mention-only files without a hand-maintained exclusion list and removed the
    need for a fuzzy "doc reference" disposition class.
- **Verification results:**
  - `negctrl_seam_table_red_first`: **RED before any seam was edited** —
    26 passed / 29 failed of 55, failing assertions including
    `task-workflow/upstream-followup.md emits followup_kind: upstream_defect
    exactly 1 time(s)`, `… references followup_of: exactly 1 time(s)`,
    `aitask_archive.sh emits --followup-kind carry_over exactly 1 time(s)` and
    the 12 rendered-tree assertions. **GREEN after: 55/55**, assertions
    byte-unchanged. Test 1 (exhaustiveness) and Test 3 (vocabulary coverage)
    passed from the start, confirming the tables matched the tree before the
    behaviour changed.
  - `mv_anchor_failsafe_baseline`: the unresolvable-origin assertion
    ("unresolvable origin leaves the task a topic root") **passed before** the
    §4b edit and **passes unchanged after**.
  - `kind_independent_of_anchor_resolution`: provenance present in **both** the
    resolvable and unresolvable branches.
  - `guarded_assert_nonvacuity_counter`: probed by repointing the guarded paths
    at non-existent files — the suite fails with "4 rendered tree(s) exist but 0
    guarded assertions ran", both before and after implementation.
  - Suites green: seams 55/55, followup_kind_roundtrip 31/31, anchor_create
    24/24, create_manual_verification 18/18, verification_followup_anchor 12/12,
    verification_followup 32/32, archive_carryover 13/13,
    archive_carryover_anchor 5/5, create_manual_verification_gates 42/42, plus
    18 further archive/gate/render suites (all rc=0).
  - `tests/test_skill_render_task_workflow.sh`: 184 tests, 181 passed. The 3
    failures are `golden SKILL × {default,fast,remote}` and are **pre-existing
    at HEAD** (see Post-Review Changes 1) — the 3 new `task-creation-batch-*`
    goldens pass.
  - `bash tests/run_all_python_tests.sh`: `PYTHON SUITE: PASSED (runner=pytest,
    exit=0)`.
  - `./.aitask-scripts/aitask_skill_verify.sh`: OK (13 templates, 3 agents, 4
    stub surfaces; wrapper parity clean).
  - `shellcheck` on the three helpers: finding codes identical to HEAD
    (6×SC1091, 5×SC2012, 3×SC2016) — no new findings.
- **Upstream defects identified:**
  - `tests/golden/procs/task-workflow/SKILL-default.md:1 — the three SKILL-*.md
    goldens are stale at HEAD: commit 4f8d0387e (t1466) edited
    .claude/skills/task-workflow/SKILL.md without regenerating them (goldens
    last updated in 4ba78d1c7, t1272), so tests/test_skill_render_task_workflow.sh
    has 3 failing golden diffs independent of any current work. Regenerating the
    three files cures it; deliberately left out of t1468_2 to preserve
    provenance.`
- **Notes for sibling tasks:**
  - **The vocabulary now has an emitter for all 8 kinds**, pinned by Test 3 of
    `tests/test_followup_kind_seams.sh`: adding a ninth kind to
    `lib/followup_kinds.py` fails that test until a seam emits it. t1468_3/_4/_5
    should expect that guard.
  - **`tests/test_followup_kind_seams.sh` is the registry of creation seams.**
    Any sibling that adds or moves a task-creating seam must add a disposition
    row (kind or `NONE`) or the exhaustiveness diff fails by name.
  - **Rendered-assertion targets differ by tracking status.** Only
    `task-workflow-remote-` (all three agent trees) is un-ignored in git;
    `aitask-review-remote-` / `aitask-qa-remote-` are untracked. Assert against
    the tracked prerenders or the tracked goldens; a `[[ -f ]]` guard on an
    untracked path is vacuous on a fresh clone unless paired with a
    non-vacuity counter.
  - **`aitask_skill_rerender.sh` takes a positional profile and has no
    `--force`** (that flag lives on `aitask_skill_render.sh`); one call per
    profile loops all three agent trees.
