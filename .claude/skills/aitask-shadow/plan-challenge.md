# Plan Challenge (adversarial)

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user wants
a plan stress-tested before approving it — "poke holes in this", "what could go
wrong", "try to break it". Your job here is to be a constructive adversary:
actively look for where the plan fails, not to reassure.

**Inputs:** the captured screen (shadow Step 1) and/or the fetched plan file
(shadow Step 2). Fetch the full plan first if only a fragment is on screen.

**Advisory-only:** present the challenges to the user; never drive the followed
agent's pane.

## Procedure

1. **Read the plan in full** and form a clear model of what it intends to do and
   how.

2. **Attack it along these axes** (skip any that don't apply; add others the plan
   invites):
   - **Regressions / breakage** — what existing behavior could this change break?
     Which load-bearing path does it touch?
   - **Missed edge cases** — inputs, states, or environments the plan does not
     handle (empty/large inputs, concurrency, error paths, platform differences,
     first-run vs upgrade).
   - **Wrong shape** — is the approach itself a mismatch for the goal? Is there a
     simpler or more robust path the plan skipped?
   - **Blast radius / "edited unaware"** — what happens when someone later edits
     one of the touched files without knowing this plan's assumptions? Hidden
     coupling, implicit contracts, duplicated sources of truth.
   - **Verification gaps** — does the plan's own verification actually prove it
     works, or could it pass while the feature is broken?
   - **Unstated dependencies** — does it rely on something not yet built, a
     specific tool version, or another task landing first?

3. **Produce a prioritized list of concrete weaknesses.** For each: a one-line
   statement of the problem, *why* it bites (the scenario that triggers it), and
   its severity (high / medium / low). Be specific to this plan — no generic
   "consider adding tests" filler. Order by severity.

4. **Separate fatal from fixable.** Flag which findings (if any) should block
   approval versus which are improvements the user could accept as follow-ups.

5. **Stay honest.** If the plan is genuinely solid on an axis, say so briefly
   rather than manufacturing a concern. A short list of real problems beats a
   long list of weak ones. Present everything to the user to decide.
