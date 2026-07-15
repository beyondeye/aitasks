---
Task: t1149_1_preflight_module.md
Parent Task: aitasks/t1149_chatlink_config_wizard_tui.md
Sibling Tasks: aitasks/t1149/t1149_2_config_status_panel.md, aitasks/t1149/t1149_3_config_wizard_flow.md, aitasks/t1149/t1149_4_wizard_docs_rewrite.md, aitasks/t1149/t1149_5_live_discord_validation.md, aitasks/t1149/t1149_6_manual_verification_chatlink_config_wizard_tui.md
Archived Sibling Plans: aiplans/archived/p1149/p1149_*_*.md
Worktree: (current branch — fast profile, no worktree)
Branch: current
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-15 19:30
---

# p1149_1 — Preflight module (foundation)

## Context

Part of t1149 (chatlink config wizard TUI). The gateway daemon validates its
configuration only at startup, inside `serve()`
(`.aitask-scripts/chatlink/daemon.py:737-784`): a chain of fail-closed
`_refuse()` calls, plus a warn-only docker-binary check. Per-key config
warnings from `config.py::load_config` go to stderr and are lost. Nothing
structured exists for a TUI to display.

This child extracts that check chain into a shared, structured, **Textual-free**
`chatlink/preflight.py` — the step-check engine for the t1149_2 status panel
and the t1149_3 wizard — and rewires the daemon onto it **behavior-preserving**
(byte-identical refuse messages + exit codes).

**Plan verified against source this session (no drift):**
- `_refuse(msg)` prints `chatlink: {msg}` to stderr and returns **2**
  (`daemon.py:693-695`); five refusal sites (`:741,:746,:750,:757,:766`).
- `parse_dry_run_argv` / `resolve_explore_relay_argv` at `daemon.py:700-734`.
- `tests/test_chatlink_daemon.sh:1111-1151` already exercises the three refuse
  paths (rc=2 + zero-side-effect construction spy) but asserts **exit codes
  only**, not message text — pinning messages is a compatible extension.
- `config.py` `_warn()` at `:54`, called from `_clamped_int`, `_str_list`,
  `_env_name_list`, `_normalize_intake_channel`, `load_config`.
- `tests/test_chatlink_daemon.sh:1137-1138` monkeypatches
  `dm.resolve_explore_relay_argv = lambda: ()` on the **daemon module
  namespace** — a load-bearing test seam this plan must preserve (see
  Implementation step 3). The `dm.paths.config_file` / `dm.paths.read_token`
  patches survive any refactor automatically (`paths` is a shared module
  singleton), but the daemon-global resolver patch does not.

## Pinned contracts (parent plan aiplans/p1149_chatlink_config_wizard_tui.md)

1. `CheckResult`: `id`, `category`, `severity` ∈ {pass, warn, fail},
   TUI-friendly `message`, `fix_hint`, and for fail results
   `daemon_refuse_message` — the EXACT legacy `_refuse()` text. Rewired
   `serve()` emits `_refuse(result.daemon_refuse_message)` for the first
   failing check in the legacy order, so refusal text has exactly one
   definition and the TUI text can never drift from daemon behavior.
1b. **Scope/naming contract (pinned — don't bake today's single operation
   into generic ChatLink concepts).** Checks are bucketed by `category` so
   future ChatLink operations can add checks additively without rewriting
   the transport/config machinery or changing daemon behavior:
   - `transport` — Discord/config surface: `config_file`, `config_yaml`,
     `intake_channel`, `allowlist`, `token`.
   - `runtime` — backend/sandbox: `docker_binary`, `docker_image` (today's
     image `ait-chatlink-agent`; the check shape must permit
     operation-specific image requirements later without changing this
     check), per-key config warnings `config_key:<key>`.
   - `operation` — checks specific to the operation ChatLink launches.
     Today that is exactly one: **`explore_relay_agent_command`** (NOT a
     generic `agent_command` — future operations add their own
     `<operation>_…` check ids and functions additively).
   The `daemon_refuse_message` texts are unaffected by naming (byte-for-byte
   contract stands). Preflight's API must allow adding future operation
   checks without touching existing transport/runtime checks or `serve()`.
