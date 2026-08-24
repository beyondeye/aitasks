---
Task: t1560_2_wire_step9_across_rendered_surfaces.md
Parent Task: aitasks/t1560_serialize_step9_merge_across_concurrent_tasks.md
Sibling Tasks: aitasks/t1560/t1560_3_document_merge_mutex_and_audit_merge_paths.md, aitasks/t1560/t1560_4_manual_verification_serialize_step9_merge.md
Archived Sibling Plans: aiplans/archived/p1560/p1560_1_merge_mutex_and_broker_script.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-24 17:55
---

# t1560_2 — Wire the Step 9 merge broker across every rendered surface

## Context

Sibling **t1560_1** shipped `.aitask-scripts/aitask_merge_task.sh` (the merge
broker), `lib/merge_lock.sh` and three opt-in seams in `lib/stale_lock.sh`.
Nothing invokes it yet — `grep -rn aitask_merge_task` outside the broker's own
files, its two tests and the five permission allowlists returns nothing. Step 9
still performs the merge as inline, unserialized bash in the shared repo root,
which is the concurrency hazard the parent task t1560 exists to close.

This task replaces that inline critical section with broker calls, gives **every**
verdict the broker can emit an explicit, verb-qualified disposition, and
propagates the change to every rendered variant, port and golden.

Parent spec: `aiplans/p1560_serialize_step9_merge_across_concurrent_tasks.md`
§4 (verdict control flow), §4a (the verification window), §5 (the prompt-drift
finding). Verdict strings and their lock semantics come from the
**implementation**, not that prose.

### Findings from plan verification (the existing plan is stale on three points)

1. **The cleanup block is already guarded.** Both t1560 and the current
   `p1560_2` say Step 9's cleanup is an unguarded
   `git worktree remove` / `rm -rf` / `git branch -d` sequence at
   `SKILL.md:836-841` that "must gain the error handling it currently lacks".
   **t1548 already fixed that.** It is now
   `./.aitask-scripts/aitask_task_worktree.sh remove <task_name> --strict`, run
   bare, at `SKILL.md:841-851`. The broker's `cleanup` verb delegates to that
   same helper, so this change is about running cleanup **under the reservation**
   and branching its verdicts — not about adding error handling.

2. **`tests/test_skill_render_task_workflow.sh` Test 4c will break.** Named by
   neither the task nor the plan. It pins three literals that move into the
   broker: `git checkout "$output_branch" --`,
   `git rev-parse --verify --quiet "refs/heads/$output_branch"`, and
   `git merge "aitask/<task_name>"`. `UNSAFE_OUTPUT_BRANCH` survives — it is now
   a broker verdict — as do the `Resolve the merge target` and
   `output_branch=$(sed -n 's/^Output branch: //p'` assertions.

3. **The shipped vocabulary is larger than §4's table, and two of the additions
   invert its assumptions.** §4 has no row for `PREFLIGHT_CHECKOUT_FAILED`,
   `PREFLIGHT_HEAD_MISMATCH`, `RETAINED`, `HOLDER_INCOMPLETE` or
   `FREE_GUARD_PRESENT`. Two of these are traps:
   - `PREFLIGHT_CHECKOUT_FAILED` / `PREFLIGHT_HEAD_MISMATCH` were **split out of
     `MERGE_FAILED`** by t1560_1 precisely because `MERGE_FAILED` retains the
     reservation and these **release** it — so treating them like `MERGE_FAILED`
     would run held-lock recovery against a free lock.
   - `RETAINED:<inner>` wraps a verdict that *reads* like a release but means
     **the lock is still held**. Treating it as its inner verdict wedges the lock.

The plan's own "what is NOT needed" claim **is** correct and is kept:
`workflow_phase.py:103` and `test_workflow_phase_prompt_drift.sh:60,104` both
match the 39-character prefix `Proceed with merge of code changes into`;
everything after `into` is outside both guards. Guard A greps
`.claude/skills/task-workflow/` recursively for `hits >= 1`.

### Decisions taken with the user

- **Extract to a procedure file.** The broker control flow goes in a new
  `.claude/skills/task-workflow/merge-broker.md`, invoked from Step 9 — the
  pattern already used by `remote-drift-check.md`, `merge-target-sync.md` and
  `gate-recording.md`.
- **Coverage scope is `begin` / `finish` / `abort` / `cleanup` / `status`** — the
  five verbs Step 9 invokes; **41 verb-qualified rows** over 30 distinct tokens.
  `force-release` is excluded: it is a human recovery ladder run outside the
  workflow, documented by **t1560_3**.

Both deviate from the acceptance criteria as written (which name
`SKILL-{default,fast,remote}.md` as the coverage target and four verbs), so the
task file and the durable plan are amended **first** — step 0 below.

## Implementation

### Pre-phase (risk mitigations)

1. [repin_injection_safety_pins] **Before** removing any of Test 4c's three
   assertions in `tests/test_skill_render_task_workflow.sh`, add their
   replacements in the same edit: assert the rendered Step 9 invokes
   `aitask_merge_task.sh begin` passing `"$output_branch"` as a bound, quoted
   shell variable, and assert (via a counted `grep -cE`, expecting 0) that no
   rendered command line substitutes the literal `<output_branch>` placeholder.
   Only once the replacements are in the file may the three moved git-primitive
   pins be deleted. The injection-safety property must never be unpinned, not
   even between two edits of one commit.

