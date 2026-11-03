#!/usr/bin/env python3
"""Run the shadow ``>q`` wording experiment through the real Claude Code and Codex CLIs.

Subcommands:

    harness.py plan                      # print the enumerated pilot cell list and totals
    harness.py manifest [--write]        # hash the private store's fixtures into fixtures/MANIFEST.json
    harness.py preflight [--batch B]     # model-free stub checks (direct + under `codex sandbox`)
    harness.py smoke [--batch B]         # one startup-only turn per agent (2 paid invocations)
    harness.py pilot [--batch B]         # the 12 pilot sessions, then judging (bounded by limits.json)
    harness.py classify --batch B        # re-classify saved raw streams offline (no CLI calls)

Design notes (full rationale in the t2179_1 plan):

* Sandboxes live under ``$AIT_SHADOW_Q_SANDBOX_ROOT`` (default
  ``/tmp/aitasks_shadow_q``), never inside a repository. Claude loads ancestor
  ``CLAUDE.md`` files, and a parent ``.claude/skills/`` would shadow the variant.
* Replay stubs write nothing and print no marker. Helper-call evidence comes
  from the CLI trace only (``validate.py``).
* Every private byte goes to the store (``store.PrivateSink``). Public JSONL
  goes through ``store.PublicSink``'s whitelist.
* The invocation cap is strict and checked before every launch. The cost and
  token thresholds stop new launches; in-flight turns finish.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import glob
import hashlib
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import validate as V  # noqa: E402
from qspan import find_q_span, substitute_q_bullet  # noqa: E402
from store import (  # noqa: E402
    REPO, PrivateSink, PublicSink, build_manifest_files, check_manifest, resolve_store, sha256_file,
)

FROZEN = HERE / "frozen"
VARIANTS_DIR = HERE / "variants"
RUNS_PUBLIC = HERE / "runs"
FAKE_PANE = "%9999"
SOURCE_TASK = "60_2"
VARIANTS = ("v1_baseline", "v2_concise_intent", "v3_explicit_semantics", "v4_prescriptive")
AUQ_SCENARIOS = ("file_selection", "runnable_examples", "go_versions")  # A, B, C
ALL_SCENARIOS = AUQ_SCENARIOS + ("working_wait",)
LATIN = {"ABC": AUQ_SCENARIOS, "BCA": AUQ_SCENARIOS[1:] + AUQ_SCENARIOS[:1],
         "CAB": AUQ_SCENARIOS[2:] + AUQ_SCENARIOS[:2]}
AGENT_DIRS = {
    "claude": {"skills": ".claude/skills", "stub": ".claude/skills/aitask-shadow/SKILL.md",
               "render": ".claude/skills/aitask-shadow-fast-"},
    "codex": {"skills": ".agents/skills", "stub": ".agents/skills/aitask-shadow/SKILL.md",
              "render": ".agents/skills/aitask-shadow-fast-codex-"},
}
STRIP_ENV_PREFIXES = ("CLAUDE", "TMUX", "HERDR_", "CODEX_THREAD", "CODEX_SANDBOX")
STRIP_ENV_EXACT = {"ANTHROPIC_REASONING_EFFORT", "AITASK_AGENT_STRING", "CLAUDECODE"}


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_limits() -> dict:
    return json.loads((HERE / "limits.json").read_text())


def load_freeze() -> dict:
    return json.loads((FROZEN / "FREEZE.json").read_text())


# --------------------------------------------------------------------------
# Variants and minimal-context renders
# --------------------------------------------------------------------------

def variant_bullet(variant: str) -> str:
    return (VARIANTS_DIR / f"{variant}.md").read_text(encoding="utf-8").rstrip("\n")


def build_variant(agent: str, variant: str) -> str:
    base = (FROZEN / agent / "render" / "SKILL.md").read_text(encoding="utf-8")
    if variant == "v1_baseline":
        out = substitute_q_bullet(base, variant_bullet(variant))
        if out != base:
            raise RuntimeError("v1 substitution changed the frozen render")
        return out
    return substitute_q_bullet(base, variant_bullet(variant))


def _section(text: str, heading_prefix: str) -> str:
    lines = text.split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.startswith(heading_prefix))
    end = next((j for j in range(start + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def build_minimal(agent: str, variant: str) -> str:
    full = build_variant(agent, variant)
    lines = full.split("\n")
    pre_end = next(i for i, ln in enumerate(lines) if ln.startswith("## Step 0"))
    preamble = "\n".join(lines[:pre_end]).rstrip("\n")
    step1 = _section(full, "## Step 1")
    s, e = find_q_span(full)
    bullet = "\n".join(lines[s:e])
    step3_head = next(ln for ln in lines if ln.startswith("## Step 3"))
    guard = _section(full, "## Guardrail")
    return "\n\n".join([preamble, step1, step3_head, bullet, guard]) + "\n"


# --------------------------------------------------------------------------
# Replay stubs
# --------------------------------------------------------------------------

def _real_header(script: str, max_lines: int = 40) -> str:
    """The real helper's leading comment block, so a `cat` of the stub reads like the helper."""
    p = REPO / ".aitask-scripts" / script
    if not p.exists():
        return ""
    out = []
    for i, ln in enumerate(p.read_text(encoding="utf-8").split("\n")):
        if i == 0:
            continue
        if not ln.startswith("#"):
            break
        out.append(ln)
        if len(out) >= max_lines:
            break
    return "\n".join(out)


STUB_PRELUDE = """#!/usr/bin/env bash
{header}
set -euo pipefail
_here="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
_r="$_here/.replay"
_k="$(cat "$_r/current")"
"""

STUBS = {
    "aitask_shadow_capture.sh": """
_phase=0; _stdin=0
while [ $# -gt 0 ]; do
  case "$1" in
    --phase) _phase=1; shift; [ $# -gt 0 ] && shift; break ;;
    --deep|--any-pane) shift ;;
    -) _stdin=1; shift ;;
    -h|--help) sed -n '2,37p' "$0" | sed 's/^# \\{0,1\\}//'; exit 0 ;;
    -*) echo "aitask_shadow_capture.sh: unknown option: $1" >&2; exit 2 ;;
    *) shift ;;
  esac
done
if [ "$_phase" = 1 ]; then cat "$_r/phase_$_k.txt"; exit 0; fi
if [ "$_stdin" = 1 ]; then LC_ALL=C sed -e 's#\\x1b\\[[0-9;?]*[ -/]*[@-~]##g'; exit 0; fi
cat "$_r/screen_$_k.txt"
""",
    "aitask_shadow_context.sh": """
cat "$_r/context_$_k.txt"
""",
    "aitask_skill_resolve_profile.sh": """
echo fast
""",
    "aitask_skill_render.sh": """
exit 0
""",
    "aitask_explain_context.sh": """
exit 0
""",
}


def stub_text(name: str) -> str:
    return STUB_PRELUDE.format(header=_real_header(name)) + STUBS[name].lstrip("\n")


# --------------------------------------------------------------------------
# Sandbox
# --------------------------------------------------------------------------

@dataclasses.dataclass
class Sandbox:
    root: Path
    agent: str
    variant: str
    condition: str
    scenarios: list[str]  # scenario served at screen position k (1-based index k-1)
    dispatched: Path
    dispatched_sha: str
    span: tuple[int, int]
    nlines: int

    def set_position(self, k: int) -> None:
        (self.root / ".aitask-scripts" / ".replay" / "current").write_text(f"{k}\n")

    def expected_for(self, k: int) -> dict[tuple[str, str], str]:
        r = self.root / ".aitask-scripts" / ".replay"
        screen = (r / f"screen_{k}.txt").read_text(encoding="utf-8")
        return {
            ("aitask_shadow_capture.sh", "noarg"): screen,
            ("aitask_shadow_capture.sh", "deep"): screen,
            ("aitask_shadow_capture.sh", "explicit_id"): screen,
            ("aitask_shadow_capture.sh", "any_pane"): screen,
            ("aitask_shadow_capture.sh", "phase"): (r / f"phase_{k}.txt").read_text(encoding="utf-8"),
            ("aitask_shadow_context.sh", "default"): (r / f"context_{k}.txt").read_text(encoding="utf-8"),
            ("aitask_skill_resolve_profile.sh", "default"): "fast\n",
            ("aitask_skill_render.sh", "default"): "",
            ("aitask_explain_context.sh", "default"): "",
        }


class SandboxError(RuntimeError):
    pass


TASK_DIR_ALIASES = {"_aitasks": "aitasks", "_aiplans": "aiplans"}
FORBIDDEN_ANCESTOR_ENTRIES = ("CLAUDE.md", "AGENTS.md", ".claude", ".agents", ".codex")


def check_ancestors(path: Path) -> list[str]:
    """Refuse an ancestor that carries agent instructions; return the empty ones found (flag only).

    An ancestor ``CLAUDE.md`` / ``AGENTS.md`` file, or a ``.claude`` / ``.agents`` / ``.codex``
    directory holding any file, would leak into the subject's instruction stack. An *empty*
    directory carries nothing: the Codex CLI was observed creating empty ``/tmp/.agents`` and
    ``/tmp/.codex`` mid-pilot, which refused every later sandbox.
    """
    p = Path(path).resolve()
    empty: list[str] = []
    for anc in p.parents:
        for name in FORBIDDEN_ANCESTOR_ENTRIES:
            e = anc / name
            if not e.exists() and not e.is_symlink():
                continue
            if e.is_dir() and not e.is_symlink() and not any(x.is_file() or x.is_symlink() for x in e.rglob("*")):
                empty.append(str(e))
                continue
            raise SandboxError(f"sandbox ancestor {anc} contains {name}")
    return empty


def sandbox_root() -> Path:
    return Path(os.environ.get("AIT_SHADOW_Q_SANDBOX_ROOT", "/tmp/aitasks_shadow_q"))


