---
Task: t2072_shadow_concern_block_review_label.md
Base branch: main
Output branch: main
---

# t2072 — Review label line above the shadow concern block

## Context

With many agents in parallel, a user looking at the last
`===AITASK-CONCERNS===` … `===END-CONCERNS===` block in an `aitask-shadow` pane
cannot tell whether it came from a plan review or an implementation review
without scrolling up to the round's opening line (which only exists when the
phase signal picked the default). Fix: every producer emits one fixed,
plain-text label line **immediately above** the opening fence. No task or round
number (the round already lives in the `Round:` header inside the block).

Parser safety (verified): every consumer locates the block by substring search
for the opening fence (`concern_parser._last_block_region` uses `rfind`;
`_iter_block_regions`, `block_head_truncated` are substring-based; no other
`.aitask-scripts` code reads the fence). Text above the fence is never seen —
same as the existing `In plain words:` lines and the "Where this is heading"
preamble. Rechecks (`>r`, `>r<code>`, minimonitor's injected
`refetch and recheck round N`) re-run the producer's emit step end to end
(`SKILL.md.j2` `>r` bullet), so a rule stated in the producer covers them.

## Final labels (one per producer)

| producer | label line |
|---|---|
| `plan-challenge.md` (`>pc`) | `Review: plan challenge` |
| `plan-assumptions.md` (`>pa`) | `Review: plan assumptions` |
| `plan-diagnose-errors.md` (`>d`) | `Review: error diagnosis` |
| `impl-challenge.md` (`>i`, `>i1`–`>i4`) | `Review: implementation` |

None of these phrases occurs anywhere in the skill dir or tests today (grepped),
so occurrence counts in the contract test are unambiguous.

## Steps

### 1. Producers — two placements each (mirrors the round-header rule)

In each of `.claude/skills/aitask-shadow/{plan-challenge,plan-assumptions,plan-diagnose-errors,impl-challenge}.md`:

**(a) Directive paragraph**, inserted directly after the existing
"**Emit a round header as the first line inside the block.**" paragraph
(plan-challenge ~l.162, plan-assumptions ~l.172, plan-diagnose-errors ~l.148,
impl-challenge ~l.619). Text (label substituted per producer):

