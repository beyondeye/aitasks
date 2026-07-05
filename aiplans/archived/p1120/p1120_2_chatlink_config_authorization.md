---
Task: t1120_2_chatlink_config_authorization.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_3_*.md … t1120_8_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_1_relay_protocol_library.md
Worktree: aiwork/t1120_2_chatlink_config_authorization
Branch: aitask/t1120_2_chatlink_config_authorization
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-05 17:47
---

Contracts: snapshot of parent plan §PINNED — **FROZEN as of t1120_1** (child
snapshots authoritative; re-checked this pass, contracts 9/10/11 unchanged).

# Plan: t1120_2 — Chatlink config + authorization policy layer

## Context

Second child of the t1120 Discord bug-report umbrella. Builds the config +
authorization policy layer above the chat layer's `IdentityClaims` — the
allowlist/policy layer explicitly deferred by t1074_1, and the token-storage /
allowed-user / channel-routing config deferred by
`aidocs/chat/discord_bot_setup.md`. Consumes frozen contracts **9** (policy
API), **10** (config & secrets), **11** (ceilings). Consumer: t1120_3's daemon
(loads config — refuse-to-start if missing; reads token for `connect(token)`;
injects `policy`; enforces ceilings).

All new modules are **additive to the existing `.aitask-scripts/chatlink/`
package** (created by t1120_1: `relay.py`, `render.py`, `relay_ask.py`).
`chatlink/__init__.py` is docstring-only — the import-purity guard
(`tests/test_chatlink_relay.sh` Part 2) only covers `chatlink.relay` /
`chatlink.relay_ask`, so gateway-side modules importing `yaml` / `chat` /
`config_utils` are safe. Update the `__init__.py` docstring's module list to
add `paths` / `config` / `policy` (gateway-side).

## Step 1 — `chatlink/paths.py`

Mirror `.aitask-scripts/applink/paths.py` (`project_root()` = 3 levels up;
`ensure_secure_dir` best-effort 0o700, applink `paths.py:20-34`):

- `project_root()`, `metadata_dir()`
- `sessions_dir()` → `aitasks/metadata/chatlink_sessions/` (via
  `ensure_secure_dir` at creation call sites)
- `token_file()` → `<sessions_dir>/bot_token`
- `write_token(token: str)` — write via `ensure_secure_dir(sessions_dir())`,
  then `chmod 0o600` (best-effort, mirroring applink `tls.py` key handling);
  `read_token() -> str | None` (missing/unreadable ⇒ `None`, never raises)
- `relay_root()` → `<sessions_dir>/relay/` (the dir t1120_1's
  `create_session_dir(relay_root)` takes as its argument)
- `config_file() -> Path | None` — reuse
  `lib/config_utils.resolve_config_path("chatlink.config",
  default_rel="aitasks/metadata/chatlink_config.yaml", root=project_root())`
  (do NOT fork a resolver). **`resolve_config_path` returns a repo-root-
  relative string** (`lib/config_utils.py:214-216`) — `config_file()` MUST
  absolutize it: `project_root() / rel` → absolute `Path`, so the t1120_3
  daemon can open it from any cwd (service dir, scratch dir). `None` ⇒ config
  absent ⇒ daemon fail-closed. Covered by a cwd-shifted test (see Testing).
- **Import bootstrap (explicit, not test-only):** `paths.py` imports
  `config_utils` via the guarded pattern precedented by
  `lib/agent_model_picker.py:29-31` / `codebrowser/code_viewer.py:17-19`:
  `try: from config_utils import resolve_config_path` /
  `except ImportError:` insert `Path(__file__).resolve().parent.parent /
  "lib"` into `sys.path` and retry. `chatlink.paths` is then importable with
  only `.aitask-scripts` on `sys.path` (the `PYTHONPATH` the
  `aitask_relay_ask.sh` wrapper already sets) — no hidden coupling on
  entrypoints pre-inserting `lib/`. This is a **contract for t1120_3 and
  future gateway entrypoints**: importing any `chatlink.*` module requires
  only `.aitask-scripts` on the path. (Purity guard unaffected —
  `relay`/`relay_ask` do not import `paths`.)

