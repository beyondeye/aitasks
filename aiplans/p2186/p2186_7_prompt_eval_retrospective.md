---
Task: t2186_7_prompt_eval_retrospective.md
Parent Task: aitasks/t2186_generic_agent_prompt_eval_harness.md
Sibling Tasks: aitasks/t2186/t2186_1_*.md, aitasks/t2186/t2186_2_*.md, aitasks/t2186/t2186_3_*.md, aitasks/t2186/t2186_4_*.md, aitasks/t2186/t2186_5_*.md, aitasks/t2186/t2186_6_*.md
Archived Sibling Plans: aiplans/archived/p2186/p2186_*_*.md
Base branch: main
Output branch: main
---

# t2186_7: Retrospective: state of the implementation and five pre-registered trade-off investigations

Child 7 of t2186. The parent plan is `aiplans/p2186_generic_agent_prompt_eval_harness.md`; the task file carries the shared
constraints, the facts established during exploration and the target layout. Read both. Treat any deviation recorded in an archived sibling plan's Final Implementation Notes as authoritative over this plan.

## Context

Child 7 of t2186, the trailing retrospective. It records the state of the implementation, then
runs a **post-implementation investigation** of five design trade-offs, with the implemented
design as the baseline:
1. separate port vs shared implementation;
2. declarative rules vs small Python extensions;
3. cached judge structure vs the original prompt;
4. sequential sampling vs fixed repetitions;
5. one judge plus audit vs two judges throughout.

Each is pre-registered before it runs and ends at "retain", "change" or "insufficient
evidence", with a reason. Implementation changes and missing evidence become separately scoped
follow-up tasks; no implementation change lands in this child.

## Implementation

### `prompt_eval_retrospective`

#### Part A — state of the implementation

1. An effect table from `DESIGN_LEDGER.md`: each cost lever measured or unmeasured, with its
   numbers and source batch.
2. Re-run the child-1 equivalence proof at HEAD (still identical?) and the full offline suite.
3. Whether to promote the harness to an `ait` command: recommend only; a promotion is its own,
   separately scoped task.

#### Part B — post-implementation investigation

**The implemented design is the baseline.** Each investigation asks whether an alternative would
be better, and where the evidence to decide is still missing, it creates a scoped follow-up task
to collect it instead of guessing.

**Protocol — the same for all five:**
1. **Pre-register before running anything.** For each investigation, record in
   `aidocs/benchmarks/prompt_eval/investigations/PREREG.md`:
   - the baseline;
   - the alternative;
   - the evidence needed;
   - the estimated effort and spend;
   - the decision criterion.

   Commit it before the first measurement. The criteria proposed below are starting points that
   this child finalizes in PREREG.md; a criterion is never changed after its data is seen.
2. **Offline evidence first.** Use the ledger, saved batches, simulation, replay and prototypes
   in scratch worktrees (not committed).
3. **Paid comparisons separately.** Each one gets its own `plan` projection and its own approval
   prompt. A declined comparison leaves that investigation at "insufficient evidence".
4. **One outcome per investigation:** "retain", "change" or "insufficient evidence", each with
   its reason, written to `investigations/<id>.md`. Public files hold numbers and ids; quotes go
   to the private store.
5. **Changes are separate tasks.** Any implementation change becomes a separately scoped task,
   never an edit in this child. Missing evidence becomes a scoped follow-up task that carries
   its PREREG entry verbatim.

**I1 — Separate port vs shared implementation**

- **Baseline:** `pecore/` is a separate port, and shadow_q stays as a frozen copy.
- **Alternative:** shadow_q becomes a thin wrapper that runs its commands through `pecore/` with
  the shadow_q spec.
- **Evidence:**
  - The ledger's duplicated fixes and behaviour drift across children 1-6: counts, kinds, and
    which ones were intended.
  - A thin-wrapper prototype in a scratch worktree. It must pass the child-1 equivalence proof
    on the pinned pilot, the run-path equivalence tests, and `tests/test_shadow_q_harness.py`
    (with only import or argv adaptations, each listed).
  - Reproducibility of the original experiment: the pinned `git archive 6930f54e2` route must
    still rebuild the pilot classification byte for byte, whichever copy is live.
  - The status of t2179_2 and t2187, the tasks that own or use shadow_q.
- **Effort and spend:** medium; no spend.
- **Proposed criterion:**
  - **Change** if (a) the ledger shows at least one unintended drift or at least two duplicated
    fixes, (b) the prototype passes all three equivalence checks, and (c) t2179_2 has landed.
  - **Retain** if the ledger shows neither.
  - **Insufficient evidence** otherwise.

**I2 — Declarative rules vs small Python extensions**

- **Baseline:** a declarative spec over the core rule library.
- **Alternative:** a small extension interface. A spec-local module registers rule functions
  with one fixed signature over turns and helper facts, and each returns an outcome or nothing.
- **Evidence:**
  - From the ledger's authoring-friction section (child 4's generality record): awkward
    configuration, special cases, and core changes a spec forced.
  - Then **one additional, structurally different prompt**, authored both ways, offline with
    fake CLIs. A candidate is a multi-turn procedure step that branches on a helper's last line,
    e.g. the premise-staleness check (silent on `SKIP`, asks on `ASK_STALE`). It is unlike both
    the shadow `>q` bullet and the single-turn note send.
  - Ease of **authoring**: lines and files written, core changes needed.
  - Ease of **debugging**: time and the steps needed to localise a planted rule fault, and the
    quality of the error message.
  - Ease of **maintaining**: files touched for one rule change, and test coverage reachable
    without the core.
- **Effort and spend:** medium to high; no spend. Building both versions of the third prompt is
  likely its own scoped follow-up task, which this child creates with the PREREG entry.