def _copytree_files(src: Path, dst: Path) -> None:
    for p in sorted(src.rglob("*")):
        if p.is_file():
            target = dst / p.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)


def build_sandbox(root: Path, agent: str, variant: str, condition: str, scenarios: list[str],
                  store: Path) -> Sandbox:
    root = Path(root)
    check_ancestors(root)
    if root.exists() and any(root.iterdir()):
        raise SandboxError(f"sandbox {root} is not empty")
    root.mkdir(parents=True, exist_ok=True)
    minimal = condition == "minimal"
    dirs = AGENT_DIRS[agent]
    fx = store / "fixtures"
    if not minimal:
        # CLAUDE.md, AGENTS.md and the docs they point at, at their repository paths.
        _copytree_files(store / "instructions", root)
        listing = store / "skill_listing" / agent
        if listing.is_dir():
            _copytree_files(listing, root / dirs["skills"])
    # The agent's own frozen stub and render tree, at the stub's dispatch path.
    stub_dst = root / dirs["stub"]
    stub_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FROZEN / agent / "stub" / "SKILL.md", stub_dst)
    render_dst = root / dirs["render"]
    _copytree_files(FROZEN / agent / "render", render_dst)
    text = build_minimal(agent, variant) if minimal else build_variant(agent, variant)
    (render_dst / "SKILL.md").write_text(text, encoding="utf-8")
    # Task (and plan) files: identical across the AUQ scenarios of one session.
    task_dirs = {fx / sc / "task" for sc in scenarios}
    digests = {json.dumps(build_tree_digest(d)) for d in task_dirs}
    if len(digests) != 1:
        raise SandboxError("scenarios in one session carry different task files")
    # Stored as `_aitasks/` / `_aiplans/` (aitasks_go ignores those path components); served under their real names.
    for f in sorted(next(iter(task_dirs)).rglob("*")):
        if f.is_file():
            rel = Path(*[TASK_DIR_ALIASES.get(part, part) for part in f.relative_to(next(iter(task_dirs))).parts])
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, root / rel)
    # Replay data + stubs.
    scripts = root / ".aitask-scripts"
    replay = scripts / ".replay"
    replay.mkdir(parents=True)
    for k, sc in enumerate(scenarios, start=1):
        shutil.copy2(fx / sc / "screen_1.txt", replay / f"screen_{k}.txt")
        shutil.copy2(fx / sc / "phase.txt", replay / f"phase_{k}.txt")
        shutil.copy2(fx / sc / "context.txt", replay / f"context_{k}.txt")
    (replay / "current").write_text("1\n")
    for name in STUBS:
        p = scripts / name
        p.write_text(stub_text(name), encoding="utf-8")
        p.chmod(0o755)
    for leak in root.rglob("*"):
        if leak.name in ("reference.md", "shallow.md", "adequate.md") or "controls" in leak.parts:
            raise SandboxError(f"scorer-only file leaked into the sandbox: {leak}")
    # A real-looking repository: everything committed, the replay dir excluded.
    env = {**os.environ, "GIT_AUTHOR_NAME": "dev", "GIT_AUTHOR_EMAIL": "dev@example.invalid",
           "GIT_COMMITTER_NAME": "dev", "GIT_COMMITTER_EMAIL": "dev@example.invalid"}
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, env=env)
    (root / ".git" / "info").mkdir(parents=True, exist_ok=True)
    (root / ".git" / "info" / "exclude").write_text(".aitask-scripts/.replay/\n")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "snapshot"], check=True, env=env)
    dispatched = render_dst / "SKILL.md"
    dtext = dispatched.read_text(encoding="utf-8")
    s, e = find_q_span(dtext)
    return Sandbox(root=root, agent=agent, variant=variant, condition=condition, scenarios=list(scenarios),
                   dispatched=dispatched, dispatched_sha=sha256_file(dispatched),
                   span=(s + 1, e), nlines=len(dtext.split("\n")))


def q_lines_of(skill_text: str) -> list[str]:
    """The `>q` bullet's non-blank lines, stripped: what a read must be seen to return."""
    s, e = find_q_span(skill_text)
    return [ln.strip() for ln in skill_text.split("\n")[s:e] if ln.strip()]


def build_tree_digest(d: Path) -> dict[str, str]:
    return {str(p.relative_to(d)): sha256_file(p) for p in sorted(d.rglob("*")) if p.is_file()}


def replay_helpers_for_allowlist() -> list[str]:
    """Helpers the stubs, Steps 0-2 and the `>q` bullet invoke, grepped from the frozen renders."""
    found: set[str] = set()
    rx = re.compile(r"\.aitask-scripts/(aitask_[A-Za-z0-9_]+\.sh)")
    for agent in AGENT_DIRS:
        stub = (FROZEN / agent / "stub" / "SKILL.md").read_text(encoding="utf-8")
        found.update(rx.findall(stub))
        skill = (FROZEN / agent / "render" / "SKILL.md").read_text(encoding="utf-8")
        lines = skill.split("\n")
        s3 = next(i for i, ln in enumerate(lines) if ln.startswith("## Step 3"))
        found.update(rx.findall("\n".join(lines[:s3])))
        qs, qe = find_q_span(skill)
        found.update(rx.findall("\n".join(lines[qs:qe])))
    return sorted(found)


# --------------------------------------------------------------------------
# Environment, agents, CLI argv
# --------------------------------------------------------------------------

def subject_env(sbx_root: Path | None = None) -> tuple[dict, list[str]]:
    env = dict(os.environ)
    stripped = []
    for k in list(env):
        if k in STRIP_ENV_EXACT or k.startswith(STRIP_ENV_PREFIXES):
            stripped.append(k)
            env.pop(k)
    empty = sandbox_root() / "empty_tmux"
    empty.mkdir(parents=True, exist_ok=True)
    env["TMUX_TMPDIR"] = str(empty)
    return env, sorted(stripped)


