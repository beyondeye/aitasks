#!/usr/bin/env bash
# test_applink_advertise.sh — unit tests for the advertised-endpoint override
# (t1061_1): host normalization, config parsing, resolver group precedence,
# QR URI emission (incl. the byte-identical legacy guarantee), and the real
# CLI entry points (headless + TUI argparsers).
#
# Wire grammar under test: aidocs/applink/protocol.md §Pairing flow,
# "Endpoint & trust model".
# Run: bash tests/test_applink_advertise.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

# ---- Group A: pure helpers (pairing.py only — stdlib, no deps) --------------
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

from pairing import (
    Endpoint,
    build_pairing_uri,
    encode_alt_param,
    normalize_advertised_host,
    resolve_advertised_endpoints,
)


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


# --- normalize_advertised_host: accepted forms -------------------------------
check("bare host", normalize_advertised_host("foo.example.com") == ("foo.example.com", None))
check("host:port", normalize_advertised_host("foo.example.com:443") == ("foo.example.com", 443))
check("scheme stripped", normalize_advertised_host("https://foo.trycloudflare.com") == ("foo.trycloudflare.com", None))
check("scheme+port+trailing slash", normalize_advertised_host("wss://foo.example.com:443/") == ("foo.example.com", 443))
check("path stripped", normalize_advertised_host("foo.example.com/some/path") == ("foo.example.com", None))
check("query stripped", normalize_advertised_host("foo.example.com?x=1") == ("foo.example.com", None))
check("IPv4 literal", normalize_advertised_host("100.101.102.103") == ("100.101.102.103", None))
check("bracketed IPv6", normalize_advertised_host("[fd7a::1]") == ("fd7a::1", None))
check("bracketed IPv6 + port", normalize_advertised_host("[fd7a::1]:8765") == ("fd7a::1", 8765))
check("bare IPv6 literal", normalize_advertised_host("fd7a:115c:a1e0::1") == ("fd7a:115c:a1e0::1", None))
check("surrounding whitespace trimmed", normalize_advertised_host("  foo.example.com  ") == ("foo.example.com", None))

# --- normalize_advertised_host: rejects ---------------------------------------
for label, bad in [
    ("empty", ""),
    ("only slash", "/"),
    ("only scheme", "https://"),
    ("userinfo @", "user@foo.example.com"),
    ("bad port (text)", "foo.example.com:http"),
    ("port out of range", "foo.example.com:70000"),
    ("port zero", "foo.example.com:0"),
    ("multi-colon non-IPv6", "a:b:c"),
    ("malformed brackets", "[fd7a::1"),
    ("whitespace inside host", "foo bar.example.com"),
]:
    try:
        normalize_advertised_host(bad)
        raise AssertionError(f"FAIL: reject {label!r} — no ValueError for {bad!r}")
    except ValueError:
        print(f"ok - rejects {label}")

# --- resolver: group precedence -----------------------------------------------
CFG_TUNNEL = {
    "advertised_host": "cfg.example.com",
    "advertised_port": 9999,
    "advertised_kind": "tunnel",
    "advertised_trust": "ca",
}

# Any CLI flag → config group ignored wholesale (stale-kind case from review).
res = resolve_advertised_endpoints(
    serving_port=8765, detected_ip="192.168.1.5",
    config=CFG_TUNNEL, cli_host="100.64.0.7", cli_trust="pin")
check("CLI host ignores config kind (mesh, not tunnel)", res.primary.kind == "mesh")
check("CLI host ignores config port (serving port)", res.primary.port == 8765)
check("CLI trust explicit pin", res.primary.trust == "pin")
check("CLI group override active", res.override and res.warning is None)

# Config-only group.
res = resolve_advertised_endpoints(
    serving_port=8765, detected_ip="192.168.1.5", config=CFG_TUNNEL)
check("config group host", res.primary == Endpoint("cfg.example.com", 9999, "tunnel", "ca"))
check("config group alt = LAN", res.alts == [Endpoint("192.168.1.5", 8765, "lan", "pin")])

# No override anywhere → legacy.
res = resolve_advertised_endpoints(
    serving_port=8765, detected_ip="192.168.1.5", config={})
check("no override → legacy primary", res.primary == Endpoint("192.168.1.5", 8765, "lan", "pin"))
check("no override → no alts, not override", res.alts == [] and not res.override)
check("no override → no warning", res.warning is None)

# Within-group port chain: explicit > embedded > serving.
res = resolve_advertised_endpoints(
    serving_port=8765, detected_ip="192.168.1.5", config={},
    cli_host="foo.example.com:443", cli_port=444)
check("explicit port beats embedded", res.primary.port == 444)
res = resolve_advertised_endpoints(
    serving_port=8765, detected_ip="192.168.1.5", config={},
    cli_host="foo.example.com:443")
check("embedded port beats serving", res.primary.port == 443)
res = resolve_advertised_endpoints(
    serving_port=8765, detected_ip="192.168.1.5", config={},
    cli_host="foo.example.com")
