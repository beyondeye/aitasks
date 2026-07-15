---
Task: t1149_chatlink_config_wizard_tui.md
Worktree: (current branch — fast profile, no worktree)
Branch: current
Base branch: main
---

# t1149 — Chatlink config wizard TUI (decomposition plan)

## Context

Today, configuring the `ait chatlink` gateway is a manual, error-prone dance:
hand-uncommenting the seeded YAML (`aitasks/metadata/chatlink_config.yaml`), a
`mkdir/chmod/printf` token-file ritual, and an unverified `docker build` — all
documented as literal shell in `website/content/docs/workflows/bug-report-intake.md`.
The only validation runs at **daemon startup** (`daemon.serve()` refuse chain,
`.aitask-scripts/chatlink/daemon.py:737`), and its failures print to stderr and
vanish. The TUI (`chatlink_app.py`) is read-only and config-blind — a broken
config just shows "no audit log yet".

**Goal:** make the gateway configurable from inside `ait chatlink` — a
config-status panel plus a step-validated wizard — so errors surface as the user
goes, replacing the hand-edit path (kept as a documented fallback).

This is a large, UX-heavy task. Per the task author's explicit intent and a
confirmed complexity assessment, it is **decomposed into 5 children + 1 aggregate
manual-verification sibling**. The parent creates the children and their plans;
each child is independently implementable and testable.

## Pinned design decisions (apply across children)

1. **Preflight is the shared engine.** A new `chatlink/preflight.py`
   (**Textual-import-free** — guard-tested) is the single source of truth for
   "is this config runnable?". It returns a list of structured check results
   (`id`, `severity` ∈ pass/warn/fail, TUI-friendly `message`, `fix_hint`, and —
   for fail results — `daemon_refuse_message` = the **exact** legacy `_refuse`
   text, see decision 5). Consumed by BOTH the daemon refuse-path
   (behavior-preserving) and the TUI panel/wizard.
   - **Cheap vs expensive probes (pinned to prevent TUI stalls).** Preflight
     splits checks by cost so a passive poller never runs a subprocess. Each
     check declares a **probe level**: `cheap` = pure file/YAML/in-memory
     (config path, YAML parse, `intake_channel`, allowlist non-empty, token file
     present); `expensive` = spawns a process or hits the OS (`resolve_explore_
     relay_argv()` → `ait codeagent … --dry-run`, `shutil.which("docker")`,
     `docker image inspect ait-chatlink-agent`). The API exposes them separately
     (e.g. `run_cheap_checks()` and `run_expensive_checks(timeout=…)`), and every
     expensive probe takes an explicit **timeout** and fails-closed (a
     timeout/OSError → a `fail`/`warn` result, never a hang). The daemon runs
     both (as `serve()` does today, in order); the panel/wizard choose per
     decision 1-panel below.
2. **`load_config` gains a warnings-returning variant.** Today per-key warnings
   go to stderr and are lost. Preflight needs them structured — add a variant
   (e.g. `load_config_with_warnings(path) -> (cfg, list[Warning])`) that collects
   what `_warn()` emits; `load_config` stays as the thin fail-closed wrapper so
   existing callers are unchanged.
3. **YAML writing = merge over the existing file, then write a clean, curated
   file — never drop set-but-unexposed keys.** The wizard exposes intake channel,
   allowlists, `deny_message_mode`, `repo_name`, and the six ceilings. It does
   **not** expose every key (`sandbox_env_passthrough`, and any future key). The
   writer therefore: (a) `yaml.safe_load`s the **existing** config file (if any)
   into a dict; (b) overlays the wizard-edited keys; (c) **carries through
   verbatim every key the wizard did not edit** (including `sandbox_env_
   passthrough` and unknown keys); (d) `yaml.dump`s the merged mapping under a
   fixed curated header comment block. This preserves a user's existing custom
   config and makes drop semantics explicit: *nothing the wizard doesn't touch is
   lost.* (Comment-preserving in-place editing is rejected: it needs `ruamel.yaml`,
   not a repo dep — PyYAML only, per `settings_app.save_profile`; the status panel
   replaces inline comments as the guidance surface.) A writer unit test asserts a
   pre-existing `sandbox_env_passthrough` survives a wizard save untouched.
