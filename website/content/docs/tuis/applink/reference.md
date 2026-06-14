---
title: "Reference"
linkTitle: "Reference"
weight: 30
description: "Keybindings, screens, and implementation notes for ait applink"
---

## Keybindings

| Key | Action |
|-----|--------|
| `r` | Regenerate the pairing token (Pairing screen) |
| `s` | Show the Devices screen (from Pairing) |
| `x` | Revoke the highlighted device (Devices screen) |
| `p` | Show the Pairing screen (from Devices) |
| `j` | Open the TUI switcher modal |
| `q` | Quit |

## Screens

### Pairing

- Generates a one-time 256-bit token via `secrets.token_urlsafe(32)`.
- Detects the LAN IPv4 and builds the URI per
  `aidocs/applink/protocol.md` §Pairing flow.
- Embeds the server's TLS-certificate fingerprint (SHA-256 of the DER cert,
  base64url) so the mobile client can pin it at pairing time.
- Renders the URI as a QR code using `segno`, displayed with half-block
  Unicode for compact terminal output. The raw URI is not shown on screen
  to avoid leaking the pairing token to bystanders.

### Regenerate semantics

`r` rotates only the *unused* pairing token. Devices that have already
paired carry their long-lived bearer and keep their connection IDs across
a regenerate action. To deliberately disconnect a device, revoke it from
the Devices screen (below) — regenerating a QR never drops live sessions.

### Devices

Lists every paired device, one row per bearer session, with its
name/model, platform, connection state (Connected / Suspended), pairing
time, last-seen age, and coarse location when the device supplies one.
Press `x` to revoke the highlighted device: its bearer is invalidated and
any live socket is closed immediately. The list refreshes automatically.

## Listener

On launch the TUI starts a `wss://` WebSocket server (TLS via a persistent
self-signed certificate generated on first run). It accepts the `pair`
verb, issues a session bearer under the selected permission profile, and
routes subsequent command verbs into the shared monitor core, gating each
verb against the session's profile. See `aidocs/applink/protocol.md` for
the envelope and pairing flow, `aidocs/applink/permissions.md` for the
permission profiles, and `aidocs/applink/monitor_port_design.md` for the
command-verb inventory.

Permission profiles live in `aitasks/metadata/applink_profiles/*.yaml`
(`read_only`, `monitor_control`, `full`). Validate a profile with:

```
./.aitask-scripts/aitask_applink_validate_profile.sh <profile.yaml>
```

Per-device bearer sessions and the TLS certificate are stored under
`aitasks/metadata/applink_sessions/` (gitignored, per machine).

## URI grammar

```
applink://<lan-ip>:<port>/pair?t=<base64url(token)>&fp=<fingerprint>[&name=<urlencoded(hostname)>]
```

See `aidocs/applink/protocol.md` for the canonical definition, including
the JSON envelope, version handshake rules, and the connection state
machine.

## Python module layout

```
.aitask-scripts/applink/
├── __init__.py
├── applink_app.py      # Textual App + Pairing/Devices screens + runtime
├── server.py           # wss:// WebSocket transport + connection lifecycle
├── router.py           # pure frame router: parse, auth, gate, dispatch
├── sessions.py         # pairing tokens + bearer session table (persisted)
├── profiles.py         # permission-profile loading + verb gating
├── tls.py              # self-signed cert, fingerprint, SSL context
├── pairing.py          # token, IP detection, URI builder
├── paths.py            # runtime/profile path resolution
└── qr_widget.py        # TerminalQR(Static) — compact half-block renderer
```

## Dependencies

- `textual>=8.2.7,<9`
- `segno>=1.5,<2` (chosen over `qrcode` for built-in Micro QR support)
- `websockets>=12,<17` (WebSocket transport)
- `openssl` (system binary; generates the self-signed TLS certificate)

The Python packages are installed by `ait setup`.
