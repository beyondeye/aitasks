#!/usr/bin/env bash
# test_chatlink_preflight.sh — structured preflight checks (t1149_1).
#
# Covers: CheckResult shape (id + category buckets transport/runtime/
# operation, operation id is explore_relay_agent_command), the cheap/
# expensive probe split, pinned daemon_refuse_message strings per check id,
# timeout fail-closed behavior via a stub slow command, timeout=None waits
# for completion, per-check docker probes (faked subprocess), and the
# Textual-free import guard.
# Run: bash tests/test_chatlink_preflight.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

# Textual-free contract FIRST (before anything else can pull modules in).
import chatlink.preflight as pf
assert "textual" not in sys.modules, \
    "FAIL: chatlink.preflight must not load textual"
print("ok - import chatlink.preflight does not load textual")

from chatlink import paths as cl_paths

PASS = 0


def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


def by_id(results):
    return {r.id: r for r in results}


tmpdir = tempfile.TemporaryDirectory()
base = Path(tmpdir.name)

real_cfg_file = cl_paths.config_file
real_read_token = cl_paths.read_token
real_project_root = cl_paths.project_root
try:
    # ---- cheap checks -----------------------------------------------------
    # (1) missing config path: config_file fail + token still checked.
    cl_paths.config_file = lambda: None
    cl_paths.read_token = lambda: None
    out = pf.run_cheap_checks()
    res = by_id(out.results)
    check("missing config: config_file fail + token fail, nothing else",
          set(res) == {"config_file", "token"}
          and res["config_file"].severity == pf.FAIL
          and res["token"].severity == pf.FAIL
          and out.config is None and out.config_warnings == [])
    check("missing config: pinned daemon refusal text",
          res["config_file"].daemon_refuse_message == (
              "no gateway config found — create "
              f"{cl_paths.CONFIG_DEFAULT_REL} (seeded by 'ait setup') "
              "first."))
    check("token: pinned daemon refusal text",
          res["token"].daemon_refuse_message == (
              f"no bot token at {cl_paths.token_file()} — write the bot "
              "token there (0600) before starting."))

    # (2) malformed YAML: config_yaml fail carries the exact refusal text;
    # the raw load warning is exposed for the daemon replay.
    bad = base / "bad.yaml"
    bad.write_text("[unbalanced\n")
    cl_paths.config_file = lambda: bad
    out = pf.run_cheap_checks()
    res = by_id(out.results)
    check("malformed yaml: config_yaml fail, pinned refusal text",
          res["config_yaml"].severity == pf.FAIL
          and res["config_yaml"].daemon_refuse_message == (
              f"gateway config {bad} is missing or malformed — fix the "
              "YAML before starting.")
          and out.config is None)
    check("malformed yaml: raw load warning exposed for daemon replay",
          out.config_warnings == [
              f"{bad}: malformed YAML — refusing (fail-closed)"])

    # (3) empty mapping: intake fail (pinned text) + allowlist warn.
    empty = base / "empty.yaml"
    empty.write_text("{}\n")
    cl_paths.config_file = lambda: empty
    out = pf.run_cheap_checks()
    res = by_id(out.results)
    check("empty config: intake_channel fail, pinned refusal text",
          res["intake_channel"].severity == pf.FAIL
          and res["intake_channel"].daemon_refuse_message == (
              "config has no valid intake_channel — the daemon refuses "
              "to watch without one."))
    check("empty config: allowlist deny-by-default warn (no refusal text)",
          res["allowlist"].severity == pf.WARN
          and res["allowlist"].daemon_refuse_message is None)

    # (4) valid degraded config: per-key warn result + config loaded.
    degraded = base / "degraded.yaml"
    degraded.write_text(
        "intake_channel:\n  provider: mock\n  workspace_id: W1\n"
        "  conversation_id: C1\nallowed_user_ids: [U1]\n"
        "sandbox_cpus: 99\n")
    cl_paths.config_file = lambda: degraded
    cl_paths.read_token = lambda: "tok"
    out = pf.run_cheap_checks()
    res = by_id(out.results)
    check("degraded config: config_key warn result with the raw message",
          res["config_key:sandbox_cpus"].severity == pf.WARN
          and res["config_key:sandbox_cpus"].message == (
              "sandbox_cpus: 99 outside [1, 16] — clamped to 16"))
    check("degraded config: loads, clamped, warnings exposed once",
          out.config is not None and out.config.sandbox_cpus == 16
          and out.config_warnings == [
              "sandbox_cpus: 99 outside [1, 16] — clamped to 16"])
    check("valid config: intake/allowlist/token pass",
          res["intake_channel"].severity == pf.PASS
          and res["allowlist"].severity == pf.PASS
          and res["token"].severity == pf.PASS)

    # (5) category buckets (scope/naming contract, t1149 parent plan).
    check("cheap results carry the transport/runtime buckets",
          all(res[i].category == pf.TRANSPORT for i in
              ("config_file", "config_yaml", "intake_channel", "allowlist",
               "token"))
          and res["config_key:sandbox_cpus"].category == pf.RUNTIME)

    # (6) legacy refusal order preserved in the results list.
    ids = [r.id for r in out.results]
    check("cheap results in the daemon's legacy refusal order",
          ids == ["config_file", "config_yaml", "config_key:sandbox_cpus",
                  "intake_channel", "allowlist", "token"])

    # ---- operation check --------------------------------------------------
    resu, argv = pf.check_explore_relay_agent_command(
        resolver=lambda: ("docker", "run", "img"))
    check("agent command: resolver argv passes through",
          resu.severity == pf.PASS and argv == ("docker", "run", "img")
          and resu.id == "explore_relay_agent_command"
          and resu.category == pf.OPERATION)
    resu, argv = pf.check_explore_relay_agent_command(resolver=lambda: ())
    check("agent command: empty argv fails with pinned refusal text",
          resu.severity == pf.FAIL and argv == ()
          and resu.daemon_refuse_message == (
              "could not resolve the explore-relay agent command — run "
              "'ait codeagent invoke explore-relay --headless --dry-run' "
              "manually to diagnose the code-agent config."))

    def boom():
        raise RuntimeError("resolver exploded")

    resu, argv = pf.check_explore_relay_agent_command(resolver=boom)
    check("agent command: resolver exception fails closed",
          resu.severity == pf.FAIL and argv == ())

    # ---- resolver timeout semantics (real subprocess, stub `ait`) --------
    fake_root = base / "fakeroot"
    fake_root.mkdir()
    fake_ait = fake_root / "ait"

    def install_ait(body):
        fake_ait.write_text("#!/bin/sh\n" + body)
        fake_ait.chmod(fake_ait.stat().st_mode | stat.S_IEXEC)

    cl_paths.project_root = lambda: fake_root

    # timeout fires: a slow stub returns () quickly instead of hanging.
    install_ait("sleep 5\n")
    t0 = time.monotonic()
    argv = pf.resolve_explore_relay_argv(timeout=0.5)
    elapsed = time.monotonic() - t0
    check("resolver timeout: slow command fails closed to () quickly",
          argv == () and elapsed < 3.0)

    # timeout=None waits for completion and parses the DRY_RUN line.
    install_ait('echo "DRY_RUN: docker run --rm img cmd"\n')
    check("resolver timeout=None: waits and parses the argv",
          pf.resolve_explore_relay_argv(timeout=None)
          == ("docker", "run", "--rm", "img", "cmd"))
    check("resolver explicit timeout: normal completion still parses",
          pf.resolve_explore_relay_argv(timeout=10)
          == ("docker", "run", "--rm", "img", "cmd"))
