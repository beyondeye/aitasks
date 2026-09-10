---
Task: t1705_9_frozenagent_tui_docs.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_10_freeze_restore_workflow_docs.md, aitasks/t1705/t1705_11_manual_verification_frozen_codeagents_session_store_and_view.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_1_spike_freeze_standin_and_session_id_capture.md, aiplans/archived/p1705/p1705_2_framework_session_store.md, aiplans/archived/p1705/p1705_3_session_id_capture_hooks.md, aiplans/archived/p1705/p1705_4_freeze_engine.md, aiplans/archived/p1705/p1705_5_restore_and_repick_flows.md, aiplans/archived/p1705/p1705_6_frozenagent_viewer_tui.md, aiplans/archived/p1705/p1705_7_monitor_minimonitor_frozen_rows.md, aiplans/archived/p1705/p1705_8_frozen_agents_acceptance_test.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-10 11:04
---

# t1705_9 — TUI-surface documentation for frozen agents

## Context

Children t1705_4–7 shipped a third lifecycle state for a code agent, beyond live
and parked: **frozen**. The process ends, its terminal output is captured, and a
stand-in viewer takes over its pane. That work landed a new TUI
(`ait frozenagent`), frozen rows and five keys across `ait monitor` and
`ait minimonitor`, a switcher entry and a dispatcher verb.

**None of it is documented.** `grep -rn frozen website/content/docs/` returns
three hits and all three are the ordinary English word. This task writes the
TUI-surface docs. The workflow and concept pages — when and why you freeze, the
framework-session concept, what `ait setup` installs — are the next child
(t1705_10) and stay out of scope here.

This plan is a **re-verification**. The prior plan was written before t1705_6 and
t1705_7 landed and describes a surface that does not exist: it documents keys
`z`/`Z`/`F`, an `F` filter, and a `"restoring…"` status string, none of which
shipped. The parent plan's own amendment **B5** anticipated exactly this — it
names t1705_9 among the plans that "would otherwise implement, test, or
*publish* the superseded protocol." Everything below is quoted from the tree.

---

## What actually shipped (verified this pass)

### Keys — `ait monitor` and `ait minimonitor`

| Key | Meaning | Confirmed |
|---|---|---|
| `f` | Freeze this agent (confirm) | `monitor_app.py:541`, `minimonitor_app.py:1150` |
| `Z` | Freeze all (confirm, names the count) | `:542`, `:1151` |
| `R` | Restore | monitor branches inside `restart_task` (`:3752`); minimonitor binds `restore_frozen` (`:1154`) |
| `p` | Re-pick | monitor binds `repick_frozen` frozen-only, `show=False` (`:545`); minimonitor branches inside `pick_task_by_number` (`:3219`) |
| `k` | Drop | both branch inside `kill_pane` / `kill_own_agent` |
| `P` | Hide/show parked **and** frozen | `:537`, `:1146` |

Two things a reference table must not flatten:

- **The wiring is not symmetric even though the user-visible keys are.** The
  monitor has no live meaning for `p` at all (pressed on a live card:
  `That agent is not frozen — nothing to re-pick`), while minimonitor's `p` keeps
  pick-by-number. Mirror-image for `R`.
- **Guards live in the action, never the binding** — stated in
  `monitor_shared.py:976-992`, because `check_action` would hide `R` and `p`
  entirely. All five act only on the window's *current* agent (monitor: focused
  card; minimonitor: followed agent), never an arbitrary list row.

**There is no `F` key.** `P` is a single unified filter over parked+frozen; the
action id stays `toggle_parked_visibility` deliberately, because it is the
persisted identifier user key-overrides resolve against. Counters stay separate
and disjoint — monitor `N frozen` (two leading spaces), minimonitor `Nf` — and
both render whether or not `P` is hiding rows, since they are computed from
unfiltered `_snapshots`.

### Confirmations

- `f` → `Freeze this agent?` / body naming the window / **`Freeze`** (primary).
- `Z` → `Freeze all N agent(s)?` / body: "This affects **every aitasks session on
  this machine** — including parked agents and agents in other projects, not just
  the N agent(s) shown here." / **`Freeze`** (primary).
- `k` → `Drop this frozen agent?` / "**Its captured output is deleted** along
  with the record… This cannot be undone" / **`Drop`** (`variant="error"`).
- `R` and `p` are **unconfirmed** on every surface.

The primary/destructive contrast is deliberate (`monitor_app.py:3543-3556`) and
must survive into the prose.

### The viewer — `ait frozenagent`

- Grammar is exactly `ait frozenagent [--record <id>]`; anything else → usage,
  exit **2**. Launcher exits **1** on missing deps / old Python.
- Header is `" · "`-joined: project · window · task · agent · `frozen <at>` ·
  `<n> lines` · state, with `\[plain]`, `· capture missing` and
  `· colour data missing` suffixes.
- Keys `r m / n y g G shift+↑/↓ escape R p k enter j ? q`.
- List mode columns `project window task agent frozen lines`, empty cells `—`.
- **Its drop dialog says `Remove`, not `Drop`** — a genuine inconsistency with
  the monitors (see Follow-ups).
- Restore deadline is a **hardcoded 40 s**; the monitors derive theirs from
  `frozen.restore_ack_grace`. Filed as **t1766**; the two surfaces genuinely
  differ today and the docs must say so rather than state one number.
- Switcher key `f`, deliberately absent from the switcher's hint row (column
  budget) — reachable but unadvertised, exactly like applink.

### Outcome vocabulary (from `agent_sessions.restore_verdict` / `drop_verdict`)

`restored` · `restored, unverified — capture kept` ·
`restore failed: <reason> — capture kept` · `restore ended — capture kept` ·
`restore did not start — run 'ait frozenagent' or reconcile` ·
`restore still <state> after the grace — run reconcile; capture kept` ·
`record vanished` · `dropped — capture removed` · `drop failed — record kept`.

`restored, unverified` is a **success**, not a fault, and the code notes it is
the only outcome a Codex record can reach (its interactive TUI fires no
SessionStart hook). Say so, or users will read it as an error.

---

## Files

**New** — `website/content/docs/tuis/frozenagent/`
- `_index.md` (`weight: 16` — the only free slot between monitor 15 and
  minimonitor 17; `maturity: [experimental]`, `depth: [main-concept]`)
- `how-to.md` (`weight: 20`), `reference.md` (`weight: 30`)

**Edit**
- `website/content/docs/tuis/minimonitor/_index.md`, `how-to.md`
- `website/content/docs/tuis/monitor/_index.md`, `how-to.md`, `reference.md`
- `website/content/docs/tuis/_index.md`, `website/content/docs/commands/_index.md`
- `aidocs/framework/tui_conventions.md`, `tmux_gateway.md`,
  `aitasks_extension_points.md`

---

## Implementation

### Pre-phase (risk mitigations)

1. `[reverify_volatile_docs_facts]` Re-read the source of every string this plan
   quotes, rather than trusting the plan: `BINDINGS` and the frozen actions in
   `monitor/monitor_app.py` and `monitor/minimonitor_app.py`; the shared dialogs,
   toasts and `format_frozen_prefix` in `monitor/monitor_shared.py`; the header,
   list columns and confirm body in `frozenagent/frozenagent_app.py`; and
   `restore_verdict` / `drop_verdict` in `lib/agent_sessions.py`. Any string that
   has drifted is corrected in the page, not reproduced from here.

