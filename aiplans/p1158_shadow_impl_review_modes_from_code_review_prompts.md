---
Task: t1158_shadow_impl_review_modes_from_code_review_prompts.md
Base branch: main
plan_verified: []
---

# Plan: t1158 — Effort-tiered, angle-based implementation review modes for the shadow skill

## Context

Shadow's `impl-challenge.md` is today one flat adversarial pass with three axes
(implementation flaws, unmitigated risks, unjustified deviations). Claude Code's
built-in `/code-review` structures the same job much more sharply — effort
tiers, per-angle finder methodology, a 3-state verify ladder — and its full
prompt text was extracted verbatim into
`aidocs/codeagents/claudecode_builtin_prompts.md` (§4 shared fragments, §5
per-level assembly). This task adapts that material into selectable review
tiers for the shadow implementation review, layered **on top of** shadow's
unique axes (plan-vs-diff deviations, unmitigated plan risks, Final
Implementation Notes cross-referencing), while preserving the load-bearing
concern-block contract and advisory-only guardrails unchanged.

**User decisions (confirmed during planning):**
- Tier set: **quick / basic / standard / deep**, where **Basic is the explicit
  one-to-one successor of the existing legacy adversarial review** (its three
  axes and single full-context-pass methodology preserved as directly as
  practical), and **Standard is the recommended improved review**.
- Angle catalog lives in a **sibling fragment file**
  (`.claude/skills/aitask-shadow/impl-review-angles.md`), per the
  "extract procedures to their own file" convention and the `concern-format.md`
  single-source precedent.
- Findings gain a per-finding **disposition tag** (`blocking` vs `follow-up`)
  in every tier, anticipating the planned shadow-concern redesign (splitting
  address-now vs follow-up concerns) without touching the concern-block wire
  format.

The change is markdown-only, confined to the Claude tree
(`.claude/skills/aitask-shadow/`). The `.agents/` and `.opencode/` shadow trees
are redirect wrappers with no mirrored sub-procedures (verified: they carry only
`SKILL.md`) — no cross-agent port. No tests parse `impl-challenge.md` content.
The shadow skill has no `.j2`/stub surface (plain skill dir), so goldens should
be unaffected — verified in-task by running `aitask_skill_verify.sh`.

## Files

1. **EDIT** `aitasks/t1158_shadow_impl_review_modes_from_code_review_prompts.md`
   (acceptance-criteria amendment — Step 0)
2. **NEW** `.claude/skills/aitask-shadow/impl-review-angles.md` (~150 lines)
3. **REWRITE** `.claude/skills/aitask-shadow/impl-challenge.md` (142 → ~300 lines)
4. **EDIT** `.claude/skills/aitask-shadow/SKILL.md` (Step 3 routing bullet only)
5. **EDIT** `tests/test_concern_parser.py` (one focused round-trip test method;
   no parser change)

## Step 0 — Amend the task's acceptance criteria (no-silent-AC-deviation)

Basic is deliberately a non-quick tier **without** the verdict ladder, but the
task's written AC currently requires "a verify pass with the 3-state verdict
ladder runs in the non-quick tiers". Implementing this plan faithfully would
fail the written AC. So, first implementation action (post-approval — task-file
edits are mutations and run outside plan mode):

- Edit the AC bullet in the task file to: "A verify pass with the 3-state
  verdict ladder runs in the **Standard and Deep** tiers, and verdicts appear
  in the findings presentation. **Basic is the deliberate legacy-compatibility
  exception**: it preserves the pre-tier single-pass adversarial review with
  no formal verify."
- Also extend the tier-set AC bullet to record the decided set:
  "quick / basic / standard / deep (basic = legacy compatibility tier)".
- Update `updated_at`, commit via `./ait git add aitasks/` +
  `./ait git commit -m "ait: Amend t1158 AC for basic legacy tier"`.

## Step 1 — New shared fragment file `impl-review-angles.md`

Single source of truth for the angle catalog + verdict machinery, adapted from
`claudecode_builtin_prompts.md` §4 (faithful to the extracted text, with shadow
adaptations noted below). Header states: "Shared fragments for the shadow
implementation review tiers (`impl-challenge.md`). Read when a tier references
it. Adapted from Claude Code's built-in /code-review prompts — see
`aidocs/codeagents/claudecode_builtin_prompts.md`."

Sections:

- **Correctness angles A–E** (§4.2, near-verbatim). Adaptations:
  - "the diff" = the task's resolved diff source (committed / staged /
    working-tree) as resolved by impl-challenge Inputs — not
    `git diff @{upstream}` (shadow has no Phase 0; input resolution replaces it).
  - "PR" wording → "task's change".
  - Angle C's Grep-for-callers and Angle A's Read-the-enclosing-function stay:
    reading the shadow's own repo checkout is allowed (advisory-only governs the
    followed pane, not repo reads).
- **Cleanup angles** — Reuse, Simplification, Efficiency, Altitude,
  Conventions (CLAUDE.md) (§4.3, near-verbatim) + the cleanup-precedence note
  ("correctness bugs always outrank cleanup findings when the cap forces a cut").
- **Shadow / legacy axes as first-class angles** (lifted one-to-one from the
  current impl-challenge "Attack the implementation along these axes" section —
  ALL THREE legacy axes live here once, so Basic's legacy pass and the
  standard/deep angle runs reference the same texts with zero inline
  duplication):
  - **Angle S0 — implementation flaws (legacy broad axis)**: bugs, missed
    cases, incorrect logic, off-by-ones, mishandled error/empty/edge inputs,
    or regressions in the code as actually written, checked against the
    plan/task intent and the real diff. (Basic's flaw hunt; in standard/deep
    this broad axis is *superseded* by the mechanized angles A–E — S0 is not
    run there, and A is NOT a subsumption of S0: A's line-by-line hunk
    methodology is a different, narrower procedure than the legacy broad
    sweep.)
  - **Angle S1 — unmitigated plan risks**: cross-reference the plan's `## Risk`
    section and Final Implementation Notes; surface only risks that remain open;
    never re-flag an explicitly mitigated one.
  - **Angle S2 — plan-deviation auditor**: compare diff vs plan; flag only
    deviations unexplained by the Final Implementation Notes or whose
    justification does not hold up.
- **Anti-drop rule** (§4.4, with-verify wording): pass every candidate with a
  nameable failure scenario through to verify.
- **Verdict ladder** (§4.5): CONFIRMED / PLAUSIBLE / REFUTED definitions,
  plus the **recall addendum** ("PLAUSIBLE by default…") as a separately
  referenced block (deep tier only).
- **Gap-sweep focus list** (§4.7, inline variant): moved/extracted code that
  dropped a guard; second-tier footguns; setup/teardown asymmetry; flipped
  config defaults. "If nothing new, return nothing — do not pad."

## Step 2 — Rewrite `impl-challenge.md`

**Keep unchanged (verbatim or near-verbatim):**
- Title/purpose framing, advisory-only paragraph.
- **Inputs 1–3** (task+plan via `aitask_shadow_context.sh` with archived-plan
  fallback; diff via `aitask_revert_analyze.sh --task-commits` with
  working-tree fallback + "tell the user which source you reviewed"; Final
  Implementation Notes), and the `--deep` capture note.
- **"Too early to review" gate** — unchanged, still runs first in every tier.
- **Concern-block section** — same rules (fences, `- [priority | region] body`,
  mandatory dash, block-last, closing fence, omit-when-clean). Two
  producer-side amendments, both parser-neutral: (a) one sentence saying the
  body should mention the disposition (all tiers) and the verdict
  (standard/deep) as prose — inside the body free text, never changing the
  line format; (b) the ordering rule becomes "order items to match the prose
  list (blocking partition first, severity-ordered within each partition)"
  instead of severity-only.

**New: Tier selection (after the too-early gate).**
- Auto-detect from the user's free-text ask:
  - "quick" / "fast" → **Quick**
  - "basic" / "legacy" / an unqualified "adversarial review" → **Basic**
  - "standard" / "normal" → **Standard**
  - "deep" / "thorough" / "max" / "exhaustive" → **Deep**
  - Generic "review the implementation" with no level or compatibility wording
    → `AskUserQuestion` (Header "Review tier"): "Standard (Recommended)" /
    "Basic" / "Quick" / "Deep", each with a one-line description of pass
    structure and findings cap; Basic's description names it the legacy
    three-axis review.
  - **Deterministic 3-option-capped adaptation (documented inline in the
    file):** agents whose user-input tool caps at 3 options per question
    (e.g. Codex CLI `request_user_input` — see
    `.agents/skills/codex_tool_mapping.md`) MUST use this fixed two-stage
    chooser instead of ad-hoc combining/dropping:
    - Stage 1: "Standard (Recommended)" / "Basic — legacy adversarial review"
      / "Other tier (quick or deep)…"
    - Stage 2 (only when "Other tier"): "Quick — reduced hunk-only scan" /
      "Deep — expanded angles + gap sweep".
    Free-text tier naming continues to bypass the chooser entirely on every
    agent.