- **Proposed criterion:**
  - **Change** (add the interface) if the declarative version of the third prompt needs a core
    change or a special case that the extension version keeps in one self-contained file, and
    the planted fault is localised at least as fast.
  - **Retain** if the declarative version needs no core change and is no harder to debug.
  - **Insufficient evidence** otherwise.

**I3 — Cached judge structure vs the original prompt**

- **Baseline:** the original (v1) judge-prompt structure.
- **Alternative:** the cached structure (v2, shared context in the system prompt), and the
  system-prompt-replacement arm if child 5 measured it.
- **Evidence:** both structures on **the same blinded answers**, including the difficult ones
  (the pilot's 8 disputed answers, borderline `could_choose` means, flagged answers). Measure:
  - cost per call;
  - per-dimension score deltas;
  - adequacy-verdict flips.

  All of it is measured against **independently reviewed reference judgments**, recorded
  privately before either arm's scores are read. A candidate source is the t2179_2 independent
  audit, if it has landed; otherwise a fresh blind review of the reference set. Child 5's probe
  data is reused but is not sufficient. **Passing calibration controls alone does not establish
  equivalence.**
- **Effort and spend:**
  - an offline part (reuse child 5's verdicts);
  - a paid comparison, projected separately: about 16 answers × 2 structures × the Claude judge,
    roughly $6-9 at pilot prices, re-derived at the gate.

  Codex's structure is unchanged, so it is compared on grouping cost only.
- **Proposed criterion:**
  - **Change** (adopt v2 as the default) only if, against the reference, v2's adequacy
    disagreements are no more than v1's, no difficult case flips without reference support, and
    the cost per call drops by a pre-registered margin.
  - **Retain** if v2 is worse on any of those.
  - **Insufficient evidence** without a reference set or with too few difficult cases.

**I4 — Sequential sampling vs fixed repetitions**

- **Baseline and alternative:** the two modes child 5 implemented. Fixed repetitions is the
  default, sequential sampling is opt-in.
- **Evidence:**
  - Seeded simulation over true success rates, concentrated **near the acceptance threshold**
    (target ± 0.1).
  - **Replayed data**: bootstrap resampling of real per-trial outcomes from the saved batches
    (the pilot; child 4's run if one was approved).
  - Metrics, all on the decision score: expected repetitions (cost), wrong-decision rate,
    undecided-at-max rate, insufficient-coverage rate. Simulations include non-zero unresolved
    rates, so the comparison covers cells that answer incompletely.
  - Whether fixed repetitions give a better reliability/cost trade-off for **small experiments**
    (≤ 5 reps per cell).
- **Effort and spend:** low; no spend.
- **Proposed criterion:**
  - **Change** (make sequential the default for a stated size class) if near the threshold its
    wrong-decision rate stays within a pre-registered δ of fixed repetitions' and it saves at
    least a pre-registered fraction of repetitions.
  - **Retain** fixed repetitions where either fails, including the small-experiment class if
    savings there are below the margin.
  - **Insufficient evidence** if the replay data is too thin to confirm the simulation (stated).

**I5 — One judge plus audit vs two judges throughout**

- **Baseline:** two judges throughout.
- **Alternative:** one judge plus the pre-registered audit sample.
- **Evidence:**
  - **Missed disagreements**: answers the two judges dispute that the audit did not sample.
  - **False passes**: audit-mode "adequate" where the two-judge rule says "inadequate".
  - Aggregate agreement.
  - All of it on **evidence beyond the 16-answer pilot**: a two-judge dataset of a
    pre-registered minimum size (proposed ≥ 60 answers). shadow_q has no more answers today, and
    aitask_note has no judge. So this child runs the replay on the pilot as a first look,
    labelled insufficient, and creates a scoped follow-up task that runs once such data exists.
    It also notes t2187 to judge with two judges throughout, so its run can be that data.
- **Effort and spend:** low offline; the data comes from t2187, or from a separately projected
  re-judging.
- **Proposed criterion:**
  - **Change** (make audit mode the default) only if, on at least the minimum answer count, the
    false-pass rate's upper Wilson 95% bound and the missed-disagreement rate stay within
    pre-registered bounds, and judging cost drops by the pre-registered margin.
  - **Retain** two judges if a bound fails.
  - **Insufficient evidence** below the minimum count.

#### Part C — hand-off

- A summary table in `investigations/README.md`: investigation → outcome → reason → follow-up
  task.
- Send t2187 a note (`./ait note 2187 --from 2186_7`) with:
  - the concrete commands;
  - the I3/I5 status, and the request to judge with two judges throughout;
  - the CLI-version drift.

  t2187 stays `Postponed` until the user decides to spend.

## Step 9

Archive via the normal Step 9 (Post-Implementation). The parent t2186 auto-archives with its last child.

## Verification

- `investigations/PREREG.md` is committed before the first measurement: its commit precedes
  every outcome file's.
- Each of I1-I5 has exactly one outcome (retain, change or insufficient evidence) with a reason.
  Every "change" and every missing-evidence item names a created follow-up task.
- No implementation change lands in this child; paid comparisons ran only after their own
  approval.
- The t2187 note returns `NOTE_APPENDED:`.

## Risk

### Code-health risk: low
- Documents and follow-up tasks only. · severity: low · → mitigation: none (contained by
  design)

### Goal-achievement risk: medium
- The investigations could be decided on thin or post-hoc evidence. · severity: medium
  · → mitigation: none (addressed in design: PREREG.md committed first, independent reference
  judgments for I3, a minimum answer count for I5, the decision score for every verdict,
  "insufficient evidence" plus a follow-up when the evidence is missing)
