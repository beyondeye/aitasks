---
Task: t1873_shadow_review_only_followed_agent_changes.md
Base branch: main
Output branch: main
---

# t1873 — Shadow implementation review covers only the followed agent's changes

## Context

`impl-challenge.md` "Review-state assessment" step 3 tells the shadow to review
**every** dirty path in the shared checkout, flag unplanned paths as "possibly
unrelated", and ask the user to narrow. When the shadow followed t1852_2 (pane %138),
t1869/t1847's changes kept coming back as actionable concerns, and rechecks never
converged.

The fix has two halves:
- A tested helper **reports ownership evidence** for every changed file part, using the
  plan-path machinery.
- The shadow **makes the ownership judgement** by inspecting the changes in task context.
  Uncertain parts are reviewed as tentative observations ("possibly another task's") that
  cannot block approval. Clearly foreign parts are excluded. The user is asked only about
  material ambiguity. Every recheck judges afresh (earlier decisions are context only), so
  unrelated work never re-enters the actionable concerns.

User direction during plan review (binding):
- The helper reports evidence and makes no IN/OUT decision and no fixed blocking eligibility.
- Plan file lists are useful evidence when present, but neither complete nor reliable. There
  is no required "Files to modify" heading, and existing plans must work as they are.
- The shadow may review an unlisted file whose content and task context make the
  connection credible, and may exclude a listed file when evidence points to another task.
- Committed and newer dirty changes of one file stay separate.
- A dedicated task worktree means everything dirty in it is the task's.
- No transcript parsing.

## 1. Language-agnostic reference detection — `.aitask-scripts/lib/plan_paths.py`

Add the inverted search already specified in
`aidocs/framework/plan_path_reference_extraction_findings.md` §3–§5. It tests each **changed
path git reported** for a reference in a text, instead of extracting candidates through the
extension grammar, which misses Go, TS, Rust, extensionless files and spaced paths:

- `find_references(text, candidates) -> dict[path, list[Ref]]`, where `Ref = (line_no,
  heading)`. `heading` is the nearest enclosing markdown heading, or bold-label line,
  giving each mention its context (e.g. `Critical files`, `Context`, `Verification`). This
  is how a file list counts as evidence when present, without being required.
  - Match rule (§3): `(^|D)(\./)?<path>(D|\.(D|$)|$)`, with D = whitespace plus
    `[]["'`(){}<>,;:!?|=*#`.
  - NFC on both sides, with a normalised→original map; a collision reports all
    originals (§4).
  - `surrogateescape` throughout (§5).
  - Never raises on content.
- `find_dir_references(text, dirs)`: the same rule for `<dir>/` stems.
- `extract()` / `_EXTENSIONS` are **unchanged**, so the drift check, trail gather and parallel
  admission outputs do not shift. The docstring gains a paragraph on the second entry point.
  The seam guard stays green (no extension alternation in the new code).
- `tests/test_plan_paths.py`, new `ReferenceTests` class:
  - `.go`/`.ts`/`.rs`/`Makefile`/`bin/run` are found.
  - `src/app.py:42` and `src/app.py#L20` match; `src/app.py@v2` and `src/a` in
    `src/a+b.py` do not.
  - A sentence-final period matches, and so does a backtick-quoted spaced path.
  - NFC text vs an NFD path returns the original.
  - Invalid UTF-8 round-trips.
  - Heading attribution works for `##` headings and `**Label:**` lines.
  - The directory form works.
- The findings doc §3 is updated to name `find_references` as the implemented form.

## 2. Evidence helper — `aitask_shadow_scope.sh` + `lib/shadow_scope.py`

`./.aitask-scripts/aitask_shadow_scope.sh <task_id> [--checkout <dir>]` (F = followed task).
It reports evidence only: **it never classifies ownership and never says what may block.**

