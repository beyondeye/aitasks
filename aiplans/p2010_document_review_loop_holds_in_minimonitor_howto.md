---
Task: t2010_document_review_loop_holds_in_minimonitor_howto.md
Base branch: main
Output branch: main
---

# t2010 — Document review-loop holds, disarm causes and `--loop-log` in the minimonitor how-to

## Context

t2001 (`159437cd1`) made the minimonitor auto-recheck loop (`L`) **hold**, not
disarm, when the shadow pane is in a tmux mode (copy-mode, entered by scrolling an
inline shadow back with the mouse wheel). The user-facing page
`website/content/docs/tuis/minimonitor/how-to.md`, "How to Run the Auto-Recheck Loop"
(line 260), describes none of it:

- the banner table (lines 264–271) lists only ARMED / settle / delivering / sent,
  so **no hold banner is documented**, including the new scrolled-back one;
- the disarm paragraph (line 273) names only absence and an unreadable shadow,
  although delivery failures disarm too;
- `ait minimonitor --loop-log`, the durable record of every disarm and hold, is not
  mentioned anywhere on the website.

Docs-only change to one page. Current-state prose only (no version history, no task
ids in the page body). The section heading stays unchanged: three pages link to its
`#how-to-run-the-auto-recheck-loop` anchor (minimonitor `_index.md:83`,
`how-to.md:432`, `workflows/shadow-agent.md:34`).

## Verified facts the prose relies on (read in planning)

Banner strings — `LOOP_HOLD_BANNERS`, `.aitask-scripts/monitor/review_loop.py:196`:

| code | banner (verbatim) |
|---|---|
| `shadow_in_mode` | `⟳ holding: shadow scrolled back — scroll it down or press q there` |
| `shadow_mode_unreadable` | `⟳ holding: shadow pane mode unreadable — will retry` |
| `pre_enter_in_mode` | `⟳ holding: Enter withheld (shadow in tmux mode) — check its composer` |
| `pre_enter_mode_unreadable` | `⟳ holding: Enter withheld (shadow mode unreadable) — check its composer` |
| `pre_enter_dialog` | `⟳ holding: shadow showed a dialog — will retry` |
| `pre_enter_unreadable` | `⟳ holding: shadow pane unreadable — will retry` |

`delivery_superseded` and `shadow_not_settled` have no banner. They are recorded
but never shown (`minimonitor_app._loop_hold`, line 4247).

Behaviour (`minimonitor_app.py` `_loop_hold` 4222, banner block 4675–4691,
`_fire_shadow_recheck` 4781–4793, `_submit_shadow_prompt` 4878–4930; aidocs
`shadow_agent.md` items 6 and 9):

- A hold is edge-triggered: one toast `Auto-recheck loop holding: <message>` when
  the reason changes. The banner outranks ARMED and stays until a recheck is
  delivered (`_clear_loop_hold` on `sent` / FIRED), or until the user disarms or
  re-arms.
- **Pre-write mode holds** (`shadow_in_mode`, `shadow_mode_unreadable`): nothing has
  been typed yet. The loop re-reads the mode on every tick and delivers on the first
  tick after the pane leaves the mode. It never cancels the user's mode.
- **Pre-Enter mode holds** (`pre_enter_in_mode`, `pre_enter_mode_unreadable`): the
  text **is** in the shadow composer and the Enter was withheld. These holds clear
  when the user submits the text, which counts as the round with no duplicate, or
  clears it, after which the loop re-fires once the shadow settles. The banner
  describes the event, so it stays true after the user acts.
- **Pre-Enter dialog/unreadable** (`pre_enter_dialog`, `pre_enter_unreadable`): the
  text was typed and no Enter was sent. Both collapse to "not ready", so the loop
  holds and does not re-type. The code's own note says the text is "presumed still
  sitting there", so the docs must say "if the text is still there, submit or clear
  it" rather than claim the loop re-sends unconditionally.
- Disarms (`DISARM_*`, line 109): the agent or shadow pane gone; a shadow with no
  readiness detection; no tmux monitor; prompt write failed; Enter send failed;
  submit unconfirmed (text left in the composer); text not in the composer. The toast
  reads `Auto-recheck loop disarmed: <message>`, with a ` (not recorded)` suffix when
  the log write failed.
- `ait minimonitor --loop-log [N]` (`aitask_minimonitor.sh:22` dispatches before the
  tmux check and the single-instance guard; `review_loop_log.main`): default 20,
  newest first, each event shown as `ts KIND message` plus a context line with
  `agent shadow_agent shadow_pane session window state rounds_fired project_root` and,
  for a delivery, `pre_enter_verdict pane_in_mode pane_mode`. The store is
  `~/.config/aitasks/review_loop_events/`, overridable with
  `AITASKS_REVIEW_LOOP_LOG_DIR`. I ran `./ait minimonitor --loop-log 3`: rc 0, output
  in the format above.

## Implementation steps

All edits are in `website/content/docs/tuis/minimonitor/how-to.md`, inside
"How to Run the Auto-Recheck Loop". The existing four-row banner table is kept
unchanged. It uses the page's existing **bold-lead paragraph** style
(`**Where the loop can run.**`); no new headings.

### 1. Add a "holds" block right after the banner table (before line 273)

