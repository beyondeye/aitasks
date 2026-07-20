---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1149
created_at: 2026-07-20 19:29
updated_at: 2026-07-20 22:59
---

## Context

First slice of t1186 (chatlink wizard live allowlist pickers). Introduces per-dimension
authorization modes into the chatlink runtime BEFORE any wizard UI exists (the wizard UI
lands in t1186_4; step reorder in t1186_3; fetch surface in t1186_2). The four t1186
children are strictly sequential slices of one feature — this child is not independently
shippable as a user-facing feature, and that is by design: hand-editing the config file
is already the only way to set the new fields, `config_write`'s merge-never-drop
preserves them through wizard saves, and this child adds a preflight posture row so
hand-edited modes are inspectable before the wizard exposes them.

User decision (2026-07-20): two new config fields `user_authorization_mode` and
`role_authorization_mode`, each `allowlist | denylist`, both default `allowlist`
(existing configs keep today's exact fail-closed behavior). `allowlist`: listed ids
allowed, empty list grants nobody. `denylist`: listed ids blocked, empty list blocks
nobody. Error paths stay fail-closed in every combination: `no_config`, `no_claims`
(claims-fetch failure), `not_channel_member` deny first.

## Pinned decision table (contract — transcribe into a table-driven test)

Composition rule precedence: explicit deny > explicit allow > default.

| user mode | role mode | evaluation order | default (no match) | reason codes in play |
|-----------|-----------|------------------|--------------------|----------------------|
| allowlist | allowlist | user∈allowed→allow; role∈allowed→allow | deny (`role_not_allowed` if allowed_roles non-empty else `user_not_allowed`) | ok_user, ok_role, role_not_allowed, user_not_allowed |
| denylist  | denylist  | user∈denied→deny; role∈denied→deny | allow `ok_not_denied` | user_denied, role_denied, ok_not_denied |
| denylist  | allowlist | user∈denied→deny; role∈allowed→allow | deny (`role_not_allowed` if allowed_roles non-empty else `user_not_allowed`) | user_denied, ok_role, role_not_allowed, user_not_allowed |
| allowlist | denylist  | role∈denied→deny; user∈allowed→allow | deny `user_not_allowed` | role_denied, ok_user, user_not_allowed |

Degenerate deny-all postures (fail-closed by design; loudly warned, never silent — an
empty allowlist dimension makes the default restrictive, so denylist entries become
meaningless): (a) allowlist/allowlist both allowed lists empty (today's pinned default);
(b) denylist/allowlist with `allowed_role_ids` empty; (c) allowlist/denylist with
`allowed_user_ids` empty. Open-access posture: denylist/denylist with both denied lists
empty allows every channel member. The fail-closed degenerate default was deliberately
chosen over "empty allowlist dimension is inactive", whose degenerate case is fail-open
(a non-empty role allowlist silently becoming decorative) — the worse failure mode.

## Key files to modify

- `.aitask-scripts/chatlink/config.py` — `ChatlinkConfig` gains
  `user_authorization_mode: str = "allowlist"`, `role_authorization_mode: str = "allowlist"`,
  `denied_user_ids: list[str] = []`, `denied_role_ids: list[str] = []` (near lines 74-76).
  Parse in `load_config_with_warnings` (return block ~:249-298): each mode validated
  against `{"allowlist","denylist"}` mirroring the `deny_mode` string-enum pattern
  (:224-230; bad value → default + warning); denied lists via `_str_list` (:112-127).
- `.aitask-scripts/chatlink/policy.py` — `decide()` (:48-67): keep the first three
  denies, then implement the pinned composition rule exactly as in the table above.
  New constants `REASON_USER_DENIED = "user_denied"`, `REASON_ROLE_DENIED = "role_denied"`,
  `REASON_OK_NOT_DENIED = "ok_not_denied"`. New pure helper
  `effective_posture(config) -> "deny_all" | "open_members" | "restricted"` classifying
  the postures ONCE (single source for preflight, wizard t1186_4, tests). Update module
  docstring (deny-by-default is the all-allowlist default; precedence pinned).
- `.aitask-scripts/chatlink/preflight.py` — rebuild the allowlist row group (:240-251)
  on `effective_posture()`: `deny_all` → WARN naming the degenerate posture explicitly
  (all three deny-all combos; mixed ones say "denylist has no effect — the empty
  <dimension> allowlist denies everyone; fill it or switch it to denylist");
  `open_members` → WARN "open access: any channel member can open a bug report";
  `restricted` → PASS row showing per-dimension posture
  (`users: <mode> (<n> ids) / roles: <mode> (<n> ids)`). Plus per-dimension consistency
  WARN when an inactive list is non-empty (e.g. `denied_user_ids` set while
  `user_authorization_mode` is `allowlist` — ignored field). Never a FAIL /
  `daemon_refuse_message`.
- Docs (document both modes + precedence; default stays deny-by-default):
  `seed/chatlink_config.yaml` :28-35 (add both mode keys + `denied_*` with comments +
  precedence rule); `.aitask-scripts/chatlink/__init__.py:13`;
  `aidocs/chat/chatlink_runtime.md` :101-113 (+ new reasons in the reason table);
  `website/content/docs/workflows/bug-report-intake.md` :103-106.

## Reference files for patterns

- `deny_mode` string-enum validation: `config.py:224-230`.
- Deny-reason negative controls: `tests/test_chatlink_config.sh:254-300`.
- Preflight row shape (`CheckResult`, WARN vs FAIL): `preflight.py:216-251`,
  `tests/test_chatlink_preflight.sh:107-114`.
- Runtime call site (unchanged, for understanding): `intake.py:184-196`.

## Implementation plan

1. Config fields + parsing + validation warnings.
2. Policy constants, `decide()` composition rule, `effective_posture()` helper, docstring.
3. Preflight posture-derived rows + inactive-list WARNs.
4. Docs (4 surfaces).
5. Tests (see Verification).

## Verification

- `tests/test_chatlink_config.sh`: existing allowlist negative controls (:254-289) must
  pass UNCHANGED. Add: table-driven test transcribing the pinned decision table verbatim
  (mode combos × empty/non-empty lists × listed/unlisted member → allow flag + reason);
  mode parsing (defaults, explicit, invalid→default+warn); deny-precedence controls
  (users=allowlist:[U] + roles=denylist:[Y] with U holding Y → denied; denied X-holder
  under users=denylist + roles=allowlist:[X] → denied); the three degenerate deny-all
  postures each denying a plain channel member (incl. the surprising
  users=denylist + roles=allowlist:[] case); both-denylist-empty → allow;
  non-channel-member → `not_channel_member` in every combination; `effective_posture()`
  unit-tested over the full table.
- `tests/test_chatlink_preflight.sh`: update :112 to the posture-derived row; add the
  two mixed degenerate-posture WARNs, the open-access WARN, the restricted PASS row,
  and the ignored-inactive-list WARN.
- `bash tests/test_chatlink_wizard.sh` and `bash tests/test_chatlink_tui.sh` stay green
  (no wizard changes in this child; the existing empty-allowlist wizard warning still
  reflects the default allowlist/allowlist posture).
