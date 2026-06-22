---
Task: t1043_applink_launch_firewall_doctor.md
Base branch: main
plan_verified: []
---

# t1043 — AppLink launch-time firewall doctor

## Context

During live mobile pairing, the phone could not connect: the AppLink server
bound `0.0.0.0:8765` correctly, but the host's `ufw` firewall silently dropped
inbound TCP on that port (ICMP passed, TCP SYN timed out). The mobile app
surfaced only a generic "NETWORK, try again", and the user had to hand-craft
`sudo ufw allow from <lan>/24 to any port 8765 proto tcp`. This task adds a
launch-time **firewall doctor** so the user never crafts firewall rules by hand:
detect an active host firewall, surface a clear advisory, and offer to open the
bound port with a single LAN-scoped, consent-gated privileged command.

### Decided design pivot (updates the task's "Chosen approach" step 1)

The task's step 1 ("probe reachability via a self-connect to `<lan-ip>:<port>`
from the host") **cannot detect a real firewall drop** and would ship a no-op
doctor: on Linux a connection from the host to *its own* LAN IP is routed
through the loopback device (`lo`), which ufw/iptables/nftables accept
unconditionally via the standard `-i lo -j ACCEPT` before-rule. So the
self-connect succeeds even when the firewall blocks external inbound — i.e. it
reports "reachable ✓" in exactly the scenario this task exists to catch.