### 0. Amend the acceptance criteria — and commit it separately

Update `aitasks/t1560/t1560_2_wire_step9_across_rendered_surfaces.md` and
`aiplans/p1560/p1560_2_wire_step9_across_rendered_surfaces.md` to record: the
procedure extraction and its golden, the five-verb coverage scope, the
disposition-table contract below, finding 1 (cleanup already guarded by t1548),
and finding 2 (Test 4c). No silent deviation.

**Commit boundary — task data goes in its own commit, through `./ait git`.**
Files under `aitasks/` and `aiplans/` are committed with `./ait git`, never plain
`git` (CLAUDE.md). Land the amendment on its own, path-scoped, **before** any
source edit:

```bash
# -m goes BEFORE the `--`; after it git reads it as a pathspec and fails.
./ait git commit -o -m "ait: Amend t1560_2 AC for the merge-broker procedure extraction (t1560_2)" -- \
  aitasks/t1560/t1560_2_wire_step9_across_rendered_surfaces.md \
  aiplans/p1560/p1560_2_wire_step9_across_rendered_surfaces.md
```

`-o --` commits exactly those paths and ignores whatever else is staged. The
implementation, tests, rerender and goldens land later in a separate `feature:`
commit — an amended AC mixed into the implementation commit is unreviewable,
because the reviewer cannot tell which came first.

### 1. The disposition table — the canonical, machine-checkable contract

`merge-broker.md` carries **one table row per (verb, verdict) pair**, and that
table is what the coverage test parses. A verb-qualified row is the unit of
coverage: `NOT_HELD` appears under `finish`, `abort` **and** `cleanup`, and
`RETAINED` under `begin`, `finish` and `abort`, so a token-union check would pass
with an entire verb's branch missing. Prose alone cannot be asserted on; the
table can.

Five closed-vocabulary columns. `terminal-release` is deliberately **not** named
"release-call": it is the release verb that *terminates* the path, not one to
call on receipt of the verdict. `lock-through` is what says when.

| column | values |
|---|---|
| `lock` (at verdict time) | `ours-held` · `not-ours` · `none` |
| `terminal-release` | `finish` · `abort` · `ladder` · `none` |
| `lock-through` (stages the reservation spans *before* that release) | `n/a` · `immediate` · `verification` · `verification+cleanup` |
| `continues-to` | `approval` · `verification` · `archival` · `caller-path` · `stop-in-flight` · `stop` · `recovery` |
| `terminal-lock` | `released` · `held-ladder` · `n/a` |

`ladder` = the reservation is held and this branch makes **no further broker
release call**; it hands the user the recovery ladder. `caller-path` = resume
whatever path called this verb.

**Alternation.** A row may carry `;`-separated alternatives in the four closed
columns (`;`, not `|`: a bare pipe cannot live inside a markdown table cell); all alternating cells in a row must have **equal arity**, and
alternative *i* of each column pairs positionally with alternative *i* of the
others. Each positional tuple must satisfy the invariants independently. The
verdict cell is matched by **token prefix** (up to the first `:`), so a payload
containing `\|` never confuses the parser.

**The 41 rows.** Derived from the broker source, not from §4's prose:

*`begin`* — `begin <task_id> "$output_branch" "aitask/<task_name>" --wait-secs 120`

| verdict | lock | terminal-release | lock-through | continues-to | terminal-lock |
|---|---|---|---|---|---|
| `MERGE_OK:<sha>` | ours-held | finish | verification+cleanup | verification | released |
| `MERGE_CONFLICT:<paths>` | ours-held | finish;abort | verification+cleanup;immediate | verification;stop-in-flight | released;released |
| `MERGE_FAILED:<msg>` | ours-held | abort | immediate | stop-in-flight | released |
| `RETAINED:<inner>` | ours-held | finish | immediate | stop-in-flight | released |
| `BUSY:<holder>:<waited>` | none | none | n/a | stop-in-flight | n/a |
| `STALE_MERGE_RESIDUE` | none | none | n/a | stop | n/a |
| `DIRTY_TREE:<n>` | none | none | n/a | stop | n/a |
| `PREFLIGHT_MISSING:<b>` | none | none | n/a | stop | n/a |
| `PREFLIGHT_FOREIGN_WORKTREE:<p>` | none | none | n/a | stop | n/a |
| `PREFLIGHT_CHECKOUT_FAILED:<msg>` | none | none | n/a | stop | n/a |
| `PREFLIGHT_HEAD_MISMATCH:<b>:<head>` | none | none | n/a | stop | n/a |
| `UNSAFE_OUTPUT_BRANCH:<b>` | none | none | n/a | stop | n/a |
| `NO_SESSION_ANCHOR` | none | none | n/a | stop | n/a |
| `LOCK_UNAVAILABLE` | none | none | n/a | stop | n/a |

*`finish`* — `finish <task_id>`

