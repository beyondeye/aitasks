---
Task: t1120_2_chatlink_config_authorization.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_1_*.md … t1120_7_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_*_*.md
Worktree: aiwork/t1120_2_chatlink_config_authorization
Branch: aitask/t1120_2_chatlink_config_authorization
Base branch: main
---

Contracts: snapshot of parent plan §PINNED — provisional until t1120_1 freeze.

# Plan: t1120_2 — Chatlink config + authorization policy layer

Deliverables, consumed contracts (9/10/11), and reference anchors are in the
task file (`aitasks/t1120/t1120_2_chatlink_config_authorization.md`). Read
t1120_1's archived plan first (`aiplans/archived/p1120/p1120_1_*.md`) — it may
have revised contracts (freeze rule).

## Step 1 — `chatlink/paths.py`

Mirror `applink/paths.py`: `chatlink_sessions_dir()` →
`aitasks/metadata/chatlink_sessions/` with `ensure_secure_dir` (0o700);
`token_file()` → `<sessions_dir>/bot_token` (0600 on write);
`relay_root()` → `<sessions_dir>/relay/`; `config_file()` →
`aitasks/metadata/chatlink_config.yaml`. Reuse
`lib/config_utils.resolve_config_path` for the config file (seeded default —
do not fork a resolver).

## Step 2 — `chatlink/config.py`

Dataclass `ChatlinkConfig`: `intake_channel` (serialized `ConversationRef`
dict — `provider/workspace_id/conversation_id`), `allowed_user_ids: list`,
`allowed_role_ids: list`, `deny_message_mode: ignore|ephemeral`, ceilings
(`max_concurrent_sandboxes` default 2, `intake_rate_per_user_per_hour` default
4, `sandbox_memory` "2g", `sandbox_cpus` 2, `sandbox_pids` 512,
`sandbox_wall_clock_s` 1800). Fault-tolerant load: missing file ⇒ `None`
(daemon refuses to start with a clear message — fail-closed); bad values ⇒
clamped with a warning (applink `server.py:63-84` style). Ship a commented
seed template (see Step 4).

## Step 3 — `chatlink/policy.py`

- `Decision` dataclass `{allow: bool, reason: str}` (distinct machine-readable
  reasons: `no_config`, `user_not_allowed`, `role_not_allowed`,
  `not_channel_member`, `not_initiator`, `ok_user`, `ok_role`).
- `decide(claims: IdentityClaims, config) -> Decision` — deny-by-default:
  allow only if `claims.user_id ∈ allowed_user_ids` OR any
  `claims.roles[].id ∈ allowed_role_ids`; require `is_channel_member`;
  empty/missing config or claims ⇒ deny. Never invent privileges (claims
  absent ⇒ False, per `chat/model.py:281` semantics).
- `may_answer(initiator_id, actor_id) -> Decision` — the named
  initiating-user-only primitive (contract 9); actor≠initiator ⇒
  `not_initiator`.

## Step 4 — setup seeding + secrets hygiene

- Read `aidocs/framework/aitasks_extension_points.md`, then wire seeding of
  `chatlink_config.yaml` (commented template) into `aitask_setup.sh` the same
  way applink profiles/metadata files are seeded; populate-missing semantics
  (`ait setup` verb, not `upgrade`).
- `.gitignore`: verify/add the rule covering
  `aitasks/metadata/chatlink_sessions/` exactly as `applink_sessions` is
  ignored (check both repo `.gitignore` and any data-branch ignore file — copy
  applink's placement).

## Testing

Bash test script: config load/clamp/missing-file fail-closed; every deny
reason as its own negative control; `may_answer` non-initiator; permissions
(dir 0700, token 0600 after create); `git check-ignore
aitasks/metadata/chatlink_sessions/bot_token` succeeds. Pure — no chat
adapter, no network.

## Step 9 reference

Post-implementation follows task-workflow Step 9.
