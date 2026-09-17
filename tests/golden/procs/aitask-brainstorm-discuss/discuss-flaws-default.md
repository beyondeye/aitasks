# Structural design-flaw and risk check

**Advisory-only:** never edit proposal files, node YAML or any brainstorm session
state, and never run a mutating `ait brainstorm` command — present everything to the user.

A sub-procedure of the brainstorm discuss skill (`aitask-brainstorm-discuss`).
Serves `>f`. Your job is to be a constructive adversary of a **design proposal**:
look for where the design fails or rests on something unproven, not to reassure.
Adapted from the shadow companion's plan challenge and assumption surfacing,
re-framed for a design proposal rather than an implementation plan.

**Output is plain prose/markdown for the user.** There is no machine-readable
block, no round snapshot and no rejection store in this skill — do not emit
delimiter fences or round headers.

**Inputs:** the proposal(s) the user named (handles or node ids). With no operand
and exactly one proposal listed at Step 0, use it; with several, ask which in one
line, or run the check on each in turn if the user says "all". Read each in full
from its `PROPOSAL:` path. Read its node YAML (`META:`) when a finding depends on
a declared assumption or trade-off, and the `TASK_FILE:` when a finding depends on
what the brainstormed task actually asked for.

## Procedure

1. **Form a model of the design.** In two or three sentences for yourself: what
   the proposal builds, which parts it adds or changes, and what it must deliver
   to satisfy the brainstormed goal.

2. **Attack the design along these axes** (skip any that genuinely do not apply;
   add others the proposal invites):
   - **Regressions to existing behaviour** — what that works today could this
     design break or quietly change?
   - **Missed edge cases** — inputs, states or environments it does not handle:
     empty or huge inputs, concurrent use, failure and recovery paths, platform
     differences, first run versus upgrade.
   - **Wrong shape for the goal** — is the approach itself a mismatch? Is there a
     simpler or more robust design it skipped?
   - **Blast radius / parts changed unaware** — which parts does it touch, and
     what happens when someone later edits one of them without knowing this
     design's assumptions? Hidden coupling, implicit contracts, two sources of
     truth.
   - **Verification gaps** — could the design be built and "pass" while the goal
     is not actually met? Is there any way to prove it works?
   - **Unstated dependencies** — does it rely on something not yet built, a tool
     or version, or other work landing first?

3. **Surface the assumptions it rests on**, across five buckets:
   - **Environment / tooling** — a tool, version, config or service is present.
   - **Data / inputs** — shape, size, encoding, ordering, uniqueness of what it
     processes.
   - **Behaviour of other code** — an existing component behaves as the design
     expects.
   - **Sequencing** — something happens first, or only once.
   - **Intent / scope** — the design understood the actual goal, and what it
     leaves out really is out of scope.

   An assumption becomes a **finding** only when it is load-bearing (the design
   fails if it is false) **and** the proposal does not verify it. List the
   peripheral or verified ones in one short closing paragraph, not as findings.

4. **Write each finding** with:
   - a one-line statement of the flaw or risk, and the scenario that triggers it;
   - **severity** — `high` / `medium` / `low`;
   - **load-bearing or peripheral** — does the design fail if this is real, or
     does it only get worse?
   - an **impact vector** for addressing it, as three sentences:
     `Improves: <dimension>(<magnitude>)[, …].`
     `Worsens: <dimension>(<magnitude>)[, …].` — **mandatory**, written as
     `Worsens: nothing.` when the fix genuinely costs nothing
     `Effort: <high|medium|low>.`
     Draw dimensions from: `goal`, `correctness`, `robustness`, `performance`,
     `verification`, `maintainability`, `simplicity`; magnitudes are
     `high` / `medium` / `low`. The worsen side is what stops a list of demands
     from silently over-building the design;
   - a closing plain-words line per `discuss-audience.md` §2 — composed **after**
     the finding above, derived from it.

5. **Order and stay honest.** Load-bearing findings first, then by severity. If
   the design is genuinely solid on an axis, say so in one line instead of
   manufacturing a concern — a short list of real problems beats a long list of
   weak ones. Close with the one or two findings you would want settled before
   choosing this proposal, and leave the decision to the user.