2. Cheap vs expensive probe split: `run_cheap_checks()` (config path
   resolvable, YAML parses / is a mapping, `intake_channel` valid, allowlist
   non-empty [warn — deny-by-default], token present) vs **per-check expensive
   functions** `check_explore_relay_agent_command(resolver=…, timeout=…)`,
   `check_docker_binary()`, `check_docker_image(timeout=…)`, with
   `run_expensive_checks(timeout=…)` as the TUI convenience that runs all
   three. Every expensive probe accepts a timeout and fails closed
   (timeout/OSError → fail/warn result, never a hang).
3. **Daemon subset is explicit (pinned):** `serve()` consumes exactly the
   legacy checks — cheap chain + `check_explore_relay_agent_command` (refuse)
   + `check_docker_binary` (warn) — and **never** `check_docker_image`, which
   is panel/wizard-only. A spy negative-control test asserts daemon startup
   never invokes the image-inspect seam.
4. **Timeout semantics (pinned):** the resolver/probe `timeout` parameters
   **default to `None` = wait indefinitely (today's behavior)**, and the
   daemon path passes **no timeout** — daemon startup behavior is unchanged
   (no new refusal mode on slow machines). Explicit timeouts are chosen by
   the TUI consumers (t1149_2/t1149_3) via preflight constants (e.g.
   `AGENT_PROBE_TIMEOUT_S = 30`, `DOCKER_PROBE_TIMEOUT_S = 5`). Timeout
   behavior is unit-tested with a stub slow command in the preflight test —
   never on the daemon path.
5. **Daemon stderr is preserved byte-for-byte — including config warnings
   (pinned):** today `load_config` prints `chatlink config: <msg>` warning
   lines to stderr during startup (degraded keys, and the fail-closed
   `… — refusing` lines that precede a refusal). After the rewire, the daemon
   path **replays the collected warnings to stderr in collection order**
   (single collection point inside `load_config_with_warnings`, so order is
   identical) before/alongside acting on the results — no lost lines, no
   duplicates. Tests assert the **full stderr sequence** for (a) a
   degraded-key config that still starts past config checks, and (b) a
   malformed-YAML refusal (both the `chatlink config: …` line and the
   `chatlink: …` refusal line, in order).
6. **`config.py` API shape (pinned — collector must not silence legacy
   callers):**
   - `load_config_with_warnings(path) -> (cfg_or_None, list[str])` —
     **collect-only, emits nothing to stderr.** The structured variant for
     preflight/TUI.
   - `load_config(path)` — delegates to the variant, then **replays every
     collected warning to stderr via the legacy `_warn`** (collection order ==
     emission order) before returning. Existing callers and
     `tests/test_chatlink_config.sh` (which capture `load_config()` stderr
     directly) see byte-identical output. Fail-closed semantics unchanged.
   - Paired test assertions: same degraded config → `load_config` prints the
     warning lines; `load_config_with_warnings` prints nothing and returns
     them in the list.
   - The daemon path uses **only the silent variant** (via preflight) with the
     **single** replay point of contract 5 — one emission, no duplicates.
7. No Textual import — guard-tested.

## Implementation steps

1. **`config.py`**: add `load_config_with_warnings(path)` — thread a `warn`
   callable down the helpers (`_clamped_int`/`_str_list`/`_env_name_list`/
   `_normalize_intake_channel`); the new function installs a list-collector
   and emits nothing. `load_config(path)` delegates, then **replays the
   collected warnings to stderr via `_warn`** (pinned contract 6) — legacy
   stderr behavior byte-identical, never silently list-only. Paired
   print/silent assertions added to `tests/test_chatlink_config.sh`.
2. **`preflight.py`**: `CheckResult` dataclass with `category` (pinned
   contract 1b); stable check ids (consumed by t1149_2/t1149_3):
   transport — `config_file`, `config_yaml`, `intake_channel`, `allowlist`,
   `token`; runtime — `docker_binary`, `docker_image`, `config_key:<key>`
   warns; operation — `explore_relay_agent_command`.
3. Move `resolve_explore_relay_argv()` + `parse_dry_run_argv`
   (`daemon.py:700-734`) into `preflight.py`, adding `timeout=None` on the
   `subprocess.run` call. `daemon.py` imports them into its namespace
   (preflight must NOT import daemon — no circular import).
   **Monkeypatch-seam preservation (pinned):** `serve()` passes its own
   module-global reference into the check —
   `check_explore_relay_agent_command(resolver=resolve_explore_relay_argv)` —
   looked up in the **daemon namespace at call time**, so the existing test patch
   `dm.resolve_explore_relay_argv = lambda: ()`
   (`test_chatlink_daemon.sh:1137-1138`) keeps working **unchanged**; that
   test staying green is the proof. `run_expensive_checks()` defaults
   `resolver` to the preflight-local function for TUI use. The daemon
   re-export is therefore behavioral, not cosmetic.
4. Docker image check: `docker image inspect ait-chatlink-agent`
   (`subprocess.run`, timeout, capture) — warn severity, fix hint:
   `docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/`.
   Panel/wizard-only — never called by the daemon (pinned contract 3).
5. **Rewire `serve()`** (`daemon.py:737-784`): run the daemon subset in
   today's order (config → intake → token → agent → docker-binary warn);
   replay collected config warnings to stderr byte-for-byte (pinned
   contract 5); first fail → `_refuse(daemon_refuse_message)`; docker-binary
   warn → same stderr warning text as today; **no timeout passed** (pinned
   contract 4). The allowlist and docker-image checks are NEW panel-only
   checks: the daemon path must NOT run docker-image, NOT refuse on
   allowlist, and NOT add any new stderr output.
6. **Tests**: extend `tests/test_chatlink_daemon.sh` — each refusal path also
   asserts the byte-identical **full stderr sequence** (config-warning lines
   + refusal line; today only rc=2 is asserted), plus a degraded-key config
   start attempt (warnings preserved, no refusal) and a spy negative control
   that daemon startup never invokes the image-inspect seam; the existing
   `dm.resolve_explore_relay_argv` patch stays untouched and green.
   New `tests/test_chatlink_preflight.sh` — result shape (incl. `category`),
   probe split, pinned `daemon_refuse_message` per check id, timeout
   fail-closed behavior via a stub slow command, `timeout=None` waits,
   Textual-free import guard (`import chatlink.preflight` → no `textual` in
   `sys.modules`).
7. **Propagate the scope contract to sibling surfaces** (task-data commit via
   `./ait git`): update the parent plan's pinned-decisions section and the
   t1149_2 / t1149_3 plans+tasks so (a) they consume the bucketed ids
   (`explore_relay_agent_command`, `category` grouping), and (b) panel/wizard
   copy describes configuring **the current Discord bug-report intake /
   explore-relay flow** — not all possible future ChatLink operations.
   (t1149_5 already reuses `CheckResult` and inherits the shape.)

## Risk

### Code-health risk: medium
- Rewiring `serve()` could silently weaken the fail-closed startup validation
  (changed order, lost refusal, lost/duplicated config-warning stderr, new
  stderr noise, an accidental docker-image probe, or a new timeout-refusal
  mode) · severity: medium · → mitigation: in-plan — single-source
  `daemon_refuse_message` + full-stderr-sequence assertions (warnings +
  refusal line) + explicit daemon subset with image-inspect spy negative
  control + `timeout=None` default with no daemon timeout + the existing
  zero-side-effect construction spy.
- Moving the resolver could break the daemon-namespace monkeypatch seam
  (`dm.resolve_explore_relay_argv`) · severity: medium · → mitigation:
  in-plan — `serve()` passes its module-global resolver reference into the
  check; the existing test patch stays unchanged and green as proof.
- Threading a warn-collector through `config.py` helpers could alter warning
  output for existing callers (silent list-only regression) · severity: low ·
  → mitigation: in-plan — `load_config` replays collected warnings to stderr
  (pinned contract 6); paired print/silent assertions in
  `test_chatlink_config.sh`, which must stay green.

### Goal-achievement risk: low
- The result contract might prove insufficient for the panel/wizard consumers
  (missing field) · severity: low · → mitigation: contract pinned in the
  parent plan; sibling children can extend the dataclass additively.

### Planned mitigations
None — both risks are mitigated in-plan by the pinned contracts and tests; no
separate before/after mitigation tasks proposed.

## Verification

- `bash tests/test_chatlink_daemon.sh` — every legacy refusal path byte-identical (full stderr sequence: config-warning lines + refusal line; exit code rc=2); degraded-key config preserves warning lines without refusing; daemon never invokes the image-inspect seam (spy); the pre-existing `dm.resolve_explore_relay_argv` monkeypatch still controls serve(); refuse paths still construct nothing (spy).
- `bash tests/test_chatlink_preflight.sh` — result shape (id + category buckets: transport/runtime/operation, operation id is `explore_relay_agent_command`), probe split, pinned refusal strings, timeout fail-closed via stub slow command, `timeout=None` waits, Textual-free guard.
- Sibling surfaces updated: parent plan + t1149_2/t1149_3 plans reference the bucketed ids and the current-flow-scoped copy.
- `bash tests/test_chatlink_config.sh` — existing config tests green; `load_config_with_warnings` returns the same warnings `_warn` printed.
- `bash tests/test_chatlink_tui.sh` — daemon import guard intact.

Refer to Step 9 (Post-Implementation) of the task workflow for merge/archival.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. New
  `.aitask-scripts/chatlink/preflight.py`: `CheckResult` (id, category,
  severity, message, fix_hint, daemon_refuse_message), category buckets
  `TRANSPORT`/`RUNTIME`/`OPERATION`, `run_cheap_checks() -> CheapChecks`
  (results + config + config_warnings — rich return so the daemon never
  re-loads), per-check expensive functions
  (`check_explore_relay_agent_command(resolver=…, timeout=…) -> (result,
  argv)`, `check_docker_binary()`, `check_docker_image(timeout=…)`),
  `run_expensive_checks(...)` TUI convenience, and the resolver pair
  (`parse_dry_run_argv`, `resolve_explore_relay_argv(timeout=None)`) moved
  from daemon.py. `config.py`: `load_config_with_warnings()` (collect-only,
  silent), `load_config()` replays via `_warn` (byte-identical),
  `emit_warning()` public replay point; `warn` callable threaded through the
  four helpers. `daemon.py`: `serve()` consumes cheap chain + agent check +
  docker-binary check in the legacy order, refuses with
  `res.daemon_refuse_message`, replays config warnings once, never
  references the image check; resolver re-exported and passed from the
  daemon namespace at call time (monkeypatch seam proof: pre-existing test
  patch untouched and green).
- **Deviations from plan:** None material. `run_expensive_checks` takes
  `agent_timeout`/`docker_timeout` (defaulting to the TUI constants) rather
  than a single `timeout` param — per-probe timeouts are truer to pinned
  contract 4. `CheapChecks` is the "rich return" carrier the plan's contract
  implied (daemon needs config + warnings, not just results).
- **Issues encountered:** A bare local `rc` in the new daemon-test block
  shadowed the heredoc's module alias `import chatlink.reconcile as rc`
  (UnboundLocalError in `main()`); renamed the new locals to `rc4`.
- **Key decisions:** (1) The daemon's docker-binary warning stays a literal
  in `serve()` (routed through `check_docker_binary()` for the decision but
  not for the text) — only refusal texts are single-sourced via
  `daemon_refuse_message`; the warn line is byte-pinned by the daemon test
  instead. (2) Image-check negative control is both a runtime spy across all
  serve() validation runs AND a bash structural guard (`grep
  check_docker_image daemon.py` must be empty). (3) Timeout fail-closed is
  tested against a real slow subprocess (stub `ait` + patched
  `paths.project_root`), not a mocked raise.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** t1149_2/t1149_3 consume the shipped API
  documented in their plans (updated in this task): group panel rows by
  `CheckResult.category`; poll only `run_cheap_checks()`; expensive probes
  via the per-check functions or `run_expensive_checks()` with the
  `AGENT_PROBE_TIMEOUT_S`/`DOCKER_PROBE_TIMEOUT_S` constants; per-key config
  warnings appear as `config_key:<key>` warn results ONLY when the config
  loads (fail-closed loads emit a `config_yaml` fail instead, with the raw
  lines still in `CheapChecks.config_warnings`). The wizard's summary screen
  can reuse `check_explore_relay_agent_command`'s returned argv for display.
  Copy stays scoped to the current Discord bug-report intake / explore-relay
  flow (scope/naming contract in the parent plan §1b).
