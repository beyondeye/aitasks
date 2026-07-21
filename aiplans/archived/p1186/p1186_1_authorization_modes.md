---
Task: t1186_1_authorization_modes.md
Parent Task: aitasks/t1186_chatlink_wizard_allowlist_live_pickers.md
Sibling Tasks: aitasks/t1186/t1186_2_discord_fetch_surface.md, aitasks/t1186/t1186_3_wizard_step_reorder.md, aitasks/t1186/t1186_4_allowlist_picker_ui.md, aitasks/t1186/t1186_5_manual_verification_chatlink_wizard_allowlist_live_pickers.md
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-21 06:22
---

# p1186_1 — Per-dimension authorization modes (config + policy + preflight + docs + tests)

First sequential slice of t1186. Lands runtime semantics before the wizard UI exists
(t1186_4). Not independently user-shippable by design; a preflight posture row makes
hand-edited mode fields inspectable in the interim. The parent plan
(`aiplans/p1186_chatlink_wizard_allowlist_live_pickers.md`) carries the full context and
the **pinned decision table** — transcribe that table verbatim into a table-driven test.

**Plan verified 2026-07-20:** all file/line anchors re-checked against current source —
`config.py` fields :74-76, `_str_list` :112-127, `deny_mode` enum pattern :224-230,
return block :249-298; `policy.decide()` :48-67; `preflight.py` allowlist row group
:240-251; `seed/chatlink_config.yaml` :28-35; `__init__.py:13`;
`aidocs/chat/chatlink_runtime.md` :101-113; `website/content/docs/workflows/bug-report-intake.md`
:95-112 (key table + deny-by-default paragraph); `tests/test_chatlink_config.sh`
policy controls :250-301; `tests/test_chatlink_preflight.sh:112`. All current; no
drift; plan unchanged apart from this note and the `## Risk` section.

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

Pinned decision table (from the task file — transcribe verbatim into the table-driven
test):

| user mode | role mode | evaluation order | default (no match) | reason codes in play |
|-----------|-----------|------------------|--------------------|----------------------|
| allowlist | allowlist | user∈allowed→allow; role∈allowed→allow | deny (`role_not_allowed` if allowed_roles non-empty else `user_not_allowed`) | ok_user, ok_role, role_not_allowed, user_not_allowed |
| denylist  | denylist  | user∈denied→deny; role∈denied→deny | allow `ok_not_denied` | user_denied, role_denied, ok_not_denied |
| denylist  | allowlist | user∈denied→deny; role∈allowed→allow | deny (`role_not_allowed` if allowed_roles non-empty else `user_not_allowed`) | user_denied, ok_role, role_not_allowed, user_not_allowed |
| allowlist | denylist  | role∈denied→deny; user∈allowed→allow | deny `user_not_allowed` | role_denied, ok_user, user_not_allowed |

## Steps

1. **config.py** — add the four fields to `ChatlinkConfig` (near :74-76); parse in
   `load_config_with_warnings` return block (:249-298): modes validated against
   `{"allowlist","denylist"}` per the `deny_mode` string-enum pattern (:224-230, bad
   value → default + warning); denied lists via `_str_list` (:112-127).
2. **policy.py** — constants `REASON_USER_DENIED="user_denied"`,
   `REASON_ROLE_DENIED="role_denied"`, `REASON_OK_NOT_DENIED="ok_not_denied"`;
   rewrite the tail of `decide()` (:61-67) to the pinned rule; add pure
   `effective_posture(config) -> Posture` where `Posture` is a small frozen dataclass:
   `kind: str` (`"deny_all" | "open_members" | "restricted"`) plus
   `degenerate_dimensions: tuple[str, ...]` naming the dimension(s) whose empty active
   allowlist caused a `deny_all` — `("users", "roles")` for both-allowlist-empty,
   `("roles",)` for denylist/allowlist with empty `allowed_role_ids`, `("users",)` for
   allowlist/denylist with empty `allowed_user_ids`, `()` otherwise. This keeps the
   classification single-sourced *including the cause*: preflight and the wizard
   (t1186_4) consume the facts and only render copy — neither re-derives which combo
   is degenerate. Update module docstring (deny-by-default is the all-allowlist
   default; precedence pinned).
