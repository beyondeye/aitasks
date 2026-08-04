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
adversarial review. Its **methodology** is that legacy three-axis analysis
preserved one-to-one (one full-context pass, no cap, no fan-out); its
**reporting rules** — dispositions, partition ordering, and the
no-silent-omission rule — are the shared modern ones every tier uses.
**Advanced is the recommended improved review.** Angle texts, the verdict ladder, the disposition rubric, and
the ordering / cap / no-silent-omission rules live in the shared catalog
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
2. **The actual code changes (real diff)** — a **composite** of four channels:
   committed, staged, unstaged, and untracked. The **Review-state assessment**
   below owns the resolution (the commands, the NUL-safe enumeration rule, and
   the disclosure obligation) — do not resolve a diff source separately here.

   Why a composite and not a first-match chain: the task workflow commits the
   code *and* writes Final Implementation Notes only **after** the Step 8 review
   prompt. So at the common pre-commit review moment there may be **no task
   commit yet**, with all real changes sitting in the working tree / index — and
   just as often an earlier session's task commit **plus** newer uncommitted
   edits, where the newest work is exactly what the review most needs. A chain
   that stops at the first non-empty channel silently reviews the older half.

   Throughout this procedure and the angle catalog, "the diff" means this
   **resolved composite diff source** — there is no separate diff-gathering phase.
3. **The plan's `## Final Implementation Notes`** — the agent's own narrative
   (*Actual work done*, *Deviations from plan*, *Issues encountered*, *Key
   decisions*), written by task-workflow Step 8 at end of implementation. This is
   where deviations are *justified*.

   **Frequently absent, and that is normal.** Step 8 writes them inside its
   "Commit changes" branch — *after* the review prompt — so at the most common
   moment for this review they do not exist yet. Their absence is a fact to state
   (see the assessment below), never a reason to stop or to ask permission, and
   the angle catalog's notes-absent modes for S1/S2 apply.

When you (re)capture the followed pane to read long content, use the deep
plan-review capture — `./.aitask-scripts/aitask_shadow_capture.sh --deep` — so a
long diff or notes section isn't truncated to the default window's tail. Pass no
pane id: the helper resolves your bound followed pane itself (add
`<followed_pane_id>` only if Step 1 also had to).

## Review-state assessment (required — run first, every tier)

Resolve what there is to review, then **state** it. This assessment *informs*;
it does not prompt. Absent Final Implementation Notes are the **normal**
pre-commit state, not an anomaly — reviewing before they exist is the expected
flow, so it never costs the user a confirmation round-trip.

**1. Resolve the plan.** Take the active plan from input 1, then the
archived-plan fallback. Only when neither exists is the plan unavailable.

**2. Resolve the diff source as a COMPOSITE, not a precedence chain.** Build the
union of all four channels — never stop at the first non-empty one:

```bash
# committed — TWO steps: the helper yields commit METADATA, not paths
#   (COMMIT|<hash>|<date>|<subject>|<ins>|<del>|<matched-id>)
./.aitask-scripts/aitask_revert_analyze.sh --task-commits <task_id>
# …then, per <hash>, extract its paths NUL-separated:
git diff-tree -r --no-commit-id --name-only -z <hash>
git diff --cached --name-only -z                                     # staged
git diff --name-only -z                                              # unstaged
git ls-files --others --exclude-standard -z                          # UNTRACKED
```

Read each channel's content the usual way — `git show <hash>` (or
`git diff <first>^..<last>`) for commits, `git diff --cached` and `git diff` for
the index and worktree. The committed channel is the one that needs the explicit
second call: without the `git diff-tree` step it contributes commit subjects but
no paths, so a committed file whose name contains a space would fall outside the
path-safety guarantee the other three channels get. (`git diff-tree -r
--no-commit-id --name-only -z` is the plumbing form — no header to strip, no
quoting, NUL-terminated.)

**Enumerate paths NUL-separated, never from `git status --short`.** That
porcelain format is `XY PATH`, so a field-splitting read (`awk '{print $2}'`)
drops everything after the first space — `new helper.py` enumerates as `new` and
is then never read — and the format additionally C-quotes paths containing
spaces, quotes, or non-ASCII bytes. `git ls-files --others --exclude-standard -z`
emits raw, unquoted, NUL-terminated paths and already honors `.gitignore`.
Consume every channel with a null-safe loop
(`while IFS= read -r -d '' path; do … done < <(…)`) and quote `"$path"`
everywhere downstream. The `-z` on the two `git diff` calls is for the same
reason — a tracked path can contain a space just as easily.

