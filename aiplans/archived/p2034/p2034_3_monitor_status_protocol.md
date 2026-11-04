---
Task: t2034_3_monitor_status_protocol.md
Parent Task: aitasks/t2034_shared_monitor_status_server.md
Sibling Tasks: aitasks/t2034/t2034_6_monitor_classifier_crosscheck_python_go.md
Archived Sibling Plans: aiplans/archived/p2034/p2034_*_*.md
Base branch: main
Output branch: main
---

# t2034_3: monitor status protocol — spec, codec, recorder/replayer, fixture

## Context

Parent t2034 replaces per-instance tmux scanning (monitor, minimonitor, applink)
with one shared status server per (tmux server, framework `VERSION`). t2034_1
measured the payoff (≈0.9–1.0 core, mostly tmux-server dedup). t2034_2 made the
`TmuxMonitor` producer client-agnostic. This task defines the wire between that
server and its clients: the spec, a Python codec, a stream recorder/replayer, and
a committed fixture. Downstream consumers are t2037 (Python server + client +
migrations) and, cross-repo, aitasks_go#16_2 / #16_3 / #16_5 (the Go monitor
renders this stream and uses recorded streams as parity fixtures) and
aitasks_go#47 / #47_1 / #47_4 (the Go server must speak it).

Decisions settled with the user during planning:
- **Fixture source:** the committed fixture is **synthetic**. It is generated from a
  scripted scenario through the same stream encoder the server will use, so it is
  deterministic, and a test regenerates it and checks it is byte-identical. The
  recorder is a socket client that saves a server's stream. Until t2037 provides
  the server, the recorder is tested against the replayer. The spec says both
  things explicitly.
- **Content:** each client chooses which panes' content it receives
  (`content: "all" | "none" | [pane ids]`). Status metadata does not depend on the
  selection: every pane and every member except `content` is always sent. Changing
  the selection is answered with a fresh `snapshot`, so newly selected panes
  arrive with their current content.

Settled earlier by t2034_2 (per its note and archived plan), and carried into the
spec here:
- The client's own pane and the multi-session `M` filter never reach the server.
- Which agents are parked is global. Each client sends capture **pins**, and the
  server computes the capture skip set.
- Clients substitute the parked placeholder themselves; frozen takes precedence.
- The compare-mode override is one shared per-pane setting.
- applink's own pane is admitted only where the producer cache was never consulted.

Exploration facts the design rests on:
- `PaneSnapshot` (`monitor_core.py:1380`) and `TmuxPaneInfo` (`:1181`) have no
  serialization helpers today.
- `content` is raw ANSI: `capture-pane -p -e -S -200` plus the visible pane.
  `timestamp` is process-local monotonic time.
- Between them, clients read every PaneSnapshot field except `timestamp`, and
  every TmuxPaneInfo field except `shadow_target`, `record_id`, `standin_ready`
  and `pane_dead`. All of them are put on the wire anyway, for Go parity.
- Clients also read these, which therefore belong in the stream:
  - `get_compare_mode` / `is_compare_mode_overridden`
  - `get_last_change_wall`
  - `control_state`
  - shadows keyed by the followed pane (`get_shadow_snapshot`)
  - the completed set (computed client-side today: `_compute_completed_panes`
    plus `is_task_completed`)
  - the session→project map
  - discovery facts (`last_enumerated_sessions` / `last_discovered_agents` /
    `last_discovered_panes`). The mark purge and own-agent-gone detection depend
    on these and fail closed when they are absent (`monitor_shared.py:1409`,
    `minimonitor_app.py:4452`).
- The framework version comes from `lib/framework_version.read_installed_version`.
- Conventions to copy:
  - applink's additive versioning: `aidocs/applink/protocol.md` §Versioning.
  - `awaiting_input_kind` stays an open string:
    `monitor_idle_and_prompt_detection.md:394-400`.
  - The NDJSON style of `monitor/review_loop_log.py`: compact, `sort_keys`,
    tolerant reader.
  - The "verbatim reproduction is indistinguishable" rule:
    `monitor_idle_and_prompt_detection.md:122-127`.
- No record/replay or Unix-socket machinery exists yet.

## Protocol design (what the spec states)

**Transport and framing.**
- A Unix stream socket carries UTF-8 JSON, one object per line terminated by `\n`.
- Encoding is compact, with sorted keys and no NaN or Infinity. Duplicate member
  names are malformed.
- Line limits: 64 KiB client→server, 64 MiB server→client. Per-record `content`
  is capped at 4 MiB.
- Each connection is in order. The socket path and the lifecycle (lock, idle
  exit, stale socket) belong to t2037_1, which adds them to this same document.

**Envelope.**
- Every message has `type`.
- Client requests may carry `id` (a string ≤128 characters, or an integer
  0…2^53−1). `result`, `error` and a reply `snapshot` echo it.
- Every server message carries `ts`: wall-clock epoch seconds, rounded to ms.

**Versioning.**
- `proto` is an integer major version; this task defines `1`. `VERSION` equality
  is what makes a server "the right server".
- Additive changes do not bump `proto`: new optional members, new request types,
  new error codes, new open-string values.
- Open strings: `awaiting_input_kind`, `control_state`, error `code`.
- Closed enums, where a new value requires a `proto` bump: `category`
  (agent/tui/other) and `compare_mode` (stripped/raw).
- Unknown members are ignored at every level; the decoder drops them.
- Clients ignore unknown server message types. A server answers an unknown
  request type with `error{code:"unknown_type"}`.

**Malformed input.** A line is malformed if it:
- is not JSON, or is not an object;
- is missing `type` or a required member;
- has a member of the wrong type, where bool is not int and a float with a
  fraction is not int;
- has an out-of-range number or a bad pane id (`^%[0-9]{1,10}$`);
- has a bad enum value or an oversize list or string;
- has duplicate keys or is empty;
- is a message type that is invalid in its direction.

A malformed client line **within the size limit** gets `error{code:"bad_message"}`
and the connection is kept, as applink does. A malformed server line is a
protocol violation: the client disconnects and reconnects or falls back.

**Oversized lines are a framing error, not a malformed message.**
- A line longer than the receiver's limit (64 KiB client→server, 64 MiB
  server→client, the terminating `\n` not counted) cannot be re-framed safely.
