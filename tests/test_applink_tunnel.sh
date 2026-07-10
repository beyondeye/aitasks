#!/usr/bin/env bash
# test_applink_tunnel.sh — unit tests for the auto-spawned Cloudflare Quick
# Tunnel (t1061_3): strict URL parsing, QuickTunnel supervision against a fake
# cloudflared binary, merge_tunnel_endpoint emission (incl. the byte-identical
# legacy negative control), the auto_tunnel config key, and the --auto-tunnel
# flag on both real entry points.
# Run: bash tests/test_applink_tunnel.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

# ---- Group A: parse_tunnel_url (pure — stdlib only) --------------------------
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

from tunnel import parse_tunnel_url


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


# Fixtures modeled on REAL cloudflared 2026.7.1 log output (captured during
# the t1061_3 origin-TLS verification): unrelated URLs appear BEFORE the
# tunnel banner, so the parser must be strict, not "first https URL wins".
TERMS_LINE = (
    "2026-07-10T07:34:37Z INF Thank you for trying Cloudflare Tunnel. "
    "... subject to the Cloudflare Online Services Terms of Use "
    "(https://www.cloudflare.com/website-terms/), and Cloudflare reserves "
    "... you should use a pre-created named tunnel by following: "
    "https://developers.cloudflare.com/cloudflare-one/connections/connect-apps"
)
BANNER_LINE = (
    "2026-07-10T07:34:42Z INF |  "
    "https://lexmark-museums-investigations-solve.trycloudflare.com"
    "                            |"
)
METRICS_LINE = (
    "2026-07-10T07:34:42Z INF Starting metrics server on 127.0.0.1:20241/metrics"
)

check("terms-of-use line (cloudflare.com URLs) does not match",
      parse_tunnel_url(TERMS_LINE) is None)
check("metrics address does not match", parse_tunnel_url(METRICS_LINE) is None)
check("banner line matches the tunnel URL",
      parse_tunnel_url(BANNER_LINE)
      == "https://lexmark-museums-investigations-solve.trycloudflare.com")
check("plain URL line matches",
      parse_tunnel_url("https://foo-bar.trycloudflare.com")
      == "https://foo-bar.trycloudflare.com")
check("no-URL line", parse_tunnel_url("2026-07-10 INF Registered tunnel connection") is None)
check("empty line", parse_tunnel_url("") is None)

# Lookalike rejects: only https://<sub>.trycloudflare.com is acceptable.
check("evil-trycloudflare.com rejected (no dot before suffix)",
      parse_tunnel_url("https://evil-trycloudflare.com") is None)
check("trycloudflare.com.evil.net rejected (suffix continues)",
      parse_tunnel_url("https://sub.trycloudflare.com.evil.net") is None)
check("http (non-TLS) scheme rejected",
      parse_tunnel_url("http://sub.trycloudflare.com") is None)
check("bare apex without subdomain rejected",
      parse_tunnel_url("https://.trycloudflare.com") is None)
check("URL followed by path still matches host",
      parse_tunnel_url("visit https://a-b.trycloudflare.com/metrics now")
      == "https://a-b.trycloudflare.com")

# First trycloudflare match wins within a line.
two = ("https://first-one.trycloudflare.com and "
       "https://second-one.trycloudflare.com")
check("first trycloudflare match wins", parse_tunnel_url(two)
      == "https://first-one.trycloudflare.com")

print("Group A: all assertions passed")
PYEOF

# ---- Group B: QuickTunnel supervision against a fake cloudflared ------------
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import os
import stat
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

from tunnel import (
    QuickTunnel, find_cloudflared, parse_tunnel_url,
    STATE_FAILED, STATE_STARTING, STATE_STOPPED, STATE_UP,
)


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


def fake_binary(tmp: Path, name: str, script: str) -> str:
    p = tmp / name
    p.write_text("#!/usr/bin/env bash\n" + script)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


