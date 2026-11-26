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

### Live evidence (pre-phase, done 2026-11-25, Codex 0.172.0, gpt-6.2-sol)

Probe: a scratch MCP server driven through a private tmux server
(`tmux -L t2329probe`), registered with `-c` overrides only.

**Round 1 — page 2 as an optional text field: failed.**
- The handshake was `2025-06-18` with elicitation `{"form": {}, "url": {}}`.
- Codex renders the two pages as "Field 1/2" then "Field 2/2".
- An optional text field left **blank cannot be submitted**: Enter, space+Enter,
  `^n` (it wraps to field 1) and Tab all left the form open.
- With text typed, Enter submitted `{"answer":"blue","other_text":"x"}`.
- Other + text worked: `{"answer":"other","other_text":"Teal, please"}`.
- So the optional-field design is out.

**Round 2 — the user's design, page 2 required: all three runs passed.** Page 2
is titled "Notes or your own answer", and its description reads "If you picked a
listed option, enter a note or type none to continue. If you picked Other, enter
your own answer."

| Run | Reply |
|---|---|
| C1: Blue + `none` | `accept`, `{"answer":"blue","detail":"none"}` |
| C2: Green + note | `accept`, `{"answer":"green","detail":"use the darker shade"}` |
| C3: Other + own answer | `accept`, `{"answer":"other","detail":"Teal, please"}` |

All three ran on `2025-06-18` with `form` elicitation. Codex rendered page 2 as
"Field 2/2 (1 required unanswered)" with the description shown and a
`› Type your answer` box.

### Decisions

- **Two-page form, choice first (user decision).** Page 1 is the choice and lists
  the server-added **Other**. Page 2 is a **required** string property `detail`
  (`minLength` 1, `maxLength` 20000) carrying the round-2 title and description.
  - **Listed option:** a `detail` of `none` (after `strip()` and `casefold()`)
    means no note. Any other text is stored verbatim as `note`.
  - **Other:** `detail` is stored verbatim as the answer `other_text`. A literal
    `none` is kept as the answer.
- **Server-added Other.** The fixed id is `other` and the label `Other`. A caller
  option whose normalised id or label is `other` is refused.
- **A note never blocks an approval.** An `approve…` id plus a note still approves,
  as the user decided earlier. The note goes back in `resolved` and the agent
  must relay it. **Other never approves**, because its id does not start with
  `approve`.
- **Other intent is never lost.** This is the recovery safeguard for clients
  that, unlike Codex, let a blank or whitespace `detail` through.
  - An Other answer whose `detail` is blank sets an `other_requested` marker. The
    next form is text-only ("Your own answer"). An unmarked chat reply is refused,
    even one that equals a listed approving label.
  - `aitask_question_resume(back_to_choices="<question id>")` withdraws the marker
    for exactly that question, inside the same occurrence. Earlier answers
    survive.
- **Explicit free-text route in chat; no silent fall-through.**
  - `aitask_question_resume(as_other=true)` records chat text as Other: the exact
    text, no option matching.
  - Unmarked text that matches no option is refused exactly as today. So a
    forwarded clarification ("What changed?") never becomes an answer.
  - A bare unmarked "Other" is refused, with a reason naming `as_other`.
  - In the t2330 matcher (notes acknowledged), the server-added Other is matched
    only in the exact and normalized tiers, never fuzzy. `"ambiguous choice"`
    stays a refusal.

## Implementation

### Pre-phase (risk mitigations)
1. [live_optional_field_probe] **Done.** See "Live evidence" above. The round-2
   pass conditions all hold: (a) the `2025-06-18` form handshake; (b) a listed
   choice + `none`; (c) a listed choice + a real note; (d) Other + a custom answer.
   The scratch probe and its logs stay in the session scratchpad. The evidence is
   copied into the prototype doc in step 7.

### Main steps
2. **`store.py`: question checks.**
   - Add `"allow_other"` to the allowed question fields. It must be a `bool`, and
     it is allowed only on `kind: "choice"`.
   - When true, refuse an option whose `_normalize(id)` or `_normalize(label)` is
     `other` (reserved).
   - Add the constants `OTHER_ID`, `OTHER_LABEL`, `OTHER_DESCRIPTION`,
     `DETAIL_FIELD = "detail"`, `NO_NOTE = "none"` and `TEXT_LIMIT = 20000`.
   - Add `choice_options(question)`: the options, with Other appended when the
     flag is set.
   - The stored questions stay exactly as the caller sent them, so `spec_digest`
     changes when `allow_other` changes: reusing an opening refuses, and a new
     opening opens a new occurrence.
