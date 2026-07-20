# Implementation Challenge (adversarial, tiered)

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user wants
the **code actually written** for a task stress-tested — "review the
implementation", "did it actually do what the plan said", "check the code that was
written". This is the implementation-side companion to `plan-challenge.md` (which
reviews the *plan*). Your job is to be a constructive adversary against the
**implementation**: actively look for where the code, as written, is wrong — not
to reassure.

The review runs at one of four **effort tiers** — `quick`, `default`,
`advanced`, `deep` — selected in the **Tier selection** section below.
**Default is the compatibility tier**: the direct successor of the pre-tier
adversarial review (the legacy three-axis analysis, preserved as-is).
**Advanced is the recommended improved review.** Angle texts, the verdict ladder, the disposition rubric, and
the ordering/cap rules live in the shared catalog
`.claude/skills/aitask-shadow/impl-review-angles.md` — read it when a tier
references it.

**Advisory-only:** present the findings to the user; never drive the followed
agent's pane. (Reading local git state — commits, diffs — is fine; "advisory-only"
governs the *followed pane*, not your own repo reads.)

## Inputs

1. **Task definition + plan** — via `./.aitask-scripts/aitask_shadow_context.sh <task_id>`
   (`TASK_FILE:` + active `PLAN_FILE:`). This is "what was supposed to be built."
   Resolve `<task_id>` as in the shadow SKILL.md Step 2 if it wasn't passed.

   **Archived-plan fallback (needed once the task is committed/archived).**
   `aitask_shadow_context.sh` returns only the *active* plan and deliberately does
   not scan the archive — so a completed task yields `PLAN_FILE:NOT_FOUND` even
   though its plan (carrying the Final Implementation Notes you most need here)
   lives under `aiplans/archived/`. When the active plan is missing, look there
   before concluding there is no plan:
   ```bash
   ls aiplans/archived/p<N>_*.md 2>/dev/null                        # parent task
   ls aiplans/archived/p<parent>/p<parent>_<child>_*.md 2>/dev/null  # child task
   ```
   Use the archived plan if found. Only when *neither* an active nor an archived
   plan exists is the plan genuinely unavailable.