- **Compatibility framing (documented in the file):** Basic is the
  compatibility tier — the direct successor of the pre-tier adversarial
  review; Standard is the recommended improved review. Nothing routes to Quick
  implicitly.
- **Angle scoping (explicit-composition rule — user intent wins):** works at
  every level. The tier picks the *default* angle set; a user ask naming
  specific angles or focus areas ("just check the callers", "only plan
  deviations", "skip the cleanup angles") narrows or extends it, at the tier's
  depth. Map free-text focus phrases to catalog angle names and confirm the
  resolved set in one line. Two guard rails:
  - Only an explicit user narrowing may drop a legacy axis from a run's
    default set — for **Basic that protects all three axes (S0/S1/S2)**
    equally; for standard/deep it protects S1/S2 (S0 is not in their default
    set — superseded by the A–E methodology).
  - Scoping **never changes a tier's methodology**: at Basic, a focus request
    narrows the attention of the *single adversarial pass* — it does not
    activate Standard's candidate fan-out, verdict ladder, or Deep's gap
    sweep. A user who wants the angle methodology asks for Standard/Deep.
- State the chosen tier (and any angle scoping) to the user before starting.

**New: four tier definitions:**

- **Quick** (`quick → 1 diff pass → no verify → ≤4 findings`):
  Reduced hunk-only scan; no full-context review, no verification. Single pass
  over the resolved diff. Flag only runtime-correctness bugs visible from the
  hunk alone (inverted condition, off-by-one, null deref, removed guard,
  falsy-zero, missing await, wrong-variable copy-paste, swallowed error) plus
  hunk-visible duplication and dead code; also one cheap shadow glance — scan
  Final Implementation Notes vs the diff for a glaring unexplained deviation.
  Skip test/fixture hunks. No full-file reads. ≤4 findings, one line each,
  most-severe first. States up front that it is a reduced-scope pass. (Adapted
  from /code-review `low`, §5.1.)

- **Basic (= Legacy)** (`basic → 1 full-context adversarial pass → no formal
  verify → prioritized findings`): the current three-axis adversarial review,
  preserved as directly as practical. One full-context adversarial pass over
  the resolved implementation diff, the plan, its `## Risk` section, and the
  Final Implementation Notes, attacking along the three legacy axes — **S0
  (implementation flaws), S1 (risks left unmitigated), S2 (unjustified
  deviations)** — referencing the catalog texts (all three live only in
  `impl-review-angles.md`; the *methodology* here stays the legacy single
  pass, not an angle fan-out). No multi-angle candidate fan-out, no verdict
  ladder, no gap sweep, no findings cap, no minimum. Preserves the existing
  honesty rules, prioritization, advisory-only guardrail, and concern-block
  behavior exactly.

- **Standard** (`standard → 10 angles × 6 candidates → precision verify → ≤8
  findings`): the recommended improved review; precision stance ("every
  finding one a maintainer would act on"). Phase 1: run 10 finder angles
  inline in sequence — A, B, C + Reuse, Simplification, Efficiency, Altitude,
  Conventions + S1, S2 — up to 6 candidates each
  (`file`/`line`/summary/failure_scenario), anti-drop rule. Phase 2:
  self-verify — for each deduped candidate, re-read the relevant code and
  assign CONFIRMED / PLAUSIBLE / REFUTED per the ladder (precision-biased: no
  recall addendum); keep CONFIRMED + PLAUSIBLE. ≤8 findings. (Adapted from
  §5.3 with the Opus-inline execution model — angles run inline, sequentially,
  in this context; no subagents.)

- **Deep** (`deep → 12 angles × 8 candidates → recall verify → gap sweep → ≤15
  findings`): recall stance ("catch every real bug… err on the side of
  surfacing"). Phase 1: 12 angles (adds D, E), up to 8 candidates each; "do
  NOT let one angle's conclusions suppress another's". Phase 2: recall-biased
  verify (ladder + PLAUSIBLE-by-default addendum); keep CONFIRMED + PLAUSIBLE.
  Phase 3: gap-sweep per the fragment file's focus list (up to 8 additional
  candidates, verified the same way). ≤15 findings. (Adapted from §5.5.)

**Angle-activation table (explicit, in the file):**

| Angle / mechanism | quick | basic | standard | deep |
|---|---|---|---|---|
| Single full-context legacy pass (methodology) | — | ✓ | — | — |
| S0 — implementation flaws (legacy broad axis) | — | ✓ (legacy axis 1) | — (superseded by A–C) | — (superseded by A–E) |
| A — line-by-line diff scan | hunk-only variant | — | ✓ | ✓ |
| B — removed-behavior auditor | — | — | ✓ | ✓ |
| C — cross-file tracer | — | — | ✓ | ✓ |
| D — language-pitfall specialist | — | — | — | ✓ |
| E — wrapper/proxy correctness | — | — | — | ✓ |
| Reuse / Simplification / Efficiency | dup+dead-code hunk glance | — | ✓ | ✓ |
| Altitude | — | — | ✓ | ✓ |
| Conventions (CLAUDE.md) | — | — | ✓ | ✓ |
| S1 — unmitigated plan risks | — | ✓ (legacy axis 2) | ✓ | ✓ |
| S2 — plan-deviation auditor | notes-vs-diff glance | ✓ (legacy axis 3) | ✓ | ✓ |
| Verify pass (verdict ladder) | — | — | precision | recall |
| Gap sweep | — | — | — | ✓ |
| Findings cap (see cap-overflow rule) | ≤4 | none | ≤8 | ≤15 |

**Findings presentation (all tiers, replacing the current "Produce a prioritized
list" section):** prose list — per finding: one-line statement, why it bites
(triggering scenario), severity (high/medium/low), a **disposition tag**
(`blocking` / `follow-up`, per the rubric below), and in standard/deep the
**verdict** (CONFIRMED or PLAUSIBLE). The per-finding disposition replaces the
current loose "separate fatal from fixable" paragraph in every tier including
Basic (a presentation refinement of Basic's existing fatal/fixable split, not a
methodology change). This anticipates the planned shadow-concern redesign
(splitting address-now vs follow-up concerns): the producer classifies each
finding now, so a later `concern-format.md` format change only has to promote
an existing prose field into structure.

**Disposition rubric (angle-independent — goes in `impl-review-angles.md` so
every tier classifies identically):** disposition is decided by the finding's
**reachable impact measured against the change's obligations** — the task's
acceptance criteria, the plan's stated goal and contracts, existing behavior,
and mandatory project rules. The discovering angle is **discovery context
only** and never determines disposition; verdict confidence never does either.

- `blocking` — if real, the change as landed fails an obligation. ANY of:
  - it breaks or regresses existing behavior on a reachable path;
  - the task's acceptance criteria or the plan's stated goal is not delivered
    (requirement unmet, misunderstood, or misimplemented) — including
    performance/efficiency findings when the task or plan obligates that
    characteristic (e.g. blocking I/O added to a path the plan promised to
    keep hot-path-safe);
  - it violates a mandatory, quotable project rule (e.g. a CLAUDE.md rule the
    conventions angle can cite) that the change is obligated to honor;
  - a risk the plan's `## Risk` section committed to mitigate **in this
    change** remains open;
  - it is an unjustified deviation that alters a contract or user-visible
    behavior.
- `follow-up` — real, but the change still delivers its obligations; the
  finding is separable improvement or separable debt. Typical (not
  categorical) cases:
  - a **pre-existing** defect surfaced by review but not introduced or
    worsened by this change;
  - improvements (reuse / simplification / efficiency / altitude /
    maintainability) whose impact does not breach an obligation above — a
    newly introduced maintainability imperfection is follow-up when it does
    not invalidate the change;
  - hardening or test gaps beyond the task's stated AC;
  - improvements to adjacent code the diff merely touches.
- **Accepted/deferred risks (three-way, replacing any blanket treatment):**
  - a risk the plan **validly** accepted or deferred (explicitly documented,
    rationale holds, no obligation breached) is **omitted by default** — per
    S1's rule, an explicitly addressed decision is not re-flagged;
  - emit it as `follow-up` **only when tracking is genuinely required** (the
    acceptance defers real work and no follow-up task or mitigation entry
    exists to carry it);
  - an acceptance that **does not hold up** — the rationale is unsupported,
    or the "accepted" risk in fact breaches a task obligation (AC, plan
    contract, existing behavior) — is `blocking`, classified like any other
    unmet obligation.
- **Cross-checks (the categorical trap, stated in the file):** a
  cleanup-angle finding whose reachable impact breaches an obligation (a
  task-breaking performance regression, a mandatory-rule violation) is
  `blocking`; a correctness-angle finding that is a minor newly introduced
  imperfection breaching no obligation is `follow-up`. Classify by impact,
  not by angle category.
- **Uncertainty rule:** a PLAUSIBLE verdict does NOT demote a finding to
  `follow-up`. Confidence (verdict) and disposition are orthogonal: classify
  by consequence-if-real; the verdict expresses how sure you are.

**Ordering and caps (partition before cap):** partition findings
`blocking` first, then `follow-up`; severity-ordered *within* each partition.
Findings caps (quick ≤4, standard ≤8, deep ≤15) apply **after**
classification and cut from the end of the `follow-up` partition first — a
blocking finding is never dropped in favor of a follow-up, regardless of
severity. **Cap-overflow rule (deterministic):** the cap never truncates the
`blocking` partition — when blocking findings alone reach or exceed the tier
cap, report **all** blocking findings (the advertised cap is exceeded by
exactly the blocking overflow) and omit the entire `follow-up` partition.
**Disclosure:** whenever the cap omits anything, state it explicitly at the
end of the prose list — how many findings were omitted and from which
partition (e.g. "cap: 3 follow-up findings omitted"). Silent omission is
never allowed. The concern block mirrors the same partition order and the
same included set.

Keep the honesty rules: "if a dimension is genuinely clean say so briefly", no
filler, **never pad to reach a cap or minimum** (shadow's honesty rule
deliberately overrides the extracted min-findings floors — do not adopt them,
in any tier). Then the concern block last, exactly as today — wire format
frozen, but the body text carries the disposition (and verdict, in
standard/deep) as prose.

**Minimonitor pipeline compatibility (wire contract preserved exactly — no
parser/minimonitor code change in this task):**

- Opening `===AITASK-CONCERNS===` and closing `===END-CONCERNS===` sentinels
  unchanged; concern lines remain `- [priority | region] body`.
- Disposition and verdict remain **free text inside `body`** — no new parser
  fields, no wire-format change in t1158 (e.g. a body ending
  "…Disposition: blocking. Verified: CONFIRMED.").
- The concern block remains the **final output**; a complete closing fence
  remains mandatory (auto-offer requirement); block omitted when there are no
  concerns.
- Producer order: blocking concerns before follow-ups, so the picker and the
  forwarded payload inherit blocking-first order (parser and
  `build_clipboard_payload` are order-preserving).
- **Authoring constraint (t1123 parser-live guard):** the rewritten
  impl-challenge.md and the new impl-review-angles.md must never embed a
  contiguous open→items→close example block — name the sentinels inline, as
  concern-format.md does. The guard in `tests/test_concern_parser.py` globs
  ALL `.claude/skills/aitask-shadow/*.md`, so the new file is automatically
  in scope.
- **Documented UX boundary (stated in impl-challenge.md):** minimonitor will
  display and forward the disposition/verdict text inside each concern body,
  but provides no native address-now/follow-up sections, badges, filters, or
  separate actions yet — those belong to the future concern-format redesign,
  outside t1158.

## Step 3 — SKILL.md Step 3 routing text

Update the impl-challenge bullet (SKILL.md line ~154) to:

- **Adversarially challenge the implementation** ("review the implementation",
  "adversarial review", "basic/legacy review", "quick review of the
  implementation", "deep review of the code", "did it actually do what the
  plan said") → read and follow `impl-challenge.md`. It offers effort tiers
  (quick / basic / standard / deep; basic = the legacy three-axis adversarial
  review) — a tier named in the user's ask is honored ("adversarial review"
  with no qualifier → basic); otherwise it asks, recommending standard.

No other SKILL.md changes (Step 0 greeting derives from Step 3 automatically —
maintainer note forbids hardcoded copies).

## Verification

1. AC-consistency check: the amended task AC (Step 0) and the implemented tier
   behavior agree — verify ladder named for Standard + Deep only, Basic
   recorded as the legacy exception.
2. Read-back review: concern-block rules in the rewritten file diff-clean
   against `concern-format.md` requirements (fences, dash, block-last,
   omit-when-clean); ordering rule states the blocking-first partition.
3. Basic-tier fidelity check: diff ALL THREE catalog axis texts (S0, S1, S2)
   against the pre-change `impl-challenge.md` axes ("Attack the implementation
   along these axes" section) — substance preserved one-to-one, each living
   only in `impl-review-angles.md` (no inline duplication in Basic).
4. Tier-detection table check: each routing phrase class ("quick", "basic",
   "legacy", unqualified "adversarial review", "standard", "deep",
   generic-no-level) maps to the documented tier / prompt; the 3-option-capped
   two-stage chooser covers all four tiers deterministically.
5. Disposition-rubric check: rubric present in `impl-review-angles.md`,
   impact-vs-obligations based with the angle-category cross-checks, the
   uncertainty rule, and the partition-before-cap ordering + cap-overflow +
   disclosure rules referenced by every tier that caps findings.
6. **Minimonitor concern-pipeline compatibility:**
   ```bash
   python3 -m unittest tests.test_concern_parser tests.test_concern_picker_modal tests.test_minimonitor_concern_action
   ```
   Must verify: shadow procedure documents contain no parser-live example
   block (the existing guard globs all `.claude/skills/aitask-shadow/*.md`,
   auto-covering the new impl-review-angles.md); complete blocks trigger the
   auto-offer and incomplete blocks do not; blocking-first producer order
   survives parsing and picker selection; clipboard forwarding preserves the
   selected order; and a concern body containing
   `Disposition: blocking. Verified: CONFIRMED.` round-trips unchanged
   through parse → payload. The last case is not directly covered today —
   add the **smallest focused parser test** to `tests/test_concern_parser.py`
   (one test method: parse a block whose body carries that trailer,
   assert body text and clipboard payload preserve it verbatim). Do NOT
   change the parser or minimonitor implementation to add structured
   disposition support — that is the future redesign, not t1158.
7. `./.aitask-scripts/aitask_skill_verify.sh` — expect no golden/stub impact
   (plain sub-procedure); investigate if it flags anything.
8. `grep -rn "impl-challenge" .claude .agents .opencode` — confirm wrappers and
   SKILL.md references still resolve; no other surface names tier internals.
9. `bash tests/test_shadow_spawn_config.sh` as a cheap smoke that the shadow
   surface is intact.

## Commit

Single code commit: `feature: Add effort-tiered review modes to shadow impl-challenge (t1158)`
(files: the two sub-procedure files + SKILL.md + the focused parser test).
Task-file AC amendment commits separately via `./ait git` (Step 0). Then Step 9 post-implementation
per task-workflow (no worktree — fast profile works on current branch; gates:
`risk_evaluated` declared → recorded by Step-9 orchestrator).

## Risk

### Code-health risk: low
- Markdown-only change in the Claude skill tree; no code, no parser, no `.j2`
  surface. The one load-bearing contract (concern block) is preserved by
  keeping its section text unchanged, and the legacy behavior is preserved as
  the Basic tier rather than rewritten. · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- The adapted tier prompts' review *quality* cannot be verified mechanically —
  the AC checks structure (tiers, angles, ladder present), but whether the
  angle adaptation actually produces sharper shadow reviews is only observable
  in live use. Bounded: structure is verifiable now, Basic preserves the known-
  good legacy behavior as a fallback, and prompts are cheap to iterate.
  · severity: medium · → mitigation: shadow_impl_review_tier_live_check

### Planned mitigations
- timing: after | name: shadow_impl_review_tier_live_check | type: manual_verification | priority: medium | effort: low | addresses: goal-achievement (live review quality unverifiable mechanically) | desc: Spawn the shadow against a real completed task and run the impl review at each tier (quick/basic/standard/deep), confirming tier auto-detection from free text (incl. "adversarial review" → basic), Basic's one-to-one legacy behavior, verdict-annotated findings in standard/deep, disposition tags + blocking-first ordering in all tiers, and the deterministic two-stage chooser on a 3-option-capped agent (Codex). For a generated Standard or Deep review, additionally confirm the minimonitor pipeline end-to-end — (1) the concern auto-offer triggers, (2) the picker opens in blocking-first order, (3) disposition and verdict text show in each concern body, (4) selected concerns forward to the clipboard/followed agent unchanged.
