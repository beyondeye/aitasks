"""Structured preflight checks for the chatlink gateway (t1149_1).

The single source of truth for "is this gateway configuration runnable?".
Consumed by BOTH the daemon refuse path (``daemon.serve()`` — behavior
preserving: each failing check carries the exact legacy refusal text in
``daemon_refuse_message``) and the ``ait chatlink`` TUI (t1149_2 status
panel, t1149_3 wizard), which renders the TUI-friendly ``message`` /
``fix_hint``.

**Textual-import-free** (guard-tested) — like the daemon, this module must
never pull in Textual.

Checks are bucketed by ``category`` so future ChatLink operations can add
checks additively without rewriting the transport/config machinery or
changing daemon behavior:

- ``transport`` — Discord/config surface: ``config_file``, ``config_yaml``,
  ``intake_channel``, ``allowlist``, ``token``.
- ``runtime`` — backend/sandbox: ``docker_binary``, ``docker_image`` (the
  current sandbox image; future operations may declare their own image
  requirements as additional checks), per-key config warnings
  ``config_key:<key>``.
- ``operation`` — checks specific to the operation ChatLink launches. Today
  exactly one: ``explore_relay_agent_command`` (operation-qualified on
  purpose — a future operation adds its own ``<operation>_…`` check id and
  function instead of overloading a generic name).

Probe cost split (t1149 parent-plan contract): :func:`run_cheap_checks` is
pure file/YAML/in-memory — safe to call from a TUI polling loop.
The expensive per-check functions (:func:`check_explore_relay_agent_command`,
:func:`check_docker_binary`, :func:`check_docker_image`) spawn processes /
hit the OS; each accepts a ``timeout`` **defaulting to ``None`` = wait
indefinitely (the daemon's legacy behavior — the daemon passes no timeout)**
and fails closed on timeout/OSError (a ``fail``/``warn`` result, never a
hang). TUI consumers pass the explicit ``*_PROBE_TIMEOUT_S`` constants.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .config import load_config_with_warnings, ChatlinkConfig

# Severities.
PASS = "pass"
WARN = "warn"
FAIL = "fail"

# Categories (see module docstring).
TRANSPORT = "transport"
RUNTIME = "runtime"
OPERATION = "operation"

#: Sandbox image the current flow launches (see chatlink/docker/).
DOCKER_IMAGE = "ait-chatlink-agent"

# Timeouts for TUI consumers (t1149_2 panel / t1149_3 wizard). The daemon
# never passes a timeout (legacy wait-forever behavior preserved).
AGENT_PROBE_TIMEOUT_S = 30.0
DOCKER_PROBE_TIMEOUT_S = 5.0


@dataclass
class CheckResult:
    """One preflight check outcome. ``daemon_refuse_message`` is set only on
    ``fail`` results the daemon refuses on — it is the EXACT legacy
    ``_refuse()`` text (single definition; the TUI ``message`` can never
    drift from daemon behavior)."""

    id: str
    category: str
    severity: str
    message: str
    fix_hint: str = ""
    daemon_refuse_message: str | None = None


@dataclass
class CheapChecks:
    """Outcome of :func:`run_cheap_checks` — the structured results plus the
    already-loaded config and its raw warning lines, so the daemon can act
    on the config without re-loading and can replay the warnings to stderr
    byte-for-byte (contract: no lost lines, no duplicates)."""

    results: list[CheckResult] = field(default_factory=list)
    config: ChatlinkConfig | None = None
    config_warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------- #
# Agent-command resolution (moved from daemon.py in t1149_1; the daemon
# re-imports these names so its module namespace stays a monkeypatch seam)
# --------------------------------------------------------------------- #


def parse_dry_run_argv(output: str) -> tuple:
    """Extract the argv from an ``ait codeagent … --dry-run`` output.

    The engine prints ``DRY_RUN:`` followed by ``%q``-quoted words —
    ``shlex.split`` undoes that quoting. ``()`` when no line matches."""
    for line in output.splitlines():
        if line.startswith("DRY_RUN:"):
            return tuple(shlex.split(line[len("DRY_RUN:"):]))
    return ()


def resolve_explore_relay_argv(timeout: float | None = None) -> tuple:
    """Resolve the production agent argv (t1120_4 handoff): the full
    command shape comes from the engine-owned
    ``ait codeagent invoke explore-relay --headless --dry-run`` — never
    hand-assembled here. The dry-run's env preconditions (relay dir +
    bug-report file must exist) are satisfied with a throwaway scratch dir;
    the real per-session values travel via the launch env, not argv.
    ``()`` on any failure (the caller refuses / fails closed).

    ``timeout=None`` waits indefinitely — the daemon's legacy behavior.
    TUI consumers pass :data:`AGENT_PROBE_TIMEOUT_S`."""
    root = paths.project_root()
    try:
        with tempfile.TemporaryDirectory(prefix="chatlink-argv-") as td:
            report = Path(td) / "bug_report.md"
            report.write_text("dry-run resolution placeholder\n",
                              encoding="utf-8")
            env = dict(os.environ,
                       CHATLINK_RELAY_DIR=td,
                       CHATLINK_BUG_REPORT_FILE=str(report))
            proc = subprocess.run(
                [str(root / "ait"), "codeagent", "invoke", "explore-relay",
                 "--headless", "--dry-run"],
                capture_output=True, text=True, env=env, cwd=root,
                timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ()
    if proc.returncode != 0:
        return ()
    return parse_dry_run_argv(proc.stdout)


# --------------------------------------------------------------------- #
# Cheap checks (pure file/YAML/in-memory — TUI-poll safe)
# --------------------------------------------------------------------- #


def _config_key_id(warning: str) -> str:
    """``config_key:<key>`` id from a load_config warning line (best
    effort: the collected messages lead with the offending key)."""
    return "config_key:" + warning.split(":", 1)[0].strip()


def _check_token() -> CheckResult:
    if paths.read_token() is None:
        return CheckResult(
            id="token", category=TRANSPORT, severity=FAIL,
            message="bot token missing",
            fix_hint=(f"write the bot token to {paths.token_file()} "
                      "(0600) — the t1149_3 wizard token step does this"),
            daemon_refuse_message=(
                f"no bot token at {paths.token_file()} — write the bot "
                "token there (0600) before starting."),
        )
    return CheckResult(
        id="token", category=TRANSPORT, severity=PASS,
        message="bot token present")


def run_cheap_checks() -> CheapChecks:
    """Run the pure file/YAML/in-memory checks (no subprocess — safe on a
    TUI polling tick). Results are emitted in the daemon's legacy refusal
    order (config file → yaml → intake → [allowlist] → token); the daemon
    refuses on the first ``fail``. ``allowlist`` is warn-only (panel
    surface — deny-by-default is a valid, if useless, configuration)."""
    out = CheapChecks()
    cfg_path = paths.config_file()
    if cfg_path is None:
        out.results.append(CheckResult(
            id="config_file", category=TRANSPORT, severity=FAIL,
            message="gateway config file not found",
            fix_hint=(f"create {paths.CONFIG_DEFAULT_REL} (seeded by "
                      "'ait setup'), or point chatlink.config in "
                      "project_config.yaml at your file"),
            daemon_refuse_message=(
                "no gateway config found — create "
                f"{paths.CONFIG_DEFAULT_REL} (seeded by 'ait setup') "
                "first."),
        ))
        out.results.append(_check_token())
        return out
    out.results.append(CheckResult(
        id="config_file", category=TRANSPORT, severity=PASS,
        message=f"config file: {cfg_path}"))

    cfg, warnings = load_config_with_warnings(cfg_path)
    out.config = cfg
    out.config_warnings = warnings
    if cfg is None:
        out.results.append(CheckResult(
            id="config_yaml", category=TRANSPORT, severity=FAIL,
            message="config file is malformed (not valid YAML / not a "
                    "mapping)",
            fix_hint="fix the YAML — see the warnings for the exact reason",
            daemon_refuse_message=(
                f"gateway config {cfg_path} is missing or malformed — fix "
                "the YAML before starting."),
        ))
        out.results.append(_check_token())
        return out
    out.results.append(CheckResult(
        id="config_yaml", category=TRANSPORT, severity=PASS,
        message="config parses"))
    for msg in warnings:
        out.results.append(CheckResult(
            id=_config_key_id(msg), category=RUNTIME, severity=WARN,
            message=msg,
            fix_hint="value degraded to its default/clamped bound — edit "
                     "the config key"))

    if cfg.intake_channel is None:
        out.results.append(CheckResult(
            id="intake_channel", category=TRANSPORT, severity=FAIL,
            message="no valid intake_channel configured",
            fix_hint="set intake_channel provider/workspace_id/"
                     "conversation_id (all three, non-empty)",
            daemon_refuse_message=(
                "config has no valid intake_channel — the daemon refuses "
                "to watch without one."),
        ))
    else:
        ref = cfg.intake_channel
        out.results.append(CheckResult(
            id="intake_channel", category=TRANSPORT, severity=PASS,
            message=(f"intake channel: {ref['provider']} "
                     f"{ref['workspace_id']}/{ref['conversation_id']}")))

    if not cfg.allowed_user_ids and not cfg.allowed_role_ids:
        out.results.append(CheckResult(
            id="allowlist", category=TRANSPORT, severity=WARN,
            message="both allowlists empty — deny-by-default: nobody can "
                    "open a bug report",
            fix_hint="add reporter ids to allowed_user_ids or "
                     "allowed_role_ids"))
    else:
        count = len(cfg.allowed_user_ids) + len(cfg.allowed_role_ids)
        out.results.append(CheckResult(
            id="allowlist", category=TRANSPORT, severity=PASS,
            message=f"allowlist: {count} user/role id(s)"))

    out.results.append(_check_token())
    return out


# --------------------------------------------------------------------- #
# Expensive checks (spawn a process / hit the OS — never on a poll tick)
# --------------------------------------------------------------------- #


def check_explore_relay_agent_command(
    resolver=None, timeout: float | None = None,
) -> tuple[CheckResult, tuple]:
    """Operation check for the current explore-relay flow: can the agent
    command be resolved? Returns ``(result, argv)`` — the daemon needs the
    argv to launch sessions, so the computed value is returned rather than
    re-derived.

    ``resolver`` is a **zero-argument** callable returning the argv tuple
    (or ``()``); the daemon passes its module-global
    ``resolve_explore_relay_argv`` so the existing test monkeypatch seam
    keeps working. When ``None``, the preflight-local resolver is used with
    ``timeout``. Fails closed on any resolver exception."""
    if resolver is None:
        def resolver():
            return resolve_explore_relay_argv(timeout=timeout)
    try:
        argv = tuple(resolver())
    except Exception:
        argv = ()
    if not argv:
        return CheckResult(
            id="explore_relay_agent_command", category=OPERATION,
            severity=FAIL,
            message="explore-relay agent command cannot be resolved",
            fix_hint="run 'ait codeagent invoke explore-relay --headless "
                     "--dry-run' manually to diagnose the code-agent "
                     "config",
            daemon_refuse_message=(
                "could not resolve the explore-relay agent command — run "
                "'ait codeagent invoke explore-relay --headless --dry-run' "
                "manually to diagnose the code-agent config."),
        ), ()
    return CheckResult(
        id="explore_relay_agent_command", category=OPERATION, severity=PASS,
        message=f"agent command: {argv[0]} … ({len(argv)} words)"), argv


def check_docker_binary() -> CheckResult:
    """Runtime check: is the ``docker`` binary on PATH? Warn-only — the
    daemon serves without it (launches then fail honestly)."""
    if shutil.which("docker") is None:
        return CheckResult(
            id="docker_binary", category=RUNTIME, severity=WARN,
            message="'docker' not found — sandbox launches will fail",
            fix_hint="install Docker (see aidocs/chat/chatlink_sandbox.md)")
    return CheckResult(
        id="docker_binary", category=RUNTIME, severity=PASS,
        message="docker binary present")


def check_docker_image(timeout: float | None = None) -> CheckResult:
    """Runtime check: is the sandbox image built? Warn-only, and
    **panel/wizard-only — the daemon never calls this** (a missing image
    surfaces at session launch, exactly as before t1149_1)."""
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", DOCKER_IMAGE],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return CheckResult(
            id="docker_image", category=RUNTIME, severity=WARN,
            message=f"could not probe for image {DOCKER_IMAGE}",
            fix_hint="is Docker installed and responsive?")
    if proc.returncode != 0:
        return CheckResult(
            id="docker_image", category=RUNTIME, severity=WARN,
            message=f"sandbox image {DOCKER_IMAGE} not built",
            fix_hint=("docker build -t ait-chatlink-agent "
                      ".aitask-scripts/chatlink/docker/"))
    return CheckResult(
        id="docker_image", category=RUNTIME, severity=PASS,
        message=f"sandbox image {DOCKER_IMAGE} present")


def run_expensive_checks(
    agent_timeout: float | None = AGENT_PROBE_TIMEOUT_S,
    docker_timeout: float | None = DOCKER_PROBE_TIMEOUT_S,
    resolver=None,
) -> list[CheckResult]:
    """TUI convenience: run all expensive checks with the TUI timeouts.
    The daemon does NOT use this — it calls the per-check functions it
    legacy-consumes (agent + docker binary) with no timeout, and never the
    image check."""
    agent_result, _argv = check_explore_relay_agent_command(
        resolver=resolver, timeout=agent_timeout)
    return [
        agent_result,
        check_docker_binary(),
        check_docker_image(timeout=docker_timeout),
    ]