### 1. `tuis/frozenagent/_index.md`

Front matter copied from `applink/_index.md`'s shape. Intro (two sentences: what
a frozen agent is, and that the viewer occupies its pane), then the shared
**Customizable keys** blockquote verbatim — it is a plain blockquote, not a
shortcode, byte-identical across all eight `_index.md` files.

Sections: `## Launching` (bare = cross-project list; `--record <id>` = viewer;
the stand-in launch is automatic) · `## Layout` (the seven header fields) ·
`## Viewing` (`r`, `m`, `g`/`G`) · `## Searching` (`/`, `n`, wrap notice) ·
`## Selecting and copying` (keyboard range vs mouse drag; `y`; OSC 52 **and** the
tmux buffer) · `## Restore, re-pick and drop` · `## List mode`. Close with the
`**Next:** / **Reference:**` footer pair.

**Do not add the `{{< relref "/docs/workflows/freeze-and-restore-agents" >}}`
link the old plan calls for.** That page does not exist and a relref to a missing
page *fails the Hugo build*. t1705_10's own plan (step 5) already owns adding the
cross-link once its page lands.

### 2. `how-to.md` and `reference.md`

`how-to.md`: four recipes — read a frozen agent's summary; copy a spawned-task
list out of a transcript; bring an agent back (restore vs re-pick, and that
neither is confirmed); remove a frozen record.

`reference.md`: `## Keybindings` (every binding incl. `j` and `q`, noting the
footer advertises only nine) · `## Header fields` · `## States shown` — the raw
store vocabulary `live freezing frozen restoring aborting`, plus the outcome
sentences above; there is no `restored-unverified` token · `## Exit codes`
(0 / 1 / 2) · `## Configuration` — **only** `frozen.capture_max_lines` and
`frozen.restore_ack_grace`, the two keys actually read, noting no `frozen:`
section ships by default, and that the viewer's own restore wait is fixed while
the monitors' is derived from the grace.

### 3. Minimonitor pages

`_index.md`: add a **Frozen agents** row to the `## Relationship to monitor`
comparison table (L26-36).

`how-to.md`:
- A `### Frozen agents` subsection beside the parked one, modelled on
  `### How to Park an Agent You Are Done Watching`: the row shape
  `<mark><F> name  frozen` (two-cell prefix — the mark cell then a bold-cyan
  `F`; frozen **coexists** with the mark rather than replacing it), no state dot
  and no capture, and that `space` always targets the *followed* agent, so list
  rows are read-only.
- `f` / `Z` with their confirm texts, `R` / `p` / `k`, and the own-panel render
  (`<mark><F> identity`, then indented dim `frozen <stamp>`, with the phase line
  suppressed rather than left stale).
- **L69** — widen the counter sentence to name `Np` and `Nf` alongside the three
  existing terms (it currently claims three counters cover every agent, which is
  already wrong for parked).
- **L290 and L387** — widen `P` from parked-only to parked+frozen.
- **L300** — qualify "marks … do not change any counter" the way monitor's
  equivalent (L240) already is.
- **L340** — rewrite the auto-despawn sentence: the companion does **not**
  despawn when its agent is frozen. Keep the other three auto-despawn statements
  (`how-to.md:21`, `_index.md:12,62`) consistent.

### 4. Monitor pages

`reference.md`: keybinding rows for `f`, `Z`, and the frozen branches of `R`,
`p`, `k`; widen **L39**'s `P` description; add the `N frozen` term to the status-
counter section (L124-132); document the preview placeholder
`This agent is frozen — press R to restore or p to re-pick.`

`how-to.md`: a frozen counterpart to the parked section, mirroring **L255**'s
"counted separately … shown whether or not `P` is hiding their rows" wording.
Reword **L251**, which uses "a frozen dot" in an unrelated sense that becomes
ambiguous once frozen is a real state. `_index.md` only if it enumerates states.

### 5. Indexes

