---
Task: t1061_applink_outside_network_connectivity_roadmap.md
Worktree: (none — fast profile, current branch)
Branch: main (current branch)
Base branch: main
---

# t1061 — AppLink outside-network connectivity: paired cross-repo decomposition

## Context

`ait applink` is LAN-only today: pairing (`.aitask-scripts/applink/pairing.py`)
encodes only `detect_lan_ip()` into the QR (`applink://<lan-ip>:<port>/pair?…`),
the phone dials that frozen IP directly with the self-signed cert's SHA-256
fingerprint as the *entire* trust anchor, and there is no reconnect, failover,
or public-endpoint path on either side. t1061 is an umbrella task explicitly
meant to be **decomposed, not implemented as one unit**, spanning this repo
(server) and `aitasks_mobile` (client, `xdeprepo`).

This plan is a **paired cross-repo decomposition** (per the Cross-Repo Planning
Procedure): it designs ≥2 children on each side, assigned nominally to the
local parent (t1061) or a future counterpart parent in `aitasks_mobile`.
**Nothing is created until this plan is approved**; the Cross-Repo Child
Assignment Procedure then creates the mobile parent and all children with the
symbolic deps below resolved to real IDs.

## Prerequisite check (Tier 0 — verified satisfied)

The source task mandates Tier-0 work "before decomposing/starting t1061".
Verified against `aitasks/archived/` in this session:

| Task | Tier | Status |
|------|------|--------|
| t1054 keyframe viewport-only rows | 0 | **archived** ✅ |
| t1055 `pause` flow-control verb | 0 | **archived** ✅ |
| t1007 data-plane DoS/resource caps | 0 | **archived** ✅ |
| t1045 roster-vs-focused content split | 0 | **archived** ✅ |
| t1057 history RPC scrollback | 1 | **archived** ✅ |
| t1056 `viewport_hint` clipping | 1 | active — does **not** gate this decomposition (bandwidth optimization, independent of connectivity; its value pairs with mobile work but no child below depends on it) |

Hard gate t985 (security review) is done/archived; its residuals are the
Tier-2 tasks t1066/t1067/t1068, referenced (not duplicated) below. **The
decomposition is therefore cleared to proceed.**

### Key exploration facts the design rests on

**Server (this repo):**
- `pairing.build_pairing_uri(token, ip, port, fp, hostname)` already takes `ip`
  as a parameter — the natural injection point. The host is chosen at the two
  call sites: `applink_app.AppLinkRuntime.__init__` (line 93,
  `self.ip = detect_lan_ip()`) and `headless.serve` (line 126). **No override
  (config / env / CLI) exists anywhere.** TUI argparse exposes only `--smoke`;
  headless has `--port` only.
- Server binds `0.0.0.0` already (`server.py` line 36) — a tunnel/mesh interface
  is reachable at the socket level; only the QR host and firewall scoping keep
  it LAN. **Bind address and advertised address are already independent
  concepts** — this plan never touches the bind side.
- Cert (`tls.py`): fixed `CN=ait-applink`, **no SANs**, 10-year validity — but
  trust is pure fingerprint pinning, so **mesh VPN (Phase-2 A1: Tailscale etc.)
  works with the existing cert + pin unchanged**. Only TLS-terminating tunnels
  (A2: cloudflared/ngrok) break pinning. The no-SAN cert also means any
  origin-validating tunnel client (cloudflared) must be told to skip origin
  verification (see A3).
- Applink config idiom: `tmux.applink.*` keys in
  `aitasks/metadata/project_config.yaml`, parsed by
  `server.load_applink_config()` (fault-tolerant).
- Firewall doctor (`firewall_doctor.py`) scopes all rules to the **LAN CIDR of
  the interface owning `lan_ip`** — a mesh/tunnel interface (e.g. `tailscale0`,
  100.64.0.0/10) is never covered.