async def main():
    tmp = Path(tempfile.mkdtemp(prefix="tunnel-test-"))
    changes = []

    # -- happy path: URL printed (to stderr, like real cloudflared), then idle
    happy = fake_binary(tmp, "cf_happy", """
echo "INF Thank you ... https://developers.cloudflare.com/x" >&2
echo "INF |  https://abc-def.trycloudflare.com  |" >&2
sleep 60
""")
    t = QuickTunnel(8765, binary=happy, on_change=lambda: changes.append(t.state))
    check("initial state off", t.state == "off")
    check("argv shape", t._argv("cloudflared") == [
        "cloudflared", "tunnel", "--url", "https://localhost:8765",
        "--no-tls-verify"])
    ok = await t.start()
    check("start returns True", ok)
    check("state starting after spawn", t.state == STATE_STARTING)
    url = await t.wait_url(timeout=10)
    check("wait_url returns the URL", url == "https://abc-def.trycloudflare.com")
    check("state up", t.state == STATE_UP)
    check("hostname strips scheme", t.hostname == "abc-def.trycloudflare.com")
    check("status_line up", t.status_line() == "Tunnel: up — abc-def.trycloudflare.com")
    check("on_change fired for starting and up",
          changes[:2] == [STATE_STARTING, STATE_UP])
    await t.stop()
    check("state stopped after stop", t.state == STATE_STOPPED)
    check("url cleared after stop", t.url is None and t.hostname is None)
    await t.stop()
    check("stop is idempotent", t.state == STATE_STOPPED)

    # -- child killed on stop (no orphan): PID must be gone
    pidfile = tmp / "pid"
    slow = fake_binary(tmp, "cf_slow", f"""
echo $$ > {pidfile}
echo "INF |  https://xyz-1.trycloudflare.com  |" >&2
sleep 60
""")
    t2 = QuickTunnel(8765, binary=slow)
    await t2.start()
    await t2.wait_url(timeout=10)
    pid = int(pidfile.read_text().strip())
    await t2.stop()
    await asyncio.sleep(0.1)
    alive = True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        alive = False
    check("child process killed on stop", not alive)

    # -- never prints a URL: wait_url times out, state stays starting
    silent = fake_binary(tmp, "cf_silent", "sleep 60\n")
    t3 = QuickTunnel(8765, binary=silent)
    await t3.start()
    url = await t3.wait_url(timeout=0.3)
    check("timeout path returns None", url is None)
    check("state still starting on timeout", t3.state == STATE_STARTING)
    await t3.stop()

    # -- child dies before printing a URL: failed + detail
    dying = fake_binary(tmp, "cf_dying", "echo 'INF boom' >&2\nexit 3\n")
    t4 = QuickTunnel(8765, binary=dying)
    await t4.start()
    url = await t4.wait_url(timeout=10)
    check("dead child: wait_url None", url is None)
    check("dead child: state failed", t4.state == STATE_FAILED)
    check("dead child: detail carries rc", "rc=3" in (t4.detail or ""))
    await t4.stop()
    check("failure state preserved through stop", t4.state == STATE_FAILED)

    # -- child dies AFTER the URL was up: URL cleared (no stale endpoint)
    updying = fake_binary(tmp, "cf_updying", """
echo "INF |  https://gone-1.trycloudflare.com  |" >&2
sleep 0.5
exit 1
""")
    t5 = QuickTunnel(8765, binary=updying)
    await t5.start()
    await t5.wait_url(timeout=10)
    check("up before death", t5.state == STATE_UP)
    for _ in range(50):
        if t5.state == STATE_FAILED:
            break
        await asyncio.sleep(0.1)
    check("death after up: state failed", t5.state == STATE_FAILED)
    check("death after up: url cleared", t5.url is None)
    await t5.stop()

    # -- binary missing: fail-visible, start returns False
    t6 = QuickTunnel(8765, binary=str(tmp / "does-not-exist"))
    ok = await t6.start()
    check("missing binary: start False", not ok)
    check("missing binary: state failed", t6.state == STATE_FAILED)
    check("missing binary: wait_url immediate None",
          await t6.wait_url(timeout=5) is None)
    t7 = QuickTunnel(8765, binary=None)
    # find_cloudflared may or may not find a real binary; only assert the
    # helper is callable and returns str|None.
    check("find_cloudflared returns str|None",
          find_cloudflared() is None or isinstance(find_cloudflared(), str))
    del t7

