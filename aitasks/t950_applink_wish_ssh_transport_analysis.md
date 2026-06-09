---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-09 12:25
updated_at: 2026-06-09 12:39
---

Write a design / analysis doc at `aidocs/applink/wish_ssh_evaluation.md` that
evaluates **charmbracelet/wish** (SSH-based serving of Bubble Tea TUIs) as a
transport/access option for the `ait applink` bridge (parent t822), and gives a
recommended approach **per use case**. This is a docs-only task: produce the
aidoc and wire its cross-references; no code under `.aitask-scripts/`.

The analysis below was produced during an `/aitask-explore` session and should
be the backbone of the doc — refine wording, but preserve the conclusions and
the per-use-case recommendations.

## Background / what wish is

`charmbracelet/wish` is a Go SSH-server framework (built on gliderlabs/ssh) that
serves **Bubble Tea TUIs over SSH**. The client must be an **SSH / terminal
client** receiving a raw VT/ANSI stream; auth is SSH **public-key**; it ships
middleware (`bubbletea`, `activeterm`, `accesscontrol`, `logging`, `git`,
port-forwarding). Reference apps: Soft Serve, Wishlist.

Contrast with the current applink design (`aidocs/applink/protocol.md`,
`content_transport.md`, `permissions.md`): the load-bearing decision there is
that **the phone is a NATIVE client, not a terminal emulator** — the server
parses ANSI once and ships styled spans (MessagePack keyframe/delta/append/
cursor/dim), the phone renders natively with **no VT parser**, idle panes cost
zero bytes, structured **verbs** are individually **permission-gated**
(read_only / monitor_control / full), QR pairing yields token->bearer, and a
Suspended->Connected resume state machine survives mobile backgrounding. A
staged roadmap (LAN -> tunnel -> relay -> WebRTC) reuses envelope+pairing+verbs.

## Use case 1 — Native mobile companion (the original t822 goal)

**Recommendation: keep the structured styled-span applink protocol; wish would
be a regression here.** Reasons:
- SSH delivers a raw VT stream, so the mobile app would have to embed a full
  **terminal emulator + VT parser** — exactly what the design removes. The
  companion degrades into "a phone SSH terminal," losing native UI / tap
  targets / gestures.
- No structured control plane: per-verb permission gating collapses into
  "keystrokes into a PTY"; the profile model doesn't map.
- Bandwidth/battery regression vs the delta/append/zero-idle plane built for
  cellular.
- Backgrounding doesn't map: SSH sessions drop; no built-in resume-with-catch-up.
- Multi-pane subscribe/focus/cadence is lost (SSH = one PTY).
- Throws away the staged cross-network roadmap.

## Use case 2 — Reaching ait TUIs from another *terminal* (local PC, laptop, power-user phone terminal)

**Recommendation: wish is an excellent, near-free fit — as a COMPLEMENTARY
access path, not a replacement.** Especially once TUIs are ported to Go/Bubble
Tea (the `aitasks_go` project), one Bubble Tea TUI codebase serves local +
remote. SSH gives transport security, host-key verification (~= cert pinning),
public-key identity + `authorized_keys` revocation, channels/compression, and
native tunneling — no custom protocol to design/version. This is a better-built
version of the roadmap's "Phase 2 tunnel escape hatch."

## Use case 3 — Hosted aitasks (framework runs on a remote/cloud box), accessed from local PC + mobile

- **wish for hosted -> local PC: yes, this is wish's home turf** (Soft Serve /
  Wishlist model). The hosted box runs wish serving the Go TUIs; the local PC
  just `ssh hosted-box`. The "mobile can't be a dumb terminal" caveat does NOT
  apply to a PC — your PC *is* a terminal.
- **Where should mobile connect? Directly to the hosted box — NOT via the local
  PC.** Routing mobile through the PC reintroduces the "PC must be on" dependency,
  adds a double hop, and makes the PC a stateful relay it was never designed to
  be. The hosted box is already always-on and internet-reachable — it is the
  natural applink server.
- **Cleanest topology: both front-ends in parallel over one source of truth.**
  The hosted box exposes (a) wish/SSH for terminal clients and (b) applink
  WebSocket+styled-spans for native mobile, both over the same headless core.
  Local PC and phone are peer clients, neither is a gateway.