finally:
    cl_paths.config_file = real_cfg_file
    cl_paths.read_token = real_read_token
    cl_paths.project_root = real_project_root

# ---- docker checks (faked subprocess.run — deterministic without docker) --
real_run = pf.subprocess.run


class FakeProc:
    def __init__(self, rc):
        self.returncode = rc


try:
    pf.subprocess.run = lambda *a, **k: FakeProc(0)
    check("docker image present: pass",
          pf.check_docker_image().severity == pf.PASS)
    pf.subprocess.run = lambda *a, **k: FakeProc(1)
    resu = pf.check_docker_image()
    check("docker image missing: warn with build fix hint",
          resu.severity == pf.WARN and "docker build" in resu.fix_hint
          and resu.category == pf.RUNTIME)

    def raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="docker", timeout=1)

    pf.subprocess.run = raise_timeout
    check("docker image probe timeout: fails closed to warn",
          pf.check_docker_image(timeout=1).severity == pf.WARN)
finally:
    pf.subprocess.run = real_run

real_which = pf.shutil.which
try:
    pf.shutil.which = lambda name: None
    check("docker binary absent: warn",
          pf.check_docker_binary().severity == pf.WARN)
    pf.shutil.which = lambda name: "/usr/bin/docker"
    check("docker binary present: pass",
          pf.check_docker_binary().severity == pf.PASS)
finally:
    pf.shutil.which = real_which

# ---- run_expensive_checks (TUI convenience) -------------------------------
real_run = pf.subprocess.run
real_which = pf.shutil.which
try:
    pf.subprocess.run = lambda *a, **k: FakeProc(0)
    pf.shutil.which = lambda name: "/usr/bin/docker"
    results = pf.run_expensive_checks(resolver=lambda: ("x",))
    check("run_expensive_checks: agent + docker binary + docker image",
          [r.id for r in results] == ["explore_relay_agent_command",
                                      "docker_binary", "docker_image"]
          and all(r.severity == pf.PASS for r in results))
finally:
    pf.subprocess.run = real_run
    pf.shutil.which = real_which

# Textual never crept in through any of the paths above.
check("textual never imported by preflight paths",
      "textual" not in sys.modules)

tmpdir.cleanup()
print(f"\nAll {PASS + 1} preflight checks passed.")
PYEOF

echo
echo "PASS: test_chatlink_preflight.sh"
