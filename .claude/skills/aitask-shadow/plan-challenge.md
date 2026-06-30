# Plan Challenge (adversarial)

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user wants
a plan stress-tested before approving it — "poke holes in this", "what could go
wrong", "try to break it". Your job here is to be a constructive adversary:
actively look for where the plan fails, not to reassure.

**Inputs:** the captured screen (shadow Step 1) and/or the fetched plan file
(shadow Step 2). Fetch the full plan first if only a fragment is on screen. When
you (re)capture the followed pane to read the plan, use the deeper plan-review
capture — `./.aitask-scripts/aitask_shadow_capture.sh --deep <followed_pane_id>` —
because plans are long and the default 200-line window can truncate earlier
constraints, decisions, or risk notes.

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

6. **Also emit the structured concern block (for pick-and-forward).** After the
   human-readable list above, append a machine-parseable copy of the *same*
   concerns so the user can tick a subset and forward them to the followed agent
   via minimonitor's concern picker — instead of retyping them. This block is
   **additive**: it does not replace the prose, and it does **not** relax the
   advisory-only guardrail (it is text for the *user* to copy; you still never
   drive the followed pane).

   Emit exactly this fenced format (single source of truth:
   `aidocs/framework/shadow_concern_format.md`):

   ```
   ===AITASK-CONCERNS===
   - [high | Step 7 ownership guard] The guard re-runs aitask_pick_own.sh even when Step 4 already acquired the lock on this host, so every resumed task writes a second, redundant ownership commit to the data branch. It bites on the common reclaim path — crash recovery, multi-day tasks — quietly doubling the commit history each time. Gating the re-run on whether the lock is already held by this host would fix it, but I'd leave the exact guard condition to you.
   - [medium | verification] The only test asserts the script exits 0; it never reads back the file the script was supposed to write. A regression that turns the write into a silent no-op would still pass, so the test proves the script ran, not that it worked. Asserting on the written content (or a round-trip read) would close the gap — however you prefer to structure it.
   ===END-CONCERNS===
   ```

   Rules — all load-bearing for minimonitor's parser; match them exactly:
   - One concern per line, in the form `- [priority | region] body`.
   - The leading `- ` (dash **and** space) is **MANDATORY** on every concern
     line — it is the wrap-collision guard (a soft-wrapped continuation line
     never carries it, so the parser can't mistake wrapped text for a new item).
   - `priority` is one of `high`, `medium`, `low` — reuse the severity you
     assigned in Step 3.
   - `region` names the plan section / axis the concern targets (a step name,
     `verification`, `blast radius`, …).
   - `body` carries the **full framing** of the concern — the problem, *why it
     bites* (the triggering scenario), and enough context for the receiving
     agent to choose **how** to address it. Match the **substance** of the
     corresponding prose item from Step 3; do **not** compress it to a bare
     one-liner — the framing is as important as the point. "One logical line" is
     a **parser constraint** (emit no literal newline mid-concern — let the
     terminal soft-wrap), **not** a brevity constraint: a rich, multi-sentence
     body that soft-wraps across several rows is correct and reassembles into
     one concern.
   - Order items by severity, matching the prose list.
   - **Always emit the closing `===END-CONCERNS===` fence** — minimonitor's
     auto-offer only fires on a complete block.
   - Emit the block **only when you have at least one concern**. If the plan is
     genuinely clean (Step 5), omit the block entirely.
