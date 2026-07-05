# Q&A Relay Protocol (chatlink)

Normative specification of the structured question/answer relay between a
**spawned headless code agent** (the asker) and the **chatlink gateway
daemon** (the renderer/answer-router). This document is the source the
relay library (`.aitask-scripts/chatlink/relay.py`), the renderer
(`chatlink/render.py`), the agent-side ask helper (`aitask_relay_ask.sh` /
`chatlink/relay_ask.py`), and the gateway daemon (t1120_3) cite.

Origin: t1120_1 (contract owner for the t1120 umbrella's PINNED cross-child
contracts — see `aiplans/p1120_discord_bug_report_channel_integration.md`
§PINNED). Contract numbers below refer to that section.

## Transport model

The relay is a **file-based JSON spool** in a bind-mountable directory —
identical for a local subprocess and a Docker container. The agent never
talks to the chat platform; the gateway owns the conversation. There is no
socket, no daemon-side push: both sides poll the spool (1 s cadence is
proven sufficient — see Spike findings).

## Session identity (contract 1)

One `session_id` per spawned agent: `s<base36-epoch-seconds><2-char random>`

- charset `[a-z0-9]`, **max 12 chars**, always starts with `s`.
- Minted **only** by `chatlink.relay.mint_session_id()` — the single mint
  point, which validates length/charset at construction.
- **Collision-aware creation:** the random suffix has only 1296 slots per
  second, so session-directory creation uses `os.makedirs(exist_ok=False)`
  and re-mints on `FileExistsError` (bounded retries, then error). A
  collision must never mix two sessions in one spool directory.
- Appears in: the relay session dir name, `custom_id`s, the container
  label, audit lines, and the output payload.

## Spool layout (contract 2)

```
<relay_root>/<session_id>/
    question-<seq>.json     # written by the agent-side ask helper
    answer-<seq>.json       # written by the gateway (or by the helper on timeout)
    payload.json            # final agent output (contract 7; validated by the gateway)
    status.json             # gateway-owned session lifecycle state (opaque here)
```

- `<seq>` is a decimal integer ≥ 1, monotonic per session, ≤ 6 digits.
  The next seq is **derived from the spool** (max existing question seq + 1)
  — no in-memory counter.
- **Atomic writes everywhere:** write `<name>.tmp`, then `os.rename` /
  `Path.replace`; readers ignore `*.tmp` (pattern:
  `applink/sessions.py:200-217`). No reader may ever observe a partial JSON
  file.
- `status.json` shape is owned by the gateway daemon (t1120_3); the relay
  library only provides atomic read/write of an opaque JSON object.

## Question schema (contract 3, amended)

```json
{
  "id": "q-<session_id>-<seq>",
  "seq": 1,
  "session_id": "sxxxxxxxx",
  "text": "Which module owns this bug?",
  "header": "Module",
  "options": [
    {"value": "o0", "label": "parser", "description": "the tokenizer/parser"},
    {"value": "o1", "label": "renderer", "description": "the output layer"}
  ],
  "multi_select": false,
  "allow_free_text": true,
  "timeout_s": 90
}
```

- **Option `value` is a stable id auto-assigned by the relay library at
  question-write time** as `o<idx>` (zero-based, `[a-z0-9]`). Callers never
  pass values. Labels are display-only: non-empty, ≤ 100 chars; duplicate
  labels are tolerated on the wire (values disambiguate), but callers should
  avoid them.
- A question with no options and `allow_free_text: false` is invalid
  (unanswerable) — rejected at construction.
- `multi_select: true` requires ≥ 1 option.
- `timeout_s` > 0. The helper default is **90 s** — deliberately under the
  ~120 s default Bash-tool timeout of a calling headless agent (see Spike
  findings).

## Answer schema (contract 3, amended)

```json
{
  "id": "q-<session_id>-<seq>",
  "seq": 1,
  "status": "answered",
  "values": ["o1"],
  "free_text": null,
  "answered_by": "U123"
}
```

- `status` ∈ `answered | timeout | cancelled`.
- `values` carries option **values** (never labels). For `timeout` /
  `cancelled` it is `[]` and `free_text` is `null`.
- An `answered` answer must carry ≥ 1 value **or** non-null `free_text`.
- `answered_by` is the platform actor id of the answering user (`null` for
  helper-written timeout answers and gateway-written cancellations).

## custom_id encoding (contract 4)

```
cl1:<session_id>:<seq>:<component>
```

- `cl1` literal prefix (protocol version 1).
- `<component>` tag: `[a-z0-9_]`, ≤ 8 chars. Reserved tags:
  - `select` — the option select menu
  - `freetext` — the "Answer…" button (opens the modal)
  - `modal` — the free-text modal
  - `ftfield` — the modal's text field
  - `pg<n>` — pagination nav button targeting page `<n>`
- Total length hard-validated ≤ 100 (platform limit): **reject, never
  truncate.** Worst case by construction is 32 chars.
- **Restart safety is stateless:** routing is derivable from `custom_id` +
  spool state alone. `pending(seq)` ⇔ `question-<seq>.json` present ∧
  `answer-<seq>.json` absent. No in-memory-only routing maps.

## Timeout / cancel ownership (contract 6, amended)

- The **agent-side helper owns the timeout** (bounded default, fail-safe:
  on timeout the agent proceeds with `status: timeout`; it never hangs and
  never exits nonzero for a timeout).