asyncio.run(main())
print("Group B: all assertions passed")
PYEOF

# ---- Group C: merge_tunnel_endpoint + emission -------------------------------
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
from pathlib import Path
from urllib.parse import quote

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

from pairing import (
    Endpoint,
    build_pairing_uri,
    merge_tunnel_endpoint,
    resolve_advertised_endpoints,
)


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


TUN = Endpoint("abc-def.trycloudflare.com", 443, "tunnel", "ca")


def emit(adv):
    return build_pairing_uri(
        "TOK", adv.primary.host, adv.primary.port, "FP", None,
        kind=adv.primary.kind if adv.override else None,
        trust=adv.primary.trust if adv.override else None,
        alt=adv.alts or None,
    )


# Negative control: no tunnel + no override ⇒ byte-identical legacy URI.
legacy = resolve_advertised_endpoints(serving_port=8765, detected_ip="192.168.1.20")
check("no tunnel: resolved unchanged (same object semantics)",
      merge_tunnel_endpoint(legacy, None) == legacy)
check("no tunnel + no override: byte-identical legacy URI",
      emit(merge_tunnel_endpoint(legacy, None))
      == "applink://192.168.1.20:8765/pair?t=TOK&fp=FP")

# Tunnel + no override: primary stays LAN/pin (no kind/trust params), tunnel
# rides as the single alt record with exact grammar.
merged = merge_tunnel_endpoint(legacy, TUN)
check("tunnel appended to alts", merged.alts == [TUN])
check("primary untouched", merged.primary == legacy.primary)
check("override flag untouched", merged.override is False)
expected_alt = quote("abc-def.trycloudflare.com:443;tunnel;ca", safe="")
uri = emit(merged)
check("emission: authority stays LAN", uri.startswith("applink://192.168.1.20:8765/pair"))
check("emission: no kind/trust params without override",
      "kind=" not in uri and "trust=" not in uri)
check("emission: exact alt grammar", uri.endswith(f"&alt={expected_alt}"))

# Tunnel + user override: tunnel appended AFTER the existing LAN alt; the
# user's primary is untouched.
over = resolve_advertised_endpoints(
    serving_port=8765, detected_ip="192.168.1.20",
    cli_host="100.101.102.103", cli_kind="mesh",
)
m2 = merge_tunnel_endpoint(over, TUN)
check("override primary untouched", m2.primary.host == "100.101.102.103")
check("tunnel appended after LAN alt",
      m2.alts == [Endpoint("192.168.1.20", 8765, "lan", "pin"), TUN])
u2 = emit(m2)
expected_alt2 = quote(
    "192.168.1.20:8765;lan;pin,abc-def.trycloudflare.com:443;tunnel;ca", safe="")
check("override emission: alt list ordered LAN-then-tunnel",
      u2.endswith(f"&alt={expected_alt2}"))

print("Group C: all assertions passed")
PYEOF

# ---- Group D: auto_tunnel config key + server accessors ----------------------
if ! "$PYTHON" -c "import yaml, websockets" 2>/dev/null; then
    echo "SKIP Group D: pyyaml/websockets not installed (run 'ait setup' first)"
else
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import tunnel as TN
from pairing import Endpoint
from server import AppLinkServer, load_applink_config


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


def cfg_for(yaml_text):
    tmp = Path(tempfile.mkdtemp(prefix="cfg-"))
    (tmp / "aitasks" / "metadata").mkdir(parents=True)
    (tmp / "aitasks" / "metadata" / "project_config.yaml").write_text(yaml_text)
    return load_applink_config(tmp)


check("auto_tunnel absent -> None", cfg_for("tmux:\n  applink: {}\n")["auto_tunnel"] is None)
check("auto_tunnel: cloudflared accepted",
      cfg_for("tmux:\n  applink:\n    auto_tunnel: cloudflared\n")["auto_tunnel"] == "cloudflared")