3. **`store.py`: answer validation.** `validate_answer(question, value, source,
   text=None, as_other=False, part="choice")`.
   - **One text bound.** Every stored user text (`other_text`, `note`, and the
     `as_other` chat text) goes through `_user_text(text, name)`. The text must
     be non-blank after `strip()` and at most `TEXT_LIMIT` characters, or it
     raises `QuestionError`. The stored value is the text as typed.
   - **form, part `choice`.** The exact id must be in `choice_options`. A `text`
     given on a question without `allow_other` is refused.
     - **Other:** a stripped-blank `text` raises `OtherTextMissing(QuestionError)`
       (in `errors.py`). Otherwise store `other_text = text`, with `"none"`
       accepted literally.
     - **Listed option:** a blank `text`, or one whose `text.strip().casefold() ==
       "none"`, means no note. Otherwise check the bound and store `note = text`.
   - **form, part `other_text`** (the text-only recovery form). `value` must be
     `OTHER_ID`, and `text` passes `_user_text` (`none` is literal). Store
     `other_text = text`.
   - **chat (`codex_prompt_model_forwarded`).**
     - `as_other=true` → refused unless `allow_other`. Otherwise `value` goes
       through `_user_text` and is recorded as `OTHER_ID` with
       `other_text = value` and `match: "as_other"`. No option matching.
     - `as_other=false` with the marker set → refused: "the user chose Other;
       resume with as_other=true and their exact text, or back_to_choices".
     - `as_other=false` otherwise → `_resolve(choice_options(q), value,
       literal_only={OTHER_ID})`. The new `literal_only` parameter keeps those ids
       out of the fuzzy tier.
       - A listed option → as today.
       - The Other option itself → refused, naming `as_other`.
       - Unknown or ambiguous → refused as today.
   - `_choice_names` and `_choices_reason` use `choice_options`. Other is named
     `"Other" (resume with as_other=true and the user's own text)`.
4. **`store.py`: state and records.**
   - **`submit(..., text=None, as_other=False)`.** Before the `multi` dispatch to
     `_submit_selection`, refuse `as_other=true` or a non-None `text` unless the
     question is a `choice` with `allow_other`. A multi-select reply carrying
     either changes neither the selection nor the receipt.
   - **Attempts know their part.** `begin()` stores `attempt["part"]`: `"choice"`,
     or `"other_text"` when the marker is set. A form `submit` validates against
     the **attempt's** part, never the current marker. A response is therefore
     judged by the form that was actually shown.
   - **On `OtherTextMissing` (form only).** Run the existing stale-attempt check
     first. Then set `body["other_requested"][qid] = {"at", "attempt"}`, clear the
     attempt, set the state to `awaiting-chat-answer`, add the event
     `other_text_missing`, and return
     `view(outcome="other_text_requested", transport_outcome="other_text_missing")`.
   - **New `Store.back_to_choices(session_id, question_id)`.** In one `edit()`
     transaction, after the `_refresh` that `edit()` runs:
     - It refuses and writes nothing unless the state is `pending`,
       `awaiting-chat-answer` or `deferred`. A cancelled, invalidated (including
       retired by a newer opening) or complete occurrence keeps its state, marker
       and receipt.
     - It also refuses unless `question_id` is the current pending question and
       carries the marker.
     - Otherwise it removes the marker and retires any active attempt
       (`attempt = None`, state `awaiting-chat-answer`, event `other_withdrawn`
       naming the attempt). With no active attempt, the open state is left as it
       is.
     - A late text-only response then gets `stale_attempt`, and `begin()` is no
       longer `busy`.
   - **Records.** The record is still `{"value", "raw", "source", **provenance}`,
     so `other_text` and `note` land in it. For a form answer, `raw` stays the id.
     The page-2 text as typed is stored as `detail_raw`, so a `none` that meant
     "no note" stays visible. Acceptance drops the question's marker.
   - **Duplicate vs conflict.** A different `other_text` for the same id is a
     `conflict`. A different `note` is a `duplicate` that keeps the original.
   - **`resolved()`** uses `choice_options` and copies `other_text` and `note`.
   - **`view()`.** Show each pending `allow_other` question with Other appended (a
     copy). Add `pending_part: "other_text"` when the first pending question
     carries the marker.
5. **`server.py`.**
   - **`form()`.** A choice with `allow_other` uses `choice_options` for the
     `answer` property, which is required.
     - Add a second required property `detail`:
       `{"type": "string", "title": "Notes or your own answer", "description":
       "If you picked a listed option, enter a note or type none to continue. If
       you picked Other, enter your own answer.", "minLength": 1, "maxLength":
       20000}`. Both strings are the ones round 2 proved live. The message adds
       the same sentence.
     - For the `other_text` part, `form()` builds the text-only form instead:
       `{"detail": {..., "title": "Your own answer", "minLength": 1, "maxLength":
       20000}}`, required, with the message "You chose Other for: <text>. Type
       your answer."
     - A plain choice keeps today's one-field schema byte for byte.
   - **`present()`.**
     - Replace `set(content) != set(properties)` with these checks: content is a
       dict, its keys are a subset of `properties`, and `required` is a subset of
       its keys.
     - There is **no blanket string-value rule**, because native multi-select
       sends an array in `selected`. Only `detail`, when present, must be a
       string. Every other value check stays where it is.
     - Choice part: submit `value=content["answer"]` with
       `text=content.get("detail")`. Text-only part: submit `value=OTHER_ID` with
       `text=content["detail"]`.
     - The `other_text_requested` outcome is returned with the transport info.
