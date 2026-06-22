#!/usr/bin/env bash
# test_applink_firewall.sh — unit test for the launch-time firewall doctor (t1043).
#
# Covers the pure surface of .aitask-scripts/applink/firewall_doctor.py:
# backend detection (priority + None + failure-silence), LAN-CIDR derivation,
# per-backend command synthesis, shell-safe command rendering (firewalld
# rich-rule quoting), idempotent result classification, the backend-agnostic
# generic-help fallback, and the diagnose() always-returns-a-status contract.
# firewall_doctor.py imports only stdlib, so this test needs no dependency-skip
# guard (same as test_applink_pairing.sh).
# Run: bash tests/test_applink_firewall.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import shlex
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import firewall_doctor as fd


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


# --- detect_backend: priority, None, and failure-silence -------------------

def probe_for(active):
    """Return a probe that reports `active` only for the named service."""
    return lambda svc: "active" if svc == active else "inactive"

check("detect_backend ufw wins",
      fd.detect_backend(probe=probe_for("ufw")) == "ufw")
check("detect_backend firewalld",
      fd.detect_backend(probe=probe_for("firewalld")) == "firewalld")
check("detect_backend nftables",
      fd.detect_backend(probe=probe_for("nftables")) == "nftables")
check("detect_backend priority ufw>firewalld",
      fd.detect_backend(probe=lambda svc: "active") == "ufw")
check("detect_backend None when nothing active",
      fd.detect_backend(probe=lambda svc: "inactive") is None)
check("detect_backend None on empty probe (failure-silent default)",
      fd.detect_backend(probe=lambda svc: "") is None)

# _default_probe must swallow a missing systemctl / timeout and return "" so the
# whole doctor degrades to "no backend" rather than hanging or crashing.
import subprocess as _sub
_orig_run = fd.subprocess.run

def _raise_fnf(*a, **k):
    raise FileNotFoundError("systemctl")

def _raise_timeout(*a, **k):
    raise _sub.TimeoutExpired(cmd="systemctl", timeout=1.5)

fd.subprocess.run = _raise_fnf
check("_default_probe → '' when systemctl missing (FileNotFoundError)",
      fd._default_probe("ufw") == "")
fd.subprocess.run = _raise_timeout
check("_default_probe → '' on timeout (TimeoutExpired)",
      fd._default_probe("ufw") == "")
fd.subprocess.run = _orig_run

# --- parse_lan_cidr --------------------------------------------------------

IP_OUT = (
    "1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever\n"
    "2: wlp0s20f3    inet 192.168.1.23/24 brd 192.168.1.255 scope global "
    "dynamic noprefixroute wlp0s20f3\\       valid_lft 1234sec\n"
)
check("parse_lan_cidr returns real network/prefix",
      fd.parse_lan_cidr(IP_OUT, "192.168.1.23") == "192.168.1.0/24")
check("parse_lan_cidr /24 fallback when ip absent",
      fd.parse_lan_cidr(IP_OUT, "10.0.0.5") == "10.0.0.0/24")
check("parse_lan_cidr /24 fallback on empty output",
      fd.parse_lan_cidr("", "192.168.5.7") == "192.168.5.0/24")

# --- build_open_commands (exact argv) --------------------------------------

check("ufw argv",
      fd.build_open_commands("ufw", 8765, "192.168.1.0/24") ==
      [["ufw", "allow", "from", "192.168.1.0/24", "to", "any",
        "port", "8765", "proto", "tcp"]])
check("firewalld argv is add-rich-rule + reload",
      fd.build_open_commands("firewalld", 8765, "192.168.1.0/24") ==
      [["firewall-cmd", "--permanent",
        "--add-rich-rule=rule family=ipv4 source address=192.168.1.0/24 "
        "port port=8765 protocol=tcp accept"],
       ["firewall-cmd", "--reload"]])
check("nftables argv",
      fd.build_open_commands("nftables", 8765, "192.168.1.0/24") ==
      [["nft", "add", "rule", "inet", "filter", "input", "ip", "saddr",
        "192.168.1.0/24", "tcp", "dport", "8765", "accept"]])
check("iptables argv",
      fd.build_open_commands("iptables", 8765, "192.168.1.0/24") ==
      [["iptables", "-I", "INPUT", "-p", "tcp", "-s", "192.168.1.0/24",
        "--dport", "8765", "-j", "ACCEPT"]])

# --- auto_fixable ----------------------------------------------------------