| verdict | lock | terminal-release | lock-through | continues-to | terminal-lock |
|---|---|---|---|---|---|
| `RELEASED` | none | none | n/a | caller-path | n/a |
| `NOT_HELD` | none | none | n/a | caller-path | n/a |
| `NOT_HOLDER:<t>` | not-ours | none | n/a | caller-path | n/a |
| `NOT_OWNER_SESSION:<t>:<pid>` | not-ours | none | n/a | caller-path | n/a |
| `HOLDER_INCOMPLETE` | not-ours | none | n/a | caller-path | n/a |
| `RETAINED:release_failed` | ours-held | ladder | immediate | recovery | held-ladder |

*`abort`* — `abort <task_id>`

| verdict | lock | terminal-release | lock-through | continues-to | terminal-lock |
|---|---|---|---|---|---|
| `ABORTED` | none | none | n/a | stop-in-flight | n/a |
| `RELEASED_NO_MERGE` | none | none | n/a | stop-in-flight | n/a |
| `ABORT_FAILED:<msg>` | ours-held | ladder | immediate | recovery | held-ladder |
| `ABORT_UNSAFE:<state>:<remedy_flag>` | ours-held | ladder | immediate | recovery | held-ladder |
| `NOT_HELD` | none | none | n/a | stop-in-flight | n/a |
| `NOT_HOLDER:<t>` | not-ours | none | n/a | stop-in-flight | n/a |
| `NOT_OWNER_SESSION:<t>:<pid>` | not-ours | none | n/a | stop-in-flight | n/a |
| `HOLDER_INCOMPLETE` | not-ours | none | n/a | stop-in-flight | n/a |
| `RETAINED:<inner>` | ours-held | ladder | immediate | recovery | held-ladder |

*`cleanup`* — `cleanup <task_id> <task_name> --task-complete` (never releases)

| verdict | lock | terminal-release | lock-through | continues-to | terminal-lock |
|---|---|---|---|---|---|
| `CLEANED` | ours-held | finish | immediate | archival | released |
| `CLEANED_PARTIAL:<remains>` | ours-held | finish | immediate | stop-in-flight | released |
| `CLEANUP_REQUIRES_COMPLETION` | ours-held | finish | immediate | stop-in-flight | released |
| `TARGET_MISMATCH:<recorded>` | ours-held | finish | immediate | stop-in-flight | released |
| `NOT_HELD` | none | none | n/a | stop-in-flight | n/a |
| `NOT_HOLDER:<t>` | not-ours | none | n/a | stop-in-flight | n/a |
| `NOT_OWNER_SESSION:<t>:<pid>` | not-ours | none | n/a | stop-in-flight | n/a |
| `HOLDER_INCOMPLETE` | not-ours | none | n/a | stop-in-flight | n/a |

*`status`* — `status` (never acquires)

| verdict | lock | terminal-release | lock-through | continues-to | terminal-lock |
|---|---|---|---|---|---|
| `FREE` | none | none | n/a | approval | n/a |
| `FREE_GUARD_PRESENT:<dir>.gc` | none | none | n/a | approval | n/a |
| `HELD:<t>\|<pid>\|<live>\|<branch>\|<at>` | not-ours | none | n/a | approval | n/a |
| `HOLDER_INCOMPLETE:<pid>\|<live>` | not-ours | none | n/a | approval | n/a |

Notes the prose beside the table must carry:

- **`MERGE_OK` does not release now.** Its `finish` is terminal, reached only
  after verification *and* cleanup. Releasing on receipt would hand the shared
  tree to another task while `ait gates run` is reading it — the contamination
  hazard the reservation exists to prevent. `lock-through` is the column that
  says so, and `I6` is what enforces it.
- `RETAINED` is the trap: **the reservation is still held** even though the inner
  verdict reads like a release. On `begin` it attempts exactly one `finish` and
  then **branches on that call's own verdict** via the `finish` table — `finish`
  can also answer `NOT_HELD` (the lock is gone) or
  `NOT_HOLDER` / `NOT_OWNER_SESSION` / `HOLDER_INCOMPLETE` (it is not ours), and
  reporting any of those as "still held" would be false and would start the wrong
  recovery. Only `finish`'s own `RETAINED:release_failed` is the still-held case.
  On `finish` / `abort` the release has already been attempted, so those branches
  go straight to the ladder — never a second release call.
- **`CLEANED_PARTIAL` never archives.** A surviving worktree or
  `aitask/<task_name>` is exactly what the `POSTIMPL` resume needs; archiving
  would close the only route back to it, and would regress the pre-existing Step 9
  contract where the bare `--strict` teardown makes **only** `CLEAN` exit 0, so
  "archival cannot proceed over a worktree or branch that is still there". The
  options are "Retry cleanup" (branch on the new verdict; only a fresh `CLEANED`
  reaches archival) and "Release and stop in-flight". Either way `finish` runs, so
  the ladder terminates — but the task is not completed.
- `PREFLIGHT_CHECKOUT_FAILED` / `PREFLIGHT_HEAD_MISMATCH` **release**. They were
  split out of `MERGE_FAILED` for exactly this reason; calling `abort` on them
  runs held-lock recovery against a free lock.
