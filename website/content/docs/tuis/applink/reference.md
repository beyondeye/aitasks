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
| `s` | Show the Status screen (from Pairing) |
| `p` | Show the Pairing screen (from Status) |
| `j` | Open the TUI switcher modal |
| `q` | Quit |

## Screens

### Pairing

- Generates a one-time 256-bit token via `secrets.token_urlsafe(32)`.
- Detects the LAN IPv4 and builds the URI per
  `aidocs/applink/protocol.md` §Pairing flow.
- Renders the URI as a QR code using `segno`, displayed with half-block
  Unicode for compact terminal output. The raw URI is not shown on screen
  to avoid leaking the pairing token to bystanders.

### Regenerate semantics

`r` rotates only the *unused* pairing token. Devices that have already
paired carry their long-lived bearer and keep their connection IDs across
a regenerate action.

### Status

Placeholder. Renders a single card reading "No client connected — socket
wiring is a follow-up task". Will host the connection state machine and
client list once the transport lands.

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
├── applink_app.py      # Textual App + screens
├── pairing.py          # token, IP detection, URI builder
└── qr_widget.py        # TerminalQR(Static) — compact half-block renderer
```

## Dependencies

- `textual>=8.2.7,<9`
- `segno>=1.5,<2` (chosen over `qrcode` for built-in Micro QR support)

Both are installed by `ait setup`.

## Status

This child task (t822_2) ships only the pairing skeleton. The
WebSocket listener and command-verb handlers are tracked in a follow-up
scoped by sibling task t822_3 (monitor port design).
