---
Task: t1734_shadow_plain_words_concerns_and_round_drift_preamble.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t1734 — shadow plain-words concerns and round-drift preamble

## Context

The shadow agent's review rounds (plan-challenge, impl-challenge,
plan-assumptions, plan-diagnose-errors) emit a prose findings list followed by
the machine-parseable concern block. A human watching `ait minimonitor` sees
each round's concerns, but has no cheap way to follow the *direction* of the
loop — what each concern really asks for, what the plan has become after
several rounds of incorporations, and whether those incorporations were worth
their cost. t1503 will make non-convergence *mechanically* visible (round
counter); this task adds the *human-readable* signal on the shadow side.

Two additions, both **prose emitted before the concern block** — the parser
(`concern_parser.py`), the minimonitor picker and
`review_loop.py::compose_recheck_prompt` are untouched:

1. **Plain-words line per concern** (every round, every producer): each prose
   finding ends with `In plain words: …`, a non-expert restatement of the
   *full block body* (composed after the body, so they never diverge).
2. **Round preamble "Where this is heading"** (rounds ≥ 2): six fixed headings
   comparing the current plan / code change against the round-1 snapshot and
   the previous round, with a fixed bottom-line rule.

Plus the **snapshot seam** that makes (2) possible for plan-phase reviews: the
plan is often only on the followed pane (pre-`ExitPlanMode`), so the shadow
must save what it read at round 1.

Verified facts from exploration:

- Producer sub-procedures live **only** in `.claude/skills/aitask-shadow/`; the
  Codex / OpenCode trees carry a `SKILL.md` wrapper only, and the render
  dep-walker (`lib/skill_template.py`, `FULL_PATH_REF_RE`) copies every `.md`
  reachable via a backticked full path
  `.claude/skills/aitask-shadow/<file>.md` into each per-agent rendered dir.
  So `round-preamble.md` becomes reachable simply by being referenced that way
  from the producers — no porting, no `.j2` change.
- `tests/test_concern_parser.py` already carries five producer-rule guard
  classes of identical shape (`TestProducerRoundHeaderRule` is the closest
  model: bolded directive + rules-list bullet, counted after whitespace
  collapse, synthetic negative control, fixture-dir production-assertion
  control, and a rendered-surface twin in
  `TestRenderedShadowDocsKeepTheGuarantees`).
- `aitask_shadow_rejected.sh` already has task-id validation
  (`resolve_task_id`), the per-task mutex (`lock_or_busy` on
  `rejected.md.lockd`), atomic writes (`ait_atomic_render`, refuses zero-byte),
  and `prune` sweeps every regular file at depth 1 of
  `.aitask-shadow/<task_id>/` — so `plan_r<N>.md` files are cleaned at archive
  for free.
- `tests/test_skill_render_aitask_shadow.sh` enumerates the procedure files
  (`PROC_FILES_INVARIANT`) and asserts closure completeness per agent; the new
  file must be added there. `impl-challenge.md` is the only Jinja-bearing
  procedure with committed goldens (`tests/golden/procs/aitask-shadow/
  impl-challenge-{default,fast,remote}.md`) — editing it requires regenerating
  those three.

## Files

| File | Change |
|---|---|
| `.claude/skills/aitask-shadow/round-preamble.md` | **new** shared procedure: audience rule, plain-words rule, preamble headings + bottom-line rule, vocabulary mapping (agent-only), snapshot protocol, per-producer subject table |
| `.claude/skills/aitask-shadow/plan-challenge.md` | snapshot step; two-placement rules ×2 |
| `.claude/skills/aitask-shadow/plan-assumptions.md` | same |
| `.claude/skills/aitask-shadow/plan-diagnose-errors.md` | two-placement rules ×2 (no snapshot — subject is the error picture) |
| `.claude/skills/aitask-shadow/impl-challenge.md` | two-placement rules ×2 (no snapshot — baseline is the committed plan) |
| `.claude/skills/aitask-shadow/concern-format.md` | short "prose-only, not parsed" note |
| `.aitask-scripts/aitask_shadow_rejected.sh` | `snapshot` + `snapshots` verbs; header comment; usage |
| `tests/test_shadow_snapshot.sh` | **new** bash test for the two verbs |
| `tests/test_concern_parser.py` | `TestProducerPlainWordsRule`, `TestProducerRoundPreambleRule`, two rendered-surface methods |
| `tests/test_skill_render_aitask_shadow.sh` | add `round-preamble` to `PROC_FILES_INVARIANT` |
| `tests/golden/procs/aitask-shadow/impl-challenge-{default,fast,remote}.md` | regenerate |
| `aidocs/framework/shadow_agent.md` | preamble + snapshot files under the review-loop section; t1503 cross-ref |
| `website/content/docs/workflows/shadow-agent.md` | user-facing paragraph |

