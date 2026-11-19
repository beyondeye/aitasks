---
Task: t2330_codex_questions_tolerant_prompt_answer_matching.md
Base branch: main
Output branch: main
---

# t2330 — Tolerant prompt-answer matching for attended Codex questions

## Context

When an attended Codex question times out, the user answers at the chat prompt
and Codex forwards the text via `aitask_question_resume(prompt_answer=…)`.
`validate_answer()` (`.aitask-scripts/aitask_questions/store.py:101-114`)
accepts a choice only when `value.strip()` equals an option id or label
byte-for-byte, so `start implementation` is refused for the label
`Start implementation`. The agent also paraphrases labels when it lists the
choices (the mapping never says to quote them), and the refusal reason does not
list the accepted forms, so the user is told to retype. Goal: accept
case/spacing variants and unambiguous partial/typo answers on the chat-answer
path only, keep refusals safe (negation, qualifiers, changed action words,
ambiguity), name the choices on refusal, echo what was recorded, and tell the
agent to quote labels verbatim.

Files are all clean in the tree (re-check `git status` on `codex_questions.md`
before editing it — t2324 had touched it). `allow_other` (t2329) has not
landed, so there is no Other branch to order against; t2329 already holds a
note to reconcile when it lands second.

## Decisions (pinned)

- **Scope:** only `source == "codex_prompt_model_forwarded"` on `choice`
  questions. `mcp_form` keeps exact-id matching; `text` and `multi` questions
  are unchanged (multi already parses its own JSON).
- **Normalization** (`_normalize`): strip outer whitespace; repeatedly strip
  surrounding quotes/backticks (`"'` plus curly quotes) and trailing `.` `!`
  `,`; casefold; `_` and `-` → space; collapse whitespace. `?` is **not**
  stripped (a question is not an answer).
- **Step 1 – exact, then normalized — a unique literal match wins.** Options
  whose id or label equals `value.strip()`: exactly one → accept, `match:
  "exact"`; ≥2 → refused as ambiguous. Only when there is **no** literal match:
  options whose normalized id or label equals the normalized reply: exactly
  one → accept, `match: "normalized"`; ≥2 → refused as ambiguous. Chosen
  because the literal tier is exactly what is accepted today, so nothing that
  works now stops working; a normalization collision only refuses replies
  that need normalizing. Example (distinct ids `merge_main` / `merge-main`):
  `merge_main` → `merge_main` (exact), `merge-main` → `merge-main` (exact),
  `MERGE MAIN` and `merge main` → refused, reason naming both. So `revise` /
  `approve_start` / `blue` are `exact`; `REVISE`, `approve start`, `BLUE`,
  `start implementation` are `normalized`.
