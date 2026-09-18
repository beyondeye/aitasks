---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
verifies: [t1705_1, t1705_2, t1705_3, t1705_4, t1705_5, t1705_6, t1705_7, t1705_8, t1705_9, t1705_10]
anchor: 1705
followup_kind: carry_over
created_at: 2026-09-18 16:09
updated_at: 2026-09-18 16:09
---

Carry-over of deferred manual-verification items from t1705_11. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] [t1705_3] Same check for Codex (or, if t1705_1 found Codex hooks unsupported, the docs and the hook header say so and Codex restore is offered as re-pick only) — DEFER 2026-09-18 16:02
- [ ] [t1705_4] Freezing a real finished agent from a shell (`aitask_frozen.sh freeze <pane>`) leaves the window and the companion minimonitor in place, the viewer in the agent's pane, and the full scrollback readable; the agent process is gone — DEFER 2026-09-18 16:03
- [ ] [t1705_4] Freeze-All on a session with 3+ agents freezes every one and reports each; a window holding one frozen and one live agent survives killing the live one — DEFER 2026-09-18 16:04
- [ ] [t1705_5] Restore (`R`) of a real Claude agent brings the same conversation back in the same pane (ask it what it did earlier); the capture directory is deleted and the frozen row disappears — DEFER 2026-09-18 16:07
- [ ] [t1705_5] Re-pick (`p`) of a frozen task-bound agent launches `/aitask-pick <id>` in the same pane; a restore whose agent exits immediately shows the failure and the viewer is back with the transcript intact — DEFER 2026-09-18 16:07
- [ ] [t1705_6] `ait frozenagent --record <id>` renders colours faithfully; `r` toggles plain text; `/` finds text and `n` cycles; shift+down selects lines and `y` puts them on the system clipboard from inside tmux; `m` renders the selection as markdown — DEFER 2026-09-18 16:07
- [ ] [t1705_6] Bare `ait frozenagent` lists frozen agents across two projects; `enter` opens one; `k` removes a record after confirmation; the switcher (`j` then `f`) reaches the list — DEFER 2026-09-18 16:07
- [ ] [t1705_7] Minimonitor shows a frozen agent as `<mark><F> name  frozen` with no state dot; the `Nf` term stays visible with `F` filtering on; `z` freezes the followed agent after a confirm; `Z` freezes all; `R`/`p`/`k` act on a frozen row; `space` still cycles the mark on it; the hints band is still ten rows — DEFER 2026-09-18 16:07
- [ ] [t1705_7] `ait monitor` mirrors the same row, `N frozen` term, `F` filter, preview placeholder and keys; auto-switch never lands on a frozen card — DEFER 2026-09-18 16:07
- [ ] [t1705_10] The freeze-and-restore workflow page reads as a usable daily loop; the framework-session concept page's state diagram matches the store's states; the setup page's "Session hooks" section matches what `ait setup` really writes — DEFER 2026-09-18 16:07

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1705_11** id=2026-09-18T13:10:16Z.c6d5bb9c0c83e7f4d2dda7e1 from=t1705_11 at=2026-09-18T13:10:16Z base=8408f8be14820126c8e7aacf478795c869c40087 base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | Context from the t1705_11 auto-verification pass (2026-09-18), advisory only:
> | 
> | - Two of your items are blocked on t1705_10 (still Ready): the Codex docs half
> |   of "[t1705_3] Same check for Codex" and the whole "[t1705_10] workflow page /
> |   framework-session concept page / Session hooks section" item. The hook
> |   header and agent_restore.py already satisfy the non-docs half of the Codex
> |   item. This task carries depends: [] so it is pickable before t1705_10 lands;
> |   the other eight items do not need it.
> | - The eight remaining items need a live `-L ait` server with real agents. All
> |   automated coverage was green today (spike 48/48 with real claude+codex,
> |   parity 59/59, acceptance 160/160, hook-install 39/39 with the venv python).
> |   The highest-value hand check is Restore of a real claude recalling prior
> |   context. Also exercise t1773 (restore after the window is gone) by hand.
> | - Full execution log: aiplans/archived/p1705/p1705_11_manual_verification_auto.md
