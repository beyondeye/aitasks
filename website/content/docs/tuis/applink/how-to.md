---
title: "How-To Guides"
linkTitle: "How-To"
weight: 20
description: "Pairing a mobile device with ait applink"
---

## Pair a mobile device

1. Run `ait applink` on the host that holds your aitasks workspace.
2. The Pairing screen shows a QR code and the underlying `applink://` URI.
3. Open the companion app on your phone (separate
   `aitasks_mobile` repo) and tap **Scan QR**.
4. The companion app decodes the URI and (once the transport lands) opens a
   TLS WebSocket back to the host using the pinned certificate fingerprint.

## Run the bridge headless (unattended host)

On a host nobody is watching, run the bridge without the TUI:

```
ait monitor --headless-for-applink [--port N] [--profile <name>] [--no-qr]
```

This skips the terminal UI entirely and serves only the applink listener
(control plane + screen push loop). At startup it prints the pairing URL, the
certificate fingerprint, and an ASCII QR to standard output — scan the QR (or
open the URL) with the companion app exactly as you would from the Pairing
screen. Pass `--no-qr` to print just the URL and fingerprint (handy when
redirecting output to a log file). `--profile` sets the permission profile
assigned to a newly paired device (default `monitor_control`).

Because there is no keyboard, control the running bridge with signals:

- **SIGHUP** — mint a fresh pairing token and reprint the block (the headless
  equivalent of pressing **r**). Already-paired devices keep their bearer.
- **SIGINT** / **SIGTERM** — stop the bridge cleanly.

Paired devices are persisted, so they survive a restart and resume
automatically.

## Regenerate the token

Press **r** on the Pairing screen. A new 256-bit token is drawn and the QR
re-renders in place. Any previously issued *unused* QR becomes invalid
immediately — but devices that have already paired keep their long-lived
bearer and stay connected. Regenerate is safe to use mid-session.

## Switch screens

- **s** — show the Status placeholder screen.
- **p** — return to Pairing.
- **j** — jump to another TUI (board, monitor, brainstorm, …) via the shared
  TUI switcher.
- **q** — quit.

## What is the LAN IP detection?

The TUI resolves the host's primary non-loopback IPv4 by:

1. Calling `getaddrinfo(gethostname(), …)` and picking the first non-`127.*`
   entry, then
2. As a fallback, opening a UDP socket against `8.8.8.8` and reading the
   kernel-selected source address.

If both probes fail, the URI is built with `0.0.0.0` — the QR still
generates so the rest of the flow can be demonstrated offline.