**Untracked paths are load-bearing.** Neither `git diff` nor `git diff --cached`
sees a brand-new file, so a task whose whole deliverable is a new helper or a new
test would look like "nothing to review" while the implementation sits right
there. Untracked files must be **read in full** (there is no diff to read) and
reviewed as all-new code.

**3. List the included paths, and state the attribution limit.** Print the
composite path list before reviewing, grouped by channel. Uncommitted and
untracked changes carry **no task id** — they cannot be attributed to t\<id\>, so
a dirty worktree may hold another task's work. State this in one line rather than
prompting about it: cross-check the uncommitted paths against the files the plan
names, review everything, but explicitly flag any path the plan does not mention
as *possibly unrelated to this task*, and invite the user to narrow in free text
("only the monitor files"). A named narrowing is honored exactly like angle
scoping.

**4. Act on what you resolved:**

- **All four channels empty** — the *only* stop. Report "nothing to review for
  t\<id\>" and end. This is not a prompt: there is nothing to proceed with.
- **No plan at all** — continue, code-only, announcing that angles S1 and S2
  (plan risks, plan deviations) are unavailable for this run.
- **Notes absent (the normal pre-commit case)** — **no warning, no prompt.** One
  stated line: which channels are under review, and that the notes are not
  written yet because task-workflow writes them *after* its Step 8 review prompt,
  so deviations are audited against the plan directly.
- **Notes present** — state the channels; full S1/S2 semantics apply.

This section carries the "tell the user what you reviewed" obligation for the
whole procedure — stated once here, not repeated per tier.

## Tier selection (after the assessment)

Auto-detect the tier from the user's free-text ask:

- "quick" / "fast" → **Quick**
- "default" / "basic" / "legacy" / an unqualified "adversarial review" →
  **Default**
- "advanced" / "standard" / "normal" → **Advanced**
- "deep" / "thorough" / "max" / "exhaustive" → **Deep**
- A generic "review the implementation" with no level or compatibility wording:
  run **advanced** — the tier configured by profile
  'fast' via `shadow_impl_review_tier`. Announce it and name the
  override in the same line: "say 'deep review' (or any other tier) to run a
  different one." Do **NOT** ask.

Nothing routes to Quick implicitly — it runs only on an explicit request.

**Resolution order (apply in this order).** **1.** A tier named in the user's ask
— the four explicit-wording bullets above — always wins, including over a profile
default. **2.** Otherwise the profile's configured tier, when the key is set.
**3.** Otherwise the prompt.

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

**Announce an inferred tier (required).** When the tier was **inferred** rather
than named — in particular when an unqualified "adversarial review" resolved to
Default — say so explicitly in that same line and name the alternative, e.g.:
*"Running **Default** (the legacy three-axis review) — Advanced is the
recommended tier; say 'advanced review' for it."* A user must never have to infer
which review they got from the shape of its output. This covers a
**profile-derived** tier too: when the tier came from `shadow_impl_review_tier`
rather than from the user's wording, say which profile supplied it and how to
override it for this run.

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
| Anti-drop rule | ✓ | ✓ | ✓ | ✓ |
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
for a glaring unexplained deviation — **skip this glance entirely when the notes
are absent** (the normal pre-commit case); there is nothing to glance at, and
Quick does not read the plan itself. Skip test/fixture hunks (`test/`, `spec/`,
`__tests__/`, `*_test.*`, `*.test.*`, `fixtures/`, `testdata/`). No full-file
reads. Do **not** flag style, naming, perf, missing tests, or anything outside
the hunk. Within that scope the catalog's **anti-drop rule** still applies: a
hunk-visible candidate you are merely unsure about is reported, not dropped. At
most **4 findings**, one line each. If nothing qualifies, say so.

## Tier: Default (= Legacy)

`default → 1 full-context adversarial pass → no formal verify → prioritized findings`

The compatibility tier: the pre-tier adversarial review's **methodology**
preserved one-to-one. (Its reporting rules are the shared modern ones — see the
findings-presentation section below.) One full-context adversarial pass over the
resolved implementation diff, the
plan, its `## Risk` section, and the Final Implementation Notes, attacking
along the three legacy axes from the catalog (skip any that don't apply; add
others the change invites):

- **Angle S0 — implementation flaws** (legacy axis 1)
- **Angle S1 — unmitigated plan risks** (legacy axis 2)
- **Angle S2 — plan-deviation auditor** (legacy axis 3)

