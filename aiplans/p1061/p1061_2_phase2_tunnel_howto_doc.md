---
Task: t1061_2_phase2_tunnel_howto_doc.md
Parent Task: aitasks/t1061_applink_outside_network_connectivity_roadmap.md
Sibling Tasks: aitasks/t1061/t1061_1_*.md, aitasks/t1061/t1061_3_*.md, aitasks/t1061/t1061_4_*.md, aitasks/t1061/t1061_5_*.md
Archived Sibling Plans: aiplans/archived/p1061/p1061_*_*.md
Worktree: (none — fast profile, current branch)
Branch: main (current branch)
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-05 17:48
---

# Plan: A2 — Phase-2 tunnel how-to + roadmap status update (t1061_2)

## Context

A1 (`t1061_1`, archived) landed the advertised-endpoint override: config keys
`tmux.applink.advertised_host/port/kind/trust`, CLI flags
`--advertise-host/-port/-kind/-trust` on both entry points, and the canonical
"Endpoint & trust model" wire grammar in `aidocs/applink/protocol.md`
§Pairing flow. Mesh-VPN reach now works end-to-end with the unchanged
self-signed cert + fingerprint pin. This child (A2) writes the user-facing
recipe collection (`aidocs/applink/tunnel_howto.md`), updates the protocol
roadmap's Phase-2 status, and cross-links from `wish_ssh_evaluation.md`.
Doc-only — no code changes.

**Verified against current sources (2026-07-05):**
- Config keys exist with per-key fault tolerance in
  `server.load_applink_config()` (`.aitask-scripts/applink/server.py:70-130`);
  documented in `seed/project_config.yaml:401-441` and live
  `aitasks/metadata/project_config.yaml:45-48`.
- CLI flags on both entry points: `headless._add_advertise_args`
  (`headless.py:258-283`, with `--advertise-port/-kind/-trust` requiring
  `--advertise-host`) and the TUI argparser in `applink_app.py`. Launchers:
  `ait applink` (TUI, `aitask_applink.sh:33`) and
  `ait monitor --headless-for-applink` (`aitask_monitor.sh:42`).
- Canonical grammar: `protocol.md:132` "### Endpoint & trust model"
  (`kind := lan|mesh|tunnel`, `trust := pin|ca`, single `alt=` param, IPv6
  bracketing, advertisement-only semantics, old-client rule, `trust=ca`
  inert until `aitasks_mobile#31_3`). The how-to cross-references — never
  restates — this.
- `normalize_advertised_host` (`pairing.py:94`) accepts scheme://, paths,
  `host:port`, bracketed/bare IPv6 — the how-to can say "paste the hostname
  from your tunnel UI".
