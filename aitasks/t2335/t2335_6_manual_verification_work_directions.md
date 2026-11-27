---
priority: medium
effort: low
depends: [t2335_5]
issue_type: manual_verification
status: Ready
labels: [sitrep, tui, trails]
verifies: [2335]
premise_baseline: c443f811efd914e808d99dce252774f7a6f398de @ 2026-11-19 05:12
anchor: 2175
created_at: 2026-11-19 05:12
updated_at: 2026-11-19 05:12
---

## Goal

Check the work-directions flow end to end in a real terminal, in a scratch repo and a scratch tmux session (not the main aitasks one).

## Verification Checklist

- [ ] With several open items and no directions, the Directions tab shows the empty state; the request key types `>d` into the sitrep agent
- [ ] `>d` proposes directions, summaries, linked trails and ONE ranked order, asks once, and after "yes" the Directions tab shows the rows in that order
- [ ] Reordering at the confirmation is honoured and persists across a TUI restart
- [ ] Completing or archiving a member task, then pressing r, turns that direction STALE with a readable reason; the others stay current
- [ ] Harvesting a new wrap-up raises the "N items in no direction" count; Enter on that line lists exactly those items
- [ ] The request key on a stale direction types `>d <direction>`; after the agent rewrites it the row reads current and the rank of the other directions is unchanged
- [ ] z on a direction opens `ait trails` with the member tasks highlighted and the critical path marked; the banner names the overlay and the clear key removes it
- [ ] Markers are distinguishable without colour (try a monochrome or low-colour terminal)
- [ ] For a direction whose tasks are in no trail, the agent offers `/aitask-trail` and creates nothing until told yes
- [ ] Asking the agent "what is blocking <direction>" answers from the sources, flags a stale direction first, and logs the Q&A
- [ ] `>p` names the next step of the top-ranked direction and still picks nothing
- [ ] Left / right cycles all tabs including Directions; at 80 columns the strip and the two-line rows stay unwrapped
- [ ] A format-3 store from before the upgrade opens without error and is upgraded only by the first changing write

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2335_4** id=2026-11-27T12:17:56Z.61b825d810aae5b8ebb165ac from=t2335_4 from_verified=yes at=2026-11-27T12:17:56Z base=b625ddd285ba5aa1dde576919538b24330b58d0c base_branch=main dirty=yes host=omg16
>
> | Advisory (as of commit b625ddd28), for the checklist wording. Check against the code.
> | - "after the agent rewrites it the row reads current": a direction saved by `>d` reads `unknown` until a refresh (`r`) runs; `current` appears only after that.
> | - `>w` can now decline to write and offer `>d <direction>` when its text would contradict the saved summary; that is intended.
> | - The `>d` confirmation shows the full new situation text when it replaces one, and the full ranked order.
> | - Not exercised by a live agent in t2335_4 (the author walked the rendered text in a scratch repo): the whole `>d` flow, including a dropped direction that cancels a move, a rank-only save, and a next step refused because the picker lists the task as Blocked or Has children.
