---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [codex_questions, codexcli, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2281
created_at: 2026-11-17 22:02
updated_at: 2026-11-18 22:56
---

## Symptom

When an attended Codex question (`aitask_questions` MCP server) times out, the
question waits for an answer typed at the ordinary chat prompt. Answering there
is very picky. Observed on t2323's `plan_approved` checkpoint:

- The pending choice had options `approve_start` / "Start implementation",
  `revise` / "Revise plan", `approve_stop` / "Approve and stop here",
  `abort` / "Abort task".
- Codex described the choices in prose as "start implementation, revise the
  plan, approve and stop, or abort".
- The user typed `start implementation`. Codex forwarded it as
  `aitask_question_resume(..., question_id="decision", prompt_answer="start implementation")`.
- The server returned `invalid_prompt_answer` with the question still
  `awaiting-chat-answer`. Codex then asked the user to retype exactly
  `Start implementation`.

## Root cause (explored 2026-11-17)

1. `validate_answer()` in `.aitask-scripts/aitask_questions/store.py` (about
   lines 101-114) matches a chat answer with
   `value.strip() in {o["id"], o["label"]}`. That is case-sensitive and
   whitespace-exact, so `start implementation` does not match the label
   `Start implementation`. The comment there says "Prompt input may carry an
   unambiguous label, but never parse prose/substring matches as consent."
2. `.agents/skills/codex_tool_mapping.md` (the timeout steps, about lines
   75-91) says to "Tell the user in plain prose which question is waiting, what
   the choices are… no numbered menu of options". Nothing says to quote the
   labels verbatim, so the agent paraphrases them ("revise the plan",
   "approve and stop"). Those paraphrases do not match the labels either, so
   the user cannot type back what they were shown.
3. The rejection reason is just "ambiguous or unknown choice; question remains
   pending". It does not list the accepted forms, so the agent can only ask the
   user to retype.

## Requested behaviour (from the user)

Add fuzzy matching, and accept a chat answer when the match is not ambiguous.

## Proposed design

Apply this only to the chat-answer source (`codex_prompt_model_forwarded`).
Form input (`mcp_form`) keeps exact id matching.

1. **Normalized exact match.** Casefold, collapse runs of whitespace, treat
   `_` and `-` as spaces, and strip surrounding quotes/backticks and trailing
   punctuation (`.`, `!`, `,`). Compare the result against each option's
   normalized id and label. One matching option means accepted (`match:
   normalized`). If two or more options normalize to the same string, the
   answer is ambiguous and is refused.
2. **Fuzzy match**, only when step 1 found nothing:
   - Word-prefix match: the reply's words are prefixes of the label's (or id's)
     words, in order. Examples: `revise` → "Revise plan", `start impl` → "Start
     implementation", `approve stop` → "Approve and stop here" if words may be
     skipped (decide and pin the rule).
   - Typo match: a similarity ratio (e.g. `difflib.SequenceMatcher`) between the
     normalized reply and the normalized label/id. Example: `strat implementaion`.
   - Accept only when exactly one option clears a minimum score and leads the
     runner-up by a fixed margin. Pin both constants in the code and the tests.
     Otherwise the answer is ambiguous and is refused.
3. **Safety rails.** Fuzzy acceptance is consent from heuristic evidence, so it
   stays bounded:
   - Skip fuzzy matching (fall back to step 1 only) when the reply contains a
     negation or hedge token, such as `not`, `don't`/`dont`, `no`, `never`,
     `without`, `instead`, `but`. `don't start implementation` must never
     select "Start implementation".
   - Skip fuzzy matching for long prose: more words than the longest label plus
     a small allowance.
   - Record how the answer matched in the answer record (`match: exact |
     normalized | fuzzy`, plus the score for fuzzy). Keep the raw text as
     today. Decide whether the receipt/digest must cover `match`, and write that
     decision down.
   - Return the resolved option (id and label) in the `aitask_question_resume`
     result. The agent then echoes it, e.g. "Recorded: Start implementation".
     Add this to the docstring/mapping.
   - Check whether anything downstream relies on prompt answers being exact.
     One place to check: the `approve`-prefix check that `aitask_gate.sh` and
     `approval.py` make on `plan_approved` / `review_approved` receipts (see
     `aidocs/codeagents/codex_questions.md`, around lines 332 and 367). Fuzzy
     acceptance must resolve to the option **id** before any of those checks
     run. That is already how `validate_answer` returns.
4. **Rejection reason lists the choices.** On refusal, the reason (and the
   `invalid_prompt_answer` result) names the option labels, and the candidate
   labels when the answer was ambiguous. The agent can then re-ask with the real
   labels.
5. **Agent guidance.**
   - `.agents/skills/codex_tool_mapping.md` timeout step 2: quote each option
     label verbatim (still plain prose, no numbered menu), and say that a
     case-insensitive or unambiguous partial answer is accepted.
   - Step 4: forward the user's exact text unchanged. The server does the
     matching; the agent never rewrites the reply into a label.
   - Echo the resolved label after an accepted answer.
   - Update the `aitask_question_resume` docstring in
     `.aitask-scripts/aitask_questions/server.py`. Update `INSTRUCTIONS` only
     if needed, and keep its first 512 characters within the pinned limit
     (tests pin this).
   - Update `aidocs/codeagents/codex_questions.md` (around line 137, "A choice
     answer must match one option id or label exactly; prose is not parsed")
     to describe the new rule.
   - Update the matching comment in `store.py`.

## Tests (`tests/test_aitask_questions.py`, plus `tests/test_aitask_questions_mcp.py` for the resume result)

- `start implementation`, `START IMPLEMENTATION`, `  Start   implementation. `
  and `approve start` (id with spaces) are all accepted as `approve_start`.
- `revise` → `revise`, and `start impl` → `approve_start` (fuzzy, prefix).
- A typo, `strat implementaion` → `approve_start` (fuzzy, ratio).
- `approve` alone is ambiguous between `approve_start` and `approve_stop`, so
  it is refused and the reason names both candidates.
- `don't start implementation`, `not now` and `no` are refused. (`no` is
  accepted only when it matches an option exactly or after normalization.)
- A long prose reply that contains a label is refused.
- Two options that normalize to the same string: refused as ambiguous.
- `mcp_form` input is unchanged and still needs an exact id.
- The answer record carries `match`, and the resume result carries the resolved
  id/label.
- A `plan_approved` receipt produced by a fuzzy answer still passes the gate's
  `approve`-prefix check, because the stored value is the option id.

## Related / coordination

- **t2329** (Ready, `allow_other` free text on choices) changes the same
  chat-answer path. Ordering contract: on an `allow_other` question, text falls
  through to Other only after both the normalized step and the fuzzy step find
  no match. A fuzzy match should probably need a stricter score there, so a
  genuine free-text answer is not captured as a listed option. Whichever task
  lands second reconciles this; a note has been sent to t2329.
- **t2324** (Implementing) has uncommitted edits to
  `aidocs/codeagents/codex_questions.md`. Re-read that file before editing and
  keep the edit to the one paragraph.
- The OpenCode/Claude flows use their native question widgets and are not
  affected.