def resolve_agents() -> dict:
    out = {}
    r = subprocess.run(["./.aitask-scripts/aitask_codeagent.sh", "resolve", "shadow"], cwd=REPO,
                       capture_output=True, text=True, check=True).stdout
    kv = dict(ln.split(":", 1) for ln in r.splitlines() if ":" in ln)
    out["codex"] = {"agent_string": kv["AGENT_STRING"], "cli_id": kv["CLI_ID"], "source": "codeagent resolve shadow"}
    d = subprocess.run(["bash", "-c", 'unset DEFAULT_AGENT_STRING; source .aitask-scripts/lib/agent_string.sh && '
                        'printf %s "$DEFAULT_AGENT_STRING"'], cwd=REPO, capture_output=True, text=True,
                       check=True).stdout.strip()
    r2 = subprocess.run(["./.aitask-scripts/aitask_codeagent.sh", "--agent-string", d, "resolve", "shadow"],
                        cwd=REPO, capture_output=True, text=True, check=True).stdout
    kv2 = dict(ln.split(":", 1) for ln in r2.splitlines() if ":" in ln)
    out["claude"] = {"agent_string": kv2["AGENT_STRING"], "cli_id": kv2["CLI_ID"],
                     "source": "lib/agent_string.sh DEFAULT_AGENT_STRING"}
    for agent, a in out.items():
        line = subprocess.run(["./.aitask-scripts/aitask_codeagent.sh", "--agent-string", a["agent_string"],
                               "--dry-run", "invoke", "shadow", FAKE_PANE, SOURCE_TASK], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
        a["dry_run_line"] = line
    return out


def environment_record() -> dict:
    rec: dict = {}
    for name, cmd in (("claude", ["claude", "--version"]), ("codex", ["codex", "--version"])):
        try:
            rec[f"{name}_version"] = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            rec[f"{name}_version"] = ""
    reasoning: dict = {}
    try:
        import tomllib
        cfg = tomllib.loads(Path("~/.codex/config.toml").expanduser().read_text())
        reasoning["codex_model_reasoning_effort"] = cfg.get("model_reasoning_effort")
        reasoning["codex_plan_mode_reasoning_effort"] = cfg.get("plan_mode_reasoning_effort")
        reasoning["codex_personality"] = cfg.get("personality")
    except (OSError, ValueError):
        pass
    sp = Path("~/.claude/settings.json").expanduser()
    if sp.exists():
        s = json.loads(sp.read_text())
        reasoning["claude_effortLevel"] = s.get("effortLevel")
        reasoning["claude_env_ANTHROPIC_REASONING_EFFORT"] = (s.get("env") or {}).get("ANTHROPIC_REASONING_EFFORT")
        reasoning["claude_settings_sha256"] = sha256_file(sp)
        ms = (s.get("modelSettings") or {})
        rec["claude_modelSettings"] = {k: (v or {}).get("effortLevel") for k, v in ms.items()}
    rec["reasoning"] = reasoning
    try:
        feats = subprocess.run(["codex", "features", "list"], capture_output=True, text=True, timeout=30).stdout
        m = re.search(r"^memories\s+\S+(?:\s+\S+)*?\s+(true|false)\s*$", feats, re.M)
        rec["codex_memories"] = m.group(1) if m else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        rec["codex_memories"] = "unknown"
    return rec


# Read-only utilities a subject naturally chains with a helper (`helper; echo "EXIT:$?"`, `| head`).
# dontAsk mode checks every subcommand of a compound command, so without these a natural
# helper call is denied (seen in the pilot startup smoke). None of them can write.
READONLY_BASH = ("echo", "printf", "true", "cat", "head", "tail", "wc", "ls", "nl", "sed -n", "grep")


def claude_allowed_tools(sbx: Path) -> list[str]:
    tools = ["Read", "Glob", "Grep", "Skill"] + [f"Bash({u}:*)" for u in READONLY_BASH]
    for h in replay_helpers_for_allowlist():
        tools.append(f"Bash(./.aitask-scripts/{h}:*)")
        tools.append(f"Bash({sbx}/.aitask-scripts/{h}:*)")
    return tools


def subject_argv(agent: str, cli_id: str, turn: int, prompt: str, sbx: Path, session_id: str,
                 limits: dict, trust_override: bool) -> list[str]:
    if agent == "claude":
        argv = ["claude", "-p", prompt, "--model", cli_id, "--output-format", "stream-json", "--verbose",
                "--permission-mode", "dontAsk", "--permission-prompts", "none",
                "--max-budget-usd", str(limits["claude_max_budget_usd_subject_turn"])]
        if turn > 1:
            argv += ["--resume", session_id]
        argv += ["--allowedTools", *claude_allowed_tools(sbx)]
        return argv
    trust = ["-c", f'projects."{sbx}".trust_level="trusted"'] if trust_override else []
    if turn == 1:
        return ["codex", "exec", "--json", "-m", cli_id, "-s", "read-only", "-C", str(sbx), *trust, prompt]
    return ["codex", "exec", "resume", "--json", "-m", cli_id, "-c", 'sandbox_mode="read-only"', *trust,
            session_id, prompt]


# --------------------------------------------------------------------------
# Runner: one CLI invocation with limits
# --------------------------------------------------------------------------

@dataclasses.dataclass
class RunResult:
    exit_code: int | None
    killed: str
    stdout_path: Path
    stderr_path: Path
    latency_s: float
    tool_calls: int


CODEX_TOOL_ITEMS = ("command_execution", "web_search", "mcp_tool_call", "file_change")


def _count_tool_start(agent: str, line: str, seen: set | None = None) -> int:
    """New tool invocations announced by one stream line, each counted once by its id.

    Claude: every ``tool_use`` block. Codex: every tool item (``command_execution``,
    ``web_search``, ``mcp_tool_call``, ``file_change``), from ``item.started`` or, when an
    item only ever completes, ``item.completed``.
    """
    seen = seen if seen is not None else set()
    if '"tool_use"' not in line and '"item.' not in line:
        return 0
    try:
        obj = json.loads(line)
    except ValueError:
        return 0
    n = 0
    if agent == "claude" and obj.get("type") == "assistant":
        for c in (obj.get("message") or {}).get("content", []) or []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                key = ("claude", c.get("id") or f"anon{len(seen)}")
                if key not in seen:
                    seen.add(key)
                    n += 1
    if agent == "codex" and obj.get("type") in ("item.started", "item.completed"):
        item = obj.get("item") or {}
        if item.get("type") in CODEX_TOOL_ITEMS:
            key = ("codex", item.get("id") or f"anon{len(seen)}")
            if key not in seen:
                seen.add(key)
                n += 1
    return n


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def kill_group(proc: subprocess.Popen, grace: float) -> None:
    """SIGTERM the whole process group, SIGKILL after ``grace``; every wait is bounded."""
    pgid = proc.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    end = time.monotonic() + grace
    while time.monotonic() < end and (proc.poll() is None or _group_alive(pgid)):
        time.sleep(0.05)
    if proc.poll() is None or _group_alive(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass


def run_cli(argv: list[str], cwd: Path, env: dict, agent: str, timeout_s: float, max_tool_calls: int | None,
            stdout_path: Path, stderr_path: Path, grace_s: float = 10.0, stdin_text: str | None = None) -> RunResult:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    killed = ""
    tool_calls = 0
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE if stdin_text is not None
                                else subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err,
                                text=True, start_new_session=True, bufsize=1)
        if stdin_text is not None:
            def _feed():
                try:
                    proc.stdin.write(stdin_text)
                    proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
            threading.Thread(target=_feed, daemon=True).start()
        lines: list[str] = []
        done = threading.Event()

        def _reader():
            try:
                for line in proc.stdout:
                    lines.append(line)
            except (ValueError, OSError):
                pass
            done.set()

        threading.Thread(target=_reader, daemon=True).start()
        seen = 0
        tool_ids: set = set()
        hard_end = None  # set once a kill was sent: the loop never outlives kill + grace
        while True:
            if done.is_set():
                # stdout is at EOF: wait on the process itself (bounded), never spin.
                try:
                    proc.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
            else:
                done.wait(0.2)
            while seen < len(lines):
                line = lines[seen]
                out.write(line)
                out.flush()
                tool_calls += _count_tool_start(agent, line, tool_ids)
                seen += 1
            if max_tool_calls is not None and tool_calls > max_tool_calls and not killed:
                killed = "limit_tool_calls"
                kill_group(proc, grace_s)
                hard_end = time.monotonic() + grace_s
            # The deadline covers the process's whole lifetime, not just its stdout:
            # a child that closes stdout and keeps running is still timed out.
            if not killed and time.monotonic() - t0 > timeout_s:
                killed = "limit_timeout"
                kill_group(proc, grace_s)
                hard_end = time.monotonic() + grace_s
            if done.is_set() and seen >= len(lines) and proc.poll() is not None:
                break
            if hard_end is not None and time.monotonic() > hard_end:
                break
        if proc.poll() is None:
            kill_group(proc, grace_s)
        if _group_alive(proc.pid):  # leftovers in the group after the leader exited
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        while seen < len(lines):
            out.write(lines[seen])
            seen += 1
        out.flush()
        try:
            proc.stdout.close()
        except OSError:
            pass
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except OSError:
                pass
    return RunResult(proc.returncode, killed, stdout_path, stderr_path, time.monotonic() - t0, tool_calls)


# --------------------------------------------------------------------------
# Budget
# --------------------------------------------------------------------------

class Budget:
    """Strict invocation ceiling + stop-launch cost/token thresholds (thread-safe, durable).

    With a ``journal`` (a public, fsynced JSONL) the journal is authoritative:

    * the first record is a ``baseline``. For a batch that predates the journal, it holds
      the historical totals (max over ``invocations.jsonl`` and the snapshot); for a new
      batch it is all zeros;
    * every successful :meth:`acquire` writes ``reserve`` with the next global ``seq``
      (continuing after the baseline) **before** the launch;
    * every :meth:`add_usage` writes ``usage`` carrying the **same** ``seq`` (per thread).

    :meth:`recover` replays it: used = max(baseline, highest seq). Spend = baseline + matched
    usage + the conservative bound for every reservation without usage. Historical calls and
    new pending reservations are therefore counted together, and nothing completed is counted
    twice.

    **Any** threshold stops **every** new launch, of either agent (subject or judge).
    """

    def __init__(self, cap: int, claude_cost_usd: float, codex_tokens: int, reserve: int = 0,
                 journal: Path | None = None, batch: str = "", unreported_claude_usd: float = 2.0,
                 unreported_codex_tokens: int = 200_000):
        self.cap = cap
        self.claude_cost_threshold = claude_cost_usd
        self.codex_token_threshold = codex_tokens
        self.reserve = reserve
        self.used = 0
        self.claude_cost = 0.0
        self.codex_tokens = 0
        self.lock = threading.Lock()
        self.stop_reason = ""
        self.batch = batch
        self.unreported_claude_usd = unreported_claude_usd
        self.unreported_codex_tokens = unreported_codex_tokens
        self.journal_path = Path(journal) if journal is not None else None
        self.sink = PublicSink(journal, "budget") if journal is not None else None
        self._local = threading.local()

    def _journal(self, rec: dict) -> None:
        if self.sink is not None:
            self.sink.append({"batch": self.batch, "at": now(), **rec})

    def _threshold_reason(self) -> str:
        if self.claude_cost >= self.claude_cost_threshold:
            return "claude_cost"
        if self.codex_tokens >= self.codex_token_threshold:
            return "codex_tokens"
        return ""

    def acquire(self, purpose: str, agent: str | None) -> str:
        """Return "" to launch, else the not-run reason. Reserve is held for controls."""
        with self.lock:
            limit = self.cap - (self.reserve if purpose in ("subject", "smoke", "answer_judge") else 0)
            if purpose == "control_judge":
                limit = self.cap
            if self.used >= limit:
                return "invocation_cap"
            reason = self._threshold_reason()
            if reason:
                return reason
            self.used += 1
            self._local.seq = self.used
            self._journal({"event": "reserve", "seq": self.used, "purpose": purpose, "agent": agent})
            return ""

    def release_reserve(self) -> None:
        with self.lock:
            self.reserve = 0

    def add_usage(self, agent: str, cost_usd: float | None, tokens: int | None) -> None:
        """Record the finished call this thread reserved. Unreported usage is charged at the bound."""
        with self.lock:
            estimated = False
            if agent == "claude":
                if cost_usd is None:
                    cost_usd, estimated = self.unreported_claude_usd, True
                self.claude_cost += float(cost_usd)
            if agent == "codex":
                if tokens is None:
                    tokens, estimated = self.unreported_codex_tokens, True
                self.codex_tokens += int(tokens)
            seq = getattr(self._local, "seq", None)
            self._local.seq = None
            self._journal({"event": "usage", "seq": seq, "agent": agent,
                           "cost_usd": cost_usd if agent == "claude" else None,
                           "tokens": tokens if agent == "codex" else None, "estimated": estimated})

    @staticmethod
    def historical(invocations: Path | None, state: Path | None) -> dict:
        res = {"used": 0, "claude": 0.0, "codex": 0}
        if invocations is not None and invocations.exists():
            rows = [json.loads(x) for x in invocations.read_text().splitlines()]
            u = lambda r: r.get("usage") or {}  # noqa: E731
            res = {"used": len(rows),
                   "claude": sum(float(u(r).get("cost_usd") or 0) for r in rows if r.get("agent") == "claude"),
                   "codex": sum(int(u(r).get("input_tokens", 0)) - int(u(r).get("cached_input_tokens", 0))
                                + int(u(r).get("output_tokens", 0)) for r in rows if r.get("agent") == "codex")}
        if state is not None and state.exists():
            st = json.loads(state.read_text())
            res["used"] = max(res["used"], int(st.get("invocations", 0)))
            res["claude"] = max(res["claude"], float(st.get("claude_cost_usd", 0)))
            res["codex"] = max(res["codex"], int(st.get("codex_tokens", 0)))
        return res

    def recover(self, journal: Path | None, invocations: Path | None = None, state: Path | None = None) -> dict:
        """Load the journal (writing its migration baseline first if it does not exist yet)."""
        hist = self.historical(invocations, state)
        if journal is None:
            res = hist
        else:
            journal = Path(journal)
            if not journal.exists() or not journal.read_text().strip():
                self._journal({"event": "baseline", "seq": hist["used"], "cost_usd": round(hist["claude"], 6),
                               "tokens": hist["codex"]})
            base = {"used": 0, "claude": 0.0, "codex": 0}
            reserves: dict[int, str] = {}
            usage: dict[int, tuple] = {}
            orphan_cost, orphan_tok = 0.0, 0
            for line in journal.read_text().splitlines():
                r = json.loads(line)
                ev = r.get("event")
                if ev == "baseline":
                    base = {"used": int(r.get("seq") or 0), "claude": float(r.get("cost_usd") or 0),
                            "codex": int(r.get("tokens") or 0)}
                elif ev == "reserve":
                    reserves[int(r["seq"])] = r.get("agent")
                elif ev == "usage":
                    if r.get("seq") is None:
                        orphan_cost += float(r.get("cost_usd") or 0)
                        orphan_tok += int(r.get("tokens") or 0)
                    else:
                        usage[int(r["seq"])] = (float(r.get("cost_usd") or 0), int(r.get("tokens") or 0))
            cost, toks = base["claude"] + orphan_cost, base["codex"] + orphan_tok
            for seq, agent in reserves.items():
                if seq in usage:
                    cost += usage[seq][0]
                    toks += usage[seq][1]
                elif agent == "claude":
                    cost += self.unreported_claude_usd
                elif agent == "codex":
                    toks += self.unreported_codex_tokens
            res = {"used": max([base["used"], *reserves.keys()]) if reserves else base["used"],
                   "claude": cost, "codex": toks}
            # The journal includes the baseline, so a max with the historical sources is safe.
            res = {k: max(res[k], hist[k]) for k in res}
        with self.lock:
            self.used = max(self.used, res["used"])
            self.claude_cost = max(self.claude_cost, res["claude"])
            self.codex_tokens = max(self.codex_tokens, res["codex"])
        return res

    def snapshot(self) -> dict:
        with self.lock:
            return {"invocations": self.used, "cap": self.cap, "claude_cost_usd": round(self.claude_cost, 4),
                    "claude_cost_threshold_usd": self.claude_cost_threshold, "codex_tokens": self.codex_tokens,
                    "codex_token_threshold": self.codex_token_threshold}


# --------------------------------------------------------------------------
# Usage / model extraction
# --------------------------------------------------------------------------

def turn_usage(agent: str, events: list[V.Event]) -> dict:
    u: dict = {}
    for e in events:
        if e.kind != "final":
            continue
        if agent == "claude":
            us = e.meta.get("usage") or {}
            for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                if isinstance(us.get(k), (int, float)):
                    u[k] = us[k]
            if e.meta.get("cost_usd") is not None:
                u["cost_usd"] = e.meta["cost_usd"]
        else:
            us = e.meta.get("usage") or {}
            for k in ("input_tokens", "cached_input_tokens", "output_tokens"):
                if isinstance(us.get(k), (int, float)):
                    u[k] = u.get(k, 0) + us[k]
    return u


def codex_noncached_tokens(u: dict) -> int:
    return int(u.get("input_tokens", 0)) - int(u.get("cached_input_tokens", 0)) + int(u.get("output_tokens", 0))


def claude_model(events: list[V.Event]) -> tuple[str, str]:
    for e in events:
        if e.kind == "meta" and e.meta.get("model"):
            return e.meta["model"], "claude_stream_init"
    return "", ""


def codex_rollout_facts(thread_id: str, sessions_dir: Path | None = None) -> dict:
    """Model / effort / cli_version from the CLI-written rollout. Copies nothing."""
    base = sessions_dir or Path(os.environ.get("AIT_SHADOW_Q_CODEX_SESSIONS", "~/.codex/sessions")).expanduser()
    hits = glob.glob(str(base / "*" / "*" / "*" / f"rollout-*-{thread_id}.jsonl"))
    facts: dict = {}
    if not hits:
        return facts
    with open(sorted(hits)[0], encoding="utf-8") as fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            p = obj.get("payload") or {}
            if obj.get("type") == "session_meta" and "cli_version" not in facts:
                facts["cli_version"] = p.get("cli_version", "")
            if obj.get("type") == "turn_context" and "model" not in facts:
                facts["model"] = p.get("model", "")
                facts["effort"] = p.get("effort", "")
            if "model" in facts and "cli_version" in facts:
                break
    return facts


# --------------------------------------------------------------------------
# Session execution
# --------------------------------------------------------------------------

@dataclasses.dataclass
class Cell:
    condition: str  # smoke | fresh | repeated | minimal
    agent: str
    variant: str
    scenarios: list[str]
    rep: int = 1
    order: str = ""

    @property
    def cell_id(self) -> str:
        sc = self.order or self.scenarios[0]
        return f"{self.condition}-{self.agent}-{self.variant}-{sc}-r{self.rep}"

    @property
    def n_turns(self) -> int:
        if self.condition == "smoke":
            return 1
        return 1 + len(self.scenarios)

    def public_cell(self) -> dict:
        return {"scenario": self.scenarios[0] if self.condition != "repeated" else "",
                "variant": self.variant, "agent": self.agent, "condition": self.condition,
                "rep": self.rep, "order": self.order}


class Experiment:
    def __init__(self, batch: str, store: Path, limits: dict, budget: Budget, agents: dict | None = None,
                 env_record: dict | None = None, store_commit: str = "", seed: int = 2179):
        self.batch = batch
        self.store = store
        self.private = PrivateSink(store)
        self.limits = limits
        self.budget = budget
        self.agents = agents if agents is not None else resolve_agents()
        self.env_record = env_record if env_record is not None else environment_record()
        self.store_commit = store_commit
        self.seed = seed
        pub = RUNS_PUBLIC / batch
        self.sessions_sink = PublicSink(pub / "sessions.jsonl", "session")
        self.trials_sink = PublicSink(pub / "trials.jsonl", "trial")
        self.inv_sink = PublicSink(pub / "invocations.jsonl", "invocation")
        self.score_sink = PublicSink(pub / "scores.jsonl", "score")
        self.control_scenarios = list(AUQ_SCENARIOS)
        self.inv_seq = 0
        self.lock = threading.Lock()
        self.trust_override = False
        self.circuit: dict[str, int] = {"claude": 0, "codex": 0}
        self.circuit_open: set[str] = set()
        self.answers: list[dict] = []  # valid answers for judging (private text stays in the store)

    # -- hooks used by judge.py --------------------------------------------
    run_cli = staticmethod(run_cli)

    def scratch_dir(self, name: str) -> Path:
        d = sandbox_root() / self.batch / "judge_scratch" / name
        d.mkdir(parents=True, exist_ok=True)
        check_ancestors(d)
        return d

    def env_for_judge(self) -> tuple[dict, list[str]]:
        return subject_env()

    def record_invocation(self, purpose: str, agent: str, run_id: str, turn: int, outcome: str,
                          latency: float, usage: dict) -> None:
        self._record_inv(purpose, agent, run_id, turn, outcome, latency, usage)

    # -- one session -------------------------------------------------------
    def run_session(self, cell: Cell, order_index: int) -> dict:
        if cell.agent in self.circuit_open:
            return self._not_run(cell, "circuit_open", order_index)
        attempt = 1
        while True:
            res = self._attempt(cell, order_index, attempt)
            if res.get("retry") and attempt <= self.limits["max_retries_per_session"]:
                attempt += 1
                continue
            return res

    def _record_inv(self, purpose: str, agent: str, run_id: str, turn: int, outcome: str, latency: float,
                    usage: dict) -> None:
        with self.lock:
            self.inv_seq += 1
            seq = self.inv_seq
        self.inv_sink.append({"batch": self.batch, "seq": seq, "purpose": purpose, "agent": agent,
                              "run_id": run_id, "turn_index": turn, "outcome": outcome,
                              "latency_s": round(latency, 2), "usage": usage, "started_at": now()})

    def _not_run(self, cell: Cell, reason: str, order_index: int) -> dict:
        run_id = f"{cell.cell_id}-notrun"
        q_turns = list(range(2, cell.n_turns + 1)) if cell.condition != "smoke" else []
        for pos, t in enumerate(q_turns, start=1):
            self.trials_sink.append({"batch": self.batch, "run_id": run_id, "trial_id": f"{run_id}-t{t}",
                                     "cell": cell.public_cell(), "turn_index": t, "position": pos,
                                     "scenario": cell.scenarios[pos - 1], "variant": cell.variant,
                                     "agent": cell.agent, "condition": cell.condition,
                                     "outcome": f"not_run:{reason}", "judged": False})
        self.sessions_sink.append({"batch": self.batch, "run_id": run_id, "cell": cell.public_cell(),
                                   "order_index": order_index, "agent": cell.agent, "status": "not_run",
                                   "outcome": f"not_run:{reason}", "attempt": 0, "store_commit": self.store_commit})
        return {"outcome": f"not_run:{reason}", "trials": []}

    def _attempt(self, cell: Cell, order_index: int, attempt: int) -> dict:
        agent = cell.agent
        a = self.agents[agent]
        stamp = _dt.datetime.now().strftime("%H%M%S")
        run_id = f"{cell.cell_id}-a{attempt}-{stamp}-{random.Random(self.seed + order_index * 7 + attempt).randrange(16**4):04x}"
        sbx_path = sandbox_root() / self.batch / run_id / "sandbox"
        priv_dir = Path("runs") / self.batch / run_id
        started = now()
        t0 = time.monotonic()
        try:
            sbx = build_sandbox(sbx_path, agent, cell.variant, cell.condition, cell.scenarios, self.store)
        except (SandboxError, OSError, subprocess.CalledProcessError) as exc:
            self.private.write_text(priv_dir / "setup_error.txt", f"{exc}\n")
            spec = V.SessionSpec(agent, cell.condition, self._q_turns(cell), (0, 0), 0, True, {},
                                 setup_failed="setup_failed")
            return self._finish(cell, run_id, order_index, attempt, [], spec, started, t0, {},
                                retry=attempt <= self.limits["max_retries_per_session"])
        env, stripped = subject_env(sbx.root)
        env["AITASK_AGENT_STRING"] = a["agent_string"]
        session_id = ""
        turns: list[V.Turn] = []
        usage_total: dict = {}
        expected: dict[int, dict] = {}
        retry = False
        model, model_source = "", ""
        stop_reason = ""
        for t in range(1, cell.n_turns + 1):
            pos = max(1, t - 1)
            sbx.set_position(pos)
            expected[t] = sbx.expected_for(pos)
            prompt = f"/aitask-shadow {FAKE_PANE} {SOURCE_TASK}" if agent == "claude" else \
                f"$aitask-shadow {FAKE_PANE} {SOURCE_TASK}"
            if t > 1:
                prompt = ">q"
            purpose = "smoke" if cell.condition == "smoke" else "subject"
            reason = self.budget.acquire(purpose, agent)
            if reason:
                stop_reason = reason
                break
            argv = subject_argv(agent, a["cli_id"], t, prompt, sbx.root, session_id, self.limits,
                                self.trust_override)
            rr = run_cli(argv, sbx.root, env, agent, self.limits["subject_turn_timeout_s"],
                         self.limits["max_tool_calls_per_turn"],
                         self.private.path(priv_dir / f"turn{t}.stdout.jsonl"),
                         self.private.path(priv_dir / f"turn{t}.stderr.txt"),
                         self.limits["kill_grace_s"])
            raw = rr.stdout_path.read_text(encoding="utf-8", errors="replace")
            events = V.parse(agent, raw)
            turn = V.Turn(t, events, rr.exit_code, rr.killed)
            turns.append(turn)
            u = turn_usage(agent, events)
            has_tokens = any(k in u for k in ("input_tokens", "output_tokens"))
            self.budget.add_usage(agent, u.get("cost_usd"),
                                  codex_noncached_tokens(u) if agent == "codex" and has_tokens else None)
            for k, v in u.items():
                usage_total[k] = usage_total.get(k, 0) + v
            self._record_inv("smoke" if cell.condition == "smoke" else "subject", agent, run_id, t,
                             rr.killed or ("ok" if rr.exit_code == 0 else f"exit_{rr.exit_code}"), rr.latency_s,
                             {**{k: v for k, v in u.items() if k in ("input_tokens", "cached_input_tokens",
                                                                    "output_tokens", "cost_usd",
                                                                    "cache_read_input_tokens",
                                                                    "cache_creation_input_tokens")},
                              "tool_calls": rr.tool_calls})
            final = turn.final_text
            self.private.write_text(priv_dir / f"turn{t}.final.txt", final)
            if t == 1:
                for e in events:
                    if e.kind == "meta":
                        session_id = e.meta.get("session_id") or e.meta.get("thread_id") or session_id
                if agent == "claude":
                    model, model_source = claude_model(events)
                else:
                    facts = codex_rollout_facts(session_id) if session_id else {}
                    if facts.get("model"):
                        model, model_source = facts["model"], "codex_rollout_turn_context"
                        self.env_record.setdefault("codex_rollout_effort", facts.get("effort", ""))
            if not turn.has_activity and (rr.exit_code not in (0, None) or rr.killed == "limit_timeout"):
                if rr.killed != "limit_timeout" and attempt <= self.limits["max_retries_per_session"]:
                    retry = True
                break
            if rr.killed or not session_id:
                break
        sha_after = sha256_file(sbx.dispatched)
        spec = V.SessionSpec(agent, cell.condition, self._q_turns(cell), sbx.span, sbx.nlines,
                             sha_after == sbx.dispatched_sha, expected, model_reported=bool(model),
                             q_lines=q_lines_of(sbx.dispatched.read_text(encoding="utf-8")))
        meta = {"run_id": run_id, "argv_turn1": subject_argv(agent, a["cli_id"], 1, "<prompt>", sbx.root, "",
                                                             self.limits, self.trust_override),
                "stripped_env": stripped, "session_id": session_id, "model": model, "model_source": model_source,
                "dry_run_line": a.get("dry_run_line", ""), "sandbox": str(sbx.root), "scenarios": cell.scenarios,
                "dispatched_sha256": sbx.dispatched_sha, "span": sbx.span, "stop_reason": stop_reason}
        self.private.write_text(priv_dir / "meta.json", json.dumps(meta, indent=2) + "\n")
        result = self._finish(cell, run_id, order_index, attempt, turns, spec, started, t0, usage_total,
                              retry=retry and not stop_reason, model=model, model_source=model_source,
                              stop_reason=stop_reason, sbx=sbx)
        if not result.get("retry"):
            shutil.rmtree(sbx.root.parent, ignore_errors=True)
        return result

    def _finish(self, cell: Cell, run_id: str, order_index: int, attempt: int, turns: list[V.Turn],
                spec: V.SessionSpec, started: str, t0: float, usage: dict, retry: bool = False,
                model: str = "", model_source: str = "", stop_reason: str = "", sbx: Sandbox | None = None) -> dict:
        if retry:
            self.sessions_sink.append({"batch": self.batch, "run_id": run_id, "cell": cell.public_cell(),
                                       "order_index": order_index, "agent": cell.agent, "attempt": attempt,
                                       "status": "failed", "outcome": "retried", "started_at": started,
                                       "ended_at": now(), "store_commit": self.store_commit})
            return {"retry": True}
        cls = V.classify_session(turns, spec)
        trials = cls["trials"]
        # Slots that never ran (budget stop or an early break) are recorded too.
        ran = {t["turn_index"] for t in trials}
        missing_cls = self._missing_slot_class(turns, stop_reason, spec)
        for t in self._q_turns(cell):
            if t not in ran:
                trials.append({"turn_index": t, "outcome": missing_cls, "flags": {}})
        trials.sort(key=lambda x: x["turn_index"])
        valid_any = False
        for tr in trials:
            pos = tr["turn_index"] - 1
            scen = cell.scenarios[pos - 1] if pos >= 1 else cell.scenarios[0]
            turn = next((x for x in turns if x.index == tr["turn_index"]), None)
            answer = turn.final_text if turn else ""
            trial_id = f"{run_id}-t{tr['turn_index']}"
            rec = {"batch": self.batch, "run_id": run_id, "trial_id": trial_id, "cell": cell.public_cell(),
                   "turn_index": tr["turn_index"], "position": pos, "scenario": scen, "variant": cell.variant,
                   "agent": cell.agent, "condition": cell.condition, "outcome": tr["outcome"],
                   "flags": {k: v for k, v in tr["flags"].items() if isinstance(v, (bool, int))},
                   "answer_sha256": sha256_text(answer) if answer else "", "answer_chars": len(answer),
                   "judged": False}
            self.trials_sink.append(rec)
            if tr["outcome"] == "valid":
                valid_any = True
                with self.lock:
                    self.answers.append({"trial_id": trial_id, "scenario": scen, "agent": cell.agent,
                                         "variant": cell.variant, "condition": cell.condition,
                                         "answer_path": str(Path("runs") / self.batch / run_id /
                                                            f"turn{tr['turn_index']}.final.txt")})
        sflags = cls["session"]["flags"]
        pub_flags = {k: v for k, v in sflags.items() if isinstance(v, (bool, int))}
        pub_flags["variant_loaded"] = sflags.get("variant_load") == "loaded"
        pub_flags["variant_sha_ok"] = bool(spec.variant_sha_ok)
        pub_flags["helper_infra"] = bool(sflags.get("helper_infra"))
        outcome = cls["session"]["outcome"]
        if outcome == "ok" and cell.condition != "smoke":
            outcome = "has_valid" if valid_any else "no_valid"
        rec = {"batch": self.batch, "run_id": run_id, "cell": cell.public_cell(), "seed": self.seed,
               "order_index": order_index, "started_at": started, "ended_at": now(),
               "latency_s": round(time.monotonic() - t0, 2), "agent": cell.agent,
               "agent_string": self.agents[cell.agent]["agent_string"], "cli_id": self.agents[cell.agent]["cli_id"],
               "cli_version": self.env_record.get(f"{cell.agent}_version", ""), "reported_model": model,
               "model_source": model_source, "reasoning": self._reasoning(cell.agent), "profile": "fast",
               "hashes": self._hashes(cell, sbx), "codex_trust_override": self.trust_override,
               "codex_memories": self.env_record.get("codex_memories", ""),
               "usage": {k: v for k, v in usage.items() if k in ("input_tokens", "cached_input_tokens",
                                                                  "output_tokens", "cost_usd",
                                                                  "cache_read_input_tokens",
                                                                  "cache_creation_input_tokens")},
               "exit_codes": [t.exit_code for t in turns], "status": "ok" if turns else "failed",
               "attempt": attempt, "outcome": outcome, "flags": pub_flags,
               "helpers_called": cls["session"]["helpers_called"],
               "off_path_helpers": sflags.get("off_path_helpers", []), "turns": len(turns),
               "store_commit": self.store_commit, "freeze_sha": load_freeze()["repo_sha"],
               "dry_run_line_sha256": sha256_text(self.agents[cell.agent].get("dry_run_line", ""))}
        self.sessions_sink.append(rec)
        if cell.condition != "smoke":
            with self.lock:
                if valid_any:
                    self.circuit[cell.agent] = 0
                else:
                    self.circuit[cell.agent] += 1
                    if self.circuit[cell.agent] >= self.limits["pilot"]["circuit_breaker_consecutive"]:
                        self.circuit_open.add(cell.agent)
        return {"outcome": outcome, "trials": trials, "session": rec, "flags": sflags,
                "stop_reason": stop_reason}

    @staticmethod
    def _missing_slot_class(turns: list[V.Turn], stop_reason: str, spec: V.SessionSpec) -> str:
        """Outcome for a `>q` slot that never ran, derived from why the session stopped."""
        if spec.setup_failed:
            return f"infra_failure:{spec.setup_failed}"
        if stop_reason:
            return f"not_run:pilot_stopped:{stop_reason}"
        last = turns[-1] if turns else None
        if last is None:
            return "infra_failure:launch_error"
        if last.killed == "limit_timeout":
            return "subject_noncompliance:limit_timeout" if last.has_activity else "infra_failure:limit_timeout"
        if last.killed == "limit_tool_calls":
            return "subject_noncompliance:limit_tool_calls"
        return "infra_failure:launch_error"

    @staticmethod
    def _q_turns(cell: Cell) -> list[int]:
        return [] if cell.condition == "smoke" else list(range(2, cell.n_turns + 1))

    def _reasoning(self, agent: str) -> dict:
        r = self.env_record.get("reasoning", {})
        if agent == "codex":
            out = {k: v for k, v in r.items() if k.startswith("codex_")}
            if self.env_record.get("codex_rollout_effort"):
                out["codex_rollout_effort"] = self.env_record["codex_rollout_effort"]
            return out
        out = {k: v for k, v in r.items() if k.startswith("claude_")}
        cli = self.agents["claude"]["cli_id"]
        ms = self.env_record.get("claude_modelSettings", {})
        if cli in ms:
            out["claude_modelSettings_effortLevel"] = ms[cli]
        return out

    def _hashes(self, cell: Cell, sbx: Sandbox | None) -> dict:
        h = {}
        if sbx is not None:
            h["dispatched_SKILL.md"] = sbx.dispatched_sha
        h["variant"] = sha256_file(VARIANTS_DIR / f"{cell.variant}.md")
        if cell.condition != "minimal":
            h["CLAUDE.md"] = sha256_file(self.store / "instructions" / "CLAUDE.md")
            h["AGENTS.md"] = sha256_file(self.store / "instructions" / "AGENTS.md")
        for sc in cell.scenarios:
            h[f"{sc}/screen_1.txt"] = sha256_file(self.store / "fixtures" / sc / "screen_1.txt")
        return h


# --------------------------------------------------------------------------
# Pilot plan
# --------------------------------------------------------------------------

def pilot_cells() -> list[Cell]:
    cells = [Cell("fresh", ag, v, ["file_selection"]) for ag in ("claude", "codex") for v in VARIANTS]
    cells.append(Cell("repeated", "claude", "v1_baseline", list(LATIN["ABC"]), order="ABC"))
    cells.append(Cell("repeated", "codex", "v1_baseline", list(LATIN["BCA"]), order="BCA"))
    cells += [Cell("minimal", ag, "v1_baseline", ["file_selection"]) for ag in ("claude", "codex")]
    return cells


def smoke_cells() -> list[Cell]:
    return [Cell("smoke", ag, "v1_baseline", ["file_selection"]) for ag in ("claude", "codex")]


def plan_pilot() -> dict:
    cells = pilot_cells()
    items = [
        {"item": "stub_preflight", "invocations": 0},
        {"item": "startup_smoke", "invocations": sum(c.n_turns for c in smoke_cells())},
        {"item": "fresh_sessions", "invocations": sum(c.n_turns for c in cells if c.condition == "fresh")},
        {"item": "repeated_sessions", "invocations": sum(c.n_turns for c in cells if c.condition == "repeated")},
        {"item": "minimal_sessions", "invocations": sum(c.n_turns for c in cells if c.condition == "minimal")},
    ]
    answers = sum(c.n_turns - 1 for c in cells)
    judges = 2
    control_scenarios = sorted({s for c in cells for s in c.scenarios})
    items.append({"item": "answer_judging", "answers": answers, "invocations": answers * judges})
    items.append({"item": "calibration_controls", "scenarios": control_scenarios,
                  "invocations": len(control_scenarios) * 2 * judges})
    total = sum(i["invocations"] for i in items)
    cap = load_limits()["pilot"]["invocation_cap"]
    return {"items": items, "planned_total": total, "cap": cap, "headroom": cap - total,
            "sessions": len(cells), "answers": answers}


def seeded_order(cells: list, seed: int) -> list:
    out = list(cells)
    random.Random(seed).shuffle(out)
    return out


def expand_matrix(matrix: dict) -> list[Cell]:
    cells: list[Cell] = []
    for block in matrix["blocks"]:
        cond = block["condition"]
        for agent in block["agents"]:
            for variant in block["variants"]:
                if cond == "repeated":
                    for order in block["orders"]:
                        for rep in range(1, block.get("reps", 1) + 1):
                            cells.append(Cell(cond, agent, variant, list(LATIN[order]), rep=rep, order=order))
                    continue
                for sc in block["scenarios"]:
                    reps = block.get("reps_by_scenario", {}).get(sc, block["reps"])
                    for rep in range(1, reps + 1):
                        cells.append(Cell(cond, agent, variant, [sc], rep=rep))
    return cells


# --------------------------------------------------------------------------
# Preflight (model-free)
# --------------------------------------------------------------------------

STUB_FORMS = [
    ("aitask_shadow_capture.sh", "noarg", []),
    ("aitask_shadow_capture.sh", "deep", ["--deep"]),
    ("aitask_shadow_capture.sh", "explicit_id", [FAKE_PANE]),
    ("aitask_shadow_capture.sh", "any_pane", ["--any-pane", FAKE_PANE]),
    ("aitask_shadow_capture.sh", "phase", ["--phase"]),
    ("aitask_shadow_capture.sh", "phase", ["--phase", SOURCE_TASK]),
    ("aitask_shadow_capture.sh", "stdin", ["-"]),
    ("aitask_shadow_context.sh", "default", [SOURCE_TASK]),
    ("aitask_skill_resolve_profile.sh", "default", ["shadow"]),
    ("aitask_skill_render.sh", "default", ["aitask-shadow", "--profile", "fast", "--agent", "claude"]),
    ("aitask_explain_context.sh", "default", ["--max-plans", "1", "aitasks/t60/t60_2_m3_2g_go_test_adapter.md"]),
]
STDIN_PROBE = "\x1b[1mbold\x1b[0m line\n"


def preflight(sbx: Sandbox, codex_wrapper: list[str] | None) -> list[dict]:
    """Run every stub form directly and (if given) under ``codex_wrapper``; plus a write negative control."""
    results = []
    expected = sbx.expected_for(1)
    modes = [("direct", [])] + ([("codex_sandbox", codex_wrapper)] if codex_wrapper else [])
    for mode, wrap in modes:
        for helper, form, args in STUB_FORMS:
            argv = [*wrap, f"./.aitask-scripts/{helper}", *args]
            try:
                p = subprocess.run(argv, cwd=sbx.root, capture_output=True, text=True, timeout=60,
                                   input=STDIN_PROBE if form == "stdin" else None)
                out, rc = p.stdout, p.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                out, rc = f"{exc}", -1
            want = "bold line\n" if form == "stdin" else expected[(helper, form)]
            ok = rc == 0 and out == want
            results.append({"mode": mode, "helper": helper, "form": form, "args": args, "ok": ok, "rc": rc})
        if wrap:
            target = sandbox_root() / "preflight_write_probe.txt"
            target.unlink(missing_ok=True)
            p = subprocess.run([*wrap, "bash", "-c", f"echo x > {target}"], cwd=sbx.root, capture_output=True,
                               text=True, timeout=60)
            wrote = target.exists()
            target.unlink(missing_ok=True)
            results.append({"mode": mode, "helper": "negative_control", "form": "write_outside", "args": [],
                            "ok": (not wrote) and p.returncode != 0, "rc": p.returncode})
    return results


def codex_sandbox_wrapper() -> list[str] | None:
    if shutil.which("codex") is None:
        return None
    return ["codex", "sandbox", "-c", 'sandbox_mode="read-only"', "--"]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def store_commit(store: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(store), "log", "-1", "--format=%H", "--", "."],
                              capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def require_manifest(store: Path) -> dict:
    mf = json.loads((HERE / "fixtures" / "MANIFEST.json").read_text())
    problems = check_manifest(store, mf)
    if problems:
        raise SystemExit("store does not match fixtures/MANIFEST.json:\n" + "\n".join(problems[:20]))
    return mf


def cmd_manifest(args) -> int:
    store = resolve_store(args.store)
    files = build_manifest_files(store)
    mf = {"store_project": "aitasks_go", "store_subdir": "aidocs/shadow_q_store",
          "store_commit": store_commit(store), "scenarios": list(ALL_SCENARIOS), "files": files}
    if args.write:
        from store import untracked_files
        missing = untracked_files(store, files)
        if missing:
            print("MANIFEST_REFUSED: not tracked by the store's git (commit or un-ignore them first):")
            for m in missing:
                print(f"  {m}")
            return 1
        (HERE / "fixtures").mkdir(exist_ok=True)
        (HERE / "fixtures" / "MANIFEST.json").write_text(json.dumps(mf, indent=2, sort_keys=True) + "\n")
    print(f"MANIFEST:{len(files)} files; store_commit={mf['store_commit'][:12]}")
    return 0


def cmd_plan(_args) -> int:
    print(json.dumps(plan_pilot(), indent=2))
    return 0


def cmd_preflight(args) -> int:
    store = resolve_store(args.store)
    require_manifest(store)
    sink = PublicSink(RUNS_PUBLIC / args.batch / "preflight.jsonl", "preflight")
    wrapper = codex_sandbox_wrapper()
    all_ok = True
    for agent in ("claude", "codex"):
        root = sandbox_root() / args.batch / f"preflight-{agent}" / "sandbox"
        shutil.rmtree(root.parent, ignore_errors=True)
        sbx = build_sandbox(root, agent, "v1_baseline", "fresh", ["file_selection"], store)
        res = preflight(sbx, wrapper if agent == "codex" else None)
        for r in res:
            sink.append({"batch": args.batch, "agent": agent, "form": f"{r['helper']}:{r['form']}",
                         "mode": r["mode"], "ok": r["ok"], "outcome": f"rc={r['rc']}"})
            print(f"PREFLIGHT:{agent}|{r['mode']}|{r['helper']}:{r['form']}|{'ok' if r['ok'] else 'FAIL'}|rc={r['rc']}")
            all_ok = all_ok and r["ok"]
        shutil.rmtree(root.parent, ignore_errors=True)
    if wrapper is None:
        print("PREFLIGHT:codex|codex_sandbox|unavailable|FAIL")
        all_ok = False
    print("PREFLIGHT_RESULT:" + ("PASS" if all_ok else "FAIL"))
    return 0 if all_ok else 1


def _experiment(args, reserve: int = 0) -> Experiment:
    store = resolve_store(args.store)
    require_manifest(store)
    limits = load_limits()
    p = limits["pilot"]
    pub = RUNS_PUBLIC / args.batch
    journal = pub / "budget_journal.jsonl"
    budget = Budget(p["invocation_cap"], p["claude_cost_threshold_usd"], p["codex_token_threshold"], reserve,
                    journal=journal, batch=args.batch,
                    unreported_claude_usd=limits["unreported_claude_call_usd"],
                    unreported_codex_tokens=limits["unreported_codex_call_tokens"])
    budget.recover(journal, pub / "invocations.jsonl", pub / "budget_state.json")
    exp = Experiment(args.batch, store, limits, budget, store_commit=store_commit(store))
    trust_path = RUNS_PUBLIC / args.batch / "trust_override.json"
    if trust_path.exists():
        exp.trust_override = json.loads(trust_path.read_text()).get("codex_trust_override", False)
    return exp


def _save_budget(exp: Experiment) -> None:
    (RUNS_PUBLIC / exp.batch).mkdir(parents=True, exist_ok=True)
    (RUNS_PUBLIC / exp.batch / "budget_state.json").write_text(json.dumps(exp.budget.snapshot(), indent=2) + "\n")


def smoke_verdict(res: dict) -> tuple[bool, list[str], list[str]]:
    """(ok, stop_reasons, notes) for one smoke session, per the plan's explicit stop list."""
    sess = res.get("session", {}) or {}
    fl = res.get("flags", {}) or {}
    stops, notes = [], []
    if str(sess.get("outcome", "")).startswith("infra_failure") or not res.get("session"):
        stops.append(f"setup:{sess.get('outcome', 'no session record')}")
    if fl.get("variant_load") != "loaded":
        stops.append(f"variant_load={fl.get('variant_load')}")
    if fl.get("helper_infra"):
        stops.append(f"helper:{fl['helper_infra']}")
    if not sess.get("reported_model"):
        stops.append("no_reported_model")
    if not (sess.get("flags") or {}).get("variant_sha_ok", True):
        stops.append("variant_sha_changed")
    helpers = set(sess.get("helpers_called", []))
    for need in ("aitask_skill_resolve_profile.sh:default", "aitask_skill_render.sh:default"):
        if need not in helpers:
            notes.append(f"not_called:{need}")
    if fl.get("capture_before_greeting"):
        notes.append("capture_before_greeting")
    if not fl.get("greeting_seen"):
        notes.append("no_greeting_detected")
    if fl.get("denied_off_path"):
        notes.append("denied_off_path")
    return not stops, stops, notes


def cmd_smoke(args) -> int:
    exp = _experiment(args)
    ok_all = True
    cells = [c for c in smoke_cells() if not getattr(args, "agent", None) or c.agent == args.agent]
    for i, cell in enumerate(cells):
        res = exp.run_session(cell, i)
        ok, stops, notes = smoke_verdict(res)
        if (cell.agent == "codex" and not ok and (res.get("flags") or {}).get("variant_load") != "loaded"
                and not exp.trust_override):
            print("SMOKE:codex|variant not loaded; re-running once with the trust override")
            exp.trust_override = True
            (RUNS_PUBLIC / exp.batch / "trust_override.json").write_text(
                json.dumps({"codex_trust_override": True}) + "\n")
            res = exp.run_session(cell, i + 10)
            ok, stops, notes = smoke_verdict(res)
        fl = res.get("flags", {}) or {}
        print(f"SMOKE:{cell.agent}|{'PASS' if ok else 'FAIL'}|stops={stops}|notes={notes}"
              f"|model={(res.get('session') or {}).get('reported_model')}|match_kinds={fl.get('match_kinds')}")
        ok_all = ok_all and ok
    _save_budget(exp)
    print("BUDGET:" + json.dumps(exp.budget.snapshot()))
    print("SMOKE_RESULT:" + ("PASS" if ok_all else "FAIL"))
    return 0 if ok_all else 1


NEVER_LAUNCHED = ("retried", "infra_failure:setup_failed")


def pending_cells(batch: str, cells: list[Cell]) -> list[Cell]:
    """Cells with no launched session yet (only setup failures / not_run records). Launched sessions stand."""
    p = RUNS_PUBLIC / batch / "sessions.jsonl"
    launched: set[str] = set()
    if p.exists():
        for line in p.read_text().splitlines():
            r = json.loads(line)
            out = str(r.get("outcome", ""))
            if out in NEVER_LAUNCHED or out.startswith("not_run"):
                continue
            launched.add(str(r.get("run_id", "")).split("-a")[0])
    return [c for c in cells if c.cell_id not in launched]


def cmd_pilot(args) -> int:
    limits = load_limits()
    exp = _experiment(args, reserve=limits["pilot"]["reserve_for_controls"])
    cells = seeded_order(pilot_cells(), exp.seed)
    if getattr(args, "resume", False):
        cells = pending_cells(exp.batch, cells)
        print(f"RESUME:{len(cells)} cell(s) never launched: " + ", ".join(c.cell_id for c in cells))
    ans_p = exp.private.path(Path("runs") / exp.batch / "answers.json")
    if ans_p.exists():
        exp.answers = json.loads(ans_p.read_text())
    results = []
    with ThreadPoolExecutor(max_workers=limits["max_concurrent_sessions"]) as pool:
        futs = [pool.submit(exp.run_session, c, i) for i, c in enumerate(cells)]
        for f in futs:
            results.append(f.result())
            _save_budget(exp)
    (exp.private.path(Path("runs") / exp.batch / "answers.json")).write_text(json.dumps(exp.answers, indent=2) + "\n")
    _save_budget(exp)
    print("BUDGET:" + json.dumps(exp.budget.snapshot()))
    trials = [t for r in results for t in r.get("trials", [])]
    print("PILOT_SUMMARY:" + json.dumps(V.summarise(trials)))
    return 0


def cmd_judge(args) -> int:
    import judge as J
    limits = load_limits()
    exp = _experiment(args, reserve=limits["pilot"]["reserve_for_controls"])
    answers = json.loads(exp.private.path(Path("runs") / exp.batch / "answers.json").read_text())
    res = J.judge_batch(exp, answers)
    _save_budget(exp)
    rebuild_scores_json(exp.batch, exp.store)
    print("CALIBRATION:" + json.dumps(res["calibration"]))
    print("BUDGET:" + json.dumps(exp.budget.snapshot()))
    return 0


def cmd_rejudge(args) -> int:
    """Re-judge chosen answers with the current judge prompt (both judges); before/after go public as numbers."""
    import judge as J
    exp = _experiment(args)
    answers = {a["trial_id"]: a for a in json.loads(exp.private.path(Path("runs") / exp.batch / "answers.json").read_text())}
    old = json.loads((RUNS_PUBLIC / exp.batch / "scores.json").read_text())["rows"]
    out = []
    for tid in args.trials.split(","):
        a = answers[tid]
        bid = f"r{random.Random(tid).randrange(16**6):06x}"
        text, _n = J.blind(exp.private.path(a["answer_path"]).read_text(encoding="utf-8"))
        ref = (exp.store / "fixtures" / a["scenario"] / "reference.md").read_text(encoding="utf-8")
        screen = (exp.store / "fixtures" / a["scenario"] / "screen_1.txt").read_text(encoding="utf-8")
        prompt = J.build_prompt(bid, text, ref, screen, J.task_context(exp.store, a["scenario"]))
        for judge in ("claude", "codex"):
            s = J.judge_one(exp, judge, "answer_judge", bid, prompt, a["scenario"])
            before = next((r["scores"] for r in old if r["trial_id"] == tid and r["judge"] == judge), None)
            out.append({"trial_id": tid, "agent": a["agent"], "variant": a["variant"], "condition": a["condition"],
                        "scenario": a["scenario"], "judge": judge, "before": before, "after": s})
    (RUNS_PUBLIC / exp.batch / f"rejudge_{args.tag}.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    _save_budget(exp)
    for o in out:
        b, a_ = o["before"] or {}, o["after"] or {}
        print(f"REJUDGE:{o['agent']}|{o['variant']}|{o['condition']}|{o['scenario']}|{o['judge']}|factual {b.get('factual_correctness')}->{a_.get('factual_correctness')}|unsupported {b.get('unsupported_claims')}->{a_.get('unsupported_claims')}|composite {b.get('composite')}->{a_.get('composite')}")
    print("BUDGET:" + json.dumps(exp.budget.snapshot()))
    return 0


def rebuild_scores_json(batch: str, store: Path) -> dict:
    """Public numbers-only join of judgments to trial cells (``runs/<batch>/scores.json``).

    Built from the public ``scores.jsonl`` and the private blinding map. Only the main
    judging pass (blind ids in the map) is joined; re-judge checks stay in their own file.
    """
    pub = RUNS_PUBLIC / batch
    rows_in = [json.loads(x) for x in (pub / "scores.jsonl").read_text().splitlines()]
    blind = json.loads(PrivateSink(store).path(Path("judging") / batch / "blind_map.json").read_text())
    answers = {a["trial_id"]: a for a in json.loads(PrivateSink(store).path(Path("runs") / batch / "answers.json").read_text())}
    calib = {f"{r['scenario']}|{r['judge']}": r["calibrated"] for r in rows_in if r.get("outcome") == "calibration"}
    rows = []
    for r in rows_in:
        if not r.get("scores") or r.get("control") or r["blind_id"] not in blind:
            continue
        tid = blind[r["blind_id"]].get("trial_id")
        a = answers.get(tid)
        if a is None:
            continue
        sc = dict(r["scores"])
        sc.setdefault("failure_flag", r.get("failure_flag"))
        rows.append({"trial_id": tid, "scenario": a["scenario"], "agent": a["agent"], "variant": a["variant"],
                     "condition": a["condition"], "judge": r["judge"], "scores": sc,
                     "judge_calibrated": calib.get(f"{a['scenario']}|{r['judge']}", False)})
    out = {"calibration": calib, "rows": rows}
    (pub / "scores.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


def judgments_by_trial(batch: str) -> dict[str, list[dict]] | None:
    p = RUNS_PUBLIC / batch / "scores.json"
    if not p.exists():
        return None
    out: dict[str, list[dict]] = {}
    for r in json.loads(p.read_text())["rows"]:
        out.setdefault(r["trial_id"], []).append({"judge": r["judge"], "calibrated": r["judge_calibrated"],
                                                   "failure_flag": r["scores"].get("failure_flag"),
                                                   "could_choose": r["scores"]["could_choose"]})
    return out


def cmd_summary(args) -> int:
    """Aggregate the public JSONL of a batch (numbers only) for the report."""
    pub = RUNS_PUBLIC / args.batch
    def rows(name):
        p = pub / name
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
    sessions, trials, invs = rows("sessions.jsonl"), rows("trials.jsonl"), rows("invocations.jsonl")
    final_trials = [t for t in trials if t.get("condition") != "smoke"]
    out = {"trials": V.summarise(final_trials, judgments_by_trial(args.batch)), "outcomes": {}, "invocations": {},
           "latency": {}, "usage": {}}
    for t in final_trials:
        out["outcomes"][t["outcome"]] = out["outcomes"].get(t["outcome"], 0) + 1
    for i in invs:
        key = f"{i['purpose']}:{i['agent']}"
        out["invocations"][key] = out["invocations"].get(key, 0) + 1
        out["latency"].setdefault(key, []).append(i.get("latency_s"))
        u = i.get("usage") or {}
        agg = out["usage"].setdefault(key, {})
        for k, v in u.items():
            if isinstance(v, (int, float)):
                agg[k] = round(agg.get(k, 0) + v, 4)
    out["latency"] = {k: {"n": len(v), "mean": round(sum(v) / len(v), 1), "max": max(v)}
                      for k, v in out["latency"].items() if v}
    out["sessions"] = len([s for s in sessions if s.get("outcome") != "retried"])
    out["retried"] = len([s for s in sessions if s.get("outcome") == "retried"])
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def reclassify_batch(batch: str, store: Path) -> list[dict]:
    """Re-run the current validator over a batch's saved raw streams (no CLI calls).

    Rebuilds each launched session's spec from its private meta, the frozen renders
    and the store fixtures, and checks those inputs against the hashes recorded at
    run time. Returns one record per `>q` slot with the recorded and the new class.
    """
    pub = RUNS_PUBLIC / batch
    sessions = {r["run_id"]: r for r in (json.loads(x) for x in (pub / "sessions.jsonl").read_text().splitlines())}
    recorded = {r["trial_id"]: r for r in (json.loads(x) for x in (pub / "trials.jsonl").read_text().splitlines())}
    kills: dict[tuple[str, int], str] = {}
    for x in (pub / "invocations.jsonl").read_text().splitlines():
        r = json.loads(x)
        if str(r.get("outcome", "")).startswith("limit_"):
            kills[(r["run_id"], r["turn_index"])] = r["outcome"]
    out = []
    for run in sorted(p for p in (store / "runs" / batch).iterdir() if p.is_dir()):
        meta_p = run / "meta.json"
        sess = sessions.get(run.name)
        if not meta_p.exists() or sess is None:
            continue
        meta = json.loads(meta_p.read_text())
        cell = sess["cell"]
        agent, variant, condition = cell["agent"], cell["variant"], cell["condition"]
        text = build_minimal(agent, variant) if condition == "minimal" else build_variant(agent, variant)
        if sha256_text(text) != meta["dispatched_sha256"]:
            raise SystemExit(f"{run.name}: rebuilt dispatched SKILL.md does not match the recorded sha")
        scen = meta["scenarios"]
        for sc in scen:
            want = sess.get("hashes", {}).get(f"{sc}/screen_1.txt")
            if want and want != sha256_file(store / "fixtures" / sc / "screen_1.txt"):
                raise SystemExit(f"{run.name}: fixture {sc} changed since the run")
        turn_files = sorted(run.glob("turn*.stdout.jsonl"), key=lambda p: int(re.search(r"turn(\d+)", p.name).group(1)))
        exits = sess.get("exit_codes", [])
        turns, expected = [], {}
        for f in turn_files:
            t = int(re.search(r"turn(\d+)", f.name).group(1))
            pos = max(1, t - 1)
            fx = store / "fixtures" / scen[pos - 1]
            screen = (fx / "screen_1.txt").read_text(encoding="utf-8")
            expected[t] = {("aitask_shadow_capture.sh", k): screen for k in ("noarg", "deep", "explicit_id", "any_pane")}
            expected[t][("aitask_shadow_capture.sh", "phase")] = (fx / "phase.txt").read_text(encoding="utf-8")
            expected[t][("aitask_shadow_context.sh", "default")] = (fx / "context.txt").read_text(encoding="utf-8")
            expected[t][("aitask_skill_resolve_profile.sh", "default")] = "fast\n"
            expected[t][("aitask_skill_render.sh", "default")] = ""
            expected[t][("aitask_explain_context.sh", "default")] = ""
            ec = exits[t - 1] if t - 1 < len(exits) else None
            turns.append(V.Turn(t, V.parse(agent, f.read_text(encoding="utf-8", errors="replace")), ec,
                                kills.get((run.name, t), "")))
        q_turns = [] if condition == "smoke" else list(range(2, 1 + (1 if condition != "repeated" else 3) + 1))
        dlines = text.split("\n")
        span = tuple(meta["span"])
        spec = V.SessionSpec(agent, condition, q_turns, span, len(dlines),
                             bool((sess.get("flags") or {}).get("variant_sha_ok", True)), expected,
                             model_reported=bool(meta.get("model")), q_lines=q_lines_of(text))
        cls = V.classify_session(turns, spec)
        for tr in cls["trials"]:
            tid = f"{run.name}-t{tr['turn_index']}"
            old = recorded.get(tid, {}).get("outcome", "")
            pos = tr["turn_index"] - 1
            out.append({"batch": batch, "run_id": run.name, "trial_id": tid, "turn_index": tr["turn_index"],
                        "agent": agent, "variant": variant, "condition": condition, "scenario": scen[pos - 1],
                        "recorded": old, "reclassified": tr["outcome"], "changed": old != tr["outcome"],
                        "flags": {k: v for k, v in tr["flags"].items() if isinstance(v, (bool, int))}})
        if condition == "smoke":
            out.append({"batch": batch, "run_id": run.name, "trial_id": f"{run.name}-smoke", "turn_index": 1,
                        "agent": agent, "variant": variant, "condition": condition, "scenario": scen[0],
                        "recorded": "smoke", "reclassified": f"variant_load:{cls['session']['flags'].get('variant_load')}",
                        "changed": False, "flags": {}})
    return out


def cmd_classify(args) -> int:
    """Offline re-classification of saved raw streams with the current validator (no CLI calls)."""
    store = resolve_store(args.store)
    rows = reclassify_batch(args.batch, store)
    target = RUNS_PUBLIC / args.batch / "trials_reclassified.jsonl"
    target.unlink(missing_ok=True)
    sink = PublicSink(target, "reclass")
    for r in rows:
        sink.append(r)
        print(f"RECLASS:{r['agent']}|{r['condition']}|{r['variant']}|{r['scenario']}|t{r['turn_index']}|"
              f"{r['recorded']} -> {r['reclassified']}{'  CHANGED' if r['changed'] else ''}")
    print(f"RECLASS_SUMMARY:{len(rows)} slot(s); {sum(r['changed'] for r in rows)} changed")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--store", help="private store root (default: resolve aitasks_go)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    m = sub.add_parser("manifest")
    m.add_argument("--write", action="store_true")
    for name in ("preflight", "smoke", "pilot", "judge", "rejudge", "summary", "classify"):
        s = sub.add_parser(name)
        s.add_argument("--batch", default="pilot")
        if name == "smoke":
            s.add_argument("--agent", choices=("claude", "codex"))
        if name == "pilot":
            s.add_argument("--resume", action="store_true", help="run only cells that never launched")
        if name == "rejudge":
            s.add_argument("--trials", required=True, help="comma-separated trial ids")
            s.add_argument("--tag", required=True)
    args = ap.parse_args(argv)
    return {"plan": cmd_plan, "manifest": cmd_manifest, "preflight": cmd_preflight, "smoke": cmd_smoke,
            "pilot": cmd_pilot, "judge": cmd_judge, "rejudge": cmd_rejudge, "summary": cmd_summary,
            "classify": cmd_classify}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
