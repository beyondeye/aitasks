---
Task: t2329_codex_questions_choice_other_free_text.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2329 — "Other" free text on Codex attended `choice` questions

## Context

Claude's `AskUserQuestion` always offers "Other", where the user types their own
answer. The Codex attended-questions MCP server (`aitask_questions`) has no
equivalent. The current workaround in `.agents/skills/codex_tool_mapping.md` is an
`{id: "other"}` option plus a second `text` question under a new `opening`. That
costs two asks, two occurrences and two receipts, and the typed text is not tied
to the choice. This task adds `allow_other: true` to `kind: "choice"`, so one form
and one receipt carry both parts.

Decisions already taken:
- **Server-added Other.** When `allow_other` is set, the server adds an option with
  the fixed id `other` and label `Other`. A caller option whose id or label
  normalises to `other` is refused. This keeps callers simple: they set one flag.
- **Text typed alongside a listed choice (form)** → the user chose **keep it as a
  note**. The listed id is recorded, the text is stored as `note`, and `resolved`
  carries it back. Gate consumers ignore it, so an `approve…` id still approves.
  The docs say so, and the agent must relay the note.
- **Other intent is never lost (review finding 1).** Other with blank text in the
  form is not answered and not discarded. The server stores an
  `other_requested` marker on the occurrence. From then on the question accepts
  **only** Other text: the next form is a text-only "your answer for Other"
  form. A chat reply needs the explicit Other route below, and an unmarked chat
  reply is refused, even one that equals a listed (e.g. approving) label. Other
  never approves, so the marker fails safe. **Backing out stays inside the
  occurrence (review finding 2b).** `aitask_question_resume(...,
  back_to_choices="<question id>")` names the question explicitly (review finding
  7). It clears that question's marker only when that question is the current
  pending one, then shows the full choice form again (or matches a `prompt_answer`
  given in the same call). Earlier accepted answers are untouched, so a user who changes their
  mind on question three does not have to answer questions one and two again.
- **Explicit free-text route; no silent fall-through (review finding 2).**
  `aitask_question_resume` gains `as_other: bool = False`. Only `as_other=true`
  records chat text as Other (exact text, no option matching). Unmarked text that
  matches no option is **refused exactly as today** (`invalid_prompt_answer`,
  pending, no receipt), so a forwarded clarification such as "What changed?" never
  becomes an answer. A bare unmarked "Other" is also refused, with a reason naming
  the `as_other` route. In the t2330 matcher (notes acknowledged), the
  server-added Other takes part only in the exact and normalized tiers, never in
  fuzzy. `"ambiguous choice"` stays a refusal. Listed options keep today's tiers.

## Implementation

### Pre-phase (risk mitigations)
1. [live_optional_field_probe] Live Codex check of the form shape, **before any
   product code changes**.
   - **Probe server.** Write a throwaway STDIO MCP server in the scratchpad (same
     `mcp` SDK as `server.py`). Its one tool elicits a form with a required
     `answer` string (`oneOf` Blue/Green/Other) plus an optional `other_text`
     string (not in `required`). It returns `ctx.request_context.protocol_version`,
     the client's elicitation capability dump, `response.action` and the raw
     `response.content`.
   - **Launch.** Run `codex --no-alt-screen` (0.172.0) in a private tmux server
     (`tmux -L t2329probe`), registering the probe with `-c mcp_servers.probe.*`
     overrides only; no config file is edited. Drive it with keys.
     - Run A: pick Blue, leave field 2 blank, submit.
     - Run B: pick Other, type text, submit.
   - **Record** the "Field i/N" rendering, then exit and kill the tmux server.
   - **Pass condition (all three required):**
     - (a) the handshake negotiated protocol `2025-06-18` with form elicitation
       (an elicitation capability of `{"form": {}}` or the legacy empty `{}`);
     - (b) run A came back `accept` with `answer == "blue"`, and `other_text` either
       absent or `""`;
     - (c) run B came back `accept` with `answer == "other"` and `other_text` equal
       to the typed text.
   - **Any failure, including a different negotiated protocol** → **stop and
     report to the user before writing product code.** If the field cannot be
     skipped, the re-plan is the task's fallback (a server-asked follow-up). Do
     not implement the two-field form.

