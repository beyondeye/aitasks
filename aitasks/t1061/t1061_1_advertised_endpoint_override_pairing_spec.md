---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [applink, applink_connectivity]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1061
implemented_with: claudecode/fable5
created_at: 2026-07-02 23:45
updated_at: 2026-07-05 16:44
---

**A1 of the t1061 paired decomposition** (see
`aiplans/p1061_applink_outside_network_connectivity_roadmap.md` — its
"Endpoint & trust model" section is normative for this child). The single
enabling change for Phase 2: let the QR advertise user-chosen endpoint(s)
instead of (or alongside) the detected LAN IP, and pin down the endpoint/trust
wire grammar that A3 (auto tunnel), and mobile M2/M3
(`aitasks_mobile#31_2`/`31_3`) build against.

## Context

- The advertised host is always `detect_lan_ip()` today — chosen at exactly
  two call sites: `applink_app.AppLinkRuntime.__init__` (`self.ip =
  detect_lan_ip()`) and `headless.serve`. **No override (config / env / CLI)
  exists.** `pairing.build_pairing_uri(token, ip, port, fp, hostname)` already
  takes `ip` as a parameter — no signature change needed for the primary host.
- Server bind stays untouched (`0.0.0.0`, `server.py`); advertised host/port
  are advertisement-only (a tunnel may expose a different public port).
- Mesh VPN (Tailscale/ZeroTier/WireGuard) works with the existing self-signed
  cert + fingerprint pin unchanged — this child alone makes Phase-2 A1 (mesh)
  fully functional.

## Endpoint & trust wire grammar (spec first — document in protocol.md §Pairing)

```
endpoint := host, port, kind, trust
kind     := lan | mesh | tunnel        (racing preference hint; lan preferred)
trust    := pin | ca                   (pin = QR fp is the trust anchor;
                                        ca = platform CA chain + real hostname
                                        verification, fp not consulted)
```

- Primary endpoint = URL authority (`applink://<host>:<port>/pair`); its
  metadata rides in optional `kind=` / `trust=` params (defaults `lan`/`pin` —
  exactly today's semantics).
- `alt=` = **single** param (never repeated — the current mobile parser
  collapses repeated query keys last-wins), value = URL-encoded
  comma-separated list of `host:port;kind;trust` records (fields `;`-separated,
  fixed order, all mandatory within a record).
- IPv6 hosts bracketed (`[fd7a::1]:8765`) in authority and `alt` records;
  server-side emission always brackets IPv6.
- `fp=` stays mandatory and connection-scoped (anchor for every `trust=pin`
  endpoint; kept for identity continuity even in all-`ca` QRs).
- All params are additive — same `applink://` scheme, no protocol `v` bump;
  old clients read only authority + `t`/`fp`/`name` and ignore the rest.

## Key files to modify

- `aidocs/applink/protocol.md` — §Pairing: document the grammar above
  (endpoint record, `kind=`/`trust=`/`alt=`, single-param `alt` rationale,
  IPv6 bracketing, defaults, old-client behavior). One canonical definition.
- `aitasks/metadata/project_config.yaml` + `server.load_applink_config()` —
  new keys (follow the fault-tolerant `history_capture_lines` pattern):
  - `tmux.applink.advertised_host` (string, FQDN or any IP)
  - `tmux.applink.advertised_port` (optional int, defaults to serving port)
  - `tmux.applink.advertised_kind` (`lan|mesh|tunnel`, default `mesh` when an
    override is set — the manual-override use case is a mesh VPN)
  - `tmux.applink.advertised_trust` (`pin|ca`, default `pin`) — lets a
    **manually run** TLS-terminating tunnel (user's own cloudflared/ngrok, no
    A3) advertise `trust=ca`
- `.aitask-scripts/applink/headless.py` + `.aitask-scripts/applink/applink_app.py`
  — CLI: `--advertise-host` / `--advertise-port` / `--advertise-kind` /
  `--advertise-trust`. Precedence is **group-level**: any `--advertise-*`
  flag makes the CLI define the entire override (all `advertised_*` config
  keys ignored — no field mixing, so a one-shot CLI host can't inherit a
  stale configured kind/trust); otherwise config; otherwise
  `detect_lan_ip()`. Defaults within the winning group: port = explicit >
  embedded-in-host > serving port; kind `mesh`; trust `pin`.
  (`--advertise-kind` added during planning to close the stale-config
  coupling gap.)
- Emission: thread the override into `AppLinkRuntime.__init__`/`build_uri()`
  and `headless.serve()`. When both an override and a detected LAN IP exist:
  primary = override endpoint, `alt` = LAN endpoint (`;lan;pin`).
- `.aitask-scripts/applink/firewall_doctor.py` — when an override host is set
  and does not belong to the LAN interface, either resolve the owning
  interface's CIDR (mesh case, e.g. `tailscale0` → 100.64.0.0/10) for the
  scoped rules, or emit an explicit "override endpoint not covered by these
  rules" line. Never silently print LAN-only guidance for a tunnel endpoint.

## Notes

- Emitting `trust=ca` is useless until M3 (`aitasks_mobile#31_3`) lands
  client-side — emit it faithfully; the A2 how-to marks the manual
  reverse-tunnel recipe as gated on M3 (pre-M3 clients pin-verify and fail).

## Verification

- Unit tests: config parsing, precedence (CLI > config > detect), URI emission
  (primary + `alt` grammar incl. IPv6 bracketing and URL-encoding),
  firewall-doctor override messaging.
- Manual: set `advertised_host` to a Tailscale IP, scan QR, confirm pairing
  works over the mesh with the unchanged pin.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-05T13:44:06Z status=pass attempt=1 type=human
