---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [shadow]
gates: [risk_evaluated]
anchor: 1158
created_at: 2026-07-21 11:34
updated_at: 2026-07-21 11:34
---

The shadow agent's implementation review (`aitask-shadow` → `impl-challenge.md`)
silently hides findings instead of surfacing them flagged. Reported symptom: since
the tier work landed (t1158 `basic`/`standard`/…, renamed by t1169 to
`default`/`advanced`), running the **Default** tier — the direct successor of the
old unqualified "adversarial review" — very rarely yields any concerns at all.

Exploration confirmed the mechanism. Two distinct defects.

## Defect 1 — a silent post-filter that hides findings (the reported symptom)

`.claude/skills/aitask-shadow/impl-challenge.md` "Findings presentation (all
tiers)" routes **every** tier through the shared disposition rubric in
`.claude/skills/aitask-shadow/impl-review-angles.md`. That rubric's
**Accepted/deferred risks (three-way)** clause says a validly accepted/deferred
risk is **"omitted by default"**, emitted as `follow-up` "only when tracking is
genuinely required".

- The finding is **dropped entirely** — not shown with a lower severity, not
  shown as informational, not counted anywhere. The user never learns it existed
  and cannot overrule the shadow's judgement that it wasn't worth their time.
- This rule **did not exist** in the pre-tier review (`git show
  e77b33f84:.claude/skills/aitask-shadow/impl-challenge.md`), whose only guidance
  was "prioritized list … separate fatal from fixable … stay honest". So Default
  is *not* in fact "the legacy review preserved one-to-one", contrary to what
  `impl-challenge.md` and `website/content/docs/workflows/shadow-agent.md` both
  claim.
- It also contradicts the catalog's own stated principle a few lines below:
  **"Silent omission is never allowed."** That disclosure rule is scoped only to
  *cap* omissions — and the Default tier has **no cap** (see the angle-activation
  table). So the one omission path Default actually exercises is precisely the
  one nothing discloses.

**Desired behavior (from the user):** concerns judged non-urgent must still be
**shown, flagged as such** — the user decides what to act on, not the reviewer.
Hiding is only acceptable for REFUTED (factually wrong) candidates.

## Defect 2 — the Default tier has no anti-drop counterweight

Independently of the rubric, Default is structurally the weakest full-context
tier and is missing the one rule that protects recall:

- The **anti-drop rule** (`impl-review-angles.md`, "finders that silently drop
  half-believed candidates … are the dominant cause of misses") is referenced
  **only** from Advanced Phase 1 and Deep Phase 1. Default never reads it.
- Default therefore inherits all of the suppression pressure ("a short list of
  real problems beats a long list of weak ones", "never pad", "if a dimension is
  genuinely clean, say so briefly") with **none** of the counterweight, and it
  has no verify pass / verdict ladder to route a half-believed candidate into.
- Two of Default's three axes are self-suppressing by construction: **S1** ("Do
  NOT re-flag a risk the implementation explicitly addressed/mitigated") and
  **S2** ("Flag only deviations that are unexplained"). Only S0 is an
  unrestricted sweep.

## Contributing factor — the tier naming misleads

t1169 renamed `basic` → `default` and `standard` → `advanced`. "Default" now
reads as the sensible middle choice, but it is the legacy-compat tier: no Angle
A/B/C, no cleanup angles (reuse / simplification / efficiency / altitude /
conventions), no verify pass. Worse, `impl-challenge.md` "Tier selection"
auto-routes an unqualified **"adversarial review"** — the exact phrase a
long-time user still types — straight to Default, with no prompt. A user who
asked for "the adversarial review" before t1158 and asks for it now gets a
materially weaker review and is never told.

## Acceptance criteria

1. **Flag, don't hide.** Remove the "omitted by default" disposition for validly
   accepted/deferred risks in `impl-review-angles.md`. Replace it with a visible
   third disposition (e.g. `informational` / `accepted-risk`) or an explicit
   low-severity `follow-up` that states *why* the shadow considers it already
   handled, so the user can disagree. Decide at planning time whether this is a
   new disposition value or a re-scoping of `follow-up` — a new value has
   downstream reach (see AC 5).
2. **No silent omission anywhere.** Broaden the catalog's disclosure rule beyond
   cap omissions: any tier, any reason, an omitted finding is counted and
   disclosed at the end of the prose list. Verify no other "omit"/"do not flag"
   instruction in `impl-challenge.md` / `impl-review-angles.md` can drop a
   finding without a trace.
3. **Give Default the anti-drop rule.** Make the anti-drop rule apply to the
   Default tier (and Quick, if it can be done without breaking Quick's advertised
   hunk-only scope), or state explicitly in the Default tier text how a
   half-believed candidate is to be reported rather than dropped.
4. **Fix the "preserved one-to-one" claim.** Either make Default genuinely equal
   to the pre-tier review, or correct the wording in `impl-challenge.md` and
   `website/content/docs/workflows/shadow-agent.md` to describe what Default
   actually does now. Consider whether an unqualified "adversarial review" should
   still auto-route to Default silently, or should instead prompt for a tier /
   route to Advanced — the auto-detect table in `impl-challenge.md` "Tier
   selection" is the single change point.
5. **Keep the concern-block contract intact.** Disposition/verdict text lives free
   inside the concern `body` (see `concern-format.md`); the parser
   (`.aitask-scripts/monitor/concern_parser.py`) has no disposition field, so a
   new disposition value must not alter the `- [priority | region] body` line
   format. If a new value is introduced, check the minimonitor picker and
   `tests/test_concern_parser.py` for anything that pattern-matches the existing
   `Disposition: blocking.` / `Disposition: follow-up.` prose.
6. **Docs.** Update `website/content/docs/workflows/shadow-agent.md` (its
   "Every finding states …" paragraph enumerates the dispositions) and
   `aidocs/framework/shadow_agent.md` if it describes findings handling.

## Key files

- `.claude/skills/aitask-shadow/impl-review-angles.md` — disposition rubric,
  anti-drop rule, ordering/caps + disclosure. Primary change point.
- `.claude/skills/aitask-shadow/impl-challenge.md` — tier definitions, tier
  auto-detect, findings-presentation section, concern-block rules.
- `.claude/skills/aitask-shadow/concern-format.md` — concern line contract
  (single source of truth; consumer side must not break).
- `website/content/docs/workflows/shadow-agent.md` — user-facing tier + finding
  descriptions.
- Reference for the true legacy behavior:
  `git show e77b33f84:.claude/skills/aitask-shadow/impl-challenge.md`.

## Notes

- The shadow sub-procedure files live **only** in the Claude tree; `.agents/` and
  `.opencode/` carry a `SKILL.md` wrapper only — no cross-agent port task is
  needed for changes confined to these files.
- Related but distinct, do not fold: **t1182** (manual-verification carryover for
  the t1158 tier work) and **t1159** (shadow review-loop automation). t1182's
  checklist may want an added item once this lands.
