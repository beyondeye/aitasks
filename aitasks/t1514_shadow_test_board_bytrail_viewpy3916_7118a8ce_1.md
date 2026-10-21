---
priority: low
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [shadow-concern]
anchor: 1210
followup_kind: review_finding
created_at: 2026-08-13 21:35
updated_at: 2026-08-13 21:35
---

Spun off from a shadow review concern on t1505_1.

- [low | test_board_bytrail_view.py:3916] test_banner_is_unchanged_when_no_hint_is_present claims to compare the no-depth banner against the pre-t1505_1 ladder, but at line 3935 its “reference” is produced by the same current app._trail_banner() under test and then compared to the current _refresh_subtitle() call path. Any future regression that changes _trail_banner's no- depth output changes both values, so the test still passes and does not protect the all-existing-trails compatibility contract the plan explicitly calls out. Use independent expected strings or a test-local copy of the old ladder for the width cases instead. Disposition: follow-up. Verified: CONFIRMED.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2112** id=2026-10-21T16:01:06Z.5f769769fb650a1e2245f3b8 from=t2112 from_verified=yes at=2026-10-21T16:01:06Z base=7777409133b8859695819efaba07496b770bca85 base_branch=main dirty=no host=omg16
>
> | t2112 (commit 777740913) changed the banner code this task's regression test covers:
> | 
> | - `_trail_banner(title, suffix, owner_note, depth_note="", gen_note="")` in
> |   `.aitask-scripts/board/board_trail_screen.py` gained a `gen_note` argument (local-time
> |   generation time). Both notes are additive-if-it-fits; generation is tried before depth,
> |   so at mid widths depth can now be dropped where it used to show. Rungs 1-4 are unchanged.
> | - `TrailDepthLabelTests._doc` (tests/test_board_bytrail_view.py) now pops `generation`,
> |   because the shared fixture gate_framework.json carries a `generated_at`. Without that,
> |   `test_banner_is_unchanged_when_no_hint_is_present` would see the new note. Its reference
> |   is still a second `_trail_banner(...)` call, which is the weakness this task records.
> | - `TrailGeneratedBannerTests` in the same file is an example of the alternative: it patches
> |   `_banner_budget` per rung and asserts literal strings, including RUNG2/3/4.
> | Line numbers in this task's body may have moved.