**No env-var names defined** — v1 has none (token file is the only token
source; relay dir is passed by argv per t1120_1). Recorded here so siblings
know none exist (contract 10: "no env-var names invented outside this task").

## Step 2 — `chatlink/config.py`

Dataclass `ChatlinkConfig` + `load_config(path) -> ChatlinkConfig | None`:

- `intake_channel: dict | None` — the serialized `ConversationRef.to_dict()`
  form. **The loader normalizes to exactly the `to_dict` shape**
  (`chat/model.py:108-116`): required non-empty str keys `provider`,
  `workspace_id`, `conversation_id`; `thread_id` must be str or `None` (else
  ⇒ `None` with warning); `metadata` must be a dict (a scalar/list would
  crash `ConversationRef.from_dict`'s `dict(d.get("metadata", {}))` at
  `model.py:126` in the daemon — invalid ⇒ dropped to `{}` with warning);
  unknown extra keys dropped. **Store as dict** — `config.py` stays
  `chat`-import-free; t1120_3's daemon reconstructs via
  `ConversationRef.from_dict` (round-trip contract, `chat/model.py:95-99`),
  which the normalization guarantees cannot raise. Missing/invalid required
  keys ⇒ `None` field + warning (daemon refuses intake without it).
- `allowed_user_ids: list[str]`, `allowed_role_ids: list[str]` — coerce
  scalars to `str`; drop non-scalar entries with a warning; default `[]`.
- `deny_message_mode: str` — `ignore` (default) | `ephemeral`; unknown value ⇒
  clamped to `ignore` with warning.
- `repo_name: str | None` — optional logical project name for audit/display
  (contract 10 "repo linkage"; the gateway is per-workspace like applink, so
  the operative repo is the one the config lives in — this field is label
  metadata only, default `None`).
- Ceilings (contract 11), each an int/str field with default + clamp range:
  `max_concurrent_sandboxes` 2 (1–16), `intake_rate_per_user_per_hour` 4
  (1–60), `sandbox_memory` `"2g"` (validated regex `^[0-9]+[kmg]$`, else
  default), `sandbox_cpus` 2 (1–16), `sandbox_pids` 512 (16–4096),
  `sandbox_wall_clock_s` 1800 (60–14400).

Fault-tolerant load (applink `server.py:63-94` pattern): **missing/unreadable/
malformed-YAML file ⇒ return `None`** (fail-closed — daemon refuses to start
with a clear message); a present file with bad values ⇒ each key degrades
independently to its clamped default with a warning (never raises).
PyYAML via `import yaml` inside the loader (gateway runs in the CPython venv).

## Step 3 — `chatlink/policy.py`

- `Decision` dataclass `{allow: bool, reason: str}`. Machine-readable reasons
  (complete enum): `no_config`, `no_claims`, `not_channel_member`,
  `user_not_allowed`, `role_not_allowed`, `not_initiator`, `ok_user`,
  `ok_role`, `ok_initiator`.
- `decide(claims, config) -> Decision` — **deny-by-default**, never invents
  privileges (`chat/model.py:281-301` semantics: absent knowledge = False):
  1. `config is None` ⇒ deny `no_config`
  2. `claims is None` or empty `claims.user_id` ⇒ deny `no_claims`
  3. `not claims.is_channel_member` ⇒ deny `not_channel_member`
  4. `claims.user_id ∈ allowed_user_ids` ⇒ allow `ok_user`
  5. any `role.id ∈ allowed_role_ids` for `role in claims.roles` ⇒ allow
     `ok_role`
  6. else: `allowed_role_ids` non-empty ⇒ deny `role_not_allowed`; otherwise
     deny `user_not_allowed` (covers both-lists-empty — absent config ⇒ deny)
- `may_answer(session_initiator_id, actor_id) -> Decision` — the **named
  initiating-user-only primitive** (contract 9): both non-empty and equal ⇒
  allow `ok_initiator`; anything else (mismatch, empty, `None`) ⇒ deny
  `not_initiator` (fail-closed).