## Step 1 — `round-preamble.md` (new shared procedure)

Path: `.claude/skills/aitask-shadow/round-preamble.md`. Pattern:
`impl-review-angles.md` (shared fragments, referenced by name, never restated
in the producers). **Must not** contain a concern block or any line starting
with `- [` (guards `TestShadowDocsNotParserLive`,
`test_every_producer_example_starts_with_a_round_header`). Sections:

1. **Who this is for (binding audience rule).** Every plain-words line and
   every preamble sentence is written for a reader who will not read the plan:
   outcomes and behaviours, not mechanisms; no file paths, function names or
   framework terms unless a single word has no plain substitute — then unpack
   it in the same sentence.
2. **The plain-words line.** Shape: the last line of each prose finding is
   `In plain words: <one or two sentences>`. Derivation order: compose the
   block body (with its trailer) **first**, then restate *that body* — the
   problem, why it bites, and what the fix would change — in plain language.
   It lives in the prose list only; never inside the block, never on a `- [`
   line. A concern with no plain restatement possible is a concern the author
   does not understand yet.
3. **The round preamble ("Where this is heading").** Applies to every round
   with N ≥ 2 (round 1 emits none). Placement: immediately after the one-line
   "which sub-procedure / which round" announcement and **before** the findings
   list — so always before the block. The six fixed headings with their plain
   labels, verbatim from the task:
   1. **Since last round** — added / removed / changed + what it means for the
      result.
   2. **Since the original plan** — cumulative vs the round-1 snapshot; each
      bullet names in words which earlier concern asked for it, or "nobody
      asked for this".
   3. **Is it still doing what was asked?** — `same thing` / `does less` /
      `does more` / `does something different`, **always** followed by
      "It no longer will: …" and "It now also will: …" (write "nothing" when
      empty; the label alone never stands).
   4. **How much bigger did it get?** — `not at all` / `a little` /
      `noticeably` / `a lot`, plus the list of what was added.
   5. **Was each change worth it?** — per change from (2): `needed` /
      `nice to have` / `not worth it` / `nobody asked`; closing count line
      `<a> needed / <b> nice to have / <c> not worth it / <d> nobody asked`.
   6. **Bottom line** — `on track` / `drifting` / `getting over-built` by the
      fixed rule, plus "I'd undo …" naming which incorporations to roll back
      into follow-up tasks (or "I'd undo nothing").

   **Fixed rule:** `getting over-built` if any change is `not worth it`, or
   any `nobody asked` change is `noticeably`+ in size, or (3) is `does more` /
   `does something different`; `drifting` if (3) is `does less`, or only
   `nice to have` changes drove `noticeably`+ growth; otherwise `on track`.
4. **Mapping to the framework vocabulary — for you, never in the output.**
   `needed` ⇔ the concern's `Improves:` touched an obligation dimension
   (`goal`, `correctness`, AC-obligated `robustness`/`performance`; i.e. it was
   `Disposition: blocking`); `nice to have` ⇔ `follow-up`; `not worth it` ⇔
   realized `simplicity` cost exceeds the quoted `Worsens:`, or the concern was
   `informational`; (3) is the `goal` dimension; (4) is realized `simplicity`.
   The preamble closes the loop on the impact vector: did the plan pay the
   price each concern quoted, only that price, and nothing nobody quoted?
