---
Task: t1061_1_advertised_endpoint_override_pairing_spec.md
Parent Task: aitasks/t1061_applink_outside_network_connectivity_roadmap.md
Sibling Tasks: aitasks/t1061/t1061_2_*.md, aitasks/t1061/t1061_3_*.md, aitasks/t1061/t1061_4_*.md, aitasks/t1061/t1061_5_*.md
Archived Sibling Plans: aiplans/archived/p1061/p1061_*_*.md
Worktree: aiwork/t1061_1_advertised_endpoint_override_pairing_spec
Branch: aitask/t1061_1_advertised_endpoint_override_pairing_spec
Base branch: main
---

# Plan: A1 — Advertised-endpoint override + endpoint/trust pairing spec

Authoritative design: parent plan
`aiplans/p1061_applink_outside_network_connectivity_roadmap.md`
(§"Endpoint & trust model" is normative — read it first). The task body
carries the full brief; this plan sequences the work.

## Steps

1. **Spec (docs first).** Add the endpoint/trust wire grammar to
   `aidocs/applink/protocol.md` §Pairing: endpoint record
   (`host, port, kind∈{lan,mesh,tunnel}, trust∈{pin,ca}`), primary endpoint =
   URL authority with optional `kind=`/`trust=` params (defaults `lan`/`pin`),
   single `alt=` param carrying URL-encoded comma-separated
   `host:port;kind;trust` records, IPv6 bracketing, `fp=` stays mandatory and
   connection-scoped, old-client behavior (additive params, no `v` bump).
   Include the single-param rationale (mobile parser collapses repeated keys).
2. **Config keys.** `aitasks/metadata/project_config.yaml` +
   `server.load_applink_config()` (follow `history_capture_lines` pattern):
   `advertised_host`, `advertised_port` (default: serving port),
   `advertised_kind` (default `mesh` when an override is set),
   `advertised_trust` (default `pin`). Fault-tolerant parsing; also update the
   seed copy if `seed/` ships a project_config template (check).
3. **CLI flags.** `--advertise-host` / `--advertise-port` /
   `--advertise-trust` on both `.aitask-scripts/applink/headless.py` and
   `.aitask-scripts/applink/applink_app.py` argparsers. Precedence:
   CLI > config > `detect_lan_ip()` (+ `pin` default).
4. **Emission.** Thread the resolved advertised endpoint into
   `AppLinkRuntime.__init__`/`build_uri()` and `headless.serve()`. When both
   an override and a detected LAN IP exist: primary = override,
   `alt=<lan-ip>:<port>;lan;pin`. Extend `pairing.build_pairing_uri` with the
   optional `kind`/`trust`/`alt` params (keep backward-compatible defaults).
   Always bracket IPv6 hosts.
5. **Firewall doctor.** In `firewall_doctor.py` / its call sites: when the
   advertised host is not on the LAN interface, resolve the owning
   interface's CIDR (mesh case) or emit an explicit "override endpoint not
   covered by these rules" line.
6. **Tests.** Config parsing, precedence, URI emission (primary + `alt`
   grammar, IPv6, URL-encoding), firewall-doctor override messaging.

## Verification

- `bash tests/test_<new>.sh` (new unit tests) + existing applink tests still
  pass; `shellcheck` untouched (Python-only + yaml + docs).
- Manual: set `advertised_host` to a Tailscale IP, scan QR, pair over mesh
  with the unchanged pin.

## Step 9 (Post-Implementation)

Standard cleanup/merge/archival per task-workflow Step 9.