- Type annotations reference `IdentityClaims` under `TYPE_CHECKING` only —
  `decide` uses attribute access, keeping `policy.py` import-light; role
  matching is on `Role.id` (`chat/model.py:275`), platform-honest (Discord
  role ids / Slack usergroup ids both flow through `Role.kind`-tagged claims).

## Step 4 — setup seeding + secrets hygiene

Per `aidocs/framework/aitasks_extension_points.md` (read this pass):

1. **`seed/chatlink_config.yaml`** — fully commented template documenting
   every key, defaults, and the `intake_channel` dict shape.
2. **`install.sh`**: `install_seed_chatlink_config()` mirroring
   `install_seed_gates_registry` (`install.sh:435-446`) + call at its call
   site (fresh installs get the file before `seed/` is deleted).
3. **`.aitask-scripts/aitask_setup.sh`** (populate-missing = `ait setup`
   verb, not `upgrade`):
   - add `cp "$project_dir/seed/chatlink_config.yaml" …/metadata/` line in
     the `setup_data_branch` seed block (`aitask_setup.sh:1332-1345`);
   - new `ensure_chatlink_config()` mirroring the seed-fallback path of
     `ensure_project_config_defaults` (`aitask_setup.sh:1523-1544`): target
     missing + seed present ⇒ copy; called from main next to
     `ensure_project_config_defaults` (~line 3202);
   - new data-branch `.gitignore` append block for
     `aitasks/metadata/chatlink_sessions/` alongside the existing blocks
     (`aitask_setup.sh:1348-1382`), comment `# chatlink runtime state
     (per-PC: bot token + relay spools)`.
4. **This repo now**: append the same rule to `.aitask-data/.gitignore` and
   commit via `./ait git` (mirror of applink's commit `9df76f759`; applink's
   rule lives at `.aitask-data/.gitignore:14` — there is NO repo-root
   `.gitignore` rule and NO setup seeding for applink_sessions; legacy-mode
   (no data branch) ignore rule is out of scope, matching applink's posture —
   the runtime dir is 0700 regardless).
5. No new skill-invoked shell helper ⇒ the 7-touchpoint permission whitelist
   does not apply (config/policy/paths are Python modules consumed by the
   t1120_3 daemon).

⚠️ **Never run `ait setup` in this repo during verification** (it sweeps a
dirty tree into an auto-commit — t1128). Fresh-install verification runs only
in a scratch dir.

## Testing

New `tests/test_chatlink_config.sh` (self-contained bash + inline Python,
pattern: `tests/test_chatlink_relay.sh`), pure — no chat adapter, no network:

- **Config**: valid load; **missing file ⇒ `None`**; malformed YAML ⇒ `None`
  (fail-closed); per-key clamp negative controls (string ceiling, negative,
  over-max, bad `sandbox_memory`, unknown `deny_message_mode`) each degrading
  independently; invalid `intake_channel` shape ⇒ field `None`, rest loads;
  **metadata normalization**: scalar/list `metadata` ⇒ `{}` with warning, and
  the normalized dict feeds `ConversationRef.from_dict` without raising
  (round-trip positive control, imports `chat` in the test only).
- **cwd independence**: run inline Python with `cwd` shifted to a temp dir
  outside the repo (subprocess `cwd=` param); assert `paths.config_file()`
  returns an **absolute** path and `load_config(config_file())` succeeds —
  guards the relative-path integration bug.
- **Import bootstrap**: subprocess with `sys.path` containing only
  `.aitask-scripts` (no explicit `lib/` entry); `import chatlink.paths` and
  call `config_file()` — proves the guarded `config_utils` import works for
  any entrypoint.
- **Policy negative controls** (each asserting its distinct reason):
  no config, no claims, non-channel-member, unknown user, role mismatch,
  non-initiator answer attempt (incl. empty/None actor); positives: allowed
  user (`ok_user`), allowed role (`ok_role`), initiator (`ok_initiator`).