- Phase-2 roadmap row: `protocol.md:227` ("Documented as a `how-to`, not a
  protocol change") and `protocol.md:245-249` (What-changes-per-phase table),
  `protocol.md:255` ("Tunnel users get cross-network for free").
- Cross-link site: `wish_ssh_evaluation.md:105-106` ("Phase 2 tunnel escape
  hatch").
- `aidocs/applink/tunnel_howto.md` does not exist yet.
- Sibling A3 (`t1061_3`, pending) will auto-spawn a Cloudflare Quick Tunnel —
  the manual reverse-tunnel recipe links it as the future turnkey path.
- **Client-side support status (drives how recipes are phrased):**
  multi-endpoint `alt` parsing + LAN-vs-tunnel racing is mobile M2
  (`aitasks_mobile#31_2`, **pending**); per-endpoint CA trust is M3
  (`aitasks_mobile#31_3`, **pending**). Today's clients read only the QR
  authority + `t`/`fp`/`name`, ignore `alt`/`kind`/`trust`, and always
  pin-verify (protocol.md:170-179 old-client rule).

## Organizing principle for the recipes (review-driven)

**Classify every recipe by what TLS certificate the phone sees** — that
single axis determines the trust mode and whether the recipe works today:

| Recipe | Phone connects to | Cert the phone sees | Trust mode | Works today? |
|---|---|---|---|---|
| Mesh VPN (Tailscale/ZeroTier/WireGuard) | PC's mesh IP | PC's self-signed cert (TLS end-to-end) | `pin` (default) | **Yes** |
| `ssh -L` gateway forward (raw TCP) | gateway host:port | PC's self-signed cert (TLS end-to-end) | `pin`, `kind=tunnel` | **Yes** |
| Raw-TCP public tunnel (e.g. `ngrok tcp`) | tunnel host:port | PC's self-signed cert (TLS end-to-end) | `pin`, `kind=tunnel` | **Yes** |
| TLS-terminating tunnel (cloudflared / `ngrok http`) | public hostname:443 | tunnel provider's public CA cert | `ca` — **gated on `aitasks_mobile#31_3`** | **No (pre-M3: pin mismatch is the expected failure)** |

A shorter version of this table opens the how-to so a user can tell an
expected pre-M3 failure from a misconfiguration.

## Steps

### 1. New `aidocs/applink/tunnel_howto.md`

Recipe collection for reaching the applink server from outside the LAN
(Phase 2 — user-owned tunnel). Structure:

1. **Intro** — what Phase 2 is (phone reaches the PC via user-run
   tunnel/mesh; QR advertises that endpoint instead of the LAN IP); link
   `protocol.md` §Roadmap and §Pairing flow "Endpoint & trust model" for the
   wire semantics. Include the classify-by-cert table above (which recipe to
   pick; pin vs ca; works-today status).
   **Every recipe carries an explicit topology line** (review-driven):
   *command runs on host X · listener created on host Y · phone connects to
   Y · cert the phone sees is Z · trust mode.*
2. **Recipe 1 (lead): mesh VPN — Tailscale / ZeroTier / WireGuard.**
   Existing cert + pin work unchanged. Steps: install mesh on PC + phone;
   find the PC's mesh IP (e.g. `tailscale ip -4`); set
   `tmux.applink.advertised_host: <mesh-ip>` in
   `aitasks/metadata/project_config.yaml` (commented example already ships
   there) or pass `--advertise-host <mesh-ip>` to `ait applink` /
   `ait monitor --headless-for-applink`; re-show the QR and scan.
   Topology line: config/flag set on the PC; phone connects directly to the
   PC's mesh IP; phone sees the PC's self-signed cert; trust `pin`.
   `advertised_kind` defaults to `mesh` when an override host is set.
   **`alt` phrasing (review-driven):** describe as *server/QR emission
   behavior* — the QR additionally carries the LAN endpoint as `alt` so that
   clients supporting endpoint alternatives (lands with
   `aitasks_mobile#31_2`) can prefer LAN when co-located; today's clients
   ignore `alt` and use only the advertised primary. Firewall note: the
   doctor detects a mesh-interface IP and extends its commands to that CIDR;
   a mesh DNS name (MagicDNS) classifies external — set the numeric mesh IP
   for interface-scoped firewall guidance.
3. **Recipe 2: `ssh -L` gateway forward (raw TCP, pin-preserving).**
   Scenario and topology spelled out explicitly (review-driven): requires a
   **gateway host** that (a) the phone can reach and (b) can SSH to the PC.
   The command **runs on the gateway**; the listener is **created on the
   gateway** and must bind a non-loopback interface:
   `ssh -L 0.0.0.0:8765:<pc-lan-ip>:8765 user@<pc-host>` (run on the
   gateway). Phone connects to `<gateway-host>:8765`. SSH forwards raw TCP,
   so TLS stays end-to-end PC↔phone → phone sees the PC's self-signed cert →
   **`trust=pin` keeps working**. Advertise on the PC:
   `--advertise-host <gateway-host> --advertise-kind tunnel`. Call out the
   common mistake: running the command on the PC or laptop creates the
   listener there, and advertising a host the phone cannot reach fails at
   connect time. Mention the bind-address/`GatewayPorts` caveat and the
   `ssh -R` variant (PC dials out to the gateway:
   `ssh -R 0.0.0.0:8765:localhost:8765 user@<gateway>` run on the PC,
   requires `GatewayPorts` in the gateway's sshd config) for when the
   gateway cannot SSH into the PC. Briefly note `ngrok tcp`-style raw-TCP
   public tunnels sit in this same pin-preserving class.
4. **Recipe 3: TLS-terminating reverse tunnel (cloudflared / `ngrok http`)**
   — explicitly marked **gated on `aitasks_mobile#31_3` (M3, per-endpoint CA
   trust) landing client-side**. Topology: tunnel daemon runs on the PC
   (outbound-only); phone connects to the public hostname; the tunnel edge
   terminates TLS, so the phone sees the **provider's public CA cert**, not
   the PC's — `trust=pin` cannot succeed, `advertised_trust: ca` is
   required, and pre-M3 the pin-mismatch failure is **expected behavior,
   not misconfiguration** (per the old-client rule in "Endpoint & trust
   model"). Recipe (for when M3 lands): run e.g.
   `cloudflared tunnel --url https://localhost:8765 --no-tls-verify`; set
   `advertised_host` = the public hostname, `advertised_port: 443`,
   `advertised_trust: ca`, `advertised_kind: tunnel`. Link A3 (`t1061_3`)
   as the planned auto-spawned turnkey variant of this recipe.
5. **Operational security cautions (review-driven)** — short section, linking
   `security.md` for the full posture: use gateways/tunnel accounts you
   trust (a raw-TCP gateway can observe traffic volume/timing though not
   plaintext; a TLS-terminating tunnel edge sees plaintext frames); restrict
   the gateway listener's firewall/source ranges where practical; stop
   tunnels / tear down forwards when done; pairing tokens are single-use
   with a short TTL, but if a QR may have been exposed beyond the intended
   phone, generate a fresh one (TUI `r`) before pairing; revoke sessions
   from the TUI if in doubt.
6. **Troubleshooting** — invalid `advertised_host` config degrades
   fail-visible to the LAN QR with a warning (headless prints it after the
   pairing block; TUI shows it in the pairing screen advisory); accepted
   host forms (scheme/path stripped, `host:port`, IPv6 bracketing) per
   `normalize_advertised_host`; CLI group precedence (any `--advertise-*`
   flag makes the CLI define the entire override, config ignored);
   pre-M3 pin-mismatch against TLS-terminating tunnels is expected (see
   classify-by-cert table).

Terminology: use "cross-repo"/"linked repo" language, generic host examples;
current-state-only prose (no version history), per
`aidocs/framework/documentation_conventions.md`.

### 2. Update `aidocs/applink/protocol.md` §Roadmap Phase-2 status

Current-state-only edits:
- Phase table row 2 (`protocol.md:227`): "Documented as a `how-to`" → link
  `[tunnel_howto.md](tunnel_howto.md)`; reflect that the server-side
  advertised-endpoint override exists (pairing QR can advertise a
  mesh/tunnel endpoint) and that CA-trust reverse tunnels await the mobile
  per-endpoint CA-trust path (`aitasks_mobile#31_3`).
- "What changes per phase" table Phase-2 Discovery cell (`protocol.md:248`,
  "User-typed or copy-pasted from tunnel UI") → mention the
  `advertised_host` config/CLI override as the mechanism.
- §"Why ship Phase 1 first" bullet (`protocol.md:255`) → point tunnel users
  at the how-to.

### 3. Cross-link from `aidocs/applink/wish_ssh_evaluation.md`

At the "Phase 2 tunnel escape hatch" framing (`wish_ssh_evaluation.md:105`),
add a link to `tunnel_howto.md` alongside the existing protocol.md link.

## Verification

- Every command / config key / flag named in the how-to exists in the A1
  implementation (grep against `.aitask-scripts/applink/` source and both
  config surfaces).
- **Per-recipe semantic sanity checklist (review-driven — topology is a
  semantic claim, not a spelling claim).** For each recipe, re-derive and
  confirm against the doc text:
  - *Mesh:* config/flag on PC · phone → PC mesh IP directly · cert = PC
    self-signed · trust `pin` · works today.
  - *`ssh -L`:* command on gateway · listener on gateway (non-loopback
    bind) · phone → gateway:port · gateway → PC over SSH · cert = PC
    self-signed (raw TCP passthrough) · trust `pin` · works today.
  - *`ssh -R` variant:* command on PC · listener on gateway (needs
    `GatewayPorts`) · phone → gateway:port · cert = PC self-signed ·
    trust `pin`.
  - *TLS-terminating tunnel:* daemon on PC (outbound) · phone → public
    hostname:443 · cert = provider CA cert · trust `ca` · gated on M3,
    pre-M3 failure expected.
- `alt`/racing claims phrased as server/QR emission or "clients that support
  endpoint alternatives (`aitasks_mobile#31_2`)" — never as current mobile
  behavior.
- Internal doc links resolve (all referenced anchors/files exist:
  `tunnel_howto.md` ↔ `protocol.md` §Roadmap / §Endpoint & trust model,
  `security.md`, `wish_ssh_evaluation.md` → `tunnel_howto.md`).
- No hugo build needed (aidocs only).

## Step 9 (Post-Implementation)

Standard cleanup/merge/archival per task-workflow Step 9 (fast profile —
current branch, no worktree/merge).

## Risk

### Code-health risk: low
- Doc drift: a misspelled config key / flag / command would mislead users
  following the recipes · severity: low · → mitigation: covered in-plan
  (Verification greps every named key/flag/command against source).
- Operational wrongness beyond spelling: a recipe with correct tokens but
  wrong topology (listener host, cert visibility) would mislead worse than
  a typo · severity: medium · → mitigation: covered in-plan (per-recipe
  topology lines in the doc + semantic sanity checklist in Verification).

### Goal-achievement risk: low
- The mesh recipe's live end-to-end proof (real Tailscale device) cannot be
  run in this session · severity: low · → mitigation: covered in-plan (task
  Verification explicitly allows verifying each command/config key against
  the A1 implementation instead; A1 already offered the live mesh pairing
  check as its own manual-verification follow-up).
- Overstating client capability (`alt` racing, CA trust) before M2/M3 land
  would set wrong user expectations · severity: low · → mitigation: covered
  in-plan (classify-by-cert table with works-today column; server-emission
  phrasing rule; explicit M3 gating on the reverse-tunnel recipe).

### Planned mitigations
None — all risks are covered in-plan; no separate before/after mitigation
tasks proposed.
