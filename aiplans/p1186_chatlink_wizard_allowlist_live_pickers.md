---
Task: t1186_chatlink_wizard_allowlist_live_pickers.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# t1186 — Chatlink wizard: live Discord-backed allowlist pickers + dual authorization modes (parent decomposition plan)

## Context

The chatlink config wizard's step 2 ("Who may open a bug report") requires hand-typing
Discord snowflake IDs into two free-text inputs, with zero validation. The reporter asked
for live pickers (fetch channel members / server roles from Discord) and for sane
"nobody selected" semantics. Live Discord connectivity already exists in the wizard
(t1149_5 `live_check.py`), and the adapter already has `fetch_participants()`; only
guild-role enumeration is missing.

**User decisions (recorded 2026-07-20):**
1. **Per-dimension authorization modes** — two new config fields,
   `user_authorization_mode` and `role_authorization_mode`, each `allowlist | denylist`
   (both default `allowlist`, preserving existing configs and the fail-closed default):
   - `allowlist`: the listed ids are allowed; empty list grants nobody (today's behavior).
   - `denylist`: the listed ids are blocked; empty list blocks nobody.
   Users and roles get **independent** mode choices. Both empty-list use cases
   ("block all" / "allow all") are expressed explicitly via the modes, not by
   overloading the empty list. Error paths stay fail-closed in every mode combination:
   `no_config`, `no_claims` (claims-fetch failure), and `not_channel_member` deny first.

   **Pinned composition rule (precedence: explicit deny > explicit allow > default):**
   1. denylist-mode match (user or role) → deny (`user_denied` / `role_denied`)
   2. allowlist-mode match (user or role) → allow (`ok_user` / `ok_role`)
   3. default: allow (`ok_not_denied`) only when BOTH dimensions are denylist-mode;
      otherwise deny (an allowlist dimension makes the default restrictive —
      reason `role_not_allowed` / `user_not_allowed` as today).
   Consequences: both-allowlist ≡ current behavior exactly; both-denylist-empty =
   any channel member; `users=denylist + roles=allowlist:[X]` = "role X holders
   except the denied users"; `users=denylist + roles=denylist:[]` = "everyone
   except the denied users".

## Pinned decision table (contract artifact — becomes a table-driven test in t1186_1)

For a verified channel member (the `no_config` / `no_claims` / `not_channel_member`
denies always run first, in every combination):

| user mode | role mode | evaluation order | default (no match) | reason codes in play |
|-----------|-----------|------------------|--------------------|----------------------|
| allowlist | allowlist | user∈allowed→allow; role∈allowed→allow | deny (`role_not_allowed` if allowed_roles≠∅ else `user_not_allowed`) | ok_user, ok_role, role_not_allowed, user_not_allowed |
| denylist  | denylist  | user∈denied→deny; role∈denied→deny | allow `ok_not_denied` | user_denied, role_denied, ok_not_denied |
| denylist  | allowlist | user∈denied→deny; role∈allowed→allow | deny (`role_not_allowed` if allowed_roles≠∅ else `user_not_allowed`) | user_denied, ok_role, role_not_allowed, user_not_allowed |
| allowlist | denylist  | role∈denied→deny; user∈allowed→allow | deny `user_not_allowed` | role_denied, ok_user, user_not_allowed |

**Degenerate postures (fail-closed by design; loudly warned, never silent):** an
allowlist dimension with an empty list makes the default restrictive, so these
configs deny every channel member and render any denylist entries meaningless:
- allowlist/allowlist with both allowed lists empty (today's pinned default)
- denylist/allowlist with `allowed_role_ids` empty
- allowlist/denylist with `allowed_user_ids` empty

**Open-access posture:** denylist/denylist with both denied lists empty allows every
channel member.

A shared pure helper `policy.effective_posture(config) -> "deny_all" | "open_members" |
"restricted"` classifies these postures ONCE; preflight rows, the wizard's posture
warning, and the tests all derive from it (no duplicated posture logic). The
deliberately fail-closed degenerate default was chosen over the alternative
("empty allowlist dimension is inactive"), whose degenerate case is fail-open
(a non-empty role allowlist silently becoming decorative); rejected as the worse
failure mode.
2. **Slack parity** → separate standalone follow-up task (created during implementation).
3. **Role source** → guild-wide role enumeration via a new Discord config-time helper.
4. **Decomposition** → 4 child tasks (approved).

Scope-honest field naming: denylist modes get their own `denied_user_ids` /
`denied_role_ids` fields; the existing `allowed_user_ids` / `allowed_role_ids` keep their
meaning. Each dimension's mode selects which list is consulted; the inactive list is
preserved (never cleared) and flagged by preflight. No migration of existing configs.

## New step order

`_STEPS` becomes: `IntakeChannelScreen(1), TokenScreen(2), LiveCheckScreen(3),
AllowlistScreen(4), DenyRepoScreen(5), CeilingsScreen(6), SummaryScreen(7)` — token and
live validation move ahead of the allowlist so the picker can fetch. `LiveCheckScreen`
reads only `provider/token/workspace_id/conversation_id/thread_id`, all set by steps 1–2.

## Child tasks

**The four children are strictly sequential slices of one feature** (the auto
sibling-dependency chain enforces the order). t1186_1 is not independently shippable as
a user-facing feature: it lands runtime semantics before the wizard can display or edit
them. That window is acceptable because (a) hand-editing the config file is already the
only way to set the new fields, (b) `config_write`'s merge-never-drop preserves them
through wizard saves, and (c) t1186_1 adds a preflight posture row so hand-edited modes
are inspectable (`ait`-side) even before the wizard UI exists. The parent archives only
after all four children (plus the manual-verification sibling) complete.

### t1186_1 — `authorization_modes` (config fields + policy + preflight + docs + tests)

- `.aitask-scripts/chatlink/config.py`: `ChatlinkConfig` gains
  `user_authorization_mode: str = "allowlist"`, `role_authorization_mode: str = "allowlist"`,
  `denied_user_ids: list[str] = []`, `denied_role_ids: list[str] = []` (near :74-76).
  Parse in `load_config_with_warnings` (:249-298): each mode validated against
  `{"allowlist","denylist"}` mirroring the `deny_mode` string-enum pattern (:224-230;
  bad value → default + warning); denied lists via `_str_list` (:112-127).
- `.aitask-scripts/chatlink/policy.py` `decide()` (:48-67): first three denies unchanged
  (`no_config`, `no_claims`, `not_channel_member`). Then the pinned composition rule
  (explicit deny > explicit allow > default):
  1. `user_authorization_mode == "denylist"` and `user_id in denied_user_ids` → deny
     `user_denied`
  2. `role_authorization_mode == "denylist"` and any `role.id in denied_role_ids` → deny
     `role_denied`
  3. `user_authorization_mode == "allowlist"` and `user_id in allowed_user_ids` → allow
     `ok_user`
  4. `role_authorization_mode == "allowlist"` and any `role.id in allowed_role_ids` →
     allow `ok_role`
  5. default: both modes denylist → allow `ok_not_denied`; otherwise deny with
     `role_not_allowed` if (`role_authorization_mode == "allowlist"` and
     `allowed_role_ids` non-empty) else `user_not_allowed` — preserving today's reason
     mapping when both modes are allowlist.
  New constants: `REASON_USER_DENIED`, `REASON_ROLE_DENIED`, `REASON_OK_NOT_DENIED`.
  New pure helper `effective_posture(config) -> "deny_all" | "open_members" |
  "restricted"` implementing the pinned posture classification (single source for
  preflight, wizard, tests). Update module docstring (deny-by-default is the
  all-allowlist default; per-dimension denylist documented, precedence pinned).
- `.aitask-scripts/chatlink/preflight.py` (:240-251): rebuild the allowlist row group on
  `effective_posture()`:
  - `deny_all` → WARN naming the degenerate posture explicitly, covering ALL three
    deny-all combinations from the pinned table (both-allowlist-empty keeps wording
    close to today's; the two mixed degenerate postures get "denylist has no effect —
    the empty <dimension> allowlist denies everyone; fill it or switch it to denylist").
  - `open_members` → WARN "open access: any channel member can open a bug report".
  - `restricted` → PASS row showing the effective posture per dimension
    (`users: <mode> (<n> ids) / roles: <mode> (<n> ids)`) — makes hand-edited mode
    fields inspectable before the wizard UI lands (t1186_4).
  - Per-dimension consistency WARN when an inactive list is non-empty (e.g.
    `denied_user_ids` set while `user_authorization_mode` is `allowlist` — ignored
    field). Never a FAIL / `daemon_refuse_message`.
- Docs (document both modes + precedence; default stays deny-by-default):
  `seed/chatlink_config.yaml` :28-35 (add both mode keys + `denied_*` keys with
  comments and the precedence rule); `.aitask-scripts/chatlink/__init__.py:13`;
  `aidocs/chat/chatlink_runtime.md:101-113` (+ new reasons in the reason table);
  `website/content/docs/workflows/bug-report-intake.md:103-106`.
- Tests:
  - `tests/test_chatlink_config.sh`: existing allowlist negative controls (:254-289)
    unchanged; add a **table-driven test transcribing the pinned decision table
    verbatim** (all four mode combinations × empty/non-empty lists × member
    listed/unlisted → expected allow flag + reason code), plus targeted controls:
    mode parsing (defaults, explicit, invalid→default+warn); deny precedence
    (`users=allowlist:[U] + roles=denylist:[Y]`: U holding Y is denied; denied X-holder
    denied under `users=denylist + roles=allowlist:[X]`); the three degenerate
    deny-all postures (each denies an otherwise-unremarkable channel member — incl.
    the surprising `users=denylist + roles=allowlist:[]` case); both-denylist-empty →
    allow; non-channel-member → still `not_channel_member` in every combination;
    `effective_posture()` unit-tested over the full table.
  - `tests/test_chatlink_preflight.sh` (:112 area): existing WARN assertion updated to
    the posture-derived row; add assertions for the two mixed degenerate-posture WARNs,
    the open-access WARN, the restricted PASS row, and the ignored-inactive-list WARN.
- No wizard changes in this child (wizard UI for the modes lands in t1186_4; until then
  `build_edits` omits the new keys and `config_write`'s omit≠clear merge preserves any
  hand-edited values).

### t1186_2 — `discord_fetch_surface` (adapter helpers + headless fetch module)

- `.aitask-scripts/chat/discord_adapter.py`: **two** new Discord-specific config-time
  helpers next to `fetch_bot_permissions` (:1188), following its documented precedent
  (**outside** the `ChatAdapter` ABC — no changes to `slack_adapter.py`/`mock.py`),
  errors wrapped `map_discord_error(exc, target="conversation")`:
  - `async def fetch_roles(self, conversation) -> list[Role]` — guild resolution as in
    `_require_guild()` (:1048), `guild.roles` cache else `await guild.fetch_roles()`;
    skip `is_default` (@everyone); return `Role(id=str(r.id), name=r.name,
    kind="discord_role")`.
  - `async def fetch_channel_members(self, conversation) -> list[User]` — the picker's
    member source. The runtime `fetch_participants` path (:1098-1108) is NOT sufficient
    live: it reads `channel.members` (guild-member-cache-derived, may be empty in a
    short-lived config-time connection) and its `fetch_members()` fallback only exists
    on Thread/Guild objects — a real `TextChannel` has no `fetch_members`, so fakes
    pass while production shows an empty picker. Instead: resolve channel + guild;
    ensure the member list is actually populated — if `guild.chunked` use the cache,
    else `await guild.chunk()` (gateway chunking; Server Members Intent is already
    mandatory and live-check-verified), falling back to `async for m in
    guild.fetch_members(limit=None)` when chunking is unavailable; then **visibility-
    filter** with `channel.permissions_for(member).view_channel` (the same membership
    oracle `fetch_identity_claims` uses at :1183-1185); return `user_to_domain(m)` per
    member. `fetch_participants` itself is left untouched (runtime ABC surface).
- New headless module `.aitask-scripts/chatlink/allowlist_fetch.py` mirroring
  `live_check.py` contracts (Textual-free + discord-import-free at module level, lazy
  `DiscordAdapter` import behind an injectable `connector` seam, sync entry point running
  `asyncio.run`, shared monotonic deadline, bounded 5s teardown under
  `contextlib.suppress`, **never raises**, token hygiene: exception class names only —
  reuse `live_check._exc_names`):
  - `run_allowlist_fetch(token, workspace_id, conversation_id, thread_id=None, *,
    timeout=FETCH_TIMEOUT_S, connector=None) -> AllowlistFetchResult`
  - `AllowlistFetchResult`: `members: list[tuple[id, display_name]]` (bots filtered out —
    intake drops bot actors anyway), `roles: list[tuple[id, name]]`,
    `members_error: str|None`, `roles_error: str|None` (per-stage, sanitized),
    `members_truncated: bool` (cap `MAX_MEMBERS = 500`).
  - Members via new `adapter.fetch_channel_members(parent_ref)` (parent conversation
    ref, as live_check stage 4 does for threads); roles via new
    `adapter.fetch_roles(parent_ref)`. Partial results allowed: one stage failing does
    not blank the other.
- ID-validation helpers here (headless, imported by the wizard in t1186_4):
  `dedupe_ids(ids) -> list` (order-preserving) and
  `invalid_snowflakes(ids) -> list` (non-matches of `^\d{15,21}$`).
- Tests in `tests/test_chatlink_wizard.sh` (headless section; `textual` must stay out of
  `sys.modules`): FakeAdapter with `fetch_channel_members`/`fetch_roles`/`close` +
  `connector_for` (mirror :238-284); assert all-pass shape, bot filtering, truncation at
  cap, per-stage failure isolation, sanitized class-name-only errors, token hygiene
  sweep, timeout, teardown close-count, thread→parent ref; helper tests for
  dedupe/snowflake. The chunking/visibility logic inside `fetch_channel_members` is
  discord.py-object-driven and cannot be faked meaningfully at this seam — it is
  explicitly delegated to the live manual-verification sibling (unchunked-cache
  scenario: verify the picker lists members on a freshly connected bot against a real
  server, including a member invisible to the channel being excluded).

### t1186_3 — `wizard_step_reorder` (derived numbering + declared seams + reorder)

- `.aitask-scripts/chatlink/wizard.py`:
  - `_WizardStep` gains class attr `step_name: str` (title text without numbering) and
    keyword args `step_no`/`step_total` on `__init__`; base `compose()` renders
    `f"Step {step_no}/{step_total} — {step_name}"`. Replace all 7 hardcoded
    `step_title` literals (:224, :256, :291, :312, :346, :385, :510) with `step_name`.
  - Seam needs declared on the class: `needs_seams: bool = False` on the base, `True` on
    `TokenScreen`/`LiveCheckScreen`/`SummaryScreen`; `make_step()` (:674-679) branches
    on `cls.needs_seams` and derives `step_no=idx+1`, `step_total=len(_STEPS)` — the
    hardcoded class tuple is gone.
  - Reorder `_STEPS` (:697-698) to the order above.
- `tests/test_chatlink_tui.sh`: reorder the pilot walkthrough input sequences and the
  `isinstance` progression assertions (:290-563) to the new step order; add one
  assertion that a rendered `#wizard_title` shows the derived `Step N/7` for a
  representative screen.

### t1186_4 — `allowlist_picker_ui` (per-dimension mode selectors + SelectionList pickers + validation)

- `wizard.py` `WizardSeams` (:68-79): add `allowlist_fetch_runner: Callable|None = None`;
  `resolve_seams()` (:82-94) defaults it to `allowlist_fetch.run_allowlist_fetch`.
  `chatlink_app.py` (:109-129, :167-175): accept/store/wire an
  `allowlist_fetch_runner` init param (test seam).
- `AllowlistScreen` (:255-287) rebuild — manual `Input`s remain canonical:
  - **Per-dimension mode selectors + pinned screen state model**: two `CycleField`s
    (precedent: deny-mode field, already imported from `lib/profile_editor`), one above
    each ID Input, cycling `allowlist | denylist`, prefilled from state.
    **State model (pinned):** the screen owns four working lists (`allowed_user_ids`,
    `denied_user_ids`, `allowed_role_ids`, `denied_role_ids`) plus the two modes; each
    Input always displays/edits exactly the active-mode list of its dimension and
    relabels with the mode. **Mode toggle** for a dimension: parse the Input into the
    outgoing mode's working list, then load the Input from the incoming mode's list —
    both lists survive round-trip toggling; nothing is cleared. Fetched
    `SelectionList` selected-state is **recomputed from the newly active list** on
    every toggle, and the selection-change handler reads the dimension's mode at event
    time so a selection can never write to an inactive list (stale-event guard).
    Filtering only narrows visible rows; it never mutates selection or lists.
    `_accept()` parses both Inputs into their active lists and writes all four lists +
    both modes into wizard state (Back/Next retention via the shared state dict);
    `initial_state()` (:97-122) and `build_edits()` (:125-144) extended to round-trip
    all six keys (a dimension's inactive list is preserved, not cleared).
  - `needs_seams = True`. Add a "Fetch from Discord" `Button` (disabled unless
    `state["provider"] == "discord"`; token from `state["token"] or seams.token_reader()`).
  - Thread worker + generation-token guard copied from the `LiveCheckScreen` pattern
    (:409-453): pure `work()` calling the seam runner, `call_from_thread`, `_apply_results`
    early-returns on stale generation or `not self.is_attached`.
  - On results: two `SelectionList`s (members, roles; entry label `"{name} ({id})"`,
    value=id; follow the `aitask_board.py:3097-3143` precedent) with a filter `Input`
    that narrows entries; entries whose id is already in that dimension's active-mode
    text Input start selected. Selection changes rewrite that Input: (manually-typed
    ids not in the fetched set, preserved) ∪ (selected fetched ids). `_accept()` keeps
    parsing the Inputs — state/`build_edits()` flow unchanged. Show a truncation notice
    when `members_truncated`.
  - Advisory failure: per-stage sanitized error line; manual entry always available
    (offline / no token / non-Discord / fetch failure).
  - `_accept()` validation: always `dedupe_ids`; when provider == discord,
    `invalid_snowflakes` non-empty → inline error naming the bad tokens, do not advance
    (hard block — a typo'd id would otherwise silently never match). Non-Discord
    providers: dedupe only. The one-shot warning becomes posture-aware via
    `policy.effective_posture()` over the screen's working values (same helper as
    preflight — no duplicated posture logic): `deny_all` → "nobody will be able to open
    a bug report" (wording names the degenerate mixed cases: "the empty <dimension>
    allowlist denies everyone"); `open_members` → "any channel member will be able to
    open a bug report"; press Next again to accept. `restricted` advances silently.
  - `SummaryScreen._summary_text()` (:531-536): show per-dimension lines —
    `users: <mode>: <ids or (none)>` / `roles: <mode>: <ids or (none)>` — replacing the
    single concatenated allowlist line.
- `tests/test_chatlink_tui.sh`: injected fake fetch-runner spy (mirror `wiz_spy_live`,
  :253-268): not called before Fetch pressed; called with entered token/channel; results
  populate SelectionLists; toggling selection rewrites the Input; manual ids survive
  fetch+selection; fetch failure degrades to manual entry and still advances; invalid
  snowflake blocks advance with error; dedupe on accept; posture-aware warnings for
  deny_all (incl. one mixed degenerate posture) and open_members; saved config reflects
  picker selections end-to-end. **Required state-model tests (from review):**
  (1) mode-toggle-after-selection — fetch, select entries, toggle the dimension's mode,
  assert the selection landed only in the previously active list and the Input now
  shows the other list; (2) filter-after-toggle — filter, toggle, assert no selection
  or list mutation from filtering; (3) toggle round-trip — allowed→denied→allowed
  preserves both lists exactly; (4) Back/Next retention — leave and re-enter the screen,
  assert all four lists + both modes are retained and re-displayed correctly.

## Post-creation extras (implementation session, after plan approval)

- **Standalone Slack-parity follow-up task** (user decision 2): create via
  `aitask_create.sh --batch` — Slack member/usergroup pickers reusing the t1186_2/4
  seams (`slack_adapter.fetch_participants` exists; needs a usergroup-enumeration
  helper); `anchor: 1149` topic group.
- **Aggregate manual-verification sibling**: offered per workflow after child creation —
  live wizard walkthrough on a real Discord server covering what injectable-fake tests
  cannot: member fetch on a freshly connected bot (unchunked-cache scenario),
  channel-visibility exclusion, large-list filter, step reorder, and both authorization
  modes (incl. one degenerate-posture warning) end-to-end.
- t1184 / t1124 / t1120_8 are NOT folded in; they are flagged in the planned "after"
  risk-mitigation chore below.

## Verification

- `bash tests/test_chatlink_config.sh`, `test_chatlink_preflight.sh`,
  `test_chatlink_wizard.sh`, `test_chatlink_tui.sh` all green after each child.
- Guard tests stay green: daemon Textual-import-free; `test_chatlink_wizard.sh` asserts
  `textual` never imported in the headless section.
- Existing allowlist negative controls pass **unchanged** (default behavior preserved);
  denylist and mixed-mode combinations covered by new controls in t1186_1, including
  deny-precedence negative controls.
- Live behavior (real Discord fetch, member-cache/chunking on large guilds) is covered by
  the manual-verification sibling, not unit tests.

## Step 9 reference

Standard post-implementation per task-workflow Step 9 applies per child: gates run
(`risk_evaluated` active), archive via `aitask_archive.sh <parent>_<child>`; parent
archives automatically after the last child.

## Risk

### Code-health risk: medium
- Per-dimension modes create a 4-combination policy matrix (plus precedence rule) restated across policy/preflight/docs/tests; a missed surface or an unpinned combination leaves the contract ambiguous · severity: medium · → mitigation: t1192
- Wizard structural refactor (reorder + derived numbering + seam declaration) touches every screen class and every pilot-walkthrough test sequence · severity: medium · → mitigation: none (covered by rewritten TUI walkthrough tests)
- New `allowlist_fetch` module duplicates live_check-style orchestration; drift risk contained by reusing `_exc_names` and the same contracts · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Live-Discord member enumeration can only be proven against a real server; the dedicated `fetch_channel_members` helper (guild chunk / fetch_members fallback + visibility filter) addresses the known empty-cache failure mode, but chunking latency on very large guilds and fakes-pass-while-live-fails residual risk remain · severity: medium · → mitigation: t1192 (+ aggregate manual-verification sibling)
- Picker UX for very large member lists (cap + filter) may need iteration after first real use · severity: low · → mitigation: none

### Planned mitigations
- timing: after | name: update_live_verification_for_new_allowlist_semantics (created: t1192, at decomposition time — Step 8d never runs for a decomposed parent) | type: chore | priority: medium | effort: low | addresses: per-dimension mode matrix consistency + live-Discord behavior risk | desc: Update the existing live-verification tasks/checklists (t1124 discord live smoke, t1184 live-validation follow-up, t1120_8) to the per-dimension authorization modes, the reordered wizard step flow, and the picker path.