`tuis/_index.md`: a `- **[Frozen Agent](frozenagent/)** (\`ait frozenagent\`) — …`
bullet, and widen the switcher paragraph's enumeration `(Monitor, Board, Code
Browser, Settings, Stats, Syncer, Chat Link)`, noting `f` works even though the
hint row omits it.

`commands/_index.md`: one row in the `### TUI` group,
`| [\`ait frozenagent\`](../tuis/frozenagent/) | … |`. **No `ait frozen` row** —
that verb does not exist, and `aitasks_extension_points.md:348` ("the `ait`
dispatcher is user-facing only") is the standing reason to keep the engine
internal. Record that decision, which `aitask_frozen.sh:38-39` defers to here.

### 6. aidocs

- `tui_conventions.md` — a `### Frozen stand-in panes` under
  `## Companion pane auto-despawn` (L629), after `### @aitask_monitor_kind`: the
  self-stamp rule for `@aitask_standin_ready` (only the app stamps its own pane),
  the sibling rule (a stamped pane counts as a real agent; the cleanup script
  abstains when the *dying* pane is stamped), and a pointer to the parent plan's
  state machine.
- `tmux_gateway.md` — **create** the `@aitask_*` inventory table. There is no
  table at L111-129 to extend; that range is prose naming one option. Seed it
  with `@aitask_shadow_target`, `@aitask_monitor_kind`, `@aitask_record`,
  `@aitask_frozen`, `@aitask_standin_ready`, `@aitask_agent_session`. Add a line
  that `respawn-pane` and `run-shell -b` are gateway-routed like everything else.
- `aitasks_extension_points.md` — a SessionStart-hook install-surface checklist
  row, copying the `| Touchpoint | Entry shape |` idiom from
  `## Adding a new helper script`.

---

## Verification

```bash
cd website && hugo build --gc --minify && python3 check_links.py --build
```

Must exit zero — a relref to a page that does not exist fails the build, which is
the specific trap in step 1. Then:

```bash
grep -rn 'frozen' website/content/docs/tuis/minimonitor/ website/content/docs/tuis/monitor/
grep -n 'frozenagent' website/content/docs/tuis/_index.md website/content/docs/commands/_index.md
grep -rn 'stale_op_grace' website/content/    # must return nothing
grep -rn '`F`' website/content/docs/tuis/     # no phantom filter key
```

Spot-check every quoted key, glyph and message against the source rather than
this plan: `monitor/monitor_app.py`, `minimonitor_app.py`, `monitor_shared.py`,
`frozenagent/frozenagent_app.py`, `lib/agent_sessions.py`, `lib/tui_switcher.py`.

No code changes, no tmux.

---

## Follow-ups to file

- **The destructive verb differs across surfaces.** The monitors say `Drop`
  (deliberately, t1705_7); the viewer says `Remove` (t1705_6). Same operation,
  two labels. Documentation-only task, so this is a follow-up, not a fix here.
- A note to **t1705_10**, which owns both the capture cap under `## Limits` and
  "records for windows that no longer exist" under `## When something goes
  wrong`, carrying the three facts it could most easily get wrong:
  `capture_max_lines` is scrollback *depth* (`-S -<cap>`), so a capture holds
  roughly `cap + pane_height` lines; `frozen.stale_op_grace` is not read at all
  and documenting it would document a no-op; and restoring a frozen record whose
  window was closed does **not** work today (acceptance case 6b, t1773) — the
  fail-safe half holds, so nothing is lost, but it must not be written up as a
  working recovery route.

---

## Risk

### Code-health risk: low
- None identified. Documentation-only — no code, no tmux. The widest edit is
  prose in shipped monitor/minimonitor pages, and both failure modes a docs
  change has (a dead internal link, a broken shortcode) are caught by
  `hugo build` plus `check_links.py --build` in Verification.

### Goal-achievement risk: medium
- The deliverable *is* accuracy, and the plan quotes roughly forty verbatim
  keys, glyphs, dialog bodies and verdict sentences across twelve files; any
  that drifted between this verification pass and writing would publish a
  falsehood that builds green · severity: medium (residual — addressed by
  inline pre-phase reverify_volatile_docs_facts) · → mitigation: inline
  pre-phase reverify_volatile_docs_facts
- Two behaviours the pages describe belong to open defects — **t1773**
  (restoring a record whose window was closed) and **t1766** (the viewer's
  hardcoded 40 s restore deadline, which the `## Configuration` section states
  as a real viewer-vs-monitor difference). Neither lands before this task, so
  the prose is correct when published and goes stale later · severity: medium
  (residual — corrected after the fact by the spawned follow-up) ·
  → mitigation: recheck_frozen_docs_after_open_defects

### Planned mitigations
- timing: pre-phase | name: reverify_volatile_docs_facts | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — quoted strings drifting between planning and writing | desc: Re-read every quoted source string before writing any page, correcting the plan where the tree has moved.
- timing: after | name: recheck_frozen_docs_after_open_defects | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: high | addresses: goal-achievement — pages describing two open defects' current behaviour go stale when those defects land | desc: Once t1773 and t1766 land, re-check and correct the frozen-agent pages that describe closed-window restore and the viewer-vs-monitor restore deadline.

*Reassessment against the augmented plan (single pass): both levels unchanged.
The pre-phase converts "the quotes may be stale" into "the quotes are re-read at
write time", which is a real reduction but does not make twelve files of dense
verbatim quotation airtight; and a spawned after-task hardens the result later
without lowering this session's delivery risk. `medium` — "covered but not
airtight" — remains the honest reading.*

---

## PINNED contracts (from p1705 — do not re-decide)

Copied verbatim from `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` §A–§D. On any discrepancy the parent plan wins; if a child must deviate, update the parent plan and every sibling plan in the same commit.

> **⚠ PARTLY SUPERSEDED — read the parent plan's `## Amendments from
> re-verification (t1705_5, 2026-09-07 / 2026-09-08)` block (B1–B7) BEFORE
> implementing anything from §A–§D below.** t1705_5 re-verified the §D restore
> contract against the shipped tree and amended it; the parent plan carries the
> authoritative list. The text below is retained as the unedited parent contract.
>
> The four that change §D's wire protocol:
>
> - **B1** — `restore-begin` and `lease-take` both REQUIRE `--owner-pid <pid>`.
> - **B2** — §D step 3's `env VAR=…` prefix is superseded by **`respawn-pane -e`**
>   (one `-e` per variable). The prefix is now the documented *fallback* for a
>   tmux build without `-e`, not the primary mechanism.
> - **B3** — the hook consumes only `AITASK_RESTORE_RECORD` and
>   `AITASK_RESTORE_NONCE`; the other two are exported as diagnostics only.
> - **B4** — §C's `restoring`/`aborting` reconcile rows are already SHIPPED
>   (t1705_4), so §C is a specification of existing behaviour.
>
> **Why this matters for this task specifically.** This task PUBLISHES user-facing
> docs. Documenting §D's original `env`-prefix mechanism would ship the superseded
> contract to users. Document B1–B4.



#### A. Session store — `lib/agent_sessions.py` + `aitask_agent_sessions.sh`

- Path `~/.config/aitasks/agent_sessions.json`, env override
  `AITASKS_AGENT_SESSIONS_FILE`, lock dir derived from the resolved path
  (`<file>.lockd`), 0600 with `_target_mode` preservation, write via
  `lib/atomic_write.py`. Captures under `~/.config/aitasks/frozen/<id>/`
  (0700 dir; `capture.ansi`, `capture.txt`), env `AITASKS_FROZEN_DIR`.
- Schema v1:
  ```json
  {"version": 1, "sessions": [{
    "id": "7f3a2c1d",                 // record id (8 hex, os.urandom) — PRIMARY KEY
    "root": "/real/path/project",     // realpath, both sides         ┐ DURABLE IDENTITY
    "window": "agent-pick-1705",      //                               │ (root, window, window_slot)
    "window_slot": 0,                 // assigned once; >0 only for a 2nd agent in the same window ┘
    "pane_id": "%104", "pane_pid": 41233,   // LOCATION / GENERATION data — replaceable, never identity
    "session": "aitasks",             // tmux session name — display only
    "operation": "pick", "task_id": "1705",          // task_id "" when unbound
    "agent_string": "claudecode/opus5", "agent_kind": "claudecode",
    "codeagent_session_id": "", "transcript_path": "",  // "" = unknown → re-pick only
    "started_at": "2026-09-04T09:12:03Z",
    "state": "live",                  // live | freezing | frozen | restoring | aborting
    "state_at": "2026-09-04T09:12:03Z",
    "op_nonce": "", "op_owner_pid": 0, "op_started_at": "",   // LEASE of the in-flight freeze/restore (see below)
    "frozen_at": "", "capture_ansi": "", "capture_txt": "",
    "capture_lines": 0, "last_phase": "",
    "standin_pid": 0,                 // #{pane_pid} of the stand-in viewer, written at freeze-commit and every stand-in respawn
    "launch_pid": 0,                  // #{pane_pid} of the replacement agent, written by restore-launched (nonce-bound)
    "restore_attempts": 0, "restore_mode": "",   // "" | resume | repick (current attempt)
    "ack": "",                        // "" | hook | liveness — how the last restore was confirmed
    "last_error": ""                  // "" | "<nonce>:session_mismatch" | "<nonce>:<reason>" — coordinator-readable outcome channel
  }]}
  ```
  `pane_id` / `pane_pid` are **location and generation data**: a tmux server
  restart, a reattach or a respawn replaces them on the same record. They
  are never part of the identity key and a recycled `%N` can attach to
  nothing on its own — attachment needs either `@aitask_record` on the pane
  (options die with the pane, so a recycled pane never carries a stale one)
  or a `(root, window)` match under the conflict policy below.
  Unknown `state` = corruption (not a default). `load()` raises
  `MalformedSessionsError`; `load_safe()` returns empty. Generation normalised
  to `SCHEMA_VERSION` on read.
- **Record ownership (one allocator) and the `(root, window)` conflict
  policy.** The `upsert` verb is the *only* creator of records. Resolution
  order for a caller without `--restore-of`:
  1. `--id <rid>` (from `@aitask_record` on the caller's pane) → that record,
     whatever its `(root, window)` (a renamed window keeps its record).
  2. Else, **among `live` records only** with the caller's `(root, window)`,
     the relocation candidates are: the one whose `pane_id` equals the
     caller's pane, else those whose `pane_pid` is dead or whose pane no
     longer exists. **Exactly one candidate** → it is the same agent slot:
     replace `pane_id`/`pane_pid`, update session id / transcript / agent
     string, print `UPSERTED:<id>|updated` (the tmux-restart and reattach
     case — no second record). **More than one candidate** (two agents shared
     the window before a server restart; nothing on the caller's side can
     tell them apart) → **fail closed on relocation**: fall through to rule 3
     and print `UPSERTED:<id>|created_slot<N>|ambiguous_relocation`; the stale
     records are left for purge (rule: a `live` record whose `pane_pid` is
     dead and whose `pane_id` is absent from an enumerated window →
     `DROPPED:…|dead_pane`), never guessed.
     Transitional records (`freezing`/`restoring`/`aborting`) are **never**
     relocated or updated by an unstamped caller: they are touched only by
     `--restore-of` + the current nonce, or by `reconcile`. If the caller's
     pane *is* a transitional record's pane → refuse
     (`UPSERT_REFUSED:<id>|<state>_unacknowledged`, a stray session in a
     transacting pane); otherwise they are simply not candidates.
  3. Else every `(root, window)` record is `live` in **another** pane (a
     second agent split into the same window), transitional, or `frozen`
     (retained state whose window name is being reused, e.g. the same task
     re-picked after a tmux restart) → **create beside it**: new record,
     `window_slot` = lowest unused slot for that `(root, window)`, print
     `UPSERTED:<id>|created_slot<N>`. A retained frozen record never blocks a
     live launch and is never attached to; it stays restorable into a fresh
     window (`unique_window_name` disambiguates) and is listed distinctly by
     its `frozen_at`.
  4. Else → create (`state=live`, `window_slot=0`), print `UPSERTED:<id>|created`.
  In every create/update branch the caller's pane is stamped
  `@aitask_record=<id>`.
  Other branches:
  - record exists in `restoring` **and** the caller passes
    `--restore-of <id> --nonce <n>` (the hook forwards them from the
    replacement agent's environment, §D) → the **restore acknowledgement**:
    nonce must equal `op_nonce`; in `resume` mode `--session-id` must equal
    `codeagent_session_id` — else the store **persists**
    `last_error="<nonce>:session_mismatch"` (state unchanged) and prints
    `RESTORE_SESSION_MISMATCH:<id>` exit 7. The hook has no return channel to
    the detached coordinator, so the record *is* the channel: the coordinator
    and `reconcile` both read `last_error` for the current nonce and take the
    abort branch, never the liveness fallback. In `repick` mode the new
    session id is adopted. On success: `pane_id`/`pane_pid` updated from the
    caller's pane, `@aitask_record` stamped on it, state `live`, `ack=hook`,
    capture files deleted, print `UPSERTED:<id>|restored`;
  - record exists in `restoring` without `--restore-of`/`--nonce` → refuse,
    print `UPSERT_REFUSED:<id>|restoring_unacknowledged` (a stray session in
    a restoring pane is never an ack);
  - record exists in `freezing` / `frozen` → refuse, print
    `UPSERT_REFUSED:<id>|<state>` (a hook firing in a stand-in pane is a bug).
  Two callers: the SessionStart hook (child 3, normal path) and the freeze
  engine (child 4, fallback when the hook never fired). Both read
  `@aitask_record` off the pane first and pass `--id` when present, so a pane
  that was already recorded is never duplicated even after a `pane_id`
  recycle. A restore into a **new** pane (window gone) carries the record id
  in the environment, never on the pane, so it selects the old record instead
  of creating a second one.
- **Operation lease.** `freeze-begin`, `restore-begin` and `lease-take` mint
  `op_nonce` (8 hex), record `op_owner_pid` (the coordinator) and
  `op_started_at`, and print the nonce. **Every verb that mutates a record
  holding a lease** (`freeze-commit`, `freeze-abort`, `restore-launched`,
  `restore-confirm`, `restore-abort`, `standin-respawned`, the ack form of
  `upsert`) requires `--nonce <n>`; a mismatch prints `NONCE_MISMATCH:<id>`
  exit 6 and writes nothing — a coordinator that lost the race to
  `reconcile` fails closed instead of double-acting. `lease-take <id>` →
  `LEASED:<id>|<nonce>` is how `reconcile` (or a stand-in relaunch on a
  `frozen` record) acquires ownership: it is refused (`LEASE_HELD:<id>`)
  while a lease exists whose `op_started_at` is younger than
  `stale_op_grace` (default 60 s) **or** whose `op_owner_pid` is alive; a
  stale lease with a dead/unverifiable owner is taken over. Within the grace,
  or with a live owner, reconcile leaves the record alone. Lease-clearing
  transitions (`freeze-commit`, `freeze-abort`, `restore-confirm`, hook ack,
  `standin-respawned` out of `aborting`) clear the lease.
- **State machine** (every transition is one locked verb; illegal transitions
  print `TRANSITION_REFUSED:<id>|<from>|<verb>` exit 5 and write nothing):
  ```
  live ──freeze-begin──▶ freezing ──freeze-commit──▶ frozen ◀────────────────┐
   ▲                        │                          │                      │
   └────freeze-abort────────┘                          │ restore-begin        │ standin-respawned
   ▲                                                   ▼                      │ (same nonce)
   └──upsert (hook ack) / restore-confirm── restoring ──restore-abort──▶ aborting
  drop: any state → record removed + capture files removed
  ```
  `aborting` is **nonce-owned**: the record stays leased by the aborting
  attempt until its stand-in is back (`standin-respawned --nonce` → `frozen`,
  lease cleared). `restore-begin` on `aborting` → `TRANSITION_REFUSED`, so a
  user or a second controller cannot start another restore in the gap and
  an old coordinator cannot respawn over a newer attempt: its `standin-respawned`
  carries a stale nonce and is refused.
  **Captures are deleted only on a verified ack** (`ack=hook`). A
  liveness-only `restore-confirm` transitions to `live` but **keeps** the
  capture files (`ack=liveness`); they are removed on `drop` or liveness
  purge. This is what stops a malformed resume that starts a fresh session
  from destroying the only copy.
- Wrapper verbs (sole writer; `list`/`show` take no lock; exit 0/2/3
  `LOCK_BUSY`/4 `ERROR`/5 `TRANSITION_REFUSED`/6 `NONCE_MISMATCH`/7
  `RESTORE_SESSION_MISMATCH`/8 `LEASE_HELD`):
  `upsert --root <r> --window <w> --pane <id> --pane-pid <pid> [--id <rid>] [--session-id <sid>] [--transcript <p>] [--agent-string <s>] [--operation <op>] [--task-id <t>] [--restore-of <rid> --nonce <n>]`;
  `freeze-begin <id> --capture-ansi <p> --capture-txt <p> --lines <n> [--phase <t>]` → `FREEZING:<id>|<nonce>`;
  `freeze-commit <id> --nonce <n> --pane <pane_id|""> --pane-pid <pid|0>` → `FROZEN:<id>` (writes the stand-in's location: `pane_id`/`standin_pid` from the arguments; `--pane "" --pane-pid 0` is the gone-pane commit used by reconcile; `--pane` without `--pane-pid` or vice versa → usage error exit 2);
  `freeze-abort <id> --nonce <n>` → `LIVE:<id>` (captures deleted);
  `restore-begin <id> --mode resume|repick` → `RESTORING:<id>|<nonce>` (captures **retained**, `restore_attempts`+1, `launch_pid=0`, `last_error=""`);
  `restore-launched <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LAUNCHED:<id>` (records the replacement's `launch_pid` + location; written by the coordinator right after `respawn-pane`/`launch_in_tmux` returns — the nonce-bound evidence that the respawn happened);
  `restore-confirm <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LIVE:<id>|liveness` (captures **kept**; refused with `TRANSITION_REFUSED` unless `launch_pid != 0` and equals `--pane-pid`);
  `standin-respawned <id> --nonce <n> --pane <id> --pane-pid <pid>` → `STANDIN:<id>` (records the stand-in's `standin_pid` + location; from `aborting` it also transitions to `frozen` and clears the lease; from `frozen` (a `lease-take`n relaunch of a dead stand-in) it just updates and clears the lease; `freeze-commit` folds the same write in);
  `restore-abort <id> --nonce <n>` → `ABORTING:<id>` (captures retained; lease kept by the same nonce);
  `lease-take <id>` → `LEASED:<id>|<nonce>` / `LEASE_HELD:<id>` exit 8;
  `drop <id>` → `DROPPED:<id>`;
  `list [--state <s>] [--root <r>]` → `SESSION:<id>|<state>|<root>|<window>|<pane_id>|<task_id>|<agent_string>|<state_at>`;
  `show <id>` → `KEY:value` lines;
  `purge --observed <file>` → `DROPPED:<id>|<reason>` + `PURGED:<n>`.
  **Observation protocol (superset of the marks one, backward-compatible):**
  ```
  ROOT<TAB><root>                                   -- successfully enumerated root
  WINDOW<TAB><root><TAB><window>                    -- observed agent window
  PANE<TAB><root><TAB><window><TAB><pane_id><TAB><pane_pid><TAB><pane_dead>   -- every pane of that window
  INCOMPLETE                                        -- suppress every sweep
  ```
  `monitor_shared._write_observation_file()` gains a `panes=` argument and
  writes the `PANE` rows from `TmuxMonitor.last_discovered_panes()` (the
  `_LIST_PANES_FORMAT` already carries `pane_id` and `pane_pid`; `pane_dead`
  is appended to the format — see §B arity rule). The marks reader
  (`agent_marks._read_observed`) is extended to **skip** `PANE` rows so one
  file serves both purges; `agent_sessions` requires them. A file with
  `ROOT`/`WINDOW` but no `PANE` rows for an enumerated root is treated as
  pane-incomplete for that root: `dead_window` still applies, `dead_pane`
  does not (fail closed).
- **Purge policy** (fail-closed on `INCOMPLETE`, mirrors `sweep_liveness`):
  a `live` record whose `(root, window)` is absent from a successfully
  enumerated root → `DROPPED:…|dead_window`; a `live` record whose window has
  a `WINDOW` row **and** `PANE` rows, but whose `pane_id` appears in none of
  them (or appears with `pane_dead=1`) and whose `pane_pid` is dead
  (`os.kill(pid, 0)` → `ESRCH`; an `EPERM`/unverifiable pid is treated as
  alive) → `DROPPED:…|dead_pane` — this is what retires the stale candidates
  left behind by an ambiguous relocation. Two producers feed `purge`: the
  monitor maintenance tick (observation file above) and `aitask_frozen.sh
  reconcile`, which builds the same file from its own `list-panes` pass so
  retirement does not depend on a TUI being open. `freezing` / `frozen` / `restoring` /
  `aborting` records are never purged by liveness — they are reconciled by
  `aitask_frozen.sh reconcile` (§C/§D). A frozen record whose capture file is
  missing → `DROPPED:…|capture_missing`.
- `SessionsView` (mtime+size+inode gated) for the TUIs; `invalidate()` after
  every write. `standin_command(record_id) -> str` returns
  `ait frozenagent --record <id>` unless `AITASKS_FROZEN_STANDIN_CMD` is set
  (documented **test seam**; production never sets it).

#### B. Pane options (tmux user options, pane-scoped)

| Option | Set by | Cleared by | Read by | Meaning |
|---|---|---|---|---|
| `@aitask_record=<id>` | `upsert` (hook or freeze engine) | `drop`; pane death | freeze engine, restore coordinator, hook (`--id`) | the pane-visible join to its store record |
| `@aitask_frozen=<id>` | freeze engine, immediately before `respawn-pane` | `restore-confirm` path (coordinator), `drop` | `_LIST_PANES_FORMAT` (appended), `kill_agent_pane_smart` format, `aitask_companion_cleanup.sh`, `maybe_spawn_minimonitor` occupancy | this pane is a frozen stand-in — **authoritative** classifier |
| `@aitask_standin_ready=<id>` | **the viewer itself**, after mount (only the app stamps its own pane — `mark_monitor_pane` rule) | freeze engine + restore coordinator (`set-option -pu`) immediately **before** every `respawn-pane`; `drop` | `reconcile` | positive proof that the stand-in is up — the only signal that distinguishes "stamped, viewer running" from "stamped, agent still running" |
| `@aitask_agent_session=<sid>` | SessionStart hook on `$TMUX_PANE` | pane death | freeze engine fallback when the store has no session id | codeagent session id |

**Pane user options survive `respawn-pane`** (they are pane-scoped, not
process-scoped), which is why `@aitask_standin_ready` must be explicitly unset
before each respawn and why `@aitask_record` stays valid across freeze/restore
on the same pane. `#{pane_current_command}` is a process basename and is
**never** used as identity; `#{pane_pid}` (stored as `pane_pid`) and the
options above are the only server-observable identities reconcile reads.

Constants live in `monitor/monitor_core.py` beside `SHADOW_TARGET_OPTION`
(`RECORD_OPTION`, `FROZEN_OPTION`, `STANDIN_READY_OPTION`,
`AGENT_SESSION_OPTION`) and are mirrored in `lib/agent_sessions.sh` for shell
callers.

#### C. Freeze — `lib/agent_freeze.py` + `aitask_frozen.sh freeze <pane>|--all`

Runs **out of the agent pane** (from a TUI, a shell, or `run-shell -b`).
Every step is persisted before the next irreversible one:

1. Resolve the record: `@aitask_record` → `show`; else `upsert` (fallback).
   Read `codeagent_session_id`; if empty, try `@aitask_agent_session`.
2. `capture-pane -p -e -J -t <pane> -S -<cap>` via `TmuxClient.run` →
   `capture.ansi`; strip via `monitor/ansi_utils` → `capture.txt`.
3. `freeze-begin` → state `freezing`, capture paths persisted, **lease
   minted** (`op_nonce`, `op_owner_pid`=this coordinator).
4. `set-option -p -t <pane> @aitask_frozen <id>`; `set-option -pu -t <pane>
   @aitask_standin_ready` (clear any stale ready mark from a previous cycle).
5. `respawn-pane -k -t <pane> '<standin_command(id)>'` via the gateway.
   Window name unchanged, so `classify_pane` / `task_id_from_window_name`
   keep working. The viewer stamps `@aitask_standin_ready=<id>` on mount.
6. `freeze-commit --nonce <n> --pane <pane> --pane-pid <stand-in pid>` →
   state `frozen`, `standin_pid` + location recorded (read via
   `display-message -p -t <pane> '#{pane_id}\t#{pane_pid}'` after the
   respawn), lease cleared.

Failure at 1–3 → nothing to undo beyond temp files (`FREEZE_FAILED:<stage>`).
Failure at 4 → `freeze-abort --nonce`. Failure at 5 (tmux refused) → unstamp +
`freeze-abort --nonce`; the agent is still running. Failure at 6 (store busy)
→ the record stays `freezing`; **reconcile** completes it once the lease is
stale. A `NONCE_MISMATCH` at 6 means reconcile already resolved the record;
the coordinator reports it and exits without touching the pane.

**`aitask_frozen.sh reconcile`** (idempotent; run by the coordinator after
every freeze/restore, by the monitor maintenance tick beside
`_maybe_purge_marks`, and manually) resolves every non-`live` record **whose
lease is stale** (`op_started_at` + `stale_op_grace` elapsed **and**
`op_owner_pid` dead/unverifiable — otherwise the record is skipped as
in-flight) from server-observable facts only
(`list-panes -F '#{pane_id}\t#{pane_pid}\t#{pane_dead}\t#{@aitask_frozen}\t#{@aitask_standin_ready}\t#{@aitask_record}'`;
"agent alive" = `pane_pid == record.pane_pid`; "viewer here" =
`pane_pid == record.standin_pid`; "replacement here" =
`pane_pid == record.launch_pid`; "stand-in up" = `@aitask_standin_ready == id`;
"mismatch" = `last_error` begins with the current `op_nonce`):

| record state | pane observation | action |
|---|---|---|
| `freezing` | `@aitask_frozen==id` **and** stand-in up | `freeze-commit --pane <pane> --pane-pid <observed pid>` |
| `freezing` | agent alive, stand-in not up | unstamp both options, `freeze-abort` (captures deleted) |
| `freezing` | `@aitask_frozen==id`, stand-in not up, neither agent nor viewer pid, pane not dead | **indeterminate — no transition** (viewer may still be booting); re-checked next pass |
| `freezing` | `@aitask_frozen==id`, pane dead | respawn the stand-in (clear ready first), `standin-respawned`, then re-check |
| `freezing` | pane gone | `freeze-commit --pane "" --pane-pid 0` |
| `frozen` | pane gone | keep (restorable into a new window) |
| `frozen` | `@aitask_frozen==id`, pane dead | `lease-take`, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | mismatch recorded for this nonce | `restore-abort` (→ `aborting`), kill the wrong agent via `respawn-pane -k` back to the stand-in, `standin-respawned --nonce` (→ `frozen`) — **never** liveness-confirm |
| `restoring` | viewer here (`pane_pid==standin_pid`) — the coordinator died before or during the respawn, whether or not the ready mark survived | `restore-abort`; respawn the stand-in so it re-stamps ready; `standin-respawned --nonce` |
| `restoring` | `launch_pid==0` and pane pid is neither the viewer's nor the agent's | **indeterminate — no transition** (respawn may be mid-flight); after `stale_op_grace` ×2 → `restore-abort` + respawn stand-in + `standin-respawned --nonce` |
| `restoring` | replacement here (`pane_pid==launch_pid`), pane not dead, no mismatch, `state_at` + `restore_ack_grace` (default 20 s) elapsed | `restore-confirm --pane --pane-pid` (`ack=liveness`, captures kept) |
| `restoring` | pane dead | `restore-abort`, clear ready, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | pane gone | `restore-abort` with `pane_id=""`, then `standin-respawned --nonce --pane "" --pane-pid 0` (→ `frozen`, restorable into a new window) |
| `aborting` (stale lease taken over) | stand-in up (`@aitask_standin_ready==id`) | `standin-respawned --nonce` (→ `frozen`) |
| `aborting` (stale lease taken over) | anything else | clear ready, respawn the stand-in, `standin-respawned --nonce` (→ `frozen`) |

Every reconcile action on a leased record is preceded by `lease-take`; a
`LEASE_HELD` answer means a live coordinator owns it and reconcile skips.

A liveness confirm therefore requires **positive evidence** that the
process in the pane is the one the coordinator launched (`launch_pid`), and
a viewer whose ready mark was cleared is still recognised by `standin_pid`.

Failure injection: `AITASKS_FREEZE_FAIL_AT=capture|begin|stamp|respawn|commit`,
`AITASKS_RESTORE_FAIL_AT=begin|respawn|ack`, and `AITASKS_FROZEN_PAUSE_AT=<stage>`
(the coordinator `SIGSTOP`s itself so a test can run a concurrent
`reconcile` and then `SIGCONT`) — documented test seams, honoured only under
`AITASKS_TEST_MODE=1`.

**Cleanup contract** (`aitask_companion_cleanup.sh` + `count_other_real_agents`
must agree — pinned by the parity test):
- a `@aitask_frozen`-stamped pane **counts as a real agent sibling** (the
  window exists to hold it; killing agent B must not destroy frozen A's viewer);
- when the *dying* pane is the stamped one, the cleanup script **abstains
  entirely** (it is being respawned, not departing);
- `kill_agent_pane_smart` on a frozen pane = `drop` + kill by the same rule.

#### D. Restore — `lib/agent_restore.py` + `aitask_frozen.sh restore <id> [--repick] | --all`

**Never runs inside the pane it replaces.** The viewer's `R`/`p` keys and the
minimonitor keys invoke `run-shell -b "<repo>/.aitask-scripts/aitask_frozen.sh restore <id>"`
through the gateway; the coordinator is a detached process that outlives the
respawn. Two-phase, acknowledged:

1. Build the argv: `aitask_codeagent.sh --agent-string <s> --resume-session <sid> --dry-run invoke raw`
   (resume) or the existing pick launch argv (`--repick`, task id required).
   Empty session id and no `--repick` → `RESTORE_FAILED:no_session` (nothing changes).
2. `restore-begin --mode <m>` → state `restoring`, lease minted (nonce `n`);
   captures and `@aitask_frozen` retained.
3. Prefix the argv with the **restore identity environment** (the
   `explore-relay` `env` precedent — `env` execs into the agent, so the pane
   pid is still the agent's):
   `env AITASK_RESTORE_RECORD=<id> AITASK_RESTORE_NONCE=<n> AITASK_RESTORE_MODE=<m> AITASK_RESTORE_EXPECT_SESSION=<sid> <argv>`.
   Then `set-option -pu @aitask_standin_ready` and
   `respawn-pane -k -t <stand-in> '<env argv>'` — or, when `pane_id=""`,
   `launch_in_tmux` into a new window with the recorded name. Immediately
   after tmux returns, read the new `#{pane_pid}` and write
   `restore-launched --nonce --pane --pane-pid` — the nonce-bound evidence
   that a replacement was actually started. The replacement agent's
   SessionStart hook forwards the four variables as `upsert --restore-of
   --nonce --session-id` (§A ack rules), which is what selects the **old**
   record from a brand-new pane, verifies the resumed session id, and stamps
   `@aitask_record` there.
4. Wait for the ack: poll `show <id>` until `state=live`, `last_error`
   carries this nonce, **or** `restore_ack_grace` elapses.
   - `live` with `ack=hook` → clear `@aitask_frozen`, print `RESTORED:<id>|hook`
     (captures already deleted by the ack).
   - `last_error="<nonce>:session_mismatch"` (the hook reported a different
     session in `resume` mode; persisted by the store because the hook has
     no channel to this process) → `restore-abort --nonce` (→ `aborting`,
     still owned by this nonce), `set-option -pu @aitask_standin_ready`,
     `respawn-pane -k` back to the stand-in, then `standin-respawned --nonce
     --pane --pane-pid` (→ `frozen`), print `RESTORE_FAILED:<id>|session_mismatch`;
     **capture intact**. The same abort → respawn → `standin-respawned --nonce`
     sequence is used by every failure branch below; a `NONCE_MISMATCH` at
     any step means reconcile already finished the abort.
   - grace elapsed, pane alive, `pane_pid == launch_pid`, no hook ack and no
     error → `restore-confirm --nonce --pane --pane-pid` → `live` with
     `ack=liveness`, **captures kept**, clear the stamp, print
     `RESTORED:<id>|liveness` (the viewer/minimonitor show "restored,
     unverified — capture kept").
   - pane dead at any poll (invalid session, binary missing, immediate exit)
     → `restore-abort --nonce`, clear ready, respawn the stand-in,
     `standin-respawned --nonce`, print `RESTORE_FAILED:<id>|agent_exited` —
     **the capture is intact and the viewer is back**.
   - `NONCE_MISMATCH` on any verb → reconcile already settled it; exit
     without touching the pane.
5. Coordinator crash between 2 and 4 → `reconcile` (§C table) settles it
   once the lease is stale.

`aitask_codeagent.sh` gains a global `--resume-session <sid>` (template
`OPT_HEADLESS`): `claude --model <id> --resume <sid>`, `codex resume <sid>`
(model flag per codex CLI), opencode → `RESUME_UNSUPPORTED:opencode` exit 2.
Resolution stays single-sourced in `lib/agent_string.sh`. Restore-All iterates
`frozen` records; per-record failures are reported, never abort the batch.


---

## Post-Review Changes

### Change Request 1 (2026-09-10 11:40)
- **Requested by user:** Two confirmed correctness concerns raised at Step-8
  review, both blocking.
  1. `frozenagent/how-to.md` called the capture "the only copy of that agent's
     output". A freeze captures with `capture-pane -S -<cap>`, so it retains only
     the **tail** of the scrollback — earlier output can already be out of reach
     before the freeze runs. The destructive warning overstated what the record
     preserves.
  2. `frozenagent/reference.md` described `frozen.restore_ack_grace` as "the
     difference between a `restored` and a `restored, unverified` outcome".
     `agent_frozen_ops` uses it only as the **acknowledgement waiting period**
     before liveness fallback; a record whose agent never acknowledges stays
     unverified however high the grace is, so the table promised a guarantee the
     setting cannot give.
- **Changes made:**
  1. Reworded the drop warning to say dropping deletes the *retained capture*,
     and added a paragraph stating the capture is the tail of the scrollback,
     bounded by `frozen.capture_max_lines` (50000 by default).
  2. Rewrote the `restore_ack_grace` table cell as "how long a restore waits for
     the resumed agent's SessionStart hook to acknowledge it, before falling back
     to confirming on liveness alone", and replaced the follow-on paragraph with
     an explicit "waiting period, not an outcome" note naming the two cases that
     never acknowledge (a CLI that reports no session on startup; the session
     hook not installed). Also widened the `capture_max_lines` cell with the
     same tail-not-total correction.
- **Files affected:** `website/content/docs/tuis/frozenagent/how-to.md`,
  `website/content/docs/tuis/frozenagent/reference.md`
- **Re-verified:** `hugo build --gc --minify` clean; `check_links.py --build`
  30173 resolved / 0 broken.

### Note on a concurrent change (not part of this task)
While this task was in implementation, **t1766** landed in the working tree from
another session: `frozenagent_app.py` now derives its restore watch deadline from
`frozen.restore_ack_grace` via `agent_frozen_ops.restore_settle_timeout`, so the
viewer no longer differs from the monitors. Those two files
(`.aitask-scripts/frozenagent/frozenagent_app.py`,
`tests/test_frozenagent_app.py`) are **deliberately not staged by this task**.
The `## Configuration` section was rewritten to describe the knob in terms that
hold whether or not t1766 lands, so no page asserts the difference either way.

### Change Request 2 (2026-09-10 11:52)
- **Requested by user:** `frozenagent/how-to.md:70-72` said "restore or re-pick
  instead — both keep it", and `_index.md:116-120` said "**R** and **p** do not
  confirm — nothing is lost if you change your mind". Both are false guarantees:
  a user trying to preserve the transcript could pick restore or re-pick on that
  basis and lose it.
- **Verified:** CONFIRMED at `.aitask-scripts/lib/agent_sessions.py:798-807` —
  the hook-ack success path sets `ack="hook"` and calls `remove_captures(rec.id)`,
  and **both** `resume` and `repick` modes reach it (repick adopts the new
  session id and falls through to the same block). So the retention matrix is:
  verified restore → **deleted**; verified re-pick → **deleted**; liveness-only
  restore → kept; failed restore → kept; drop → deleted.
  The same pages already stated this correctly in the outcome tables
  (`restored` → "the capture is deleted"), so the prose contradicted the table.
- **Changes made:** a third false statement was found in the same sweep and
  fixed alongside the two reported.
  1. `how-to.md` "Bring an agent back": replaced "neither destroys anything" with
     the accurate reason R/p need no confirmation (a *failed* attempt leaves the
     viewer and capture intact), and added an explicit paragraph that a
     successful verified restore or re-pick deletes the capture — copy with `y`
     first if retention matters.
  2. `how-to.md` "Remove a frozen record": dropped the "restore or re-pick
     instead — both keep it" advice; now states drop is the only action that
     discards record + transcript *and* leaves nothing running, while noting a
     verified restore/re-pick deletes the capture too.
  3. `_index.md` restore/re-pick/drop list: same correction, plus a standalone
     paragraph naming the two cases where the capture survives (failed attempt,
     or `restored, unverified`).
- **Files affected:** `website/content/docs/tuis/frozenagent/how-to.md`,
  `website/content/docs/tuis/frozenagent/_index.md`
- **Re-verified:** swept every remaining `capture kept` / `capture is deleted`
  claim across `website/content/docs/tuis/` for consistency with the matrix
  above; `hugo build --gc --minify` clean; `check_links.py --build` 30173
  resolved / 0 broken.

### Change Request 3 (2026-09-10 12:03)
- **Requested by user:** `frozenagent/how-to.md:49` said re-pick "is the only
  option when the record carries no task id". That is inverted — re-pick is the
  option that *requires* a task id.
- **Verified:** CONFIRMED at `.aitask-scripts/frozenagent/frozenagent_app.py:851-853`
  — `if repick and not rec.task_id:` notifies
  `"This record has no task id — restore instead"` and returns. The mirror guard
  is at `.aitask-scripts/lib/agent_restore.py:340-344`: a `resume` with no
  `codeagent_session_id` returns `RESTORE_FAILED:<id>|no_session`, commented as
  "the reason `--repick` exists". So the two routes need *different* ids and a
  record may carry only one. `_index.md:114` and `reference.md:26` already stated
  the task-id requirement correctly; only the how-to was wrong.
- **Changes made:** replaced the inverted clause with an explicit pair — re-pick
  needs a task id (quoting the viewer's refusal), restore needs a recorded
  session id.
  - **Self-caught while writing the fix:** the first draft quoted `no_session` as
    if the user sees it. They do not — the coordinator runs detached under
    `run-shell -b`, so its stdout is unreadable, `restore-begin` never runs,
    `restore_attempts` never bumps, and the viewer's pre-begin gate reports
    `restore did not start — run 'ait frozenagent' or reconcile` after the
    dispatch grace. Reworded to describe the behaviour and quote the message the
    user actually gets.
- **Files affected:** `website/content/docs/tuis/frozenagent/how-to.md`
- **Re-verified:** `hugo build --gc --minify` clean; `check_links.py --build`
  30173 resolved / 0 broken.
- **Deferred to t1705_10 (noted, not written here):** `restore` is also refused
  for an agent whose CLI has no resume support
  (`RESTORE_FAILED:<id>|resume_unsupported:<agent>`, `agent_restore.py:345-348`).
  That is a per-agent recovery limitation and belongs in t1705_10's
  "When something goes wrong" section rather than in a TUI-surface page.

### Change Request 4 (2026-09-10 12:07)
- **Requested by user:** the plan deferred the `resume_unsupported` limitation
  (and the other config/behaviour facts) to t1705_10, but no durable note had
  been sent — `aitask_query_files.sh inbox 1705_10` showed only the older
  t1705_8 entry. A sentence in this plan is not context t1705_10 receives.
- **Verified:** CONFIRMED. The inbox held exactly one unread note, from t1705_8.
  The "Follow-ups to file" bullet in this plan was written as an intention, and
  nothing had executed it.
- **Changes made:** sent the note via the `/aitask-note` skill.
  `NOTE_APPENDED:2026-09-10T09:04:57Z.c3ed18370a74314077320714|aitasks/t1705/t1705_10_freeze_restore_workflow_docs.md`,
  `from_verified=yes`. Live lane returned `LIVE_NONE:unlocked` — nobody is
  holding t1705_10 on this host, which is a success with live delivery
  unavailable, not a partial failure. The note carries five verified facts with
  source citations (opencode `resume_unsupported` and the affected-agent set; the
  task-id vs session-id requirement pair; the full capture-retention matrix
  including that a verified re-pick deletes the capture; `capture_max_lines` as
  scrollback depth; `stale_op_grace` as a non-knob) and two explicitly
  moment-relative pointers to re-check rather than believe (t1773's closed-window
  restore, and t1766 having appeared uncommitted in the working tree).
- **Files affected:** `aitasks/t1705/t1705_10_freeze_restore_workflow_docs.md`
  (its `## Inbox`, written and committed by the note framework — not staged by
  this task's code commit).

---

## Final Implementation Notes

- **Actual work done:** Wrote the frozen-agent TUI documentation set — three new
  pages under `website/content/docs/tuis/frozenagent/` (`_index.md` at weight 16,
  `how-to.md`, `reference.md`) — and threaded frozen agents through the shipped
  monitor/minimonitor docs, the TUIs and commands indexes, and three
  `aidocs/framework` files. Twelve files, all documentation; no code, no tmux.
  Verified with `hugo build --gc --minify` and `check_links.py --build`
  (30173 links resolved, 0 broken) after every edit round.

- **Deviations from plan:** three, all forced by the tree rather than chosen.
  1. **`tmux_gateway.md` had no `@aitask_*` inventory to extend.** The plan (and
     the task) described "joining the inventory (:112-129)"; that range is prose
     naming a single option. I created the table instead, seeding it with all six
     options and the two properties that make them load-bearing (they die with
     the pane, they survive `respawn-pane`).
  2. **The forward `{{< relref >}}` to `workflows/freeze-and-restore-agents` was
     omitted deliberately.** The task text and the prior plan both called for it,
     but that page does not exist until t1705_10 and Hugo *fails the build* on a
     relref to a missing page. t1705_10's own plan (step 5) already owns adding
     the cross-link, so nothing is lost.
  3. **Sub-page weights follow the task's stated 20/30 (applink form)** rather
     than the 10/20 used by the monitor family. Both order how-to before
     reference; the numbers are invisible to readers.

- **Issues encountered:**
  - **A concurrent session landed t1766 in the shared working tree mid-task.**
    `frozenagent_app.py` and `tests/test_frozenagent_app.py` showed as modified
    though this task never touched them: the viewer now derives its restore watch
    deadline from `frozen.restore_ack_grace` via
    `agent_frozen_ops.restore_settle_timeout`. Both files were left **unstaged**
    — they belong to t1766 — and the `## Configuration` section was rewritten to
    describe the knob in terms that hold whether or not t1766 lands, so no page
    asserts a viewer-vs-monitor difference either way.
  - **Four rounds of blocking review concerns, all confirmed and all mine.** They
    are recorded individually above; the through-line is that every one was a
    place where prose I wrote contradicted a table I had *also* written from the
    source. The outcome tables were right each time; the surrounding sentences
    were the failure. Sweeping for the claim rather than fixing the reported line
    found a third instance in CR2 that had not been reported.
  - **Duplicate keybinding rows twice.** Appending `k`/`R`/`p` rows to the
    monitor and minimonitor tables collided with existing rows for the same keys.
    Correct fix was to widen the existing row, since these keys keep their live
    meaning and only *branch* when the target is frozen — which is also the more
    accurate description of the code.

- **Key decisions:**
  - **No `ait frozen` row in the commands table.** `aitask_frozen.sh:38-39`
    explicitly deferred that call to this task. `ait` has no `frozen` case, and
    `aitasks_extension_points.md:348` ("the `ait` dispatcher is user-facing only")
    is the standing reason to keep an internal engine face out of it. Recorded
    here as the decision, not just an omission.
  - **Documented the wiring asymmetry rather than flattening it.** The keys are
    identical to a user, but monitor binds `p` frozen-only while minimonitor
    branches inside `pick_task_by_number`, and mirror-image for `R`. A reference
    table that listed one action id per key would be wrong for one of the apps.
  - **`restored, unverified — capture kept` is documented as a success**, with
    the reason (nothing confirmed the session) and the consequence (the capture
    is kept). Left unexplained it reads as a fault.
  - **Fixed two pre-existing parked-doc inaccuracies inline** (user-directed):
    minimonitor never documented its `Np` counter, and claimed marks "do not
    change any counter". Adding `Nf` beside an undocumented `Np` would have made
    the page wrong twice over.
  - **Reworded `monitor/how-to.md:251` and `minimonitor/how-to.md:147`**, which
    used "frozen" in the ordinary English sense ("a frozen dot", "the header and
    name are frozen") next to a newly-real lifecycle state named `frozen`.

- **Upstream defects identified:**
  - `monitor_app.py:3549` / `minimonitor_app.py:3017` — the frozen-drop
    confirmation body advises "restore or re-pick it instead if you still want
    it", which implies those routes preserve the capture. A *verified* restore or
    re-pick deletes it (`agent_sessions.py:798-807`); only a failed or
    liveness-only restore keeps it. The dialog's advice is right about not losing
    the *agent* and misleading about keeping the *transcript*.
  - `frozenagent_app.py:134,927` — the viewer's drop confirmation uses the verb
    **"Remove"** ("Remove the frozen record and its capture?") while both monitors
    use **"Drop"** with a matching title, deliberately chosen in t1705_7 so the
    destructive verb names itself. Same operation, two verbs across three
    surfaces.

- **Notes for sibling tasks:** t1705_10 has been sent a durable `ait note`
  (`2026-09-10T09:04:57Z.c3ed18370a74314077320714`, `from_verified=yes`) carrying
  the five verified facts most likely to be documented wrongly — opencode's
  `resume_unsupported` refusal and which agents do support resume, the task-id vs
  session-id requirement pair, the full capture-retention matrix, `capture_max_lines`
  as scrollback *depth*, and `stale_op_grace` as a non-knob — plus two
  explicitly moment-relative pointers to re-check rather than believe (t1773's
  closed-window restore, and t1766's uncommitted appearance in the tree). The
  general lesson for any sibling writing prose about this subsystem: the
  behaviour is asymmetric almost everywhere (per-agent, per-app, per-outcome),
  so a sentence that generalises across agents, across the two monitors, or
  across restore outcomes is probably false — check the specific branch.