**Checkout resolution** (bash wrapper → `--checkout` for Python):
1. `--checkout` (`explicit`)
2. `aitask_task_worktree.sh resolve <task_name>` → `USABLE <path>` (`worktree_record`)
3. The bound followed pane's cwd. Source `aitask_shadow_capture.sh`, call
   `shadow_self_target`, then `ait_tmux display-message -p -t <pane>
   '#{pane_current_path}'` (gateway), then its git toplevel (`followed_pane`).
4. The shadow's own toplevel (`shadow_cwd`, a stated limit).

`SIGNAL:dedicated_worktree|yes|<reason>` when the checkout came from the worktree record
or is a linked worktree on `aitask/<task_name>`; otherwise `…|no`. This is evidence; the
prose rule says a dedicated worktree's changes are all the task's.

**Parts.** Each changed path yields up to two parts, reported separately:
- `committed`: the path in F's own tagged commits. `aitask_revert_analyze.sh --task-commits <F>`
  is filtered to matched-id == F exactly (a parent id also returns children), then
  `git diff-tree -r --no-commit-id --name-only -z` per hash. The part lists the hashes, so
  the shadow reads exactly `git show <hash> -- <path>`.
- `dirty`: whichever of `staged`/`unstaged`/`untracked` the path has now.

Enumeration is NUL-safe (`-z`, `core.quotePath=false`). `aitasks/`, `aiplans/` and
`.aitask-data/` are excluded.

**Evidence tokens per part** (comma-separated, each keeping its source):
- `f_commits:<n>`: on a committed part, F's tagged commits touching it. On a dirty part,
  `f_commit_earlier:<n>`, which tells the shadow the dirty change is newer than F's committed
  work.
- `f_plan:<heading>`: F's plan (active, else archived) references the path. There is one token
  per distinct enclosing heading, slugged to `[a-z0-9_-]`, ≤40 chars; `top` when there is no heading.
- `f_task:<heading>`: F's task body (`plan_paths.task_body_text`) references it.
- `f_plan_dir:<dir>`: F's plan references an ancestor directory (`<dir>/`).
- `baseline_dirty`: the path was already dirty when F was claimed. This comes from reusing
  `aitask_change_surface.sh list F` (`OTHER:` lines) run in the checkout; its baseline
  state is `SIGNAL:baseline|ok|missing|foreign`.
- `other_plan:t<X>` / `other_task:t<X>` / `other_commit:t<X>`: another active task
  (`status: Implementing`, not F / F's parent / F's children) references the path in its plan
  or task body, or has a tagged commit touching it.
- `-` when there is no evidence at all.

**Output** (path last; exit 0 for every resolution outcome, 2 for usage/malformed id):
```
TASK:<id>
CHECKOUT:<abs>|<explicit|worktree_record|followed_pane|shadow_cwd>
SIGNAL:dedicated_worktree|<yes|no>[|<reason>]
SIGNAL:plan|<ok|missing>[|<path>]
SIGNAL:task|<ok|missing>
SIGNAL:commits|<n>|<short hashes csv>
SIGNAL:baseline|<ok|missing|foreign>
SIGNAL:other_tasks|<n>|<csv ids>
PART|committed|<hashes csv>|<evidence csv>|<path>
PART|dirty|<staged,unstaged,untracked subset>|<evidence csv>|<path>
WARN:<reason>[|detail]
```
A path containing a newline is never emitted and is counted in `WARN:unrepresentable_paths|<n>`.

## 3. Prose contract — the shadow's judgement (`.claude/skills/aitask-shadow/`)

**`impl-challenge.md`**
- Inputs §2 / Assessment step 2: run the helper first; the parts are the candidate set.
  Each part is read through its own channel: `git show <hash> -- <path>` for committed,
  `git diff --cached` / `git diff` / the full file for dirty, all under `git -C "$checkout"`.
  Keep the composite rationale, the NUL-safe rule and the untracked-is-load-bearing rule.
  "The diff" becomes the **scoped composite**: the parts judged in scope or tentative.