- **Step 2 – fuzzy, word-aligned** (only when step 1 found nothing). No
  whole-string similarity anywhere — every fuzzy path is word-by-word, so an
  added qualifier or a changed action word can never be absorbed into a high
  overall score (`stop implementation`, `undelete branch`, `maybe delete
  branch`, `delete branch later` all scored ≥ 0.81 under a whole-string ratio).
  - **Skipped** (refused) when the reply contains `?`, or a negation/hedge word
    (`not no never without instead but or nor except unless neither maybe
    later dont cant wont` and any word ending `n't` / `n’t`).
  - **Fuzzy runs against labels only** — the text the user was shown. Ids
    take part only in the exact and normalized tiers, where a normalized id
    is the same token as the literal id up to case and `_`/`-`/space (so
    `approve start`, `REVISE`, `DELETE` work exactly as the literal id does
    today). A fuzzy id match would let a prefix of an id bypass a conflicting
    label: with `delete`/"Do not delete branch", `del` would prefix-match the
    id and record the negative option. A misleading id itself is the asking
    agent's error, the limit `codex_questions.md` already records for the
    `approve` prefix ("catches an honest mix-up, not a model that mislabels
    its own options").
  - The label is normalized and split into words. The reply matches it when
    the reply's words map **in order**, one-to-one, onto the label's words
    such that:
    - **every reply word maps** — a reply never has more words than the form
      (no added qualifiers: `delete branch later`, `maybe delete branch`);
    - **every form word maps, except pure filler** —
      `FILLER = {a, an, the, and, to, of}` may be omitted, nothing else.
      Content words that decide the action can never be skipped: `approve
      and` / `approve here` do not match "Approve and stop here" (`stop`
      missing), `do delete branch` does not match "Do not delete branch"
      (`not` missing). Negations, `here`, `now` and every other word are
      content. This also makes the first mapped words the action words, so
      `stop implementation` cannot reach "Start implementation";
    - a reply word maps to a form word when it **equals** it, is a **prefix**
      of it of ≥ `MIN_PREFIX = 3` characters, or is a **typo** of it: same
      first character, and optimal-string-alignment distance (insert / delete
      / substitute / adjacent transposition) ≤ the budget for the shorter of
      the two words — `TYPO_BUDGET = ((8, 2), (4, 1))` (≥ 8 chars: 2 edits,
      ≥ 4 chars: 1, shorter: 0).
  - An option matches when its label matches. **Exactly one** matching
    option → accept, `match: "fuzzy"`, `via: "prefix"` (no typo used) or
    `"typo"`, `edits: <total edits>`. ≥2 → refused as ambiguous; 0 → refused
    as unknown. (The task's "minimum score + margin" is replaced by this
    discrete rule, because the counterexamples above passed any ratio
    threshold that still accepted ordinary typos; `edits` is recorded in place
    of a score.)
  - Measured with a prototype of exactly this rule: accepted — `start impl`,
    `approve stop here` (prefix, 0 edits), `strat implementaion` (2 edits),
    `delte branch`, `abrot task`, `reviese plan` (1 each), `del branch`;
    refused — `approve and`, `approve here`, `approve and stop` (`here` is
    content), `approve`, `start`, `rev`, `abrot` (`task` missing), `stop
    implementation`, `undelete branch`, `maybe delete branch`, `delete branch
    later`, `apprvoe`, `kep`, `de`, `branch`; against "Do not delete branch"
    (id `delete`): `del`, `dele`, `do delete branch`, `delete branch`.
- **Refusal reason** keeps the "question remains pending" wording and appends
  the choices: `unknown choice; question remains pending; answer with one of:
  "Start implementation", "Revise plan", …` or `ambiguous choice (matches
  "Start implementation" and "Approve and stop here"); question remains
  pending; answer with one of: …`. Labels JSON-quoted; list capped at 20 with
  `… and N more`.
- **Answer record** for a choice gains `label` and `match` (plus `via` /
  `edits` for fuzzy). `value` stays the option **id**, so
  `approval._approving` (the `approve`-prefix check) and every consumer are
  unaffected; `raw` keeps the user's text.
- **Receipt/digest:** the receipt binding is `digest(id, spec_digest,
  manifest, target)` — answers (value, raw, source) are not in it today and are
  immutable once accepted. `match` is provenance like `source`; it is **not**
  added to the binding. Written down in `codex_questions.md`.
- **Resume result:** on `accepted`/`duplicate` for a choice,
  `aitask_question_resume` adds `resolved: {question_id, id, label, match[,
  via, edits]}` to whatever `present()` returns. The store builds it from the
  question's options and the stored id (label looked up, `match` defaulting
  to `exact` for pre-change records), so it does not depend on the record
  shape.
- `INSTRUCTIONS` is left unchanged (it already says "their exact text"; the
  512-char head stays pinned).

## Implementation steps

1. **`store.py`** — constants `MIN_PREFIX`, `TYPO_BUDGET`, `HEDGE_WORDS`.
   Add `_normalize(text)`, `_osa(a, b)` (optimal string alignment distance),
   `_word_match(reply_word, form_word) -> edits | None`,
   `_align(reply_words, form_words) -> edits | None` (in-order one-to-one
   mapping, only `FILLER` form words skippable, minimal total edits — a
   memoized DP over (reply index, form index)), constant `FILLER`, `_choices_reason(kind, options, candidates)`, and
   `match_choice(options, value) -> (option, provenance)`. Rewrite
   `validate_answer` to return `(answer, provenance)`: text → `(value, {})`;
   form → exact id, `{"match": "exact", "label": …}`; prompt →
   `match_choice`. Refusals raise `QuestionError(reason)`. Replace the comment
   with the new rule (exact/normalized, word-aligned fuzzy, never prose /
   qualifiers / negation / ambiguity; the id is what is stored).
