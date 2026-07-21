---
Task: t1200_shadow_review_flag_omitted_findings_default_recall.md
Base branch: main
plan_verified: []
---

# t1200 — Shadow impl-review: flag omitted findings, close the Default-tier recall gap

## Context

The shadow agent's implementation review (`aitask-shadow` → `impl-challenge.md`)
runs at four effort tiers, added by **t1158** and renamed by **t1169**
(`basic`→`default`, `standard`→`advanced`). The user reports that since that
work landed, the **Default** tier — the direct successor of the old unqualified
"adversarial review" — very rarely surfaces any concerns at all, and suspected
findings were being post-filtered.

That suspicion is correct. Exploration found two independent defects:

1. **A silent post-filter.** `impl-challenge.md` "Findings presentation (all
   tiers)" routes *every* tier through the disposition rubric in
   `impl-review-angles.md`. That rubric's **Accepted/deferred risks (three-way)**
   clause says a validly accepted/deferred risk is **"omitted by default"**. The
   finding is dropped outright — not downgraded, not counted, not disclosed. The
   rule did not exist in the pre-tier review
   (`git show e77b33f84:.claude/skills/aitask-shadow/impl-challenge.md`), and it
   contradicts the catalog's own principle a few lines below: *"Silent omission
   is never allowed."* That disclosure rule is scoped only to **cap** omissions —
   and Default has **no cap**, so Default's only omission path is the one nothing
   discloses.

