---
priority: medium
effort: medium
depends: [t2034_2]
issue_type: feature
status: Ready
labels: [monitor, minimonitor, tmux]
anchor: 2034
created_at: 2026-10-16 08:01
updated_at: 2026-10-16 08:01
---

Define the wire protocol between the shared monitor status server and its
clients (see the parent task), with a Python codec and a stream
recorder/replayer. The recorded stream is also the parity fixture format for the
Go `ait monitor` port (aitasks_go#16): both its Textual and Go twins replay it.

## Starting proposal (refine during planning)

- Transport: Unix domain socket, newline-delimited JSON, one message per line.
  Not gRPC (a protobuf toolchain plus a grpcio dependency for Python clients),
  not WebSocket (nothing local needs it; applink stays the remote path).
- Handshake: `hello{proto, version, client_pane}` → `welcome{proto, version}`. A
  framework `VERSION` mismatch means the client is talking to the wrong server
  (servers are per version) and falls back to in-process scanning.
- `subscribe{sessions: "*" | [...], include_shadows}` → a full
  `snapshot{gen, panes, shadows, completed, sessions}`, then one
  `delta{gen, ...}` per tick. `gen` is monotonic (the same idea as
  `_capture_generation`); clients drop stale messages.
- Requests: `refresh_now` (the keypress-driven refresh sites), the parked-set and
  compare-mode messages per child 2's semantics, and `capture{pane, lines}` for
  one-off reads.
- Pane record: every `PaneSnapshot` field (`monitor/monitor_core.py:1354`) that
  clients read today, including `idle_seconds`, `is_idle`, `awaiting_input`,
  `awaiting_input_kind`, `agent_key` and `scoped`, plus task completion.
  `awaiting_input_kind` stays an open string, as on the applink wire
  (`aidocs/applink/protocol.md`, "Versioning").

## Deliverables

- Spec `aidocs/framework/monitor_status_protocol.md`, including child 2's
  settings semantics.
- Python codec with round-trip tests; unknown fields ignored, malformed lines
  rejected.
- A recorder that writes a live stream to a file and a replayer that serves one,
  usable by the parity demos. Commit at least one recorded fixture covering idle,
  active, several `awaiting_input_kind` values, completed, a shadow-bound pane
  and multiple sessions. Fixtures must not reproduce a real dialog's line
  geometry outside the prompt-detection tests (see "A verbatim reproduction is
  indistinguishable" in `aidocs/framework/monitor_idle_and_prompt_detection.md`).
- Once committed, send aitasks_go#16 a note naming the spec and fixture paths
  (`./ait note 16 --project aitasks_go --from <this task id> --text "..."`).
