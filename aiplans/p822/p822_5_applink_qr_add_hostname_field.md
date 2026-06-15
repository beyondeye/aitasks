---
Task: t822_5_applink_qr_add_hostname_field.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_10_applink_append_fastpath.md, aitasks/t822/t822_11_applink_modal_handshakes.md, aitasks/t822/t822_12_applink_permissions_doc_sync.md, aitasks/t822/t822_13_applink_headless_monitor_flag.md, aitasks/t822/t822_8_applink_snapshot_push_loop.md, aitasks/t822/t822_9_applink_delta_engine.md
Archived Sibling Plans: aiplans/archived/p822/p822_1_applink_protocol_design.md, aiplans/archived/p822/p822_2_applink_tui_qr.md, aiplans/archived/p822/p822_3_monitor_port_design.md, aiplans/archived/p822/p822_4_manual_verification_auto.md, aiplans/archived/p822/p822_6_extract_monitor_core.md, aiplans/archived/p822/p822_7_applink_websocket_listener.md
Base branch: main
plan_verified: []
---

# Plan: t822_5 — unit test for the `name=` hostname field in the QR pairing URI

## Context

Task t822_5 asked to (a) append `&name=<urlencoded(socket.gethostname())>` to the
`applink://` QR pairing URI, and (b) add a unit test confirming `name=` is present
and matches `urlencoded(socket.gethostname())`.

**Scope finding (explicit AC deviation — surfaced, not silently dropped):** during
exploration the *production half is already implemented*, landed by earlier siblings:

- `.aitask-scripts/applink/pairing.py:60-79` — `build_pairing_uri(token, ip, port,
  fingerprint, hostname=None)` already emits `&name={quote(hostname, safe='')}` when
  `hostname` is truthy (optional/additive, exactly per spec
  `aidocs/applink/protocol.md` §Pairing flow).
- `.aitask-scripts/applink/applink_app.py:90,99-106` — `AppLinkRuntime.host =
  _hostname()` (which returns `socket.gethostname()`, line 52-56) and
  `build_uri()` passes `hostname=self.host or None`.

So the QR-builder change requires **no further code**. The only undelivered AC item
is the **unit test**. This task therefore reduces to adding that test. (Confirmed:
no existing test references `build_pairing_uri` — `tests/` has only
`test_applink_{smoke,devices,router}.sh`, none covering the URI builder.)

## Approach

Add one new test file, `tests/test_applink_pairing.sh`, mirroring the existing
applink test scaffold (`tests/test_applink_devices.sh`): a bash wrapper that resolves
the ait Python via `lib/python_resolve.sh` and runs an embedded Python block.

`pairing.py` imports only stdlib (`secrets`, `socket`, `urllib.parse`) — **no textual
/ segno**, so the test needs **no dependency-skip guard** (unlike the smoke/devices
tests). It imports `pairing` directly from `.aitask-scripts/applink/`.

### File to create: `tests/test_applink_pairing.sh`

Embedded-Python assertions against `pairing.build_pairing_uri`:

1. **`name=` matches `urlencoded(socket.gethostname())`** (the literal AC): call
   `build_pairing_uri(token="tok", ip="192.168.1.5", port=8765, fingerprint="fp",
   hostname=socket.gethostname())` and assert the URI contains
   `f"name={quote(socket.gethostname(), safe='')}"`.
2. **Encoding of unsafe chars:** `hostname="my host.örg"` →
   URI contains `name=my%20host.%C3%B6rg` (asserts `quote(..., safe='')` semantics:
   space and non-ASCII percent-encoded). Compare against `quote("my host.örg", safe='')`.
3. **Optional / additive:** `hostname=None` (and `hostname=""`) → URI contains **no**
   `name=` parameter; the rest of the URI
   (`applink://.../pair?t=...&fp=...`) is unchanged. This guards the
   "older clients unaffected" requirement in the task body.

Use the same `check(label, cond)` assert-and-print helper and final `ALL PASSED`
line as `test_applink_devices.sh`, with `set -e` so any failed assertion fails the
script.

## Out of scope

- No change to `pairing.py` / `applink_app.py` — already correct.
- Textual UI / runtime construction — covered by `test_applink_smoke.sh`.

## Verification

1. `bash tests/test_applink_pairing.sh` → all checks `ok`, prints `ALL PASSED`,
   exit 0.
2. `shellcheck tests/test_applink_pairing.sh` → no warnings.
3. Sanity: temporarily breaking the assertion (or the builder) makes the test fail —
   confirms it actually exercises the field.

## Risk

### Code-health risk: low
- Test-only change; adds one new, isolated `tests/` file with zero production-code
  impact and no shared-helper edits. · severity: low · → mitigation: none needed.

### Goal-achievement risk: low
- The AC's production half is already implemented and the remaining deliverable is
  precisely this unit test; the test directly asserts the specified behavior
  (`name=` present + `urlencoded(gethostname())`). · severity: low · → mitigation:
  none needed.

## Step 9 (Post-Implementation)

Standard cleanup per task-workflow Step 9 (profile `fast`, current branch, no
worktree): commit the new test, write Final Implementation Notes into the plan
(documenting that the production change pre-landed in t822_2/t822_7 and this task
delivered only the test), archive via `./.aitask-scripts/aitask_archive.sh 822_5`,
push via `./ait git push`. Parent t822 keeps its other pending children.