**Confirmed with the user → replace the self-connect probe with active-backend
detection + a conditional advisory.** The doctor never claims the port is
"blocked" (no false positives); it only says *"a firewall is active — if your
phone can't connect, here's the one-keypress fix."* The definitive port check +
LAN-scoped allow happens only on explicit consent. The task's acceptance
criteria will be updated to record this (the "probe must not produce false
positives" AC is satisfied; the "self-connect probe" mechanism is dropped).

**Fix scope (confirmed with user):** auto-run the allow for **ufw** and
**firewalld** (both natively idempotent), show-command-only for raw
**nftables/iptables** (no clean idempotent one-liner). A **"show me the command,
I'll run it myself"** option is offered for **every** backend.

## Approach

A new pure, Textual-free module `firewall_doctor.py` holds all detection /
command-synthesis logic (unit-testable, mirroring how `pairing.py` is a pure
helper consumed by the TUI). The TUI (`applink_app.py`) and the headless runner
(`headless.py`) each wire it in at launch — advisory + `f`-key consent flow in
the TUI, advisory + exact command printed to stdout in headless.

## New file: `.aitask-scripts/applink/firewall_doctor.py`

Pure module, stdlib only (no Textual/segno), so its unit test needs no
dependency-skip guard (same constraint as `pairing.py`). All subprocess calls
are isolated in thin wrappers; the parse/synthesis functions take their input as
arguments so tests inject fixtures.

Public surface:

- `detect_backend(probe=_default_probe) -> str | None` — returns `"ufw"`,
  `"firewalld"`, `"nftables"`, or `None`, in that priority order. Detection is
  **unprivileged, timeout-bound, and failure-silent**: `systemctl is-active
  <svc>` for `ufw`/`firewalld`/`nftables` (read-only, no root), each call with a
  short subprocess timeout (~1.5s) and swallowing `FileNotFoundError` /
  `TimeoutExpired` / `OSError` (so non-systemd hosts, containers, WSL, slow DBus
  → `None`, never a hang or crash). `probe(name)` is an injectable callable
  returning the `is-active` string so the test can drive every branch (including
  the missing-`systemctl` and timeout paths) without touching the host. Returns
  `None` when no service-managed firewall is cheaply detectable.

  **This drives only the auto-advisory** — its scope is honestly limited to
  managed/active backends we can detect without root. Backend-agnostic coverage
  is NOT carried by detection alone: the `f` key (TUI) and a headless hint always
  expose the **generic show-command help** below, which is the always-reachable
  UI route to the nft/iptables/ufw/firewalld fallback even when `detect_backend`
  returns `None` (bare iptables, Docker-managed rules, iptables-nft, nft rules
  without `nftables.service`, etc.).

- `parse_lan_cidr(ip_addr_output: str, lan_ip: str) -> str` — pure. Given the
  output of `ip -o -4 addr show`, find the entry whose address equals `lan_ip`
  and return its real `<network>/<prefix>` (e.g. `192.168.1.0/24`). Falls back
  to a `/24` derived by zeroing the last octet when not found / `ip`
  unavailable. `host_lan_cidr(lan_ip)` is the thin wrapper that runs `ip` and
  calls this.

- `build_open_commands(backend, port, cidr, proto="tcp") -> list[list[str]]` —
  pure. The privileged argv(s):
  - `ufw`: `[["ufw","allow","from",cidr,"to","any","port",str(port),"proto",proto]]`
  - `firewalld`: `[["firewall-cmd","--permanent",
    f"--add-rich-rule=rule family=ipv4 source address={cidr} port port={port} protocol={proto} accept"],
    ["firewall-cmd","--reload"]]`
  - `nftables`: `[["nft","add","rule","inet","filter","input","ip","saddr",cidr,"tcp","dport",str(port),"accept"]]` (show-only)
  - `iptables`: `[["iptables","-I","INPUT","-p",proto,"-s",cidr,"--dport",str(port),"-j","ACCEPT"]]` (show-only)

- `auto_fixable(backend) -> bool` — `True` for `ufw`/`firewalld`, `False`
  otherwise (drives whether the consent modal offers "Open it for me").

- `privilege_wrapper() -> list[str] | None` — `["pkexec"]` if `shutil.which
  ("pkexec")` else `None`. We deliberately prefer pkexec (its own polkit dialog,
  doesn't fight Textual's hold on the terminal) and do **not** shell out to
  interactive `sudo` from inside the TUI.

- `display_command(commands) -> str` — human-runnable, `sudo`-prefixed,
  **shell-safe** rendering. Each argv is rendered with `shlex.join()` (NOT a
  naive space-join) so multi-word argv elements stay valid when copy-pasted —
  critically the firewalld rich rule, whose `--add-rich-rule=rule family=ipv4 …
  accept` is a **single argv element containing spaces**. Multiple commands
  (firewalld add + reload) are joined with ` && `. Example outputs:
  `sudo ufw allow from 192.168.1.0/24 to any port 8765 proto tcp` and
  `sudo firewall-cmd --permanent '--add-rich-rule=rule family=ipv4 source address=192.168.1.0/24 port port=8765 protocol=tcp accept' && sudo firewall-cmd --reload`.

- `generic_help(port, cidr) -> str` — pure; the backend-agnostic fallback shown
  when nothing was detected. Lists the `display_command` for each of
  ufw/firewalld/nft/iptables (all `shlex`-safe), prefaced by a cautious line so
  the user can apply whichever matches their host.

- `diagnose(port, lan_ip) -> FirewallStatus` — orchestrator (runs subprocesses).
  **Always returns a `FirewallStatus`, never `None`** (concern A: the generic
  fallback needs the CIDR even when nothing is detected). The dataclass:
  `{backend: str|None, cidr: str, port: int, auto_fixable: bool, commands:
  list[list[str]], display: str|None}`, with a `detected` property =
  `backend is not None`. `cidr` is **always** populated via `host_lan_cidr
  (lan_ip)` regardless of detection, so both the advisory and the generic-help
  modal/hint always have the real LAN-scoped CIDR. When `detect_backend` returns
  `None`: `backend=None`, `auto_fixable=False`, `commands=[]`, `display=None`,
  but `cidr`/`port` set. **Must only be called off the construct/`--smoke` path**
  (it spawns `systemctl`/`ip`); invoked via `asyncio.to_thread(...)` from both
  call sites so its blocking subprocesses never stall the event loop.

- `interpret_result(backend, returncode, output) -> tuple[bool, str]` — pure.
  Backend-aware success classification so a **no-op re-run reports success, not
  failure**: ufw "Skipping adding existing rule" and firewalld
  "Warning: ALREADY_ENABLED" (and non-zero-but-benign variants) map to
  `(True, "already open")`. Unit-tested with captured "already exists/enabled"
  fixtures for ufw and firewalld.

- `run_open(status) -> tuple[bool, str]` — takes the **`FirewallStatus`** (not a
  bare command list) so it carries `status.backend` for classification (concern
  B). Wraps each of `status.commands` with `privilege_wrapper()`, runs them
  capturing combined output, and returns `interpret_result(status.backend, rc,
  output)`. Thin; real execution is not unit-tested (needs privilege) — synthesis
  + `interpret_result` classification are; live execution is the
  manual-verification follow-up.

- `render_firewall_block(status) -> str` — pure; the stdout advisory block for
  headless (advisory line + the `display_command`).

## TUI wiring: `.aitask-scripts/applink/applink_app.py`

- `AppLinkRuntime`: add `self.firewall = None`. Populate it in the mount worker,
  **not** the constructor, to preserve the `--smoke` no-I/O contract. In
  `ApplinkApp._start_server`, after `server.start()` returns and only when
  `server.error is None`, set `self.runtime.firewall = await asyncio.to_thread(
  firewall_doctor.diagnose, self.runtime.port, self.runtime.ip)` (off-thread so
  the blocking `systemctl`/`ip` calls never stall the loop) and nudge the screen
  to refresh its advisory. `runtime.firewall` is a `FirewallStatus` carrying the
  real `cidr` whether or not a backend was detected — so the modal never lacks a
  CIDR source (concern A). It stays `None` only in the brief window before the
  worker completes (and on the `--smoke` path).

- `PairingScreen`:
  - Add a muted `Static("", id="firewall_advisory")` below `#pairing_hint`.
    Show the advisory only when `runtime.firewall` exists **and**
    `runtime.firewall.detected` (i.e. `backend is not None`):
    `⚠ Firewall (<backend>) active — if your phone can't connect, press 'f' to
    open port <port> for <cidr>.` When undetected, show a quieter one-liner
    ("Press 'f' for firewall help if your phone can't connect.") rather than a
    false "reachable" claim. Refreshed via the existing `_on_server_change`
    nudge / a short `set_interval`.
  - Add `Binding("f", "fix_firewall", "Firewall help")` — **always active and
    always meaningful** (resolves the "f is confusing with no advisory"
    concern). It opens `FirewallFixModal` in one of two modes:
  - `action_fix_firewall` always pushes `FirewallFixModal(runtime.firewall)`
    (the single `FirewallStatus` carries `backend`, `cidr`, `port`, `commands`,
    `display` — concern A: no separate `cidr` argument needed). The modal
    branches on `status.detected`; it never dead-ends with a falsely reassuring
    "should be reachable" message. (If the worker hasn't populated
    `runtime.firewall` yet, `action_fix_firewall` notifies "still checking…".)

- New `FirewallFixModal(ModalScreen)` in `applink_app.py` (following
  `lib/stale_entry_modal.py` / `lib/agent_model_picker.py`):
  - **Detected mode** (`status` not None) — shows backend/port/`cidr` and offers:
    - "Open it for me" (only when `status.auto_fixable` **and**
      `privilege_wrapper()` is not None) → run `firewall_doctor.run_open(status)`
      via a thread worker (`@work(thread=True)` / `run_worker(..., thread=True)`)
      so pkexec's polkit dialog runs without blocking the event loop; on return
      `self.notify` the `(ok, detail)` message (a no-op re-run shows "already
      open"), and on failure fall back to showing the command.
    - "Show me the command" (always) → display `status.display` in a selectable
      `Static` to copy/run manually.
    - "Cancel".
    - When `auto_fixable` is False (nft/iptables) or pkexec is missing, only
      "Show me the command" + "Cancel" are offered.
  - **Generic mode** (`not status.detected`) — no managed firewall was
    auto-detected. Shows a cautious header ("No managed firewall auto-detected.
    If the phone still can't connect, open port <status.port> for <status.cidr>
    on your firewall:") and the `firewall_doctor.generic_help(status.port,
    status.cidr)` block (all four backends' `shlex`-safe commands) in a
    selectable `Static`, plus "Cancel". This is the always-reachable UI route to
    the backend-agnostic fallback — and `status.cidr` is always real (concern A).

## Headless wiring: `.aitask-scripts/applink/headless.py`

- After `server.start()` succeeds (before/after `_emit()`), call
  `status = await asyncio.to_thread(firewall_doctor.diagnose, port, ip)`
  (off-thread, timeout-bound, failure-silent — so a non-systemd / slow box never
  delays or breaks startup). If `status.detected`, print
  `render_firewall_block(status)` (advisory + exact `sudo` command). **If not
  detected,** print a single concise hint line (`status.cidr` + the ufw example,
  noting "see other backends if not ufw") so the backend-agnostic fallback also
  has a headless route — not the full multi-backend block, to keep an unwatched
  box quiet. No keypress affordance (no TTY) — informational only, consistent
  with "privilege escalation only on explicit consent": the user runs the printed
  command.
- Keep the no-Textual contract — `firewall_doctor` is stdlib-only, safe to
  import here (asserted by `tests/test_applink_headless.sh`).

## Tests: new `tests/test_applink_firewall.sh`

Mirror `tests/test_applink_pairing.sh` (uses `lib/python_resolve.sh` +
`require_ait_python`, no dep-skip guard since the module is stdlib-only). Cover:

- `detect_backend` priority + `None`, driven by an injected `probe` returning
  fake `is-active` results for each branch — **including** the missing-`systemctl`
  (`FileNotFoundError`) and timeout (`TimeoutExpired`) paths → `None` (concern 4).
- `parse_lan_cidr`: exact match against a sample `ip -o -4 addr show` block
  (real prefix), and the `/24` fallback when the IP is absent.
- `build_open_commands`: exact argv for all four backends.
- `auto_fixable`: ufw/firewalld True, nft/iptables False.
- `privilege_wrapper`: pkexec-present vs absent (inject a fake `which`).
- `display_command`: **shell-safe** — assert the firewalld rendering quotes the
  rich-rule argv element (e.g. contains `'--add-rich-rule=...accept'` as a single
  shell token, round-trippable via `shlex.split`), and that ufw renders without
  spurious quoting (concern 2).
- `interpret_result`: ufw "Skipping adding existing rule" and firewalld
  "ALREADY_ENABLED" fixtures → `(True, "already open")`; a genuine error string →
  `(False, …)` (concern 3).
- `generic_help`: contains all four backends' commands + the cautious header
  (concern 1 fallback route).
- `render_firewall_block`: contains the advisory and the `sudo`-prefixed command.

Also extend `tests/test_applink_smoke.sh` with a **construction spy** asserting
`--smoke` never calls `firewall_doctor.diagnose` (proves the no-I/O-before-event
-loop contract — diagnose runs only in the mount worker).

## AC update (no silent deviation)

Update `aitasks/t1043_applink_launch_firewall_doctor.md` before implementing:
replace the "self-connect probe" wording in the "Chosen approach" step 1 and the
matching acceptance bullet with the active-backend-detection design, and record
that nft/iptables are show-command-only with a "show command for any backend"
option. **Preserve the reasoning, not just the new wording (concern 6):** add a
short `## Why not a self-connect probe` rationale block to the task explaining
the loopback-bypass (host→own-LAN-IP routes via `lo`, accepted by the firewall's
`-i lo` before-rule, so a self-connect can't observe an external INPUT drop) — so
a future reviewer does not reintroduce it. Also state honestly that the
**auto-advisory** covers cheaply-detectable managed backends, while
**backend-agnostic coverage** is delivered by the always-reachable `f`/headless
show-command help. (Done as part of Step 7 implementation; flagged here per the
no-silent-AC-deviation rule.)

## Risk

### Code-health risk: medium
- `diagnose()` spawns subprocesses (`systemctl`/`ip`); if wired into the
  constructor instead of the mount worker it would break the `--smoke` no-I/O
  CI contract · severity: medium · → mitigation: covered by the smoke
  construction-spy test (TBD)
- New `pkexec` invocation from inside a Textual app (worker/thread + polkit
  dialog interaction) is net-new in this repo and must not block the event loop
  · severity: medium · → mitigation: live manual verification (TBD)

### Goal-achievement risk: medium
- The doctor's real-world usefulness (advisory fires on the actual box; pkexec's
  polkit dialog works under Hyprland/Wayland; the LAN-scoped rule actually lets
  the phone through) can only be confirmed by **live** testing — unit tests
  cover synthesis only · severity: medium · → mitigation: manual-verification
  follow-up (TBD)
- Auto-detection scope is honestly limited (managed/active backends only); raw
  iptables/Docker/iptables-nft setups won't auto-advise · severity: low ·
  mitigated by the always-reachable `f`/headless generic show-command help, so
  the backend-agnostic fallback always has a UI route · → mitigation: none needed
- pkexec / polkit agent may be absent on some hosts · severity: low · clean
  fallback already designed (show-command path) · → mitigation: none needed

The live-behavior risk is the standard target of the **Step 8c
manual-verification follow-up** offered after commit (live ufw + phone pairing +
pkexec dialog). Recommend handling it there rather than as a separate before/after
risk-mitigation task to avoid duplication.

## Verification

- `bash tests/test_applink_firewall.sh` — all pure-function assertions pass.
- `bash tests/test_applink_smoke.sh` — smoke still green; spy confirms no
  firewall I/O on `--smoke`.
- `bash tests/test_applink_headless.sh` — no-Textual contract intact.
- `shellcheck tests/test_applink_firewall.sh`.
- **Live (manual-verification follow-up):** with `ufw` active and the port
  closed, launch `ait applink`, confirm the advisory appears, press `f`, confirm
  the polkit dialog opens, approve, and confirm the phone then pairs; re-press
  `f` to confirm idempotency ("already allowed" no-op). Repeat the headless path
  via `ait monitor --headless-for-applink` (advisory + command printed).

## Post-implementation

Follow shared workflow Step 8 (review) → Step 8c (offer the live
manual-verification follow-up) → Step 9 (no separate branch on `fast`; archive).
