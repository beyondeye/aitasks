---
Task: t2048_codex_session_capture_on_macos.md
Base branch: main
Output branch: main
---

# t2048 — Codex session capture on macOS (`ps` / `lsof` probe)

## Context

`agent_sessions.codex_observe_pid()` (and through it `codex_session_for_pid`,
`codex_resume_evidence`, `codex_process_model`, `process_model_evidence`) reads
`/proc/<pid>/{fd,cmdline,stat,task/*/children}`. macOS has no `/proc`, so every
answer there is `MISS_NO_PROCESS`: freezes never capture a codex session id and
restores stay "restored, unverified". The goal is a macOS rung that gives the
same four facts from `ps` and `lsof`, leaves Linux untouched, and keeps
"could not look" (`MISS_NO_PROCESS`) distinct from "looked, not codex".

### Measured on this Mac (codex 0.163.0, standalone install), t2048 planning

- `ps -o args=` prints argv space-joined (argument boundaries lost) — not used;
  argv comes from `KERN_PROCARGS2` (see Design).
- `ps -p PID -o pgid=,tpgid=,tty=` → e.g. `18806 18806 ttys005`; no terminal is
  `tpgid 0`, `tty ??`. Dead / invalid pid → rc 1.
- `lsof -n -P -w -Ffn -p PID` → `p<pid>`, then `f<fd>` / `n<path>` pairs; real
  fds are numeric, plus `cwd`/`txt` pseudo-entries. ~50 ms. Dead pid → rc 1.
- `codex resume <sid> -c tui.alternate_screen=never` (in-process TUI) holds the
  rollout open from launch (fd 38) — the premise of the resolver and of
  `codex_resume_evidence` holds on macOS.
- **Daemon routing behaves the same as on Linux (t2046/t2047):** a TUI launched
  without `tui.alternate_screen=never` holds no rollout; the
  `app-server-daemon/.../bin/codex` process (a child of the pane codex, own
  pgid, no tty) holds it. The pane codex therefore resolves to `MISS_NO_MATCH`,
  exactly as the docstring already documents for Linux. No new handling needed;
  docstring gets a "measured on macOS too" note.

## Design

Keep every `/proc` reader and the whole shell/foreground/identity logic as is.
Dispatch inside the **existing primitives** — the tests already wrap them by
name with `(pid, proc_root)` signatures — so the shared logic runs unchanged on
both backends:

