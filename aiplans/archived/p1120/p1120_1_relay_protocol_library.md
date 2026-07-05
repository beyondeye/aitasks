---
Task: t1120_1_relay_protocol_library.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_2_*.md … t1120_7_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_*_*.md
Worktree: aiwork/t1120_1_relay_protocol_library
Branch: aitask/t1120_1_relay_protocol_library
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-05 12:49
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

## Step 0 spike findings (2026-07-05 — PASS)

Run: `claude --model claude-fable-5 -p "<explicit step-list prompt>"
--allowedTools "Bash,Read,Write"` via `ait codeagent invoke raw`.
- **Round trip verified**: agent read fixture → ran blocking `spike_ask.sh` →
  question-1.json appeared **6 s** after launch → agent stayed blocked
  (payload absent 8 s later, negative control) → hand-written answer-1.json
  consumed within the 1 s poll → payload.json written with the correct value
  (`{"status": "answered", "chosen_value": "o1", "chosen_label": "B"}`) →
  clean exit 0.
- **Prompt-shape requirements**: the prompt must say explicitly that the
  command BLOCKS and must not be killed/backgrounded; headless `-p` mode
  needs `--allowedTools` (no permission prompts available).
- **Agent-side tool-timeout interaction (finding for t1120_4)**: the blocking
  helper runs inside the agent's Bash tool, whose default timeout is ~120 s.
  The helper's default `--timeout` must stay comfortably under the agent's
  tool timeout, or the calling skill must raise the tool timeout explicitly.
  Not a pinned-contract change (no default value was pinned) — recorded here
  for the t1120_4 skill design.
- **No spike-forced contract changes**: 1 s polling cadence, pinned schemas
  (with Step 0b amendments), and env-var + argv helper invocation all worked
  as designed. The Step 0b sweep therefore carries only the two pre-known
  amendments.

## Step 0b — pre-known contract amendments (single back-propagation sweep)

Two amendments are already known to be required (plan-review findings, verified
against `chat/` source) and MUST be folded into the same rule-0 sweep as any
spike findings — one combined pass over parent §PINNED + all sibling task/plan
snapshot copies, committed via `./ait git` together:

- **Contract 3 (option identity):** options gain a stable `value` —
  auto-assigned by the relay lib at question-write time as `o<idx>`
  (zero-based, `[a-z0-9]`, bounded). Wire schema becomes
  `options: [{value, label, description}]`; `Answer.values` carries option
  **values** (not labels). Rationale: `SelectOption` requires value/label
  separation (`interactions.py:60-72`); labels are display-only and may
  collide or exceed platform value limits. Validation: labels non-empty,
  ≤ 100 chars; duplicate labels are allowed on the wire but values are
  unique by construction.
