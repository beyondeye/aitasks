# AppLink Wire Protocol

How the `ait applink` TUI bridges a local `ait` workspace to a mobile companion app over a secure, versioned wire protocol.

## Overview

`ait applink` exposes `ait monitor`-style activity to a paired mobile device. The PC acts as the server, the phone (developed in the sibling repo `../aitasks_mobile`, Kotlin Multiplatform) as the client. This document defines the contract between the two so each side can be implemented independently.

Scope:

- **Transport** — which network protocol carries frames.
- **Envelope** — JSON shape of every frame.
- **Pairing** — how a phone bootstraps a session via QR.
- **Connection lifecycle** — the state machine both sides follow.
- **Versioning** — how the protocol evolves without breaking older clients.

Permission profiles (`read_only`, `monitor_control`, `full`) and per-verb gating live in [permissions.md](permissions.md).

Parent task: [t822](../../aitasks/t822_new_ait_bridge_tui.md). Sibling design doc covering the monitor port and command verbs: [monitor_port_design.md](monitor_port_design.md) (authored by t822_3).

## Transport choice

Three transports were evaluated. The **default** is LAN WebSocket; the other two are documented as deferred alternatives.

An SSH-based alternative ([charmbracelet/wish](https://github.com/charmbracelet/wish)) and the hosted-deployment topology are evaluated separately in [wish_ssh_evaluation.md](wish_ssh_evaluation.md). The conclusion there is that `wish` is a *complementary terminal-client access path* (and an excellent fit for hosted deployments), **not** a replacement for the native styled-span data plane this document and [content_transport.md](content_transport.md) define.

| Transport | Latency | Firewall resilience | Infra cost | Battery | Cross-network |
|-----------|---------|---------------------|------------|---------|---------------|
| **LAN WebSocket** (chosen) | ~5 ms | Same-LAN only | None | Lowest | No |
| Relay server | ~50–150 ms | High (works anywhere) | Hosted broker | Medium | Yes |
| WebRTC + signaling | ~10–50 ms | Medium (NAT/STUN may fail) | Signaling server | High (ICE keepalives) | Yes |

**Rationale for LAN WebSocket as v1 default:**

- **Zero infrastructure.** No broker to host, no STUN/TURN to operate.
- **Local-first.** Aligns with the framework's "all data is local files in git" philosophy.
- **Lowest battery cost.** Direct socket; no ICE candidate gathering, no relay heartbeats.
- **Sufficient for the v1 use case** (phone and PC on the same Wi-Fi network during a working session).

**Cross-network fallback (deferred):** When the PC and phone are on different networks, the user runs `ait applink` from a machine reachable on the LAN side and uses an external tunnel (e.g., `ssh -L`, `cloudflared`). A first-class relay-server transport may be added later — see "Versioning" for how to introduce it without breaking v1 clients.

**Security baseline:** all WebSocket traffic uses TLS (`wss://`). The server presents a self-signed certificate generated at first run; the cert fingerprint is embedded in the QR (see Pairing flow). The mobile client pins this fingerprint for the lifetime of the pairing.

## Message envelope

Every frame is a JSON object:

```json
{
  "v": 1,
  "id": "<req-id>",
  "kind": "req|res|push|err",
  "verb": "<name>",
  "payload": { ... },
  "auth": "<bearer-or-null>"
}
```

Field semantics:

| Field | Required | Description |
|-------|----------|-------------|
| `v` | yes | Protocol major version. v1 covers everything in this document. |
| `id` | yes | Caller-generated correlation token. Pair `res` and `err` frames to their originating `req`. |
| `kind` | yes | Frame type — see table below. |
| `verb` | yes | Action name (e.g., `pair`, `send_keys`, `snapshot`). The verb namespace is shared across `req`/`res`/`push`. |
| `payload` | varies | Verb-specific arguments or return data. May be omitted (or `null`) when empty. |
| `auth` | yes after pairing | Session bearer token. The pairing `req` is the only frame that may carry `null` here. |

Kind values:

| Kind | Direction | Meaning |
|------|-----------|---------|
| `req` | client → server | Action request expecting `res` or `err`. |
| `res` | server → client | Successful response to a `req` with matching `id`. |
| `push` | server → client | Unsolicited update (snapshots, state changes). `id` is server-generated; no `res` is expected. |
| `err` | server → client | Failed response to a `req`. Payload schema below. |

Error frame payload:

```json
{
  "code": "AUTH_FAILED|PERMISSION_DENIED|UNKNOWN_VERB|BAD_PAYLOAD|INTERNAL|NOT_IMPLEMENTED",
  "message": "<human-readable>",
  "detail": { ... }
}
```

`detail` is verb-specific and may be omitted.

## Pairing flow

The PC server is always-on (started by the user via `ait applink`). The phone bootstraps via QR:

1. **Server generates pairing token** — 256-bit random token `T = secrets.token_urlsafe(32)`. Stored in memory only; expires after a configurable TTL (default 5 minutes) if unused.
2. **Server computes its TLS-cert fingerprint** — SHA-256 of the self-signed cert's DER form, base64url-encoded. (Cert lifecycle and crypto-suite review are deferred — see "Out of scope".)
3. **TUI renders QR.** The QR encodes:
   ```
   applink://<lan-ip>:<port>/pair?t=<base64url(T)>&fp=<fp>&name=<urlencoded(hostname)>
   ```
   - `name` is OPTIONAL and additive. The TUI sets it to the URL-encoded
     PC hostname (e.g. `socket.gethostname()` / `hostnamectl --static`).
     Mobile clients use it as the default value for a user-editable PC
     label on the connection list. Older clients that ignore unknown
     query params are unaffected (per §Versioning rule for additive
     payload fields, applied here to the QR URL).
4. **Phone scans the QR**, parses `<lan-ip>`, `<port>`, `t`, `fp`, and (optionally) `name`. It opens a `wss://<lan-ip>:<port>/` connection, pinning the server's cert to `fp`.
5. **Phone sends pair request:**
   ```json
   {"v":1, "id":"p1", "kind":"req", "verb":"pair",
    "payload":{"token":"<T>", "device":{"name":"Pixel 8", "platform":"android"}},
    "auth": null}
   ```
6. **Server validates `T`**, generates a session bearer (256-bit random), and replies:
   ```json
   {"v":1, "id":"p1", "kind":"res", "verb":"pair",
    "payload":{"bearer":"<session-token>",
               "profile":"monitor_control",
               "expires_at":"2026-05-25T18:30:00Z"}}
   ```
   The TUI picks `profile` from a list configured by the user before showing the QR (see [permissions.md §Storage and selection](permissions.md#storage-and-selection)).
7. **Subsequent frames** from the phone carry `"auth": "<bearer>"`. Frames without a valid bearer get an `err` with `code: "AUTH_FAILED"` and the server closes the socket after a short grace period.
8. **Revoke.** The user revokes a session from the TUI (`r` keybinding). The server marks the bearer invalid; the next phone frame receives `AUTH_FAILED` and the socket is closed.

Pairing tokens are single-use: once consumed in step 6, `T` is invalidated even if the session is later revoked.

## Connection state machine

Both sides track the same state. Allowed transitions:

| From | To | Trigger |
|------|----|---------|
| Discovering | Pairing | Phone scans QR, opens socket |
| Pairing | Connected | `pair` req succeeds (step 6 of pairing) |
| Pairing | Disconnected | `pair` req fails or times out |
| Connected | Suspended | Socket closed by either side (e.g., phone screen off); bearer still valid |
| Suspended | Connected | Phone reconnects within bearer TTL; sends `resume` req with bearer |
| Connected | Disconnected | User revokes; bearer expires; explicit `bye` req |
| Suspended | Disconnected | Bearer expires while suspended |
| Disconnected | Discovering | TUI generates new QR (`r` keybinding) |

`Suspended` exists to allow mobile clients to survive backgrounding without re-pairing. The server retains the bearer and the last snapshot ID; the phone catches up by issuing a `snapshot` req on `resume`.

## Versioning

The `v` field is the protocol major version.

- **Bump `v`** when an existing verb's payload shape changes incompatibly, or when a previously required field is removed. The server MAY support multiple versions concurrently (`v: 1` and `v: 2` from different clients).
- **Do NOT bump `v`** for additive changes: new verbs, new optional payload fields, new error codes, new push kinds. Clients ignore fields they don't recognize.
- **Server advertises supported versions** in the `pair` response under `payload.supported_versions: [1]` (added in a future version; absent in v1 means `[1]` only).
- **Client picks the highest mutually-supported version** for subsequent frames. v1 clients ignore unknown `payload` keys in v1 responses.
- **Cross-network transports** (relay, WebRTC) plug in without a version bump — they share the same envelope and verb namespace; only the connect URI scheme differs.

## Pane content transport

Pane content (the streamed tmux output that drives the mobile render loop) does **not** flow through the JSON envelope above. It uses a parallel **binary data plane** over WebSocket binary frames, with its own schema, framing, delta strategy, and back-pressure rules. The full design is canonical in [content_transport.md](content_transport.md); the short summary:

- **Encoding:** per-line **styled spans** (text + fg/bg/attrs/width), packed in MessagePack. Server parses ANSI once; mobile never sees raw escape sequences and needs no VT parser.
- **Frame types:** `keyframe`, `delta`, `append`, `cursor`, `dim` — all final from day 1, all frame-independent (a keyframe alone is enough to render any state).
- **Subscription:** mobile sends a control-plane `subscribe` verb with the panes to follow, focused/idle cadences, and a forced-keyframe interval. An **empty or absent `panes` list means "all currently-discovered panes"** (the roster the server enumerates at subscribe time) — so a client can subscribe to everything without first learning pane ids. `focus` raises one pane's cadence; `request_keyframe` is the sole recovery path after a gap.
- **Bandwidth:** idle panes cost zero bytes; a focused busy pane stays under ~1 KB per refresh at 4 Hz after `permessage-deflate`.
- **Staged rollout, fixed format:** Stage 1 ships keyframes only; Stages 2-5 add delta, append fast-path, viewport clipping, and history RPC. No `v` bump across stages — additive per the [Versioning](#versioning) rules.

The data plane is gated by the same permission profiles defined in [permissions.md](permissions.md): the `snapshot` push (i.e. all data-plane frames) is allowed in every profile; `subscribe` / `focus` / `request_keyframe` are control verbs gated identically.

## Roadmap to cross-network

v1 is LAN-only, but the design is deliberately staged so each subsequent phase reuses the parts that took the most thought (envelope, pairing, verbs, permissions) and only swaps the connectivity layer. The four phases:

| Phase | Connectivity | Who hosts | New protocol work |
|-------|--------------|-----------|-------------------|
| **1. LAN WebSocket** (v1, this document) | Same Wi-Fi only | Nobody (PC is server) | Full envelope, pairing, state machine, permissions |
| **2. Tunnel escape hatch** | Anywhere reachable by user-owned tunnel (`ssh -L`, `cloudflared`, Tailscale, ZeroTier) | User | **None.** The phone connects to a tunnel endpoint exactly as if it were a LAN host. Documented as a `how-to`, not a protocol change. |
| **3. First-party relay** | Anywhere with internet | Hosted broker (we ship a self-hostable reference impl) | QR scheme + outbound-socket model; relay-broker pinning replaces direct cert pinning |
| **4. P2P via signaling** (optional) | Anywhere NAT allows | Relay used as signaling only; frames flow P2P over WebRTC datagrams | Same envelope wrapped in WebRTC data channels; ICE/STUN/TURN config |

### What carries forward unchanged

These are designed to be transport-independent in v1 and remain identical across all four phases:

- `## Message envelope` — same JSON shape; same `kind`/`verb`/`auth`/`id` semantics.
- `## Pairing flow` — token T + bearer model. The QR payload contents change between phases (see below), but the *flow* (server issues T, mobile redeems T for a bearer, subsequent frames carry the bearer) does not.
- `## Connection state machine` — `Discovering → Pairing → Connected → Suspended → Disconnected` transitions are transport-agnostic. `Suspended → Connected` reconnect logic generalizes to relay reconnects and WebRTC ICE-restart.
- `## Versioning` — the `v` field already covers additive cross-network changes without a version bump (see "Cross-network transports plug in without a version bump" in §Versioning).
- All command verbs and permission profiles (see [permissions.md](permissions.md)) — gating is on the verb, not the transport.

### What changes per phase

| Concern | Phase 1 (LAN) | Phase 2 (tunnel) | Phase 3 (relay) | Phase 4 (WebRTC) |
|---------|---------------|------------------|-----------------|------------------|
| QR URI scheme | `applink://<lan-ip>:<port>/pair?t=...&fp=...` | Same scheme; `<lan-ip>:<port>` is a tunnel endpoint | `applink://<broker-host>/r/<session-id>?t=...` | Phase 3 URI + an `ice=` parameter listing STUN/TURN endpoints |
| Server-side socket | Inbound (PC listens) | Inbound via tunnel | **Outbound** (PC dials broker) | Outbound to broker for signaling; P2P thereafter |
| TLS trust | Self-signed cert + fingerprint pinning | Inherits tunnel's trust model (often user's CA / Tailscale identity) | Broker uses a real CA cert; **end-to-end key exchange** added on top (broker is not trusted with frame contents) | Same as Phase 3 for signaling; DTLS-SRTP for the data channel |
| Discovery | LAN IP detected by server | User-typed or copy-pasted from tunnel UI | Broker assigns session ID at QR-generation time | Phase 3 mechanism |
| Failure modes | Wi-Fi drops | Tunnel daemon down | Broker unreachable / banned IP | ICE failure (fall back to relayed mode through TURN) |

### Why ship Phase 1 first

- **Zero infra to validate the design.** Envelope, pairing, verb gating, permission profiles, and state-machine transitions can all be exercised end-to-end before we commit to operating a broker.
- **Permanent offline fallback.** Even after Phase 3 ships, Phase 1 remains useful when the broker is down, the user is on an air-gapped network, or corporate firewalls block egress to our broker host.
- **Tunnel users get cross-network for free** in Phase 2 — many devs already run Tailscale / `cloudflared` and need no further work from us.
- **Phase 3 design is unblocked but not started.** The relay is the larger investment (hosting, abuse mitigation, ToS, end-to-end key exchange spec) and can begin once Phase 1 has shaken out the verb/gating decisions.

The relay design itself (broker dial protocol, session-ID issuance, end-to-end key exchange replacing direct fingerprint pinning, broker pricing/hosting) is **deferred to a future design task** — to be created after the Phase 1 implementation has landed and we have real usage to inform the broker contract.

## Out of scope (this document)

- Cryptographic primitive review — TLS suite selection, cert rotation, bearer-token entropy audit are deferred to a follow-up security task.
- Mobile-side bindings — lives in `../aitasks_mobile`; the user mirrors a matching task there manually after this PR lands.
- Concrete verb inventory — the canonical list of `monitor`-derived verbs (e.g., `send_keys`, `kill_pane`, `spawn_tui`) and their payload schemas are authored by sibling task t822_3 in [monitor_port_design.md](monitor_port_design.md). This document fixes the envelope and lifecycle only.
- Implementation — see follow-up tasks spawned after t822_2 lands the TUI skeleton.
