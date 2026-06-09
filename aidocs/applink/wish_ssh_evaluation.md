# AppLink: Evaluating wish / SSH as a Transport

An evaluation of [charmbracelet/wish](https://github.com/charmbracelet/wish) —
an SSH framework for serving terminal apps — as a connection mechanism for
reaching `ait` TUIs remotely, and how it relates to the native-mobile transport
defined in [protocol.md](protocol.md) and [content_transport.md](content_transport.md).

## Overview

This document answers three questions raised while exploring (a) porting the
framework TUIs to Go and (b) using `wish` for remote access:

1. Should `wish` replace the `applink` transport for the **native mobile
   companion** (parent task [t822](../../aitasks/t822_new_ait_bridge_tui.md))?
2. Is `wish` useful for **other access modes** — reaching `ait` TUIs from another
   terminal, or running the framework on a **hosted** box?
3. How does the framework's heavy use of **tmux** (switching TUIs, multiple
   agents) integrate with `wish`?

The short answer: `wish` is **complementary** to `applink`, not a replacement.
It is an excellent fit for terminal clients and hosted deployments, and a poor
fit for the native mobile companion. The two serve different audiences over the
same headless core.

This is an evaluation / recommendation document, not an implementation spec. It
deliberately does **not** redefine the wire format in
[content_transport.md](content_transport.md) or the verb/permission model in
[permissions.md](permissions.md).

## What wish is

`charmbracelet/wish` is a Go library (built on `gliderlabs/ssh`) that treats SSH
as a general-purpose application protocol — like HTTP or SMTP — rather than just
shell access. It lets you stand up an SSH server that serves an interactive
**Bubble Tea** TUI to any SSH client, with no OpenSSH dependency and automatic
host-key generation.

| Aspect | Detail |
|--------|--------|
| Transport | SSH (TCP), with a PTY allocated per session |
| Client | Must be an **SSH / terminal client**; receives a raw VT/ANSI stream |
| Auth | SSH **public-key** authentication — no passwords, no HTTPS certs |
| Middleware | `bubbletea` (serve a TUI, native resize), `activeterm`, `accesscontrol`, `logging`, `recover`, `git`, SCP; port-forwarding via the underlying SSH server |
| Reference apps | Soft Serve (git host TUI), Wishlist (SSH directory), SSHWordle |

The defining property for this evaluation: **the client is a terminal.** The
remote TUI runs server-side and the client renders a raw terminal stream.

## Core contrast with applink

The load-bearing decision in the `applink` design is the opposite: **the phone
is a native client, not a terminal emulator.** The server parses ANSI exactly
once and ships per-line **styled spans** in MessagePack
([content_transport.md](content_transport.md)); the phone renders natively with
**no VT/xterm parser**, idle panes cost zero bytes, and a focused busy pane stays
under ~1 KB per refresh. Control flows through structured, individually
**permission-gated verbs** ([permissions.md](permissions.md)), pairing is a
QR-driven token→bearer exchange, and a `Suspended → Connected` state machine
survives mobile backgrounding.

| Dimension | wish / SSH | applink (native) |
|-----------|------------|------------------|
| What the client renders | Raw VT/ANSI stream (needs a terminal emulator) | Pre-parsed styled spans (native widgets) |
| Where ANSI is parsed | On the client (terminal) | Once, on the server |
| Control model | Keystrokes into a PTY | Structured verbs, per-verb gating |
| Auth / identity | SSH public key + host key | QR token → session bearer + cert pinning |
| Bandwidth profile | Full VT repaints (SSH-compressed) | keyframe/delta/append; zero bytes when idle |
| Backgrounding | Session drops; reconnect = new session | `Suspended → Connected` resume + catch-up |
| Cross-network | Native (SSH tunnels, jump hosts) | Staged roadmap (tunnel → relay → WebRTC) |

## Recommendation per use case

### Use case 1 — Native mobile companion (the t822 goal)

**Verdict: keep the `applink` styled-span protocol; `wish` would be a
regression.**

- SSH delivers a raw VT stream, so the mobile app would have to embed a **full
  terminal emulator + VT parser** — exactly what the design removes. The
  companion degrades into "a phone SSH terminal," losing native UI, tap targets,
  and gestures.