- `ABORT_UNSAFE:<state>:<remedy_flag>` must **echo the broker-supplied
  `<remedy_flag>`** into the `force-release <flag> --yes` instruction — never a
  hardcoded `--abort-merge` / `--reset-hard`. All three shipped states currently
  carry `--reset-hard`; hardcoding it would be accidentally correct today and
  wrong the moment the broker's state→remedy mapping grows.
- **A stated deviation from §4a's "any refusal verdict → still `finish`".** That
  holds only where the broker reports **our** lock still held
  (`CLEANUP_REQUIRES_COMPLETION`, `TARGET_MISMATCH`). Where it reports the lock
  absent (`NOT_HELD`) or foreign (`NOT_HOLDER` / `NOT_OWNER_SESSION` /
  `HOLDER_INCOMPLETE`), `terminal-release` is `none`: a second call cannot change
  the outcome, and releasing another task's reservation is never correct.
- `LOCK_UNAVAILABLE` is declared in `_VERDICTS_BEGIN` but only `force-release`
  emits it. Its row exists because the vocabulary declares it; record the wart
  for t1560_1 rather than editing the broker.
- `BUSY` → name the holder, offer wait-and-retry (`--wait-secs 300`) / stop,
  bounded at 3 declines.

**The §4a verification-outcome table** is separate and also machine-checkable.
Every row's `lock-through` includes `verification` — that is the executable form
of "the reservation spans the gates run":

| outcome | cleanup | terminal-release | lock-through | continues-to |
|---|---|---|---|---|
| all `pass`/`skip`, or no declared gates and `verify_build` passed | `--task-complete` | finish | verification+cleanup | archival |
| `fail` caused by this task | no | none (keep holding) | verification | re-run under the reservation; after each failure offer "keep the reservation" / "release and stop here" |
| `fail` pre-existing / unrelated | `--task-complete` | finish | verification+cleanup | archival |
| `error` / `blocked:` / `pending` | no | finish | verification | stop-in-flight |
| `gates_rc` nonzero | no | finish | verification | stop-in-flight |

`abort` is valid on **no** §4a row — the merge commit already exists and
`git merge --abort` cannot undo it. `finish` on an in-flight row is a **release,
not a success claim**. Cleanup is a completion step only: every in-flight exit
retains `aitask/<task_name>` and its worktree, because that is the branch the
`POSTIMPL` resume re-merges.

### 2. New `.claude/skills/task-workflow/merge-broker.md`

Profile-invariant (no `{% if profile.* %}`). Sections, in this order and with
these exact headings — they are the handoff anchors step 4 asserts on:

- `## Carried state` — the four values that must remain valid across **every**
  hop, and which no hop may be entered without: `task_id`, `task_name`,
  `$output_branch` (bound and validated, never a literal), and `lock` (one of
  `none` / `ours-held` / `not-ours`). A hop that cannot state the current `lock`
  value must stop rather than guess.
- `## Preconditions` — worktree mode only, under Step 9's existing
  `**If a separate branch was created:**` prose gate. The broker has **no**
  no-task-branch guard: `begin` with `task_branch == output_branch` merges as
  "Already up to date" and returns `MERGE_OK` **with the reservation held**, so
  invoking it in current-branch mode acquires a lock nothing will release.
- `## Invariant` — verbatim:

  > Every path on which the broker reported the lock **held** ends in exactly one
  > `finish` or `abort`. Every path on which it is **not** held calls neither, and
  > never proceeds to verification, cleanup or archival.

- `## Output contract` — exit status is disjoint from the verdict: `0` = a
  verdict was produced (including `BUSY` and `MERGE_CONFLICT`), `1` =
  infrastructure failure with nothing on stdout, `2` = usage error. Exactly one
  verdict line on stdout; `WAITING:<holder>:<elapsed>` on stderr. Nonzero exit →
  **stop and diagnose**; never fall through to a verdict branch.
- `## Entry — acquire the reservation and merge` — in: `lock: none`. The `begin`
  table and its 14 branches. The tag/detached-HEAD and foreign-worktree
  explanations move here from Step 9's pre-flight prose, since the broker now
  performs those checks.
- `## Return to Step 9 — Verify implementation` — out: `lock: ours-held`, and it
  **stays** `ours-held` for the whole of Step 9's verification block. Hands
  control back to Step 9.
- `## Re-entry — release decision` — in: `lock: ours-held` plus the gates
  outcome. The §4a table.
- `## Exit — cleanup and release` — the `cleanup`, `finish` and `abort` tables.
  Terminal state is `lock: none` on the archival path **and on every ordinary
  in-flight exit** (released; task and branch retained). **Rows whose
  `continues-to` is `recovery` are exempt:** their terminal state is
  `held-ladder` — the reservation is still held, the agent must say so in plain
  words, must not report a released lock, and must not take ordinary in-flight
  routing. They leave via `## Recovery ladder` instead.
- `## Recovery ladder` — where every `held-ladder` row goes: `status`, then
  `force-release` echoing the broker-named remedy flag, `rmdir <lock_dir>.gc`
  first if a guard leaked. Point at it; do not render `force-release`'s own
  verdicts (t1560_3).