2. **The actual code changes (real diff)** — first discover the task's commits:
   ```bash
   ./.aitask-scripts/aitask_revert_analyze.sh --task-commits <task_id>
   ```
   Each `COMMIT|<hash>|<date>|<subject>|<ins>|<del>|<matched-id>` line names a
   commit; read their diff (`git show <hash>`, or `git diff <first>^..<last>`).

   **Working-tree fallback (important — this is often the live case).** The task
   workflow commits the code *and* writes Final Implementation Notes only **after**
   the Step 8 review prompt. So at the common pre-commit review moment there may be
   **no task commit yet**, with all real changes sitting in the working tree /
   index. If `--task-commits` returns nothing (or only older sessions' commits),
   inspect the uncommitted state instead:
   ```bash
   git status --short   # what changed
   git diff             # unstaged changes
   git diff --cached    # staged changes
   ```
   Review whichever of committed / staged / unstaged actually carries this task's
   changes. **Tell the user which source you reviewed** (committed vs
   working-tree) — a working-tree review is of in-progress, not-yet-final state.

   Throughout this procedure and the angle catalog, "the diff" means this
   **resolved diff source** — there is no separate diff-gathering phase.
3. **The plan's `## Final Implementation Notes`** — the agent's own narrative
   (*Actual work done*, *Deviations from plan*, *Issues encountered*, *Key
   decisions*), written by task-workflow Step 8 at end of implementation. This is
   where deviations are *justified*.

When you (re)capture the followed pane to read long content, use the deep
plan-review capture — `./.aitask-scripts/aitask_shadow_capture.sh --deep <followed_pane_id>` —
so a long diff or notes section isn't truncated to the default window's tail.

## "Too early to review" gate (required — run first, every tier)

If the resolved plan — **after** applying the archived-plan fallback in input 1 —
does **not** contain a `## Final Implementation Notes` section, the implementation
phase of the task workflow has not completed. (Resolve the archived plan first: a
committed/archived task has an archived plan *with* the notes, and must not trip
this gate.) When the notes are genuinely absent, before doing anything else
**warn the user**: it is probably too early to review the implementation — the
task workflow likely has not finished, so the diff may be partial and no
deviations have been narrated yet. Let the user decide: **abort**,
or **proceed anyway** against the partial state. Do not silently continue. If the
user proceeds anyway, the diff to review is necessarily the **working-tree /
index** state (input 2's fallback), not committed history — review that and say so.

## Tier selection (after the gate)

Auto-detect the tier from the user's free-text ask:

- "quick" / "fast" → **Quick**
- "default" / "basic" / "legacy" / an unqualified "adversarial review" →
  **Default**
- "advanced" / "standard" / "normal" → **Advanced**
- "deep" / "thorough" / "max" / "exhaustive" → **Deep**
- A generic "review the implementation" with no level or compatibility wording:
  ask via `AskUserQuestion` (Header "Review tier") with four options —
  "Advanced (Recommended) — systematic angle-based review with precision
  verification, ≤8 findings" / "Default — the legacy three-axis adversarial
  review, single full-context pass, no cap" / "Quick — reduced hunk-only scan,
  no verification, ≤4 findings" / "Deep — expanded angles, recall-biased
  verification, gap sweep, ≤15 findings". This single 4-option question works
  on every supported agent — Codex CLI's `request_user_input` accepts 4
  options per question (verified live on v0.144.6; see
  `.agents/skills/codex_tool_mapping.md`).

Nothing routes to Quick implicitly — it runs only on an explicit request.

**Angle scoping (user intent wins).** The tier picks the *default* angle set
(see the activation table). A user ask naming specific angles or focus areas
("just check the callers", "only plan deviations", "skip the cleanup angles")
narrows or extends that default, at the tier's depth (candidate caps and the
verify pass still apply in Advanced/Deep). Map free-text focus phrases to
catalog angle names and confirm the resolved set in one line. Two guard rails:

- Only an **explicit user narrowing** may drop a legacy axis from a run's
  default set — for the Default tier that protects all three axes (S0/S1/S2)
  equally; for Advanced/Deep it protects S1/S2 (S0 is not in their default
  set — superseded by the A–E methodology).
- Scoping never changes a tier's **methodology**: at Default, a focus request
  narrows the attention of the single adversarial pass — it does not activate
  Advanced's candidate fan-out, verdict ladder, or Deep's gap sweep. A user
  who wants the angle methodology asks for Advanced/Deep.

State the chosen tier (and any angle scoping) to the user before starting.

## Angle-activation table

Angle and mechanism texts live in `impl-review-angles.md`.

| Angle / mechanism | quick | default | advanced | deep |
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
| Findings cap (see cap-overflow rule in the catalog) | ≤4 | none | ≤8 | ≤15 |

## Tier: Quick

`quick → 1 diff pass → no verify → ≤4 findings`

A reduced hunk-only scan; no full-context review, no verification. Tell the
user up front this is the reduced-scope pass. One pass over the resolved diff:
flag only runtime-correctness bugs visible from the hunk alone — inverted/wrong
condition, off-by-one, null/undefined deref where adjacent lines show the value
can be absent, removed guard, falsy-zero check, missing `await`, wrong-variable
copy-paste, error swallowed in a catch that should propagate — plus hunk-visible
duplication of an existing helper and dead code the diff leaves behind. Also
one cheap shadow glance: scan the Final Implementation Notes against the diff
for a glaring unexplained deviation. Skip test/fixture hunks (`test/`, `spec/`,
`__tests__/`, `*_test.*`, `*.test.*`, `fixtures/`, `testdata/`). No full-file
reads. Do **not** flag style, naming, perf, missing tests, or anything outside
the hunk. At most **4 findings**, one line each. If nothing qualifies, say so.

## Tier: Default (= Legacy)

`default → 1 full-context adversarial pass → no formal verify → prioritized findings`

The pre-tier adversarial review, preserved one-to-one — the compatibility tier.
One full-context adversarial pass over the resolved implementation diff, the
plan, its `## Risk` section, and the Final Implementation Notes, attacking
along the three legacy axes from the catalog (skip any that don't apply; add
others the change invites):

- **Angle S0 — implementation flaws** (legacy axis 1)
- **Angle S1 — unmitigated plan risks** (legacy axis 2)
- **Angle S2 — plan-deviation auditor** (legacy axis 3)

No multi-angle candidate fan-out, no verdict ladder, no gap sweep, no findings
cap, no minimum. The findings presentation, honesty rules, advisory-only
guardrail, and concern-block behavior below apply exactly as in every tier.

## Tier: Advanced

`advanced → 10 angles × 6 candidates → precision verify → ≤8 findings`

The recommended improved review. You are reviewing for **precision**: every
finding you surface should be one a maintainer would act on.

**Phase 1 — Find candidates.** Run **10 independent finder angles** in sequence
yourself, in THIS context — do NOT spawn subagents for them: **A, B, C** +
**Reuse, Simplification, Efficiency, Altitude, Conventions** + **S1, S2** (texts
in the catalog). Each surfaces **up to 6 candidate findings** with `file`,
`line`, a one-line `summary`, and a concrete `failure_scenario` (for
cleanup/S-axis candidates, the failure scenario states the concrete cost per
the catalog's cleanup-precedence note). Apply the catalog's **anti-drop rule**.

**Phase 2 — Verify (self, 1-vote, 3-state, precision-biased).** Dedup
candidates that point at the same line/mechanism, keeping the one with the most
concrete failure scenario. For each remaining candidate, re-read the relevant
code and assign exactly one verdict from the catalog's **verdict ladder**
(without the recall addendum). Keep CONFIRMED and PLAUSIBLE; drop REFUTED.

At most **8 findings** (cap-overflow rule in the catalog).

## Tier: Deep

`deep → 12 angles × 8 candidates → recall verify → gap sweep → ≤15 findings`

You are reviewing for **recall**: catch every real bug a careful reviewer would
catch in one sitting. At this level, catching real bugs matters more than
avoiding false positives — err on the side of surfacing.

**Phase 1 — Find candidates.** Run **12 independent finder angles** in sequence
yourself, in THIS context — do NOT spawn subagents for them: **A, B, C, D, E** +
**Reuse, Simplification, Efficiency, Altitude, Conventions** + **S1, S2**. Each
surfaces **up to 8 candidate findings**. Do NOT let one angle's conclusions
suppress another's — if two angles flag the same line for different reasons,
record both. Apply the catalog's **anti-drop rule**.

**Phase 2 — Verify (self, 1-vote, recall-biased).** Dedup near-duplicates (same
defect, same location, same reason → keep one). For each remaining candidate,
re-read the relevant code and assign exactly one verdict from the catalog's
**verdict ladder**, applying the **recall addendum** (PLAUSIBLE by default).
Keep CONFIRMED and PLAUSIBLE; drop REFUTED. Do NOT drop on uncertainty.

**Phase 3 — Sweep for gaps.** Run the catalog's **gap-sweep focus list**:
one more pass as a fresh reviewer holding the verified list, hunting ONLY for
defects not already listed; up to 8 additional candidates, verified the same
way as Phase 2. Never pad.

At most **15 findings** (cap-overflow rule in the catalog).

## Findings presentation (all tiers), then stay honest

Produce a prose findings list, partitioned per the catalog's **ordering and
caps** rules: `blocking` findings first, then `follow-up`, severity-ordered
within each partition. For each finding give:

- a one-line statement of the problem;
- *why* it bites (the triggering scenario);
- severity (high / medium / low);
- its **disposition** — `blocking` or `follow-up`, classified per the
  catalog's **disposition rubric** (impact vs obligations — never by angle,
  never by verdict);
- in Advanced/Deep: its **verdict** (CONFIRMED or PLAUSIBLE).

If the tier's cap omitted anything, disclose it per the catalog's disclosure
rule. **Stay honest** (same rule as `plan-challenge.md`): if a dimension is
genuinely clean, say so briefly — a short list of real problems beats a long
list of weak ones. No generic "consider adding tests" filler, and never pad to
reach a cap or a minimum — the extracted /code-review minimum-findings floors
are deliberately NOT adopted, in any tier.

## Also emit the structured concern block (for pick-and-forward)

After the human-readable list, append a machine-parseable copy of the *same*
concerns so the user can tick a subset and forward them to the followed agent via
minimonitor's concern picker. This block is **additive** and does **not** relax
the advisory-only guardrail (it is text for the *user* to copy).

**Emit this block as the final output of your review — nothing after it.**
Minimonitor's picker captures the tail of your pane and forwards the *last*
concern block it finds, so trailing commentary after the block (or forgetting to
emit it) makes the picker fall back to an earlier/stale block. Print the review,
then the block, then stop.

Emit a block delimited by an opening `===AITASK-CONCERNS===` line and a closing
`===END-CONCERNS===` line (those two exact literals; single source of truth:
`.claude/skills/aitask-shadow/concern-format.md`), with one concern per line
between them. The concern lines themselves look like:

```
- [high | file.ext:120] In path/to/file.ext the new guard compares the raw email instead of the normalized one, so a task assigned with a trailing-space email never matches and re-locks every resume. It bites on the common reclaim path. Normalizing both sides before compare would fix it — exact form your call. Disposition: blocking. Verified: CONFIRMED.
- [medium | unmitigated risk] The plan's Risk section flagged concurrent writers to the ledger, but the diff adds no locking around the append, so two resumes can interleave and drop one run. The Final Implementation Notes don't mention it, so it looks unaddressed rather than deliberately deferred. Disposition: follow-up. Verified: PLAUSIBLE.
```

Rules — all load-bearing for minimonitor's parser; match them exactly:
- One concern per line, in the form `- [priority | region] body`.
- The leading `- ` (dash **and** space) is **MANDATORY** on every concern line —
  it is the wrap-collision guard (a soft-wrapped continuation line never carries
  it, so the parser can't mistake wrapped text for a new item).
- `priority` is one of `high`, `medium`, `low` — reuse the severity you assigned.
- `region` for implementation concerns should identify the **code locus**
  or the **axis** (`unmitigated risk`, `unjustified deviation`, `correctness`)
  — and MUST stay **short** (≤ ~30 chars): use `basename.ext:LINE`, never a
  full repo path (put the full path in the body instead). The whole
  `[priority | region]` marker must survive on ONE rendered row: some agent
  TUIs hard-wrap long lines with literal newlines that even a wrap-joined
  capture cannot rejoin, and a wrap *inside the bracket* makes the item
  unparseable to minimonitor.
- `body` carries the **full framing** — the problem, *why it bites*, and enough
  context for the receiving agent to choose **how** to fix it. Do **not** compress
  it to a bare one-liner. "One logical line" is a **parser constraint** (emit no
  literal newline mid-concern — let the terminal soft-wrap), not a brevity
  constraint.
- End the body with the finding's disposition as prose (`Disposition: blocking.`
  or `Disposition: follow-up.`) and, in Advanced/Deep, its verdict
  (`Verified: CONFIRMED.` / `Verified: PLAUSIBLE.`). These stay **free text
  inside the body** — they are not parser fields, and the line format above is
  unchanged.
- Order items to match the prose list: blocking partition first, then
  follow-up, severity-ordered within each partition.
- **Always emit the closing `===END-CONCERNS===` fence** — minimonitor's
  auto-offer only fires on a complete block.
- Emit the block **only when you have at least one concern**. If the
  implementation is genuinely clean, omit the block entirely.

**UX boundary (current minimonitor behavior):** minimonitor displays and
forwards the disposition/verdict text inside each concern body, but it has no
native address-now/follow-up sections, badges, filters, or separate actions
yet — those belong to the future concern-format redesign, outside this
procedure's scope.
