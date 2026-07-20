---
priority: medium
effort: medium
depends: [t1186_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1186_1, 1186_2, 1186_3, 1186_4]
anchor: 1149
created_at: 2026-07-20 22:51
updated_at: 2026-07-20 22:51
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1186_1] With a hand-edited config setting user_authorization_mode=denylist + role_authorization_mode=denylist and both denied lists empty, `ait chatlink` preflight shows the open-access WARN ("any channel member can open a bug report") and a live Discord channel member NOT on any list can open a bug report
- [ ] [t1186_1] With users=denylist + roles=allowlist and allowed_role_ids empty (degenerate posture), preflight shows the "denylist has no effect — the empty role allowlist denies everyone" WARN and a live channel member is denied
- [ ] [t1186_1] With default config (both modes allowlist, lists as before t1186), live intake behavior is unchanged: listed user allowed, unlisted denied, both-empty denies everyone with the deny-by-default WARN in preflight
- [ ] [t1186_2] On a freshly connected bot against a real Discord server (cold member cache), the wizard fetch returns the channel's member list (chunking path) — not an empty list
- [ ] [t1186_2] A guild member WITHOUT view permission on the intake channel does not appear in the member picker; guild roles appear with @everyone excluded
- [ ] [t1186_3] Full wizard walkthrough shows the new step order (intake → token → live check → allowlist → deny/repo → ceilings → summary) with derived "Step N/7" numbering correct on every screen, and Back navigation retains entered values across the reordered steps
- [ ] [t1186_4] Fetch from Discord in the allowlist step populates member and role SelectionLists; filtering narrows rows; selecting entries rewrites the ID input; manually typed IDs survive fetching and selection
- [ ] [t1186_4] Toggling a dimension between allowlist/denylist relabels the input, swaps between the allowed/denied lists without losing either, and the saved config round-trips both modes and all four lists (verify the written chatlink_config.yaml)
- [ ] [t1186_4] With no network / wrong token / provider != discord, the allowlist step still works via manual entry (advisory error only, Next never blocked by a failed fetch); an invalid (non-snowflake) ID blocks Next with an error naming the bad token
- [ ] [t1186_4] The one-shot posture warning fires for nobody-allowed and everyone-allowed postures and a second Next accepts; a restricted posture advances silently