check("serving port fallback", res.primary.port == 8765)

# Invalid config host → LAN fallback + warning (fail-visible, never malformed QR).
res = resolve_advertised_endpoints(
    serving_port=8765, detected_ip="192.168.1.5",
    config={"advertised_host": "user@bad host", "advertised_port": None,
            "advertised_kind": None, "advertised_trust": "pin"})
check("invalid config host → legacy fallback", res.primary.host == "192.168.1.5" and not res.override)
check("invalid config host → warning set",
      res.warning is not None and "advertised_host" in res.warning
      and "LAN address" in res.warning)

# Invalid CLI host → raises (argparse rejects earlier; resolver is the backstop).
try:
    resolve_advertised_endpoints(
        serving_port=8765, detected_ip="192.168.1.5", config={},
        cli_host="user@bad host")
    raise AssertionError("FAIL: invalid CLI host did not raise")
except ValueError:
    print("ok - invalid CLI host raises")

# CLI kind/trust/port without host → rejected.
try:
    resolve_advertised_endpoints(
        serving_port=8765, detected_ip="192.168.1.5", config={}, cli_trust="ca")
    raise AssertionError("FAIL: CLI trust without host did not raise")
except ValueError:
    print("ok - CLI flags without host rejected")

# Out-of-range cli_port → resolver backstop raises (argparse rejects earlier);
# 0 must never silently fall through to the serving port.
for bad_port in (0, 70000):
    try:
        resolve_advertised_endpoints(
            serving_port=8765, detected_ip="192.168.1.5", config={},
            cli_host="foo.example.com", cli_port=bad_port)
        raise AssertionError(f"FAIL: cli_port={bad_port} did not raise")
    except ValueError:
        print(f"ok - resolver rejects cli_port={bad_port}")

# 0.0.0.0 detected (offline sentinel) → never emitted as alt.
res = resolve_advertised_endpoints(
    serving_port=8765, detected_ip="0.0.0.0", config={}, cli_host="100.64.0.7")
check("0.0.0.0 detected → no alt", res.alts == [])
# Override equal to detected IP → no self-alt.
res = resolve_advertised_endpoints(
    serving_port=8765, detected_ip="100.64.0.7", config={}, cli_host="100.64.0.7")
check("override == detected → no alt", res.alts == [])

# --- emission -------------------------------------------------------------------
LEGACY = "applink://192.168.1.5:8765/pair?t=tok&fp=fp"
check("legacy URI byte-identical (old-client guarantee)",
      build_pairing_uri("tok", "192.168.1.5", 8765, "fp") == LEGACY)
check("legacy URI + name byte-identical",
      build_pairing_uri("tok", "192.168.1.5", 8765, "fp", "pc") == LEGACY + "&name=pc")

alts = [Endpoint("192.168.1.5", 8765, "lan", "pin")]
uri = build_pairing_uri("tok", "100.64.0.7", 8765, "fp", "pc",
                        kind="mesh", trust="pin", alt=alts)
expected_alt = quote("192.168.1.5:8765;lan;pin", safe="")
check("override URI exact",
      uri == "applink://100.64.0.7:8765/pair?t=tok&fp=fp"
             f"&kind=mesh&trust=pin&alt={expected_alt}&name=pc")
check("alt URL-encodes ';' and ':'", "%3B" in uri and "%3A" in uri)

uri_ca = build_pairing_uri("tok", "foo.trycloudflare.com", 443, "fp",
                           kind="tunnel", trust="ca", alt=alts)
check("trust=ca emitted faithfully", "&kind=tunnel&trust=ca&" in uri_ca)

# IPv6: bracketed in authority and inside alt records.
uri6 = build_pairing_uri("tok", "fd7a:115c:a1e0::1", 8765, "fp",
                         kind="mesh", trust="pin",
                         alt=[Endpoint("fd7a::99", 8765, "lan", "pin")])
check("IPv6 authority bracketed", uri6.startswith("applink://[fd7a:115c:a1e0::1]:8765/pair?"))
check("IPv6 alt record bracketed",
      quote("[fd7a::99]:8765;lan;pin", safe="") in uri6)

# Multi-record alt encoding (fixed field order, comma-separated).
two = encode_alt_param([Endpoint("192.168.1.5", 8765, "lan", "pin"),
                        Endpoint("100.64.0.7", 443, "mesh", "pin")])
check("alt multi-record exact",
      two == quote("192.168.1.5:8765;lan;pin,100.64.0.7:443;mesh;pin", safe=""))

print("Group A: all assertions passed")
PYEOF

# ---- Group B: config loader (needs pyyaml) ----------------------------------
if "$PYTHON" -c "import yaml" 2>/dev/null; then
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))
sys.path.insert(0, str(root / ".aitask-scripts"))

from server import load_applink_config


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


def load_from(yaml_text):
    with tempfile.TemporaryDirectory() as td:
        meta = Path(td) / "aitasks" / "metadata"
        meta.mkdir(parents=True)
        (meta / "project_config.yaml").write_text(yaml_text)
        return load_applink_config(td)


