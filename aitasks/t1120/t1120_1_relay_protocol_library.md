---
priority: high
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [chat_surface, python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1120
implemented_with: claudecode/fable5
created_at: 2026-07-05 11:58
updated_at: 2026-07-05 12:50
---

## Context

First child of t1120 (Discord bug-report channel integration). Builds the generic
structured Q&A relay: the seam by which a spawned headless agent asks clarifying
questions that a gateway renders as Discord components. **No relay IPC exists in
the repo today** — this is greenfield. The full decomposition and the PINNED
cross-child contracts live in `aiplans/p1120_discord_bug_report_channel_integration.md`
(§PINNED cross-child contracts) — this child is the **contract owner**.

**Contracts: snapshot of parent plan §PINNED — provisional until this child's
Step-0 spike passes (contract 0).** If the spike forces contract changes, this
child MUST update the parent plan AND every already-created sibling task/plan
file embedding contract text, committed via `./ait git` in one pass. After this
child archives, the parent plan's freeze status flips to FROZEN (record the flip
in this child's plan).

## Step 0 — throwaway headless-relay spike (FIRST, NON-SKIPPABLE)

Validates the umbrella's central assumption before any contract-consuming code:
- Hand-write a minimal throwaway skill that calls a blocking relay helper stub.
- Invoke the agent headlessly (`ait codeagent --agent-string <s> invoke raw -p <prompt>`).
- Hand-write the `answer-<seq>.json` file while the agent blocks.
- Verify the round trip: question JSON emitted → agent blocks → answer consumed →
  agent continues and writes output.
Record findings in the plan; back-propagate any contract changes (see above).
Spike artifacts are throwaway (not committed as product code).

## Key deliverables

1. Design doc `aidocs/chat/qa_relay_protocol.md` — normative schemas, spool
   layout, custom_id encoding, timeout/cancel ownership, sequential-v1 +
   batch-extension note, restart-derivability rule.
2. `chatlink/relay.py` (new package `.aitask-scripts/chatlink/`) — pure-stdlib
   spool read/write lib: atomic writes (tmp+rename, readers ignore `*.tmp`),
   session_id mint point (`s<base36-epoch-seconds><2-char random>`, max 12 chars,
   `[a-z0-9]`), custom_id build/parse (`cl1:<session_id>:<seq>:<component>`,
   component tag ≤ 8 chars `[a-z0-9_]`, hard-validate ≤ 100 chars — reject, never
   truncate), question/answer schema validation.
3. `chatlink/render.py` — question → `chat/interactions.py` components
   (SelectMenu/Buttons per options/multi_select; free-text = "Answer…" button →
   modal two-step) + answer assembly from `Interaction` (custom_id, values).
   Degradation rules: >25 options ⇒ paginated select or reject-with-reason;
   >2000 chars ⇒ chunked; branch on `Capabilities`, never platform name.
4. `aitask_relay_ask.sh` helper (+ Python core for testability) — agent-side
   blocking ask: writes `question-<seq>.json`, blocks on `answer-<seq>.json`
   with bounded default timeout; **timeout ⇒ proceed with `status: timeout`,
   never hang**.

## Normative schemas (contract 3)

Question: `{id, seq, session_id, text, header, options: [{label, description}],
multi_select: bool, allow_free_text: bool, timeout_s}`.
Answer: `{id, seq, status: answered|timeout|cancelled, values: [..],
free_text: str|null, answered_by}`.
Spool layout (contract 2): `<relay_root>/<session_id>/question-<seq>.json`,
`answer-<seq>.json`, `payload.json`, `status.json`.
One question in flight at a time (sequential v1).

## Reference files for patterns

- `.aitask-scripts/chat/interactions.py` (Button :38, SelectMenu :75, ActionRow
  :96, Modal :132, Interaction :213) — component substrate.
- `.aitask-scripts/chat/capabilities.py` — degradation branching input.
- `.aitask-scripts/applink/sessions.py:200-217` — atomic write pattern.
- `aidocs/framework/shell_conventions.md` — shell script conventions;
  `claude -p` billing caveat (spike only, opt-in).

## Verification

- Unit tests (bash test script per repo convention): schema validation
  round-trip, custom_id build/parse + length rejection, atomic-write hygiene,
  restart-derivability (pending = question present ∧ answer absent — no
  in-memory state), stale-answer negative control (seq already passed ⇒
  ignored), timeout fail-safe (helper exits with timeout status, never hangs),
  renderer degradation (>25 options, >2000 chars).
- No chat/discord imports in `relay.py` or the helper (agent side is pure).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-05T09:50:46Z status=pass attempt=1 type=human