- After the limit is crossed, the rest of that line, which may arrive in later
  fragments, would otherwise be parsed as a message of its own.
- So the receiver never tries to resynchronize within the stream:
  - a server sends `error{code:"too_long"}` and closes the connection;
  - a client closes the connection and reconnects or falls back.
- This holds whether the oversized line arrives in one write or in fragments.
- Requests that follow it on the same connection are never answered.
- An unterminated tail at EOF is discarded, never parsed: a message is complete
  only when its `\n` arrives.
- Implementation note for Python: `asyncio.StreamReader.readline()` raises
  `ValueError` at the limit and, for a fragmented line, clears the buffer
  mid-line. That clearing is exactly the desync this rule avoids, so the reader
  treats that `ValueError` as terminal.

**Handshake.**
- The client sends `hello{proto, version, client:{kind, pane?, pid?}}`.
- The server answers `welcome{proto, version, server:{impl, pid}}`, or
  `error{code:"proto_mismatch"|"version_mismatch", server_proto, server_version}`
  and then closes.
- A replayer echoes the client's `version` and adds
  `replay:{recorded_version, source}`.

**Subscription.**
- `subscribe{content?, include_shadows?, pins?}`. Defaults: `content` = `"all"`,
  `include_shadows` = `true`, `pins` = `[]`. There is no `sessions` member,
  because the `M` filter is client-side.
- The reply is `snapshot{gen, ts, id?, panes, shadows, completed, sessions, parked,
  discovery, control_state}`, with every member present.
- After that the server sends one `delta{gen, ts, panes?, removed?, shadows?,
  shadows_removed?, completed?, sessions?, parked?, discovery?, control_state?}`
  per producer commit: a tick, or a `refresh`. A delta is sent even when nothing
  changed, as a heartbeat that keeps `gen` contiguous.
- One message describes exactly one generation; all of its members are facts of
  that generation.
- **Initial vs repeated subscription.** The first `subscribe` on a connection
  starts that connection's one stream. A later `subscribe` on the same connection
  is a **resync**:
  - it changes `content` / `include_shadows` / `pins` if it carries them;
  - it is answered with a snapshot of the **current** state, meaning the state
    at the `gen` of the last delta already sent on this connection;
  - the one existing stream then continues from `gen + 1`;
  - it never starts a second stream, never replays history, and never rewinds.
  - `set_content` follows the same rule.
- **Ordering.** Each connection has exactly one ordered outbound sequence. A reply
  snapshot (to `subscribe` or `set_content`) goes into that sequence **between**
  two deltas:
  - every delta before it was encoded under the old selection;
  - its `gen` equals the last delta sent;
  - every delta after it is encoded under the new selection.
  - The server never interleaves a reply snapshot inside a delta, and never
    sends a delta whose `gen` is not the reply snapshot's `gen + 1`.
  - `result` / `error` replies go into the same sequence, so a
    `result{request:"refresh", gen}` always arrives after the delta that carries
    that `gen`.

**Generation rules.**
- A delta with `gen ≤ state.gen` is stale and dropped.
- `gen == state.gen + 1` applies.
- Any larger `gen` is a gap: the client sends `subscribe` again to get a fresh
  snapshot.
- A delta that arrives before any snapshot is an error.
- A snapshot replaces the client's state wholesale.

**Patches.**
- An entry in `panes` or `shadows` for an id the client does not hold must be a
  **full record**.
- For an id the client already holds, the entry is a **patch**: each member
  present replaces the stored member wholesale. `pane` is one member; there is no
  deep merge.
- `removed` and `shadows_removed` delete entries.
- The other top-level members, when present, replace the stored value wholesale.

**Content selection.**
- Selection affects **only** the `content` member of pane records and shadow
  records. A shadow's content follows its followed pane id.
- A record for an unselected pane has no `content`; clients treat it as `""`.
- `set_content{content}` replies with a fresh `snapshot` that uses the new
  selection.

**Pane record.** Members:
- `pane`: every `TmuxPaneInfo` field, with `category` as its enum value and
  `history_size` as int or null.
- `content`: raw ANSI; optional.
- `idle_seconds`, `is_idle`, `awaiting_input`, `awaiting_input_kind`, `agent_key`,
  `scoped`, `parked`, `frozen`, `frozen_record_id`.
- `compare_mode` and `compare_override`.
- `last_change`: wall epoch, or null.

Not on the wire:
- `timestamp`: the client stamps its own monotonic time when it converts a record.
- `@aitask_monitor_kind` and scratchpad columns, which never reach a snapshot.

**Top-level members.**
- `shadows`: followed pane id → shadow pane record.
- `completed`: sorted pane ids.
- `sessions`: `{name: {project_root, project_name}}`.
- `parked`: the sorted global `[session, window]` pairs.
- `discovery`: `{enumerated: [...], agents: [[s,w],...], windows: [{session, window,
  panes:[{id, pid, dead}]}]}`. These are the producer's same-generation discovery
  facts. `enumerated` lists the sessions scanned this tick, which is not the same
  as the session→project map in `sessions`.
- `control_state`: an open string; today one of connected / reconnecting /
  fallback / stopped.
- `completed` semantics: AGENT panes that are neither parked nor frozen, whose
  task (from the window name) is `Done` or archived. This is today's
  `_compute_completed_panes` rule, moved server-side.
- `gen` counts per server process. Each connection starts with a fresh client
  state, so a restarted server resetting `gen` does no harm. A selection change
  takes effect from its reply snapshot onward.

**Requests.** Each is answered with `result{id?, request, …}` or
`error{id?, code, message}`.
- `set_content{content}` → `snapshot`.
- `set_pins{pins: "all" | [[session, window], …]}` → `result`.
- `refresh{panes?, shadows?}`:
  - with neither member, a full tick runs now;
  - with them, single-pane classified captures and commits run (today's
    `_fast_preview_refresh` / `_fast_shadow_refresh`);
  - the effects are broadcast as a delta, then answered with
    `result{request:"refresh", gen}`.
- `set_compare_mode{pane, mode|null}` and `cycle_compare_mode{pane}` →
  `result{mode, following_default}`. The change is shared and visible to everyone
  in the next delta.