- **Paths/permissions**: sessions dir 0o700 after creation; token file 0o600
  after `write_token`; `read_token` on missing file ⇒ `None`.
- **Secrets hygiene**: `git -C .aitask-data check-ignore
  aitasks/metadata/chatlink_sessions/bot_token` succeeds (graceful skip when
  `.aitask-data` absent — legacy checkouts).
- **Import posture**: existing `tests/test_chatlink_relay.sh` still passes
  (purity guard unaffected by the new gateway-side modules).
- **Setup flow** (per extension-points doc, once during implementation):
  simulate a fresh install into a scratch dir and confirm
  `chatlink_config.yaml` lands via `install_seed_chatlink_config`; run
  `ensure_chatlink_config` against a scratch tree missing the target.
- `shellcheck` on edited `install.sh` / `aitask_setup.sh`.

## Verification notes (2026-07-05, pre-implementation verify pass)

- Contract 0 **FROZEN as of t1120_1**; contracts 9/10/11 match this snapshot.
- `chatlink/` exists (t1120_1) — plan adjusted from "new package" to additive
  modules; `__init__.py` docstring-only, purity guard scope confirmed
  (`tests/test_chatlink_relay.sh:409-447`).
- applink anchors confirmed: `ensure_secure_dir` `paths.py:20-34`; ceilings
  constants `server.py:36-60`; fault-tolerant clamp loader `server.py:63-94`.
- `IdentityClaims` `chat/model.py:282` (user_id, roles[], is_workspace_admin,
  is_owner, is_channel_member); `Role.id/.name/.kind` `model.py:260-278`;
  `ConversationRef.to_dict/from_dict` round-trip `model.py:83-127`.
- `resolve_config_path` `lib/config_utils.py:175` + existing
  `aitask_resolve_config_path.sh` CLI — reused, not forked. **Returns a
  repo-root-relative string** (`:214-216`); `config_file()` absolutizes
  against `project_root()` (plan-review finding).
- `ConversationRef.from_dict` `model.py:126` does
  `dict(d.get("metadata", {}))` — raises on scalar metadata; loader
  normalization guards it (plan-review finding).
- Guarded `sys.path` bootstrap precedent: `lib/agent_model_picker.py:29-31`,
  `codebrowser/code_viewer.py:17-19`; the `aitask_relay_ask.sh` wrapper
  already sets `PYTHONPATH=.aitask-scripts` only (plan-review finding).
- applink_sessions gitignore lives ONLY at `.aitask-data/.gitignore:14`
  (manual commit `9df76f759`); no setup seeding exists for it — chatlink adds
  the setup-side block (gap not replicated).
- Seeding pattern anchors: `install.sh:435-446` (`install_seed_gates_registry`),
  `aitask_setup.sh:1332-1345` (data-branch seed copies), `:1348-1382`
  (gitignore append blocks), `:1523-1544` (`ensure_project_config_defaults`).
- t1120_3 pending plan expectations align (load-or-refuse, `connect(token)`,
  injected policy, ceilings enforcement).

## Risk

