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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2034_1** id=2026-11-03T15:15:43Z.19a9094cdd91cf8b3723d289 from=t2034_1 at=2026-11-03T15:15:43Z base=6930f54e25e74a1e92e01e7fab1a8c1cbbcf2914 base_branch=main dirty=yes host=omg16
>
> | Cross-repo dependents of this task (aitasks_go, as of 2026-11-03), checked by
> | reading their xdeps:
> | - aitasks_go#16_2 monitor_app_shell — xdeps [2034_3]; renders from "the shared monitor
> |   status server's snapshot stream (protocol: aitasks#2034_3)".
> | - aitasks_go#47 / #47_1 go_monitor_status_server — xdeps [2037, t2034_3].
> | - aitasks_go#16 (Go monitor port) uses the recorded protocol stream as its parity
> |   fixture (per the t2034 parent description).
> | 
> | What reaches them automatically: only this task's Done status (aitasks_go `ait ls`
> | reads it live through the project registry). Content does NOT: aitasks_go planning
> | reads sibling context from its own repo only, and nothing reads this repo's
> | archived plans. Their bodies cannot yet know where the spec, codec and recorder
> | fixtures will live.
> | 
> | Suggested handoff at completion (Step 8e of this task): one cross-repo note per
> | dependent, with the protocol spec path, codec module path, recorded-stream
> | fixture path(s) and the commit that holds them, e.g.
> |   ./ait note 16_2 --project aitasks_go --from 2034_3 --with-live --file - <<'EOF' ... EOF
> |   ./ait note 47   --project aitasks_go --from 2034_3 --with-live --file - <<'EOF' ... EOF
> | Re-check the dependent list first (grep xdeps in aitasks_go), since it may have
> | changed since this note was written.