- The structured control plane collapses: per-verb gating
  (`read_only` can't `kill_pane`) becomes "any keystroke into a PTY," and the
  permission-profile model in [permissions.md](permissions.md) no longer maps.
- Bandwidth and battery regress versus the delta/append/zero-idle data plane
  built for cellular.
- SSH sessions do not map to mobile backgrounding — there is no built-in
  `Suspended → resume`-with-catch-up.
- Per-pane `subscribe` / `focus` / cadence is lost (SSH gives one PTY).
- It discards the staged cross-network roadmap (envelope + pairing + verbs carry
  across LAN → relay → WebRTC).

### Use case 2 — Reaching ait TUIs from another terminal

For a **local PC, a laptop, or a power-user phone terminal app** (Termius,
Blink), the client *is* a terminal — so the "needs a terminal emulator"
objection from use case 1 does not apply.

**Verdict: `wish` is an excellent, near-free complementary access path.** Once
the TUIs are ported to Go / Bubble Tea (the `aitasks_go` effort), the same
Bubble Tea codebase serves both local and remote. SSH provides transport
security, host-key verification (≈ the cert pinning `applink` does by hand),
public-key identity with `authorized_keys`-based revocation, channel
multiplexing, and compression — with no custom protocol to design or version.
This is a better-engineered version of the roadmap's "Phase 2 tunnel escape
hatch" ([protocol.md §Roadmap to cross-network](protocol.md#roadmap-to-cross-network)).

### Use case 3 — Hosted aitasks (framework on a remote box)

When the framework (the tmux session with the `ait` IDE) runs on a hosted box —
cloud VM, dev container, always-on server — accessed from a local PC and a
phone:

**Verdict: use `wish` for terminal clients and `applink` for mobile, both
served directly from the hosted box; do not relay mobile through the local PC.**

- **`wish` for hosted → local PC: this is its home turf** (the Soft Serve /
  Wishlist model). The hosted box runs `wish` serving the Go TUIs; the local PC
  just `ssh`-es in.
- **Mobile should connect directly to the hosted box — not via the local PC.**
  Routing the phone through the PC reintroduces the "PC must be on" dependency,
  adds a double hop, and turns the PC into a stateful relay it was never designed
  to be. The hosted box is already always-on and internet-reachable, so it is the
  natural `applink` server.
- **Cleanest topology: both front-ends in parallel over one source of truth.**
  The hosted box exposes (a) `wish`/SSH for terminal clients and (b) `applink`
  WebSocket + styled spans for native mobile, both over the same headless core.
  The PC and the phone are peer clients; neither is a gateway.
- **Bonus:** a public hosted address solves the v1 LAN-only limitation **without
  building the deferred Phase-3 relay broker** — the server is already
  reachable, so pairing/bearer flows work as-is.

## Deployment topologies

| Topology | `applink` server runs on | Mobile connects to | `wish` (terminal) connects to | Notes |
|----------|--------------------------|--------------------|-------------------------------|-------|
| Local (v1) | Local PC | Local PC (LAN) | Local PC | Today's design; same-Wi-Fi assumption |
| Hosted, mobile-direct (**recommended**) | Hosted box | Hosted box (public) | Hosted box | PC and phone are peer clients; PC can be off |
| Hosted, PC-relayed (**not recommended**) | Local PC | Local PC → hosted | Hosted box | Reintroduces PC-must-be-on, double hop, stateful proxy |

### Public-exposure hardening

Going direct mobile → hosted means the `applink` server now listens on a
**public** interface, which raises the bar on the security review the v1
[protocol.md](protocol.md) explicitly defers under its same-LAN assumption. The
transport-agnostic envelope and pairing already support it; the hardening is the
work. Enumerated (not specified here):

- Real CA-signed TLS certificate (or an explicit pinning story) plus rotation,
  instead of a first-run self-signed cert.
- Bearer-token entropy audit and shorter default TTLs for an internet-facing
  server.
- **Rate-limiting and lockout on pairing attempts** to resist online token
  guessing.
- Bind/listen scoping and audit logging of denied verbs.

A full security specification for public exposure is out of scope for this
document.

## tmux integration

The framework UX is deeply tmux-native: agents and TUIs are tmux windows,
navigation is tmux `switch-client` / `select-window` plus the `j` switcher
overlay (`.aitask-scripts/lib/tui_switcher.py`), and `ait monitor` multiplexes
agents via `list-panes` / `capture-pane` / `new-window` / `kill-pane`
(`.aitask-scripts/monitor/tmux_monitor.py`). There are **two distinct layers of
multiplexing**, and they integrate with `wish` very differently:

- **Layer A — tmux as the agent/process multiplexer.** Each agent runs in a
  window/pane; `capture-pane` is the snapshot source. Pure backend; it stays.
- **Layer B — tmux as the user-facing window manager.** One TUI per window, the
  `j` switcher, the `switch-client` teleport between sessions. This is navigation
  UX.

### The trap: nested tmux / `tmux attach` over wish

The naive integration — `ssh hosted` then attach the tmux session, or run tmux
inside the `wish` PTY — technically works but:

- Causes tmux-in-a-PTY-over-SSH pain: prefix-key collisions with the client's
  own terminal/tmux, and resize / DCS-passthrough quirks.
- **Bypasses everything `wish` is for**, and critically exposes **all of tmux
  with zero permission gating** — every window, `kill`, and `detach` — which
  directly contradicts the `applink` permission-profile model.

So **do not expose Layer B through `wish`.** (A thin `wish → tmux attach` is
acceptable only as a trivial single-trusted-user MVP, never the productized
path.)

### The clean integration

Keep Layer A server-side; **move Layer B into the served TUI.** `wish` serves a
single Bubble Tea **control TUI** (the Go port of monitor / board / switcher)
that:

- does navigation **in-app** — its own keybindings flip between agents / TUIs /
  sessions (an in-app session picker driven by `list-sessions`, not a tmux client
  teleport), and
- reaches into tmux server-side through the same control surface `monitor`
  already uses.

tmux is thereby **demoted from "window manager the user drives" to "agent backend
the TUI drives."** The enabler already exists: `ait monitor` renders multiple
agents in **one** screen (the `PaneCard` grid), which is exactly the model that
fits a single `wish` PTY. The one-TUI-per-window + `j`-switcher + `switch-client`
model does **not** port; it is replaced by in-TUI navigation.

## Unifying conclusion: monitor_core with three front-ends

All three use cases converge on the **`monitor_core` extraction seam** already
defined by sibling task t822_3
([monitor_port_design.md](../../aitasks/t822/t822_3_monitor_port_design.md)).
Build **one headless core**, then attach front-ends over it, with tmux sitting
**below** the core as backend:

| Front-end | Navigation layer | tmux role |
|-----------|------------------|-----------|
| Local Textual (today) | tmux windows + `j` switcher + `switch-client` | window manager **and** backend |
| `wish` (SSH / terminal) | in-app, inside the served Bubble Tea TUI | backend only |
| `applink` (native mobile) | native mobile UI | backend only |

The rule that falls out: **the moment you go remote — `wish` *or* mobile —
tmux's window-manager role disappears and navigation moves into the front-end.**
Only local interactive use keeps tmux as the user-facing window manager. `wish`
and `applink` are **complementary** (terminal clients vs native mobile), not
competing transports.

## Cross-references

- [protocol.md](protocol.md) — control-plane envelope, pairing, lifecycle,
  versioning, and the cross-network transport roadmap.
- [content_transport.md](content_transport.md) — the binary styled-span data
  plane that makes the native (non-terminal) mobile client viable.
- [permissions.md](permissions.md) — the per-verb permission profiles that the
  raw-PTY `wish` model cannot reproduce.
- [t822_3 monitor_port_design.md](../../aitasks/t822/t822_3_monitor_port_design.md)
  — the `monitor_core` headless-extraction seam all three front-ends consume.
- The Go / Bubble Tea TUI port (the `aitasks_go` project) is the **precondition**
  that makes `wish` cheap: with the TUIs already in Bubble Tea, the `bubbletea`
  middleware serves them remotely with near-zero extra code.

## Out of scope (this document)

- Any code under `.aitask-scripts/` and the actual `wish` / `monitor_core`
  implementation.
- The Go / Bubble Tea TUI port itself (tracked under the `aitasks_go` project).
- Mobile-side changes (developed in the `aitasks_mobile` repo).
- A full security specification for public exposure — the hardening items above
  are enumerated only; the deferred cryptographic / security review remains its
  own follow-up.
