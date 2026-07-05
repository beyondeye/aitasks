---
Task: t1120_1_relay_protocol_library.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_2_*.md … t1120_7_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_*_*.md
Worktree: aiwork/t1120_1_relay_protocol_library
Branch: aitask/t1120_1_relay_protocol_library
Base branch: main
---

Contracts: snapshot of parent plan §PINNED — provisional until t1120_1 freeze
(this task IS the freeze owner — see Step 5).

# Plan: t1120_1 — Generic Q&A relay protocol library

The full deliverable list, normative schemas (question/answer, spool layout,
custom_id encoding), and reference-pattern anchors are in the task file
(`aitasks/t1120/t1120_1_relay_protocol_library.md`) — they are not repeated
here. Parent contracts: `aiplans/p1120_discord_bug_report_channel_integration.md`
§PINNED (this child consumes 1–6, 12 and owns the freeze rule 0).

## Step 0 — throwaway headless-relay spike (FIRST, NON-SKIPPABLE)

1. In a scratch dir (not committed): write `spike_ask.sh` — writes
   `question-1.json` to `$RELAY_DIR`, polls for `answer-1.json` (1 s interval,
   120 s timeout), prints the answer values, exits.
2. Write a minimal throwaway prompt (NOT a skill install) instructing the agent
   to: read a tiny fixture file, call `spike_ask.sh` once to ask "A or B?",
   then write `payload.json` echoing the answer.
3. Invoke headlessly: `./ait codeagent --agent-string <current> invoke raw -p
   "<prompt>"` (billing caveat accepted once for the spike — this is the
   explicit opt-in context).
4. While it blocks, hand-write `answer-1.json` (`status: answered`).
5. PASS = agent blocked, consumed the answer, wrote `payload.json` with the
   chosen value. Record in this plan: blocking behavior, any prompt-shape
   requirements, timing observations.
6. **If the spike forces contract changes** (e.g. polling cadence, schema
   fields, helper invocation shape): apply contract-freeze rule 0 — update the
   parent plan §PINNED AND every sibling task/plan file embedding the changed
   text, commit all via `./ait git` in one pass.

## Step 1 — design doc `aidocs/chat/qa_relay_protocol.md`

Write the normative protocol doc: schemas, spool layout, atomicity rule,
custom_id encoding + length budget, timeout/cancel ownership (contract 6),
sequential-v1 + batch extension point, restart-derivability rule, spike
findings summary. This doc is the source the renderer and daemon cite.

## Step 2 — `.aitask-scripts/chatlink/relay.py` (new package)

- `mint_session_id()` — `s<base36(epoch_seconds)><2 rand [a-z0-9]>`, assert
  ≤ 12 chars; single mint point.
- `build_custom_id(session_id, seq, component)` / `parse_custom_id(s)` —
  validate charset/lengths, total ≤ 100; raise on violation (never truncate).
- `SessionDir` helper: `write_question(q)`, `read_answer(seq)`,
  `write_answer(a)`, `pending_questions()` (question present ∧ answer absent),
  `write_status(...)`, `write_payload(...)` — all atomic (`.tmp` + `os.rename`,
  readers skip `*.tmp`; pattern: `applink/sessions.py:200-217`).
- Dataclasses `Question`/`Answer` with `to_dict`/`from_dict` + strict
  validation (required fields, enum status, types). Stdlib only — import guard
  test like `tests/test_chat_no_aitasks_import.sh`.

## Step 3 — `.aitask-scripts/chatlink/render.py`

- `render_question(q, capabilities) -> (text, [ActionRow])`:
  - options + not multi_select ⇒ `SelectMenu` (min/max 1); multi_select ⇒
    SelectMenu with `max_values=len(options)`.
  - `allow_free_text` ⇒ append "Answer…" `Button` (modal opened by the daemon
    on that interaction — contract 5; render exposes
    `build_modal(q) -> Modal` with one `FormField(kind="multiline")`).
  - Degradation (contract 12): >25 options ⇒ paginated selects (page buttons)
    or reject-with-reason if pagination impossible; text > `capabilities.
    max_message_length` ⇒ chunk. Branch only on `Capabilities` fields.
- `assemble_answer(q, interaction) -> Answer` — from
  `Interaction.custom_id`/`values` (`values["values"]` for selects, field map
  for MODAL_SUBMIT).

## Step 4 — `aitask_relay_ask.sh` + Python core

- Python core `chatlink/relay_ask.py`: argparse (`--relay-dir --text --header
  --option label::desc … --multi-select --free-text --timeout`), writes the
  next-seq question, blocks (poll 1 s) until answer or timeout; on timeout
  writes nothing but prints `STATUS:timeout` and exits 0 (fail-safe — contract
  6); on answer prints `STATUS:answered` + `VALUE:` lines.
- `aitask_relay_ask.sh`: thin wrapper (shebang/`set -euo pipefail` per
  `aidocs/framework/shell_conventions.md`; read
  `aidocs/framework/aitasks_extension_points.md` for new-helper rules).

## Step 5 — freeze flip

After implementation and review, record in this plan's Final Implementation
Notes: "parent plan §PINNED contracts FROZEN as of t1120_1" and edit the
parent plan's contract 0 line to state FROZEN (commit via `./ait git`).

## Testing

One bash test script (self-contained, `assert_eq`/`assert_contains`), covering
the task file's Verification list: schema round-trip + rejection, custom_id
build/parse/reject, atomicity (reader ignores `.tmp`), restart-derivability,
stale-answer negative control, timeout fail-safe (subprocess with 1 s timeout),
renderer degradation (26 options; 3000-char text), no-chat-import guard for
`relay.py`/`relay_ask.py`.

## Step 9 reference

Post-implementation follows task-workflow Step 9 (merge/verify/archive push).