**Per-verdict branches.** Below the tables, each of the 41 rows gets exactly one
operational branch introduced by a level-4 heading `#### <verb> / <TOKEN>` (e.g.
`#### begin / MERGE_OK`). The branch body must name that row's
`terminal-release` and `continues-to` values in its instructions. The heading is
the linkage anchor step 4.7 asserts on — a correct table is worthless if the
prose beside it says something else.

The verification block **stays in `SKILL.md`** because
`tests/test_gate_verifiers.sh:246` pins `ait gates run` and the engine sentinel
to that exact file, and the `record_gates` Jinja block lives with it. That is
what creates the Step 9 → procedure → Step 9 → procedure hop sequence; the named
headings above plus the `## Carried state` block are what make it auditable
instead of implicit.

### 3. Step 9 in `.claude/skills/task-workflow/SKILL.md`

The **only** hand-edited copy. Re-locate the blocks; line numbers drift.

- Keep the `output_branch` resolution block unchanged (`:731-748`).
- Replace the inline pre-flight (`:750-763`) with the **queue probe**:
  `aitask_merge_task.sh status`, four verdicts branched inline per the table — it
  stays here because it shapes the approval question.
- Keep the **non-skippable banner** (`:765-775`) byte-identical.
- Append the queued clause to the **end** of the approval question, leaving the
  prefix untouched: `… branch (<provenance>)? Queued behind t<N>.` — rendered
  only when the probe reported `HELD`.
- Keep the `record_gates` merge_approved block (`:778-781`).
- Replace the `git status --porcelain` check (`:783-786`), the
  checkout/symbolic-ref/merge block (`:788-794`) and the one-line conflict
  handler (`:796`) with the hand-off to `merge-broker.md`
  `## Entry — acquire the reservation and merge`.
- Keep the verification block (`:798-839`) where it is, prefixed by a line naming
  it as the re-entry target of `## Return to Step 9 — Verify implementation` and
  stating that the reservation is held for its entire duration, and suffixed by
  the hand-off to `## Re-entry — release decision`. Those two lines bracket
  `ait gates run`, which is what step 4.6 asserts positionally.
- Replace the cleanup block (`:841-851`) — cleanup now happens inside
  `## Exit — cleanup and release`.
- Archival and everything below unchanged, prefixed by a line stating it is
  entered with `lock: none`.

### 4. Tests

**`tests/test_merge_broker_rendered_verdicts.sh`** (new). For each profile it
renders `SKILL.md` and `merge-broker.md` via
`.aitask-scripts/lib/skill_template.py` and parses the **disposition tables** out
of the rendered `merge-broker.md` — never a token grep over concatenated prose.

1. **Coverage.** Parse `./.aitask-scripts/aitask_merge_task.sh --list-verdicts`
   (the live seam, never a transcription). For each of the five verbs and each of
   its verdict tokens, assert **exactly one** row exists under that verb's table
   whose verdict cell starts with that token. Missing → fail printing
   `MISSING_ROW:<verb>:<token>`; duplicated → `DUPLICATE_ROW:<verb>:<token>`.
   Also assert no row exists for a token the broker does not declare
   (`UNKNOWN_ROW:<verb>:<token>`), so the table cannot drift ahead of the broker.
2. **Closed vocabularies + arity.** Every cell value must come from its column's
   set; all alternating cells in a row must have equal arity. Failures name the
   row and column.
3. **`ABORT_UNSAFE` remedy.** The `abort`/`ABORT_UNSAFE` row and its
   `#### abort / ABORT_UNSAFE` branch contain no literal `--abort-merge` /
   `--reset-hard`, scoped to that block (the recovery ladder legitimately names
   flags).
4. **Prompt compatibility.** Locate the rendered line carrying the phase anchor,
   **extract the quoted question text from it**, instantiate its placeholders the
   way Step 9 does at runtime, and regex-search *that* value with the real
   `workflow_phase.WORKFLOW_PROMPTS` — both without the queued clause and with it
   appended. Asserting a hardcoded copy of the question would keep passing while a
   rewrite broke the real anchor, which is the one thing this check exists to
   catch. Fail as `PROMPT_ANCHOR_MISSING` / `QUESTION_NOT_EXTRACTED` /
   `PROMPT_NO_MATCH:<variant>`.
5. **Handoff anchors.** Each of the four handoff headings appears in the rendered
   `merge-broker.md`, and `SKILL.md` references each by name — asserted in both
   directions, so moving one side without the other fails.
6. **Handoff ordering (release-after-verification, structurally).** In the
   rendered `SKILL.md`, the reference to
   `## Return to Step 9 — Verify implementation` appears at a **lower line number
   than** the `ait gates run` line, and the reference to
   `## Re-entry — release decision` at a **higher** one. This is what proves the
   gates run is entered *and completed* inside the held window, on the rendered
   output rather than the source.
7. **Branch linkage.** For every row, exactly one `#### <verb> / <TOKEN>` heading
   exists (`MISSING_BRANCH` / `DUPLICATE_BRANCH`), every such heading has a row
   (`ORPHAN_BRANCH`), and the branch body names that row's `terminal-release` and
   `continues-to` values (`BRANCH_CONTRADICTS_ROW:<verb>:<token>:<column>`).

