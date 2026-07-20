---
Task: t1189_chatlink_live_check_user_facing_hints_and_channel_access_doc.md
Base branch: main
plan_verified: []
---

# Plan: t1189 — chatlink live-check user-facing hints + channel-access docs

## Context

A real chatlink wizard run hit a `live_channel_visible` failure whose fix hint pointed at
`aidocs/chat/discord_bot_setup.md` — a framework-internal doc that is NOT shipped to user
installs. Three fixes: (1) point all user-visible hint strings at the public website doc,
(2) exploit the already-connected adapter's bot user id (`_self_id` = application ID for
modern bots) to render a ready-to-paste invite URL exactly in the failure cases that need
it, and (3) document Discord's server-invite vs. per-channel permission-overwrite model,
which no doc currently explains.

Exploration confirmed the sink surface is exactly the 5 user-visible strings the task
enumerates (full grep sweep found no others; all other `aidocs/` hits under
`.aitask-scripts/chatlink/` and `.aitask-scripts/lib/` are comments/docstrings). No test
asserts on the current aidocs wording.

## Changes

### 1. `.aitask-scripts/chatlink/live_check.py` — hints + invite URL

- Add module constants:
  ```python
  _DOCS_URL = "https://www.aitasks.io/docs/workflows/bug-report-intake/"
  _INVITE_URL_TMPL = ("https://discord.com/oauth2/authorize?client_id={cid}"
                      "&scope=bot+applications.commands&permissions=397552863296")
  ```
- Rewrite the two aidocs-citing templates (lines 65–69) to reference `_DOCS_URL`, e.g.:
  - `_FIX_VISIBILITY` → `"check server/channel ids and invite the bot to the server with channel access (see " + _DOCS_URL + ")"`
  - `_FIX_PERMISSIONS` → `"re-invite the bot with the documented permission set (see " + _DOCS_URL + ")"`
- Add a hint builder preserving the fixed-template hygiene contract (bot id is spliced
  only when it is a pure digit string — never exception text):
  ```python
  def _invite_hint(base: str, bot_id: str | None) -> str:
      """Append a ready-to-paste invite URL when the bot user id is known."""
      if bot_id and bot_id.isdigit():
          return base + " — invite URL: " + _INVITE_URL_TMPL.format(cid=bot_id)
      return base
  ```
- In `_run_async`, right after a successful connect (line ~157), capture
  `bot_id = getattr(adapter, "self_id", None)` and route **all five**
  `_FIX_VISIBILITY` / `_FIX_PERMISSIONS` failure sites through
  `_invite_hint(...)` (visibility timeout, visibility exception, permissions timeout,
  permissions exception, missing-required). Connect-stage failures (`_FIX_TOKEN` /
  `_FIX_INTENTS`) are unchanged — no adapter is available there and the invite URL is
  not the remedy.
- `REQUIRED_BOT_PERMISSIONS` pairing comment (lines 41–42): keep pointing at
  `aidocs/chat/discord_bot_setup.md` step 5 — that doc remains the canonical
  *enumerated* permission list, and code comments citing aidocs are explicitly fine
  per the task. No change needed beyond verifying it still matches.

### 2. `.aitask-scripts/chat/discord_adapter.py` — public `self_id` accessor

Add a read-only property on `DiscordAdapter` (near the top of the class, ~line 624),
so `live_check` doesn't reach into the private attribute:

```python
@property
def self_id(self) -> str | None:
    """Bot user id (equals the application ID for modern bots); set on connect."""
    return self._self_id
```

Discord-specific placement is consistent with `fetch_bot_permissions` (also
Discord-only, consumed by the Discord-only live check); the `ChatAdapter` ABC is not
touched.

### 3. Sandbox-hint strings — website URL

Replace `aidocs/chat/chatlink_sandbox.md` with the website doc URL in the three
user-visible strings (keep wording otherwise intact):

- `.aitask-scripts/chatlink/preflight.py:307` — `fix_hint="install Docker (see <_DOCS_URL>)"`
- `.aitask-scripts/chatlink/daemon.py:742-744` — stderr warning
- `.aitask-scripts/lib/sandbox_launch.py:331-333` — `LaunchError` message

(Hardcode the URL string in each; these modules don't import from `chatlink.live_check`.)

### 4. Tests — `tests/test_chatlink_wizard.sh` (live_check heredoc, lines 213–401)

- `FakeAdapter` gains `self_id = "1234567890"` (constructor-overridable).
- New cases:
  - channel-not-found failure → `fix_hint` contains
    `client_id=1234567890` and the full `discord.com/oauth2/authorize` URL.
  - missing-required-permission failure → same invite-URL assertion.
  - adapter with `self_id = None` → hint contains the website URL but NO
    `oauth2/authorize` (fallback path).
  - non-digit `self_id` (e.g. `"boom<token>"`) → no invite URL spliced (hygiene
    negative control; existing `hygiene(rows)` helper also applies).
- Existing cases keep passing unchanged (none assert aidocs wording).
- Sanity-check `tests/test_chatlink_tui.sh` (spy row uses its own `fix_hint`) and
  `tests/test_chat_discord.sh` still pass; optionally assert the new `self_id`
  property in the existing connect test there.

### 5. `website/content/docs/workflows/bug-report-intake.md`

- After the invite-URL step (~lines 76–80): add a short paragraph explaining that the
  invite adds the bot to the **server**; per-channel access follows the channel's
  permission **overwrites** — for a private channel the bot (or its role) must be
  explicitly added in the channel's permission settings (Edit Channel → Permissions).
- Troubleshooting table (~line 301): add a row —
  Symptom: wizard live check or session reports "bot lacks access to the intake
  channel" · Cause: bot is in the server but the channel's permission overwrites
  exclude it (typical for private channels) · Fix: add the bot (or its role) in the
  channel's permission settings, or re-check the invite's permission set.

### 6. `aidocs/chat/discord_bot_setup.md`

Add the same channel-access clarification right after step 6 ("Authorize", ~line 63):
server invite ≠ channel access; private channels require an explicit permission
overwrite for the bot/role.

### 7. Coordination (task-data edits, via `./ait git`)

- `aitasks/t1149/t1149_4_wizard_docs_rewrite.md`: append a reverse coordination note —
  t1189 added channel-access content (prereq paragraph + troubleshooting row) to
  `bug-report-intake.md`; the rewrite must carry it forward. Update `updated_at`.
- `aitasks/t1184_manual_verification_live_discord_validation_followup.md`: touch up
  checklist lines 29–30 — the failing `live_channel_visible` / `live_permissions` rows
  now carry a website-doc link and a concrete invite URL in their fix hint. Update
  `updated_at`.

## Verification

- `bash tests/test_chatlink_wizard.sh` — new + existing live_check cases.
- `bash tests/test_chatlink_tui.sh`, `bash tests/test_chat_discord.sh` — regressions.
- `grep -rn "aidocs/" .aitask-scripts/chatlink/ .aitask-scripts/lib/` — remaining hits
  are comments/docstrings only.
- Optional: `cd website && hugo build --gc --minify` (doc table syntax).

Then proceed to **Step 9 (Post-Implementation)** for gates, archival, and cleanup.

## Risk

### Code-health risk: low
- Invite-URL splice could weaken the fixed-template token-hygiene contract if the id
  ever carried exception/token text · severity: low · → mitigation: in-plan
  (digits-only guard + hygiene negative-control test)

### Goal-achievement risk: low
- t1149_4's pending rewrite of the same website sections could drop the new
  channel-access content · severity: low · → mitigation: in-plan (reverse coordination
  pointer added to t1149_4)