check("unknown backend -> None",
      cfg_for("tmux:\n  applink:\n    auto_tunnel: ngrok\n")["auto_tunnel"] is None)
check("non-string -> None",
      cfg_for("tmux:\n  applink:\n    auto_tunnel: [x]\n")["auto_tunnel"] is None)
bad = cfg_for("tmux:\n  applink:\n    auto_tunnel: true\n    history_capture_lines: 500\n")
check("bad auto_tunnel leaves sibling keys intact",
      bad["auto_tunnel"] is None and bad["history_capture_lines"] == 500)

# Server accessors (no listener started — pure state).
srv = AppLinkServer.__new__(AppLinkServer)
srv.tunnel = None
check("tunnel_active False without supervisor", srv.tunnel_active() is False)
check("tunnel_endpoint None without supervisor", srv.tunnel_endpoint() is None)

t = TN.QuickTunnel(8765, binary="/nonexistent")
srv.tunnel = t
t.state = TN.STATE_STARTING
# STARTING must NOT activate the cap exemption: no tunneled client can
# arrive before the URL is published, so pre-URL exemption would only widen
# local exposure (e.g. cloudflared hanging before its banner).
check("tunnel_active False while starting", srv.tunnel_active() is False)
check("tunnel_endpoint None while starting", srv.tunnel_endpoint() is None)
t.state = TN.STATE_UP
t.url = "https://abc-def.trycloudflare.com"
check("tunnel_active True while up", srv.tunnel_active() is True)
check("tunnel_endpoint up -> Endpoint(host,443,tunnel,ca)",
      srv.tunnel_endpoint() == Endpoint("abc-def.trycloudflare.com", 443, "tunnel", "ca"))
t.state = TN.STATE_FAILED
t.url = None
check("tunnel_active False after failure", srv.tunnel_active() is False)
check("tunnel_endpoint None after failure", srv.tunnel_endpoint() is None)

print("Group D: all assertions passed")
PYEOF
fi

# ---- Group E: --auto-tunnel on both real entry points ------------------------
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


try:
    import segno  # noqa: F401
    import headless
    ns = headless._parse_args(["--auto-tunnel"])
    check("headless --auto-tunnel accepted", ns.auto_tunnel is True)
    ns = headless._parse_args([])
    check("headless default off", ns.auto_tunnel is False)
except ImportError:
    print("SKIP headless argparse checks (segno not installed)")

try:
    import applink_app
    ns = applink_app._parse_args(["--auto-tunnel"])
    check("TUI --auto-tunnel accepted", ns.auto_tunnel is True)
    ns = applink_app._parse_args([])
    check("TUI default off", ns.auto_tunnel is False)
except ImportError:
    print("SKIP TUI argparse checks (textual not installed)")

print("Group E: all assertions passed")
PYEOF

# ---- Group F: delayed tunnel-up — headless emit merges at each call ----------
if ! "$PYTHON" -c "import yaml, websockets, segno" 2>/dev/null; then
    echo "SKIP Group F: deps not installed (run 'ait setup' first)"
else
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
from pathlib import Path
from urllib.parse import quote

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import tunnel as TN
from pairing import build_pairing_uri, merge_tunnel_endpoint, resolve_advertised_endpoints
from server import AppLinkServer


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


# Model the headless _emit closure: adv resolved ONCE, tunnel merged at each
# call via server.tunnel_endpoint() — a late tunnel-up must appear in the
# SIGHUP reprint without re-resolving.
srv = AppLinkServer.__new__(AppLinkServer)
srv.tunnel = None
adv = resolve_advertised_endpoints(serving_port=8765, detected_ip="192.168.1.20")


def emit():
    merged = merge_tunnel_endpoint(adv, srv.tunnel_endpoint())
    return build_pairing_uri(
        "TOK", merged.primary.host, merged.primary.port, "FP", None,
        kind=merged.primary.kind if merged.override else None,
        trust=merged.primary.trust if merged.override else None,
        alt=merged.alts or None,
    )