### Main steps
2. **`store.py`: question checks.** Add `"allow_other"` to the allowed question
   fields. It must be a `bool`, and it is allowed only on `kind: "choice"`. When
   true, refuse an option whose `_normalize(id)` or `_normalize(label)` is `other`
   (reserved). Add the constants `OTHER_ID`, `OTHER_LABEL` and
   `OTHER_DESCRIPTION`, and a helper `choice_options(question)` that returns the
   options with the Other option appended when the flag is set. The stored
   questions stay exactly as the caller sent them, so `spec_digest` changes when
   `allow_other` changes: reusing an opening refuses, and a new opening opens a new
   occurrence.
3. **`store.py`: answer validation.** `validate_answer(question, value, source,
   text=None, as_other=False, other_requested=False)`:
   - **One text bound everywhere (review finding 5).** Every user text that is
     stored (`other_text` from either form, a `note`, and the `as_other` chat
     text) must be 1..20000 characters after the same `strip()` blank check the
     existing answer check uses. It goes through a shared
     `_user_text(text, name)` helper that raises `QuestionError`. An over-limit
     reply is refused (a form reply → `invalid_form_response`, and the marker is
     kept), and the question stays pending with no answer.
   - **form (`mcp_form`):**
     - part `other_text` → the answer is the text-only form: `value` must be
       `OTHER_ID` and `text` must pass `_user_text` → `{label: "Other", match:
       "exact", other_text: text}`.
     - otherwise the exact id must be in `choice_options`, and a stripped-blank
       `text` counts as None:
       - Other + text → `other_text`;
       - Other with no text → raise the new `OtherTextMissing(QuestionError)` (in
         `errors.py`);
       - listed option + text → `note`;
       - `text` on a question without `allow_other` → refused.
   - **chat (`codex_prompt_model_forwarded`):**
     - `as_other=true` → refused unless `allow_other`. (`submit` already refused it
       for any non-`choice` kind before dispatch, see step 4.) Otherwise `value` (exact,
       unchanged, non-blank) is recorded as `OTHER_ID` with `other_text = value`
       and `match: "as_other"`. No option matching.
     - `as_other=false` with `other_requested` → refused: "the user chose Other in
       the form; resume with as_other=true and their exact text".
     - `as_other=false` otherwise → `_resolve(choice_options(q), value,
       literal_only={OTHER_ID})`. `_resolve` gains `literal_only`: ids in it skip
       the fuzzy tier. A listed option → as today. The Other option itself →
       refused, with a reason naming `as_other`. Unknown or ambiguous → refused as
       today.
   - `_choice_names` and `_choices_reason` use `choice_options`. Other is named
     `"Other" (resume with as_other=true and the user's own text)`.
