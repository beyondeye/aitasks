# Plan Socratic Questioning

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user wants
to *think a plan through themselves* rather than be told what's wrong — "ask me
questions about this", "make me reason about it", "help me decide if this is
right". Here you lead with questions, not verdicts.

**Inputs:** the captured screen (shadow Step 1) and/or the fetched plan file
(shadow Step 2). Fetch the full plan first if only a fragment is on screen.

**Advisory-only:** present the questions to the user; never drive the followed
agent's pane.

## Procedure

1. **Read the plan in full** and understand its goal, approach, and trade-offs.

2. **Pose open-ended, non-leading questions** that guide the user to examine the
   plan's own reasoning. Good Socratic questions:
   - probe the *why* behind a choice ("What made this approach preferable to
     <alternative>?"),
   - surface trade-offs the user may not have weighed ("What does this give up to
     gain <X>?"),
   - test the goal fit ("How will you know this actually solved the original
     problem?"),
   - explore consequences ("If this assumption turned out false, what breaks?"),
   - invite the user's own judgment rather than implying a "correct" answer.

   Avoid rhetorical questions that just smuggle in your opinion ("Don't you think
   this is risky?"). If you have a concern, turn it into a genuine question the
   user could answer either way.

3. **Go a few at a time.** Ask 2–4 focused questions, then let the user respond
   and follow their reasoning — don't dump a long interrogation. Adapt the next
   questions to their answers, deepening where they're uncertain.

4. **Stay curious, not combative.** The aim is to help the user reach their own
   well-examined decision about the plan. Summarize, when useful, what their
   answers have surfaced — but leave the conclusion to them.

If the user actually wants direct critique instead of questions, switch to
`plan-challenge.md`.