| primitive (unchanged name/signature) | Linux (unchanged) | macOS |
|---|---|---|
| `_codex_cmdline_argv(pid, proc_root)` | `/proc/<pid>/cmdline` | **exact argv** from `sysctl([CTL_KERN, KERN_PROCARGS2, pid])` via ctypes (`_darwin_procargs(pid) -> bytes | None`, parsed by `_parse_procargs2(raw)`: int argc, exec path, NUL padding, argc NUL-terminated strings; decoded utf-8/replace like `/proc`). sysctl error (EINVAL: dead pid, other user's process), short buffer, fewer than argc strings → `None` |
| `_proc_job(pid, proc_root)` | `/proc/<pid>/stat` | `ps -o pgid=,tpgid=,tty=` → `(pgid, tty_name, tpgid)` (tty is an opaque equality key; only equality is ever compared) |
| `_direct_children(pid, proc_root)` | `task/*/children` | `ps -A -o pid=,ppid=`; pid absent from the listing → `None` |
| fd targets in `codex_observe_pid` | `fd/` listing + `os.readlink` loop | new `_lsof_open_files(pid)` run with `LC_ALL=C`: numeric-fd `n` values, each decoded by `_decode_lsof_name()`; no `p<pid>` line / rc≠0 → `None` |

**Why not `ps -o args=`** (review finding, verified): it space-joins argv, so a
single prompt argument `"explain -m gpt-5.4"` would be re-split into a fake
`-m gpt-5.4` and `_argv_model` would invent a model — which
`agent_freeze._observe_codex_session` can use to override the remembered model
or clear a valid pair. `KERN_PROCARGS2` was measured on this Mac to return
`[b'/x/my dir/codex', b'-e', b'sleep 20', b'explain -m gpt-5.4']` for an
`exec -a` process: boundaries and argv0 exact.

**lsof name decoding** (review finding, verified with real files under
`LC_ALL=C`): lsof renders `\` as `\\`, `\n`/`\t`/`\r`/`\b`/`\f` by name,
bytes ≥0x7f as `\xNN` (`café` → `caf\xc3\xa9`), and other control bytes as
`^X` (`\x01` → `^A`) — **indistinguishable from a literal `^A`**.
`_decode_lsof_name(s) -> str | None` decodes the backslash escapes exactly
(bytes → `os.fsdecode`), and returns `None` (uncertain) for any `^`, an unknown
or truncated escape. In `codex_observe_pid` ps mode, a **rollout-shaped**
target (basename matches `_CODEX_ROLLOUT_RE` on the raw value — the basename is
codex-generated ASCII) that is uncertain, or whose decoded path does not exist,
makes the whole observation `MISS_NO_PROCESS` — never `MISS_NO_MATCH`, which
would clear a stored id. Non-rollout-shaped targets are ignored as today.

Backend choice: `_ps_probe(proc_root) -> bool` = `_PS_PROBE_PLATFORM and
proc_root == "/proc"` where `_PS_PROBE_PLATFORM = sys.platform == "darwin"`.
On Linux this is always False → zero behaviour change; a test-supplied fake
`proc_root` is never routed to `ps`.

All commands go through one `_run_probe(cmd) -> str | None`
(`subprocess.run`, `capture_output`, `text`, `errors="replace"`,
`timeout=_PROBE_TIMEOUT_S = 2` — same bound as
`monitor_core._is_companion_process`). Non-zero rc, timeout, `OSError`
(binary missing) → `None`, i.e. `MISS_NO_PROCESS`, never a disproof.

## Steps

1. **`.aitask-scripts/lib/agent_sessions.py`**
   - `import subprocess` (ctypes imported lazily inside `_darwin_procargs`);
     add `_PS_PROBE_PLATFORM`, `_PROBE_TIMEOUT_S`, `_ps_probe()`,
     `_run_probe(cmd, env=None)`, `_darwin_procargs()`, `_parse_procargs2()`,
     `_ps_job()`, `_ps_children()`, `_decode_lsof_name()`,
     `_lsof_open_files()` next to the `/proc` readers, with a short block
     comment recording the measured formats above. `_lsof_open_files` returns
     `(raw, decoded_or_None)` pairs so the caller can apply the
     rollout-shaped uncertainty rule.
   - Each of `_codex_cmdline_argv`, `_proc_job`, `_direct_children` starts with
     `if _ps_probe(proc_root): return _ps_…(pid)`.
   - `codex_observe_pid`: in ps mode skip the `fd/` listing (both the depth-0
     and the shell-child one); read argv first (None → `MISS_NO_PROCESS`), then
     after agent selection get targets from `_lsof_open_files(agent_pid)`
     (None → `MISS_NO_PROCESS`). Factor the existing readlink loop into
     `_readlink_targets(entries)` (still calls `os.readlink`, still skips
     `(deleted)`), so both modes feed one candidate loop. The
     `_observed_process_unchanged` recheck stays after the evidence read, so the
     lsof snapshot is bracketed by two argv reads exactly like the readlinks.
   - Docstrings/comments: module header ("spawns no process" → except the
     read-only `ps`/`lsof` probes macOS needs, t2048), `MISS_NO_PROCESS`
     comment, `_codex_cmdline_argv` docstring, `codex_observe_pid` "Linux-only"
     paragraph (+ daemon-routing measured on macOS), restore-verdict comment
     ~L1662. `process_environ_value` stays `/proc`-only (macOS → `None`, i.e.
     "could not read") — stated in its docstring.
2. **Comment drift in callers** — `agent_restore.py` L256 / L1096 and
   `agent_freeze.py` L256 / L1376 say "no `/proc` (macOS)": reword to "process
   not inspectable (no `/proc` and no `ps`/`lsof` answer)".
3. **Tests — `tests/test_agent_sessions_transcripts.py`**
   - A fake backend answering **from the same fake `/proc` fixture**:
     `_darwin_procargs` patched to build a real `KERN_PROCARGS2` byte image from
     `cmdline` (so `_parse_procargs2` is exercised); `_run_probe` answering
     `ps` (stat → pgid/tpgid/tty name; `task/*/children` → `pid ppid` lines)
     and `lsof` (`fd/` symlinks → `-F` output, **names encoded with lsof's
     escaping rules**, not raw); missing file → `None`.
   - Captured fixture `tests/data/session_hooks/lsof_escaped_names.json`:
     pairs of `{true name, real lsof -Fn rendering under LC_ALL=C}` captured on
     this Mac for `café`, `a\nb`, `back\slash`, `t\tx`, `d\x7fx`, `c\x01x`,
     `q^Ax`, `sp ace`. Tests: `_decode_lsof_name` maps every capture back to its
     true name, and returns `None` for both `^A` captures; end-to-end, a rollout
     under a `café` CODEX_HOME resolves its session, and one under `c\x01x`
     yields `MISS_NO_PROCESS` (not `MISS_NO_MATCH`).
   - argv regression: a codex whose single prompt argument is
     `"explain -m gpt-5.4"` reports `cli_id == ""` on the macOS backend (and on
     Linux — control); `_parse_procargs2` on a captured real buffer, a
     truncated buffer, and argc larger than the strings present (→ `None`).
   - Parity subclasses `PsCodexPidCorrelationTests`, `PsCodexShellPaneTests`,
     `PsCodexProcessModelTests`, `PsProcessAgentEvidenceTests` (argv part) that
     patch `_ps_probe → True` and `_run_probe → fake`, re-running the whole
     shared-logic suite on the macOS backend. Tests whose fixture has no ps
     analogue (wrapping `os.readlink`; an unreadable `children` file; a child
     listed twice; environ) are skipped in the subclass with an explicit
     reason, and replaced by ps-specific tests below.
   - ps-specific tests: argv0 with a space resolves as codex; procargs
     unreadable → `MISS_NO_PROCESS`; `ps`/`lsof` missing
     (`FileNotFoundError`), timeout, rc≠0 → `MISS_NO_PROCESS` (never
     `MISS_NOT_CODEX`); lsof `cwd`/`txt` entries ignored; a suspend during the
     lsof read → `MISS_NO_PROCESS`; `ps -A` failure on the shell route →
     `MISS_NO_PROCESS`.
   - `_ps_probe` contract: False on non-darwin for any root; True on darwin
     only for `"/proc"`; a fake root is never routed to ps.
   - Pre-fix control: run the new tests against unmodified
     `agent_sessions.py` (git stash) and confirm they fail.
4. Run `tests/test_agent_sessions_transcripts.py`, plus the freeze/restore
   modules that consume it (`tests/test_agent_freeze*.py`,
   `tests/test_agent_restore*.py`) and the full Python suite.

### Post-phase (risk mitigations)

1. [live_macos_check] On this Mac, with a scratch `CODEX_HOME` (copied
   `auth.json` + one copied rollout, no `config.toml`, so no hooks fire) and a
   private tmux socket `-L t2048probe` in the scratchpad cwd, call
   `codex_observe_pid(pane_pid)` for: (a) depth-0
   `codex resume <sid> -c tui.alternate_screen=never` → `(sid, path, "", "")`;
   (b) the same typed at an interactive `zsh` prompt (shell route) →
   `(sid, …)`; (c) after Ctrl-Z in (b) → `MISS_NOT_CODEX`; (d) daemon-routed
   (no `alternate_screen=never`) → `MISS_NO_MATCH`; (e) a dead pid →
   `MISS_NO_PROCESS`. Record results in Final Implementation Notes. Tear down
   the tmux server and the scratch daemon.

## Verification

- `python3 tests/test_agent_sessions_transcripts.py` (all old + new tests green
  on macOS; on Linux the parity classes run via the fake runner too).
- `bash tests/run_all_python_tests.sh` — last line `PYTHON SUITE: PASSED`.
- Pre-fix control shows the new tests red.
- Live checks (a)–(e) above.

## Step 9 (Post-Implementation)

Current-branch mode: commit code, archive task + plan via the standard Step 9.

## Risk

### Code-health risk: medium
- The resolver is load-bearing for freeze (clears stored ids on `MISS_NOT_CODEX`/`MISS_NO_MATCH`) and restore verification; a ps-mode parsing mistake that yields a false disproof would wipe valid hook-captured ids on macOS · severity: medium · → mitigation: none (covered by parity suite + ps-specific "could not look" tests in Step 3)
- `agent_sessions.py` loses its "spawns no process" property and adds subprocess latency (~10 probe calls, each ≤2 s worst case) on the freeze keypress path · severity: low · → mitigation: none (documented; measured ~10–50 ms per call)

### Goal-achievement risk: low
- macOS job-control semantics (`tpgid`, tty, Ctrl-Z) for the shell route are assumed equal to Linux; only the depth-0 and daemon cases were measured during planning · severity: low (residual — addressed by inline post-phase live_macos_check) · → mitigation: inline post-phase live_macos_check
- Text-rendered process facts can invent or hide evidence: `ps args` re-splits a prompt argument into a fake `-m` (invented model), and lsof's escaped/`^X` names can hide a real rollout (false `MISS_NO_MATCH`) · severity: low (residual — argv comes from `KERN_PROCARGS2`, lsof names are decoded exactly or declared uncertain → `MISS_NO_PROCESS`, both pinned by captured-fixture tests) · → mitigation: none
- `KERN_PROCARGS2` via ctypes depends on a stable, undocumented-but-long-standing buffer layout; a layout surprise must fail closed · severity: low · → mitigation: none (`_parse_procargs2` returns `None` on any inconsistency → `MISS_NO_PROCESS`)
- Non-ASCII CODEX_HOME paths on macOS rely on the decoder being right; an error there degrades to no capture, never a disproof (existence check on the decoded path) · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: live_macos_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: macOS shell-route job-control semantics unmeasured | desc: live-verify depth-0, shell route, Ctrl-Z, daemon-routed and dead-pid cases on a real Mac