4. **`store.py`: state and records.**
   - **`submit`.** Add the parameters `text=None` and `as_other=False`, and pass
     `other_requested = qid in body.get("other_requested", {})` to the validator.
     **Before the `multi` dispatch to `_submit_selection`** (review finding 3),
     refuse `as_other=true` or a non-None `text` unless the question is a
     `choice` with `allow_other`. A multi-select reply carrying `as_other`
     therefore changes neither the selection nor the receipt.
   - **New `Store.back_to_choices(session_id, question_id)`.** It refuses unless
     `question_id` is the current pending question **and** carries the marker.
     **Lifecycle guard first (review finding 6).** Inside the same `edit()`
     transaction, and after the `_refresh` that `edit()` already runs (so a
     just-invalidated occurrence is seen as invalidated), it refuses with
     `QuestionError` and writes nothing unless the state is open: `pending`,
     `awaiting-chat-answer` or `deferred`. A `cancelled`, `invalidated` (including
     one retired by a newer opening) or `complete` occurrence keeps its state, its
     marker and its receipt exactly. Only then does it remove the marker and
     **retire any active attempt** (`attempt = None`, the state becomes
     `awaiting-chat-answer`, the event `other_withdrawn` names the retired attempt
     id). With no active attempt the open state is left as it is (a `deferred`
     occurrence stays `deferred`). Then it returns the view (review finding 4). After that, a delayed response
     from the text-only form fails the existing attempt-id check with
     `stale_attempt`, and `begin()` is no longer `busy`, so the restored choice form
     can start. Earlier answers, `selections` and the occurrence identity are not
     touched.
   - **Attempts know their part.** `begin()` stores `attempt["part"]` (`"choice"`,
     or `"other_text"` when the marker is set). A form `submit` validates against
     the **attempt's** part, not the current marker. A response is therefore
     always judged by the form that was actually shown, and a part mismatch is
     `stale_attempt`.
   - **On `OtherTextMissing` (form only).** Run the existing stale-attempt check
     first. Then set `body["other_requested"][qid] = {"at", "attempt"}`, clear the
     attempt, set the state to `awaiting-chat-answer`, add the event
     `other_text_missing`, and return
     `view(outcome="other_text_requested", transport_outcome="other_text_missing")`.
   - **Accepted answers.** The record is still `{"value", "raw", "source",
     **provenance}`, so `other_text` and `note` land in it. On acceptance, drop the
     question's marker.
   - **Duplicate vs conflict.** A different `other_text` for the same id is a
     `conflict`; a different `note` is a `duplicate` that keeps the original.
   - **`resolved()`** uses `choice_options` and copies `other_text` and `note`.
   - **`view()`.** Show each pending `allow_other` question with the Other option
     appended (a copy). Add `pending_part: "other_text"` when the first pending
     question carries the marker, so the agent's relay and `status` say what is
     awaited.
5. **`server.py`.**
   - **`form()`.** A choice with `allow_other` uses `choice_options`. Its schema has
     `"answer"` (required) and `"other_text"` (string, `maxLength` 20000, **not
     required**, titled "Your answer (if Other)", described as otherwise an
     optional note). When the pending page is the `other_text` part, `form()`
     builds a text-only form instead: `{"other_text": required, minLength 1,
     maxLength 20000}`. Both forms carry the same schema bound as the server-side
     `_user_text` limit,
     message "You chose Other for: <text>. Type your answer."
   - **`present()`.** Replace `set(content) != set(properties)` with: content is a
     dict, its keys are a subset of `properties`, and `required` is a subset of its
     keys. There is **no blanket string-value rule** (review finding 1): native
     multi-select sends an array in `selected`, which the existing
     `_submit_selection` validation keeps checking. Only an `other_text` value,
     when present, must be a string. Every other value check stays where it is
     today (`validate_answer` and `selection.parse_submission`). For the
     text-only form submit `value=OTHER_ID`
     with `text=content["other_text"]`. Otherwise use `text=content.get("other_text")`.
     The `other_text_requested` outcome is simply returned with the transport info.
6. **`server.py`: the text the agent reads.**
   - Add `as_other: bool = False` and `back_to_choices: str | None = None` to
     `aitask_question_resume`.
     - **`back_to_choices` is the explicit id of the question to withdraw Other
       from** (review finding 7). It is never derived from "the first pending
       question" and never from `question_id`, which keeps its present meaning:
       an answer is present, paired with `prompt_answer`. So a withdrawal alone
       (`back_to_choices="q3"`, no `question_id`) is valid and just re-presents the
       restored form. A withdrawal plus an answer must name the same question in
       both, or the call is refused before anything is written.
     - A stale id (a question already answered, or not the current pending one) is
       refused by `store.back_to_choices`, so a delayed withdrawal for q1 can never
       clear q2's marker.
     - The resume calls `store.back_to_choices` first. A `QuestionError` is
       returned as `outcome: "invalid_request"` with its reason, and the state is
       unchanged. Then the usual optional `prompt_answer` submit and `present()`
       run.
     - Pass `as_other` through to `submit`.
   - Docstrings:
     - `allow_other` shape (choice only) on `aitask_question_ask`;
     - on resume: pass `as_other=true` only when the user's message gives their own
       answer for an `allow_other` choice (or answers a `pending_part:
       other_text`). A clarification or question is not one. Use
       `back_to_choices="<that question's id>"` only when the user says they
       want a listed option instead of Other. Echo "Recorded: Other — <text>" and any note.
   - Append one sentence to `INSTRUCTIONS` **after** the pinned first 512
     characters.
