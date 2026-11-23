---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [sitrep, monitor, minimonitor, frozen_agents]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-11-19 15:32
updated_at: 2026-11-22 18:28
---

# Show a frozen agent's sitrep state (harvested / triaged) so "safe to drop" is visible

## Problem

When the sitrep agent finishes triaging a wrap-up, it writes the derived
action/watch items and closes the triage question
(`set-state c<N> done --outcome "triaged: …"`). The question moves to
Recently done, shown in the sitrep TUI behind `d`. Nothing in this step
touches, marks or reports on the **frozen agent** whose capture the
wrap-up came from.

So a user looking at a frozen card in `ait monitor` / `ait minimonitor`
cannot tell whether that agent is done with and can be dropped. A frozen
row shows only `<mark>F` (`format_frozen_prefix`,
`.aitask-scripts/monitor/monitor_shared.py:427`). The only way to find out
today is to press `h` and see whether the harvest dialog offers **Drop**.

## What the exploration established

- **Drop safety is decided by harvest, not triage.** `drop` / `purge` are
  gated by the harvest receipt `<capture.txt>.harvested`, which must carry
  `cert=2` and the current capture's sha256
  (`lib/agent_sessions.py` `capture_harvested`, `HARVEST_RECEIPT_SUFFIX`,
  `HARVEST_RECEIPT_CERT`). Once a capture is harvested, its passages are
  retained, content-addressed, in `.aitask-sitrep/sources/`. Dropping a
  harvested agent before triage therefore loses nothing.
- **Harvest already runs often:** detached right after a freeze
  (`lib/agent_freeze.py` `_spawn_harvest_detached`), on `h`
  (`monitor/sitrep_close.py`), on the monitor's maintenance tick
  (`monitor_shared._maybe_harvest_sitrep`, about every 10 min) and on the
  sitrep TUI's `r`.
- **Triage is a second, advisory signal:** "the user has reviewed this
  agent's follow-ups". It does not gate the drop, but it is what the user
  is actually asking about ("can I drop it now?").
- **The link from a frozen record to its triage item already exists.** The
  harvested capture passage carries the KEY header `record=<frozen id>`
  (`lib/sitrep_harvest.py`, `KEY_PASSAGE_HEADER`, around line 601). The triage
  question's context sources point at that passage, and its origin carries
  `agent=` / `pane=` / `task=`. So the state can be **derived**; the user
  never has to mark anything by hand.

## Goal

Make each frozen agent's sitrep state visible where the user decides to
drop it, derived from the store and the receipt (no manual "mark as
triaged" step):

| State | Derived from | Meaning shown to the user |
|---|---|---|
| unharvested | no valid receipt | not safe to drop yet (drop would harvest first, or refuse) |
| harvested, nothing to triage | receipt valid, no triage question for the record | safe to drop |
| harvested, triage open | receipt valid, linked triage question open | safe to drop; follow-ups still to triage |
| triaged | linked triage question(s) done | safe to drop; follow-ups handled |
| review pending | linked review-case item open | safe to drop (raw kept); review pending |
| unknown | receipt or store unreadable | never shown as safe |

## Scope (to settle in planning)

1. **A shared derivation helper** (lib/, stdlib, no monitor import, in the
   style of `sitrep_cli`): frozen record id → state, from the receipt
   check plus a lock-free store read that maps `record=<id>` passage keys
   to triage/review items. Fail closed: anything unreadable → `unknown`.
   Helpers report the evidence; they do not decide for the user.
2. **Monitor + minimonitor frozen cards:** a compact badge beside
   `F` (glyph or short text in both TUIs, through a shared formatter as
   `format_frozen_prefix` already is), plus the state in the card's detail
   / `h` dialog wording. Read off the event loop, cached per
   `todo.md` sha256 and receipt mtime, like `SitrepNowCounter`.
3. **Optional, sitrep TUI:** on a triage item whose source frozen record
   still exists, a details line / How text "source agent still frozen:
   drop it with `h` in the monitor". Show only; never drop from the
   sitrep TUI.
4. Docs: `aidocs/framework/sitrep.md` (monitor surface),
   `website/content/docs/workflows/sitrep.md` step 7 and the
   freeze-and-restore page.

## Constraints

- Sitrep stays advisory. Nothing here drops, kills or types into a pane.
  Dropping stays the guarded `h` → **Drop** path.
- Frozen-first on every read; the new reads must not slow down the
  monitor's refresh (no subprocess per card per tick).
- "Safe" is asserted only from a valid cert=2 receipt for the current
  capture sha. Triage state alone never implies safe.
- An agent that never ran a task workflow (no banner) is harvested with no
  triage question. That is the "nothing to triage" row, not an error.
- Map records only through the passage KEY `record=` header or recorded
  origin fields, never through title or text matching.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2338** id=2026-11-23T00:28:16Z.c0426d09a8978d08a0296756 from=t2338 from_verified=yes at=2026-11-23T00:28:16Z base=068eac299a2238863d46a0295a1eca6361366911 base_branch=main dirty=yes host=omg16
>
> | Advisory (t2338; a moment-relative claim, as of 2026-11-23): two files you
> | also edit carry t2338's own uncommitted one-line hunks, which I have not
> | committed so they don't tangle with your staged changes:
> | - aidocs/framework/sitrep.md, "monitor surface" table row: "`S` in the TUI
> |   switcher" -> "`S` and the Sitrep row in the TUI switcher"
> | - website/content/docs/workflows/sitrep.md, step 1 `S` paragraph: appends
> |   ", which the switcher's **Sitrep** row also opens."
> | Both describe the switcher's Sitrep row, which landed in 9b4b88a61 (t2338).
> | When you commit these files, leave these two lines out of your commit if you
> | can; t2338 commits them right after t2337 lands. If your commit picks them up
> | anyway, that's harmless: they belong to t2338 and are correct on main. Nothing
> | here asks t2337 to change its own work.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-22T16:28:23Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-23T00:27:07Z status=pass attempt=1 type=human