No multi-angle candidate fan-out, no verdict ladder, no gap sweep, no findings
cap, no minimum. The findings presentation, honesty rules, advisory-only
guardrail, and concern-block behavior below apply exactly as in every tier.

Apply the catalog's **anti-drop rule**. There is no verify pass at this tier to
adjudicate a half-believed candidate, so it goes straight into the findings list
with an honest severity and disposition — never dropped. If you believe the
matter is already handled, say so as an `informational` finding with your
reasoning, and let the user decide.

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

Produce a prose findings list, partitioned per the catalog's **ordering, caps,
and no-silent-omission** rules: `blocking` findings first, then `follow-up`,
then `informational`, severity-ordered within each partition. For each finding
give:

- a one-line statement of the problem;
- *why* it bites (the triggering scenario);
- severity (high / medium / low);
- its **disposition** — `blocking`, `follow-up`, or `informational`, classified
  per the catalog's **disposition rubric** (impact vs obligations — never by
  angle, never by verdict);
- in Advanced/Deep: its **verdict** (CONFIRMED or PLAUSIBLE).

If anything was left out — by the tier's cap or for any other reason — disclose
it per the catalog's **no-silent-omission rule**.

**Stay honest** (same rule as `plan-challenge.md`): if a dimension is genuinely
clean, say so briefly — a short list of real problems beats a long list of weak
ones. No generic "consider adding tests" filler, and never pad to reach a cap or
a minimum — the extracted /code-review minimum-findings floors are deliberately
NOT adopted, in any tier.

**Honesty is not licence to drop.** The anti-padding rule forbids *inventing*
weak findings; it never permits *suppressing* a real one. When you are unsure
whether something is worth the user's time, that is exactly what the
`informational` disposition is for — report it with your reasoning and let the
user judge. Deciding on the user's behalf that a real observation is not worth
showing is the one failure mode this section exists to prevent.

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
- [low | accepted risk] The plan explicitly accepted the unlocked counter increment, on the rationale that only the reaper writes it. That rationale holds against the diff — the only other writer is behind the same mutex — so I am not asking for a change; flagging it so you can judge the single-writer assumption yourself. Disposition: informational. Verified: CONFIRMED.
```

Rules — all load-bearing for minimonitor's parser; match them exactly:
- One concern per line, in the form `- [priority | region] body`.
- The leading `- ` (dash **and** space) is **MANDATORY** on every concern line —
  it is the wrap-collision guard (a soft-wrapped continuation line never carries
  it, so the parser can't mistake wrapped text for a new item).
- `priority` is one of `high`, `medium`, `low` — reuse the severity you assigned.
- `region` for implementation concerns should identify the **code locus**
  or the **axis** (`unmitigated risk`, `unjustified deviation`,
  `pending narration`, `correctness`)
  — it is **mandatory and never empty** (it is the row's only title in
  minimonitor's picker; an omitted one renders as `(no region)`) — and MUST
  stay **short** (≤ ~30 chars): use `basename.ext:LINE`, never a
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
- End the body with the finding's disposition as prose — one of
  `Disposition: blocking.`, `Disposition: follow-up.`, or
  `Disposition: informational.` — and, in Advanced/Deep, its verdict
  (`Verified: CONFIRMED.` / `Verified: PLAUSIBLE.`). These stay **inside the
  body** and the line format above is unchanged, but they are now **parsed**:
  minimonitor derives the disposition from this trailer and groups the picker by
  it. Two consequences for you: the trailer must be the **last thing in the
  body** (it is matched only as a terminal run, so anything written after it is
  not read as a trailer), and an omitted trailer makes the finding show up as
  needing attention.
- Order items to match the prose list: blocking partition first, then
  follow-up, then informational, severity-ordered within each partition.
- **Always emit the closing `===END-CONCERNS===` fence** — minimonitor's
  auto-offer only fires on a complete block.
- Emit the block **only when you have at least one concern**. If the
  implementation is genuinely clean, omit the block entirely.

**What minimonitor does with it (current behavior):** the picker derives each
finding's disposition from the trailer above and splits the list into a
**Needs addressing** section (`blocking`, `follow-up`, and anything with no
trailer) and an **Informational** section, which is dimmed and skipped by the
bulk-select key. The trailer text itself is hidden from the row but kept in the
forwarded payload, so the receiving agent still sees the disposition and verdict
verbatim. Ordering *within* a section is yours — keep emitting items in the
partition order above.
