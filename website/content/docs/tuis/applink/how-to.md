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