3. **preflight.py** — rebuild the allowlist row group (:240-251) on
   `effective_posture()`: deny_all WARN (message derives the named combo/dimension
   from `Posture.degenerate_dimensions` — mixed cases: "denylist has no effect — the
   empty <dimension> allowlist denies everyone; fill it or switch it to denylist");
   open_members WARN ("open access: any channel member can open a bug report");
   restricted PASS row (`users: <mode> (<n> ids) / roles: <mode> (<n> ids)`).
   Per-dimension inactive-list-non-empty WARN covering **both directions × both
   dimensions** (each dimension consults only its mode's active list, so the other is
   ignored — 4 stale-config cases): `denied_user_ids` set while
   `user_authorization_mode=allowlist`; `allowed_user_ids` set while
   `user_authorization_mode=denylist` (the most likely mode-toggle mistake — values
   look restrictive but are ignored); and the same two for the role dimension. Never
   FAIL / no `daemon_refuse_message`.
4. **Docs** — `seed/chatlink_config.yaml:28-35` (mode keys + denied_* + precedence
   comment); `.aitask-scripts/chatlink/__init__.py:13`;
   `aidocs/chat/chatlink_runtime.md:101-113` (+ reason-table rows);
   `website/content/docs/workflows/bug-report-intake.md` key table + deny-by-default
   paragraph (:95-112).
5. **Tests** — `test_chatlink_config.sh`: existing controls :250-301 UNCHANGED;
   add table-driven decision-table test, mode parsing (defaults, explicit,
   invalid→default+warn), deny-precedence controls (users=allowlist:[U] +
   roles=denylist:[Y] with U holding Y → denied; denied X-holder under users=denylist +
   roles=allowlist:[X] → denied), three degenerate-posture controls each denying a
   plain channel member (incl. users=denylist + roles=allowlist:[]),
   both-denylist-empty → allow, not_channel_member in every combo,
   `effective_posture()` over the full table asserting both `kind` and
   `degenerate_dimensions`.
   `test_chatlink_preflight.sh`: update :112 to the posture-derived row; add the two
   mixed degenerate-posture WARNs (each naming the causing dimension), the open-access
   WARN, the restricted PASS row, and all **four** ignored-inactive-list WARN cases
   (denied-while-allowlist and allowed-while-denylist, × users/roles).
   `test_chatlink_daemon.sh`: one focused **intake-wiring** test proving the parsed
   modes flow through the real gateway path (`_handle_message` → `decide` → `_deny` →
   audit/ephemeral), not just the pure policy table. Extend the `Env` factory
   (:120-152) with a config-override kwarg (e.g. `config_kwargs: dict` merged into the
   `ChatlinkConfig(...)` built at :146-152) — scope-honest, no behavior change for
   existing envs. Assert: (a) denylist-mode denied user → no session, audit
   `denied reason=user_denied`, and with `deny_mode="ephemeral"` exactly one ephemeral
   denial delivered (new reason exercises the same `_deny` surface, intake.py:468-472);
   (b) open-members posture (both-denylist, both lists empty) → a plain channel
   member's message opens a session (allow `ok_not_denied` end-to-end).

## Verification

All five touched chatlink test files green: `bash tests/test_chatlink_config.sh`,
`bash tests/test_chatlink_preflight.sh`, `bash tests/test_chatlink_daemon.sh`,
`bash tests/test_chatlink_wizard.sh`, `bash tests/test_chatlink_tui.sh`. Wizard/TUI
untouched in this child (the existing empty-allowlist wizard warning still reflects
the default allowlist/allowlist posture).

Post-implementation per task-workflow Step 9 (gates incl. risk_evaluated; archive via
`aitask_archive.sh 1186_1`).

## Risk

### Code-health risk: medium
- `decide()` tail rewrite touches the load-bearing fail-closed authorization path; a
  subtle ordering error in the 4-combination composition rule could change existing
  allowlist/allowlist behavior · severity: medium · → mitigation: existing pinned
  negative controls (test_chatlink_config.sh:250-301) must pass UNCHANGED + verbatim
  table-driven test + daemon-level intake-wiring test (real `_handle_message` →
  `_deny` → audit path, not just the pure table); feature-level drift covered by t1192
  (existing "after" mitigation from parent decomposition)
- Preflight `allowlist` row group is rebuilt into posture-derived rows; a consumer
  keying on the old row id/message would drift · severity: low · → mitigation:
  test_chatlink_preflight.sh updated in-task; row id checked at the only consumer
  (tests)

### Goal-achievement risk: low
None identified. — requirements are pinned exhaustively (decision table, reason codes,
degenerate postures, doc surfaces, test list) by user decision 2026-07-20; approach
mirrors existing string-enum + pure-helper patterns.

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned, including the three
  review-round additions: (1) `Posture` frozen dataclass (`kind` +
  `degenerate_dimensions`) returned by `policy.effective_posture()` instead of a
  bare string, (2) preflight ignored-inactive-list WARNs in both directions ×
  both dimensions (`authorization_users_ignored` / `authorization_roles_ignored`,
  RUNTIME bucket), (3) daemon-level intake-wiring test via a new `config_kwargs`
  override on the test `Env` factory (`tests/test_chatlink_daemon.sh:123-155`).
  `decide()` tail rewritten to the pinned precedence; four new `ChatlinkConfig`
  fields parsed with the `deny_mode` string-enum pattern; preflight allowlist row
  group extracted into `_authorization_results()` (`preflight.py:157`); all four
  doc surfaces updated.
- **Deviations from plan:** None material. The preflight `allowlist` row id was
  kept for all posture rows (deny_all/open_members/restricted) so the daemon's
  legacy refusal-order test and the TUI surface stay stable; only the
  ignored-list warns use new ids.
- **Issues encountered:** None — existing negative controls passed unchanged on
  first run after the `decide()` rewrite (deny-before-allow ordering directly
  encodes the pinned precedence).
- **Key decisions:** `effective_posture()` computes deny_all as "every
  allowlist-mode dimension has an empty list, and at least one dimension is an
  allowlist" — this single expression covers all three degenerate combos and
  yields the causing dimensions for free. Intake/audit/ephemeral wiring needed
  zero changes: `decision.reason` flows through `_deny` generically, which the
  new daemon test now pins.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** t1186_4 (wizard picker UI) should consume
  `policy.effective_posture(config)` for its posture copy — `kind` selects the
  message class, `degenerate_dimensions` names the dimension; do not re-derive
  combos. The config test's `mk_conf(um, rm, au, ar, du, dr)` and
  `claims_for(uid, rids, member)` helpers (test_chatlink_config.sh, t1186_1
  section) are reusable for any further policy tests. The daemon test `Env`
  now accepts `config_kwargs` for arbitrary `ChatlinkConfig` overrides.
  Wizard save path (`build_edits`) must learn the two mode keys + denied lists
  in t1186_4; `config_write`'s merge-never-drop already preserves hand-edited
  fields until then.