check("ufw auto-fixable", fd.auto_fixable("ufw") is True)
check("firewalld auto-fixable", fd.auto_fixable("firewalld") is True)
check("nftables NOT auto-fixable", fd.auto_fixable("nftables") is False)
check("iptables NOT auto-fixable", fd.auto_fixable("iptables") is False)
check("None NOT auto-fixable", fd.auto_fixable(None) is False)

# --- privilege_wrapper -----------------------------------------------------

_orig_which = fd.shutil.which
fd.shutil.which = lambda name: "/usr/bin/pkexec" if name == "pkexec" else None
check("privilege_wrapper = ['pkexec'] when present",
      fd.privilege_wrapper() == ["pkexec"])
fd.shutil.which = lambda name: None
check("privilege_wrapper = None when pkexec absent",
      fd.privilege_wrapper() is None)
fd.shutil.which = _orig_which

# --- display_command: shell-safe (concern 2) -------------------------------

ufw_disp = fd.display_command(fd.build_open_commands("ufw", 8765, "192.168.1.0/24"))
check("ufw display has no spurious quoting",
      ufw_disp == "sudo ufw allow from 192.168.1.0/24 to any port 8765 proto tcp")

fw_cmds = fd.build_open_commands("firewalld", 8765, "192.168.1.0/24")
fw_disp = fd.display_command(fw_cmds)
check("firewalld display joins the two commands with &&", " && " in fw_disp)
# The rich rule (one argv element with spaces) MUST be a single shell token.
check("firewalld rich-rule is shell-quoted as one token",
      "'--add-rich-rule=rule family=ipv4 source address=192.168.1.0/24 "
      "port port=8765 protocol=tcp accept'" in fw_disp)
# And it round-trips: shlex.split of the first command recovers the exact argv.
first = fw_disp.split(" && ")[0]
recovered = shlex.split(first)
check("firewalld display round-trips via shlex.split",
      recovered == ["sudo"] + fw_cmds[0])

# --- interpret_result: idempotency (concern 3) -----------------------------

check("ufw 'already exists' → success/already open",
      fd.interpret_result("ufw", 0, "Skipping adding existing rule") ==
      (True, "already open"))
check("firewalld ALREADY_ENABLED → success even on nonzero exit",
      fd.interpret_result("firewalld", 1, "Warning: ALREADY_ENABLED: ...")[0] is True)
check("clean exit 0 → opened",
      fd.interpret_result("ufw", 0, "Rule added") == (True, "opened"))
ok, detail = fd.interpret_result("ufw", 1, "ERROR: could not be set")
check("genuine error → failure", ok is False and "ERROR" in detail)

# --- generic_help: backend-agnostic fallback (concern 1) -------------------

gh = fd.generic_help(8765, "192.168.1.0/24")
for backend in ("ufw", "firewalld", "nftables", "iptables"):
    check(f"generic_help lists {backend}", f"{backend}:" in gh)
check("generic_help has cautious header",
      "No managed firewall" in gh and "8765" in gh and "192.168.1.0/24" in gh)

# --- render_firewall_block -------------------------------------------------

status = fd.FirewallStatus(
    backend="ufw", cidr="192.168.1.0/24", port=8765, auto_fixable=True,
    commands=fd.build_open_commands("ufw", 8765, "192.168.1.0/24"),
    display=fd.display_command(fd.build_open_commands("ufw", 8765, "192.168.1.0/24")),
)
block = fd.render_firewall_block(status)
check("render_firewall_block names the backend + port",
      "ufw" in block and "8765" in block)
check("render_firewall_block includes the sudo command",
      "sudo ufw allow" in block)

# --- diagnose always returns a FirewallStatus with a real cidr (concern A) --

fd_host = fd.host_lan_cidr
fd_detect = fd.detect_backend
fd.host_lan_cidr = lambda ip: "192.168.1.0/24"
try:
    fd.detect_backend = lambda probe=None: None
    s = fd.diagnose(8765, "192.168.1.23")
    check("diagnose never returns None", s is not None)
    check("undetected status carries real cidr",
          s.detected is False and s.cidr == "192.168.1.0/24" and s.commands == [])
    fd.detect_backend = lambda probe=None: "ufw"
    s2 = fd.diagnose(8765, "192.168.1.23")
    check("detected status has commands + display",
          s2.detected is True and s2.backend == "ufw"
          and s2.commands and s2.display)
finally:
    fd.host_lan_cidr = fd_host
    fd.detect_backend = fd_detect

print("\nALL PASSED")
PYEOF
