---
title: "App Linker"
linkTitle: "App Linker"
weight: 90
description: "TUI for pairing the mobile companion app over LAN via QR code"
maturity: [experimental]
depth: [main-concept]
---

The `ait applink` command launches a Textual TUI that bridges a local `ait`
workspace to the mobile companion app (developed in the sibling
`aitasks_mobile` repo) over a paired, QR-bootstrapped LAN connection.

It generates a one-time pairing token, renders the `applink://` URI as a
scannable QR code on the terminal, and runs a `wss://` WebSocket listener that
pairs the companion app and routes its commands into the running session under
a permission profile. Streaming pane content to the phone (the binary data
plane) is tracked under follow-up tasks.

> **Customizable keys:** every shortcut here can be rebound. Press `?` in this
> TUI for the in-place editor, or open
> [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).

## Tutorial

### Launching the App Linker

```bash
ait applink
```

The TUI opens directly on the **Pairing** screen. A QR code is rendered using
half-block characters; scan it with the companion app to start the pairing
handshake.

### Pairing flow

1. The TUI generates a 256-bit URL-safe token via `secrets.token_urlsafe(32)`.
2. The host detects its first non-loopback LAN IPv4 (or falls back to
   `0.0.0.0` if none is found).
3. The encoded URI follows the grammar defined in
   `aidocs/applink/protocol.md`:

   ```
   applink://<lan-ip>:<port>/pair?t=<token>&fp=<fingerprint>&name=<hostname>
   ```

4. Scanning the QR with the companion app conveys the token and
   fingerprint to the mobile side.

Press **r** to regenerate the token. The QR re-renders in place. Regenerate
only invalidates the *unused* pairing token; already-paired clients keep
their long-lived bearers and connection IDs.

### Screens

- **Pairing** — QR code and a short hint footer.
- **Devices** — paired-device list (name/model, platform, connection state,
  pairing time, last-seen, and coarse location when the device provides one)
  with per-device revoke.

Switch with **s** (Devices) and **p** (Pairing). Press **x** on the Devices
screen to revoke the highlighted device. Press **j** to jump to another TUI
via the shared TUI switcher.

---

**Next:** [How-To Guides](how-to/) — pairing walkthrough.  
**Reference:** [Reference](reference/) — keybindings, screens, env vars.
