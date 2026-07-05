---
priority: high
effort: medium
depends: [t1120_1]
issue_type: feature
status: Implementing
labels: [chat_surface, python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1120
created_at: 2026-07-05 11:58
updated_at: 2026-07-05 17:21
---

## Context

Second child of t1120. The config + authorization policy layer above the chat
layer's `IdentityClaims` — the allowlist/policy layer was explicitly deferred by
t1074_1 to this task, and `aidocs/chat/discord_bot_setup.md` explicitly defers
token storage schema, allowed-user/role policy, and channel-routing config here.
Parent plan: `aiplans/p1120_discord_bug_report_channel_integration.md` (§PINNED).

**Contracts: snapshot of parent plan §PINNED — provisional until t1120_1
freeze.** Consumes contracts 9 (policy API), 10 (config & secrets), 11 (ceilings).

## Key deliverables

1. `chatlink/config.py` — schema + loader for shared config
   `aitasks/metadata/chatlink_config.yaml`: intake channel ref (serialized
   `ConversationRef.to_dict()` form), allowed users/roles, repo linkage,
   ceilings (max concurrent sandboxes, per-user intake rate limit, container
   memory/cpus/pids limits, wall-clock cap). Fault-tolerant load with clamping
   (applink `server.py:63-84` pattern).
2. `chatlink/paths.py` — path resolver: runtime state dir
   `aitasks/metadata/chatlink_sessions/` (0o700 enforced via
   `ensure_secure_dir` pattern, applink `paths.py:20-34`), bot-token file
   (0600, gitignored, per-PC). **No env-var names invented outside this task.**
3. `chatlink/policy.py` — `decide(claims: IdentityClaims, config) ->
   Decision{allow: bool, reason: str}`, **deny-by-default** (absent config,
   unknown user, missing claims ⇒ deny with distinct reasons).
   **Initiating-user-only answer gating is a named primitive** here (e.g.
   `may_answer(session_initiator_id, actor_id) -> Decision`), not ad-hoc daemon
   checks.
4. **Secrets hygiene (owned here)**: add/verify `.gitignore` rule for
   `aitasks/metadata/chatlink_sessions/` (mirror how applink_sessions is
   ignored); enforce dir 0700 / token file 0600 on creation.
5. `ait setup` seeding of the config file — read
   `aidocs/framework/aitasks_extension_points.md` before editing
   `aitask_setup.sh` / seed files.

## Reference files for patterns

- `.aitask-scripts/applink/profiles.py` (ProfileGate, tiered YAML profiles) and
  `.aitask-scripts/applink/paths.py` (secure dirs) — the architectural model.
- `.aitask-scripts/chat/model.py:281` — `IdentityClaims` fields (user_id,
  roles[], is_workspace_admin, is_owner, is_channel_member; never invents
  privileges).
- `.aitask-scripts/lib/config_utils.py` `resolve_config_path` +
  `aitask_resolve_config_path.sh` — reuse for settings-defined file paths with
  seeded defaults (do NOT fork a parallel resolver).
- `.aitask-scripts/applink/server.py:42-49` — ceilings-as-constants style.

## Verification

- Pure unit tests: config load/clamp/fault-tolerance; policy deny-by-default
  negative controls (no config, unknown user, role mismatch, non-initiator
  answer attempt — each with its distinct reason); paths permission
  enforcement.
- Secrets hygiene test: `git check-ignore` matches the token path; dir/file
  permissions asserted on creation.