- Protocol constraints (`aidocs/applink/protocol.md` §Roadmap): Phase 2 must
  **not** change the QR scheme (additive query params are allowed without a `v`
  bump); the scheme change (`applink://<broker>/r/<session-id>`) is reserved
  for Phase 3. Phase-3 relay design is explicitly deferred to a design task "to
  be created after Phase 1 lands" — which it has.
- `MAX_PER_IP = 8` admission cap keys on peer IP — behind a relay/tunnel all
  traffic shares one source IP (recorded as a Phase-3 design consideration;
  also relevant to A3 since tunneled connections arrive from localhost).

**Mobile (`aitasks_mobile`):**
- `QrUrl.kt` parser accepts **any host string already** (no IPv4/RFC1918
  validation) — an FQDN or Tailscale 100.x IP parses today. Bracketless IPv6
  would mis-split on `lastIndexOf(':')`. **Unknown query params are collected
  into a `Map` and silently ignored** (safe for old clients), but **repeated
  keys collapse to the last value** — so the endpoint spec below uses a single
  `alt=` param carrying a list, never repeated params.
- Storage is Room (`ConnectionDBO`, PK = `fp`, single frozen `host`/`port`;
  bearer in platform SecretStore keyed by fp). Adding nullable/defaulted
  columns is a trivial AutoMigration (v4→v5 precedent exists); a one-to-many
  table has the `pane_status` precedent.
- TLS pinning is the entire trust anchor on **both** platforms
  (`HttpClientFactory.android.kt` custom TrustManager + `hostnameVerifier
  {_,_→true}`; `HttpClientFactory.ios.kt` Darwin `handleChallenge`). **No
  system-CA path exists**; trust-policy changes must be made twice
  (expect/actual).
- **No reconnect, no backoff, no connectivity/network-change detection
  anywhere.** Wi-Fi→cellular = socket dies → `SessionState.Disconnected`,
  terminal. Protocol-level `Suspended → Connected` resume exists but assumes
  the same live socket; `PairClient.resume` (bearer re-validation) exists but
  is unused on connect.
- Nearly all connection logic is `commonMain` (`:domain`), so
  failover/retry/racing logic is written once.
- No mobile task tracks any of this yet.

## Endpoint & trust model (normative for A1/A3/M2/M3)

**Trust is a property of an endpoint, not of a connection.** A single paired
connection may simultaneously offer a pin-trusted LAN endpoint and a
CA-trusted tunnel endpoint (A3 is exactly this case). The pairing spec and the
mobile storage model both encode trust per endpoint.

**Endpoint record** (the unit A1 emits, M2 stores, M3 evaluates):

```
endpoint := host, port, kind, trust
kind     := lan | mesh | tunnel        (racing preference hint; lan preferred)
trust    := pin | ca                   (pin = QR fp is the trust anchor;
                                        ca = platform CA chain + real hostname
                                        verification, fp not consulted)
```

**QR wire encoding** (all additive query params — same `applink://` scheme, no
`v` bump; old clients read only the authority + `t`/`fp`/`name` and ignore the
rest):

