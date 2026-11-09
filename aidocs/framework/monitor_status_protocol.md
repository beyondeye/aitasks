# Monitor status protocol — one producer, many clients

`ait monitor`, `ait minimonitor` and applink each used to build their own
`TmuxMonitor` and scan every tmux pane on their own timer. The shared monitor
status server replaces that with **one producer per (tmux server, framework
`VERSION`)** whose output every client subscribes to. This document is the wire
between that server and its clients: newline-delimited JSON over a Unix socket,
a snapshot followed by per-generation deltas, a handful of requests, and a
recording format that doubles as the parity fixture for the Go monitor.

Read this when you edit `.aitask-scripts/monitor/status_protocol.py`,
`.aitask-scripts/monitor/status_recording.py`,
`.aitask-scripts/monitor/status_client.py`, the recorded fixtures under
`tests/fixtures/monitor_status/`, or the status server, or anything that speaks
this protocol in another language.

Read together with:

- `aidocs/framework/monitor_idle_and_prompt_detection.md` — what `is_idle`,
  `awaiting_input` and `awaiting_input_kind` mean, and the "verbatim
  reproduction" rule the fixtures obey.
- `aidocs/applink/protocol.md` — the mobile wire protocol. applink stays the
  remote path; this protocol is local only. The additive-versioning rule below
  is the same one.
- `aidocs/framework/tmux_gateway.md` — the server's tmux calls go through the
  gateways like every other caller.

The member tables in this document are pinned to the Python codec's schema
tables by `tests/test_monitor_status_protocol.py` (each table is preceded by a
`schema:` marker comment). Change a table and the codec together.

## Scope

- **Local only.** A Unix stream socket, no TCP, no TLS, no pairing. Server and
  clients run as the same user on the same host.
- **One server per (tmux server/socket, framework `VERSION`).** Prompt patterns
  change between releases, and several framework versions can share one tmux
  server, so a client only ever talks to the server of its own version.
- **What the server owns:** the producer (`TmuxMonitor`) — discovery and the
  session→project map, capture, ANSI stripping, prompt classification and
  `agent_key`, the idle clock, shadow pairing (`@aitask_shadow_target`), the
  completed set and the discovery facts.
