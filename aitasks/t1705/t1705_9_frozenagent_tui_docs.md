---
priority: medium
effort: medium
depends: [t1705_8]
issue_type: documentation
status: Implementing
labels: [documentation, website, docs, minimonitor, aitask_monitor, tui, tui_switcher]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
implemented_with: claudecode/opus5
created_at: 2026-09-04 16:10
updated_at: 2026-09-10 11:25
---

## Context

Ninth child of t1705 (frozen code agents). **TUI-surface documentation**
for everything children 4–7 shipped: the new `ait frozenagent` viewer, the
frozen row / counter / filter / keys in `ait minimonitor` and `ait monitor`,
the switcher entry, the dispatcher entry, and the `aidocs/framework`
conventions the implementation introduced (respawn-pane, `run-shell -b`,
the four `@aitask_*` pane options, the stand-in self-stamp rule). Per
`aidocs/framework/planning_conventions.md`, documentation is a first-class
child, created before the manual-verification sibling. The **workflow and
concept** docs (freeze/restore as a daily workflow, the framework-session
concept, the setup "Session hooks" section) are the *next* child
(t1705_10) — do not fold them in here. Document **current state only**
(`aidocs/framework/documentation_conventions.md`): no version history, no
"new in", generic agent wording where the supported agents are named.