**Negative controls** — each a single mutation on a scratch copy of
`merge-broker.md`, each of which must fail *naming the specific row and check*:

- delete the `cleanup` / `NOT_HELD` **row** → `MISSING_ROW:cleanup:NOT_HELD`
  **while the `finish` and `abort` `NOT_HELD` rows remain present**. This is the
  duplicated-name control: a token-union check passes here, so it pins that the
  check is genuinely verb-qualified.
- delete the `begin` / `RETAINED` row → `MISSING_ROW:begin:RETAINED` while
  `finish`/`RETAINED` and `abort`/`RETAINED` remain.
- flip `begin` / `MERGE_OK`'s `lock-through` from `verification+cleanup` to
  `immediate` → must fail **`I6`** naming `begin:MERGE_OK` — *not* the coverage
  check and *not* `I1`. This is the release-ordering control: the pre-rename
  plan's `I1` accepted this mutation, which is the merge race reopening.
- rewrite the `#### abort / ABORT_FAILED` branch body to instruct `finish`
  instead of `ladder` → must fail
  `BRANCH_CONTRADICTS_ROW:abort:ABORT_FAILED:terminal-release`, proving the
  linkage check catches a table that is right beside prose that is wrong.

**`tests/test_skill_render_task_workflow.sh`:** add `merge-broker.md` to
`WRAPPED_FILES_INVARIANT`, and complete the pre-phase's re-pin-then-delete of
Test 4c's three moved assertions.

### Post-phase (risk mitigations)

1. [structural_held_lock_invariant_assertion] In
   `tests/test_merge_broker_rendered_verdicts.sh`, assert the invariants
   **executably** over the parsed table, per positional alternative:
   - `I1` `lock=ours-held` ⟹ `terminal-release ∈ {finish, abort, ladder}`
   - `I2` `lock ∈ {none, not-ours}` ⟹ `terminal-release=none` ∧ `lock-through=n/a` ∧ `terminal-lock=n/a`
   - `I3` `continues-to ∈ {verification, archival}` ⟹ `lock=ours-held`
   - `I4` `continues-to=archival` ⟹ `terminal-release=finish`
   - `I5` §4a table: `cleanup=no` ⟹ `continues-to ≠ archival`
   - `I5b` §4a table: every row's `lock-through` contains `verification`
   - `I6` `continues-to=verification` ⟹ `lock-through ∈ {verification, verification+cleanup}` — **no branch may release before the gates run completes**
   - `I7` `terminal-release=ladder` ⟺ `continues-to=recovery` ⟺ `terminal-lock=held-ladder`
   - `I8` `terminal-release ∈ {finish, abort}` ⟹ `terminal-lock=released`
   Each violation fails naming `<verb>:<verdict>` and the invariant id.
   *(Disposition changed from the confirmed `after`/spawned to inline
   `post-phase`: once the dispositions are a parsed table rather than prose, a
   safe enforceable version costs a handful of assertions and belongs with the
   first live consumer of the broker — this task — rather than after it.)*
2. [verb_coverage_drift_guard] Parse the verb names from `--list-verdicts` (the
   token before each `:`), subtract `force-release`, and assert the result equals
   the tested set `begin finish abort cleanup status` exactly. A verdict added to
   an existing verb is already caught because the vocabulary is sourced live;
   this closes the remaining hole, where a **new verb** would ship with no
   rendered branch and no failing test. Fail printing the unexpected/missing verb
   names.

### 5. Rerender, goldens and ports — same commit

```bash
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done
```

One positional profile argument, no flags; each invocation covers that profile
across claude/codex/opencode, so the `.agents/…-codex-` and `.opencode/…` ports
need no separate step. `merge-broker.md` is picked up automatically — the
dep-walker discovers backtick-wrapped refs whose file exists, so no manifest
registration.

Regenerate goldens with the documented loop: `SKILL-{default,fast,remote}.md`,
plus a single canonical `merge-broker-default.md` (profile-invariant files keep
one golden plus the byte-equality invariance assertion — the coverage test
asserts against the three live **renders**, so per-profile coverage is proven
regardless of golden count).

Stage explicitly by path: a rerender touches many targets and only the
task-workflow ones belong in this commit. This commit contains **no** `aitasks/`
or `aiplans/` file — those landed in step 0's separate `./ait git` commit.

## Verification

- `bash tests/test_merge_broker_rendered_verdicts.sh` — passes; each of the four
  negative controls fails naming its specific row and check id
- `bash tests/test_skill_render_task_workflow.sh` — golden diffs green, Test 4c
  green against the re-pinned assertions
- `bash tests/test_workflow_phase_prompt_drift.sh` — passes **unchanged**
- `bash tests/test_gate_verifiers.sh` — Test 6 still finds `ait gates run` and the
  engine sentinel in `SKILL.md`
