---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [shadow, aitask_monitormini, skills, tests]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-08 09:53
updated_at: 2026-09-08 09:54
---

Make the shadow agent's review output understandable to a human reviewer who
has **not** read the plan or the concerns in detail. Two additions to the
shadow review producers, both **prose emitted before the concern block** — the
parser, the minimonitor picker, and `review_loop.py::compose_recheck_prompt`
need no change.

## Goal

The user of `ait minimonitor` + the shadow agent should be able to follow
**the direction of what is happening** across review rounds — what each
concern is really about, what the plan has become, and whether the concerns
that were incorporated were worth their cost — without reading and
understanding all the technical details.

## Part 1 — plain-words line per concern (every round, every producer)

For each concern in the human-readable findings list, add one line
`In plain words: …` that restates **the full concern body as it is emitted in
the concern block** (the same body minimonitor reads) in simple language for a
non-expert. Derive it from the block body — compose the body first, then the
plain-words line — so the two never diverge. The line lives in the prose list
only; the block body is unchanged (it is forwarded verbatim to the followed
agent by `build_clipboard_payload`, and the picker shows `display_body()`).

## Part 2 — round preamble "Where this is heading" (rounds ≥ 2)

Every recheck round (`refetch and recheck round N`, manual or minimonitor's `L`
auto-loop) opens with a plain-language preamble **before** the findings list.
The comparison is **done by the agent** reading the texts — the round-1
snapshot of the plan, the previous round's snapshot, the current plan, and its
own previous rounds' concerns. No external diff/compare machinery; the only
helper involved makes the earlier texts *available* (see Snapshot seam).

**Binding audience rule.** Every sentence of the preamble (and every
plain-words line) is written for a reader who will not read the plan: name
outcomes and behaviors, not mechanisms; no file paths, function names, or
framework terms unless a single word has no plain substitute — and then unpack
it in the same sentence.

Fixed headings, plain labels:

1. **Since last round** — bullets: *added / removed / changed* + what it means
   for the result.
2. **Since the original plan** — cumulative, against the round-1 snapshot; each
   bullet says (in words, not by region tag) which earlier concern asked for it,
   or "nobody asked for this".
3. **Is it still doing what was asked?** — one of `same thing` / `does less` /
   `does more` / `does something different`, **always** followed by the explicit
   lists "It no longer will: …" and "It now also will: …". The label alone never
   stands.
4. **How much bigger did it get?** — `not at all` / `a little` (tweaks inside
   what was already there) / `noticeably` (a new piece, or a new case to handle)
   / `a lot` (a new component, a new setting users see, or a new dependency),
   plus the list of what was added.
5. **Was each change worth it?** — per change from (2): `needed` (fixes
   something that would be wrong or missing), `nice to have` (better, but could
   have waited as its own task), `not worth it` (cost more simplicity than the
   concern said it would, or the concern was only informational), `nobody
   asked`. End with one count line, e.g. `3 needed / 1 nice to have / 1 not
   worth it / 0 nobody asked`.
6. **Bottom line** — `on track` / `drifting` / `getting over-built`, by a fixed
   rule, plus "I'd undo …" naming which incorporations to roll back into
   follow-up tasks.

**Fixed rule for the bottom line:** `getting over-built` if any change is
`not worth it`, or any `nobody asked` change is `noticeably`+ in size, or (3)
is `does more` / `does something different`; `drifting` if (3) is `does less`,
or only `nice to have` changes drove `noticeably`+ growth; otherwise `on track`.

**Mapping to the framework vocabulary — for the agent, never in the output.**
The procedure file states how the plain labels ground in the existing concern
price: `needed` ⇔ the concern's `Improves:` touched an obligation dimension
(`goal`, `correctness`, or AC-obligated `robustness`/`performance`; i.e. it was
`Disposition: blocking`); `nice to have` ⇔ `follow-up`; `not worth it` ⇔ the
realized `simplicity` cost exceeds the quoted `Worsens:`, or the concern was
`informational`; (3) is the `goal` dimension; (4) is realized `simplicity`.
The preamble closes the loop on the impact vector: *did the plan pay the
price each concern quoted, and only that price — and did it pay anything
nobody quoted?*

## Snapshot seam (plan phase only)

The original plan is reliably available only if the shadow saves what it read
at round 1: plan-phase reviews usually run before `ExitPlanMode`, when the plan
is only on the followed pane (plan commits `ait: Add/Update plan for tN` exist
only after externalization). Add a `snapshot` verb to
`.aitask-scripts/aitask_shadow_rejected.sh` (same task-id validation, lock, and
atomic write) that stores the plan text read at round N as
`.aitask-shadow/<task_id>/plan_r<N>.md`, with a `snapshots` list verb. The
existing `prune` deletes the whole task dir at archive, so snapshots are
cleaned up for free. Every plan-review producer snapshots the plan it read at
the start of each round; the round-≥2 preamble reads `plan_r1.md` and the
previous round's file. Impl-review rounds need no snapshot: the approved plan
is committed, and the same six headings apply with "the code change" in place
of "the plan" (baseline = approved plan; last round = previous round's
composite diff, which the agent re-reads from git).

## Where it lives

- Single shared procedure file `.claude/skills/aitask-shadow/round-preamble.md`
  (pattern: `impl-review-angles.md`), referenced by all four producers —
  `plan-challenge.md`, `impl-challenge.md`, `plan-assumptions.md`,
  `plan-diagnose-errors.md` — because a recheck re-runs whichever producer ran
  last (`SKILL.md.j2` Step 3 re-review entry). The audience rule and the
  plain-words line rule live there too.
- Each producer states both new rules in the two-placement shape the existing
  producer rules use (bolded directive at the head of the emit step + a
  rules-list bullet), so `tests/test_concern_parser.py` can pin them the same
  way: add `TestProducerPlainWordsRule` and `TestProducerRoundPreambleRule`
  over `TestProducerShortRegionRule.KNOWN_PRODUCERS`, each with the negative
  control the existing guards carry. `impl-challenge.md`'s "the block is the
  last output" rule is unaffected — both additions are before the block.
- `concern-format.md` gets a short note that the plain-words line and the
  preamble are prose-only and are not part of the parsed block.
- `aidocs/framework/shadow_agent.md` documents the preamble and the snapshot
  files under the review-loop section; the website shadow page gets a
  user-facing paragraph.

## Verification

- Producer-rule guards: both new `TestProducer*Rule` classes fail when a
  producer drops either placement (synthetic text, not mutate-and-restore).
- `aitask_shadow_rejected.sh snapshot|snapshots`: bash test covering write,
  overwrite of the same round, list order, LOCK_BUSY, invalid id (exit 2), and
  that `prune` removes the snapshots.
- `tests/test_concern_parser.py::TestShadowDocsNotParserLive` still passes for
  `round-preamble.md` (no parser-live example in the new doc).
- Live check: run a plan-phase shadow through two rounds and confirm the
  round-2 output opens with the six headings, each label carries its explicit
  lists, and no sentence names a path or function.

## Relationship

Adjacent to t1503 (review-loop non-convergence surfaced by minimonitor's round
counter) — the preamble's "bottom line" is the shadow-side, human-readable
course-correction signal; t1503 remains the mechanical one. Cross-reference,
do not fold.