5. **What you compare, per producer** (a small table):

   | producer | "the plan" means | baseline for heading 2 ("since the original plan") | previous round for heading 1 |
   |---|---|---|---|
   | `plan-challenge.md`, `plan-assumptions.md` | the plan text | `plan_r1.md` snapshot | `plan_r<N-1>.md` snapshot |
   | `impl-challenge.md` | the code change | **the approved plan** (committed; `aitask_shadow_context.sh`) vs the change as it now stands — heading 2 reads "Since implementation started" and is always answerable | `diff_r<N-1>.md` snapshot when present; otherwise your own previous round's findings only, and say so |
   | `plan-diagnose-errors.md` | the error picture on the followed screen | your round-1 findings | your previous round's findings |

   **Implementation rounds have no git baseline for "last round".** The
   workflow keeps implementation uncommitted until the Step-8 "Commit
   changes" and every revision overwrites the working tree, so git only ever
   exposes the *current* diff. Heading 2 (against the approved plan — what was
   going to be built vs what now exists) is therefore the load-bearing
   comparison for impl rounds and is always available; heading 1 is
   best-effort from the round-keyed diff snapshot below. Do not build anything
   more elaborate for it.

   The comparison is **done by you, reading the texts** — no diff tool; the
   only helper makes earlier texts *available*. Your own previous rounds'
   concerns (this conversation) plus the rejected store
   (`aitask_shadow_rejected.sh list`) are the record of "who asked for what".
6. **Snapshot protocol — plan rounds.** At the start of every plan-review
   round, after reading the plan, save the plan text under the same round
   number N the block header will carry. **Source preference (first that
   applies):**
   1. **The externalized plan** — `aitask_shadow_context.sh <task_id>` returned
      `PLAN_FILE:<path>` and its content matches what is on the followed
      screen (post-`ExitPlanMode`, the workflow externalizes immediately):
      `snapshot <task_id> <N> < <path>`.
   2. **The followed agent's draft-plan file** — the deep capture shows
      **exactly one distinct** path matching `~/.claude/plans/<name>.md`
      anywhere on the followed screen: the plan-approval dialog, a Write/Edit
      line, or any other mention. That file on disk is the clean, complete
      current plan (it is the document the agent is editing, not a rendering
      of it), so it is preferred over any capture even when no Write/Edit
      line is visible: `snapshot <task_id> <N> < <that path>`. More than one
      distinct path, or none ⇒ fall through.
   3. **A widened deep capture, delimited to the latest rendering, else
      partial** — scrollback is not a document: a plan longer than the
      default 400-row window loses its opening while the capture still
      "succeeds", and an ordinary revision cycle leaves an *older complete*
      rendering above a *truncated current* one, so "the title appears
      somewhere" proves nothing. Run
      `SHADOW_PLAN_CAPTURE_LINES=2000 ./.aitask-scripts/aitask_shadow_capture.sh --deep`
      and delimit: keep only the text from the **last** occurrence of the
      plan's title line (the first `#` heading you identified while reading
      the plan) to the end of the capture. That segment is the snapshot
      **only if** every top-level heading you identified while reading the
      plan occurs in it **exactly once** (a repeated heading means two
      generations are mixed; a missing one means the current rendering lost
      its head). Otherwise retry once with `4000` and re-check; if the check
      still fails, snapshot the delimited segment (or the whole capture when
      the title never appears) with `--partial` and say so in the prose. A
      terminal capture that cannot be delimited is **always** partial, never
      complete — never claim a baseline you did not verify.
   Parse `SNAPSHOT:plan|<N>|<complete|partial>|<path>` — the path is last and
   may itself contain `|`, so split on at most the first three separators
   (`split('|', 3)` → four fields). `LOCK_BUSY` (exit 3) / exit 2 / exit 4 →
   say the snapshot was skipped and continue (never a blocker). No task id ⇒
   no snapshot; say so.

   **Snapshot protocol — implementation rounds.** `impl-challenge.md` saves
   the composite diff text it assembled in its Inputs step 2 (the same text it
   reviews — commits + index + working tree + untracked, exactly as resolved
   there) with `snapshot <task_id> <N> --kind diff`. Cheap, one pipe, and the
   only thing that makes "since last round" answerable in an uncommitted
   working tree.

   **Reading back (round ≥ 2).** Run `snapshots <task_id>`; each line is
   `SNAPSHOT:<kind>|<N>|<complete|partial>|<path>`. Read `<kind>_r1.md` and
   `<kind>_r<N-1>.md`. A `partial` round-1 plan ⇒ say "the original-plan
   baseline is partial (capture window), so 'since the original plan' may miss
   early sections". A missing file (fresh shadow session, earlier skipped
   snapshot) ⇒ say which comparison is unavailable and fill that heading from
   what you do have — never fabricate a baseline.

## Step 2 — producer edits (four files, same two-placement shape)

For each producer, two bolded directives at the head of the emit/presentation
step and two rules-list bullets. Exact literal phrases are load-bearing for the
new guards (Step 5), so use them verbatim:

- Directive A (placed in the prose-presentation step — plan-challenge step 3,
  plan-assumptions step 3, plan-diagnose-errors step 4, impl-challenge
  "Findings presentation"):
  `**Add a plain-words line to every concern.**` … end every prose item with
  `In plain words: …`, derived from the block body composed first; rules in
  `.claude/skills/aitask-shadow/round-preamble.md`.
- Directive B (same step, before the list is produced):
  `**Open every round after the first with the "Where this is heading" preamble.**`
  … six headings, before the findings list and therefore before the block;
  round 1 emits none; follow `round-preamble.md`.
- Rules-list bullets (in the `Rules — all load-bearing for minimonitor's
  parser` list, after the Round header bullet):
  - `- **Plain-words line.** … "In plain words:" … prose-only: it is never a
    `- [` line and never inside the block; the block body stays byte-identical
    to what the picker forwards.`
  - `- **Round preamble.** … "Where this is heading" … prose-only, emitted
    before the findings list and the block, rounds ≥ 2 only; see
    `round-preamble.md`.`
- Snapshot step (plan-challenge and plan-assumptions): extend step 1 "Read
  the plan in full" with `**Snapshot the plan you read**` — the three-way
  source preference and the completeness check from Step 1 §6 by reference,
  the `snapshot` command with `plan_r1.md` named as what round 2 reads back,
  and the failure handling in one sentence. impl-challenge: after Inputs
  step 2 (the composite diff), `**Snapshot the diff you reviewed**` with the
  `--kind diff` command. plan-diagnose-errors: no snapshot step.
- Reference form: full path `.claude/skills/aitask-shadow/round-preamble.md`
  in backticks at least once per producer (dep-walker discovery + per-agent
  rewrite).
- `impl-challenge.md`: its "nothing after the block" rule is unaffected and
  both additions must say "before the block". Keep the Jinja untouched.

Check with `grep -c 'In plain words:'` ≥ 2 and
`grep -c 'Where this is heading'` ≥ 2 per producer after editing.

## Step 3 — `concern-format.md` note

Under "## The format" (after "Round header"), a short subsection **"Prose
around the block that is not parsed"**: the `In plain words:` lines and the
"Where this is heading" preamble are prose for the human, live before the
block, are not part of the format and are never forwarded; owning spec is
`round-preamble.md`. Reference by full path so it renders into the closure.

## Step 4 — `aitask_shadow_rejected.sh`: `snapshot` / `snapshots`

- Header comment: add the file layout line
  `.aitask-shadow/<task_id>/plan_r<N>.md` (plan text as read at round N,
  overwritten on a repeat of the same round), the two verbs, and that `prune`
  sweeps them (already true: `find -maxdepth 1 -type f`).
- `usage()`: add both verbs.
- `cmd_snapshot <task_id> <round> [--kind plan|diff] [--partial]` — stdin is
  the text:
  - `resolve_task_id`; round must match `^[1-9][0-9]*$` else `err_usage`
    (exit 2, message names the value); `--kind` defaults to `plan`, any other
    value ⇒ exit 2 (closed vocabulary — a constant `SNAPSHOT_KINDS="plan diff"`
    is the single source, also used by `cmd_snapshots`).
  - Read stdin **before** the lock into a variable (`content="$(cat)"`);
    whitespace-only ⇒ `err_usage "no <kind> text on stdin"` (exit 2), so an
    empty input never takes the mutex (mirrors `cmd_add`).
  - `store_paths_for`; `SNAP_FILE="$STORE_DIR/${kind}_r${round}.md"`;
    `lock_or_busy "$MUTATE_LOCK_TIMEOUT"` (same `rejected.md.lockd` mutex, so
    `prune` coordinates with it too).
  - Renderer `_snapshot_body()`: when `--partial`, first emit the marker line
    `<!-- partial -->` (then a blank line); then `printf '%s\n' "$content"`.
    Through `ait_atomic_render "$SNAP_FILE" _snapshot_body` (exit 4 on
    failure). A repeat of the same `(kind, round)` overwrites — the newest
    read of that round is the record.
  - Print `SNAPSHOT:<kind>|<round>|<complete|partial>|<path>` (path last —
    it is the only field that could carry `|`; three separators precede it,
    so consumers split on at most three: `split('|', 3)` → four fields; a
    higher limit would cut a pipe-bearing path).
- `cmd_snapshots <task_id>` — no lock (rename-atomic files):
  - `NO_SNAPSHOTS` when the dir is absent or holds no `<kind>_r[1-9][0-9]*.md`
    for any known kind.
  - Else one `SNAPSHOT:<kind>|<N>|<complete|partial>|<path>` per file,
    `partial` iff line 1 is exactly `<!-- partial -->`, ordered by kind
    (`plan` then `diff`) and within a kind numerically by N (`sort -n` on the
    extracted number, not lexically — `r10` after `r2`).
- `main`: dispatch the two verbs.
- Keep `shellcheck .aitask-scripts/aitask_shadow_rejected.sh` clean.

## Step 5 — tests

**`tests/test_shadow_snapshot.sh` (new)** — modelled on
`tests/test_shadow_rejected.sh` (scoped via `AITASK_SHADOW_DIR`, same
`hold_lock` / `release_held_lock` helpers, `set -uo pipefail`, PASS/FAIL
footer; no `( … )` subshell test bodies so no counters opt-in needed):

1. `snapshot 1734 1 <<< text` → `SNAPSHOT:plan|1|complete|…/1734/plan_r1.md`,
   file content equals input, exit 0.
2. Same round again with different text → overwritten in place, still one
   file; `snapshots` lists exactly one entry with the new content on disk.
3. Rounds 1, 2, 10 written out of order, plus `--kind diff` rounds 2 and 1 →
   `snapshots` prints plan 1, 2, 10 then diff 1, 2 (kind-grouped, numeric
   order within kind).
4. `--partial` → file starts with `<!-- partial -->`, `snapshot` and
   `snapshots` both report `partial`; a later complete overwrite of the same
   round flips it back to `complete`.
5. `snapshots` on an unknown id → `NO_SNAPSHOTS`, exit 0.
6. Held lock (`hold_lock`) → `LOCK_BUSY`, exit 3, no file written; released →
   succeeds.
7. Invalid ids (`abc`, `1_2_3`, `../x`) → exit 2; invalid rounds (`0`, `07`,
   `x`) → exit 2; unknown `--kind` → exit 2; empty / whitespace stdin → exit 2
   and no file, no lock dir.
8. Pipe-bearing store root (`AITASK_SHADOW_DIR="$TMP/sh|adow"` for that case
   only): the `snapshot` and `snapshots` lines still parse with a three-split —
   the fourth field is the full path with its `|` intact.
9. Snapshot beside an existing `rejected.md` leaves `list` output unchanged;
   `prune` removes `plan_r*.md` / `diff_r*.md` and reports `PRUNED:<id>`;
   `snapshots` → `NO_SNAPSHOTS` afterwards.

**`tests/test_concern_parser.py`**:

- Module-level predicates next to `_states_round_header_rule`:
  - `_PLAIN_WORDS_DIRECTIVE = "**Add a plain-words line to every concern.**"`;
    `_states_plain_words_rule(text)` = directive in flat AND
    `flat.count("In plain words:") >= 2`.
  - `_ROUND_PREAMBLE_DIRECTIVE = '**Open every round after the first with the "Where this is heading" preamble.**'`;
    `_states_round_preamble_rule(text)` = directive in flat AND
    `flat.count("Where this is heading") >= 2` AND `"round-preamble.md"` in flat.
- `TestProducerPlainWordsRule` and `TestProducerRoundPreambleRule`, each with
  `SHADOW_DIR`/`PRODUCER_MARKER`/`KNOWN_PRODUCERS`/`_producers` borrowed from
  `TestProducerShortRegionRule`, and four tests mirroring
  `TestProducerRoundHeaderRule`: producer set is the known set; every producer
  states the rule; synthetic negative control per placement (neither / bullet
  only / directive only / both); production-assertion-fails-on-a-real-offender
  via a patched `SHADOW_DIR` fixture dir (good.md, bad.md, notaproducer.md).
- **`TestRoundPreambleContract`** — pins the shared procedure's fixed
  contract directly (the producer guards only prove each producer *points at*
  it). A module-level `ROUND_PREAMBLE_CONTRACT` tuple of required literals,
  checked against the whitespace-collapsed text of `round-preamble.md`:
  the six headings (`Since last round`, `Since the original plan`,
  `Is it still doing what was asked?`, `How much bigger did it get?`,
  `Was each change worth it?`, `Bottom line`); the four "still doing" labels
  (`same thing`, `does less`, `does more`, `does something different`); the
  two mandatory list phrases (`It no longer will:`, `It now also will:`); the
  four growth labels (`not at all`, `a little`, `noticeably`, `a lot`); the
  four worth labels (`needed`, `nice to have`, `not worth it`, `nobody
  asked`); the three verdicts (`on track`, `drifting`, `getting over-built`)
  and `I'd undo`; the audience-rule anchor `will not read the plan`; the
  plain-words shape `In plain words:`; and the snapshot command
  `aitask_shadow_rejected.sh snapshot`. Tests: `test_contract_is_complete`
  (every literal present, offenders listed); `test_headings_are_in_order`
  (the six headings occur in that sequence); `test_guard_fails_when_a_section_is_deleted`
  (negative control: for each literal, a synthetic text with all literals
  except that one fails the check — loop with `subTest`, synthetic text
  only, no repo mutation).
- Three methods in `TestRenderedShadowDocsKeepTheGuarantees`:
  `test_every_rendered_producer_states_the_plain_words_rule`,
  `…_the_round_preamble_rule`, and
  `test_rendered_round_preamble_keeps_the_contract` (same
  `ROUND_PREAMBLE_CONTRACT` sweep over the rendered
  `aitask-shadow-fast-/round-preamble.md`).
- `TestShadowDocsNotParserLive` needs no change; it globs `*.md` and picks up
  `round-preamble.md` automatically.

**`tests/test_skill_render_aitask_shadow.sh`**: add `round-preamble` to
`PROC_FILES_INVARIANT` (the comment says "the other eight" — make it nine).
Regenerate the three `impl-challenge-*.md` proc goldens with the same render
the test uses (`$RENDER "$SKILL_DIR/impl-challenge.md" <profile.yaml> claude`)
and review the diff: only the added rule text may change.

## Step 6 — docs

- `aidocs/framework/shadow_agent.md`:
  - New subsection under "Review-loop automation": **"Where this is heading"
    — the human-readable drift signal** (what it is, the six headings by
    name, the fixed bottom-line rule, that it is prose-only and pre-block,
    grounded in the impact vector, and the t1503 cross-reference: t1503 is
    the mechanical non-convergence signal, this is the shadow-side narrative
    one; neither replaces the other).
  - Under "Concern rejection store": a paragraph **Plan snapshots** —
    `plan_r<N>.md` files, the two verbs, same mutex, pruned at archive.
- `website/content/docs/workflows/shadow-agent.md`: one user-facing paragraph
  under "Interrogate a plan" / near "Review the implementation" — every finding
  carries an "In plain words" line, and from the second recheck round on the
  shadow opens with "Where this is heading" (the six questions in plain
  language, ending in on track / drifting / getting over-built plus what it
  would undo). Then `cd website && python3 check_links.py --build`.

### Post-phase (risk mitigations)

1. [pin_snapshot_step_in_plan_producers] In `tests/test_concern_parser.py`,
   add `_states_snapshot_step(text)` = collapsed text contains the literal
   `aitask_shadow_rejected.sh snapshot` AND `plan_r1.md`, and a
   `TestPlanProducerSnapshotStep` class over the fixed subset
   `PLAN_PRODUCERS = ["plan-assumptions.md", "plan-challenge.md"]` (both must
   state it; `impl-challenge.md` / `plan-diagnose-errors.md` must NOT be
   required to), with a synthetic negative control (text with the round-preamble
   rule but no snapshot command → False) and a rendered-surface twin method in
   `TestRenderedShadowDocsKeepTheGuarantees`. Run
   `bash tests/run_all_python_tests.sh tests/test_concern_parser.py`.
2. [example_blocks_never_carry_prose_only_lines] In the same file, add
   `test_no_producer_example_block_carries_a_prose_only_line` to
   `TestProducerPlainWordsRule`: reuse the `fence_bodies` walker from
   `test_every_producer_example_starts_with_a_round_header` (lift it to a
   module-level helper), take every fence containing a `- [` line, and assert
   no line in it contains `In plain words:` or `Where this is heading`; plus a
   synthetic negative control proving the check fails on a fence that does.

## Verification

```bash
bash tests/test_shadow_snapshot.sh
bash tests/test_shadow_rejected.sh                    # unchanged verbs still pass
bash tests/test_archive_shadow_prune.sh               # prune path unchanged
shellcheck .aitask-scripts/aitask_shadow_rejected.sh
bash tests/run_all_python_tests.sh tests/test_concern_parser.py
bash tests/run_all_python_tests.sh tests/test_shadow_disposition_surfaces.py
bash tests/test_skill_render_aitask_shadow.sh
bash tests/test_shadow_phase_advisory.sh
./.aitask-scripts/aitask_skill_verify.sh
(cd website && python3 check_links.py --build)
```

Guard-can-fail checks (per project convention): temporarily verify each new
predicate returns False on a copy of a producer with one placement deleted —
covered by the synthetic negative controls and the fixture-dir production
assertion, no repo file mutation.

Live check (manual, after commit): spawn a plan-phase shadow from minimonitor
on any planning task, run "challenge the plan", then "refetch and recheck
round 2"; confirm `.aitask-shadow/<id>/plan_r1.md` and `plan_r2.md` exist,
the round-2 output opens with the six headings, each label carries its
explicit lists, every finding ends with `In plain words:`, and no preamble
sentence names a path or function. Offer this as the Step 8c
manual-verification follow-up.

## Post-implementation

Step 9 of the task workflow: commit as `feature: … (t1734)`, archive task and
plan, and send a `./ait note 1503 --from 1734` pointing at the new
preamble as the narrative counterpart of t1503's mechanical signal (Step 8e).

## Risk

### Code-health risk: low
- The four producer prompts grow again (two directives, two bullets, a snapshot step), and the "load-bearing for minimonitor's parser" rules list now also carries two prose-only rules — an agent could mistake them for block content and put an `In plain words:` sentence inside a concern body. · severity: low (residual — the example the agent pattern-matches against is pinned free of prose-only lines by inline post-phase example_blocks_never_carry_prose_only_lines; prompt length itself remains a bounded cost) · → mitigation: inline post-phase example_blocks_never_carry_prose_only_lines
- `snapshot` takes the same `rejected.md.lockd` mutex as `add`/`remove`/`prune`; `prune` waits only 2s at archive, so a snapshot in flight during archival makes that prune best-effort-skip (the directory is re-prunable, and snapshots are tiny writes). · severity: low · → mitigation: none
- Editing `impl-challenge.md` forces regeneration of its three proc goldens; an unrelated diff in them would be a renderer regression, so the diff must be reviewed, not rubber-stamped. · severity: low · → mitigation: none

### Goal-achievement risk: medium
- If the agent skips the round-1 snapshot, the round-2 preamble silently loses its "since the original plan" baseline and degrades to a last-round-only comparison; nothing today pins the snapshot instruction in the two plan producers, so a later edit could drop it unnoticed. · severity: low (residual — the snapshot instruction is pinned in both plan producers and their rendered surface by inline post-phase pin_snapshot_step_in_plan_producers; a runtime skip is still reported by the preamble as "original plan unavailable") · → mitigation: inline post-phase pin_snapshot_step_in_plan_producers
- The binding audience rule (no paths, functions, framework terms) is not machine-checkable; only a live two-round run proves the preamble reads as intended. · severity: medium · → mitigation: Step 8c manual-verification follow-up (live check listed in Verification), not a risk-mitigation task
- The task specifies the preamble subject for plan reviews ("the plan") and impl reviews ("the code change") but not for `plan-diagnose-errors.md`; this plan defines it as "the error picture on the followed screen" with no snapshot, which the user sees and approves here. · severity: low · → mitigation: none
- Implementation rounds have no git baseline for "since last round" (work stays uncommitted until Step 8 and revisions overwrite the tree); the round-keyed `diff_r<N>.md` snapshot is best-effort and, when absent, heading 1 degrades to the shadow's own previous findings. Accepted by the user as the less critical comparison — heading 2 (approved plan vs current change) is always answerable. · severity: low · → mitigation: none
- A plan snapshot taken from a capture window can be incomplete for a very long plan; the three-way source preference, the title-line completeness check and the `partial` marker make that loss visible rather than silent, but a `partial` round-1 baseline still weakens heading 2 for that session. · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: pin_snapshot_step_in_plan_producers | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — round-1 snapshot skipped or later deleted from the plan producers | desc: guard requiring plan-challenge.md and plan-assumptions.md (authoring + rendered) to carry the literal snapshot command and plan_r1.md, with negative control
- timing: post-phase | name: example_blocks_never_carry_prose_only_lines | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — prose-only rules in the parser-rules list emitted inside a concern body | desc: guard asserting no producer example block fence contains "In plain words:" or "Where this is heading", with negative control