Source of truth is the landed code, not this task or the parent plan —
re-read `frozenagent/frozenagent_app.py`, `minimonitor_app.py`,
`monitor_app.py`, `tui_switcher.py` for the real keys, glyphs, hint text and
messages before writing (memory: "doc the current source, not the stale
plan").

## Pages

1. **New** `website/content/docs/tuis/frozenagent/_index.md` (front matter
   like `tuis/applink/_index.md`: `title: "Frozen Agent"`, `linkTitle`,
   `weight` after monitor, `description`, `maturity: [experimental]`,
   `depth: [main-concept]`): purpose (what a frozen agent is, in two
   sentences, linking the workflow page from t1705_10 via `{{< relref >}}`
   — the link may point at a page that lands in the next child; run
   `check_links.py` after both), the standard "Customizable keys" callout,
   `## Launching` (`ait frozenagent` list mode; `--record <id>` viewer mode;
   the stand-in launch is automatic), `## Layout` (header fields: project ·
   window · task · agent · frozen_at · lines · state; log area; search box),
   `## Viewing` (`r` plain/ANSI, `m` markdown of all/selected, `g`/`G`),
   `## Searching`, `## Selecting and copying` (keyboard range vs mouse
   selection; `y`; where the text goes — OSC 52 + tmux buffer), `## Restore,
   re-pick and drop` (`R`/`p`/`k`, what "restoring…" then "restored,
   unverified — capture kept" / "restore failed: <reason>" mean),
   `## List mode`.
   `how-to.md` (`weight: 20`): "Read a frozen agent's summary", "Copy a
   spawned-task list out of a frozen transcript", "Bring an agent back",
   "Remove a frozen record".
   `reference.md` (`weight: 30`): `## Keybindings` table (incl. `j`
   switcher and `q`), `## Header fields`, `## States shown` (frozen /
   restoring / restored-unverified / failed), `## Exit codes` of the
   launcher.
2. **Edit** `website/content/docs/tuis/minimonitor/_index.md` and
   `how-to.md`: the frozen row (`<mark><F> name  frozen`, no state dot, no
   capture), coexistence with the priority/parked mark (glyph composition,
   what `space` does on a frozen row), the `Nf` session-bar term (always
   shown, independent of the filter — same wording pattern as the parked
   term), the `F` filter, freezing the followed agent (`z`, confirm text),
   Freeze-All (`Z`), `R`/`p`/`k` on a frozen row, the own-panel frozen
   render, and that the companion does **not** auto-despawn when its agent
   is frozen (update the "auto-despawn" sentence in `how-to.md:340`).
3. **Edit** `website/content/docs/tuis/monitor/reference.md` — keybinding
   rows (`z`, `Z`, `F`, `R`, `p`, `k` on frozen), the `N frozen` term in the
   session-bar section, the frozen preview placeholder; `monitor/_index.md`
   if it enumerates agent states.
4. **Edit** `website/content/docs/tuis/_index.md` — bullet
   `- **[Frozen Agent](frozenagent/)** (\`ait frozenagent\`) — …` and the
   "Navigating between TUIs" switcher paragraph (`f`).
5. **Edit** `website/content/docs/commands/_index.md` — `ait frozenagent`
   row; note whether an `ait frozen` verb exists (decided in t1705_4: default
   no).
6. **Edit** `aidocs/framework/tui_conventions.md` — a "Frozen stand-in
   panes" subsection: the self-stamp rule for `@aitask_standin_ready`, the
   companion/cleanup sibling rule, and a pointer to the parent plan's
   state machine; `aidocs/framework/tmux_gateway.md` — `respawn-pane` and
   `run-shell -b` are gateway-routed like everything else; the four options
   in the `@aitask_*` inventory (:112-129); `aidocs/framework/aitasks_extension_points.md`
   — the SessionStart hook install surface (seed → install.sh → setup merge
   → framework-path lists) as a checklist row.

## Reference patterns

- `website/content/docs/tuis/applink/{_index,how-to,reference}.md` — the
  Diátaxis triple and front matter.
- `website/content/docs/tuis/minimonitor/how-to.md` §parked (t1685's
  wording for a non-live row and an always-visible counter).
- `aidocs/framework/documentation_conventions.md`; `website/check_links.py`.

## Verification

```bash
cd website && hugo build --gc --minify && python3 check_links.py --build   # zero dead links / fragments
grep -rn 'frozen' website/content/docs/tuis/minimonitor/ website/content/docs/tuis/monitor/ | wc -l
grep -n 'frozenagent' website/content/docs/tuis/_index.md website/content/docs/commands/_index.md
```
No code, no tmux.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1705_7** id=2026-09-09T10:08:29Z.478b145750406eaac4f7884f from=t1705_7 from_verified=yes at=2026-09-09T10:08:29Z base=a13fcfa1b338ae9c99558b52c33c7dddc8aabdfa base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | t1705_7 landed. Three things differ from what the parent plan / this task's
> | own text lead you to expect, all decided with the user and all user-visible,
> | so documenting the planned surface would document something that does not
> | exist.
> | 
> | 1. THE KEYS ARE `f` / `Z` / `R` / `p` / `k`, not `z`/`Z`/`F`.
> |    `z` is already Zoom and `R` already Restart in `ait monitor`, so the task's
> |    proposed `z` (freeze) and a frozen-only `R` could not both land there.
> |    Settled as, identical in BOTH apps:
> |      f = freeze this agent (confirm dialog)
> |      Z = freeze all         (confirm dialog naming the count)
> |      R = restore, p = re-pick, k = drop
> |    `R`/`p`/`k` are guarded INSIDE the action, not the binding: on a live row
> |    monitor's `R` still means Restart and minimonitor's `p` still means
> |    pick-by-number. They act only on the window's CURRENT agent -- minimonitor's
> |    followed agent, monitor's focused card -- never on an arbitrary list row.
> | 
> | 2. THERE IS NO `F` FILTER KEY. The filter is UNIFIED: the existing `P` now
> |    hides parked AND frozen agents. One key, one list. This makes the shipped
> |    parked docs inaccurate as written -- at least
> |    `website/content/docs/tuis/monitor/reference.md:39` ("Hide or show parked
> |    agents") and `minimonitor/how-to.md:290` -- so those lines need widening,
> |    not just new frozen prose beside them.
> |    The COUNTERS stay separate and disjoint (`N frozen` / `Nf` beside
> |    `N parked` / `Np`), and both render whether or not `P` is hiding the rows.
> | 
> | 3. The action id is still `toggle_parked_visibility` even though it now hides
> |    both. That is deliberate and worth NOT documenting as a rename: the action
> |    string is the key that `keybinding_registry` resolves user overrides
> |    against, so renaming it would silently revert customized keys. If the docs
> |    list action ids anywhere, that one has not changed.
> | 
> | Also shipped, in case it belongs in the reference: `aitask_frozen.sh freeze
> | --all --dry-run` (prints `WOULD_FREEZE:<pane>|<session>|<window>` per pane then
> | `FREEZE_ELIGIBLE:<n>`). It exists so the Freeze-All confirmation counts what
> | the operation will actually touch -- every aitasks session on the machine,
> | parked agents included, not just what the current view shows. Worth saying
> | plainly in the docs: Freeze-All is wider than the pane list suggests.
> | 
> | Advisory only -- verify against the tree before relying on any of it.
> | Not verified anywhere: none of the live tmux behaviour. t1705_7 ran inside the
> | `ait` server and shipped unit/render coverage only; t1705_8 owns live proof.

> **✉ note:t1705_7** id=2026-09-09T13:31:41Z.2d146d01638694bff5d50b1c from=t1705_7 from_verified=yes at=2026-09-09T13:31:41Z base=d822b650a2362b82356f64ff1e5292ef2556f0f4 base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | Second review round on t1705_7 changed two user-visible behaviours since the
> | earlier note about the key layout. Advisory only — verify against the tree.
> | 
> | 1. **The frozen drop confirmation names its own verb.** Pressing `k` on a frozen
> |    row (monitor: focused card; minimonitor: followed agent) opens a confirmation
> |    whose affirmative button reads **"Drop"**, styled destructively, not
> |    "Freeze". Body text: "Its captured output is deleted along with the record,
> |    and the stand-in pane is closed. This cannot be undone — restore or re-pick it
> |    instead if you still want it." Worth documenting as its own step, because the
> |    drop is the one irreversible frozen operation: the capture is the only copy of
> |    that agent's output.
> | 
> |    The freeze confirmation (`f`) is deliberately the opposite — primary styling,
> |    "Freeze" — because freezing preserves the output. If the docs describe them
> |    together, keep that contrast.
> | 
> | 2. **Restore feedback is no longer a fixed timeout.** The monitor's "still
> |    restoring" warning now derives its deadline from the project's
> |    `frozen.restore_ack_grace` (`aitasks/metadata/project_config.yaml`) rather
> |    than a hardcoded 40 seconds. At the default grace the behaviour is identical,
> |    so nothing needs a version note — but if the docs state a fixed wait anywhere,
> |    that number is now wrong. The deadline is read from the *record's* project,
> |    not the viewing monitor's, because `freeze --all` spans projects.
> | 
> |    The `ait frozenagent` viewer still uses the old fixed deadline (filed as
> |    t1766), so if the docs describe both surfaces, they genuinely differ today.
> | 
> | Also still true from the earlier note: `P` is the unified parked+frozen filter,
> | there is no `F` key, and `website/content/docs/tuis/monitor/reference.md:39` and
> | `minimonitor/how-to.md:290` describe `P` as parked-only — inaccurate, not merely
> | incomplete.

> **✉ note:t1705_8** id=2026-09-09T18:30:23Z.69c81bac1787d30a171c0121 from=t1705_8 at=2026-09-09T18:30:23Z base=80d5ea53221cf89bcf0fbf4bd14e1ae23f9297b0 base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | t1705_8's acceptance suite measured several user-visible behaviours end to end
> | against a real viewer. Four are easy to document wrongly. Advisory only --
> | verify against the tree before relying on any of it.
> | 
> | 1. **`hook` and `liveness` restores are NOT the same outcome, and the
> |    difference is user-visible.** `RESTORED:<id>|hook` means the resumed agent's
> |    SessionStart hook acknowledged the record: the session id was verified and
> |    THE CAPTURE FILES ARE DELETED. `RESTORED:<id>|liveness` means nothing ever
> |    acknowledged; the coordinator waited out `restore_ack_grace` and confirmed on
> |    the launched pid alone, so the restore is unverified and THE CAPTURE IS
> |    KEPT. Both are successes; only one is verified. Do not describe restore as a
> |    single outcome.
> | 
> | 2. **There are two `drop` verbs and they are not interchangeable.**
> |    `aitask_agent_sessions.sh drop <id>` is the tmux-free store: it removes the
> |    record and the capture files and LEAVES THE STAND-IN PANE RUNNING with all
> |    its stamps ("THIS MODULE NEVER TOUCHES TMUX"). `aitask_frozen.sh drop <id>`
> |    is the engine: it also retires the pane. Both are asserted separately
> |    (acceptance cases 10a / 10b) because they are genuinely different contracts.
> | 
> | 3. **The `frozen:` block in `project_config.yaml` does not accept every knob.**
> |    `capture_max_lines` and `restore_ack_grace` ARE read from it;
> |    `stale_op_grace` is **not** -- `agent_sessions._stale_op_grace()` reads only
> |    `AITASKS_STALE_OP_GRACE`, and only under `AITASKS_TEST_MODE=1`. Documenting a
> |    configurable `frozen.stale_op_grace` would document a silent no-op. Note also
> |    that a positive `AITASKS_RESTORE_ACK_GRACE` (test mode) short-circuits BEFORE
> |    the config is opened, so the env wins where both are set.
> | 
> | 4. **`capture_max_lines` is scrollback DEPTH, not a total line count.** The
> |    engine passes `capture-pane -S -<cap>`, which starts `cap` lines back in
> |    history and runs through the bottom of the visible pane, so the stored
> |    capture holds roughly `cap + pane_height` lines. Measured: cap 120 produced a
> |    132-line capture in an 12-row pane. Saying "captures at most N lines" is
> |    wrong by a pane height.
> | 
> | Also worth a mention if the docs cover restoring after a tmux restart: that
> | route currently fails (t1773) -- a frozen record whose window was closed cannot
> | be restored, because restore branches on the recorded `pane_id` instead of
> | checking the pane. Nothing is lost, but do not document it as working until
> | t1773 lands.

> **👁 note:read** id=2026-09-10T05:15:39Z.736f8e171def93898f0f500a by=t1705_9 at=2026-09-10T05:15:39Z mode=explicit ids=2026-09-09T10:08:29Z.478b145750406eaac4f7884f,2026-09-09T13:31:41Z.2d146d01638694bff5d50b1c,2026-09-09T18:30:23Z.69c81bac1787d30a171c0121

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T08:25:46Z status=pass attempt=1 type=human