- Step 3 is **replaced** by "Ownership judgement (default — no scope prompt)". The shadow
  judges every part by reading its change in the light of the task and plan, weighing the
  helper's evidence:
  - **Weights (guidance, not rules):**
    - `dedicated_worktree|yes` → the part is the task's.
    - `f_commits` → the committed part is the task's.
    - `f_plan` under a file-list-like heading → strong; `f_plan` elsewhere, `f_task` and
      `f_plan_dir` → supporting.
    - Content connection to the task (implements what the plan describes, tests or wires an
      in-scope change, lives in a new tree the task creates) can make an **unlisted** part
      credible.
    - `other_*` and `baseline_dirty` are counter-evidence, and can make a **listed** part foreign.
    - Plan lists are neither complete nor reliable.
  - A dirty part with `f_commit_earlier` is judged on its **own** content, separately from the
    committed part.
  - **Outcomes:**
    - *In scope*: reviewed normally; findings may be any disposition.
    - *Tentative*: plausibly related but uncertain. Reviewed, with findings in a separate
      "Tentative — possibly another task's" list. They are **never `blocking`**: in the block
      they are `Disposition: informational.`, with the body opening
      `Possibly another task's (<one-line reason>):`, so minimonitor files them as Informational
      and they cannot hold approval. They are promoted only when ownership becomes clear
      (new evidence, or the user says so).
    - *Excluded*: clearly foreign; no findings, not in the block.
    - *Unrelated*: no credible connection; not reviewed.
  - **Explain uncertain decisions briefly.** One line for each part that was judged against
    its evidence (an unlisted part taken in, a listed part excluded) and for each tentative
    part. The disclosure gives counts for the rest.
  - **Ask only about material ambiguity the shadow cannot resolve.** At most one targeted
    question per round, naming the parts. Otherwise decide and state the limit.
  - Context reads of other code are allowed, but a finding must be caused by an in-scope
    change. Another task's change is never reviewed on its own merits.
  - Limits are always stated and never claimed as full coverage: plan missing,
    `shadow_cwd`, baseline missing/foreign, and tentative/unrelated parts present.
  - Whole-workspace or another task's review happens only on an explicit user request, for
    that run, labelled in the disclosure.
- **Worked examples** (short, pinned by render tests), one per case:
  1. An unlisted related file taken in.
  2. A listed file excluded because another active task claims it and the content matches
     that task.
  3. A shared file with its committed part in scope and a newer foreign-looking dirty part
     tentative.
  4. A missing plan: judged from task mentions plus content, with the limit stated.
- Step 4: the only stop is "no part judged in scope or tentative". It reports "nothing of
  t<id>'s to review" plus the disclosure, and never a clean verdict when the plan is missing or
  parts were left unresolved.
- **Rechecks judge afresh.**
  - Every round re-runs the helper, reads the current changes and evidence, and makes a
    **fresh** scope judgement.
  - Earlier rounds' decisions and reasons, from this conversation, are **context, not rules
    to preserve**. A part excluded last round is re-judged on its current content like any other.
  - Clearly foreign work stays out of actionable findings every round, and plausibly related
    but uncertain work is tentative.
  - A prior concern whose part is now judged foreign or unrelated (including ones found
    through the old overbroad scope) is named once in prose as "outside t<id>'s scope, not
    carried". It never enters the block and needs no rejection.
  - A prior concern on a part now judged tentative is re-emitted only as informational.
    Genuine unresolved/regressed in-scope concerns remain.
  - The diff snapshot stays the scoped composite, for the round preamble.

**`impl-review-angles.md`**: the "the diff" definition becomes the scoped composite (parts). Angle C
gets a context-read clause. The disposition rubric adds that tentative-ownership findings cap at
`informational`.

**`round-preamble.md`**: the implementation snapshot is the scoped composite.
Heading 1 notes parts entering or leaving scope.

**`concern-format.md`**: add a producer rule only if it hosts producer obligations.