4. **The wizard writes files only — never commits, never commands the daemon.**
   Per `tui_conventions.md` ("no auto-commit/push of project config from runtime
   TUIs") the wizard writes the config file to the **working tree** and the token
   via `paths.write_token()` (already correct 0700/0600), then tells the user to
   review and commit the config with `./ait git`. The token file is gitignored.
5. **Behavior preservation is a hard contract for child 1, via single-source-of-
   truth (not an implicit mapping).** The daemon's refuse messages and exit codes
   (`_refuse`) must be byte-for-byte unchanged. To make this non-fragile: each
   preflight **fail** result carries the exact legacy refusal text in a
   `daemon_refuse_message` field, and the rewired `serve()` emits
   `_refuse(result.daemon_refuse_message)` for the first failing check **in the
   same order as today** — so the daemon's text/exit code has exactly one
   definition (the preflight result) and the TUI-friendly `message`/`fix_hint`
   cannot drift from it. `tests/test_chatlink_daemon.sh` asserts each refusal
   path's output/exit code is unchanged; a preflight unit test pins the
   `daemon_refuse_message` string per check id.
6. **Daemon stays Textual-free.** Preflight must not import Textual; the wizard
   lives in `chatlink_app.py` (or a sibling module imported only by it).

## Decomposition (children of t1149)

Dependency ordering (children auto-depend on siblings; explicit `depends` set
below). Preflight is the foundation; panel + wizard build on it; docs + live
checks come after.

### t1149_1 — Preflight module (foundation) · depends: none
Extract the daemon's startup check chain + `config.load_config` per-key warnings
into `chatlink/preflight.py` as structured per-check results. Rewire
`daemon.serve()` (`daemon.py:737-769`) to consume preflight, **preserving every
`_refuse()` message and exit code**. Add `load_config_with_warnings` to
`config.py`.
- **Checks to model:** config path resolvable (`paths.config_file()`), YAML
  parses / is a mapping (`load_config`), `intake_channel` valid, allowlist
  non-empty (warn — deny-by-default), token present (`paths.read_token()`),
  agent command resolvable (`resolve_explore_relay_argv()`), docker binary
  present (warn-only), docker image `ait-chatlink-agent` present (new; warn).
- **Key files:** new `chatlink/preflight.py`; edit `chatlink/daemon.py`,
  `chatlink/config.py`. Tests: extend `tests/test_chatlink_daemon.sh`
  (behavior-preserving), new `tests/test_chatlink_preflight.sh` (structured
  results + Textual-free import guard).
- **Reference:** the `_refuse` chain (`daemon.py:737-769`); `_warn` sites in
  `config.py`; applink's analogous startup validation for the results shape.

### t1149_2 — Config-status panel in the TUI · depends: t1149_1
Render preflight results as a visual checklist in `chatlink_app.py` (config file,
intake channel, allowlist, token, agent command, docker binary + image), so
config state is visible at a glance. Replaces the current bare status line's
config-blindness.
- **Cost boundary (pinned — the panel must stay passive/responsive).** The 2s
  polling loop runs **only `run_cheap_checks()`** (file/YAML/in-memory — no
  subprocess). The **expensive** checks (agent dry-run, docker binary, docker
  image) run on a **Textual worker / background thread** (`@work(thread=True)` or
  `run_worker`), with each probe's explicit timeout (decision 1), and their
  results are **cached** and only refreshed on-demand (an explicit key, e.g. the
  existing `r`/refresh, or a first-mount kick) — never on every poll tick. The
  panel shows the last cached expensive result with an age/"checking…" state so a
  slow/absent Docker or a slow dry-run never blocks or hangs the screen.
- **Key files:** `chatlink/chatlink_app.py` (new panel widget + cheap-in-poll /
  expensive-in-worker refresh; keep `__init__` I/O-free per `--smoke` contract).
- **Reference:** existing `_refresh_view`/`_status_text` polling
  (`chatlink_app.py:121-135`); Textual `@work`/`run_worker` for the background
  boundary; TUI render-level test in `test_chatlink_tui.sh` (assert
  `widget.render().plain`, `markup=False`) + a test that the poll path invokes
  no expensive probe (spy on the subprocess/docker seam).

### t1149_3 — Config wizard flow · depends: t1149_1
New Textual ModalScreens launched from the TUI (footer key `w`): intake channel →
allowlist → deny mode / repo name → ceilings (defaults pre-filled) → token entry
(`paths.write_token()`) → final preflight run. Each step validates before
advancing and shows the specific error inline. Writes the merged config file
(decision 3 — overlays edited keys, **preserves all set-but-unexposed keys** like
`sandbox_env_passthrough`) to the working tree; **no commit** (decision 4).
- **Field coverage (pinned).** Wizard-exposed keys: `intake_channel`
  (provider/workspace_id/conversation_id + optional thread_id), `allowed_user_ids`,
  `allowed_role_ids`, `deny_message_mode`, `repo_name`, and the six ceilings
  (`max_concurrent_sandboxes`, `intake_rate_per_user_per_hour`, `sandbox_memory`,
  `sandbox_cpus`, `sandbox_pids`, `sandbox_wall_clock_s`). **Not exposed but
  preserved verbatim:** `sandbox_env_passthrough` and any unknown/future key —
  the writer round-trips them (decision 3). The child plan states this
  preservation contract and tests it.
- **Key files:** `chatlink/chatlink_app.py` (`w` binding + `action_wizard`, or a
  new `chatlink/wizard.py` imported by it); new YAML-writer helper.
- **Reference patterns (all in `settings/settings_app.py`):** ModalScreen +
  `Input` + `on_input_submitted` (995, 1087); multi-step `push_screen(...,
  callback=...)` chaining (1814-1855); inline validation that does NOT dismiss on
  bad input (`AssignGroupScreen._accept_new` 1119-1129); `FuzzySelect` /
  `CycleField` for enum keys (`deny_message_mode`); three-way confirm dismiss
  (`SaveProfileConfirmScreen` 1228). Ceiling ranges/defaults are the constants in
  `config.py:28-42`. Shortcut-scope: `chatlink` module already in
  `KNOWN_BINDING_SOURCES`, so new sub-screens are auto-swept — confirm in
  `tests/test_shortcut_scopes.py`.
- **Tests:** Pilot-driven wizard walk in `test_chatlink_tui.sh`; YAML-writer unit
  test (round-trips through `load_config` unchanged).

### t1149_4 — Docs rewrite · depends: t1149_2, t1149_3
Rewrite the "Configure the gateway" + Walkthrough sections of
`bug-report-intake.md` around the wizard (panel + wizard flow **as actually
shipped by t1149_2 + t1149_3**), keeping the hand-edit YAML / token /
`docker build` path documented as the **fallback**. Add troubleshooting rows the
wizard's *static/offline* preflight now surfaces. Follows
`documentation_conventions.md` (current-state-only, genericize agent names).
- **Scope boundary (pinned).** Document **only** current wizard/panel behavior.
  **No forward references to live Discord validation** — that capability and its
  docs are owned entirely by t1149_5, which updates these same troubleshooting
  rows when it lands. This prevents docs implying a validation capability exists
  before it does, and avoids a second rewrite of freshly changed sections.
- **Key files:** `website/content/docs/workflows/bug-report-intake.md`; check
  `aidocs/chat/chatlink_runtime.md` for maintainer-side notes.

### t1149_5 — Live Discord validation step (optional, riskiest) · depends: t1149_3
Add an optional wizard step that uses `DiscordAdapter.connect(token, guild_id=…)`
(`.aitask-scripts/chat/discord_adapter.py:631`) to verify **live**: token
validity (`client.login` → `discord.LoginFailure`), privileged intents (Message
Content / Server Members), channel visibility, bot permissions — catching the top
troubleshooting rows at config time. Both Textual and discord.py are asyncio.
- **Known feasibility risks (own them in this child's plan):** `connect()` has
  **no `close()`** — this child must build teardown (call the underlying
  `discord.py` client's `close()`); it does **no** explicit intent/visibility/
  permission verification, so this child drives the post-connect helpers
  (`fetch_identity_claims`, `_resolve_channel`, `permissions_for`,
  `member_to_claims`) or reads guild state directly. Run the async connect
  off the Textual event loop (worker/thread) and fail-closed on any error.
- **Key files:** wizard module from t1149_3; possibly a small live-check helper.
  Owns its own doc row additions in `bug-report-intake.md` troubleshooting +
  a note in `aidocs/chat/discord_bot_setup.md`.
- **Tests:** inject a fake adapter (the `_sdk()` seam already supports fakes);
  assert teardown is always called.

### t1149_6 — Aggregate manual-verification sibling (auto-seeded)
Offered after the child plans are committed (N≥2). One `manual_verification`
task covering the human-only behavior of the children that **will definitely
land**: panel render, wizard navigation + per-step validation, token file perms,
config-file merge/preservation on disk. Seeded by
`aitask_create_manual_verification.sh --verifies 1149_2,1149_3` **only**.
- **t1149_5 excluded (pinned).** The optional/deferrable live-checks child is
  **not** in `--verifies` — otherwise a human would be asked to verify a flow
  that may never land this cycle. Live-check manual verification is owned by
  t1149_5 itself: it offers its own standalone manual-verification follow-up at
  its Step 8c when (and only when) it is implemented.

## Risk

### Code-health risk: medium
- The **preflight extraction (t1149_1)** rewrites a load-bearing, fail-closed
  daemon startup path; a mistake could silently weaken startup validation ·
  severity: medium · → mitigation: behavior-preserving contract + guard test
  `test_chatlink_daemon.sh` (owned in t1149_1's plan); TBD if the user wants a
  separate hardening task.
- Parent itself writes no code (creates children) — decomposition confines blast
  radius per child · severity: low · → mitigation: none needed.

### Goal-achievement risk: medium
- **Live-checks feasibility (t1149_5):** async-inside-Textual + the adapter's
  missing `close()` mean teardown must be hand-built; a leaked Gateway connection
  or event-loop clash is plausible · severity: medium · → mitigation: scoped as
  an independent, deferrable child so the wizard ships without it; TBD.
- **Coordination across 5 children** — panel/wizard/live-checks must agree on the
  preflight result shape · severity: low · → mitigation: preflight-first ordering
  pins the contract before consumers are built; aggregate MV sibling validates
  the integrated UX.

_No separate before/after mitigation tasks proposed: the preflight-first ordering,
the per-child guard tests, and the aggregate MV sibling are the mitigation. Each
child re-runs risk evaluation in its own planning._

## Execution (post-approval)

The parent's "implementation" is the decomposition itself:
1. Create t1149_1…t1149_5 via the Batch Task Creation Procedure (`--parent 1149`,
   each with Context / Key Files / Reference Patterns / Implementation Plan /
   Verification per Child Task Documentation Requirements), wiring `depends` as
   above.
2. Revert parent t1149 → `Ready`, clear `assigned_to`, release the parent lock
   (only children get locked when picked).
3. Write per-child plans to `aiplans/p1149/p1149_<n>_<name>.md` and commit them.
4. Offer the aggregate manual-verification sibling (t1149_6) over the
   definitely-landing UX children only (`--verifies 1149_2,1149_3`).
5. Child checkpoint: "Start first child" (`/aitask-pick 1149_1`) or "Stop here".

## Verification

- **Child creation:** `./.aitask-scripts/aitask_ls.sh -v --children 1149 99`
  lists 5 (or 6 with MV) children; parent shows "Has children" and reverts to
  `Ready`; `aiplans/p1149/` holds one plan per child.
- **Per-child (in each child's own session):**
  - t1149_1: `bash tests/test_chatlink_daemon.sh` + new
    `tests/test_chatlink_preflight.sh` pass; daemon refuse messages/exit codes
    unchanged; `import chatlink.preflight` pulls in no Textual.
  - t1149_2 / t1149_3: `bash tests/test_chatlink_tui.sh` (smoke + Pilot render);
    `ait chatlink` shows the status panel; `w` runs the wizard end-to-end and
    writes a config that round-trips through `load_config`.
  - t1149_5: fake-adapter test asserts teardown always runs.
- **Framework guards:** `shellcheck` clean; `tests/test_shortcut_scopes.py`
  (new wizard scope swept); `./.aitask-scripts/aitask_skill_verify.sh` N/A (no
  skill changes).