2. **No anti-drop counterweight at Default.** The **anti-drop rule**
   (`impl-review-angles.md`, *"finders that silently drop half-believed
   candidates … are the dominant cause of misses"*) is referenced **only** from
   Advanced Phase 1 and Deep Phase 1. Default never reads it, yet inherits all
   the suppression pressure ("a short list of real problems beats a long list of
   weak ones", "never pad") with no verify pass to route a half-believed
   candidate into. Two of Default's three axes are self-suppressing by
   construction (S1 "do NOT re-flag an addressed risk", S2 "only unexplained
   deviations"), so only S0 is an unrestricted sweep.

A contributing factor: `impl-challenge.md` "Tier selection" auto-routes an
unqualified **"adversarial review"** — the exact phrase a long-time user still
types — to Default with no notice, so the user silently gets a materially weaker
review than before.

**Intended outcome:** the shadow never hides a real finding. Findings it judges
non-urgent are **shown, flagged as such**, and the user decides. Default stops
silently dropping half-believed candidates, and a user who asks for "an
adversarial review" is told which tier they got.

**Decisions taken with the user during planning:**
- Add a third disposition `informational` (rather than re-scoping `follow-up`).
- Unqualified "adversarial review" keeps routing to Default, but the shadow
  announces the tier and points at Advanced.
- Default gains the anti-drop rule **only** — its one-pass three-axis legacy
  methodology is otherwise preserved.

## Scope

`aitask-shadow` is a **static** skill (no `.j2`, no rendered per-profile
variants), and the `.agents/` + `.opencode/` shadow trees carry a bare `SKILL.md`
wrapper with **no tier text** (verified). So there is **no rerender, no goldens
regeneration, and no cross-agent port task**.

The concern wire format (`- [priority | region] body`) is **unchanged** —
disposition/verdict live as free text inside `body` and are not parser fields
(pinned by `tests/test_concern_parser.py::test_disposition_verdict_trailer_round_trips`).

---

## Change 1 — `.claude/skills/aitask-shadow/impl-review-angles.md`, `## Disposition rubric`

**1a. Three-value disposition.** The rubric opens *"Every finding, in every
tier, carries a disposition: `blocking` or `follow-up`."* → make it three:
`blocking`, `follow-up`, `informational`. Keep the existing sentence that
disposition is decided by **reachable impact measured against the change's
obligations**, and that the discovering angle and the verdict never determine it.

Add the `informational` definition after the `follow-up` bullet:

> - **`informational`** — real and worth the user seeing, but the reviewer is
>   **not asking for action**: the change's obligations are met and the finding
>   is one the reviewer believes is already handled, explicitly accepted, or
>   outside this change's remit. State **why** you consider it settled (quote the
>   plan's acceptance rationale, the guard, or the obligation boundary) so the
>   user can disagree and escalate it themselves.
>   **`informational` is never a parking slot for a finding you believe is a
>   genuine unaddressed defect** — that is `blocking` or `follow-up` by the rules
>   above. It is the disposition for "I looked, I think it's fine, here is my
>   reasoning."

**1b. Rewrite the "Accepted/deferred risks (three-way)" bullet** so no branch
omits. Replace the current three branches with:

> - **Accepted/deferred risks (three-way — none of these are omitted):**
>   - a risk the plan **validly** accepted or deferred (explicitly documented,
>     rationale holds, no obligation breached) is **`informational`** — report it
>     with the plan's stated rationale named, so the user can judge that rationale
>     independently. (This supersedes Angle S1's "do not re-flag an addressed
>     risk": S1 governs whether it is a *problem*, not whether the user sees it.)
>   - an acceptance that defers real work with **no follow-up task or mitigation
>     entry** carrying it is `follow-up` — the tracking gap is the finding.
>   - an acceptance that **does not hold up** — rationale unsupported, or the
>     "accepted" risk in fact breaches a task obligation (AC, plan contract,
>     existing behavior) — is `blocking`, classified like any other unmet
>     obligation.

Also amend **Angle S1** (`## Shadow / legacy axes`) so its "Do **NOT** re-flag"
sentence points at the rubric rather than reading as a drop instruction: an
addressed/mitigated risk is reported as `informational`, not suppressed.

**1c. Uncertainty rule.** Extend the existing orthogonality note: a `PLAUSIBLE`
verdict demotes a finding to neither `follow-up` **nor** `informational` —
classify by consequence-if-real.

## Change 2 — same file, `## Anti-drop rule` (make it tier-general)

Today it terminates at the verify pass, which only Advanced/Deep have. Rewrite:

> Every candidate with a nameable failure scenario must **reach the output** —
> through the verify pass in tiers that have one (Advanced, Deep), and **directly
> into the findings list** in tiers that do not (Quick, Default). Finders that
> silently drop half-believed candidates bypass the only step that can adjudicate
> them, and are the dominant cause of misses. In a tier with no verify pass, do
> not resolve your own uncertainty by dropping: report the candidate with an
> honest severity and disposition — `informational` when you believe it is
> already handled, and say why. Applies within the tier's declared scope (Quick
> stays hunk-only) and before its cap.

## Change 3 — same file, `## Ordering and caps` → rename to `## Ordering, caps, and the no-silent-omission rule`

- Partition order becomes `blocking` → `follow-up` → `informational`;
  severity-ordered within each partition.
- Caps apply after classification and cut from the end of the **`informational`**
  partition first, then `follow-up`. `blocking` is never cut.
- The **cap-overflow rule** sentence currently reads *"…report all blocking
  findings … and omit the entire `follow-up` partition"* — it must be restated
  three-way (`informational` dropped first, then `follow-up`). Note this is not
  optional polish: Change 8's proximity rule fails any sentence that names
  `blocking` and `follow-up` together without `informational`.
- **Broaden the disclosure rule beyond caps** — this is the core fix for defect 1:

  > **No silent omission (any tier, any reason).** A candidate that survived to
  > classification is either **reported** or **disclosed**. Whenever anything is
  > left out — a cap cut, a scope narrowing the user requested, a dedup merge that
  > swallowed a distinct mechanism — state it at the end of the prose list: how
  > many, from which partition, and why (e.g. "cap: 3 follow-up, 2 informational
  > findings omitted"). The **only** sanctioned silent drop is a **REFUTED**
  > verdict, and only when you can quote the line that refutes it; "it probably
  > doesn't matter" is not a refutation. The concern block mirrors the same
  > partition order and the same included set.

## Change 4 — `.claude/skills/aitask-shadow/impl-challenge.md`

**4a. Tier selection** — the unqualified-ask line stays routed to Default, plus a
mandatory announcement. After the auto-detect list, extend the existing "State
the chosen tier … to the user before starting" sentence with:

> When the tier was **inferred** rather than named — i.e. an unqualified
> "adversarial review" resolved to Default — say so explicitly in that same line
> and name the alternative: *"Running **Default** (the legacy three-axis review)
> — Advanced is the recommended tier; say 'advanced review' for it."* A user must
> never learn which review they got only from its output.

**4b. Tier: Default (= Legacy)** — add one line to the tier body:

> Apply the catalog's **anti-drop rule**: with no verify pass here, a
> half-believed candidate is reported with an honest severity and disposition,
> never dropped.

Also correct the "preserved one-to-one" claim in this section and in the file
header: Default's **methodology** is the legacy review preserved one-to-one
(three axes, one full-context pass, no cap, no fan-out); its **reporting rules**
(disposition, ordering, no-silent-omission) are the shared modern ones.

**4c. Angle-activation table** — add an `Anti-drop rule` row with ✓ in all four
columns. Leave the findings-cap row as-is (`≤4` / none / `≤8` / `≤15`).

**4d. Findings presentation (all tiers)** —
- partition list becomes blocking → follow-up → informational;
- the per-finding `disposition` bullet enumerates all three values;
- replace *"If the tier's cap omitted anything, disclose it per the catalog's
  disclosure rule"* with a reference to the broader **no-silent-omission rule**;
- tighten the **Stay honest** paragraph so it cannot be read as license to drop:
  keep "never pad to reach a cap or a minimum" and "no generic 'consider adding
  tests' filler", and add that the anti-padding rule forbids **inventing** weak
  findings, never **suppressing** a real one — when unsure whether something is
  worth the user's time, report it as `informational` rather than dropping it.

**4e. Concern block** — `Disposition: informational.` joins the allowed
disposition prose values; the ordering bullet mirrors the three partitions. The
line format (`- [priority | region] body`), the mandatory `- ` prefix, and the
≤30-char `region` rule are **unchanged**. Add one non-fenced example concern line
carrying an `informational` trailer next to the existing two.

> ⚠ Do **not** introduce a contiguous `===AITASK-CONCERNS===` → items →
> `===END-CONCERNS===` block anywhere in these docs — `tests/test_concern_parser.py::TestShadowDocsNotParserLive`
> guards against it (the shadow reads these files at runtime and minimonitor would
> mis-forward the example, the t1119 live bug).

**4f. UX boundary note** — the closing paragraph already says minimonitor has no
disposition badges/filters; extend it to mention `informational` so the current
consumer behavior stays accurately described.

## Change 5 — `.claude/skills/aitask-shadow/SKILL.md` (dispatch bullet, ~line 153-160)

The bullet currently reads *"a tier named in the user's ask is honored
('adversarial review' with no qualifier → default)"*. Add that the inferred
routing is announced, matching 4a.

## Change 6 — Docs

`website/content/docs/workflows/shadow-agent.md` (the implementation-review
section, ~lines 56-67):
- the **"Every finding states …"** paragraph enumerates the dispositions →
  add `informational` and describe it as *"real, but the shadow believes it is
  already handled or accepted — shown with its reasoning so you can disagree"*;
  update "blocking-first" to the three-partition order and the cap-cut order.
- the **Default** bullet → note it never silently drops a candidate it was unsure
  about.
- the **tier-naming** paragraph → an unqualified "adversarial review" runs
  Default *and the shadow tells you so, pointing at Advanced*.

`aidocs/framework/shadow_agent.md` — grep shows no findings-handling or
disposition content; confirm at implementation time and leave unchanged if so.

`concern-format.md` — wire format unchanged, so no edit required; re-check that
its "Where it lives" producer list still reads correctly.

## Change 7 — Wire-format test

`tests/test_concern_parser.py`: alongside the existing
`test_disposition_verdict_trailer_round_trips`, add a case asserting a body
carrying `Disposition: informational.` round-trips verbatim through
`parse_concerns` → `build_clipboard_payload`. This pins that the new disposition
value rides in `body` and does not perturb the wire format.

## Change 8 — Disposition-surface drift guard (new test, lands **with** this change)

The disposition vocabulary is enumerated independently across three files (four
sites) with no derivation between them, plus `SKILL.md` which references
dispositions in passing. A manual grep cannot police this: the same
enumeration is **line-wrapped** in `impl-review-angles.md` —

```
carries a disposition: `blocking` or
`follow-up`. Disposition is decided by …
```

— so a line-based `grep` structurally misses it (verified during planning: the
naive grep found only 1 of the surfaces). This task is the one **adding** the
third value, so the guard must land here, not in a follow-up.

New `tests/test_shadow_disposition_surfaces.py` (repo has 132 Python tests;
`unittest` + `if __name__ == "__main__": unittest.main()`, matching
`tests/test_concern_parser.py`).

**Granularity: per enumeration site, not per file.** A file-level check passes
vacuously when one site in a file lists all three values while a second site in
the same file still says `blocking`/`follow-up` — and both multi-site files have
exactly that shape. All five sites anchor cleanly to markdown headings (verified
during planning):

```python
ANGLES    = ".claude/skills/aitask-shadow/impl-review-angles.md"
CHALLENGE = ".claude/skills/aitask-shadow/impl-challenge.md"
WEBSITE   = "website/content/docs/workflows/shadow-agent.md"

# (file, heading prefix) — one entry per site that enumerates dispositions.
SITES = [
    (ANGLES,    "## Disposition rubric"),                       # rubric definition
    (ANGLES,    "## Ordering, caps, and the no-silent-omission"),# partition + cut order
    (CHALLENGE, "## Findings presentation"),                    # per-finding bullet
    (CHALLENGE, "## Also emit the structured concern block"),   # `Disposition: …` trailer
    (WEBSITE,   "### Review the implementation"),               # user-facing paragraph
]
DISPOSITIONS = ("blocking", "follow-up", "informational")
```

Match each heading by **prefix** (so a parenthetical suffix can still be
reworded) and slice from that line to the next heading of the same-or-shallower
level. Normalize whitespace (`re.sub(r"\s+", " ", section)`) so line-wrapped
prose matches like any other.

**Per-site assertions:**

1. **Completeness** — all three `DISPOSITIONS` appear in the section.
2. **Every enumeration is three-way** — phrasing-independent, so the guard does
   not depend on a hardcoded list of stale wordings. For each occurrence of
   `blocking` in the normalized section, take a ±160-char window; if `follow-up`
   also occurs in that window, `informational` must occur in it too. This catches
   every shape the two-value enumeration currently takes without enumerating
   them: `` `blocking` or `follow-up` ``, the partition sentence *"`blocking`
   first, then `follow-up`"*, and — the case called out in review — the
   concern-block trailer *"(`Disposition: blocking.` or `Disposition:
   follow-up.`)"*.

**Global assertion:** run rule 2 over the **whole** of each of the four shadow
surfaces (the three above plus `.claude/skills/aitask-shadow/SKILL.md`), not just
the anchored sections, so a two-value enumeration that appears somewhere the
`SITES` table does not know about is still caught. `SKILL.md` is deliberately
excluded from rule 1 — it describes *tiers*, not dispositions, so requiring all
three tokens there would fail.

**Tripwires (so the guard cannot pass vacuously):**

- each heading prefix must match **exactly one** line in its file — zero or
  multiple matches fails with *"anchor not found / ambiguous: a heading was
  renamed or duplicated; update SITES"*. Without this, renaming a heading would
  silently reduce the guard to checking nothing.
- each extracted section must be non-empty.
- **negative controls:** feed the window helper (a) a synthetic string containing
  `` `blocking` or `follow-up` `` and assert it is flagged, and (b) the trailer
  form `` (`Disposition: blocking.` or `Disposition: follow-up.`) `` and assert it
  is flagged too — proving both shapes actually fail rather than the regex never
  matching.

Resolve paths relative to the repo root (derive it from `__file__`, as the other
tests in `tests/` do) so the guard passes regardless of the caller's cwd. Failure
messages must name the file, the site heading, and the offending window.

Add a short module docstring explaining *why* the guard exists (duplicated
vocabulary, no single source of truth) and that adding a fourth disposition means
updating `DISPOSITIONS` **and** every site in `SITES`.

## Verification

1. `python3 tests/test_concern_parser.py` — all tests pass, including the new
   `informational` round-trip and the existing `TestShadowDocsNotParserLive`
   guard (proves no edit introduced a parser-live example block).
2. `python3 tests/test_shadow_disposition_surfaces.py` — the new drift guard:
   every surface carries all three dispositions and no stale two-value
   enumeration survives, **including line-wrapped ones**. Its negative control
   proves the guard can fail. This **replaces** any manual grep as the
   authoritative cross-surface check.
3. `./.aitask-scripts/aitask_skill_verify.sh` — confirms no stub/template surface
   was disturbed (expected clean; `aitask-shadow` is static).
4. **Self-consistency read-through** of `impl-challenge.md` +
   `impl-review-angles.md`. Use single-quoted, fixed-string searches (no
   backticks or double quotes in the pattern — a backtick inside a double-quoted
   shell pattern is a quoting hazard):
   ```bash
   grep -rn -F -e 'omit' -e 'drop' -e 'suppress' -e 'do not flag' \
     .claude/skills/aitask-shadow/impl-challenge.md \
     .claude/skills/aitask-shadow/impl-review-angles.md
   ```
   Confirm every remaining occurrence is either the REFUTED carve-out or is
   paired with a disclosure obligation.
5. **Live behavioral check** (belongs in a manual-verification follow-up, since it
   needs a real shadow pane): run a Default-tier implementation review from
   minimonitor against a task whose plan has an explicitly *accepted* risk, and
   confirm (a) the tier announcement line appears, (b) the accepted risk shows as
   `informational` rather than vanishing, (c) the concern block parses and the
   picker forwards the informational item unchanged.

## Risk

### Code-health risk: low
- The disposition vocabulary is enumerated independently at 5 prose sites across
  3 files (`impl-review-angles.md` rubric + ordering/caps, `impl-challenge.md`
  findings-presentation + concern-block rules, the website workflow doc) with
  **no derivation between them**. Adding a third value grows
  that duplicated list, and a manual grep cannot police it — the enumeration is
  line-wrapped in `impl-review-angles.md`, so a line-based search misses it
  (verified during planning: the naive grep found 1 of the surfaces). A surface
  missed now, or on the next disposition change, silently contradicts the others
  and the shadow follows whichever it read
  · severity: medium · → mitigation: **Change 8** — the whitespace-normalized
  drift guard lands **in this task**, with a negative control. Residual risk after
  mitigation: low
- The concern block is a live parser contract. An edit that accidentally forms a
  contiguous `===AITASK-CONCERNS===`→items→`===END-CONCERNS===` example would be
  mis-forwarded by minimonitor (the t1119 live bug). Guarded by
  `TestShadowDocsNotParserLive`, so detection is automatic — residual risk is low
  · severity: low · → mitigation: none needed (existing test covers it)

### Goal-achievement risk: medium
- The deliverable is **instructions to an LLM**, not code, so the effect on the
  reported symptom ("I very rarely get concerns at Default") is probabilistic and
  cannot be proven by unit tests. Only a live Default-tier review against a real
  task can confirm the behavior actually changed
  · severity: medium · → mitigation: deferred to the Step 8c manual-verification
  follow-up (not a risk-mitigation task — Step 8c owns this surface)
- By deliberate decision, Default keeps its one-pass three-axis methodology and
  its two self-suppressing axes (S1 "do not re-flag an addressed risk", S2 "only
  unexplained deviations"). Removing the omit-by-default clause and adding
  anti-drop may therefore only **partially** lift Default's finding volume — some
  of the user's symptom may be inherent to the legacy methodology, and the real
  remedy would be "use Advanced"
  · severity: medium · → mitigation: shadow_default_tier_recall_reassessment

### Planned mitigations
- timing: after | name: shadow_default_tier_recall_reassessment | type: enhancement | priority: low | effort: medium | addresses: goal-achievement risk 2 (Default keeps its legacy methodology, so the fix may only partially lift finding volume) | desc: After live use, re-assess whether the Default tier's finding volume actually recovered; if the legacy three-axis one-pass methodology is itself the limiter, decide between promoting Advanced as the routed default or retiring Default

## Step 9 (Post-Implementation)

Standard: merge approval, `./ait gates run 1200` (the task declares
`risk_evaluated`), then `./.aitask-scripts/aitask_archive.sh 1200`.

## Final Implementation Notes

- **Actual work done:** All 8 planned changes landed as designed.
  - `impl-review-angles.md`: disposition rubric now carries three values
    (`blocking` / `follow-up` / `informational`); the `informational` definition
    was added with an explicit "never a parking slot for a genuine defect" guard;
    the "Accepted/deferred risks" bullet was rewritten three-way so **no branch
    omits** (validly accepted → `informational` with the rationale named);
    Angle S1's "do NOT re-flag" was reframed as a *classification* rule, not a
    drop instruction; the uncertainty rule now blocks demotion to
    `informational` on mere doubt; the anti-drop rule was made tier-general
    (verify pass where one exists, straight to the findings list where none
    does); `## Ordering and caps` was renamed to
    `## Ordering, caps, and the no-silent-omission rule` with the three-way
    partition/cut order and a broadened disclosure rule whose only sanctioned
    silent drop is a REFUTED verdict.
  - `impl-challenge.md`: mandatory announcement when a tier is *inferred*
    (unqualified "adversarial review" → Default, now stated out loud with
    Advanced named); Default tier gained the anti-drop rule; Quick gained it
    within its hunk-only scope; new `Anti-drop rule` row (✓ all four tiers) in
    the angle-activation table; findings presentation switched to three
    partitions and a "Honesty is not licence to drop" paragraph; concern block
    gained an `informational` example line and the three-value trailer rule;
    UX-boundary note updated.
  - `aitask-shadow/SKILL.md`, `website/content/docs/workflows/shadow-agent.md`:
    updated to match, incl. a new user-facing "the shadow never silently hides
    a finding" paragraph.
  - Tests: `test_concern_parser.py` gained an `informational` round-trip;
    new `tests/test_shadow_disposition_surfaces.py` (229 lines) guards the five
    enumeration sites.
- **Deviations from plan:** None in scope or approach. Two content edits were
  *forced by the new guard* rather than pre-planned (see below).
- **Issues encountered:**
  1. The drift guard failed on its first run against a site the plan had not
     enumerated: the rubric's **"Cross-checks (the categorical trap)"** bullet
     contrasted only `blocking` vs `follow-up`. Fixed by adding an
     `informational` branch. This is precisely the silent-contradiction class
     the guard exists to catch, and it was caught on day one.
  2. The first fix then failed the guard a *second* time: `informational`
     landed ~205 normalized chars after `blocking`, outside the 160-char
     co-occurrence window. Rather than widen the window (which would weaken the
     guard everywhere), the bullet was restructured to lead with the three-way
     statement. Net effect: the prose now *reads* three-way instead of merely
     containing the word somewhere in the paragraph.
  3. Review feedback during planning corrected two design defects before any
     code was written — a verification `grep` that was both quoting-fragile and
     structurally unable to see the line-wrapped enumeration (it found 1 of 5
     sites), and the drift guard being deferred to a follow-up task when t1200
     is itself the change adding the third value. Both were folded into the
     plan; the guard became Change 8.
- **Key decisions:**
  - **Third disposition over re-scoping `follow-up`** (user choice): preserves
    `follow-up`'s meaning of "real separable debt" instead of conflating it with
    "reviewer thinks this is already handled".
  - **Site-level, not file-level, drift guard:** both multi-site files would
    pass a file-level check vacuously (one site updated, one stale).
  - **Proximity rule over a list of stale phrasings:** the two-value enumeration
    appears in at least three shapes; matching literals would miss the fourth.
    The rule is "wherever `blocking` and `follow-up` co-occur, `informational`
    must too", which is phrasing-independent.
  - **Anchor tripwire:** each heading prefix must match exactly one line, so a
    renamed heading fails loudly instead of silently reducing the guard to
    checking nothing.
  - **Default keeps its legacy methodology** (user choice): it gained only the
    anti-drop rule. Advanced/Deep remain the answer for higher recall — tracked
    by the `after` mitigation.
- **Upstream defects identified:** None.

### Build verification
`aitask_skill_verify.sh`: OK (12 templates across 3 agents).
Tests: `test_concern_parser.py` 25 pass, `test_shadow_disposition_surfaces.py`
10 pass, `test_minimonitor_shadow_pick.py` pass, `test_shadow_spawn_config.sh`
13/13, `test_skillrun_codex.sh` pass.