cfg = load_from("""
tmux:
  applink:
    advertised_host: 100.101.102.103
    advertised_port: 8443
    advertised_kind: mesh
    advertised_trust: ca
""")
check("config: all four keys parsed",
      cfg["advertised_host"] == "100.101.102.103" and cfg["advertised_port"] == 8443
      and cfg["advertised_kind"] == "mesh" and cfg["advertised_trust"] == "ca")

cfg = load_from("tmux:\n  applink:\n    history_capture_lines: 500\n")
check("config: keys absent → defaults",
      cfg["advertised_host"] is None and cfg["advertised_port"] is None
      and cfg["advertised_kind"] is None and cfg["advertised_trust"] == "pin"
      and cfg["history_capture_lines"] == 500)

# Per-key fault tolerance: each bad key falls back independently.
cfg = load_from("""
tmux:
  applink:
    advertised_host: 100.101.102.103
    advertised_port: not-a-port
    advertised_kind: warp
    advertised_trust: maybe
""")
check("config: bad port/kind/trust degrade independently, host survives",
      cfg["advertised_host"] == "100.101.102.103" and cfg["advertised_port"] is None
      and cfg["advertised_kind"] is None and cfg["advertised_trust"] == "pin")

cfg = load_from("tmux:\n  applink:\n    advertised_port: 99999\n")
check("config: out-of-range port → None", cfg["advertised_port"] is None)

cfg = load_from("tmux: [not, a, dict]\n")
check("config: malformed tree → all defaults",
      cfg["advertised_host"] is None and cfg["advertised_trust"] == "pin")

cfg = load_applink_config("/nonexistent/dir")
check("config: missing file → defaults",
      cfg["advertised_host"] is None and cfg["advertised_port"] is None)

print("Group B: all assertions passed")
PYEOF
else
    echo "SKIP (Group B): pyyaml not installed"
fi

# ---- Group C: real CLI entry points ------------------------------------------
# Headless argparser (needs websockets/msgpack/segno for module import).
if "$PYTHON" -c "import websockets, msgpack, segno" 2>/dev/null; then
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import headless


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


args = headless._parse_args([
    "--advertise-host", "100.64.0.7:443", "--advertise-port", "444",
    "--advertise-kind", "mesh", "--advertise-trust", "pin"])
check("headless: four advertise flags parsed",
      args.advertise_host == "100.64.0.7:443" and args.advertise_port == 444
      and args.advertise_kind == "mesh" and args.advertise_trust == "pin")

args = headless._parse_args([])
check("headless: flags default to None",
      args.advertise_host is None and args.advertise_port is None
      and args.advertise_kind is None and args.advertise_trust is None)

for label, argv in [
    ("invalid --advertise-host rejected", ["--advertise-host", "user@bad host"]),
    ("advertise flags without host rejected", ["--advertise-trust", "ca"]),
    ("bad kind choice rejected", ["--advertise-host", "h", "--advertise-kind", "warp"]),
    ("--advertise-port 0 rejected", ["--advertise-host", "h", "--advertise-port", "0"]),
    ("--advertise-port 70000 rejected", ["--advertise-host", "h", "--advertise-port", "70000"]),
    ("--advertise-port non-int rejected", ["--advertise-host", "h", "--advertise-port", "http"]),
]:
    try:
        headless._parse_args(argv)
        raise AssertionError(f"FAIL: headless {label} — no SystemExit")
    except SystemExit as exc:
        check(f"headless: {label}", exc.code == 2)

print("Group C (headless): all assertions passed")
PYEOF
else
    echo "SKIP (Group C headless): websockets/msgpack/segno not installed"
fi

# TUI argparser (needs textual for module import).
if "$PYTHON" -c "import textual, segno" 2>/dev/null; then
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))
sys.path.insert(0, str(root / ".aitask-scripts"))

import applink_app


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


args = applink_app._parse_args([
    "--advertise-host", "foo.example.com", "--advertise-trust", "ca"])
check("tui: advertise flags parsed",
      args.advertise_host == "foo.example.com" and args.advertise_trust == "ca")

for label, argv in [
    ("invalid --advertise-host rejected", ["--advertise-host", ""]),
    ("advertise flags without host rejected", ["--advertise-port", "443"]),
    ("--advertise-port 0 rejected", ["--advertise-host", "h", "--advertise-port", "0"]),
    ("--advertise-port 70000 rejected", ["--advertise-host", "h", "--advertise-port", "70000"]),
]:
    try:
        applink_app._parse_args(argv)
        raise AssertionError(f"FAIL: tui {label} — no SystemExit")
    except SystemExit as exc:
        check(f"tui: {label}", exc.code == 2)

print("Group C (tui): all assertions passed")
PYEOF
else
    echo "SKIP (Group C tui): textual/segno not installed"
fi

echo "PASS: test_applink_advertise.sh"
