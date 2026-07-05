---
Task: t1061_1_advertised_endpoint_override_pairing_spec.md
Parent Task: aitasks/t1061_applink_outside_network_connectivity_roadmap.md
Sibling Tasks: aitasks/t1061/t1061_2_*.md, aitasks/t1061/t1061_3_*.md, aitasks/t1061/t1061_4_*.md, aitasks/t1061/t1061_5_*.md
Archived Sibling Plans: aiplans/archived/p1061/p1061_*_*.md
Worktree: (none — fast profile, current branch)
Branch: main (current branch)
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-05 16:40
---

# Plan: A1 — Advertised-endpoint override + endpoint/trust pairing spec (t1061_1)

## Context

`ait applink` pairing QRs today always advertise `detect_lan_ip()` — LAN-only.
This child (A1 of the t1061 paired decomposition) adds a user-chosen
advertised endpoint (config + CLI) and pins down the endpoint/trust wire
grammar that A3 (auto tunnel) and mobile M2/M3 (`aitasks_mobile#31_2`/`31_3`)
build against. Normative design: parent plan
`aiplans/p1061_applink_outside_network_connectivity_roadmap.md`
§"Endpoint & trust model". Mesh VPN (Tailscale etc.) becomes fully functional
from this child alone — existing self-signed cert + pin unchanged.

**Verified against current sources (2026-07-05):**
- `pairing.build_pairing_uri(token, ip, port, fingerprint, hostname)` — takes
  `ip`; no signature change needed for the primary host (`pairing.py:60`).
- Host chosen at exactly two call sites: `applink_app.AppLinkRuntime.__init__`
  (`applink_app.py:93`, `self.ip = detect_lan_ip()`) and `headless.serve`
  (`headless.py:126`). No override exists anywhere.
- TUI argparse has **only `--smoke`** (`applink_app.py:502`) — no `--port`;
  `ApplinkApp()` takes no ctor args and builds `AppLinkRuntime()` in
  `on_mount` (`applink_app.py:470`), so CLI flags must be threaded
  `main() → ApplinkApp → on_mount → AppLinkRuntime`.
- Headless argparse has `--port/--profile/--no-qr` (`headless.py:189`).
  Both launchers forward `"$@"` (`aitask_applink.sh:33`,
  `aitask_monitor.sh:42` → `applink/headless.py`).
- `server.load_applink_config()` (`server.py:63-84`) is the fault-tolerant
  `tmux.applink.*` pattern to follow (`history_capture_lines`).
- `runtime.ip` has exactly two consumers: `build_uri()` and
  `firewall_doctor.diagnose(port, ip)` — keep `self.ip` = detected LAN
  (firewall needs it) and add separate advertised-endpoint state.
- Firewall doctor: `diagnose(port, lan_ip)` → `FirewallStatus` (always has
  `cidr`); `host_lan_cidr`/`parse_lan_cidr` parse `ip -o -4 addr show`
  (exact-match inet entry, `/24` fallback). IPv4-only.
- Seed config has a commented `applink:` block (`seed/project_config.yaml:382-405`);
  live config has `tmux.applink.history_capture_lines`
  (`aitasks/metadata/project_config.yaml:31-37`). Both surfaces need the new keys.
- `detect_lan_ip()` can return the `"0.0.0.0"` sentinel (offline fallback) —
  never emit that as an `alt` endpoint.

## Wire grammar (documented once in protocol.md §Pairing flow — normative)

```
endpoint := host, port, kind, trust
kind     := lan | mesh | tunnel        (racing preference hint; lan preferred)
trust    := pin | ca                   (pin = QR fp is the trust anchor;
                                        ca = platform CA chain + real hostname
                                        verification, fp not consulted)
```

- Primary endpoint = URL authority (`applink://<host>:<port>/pair`); metadata
  in optional `kind=` / `trust=` params (defaults `lan`/`pin` = today's
  semantics; params omitted when no override → legacy URI **byte-identical**).
- `alt=` = **single** param (never repeated — mobile parser collapses repeated
  keys last-wins), value = URL-encoded comma-separated list of
  `host:port;kind;trust` records (fields `;`-separated, fixed order, all
  mandatory within a record).
- IPv6 hosts bracketed (`[fd7a::1]:8765`) in authority and `alt` records;
  server-side emission always brackets IPv6.
- `fp=` stays mandatory and connection-scoped (anchor for every `trust=pin`
  endpoint; kept even in all-`ca` QRs for identity continuity).
- All params additive — same `applink://` scheme, no `v` bump; old clients
  read only authority + `t`/`fp`/`name` and ignore the rest.

## Steps

### 1. Spec (docs first) — `aidocs/applink/protocol.md`