- **Contract 6 (durable timeout):** on timeout the agent-side helper writes
  `answer-<seq>.json` `{status: timeout, values: [], free_text: null,
  answered_by: null}` **atomically** before proceeding — the timeout is a
  durable spool state, not just stdout. Sequence: final poll at deadline; if
  an answer file appeared, consume it as answered; else write the timeout
  answer. Never overwrite an existing answer file. This keeps
  restart-derivability sound (a timed-out question is terminal, not
  forever-"pending") and gives the gateway a reconcilable state for
  component-disabling and stale-interaction handling (an interaction for a
  seq whose answer file already exists ⇒ stale ⇒ ephemeral "question
  expired").

## Step 1 — design doc `aidocs/chat/qa_relay_protocol.md`

Write the normative protocol doc: schemas (incl. the amended option
`{value, label, description}` shape and value-assignment rule), spool layout,
atomicity rule, custom_id encoding + length budget, timeout/cancel ownership
(amended contract 6: durable timeout answer artifact; never-overwrite rule;
stale-interaction = answer file already exists), capability requirements +
fail-closed `RenderRejected` rule (fallbacks as documented extension points),
sequential-v1 + batch extension point, restart-derivability rule, spike
findings summary. This doc is the source the renderer and daemon cite.

## Step 2 — `.aitask-scripts/chatlink/relay.py` (new package)

- `mint_session_id()` — `s<base36(epoch_seconds)><2 rand [a-z0-9]>`, assert
  ≤ 12 chars; single mint point. **Collision-aware creation:** session-dir
  creation uses `os.makedirs(exist_ok=False)`; on `FileExistsError` re-mint
  and retry (bounded, 16 attempts, then raise) — a collision must never mix
  two sessions in one spool dir.
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
    SelectMenu with `max_values=len(options)`. `SelectOption.value` = the
    option's stable `value` from the amended contract-3 schema (`o<idx>`).
  - `allow_free_text` ⇒ append "Answer…" `Button` (modal opened by the daemon
    on that interaction — contract 5; render exposes
    `build_modal(q) -> Modal` with one `FormField(kind="multiline")`).
  - **Capability gating (fail-closed):** required primitives checked
    explicitly — options require `supports_selects`; `allow_free_text`
    requires `supports_buttons` AND `supports_modals`. Any missing required
    primitive ⇒ raise structured `RenderRejected(reason)` (no silent
    emission of unsupported components, no silent dropping of a requested
    affordance). All shipped adapters (Discord, Slack, Mock) support all
    three, so this is a contract guard, not a functional regression;
    graceful fallbacks (buttons-per-option, message-based form flow) are a
    documented extension point in the design doc, not v1 scope.
  - Degradation (contract 12): >25 options ⇒ paginated selects (page buttons)
    or reject-with-reason if pagination impossible; text > `capabilities.
    max_message_length` ⇒ chunk. Branch only on `Capabilities` fields.
- `assemble_answer(q, interaction) -> Answer` — from
  `Interaction.custom_id`/`values` (`values["values"]` for selects = option
  **values**; field map for MODAL_SUBMIT → `free_text`).

## Step 4 — `aitask_relay_ask.sh` + Python core

- Python core `chatlink/relay_ask.py`: argparse (`--relay-dir --text --header
  --option label::desc … --multi-select --free-text --timeout`), writes the
  next-seq question (relay lib auto-assigns option values `o<idx>` — callers
  never pass values), blocks (poll 1 s) until answer or timeout.
  - **On timeout (amended contract 6):** final poll at deadline; if the answer
    appeared, treat as answered; else **atomically write**
    `answer-<seq>.json` `{status: timeout, values: [], free_text: null,
    answered_by: null}` (never overwriting an existing answer file), print
    `STATUS:timeout`, exit 0 (fail-safe — never hang, never exit nonzero on
    timeout).
  - On answer: prints `STATUS:answered` + one `VALUE:<label>` line per
    selected option (helper resolves option values → labels from the question
    it wrote; agent-facing output stays human-meaningful) and
    `FREE_TEXT:<text>` when a modal answer carries free text.
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
build/parse/reject, atomicity (reader ignores `.tmp`), restart-derivability
(incl. **timed-out question is terminal, not pending** — amended contract 6),
stale-answer negative control, timeout fail-safe (subprocess with 1 s timeout;
asserts the durable `answer-<seq>.json {status: timeout}` artifact exists and
an existing answer file is never overwritten), option-value stability
(`o<idx>` auto-assignment; `Answer.values` round-trips values not labels),
session-dir collision retry (pre-create the dir; assert re-mint), renderer
degradation (26 options; 3000-char text), renderer capability fail-closed
(`supports_selects=False` with options ⇒ `RenderRejected`;
`supports_modals=False` with `allow_free_text` ⇒ `RenderRejected`),
no-chat-import guard for `relay.py`/`relay_ask.py`.

**E2E real-wrapper test (real entry point):** in a temp relay dir, run the
actual `aitask_relay_ask.sh` (the shell wrapper, not the Python core) in the
background with two options; assert `question-1.json` appears with expected
content (text, auto-assigned option values); hand-write `answer-1.json`;
assert the wrapper prints `STATUS:answered` + the correct `VALUE:<label>`
line and exits 0. A second invocation in the same session dir must select
seq 2. This proves wrapper wiring, argv parsing, seq selection, and answer
parsing together.

## Post-Review Changes

### Change Request 1 (2026-07-05 13:20)
- **Requested by user:** four review findings — (1) HIGH: `write_answer`
  never-overwrite was check-then-act (`exists()` + `os.replace`), losing the
  gateway-vs-timeout race contract 6 protects against; (2) MED: pagination
  emits nav Buttons but only `supports_selects` was gated; (3) MED: paginated
  multi-select cannot accumulate selections across page-local selects;
  (4) LOW: `assemble_answer` accepted multiple values for single-select.
- **Changes made:** (1) no-overwrite answer publication is now an atomic
  create-no-replace (tmp write + `os.link`; `FileExistsError` ⇒ False, tmp
  always unlinked) — first publisher wins in both race directions; (2)
  `pages > 1` now requires `supports_buttons` (fail-closed); (3) paginated
  multi-select raises `RenderRejected` in v1 (cross-page accumulation is a
  documented extension point in the protocol doc); (4) single-select
  submissions with ≠ 1 value raise `AnswerMismatch` (multi_select still
  accepts several). Protocol doc updated (§Timeout — indivisible
  check-and-write; §Rendering — pagination button requirement,
  multi-select-pagination rejection, single-select value count). Tests: +8
  checks incl. an os.replace-spy TOCTOU negative control, selects-only
  adapter positive control, paginated-multi-select rejection, forged
  multi-value rejection (now 60 Python + 15 shell checks, all pass).
- **Files affected:** `.aitask-scripts/chatlink/relay.py`,
  `.aitask-scripts/chatlink/render.py`, `aidocs/chat/qa_relay_protocol.md`,
  `tests/test_chatlink_relay.sh`.

### Change Request 2 (2026-07-05 13:30)
- **Requested by user:** HIGH — the create-no-replace fix still staged under
  the fixed shared name `answer-<seq>.json.tmp`; a competing writer could
  overwrite the staged payload before the link published it (final path
  protected, staged payload not).
- **Changes made:** staging name is now unique per writer
  (`answer-<seq>.json.<pid>.<8-hex>.tmp` — still `*.tmp` so readers skip
  it), then `os.link(unique_tmp, final)`. Protocol doc updated. Test added:
  squatted shared-tmp negative control (poisoned `answer-8.json.tmp` is
  ignored, writer's payload publishes intact, squatted file untouched).
  Suite now 63 Python + 15 shell checks, all pass.
- **Files affected:** `.aitask-scripts/chatlink/relay.py`,
  `aidocs/chat/qa_relay_protocol.md`, `tests/test_chatlink_relay.sh`.

## Step 9 reference

Post-implementation follows task-workflow Step 9 (merge/verify/archive push).

## Final Implementation Notes

- **Actual work done:** Exactly the planned deliverables, in plan order:
  Step-0 headless spike (PASS — see "Step 0 spike findings"); Step-0b
  contract sweep (contracts 3 + 6 amended in parent §PINNED + both t1120_1
  snapshots, single `./ait git` commit); `aidocs/chat/qa_relay_protocol.md`
  (normative spec); new package `.aitask-scripts/chatlink/` (`__init__.py`,
  `relay.py`, `render.py`, `relay_ask.py`); `aitask_relay_ask.sh` wrapper;
  `tests/test_chatlink_relay.sh` (63 Python checks + 15 shell-level groups,
  incl. E2E through the real wrapper; all pass, shellcheck clean).
- **Deviations from plan:** (1) `render_question` returns a
  `RenderedQuestion` dataclass (`text_chunks`, `rows`, `page`, `page_count`)
  instead of the loosely-pinned `(text, [ActionRow])` tuple — richer return
  for the daemon (chunking + pagination state); the protocol doc documents
  it. (2) Two review iterations hardened the design beyond the plan: answer
  publication is an atomic create-no-replace (`os.link`) with unique
  per-writer staging names (TOCTOU + staging races); pagination requires
  `supports_buttons`; paginated multi-select is `RenderRejected` in v1;
  single-select answers must carry exactly one value (see Post-Review
  Changes 1–2).
- **Issues encountered:** none blocking. The initial import-purity test
  used a `"chat"` prefix that matched `chatlink` itself (fixed to exact
  top-level match).
- **Key decisions:** option identity = relay-lib-assigned `o<idx>` values
  (labels display-only); timeout is durable spool state (helper writes the
  timeout answer, final-poll-then-write); helper default timeout 90 s to
  stay under a headless agent's ~120 s Bash-tool timeout (spike finding —
  t1120_4 must raise the tool timeout for longer asks); capability gating
  fail-closed (`RenderRejected`) with fallbacks as documented extension
  points; `aitask_relay_ask.sh` deliberately ships with NO permission
  whitelist entries — the 7-touchpoint checklist fires in t1120_4 when a
  SKILL.md first cites it (handoff note committed into p1120_4).
- **Upstream defects identified:** None
- **Notes for sibling tasks:** `chatlink/relay.py` and `relay_ask.py` are
  stdlib-only and must stay that way (guard test part 2); the daemon
  (t1120_3) should use `SessionDir.pending_questions()` for restart
  reconciliation and `write_answer(..., overwrite=False)` for cancelled
  answers (same never-clobber guarantee); `render.is_page_nav` /
  `is_free_text_trigger` are the daemon's interaction-routing helpers;
  `assemble_answer` raises `AnswerMismatch` for anything stale/foreign —
  map that to the ephemeral "question expired" reply.
- **Contract freeze:** parent plan §PINNED contracts **FROZEN as of
  t1120_1** (recorded here per contract 0; parent plan contract-0 line
  edited in the same commit). Sibling snapshots are now authoritative.

## Verification notes (2026-07-05, pre-implementation verify pass)

Re-checked all plan assumptions against current source (concurrent Slack-adapter
work on main touched `chat/` internals but not the frozen surface):
- `chatlink/` absent — greenfield confirmed. `aidocs/chat/` exists
  (`discord_bot_setup.md`, `slack_app_setup.md`); `qa_relay_protocol.md` is new.
- `interactions.py` anchors drifted by +1: Button :39, SelectMenu :76,
  ActionRow :97, FormField :113, Modal :133, Interaction :214.
- Select answers arrive as `values["values"]` (`discord_adapter.py:332`);
  MODAL_SUBMIT values keyed by field `custom_id` — matches `assemble_answer`.
- `Capabilities.max_message_length = 2000` (`capabilities.py:50`).
- Atomic-write pattern confirmed at `applink/sessions.py:200-217`
  (`.tmp` write → chmod → `Path.replace`).
- `raw` in `SUPPORTED_OPERATIONS` (`aitask_codeagent.sh:28`) — spike viable.
- Parent plan §PINNED contracts 1–13 match the task/plan snapshots — no drift.

## Risk

### Code-health risk: low
- Purely additive greenfield package (`.aitask-scripts/chatlink/`) + one new
  helper script; no existing module edited; `render.py` consumes the frozen
  `chat/` surface read-only · severity: low · → mitigation: embedded
  (import-guard test keeps `relay.py`/`relay_ask.py` stdlib-pure; new-helper
  conventions per `aidocs/framework/aitasks_extension_points.md`)

### Goal-achievement risk: medium
- Central unvalidated assumption: a headless agent reliably blocks on
  `aitask_relay_ask.sh` and resumes when the answer file appears · severity:
  high · → mitigation: embedded (Step 0 throwaway spike sequenced FIRST;
  contracts provisional until it passes — contract 0)
- Back-propagation completeness: contract amendments (the two pre-known
  Step 0b ones — option `value`, durable timeout — plus any spike-forced
  changes) must update the parent plan AND all sibling task/plan snapshot
  copies in one pass; a missed file leaves stale contract text for a future
  fresh context · severity: medium · → mitigation: embedded (Step 0b single
  combined sweep; grep the changed contract text across `aitasks/t1120/` +
  `aiplans/p1120/` before committing)
- Renderer degradation shape (>25 options: paginated selects vs
  reject-with-reason) is decided in the design doc; a wrong first choice is
  recoverable · severity: low · → mitigation: embedded (contract 12 permits
  either; design doc records the decision for the daemon/siblings to cite)