- `capture{pane, lines}` (1…10000) → `result{pane, content}`: a raw-ANSI one-off
  read that does **not** touch the idle clock.

Error codes:
- `bad_message`, `too_long`, `unknown_type`, `proto_mismatch`, `version_mismatch`
- `not_subscribed`, `not_found`, `unavailable`, `internal`

**Client-side settings** (the t2034_2 rows). The spec states:
- the rule for each row;
- the protocol consequence for each row;
- the behaviour change that a shared compare mode causes;
- that single-pane routes must project through `client_view_snapshots`;
- applink's own-pane admission rule.

**Timing fields.** `ts`, `idle_seconds` and `last_change` are timing fields.
Parity comparisons, such as aitasks_go#47_4's Go-vs-Python stream match and the
#16_5 goldens, ignore them, or compare them only for order.

**Recording format** (`.jsonl`). Line 1 is a file-only header:
`{"type":"recording","rev":1,"proto":1,"version":…,"source":…,"created":…,"note":…}`.

After the header comes the stream as a subscriber received it:
- `welcome`;
- `snapshot`;
- the `delta` messages, with contiguous `gen`.

**A recording always carries full content.**
- It is recorded with `content:"all"` and `include_shadows:true`.
- Every full record in it (the snapshot's records, and each first appearance of
  a pane or shadow in a delta) carries `content`.
- So a replay subscriber can later select any pane and get its real terminal
  text.
- There is no restricted-selection recording. The recorder has no content
  option. `check_recording` rejects a file whose full records lack `content`, and
  so does the recorder itself while it writes.
- Selection is purely a replay-subscriber concern: the replayer projects each
  outgoing message with `filter_message`.

Every line is a valid protocol message, so a Go conformance test only has to
decode each line and apply it. The recorder writes lines verbatim. The replayer
paces them by `ts` differences divided by `speed`.

## Steps

### Pre-phase (risk mitigations)
0. **[baseline_affected_tests]** Before editing, run the existing protocol-adjacent
   tests on the current tree and record any failures already present:
   - `tests/test_monitor_client_agnostic.py`
   - `tests/test_prompt_detection.py`
   - `tests/test_python_bootstrap_isolation.sh`

   Read-only: the tree carries another session's dirty sitrep files, including
   `monitor_shared.py`. Never stash or restore them.

### Main steps