- URL authority (`applink://<host>:<port>/pair`) = the **primary endpoint**.
  Its metadata rides in two optional params: `kind=<kind>` and `trust=<trust>`
  (defaults when absent: `kind=lan`, `trust=pin` — exactly today's semantics).
- `alt=` = **single** param (never repeated — see the map-collapse hazard
  above), value is a URL-encoded comma-separated list of alternate endpoint
  records, each record `host:port;kind;trust` (fields `;`-separated, in that
  fixed order, all mandatory within a record).
- IPv6 hosts are bracketed (`[fd7a::1]:8765`) in both the authority and `alt`
  records. (The current mobile parser mis-splits bracketless IPv6; M2's parser
  handles brackets. Server-side emission always brackets IPv6.)
- `fp=` remains mandatory and connection-scoped (it is the PK/SecretStore
  alias and the anchor for every `trust=pin` endpoint). A QR whose endpoints
  are all `trust=ca` still carries `fp` for identity continuity.
- Advertised host/port are **advertisement-only**: the server keeps binding
  `0.0.0.0:<port>`; `advertised_port` exists because a tunnel may expose a
  different public port than the local serving port.

The full grammar is documented once, in `protocol.md` §Pairing, by A1. A3
emits it; M2 parses/stores it; M3 enforces per-endpoint trust. Old clients:
connect to the primary endpoint with pin semantics — so any QR whose primary
endpoint is `trust=ca` is **not** backward compatible and A3 must keep the
LAN/pin endpoint as primary when co-located compatibility matters (decision
recorded in A3).

## Paired decomposition

**Local parent:** t1061 (this task — becomes parent-of-children).
**Cross-repo parent (to be created in `aitasks_mobile`):**
"AppLink outside-network connectivity — mobile client (paired with aitasks#1061)"
— labels `[applink]`, `xdeprepo: aitasks` back-reference, mirrors the roadmap
context from t1061.

| Label | Side | Nominal parent | issue_type / effort / priority | In-repo deps | Cross-repo deps | Title |
|-------|------|----------------|-------------------------------|--------------|-----------------|-------|
| **A1** | local | t1061 | feature / medium / medium | — | — | Advertised-endpoint override + endpoint/trust pairing spec |
| **A2** | local | t1061 | documentation / low / medium | A1 | — | Phase-2 tunnel how-to (mesh-VPN lead) + roadmap status update |
| **A3** | local | t1061 | feature / high / medium | A1 | M3 | Auto-spawned Cloudflare Quick Tunnel (turnkey Phase 2) |
| **A4** | local | t1061 | documentation / high / medium | — | — | Phase-3 relay-broker design (design-only) |
| **A5** | local | t1061 | documentation / medium / low | — | — | Hosted-box deployment guide (Alternative B) |
| **M1** | cross-repo | mobile parent | feature / high / medium | — | — | Reconnect, backoff & network-change detection |
| **M2** | cross-repo | mobile parent | feature / high / medium | — | A1 | Multi-endpoint model + LAN-vs-tunnel racing (LocalFirstAdapter) |
| **M3** | cross-repo | mobile parent | feature / medium / medium | M2 | A1 | Per-endpoint CA-trust path for TLS-terminating tunnel endpoints |

Dependency DAG (edges point at prerequisites):
`A2→A1`; `A3→{A1, M3}`; `M2→A1`; `M3→{M2, A1}`; `A4`, `A5`, `M1` independent.

(M3 depends on M2 so per-endpoint trust is stored on M2's endpoint records
from day one — no interim connection-level trust column to migrate away from.
M1↔M2 have **no dependency edge**: M1 owns reconnect/backoff, M2 owns
endpoint storage + racing on dial; whichever lands second integrates racing
into the retry loop, and each child's brief names that integration point.)

### A1 — Advertised-endpoint override + pairing spec (local, feature)

The single enabling change for Phase 2: let the QR advertise user-chosen
endpoint(s) instead of (or alongside) the detected LAN IP, and pin down the
endpoint/trust wire grammar.

- **Spec first:** document the **Endpoint & trust model** section above in
  `protocol.md` §Pairing (endpoint record, `kind=`/`trust=`/`alt=` grammar,
  single-param `alt` rationale, IPv6 bracketing, defaults, old-client
  behavior). This is the one canonical definition A3/M2/M3 build against.
- **Config:** new `tmux.applink.advertised_host` (string, FQDN or any IP) and
  `tmux.applink.advertised_port` (optional int, defaults to serving port) in
  `aitasks/metadata/project_config.yaml`; parse in `load_applink_config()`
  (follow the `history_capture_lines` pattern — fault-tolerant). Optional
  `tmux.applink.advertised_kind` (`lan|mesh|tunnel`, default `mesh` when an
  override is set — the manual-override use case is a mesh VPN) and
  `tmux.applink.advertised_trust` (`pin|ca`, default `pin`) — the trust knob
  is what lets a **manually run** TLS-terminating tunnel (user's own
  cloudflared/ngrok, no A3) advertise `trust=ca`; without it only A3's
  auto-spawn path could ever emit CA endpoints.
- **CLI:** `--advertise-host` / `--advertise-port` / `--advertise-trust` on
  `headless.py` argparse and `applink_app.py` argparse. Precedence:
  CLI > config > `detect_lan_ip()` (+ `pin` default for trust).
- Emitting `trust=ca` is useless until M3 lands client-side — A1 emits it
  faithfully but A2's how-to marks the manual reverse-tunnel recipe as gated
  on M3 (old/pre-M3 clients pin-verify and fail; same caveat as A3's
  primary-endpoint decision).
- **Emission:** thread the override into `AppLinkRuntime.__init__`/
  `build_uri()` and `headless.serve()`. When both an override and a detected
  LAN IP exist, primary = override endpoint, `alt` = LAN endpoint
  (`;lan;pin`). Bind address untouched (`0.0.0.0`).
- **Firewall doctor awareness:** when an override host is set and does not
  belong to the LAN interface, either resolve the owning interface's CIDR
  (mesh case, e.g. `tailscale0` → 100.64.0.0/10) for the scoped rules, or emit
  an explicit "override endpoint not covered by these rules" line. Do not
  silently print LAN-only guidance for a tunnel endpoint.
- **Tests:** unit tests for config parsing, precedence, URI emission (primary +
  `alt` grammar incl. IPv6 bracketing and URL-encoding), and firewall-doctor
  override messaging.

### A2 — Phase-2 tunnel how-to + roadmap status (local, documentation)

- New `aidocs/applink/tunnel_howto.md`: lead with **mesh VPN (Tailscale /
  ZeroTier / WireGuard)** — existing cert + pin work unchanged, set
  `advertised_host` to the mesh IP, done. Then `ssh -L` port-forward. Then the
  **manual reverse-tunnel recipe** (user-run cloudflared/ngrok:
  `advertised_host` = public hostname + `advertised_trust: ca`) — explicitly
  marked as gated on M3 landing client-side; until then fingerprint pinning
  fails against the tunnel's CA cert (link M3/A3).
- Update `protocol.md` §Roadmap Phase-2 status (current-state-only prose, per
  documentation conventions) and cross-link from `wish_ssh_evaluation.md` where
  it frames wish as the Phase-2 escape hatch.
- Consider a user-facing website page later; aidocs is the source of truth now.

### A3 — Auto-spawned Cloudflare Quick Tunnel (local, feature)

Near-turnkey Phase 2 (9remote's model): the app runs the tunnel itself.

- **Origin TLS is a mandatory first verification step, not an assumption.**
  The applink origin is `wss://` with a self-signed, no-SAN cert; cloudflared
  validates origin certificates by default, so the quick tunnel would connect
  but fail to proxy. The child must empirically verify and document the
  working invocation — expected shape:
  `cloudflared tunnel --url https://localhost:<port> --no-tls-verify`
  (or `originRequest: {noTLSVerify: true}` config) — and confirm WebSocket
  upgrade proxying end-to-end before any UI work. The skipped origin
  verification is loopback-only (cloudflared → localhost), which the child
  documents as an accepted, bounded trust step. If quick tunnels turn out not
  to support the needed origin flags, fall back to documenting named tunnels
  (account required) and record the deviation.
- Spawn + supervise the `cloudflared` child process (detect binary; lifecycle
  tied to the applink server; clean shutdown), parse the generated
  `*.trycloudflare.com` URL.
- **QR emission (per the endpoint model):** tunnel endpoint =
  `host=<x>.trycloudflare.com, port=443, kind=tunnel, trust=ca`; LAN endpoint
  stays available with `;lan;pin`. **Decision for the child:** primary =
  tunnel + `trust=ca` maximizes remote turnkey-ness but breaks old clients
  scanning that QR (they'd pin-verify Cloudflare's cert and fail) — the child
  chooses primary=LAN/pin with tunnel in `alt` (compatible; M2 clients race
  and reach the tunnel) unless the pairing UI offers an explicit
  "remote-first QR" toggle. Record the choice in the child's plan.
- TUI + headless surfaces: opt-in flag/config (`tmux.applink.auto_tunnel:
  cloudflared`), status line showing tunnel state.
- Depends on **M3** (client must accept per-endpoint `trust=ca`) — staged so
  the client capability lands first. Note `MAX_PER_IP`: tunneled connections
  all arrive from loopback; verify the cap doesn't bite (t1007 caps context).
- Security note in-task: quick tunnels are ephemeral public hostnames; bearer +
  permission profiles still gate every verb; recommend pairing with t1068
  (rate-limit) for sustained use.

### A4 — Phase-3 relay-broker design (local, design-only documentation)

The design task `protocol.md` explicitly defers until Phase 1 lands (it has).
Produces `aidocs/applink/relay_broker_design.md`; **no implementation**.

- Outbound-dial model (PC dials broker; validated by Claude Code Remote
  Control's outbound-HTTPS-only architecture), self-hostable broker.
- New QR scheme `applink://<broker-host>/r/<session-id>` (the reserved Phase-3
  scheme change), broker pinning replacing direct cert pinning, **end-to-end
  key exchange** so the broker never sees frame contents (its own crypto spec
  + security-review addendum extending `security.md`).
- Design considerations to capture: `MAX_PER_IP=8` collapses behind a relay
  (all clients share the broker's source IP); short-lived purpose-scoped
  credentials (Remote Control pattern, feeds t1067); reconnect semantics
  mapping `Suspended → Connected` onto relay session stitching; persistent
  PTY/session daemon surviving restarts (9remote) as a resume-robustness
  option; Phase-4 WebRTC signaling as a forward-compatibility section only.

### A5 — Hosted-box deployment guide (local, documentation, low priority)

Alternative B per `wish_ssh_evaluation.md`: run the applink server on an
always-on public VM (PC can be off).

- Deployment guide: dedicated tmux socket (`AITASKS_TMUX_SOCKET`), systemd
  unit, real CA cert story vs pinning, firewall posture, and the hardening
  checklist referencing **t1066 (cert rotation), t1067 (bearer rotation),
  t1068 (rate-limit)** as the Tier-2 prerequisites for sustained public
  exposure. No new protocol work.

### M1 — Reconnect, backoff & network-change detection (mobile, feature)

Independent value even on LAN (Wi-Fi blips currently kill the session dead).

- Connectivity monitoring via expect/actual (`ConnectivityManager` callback on
  Android, `NWPathMonitor` on iOS) surfaced as a common `Flow`.
- Auto re-dial with exponential backoff + jitter from
  `SessionState.Disconnected`/socket-drop, re-entering the session via the
  existing bearer (`resume` verb — `PairClient.resume` exists and is currently
  unused on connect); map cleanly onto the server's `Suspended → Connected`
  state machine (`KtorMonitorStreamClient` needs re-openability — today
  `open()` is one-shot CAS).
- Outage policy: give up / surface to user after a bounded window (Remote
  Control uses ~10 min; align with bearer TTL semantics).
- All in `commonMain` (`MonitorSessionMediator`, `KtorMonitorStreamClient`)
  except the connectivity expect/actuals.
- **Integration point with M2 (no dep edge):** the re-dial step targets "the
  connection's endpoint(s)"; if M2 has landed, that means the racing dialer,
  otherwise the single stored host/port. Whichever child lands second wires
  the two together and says so in its Final Implementation Notes.

### M2 — Multi-endpoint model + LAN-vs-tunnel racing (mobile, feature)

- Room migration (v4→v5): endpoints per connection — follow the `pane_status`
  one-to-many precedent: new `connection_endpoint` table
  (fp FK, host, port, **kind**, **trust**, priority, last_good_at) rather than
  overloading the single `host`/`port` columns (which remain as the
  primary/last-good endpoint for backward compat).
- Parse the A1 spec at pairing time: `kind=`/`trust=` for the primary
  endpoint, the single `alt=` list for alternates (handle `;`-separated
  records, URL-decoding, **bracketed IPv6** — fixing the `lastIndexOf(':')`
  mis-split for bracketed hosts as part of the new parsing).
- Racing dial (9remote's `LocalFirstAdapter`): attempt endpoints concurrently
  or staggered, first successful TLS+auth wins, prefer `kind=lan` when
  co-located; remember last-good endpoint. Each attempt uses **that
  endpoint's** trust mode (pin-only until M3 lands: `trust=ca` endpoints are
  stored but skipped with a "requires CA trust" marker, so M2 is fully
  functional standalone).
- Update `mapTransportError`/UX so multi-endpoint failures aggregate sensibly.

### M3 — Per-endpoint CA-trust path (mobile, feature)

- Consumes M2's endpoint records: trust mode is read **per endpoint** (never
  per connection) — this is what lets one connection race a pinned LAN
  endpoint against a CA-trusted tunnel endpoint (A3's QR).
- Trust-mode plumbing through `createPinnedHttpClient` (signature grows to a
  per-dial trust policy, expect + both actuals):
  - **pin** (default, unchanged): fingerprint check, no CA, no hostname.
  - **ca**: platform default trust chain **and real hostname verification**
    (Android: default `TrustManager` + default `HostnameVerifier`; iOS:
    default challenge handling) — no fingerprint check.
- Safe-by-default: absent/unknown `trust` field ⇒ `pin`. Pairing UI shows a
  distinct confirmation when a scanned QR contains any `trust=ca` endpoint
  (user consents to trusting the tunnel provider for that endpoint).
- Un-skip the `trust=ca` endpoints M2 parked; `PairError` mapping extended so
  a CA failure isn't mislabeled `PinFailed`.

## Suggested implementation order

1. **A1** (spec + override; mesh-VPN Phase 2 works the moment it lands)
2. **A2** (cheap; documents the now-working mesh path)
3. **M1** (independent; biggest UX win, helps LAN users too)
4. **M2** (endpoint model + racing, pin-only)
5. **M3** (per-endpoint CA trust) → 6. **A3** (tunnel emission, staged last)
7. **A4** anytime (design-only); **A5** last (low priority).

## Out of scope (recorded, not planned)

- **Phase-4 WebRTC/P2P** — deferred until the Phase-3 design (A4) lands;
  protocol.md already frames it as Phase-3-plus-`ice=`.
- **Persistent PTY daemon surviving restarts** (9remote refinement 5) — noted
  in A4's design considerations, not a child here.
- **t1056** (`viewport_hint` clipping) — active Tier-1 task, independent of
  connectivity; not a dependency of any child.
- **Tier-2 hardening (t1066/t1067/t1068)** — already tracked as independent
  tasks; referenced by A3/A5/A4, not duplicated as children.

## Trade-offs / rejected alternatives

- **Per-connection trust mode** — rejected: A3's QR legitimately mixes a
  pin-trusted LAN endpoint with a CA-trusted tunnel endpoint; connection-level
  trust either breaks the LAN alt path or forces trust inference the protocol
  doesn't carry. Trust rides on each endpoint record instead.
- **Repeatable `alt=` params** — rejected: the current mobile parser collapses
  repeated query keys (last-wins map); a single `alt=` list param is immune
  and equally additive.
- **M3 before M2 (connection-level trust column now, migrate later)** —
  rejected: creates a throwaway schema step; M3 now depends on M2 so trust is
  per-endpoint from day one.
- **Single parent with children straddling both repos** — rejected; the
  cross-repo procedure mandates one parent per repo with cross edges only.
- **Putting the endpoint/trust spec in A3/M3** — rejected; A3, M2 and M3 all
  consume it, so the spec lives once in A1's protocol.md update.
- **Overloading `ConnectionDBO.host` with a CSV of endpoints** — rejected in
  favor of a proper one-to-many table (stable-handle/mutable-manifest split;
  `pane_status` precedent).
- **Building Phase 3 now instead of the tunnel path** — rejected; protocol.md
  stages it behind a design task, and Phase 2 delivers reach with ~zero
  protocol work.

## Post-approval mechanics (for the executor)

- Cross-Repo Child Assignment Procedure (Step 7) creates the mobile parent in
  `aitasks_mobile`, then all 8 children (A1–A5 under t1061; M1–M3 under the
  mobile parent), resolving the symbolic deps above to real IDs (`xdeps:` +
  `xdeprepo:` for cross edges), demotes t1061 to parent-of-children, and
  presents its child checkpoint.
- Each child task body must carry its full brief from this plan (context, key
  files, endpoint-model rules, verification) — children run in fresh contexts.
- **Step 9 (Post-Implementation)** applies to this parent only after all
  children complete (archival via `aitask_archive.sh`); no code changes land
  from this planning session.

## Verification (graph-level, post-creation)

Existence checks alone are insufficient — verify the **exact edges and
back-references** against this table before ending the session:

1. **Local children** — read frontmatter of each created `aitasks/t1061/t1061_*`:
   - A1: no `depends` beyond auto-sibling wiring; no `xdeps`.
   - A2: `depends` includes A1's real ID.
   - A3: `depends` includes A1's real ID; `xdeps` includes
     `aitasks_mobile#<M3-real-id>`; `xdeprepo: aitasks_mobile`.
   - A4, A5: no cross edges.
2. **Mobile parent** — via `ait projects exec aitasks_mobile` (or direct
   read): carries `xdeprepo: aitasks` and a body reference to `aitasks#1061`;
   t1061's body/plan references the mobile parent's real ID (bidirectional
   link).
3. **Mobile children** — read each created child in `aitasks_mobile`:
   - M1: no cross edges.
   - M2: `xdeps` includes `aitasks#<A1-real-id>`.
   - M3: `depends` includes M2's real ID; `xdeps` includes `aitasks#<A1-real-id>`.
4. **Negative check** — no child may depend on a label's *nominal* form
   (`A1`/`M3` literals) or a wrong-repo notation; resolve every recorded xdep
   with `./.aitask-scripts/aitask_query_files.sh --project <repo> task-file
   <id>` and confirm it lands on the intended file.
5. **Content check** — spot-read A3's and M3's created bodies: both must state
   the per-endpoint trust rule and A3 must contain the cloudflared
   origin-TLS verification step; A1's body must contain the wire grammar.
   Confirm the Tier-0-satisfied note is reflected in t1061's plan (this file).
6. Functional verification happens per-child (each child's brief includes its
   own tests/verification).

## Created tasks (label → real ID, resolved 2026-07-02)

- Cross-repo parent: **aitasks_mobile#31** (`t31_applink_outside_network_connectivity_mobile.md`)
- A1 → `t1061_1` · A2 → `t1061_2` (deps A1) · A3 → `t1061_3` (deps A1; xdeps `aitasks_mobile#31_3`) · A4 → `t1061_4` · A5 → `t1061_5`
- M1 → `aitasks_mobile#31_1` · M2 → `aitasks_mobile#31_2` (xdeps `aitasks#1061_1`) · M3 → `aitasks_mobile#31_3` (deps M2; xdeps `aitasks#1061_1`)