7. **Docs.**
   - `.agents/skills/codex_tool_mapping.md`: replace the "Other" bullet with
     `allow_other: true`, the `as_other` route, the note, and `pending_part`.
   - `aidocs/codeagents/codex_questions.md`:
     - the question shape and the form shape;
     - the marker and `back_to_choices` (earlier answers survive);
     - the record fields (`other_text`, `note`, `match: as_other`);
     - Other never approves, and a note never blocks an approval;
     - `other_text_missing`.
   - `aidocs/codeagents/codex_questions_prototype.md`: a dated (2026-11-25)
     agent-driven live-run section with the step-1 evidence (protocol, capability,
     both replies, rendering).
   - Grep `website/content` for a description of the question shape. Update it
     only if one exists.
8. **Tests.**
   - **`tests/test_aitask_questions.py` (store level):**
     - checks: `allow_other` on text or multi is refused; a non-bool is refused; a
       reserved `other` id or label is refused;
     - digest: toggling `allow_other` changes the digest (reusing the opening is
       refused, a new opening opens a new occurrence);
     - unmarked chat text matching no option, and "What changed?", stay pending
       with no receipt, with and without `allow_other`;
     - `as_other=true` records Other with the exact text, including text equal to a
       listed label; `as_other` without `allow_other` is refused; a bare "Other" is
       refused naming `as_other`;
     - "others" and "oth" are never fuzzy-captured as Other; listed exact,
       normalized and fuzzy matches still work;
     - form: Other + text is stored; Other blank → marker plus
       `other_text_requested`, no answer; with the marker, an unmarked chat "Approve"
       is refused and a marked one stores Other; a listed option + text stores a
       note;
     - duplicate vs conflict for `other_text` and `note`;
     - `approval._approving` is false for Other.
   - **`tests/test_aitask_questions_mcp.py` (process level):**
     - the callback asserts the two-field schema (`required == ["answer"]`); a
       plain choice keeps the one-field schema;
     - the optional field omitted → accepted; `""` with a listed option → accepted
       with no note;
     - Other + text stores both parts; a listed option + text stores a note;
     - an unknown extra property is still refused;
     - unmarked "What changed?" through resume → `invalid_prompt_answer`, pending,
       `receipt is None`;
     - **blank-Other recovery** on a question whose first choice has id `approve`,
       label "Approve":
       - form `{"answer": "other"}` → `awaiting-chat-answer`,
         `transport_outcome == "other_text_missing"`, `pending_part == "other_text"`;
       - resume, unmarked, "Approve" → refused, no receipt;
       - resume with no answer → the callback receives the **text-only** schema;
         answering it records Other.
       - A second variant answers marked `as_other` "Approve" instead → value
         `other`, receipt issued, `approval._approving` false.
     - **back out on the third question:** answer q1 and q2 by form; q3 (an
       `allow_other` choice) gets Other blank → marker. Resume with
       `back_to_choices="q3"` and no `question_id` → the callback receives the **full** two-field choice
       schema again; it picks a listed option. The occurrence id is unchanged; q1
       and q2 answers are byte-identical to before; `state == "complete"` with one
       receipt. `back_to_choices` with no marker → `invalid_request`, state
       unchanged. `back_to_choices="q3"` with `question_id="q2"` → refused, nothing
       written.
     - **stale withdrawal id:** q1 and q2 are both `allow_other`. q1 gets Other
       blank → marker. A text-only answer records Other for q1. q2 gets Other
       blank → marker. A delayed `back_to_choices="q1"` → `invalid_request`; q2's
       marker and `pending_part == "other_text"` are intact; q1's answer is
       unchanged; the next form is still q2's text-only form.
     - **back-out retires the live attempt (store level):** `begin()` the
       text-only attempt A; call `back_to_choices`; `submit(mcp_form, attempt A,
       other + text)` → `stale_attempt`, no answer, marker still cleared; `begin()`
       again → `started` (not `busy`) with part `choice`.
     - **back-out never reopens a closed occurrence (store level):** set the
       marker, then (a) `cancel()`, and (b) open a newer occurrence of the same
       checkpoint with a new opening, which retires the old one (`invalidated`).
       In each case `back_to_choices` on the old session raises, the state is still
       `cancelled` / `invalidated`, the marker is unchanged, `begin()` starts no
       attempt, a following form or chat `submit` records nothing, and `receipt is
       None`. The process level checks the same for (a) through
       `aitask_question_resume(back_to_choices="q1")` → `invalid_request`.
     - **text bound:** a text-only recovery reply of 20001 characters →
       `invalid_form_response`, question pending, marker kept, no receipt. A
       20000-character reply is accepted. The same bound applies to the two-field
       `other_text`, a note and an `as_other` chat reply.
     - **multi-select unaffected:** the existing native multi-select process test
       (`test_paginated_native_and_text_recovery_across_processes`), including its
       explicit empty `selected: []` page, stays green unchanged. A new case
       resumes a native multi-select with valid JSON plus `as_other=true` →
       `invalid_prompt_answer`, the stored `selections` and `receipt` are the same
       as before.