- **What stays client-side:** the client's own pane and the multi-session `M`
  filter, the parked placeholder substitution, the minimonitor review loop's
  raw-tail captures, every action (send-keys, kill, pick, shadow spawn), the TUI
  switcher. See [Client-side settings](#client-side-settings).

## Transport and framing

- A Unix **stream** socket carrying UTF-8 JSON, **one object per line**, each
  line terminated by `\n`. A message is complete only when its `\n` arrives.
- Encoders write compact JSON with **sorted keys**, `ensure_ascii` off, and never
  NaN or Infinity. Lone UTF-16 surrogates in a string are replaced with U+FFFD
  before writing. Control characters (including the ESC of ANSI sequences)
  appear as JSON `\u` escapes, so no line ever contains a raw newline or ESC.
- Integers are JSON numbers **without a fraction or exponent**. A number that a
  member declares as an integer and is written `1.0` or `1e2` is malformed (a Go
  `int64` field refuses it too). Numbers declared as seconds may be integers or
  fractions; senders round them to milliseconds. Receivers range-check a number
  as the exact value it denotes — a 400-digit integer is out of range, never an
  overflow.
- **Line limits** (the terminating `\n` not counted): 64 KiB client→server,
  64 MiB server→client. A record's `content` is capped at 4 MiB characters;
  lists and maps at 4096 items.
- Each connection is ordered: the server writes one ordered outbound sequence per
  connection (see [Ordering](#ordering)).

## Envelope

Every message is an object with a `type` member naming its kind. Other members
depend on the type.

- Client requests may carry an `id`: a string of at most 128 characters, or an
  integer `0 … 2^53−1`. A `result`, an `error`, and a `snapshot` sent as a reply
  echo it.
- Every server message carries `ts`: wall-clock epoch seconds, rounded to
  milliseconds.

Message types by direction:

<!-- schema:list types-client -->
- `hello`
- `subscribe`
- `set_content`
- `set_pins`
- `refresh`
- `set_compare_mode`
- `cycle_compare_mode`
- `capture`

<!-- schema:list types-server -->
- `welcome`
- `snapshot`
- `delta`
- `result`
- `error`

<!-- schema:list types-recording -->
- `recording`
- `welcome`
- `snapshot`
- `delta`

## Versioning

- `proto` is an integer **major** version. This document defines `1`.
- `VERSION` equality (the framework version) is what makes a server "the right
  server" for a client. `proto` is what a codec, a recording and a replayer
  check.
- **Additive changes do not bump `proto`:** new optional members, new request
  types, new error codes, new values of an open string.
- **Open strings** — receivers must accept values they do not know:
  `awaiting_input_kind` (one value per prompt pattern; adding a pattern adds a
  value), `control_state`, and an error's `code`. *Renaming or removing* a value
  is the breaking edit, because a client keyed on that value silently stops
  matching.
- **Closed enums** — a new value requires a `proto` bump, because renderers
  branch on them:

<!-- schema:list category -->
- `agent`
- `tui`
- `other`

<!-- schema:list compare_mode -->
- `stripped`
- `raw`

- **Unknown members are ignored** at every level — top-level, inside records,
  inside `pane`, inside results. The Python decoder drops them from its
  normalized output.
- **Unknown message types:** a client ignores a server message type it does not
  know. A server answers an unknown request type with
  `error{code:"unknown_type"}` and keeps the connection.

## Malformed input

A line is **malformed** if it:

- is not valid UTF-8, not JSON, or not a JSON object;
- is empty;
- has a duplicated member name at any level;
- is missing `type` or a required member;
- has a member of the wrong type — a bool is not an integer, and neither is any
  number with a fraction or exponent;
- has a number out of range, or a pane id that is not, as a whole string, `%`
  followed by 1–10 ASCII digits (`"%1\n"` and `"%\u0661"` are malformed);
- has a closed-enum member with a value outside its list, or an oversize string
  or list;
- has a `pane` member whose `pane_id` (in `panes`) or `shadow_target` (in
  `shadows`) does not equal the map key;
- is a message type that is not valid in its direction (a client sending
  `snapshot`, a `recording` header on a socket).

A malformed client line **within the size limit** is answered with
`error{code:"bad_message"}` and the connection is kept, as applink does — except
before the handshake, where the server answers and closes. A malformed server
line is a protocol violation: the client disconnects and reconnects or falls
back to in-process scanning.

**Error replies stay correlated and bounded.** When the offending line is a JSON
object whose `id` is itself a valid id, the error reply echoes that `id` — even
though the rest of the request is malformed or its type unknown — so a client
with several requests outstanding can match the error to its request. Likewise
the object's `type` is echoed as `request` when it is a string of at most 64
characters. An invalid `id` and an over-long `type` are never echoed, and the
`message` diagnostic is capped at 4096 characters: an error reply must never
itself fail to encode.

### Oversized lines

A line longer than the receiver's limit is a **framing error**, not a malformed
message, because it cannot be re-framed safely: once the limit is crossed, the
rest of that line — which may arrive in later fragments — would otherwise be
parsed as a message of its own. So the receiver never tries to resynchronize
inside the stream:

- a server sends `error{code:"too_long"}` and **closes** the connection;
- a client closes the connection and reconnects or falls back.

This holds whether the oversized line arrives in one write or in fragments, and
requests that follow it on the same connection are never answered. An
unterminated tail at EOF is discarded, never parsed.

Python note: `asyncio.StreamReader.readline()` raises `ValueError` at the
reader's limit and, for a fragmented line, clears its buffer mid-line — exactly
the desync this rule avoids. `status_protocol.read_line()` treats that error as
terminal (`FramingError`), and both the replayer and the recorder use it.

## Handshake

The client speaks first. Before a `welcome`, any other request is answered with
an error and the connection is closed.

<!-- schema:message hello -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `proto` | integer | yes | The client's protocol major version. |
| `version` | string | yes | The client's framework `VERSION`. |
| `client` | object | yes | Who is connecting (below). Informational: logs and diagnostics. |

<!-- schema:object hello.client -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `kind` | string | yes | `monitor`, `minimonitor`, `applink`, `recorder`, … (open). |
| `pane` | pane id | no | The client's own tmux pane, when it has one. |
| `pid` | integer | no | The client's process id. |

The server answers with a `welcome`, or with an `error` and then closes:
`proto_mismatch` (carrying `server_proto`) or `version_mismatch` (carrying
`server_version`). A client that gets either falls back to in-process scanning
— it is talking to the wrong server.

<!-- schema:message welcome -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `ts` | seconds | yes | Server wall clock. |
| `proto` | integer | yes | The server's protocol major version. |
| `version` | string | yes | The server's framework `VERSION`. A replayer echoes the client's. |
| `server` | object | yes | Which implementation answered (below). |
| `replay` | object | no | Present only when a replayer answered (below). |

<!-- schema:object welcome.server -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `impl` | string | yes | `python`, `go`, `replay`, `scenario`, … (open). |
| `pid` | integer | no | The server's process id. |

<!-- schema:object welcome.replay -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `recorded_version` | string | yes | The `version` of the recording being replayed. |
| `source` | string | yes | The recording header's `source`. |

A replayer is a fixture server, not "the wrong server": it **echoes the
client's `version`** so any client of any version can replay any recording, and
marks itself with `replay`.

## Subscription and generations

<!-- schema:message subscribe -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `id` | id | no | Echoed by the reply snapshot. |
| `content` | selection | no | Whose `content` this client receives: `"all"` (default), `"none"`, or an array of pane ids. See [Content selection](#content-selection). |
| `include_shadows` | bool | no | Whether shadow records are sent (default `true`). |
| `pins` | pins | no | This client's capture pins (default none): `"all"` or an array of `[session, window]` pairs. See [Client-side settings](#client-side-settings). |

There is no session filter: the multi-session `M` toggle is client view state
and the client filters by session itself.

The reply is a `snapshot` with every member present:

<!-- schema:message snapshot -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `ts` | seconds | yes | Wall clock of the generation it describes. |
| `gen` | integer | yes | That generation. |
| `id` | id | no | The request's `id`, when the snapshot is a reply that carried one. |
| `panes` | map pane id → record | yes | Every agent-facing pane, full records. |
| `shadows` | map pane id → record | yes | Shadow records keyed by the **followed** pane id. |
| `completed` | array of pane ids | yes | Panes whose task is finished (below). |
| `sessions` | map name → session | yes | The session→project map. |
| `parked` | array of pairs | yes | The global parked set, `[session, window]` pairs. |
| `discovery` | object | yes | The producer's discovery facts for this generation. |
| `control_state` | string | yes | The producer's tmux control-channel state (open string). |

After it, the server sends **one `delta` per producer commit** — a tick, or the
effects of a `refresh`:

<!-- schema:message delta -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `ts` | seconds | yes | Wall clock of this generation. |
| `gen` | integer | yes | This generation: the previous one plus one. |
| `panes` | map pane id → record or patch | no | Panes added (full record) or changed (patch). |
| `removed` | array of pane ids | no | Panes gone this generation. |
| `shadows` | map pane id → record or patch | no | Shadows added or changed, keyed by the followed pane id. |
| `shadows_removed` | array of pane ids | no | Followed pane ids whose shadow is gone. |
| `completed` | array of pane ids | no | Replaces the completed set. |
| `sessions` | map name → session | no | Replaces the session→project map. |
| `parked` | array of pairs | no | Replaces the global parked set. |
| `discovery` | object | no | Replaces the discovery facts. |
| `control_state` | string | no | Replaces the control state. |

- A delta is sent **even when nothing changed** — it is also the heartbeat that
  keeps `gen` contiguous.
- One message describes exactly one generation; every member it carries is a
  fact of that generation. A pane whose capture failed in a tick is absent from
  that generation (it is `removed`, and comes back as a full record when it is
  captured again), exactly as it is absent from that tick's in-process snapshot
  dict.

### Generation rules

- `gen` counts per server process. Each connection starts with a fresh client
  state, so a restarted server resetting `gen` does no harm.
- A delta with `gen ≤ state.gen` is stale and is dropped.
- A delta with `gen == state.gen + 1` applies.
- A larger `gen` is a **gap**: the client sends `subscribe` again and gets a
  fresh snapshot.
- A delta that arrives before any snapshot is an error.
- A snapshot replaces the client's state wholesale.

### Initial and repeated subscription

The first `subscribe` on a connection starts that connection's **one** stream. A
later `subscribe` on the same connection is a **resync**:

- it changes `content` / `include_shadows` / `pins` when it carries them;
- it is answered with a snapshot of the **current** state — the state at the
  `gen` of the last delta already sent on this connection;
- the one existing stream then continues from `gen + 1`.

It never starts a second stream, never replays history, and never rewinds.
`set_content` follows the same rule.

### Ordering

Each connection has exactly one ordered outbound sequence. A reply snapshot (to
`subscribe` or `set_content`) is placed in that sequence **between two
deltas**: every delta before it was encoded under the old selection, its `gen`
equals the last delta sent, and every delta after it is encoded under the new
selection. The server never sends a delta whose `gen` is not the reply
snapshot's `gen + 1`. `result` and `error` replies go into the same sequence, so
`result{request:"refresh", gen}` always arrives after the delta that carries that
`gen`.

### Patches

- An entry in `panes` or `shadows` for an id the client does not hold must be a
  **full record**.
- For an id the client holds, the entry is a **patch**: each member present
  replaces the stored member wholesale. `pane` is one member — there is no deep
  merge. A patch cannot remove a member.
- `removed` / `shadows_removed` delete entries.
- The other top-level members, when present, replace the stored value wholesale.

### Content selection

- Selection affects **only** the `content` member of pane records and shadow
  records. Every pane, and every other member, is sent whatever the selection —
  status metadata is independent of it. A shadow's content follows its
  **followed** pane id.
- A record for an unselected pane carries no `content`; clients treat it as
  `""`. A patch that would carry only unselected content is not sent at all (the
  delta itself still is).
- `set_content` is answered with a fresh snapshot under the new selection, so
  newly selected panes arrive with their current content.

## Records

A pane record and a shadow record have the same shape. A **full record** has
every required member; a **patch** is any subset.

<!-- schema:object record -->
| Member | Type | Required | From (`PaneSnapshot` unless noted) |
|---|---|---|---|
| `pane` | object | yes | `pane` — every `TmuxPaneInfo` field (below). |
| `content` | string | no | `content`: the raw capture **with ANSI escapes** (`capture-pane -p -e -S -<capture_lines>`, scrollback plus the visible pane). Absent for an unselected pane; `""` for a parked or frozen placeholder. |
| `idle_seconds` | seconds | yes | `idle_seconds`: seconds since the content last changed, as of `ts`. `0` for a parked or frozen placeholder. |
| `is_idle` | bool | yes | `is_idle`: `idle_seconds` above the session's idle threshold (agent panes only). `false` means *no verdict* on a placeholder. |
| `awaiting_input` | bool | yes | `awaiting_input`. |
| `awaiting_input_kind` | string | yes | `awaiting_input_kind`: the first matching prompt pattern's name, or `""`. Open string. |
| `agent_key` | string | yes | `agent_key`: the resolved agent (`claude`, `codex`, `opencode`), or `""`. |
| `scoped` | bool | yes | `scoped`: matching was narrowed to that agent's patterns. `false` means the kind came from the unscoped list. |
| `parked` | bool | yes | `parked`: a placeholder for a pane the producer deliberately did not capture. |
| `frozen` | bool | yes | `frozen`: a frozen agent's stand-in viewer. Takes precedence over `parked`. |
| `frozen_record_id` | string | yes | `frozen_record_id`: the store record id when `frozen`, else `""`. |
| `compare_mode` | enum | yes | Producer: `get_compare_mode(pane)` — `stripped` or `raw`. |
| `compare_override` | bool | yes | Producer: `is_compare_mode_overridden(pane)`. |
| `last_change` | seconds or null | yes | Producer: `get_last_change_wall(pane)` — wall clock of the last content change, or `null` if none was ever observed. |

<!-- schema:object pane -->
| Member | Type | Required | From `TmuxPaneInfo` |
|---|---|---|---|
| `window_index` | string | yes | `window_index` |
| `window_name` | string | yes | `window_name` |
| `pane_index` | string | yes | `pane_index` |
| `pane_id` | pane id | yes | `pane_id` |
| `pane_pid` | integer | yes | `pane_pid` |
| `current_command` | string | yes | `current_command` |
| `width` | integer | yes | `width` |
| `height` | integer | yes | `height` |
| `category` | enum | yes | `category.value` — `agent`, `tui` or `other` |
| `session_name` | string | yes | `session_name` |
| `shadow_target` | pane id or `""` | yes | `shadow_target`: on a shadow record, the followed pane id (equal to its key) |
| `history_size` | integer or null | yes | `history_size` |
| `frozen_record` | string | yes | `frozen_record` (`@aitask_frozen`) |
| `record_id` | string | yes | `record_id` (`@aitask_record`) |
| `standin_ready` | string | yes | `standin_ready` (`@aitask_standin_ready`) |
| `pane_dead` | bool | yes | `pane_dead` |

Not on the wire:

- `PaneSnapshot.timestamp` — it is process-local monotonic time. A receiver
  stamps its own when it converts a record (`pane_snapshot(record,
  timestamp=…)`).
- The `@aitask_monitor_kind` and scratchpad discovery columns — companion and
  scratchpad panes never reach a snapshot.

## Top-level members

- **`shadows`** — the producer's shadow snapshots (`get_shadow_snapshot`), keyed
  by the followed pane id; each record's `pane.shadow_target` equals its key.
- **`completed`** — sorted pane ids of AGENT panes whose task (resolved from the
  window name, `agent-(pick|qa|resume)-<id>`) is `Done` or already archived.
  Excluded are panes that are parked or frozen in their record, **and** panes
  whose `[session, window]` is in the global parked set even when another
  subscriber's pin had them captured live. That keeps the set identical for every
  client. This is the clients' `_compute_completed_panes` rule
  (`is_task_completed`), moved server-side.
- **`sessions`** — the session→project map (`get_session_to_project_mapping`):

<!-- schema:object session -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `project_root` | string | yes | The session's project root. |
| `project_name` | string | yes | The project's display name. |

- **`parked`** — the **global** parked set: `agent_marks.parked_session_windows`
  of the per-user marks store and the session→root map, as sorted
  `[session, window]` pairs. It is the same for every client.
- **`discovery`** — the producer's discovery facts of this generation. Clients
  use them to tell "the agent is gone" from "its capture failed this tick" (the
  mark purge and the minimonitor's own-agent check fail closed without them).

<!-- schema:object discovery -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `enumerated` | array of strings | yes | `last_enumerated_sessions()`: the sessions scanned this generation. Not the same as the keys of `sessions`. |
| `agents` | array of pairs | yes | `last_discovered_agents()`: `[session, window]` of every agent window listed, captured or not. |
| `windows` | array of windows | yes | `last_discovered_panes()`: every pane of every agent window, helper panes included. |

<!-- schema:object discovery.window -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `session` | string | yes | Session name. |
| `window` | string | yes | Window name. |
| `panes` | array of panes | yes | The window's panes, sorted by pane number. |

<!-- schema:object discovery.pane -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `id` | pane id | yes | Pane id. |
| `pid` | integer | yes | The pane's process id. |
| `dead` | bool | yes | `#{pane_dead}`. |

- **`control_state`** — `TmuxMonitor.control_state`: today one of `connected`,
  `reconnecting`, `fallback`, `stopped`. Open string; display it as given.

## Requests

Every request may carry an `id`. Each is answered with a `result` (or, for
`set_content`, a `snapshot`) or with an `error`.

<!-- schema:message set_content -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `id` | id | no | Echoed by the reply snapshot. |
| `content` | selection | yes | The new selection. Answered with a snapshot under it. |

<!-- schema:message set_pins -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `id` | id | no | Echoed by the result. |
| `pins` | pins | yes | This client's capture pins, replacing the previous ones. |

<!-- schema:message refresh -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `id` | id | no | Echoed by the result. |
| `panes` | array of pane ids | no | Panes to capture and commit now (the monitor's fast preview path). |
| `shadows` | array of pane ids | no | Followed pane ids whose shadow to refresh now. |

With neither member, a full tick runs now (the keypress refresh sites). With
them, single-pane classified captures and commits run. Either way the effects are
broadcast as a delta to every subscriber — there is one idle clock — and the
request is then answered with `result{request:"refresh", gen}`.

<!-- schema:message set_compare_mode -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `id` | id | no | Echoed by the result. |
| `pane` | pane id | yes | The pane. |
| `mode` | enum or null | yes | `stripped`, `raw`, or `null` to follow the default again. |

<!-- schema:message cycle_compare_mode -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `id` | id | no | Echoed by the result. |
| `pane` | pane id | yes | The pane. |

The compare-mode override is **shared**: the change is visible to every client,
in the pane record of the next delta.

<!-- schema:message capture -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `id` | id | no | Echoed by the result. |
| `pane` | pane id | yes | The pane to read. |
| `lines` | integer | yes | How many lines, `1 … 10000`. |

`capture` is a raw-ANSI **one-off read**: it does not touch the idle clock and
commits nothing.

### Results and errors

<!-- schema:message result -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `ts` | seconds | yes | Server wall clock. |
| `id` | id | no | The request's `id`. |
| `request` | string | yes | The request type this answers. |

Members per request, beyond those three:

<!-- schema:result set_pins -->
No further members.

<!-- schema:result refresh -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `gen` | integer | yes | The generation that carries the refresh's effects. |

<!-- schema:result set_compare_mode -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `mode` | enum | yes | The pane's effective compare mode now. |
| `following_default` | bool | yes | Whether it follows the default (no override). |

<!-- schema:result cycle_compare_mode -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `mode` | enum | yes | The pane's effective compare mode now. |
| `following_default` | bool | yes | Whether it follows the default (no override). |

<!-- schema:result capture -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `pane` | pane id | yes | The pane read. |
| `content` | string | yes | Its last `lines` lines, raw ANSI. |

<!-- schema:message error -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `ts` | seconds | yes | Server wall clock. |
| `id` | id | no | The failing request's `id`, when it had one. |
| `code` | string | yes | Error code (open string; below). |
| `message` | string | yes | Human-readable detail. |
| `request` | string | no | The failing request's type. |
| `server_proto` | integer | no | Sent with `proto_mismatch`. |
| `server_version` | string | no | Sent with `version_mismatch`. |

Error codes this version defines:

<!-- schema:list error-codes -->
- `bad_message`
- `too_long`
- `unknown_type`
- `proto_mismatch`
- `version_mismatch`
- `not_subscribed`
- `not_found`
- `unavailable`
- `internal`

`too_long`, `proto_mismatch` and `version_mismatch` close the connection; so
does any error before the handshake completes. The others keep it.

## Client-side settings

Four per-client settings were taken out of the producer (t2034_2). Each one has
a rule, and each rule has a consequence for this protocol.

| Setting | Rule | Protocol consequence |
|---|---|---|
| Own pane | The producer excludes nothing and never reads `$TMUX_PANE`. Each client drops its own pane with `client_view_snapshots(own_pane=…)`. | Never reaches the server. `hello.client.pane` is informational only. |
| Multi-session (`M`) | The producer always scans every aitasks session. `M` is client view state. | No session filter in `subscribe`; the client filters with `client_view_snapshots(home_session=…, multi_session=…)`. |
| Parked agents | *Which* agents are parked is global. *What* is still captured depends on every subscriber's capture **pins**: a minimonitor pins the agent it follows, and pins everything while its identity is unconfirmed. | Clients send pins (`subscribe.pins`, `set_pins`), never a skip set. The server computes the skip set itself: `parked_capture_skip(global parked set, [every subscriber's pins])`. The global set is in the stream as `parked`. |
| Compare-mode override | One shared per-pane setting owned by the producer, so there is one idle clock. | `set_compare_mode` / `cycle_compare_mode` act for everyone. Overrides are reaped by producer discovery only. |

- **Parked placeholders are substituted client-side.** A parked agent pinned by
  *another* subscriber arrives as a live record. Each client turns a live record
  of a parked agent it does not pin into the parked placeholder with
  `client_view_snapshots(parked_pairs=<parked>, pins=<own pins>)`. Frozen takes
  precedence over parked.
- **Single-pane routes project too.** Every write of a record into a client's
  view goes through the same projection as the bulk path — including the
  monitor's fast preview route (`_project_snapshots`), whose `refresh` result is
  live whenever another subscriber pins that agent.
- **Behaviour change of a shared compare mode.** `d` in one client, or applink's
  `cycle_compare_mode`, changes that pane's idle verdict for every client.
- **applink's own pane.** applink never marks its own pane, so on every
  cache-backed route it treats it as the cache miss it used to be: roster and
  explicit subscribe drop it, push and history skip it, `restart_task` answers
  `not_found`, `focus` answers `ok:false`, and kill takes the cache-miss route
  that still sweeps bound helpers. The key verbs are unaffected.

## Timing fields and parity comparisons

`ts`, `idle_seconds` and `last_change` are **timing fields**. They depend on
when a stream was produced, so parity comparisons — a Go server's stream against
the Python server's, or the Go monitor's goldens against the Textual twin's —
ignore them or compare them only for order. Everything else in a record is
expected to match exactly.

## Recording format

A recording is a `.jsonl` file. Line 1 is a header, a message type that exists
only in files:

<!-- schema:message recording -->
| Member | Type | Required | Meaning |
|---|---|---|---|
| `rev` | integer | yes | Recording format revision (`1`). |
| `proto` | integer | yes | Protocol major version of the stream. |
| `version` | string | yes | Framework `VERSION` of the server that produced it. |
| `source` | string | yes | Where it came from: `connect:<socket>`, `scenario:<name>`, … |
| `created` | seconds | yes | When it was recorded. |
| `note` | string | no | Free text. |

After the header comes the stream exactly as a subscriber received it: the
`welcome`, the `snapshot`, then the `delta` messages with contiguous `gen`. Every
line is a valid protocol message, so a conformance test in any language only has
to decode each line and apply it.

**A recording always carries full content.** It is recorded with
`content:"all"` and `include_shadows:true`, and every full record in it — the
snapshot's records and each first appearance of a pane or shadow in a delta —
carries `content`. That is what lets a replay subscriber select any pane later
and get its real terminal text. There is no restricted-selection recording: the
recorder has no content option, and both the recorder and `check` reject a full
record without `content`. Selection is purely a replay-subscriber concern.

## Recorder and replayer

`status_recording.py` is a module with a CLI (framework Python; stdlib only
beyond the codec):

```bash
python3 .aitask-scripts/monitor/status_recording.py check FILE
python3 .aitask-scripts/monitor/status_recording.py replay FILE --socket SOCK [--speed X] [--exit-at-end]
python3 .aitask-scripts/monitor/status_recording.py record --connect SOCK --out FILE [--duration S] [--max-deltas N]
```

**`check`** validates a recording: the order, every line, the version gates
below, the stream applied with contiguous `gen`, and the full-content rule. It
exits 0 and prints a summary, or exits 1 naming the first bad line.

**Version gates.** A recording is refused when its header's `rev` is not a
revision this codec reads, its `proto` is not one this codec speaks, or its
header does not describe its welcome (the welcome's `proto` and `version` must
equal the header's). The recorded *framework* version itself may be anything —
replaying an old recording is what a fixture is for.

**`record`** connects to a server, sends `hello` and
`subscribe{content:"all", include_shadows:true}`, and writes the header, the
`welcome`, the `snapshot` and every delta verbatim to `<out>.partial`.

- It holds the server to the handshake: a `welcome` whose `proto` is not the
  recorder's, or whose `version` is not the version the recorder sent, stops
  it. A live server answers for its own version, so only the right server
  passes; a replayer echoes the client's version, so a replayed recording of any
  framework version still records (its recorded version travels in
  `welcome.replay`).
- It stops on `--duration`, on `--max-deltas` (deltas counted **after** the
  snapshot, so a count stop can never fall before it), on EOF, or on
  cancellation.
- **Every stop path passes through one completion guard.** `<out>.partial` is
  promoted to `<out>` only if a `welcome` and then an initial `snapshot` were
  received and every delta applied cleanly. Otherwise the partial file is
  deleted, nothing is published, and the recorder reports
  `no usable recording captured: <reason>`; the CLI exits non-zero.
- A malformed line, a framing error, a stream gap, a full record without
  `content`, or any unexpected error stops it the same way — nothing is
  published after malformed input, whatever was captured before it. A
  server-initiated second snapshot ends the recording cleanly at that point.

**`replay`** serves a recording on a Unix socket (it refuses to replace an
existing path). It validates the **whole** recording before serving it — the
same checks as `check`, stream included, also for a `Recording` object handed to
`ReplayServer` directly — so a gap or a stale delta is refused at start-up, not
discovered by a waiting client. Should playback still fail, the connection gets
`error{code:"internal"}` and is closed.

- Each connection gets its own playback. The first `subscribe` sends the recorded
  snapshot (projected for that subscriber) and starts the deltas, paced by their
  `ts` differences divided by `--speed` (`0` = no waiting). The speed must be a
  finite number ≥ 0; anything else is refused at start-up, before the socket
  is opened.
- A repeated `subscribe` and every `set_content` answer with a snapshot of that
  connection's **current** reconstructed state and never restart playback (see
  [Initial and repeated subscription](#initial-and-repeated-subscription)).
- Replay is read-only: `refresh` and `set_pins` answer `result` and change
  nothing; `set_compare_mode` / `cycle_compare_mode` answer
  `error{code:"unavailable"}`; `capture` answers from the content of the
  reconstructed record whose `pane.pane_id` is the requested pane — an ordinary
  pane or a shadow (shadows are keyed by the followed pane, so they are matched
  on their own id).
- At the end of the recording the connection stays open, like a quiet server,
  unless `--exit-at-end` is given.

The tests record a replayed stream and require the result to equal the source.
They also record the status server's own stream, both in-process and against a
live tmux server, and require `check` to accept it.

## Fixtures

| Fixture | What it is |
|---|---|
| `tests/fixtures/monitor_status/basic.jsonl` | Synthetic: header, welcome, snapshot at gen 1, deltas to gen 6. |

**The committed fixture is synthetic.** It is generated by
`tests/lib/monitor_status_scenarios.py` (`basic_frames()`) from hand-built
`PaneSnapshot` frames, through the same `StreamEncoder` a server uses. It is
deterministic — a fixed clock (2026-01-01T00:00:00Z, 3 s ticks) and the fixed
version string `synthetic`, so a release bump never changes it — and
`tests/test_monitor_status_recording.py` regenerates it and requires the result
to be byte-identical to the committed file. Regenerate it only when the scenario
or the wire format changes on purpose:

```bash
python3 tests/lib/monitor_status_scenarios.py --write
```

Coverage of `basic.jsonl`:

| State | Where |
|---|---|
| Two sessions | `aitasks`, `aitasks_go` |
| Active pane | `%1` — new content and `history_size` every generation |
| Idle pane crossing the threshold, with a raw compare-mode override | `%2` |
| Awaiting input, four kinds | `%3` plan approval, `%4` a question (cleared mid-stream), `%5` a permission (`codex`, scoped), `%6` a question with `scoped=false` |
| Completed | `%7` from the start; `%4` from gen 5 |
| Shadow bound to a pane | `%12` → `%1`, appearing at gen 2 |
| TUI and OTHER panes | `%10`, `%11` |
| Parked placeholder and the global parked set | `%8` |
| Frozen stand-in | `%9` |
| Removal and appearance | `%7` removed at gen 5; `%13` appears at gen 4 |
| Control-state change | `reconnecting` at gen 3 |
| Discovery changes, a helper pane | `%12` and the companion `%14` in `agent-pick-101`'s window |

Pane content is prose-shaped, SGR-coloured text that names the state it stands
for. **It reproduces no dialog's line geometry.** A fixture that did would be
that dialog as far as captured text is concerned, and a pane displaying the file
would be flagged as awaiting input (see "A verbatim reproduction is
indistinguishable" in `monitor_idle_and_prompt_detection.md`). The recording
tests enforce it: every content string of every reconstructed state, and every
raw line of the file, is classified against every prompt pattern and must match
none, with a captured dialog as the negative control.

## Lifecycle and socket path

The Python server is `.aitask-scripts/monitor/status_server.py`:

```bash
python3 .aitask-scripts/monitor/status_server.py ensure [--version V] [--session S] [--grace G] [--deadline D]
python3 .aitask-scripts/monitor/status_server.py serve --socket SOCK [--lock-fd N] [--version V] [--tmux-socket-path P] [--session S] [--project-root R] [--grace G] [--interval I]
python3 .aitask-scripts/monitor/status_server.py path [--version V]
python3 .aitask-scripts/monitor/status_server.py restart [--version V] [--session S] [--deadline D] [--wait W]
python3 .aitask-scripts/monitor/status_server.py status
python3 .aitask-scripts/monitor/status_restart.py retire --all-keys --all-versions --owner-path P [--runtime-dir D] [--wait W]
```

`restart` and `status` are what `ait monitor --restart-server` and
`ait monitor --server-status` run; `status_restart.py retire` is the
`ait upgrade` hook's entry point. All three are described in
[Restart](#restart).

A client calls `ensure_server()`, or the `ensure` CLI. A client that gets
`UNAVAILABLE` falls back to its own in-process `TmuxMonitor`.

### Socket path

- **Directory.** `$XDG_RUNTIME_DIR/aitasks/` when `XDG_RUNTIME_DIR` names an
  existing directory, else `~/.aitask/run/`. It is created with mode 0700 and
  re-checked with `lstat`: it must be a real directory owned by the user, with no
  group or other bits. A directory the user owns with loose bits is tightened to
  0700. Anything else is refused (`unsafe_runtime_dir`).
- **Key.** The answering tmux server is asked for its own socket path
  (`list-sessions -F '#{socket_path}'`, through the gateway). Every way of naming
  a server therefore converges on one key: `-L`, `AITASKS_TMUX_SOCKET`,
  `TMUX_TMPDIR`, ambient `$TMUX`. The key is the first 16 hex digits of that
  path's SHA-256. When no tmux server answers, `ensure` reports
  `no_tmux_server`: there is nothing to monitor.
- **Version.** `VERSION` is used verbatim when it matches
  `[A-Za-z0-9._+-]{1,64}`. Otherwise it is `v` followed by 12 hex digits of its
  SHA-256.
- **Files.** In the directory:
  - `monitor-<key>-<version>.sock` — the socket, mode 0600;
  - `monitor-<key>-<version>.lock` — the lock;
  - `monitor-<key>-<version>.log` — the server's stderr, truncated at each
    start.

  A socket path longer than 103 bytes, the macOS `sun_path` limit, is refused
  (`socket_path_too_long`).

### The lock means "a server is alive"

An exclusive `flock` on the `.lock` file is held for the server's whole life.
`ensure` takes it first, then spawns the server with that lock file descriptor
inherited. The child shares the open file description, so the lock stays held
after `ensure` closes its own descriptor. Process exit releases it. Nothing ever
calls `LOCK_UN`: on a shared description that would release the server's lock
too.

So whoever holds the lock knows no server is alive. A leftover `.sock` is then
stale and is removed, but only after `lstat` shows it is a socket the user owns
(`unsafe_socket_path` otherwise). Double start is impossible. A hung but alive
server keeps its lock and is never replaced, and clients fall back in-process.
`serve` started by hand without `--lock-fd` takes the lock itself. It exits with
status 3 (`ALREADY_RUNNING`) when another server holds the lock or already
answers.

### `ensure`

`ensure_server()` is synchronous, for a client's worker thread. It returns one of
three states:

| State | Meaning |
|---|---|
| `RUNNING:<sock>\|<pid>` | A server answered a `hello` probe with this version. |
| `STARTED:<sock>\|<pid>` | This call started it. |
| `UNAVAILABLE:<reason>` | Fall back in-process. Reasons: `no_tmux_server`, `unsafe_runtime_dir`, `socket_path_too_long`, `lock_failed:<e>`, `lock_timeout`, `unsafe_socket_path`, `spawn_failed:<e>`, `server_failed:<last log line>`, `start_timeout`. |

The CLI prints exactly one of those lines and exits 0 or 1.

The steps:

1. Probe. A probe sends `hello` with `client.kind:"probe"` and never subscribes,
   so it never counts as a subscriber.
2. Take the lock non-blocking, retried for up to `--deadline` (default 10 s).
   Each retry probes again, because another caller may be starting the server.
3. With the lock held, remove a stale socket.
4. Spawn `serve` detached: `start_new_session`, so there is no controlling
   terminal, and stdio goes to the log.
5. Poll the probe every 50 ms until the server's `welcome` arrives. The server
   binds its socket before it starts the tmux control client, so readiness does
   not wait for the control channel.

A server still starting at the deadline is left running. If it comes up and
nobody subscribes, its idle grace ends it.

`serve` refuses to start when the tmux server it would talk to has a different
socket path from the one it was keyed under (`--tmux-socket-path`, exit 4).

### Ticks

- **Producer.** The server builds one `TmuxMonitor` with default config. Each
  tick publishes every session's project `tmux.monitor` config to it with
  `set_session_configs`, via `load_monitor_config` through the session→project
  map. Prefixes, TUI names, capture lines, idle threshold and compare default are
  therefore per session.
- **When ticks run.** Only while at least one connection is subscribed. With no
  subscriber the producer does not scan.
- **Interval.** Each mapped project contributes its `tmux.monitor.refresh_seconds`.
  The value counts when it is a finite number above 0; a missing or invalid value
  counts as 3, as in `ait monitor`. The interval is the minimum over the mapped
  projects, clamped to [1, 60] seconds, and 3 when nothing is mapped.
- **Full scans keep their cadence.** The schedule counts from the last **full**
  tick. A partial `refresh` commits a generation but discovers nothing, so a
  client refreshing one pane fast never postpones discovery of the rest.
- **Fresh snapshots.** A `subscribe`, first or resync, that arrives when the last
  full tick is older than one interval runs a tick first. The reply therefore
  describes the current state, not the state before an idle period. That tick's
  delta reaches an already subscribed connection under its **old** selection;
  the new selection applies from the reply snapshot on.
- **Serialization.** One producer lock serializes ticks, `refresh`,
  `set_compare_mode` / `cycle_compare_mode`, `set_pins`, and control-client
  restarts. A compare-mode change therefore lands strictly between two captures
  and never between a capture and its commit, so a compare-mode `result` can wait
  up to one tick. `capture` neither reserves a generation nor changes a capture
  input, so it does not take the lock.
- **Skip set.** The skip set, `parked_capture_skip` of the global parked set and
  every subscribed connection's pins, is republished before **every** capture:
  each tick and each partial `refresh`. It is also republished whenever pins
  change, including when a connection closes. A pin therefore takes effect on the
  next capture.
- **A failed tick** is logged and commits nothing, and `gen` does not advance.
  The next attempt waits one interval, so a persistent failure is retried at the
  tick cadence rather than in a loop. The server keeps running.
- **Oversized values.** A `refresh_seconds` integer of any size is compared as an
  integer, and capped at the 60 s clamp before conversion.

### Connections

- A connection that has not completed `hello` within 10 s gets
  `error{code:"bad_message"}` and is closed.
- `set_pins` before `subscribe` is stored. Pins count only once the connection
  subscribes.
- Each connection has one outbound queue, bounded at 128 messages. A subscriber
  that falls further behind is disconnected, and it reconnects and resyncs.

### Exit

A watchdog checks every 0.5 s. The server exits:

- **Idle.** No subscriber for the grace period: `--grace`, default 30 s, counted
  from start and from each time the last subscriber leaves.
- **Socket replaced.** The socket path no longer has the inode it bound, because
  someone removed or replaced it, so the server no longer owns the address. It
  exits without touching the new file.
- **`%exit`.** The control client saw `%exit`. tmux sends that both when the
  server goes away and when only the attached session is destroyed. Under
  `detach-on-destroy off`, destroying the attached session moves the client onto
  another session instead; the control client treats that `%session-changed` to
  a different session id the same way, so it never serves another session's
  panes. Either way the server probes the tmux server:
  - Gone, or answering with a different socket path → the server exits.
  - Still there → it was a session detach. The server restarts the control client
    on a live aitasks session, picked from a fresh session query (the last tick's
    mapping still lists the session that went away); with none, it stays on the
    subprocess fallback.
- **Signal.** SIGTERM or SIGINT. This is the exit [Restart](#restart) relies on:
  `ait monitor --restart-server` and the `ait upgrade` hook stop a server with
  SIGTERM.

On exit it closes every connection and the control client, then removes the
socket only if it still has the inode the server bound.

## Restart

A server keeps running the code it started with, and it is keyed on the tmux
server and `VERSION` only. A code change that leaves `VERSION` alone — any commit
in a development checkout — therefore never retires it, and it outlives every
change while one subscriber stays connected. Restarting it is an explicit act.

### The procedure

`.aitask-scripts/monitor/status_restart.py` stops the server of one socket. It
is stdlib-only (with `status_paths.py`), so it runs before the framework venv
can import `status_server.py`. Every outcome rests on evidence about the
server's **process**: socket silence and the lock are never used, because a
reconnecting client can take the lock for a fresh server while the procedure
runs.

1. **Find the process.** `ps -ww -eo pid=,args=` (`-ww`: args never truncated,
   on procps and BSD ps alike). The server is the one process whose args
   contain `serve --socket <sock>` as whole tokens. This process itself is
   excluded.
   - None, and nothing accepts on the socket → `STALE:<sock>`. Not a failure:
     `ensure` removes a stale socket under the lock.
   - None, but something accepts → `RETIRE_FAILED:<sock>|unverified`. Nothing
     is signalled.
   - More than one → `RETIRE_FAILED:<sock>|ambiguous_pids:<p1>,<p2>`. Nothing is
     signalled.
2. **Owner filter** (`--owner-path P`, the upgrade hook only). The token right
   before `serve` must be exactly `P`, after `realpath`, or the target prints
   `SKIPPED:<sock>|other_owner`. With an owner, an unverified socket prints
   `SKIPPED:<sock>|unverified` instead of failing.
3. **Re-read that pid's args** (`ps -ww -o args= -p <pid>`), then send SIGTERM.
4. **Wait** (5 s by default) until the pid is gone: no such process, or its args
   no longer match. A zombie reports `[name] <defunct>`, and a recycled pid runs
   something else, so both count as gone. An unreadable `ps` never does.
5. **Report** `RETIRED:<sock>|pid=<p>`, or
   `RETIRE_FAILED:<sock>|pid=<p>|still_running`. There is no SIGKILL: a server
   that ignores SIGTERM is reported, and is ended by hand.

On SIGTERM the server takes its ordinary exit (see [Exit](#exit)). Every client
then takes the loss path of [Modes](#modes): fallback, then a reconnect whose
first delay is 0. Its `ensure` starts a fresh server from the files on disk.
That includes a client started before the change, because the server script
it spawns is a path, not code in memory.

### Entry points

| Entry point | Targets | Then |
|---|---|---|
| `ait monitor --restart-server [--version V]` (`status_server.py restart`) | Only the **current** tmux server's socket for V (default: the installed `VERSION`). The runtime directory is shared by every tmux server; theirs are never touched. | V = the installed `VERSION`: `ensure_server(version=V)` in-process, then a probe of the replacement: `REPLACEMENT:<sock>\|pid=<p>\|version=<v>`. Any other V: retire only, `RETIRE_ONLY:<sock>\|version=<V>\|installed=<v>`, and no ensure — it would spawn this tree's `status_server.py` under V's key, and V's clients would accept it because the handshake compares only the version string. V's clients respawn the server from their own files on reconnect. A `RETIRE_FAILED` stops before either, because an ensure would reuse the server that did not stop. |
| `ait monitor --server-status` (`status_server.py status`) | Read-only: every socket of the current tmux server, any version. | `SERVER:<sock>\|pid=<p>\|started=<ps lstart>\|version=<slug>\|script=<argv path>`, or `NO_SERVER`. |
| `ait upgrade` (`install.sh` → `report_monitor_server_restart`) | Every socket at any tmux server and version whose verified process was started from **this project's** `status_server.py` (`--all-keys --all-versions --owner-path`, all mandatory on that CLI). | Nothing: clients respawn from the new files. Prints `MONITOR_SERVER:<line>` per server stopped or not stopped. `AIT_MONITOR_RESTART=0` opts out. |

The upgrade hook is owner-scoped for two reasons:
- install-flow tests run with a scratch `HOME` but the real `XDG_RUNTIME_DIR`;
- another project's servers still run that project's unchanged files.

`ait setup` replaces no framework code, so it has no hook.

### The contract for any server implementation

The procedure is a process contract, so it covers every implementation that
serves the socket. An implementation, the Go `ait-monitord` included, must:

| Requirement | Python server | Go `ait-monitord` |
|---|---|---|
| `serve --socket <sock>` adjacent in its argv | `<python> <tree>/.aitask-scripts/monitor/status_server.py serve --socket …` | `<binary> serve --socket …` |
| SIGTERM → the graceful exit above; process exit releases the lock | yes | required |
| The token before `serve` is its owner path | the script path (resolved) | the installed binary (`$AITASKS_HOME/engine/v<V>/ait-monitord`, or `engine/dev/`) |
| An update that replaces it runs the owner-scoped retire | `install.sh` | the engine install (`ait setup`, `ait upgrade`, `ait engine build`), with `--owner-path <binary>` |

No protocol message is involved.

### Limits

- Two trees at the same `VERSION` with different code share whichever server
  one of them started. A restart does not choose which tree starts the next
  one.
- Nothing detects that a server's code is out of date: after a commit that
  changes producer code, run `ait monitor --restart-server`.

## Python client

`.aitask-scripts/monitor/status_client.py` holds `MonitorClient`, the stand-in an
app uses in place of its `TmuxMonitor`. It wraps the `TmuxMonitor` the app
already builds (the *local* instance) and offers the same read surface. Its
`start_control_client()` / `close_control_client()` are the client's own start and
close, so an app's existing mount and unmount calls drive it.

### Modes

| Mode | Where reads come from | The local instance |
|---|---|---|
| `server` | The subscription (`StreamState`). | Action gateway only: no scan, no control client. |
| `fallback` | Delegated to the local instance: the in-process code. | The producer, with its own control client. |
| `replay` | A recording served by a `ReplayServer` on a temporary socket. | None. Actions raise `ReplayReadOnly`. |

`server` and `replay` are the *subscribed* modes. While the first attempt is still
`connecting`, async reads wait for its outcome, so an app's first refresh never
reads an empty state.

- **Starting.** `ensure_server()` runs in a worker thread with a short deadline
  (3 s by default). Any failure — `UNAVAILABLE`, a refused handshake
  (`version_mismatch`, `proto_mismatch`), an error reply, a malformed line, a
  timeout — means `fallback`.
- **`AITASKS_MONITOR_SERVER=0`** keeps the client in `fallback` for good. It
  never calls `ensure`.
- **Reconnect.** In `fallback` a reconnect loop calls `ensure` again, which starts
  a new server when the old one is gone. Its delays are 0, 0.5, 1, 2, 4, 8, 16 and
  then 30 s, repeating the last. When a server answers, the client subscribes,
  returns to `server` and closes the local control client.
- **Losing the server.** EOF, a protocol violation or framing error, a failed
  resync, or a failed `set_content` all go through one loss path, in this order:
  1. Fail every pending request.
  2. Close the socket.
  3. Release the seeded pane cache (below).
  4. Switch to `fallback` and start the local control client.
  5. Start the reconnect loop.

  A replay keeps its last state and reports the disconnect instead.
- **Liveness.** After 10 s with no server message the client sends `set_pins`
  with its current pins, as an idempotent ping. With no reply within 10 s the
  connection counts as lost. This detects a hung but alive server whatever the
  tick interval is.

### Requests and replies

Every request carries an integer `id`. The reader resolves it on a `result` or
an `error`, and on a `snapshot` with that `id`, because that is how
`subscribe` and `set_content` are answered. A reply snapshot is applied before
its request resolves, so a caller returns with the state already current.

One deadline covers the whole exchange: the write lock, the write, `drain()` (which
blocks under socket backpressure) and the reply. A stuck send therefore reaches the
same failure handling as a missing reply.

A request answered by a snapshot fails the connection when it gets an `error`
instead, or misses its deadline. The server may already have switched the
connection's selection: an unencodable reply arrives as `error{internal}` on a
connection that stays open. Fallback, reconnect and a clean resubscribe are then
the only way back to a known state.

**Gap recovery.** A delta that skips a generation starts a resync. That is an
ordinary `subscribe` request with its own deadline (10 s), sent from a task
other than the reader. The reader has to stay free to read the reply.

- Deltas that arrive before the reply snapshot are dropped, because the snapshot
  supersedes them.
- An `error` reply or a missed deadline is a lost connection. Ongoing traffic and
  successful pings never extend the drop window.
- The resync task keeps resubscribing for as long as a gap is pending. A gap that
  arrives right behind the reply snapshot finds the task still running, so the
  task, not a new one, sends the next `subscribe`. Every paused state therefore
  owns a live, bounded request.

### Connection setup and the local control client

- `start()` runs its work as a task the client owns. `close()` closes every socket
  still in its handshake, then cancels that task and the reconnect loop. A
  connection attempt that ends without being adopted, cancellation by `close()`
  included, closes its own socket.
- **A local control-client start is never cancelled.**
  `TmuxMonitor.start_control_client` runs `backend.start` in a worker thread. If
  the coroutine were cancelled at that point, it would never reach the
  stale-generation `backend.stop`, and the backend the thread goes on to start
  would stay live. Entering a subscribed mode, and `close()`, call
  `close_control_client()` instead. That bumps the generation, and each in-flight
  start retires its own backend when it finishes. `close()` waits up to 15 s for
  that.
- **Cancelling a caller never cancels the startup.** The startup task belongs to
  the client. The `start()` call that creates it awaits it through
  `asyncio.shield`, and every later `start()` only waits on the ready event. So a
  cancelled caller, the first one included, only stops waiting: the attempt still
  ends in a subscribed mode or in a fallback with its reconnect. Only `close()`
  cancels the startup. A client shared between several callers that can each be
  cancelled on their own (applink: one push loop per phone) is therefore safe
  with plain `start()`. Applink still calls the synchronous `start_detached()`
  from the owner of the client's lifetime, so the first attempt is already
  running before any push loop reads.

### Reads

- **`capture_all_async()` reads the current state.** It never asks the server to
  scan. `request_refresh(panes=…, shadows=…)` does that: the keypress refresh
  sites. The fast-preview pair `capture_pane_classified_async` /
  `refresh_shadow_snapshot` sends `refresh` with `panes` / `shadows` and returns
  the refreshed record.
- **Generations.** `capture_generation` is the client's own token. It is bumped
  by every capture call, every applied message and every mode switch. A capture
  payload whose token is no longer current commits `None`, which is the
  "superseded, skip" contract the apps already honour.
- **Projection stays with the app.** The client returns producer-equivalent,
  unprojected snapshots. `client_view_snapshots(…)` still applies. Its inputs
  are on the client: `parked_pairs()` (the stream's `parked` set while serving,
  empty otherwise) and `capture_pins` (this client's current pins).
- **One pane's idle verdict.** `status_snapshot(pane_id)` answers from the
  subscription in a subscribed mode, or `None` when the state does not hold the
  pane. In `fallback` and while connecting it is the local `capture_pane`. It
  is never a local capture while subscribed: the local instance does not scan
  there, so its idle clock has never seen the pane.
- **Compare mode.** `cycle_compare_mode_async` / `set_compare_mode_async` return
  the server's answer. The synchronous `cycle_compare_mode` / `set_compare_mode`
  send the request and return a prediction from the record, and the next delta
  carries the server's value.
- **Pins and content.** `set_capture_pins()` sends `set_pins` only when the pins
  changed, without waiting for the reply. `flush_pins()` waits, bounded by the
  request timeout, for that reply. Because the server handles one connection's
  requests in order and answers `set_pins` only after applying it, a request
  sent after `flush_pins()` returns runs under the new pins. Every
  (re)subscribe carries the current pins and selection.
  `set_parked_agents()` always goes to the local instance: the server computes
  its own skip set. `set_content()` is sent in both subscribed modes, replay
  included.

### The gateway's pane cache

The local instance's actions read its pane cache: the window collapse in
`kill_agent_pane_smart`, `switch_to_pane`, `get_running_tuis`, the
`capture_pane*` lookups. In a subscribed mode the client therefore seeds that
cache from the subscription's agent-facing panes after every applied message
(`TmuxMonitor.seed_pane_cache`). Shadows are never seeded.

**A subscribed mode never coexists with an in-flight local capture.** A fallback
capture still running when the server comes back would otherwise write its
discovery into the cache after the seed. So the client counts its in-flight local
captures, and entering a subscribed mode works like this:

1. New local captures are refused while the switch is pending. They answer as
   superseded, which the apps already skip.
2. The captures already running must drain, within 5 s. Past that deadline the
   attach is abandoned: the client stays in `fallback` and the reconnect loop
   retries.
3. The client then switches mode and seeds the cache, with no `await` between the
   two.

After the switch, the client checks again that it still owns the connection and
that the mode is unchanged. Retiring the local control client awaits, and the
server can drop during that await. In that case the attempt reports failure, so
the reconnect loop keeps retrying instead of exiting on a stale success.

The cache then holds only seeded entries. The client releases it, as
`seed_pane_cache({})`, when it leaves a subscribed mode and on close. It releases
only a cache the subscription owns. A reconnect that is lost while still in
`fallback` (for example, while waiting for local captures to drain) never seeded
the cache, so the fallback producer's discovery stays in place. That release
is required: `_clean_stale` picks stale ids from the last-content map, which a
seeded pane never entered, so it would never reap them. Until the first fallback
discovery the cache is empty, as on a cold in-process start. Cache-backed actions
then take their cache-miss route, which is the fail-safe one: a plain pane kill,
never a window collapse.

### Delegation

Names the client does not define are delegated to the local instance in
`fallback`. In `server` mode only the action gateway is delegated
(`GATEWAY_NAMES`): actions, raw-tail captures, `tmux_run` and the instance
config. Any other name raises `AttributeError`, instead of silently answering
from the empty local producer. `tests/test_monitor_client_surface.py` keeps the
list complete. It extracts every monitor attribute that monitor, minimonitor and
applink use, and requires each one to be served or allowlisted.

### Consumers: monitor and minimonitor

Both TUIs build their `TmuxMonitor` as before and wrap it with
`monitor_shared.build_monitor_client`.

- **Reads and scans.** The interval tick and the first refresh only read the
  subscription, so N clients cost one scan per server tick. A user action
  (refresh, kill, pick, a mark, `M`, `d`) also asks the server to scan. It does
  so from a coalesced `scan-refresh` worker, never on the App message pump,
  because the action's `call_later` callback runs inline on the queue that
  dispatches keys. A stalled server therefore never holds input. The monitor's
  one-column fast refresh (typing into the preview or shadow, re-attaching a
  scrolled column, `t`, Enter's delayed refresh) sends `refresh{panes|shadows}`,
  and it too runs in a worker, coalesced per column, keeping its pinned-pane,
  generation and focus-identity guards. That route is chosen for any client
  whatever its current mode. A decision made at scheduling time would go stale:
  a client in `fallback` can reconnect before a queued callback runs.
- **Order inside a scan round.** A scan round is one ordinary guarded refresh:
  1. resolve marks and, in the minimonitor, this tick's own-window identity;
  2. publish the skip set and the pins;
  3. `flush_pins()`;
  4. `request_refresh()`;
  5. read.

  So the scan runs under this tick's pins. A followed agent that is parked is
  captured live, and an unconfirmed identity scans under `CAPTURE_PIN_ALL`.
- **Pins** are published every tick, alongside the local skip set.
- **`d`** uses `cycle_compare_mode_async` in a worker and reports the server's
  answer.
- **In-process instances.** An explicit `--interval` (both TUIs) or `--lines`
  (monitor) keeps that instance in-process: the server applies each project's
  `project_config.yaml` and cannot honour a per-instance override.
  `AITASKS_MONITOR_SERVER=0` does the same for every instance.

### Consumers: applink

applink (`applink/server.py`) holds a subscription only while a phone streams.
The mobile wire protocol is unchanged.

- **Lifecycle.** The first connection that starts a push loop builds ONE
  `MonitorClient` (`kind: applink`, no shadows) over a fresh local
  `TmuxMonitor`, and starts it detached. Every phone's push loop and the
  router then read through it. When the last push loop stops, the client is
  detached first and then closed. The router goes back to the in-process
  `TmuxMonitor`, which serves verbs from a connection without a push loop and
  the first `subscribe`'s roster expansion. An idle applink therefore holds no
  subscription, and the server scans nothing on its behalf.
  - **Why a fresh local per client.** Closing a client releases its seeded
    pane cache and closes its local control client. Two lifetimes sharing one
    local could therefore undo each other.
- **Routing.**

  | Call | Served by |
  |---|---|
  | `pane_status` and content frames | the subscription |
  | the router's `restart_task` idle gate | `status_snapshot` |
  | roster expansion and pane lookups | the subscription |
  | actions (`send_keys`, kill, focus, `spawn_tui`) | the local gateway |
  | the per-frame cursor (`capture_cursor_async`) | the local gateway |
  | history pulls (`capture_pane_content_async`, applink's own depth bound) | the local gateway |

  applink sends no wire `capture`.
- **Refresh cadence.** The subscription moves on the server's tick (≥ 1 s), and
  a phone asks for its own cadence: 300 ms for the focused pane, and a
  `cadence_idle_ms` down to 500 ms, which is how a read-only client, without
  `focus`, asks for speed. So before each read, a push pass sends one batched
  `refresh{panes}`.
  - **Which panes.** Every content pane the subscription holds that is forced,
    or whose cadence is due since the pane's last refresh **attempt**. Attempts
    are timed separately from content sends, so an unchanged pane is captured
    once per cadence, not once per pass.
  - Status-only panes stay on the background tick.
  - The pass publishes the pins, then calls `flush_pins()`, then sends the
    refresh, then reads.
  - The push loop is per connection, so a stalled server delays only that
    phone's next push, never its request loop.
- **Pins.** applink pins the `(session, window)` of every pane that a phone,
  not paused, streams content for. A parked agent a phone watches is therefore
  captured live. The pins are republished after every routed frame (subscribe,
  pause, resume, focus) and on every connection removal, not only from push
  passes, which a pause or an empty roster never runs.
- **The parked view.** Both the push loop and the restart gate project through
  `client_view_snapshots(parked_pairs=client.parked_pairs(),
  pins=client.capture_pins)`. A parked agent that only another subscriber pins
  shows as parked to applink.
  - A parked placeholder (empty content) gets its `pane_status` but never a
    content frame.
  - Suppressing one invalidates that pane's content baseline and marks it for
    resync. The first live snapshot after it therefore goes out as a forced
    keyframe, even when its content is unchanged. A recovery keyframe requested
    meanwhile is not lost, and the phone never gets a delta against a baseline
    it may not hold.
- **`cycle_compare_mode`.** The router hands it to the transport as a deferred
  reply. A task awaits `cycle_compare_mode_async` and sends the `res` (or
  `err INTERNAL`) when the server answers, while the read loop handles the next
  frame. That `res` can therefore arrive after replies to later requests; the
  envelope pairs replies by `id`.
  - **The bound.** A connection may have at most `MAX_DEFERRED_PER_CONN` (4)
    deferred replies in flight. The check runs before a task is created, and an
    excess request is answered at once with `err INTERNAL`,
    `detail.reason: too_many_pending`. A slow or silent status server therefore
    never grows tasks or pending requests without bound, and ordinary input stays
    responsive.
- **In-process.** `AITASKS_MONITOR_SERVER=0` means no client at all: applink
  runs on its in-process `TmuxMonitor` exactly as it did before the status
  server existed.

## Python codec reference

`.aitask-scripts/monitor/status_protocol.py`:

| Name | What it does |
|---|---|
| `decode(line, direction=…)` / `encode(msg, direction=…)` | One line ⇄ one validated, normalized message (known members only). Directions: `CLIENT`, `SERVER`, `RECORDING`. |
| `validate(msg, direction=…)` | The schema check `decode` and `encode` share. |
| `read_line(reader)` | One complete line from an asyncio stream; `FramingError` past the reader's limit; `None` at EOF. |
| `ProtocolError`, `UnknownMessageType`, `FramingError`, `StreamError`, `StreamGap` | Errors; `.code` is the wire error code. |
| `pane_record(snap, …)` / `monitor_pane_record(monitor, snap)` / `pane_snapshot(record, timestamp=…)` | `PaneSnapshot` ⇄ record. `monitor_pane_record` reads compare mode, override and last change from a `TmuxMonitor`. |
| `sessions_member(mapping)` / `discovery_member(enumerated, agents, panes_by_window)` | Build those members from the producer's shapes. |
| `StreamFrame` | One generation's wire-shaped state. |
| `StreamEncoder` | Server side: `update(frame, ts=…)` → the next delta; `snapshot(…)` → the current state. Encodes full content. |
| `filter_message(msg, content=…, include_shadows=…)` | One subscriber's projection of a shared snapshot or delta. |
| `snapshot_message(frame, gen=…, ts=…, …)` | A snapshot of a frame for one subscriber. |
| `StreamState` | Client side: `apply(msg)` with the generation and patch rules; `snapshots()`, `shadow_snapshots()`, `completed`, `parked`, `sessions`, `discovery`, `control_state`. |

`tail_lines(content, lines)` is the `capture` tail rule (split on `\n` only),
shared by the replayer and the server.

`.aitask-scripts/monitor/status_recording.py`: `read_recording`,
`check_recording`, `record_connect`, `ReplayServer`, `replay_delays`, and the CLI
above.

`.aitask-scripts/monitor/status_server.py`:
- `ensure_server` / `EnsureResult`;
- `probe` / `probe_async`;
- `StatusServer`;
- `server_paths` / `runtime_dir` / `tmux_socket_path`;
- `ProjectConfigCache` / `tick_interval`;
- the CLI in [Lifecycle and socket path](#lifecycle-and-socket-path).

`.aitask-scripts/monitor/status_client.py`:
- `MonitorClient` and `ClientMode`;
- `GATEWAY_NAMES` / `READ_SURFACE_NAMES`;
- `ConnectionLost`, `RequestFailed`, `ReplayReadOnly`;
- `pins_to_wire`.

See [Python client](#python-client).

## Known limits

- The delta and patch semantics are proven encoder-to-state, against the
  replayer, and against the server's real producer on a live tmux server
  (content changes, a shadow binding, a pane appearing and one disappearing).
  The live proof covers one host and those transitions only.
- A partial `refresh` (`panes` / `shadows`) recaptures only the named panes. In
  the generation it commits, every other record keeps the values of its last
  capture, including `idle_seconds`, even though the message's `ts` is new.
- `idle_seconds` is as of the message's `ts`. Clients display it as given; this
  version defines no extrapolation between deltas.
- A shadow's content selection follows its followed pane id; there is no way to
  select a shadow's content without its followed pane's.
