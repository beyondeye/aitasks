---
Task: aitasks/t1009_manual_verification_applink_delta_engine_followup.md
Worktree: (none - profile fast, current branch)
Branch: main
Verification mode: autonomous
Created: 2026-06-17 17:00 IDT
---

# Manual Verification Auto-Execution: t1009

## Execution Log

### Preflight

- `./ait applink --smoke` exited 0.
- Runtime dependencies were present: `websockets`, `msgpack`, `segno`, `yaml`, `tmux`, `openssl`, and `setsid`.
- The protocol checks used `ait monitor --headless-for-applink --port <free-port> --no-qr`, which exercises the same AppLink server/router/pusher stack as `./ait applink` while exposing a script-readable pairing URL.

### Harness

- Created two disposable tmux sessions rooted in the repo and rendered deterministic pane contents with a FIFO-driven Python renderer to avoid shell echo pollution.
- Started the headless AppLink listener on port `57953`.
- Parsed the pairing URL, pinned TLS against `aitasks/metadata/applink_sessions/server.crt`, verified the printed fingerprint prefix `SRRljtVv_CM8...`, paired a scripted `websockets` client, and subscribed to panes `%25` and `%26`.
- Cleaned up the headless process and disposable tmux sessions at the end. Scratch path used during the passing run: `/tmp/ait_t1009_um4_dmju`.

### Item 1

- Item text: Start `./ait applink` and pair a scripted `python websockets` client; subscribe to a live tmux pane and decode a valid keyframe.
- Action run: `./ait applink --smoke`, then scripted TLS-pinned `websockets` pair + subscribe against the headless listener.
- Output: decoded keyframe `0x01` for pane `%25`; MessagePack body round-tripped; 12 rows observed.
- Verdict: pass.

### Item 2

- Item text: Type one line into the subscribed pane; confirm the next data frame is a delta carrying only changed rows and is much smaller than a keyframe.
- Action run: mutated row 2 in the FIFO renderer from `beta` to `beta-mutated`.
- Output: received delta `0x02`, changed rows `[1]`, frame size 35 bytes versus 94-byte full keyframe.
- Verdict: pass.

### Item 3

- Item text: Apply the delta over the prior keyframe, then request a fresh keyframe and compare row content.
- Action run: applied the decoded delta to an independent client buffer, then sent `request_keyframe`.
- Output: independent buffer matched the requested keyframe rows: `{0: 'alpha', 1: 'beta-mutated', 2: 'gamma', 3: 'delta'}`.
- Verdict: pass.

### Item 4

- Item text: Drop a delta client-side, request a keyframe, and confirm recovery without replay.
- Action run: changed row 3 to `gamma-dropped`, intentionally did not apply the received delta locally, then sent `request_keyframe`.
- Output: received recovery keyframe with `gamma-dropped` within the next refresh.
- Verdict: pass.

### Item 5

- Item text: Verify `prev_frame_id` chaining and mismatch-triggered recovery.
- Action run: inspected the delta after the first keyframe and the delta after a recovery keyframe.
- Output: first delta `prev_frame_id=1` matched prior keyframe `1`; second delta `prev_frame_id=3` matched prior recovery keyframe `3`; deliberate local mismatch requested a keyframe.
- Verdict: pass.

### Item 6

- Item text: Resize the desktop terminal hosting the pane; confirm `dim` then fresh `keyframe`.
- Action run: `tmux resize-window` resized the disposable pane session to `100x12`.
- Output: observed `dim` frame `0x05` followed by keyframe `0x01` with dims `[100, 12]`.
- Verdict: pass.

### Item 7

- Item text: Produce a changed row containing an OSC8 hyperlink and verify the delta sidecar offsets.
- Action run: rendered an OSC8 hyperlink row with URL `https://example.invalid/t1009`.
- Output: received delta rows `[1]` with `osc8={0: 'https://example.invalid/t1009'}` decoded using `strict_map_key=False`, confirming subset-relative integer map keys.
- Verdict: pass.

### Item 8

- Item text: Shrink pane content within fixed dimensions and confirm `[row_id, []]` clears removed row content.
- Action run: cleared a previously nonblank row in the renderer, applied the delta, then requested a keyframe.
- Output: delta contained the clear row, and the independent client converged to requested keyframe rows `{0: 'alpha', 1: 'LINK', 3: 'delta'}`.
- Verdict: pass.

### Item 9

- Item text: Confirm idle subscribed panes send no binary frames and focused panes update at fast cadence.
- Action run: drained the socket for an unchanged interval, focused pane `%25`, then mutated one row while pane `%26` remained unchanged.
- Output: zero binary frames during 1.1s idle drain; focused pane emitted a prompt delta; idle pane emitted zero data frames.
- Verdict: pass.

## Cleanup

- The harness terminated the headless listener process group.
- The harness killed the disposable tmux sessions.
- No production source files were changed.