In §Pairing flow: extend step 3's QR grammar line to
`applink://<host>:<port>/pair?t=…&fp=…[&kind=…][&trust=…][&alt=…][&name=…]`
and add an **"Endpoint & trust model"** subsection (inside §Pairing flow, after
step 3's bullet) carrying the grammar block above verbatim, plus: single-param
`alt` rationale, IPv6 bracketing rule, defaults, advertisement-only semantics
(bind stays `0.0.0.0`; `advertised_port` may differ from serving port),
old-client behavior (primary-endpoint-with-pin; a QR whose *primary* is
`trust=ca` is not backward compatible), and the note that `trust=ca` is inert
client-side until `aitasks_mobile#31_3` lands. This is the one canonical
definition; A3/M2/M3 cross-reference it.

### 2. Config keys — `server.load_applink_config()` + both config surfaces

Extend `load_applink_config` (`server.py:63`) with per-key fault-tolerant
parsing (each invalid key independently falls back; never raises):

- `advertised_host` — raw `str` or `None`. The loader stores it as-is;
  **normalization/validation happens in the resolver** (Step 3) so both the
  config and CLI paths share one normalizer and the loader keeps its
  never-raises contract.
- `advertised_port` — `int` in `[1, 65535]` or `None` (→ serving port).
- `advertised_kind` — one of `lan|mesh|tunnel`; invalid → `None`. Default:
  `mesh` **when an override host is set**, else `lan` (resolver applies this;
  loader returns `None` when absent/invalid so the resolver can tell).
- `advertised_trust` — `pin|ca`; invalid/absent → `pin`.

Returned dict grows these four keys. Update both config surfaces with
commented examples incl. accepted host forms and the CLI-group precedence
rule (Step 4): `seed/project_config.yaml` (extend the `applink:` block at
~line 382) and live `aitasks/metadata/project_config.yaml` (comment under
`tmux.applink`).

### 2b. Host normalization — `pairing.py` (pure, shared by CLI + config)

Users will paste endpoint strings from cloudflared/ngrok/Tailscale docs
(`https://foo.trycloudflare.com`, `foo.example.com:443/`, URLs with paths).
Raw pass-through would emit a malformed/double-ported QR. Add:

`normalize_advertised_host(value: str) -> tuple[str, int | None]`
— returns `(host, embedded_port)` or raises `ValueError` with a
human-readable reason. Rules:
- Strip a leading `scheme://` (any scheme), any `/path`, query, fragment,
  and trailing slashes.
- Accept: bare hostname/FQDN, IPv4 literal, bracketed IPv6 (`[fd7a::1]`),
  bare IPv6 literal (multiple `:` and parses via `ipaddress` → treat whole
  value as the host), each optionally with `:port`.
- `embedded_port` extracted from `host:port` / `[v6]:port`; validated
  `[1, 65535]`.
- Reject (raise): empty result, whitespace inside host, invalid port,
  a userinfo `@` part, anything that still contains `/` after stripping.

Failure handling differs by source (fail-visible, never a malformed QR):
- **CLI**: wrap as the argparse `type=` for `--advertise-host` → invalid
  input exits with argparse's clean error before any side effect.
- **Config**: resolver catches `ValueError`, **ignores the override**
  (falls back to LAN-only legacy emission — a valid, scannable QR) and
  returns a warning string that both call sites must surface: headless
  prints `[applink] invalid tmux.applink.advertised_host (<reason>) — QR
  advertises the LAN address` after the pairing block; the TUI shows the
  same text in the pairing screen advisory. Rationale: a hard exit on a
  config typo would brick an unattended headless box; a visible warning +
  safe LAN fallback keeps the server usable.

### 3. Endpoint resolver + URI emission — `pairing.py` (pure, unit-testable)

- `format_endpoint_host(host)` — bracket when `":" in host` and not already
  bracketed (IPv6); pass-through otherwise.
- `Endpoint` (NamedTuple: `host, port, kind, trust`).
- `resolve_advertised_endpoints(*, cli_host, cli_port, cli_kind, cli_trust,
  config, serving_port, detected_ip)
  -> tuple[Endpoint, list[Endpoint], str | None]` (primary, alts, warning):
  - **Group-level precedence (no cross-source field mixing):** if **any**
    `--advertise-*` CLI flag was given, the CLI group defines the entire
    override and all `advertised_*` config keys are **ignored**; otherwise
    the config group applies. This prevents a one-shot CLI host silently
    inheriting a stale configured `advertised_kind`/`trust`/`port`. Within
    the winning group, unset fields get built-in defaults:
    `port` = explicit port field > port embedded in the host string >
    serving port; `kind` = explicit > `mesh`; `trust` = explicit > `pin`.
  - No override host in the winning group → primary =
    `Endpoint(detected_ip, serving_port, "lan", "pin")`, alts `[]`
    (legacy emission — no `kind`/`trust`/`alt` params). (CLI kind/trust/port
    flags without `--advertise-host` are a usage error — argparse-reject.)
  - Override → host normalized via `normalize_advertised_host` (CLI path is
    pre-validated by argparse; config path falls back + warns per Step 2b);
    primary = `Endpoint(host, resolved_port, resolved_kind, resolved_trust)`;
    alts = `[Endpoint(detected_ip, serving_port, "lan", "pin")]` unless
    `detected_ip == "0.0.0.0"` or equals the override host.
- Extend `build_pairing_uri(…, kind=None, trust=None, alt=None)` —
  backward-compatible defaults (omitted params → today's byte-identical
  output). Param order: `t`, `fp`, `kind`, `trust`, `alt`, `name`. `alt` value
  = `quote(",".join(f"{format_endpoint_host(h)}:{p};{k};{t}"), safe='')`.
  Authority host also goes through `format_endpoint_host`.

### 4. Thread into both emission call sites + CLI flags

Four flags on both argparsers: `--advertise-host`
(type=`normalize_advertised_host` wrapper), `--advertise-port` (int),
`--advertise-kind` (choices `lan|mesh|tunnel`), `--advertise-trust` (choices
`pin|ca`). `--advertise-kind` is added beyond the task AC's three-flag list to
close the stale-config-coupling gap (group precedence, Step 3) — **update the
task body's CLI bullet** to the four-flag list + group-precedence wording
(explicit AC amendment, committed via `./ait git`).

- **`applink_app.py`:** `ApplinkApp.__init__(advertise_host=None,
  advertise_port=None, advertise_kind=None, advertise_trust=None)` stores
  them; `on_mount` passes to `AppLinkRuntime(…)`. Runtime `__init__` keeps
  `self.ip = detect_lan_ip()` (firewall consumer) and computes
  `self.primary, self.alts, self.advertise_warning` via the resolver (config
  via `load_applink_config(paths.project_root())`); `build_uri()` emits
  primary + alts; PairingScreen advisory surfaces `advertise_warning`.
  `main()` threads args (`--smoke` path unchanged — no I/O added to
  construction).
- **`headless.py`:** same four flags on `_parse_args`; `serve(…)` grows the
  four kwargs; keep `lan_ip = detect_lan_ip()` for the firewall step, resolve
  endpoints once (print the resolver warning line if any), `_emit()` uses
  them (SIGHUP reprint keeps the resolved endpoints; only the token changes).

### 5. Firewall doctor override awareness — `firewall_doctor.py`

- Pure core: `classify_override(advertised_host, lan_cidr, ip_addr_output)
  -> tuple[str, str | None]` returning `("covered", None)` (IPv4 literal
  inside `lan_cidr`), `("local_iface", <cidr>)` (IPv4 literal exactly matching
  another local `inet` entry — mesh case, e.g. `tailscale0` →
  `100.64.0.0/10`), or `("external", None)` (FQDN, IPv6, or non-local IP —
  tunnel case). **No DNS resolution by design** (doctor stays deterministic /
  offline-safe): a mesh DNS name (e.g. Tailscale MagicDNS) classifies
  `external` — the external note therefore includes the hint "if this is a
  mesh hostname, set the numeric mesh IP as advertised host to get
  interface-scoped firewall guidance". Documented in the config comments and
  pinned by a test.
- `diagnose(port, lan_ip, advertised_host=None)`: when an override is present
  and not covered — `local_iface`: append `build_open_commands(backend, port,
  <mesh-cidr>)` to `commands` (and `display`) and set a new
  `FirewallStatus.override_note` ("advertised host <h> is on <cidr> —
  commands above include it"); `external`: set `override_note` ("advertised
  endpoint <h> is not covered by these LAN-scoped rules (external/tunnel
  endpoint)" + the mesh-DNS hint when the host is not an IP literal). Never
  silently print LAN-only guidance for a tunnel endpoint.
- **Surface the note on EVERY firewall command/help surface** (the note rides
  on `FirewallStatus`, so each renderer appends it uniformly):
  1. `render_firewall_block` (headless detected-backend block,
     `headless.py:145`);
  2. the headless no-backend generic fallback print (`headless.py:147-155`);
  3. `generic_help(port, cidr, override_note=None)` (called by both the
     headless fallback path and the TUI modal);
  4. `FirewallFixModal` (`applink_app.py:187-223`) — `_command_text()`
     appends the note, and the `fw_sub` "LAN-scoped" label gains the warning
     when `override_note` is set (the `f`-key path must never show LAN-only
     remediation without it);
  5. the PairingScreen `#firewall_advisory` line (`_refresh_advisory`,
     `applink_app.py:316`).
  Pass `advertised_host` through both `diagnose` call sites
  (`headless.py:140`, `applink_app.py:484`).

### 6. Tests

- **New `tests/test_applink_advertise.sh`** (pattern:
  `test_applink_pairing.sh` — python_resolve heredoc, `check()` asserts):
  - `normalize_advertised_host`: bare host; `host:port`; `https://h`,
    `wss://h:443/`, `h/path`, trailing slash → stripped; bracketed +
    bare IPv6; embedded-port extraction; rejects (empty, bad port, `@`,
    residual `/`, whitespace) each with `ValueError`.
  - Config parsing: all four keys; fault tolerance per key (bad kind/trust/
    port/type → that key's default, others unaffected; missing file → defaults).
  - Resolver: group precedence — any CLI flag present → config group fully
    ignored (incl. the stale-`advertised_kind` case: CLI host + config
    `kind: tunnel` → resolved kind `mesh`); config-only group; within-group
    port chain (explicit > embedded > serving); invalid config host →
    LAN fallback + warning string (and warning is `None` on the happy path);
    CLI kind/trust/port without host → rejected.
  - Emission: no-override URI **byte-identical** to legacy (regression for old
    clients); override → authority = override host:port + `kind=mesh&trust=pin`
    defaults; explicit `trust=ca`; `alt` exact-string grammar incl.
    URL-encoding of `;`/`,`; IPv6 bracketing in authority and in `alt`
    records; `detected_ip == "0.0.0.0"` → no `alt`.
  - Real entry points: `headless._parse_args` and `applink_app._parse_args`
    accept the four flags and reject an invalid `--advertise-host` with an
    argparse error (namespace assertions; applink_app import guarded by the
    textual dependency-skip used in `test_applink_smoke.sh`).
- **Extend `tests/test_applink_firewall.sh`:** `classify_override` on canned
  `ip -o -4 addr show` text (covered / tailscale-owned → CIDR / FQDN →
  external **with the mesh-DNS hint pinned** / IPv6 → external);
  `override_note` rendering on every surface: `render_firewall_block`,
  `generic_help(…, override_note=…)`, and `FirewallFixModal._command_text` +
  `fw_sub` composition (textual-guarded); `diagnose` passthrough with
  `advertised_host=None` unchanged (negative control — note absent, commands
  identical).
- Existing applink tests must stay green (`test_applink_pairing.sh` asserts
  the legacy base URI exactly — the byte-identical guarantee).

## Working-tree caution

The working tree has unrelated uncommitted edits from a concurrent session
(`.aitask-scripts/applink/pusher.py`, monitor files, tests). Stage **only**
this task's files explicitly at commit time; verify `git diff --cached`
before committing.

## Verification

- `bash tests/test_applink_advertise.sh`, `bash tests/test_applink_firewall.sh`,
  `bash tests/test_applink_pairing.sh`, `bash tests/test_applink_headless.sh`,
  `bash tests/test_applink_smoke.sh` all pass.
- Manual (offer as Step-8c manual-verification follow-up): set
  `advertised_host` to a Tailscale IP, scan QR, confirm pairing works over the
  mesh with the unchanged pin.

## Step 9 (Post-Implementation)

Standard cleanup/merge/archival per task-workflow Step 9 (fast profile —
current branch, no worktree/merge).

## Risk

### Code-health risk: low
- Threading new ctor params through `ApplinkApp`/`AppLinkRuntime` touches TUI
  startup incl. the no-I/O `--smoke` contract · severity: low · → mitigation:
  emission additions are pure/param-gated; no-override path byte-identical +
  regression-tested; `--smoke` unchanged (resolver runs in `on_mount`, not
  construction).

### Goal-achievement risk: medium
- Cross-repo wire contract: `kind`/`trust`/`alt` grammar is consumed by a
  not-yet-written mobile parser (M2/M3); a divergence surfaces late in the
  other repo · severity: medium · → mitigation: grammar documented once in
  protocol.md §Pairing (canonical), emission covered by exact-string unit
  tests pinned to that grammar; mobile children xdep on this task.
- Mesh end-to-end proof needs a live Tailscale device (cannot be automated
  here) · severity: low · → mitigation: offered as a standalone
  manual-verification follow-up at Step 8c.

### Planned mitigations
None — both risks are covered in-plan (canonical spec + exact-grammar tests;
Step-8c manual-verification offer); no separate before/after mitigation tasks
proposed.