2. **`store.py` `Store.submit`** — unpack `(answer, provenance)`; store
   `{"value": answer, "raw": value, "source": source, **provenance}`.
   Duplicate/conflict comparison stays on `value`. For a `choice` question,
   both the `accepted` and the `duplicate` view carry `resolved`, built by a
   helper `_resolved(question, record)` from the **question's options** and
   the stored id — `{question_id, id, label: <option label for that id>,
   match: record.get("match", "exact")[, via, edits]}` — never from a `label`
   field in the record. So a record saved before this change (`value`, `raw`,
   `source` only), retried after its response was lost, still gets the
   confirmation, with `match: "exact"`: the only thing the old validator
   accepted was a literal id/label. The legacy record is read, not rewritten.
3. **`server.py` `aitask_question_resume`** — keep `result.get("resolved")`
   from the submit and return `{**(await present(...)), "resolved": …}` when
   it is set.
   Docstring: pass the user's text unchanged; the server accepts an option's
   id or label in any case/spacing, or the label typed word by word with each
   word abbreviated (≥ 3 letters) or slightly mistyped, as long as every word
   but a/an/the/and/to/of is there in order; it refuses negations, questions,
   added or missing words and ambiguity; `resolved` names the option recorded — echo it ("Recorded:
   <label>"); `invalid_prompt_answer.reason` lists the labels to re-ask with.
4. **`.agents/skills/codex_tool_mapping.md`** timeout steps — step 2: name
   each choice by quoting its label verbatim (still plain sentences, no
   numbered menu) and tell the user they can type a label in any case, and
   may shorten or slightly mistype each of its words as long as every word is
   there in order (small joining words like "and" or "the" may be left out) —
   e.g. `start impl` for "Start implementation", `approve stop here` for
   "Approve and stop here". Do not suggest dropping a word or answering with
   a single first word. Step 4: forward the user's exact text unchanged —
   never rewrite it into a label; the server matches. On `invalid_prompt_answer`, re-ask using
   the labels its `reason` lists. Step 5: when the result carries `resolved`,
   tell the user which option was recorded.
5. **`aidocs/codeagents/codex_questions.md`** — replace the line-137 sentence
   ("A choice answer must match one option id or label exactly; prose is not
   parsed.") with the rule: unique literal match first, then normalized (a
   collision refuses), word-aligned fuzzy match against labels only (no added
   words, only filler omitted, prefix ≥ 3, same-first-letter typo budget), refusal cases, stored `value` is the option id (so the
   `approve`-prefix check is unaffected), `match` recorded as provenance and
   not in the receipt binding, `resolved` echoed. Keep the edit to that one
   paragraph (current-state prose only).
6. **Tests — `tests/test_aitask_questions.py`**: a `ChoiceMatchTests` class
   over the t2323 option set (`approve_start`/"Start implementation",
   `revise`/"Revise plan", `approve_stop`/"Approve and stop here",
   `abort`/"Abort task") calling `match_choice` directly and through
   `Store.submit`:
   - exact: `approve_start`, `Start implementation`, `revise`.
   - normalized → `approve_start`: `start implementation`, `START
     IMPLEMENTATION`, `  Start   implementation. `, `"Start implementation"`,
     `approve start`; `REVISE` → `revise`; `approve stop` → `approve_stop`.
   - fuzzy: `start impl` → `approve_start` (prefix), `approve stop here` →
     `approve_stop` (prefix, `and` omitted as filler), `strat implementaion`
     → `approve_start` (typo, `edits == 2`).
   - refused: `approve` (reason lists "Start implementation" and "Approve and
     stop here"), `approve and`, `approve here`, `don't start
     implementation`, `do not start implementation`, `not now`, `no`, `start
     implementation?`, `st`, `stop implementation`, a long prose reply
     containing a label, `start or revise`.
   - `no` accepted only when an option is literally `no`/"No".
   - precedence: options `merge_main`/"Merge main" and `merge-main`/"Merge
     main now" — `merge_main` and `merge-main` accepted (exact) as themselves,
     `MERGE MAIN` and `merge main` refused as ambiguous with both named.
   - two options whose labels differ only in case (`Go`/`go`) — each literal
     accepted, `GO` refused as ambiguous.
   - ids are never fuzzy: `rev` and `approve sta` refused; with
     `delete`/"Do not delete branch" + `keep`/"Keep branch", `del` and
     `dele` refused, while `delete` (exact) and `DELETE` (normalized id) are
     accepted as `delete` — pinned, with a comment citing the
     asking-agent-owns-ids limit.
   - `mcp_form` still needs the exact id (`Start implementation` refused).
   - answer record carries `match`, `label`, `raw`; `value` is the id.
   - `resolved` on accepted and on duplicate; **legacy record**: submit,
     then strip the record to `{value, raw, source}` through `store.edit()`,
     resubmit the same answer → `duplicate` with `resolved == {question_id,
     id, label from the options, match: "exact"}`, and the stored record is
     still exactly `{value, raw, source}`.
   - a `plan_approved` occurrence (task file `aitasks/t42_x.md` in the temp
     project, plan bound) answered `start impl` passes
     `approval._eligible(store, 42, "plan_approved", sid)` (reason `""`).
   - existing `test_bad_or_unrelated_choices…` keeps passing unchanged
     (`Please choose Blue`, `blue or green`, `status?` still refused).
7. **Tests — `tests/test_aitask_questions_mcp.py`**: resume with
   `prompt_answer: "BLUE"` → `resolved == {"question_id": "q1", "id": "blue",
   "label": "Blue", "match": "normalized"}`; the existing bad prompt test also
   asserts the reason lists `"Blue"` and `"Green"`.

### Post-phase (risk mitigations)

1. [false_accept_table] In `tests/test_aitask_questions.py`, add
   `test_false_accept_and_false_refuse_table`: three option sets — the t2323
   set, a destructive pair (`delete`/"Delete branch", `keep`/"Keep branch"),
   and a negative-label pair (`delete`/"Do not delete branch", `keep`/"Keep
   branch"). A `REFUSED` table of ~30 replies that `match_choice` must refuse,
   including the counterexamples that defeated a whole-string ratio (`stop
   implementation`, `undelete branch`, `maybe delete branch`, `delete branch
   later`) and those that defeated free word skipping (`approve and`,
   `approve here`, `approve and stop`, and `do delete branch` / `delete
   branch` / `not delete` / `del` / `dele` against the negative-label pair —
   the last two being the fuzzy-id bypass); plus `rev`, `abrot`, `don't delete`, `do NOT delete the branch`, `never delete`,
   `delete?`, `de`, `branch`, `please delete the branch now`, `delete or
   keep`, `abort?`, `ab`, `task`, `I don't want to start implementation`,
   `start and abort`, `approve`, `apprvoe` (ambiguous across both approve
   options), `unapprove`, `disapprove`, `kep`. An `ACCEPTED` table of ~12
   ordinary replies with their expected id and `match`: `delete`, `Delete
   branch.`, `keep`, `del branch`, `delte branch`, `Revise`, `revise plan`,
   `abort task`, `abrot task`, `approve stop here`, `Start implementation!`,
   `reviese plan`, and `do not delete branch` (normalized) against the
   negative-label pair. Run each row with `subTest`, so a rule change shows every
   row it flips. Expected values are measured against the real function while
   writing the test and pinned — a row that disagrees with intent is a rule
   fix, not a table edit.

## Verification

- `~/.aitasks/venv/bin/python -m pytest tests/test_aitask_questions.py
  tests/test_aitask_questions_mcp.py tests/test_aitask_questions_selection.py -q`
- `bash tests/test_gate_codex_approvals.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests` (last line verdict).
- `./.aitask-scripts/aitask_skill_verify.sh` (mapping file is under
  `.agents/skills/`).

## Step 9 (Post-Implementation)

Current-branch mode: commit code (`bug: … (t2330)`) and plan separately,
then archive with `./.aitask-scripts/aitask_archive.sh 2330`.

## Risk

### Code-health risk: low
- Change is contained to `validate_answer` and its one call site, the resume
  result, and docs; the stored `value` contract (option id) is unchanged, so
  approval/gate consumers are unaffected · severity: low · → mitigation: none

### Goal-achievement risk: low
- Fuzzy acceptance is consent from heuristic evidence: a reply could be
  accepted as an option the user did not mean (a short prefix or typo landing
  on a destructive option like `abort`, or a hedge word not in the list), or
  the rules could refuse ordinary answers and leave the original pickiness in
  place · severity: low (residual — addressed by inline post-phase
  false_accept_table and by the word-aligned rule replacing whole-string
  similarity) · → mitigation: inline post-phase false_accept_table

### Planned mitigations
- timing: post-phase | name: false_accept_table | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement (false accept / false refuse of fuzzy matching) | desc: Pinned table-driven test of refused near-misses and accepted ordinary replies over the t2323 and a destructive option set

## Post-Review Changes

### Change Request 1 (2026-11-19 09:40)
- **Requested by user:** four verified findings against the first implementation —
  (1) only ASCII `?` was treated as a question, so `start implementation？`
  (U+FF1F) was accepted by a one-edit typo; (2) a punctuation-only reply (`!`)
  normalized to "" and fuzzy-matched the label "A" (all filler); (3) the typo
  path ran the quadratic `_osa` for word pairs whose length difference already
  exceeded the budget — a long paste stalled the submit write transaction;
  (4) refusal reasons repeated colliding labels without the id that resolves
  them, and the candidate clause was uncapped.
- **Changes made:** `QUESTION_MARKS` (`? ？ ¿ ؟ ⸮`) in `_hedged`; an empty
  normalized reply is refused after the literal tier (so an option written
  `!` still matches exactly) and `_align` returns None for an empty reply or a
  reply with more words than the label; `_word_match` skips edit distance when
  the length difference exceeds the budget, and `_osa(a, b, limit)` is now a
  banded DP (cells within `limit` of the diagonal, early exit) — linear in word
  length; worst case at the input limits (500 options, 200-char words) 0.22 s.
  `_choice_names` names a label with its exact id when another label normalizes
  alike, and caps both the candidate and the choices lists at 20 with
  "… and N more". Doc paragraph updated to match.
- **Tests added:** refusal-table rows for `？`, `¿`, `؟` and punctuation-only
  replies; punctuation-only literal option; a long-paste test asserting
  lopsided words never reach `_osa` and equal-length ones run only with the
  budget as limit; a banded-vs-full OSA property test (seeded, limits 0–3);
  reason naming/capping test with 25 colliding "Same" labels.
- **Files affected:** `.aitask-scripts/aitask_questions/store.py`,
  `tests/test_aitask_questions.py`, `aidocs/codeagents/codex_questions.md`.

### Change Request 2 (2026-11-19 10:10)
- **Requested by user:** (1) `?`-list guard still missed U+2047 `⁇` and U+203D
  `‽`; `start implementation⁇` completed as `approve_start` by a one-edit typo
  with a receipt. (2) The reason formatter compared labels only with labels:
  with `first`/"Stop" and `Stop`/"Continue", typing "Stop" was ambiguous and
  the reason offered "Stop" again instead of the usable id `first`.
- **Changes made:** the fixed `QUESTION_MARKS` list is gone — `_hedged` now
  refuses fuzzy matching for any reply holding a Unicode punctuation or symbol
  character (category P* / S*) after normalization, so no mark can be deleted
  by a typo edit. `_choice_names` counts every option's id and label as
  literal forms: a label typed by more than one option is shown with this
  option's id when the id is unique, else "(cannot be typed unambiguously)".
- **Tests added:** a sweep over every P*/S* code point appended to a label
  (never a fuzzy match; fails under the old fixed list — mutant checked); `⁇`,
  `‽`, `？`, `?` through `Store.submit` leave no answer and no receipt; reason
  naming for crossed id/label, swapped (unreachable) and case-only labels.
- **Files affected:** `store.py`, `tests/test_aitask_questions.py`,
  `aidocs/codeagents/codex_questions.md`.

### Change Request 3 (2026-11-19 10:40)
- **Requested by user:** (1) the reason builder predicted replies with its own
  collision count, not the submission rule: with `first`/" Stop " and
  `Stop`/"Continue" it offered " Stop ", which submission strips to "Stop" and
  records Continue. (2) The mapping and the resume docstring still told the
  agent to re-ask with labels, not the alternate replies.
- **Changes made:** the matching rule moved into a non-raising
  `_resolve(options, value)`; `match_choice` wraps it, and `_choice_names`
  offers a reply only when `_resolve` on that exact reply returns the intended
  option — label alone, else `(reply "<id>")`, else "(no typed reply selects
  it; show the form again)". Mapping step 4, the resume docstring and the
  aidoc now say to relay those replies verbatim and to resume with no answer
  (re-present the form) when no typed reply works.
- **Tests added:** padded-label regression; a helper that submits every
  suggested reply through `Store.submit` and checks it records its own choice
  (crossed, padded, case-only and the t2323 set). The previous count-based
  namer fails the test (mutant checked).
- **Files affected:** `store.py`, `server.py`, `codex_tool_mapping.md`,
  `codex_questions.md`, `tests/test_aitask_questions.py`.

## Final Implementation Notes
- **Actual work done:** `aitask_questions/store.py` gained the prompt-answer
  matcher: `_resolve(options, value)` (the non-raising rule: exact → normalized
  → word-aligned fuzzy on labels only), `match_choice` (raises with a reason
  that names, per choice, a reply verified by `_resolve` to select it),
  `_normalize`, banded `_osa(a, b, limit)`, `_word_match`, `_align` (in-order,
  one-to-one, only `FILLER` omittable), `_hedged` (any Unicode P*/S* char,
  negation/hedge words), `_choice_names`, and `resolved(question, record)`.
  `validate_answer` returns `(id, provenance)`; `Store.submit` stores `label`,
  `match` (+`via`/`edits`) and returns `resolved` on accepted and duplicate
  (legacy records resolve as `exact`, unrewritten). `server.py` passes
  `resolved` through `aitask_question_resume`; docstring, the Codex mapping
  (timeout steps 2/4/5) and `codex_questions.md` describe the rule.
- **Deviations from plan:** the task's "min score + margin" ratio design was
  dropped during plan review — every whole-string ratio threshold that kept
  ordinary typos also accepted `stop implementation`, `undelete branch`,
  `delete branch later`. Replaced by the discrete word-aligned rule, recording
  `edits` instead of a score. Fuzzy also runs on labels only (an id prefix
  could bypass a conflicting label), and no form word but `a an the and to of`
  may be omitted. Post-review rounds added: any punctuation/symbol disables
  fuzzy (not a question-mark list), empty normalized replies are refused,
  `_osa` is banded and skipped for impossible length differences (a long paste
  held the submit write transaction for seconds), reasons are capped at 20 and
  suggest only replies the submission matcher confirms.
- **Issues encountered:** each review round found a concrete false accept or
  wrong suggestion in the previous rule; all are pinned as rows in the
  `false_accept_table` test or dedicated tests, each with a mutant check
  showing the test fails on the prior behaviour. One full-suite run failed on
  `test_sitrep_tui_actions.py::RestoreTests::test_pre_fix_control_…`, which
  passed twice in isolation and is unrelated (load flake); the final full
  suite passed.
- **Key decisions:** a unique literal match always wins (nothing accepted
  before stops working); normalization collisions refuse; `match` is
  provenance outside the receipt binding (answers never were in it); the
  stored `value` stays the option id, so `approval._approving` is unaffected
  (tested through `approval._eligible`). INSTRUCTIONS unchanged (512-char head
  still pinned).
- **Upstream defects identified:** None
