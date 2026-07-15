---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1149
created_at: 2026-07-15 18:44
updated_at: 2026-07-15 18:51
---

## Context

Part of t1149 (chatlink config wizard TUI). The `ait chatlink` gateway daemon validates its configuration only at startup, inside `serve()` (`.aitask-scripts/chatlink/daemon.py:737-769`): a chain of fail-closed `_refuse()` calls (config path -> YAML/mapping -> `intake_channel` -> token -> explore-relay agent resolvable) plus a warn-only docker-binary check. Per-key config warnings from `config.py::load_config` go to stderr and are lost. Nothing structured exists for a TUI to display.

This child extracts that check chain into a shared, structured **preflight module** — the step-check engine for the t1149_2 status panel and the t1149_3 wizard — and rewires the daemon onto it **behavior-preserving**.

## Pinned contracts (from the approved parent plan, aiplans/p1149_chatlink_config_wizard_tui.md)

1. **Textual-import-free.** `chatlink/preflight.py` must not import Textual (extend the existing daemon import-purity guard pattern in `tests/test_chatlink_tui.sh` — `import chatlink.daemon` pulls no textual — with an equivalent guard for `chatlink.preflight`).
2. **Structured result shape:** each check returns `id`, `severity` (pass|warn|fail), TUI-friendly `message`, `fix_hint`, and — for fail results — `daemon_refuse_message` carrying the EXACT legacy `_refuse()` text. This field is the single source of truth for daemon refusal text: the rewired `serve()` emits `_refuse(result.daemon_refuse_message)` for the first failing check, in the same order as today. TUI text can therefore never drift from daemon behavior.
3. **Cheap vs expensive probe levels.** Each check declares a probe level:
   - `cheap` = pure file/YAML/in-memory: config path resolvable (`paths.config_file()`), YAML parses / is a mapping (`load_config`), `intake_channel` valid, allowlist non-empty (warn — deny-by-default means empty allowlists = nobody can report), token present (`paths.read_token()`).
   - `expensive` = spawns a process / hits the OS: explore-relay agent resolvable (`daemon.resolve_explore_relay_argv()` — runs `ait codeagent invoke explore-relay --headless --dry-run`), docker binary present (`shutil.which("docker")`, warn-only), docker image `ait-chatlink-agent` present (`docker image inspect`, warn-only — NEW check, missing image today only surfaces as a failed session).
   API exposes them separately (e.g. `run_cheap_checks()` / `run_expensive_checks(timeout=...)`). Every expensive probe takes an explicit timeout and fails closed: timeout/OSError -> a fail/warn result, never a hang.
4. **Behavior preservation is a hard contract.** Daemon refuse messages and exit codes must be byte-for-byte unchanged. `tests/test_chatlink_daemon.sh` asserts each refusal path; a preflight unit test pins `daemon_refuse_message` per check id.
5. **`load_config` fail-closed semantics must not change.** Add a warnings-returning variant (e.g. `load_config_with_warnings(path) -> (cfg_or_None, list_of_warnings)`) that collects what `_warn()` emits; keep `load_config` as a thin wrapper so all existing callers are untouched.

## Key files to modify

- NEW `.aitask-scripts/chatlink/preflight.py` — the check engine (dataclass result + check functions + run_cheap/run_expensive).
- `.aitask-scripts/chatlink/config.py` — add `load_config_with_warnings`; `_warn` gains a collector seam (e.g. optional callback/list param threaded through the helpers, defaulting to stderr so current behavior is unchanged).
- `.aitask-scripts/chatlink/daemon.py` — `serve()` (lines ~737-784) consumes preflight results instead of inlining the checks; `resolve_explore_relay_argv()` may move to preflight or be imported by it (avoid circular imports: preflight should not import daemon — move the resolver into preflight and have daemon import it, keeping a re-export for compatibility if tests reference it).
- `tests/test_chatlink_daemon.sh` — extend: assert refusal messages/exit codes unchanged.
- NEW `tests/test_chatlink_preflight.sh` — structured results, probe levels, timeouts fail closed, Textual-free import guard, `daemon_refuse_message` strings pinned per check id.

## Reference patterns

- The `_refuse` chain: `.aitask-scripts/chatlink/daemon.py:737-784` (each refusal has a distinct message; docker is warn-only to stderr).
- `_warn` sites: `.aitask-scripts/chatlink/config.py` (module-level `_warn()` at line 54, called from `_clamped_int`, `_str_list`, `_env_name_list`, `_normalize_intake_channel`, `load_config`).
- `paths.py` helpers: `config_file()`, `read_token()`, `token_file()` (`.aitask-scripts/chatlink/paths.py`).
- Test scaffolds: `tests/test_chatlink_daemon.sh`, `tests/test_chatlink_config.sh` (assert_eq/assert_contains style, self-contained bash).

## Implementation plan

1. Define `CheckResult` dataclass (id, severity, message, fix_hint, daemon_refuse_message=None, probe level implicit via which runner emits it).
2. Implement cheap checks (config path, yaml/mapping, intake_channel, allowlist, token) — reuse `load_config_with_warnings` so per-key warnings become warn-severity results (id like `config_key:<key>`).
3. Implement expensive checks (agent argv via moved `resolve_explore_relay_argv` with timeout param on the subprocess call; docker binary; docker image inspect) — all fail closed on timeout/OSError.
4. Add `load_config_with_warnings` to config.py; `load_config` delegates.
5. Rewire `daemon.serve()`: run cheap then expensive checks in the legacy order; first `fail` -> `_refuse(daemon_refuse_message)`; docker warn results -> print warning to stderr exactly as today.
6. Tests (both files), shellcheck any touched .sh.

## Verification

- `bash tests/test_chatlink_daemon.sh` passes — every legacy refusal path produces byte-identical message + exit code.
- `bash tests/test_chatlink_preflight.sh` passes — result shape, probe split, pinned refusal strings, fail-closed timeouts.
- `PYTHONPATH=.aitask-scripts python -c "import sys, chatlink.preflight; assert not any('textual' in m for m in sys.modules)"` — Textual-free.
- `bash tests/test_chatlink_tui.sh` still passes (daemon import guard intact).
