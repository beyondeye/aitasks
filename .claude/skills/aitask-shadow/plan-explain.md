# Plan Explainer (for a non-technical expert)

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user wants
a plan explained but may not share the deep technical background it assumes —
the plan is correct but *over their head* as written, or the part they care about
is buried under jargon.

This goes beyond a plain-terms paraphrase: it identifies the technical subjects
the plan is built on and offers the user, per subject, a short introduction and
the motivation for why the plan relies on it.

**Inputs:** the captured screen (shadow Step 1) and/or the fetched plan file
(shadow Step 2). If you only have a partial plan on screen, fetch the plan file
first so the explanation is complete.

**Advisory-only:** present everything to the user; never drive the followed
agent's pane.

## Procedure

1. **Read the plan** from the fetched plan file (preferred) and/or the captured
   screen. Get the whole plan, not just the visible fragment.

2. **Identify the technical subjects the plan rests on.** Scan for the
   frameworks, mechanisms, patterns, tools, and domain terms the plan assumes the
   reader already understands — e.g. "tmux panes", "git worktree", "Jinja
   rendering", "the gate ledger", "ANSI escape sequences". Aim for the handful
   that actually matter for understanding *this* plan, not an exhaustive glossary.

3. **Offer per-subject depth (let the user choose).** Present the detected
   subjects as a short list and ask which they'd like introduced. Use
   `AskUserQuestion` (multiSelect) with the subjects as options plus an
   "All of them" and a "None — just explain the plan" choice. Respect the answer:
   only expand the subjects they picked.

4. **For each chosen subject, give:**
   - **Introduction** — what it is, in one or two plain sentences (no jargon, or
     jargon immediately unpacked).
   - **Motivation** — *why this plan leans on it*: what problem it solves here,
     what would be worse without it. Tie it to the plan, not to the abstract.

5. **Walk through the plan in plain language.** Explain what the plan will do,
   step by step, in the order it happens, weaving in the chosen subject
   introductions at the point each first matters. Lead with outcomes ("after this,
   X will work") over mechanism. Call out explicitly anything that affects the
   user's decision (risk, irreversibility, what they'd need to verify).

6. **Invite follow-ups.** Offer to go deeper on any subject or any step. The goal
   is the user understanding the plan well enough to judge it — not a lecture.