6. **`server.py`: the text the agent reads.**
   - **`aitask_question_resume` gains two parameters.**
     - `as_other: bool = False`, passed through to `submit`.
     - `back_to_choices: str | None = None`, the **explicit** id of the question
       to withdraw Other from. It is never derived from the first pending
       question, and never from `question_id`. `question_id` keeps its meaning:
       an answer is present, paired with `prompt_answer`.
       - A withdrawal alone is valid and re-presents the restored choice form.
       - A withdrawal plus an answer must name the same question, or the call is
         refused before anything is written.
       - A `QuestionError` from `back_to_choices` returns
         `outcome: "invalid_request"` with its reason.
   - **Docstrings.**
     - `aitask_question_ask`: the `allow_other` shape and the two pages.
     - `aitask_question_resume`:
       - pass `as_other=true` only when the user gives their own answer for an
         `allow_other` choice, or answers a `pending_part: other_text`; a
         clarification or a question is not one;
       - use `back_to_choices` only when the user wants a listed option instead
         of Other;
       - echo "Recorded: Other — <text>", or the listed label plus any note.
   - **`INSTRUCTIONS`.** Append one sentence after the pinned first 512
     characters.
7. **Docs.**
   - `.agents/skills/codex_tool_mapping.md`: replace the "Other" bullet with
     `allow_other: true`. Describe the two pages (`none` means no note), the
     `as_other` and `back_to_choices` routes, relaying a note, and `pending_part`.
   - `aidocs/codeagents/codex_questions.md`:
     - the question shape and the two-page form, with the exact page-2 wording;
     - the `none` rule;
     - the marker and `back_to_choices`;
     - the record fields (`other_text`, `note`, `detail_raw`, `match: as_other`);
     - Other never approves, and a note never blocks an approval;
     - `other_text_missing`.
   - `aidocs/codeagents/codex_questions_prototype.md`: a dated section ("Other
     free text — 2026-11-25, agent-driven") with both probe rounds verbatim. That
     covers the round-1 failure, the round-2 replies and the rendering.
   - Grep `website/content` for a description of the question shape. Update it
     only if one exists.
8. **Tests.**
   - **`tests/test_aitask_questions.py` (store level):**
     - **checks:** `allow_other` on text or multi is refused, a non-bool is
       refused, and a reserved `other` id or label is refused. Toggling
       `allow_other` changes the digest: reusing the opening is refused, and a new
       opening opens a new occurrence.
     - **form, listed:** `detail` of `none`, `None` or ` NONE ` stores no `note`.
       Any other `detail` stores a verbatim `note`.
     - **form, Other:** `detail` `"Teal, please"` stores `other_text`. A `detail`
       of `"none"` stores `other_text == "none"`. A blank or whitespace `detail`
       sets the marker and returns `other_text_requested`, with no answer.
     - **chat:**
       - Unmarked text matching no option, and "What changed?", stay pending with
         no receipt, with and without `allow_other`.
       - `as_other=true` records Other with the exact text, including text equal
         to a listed label. `as_other` without `allow_other` is refused, and a
         bare "Other" is refused naming `as_other`.
       - "others" and "oth" are never fuzzy-captured as Other. Listed exact,
         normalized and fuzzy matches still work.
       - With the marker set, an unmarked "Approve" is refused, and a marked one
         stores Other.
     - **duplicate vs conflict** for `other_text` and `note`.
     - **approvals:** `approval._approving` is false for Other. It stays true for
       `approve…` + note.
     - **back-out retires the live attempt:**
       - `begin()` the text-only attempt A, then call `back_to_choices`.
       - `submit(mcp_form, A, …)` → `stale_attempt`, no answer.
       - `begin()` again → `started` with part `choice`.
     - **back-out never reopens a closed occurrence:** this covers both `cancel()`
       and retirement by a newer opening. In each case `back_to_choices` raises,
       the state and marker are unchanged, `begin()` starts nothing, a later
       submit records nothing, and `receipt is None`.
     - **text bound:** 20001 characters is refused on each path (two-page
       Other, note, text-only recovery, `as_other`), leaving the question pending
       and any marker in place. 20000 characters is accepted.
   - **`tests/test_aitask_questions_mcp.py` (process level):**
     - **schema:** the callback asserts the two-page schema, including
       `required == ["answer", "detail"]`, the exact title and description, and
       `maxLength` 20000. A plain choice keeps the one-field schema.
     - **the three live cases:** C1 Blue + `none` (no note), C2 Green + note, and
       C3 Other + "Teal, please" (both parts stored, `resolved` echoes them).
     - **refusals:** a missing `detail` and an unknown extra property are each
       refused, and nothing is answered.
     - **unmarked chat:** "What changed?" through resume →
       `invalid_prompt_answer`, pending, `receipt is None`.
     - **blank-Other recovery:** the question's first choice has id `approve`.
       1. Form `{"answer":"other","detail":"   "}` → `awaiting-chat-answer`,
          `transport_outcome == "other_text_missing"`, and
          `pending_part == "other_text"`.
       2. An unmarked "Approve" is refused, with no receipt.
       3. A resume with no answer receives the text-only schema, and answering it
          records Other.
       - A variant answers with `as_other` "Approve" instead → value `other`, and
         `_approving` is false.
     - **back out on q3:**
       1. q1 and q2 are answered by form. q3 gets Other plus a blank `detail` →
          marker.
       2. `back_to_choices="q3"` alone brings back the full two-page schema, and a
          listed option is picked.
       3. Same occurrence id, q1 and q2 byte-identical, and the state is complete
          with one receipt.
       - `back_to_choices` with no marker → `invalid_request`.
       - `back_to_choices="q3"` with `question_id="q2"` → refused, and nothing is
         written.
     - **stale withdrawal id:** a delayed `back_to_choices="q1"`, sent after q1
       was answered and q2 got its marker, → `invalid_request`. q2's marker and
       `pending_part` stay intact, and the next form is q2's text-only form.
     - **cancelled occurrence:** `back_to_choices` →
       `invalid_request`, and the state stays `cancelled`.
     - **multi-select unaffected:**
       - `test_paginated_native_and_text_recovery_across_processes`, including its
         explicit empty `selected: []` page, stays green unchanged.
       - A native multi-select resumed with valid JSON plus `as_other=true` →
         `invalid_prompt_answer`, and its selections and receipt do not change.
9. **Optional end-to-end live confirmation** with the real server (C1–C3 through
   `aitask_question_ask`), using the same tmux method. Record it in the prototype
   doc next to the probe evidence.

## Verification
- `python3 -m pytest tests/test_aitask_questions.py tests/test_aitask_questions_mcp.py tests/test_aitask_questions_selection.py -q`,
  with a check that the mcp module does not skip.
- `bash tests/test_codex_entrypoints_tool_mapping.sh`
- `bash tests/test_agent_instructions.sh`
- The existing `test_malformed_form_content_never_answers` and the false
  accept/refuse table stay green.

## Step 9
Post-implementation: review, commit (`feature: … (t2329)`), then archival and merge
per task-workflow Step 9. No port to other agents is needed: OpenCode and Claude
already have a native Other.

## Risk

### Code-health risk: medium
- `present()`'s exact-key check and `validate_answer` are the consent path for every Codex question. Loosening the key check to subset/required could let a malformed reply answer a question · severity: medium · → mitigation: none (covered by the step-8 refusal tests and the unchanged malformed-content test)
- New per-occurrence state (the `other_requested` marker plus a text-only form part, cleared by acceptance or `back_to_choices`) adds an ordering surface: a stale form, a defer or a duplicate around the marker · severity: medium · → mitigation: none (stale-attempt check before the marker write; attempt-bound parts; `back_to_choices` takes an explicit question id, checks the lifecycle and retires the attempt; process tests for recovery and back-out)
- The shared `present()` reply check serves choice, text and native multi-select forms. A rule tuned for the new choice form could refuse valid replies of another kind · severity: medium · → mitigation: none (no blanket value rule; native multi-select process test kept unchanged; `as_other` and `text` refused before the multi dispatch)

### Goal-achievement risk: low
- Codex's handling of the two-page form was unverified before the pre-phase. Round 1 showed an optional blank field cannot be submitted, and the design moved to a required page 2 (`none` means no note), which round 2 proved live in all three cases · severity: low (residual — addressed by inline pre-phase live_optional_field_probe) · → mitigation: inline pre-phase live_optional_field_probe
- Every listed answer now needs a page-2 entry (`none`), one extra step per question. This is a UX cost the user chose deliberately · severity: low (accepted) · → mitigation: none
- Requiring an explicit `as_other` means a model that forgets it gets a refusal and has to ask again, instead of a silent record · severity: low (accepted: it fails safe) · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: live_optional_field_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: Codex two-page form behaviour unverified | desc: Live tmux-driven Codex 0.172.0 probe with a scratch MCP server (round 1 optional field: failed; round 2 required "Notes or your own answer" page: C1 none / C2 note / C3 Other all passed on the 2025-06-18 form handshake), before any product code changes