1. **`aidocs/framework/monitor_status_protocol.md`** (new): the spec as designed
   above. Shape follows `tmux_gateway.md`: an H1, a purpose, "Read this when",
   "Read together with", then sections.
   - Transport, Envelope, Versioning, Malformed input, Handshake, Subscription and
     generations, Records (full member tables mapped to
     `PaneSnapshot` / `TmuxPaneInfo` fields), Top-level members, Requests,
     Client-side settings (t2034_2), Timing fields, Recording format,
     Recorder/replayer usage, Fixtures, Python codec reference, Known limits.
   - The **Fixtures** section states:
     - the committed fixture is synthetic, generated by `scenario_basic` through
       `StreamEncoder`;
     - live recording is tested against the replayer until t2037 provides the
       server;
     - the regeneration command;
     - a coverage table;
     - the verbatim-geometry rule, and the self-scan test that enforces it.
   - Lifecycle and socket path appear as a placeholder section owned by t2037_1
     (the parent's shape is restated: `$XDG_RUNTIME_DIR/aitasks/`, mode 0700).
   - Current-state prose only (`documentation_conventions.md`). Dialog labels are
     described in prose and never pasted.

2. **`.aitask-scripts/monitor/status_protocol.py`** (new; stdlib plus
   `monitor_core` dataclasses; no Textual). Imports use
   `try: from .monitor_core import … except ImportError: from monitor_core import …`
   (`monitor_core`'s own pattern).
   - Constants:
     - `PROTO = 1`, `RECORDING_REV = 1`;
     - the message-type names and the per-direction sets
       `CLIENT_TYPES` / `SERVER_TYPES` / `RECORDING_TYPES`;
     - the limits;
     - `ERROR_CODES`;
     - `CONTENT_ALL` / `CONTENT_NONE`, `PINS_ALL`.
   - Errors:
     - `ProtocolError(ValueError)` with a `.code` attribute;
     - `UnknownMessageType(ProtocolError)`;
     - `FramingError(ProtocolError)` (`code="too_long"`): terminal for a
       connection. `decode()` raises it for an over-limit line it is handed
       directly; the socket readers raise it through `read_line`;
     - `StreamError(ProtocolError)`, with subclass `StreamGap`.
   - Schema: declarative per-type member tables (`required` / `optional` plus a
     validator). Validators:
     - `_int` (rejects bool and fractional floats; takes bounds), `_num`
       (finite, ≥ 0), `_bool`, `_str(max)`, `_pane_id`, `_enum`, `_nullable`;
     - `_list_of` (with a cap), `_map_of`, `_pair`, `_selection`, `_pins`;
     - record and patch validators.
     - Results are validated per `request`.
   - `decode(line, *, direction, max_bytes=None) -> dict`:
     - checks the size before parsing;
     - uses `json.loads` with an `object_pairs_hook` that rejects duplicates and a
       `parse_constant` that rejects NaN/Infinity;
     - maps `RecursionError` to a `ProtocolError`;
     - validates, and returns a **normalized** dict holding known members only.
   - `encode(msg, *, direction) -> bytes`: validates, then
     `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False,
     allow_nan=False)`. On a `UnicodeEncodeError` it replaces lone surrogates with
     U+FFFD, then checks the size limit and appends `\n`.
   - Records:
     - `pane_record(snap, *, compare_mode=DEFAULT_COMPARE_MODE,
       compare_override=False, last_change=None, include_content=True) -> dict`.
       Floats are rounded to ms.
     - `monitor_pane_record(monitor, snap)` reads `get_compare_mode` /
       `is_compare_mode_overridden` / `get_last_change_wall`. This is the one
       place the producer-accessor names are mapped, for t2037_1.
     - `pane_snapshot(record, *, timestamp) -> PaneSnapshot` rebuilds
       `TmuxPaneInfo` / `PaneCategory`; a missing `content` becomes `""`.
   - `StreamFrame` (dataclass): the wire-shaped state, holding `panes`, `shadows`,
     `completed`, `sessions`, `parked`, `discovery` and `control_state`, with empty
     defaults.
   - Builders and filters:
     - `discovery_member(enumerated, agents, panes_by_window)` and
       `sessions_member(mapping, names)` build those members from the producer's
       shapes, sorted.
     - `snapshot_message(frame, *, gen, ts, content, include_shadows, id=None)`.
     - `filter_message(msg, *, content, include_shadows)` is the per-subscriber
       projection. It strips `content` from unselected records and patches, drops
       patches that become empty, and drops shadows when `include_shadows` is off.
       It never drops a delta.
   - `StreamEncoder` (server side):
     - `.gen`;
     - `.update(frame, *, ts) -> delta`: diffs against the last frame — new id →
       full record, changed members → patch, missing → removed — sorts lists,
       increments `gen`;
     - `.snapshot(*, ts, content, include_shadows, id=None)`.
   - `StreamState` (client side):
     - `.apply(msg) -> Applied | None`, where `Applied` holds `kind`, `changed`,
       `removed`, `shadows_changed`, `members_changed`, and `None` means a stale
       delta was dropped;
     - it enforces the generation rules and checks that a new id carries a full
       record;
     - `.snapshots(now)` and `.shadow_snapshots(now)` return `PaneSnapshot` dicts;
     - accessors for completed, sessions, parked, discovery and control_state.

3. **`.aitask-scripts/monitor/status_recording.py`** (new; stdlib asyncio plus
   `status_protocol`).
   - `read_line(reader, *, limit) -> bytes | None` is the one line reader that
     both sides use.
     - It wraps `readline()`. A `ValueError` (limit crossed, together or
       fragmented) becomes `FramingError(code="too_long")`.
     - An unterminated tail at EOF is returned as `None` (EOF) and never parsed.
     - Callers treat `FramingError` as terminal for the connection.
   - `read_recording(path) -> Recording(header, messages)`; `check_recording(path)`:
     - validates order;
     - decodes every line and applies it through `StreamState`;
     - **requires `content` on every full record** (the full-content contract);
     - returns a summary.
   - `async record_connect(socket_path, out_path, *, duration=None,
     max_deltas=None, source=None)`. There is **no content parameter**.
     - `max_deltas` counts deltas **after** the snapshot (`0` = snapshot only),
       so a count stop can never fall before the snapshot.
     - It sends `hello` (its version comes from `framework_version`), then
       `subscribe{content:"all", include_shadows:true}`.
     - It writes to `<out>.partial`: the header, then `welcome` / `snapshot` /
       `delta` lines verbatim. Any other message types are counted and skipped.
     - Each received line is validated, and it runs through a `StreamState`
       holding the full-content check.
     - A malformed line, a framing error, or a full record missing `content`
       stops the recording with an error and deletes `<out>.partial`.
     - **Completion guard: one function, `_finalize(…)`, through which every stop
       path passes** (duration elapsed, `max_deltas` reached, EOF, cancellation,
       error). It promotes `<out>.partial` to `<out>` **only if**:
       - a valid `welcome` was received;
       - a valid initial `snapshot` was received after it;
       - every delta written applied cleanly (contiguous `gen`, the full-content
         check).
     - Otherwise it deletes `<out>.partial`, publishes nothing, and reports
       `no usable recording captured: <reason>`. Typical reasons: stopped before
       the snapshot, EOF before the snapshot, cancelled before the snapshot.
     - The function returns a summary whose `published` flag says whether `<out>`
       exists. The CLI exits non-zero when it is false.
     - A cancellation after the snapshot is a clean stop and publishes what was
       recorded. The guard runs in a `finally` that re-raises the
       `CancelledError` after finalizing. No half-valid recording is ever left at
       `<out>`.
   - `replay_delays(messages, speed)`: a pure pacing function (speed 0 means no
     wait).
   - `ReplayServer(recording, socket_path, *, speed=1.0, exit_at_end=False,
     pacer=None)` uses `asyncio.start_unix_server`.
     - **Per-connection model.** Each connection has:
       - one playback cursor;
       - one full-content `StreamState` of what has been sent, advanced as each
         recorded delta goes out, unfiltered;
       - the current subscriber settings (`content`, `include_shadows`);
       - **one outbound writer**: an `asyncio.Queue` drained by one task. Every
         message (delta, reply snapshot, result, error) is serialized through it,
         in order.
     - The playback task is the only producer of deltas. Before each delta it
       awaits `pacer(index, delay)`, which defaults to `asyncio.sleep(delay)`.
       Tests inject a gate so playback can be held at an exact position.
     - Request handling:
       - `hello`: checks `proto`, echoes `version`, adds the replay marker.
       - The **first** `subscribe`: stores the settings, enqueues the recorded
         snapshot through `filter_message`, and starts playback.
       - A **repeated** `subscribe`, and every `set_content`:
         - updates the settings;
         - enqueues `snapshot_message` of the connection's reconstructed state at
           its current `gen`, filtered with the new settings;
         - never restarts or duplicates playback.
         - The request handler and the playback task share one lock, held across
           "read state + enqueue snapshot" and across "advance state + enqueue
           delta". So a reply snapshot always falls between two deltas, its
           `gen` equals the last delta enqueued, and the next delta is
           `gen + 1` under the new settings.
       - `set_pins` / `refresh`: answers `result` (a no-op).
       - Compare-mode requests: answers `error{code:"unavailable"}` (replay is
         read-only).
       - `capture`: answers with the tail of the reconstructed full-content
         record, or `not_found`.
       - A malformed line within the limit gets `bad_message` and the connection
         stays open. An unknown type gets `unknown_type`.
       - An oversized line (`FramingError`) gets `error{code:"too_long"}`, and the
         connection closes.
       - A request before `hello` gets an error, and the connection closes.
     - At the end of the recording the connection stays open (a quiet server)
       unless `exit_at_end` is set.
   - CLI (`argparse`; `if __name__ == "__main__"`; sys.path bootstrap as in
     `review_loop_log.py`): `record --connect SOCK --out FILE [--duration S]
     [--max-deltas N]` (no `--content`), `replay FILE --socket SOCK
     [--speed X] [--exit-at-end]`, `check FILE`. No `ait` dispatcher entry and no
     skill whitelist entries: it is not skill-invoked
     (`aitasks_extension_points.md` §365-374).

4. **`tests/lib/monitor_status_scenarios.py`** (new): `scenario_basic()` builds
   the per-tick `StreamFrame`s from synthetic `PaneSnapshot`s, with a fixed `ts`
   base, 3 s ticks, and the fixed version `"synthetic"` so a release bump never
   changes the fixture. `write_fixture(path)` writes the header, `welcome`, the
   tick-1 snapshot (content `"all"`) and the deltas for ticks 2…N. A `--write`
   flag in `main()` regenerates it.

   The scenario covers:
   - two sessions (`aitasks`, `aitasks_go`);
   - an active pane, whose content and `history_size` change on every tick;
   - an idle pane that crosses the threshold, flipping `is_idle`;
   - awaiting panes of kinds `claude_plan_approval`, `claude_askuserquestion`
     (cleared in a later tick), `codex_permission` (scoped) and
     `opencode_question` with `scoped=false` / `agent_key=""`;
   - a completed pane (`agent-pick-99`), and a second pane completed mid-stream;
   - a shadow bound to the active pane, appearing at tick 2;
   - a TUI pane and an OTHER pane;
   - a parked placeholder, with its global parked pair;
   - a frozen stand-in;
   - a raw compare-mode override;
   - an agent removed mid-stream and a new pane appearing;
   - a `control_state` blip (reconnecting → connected);
   - a discovery change.

   Content is synthetic, prose-shaped, SGR-coloured text (e.g.
   "fixture: plan approval requested (synthetic, not a dialog)"). It contains no
   dialog line geometry.

5. **`tests/fixtures/monitor_status/basic.jsonl`** (new, generated by step 4):
   about 8 lines.

6. **Tests** (new, unittest classes so both the pytest and unittest backends run
   them; `sys.path` bootstrap per `test_python_bootstrap_isolation.sh`):
   - **`tests/test_monitor_status_protocol.py`**:
     - **Round trip:** for every message type, `encode`→`decode` equals the
       normalized input and `decode`→`encode` is byte-stable.
     - **Record conversion:** `pane_record`↔`pane_snapshot` round-trips every
       field, including `history_size=None` and the parked and frozen
       placeholders (`_parked_snapshot` / `_frozen_snapshot`).
       `monitor_pane_record` is checked over a real `TmuxMonitor` after
       `set_compare_mode`.
     - **Unknown members** are dropped at the top level, in records, in `pane`
       and in results.
     - **Unknown type** raises `UnknownMessageType`.
     - **Open string:** a brand-new `awaiting_input_kind` value is accepted.
     - **Malformed table:** one case per rule in the spec, each raising a
       `ProtocolError` with the expected `code`.
     - **Direction:** a client sending `snapshot` is rejected; a `recording`
       header is accepted only for the file direction.
     - **Determinism:** the same frames produce byte-identical streams.
     - **Lone surrogates** are replaced.
     - **Encoder→state property test:** a seeded random walk of about 300 frames
       (add/remove panes and shadows, mutate members and content, change
       top-level members). `StreamState` reconstructs every frame exactly. With a
       `[ids]` selection it reconstructs the frame with content stripped from
       unselected panes, while every other member and every pane stays present.
       After `set_content`, the snapshot brings the newly selected content.
     - **Generation rules:** a stale delta is dropped, a gap raises `StreamGap`,
       a delta before a snapshot raises, a patch for an unknown id raises, and an
       empty delta is still applied (heartbeat).
   - **`tests/test_monitor_status_recording.py`**:
     - **Fixture:**
       - `check_recording` passes;
       - the order is header → welcome → snapshot → contiguous deltas;
       - the coverage assertions mirror the scenario list (at least 3 distinct
         awaiting kinds, a shadow, at least 2 sessions, a completed pane, idle and
         active panes, parked, frozen, a removal, `scoped=false`);
       - **golden:** regenerating it from `scenario_basic` is byte-identical to
         the committed file.
     - **Replayer** (temp dir from `tempfile.mkdtemp(dir="/tmp")`, which stays
       within AF_UNIX path limits; `speed=0`):
       - the handshake echoes the version and adds the replay marker;
       - `subscribe` yields the recorded snapshot and deltas;
       - `content:"none"` and `[id]` are honoured, with status members
         unaffected;
       - `set_content` returns a fresh snapshot carrying the content;
       - `capture` returns the tail;
       - `refresh` and `set_pins` return `result`;
       - `cycle_compare_mode` returns `unavailable`;
       - a proto mismatch returns an error and closes the connection;
       - a malformed line returns `bad_message` and the connection stays open;
       - an unknown type returns `unknown_type`.
     - **Mid-playback resync** (gated `pacer`, so playback is held at an exact
       position rather than finishing first, as `speed=0` can):
       - Release the snapshot plus 2 deltas, then hold. Send a repeated
         `subscribe`. The reply is a snapshot whose `gen` equals the last delta's
         and whose state equals the reconstructed state. It is **not** the
         recorded initial snapshot: the gen is greater and the state differs.
       - Release one more. The next message is exactly delta `gen + 1`. It applies
         cleanly to the reply snapshot, and no earlier delta is resent. The
         connection carries one playback sequence in total: count the deltas
         through the end.
       - Same shape for `set_content` mid-playback: hold, then
         `set_content{content:[%X]}` where `%X` was unselected. The reply snapshot
         carries `%X`'s current content and the same `gen`. Every later delta
         carries `%X` content patches, and nothing for other panes.
       - Ordering check: a `refresh` sent while playback is held answers `result`
         before the next delta. After release, deltas continue in order.
     - **Oversized request framing:** each case is followed by a **valid**
       request on the same connection:
       - a 64 KiB + 1 line written in one `write`;
       - the same line written in fragments (two writes with a drain and a yield
         between them, the newline only in the second);
       - an oversized line with **no** newline before EOF.

       Expect `error{code:"too_long"}`, then EOF, and the valid request is never
       answered. Neither a fragment tail nor the following request is ever parsed
       as a message. Control: a line exactly at the limit is accepted, and a
       malformed in-limit line keeps the connection open.
     - **`read_line` unit cases:** at the limit, over it, fragmented over it, and an
       unterminated tail at EOF (returns `None`).
     - **Recorder ↔ replayer:** `record_connect` against a `ReplayServer` produces
       a recording whose snapshot and deltas are identical to the source's, and
       `check` passes.
     - **Recorder content contract (entry point):**
       - `record_connect` has no content parameter: `inspect.signature` is
         checked, and the CLI rejects `--content`.
       - Against a stub socket server that captures the request, the recorder
         sends `subscribe{content:"all", include_shadows:true}`.
       - A stub server that answers with a snapshot whose record lacks `content`
         makes `record_connect` fail. Neither `<out>` nor `<out>.partial` is
         left behind.
     - **Recorder completion guard:** a stub server sends `welcome`, then holds
       the snapshot behind an event the test controls.
       - Each early stop, (a) `duration` elapsing, (b) cancelling the recorder
         task, and (c) the server closing (EOF), gives `published=False`, a
         `no usable recording captured` reason, and neither `<out>` nor
         `<out>.partial` on disk. Case (b) still propagates `CancelledError`.
       - Controls: release the snapshot, then stop by duration and separately by
         `max_deltas=0`. Both publish `<out>`, and `check_recording` passes on
         it.
       - Cancelling after the snapshot also publishes.
       - The CLI's `record` exits non-zero when nothing was published.
       - `check_recording` rejects a hand-edited copy of the fixture with one
         record's `content` removed.
     - **Pacing:** `replay_delays` is unit-tested.
     - **CLI:** `check` on the fixture exits 0; `check` on a corrupted copy
       exits non-zero.

7. **`CLAUDE.md`**: add one pointer in "TUI Development". Read
   `aidocs/framework/monitor_status_protocol.md` when editing
   `monitor/status_protocol.py` or `monitor/status_recording.py`, the recorded
   fixtures, or the monitor status server or client.

### Post-phase (risk mitigations)
8. **[fixture_prompt_self_scan]** In `tests/test_monitor_status_recording.py`,
   decode every pane and shadow record's `content` in the committed fixture, in
   every reconstructed state, and also take every raw file line. Run each through
   `monitor_core.classify_content` with `prompt_patterns.all_patterns()` and
   category AGENT, once with `agent=""` and once per `AGENT_KEYS` entry. Assert
   that nothing matches.

   Negative control: a line from `tests/review_loop_fixtures.py` (already
   committed, so no new copy is made) fed through the same helper **does** match.
   This proves the scan is live.

9. **[spec_codec_constants_pin]** In `tests/test_monitor_status_protocol.py`, a
   test that parses the spec's member tables and its error-code and enum lists out
   of `aidocs/framework/monitor_status_protocol.md`. It asserts they equal the
   codec's schema tables (`status_protocol` members per type and record,
   `ERROR_CODES`, the enum sets). The spec is what the Go codec will be written
   from, so drift between the doc and the Python codec would split the two
   implementations.

## Verification

- New tests: `bash tests/run_all_python_tests.sh --test-dir <scratch dir holding
  only the two new test files>`, or `python3 -m pytest
  tests/test_monitor_status_protocol.py tests/test_monitor_status_recording.py`.
- `bash tests/test_python_bootstrap_isolation.sh`: the new test files import in a
  clean interpreter.
- `bash tests/test_no_raw_tmux.sh`: the new modules call no tmux.
- Manual smoke: `python3 .aitask-scripts/monitor/status_recording.py check
  tests/fixtures/monitor_status/basic.jsonl`. Then `replay … --socket
  /tmp/x.sock --speed 0` in one shell and `record --connect /tmp/x.sock --out
  <scratch>/r.jsonl --max-deltas 6` in another, then `check` the result.
- Full suite: `set -o pipefail; bash tests/run_all_python_tests.sh`, reading only
  the final `PYTHON SUITE:` line. Failures already recorded by the step-0
  baseline are reported, not attributed to this change.

## Step 9 reference

1. Step 8: review, then commit only this task's paths by name. The tree holds
   another session's dirty sitrep files and staged renames. Use
   `git commit -F - -- <paths>`, and build from a temporary index if a shared
   file ever needs partial staging (none is planned: no file here is touched by
   that session). Commit message: `feature: … (t2034_3)`.
2. Step 8e: once the code commit exists, send cross-repo notes. First re-check
   the dependents by grepping `xdeps` for `2034_3` in aitasks_go. Then send one
   note each to aitasks_go#16 (the parent of #16_2/#16_3/#16_5) and #47
   (`--project aitasks_go --from 2034_3 --with-live`). Each note names:
   - the spec path;
   - `monitor/status_protocol.py` and `monitor/status_recording.py`;
   - `tests/fixtures/monitor_status/basic.jsonl`, noting it is synthetic;
   - the CLI;
   - the commit SHA.

   The notes are hedged as advisory. Optionally also note t2037 (the server
   reuses `StreamEncoder`, `filter_message` and `monitor_pane_record`; the
   lifecycle section of the spec is its job).
3. Step 9: archive on `main` (current-branch mode, no merge).

## Risk

### Code-health risk: low
- Additive only: three new modules/files plus a doc, a fixture and tests. No
  existing runtime path changes. The only shared file edited is `CLAUDE.md` (one
  pointer) · severity: low · → mitigation: none
- The working tree holds another session's dirty files, including
  `monitor_shared.py` and staged sitrep renames. A careless commit could sweep
  them in, or pre-existing failures could be misattributed to this change ·
  severity: low · → mitigation: inline pre-phase baseline_affected_tests
  (path-scoped commit per Step 9 reference)

### Goal-achievement risk: low
- The spec is the contract the Go codec (aitasks_go#47_1) and the Go client
  (#16_2) are written from. If the prose and the Python schema drift, the two
  implementations diverge silently · severity: low (residual — addressed by inline
  post-phase spec_codec_constants_pin) · → mitigation: inline post-phase
  spec_codec_constants_pin
- The committed fixture must not reproduce a real dialog's line geometry. A
  synthetic content string that happens to match a prompt pattern would flag
  panes on any host that displays the fixture · severity: low (residual —
  addressed by inline post-phase fixture_prompt_self_scan) · → mitigation: inline
  post-phase fixture_prompt_self_scan
- With a synthetic fixture and no server yet, the delta and patch semantics are
  proven only encoder-to-state, not against the real producer's tick-to-tick
  behaviour. t2037_1 / #47_4 may find that a producer behaviour (for example a
  pane missing for one tick after a failed capture) needs a spec clarification ·
  severity: low · → mitigation: TBD (accepted; the encoder diffs whatever the
  producer commits, and Known limits in the spec names it)

### Planned mitigations
- timing: pre-phase | name: baseline_affected_tests | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: pre-existing failures misattributed | desc: run protocol-adjacent tests on the current tree before editing and record failures that already exist
- timing: post-phase | name: fixture_prompt_self_scan | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: fixture content tripping prompt detection | desc: classify every fixture content string and raw line with all prompt patterns; assert no match, with a live-capture negative control
- timing: post-phase | name: spec_codec_constants_pin | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: spec/codec drift splitting the Go and Python implementations | desc: parse the spec's member, enum and error-code tables and assert they equal the codec's schema

## Post-Review Changes

### Change Request 1 (2026-11-04 10:40)
- **Requested by user:** six blocking findings, each verified against the code before it was fixed:
  - (1) `ReplayServer` served recordings that only `read_recording` had checked (a gen 1→4 jump was accepted), and a playback failure left the client waiting;
  - (2) recording `rev`/`proto` and header↔welcome consistency were not enforced, and the recorder accepted a welcome with a foreign proto or version;
  - (3) a 400-digit number reached `float()` and raised `OverflowError`, and the recorder then published the prefix it had captured;
  - (4) `capture` ignored shadow records, which are keyed by the followed pane;
  - (5) echoed error fields were unbounded, so a 65-character unknown type made the error reply itself fail to encode;
  - (6) error replies dropped a readable request `id`.
- **Changes made:**
  - (1) `ReplayServer.__init__` runs `check_recording` on every source, `Recording` objects included. Playback runs under a guard that sends `error{code:"internal"}` and closes the connection. A `closing` event stops the reader; the same event serves `exit_at_end`.
  - (2) `_check_versions` (rev, proto, welcome proto and version equal to the header's) runs in both `parse_recording` and `check_recording`. The recorder refuses a welcome whose proto is not its own, or whose version is not the one it sent; a replayer echoes the client's version, so the replay exception still holds.
  - (3) `_v_num` range-checks the exact value before converting. `validate()` turns any `OverflowError` / `RecursionError` / `ValueError` from a validator into a `ProtocolError`. The recorder treats any unexpected exception as an error, so it publishes nothing.
  - (4) `_record_by_pane_id` looks up pane records first, then shadows by their own `pane.pane_id`.
  - (5) `_send_error` caps `message` at 4096 characters and echoes `request` only when it is 64 characters or fewer. `UnknownMessageType` and the duplicate-key diagnostics are clipped.
  - (6) `ProtocolError` carries `request_id` / `request_type`, filled by `validate()` from a readable `id` / `type`. The replayer echoes both.
  - The spec documents each rule: error correlation and bounds, exact number range checks, recording version gates, validate-before-serve, the recorder's handshake gates, and shadow capture.
  - 14 regression tests were added.
  - In an isolated copy, reverting each fix on its own turns its test red (9 of 9). The original 9 mutants are still all caught.
- **Files affected:** `.aitask-scripts/monitor/status_protocol.py`, `.aitask-scripts/monitor/status_recording.py`, `aidocs/framework/monitor_status_protocol.md`, `tests/test_monitor_status_protocol.py`, `tests/test_monitor_status_recording.py`.

### Change Request 2 (2026-11-04 11:05)
- **Requested by user:** three low-severity findings. (1) The pane-id validators used `re.match` with `$`, which also accepts `"%1\n"` (in `shadow_target` too) — blocking. (2) The replay connection's reader started `read_line` and `closing.wait()` child tasks with no `finally`, so a server shutdown cancelled the connection and left them pending. (3) A negative or non-finite `--speed` started a server that then failed every subscriber. (2) and (3) were proposed as follow-ups; each was a few lines inside this task's own new code, so they were fixed inline instead of spawned.
- **Changes made:** (1) `_PANE_ID_RE.fullmatch` in `_v_pane_id` / `_v_shadow_target`. Regression rows cover a trailing or leading escaped newline, a non-ASCII digit, a selection id, `shadow_target`, and a map key. (2) `_ReplayConnection._next_line()` creates named child tasks, cancels them and awaits both in a `finally`; three server lifecycles in one loop leave no `replay-*` task pending. (3) `check_speed()` (finite, ≥ 0, not bool) is called by `ReplayServer.__init__`, `replay_delays` and the CLI `--speed` type, so a bad speed exits with status 2 before any socket exists. The spec now states the full-string pane-id rule and the speed rule. In an isolated copy, reverting each fix turns its test red (3/3).
- **Files affected:** `.aitask-scripts/monitor/status_protocol.py`, `.aitask-scripts/monitor/status_recording.py`, `aidocs/framework/monitor_status_protocol.md`, `tests/test_monitor_status_protocol.py`, `tests/test_monitor_status_recording.py`.

## Final Implementation Notes

- **Actual work done:**
  - **Spec** — `aidocs/framework/monitor_status_protocol.md`. Sections: transport and framing; envelope; versioning (closed and open enums); malformed input and oversized lines; handshake; subscription and generations (initial versus repeated subscribe, ordering, patches, content selection); records; top-level members; requests, results and errors; the t2034_2 client-side settings; timing fields; recording format; recorder and replayer; fixtures; a lifecycle placeholder owned by t2037_1; codec reference; known limits. Every member table carries a `<!-- schema:… -->` marker. `SpecPinTests` parses the tables and asserts they equal the codec's schema tables.
  - **Codec** — `.aitask-scripts/monitor/status_protocol.py`: `decode`/`encode`/`validate`, which return the normalized dict with unknown members dropped; `read_line`, the terminal framing rule; `pane_record` / `monitor_pane_record` / `pane_snapshot`; `StreamFrame`; `sessions_member` / `discovery_member`; `snapshot_message` / `filter_message`, the per-subscriber projection, where selection touches only `content`; `StreamEncoder`; `StreamState`. The error classes carry `code`, `request_id` and `request_type`.
  - **Recorder, replayer and checker** — `.aitask-scripts/monitor/status_recording.py`: `parse_recording` / `read_recording` / `check_recording`, with order, version gates, stream and full-content checks; `record_connect`, which has no content option, passes every stop through the `_finalize` guard and writes `<out>.partial` before promoting it; `ReplayServer`, which validates before serving, runs one playback per connection over a single outbound queue and lock, and treats a repeated subscribe or `set_content` as a resync of the current state; `replay_delays` / `check_speed`; the CLI verbs `check`, `replay` and `record`.
  - **Fixture** — the synthetic `basic.jsonl` (8 lines, gen 1–6), generated by `tests/lib/monitor_status_scenarios.py`.
  - **Tests** — `tests/test_monitor_status_protocol.py` (44) and `tests/test_monitor_status_recording.py` (53).
- **Deviations from plan:**
  - (1) The `CLAUDE.md` pointer (plan step 7) was **not** added. Another live session holds an uncommitted sitrep pointer in the same block of `CLAUDE.md`, and the user chose "skip it, follow-up task" (shared-file rule: gate before the edit). A follow-up task carries it.
  - (2) `read_line` lives in `status_protocol.py`, not `status_recording.py`, so the server and client tasks reuse it from the codec.
  - (3) The scenario functions are named `basic_frames()` / `render_basic()`; the plan said `scenario_basic`.
  - (4) `validate()` and `check_speed()` are public. `parse_recording()` exists alongside `read_recording()`.
  - (5) Two change requests from review (logged above) added the version gates, validate-before-serve, error correlation and bounds, exact number range checks, shadow capture, full-string pane-id matching, reader-task cleanup and speed validation.
- **Issues encountered:**
  - `asyncio.StreamReader.readline()` clears its buffer mid-line for a fragmented over-limit line. That is why framing is terminal: confirmed against `/usr/lib/python3.14/asyncio/streams.py`.
  - Integer members must reject every float (`1.0`, `1e2`), because a Go `int64` refuses them too.
  - `float()` of a 400-digit JSON integer overflows, so validators range-check the exact value first.
  - The working tree holds other sessions' uncommitted work in `CLAUDE.md`, `monitor_core.py` and `monitor_shared.py`, among others. This task touches none of them: all 7 of its files are new, and they are committed by path. To prove the new files stand alone, they were tested in a detached worktree at `HEAD` (97 passed).
  - The full Python suite in that worktree finished with 14 failures. 13 are identical with this task's files removed, so they are environmental to a fresh worktree; the 14th, `test_codebrowser_startup_focus`, passes 3 of 3 times serially, a load flake. The step-0 baseline recorded `test_python_bootstrap_isolation.sh` already failing on the same 5 files before any edit.
  - Mutation evidence, all in an isolated copy: 9 guard mutants, then 9 change-request-1 fix reversions, then 3 change-request-2 fix reversions. Every one turns its test red.
- **Key decisions:**
  - The fixture is synthetic, a user choice: deterministic, regenerated byte-identically by a test, self-scanned against every prompt pattern with a captured-dialog negative control.
  - Content selection is per client, also a user choice; status metadata never depends on it, and a selection change is answered with a fresh snapshot.
  - Deltas are sent on every commit, as a heartbeat that keeps `gen` contiguous.
  - Patches replace members wholesale, with no deep merge; `pane` is one member.
  - Shadows are keyed by the followed pane id.
  - A recording always carries full content.
  - The replayer echoes the client's version; the protocol, not the framework version, is what it gates on.
  - Error replies echo a readable `id` and `type`, bounded.
- **Upstream defects identified:**
  - `tests/test_python_bootstrap_isolation.sh:1 — fails before and after this task on 5 test files whose own sys.path bootstrap is incomplete (test_parallel_admission_vocab.py, test_prompt_detection.py, test_stats_backlog_panes_live.py, test_stats_focus_cycle_and_pane_selector_live.py, test_trails_app.py); they pass only because another module put the directory on sys.path first`
- **Notes for sibling tasks:**
  - **t2034_6 (classifier cross-check):**
    - The committed fixture's content is synthetic prose that matches **no** prompt pattern; it is deliberately not a classifier corpus. Its `awaiting_input_kind` values are asserted, not classified.
    - Use `tests/test_prompt_detection.py` / `tests/review_loop_fixtures.py` for corpus inputs. Use recorded live streams only once t2037 can record them, and keep them out of the repo unless redacted.
  - **t2037_1 (server):**
    - Reuse `StreamEncoder` (one per server, full content), `filter_message` per subscriber, `monitor_pane_record` (the producer-accessor mapping), `sessions_member` / `discovery_member`, `read_line` (set the reader `limit` to `MAX_CLIENT_LINE_BYTES`) and `decode` / `encode` with `direction=CLIENT` / `SERVER`.
    - Copy the replayer's per-connection pattern: one outbound queue drained by one writer task, and one lock held across "read state + enqueue". That ordering is what the spec's Ordering rule requires.
    - The server owns `completed` (`is_task_completed` over `TaskInfoCache`), the global `parked` set (`agent_marks.parked_session_windows`) and the skip set (`parked_capture_skip` over every subscriber's pins).
    - Fill in the spec's "Lifecycle and socket path" section.
    - A pane whose capture failed is simply absent from that generation (encoded as `removed`).
  - **t2037_2 (client / replay mode):**
    - `StreamState` is the client-side state. `Applied.changed` tells a renderer which cards changed.
    - Replay mode can start `ReplayServer` on a temp socket and connect normally. The fixture lives at `tests/fixtures/monitor_status/basic.jsonl`.
  - **aitasks_go#16 / #47:** each line of a recording is one protocol message. Decode with integer members strict (no fraction or exponent) and pane ids full-string. The member tables in the spec are authoritative and pinned to the Python schema.
