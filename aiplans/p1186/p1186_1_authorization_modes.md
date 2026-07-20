---
Task: t1186_1_authorization_modes.md
Parent Task: aitasks/t1186_chatlink_wizard_allowlist_live_pickers.md
Sibling Tasks: aitasks/t1186/t1186_2_discord_fetch_surface.md, aitasks/t1186/t1186_3_wizard_step_reorder.md, aitasks/t1186/t1186_4_allowlist_picker_ui.md
Archived Sibling Plans: aiplans/archived/p1186/p1186_*_*.md
Worktree: (profile 'fast' — current branch)
Branch: main
Base branch: main
---

# p1186_1 — Per-dimension authorization modes (config + policy + preflight + docs + tests)

First sequential slice of t1186. Lands runtime semantics before the wizard UI exists
(t1186_4). Not independently user-shippable by design; a preflight posture row makes
hand-edited mode fields inspectable in the interim. The parent plan
(`aiplans/p1186_chatlink_wizard_allowlist_live_pickers.md`) carries the full context and
the **pinned decision table** — transcribe that table verbatim into a table-driven test.

## Contract (pinned)

Two new config fields `user_authorization_mode` / `role_authorization_mode`
(`allowlist | denylist`, both default `allowlist` — existing configs behave exactly as
today). New lists `denied_user_ids` / `denied_role_ids`. Composition precedence:
explicit deny > explicit allow > default; default allows (`ok_not_denied`) only when
BOTH dimensions are denylist, else denies (`role_not_allowed` if role dimension is
allowlist with a non-empty list, else `user_not_allowed`). `no_config` / `no_claims` /
`not_channel_member` always deny first. Degenerate deny-all postures (both-allowlist
empty; denylist/allowlist with empty allowed_role_ids; allowlist/denylist with empty
allowed_user_ids) are fail-closed by design and loudly warned. Open-access posture:
both-denylist with both denied lists empty.

## Steps

1. **config.py** — add the four fields to `ChatlinkConfig` (near :74-76); parse in
   `load_config_with_warnings` return block (:249-298): modes validated against
   `{"allowlist","denylist"}` per the `deny_mode` string-enum pattern (:224-230, bad
   value → default + warning); denied lists via `_str_list` (:112-127).
2. **policy.py** — constants `REASON_USER_DENIED="user_denied"`,
   `REASON_ROLE_DENIED="role_denied"`, `REASON_OK_NOT_DENIED="ok_not_denied"`;
   rewrite the tail of `decide()` (:61-67) to the pinned rule; add pure
   `effective_posture(config) -> "deny_all" | "open_members" | "restricted"`
   (single source of posture truth for preflight, wizard t1186_4, tests); update module
   docstring.
3. **preflight.py** — rebuild the allowlist row group (:240-251) on
   `effective_posture()`: deny_all WARN (names the degenerate combo; mixed cases:
   "denylist has no effect — the empty <dimension> allowlist denies everyone; fill it
   or switch it to denylist"); open_members WARN ("open access: any channel member can
   open a bug report"); restricted PASS row (`users: <mode> (<n> ids) / roles: <mode>
   (<n> ids)`); per-dimension inactive-list-non-empty WARN. Never FAIL / no
   `daemon_refuse_message`.
4. **Docs** — `seed/chatlink_config.yaml:28-35` (mode keys + denied_* + precedence
   comment); `.aitask-scripts/chatlink/__init__.py:13`;
   `aidocs/chat/chatlink_runtime.md:101-113` (+ reason-table rows);
   `website/content/docs/workflows/bug-report-intake.md:103-106`.
5. **Tests** — `test_chatlink_config.sh`: existing controls :254-289 UNCHANGED;
   add table-driven decision-table test, mode parsing, deny-precedence controls,
   three degenerate-posture controls, both-denylist-empty allow, not_channel_member in
   every combo, `effective_posture()` over the full table.
   `test_chatlink_preflight.sh`: posture-derived rows (see task file).

## Verification

All four chatlink test files green; wizard/TUI untouched in this child (the existing
empty-allowlist wizard warning still matches the default posture).

Post-implementation per task-workflow Step 9 (gates incl. risk_evaluated; archive via
`aitask_archive.sh 1186_1`).