> **Emit a review label on the line directly above the opening fence.**
> Immediately before the opening `===AITASK-CONCERNS===` line, with nothing
> between them, emit one line that reads exactly `Review: plan challenge`
> (written plain — the backticks here are only this doc's formatting). It tells
> a user who has scrolled to the block which review produced it. Emit it on
> **every** block this review produces: a zero-concern (metadata-only) block and
> a recheck round (`>r`, `>r<code>`, minimonitor's `refetch and recheck round N`)
> included. The phrase is fixed — no task number, no round number (the round
> lives in the `Round:` header inside the block), and no markdown (no bold,
> backticks or brackets: Codex and OpenCode rewrite markdown before tmux
> captures the pane). It sits outside the fences, so the parser never sees it.

**(b) Rules-list bullet**, inserted directly after the existing
"- **Round header.**" bullet (before "- **Plain-words line.**"):

> - **Review label.** The line directly above the opening fence is
>   `Review: plan challenge` — that fixed phrase, plain text, alone on its line,
>   on every block including zero-concern and recheck rounds. Prose-only: never
>   inside the fences, never a `- [` line, never carrying a task or round
>   number. Spec in `concern-format.md` ("Prose around the block that is not
>   parsed").

No example code block is touched (the examples start at `Round:` inside the
block; adding the label there would show it *inside* the fences, and adding a
contiguous `label → open fence` example would trip the t1123 hazard).

### 2. `concern-format.md` — document the label

In "### Prose around the block that is not parsed" (~l.88): "Two things" →
"Three things", and add a paragraph: the producer's review label sits on the
line directly above the opening fence; fixed phrase per producer (the table
above, phrases only — no fence shown beside them); plain text, no markdown,
never a `- [` line; on every block incl. metadata-only and recheck rounds; not
parsed (consumers locate the fence by substring, so the label — even if a
renderer reflowed it onto the fence's row — never enters the region); no
consumer displays it today. Fences named inline only (t1123).

### 3. `aidocs/framework/shadow_agent.md`

Extend the "Every sub-procedure that emits a concern block — …" paragraph
(~l.207) with one sentence: each also writes a fixed `Review: <kind>` line
directly above the opening fence so the block's origin is visible where it is
read (phrases and rules in `concern-format.md`).

### 4. Tests — `tests/test_concern_parser.py`

- **`TestReviewLabelLineIsInert`** (parser): for each of the four labels × two
  block shapes (items block; metadata-only `Round:`-only block) × two
  placements (label on its own line above `OPEN`; label reflowed onto the
  fence's row, `label + " " + OPEN`), assert the capture with the label gives
  results equal to the same capture without it for `parse_concerns`,
  `parse_block_meta`, `has_concern_block`, `is_metadata_only_block`,
  `concern_block_signature`, `block_region`, `unrecovered_markers`,
  `has_invalid_round_header`. Uses the file's existing `OPEN`/`CLOSE`/`block()`.
- **`TestProducerReviewLabelRule`** (source contract), modelled on
  `TestProducerPlainWordsRule`:
  - `_PRODUCER_REVIEW_LABELS` dict (file → label); keys == `KNOWN_PRODUCERS`,
    labels distinct.
  - predicate `_states_review_label_rule(text, label)`: whitespace-collapsed
    text contains `_REVIEW_LABEL_DIRECTIVE` and its own label ≥ 2 times
    (directive + rules bullet) and **no other** producer's label (copy-paste
    guard).
  - every producer satisfies it; no label appears inside an example
    concern-block fence (reuse `_fence_bodies`); `concern-format.md` names all
    four labels.
  - negative controls on synthetic text: missing directive, one placement only,
    a foreign label present → predicate False; complete text → True.
- **Rendered surface**: add `test_every_rendered_producer_states_the_review_label_rule`
  to `_RenderedShadowDocsContract` (runs for the claude and OpenCode renders of
  the `fast` profile).

### 5. Goldens and rendered trees

- Regenerate the 9 goldens under `tests/golden/procs/aitask-shadow/`
  (`impl-challenge-{default,fast,remote}.md`,
  `impl-challenge-{default,fast,remote}-opencode.md`,
  `plan-{assumptions,challenge,diagnose-errors}-opencode.md`) with the same
  renderer the test uses (`$PYTHON .aitask-scripts/lib/skill_template.py <file>
  aitasks/metadata/profiles/<profile>.yaml <agent>`), and review the diff — it
  must be exactly the two inserted passages per file.
- Refresh the gitignored rendered trees locally:
  `aitask_skill_render.sh aitask-shadow --profile <p> --agent <a> --force` for
  p ∈ {default, fast, remote} × a ∈ {claude, codex, opencode}. (Not committed.)

## Verification

- `bash tests/test_skill_render_aitask_shadow.sh`
- `python3 -m pytest tests/test_concern_parser.py tests/test_shadow_seam.py -q`
  (or `bash tests/run_all_python_tests.sh --test-dir` scoped run)
- `./.aitask-scripts/aitask_skill_verify.sh`
- `grep -n "Review: " .claude/skills/aitask-shadow-fast-/*.md` shows both
  placements in each of the four rendered producers.

## Step 9 (Post-Implementation)

Current-branch mode: commit code (skill docs, aidocs, tests, goldens) by path
with `enhancement: … (t2072)`, plan via `aitask_task_commit.sh`, then archive.

## Risk

### Code-health risk: low
- Golden churn across 9 files; a mis-pasted label in one producer would ship a wrong phrase · severity: low · → mitigation: none needed — covered by Step 4's per-producer label predicate (foreign-label guard) and Step 5's diff review

### Goal-achievement risk: low
- LLM compliance: the agent might omit the label on some blocks (clean rounds, rechecks) · severity: low · → mitigation: none needed — rule stated in both placements per producer exactly like the round header, with explicit zero-concern/recheck wording, pinned by the source and rendered-surface contract tests

## Final Implementation Notes
- **Actual work done:** As planned. Four producers each gained a bolded directive ("**Emit a review label on the line directly above the opening fence.**", right after the round-header paragraph) and a `- **Review label.**` rules bullet (right before the Plain-words bullet), each naming the producer's fixed phrase. `concern-format.md` documents the label (table of the four phrases) as a third piece of unparsed prose; `shadow_agent.md` gained one sentence. Tests: `TestReviewLabelLineIsInert` (4 labels × items/clean block × own-line/reflowed-onto-fence placement × 8 consumers), `TestProducerReviewLabelRule` (both placements, own label only, no label in example fences, concern-format names all four, negative controls), and a rendered-surface test in `_RenderedShadowDocsContract`. 9 goldens regenerated; their diff equals the source diff.
- **Deviations from plan:** `concern-format.md` keeps the existing "Two things…" paragraph and adds a separate "A third piece of unparsed prose…" paragraph instead of rewording to "Three things". Producer wording says "a clean round's metadata-only block" rather than "zero-concern" so the round-header guard's `zero-concern` occurrence count (≥2) cannot be inflated by the new text and mask a deleted round-header rule site.
- **Issues encountered:** impl-challenge wraps its round-header paragraph differently, so the insertion anchor had to be the shorter "machine-readable record that the round completed clean." line. Rewrapping with textwrap initially split code spans across lines; reflowed with code spans kept unbreakable.
- **Key decisions:** Labels finalized as `Review: plan challenge`, `Review: plan assumptions`, `Review: error diagnosis`, `Review: implementation` (none is a substring of another — pinned by test). No consumer parses or displays the label (out of scope per task).
- **Upstream defects identified:** None