```markdown
**When the loop holds instead of sending.** Sometimes the loop is ready to send but the shadow pane is not safe to type into at that moment. It then **holds**: the delivery is called off, the loop stays armed, and the status line says why. A hold is not a failure. A toast explains it once, when it starts, and the banner stays up until a recheck is delivered or you disarm:

| Banner | Meaning |
|--------|---------|
| `⟳ holding: shadow scrolled back — scroll it down or press q there` | The shadow pane is scrolled back (tmux copy-mode — scrolling an inline shadow with the mouse wheel enters it), so anything typed now would go to the scroll-back instead of the shadow agent. Nothing has been typed. Scroll the shadow to the bottom or press **q** in it, and the recheck goes out by itself |
| `⟳ holding: shadow pane mode unreadable — will retry` | Minimonitor could not tell whether the shadow pane is scrolled back, so it typed nothing. It checks again on every refresh |
| `⟳ holding: Enter withheld (shadow in tmux mode) — check its composer` | The shadow was scrolled back after the recheck text was typed but before its Enter, so the text is waiting in the shadow's input box. Leave the scroll-back, then either submit the text there — that is this round's recheck, and the loop does not send another — or clear it, and the loop sends a fresh one once the shadow has settled |
| `⟳ holding: Enter withheld (shadow mode unreadable) — check its composer` | The recheck text was typed, but minimonitor could not tell whether the pane was scrolled back, so it withheld the Enter. Submit or clear the text in the shadow, as above |
| `⟳ holding: shadow showed a dialog — will retry`<br>`⟳ holding: shadow pane unreadable — will retry` | The recheck text was typed, but just before the Enter the shadow showed a dialog — an Enter would have answered it — or its pane could not be read. No Enter was sent. The loop tries again once the shadow reads as ready; if the recheck text is still in the shadow's input box, submit or clear it there |

Minimonitor never takes the shadow out of scroll-back for you — you are reading it. The two *Enter withheld* banners describe what happened, not what the input box holds now, so they stay accurate after you submit or clear the text. A few routine holds show no banner at all; every hold, shown or not, is recorded in the loop log described below.
```

(Check that `<br>` renders inside the table cell in the Hugo build. If it does not,
split the row into two rows that share the same meaning text.)

### 2. Replace the disarm paragraph (line 273)

Current:
> When the loop disarms itself — the agent or the shadow pane disappeared, or the
> shadow was swapped for one it cannot read — the banner clears and a warning names
> the reason. An open picker pauses the loop rather than disarming it.

New, which describes the classes without promising a closed list:

```markdown
When the loop disarms itself, the banner clears and a warning names the reason. It disarms only when something is definitely wrong: the followed agent's pane or the shadow pane has gone, the shadow was swapped for an agent minimonitor cannot read, or a delivery failed outright — for example an Enter that never landed, which leaves the recheck text in the shadow's input box for you to submit or clear there. An uncertain reading holds rather than disarms, and an open picker pauses the loop.
```

### 3. Add the `--loop-log` paragraph directly after the disarm paragraph

```markdown
**Finding out why after the warning has gone.** Every disarm and every hold is also written to a log. Run `ait minimonitor --loop-log` from any shell — it works while minimonitor is running — to print the 20 most recent events, newest first; `ait minimonitor --loop-log 100` shows more. Each event gives its time, whether the loop disarmed or held, the same reason the warning gave, and the followed agent / shadow pair it happened to, which matters when several pairs are running. An event that ended a delivery also shows what the shadow pane looked like at that moment (`pre_enter_verdict`, `pane_in_mode`, `pane_mode`) — include those when reporting a problem. A warning that ends in `(not recorded)` means the event could not be written to the log. The log lives in `~/.config/aitasks/review_loop_events/` (override with `AITASKS_REVIEW_LOOP_LOG_DIR`).
```

The rest of the section is unchanged ("Minimonitor only ever writes into the shadow
pane", "Where the loop can run", the manual recheck).

## Verification

1. Every banner string in the page matches `LOOP_HOLD_BANNERS` verbatim. Extract
   each `` `⟳ holding: …` `` span from the page and `grep -F` it in
   `.aitask-scripts/monitor/review_loop.py`; all six must hit.
2. `./ait minimonitor --loop-log 3` runs and prints in the described format
   (already observed in planning; re-run once after editing).
3. `cd website && hugo build --gc --minify` succeeds.
4. `cd website && python3 check_links.py --build` reports no broken links, including
   the three inbound `#how-to-run-the-auto-recheck-loop` links.
5. Look at the built page for the `<br>` cell and the table layout. Grep the page for
   `t2001` / `t1606` / "previously" so no history leaks in, and for `diffviewer`,
   which must not appear.

Other sessions have uncommitted edits under `website/content/docs/tuis/frozenagent/`
and `workflows/freeze-and-restore-agents.md`. They are part of the build, so a
build or link failure must be traced to its file before it is attributed. The commit
names only `website/content/docs/tuis/minimonitor/how-to.md`.

## Step 9 reference

Current-branch mode (profile `fast`): commit the page by path
(`documentation: … (t2010)`), commit the plan with `aitask_task_commit.sh`, then
archive per task-workflow Step 9.

## Risk

### Code-health risk: low
None identified. One documentation page changes, with no code, no config and no
inbound anchor changes.

### Goal-achievement risk: low
None identified. Every banner string and behaviour claim was traced to the code and
to aidocs items 6 and 9 during planning. The one subtle case is whether
dialog/unreadable holds leave text behind, and the prose already makes that
conditional. Verification step 1 pins the strings verbatim.