**`SKILL.md.j2`**: in `>i`, the default scope is the followed task's own changes, as judged
from the helper's evidence. In `>r`, a recheck makes a fresh ownership judgement, with earlier decisions as context.

Codex and OpenCode copies are generated and gitignored; the goldens are the committed record.

## 4. Housekeeping

- Follow `aidocs/framework/aitasks_extension_points.md` (new helper) and `shell_conventions.md`,
  including the whitelist entries for `aitask_shadow_scope.sh` across agents and the seed.
- Regenerate goldens: `tests/golden/procs/aitask-shadow/impl-challenge-{default,fast,remote}.md`
  and `tests/golden/skills/aitask-shadow/SKILL-*-claude.md`. Review the diff.

### Post-phase (risk mitigations)

- **live_replay_t1852_2**: run the helper read-only here for `1852_2` and `1847`, and check
  the evidence is sufficient for the right judgement. Expected: goengines committed parts carry
  `f_commits`; t1847/t1869 dirty files carry `other_*` / no `f_*` evidence for 1852_2, and
  `f_plan` for 1847. Record the output and the judgement it supports in the Final
  Implementation Notes.

## Tests

**New `tests/test_shadow_scope.sh`** (evidence reporting; git fixture modelled on
`tests/test_change_surface.sh` `new_repo`/`write_plan`; `TASK_DIR`/`PLAN_DIR` exports;
`--checkout`; F = t7, X = t9 `Implementing`). Each scenario the shadow must exercise
discretion over has a fixture proving the helper gives it the evidence it needs, and that
the helper itself emits **no verdict tokens** (`IN`/`OUT`/`blocking`):

1. **Unlisted related file:** F's plan references `goengines/x.go` only; untracked
   `goengines/go.mod` and `goengines/a b.go` (spaced; NUL-safety) → `PART|dirty|untracked|-|…`
   or `f_plan_dir:goengines` when the plan names the dir.
2. **Listed foreign file:** F's plan cites `lib/x.sh` under `## Context`; X's plan also names it,
   and it was dirty at claim → `f_plan:context,baseline_dirty,other_plan:t9`.
3. **Shared file, committed vs newer dirty:** F commits `a.sh` `(t7)`, then a foreign unstaged edit
   → `PART|committed|<hash>|f_commits:1,…|a.sh` **and**
   `PART|dirty|unstaged|f_commit_earlier:1,…|a.sh`, as separate parts. The variant where X
   declares it adds `other_plan:t9` to the dirty part only.
4. **Missing plan:** no plan file; the task body names `web/app.ts` →
   `SIGNAL:plan|missing`, `f_task:<heading>`; commits still reported.
5. **Non-Go / extensionless / heading context:** plan `**Critical files:**` lists `src/lib.rs` and
   `Makefile` → `f_plan:critical_files`; a mention under `## Verification` → `f_plan:verification`.
6. Staged + unstaged + untracked channels reported per part; a stray untracked file → evidence `-`.
7. **Dedicated worktree:** `git worktree add -b aitask/t7_x` via `--checkout` →
   `SIGNAL:dedicated_worktree|yes|branch`; the main checkout's dirt is absent; F's branch
   commits are found. A linked worktree on another branch → `…|no`.
8. `(t7)` does not match `(t70)`; parent id 7 does not absorb `(t7_1)` commits; X's
   commits give `other_commit:t9`.
9. A path with a newline → `WARN:unrepresentable_paths|1`.

**`tests/test_plan_paths.py`**: the reference tests in §1.

**`tests/test_skill_render_aitask_shadow.sh`**:
- Test 2g: drop `possibly unrelated to this task` and add `assert_not_contains "review everything"`.
- Pin across 3 profiles:
  - the helper invocation;
  - "Ownership judgement" and "not rules";
  - the four worked-example cases (unlisted related file taken in, listed file excluded,
    shared file split, missing plan);
  - tentative "never `blocking`" and `Possibly another task's`;
  - "ask only about material ambiguity";
  - the fresh-judgement recheck rule ("context, not rules to preserve");
  - the recheck carry-forward;
  - the explicit-request override;
  - `assert_not_contains` for any required `Files to modify` heading.