- **The timeout is a durable spool state.** At the deadline the helper does
  a final poll: if the answer appeared, it is consumed as answered;
  otherwise the helper **atomically writes**
  `answer-<seq>.json {status: timeout, values: [], free_text: null,
  answered_by: null}` before proceeding. It never overwrites an existing
  answer file — and the check-and-write is **indivisible**: answer files
  are published with an atomic create-no-replace (staging write +
  `os.link`), and each writer stages under a **unique per-writer name**
  (pid + random, `*.tmp`-suffixed) so competing writers can neither clobber
  the final file nor each other's staged payload (first publisher wins; the
  loser observes `FileExistsError` and reads the winner). A timed-out question is
  therefore terminal — never forever-"pending" to restart reconciliation.
- The **gateway** disables components (message edit) on
  timeout/cancel/agent-death and writes `cancelled` answers for spool
  hygiene on agent death.
- **Stale interactions:** an interaction for a seq whose answer file
  already exists is stale ⇒ the gateway replies with an ephemeral
  "question expired" and changes nothing. Stale answers (seq already
  passed) are ignored by the helper.

## Free-text: two-step modal dance (contract 5)

The question message carries an "Answer…" button (`freetext`). On that
interaction the gateway calls `open_modal` **immediately** (it must beat the
adapter's scheduled defer — `discord_adapter.py` `_defer_later`). The modal
(`modal`) has a single multiline field (`ftfield`); its MODAL_SUBMIT
interaction carries the text keyed by the field's `custom_id`. Late/expired
clicks get an ephemeral "question expired".

## Rendering rules (contract 12 + capability gating)

Rendering branches **only on `Capabilities` fields, never platform name**.

- options + `multi_select: false` ⇒ `SelectMenu` (min/max 1);
  `multi_select: true` ⇒ SelectMenu with `max_values = len(options)`.
  `SelectOption.value` = the option's stable `value`.
- `allow_free_text` ⇒ append the "Answer…" `Button`.
- **Capability gating (fail-closed):** options require `supports_selects`;
  `allow_free_text` requires `supports_buttons` AND `supports_modals`. A
  missing required primitive raises a structured `RenderRejected(reason)` —
  no silent emission of unsupported components, no silent dropping of a
  requested affordance. (All shipped adapters — Discord, Slack, Mock —
  support all three; graceful fallbacks such as buttons-per-option or a
  message-based form flow are an extension point, not v1 behavior.)
- **Degradation — many options:** a select menu holds ≤ 25 options
  (platform floor). With > 25 options the renderer paginates: pages of 24
  options plus a nav row of `pg<n>` buttons (Prev/Next targeting the
  adjacent page; disabled at the edges). Page state is stateless — the
  target page rides in the nav button's `custom_id`; option values are
  global (`o<idx>`), so answers are page-independent. Pagination
  additionally requires `supports_buttons` (the nav is button-based) —
  fail-closed otherwise. **Paginated multi-select is rejected in v1**
  (`RenderRejected`): page-local selects cannot accumulate a selection
  across pages; a cross-page accumulation flow is a documented extension
  point.
- **Single-select answers carry exactly one value**: `assemble_answer`
  rejects a multi-value submission for a `multi_select: false` question
  (forged/malformed interactions fail closed).
- **Degradation — long text:** question text exceeding
  `capabilities.max_message_length` is chunked; the daemon sends the chunks
  in order and attaches components to the **last** chunk.

## Sequencing (contract 3)

**One question in flight at a time (sequential v1).** The helper blocks
until its question reaches a terminal state before the agent can ask the
next. A batched/parallel extension (multiple pending seqs) is a documented
extension point: the spool layout and custom_id encoding already carry
`seq`, so batching requires no wire change — only helper/daemon loop
changes. Not implemented in v1.

## Spike findings (t1120_1 Step 0, 2026-07-05 — PASS)

Headless round trip validated with `claude -p` via
`ait codeagent invoke raw`:

- Agent launched headlessly ran a blocking ask script; the question file
  appeared ~6 s after launch; the agent remained blocked (negative control
  at +8 s); a hand-written answer was consumed within the 1 s poll; the
  agent wrote the correct output payload and exited 0.
- Prompt-shape: the prompt must state explicitly that the ask command
  blocks and must not be killed/backgrounded. Headless `-p` mode requires
  `--allowedTools` (no permission prompts are possible).
- **Tool-timeout interaction:** the blocking helper runs inside the calling
  agent's Bash tool (~120 s default timeout). The helper's default
  `timeout_s` (90 s) stays under it; a skill asking longer questions must
  raise the tool timeout explicitly (owned by t1120_4).

## Module map

| Concern | Where |
|---|---|
| Spool read/write, schemas, session/custom_id identity | `.aitask-scripts/chatlink/relay.py` (stdlib-only; no `chat/` imports) |
| Question → components, answer assembly | `.aitask-scripts/chatlink/render.py` (imports `chat/interactions.py`, `chat/capabilities.py`) |
| Agent-side blocking ask CLI | `.aitask-scripts/chatlink/relay_ask.py` + `aitask_relay_ask.sh` (stdlib-only) |
| Gateway daemon (intake, routing, lifecycle) | t1120_3 (`chatlink/daemon.py`) |
| Payload validation & task creation | t1120_6 (gateway side; contract 7) |