first = emit()
check("pre-tunnel emit is legacy LAN-only",
      first == "applink://192.168.1.20:8765/pair?t=TOK&fp=FP")

t = TN.QuickTunnel(8765, binary="/nonexistent")
t.state = TN.STATE_UP
t.url = "https://late-up.trycloudflare.com"
srv.tunnel = t
second = emit()
expected_alt = quote("late-up.trycloudflare.com:443;tunnel;ca", safe="")
check("post-tunnel reprint gains the tunnel alt",
      second.endswith(f"&alt={expected_alt}"))
check("post-tunnel reprint keeps LAN primary",
      second.startswith("applink://192.168.1.20:8765/pair?t=TOK&fp=FP"))

t.state = TN.STATE_FAILED
t.url = None
third = emit()
check("tunnel death: reprint drops the dead endpoint", third == first)

print("Group F: all assertions passed")
PYEOF
fi

# ---- Group G: TUI delayed tunnel-up (textual-gated) --------------------------
# The pairing QR is built once in PairingScreen.compose(); a tunnel that comes
# up later must be re-rendered into the mounted QR by ApplinkApp._on_server_change.
if ! "$PYTHON" -c "import textual, segno, yaml, websockets" 2>/dev/null; then
    echo "SKIP Group G: textual/segno not installed"
else
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import sys
from pathlib import Path
from urllib.parse import quote

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import applink_app
import tunnel as TN
from applink_app import AppLinkRuntime, PairingScreen
from pairing import resolve_advertised_endpoints
from server import AppLinkServer
from textual.app import App


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


def bare_runtime():
    """AppLinkRuntime state without the ctor (no cert/config/network I/O)."""
    rt = AppLinkRuntime.__new__(AppLinkRuntime)
    rt.port = 8765
    rt.ip = "192.168.1.20"
    rt.host = None
    rt.advertised = resolve_advertised_endpoints(
        serving_port=8765, detected_ip="192.168.1.20")
    rt.advertise_warning = None
    rt.fingerprint = "FP"
    rt.token = "TOK"
    rt.server = None
    rt.firewall = None
    return rt


def up_server():
    srv = AppLinkServer.__new__(AppLinkServer)
    t = TN.QuickTunnel(8765, binary="/nonexistent")
    t.state = TN.STATE_UP
    t.url = "https://late-up.trycloudflare.com"
    srv.tunnel = t
    return srv


LEGACY = "applink://192.168.1.20:8765/pair?t=TOK&fp=FP"
TUNNEL_ALT = quote("late-up.trycloudflare.com:443;tunnel;ca", safe="")

# Startup-order guard: build_uri with server=None (pre-mount / --smoke) emits
# the unchanged LAN QR.
rt = bare_runtime()
check("build_uri with server=None is the legacy LAN QR", rt.build_uri() == LEGACY)
rt.server = up_server()
check("build_uri with up tunnel gains the alt",
      rt.build_uri() == f"{LEGACY}&alt={TUNNEL_ALT}")


class _Harness(App):
    """Minimal app owning a PairingScreen; runtime faked at the same seam
    ApplinkApp uses (self.app.runtime)."""
    def __init__(self):
        super().__init__()
        self.runtime = bare_runtime()


async def run_checks():
    app = _Harness()
    async with app.run_test() as pilot:
        await app.push_screen(PairingScreen())
        await pilot.pause()
        screen = app.screen
        check("mounted QR starts with the pre-tunnel payload",
              screen._qr._data == LEGACY)
        # Tunnel comes up AFTER compose — the server-change hook must
        # re-render the mounted QR with the merged tunnel alt.
        app.runtime.server = up_server()
        applink_app.ApplinkApp._on_server_change(app)
        check("_on_server_change re-renders the mounted QR with the tunnel alt",
              screen._qr._data == f"{LEGACY}&alt={TUNNEL_ALT}")

asyncio.run(run_checks())
print("Group G: all assertions passed")
PYEOF
fi

echo ""
echo "test_applink_tunnel.sh: PASS"