- Add a SKILL assertion for the `>r` sentence.

**Run:**
- the above;
- `tests/test_plan_paths_seam.sh`, `tests/test_remote_drift_check.sh`,
  `tests/test_change_surface.sh`, `tests/test_shadow_capture.sh`,
  `tests/test_shadow_snapshot.sh`, `tests/test_no_raw_tmux.sh`;
- the Python plan_paths/parity/trail/admission modules via `run_all_python_tests.sh --test-dir`;
- `./.aitask-scripts/aitask_skill_verify.sh`;
- `shellcheck` on the new script;
- a codex-variant render, grepping that the new contract is present.

## Step 9

Commit code + goldens as `bug: … (t1873)`, and the plan via `aitask_task_commit.sh`; then gates
and archival.

## Risk

### Code-health risk: medium
- `find_references()` adds a second entry point to the shared plan-path module, which a future consumer could confuse with `extract()` · severity: low · → mitigation: None (docstring names both; seam guard pins the grammar to one copy)
- A reused or hand-made `aitask/<task_name>` worktree could hold foreign dirt that the dedicated rule accepts · severity: low · → mitigation: None (user-directed; the disclosure names the basis)

### Goal-achievement risk: medium
- Ownership is now a model judgement, so a shadow can still misjudge (take in foreign work, or drop the task's own unlisted file). Only tentative/never-blocking handling bounds the damage · severity: medium · → mitigation: live_replay_t1852_2 checks the evidence supports the right call on the real case; worked examples pinned by render tests

- The other plan_paths consumers (drift check, parallel admission, trail gather) keep the extension grammar, so Go/Rust/TS/extensionless plans still give them no path evidence · severity: low · → mitigation: t1877

### Planned mitigations
- timing: post-phase | name: live_replay_t1852_2 | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — evidence sufficiency on the real shared-checkout case | desc: Run the evidence helper read-only for 1852_2 and 1847 in this checkout and record the evidence and the judgement it supports
- timing: after | name: adopt_referenced_paths_consumers | type: enhancement | priority: low | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — the same language gap in drift check / parallel admission / trail gather | desc: Evaluate moving the other plan_paths consumers from extension-grammar extraction to find_references() against their changed-path sets, measuring prompt-rate impact | created: t1877

## Post-Review Changes

### Change Request 1 (2026-09-24 11:40)
- **Requested by user:** Mixed ownership within one file. The helper reports staged and unstaged edits as one dirty part, but the prose required one outcome per part, so a followed-agent staged edit plus a foreign unstaged edit could not be separated.
- **Changes made:** `impl-challenge.md` now tells the shadow to split a dirty part by hunk when owners may differ. Staged (`git diff --cached`) and unstaged (`git diff`) hunks are judged separately, with hunk-level selection within either, and only attributable hunks are reviewed and snapshotted. The split is named in the disclosure, and worked example 3 is extended. The helper is unchanged (evidence only). Render-test assertions added; goldens regenerated.
- **Files affected:** `.claude/skills/aitask-shadow/impl-challenge.md`, `tests/golden/procs/aitask-shadow/impl-challenge-{default,fast,remote}.md`, `tests/test_skill_render_aitask_shadow.sh`

## Final Implementation Notes
- **Actual work done:**
  - `lib/plan_paths.py`: added the inverted, language-agnostic reference search specified in findings doc §3–§5:
    - `find_references` reports the section heading of each mention.
    - `find_suffix_references` is a weaker module-relative form.
    - `find_dir_references` matches explicit `<dir>/` mentions only.
    - `extract()` and its extension list are untouched, so the drift check, trail gather and admission outputs do not shift.
  - New `aitask_shadow_scope.sh` + `lib/shadow_scope.py` report ownership **evidence** per committed or dirty part:
    - evidence tokens: `f_commits`, `f_commit_earlier`, `f_plan:<section>`, `f_task:<section>`, the `*_suffix` forms, `f_plan_dir`, `baseline_dirty`, `other_plan`/`other_task`/`other_commit` (+ suffix forms);
    - `SIGNAL:` lines, including `dedicated_worktree`;
    - checkout resolution: explicit > worktree record > bound followed pane (via the capture helper's `shadow_self_target` + `ait_tmux`) > `shadow_cwd`.
  - `aitask_change_surface.sh`: new read-only `baseline` subcommand, the raw N1 signal.
  - Shadow prose:
    - `impl-challenge.md`: the ownership judgement (guidance-weighted, four worked examples, hunk-level split); tentative findings capped at informational and never blocking; one-question ambiguity rule; fresh-judgement rechecks with "not carried" prior concerns; a block scope rule.
    - `impl-review-angles.md`: scoped-composite definition, Angle C context clause, ownership cap.
    - `round-preamble.md`: scoped snapshot, with scope moves noted under heading 1.
    - `SKILL.md.j2`: the `>i`/`>r` sentences.
  - Whitelist entries in all 5 touchpoints. Goldens regenerated (they mirror the source diffs exactly).
- **Deviations from plan:**
  - (1) The claim baseline comes from a new `change_surface baseline` subcommand, not from `list` `OTHER:` lines. `list` folds "plan-named AND dirty at claim" into `UNKNOWN`, which loses the baseline evidence in exactly the listed-foreign-file case.
  - (2) Added `find_suffix_references` and the `*_suffix` tokens after the live replay: t1872's plan names goengines files module-relative (`internal/tools/benchgate/main.go`), so exact matching produced no counter-evidence.
  - (3) `find_dir_references` matches explicit `<dir>/` mentions only; a file path no longer counts as a mention of its directories, which had made `f_plan_dir:lib` noise.
  - (4) `.aitask-gates/` is excluded alongside the data paths.
  - (5) `tests/test_plan_paths_seam.sh` now locates change_surface's grammar line by content, since it was pinned to line 226.
  - (6) Post-review: hunk-level split of dirty parts (Change Request 1).
- **Issues encountered:**
  - Render assertions failed where the prose wrapped a pinned phrase across lines; the prose was reflowed.
  - Two multi-line `assert_contains` needles were replaced with single-line ones, because `grep -F` treats newline-separated needles as OR'ed patterns.
- **Key decisions:** following the user's direction, the helper reports evidence and makes no IN/OUT verdict or blocking eligibility. There is no transcript parsing, no required "Files to modify" heading, and no fingerprints or decision persistence. Rechecks judge afresh.
- **Live replay (post-phase live_replay_t1852_2), 2026-09-24:**
  - `aitask_shadow_scope.sh 1852_2 --checkout .`: 28 committed goengines parts with `f_commits:1`.
  - The newer benchgate dirty parts carry `f_commit_earlier:1,f_plan_dir:goengines,other_plan_suffix:t1872`, and `README.md` / `bench/baseline.txt` carry `other_plan:t1872`. That is enough for the shadow to judge those newer edits t1872's (excluded or tentative) rather than raise them as blocking.
  - t1873's own files carry `other_plan:t1873` / `other_task:t1873`.
  - `1847`: it has since been archived and committed; its remaining dirty paths carry other tasks' claims or no F evidence.
  - Run time is about 2.6 s on this checkout.
- **Upstream defects identified:**
  - `tests/test_change_surface.sh:95-110 (and most assert_contains/assert_not_contains calls in the file)` — arguments passed as (desc, haystack, needle) against the helper's (desc, needle, haystack), so the multi-line output becomes the grep pattern set and the negative assertions are weaker than they read.