- `bash tests/test_skill_render.sh`, `bash tests/test_skill_verify.sh`
- `./.aitask-scripts/aitask_skill_verify.sh` exits 0
- `shellcheck tests/test_merge_broker_rendered_verdicts.sh`
- Read the **rendered** `merge-broker-default.md` and confirm no §4a in-flight row
  reaches `cleanup`, and that no `recovery` branch claims a released lock
- `git log --oneline -2` shows the `ait:` task-data commit **before** the
  `feature:` implementation commit, with no overlap in paths
- `git diff` on the goldens is reviewable and matches the source change

## Notes for the implementer

- Only `default`/`fast`/`remote` exist here; the parent's `fast_worktree` is a
  downstream install.
- Under this repo's own `fast.yaml` (`create_worktree: false`) the merge block
  never runs, so day-to-day use will not exercise this — the tests are the only
  regression net.
- Re-entry Routing's `POSTIMPL` claim that `aitask/<task_name>` already exists
  holds **because** no in-flight row cleans up. If a rendered branch cleans up
  before archival, that is the bug.

## Non-goals

- No changes to the broker — **t1560_1**. Two warts to record and coordinate
  rather than fix: `LOCK_UNAVAILABLE` is declared in `_VERDICTS_BEGIN` but only
  `force-release` emits it; and a flag given without its value (`--wait-secs`)
  exits 1 under `set -e` instead of 2.
- No website docs, no audit of the other merge paths — **t1560_3**.
- **No fetch added to Step 9** — **t1393**. Record in Final Implementation Notes
  that t1393's wiring point is now the broker script.

## Risk

### Code-health risk: medium
- Step 9 is the framework's most consequential agent-executed procedure, and this rewrites its critical section. Because the artifact is instructions rather than executable code, a wrong branch surfaces as an agent doing the wrong thing, not as a crash — and this repo's own `fast` profile (`create_worktree: false`) never runs the block, so local use will not catch it. · severity: medium (residual — the disposition table plus I1–I8 make the lock-wedging and release-ordering classes machine-detectable; branch *wording* beyond the linkage check remains unverified) · → mitigation: inline post-phase structural_held_lock_invariant_assertion
- Rewriting `test_skill_render_task_workflow.sh` Test 4c deletes three existing injection-safety pins (`git checkout "$output_branch" --`, the fully-qualified `rev-parse`, the quoted `git merge`). The property genuinely relocates into the broker, but deleting a guard rather than re-pinning it at its new home is how a safety property silently evaporates. · severity: low (residual — addressed by inline pre-phase repin_injection_safety_pins) · → mitigation: inline pre-phase repin_injection_safety_pins
- The procedure extraction introduces a four-hop cycle (Step 9 → `## Entry` → Step 9 verification → `## Re-entry` → `## Exit`), which a later editor can break by moving one side. · severity: low (residual — the named handoff headings, the `## Carried state` block, the bidirectional anchor assertion and the positional ordering check in test steps 5–6 make a one-sided move fail the build) · → mitigation: inline post-phase structural_held_lock_invariant_assertion

### Goal-achievement risk: low
- Five shipped verdicts have **no row** in the parent plan's §4 table — `PREFLIGHT_CHECKOUT_FAILED`, `PREFLIGHT_HEAD_MISMATCH`, `RETAINED`, `HOLDER_INCOMPLETE`, `FREE_GUARD_PRESENT`. Their dispositions are decided by this task rather than inherited, as is the stated deviation from §4a's "always finish" on foreign/absent locks. · severity: low (residual — every one is an explicit reviewable row, derived from the broker source, with the two inversion traps and the deviation called out by name) · → mitigation: inline post-phase structural_held_lock_invariant_assertion
- The coverage test proves every verdict has a row *and* a non-contradicting branch; it cannot prove the branch's full prose instructs the agent well. · severity: low (residual — I1–I8 plus the linkage check make the wedge-producing and race-reopening classes executable; what remains unverified is wording quality, not disposition) · → mitigation: inline post-phase verb_coverage_drift_guard

### Planned mitigations
- timing: pre-phase | name: repin_injection_safety_pins | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: Test 4c deletes three injection-safety pins | desc: add the replacement broker-call injection pins before deleting the moved git-primitive pins
- timing: post-phase | name: structural_held_lock_invariant_assertion | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: coverage proves verdict presence but not branch correctness; five verdicts whose dispositions this task decides; the four-hop procedure cycle | desc: assert invariants I1-I8 executably over the parsed disposition table plus the bidirectional handoff anchors
- timing: post-phase | name: verb_coverage_drift_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: a future broker verb would escape coverage silently | desc: assert the tested verb set equals --list-verdicts' verbs minus force-release

## Final Implementation Notes

- **Actual work done:** New `.claude/skills/task-workflow/merge-broker.md` (590
  lines) carrying five disposition tables — 41 verb-qualified rows over 30
  distinct tokens — the §4a verification-outcome table, five named handoff
  anchors and one `#### <verb> / <TOKEN>` operational branch per row. Step 9 in
  the Jinja source now probes the queue, appends `Queued behind t<N>.` to the end
  of the (otherwise byte-identical) approval question, hands the merge to the
  broker, brackets the verification block with the two anchors, and routes
  cleanup/release through the procedure. New
  `tests/test_merge_broker_rendered_verdicts.sh` (25 assertions, **7** negative
  controls); `tests/test_skill_render_task_workflow.sh` re-pins injection safety
  and registers the new procedure in `WRAPPED_FILES_INVARIANT`. Rerendered all
  three profiles; the tracked `task-workflow-remote-` ports in all three agent
  trees updated (`default`/`fast` renders are gitignored by
  `.gitignore:52 .claude/skills/*-/`). Goldens: `SKILL-{default,fast,remote}.md`
  regenerated plus the new canonical `merge-broker-default.md`.

