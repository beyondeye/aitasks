# applink tunnel how-to (Phase 2 — cross-network via user-owned tunnel)

Out of the box, `ait applink` pairing QRs advertise the PC's detected LAN IP,
so the phone must be on the same Wi-Fi. **Phase 2** of the
[cross-network roadmap](protocol.md#roadmap-to-cross-network) removes that
limit with zero protocol change: the phone reaches the PC through a tunnel or
mesh network the user runs, and the QR advertises that endpoint instead of the
LAN IP. The server-side mechanism is the **advertised-endpoint override** —
the `tmux.applink.advertised_*` config keys or the `--advertise-*` CLI flags
on `ait applink` and the headless runner
(`ait monitor --headless-for-applink`). The wire semantics (`kind`, `trust`,
`alt`) are canonical in
[protocol.md §Pairing flow, "Endpoint & trust model"](protocol.md#endpoint--trust-model).

## Which recipe do I want?

Every recipe below is classified by **what TLS certificate the phone sees** —
that single property determines the trust mode and whether the recipe works
with today's mobile client:

| Recipe | Phone connects to | Cert the phone sees | Trust mode | Works today? |
|---|---|---|---|---|
| [Mesh VPN](#recipe-1-mesh-vpn-tailscale--zerotier--wireguard--recommended) (Tailscale / ZeroTier / WireGuard) | PC's mesh IP | PC's self-signed cert (TLS end-to-end) | `pin` (default) | **Yes** |
| [`ssh -L` gateway forward](#recipe-2-ssh--l-gateway-forward-raw-tcp-pin-preserving) (raw TCP) | gateway `host:port` | PC's self-signed cert (TLS end-to-end) | `pin`, `kind=tunnel` | **Yes** |
| Raw-TCP public tunnel (e.g. `ngrok tcp`) | tunnel `host:port` | PC's self-signed cert (TLS end-to-end) | `pin`, `kind=tunnel` | **Yes** |
| [TLS-terminating tunnel](#recipe-3-tls-terminating-reverse-tunnel-cloudflared--ngrok-http--gated-on-mobile-ca-trust) (cloudflared / `ngrok http`) | public hostname (`:443`) | tunnel provider's public CA cert | `ca` | **No — gated on `aitasks_mobile#31_3`** (pre-that, pin mismatch is the *expected* failure) |

Anything that forwards **raw TCP** keeps TLS end-to-end between phone and PC,
so the existing self-signed cert + QR fingerprint pin keep working unchanged.
Anything that **terminates TLS at a public edge** shows the phone the
provider's CA cert instead — that needs `trust=ca`, which the mobile client
cannot complete until the per-endpoint CA-trust path (`aitasks_mobile#31_3`)
lands.

Each recipe carries a **topology line** telling you where each command runs,
where the listener is created, and what the phone actually connects to —
read it before copy-pasting.

## Recipe 1: mesh VPN (Tailscale / ZeroTier / WireGuard) — recommended

> **Topology:** config/flag set on the PC · no extra listener (the mesh
> overlay routes to the PC directly) · phone connects to the PC's mesh IP ·
> cert the phone sees: the PC's self-signed cert · trust `pin`.

A mesh VPN gives the PC a stable private IP reachable from anywhere the
phone's mesh client is signed in. Nothing about the trust model changes.

1. Install the mesh client on the PC and the phone and sign both into the
   same network (e.g. the same tailnet).
2. Find the PC's mesh IP — Tailscale: `tailscale ip -4` (a `100.x.y.z`
   address); ZeroTier: `zerotier-cli listnetworks`; plain WireGuard: the
   PC's `Address` in the tunnel config.
3. Advertise it. Either set it in `aitasks/metadata/project_config.yaml`:

   ```yaml
   tmux:
     applink:
       advertised_host: 100.101.102.103   # the PC's mesh IP
   ```

   (a commented example ships in the config) — or pass it one-shot on the
   CLI:

   ```bash
   ait applink --advertise-host 100.101.102.103
   # or headless:
   ait monitor --headless-for-applink --advertise-host 100.101.102.103
   ```

4. Show the pairing QR and scan it from the phone. Done — pairing and
   fingerprint pinning work exactly as on the LAN.

Notes:

- `advertised_kind` defaults to `mesh` when an override host is set; no need
  to set it explicitly.
- The QR still carries the detected LAN endpoint as an `alt` record
  (server-side emission). Clients that support endpoint alternatives (lands
  with `aitasks_mobile#31_2`) can use it to prefer the LAN path when
  co-located; today's clients ignore `alt` and connect to the advertised
  primary only.
- **Firewall:** the firewall doctor recognizes a numeric mesh IP owned by a
  local interface (e.g. `tailscale0`) and extends its suggested rules to
  that interface's CIDR. A mesh **DNS name** (e.g. Tailscale MagicDNS) is
  classified as external — set the numeric mesh IP as the advertised host to
  get interface-scoped firewall guidance.

## Recipe 2: `ssh -L` gateway forward (raw TCP, pin-preserving)

> **Topology:** command runs on the **gateway** · listener created on the
> **gateway** (must bind a non-loopback interface) · phone connects to
> `gateway:8765` · gateway forwards to the PC over SSH · cert the phone
> sees: the PC's self-signed cert (raw TCP passthrough) · trust `pin`.

Use this when you have a **gateway host** that (a) the phone can reach and
(b) can SSH to the PC — e.g. a VPS, or a box on a network the phone is on.
SSH forwards raw TCP, so TLS stays end-to-end between phone and PC and the
QR fingerprint pin keeps working.

1. On the **gateway** (not the PC, not your laptop), open the forward and
   bind it to a non-loopback interface so the phone can reach it:

   ```bash
   ssh -L 0.0.0.0:8765:<pc-lan-ip>:8765 user@<pc-host>
   ```

2. On the **PC**, advertise the gateway:

   ```bash
   ait applink --advertise-host <gateway-host> --advertise-kind tunnel
   ```

3. Show the QR and scan.

Common mistake: running the `ssh -L` command on the PC or your laptop
creates the listener *there*, not on the gateway — the phone then cannot
reach the advertised host and the connection fails at connect time. The
listener always lives on the machine where the `ssh` command runs.

Variants and caveats:

- **`ssh -R` (PC dials out):** if the gateway cannot SSH into the PC (NAT,
  firewall), reverse the direction — run on the **PC**:

  ```bash
  ssh -R 0.0.0.0:8765:localhost:8765 user@<gateway>
  ```

  The listener is created on the gateway; sshd only binds remote forwards
  to non-loopback interfaces when `GatewayPorts yes` (or
  `clientspecified`) is set in the **gateway's** sshd config.
- Some `ssh` builds also gate the `-L 0.0.0.0:` bind form; if the listener
  ends up loopback-only, check the bind address in `ss -tlnp`.
- **Raw-TCP public tunnels** (e.g. `ngrok tcp 8765` run on the PC) are the
  same trust class: the provider forwards raw TCP, the phone still sees the
  PC's self-signed cert, and `trust=pin` keeps working. Advertise the
  provider-assigned `host:port` with `--advertise-kind tunnel`.

## Recipe 3: TLS-terminating reverse tunnel (cloudflared / `ngrok http`) — gated on mobile CA trust

> **Topology:** tunnel daemon runs on the **PC** (outbound-only — no inbound
> port anywhere) · phone connects to the public hostname on `:443` · cert
> the phone sees: the **tunnel provider's public CA cert**, not the PC's ·
> trust `ca`.

> **Gated on `aitasks_mobile#31_3` (per-endpoint CA trust) landing
> client-side.** The tunnel edge terminates TLS, so `trust=pin` cannot
> succeed — the phone would pin-verify the provider's CA cert and fail (see
> the old-client rule in
> [Endpoint & trust model](protocol.md#endpoint--trust-model)). Until the
> mobile CA-trust path lands, that pin-mismatch failure is **expected
> behavior, not a misconfiguration**. The server-side emission
> (`advertised_trust: ca`) already works and is faithful to the spec.

Recipe (for when the mobile side lands):

1. On the PC, run the tunnel against the local applink port:

   ```bash
   cloudflared tunnel --url https://localhost:8765 --no-tls-verify
   ```

   (`--no-tls-verify` because the local origin uses the applink self-signed
   cert; the public side serves the provider's CA cert.)
2. Advertise the public hostname the tunnel prints:

   ```yaml
   tmux:
     applink:
       advertised_host: <public-hostname>
       advertised_port: 443
       advertised_kind: tunnel
       advertised_trust: ca
   ```

3. Show the QR and scan.

A future sibling task (`aitasks#1061_3`) turns this recipe into a near-turnkey
flow: `ait applink` spawns the quick tunnel itself and encodes the public URL
in the QR automatically.

## Operational security cautions

The recipes above expose the applink server beyond the LAN. Pairing tokens
are single-use with a short TTL and every session needs a valid bearer (see
[security.md](security.md) for the full posture), but observe basic hygiene:

- **Use gateways and tunnel accounts you trust.** A raw-TCP gateway cannot
  read frame contents (TLS is end-to-end) but can observe traffic volume and
  timing. A **TLS-terminating tunnel edge sees plaintext frames** — treat the
  provider accordingly.
- **Restrict the listener where practical** — scope the gateway's firewall to
  the source ranges your phone actually uses instead of `0.0.0.0/0`.
- **Tear tunnels down when done.** A forgotten forward is an open door to
  your pairing endpoint.
- **If a QR may have been exposed** beyond the intended phone (screen share,
  photo), generate a fresh one (TUI `r` keybinding) before pairing — and
  revoke any session you don't recognize from the TUI.

## Troubleshooting

- **Invalid `advertised_host` in config** → the server does not emit a broken
  QR; it falls back to the LAN address and prints a visible warning (the
  headless runner prints it after the pairing block; the TUI shows it in the
  pairing-screen advisory). Fix the value and re-show the QR.
- **Accepted host forms:** a leading scheme (`https://…`), path, and trailing
  slashes are stripped; `host:port` and bracketed IPv6 (`[fd7a::1]:443`) are
  accepted; an embedded port acts as `advertised_port` unless that is set
  explicitly. You can paste the hostname straight from your tunnel/mesh UI.
- **CLI vs config precedence:** any `--advertise-*` flag makes the CLI define
  the *entire* override — all `advertised_*` config keys are then ignored (no
  field mixing). `--advertise-port/-kind/-trust` require `--advertise-host`.
- **Pin mismatch against a TLS-terminating tunnel** is expected until the
  mobile CA-trust path (`aitasks_mobile#31_3`) lands — see the
  [recipe table](#which-recipe-do-i-want). If you need cross-network *now*,
  use the mesh or raw-TCP recipes instead.
