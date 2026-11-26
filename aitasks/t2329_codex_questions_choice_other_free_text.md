---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [codexcli, codeagent, codex_questions]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2281
implemented_with: claudecode/opus5_5
created_at: 2026-11-17 18:37
updated_at: 2026-11-25 17:46
---

## Goal

Match Claude Code's `AskUserQuestion` more closely in the Codex attended-questions MCP
server (`aitask_questions`). Claude's widget always offers an "Other" option where the
user types free text instead of picking a listed option. The Codex server has no
equivalent today.

## Current behaviour (explored 2026-11-17)

- A `choice` question is sent as one required string field whose values are limited to
  the option ids (`form()` in `.aitask-scripts/aitask_questions/server.py`).
  `validate_answer` in `.aitask-scripts/aitask_questions/store.py` accepts only an exact
  option id from the form. From the chat, through `aitask_question_resume`, it accepts
  only an exact id or label and rejects any other text.
- `kind: "text"` is a separate question kind with no options.
- The current workaround (`.agents/skills/codex_tool_mapping.md:53`): add an
  `{id: "other"}` option and, when it is chosen, ask the detail as a second `text`
  question under a new `opening`. That means two asks, two occurrences and two receipts,
  and the typed text is not bound to the original choice.
- `present()` treats a response as `invalid_form_response` unless it contains exactly the
  schema's properties (`set(response.content) != set(schema["properties"])`, about
  server.py:100). So the form cannot have an optional field today.

## Codex limits (from the openai/codex source, `codex-rs/tui/src/bottom_pane/mcp_server_elicitation.rs`)

- The Codex form shows **one field per page** ("Field i/N"). A field is either a list to
  pick from (`Select`) or a text box (`Text`). On a list page the text box is disabled,
  so **options and free text cannot share a page** in MCP form elicitation. Our server
  cannot change this.
- Optional fields are supported. A non-required text field shows
  "Type your answer (optional)", and a blank one is **left out** of the reply.
- Codex's built-in `request_user_input` *does* offer "None of the above" with notes
  typed on the same page (`is_other`, Tab). The mapping avoids it on purpose: in default
  mode it allows only optional questions and refuses approvals. Changing that policy is
  **out of scope** here.

## Proposed design