### Code-health risk: low
- New code is additive gateway-side modules in the greenfield `chatlink/`
  package; the only shared-file edits are append-style blocks in
  `aitask_setup.sh` / `install.sh` mirroring existing seeding patterns ·
  severity: low · → mitigation: embedded (scratch-dir fresh-install check per
  `aidocs/framework/aitasks_extension_points.md`; shellcheck; existing relay
  test re-run guards the package's import posture)

### Goal-achievement risk: low
- Policy semantics (role-id matching, reason taxonomy) could drift from what
  t1120_3's daemon expects; contracts are frozen and the reason enum is
  pinned here with per-reason negative controls · severity: low · →
  mitigation: embedded (complete reason enum + one test per deny path;
  t1120_3 plan cross-checked this pass)
- `intake_channel` kept as a validated dict (not a `ConversationRef`) — a
  deliberate layering choice; if t1120_3 prefers a typed ref, the round-trip
  contract makes the conversion one line · severity: low · → mitigation:
  embedded (shape validation mirrors `to_dict` exactly)

## Step 9 reference

Post-implementation follows task-workflow Step 9 (merge/verify/archive push).

## Final Implementation Notes

- **Actual work done:** Exactly the planned deliverables: gateway-side
  modules `.aitask-scripts/chatlink/paths.py` (secure dirs 0700, token
  read/write 0600, `relay_root()`, absolute `config_file()` via
  `resolve_config_path` with guarded `lib/` import bootstrap), `config.py`
  (`ChatlinkConfig`, fail-closed `load_config`, per-key clamped ceilings,
  `intake_channel` normalized to the exact `ConversationRef.to_dict()`
  shape), `policy.py` (`Decision`, deny-by-default `decide()` with the
  complete 9-reason enum, named `may_answer()` primitive); `__init__.py`
  docstring updated; `seed/chatlink_config.yaml` commented template;
  `install.sh` `install_seed_chatlink_config()` + call; `aitask_setup.sh`
  data-branch seed copy + `ensure_chatlink_config()` populate-missing +
  `chatlink_sessions/` data-branch gitignore append block; this repo's
  `.aitask-data/.gitignore` rule + seeded config committed via `./ait git`;
  `tests/test_chatlink_config.sh` (58 Python checks + cwd-independence,
  import-bootstrap, and git check-ignore hygiene parts — all pass).
- **Deviations from plan:** (1) This repo's `aitasks/metadata/
  chatlink_config.yaml` was seeded directly (with the gitignore commit)
  rather than waiting for a future `ait setup` run — `ait setup` is unsafe
  to run on a dirty tree here (t1128) and t1120_3 needs the file present;
  `ensure_chatlink_config` now no-ops (target exists). (2) The fresh-install
  verification drove the real `install_seed_chatlink_config` /
  `ensure_chatlink_config` function bodies (sed-extracted from the live
  scripts) in scratch layouts instead of a full network `install.sh` run
  (release tarballs are git-tag archives — uncommitted work can't ship into
  one); copy, keep-existing, idempotence, and missing-seed-warn paths all
  verified.
- **Issues encountered:** none blocking. Foreign concurrent-session hunks
  were present on both the main worktree and the data branch throughout —
  all commits were path-scoped and staged-content-verified.
- **Key decisions:** `config_file()` returns an **absolute** Path
  (resolve_config_path returns repo-root-relative — plan-review finding);
  `intake_channel` stored as a normalized dict (chat-import-free config
  layer; metadata-scalar guard against `from_dict` crash); bool ceilings
  rejected as typos (bool is an int subclass); v1 defines **no env vars**
  (token file is the only token source); `chatlink.*` import contract =
  only `.aitask-scripts` on `sys.path` (guarded `config_utils` bootstrap in
  `paths.py`).
- **Upstream defects identified:** `aitask_setup.sh:1348-1382 — no
  data-branch gitignore append block seeds
  aitasks/metadata/applink_sessions/ for fresh installs (the applink rule
  exists only as a manual commit on this repo's data branch, 9df76f759; a
  fresh downstream project pairing applink could commit its TLS key +
  session table). The equivalent chatlink block added by this task shows
  the fix shape.`
- **Notes for sibling tasks:** t1120_3 daemon: `paths.config_file()` →
  `config.load_config()` — `None` from either ⇒ refuse to start (distinct
  messages); reconstruct the intake ref via `ConversationRef.from_dict(
  config.intake_channel)` (normalization guarantees it cannot raise);
  `policy.decide(claims, config)` / `policy.may_answer(initiator, actor)`
  are the only authorization call sites (never re-derive); branch on the
  REASON_* constants, not string literals; `paths.read_token()` for
  `connect(token)`; `paths.relay_root()` is the `create_session_dir` arg;
  ceilings come clamped — enforce, don't re-validate. Token provisioning
  UX (how the user first writes `bot_token`) is t1120_6/t1120_7 territory:
  `paths.write_token()` is ready for it.