- **Deviations from plan:**
  - **Alternation separator is `;`, not `|`.** A bare pipe cannot live inside a
    markdown table cell, and escaping it (`\|`) collides with the payloads that
    genuinely contain one (`HELD:<t>\|<pid>\|…`). The plan's table has been
    corrected to match.
  - **Five handoff anchors, not four.** The `status` verdicts and their branches
    live in `merge-broker.md` under `## Probe — report the queue holder` rather
    than inline in Step 9, so all 41 rows sit in one parsed file and Step 9 stays
    lean — which was the point of the extraction. Step 9 still *calls* the probe
    before the approval question, as specified.
  - **The `## Recovery ladder` is a sixth section** but not a handoff anchor: it
    is where `terminal-lock: held-ladder` rows terminate.

- **Issues encountered:**
  - `./ait git commit -o -- <paths> -m "<msg>"` **fails** — after `--` git reads
    `-m` as a pathspec. The correct form is `-o -m "<msg>" -- <paths>`, and the
    plan's step-0 snippet was corrected in place so the recorded command is
    copy-safe.
  - Three defects found in review of the first implementation, all fixed:
    `cleanup / CLEANED_PARTIAL` routed to `archival`, which would archive a task
    over a surviving worktree or branch — a regression against the pre-existing
    Step 9 contract (bare `--strict` teardown: only `CLEAN` exits 0) and a
    destruction of the `POSTIMPL` recovery route. It now stops in-flight.
    `begin / RETAINED` claimed any non-`RELEASED` `finish` result proved the lock
    was still held, which is false for `NOT_HELD` / `NOT_HOLDER` /
    `NOT_OWNER_SESSION` / `HOLDER_INCOMPLETE`; it now branches on the `finish`
    table. The prompt check asserted a hardcoded copy of the approval question
    instead of the rendered one; it now extracts the real text and adds negative
    control G to prove a reworded prefix fails.

- **Key decisions:**
  - **The disposition table is the contract, not the prose.** A `grep -w` union
    over rendered text cannot tell which verb a token belongs to — `NOT_HELD`
    appears under three verbs and `RETAINED` under three — so an entire verb's
    branch can go missing while the check passes. Negative control A pins exactly
    that case by deleting `cleanup / NOT_HELD` while the `finish` and `abort` rows
    stay.
  - **`terminal-release` + `lock-through`, not "release-call".** A single column
    saying "`finish`" is temporally ambiguous: an implementation calling `finish`
    immediately after `MERGE_OK` would satisfy it and reopen the merge race.
    `lock-through` names the stages the reservation must span first, and `I6`
    enforces it; negative control C performs that exact mutation and must fail
    naming `I6`, not `I1`.
  - **The verification block stays in `SKILL.md`.** `tests/test_gate_verifiers.sh`
    Test 6 pins `ait gates run` and the engine sentinel to that exact file, and
    the `record_gates` Jinja block lives with it. That is what creates the
    four-hop cycle, so the ordering check (test step 6) asserts on the **rendered**
    SKILL.md that the acquire anchor precedes `ait gates run` and the release
    anchor follows it.
  - **`force-release` is excluded** from coverage: it is a human recovery ladder
    run outside the workflow. `merge-broker.md` points at it without rendering its
    verdicts — **t1560_3** documents it.
  - Confirmed by verification, not assumption: `workflow_phase.py:103` and
    `tests/test_workflow_phase_prompt_drift.sh:60,104` both match the 39-character
    prefix, so appending the queued clause needed **no** change to either.

- **t1393 (no fetch in Step 9):** its wiring point is now
  `.aitask-scripts/aitask_merge_task.sh` — the fetch belongs inside the broker's
  critical section, before the pre-flight, so the merge target is refreshed while
  the mutex is held rather than in Step 9's prose.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_merge_task.sh:499 — `LOCK_UNAVAILABLE` is declared in
    `_VERDICTS_BEGIN` but `cmd_begin` (110-217) never emits it; only
    `cmd_force_release` does (490, 492). The rendered `begin / LOCK_UNAVAILABLE`
    branch is therefore unreachable, and any coverage test sourcing the vocabulary
    is forced to require a branch for a verdict the verb cannot produce.
  - `.aitask-scripts/aitask_merge_task.sh:116 — a flag given without its value
    (`begin --wait-secs` with nothing after it) makes `shift 2` fail under
    `set -euo pipefail`, exiting **1** (documented as "infrastructure failure")
    instead of the **2** the header specifies for usage errors.
  Both are t1560_1's surface; per this task's non-goals they are recorded for
  coordination rather than fixed here.