9. **Optional end-to-end live confirmation** with the real server through the same
   tmux method. Record it in the prototype doc next to step 1.

## Verification
- `python3 -m pytest tests/test_aitask_questions.py tests/test_aitask_questions_mcp.py tests/test_aitask_questions_selection.py -q`,
  with a check that the mcp module does not skip.
- `bash tests/test_codex_entrypoints_tool_mapping.sh`
- `bash tests/test_agent_instructions.sh`
- The existing `test_malformed_form_content_never_answers` and the false
  accept/refuse table stay green.
- The step-1 pass condition is recorded verbatim in the prototype doc.

## Step 9
Post-implementation: review, commit (`feature: … (t2329)`), then archival and merge
per task-workflow Step 9. No port to other agents is needed: OpenCode and Claude
already have a native Other.

## Risk

### Code-health risk: medium
- `present()`'s exact-key check and `validate_answer` are the consent path for every Codex question. Loosening the key check to subset/required could let a malformed reply answer a question · severity: medium · → mitigation: none (covered by the step-8 refusal tests and the unchanged malformed-content test)
- New per-occurrence state (the `other_requested` marker plus a text-only form part, cleared by acceptance or `back_to_choices`) adds an ordering surface: a stale form, a defer or a duplicate around the marker · severity: medium · → mitigation: none (stale-attempt check before the marker write; `back_to_choices` takes an explicit question id that must be the current pending one; process tests for recovery and back-out)
- The shared `present()` reply check serves choice, text and native multi-select forms. A rule tuned for the new choice form could refuse valid replies of another kind · severity: medium · → mitigation: none (no blanket value rule; native multi-select process test kept unchanged; `as_other` and `text` refused before the multi dispatch)

### Goal-achievement risk: low
- Codex's handling of an optional second form field (can it be skipped, and is the blank left out or sent as `""`) is known only from reading the Codex source, not from a live run. If it cannot be skipped, the two-field design fails · severity: low (residual — addressed by inline pre-phase live_optional_field_probe, whose pass condition now also requires the 2025-06-18 form handshake and stops before any code is written on failure) · → mitigation: inline pre-phase live_optional_field_probe
- Requiring an explicit `as_other` means a model that forgets it gets a refusal and has to ask again, instead of a silent record · severity: low (accepted: it fails safe) · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: live_optional_field_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: Codex optional-field behaviour unverified | desc: Live tmux-driven Codex 0.172.0 check of a required-choice + optional-text form with a scratch MCP server, passing only on the 2025-06-18 form handshake plus both reply checks, before any product code changes
