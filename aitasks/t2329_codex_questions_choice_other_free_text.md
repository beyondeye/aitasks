---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [codexcli, codeagent, codex_questions]
gates: [risk_evaluated]
anchor: 2281
created_at: 2026-11-17 18:37
updated_at: 2026-11-17 18:37
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