- **Bonus:** the hosted box having a public address quietly solves the v1
  LAN-only limit *without building the relay broker* the roadmap defers (Phase 3).
- **The cost:** the applink server now listens on a **public** interface, raising
  the bar on the security review the v1 doc defers (same-LAN assumption): real
  TLS cert + rotation, bearer-token entropy audit, and rate-limiting pairing
  attempts against internet exposure.

## tmux integration (cross-cutting — applies to wish and mobile alike)

The framework UX is deeply **tmux-native**: agents and TUIs are tmux windows;
navigation is tmux `switch-client`/`select-window` + the `j` switcher overlay;
`monitor` multiplexes agents via `list-panes`/`capture-pane`/`new-window`/
`kill-pane` (`.aitask-scripts/monitor/tmux_monitor.py`,
`.aitask-scripts/lib/tui_switcher.py`). There are **two layers of multiplexing**:

- **Layer A — tmux as the agent/process multiplexer** (each agent in a window/
  pane; `capture-pane` is the snapshot source). Pure backend; stays.
- **Layer B — tmux as the user-facing window manager** (one TUI per window,
  `j` switcher, `switch-client` teleport). Navigation UX.

**The trap:** naive `wish -> tmux attach` (or nested tmux inside the wish PTY)
technically works but causes prefix-key collisions + resize/DCS-passthrough
pain, AND bypasses wish's middleware and — critically — **all per-verb permission
gating** (raw tmux exposes every window/kill/detach with zero profile control).
So **do not expose Layer B through wish.** A thin `wish -> tmux attach` is OK only
as a trivial single-trusted-user MVP, not the productized path.

**The clean integration:** wish serves a **single Bubble Tea "control" TUI**
(the Go port of monitor/board/switcher). Navigation happens **in-app** (its own
keybindings + an in-app session/agent picker driven by `list-sessions`), and the
TUI reaches tmux server-side via the same control surface monitor already uses.
tmux is **demoted from "window manager the user drives" to "agent backend the TUI
drives."** Enabler: `monitor` ALREADY renders multiple agents in one screen (the
`PaneCard` grid) — that multi-agent-in-one-view model is exactly what fits a
single wish PTY. The one-TUI-per-window + `j`-switcher + `switch-client` teleport
do NOT port; they are replaced by in-TUI navigation.

## The unifying conclusion (state this prominently in the doc)

All three angles converge on the **`monitor_core` extraction seam** that
sibling task t822_3 already defines. Build **one headless core**, then attach
**three front-ends** over it, with tmux sitting *below* the core as backend:

| Front-end | Navigation layer | tmux role |
|---|---|---|
| Local Textual (today) | tmux windows + `j` switcher + `switch-client` | window manager AND backend |
| wish (SSH/terminal) | in-app, inside the served Bubble Tea TUI | backend only |
| applink (native mobile) | native mobile UI | backend only |

Rule that falls out: **the moment you go remote (wish OR mobile), tmux's
window-manager role disappears and navigation moves into the front-end; only
local interactive use keeps tmux as the user-facing window manager.** wish and
applink are **complementary** (terminal clients vs native mobile), not
competing transports.

## Deliverable contents

`aidocs/applink/wish_ssh_evaluation.md` should contain:
1. What wish is, and the core contrast with applink's native-client design.
2. Per-use-case recommendation (the three cases above), each with a clear verdict.
3. The hosted-vs-local deployment topologies, incl. the mobile-connects-direct-
   to-hosted conclusion and the public-exposure hardening list.
4. The tmux two-layers analysis and the "control TUI over monitor_core, tmux as
   backend" integration model + the nested-tmux trap.
5. The unifying monitor_core + three-front-ends table and rule.
6. Cross-references to `protocol.md`, `content_transport.md`, `permissions.md`,
   and the t822_3 monitor_port_design seam; note the `aitasks_go` Bubble Tea
   port as the precondition that makes wish cheap.

## Out of scope

- Any code under `.aitask-scripts/` or the actual wish/monitor_core implementation.
- The Go/Bubble Tea TUI port itself (tracked under `aitasks_go`).
- Mobile-side changes (`aitasks_mobile`).
- A full security spec for public exposure — only enumerate the hardening items;
  the deferred crypto/security review remains its own follow-up.
