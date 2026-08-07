---
Task: t1427_3_producer_suppression_rule.md
Parent Task: aitasks/t1427_reject_shadow_concerns_suppress_next_round.md
Sibling Tasks: aitasks/t1427/t1427_1_rejection_store_helper.md, aitasks/t1427/t1427_2_picker_reject_tristate.md, aitasks/t1427/t1427_4_rejection_docs.md, aitasks/t1427/t1427_5_manual_verification_reject_shadow_concerns_suppress_next_rou.md
Archived Sibling Plans: aiplans/archived/p1427/p1427_*_*.md
Worktree: . (current directory — profile 'fast', no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-07 13:25
---

# p1427_3 — Producer-side rejection-suppression rule + drift guards

## Context

The concern picker (`c` in `ait monitor` / `ait minimonitor`) now lets the user
**reject** a shadow concern, and t1427_1/t1427_2 landed the durable store and the
picker write path. But nothing yet *reads* it: every shadow review round still
re-derives its concerns from scratch, so a rejected concern comes back and the
user re-triages it. This child closes the loop — it teaches all four shadow
concern producers to consult the rejection store before emitting their concern
block, and adds the drift-guard machinery that keeps the rule from silently
falling out of one producer.

Matching must be **semantic and performed by the shadow agent**, not by
`concern_parser.py`: the shadow re-words bodies between rounds, `Concern` has no
stable cross-round identity, and `concern-format.md` states `region` is "a
display label … never a key". So the deliverable is prose in prompt files plus
the guards that prove the prose is present everywhere it must be.

**Why inline in every producer.** Shadow Step 2 (context fetch) is explicitly
optional — a producer can run a whole round without it — so a
context-fetch-only delivery has an unreachable trigger. Precedent: the
short-region rule is inlined in each producer because "these are prompt files
read at runtime, and an extra file read is a rule the agent may skip"
(`tests/test_concern_parser.py:807-809`).

## Verification pass (2026-08-07) — what changed from the original plan

The plan was written from the decomposition and had never been verified
(`plan_verified` was absent). Re-reading every cited source at HEAD (`bb8b726d2`)
confirmed **all** planning-time line numbers still hold — `concern-format.md`
provenance note :60-63, `plan-challenge.md` rules :71 / emit :53-101,
`plan-assumptions.md` :75 / :50-104, `plan-diagnose-errors.md` :64 / :48-88,
`impl-challenge.md` :390 / :366-427 with the bolded-directive precedent at :373,
`SKILL.md.j2` Step 2 :151-185, and every test anchor in
`tests/test_concern_parser.py` (:783, :797, :870-922, :925-1027, :1015-1023).
`aitask_shadow_rejected.sh` exists and
`audit-helper-whitelist aitask_shadow_rejected.sh` reports no `MISSING`.

Four corrections were folded in.

1. **`impl-challenge.md` has committed procedure goldens — the plan missed
   them.** `tests/test_skill_render_aitask_shadow.sh` **Test 1p** `assert_eq`s
   `tests/golden/procs/aitask-shadow/impl-challenge-{default,fast,remote}.md`
   against a live render (`test_skill_render_aitask_shadow.sh:99-112`), because
   `impl-challenge` is the one procedure carrying Jinja (`PROC_FILES_VARYING`,
   :63). The original plan said "Producers are plain `.md` … no `.j2` work for
   them", which reads as *no golden work* and is wrong for this one file.
   Editing it without regenerating those three goldens ships a red suite. The
   other three producers are in `PROC_FILES_INVARIANT` (:64-73) and are
   golden-free — Test 1i only asserts they stay profile/agent-invariant, which
   plain prose keeps true.

2. **The rule's trigger was itself unreachable, one level down.** The original
   wording — "if a source task id is known (Step 2)" — makes suppression
   conditional on the very optional step the parent task warned about. Verified
   the id is normally in hand *without* Step 2: both launchers pass it as a
   launch argument (`minimonitor_app.py:1794-1797`,
   `monitor_app.py:2724`), and `SKILL.md.j2:33-35` documents it as
   `<source_task_id>`. **User decision:** the rule now tells the producer to use
   the launch-arg/Step-2 id and to *resolve* one when it has neither, skipping
   only on genuine resolution failure. This also matches t1427_5's checklist
   item "no resolvable task id → output states suppression was skipped".

3. **Two stale `a`/`A` bulk-select sentences live in the files this task
   edits.** t1427_2 deleted `action_toggle_all`/`action_copy_all` outright
   (`monitor_shared.py:2368-2369` records the removal), but
   `concern-format.md:134-136` still says the picker excludes informational rows
   "from bulk select" and `impl-challenge.md:429-433` still says they are
   "skipped by the bulk-select key". Sibling t1427_4 scopes only `website/` and
   `aidocs/`, so nobody owns these. **User decision:** fix both here.

4. **`concern-format.md` must not gain the producer marker phrase.**
   `TestProducerShortRegionRule.PRODUCER_MARKER` is the literal
   `load-bearing for minimonitor's parser`, and `_producers()` discovers
   producers by scanning every `*.md` in the skill dir for it
   (`test_concern_parser.py:816-833`). Writing that phrase verbatim into the new
   `concern-format.md` section would make it a **fifth producer** and fail
   `test_producer_set_is_the_known_set`. Verified today: exactly four files carry
   it. Describe the marker's role without quoting it.

A review round against this verified plan surfaced four more, all confirmed
against source before changing anything.

5. **The negative control mutated a shared file.** The Verification section
   called for dropping the rule from a real producer and restoring it
   byte-identically. This worktree is shared with concurrent sessions (t1427_2's
   notes record two other sessions writing this tree), so a restore-from-backup
   can silently overwrite work that landed in between. The repo's own precedent
   for this guard family already refuses it —
   `test_concern_parser.py:853-858` states the control "exercises the predicate
   on synthetic text rather than editing a repo file, so nothing has to be
   restored afterwards." Replaced with two in-suite controls (step 4).

6. **The predicate could not see the pre-emit directive.** `("previously-rejected"
   in flat and "aitask_shadow_rejected.sh list" in flat)` is satisfied by the
   rules-list bullet alone, so a later edit deleting the bolded directive — the
   plan's own primary countermeasure for the "agent skips the rule" risk — would
   leave every guard green. Made placement-aware (step 4).

7. **`list` does not always exit 0.** Verified in source: `cmd_list` calls
   `resolve_task_id` first, which exits **2** on a malformed id, printing
   nothing to stdout. The helper's "all resolution outcomes exit 0" comment
   scopes to *resolution* outcomes (missing / drained / populated store) — not
   to a bad argument. This is directly coupled to correction 2: telling the
   producer to infer a task id makes a malformed id **more** reachable, and
   under the original wording the producer had no defined behavior there and
   could silently emit a previously-rejected concern. The rule now defines three
   outcomes and treats everything else as "could not consult the store →
   suppression skipped" — and so does **step 1's `concern-format.md` section**,
   which a later review round caught still specifying the old always-exit-0
   contract. Both surfaces must state it, and since the doc is the format's
   source of truth, a divergence there would outrank the producers' rule; a
   Verification bullet cross-checks them.

8. **Producer discovery is marker-keyed, so a fifth producer can hide.**
   `_producers()` (:824-833) globs `*.md` then filters on `PRODUCER_MARKER`, and
   `test_producer_set_is_the_known_set` compares that filtered set to the four
   known files. A new review procedure written without the marker phrase is
   invisible to **every** rule guard — short-region, region-required, and the
   new suppression rule alike — and the known-set assertion still passes. This
   is a pre-existing property of the t1187 guard family that this task inherits,
   not something it introduces; recorded as a goal-achievement risk with a
   spawned `after` mitigation rather than widened here.

Also confirmed while verifying (no change needed, but load-bearing): `cmd_list`
takes no lock and prints `NO_REJECTIONS` for both a missing and a drained store.
And `cmd_add` accepts only lines matching `- [`, so the store can never contain
a fence and `list` output echoed into the shadow pane can never become a
forwardable block.

## The rule (common wording — must contain BOTH guard substrings verbatim: "previously-rejected" and "aitask_shadow_rejected.sh list")

> **Consult the rejection store before emitting.** Using the source task id from
> your launch arguments or Step 2 — and resolving one now if you have neither
> (it is inferable from the followed agent's window name, e.g.
> `agent-pick-635_3`) — run
> `./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>`. Exactly three
> outcomes are defined. The single line `NO_REJECTIONS` means nothing is
> rejected — proceed normally. A printed body is the list of previously-rejected
> concerns. **Anything else** — a non-zero exit (a malformed task id exits 2),
> empty output, or output you cannot read as either of the first two — means you
> could not consult the store: emit every fresh concern and state that rejection
> suppression was skipped. Never treat an error as "nothing was rejected".
> Drop any fresh
> concern that is substantively the same as a previously-rejected entry, **even
> when reworded**. Whenever N ≥ 1 were dropped, report
> `Suppressed N previously-rejected concern(s).` in the prose before the block.
> When unsure whether a fresh concern matches a rejected one, **keep it and say
> why** (fail-open — consistent with `needs_addressing()` treating an
> unspecified disposition as actionable). When no task id can be resolved, state
> that rejection suppression was skipped.

Both guard substrings must survive markdown hand-wrapping. The predicate
collapses whitespace, so a wrap at a **space** is safe, but never hyphen-wrap
`previously-rejected` and never break `aitask_shadow_rejected.sh` mid-token.

**No producer filter.** The rule matches against *every* entry, not only those
whose `producer:` column names the current producer. Rejection is a judgement
about the concern, not about which round raised it — and t1427_2 writes all
picker rejections with `--producer picker`, so a producer-scoped filter would
suppress nothing. Do not add one.

## Steps

1. **`concern-format.md`** (`.claude/skills/aitask-shadow/`): add a new
   `## Rejected-concern suppression` section **between the trigger-vs-action
   contract (ends :214) and `## Where it lives` (:216)**. Cover: the store path
   `.aitask-shadow/<task_id>/rejected.md`; the `list <task_id>` call and its
   **three-outcome contract, worded to agree with the rule above** — the single
   line `NO_REJECTIONS` means nothing is rejected, a printed body is the
   rejection list, and anything else (non-zero exit — a malformed task id exits
   2 — empty output, or output matching neither shape) means the store could not
   be consulted and suppression must be reported as skipped. **Do not write
   "always exits 0" or any equivalent**: the helper's own "all resolution
   outcomes exit 0" comment scopes to *resolution* outcomes only, and this file
   is the format's single source of truth, so a false contract here would
   outrank the producers' correct rule (correction 7). Then: why matching is
   semantic rather than hash-based (bodies are re-worded between rounds;
   `region` is a display label, never a key); the fail-open contract; the
   `Suppressed N` report; and that the store is fence-free by construction
   (`add` accepts only `- [` lines), so echoing `list` output into the shadow
   pane can never be parsed as a block.

   Close with a provenance note mirroring :60-63: every producer states this rule
   inline and `tests/test_concern_parser.py::TestProducerRejectionSuppressionRule`
   fails the build if one drops it. **Do not** include a contiguous
   open→items→close block example (t1123 guard, `TestShadowDocsNotParserLive`),
   and **do not** write the phrase `load-bearing for minimonitor's parser` —
   see correction 4.

   Also fix the stale sentence at :134-136: the picker splits into **Needs
   addressing** / **Informational** and dims the latter; the bulk-select clause
   is gone (correction 3).

2. **Four producers** — add the rule in BOTH positions per file:
   - a **bolded pre-emit directive** at the head of the emit step (stylistic
     precedent: `impl-challenge.md:373`), and
   - a **bullet in the "load-bearing for minimonitor's parser" rules list**.

   Sites (re-verified at HEAD):
   - `plan-challenge.md` — rules list :71, emit step 6 :53-101
   - `plan-assumptions.md` — rules list :75, emit step 6 :50-104
   - `plan-diagnose-errors.md` — rules list :64 ("Format rules — all …"), emit
     step 4 :48-88
   - `impl-challenge.md` — rules list :390, emit section :366-427; its existing
     bolded directive is :373, so the new one sits adjacent

   Keep the wording identical across all four modulo surrounding sentence flow.
   Introduce **no Jinja** (`{%` / `{{`) — Test 3 asserts none leaks, and Test 1i
   pins the three non-`impl-challenge` producers as identity transforms.

   In `impl-challenge.md`, also fix the stale "skipped by the bulk-select key"
   clause at :429-433 (correction 3).

3. **`SKILL.md.j2` Step 2** (:151-185): one sentence — resolving the source task
   id also enables rejection suppression (producers consult the store keyed by
   it), so it is worth resolving even when the request could be served from the
   screen alone.

4. **Drift guards — `tests/test_concern_parser.py`:**
   - **Placement-aware** module-level predicate, beside
     `_states_region_required_rule` (:870). A plain "both substrings appear
     somewhere" test is satisfied by the rules-list bullet **alone**, so
     deleting the bolded pre-emit directive — this plan's primary countermeasure
     for the "agent skips the rule" risk — would leave the guard green
     (correction 6). Both placements must therefore carry the full rule, and the
     predicate proves both:
     ```python
     _SUPPRESSION_DIRECTIVE = "**Consult the rejection store before emitting.**"

     def _states_rejection_suppression_rule(text: str) -> bool:
         """True when a producer states the suppression rule in BOTH placements.

         Counts rather than membership-tests: one copy lives in the bolded
         pre-emit directive at the head of the emit step and one in the
         parser-rules list, and a guard that could not tell them apart would go
         green after the high-attention directive was deleted.
         """
         flat = " ".join(text.split())
         return (_SUPPRESSION_DIRECTIVE in flat
                 and flat.count("previously-rejected") >= 2
                 and flat.count("aitask_shadow_rejected.sh list") >= 2)
     ```
     This makes the exact bolded lead phrase load-bearing — write it verbatim in
     all four producers.
   - New `TestProducerRejectionSuppressionRule`, mirroring
     `TestProducerRegionRequiredRule` (:881-922): reuse `SHADOW_DIR`,
     `PRODUCER_MARKER`, `KNOWN_PRODUCERS` and `_producers` from
     `TestProducerShortRegionRule` **by reference** (the :891-895 idiom);
     duplicate `test_producer_set_is_the_known_set`; and an offenders test whose
     message explains the consequence (a producer without the rule re-raises
     concerns the user already rejected).
   - **Two negative controls, neither mutating a repo file** (correction 5):
     1. *Synthetic-text control, per placement* (the :914-922 shape, extended).
        Assert the predicate is `False` for directive-only text, `False` for
        rules-bullet-only text, and `True` only when both are present. The
        one-copy cases are what prove the guard is placement-aware rather than
        a membership test.
     2. *Fixture-directory control that invokes **the production assertion
        itself**.* `unittest.mock.patch.object(TestProducerRejectionSuppressionRule,
        "SHADOW_DIR", <tmpdir>)` over a tmp dir holding two synthetic producer
        files (both carrying the marker phrase; one compliant, one missing the
        directive), then **call
        `test_every_producer_states_the_rejection_suppression_rule()`** inside
        that context under `assertRaises(AssertionError)` and require the
        message to name `bad.md` and **not** `good.md`.

        **Re-implementing the offender comprehension in the control does not
        work** — measured, not assumed. Recomputing offenders here with a direct
        call to the predicate leaves the control blind to the very mutation it
        exists to catch: pasting `_states_region_required_rule` (which all four
        real producers satisfy) into the production method leaves that method
        vacuously green *and* the re-implementation green, because the mutation
        never reaches it. Invoking the real method is what couples them, and it
        also catches a neutered assertion (`assertRaises` fires). Drives the
        real class, not a replica, and touches nothing shared.

     **Deviation from the task file's "one-for-one mirror of
     `TestProducerRegionRequiredRule`":** this class carries one control more
     than the mirror. Stated deliberately — the mirror's single synthetic
     control leaves the wrong-predicate vacuous pass uncovered.
   - Extend `TestRenderedShadowDocsKeepTheGuarantees` (:925-1023): the rendered
     check at :1015-1023 gains a third offender list for the suppression rule,
     so a conditional that dropped it from the `fast` render fails loudly.

5. **Skill-surface hygiene:** `./.aitask-scripts/aitask_skill_verify.sh` clean.
   Producers live **only** in the Claude tree (`concern-format.md` "Where it
   lives", :218-222) — no cross-agent port tasks. The helper whitelist landed in
   t1427_1 and is already green. The six goldens the edits invalidate are
   regenerated in the post-phase below, in this same commit.

### Post-phase (risk mitigations)

1. **[goldens_regenerated_render_suite_green]** Regenerate the three
   entry-point goldens invalidated by the `SKILL.md.j2` edit:
   ```bash
   PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   for profile in default fast remote; do
     "$PYTHON" .aitask-scripts/lib/skill_template.py \
       .claude/skills/aitask-shadow/SKILL.md.j2 \
       aitasks/metadata/profiles/$profile.yaml claude \
       > tests/golden/skills/aitask-shadow/SKILL-${profile}-claude.md
   done
   ```
2. **[goldens_regenerated_render_suite_green]** Regenerate the three procedure
   goldens invalidated by the `impl-challenge.md` edit — same driver, rendering
   `.claude/skills/aitask-shadow/impl-challenge.md` per profile into
   `tests/golden/procs/aitask-shadow/impl-challenge-<profile>.md`. These are the
   ones the original plan pointed away from (correction 1); the other three
   producers are golden-free.
3. **[goldens_regenerated_render_suite_green]** `git diff` each of the six
   regenerated goldens and confirm every hunk is the rule text or the
   bulk-select fix — an unrelated hunk is a render regression, not a rubber
   stamp (`skill_authoring_conventions.md:477-482`).
4. **[goldens_regenerated_render_suite_green]** Run
   `bash tests/test_skill_render_aitask_shadow.sh` and confirm Test 1, Test 1p
   and Test 1i are green **before** committing. Goldens and the edits that
   invalidated them land in the **same** commit.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — read the **last stderr
  line** for the verdict (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); if
  piping, check `${PIPESTATUS[0]}` or `set -o pipefail`.
- `bash tests/test_skill_render_aitask_shadow.sh` — Test 1 (entry-point
  goldens), Test 1p (impl-challenge goldens) and Test 1i (invariance) all green.
- `bash tests/test_concern_parser.py` specifically — the new guard class green,
  and `test_producer_set_is_the_known_set` still reporting exactly the four
  known producers.
- `./.aitask-scripts/aitask_skill_verify.sh` clean.
- **Error-contract agreement check.** Read the new `concern-format.md` section
  and the four producers' rule text side by side and confirm they describe the
  *same* three outcomes. `grep -n 'exits\? 0' .claude/skills/aitask-shadow/*.md`
  must surface no claim that `list` always exits 0. The doc is the format's
  source of truth, so a divergence here silently wins over the producers.
- Negative controls for the new guard run **entirely in-suite** (step 4) —
  synthetic text for the predicate's placement-awareness, a patched `SHADOW_DIR`
  over a tmp fixture for the discovery-and-offenders wiring. **Do not** mutate a
  real producer and restore it: this worktree is shared with other sessions, so
  a restore-from-backup can silently overwrite concurrent work, and the two
  in-suite controls already prove the guard can fail — with the failing test id
  named — without touching a shared file.
- Live two-round suppression is **already covered** by sibling t1427_5's
  checklist (items for t1427_3: reject → fresh round omits it and reports
  `Suppressed N …`; un-reject → it returns; no resolvable task id → output
  states suppression was skipped). Do not duplicate it as a new task.

## Risk

### Code-health risk: low

- Six golden files must be regenerated in the same commit; the `impl-challenge`
  procedure goldens are the easy miss, and the original plan's "no `.j2` work
  for producers" wording pointed away from them · severity: low ·
  → mitigation: inline post-phase goldens_regenerated_render_suite_green
- The predicate now pins three things per producer — the exact bolded directive
  phrase and **two** occurrences each of `previously-rejected` and
  `aitask_shadow_rejected.sh list` — across four hand-wrapped prose files.
  Whitespace collapse absorbs an ordinary wrap, but a hyphen-wrapped
  `previously-rejected` or a mid-token break in the helper name fails it ·
  severity: low · → mitigation: none needed — the new guard class is precisely
  what catches it, and it fails loudly with the offending filename
- Writing the producer marker phrase into `concern-format.md` would register a
  fifth producer · severity: low · → mitigation: none needed — covered by the
  existing `test_producer_set_is_the_known_set`, called out in step 1

### Goal-achievement risk: medium

- The feature rests on an LLM judging "substantively the same, even when
  reworded"; the drift guards prove only that the *rule text is present*, never
  that suppression *works*. No automated test can close this · severity: medium ·
  → mitigation: none new — bounded by fail-open (the failure mode is a concern
  returning, i.e. today's behavior, never a real concern hidden) and verified
  live by existing sibling t1427_5
- The rule competes with ~10 sibling rules in each producer's list and asks the
  agent to shell out before emitting; an agent may skip it · severity: low ·
  → mitigation: none new — dual placement (bolded pre-emit directive **and**
  rules-list bullet) is the countermeasure, and t1427_5 verifies it live
- A manually-invoked shadow with no pane binding and no launch arg may still
  fail to resolve a task id · severity: low · → mitigation: none — accepted and
  made **visible** by the rule's explicit "state that suppression was skipped"
  clause, which t1427_5 checks
- Producer discovery is keyed on the marker phrase, so a fifth review procedure
  written without it inherits none of the rules and `test_producer_set_is_the_known_set`
  still passes on the original four — the suppression rule would be absent from
  a live producer with every guard green · severity: low ·
  → mitigation: producer_manifest_independent_discovery

### Planned mitigations
- timing: after | name: producer_manifest_independent_discovery | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — marker-keyed producer discovery cannot see a fifth producer written without the marker phrase, so every rule guard stays green while a live producer carries none of the rules | desc: give the shadow producer set an independent discovery signal (explicit manifest, or a broader scan flagging any aitask-shadow/*.md that instructs emitting a concern block but lacks the marker) so a new producer cannot be added silently; benefits the short-region and region-required guards equally, and is spawned rather than inlined because it re-opens the shared t1187 discovery contract and its KNOWN_PRODUCERS pin
- timing: post-phase | name: goldens_regenerated_render_suite_green | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — six goldens invalidated by the edits, with the impl-challenge procedure goldens the easy miss | desc: regenerate the 3 entry-point and 3 impl-challenge goldens with the documented driver, review each diff for rule-text-and-bulk-select-fix content only, and run tests/test_skill_render_aitask_shadow.sh green before committing — all in the same commit as the edits

## Post-Review Changes

### Change Request 1 (2026-08-07 16:03)

- **Requested by user:** A review finding against the implemented guard.
  `test_guard_wiring_flags_a_real_offender` recomputed the offender list with a
  direct call to `_states_rejection_suppression_rule` instead of exercising
  `test_every_producer_states_the_rejection_suppression_rule`, so it could not
  catch that production test being copy-pasted to `_states_region_required_rule`
  — the exact vacuous pass it was written to catch, and the sole justification
  for carrying a control beyond the mirror's.

- **Verified before changing anything.** Reproduced against the shipped test:
  with the mutation applied at **one** site — the production method rewired to
  `_states_region_required_rule`, nothing else touched — all four class tests
  ran green. CONFIRMED.

  The earlier "demonstration" that had claimed the opposite was itself invalid:
  it substituted the predicate through a single variable used in **both** the
  production comprehension and the control's, so the mutation reached the
  control too. That is a negative-control discipline failure — the mutation must
  be applied at the isolated enforcement point, not at two sites at once — and
  it is what made an ineffective control look effective.

- **Changes made:**
  - The control is renamed `test_production_assertion_fails_on_a_real_offender`
    and now **invokes the production method itself** inside the patched
    `SHADOW_DIR` context, under `assertRaises(AssertionError)`, asserting the
    message names `bad.md` and **not** `good.md`. Re-implementing the
    comprehension is what broke the coupling; calling the real method restores
    it.
  - Its docstring records the measured finding, so a later reader does not
    "simplify" it back into a re-implementation.
  - Step 4 of this plan rewritten to specify the working shape.
  - Re-verified against **two** mutation classes, each applied at the single
    production site and each caught, failing for the right reason:
    M1 production method rewired to `_states_region_required_rule` → fails on
    `assertNotIn("good.md", …)` ("flagged the COMPLIANT fixture too") ·
    M2 production method neutered to a no-op → fails on
    `AssertionError not raised`. Baseline unmutated: 71 passed.

- **Files affected:** `tests/test_concern_parser.py`,
  `aiplans/p1427/p1427_3_producer_suppression_rule.md`.

## Final Implementation Notes

- **Actual work done:** All five planned steps plus the post-phase landed as
  specified, across 13 files (+405/−29 before CR-1). `concern-format.md` gained
  a `## Rejected-concern suppression` section between the trigger-vs-action
  contract and "Where it lives", carrying the store path, the three-outcome
  reader contract, the semantic-matching rationale, fail-open, the `Suppressed
  N` report, and the "the store can never become a block" property. All four
  producers carry the rule in both placements — the bolded
  `**Consult the rejection store before emitting.**` directive at the head of
  the emit step and a `**Suppress previously-rejected concerns.**` entry in the
  parser-rules list. `SKILL.md.j2` Step 2 gained one paragraph. Tests:
  `test_concern_parser.py` 66 → 71, adding `_SUPPRESSION_DIRECTIVE`,
  `_states_rejection_suppression_rule`, `TestProducerRejectionSuppressionRule`
  (4 tests) and a rendered-render guard. Six goldens regenerated.

- **Deviations from plan:**
  1. **One negative control more than the task file's "one-for-one mirror of
     `TestProducerRegionRequiredRule`".** The mirror's single synthetic control
     proves only that the predicate can return `False`; it cannot see how the
     production assertion is wired. Stated as a deliberate deviation in the plan
     before implementation, and CR-1 then proved the extra control was worth
     having — and initially built wrong.
  2. **The rules-list "emit only when ≥1 concern" bullet gained a suppression
     clause** in all four producers. Not in the plan, but the interaction is
     reachable and undefined without it: if suppression drops every fresh
     concern, the producer omits the block and says so, rather than emitting an
     empty one.

- **Issues encountered:**
  - **`impl-challenge.md` has committed procedure goldens** that the original
    task file's "producers are plain `.md` — no `.j2` work" wording pointed away
    from. Caught during the plan-verification pass, not at test time.
  - **The first version of the wiring negative control did not work, and the
    demonstration that "proved" it was itself invalid** — see Change Request 1.
    The lesson generalises beyond this task: a negative control must apply its
    mutation at the **single** enforcement point under test. Substituting a
    shared variable that both the production code and the control read makes an
    ineffective control look effective, because the mutation reaches the control
    too.
  - **The working tree carried substantial concurrent work from other sessions**
    (gate-skill wrappers under `.agents/` and `.opencode/`, `board_groups.py`,
    sync/merge/fold changes, and `tests/golden/procs/task-workflow/SKILL-fast.md`
    paired with a `task-workflow/SKILL.md` edit). The post-phase's
    review-every-diff step is what surfaced that foreign golden; a blanket
    `git add tests/golden/` would have swallowed it. Staging was done by
    explicit path list.

- **Key decisions:**
  - **The rule resolves the task id rather than waiting for one.** "If a source
    task id is known (Step 2)" would have made suppression conditional on an
    explicitly optional step — the same unreachable-trigger shape the parent
    task warned about, one level down. Both launchers already pass the id as a
    launch argument (`minimonitor_app.py:1794-1797`), so the reachable wording
    costs nothing.
  - **Three defined outcomes, and errors are not "nothing was rejected".**
    `list` exits 2 on a malformed id, so an inferred-but-wrong id must degrade
    to a visible "suppression skipped", never to silent non-suppression. Both
    the producers and `concern-format.md` state this; a Verification check
    cross-references them because the doc is the format's source of truth and
    would outrank the producers on a divergence.
  - **The guard is placement-aware.** A plain "both substrings appear somewhere"
    predicate is satisfied by the rules-list bullet alone, so deleting the
    high-attention directive — the countermeasure for an agent skipping the rule
    — would have left every guard green.
  - **No producer filter on the rejection list.** Rejection is a judgement about
    the concern, not the round that raised it, and t1427_2 writes everything with
    `--producer picker`, so a producer-scoped filter would suppress nothing.

- **Verification evidence.** `PYTHON SUITE: PASSED (runner=pytest, exit=0)` —
  3787 passed, 2 skipped, plus the serial carve-out. `test_concern_parser.py`
  71 passed. `tests/test_skill_render_aitask_shadow.sh` 475/475 (Test 1
  entry-point goldens, Test 1p `impl-challenge` goldens, Test 1i invariance).
  `aitask_skill_verify.sh` OK — 13 templates × 3 agents, wrapper parity clean.
  Programmatic cross-checks: all four producers carry the directive with
  `previously-rejected` ×4 and `aitask_shadow_rejected.sh list` ×2; the producer
  set is still exactly the four known files (`concern-format.md` did not become
  a fifth); all five surfaces state the same three outcomes. **Negative controls
  (all in-suite, no repo file mutated):** the synthetic per-placement control
  (neither copy / bullet-only / directive-only → `False`; both → `True`), and
  the production-assertion control verified against two mutations applied at the
  single production site — rewired predicate → fails naming the compliant
  fixture; neutered assertion → `AssertionError not raised`.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t1427_4 (docs):** the two stale `a`/`A` bulk-select sentences inside the
    skill tree (`concern-format.md`, `impl-challenge.md`) were fixed here, so
    t1427_4's a/A scrub applies only to `website/` and `aidocs/`. When
    documenting suppression, the user-visible contract is: the report line is
    `Suppressed N previously-rejected concern(s).`; unsure ⇒ the concern is
    **kept** with a reason; an unresolvable task id or an unreadable store ⇒ the
    round says suppression was skipped and emits everything. Do **not** document
    the helper's `list` as a user-facing CLI — producers invoke it.
  - **t1427_5 (manual verification):** its three t1427_3 checklist items match
    what shipped, including "no resolvable task id → output states suppression
    was skipped". Nothing needs re-wording.
  - **The spawned `after` mitigation** (`producer_manifest_independent_discovery`)
    covers a **pre-existing** t1187 blind spot shared by all three rule guards:
    `_producers()` discovers by marker phrase, so a fifth producer written
    without it inherits no rules and `test_producer_set_is_the_known_set` still
    passes on the original four.
  - **Anyone adding a fifth producer** must write the marker phrase
    `load-bearing for minimonitor's parser` and all three rules, and must not
    write that phrase into `concern-format.md` — doing so registers it as a
    producer and fails the known-set assertion.

Post-implementation cleanup, archival, and merge follow **Step 9
(Post-Implementation)** of the task workflow.