1. Add an optional `allow_other: true` flag for `kind: "choice"` questions, validated in
   the store's question checks; it is rejected for `text` and `multi`. Decide whether the
   "Other" option is added by the server (fixed id, e.g. `other`, refused if it clashes
   with a caller's id) or supplied by the caller.
2. In `form()`, when `allow_other` is set, send the choice field as required and a second
   optional text field (e.g. `other_text`) as not required, with a prompt like "If you
   chose Other, type your answer". The result is one form and one ask.
3. In `present()`, accept a reply that leaves out optional properties. Still refuse
   unknown properties and a missing required one.
4. Store the answer so it keeps both parts: the option id plus the free text, e.g.
   `{"value": "other", "other_text": "..."}`. Validation rules:
   - `other` with empty text → decide: re-ask or refuse (`invalid_form_response`); never
     accept it silently as an answer.
   - text typed alongside a non-Other choice → decide: keep it as a note or drop it, and
     write that down.
   The receipt and the spec digest must cover the new shape.
5. Chat-reply path (`aitask_question_resume` with `prompt_answer`): for an `allow_other`
   question, a reply that matches no option id or label is accepted as
   `other` + the exact text. An exact id/label match still selects that option. Keep the
   rule that status requests and unrelated steering are not answers. This is a model
   judgement, so update the server `INSTRUCTIONS` and the tool docstring. Keep
   `INSTRUCTIONS`' first 512 characters within the pinned limit.
6. Update `.agents/skills/codex_tool_mapping.md` (the "Other" bullet) so the source's
   implicit "Other" becomes `allow_other: true` instead of a second ask. Check
   `aidocs/codeagents/codex_questions.md` for the question-shape description.

## Verify first (live)

Before committing to step 2, run a live Codex session (`tests/manual/codex_questions_probe.py`
or the agent-driven method in `aidocs/codeagents/codex_questions_prototype.md`) with a
two-field form, required choice plus optional text, at the negotiated protocol
(`2025-06-18`, `form: {}`). Confirm that the user can skip the optional field, that the
reply leaves it out, and how "Field 2/2" looks. If the live check shows the optional
field cannot be skipped, fall back to the **server asking the follow-up itself**: when
"Other" is chosen, the server appends a pending `text` question to the same occurrence.
That keeps one ask and one receipt.

## Tests

`tests/test_aitask_questions_mcp.py`:
- an option chosen from the form, with the optional field omitted, is accepted;
- Other + text from the form is accepted, and both parts are stored;
- Other without text follows the chosen rule;
- an unknown extra property is still refused;
- from the chat: unmatched text on an `allow_other` question becomes Other + exact text;
  on a question without `allow_other` it is still refused (`invalid_prompt_answer`);
- `allow_other` on `text`/`multi` is refused;
- a changed `allow_other` changes the spec digest (new occurrence, no reuse).

## Out of scope

- Routing questions through Codex's built-in `request_user_input`.
- Free text on multi-select questions; that could be a follow-up.
- Porting to other agents: OpenCode/Claude already have a native Other.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2330** id=2026-11-17T20:02:17Z.d5118c497a11c6ed3e88ec98 from=t2330 at=2026-11-17T20:02:17Z base=7df50e1c5f3ff0194851e524ee267f234873521c base_branch=main dirty=yes host=omg16
>
> | t2330 (created 2026-11-17) changes the same chat-answer matcher as your step 5: validate_answer() in .aitask-scripts/aitask_questions/store.py, codex_prompt_model_forwarded path. It adds normalized matching (case/whitespace/_-) and unambiguous fuzzy matching (word-prefix + typo ratio, with negation/prose guards).
> | This affects your "an exact id/label match still selects that option" rule. For an allow_other question, text should fall through to Other only after both the normalized step and the fuzzy step fail. Fuzzy probably needs a stricter threshold there, so a genuine free-text answer is not captured as a listed option. Whichever task lands second reconciles the ordering (advisory).

> **✉ note:t2330** id=2026-11-19T23:36:19Z.7c73edb3f4f21b296033bf1d from=t2330 from_verified=yes at=2026-11-19T23:36:19Z base=b0bb6e2575e27ba8cd13b897b76f9c0d6f47c6ec base_branch=main dirty=yes host=omg16
>
> | t2330 landed (commit b0bb6e257) the chat-answer matcher your allow_other change reconciles with. Claims below are tree-relative to that commit.
> | 
> | - There is NO fuzzy score or margin. The task's "stricter fuzzy score on allow_other questions" idea does not map onto the code: fuzzy is a discrete word-aligned rule (store.py `_align` / `_word_match`): every reply word is an equal word, a >=3-letter prefix, or a small same-first-letter typo of one LABEL word, in order, and every label word except a/an/the/and/to/of must be covered. Ids never go through fuzzy.
> | - The hook point for Other is `_resolve(options, value)` in store.py — it returns `(option, provenance, problem, candidates)` without raising; `match_choice` wraps it. Falling through to Other naturally fits where `_resolve` returns `problem == "unknown choice"`.
> | - Suggestion (your call): an `"ambiguous choice"` result should probably stay a refusal rather than become Other text — the user's reply matched two listed options, which is not free text.
> | - Any punctuation or symbol (Unicode P*/S*) in the normalized reply, any negation/hedge word, or more words than the label already disable fuzzy, so prose-like free text reaches "unknown choice" without being captured by a listed option. If you want fuzzy stricter on allow_other questions, the discrete knobs are MIN_PREFIX / TYPO_BUDGET (or skipping the fuzzy tier there entirely).
> | - Refusal reasons are built by `_choice_names`, which offers only replies `_resolve` confirms select each choice. If Other becomes a selectable outcome, its reason text and `_choice_names` likely need to mention it.
> | - The answer record now carries `label`, `match` (exact|normalized|fuzzy) and, for fuzzy, `via`/`edits`; `Store.submit` returns `resolved`. An Other answer will need its own `match`/record shape decision.

> **👁 note:read** id=2026-11-25T13:24:50Z.940f2f8e779138ef48fe4b6a by=t2329 at=2026-11-25T13:24:50Z mode=explicit ids=2026-11-17T20:02:17Z.d5118c497a11c6ed3e88ec98,2026-11-19T23:36:19Z.7c73edb3f4f21b296033bf1d

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-25T15:46:35Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-26T10:12:42Z status=pass attempt=1 type=human
