# The shadow companion agent

Specialist guidance for the **shadow** agent — an advisory companion coding agent
that watches another running agent (the *followed agent*) and helps the user
reason about what it is doing. Read this when editing the `aitask-shadow` skill,
its capture / context helpers, the minimonitor trigger, or any code that
classifies or cleans up shadow panes.

The shadow is **advisory-only**: it is read-only with respect to the followed
agent and never sends keystrokes, answers, or any input into the followed pane.
It explains and suggests; the user acts.

When the shadow reviews a plan it also emits a structured, machine-parseable
**concern block** the user can selectively forward to the followed agent via
minimonitor's concern picker — see `.claude/skills/aitask-shadow/concern-format.md` for the format
and parser contract. For an *implementation* review the picker also splits the
list by the finding's **disposition** (derived from the body's terminal
`Disposition:` trailer), so items the shadow is not asking you to act on sit in
their own dimmed section and are skipped by bulk-select.

When some marker lines in the block could not be parsed, the picker's warning
banner is backed by an affordance: `u` opens a read-only view of the offending
lines plus the raw block region, so an over-bound split marker can be told apart
from a producer typo and reported. When *no* marker parsed — so there is no
picker to hang the banner on — that view opens directly instead.

## Pipeline: capture → context-fetch → skill

The shadow is built from three composable pieces. Workflow-phase detection is
**not** one of them: it is an advisory signal read alongside the capture, never a
pipeline stage the shadow must pass through — see "Phase detection (advisory)"
below.

1. **Capture** — `.aitask-scripts/aitask_shadow_capture.sh` reads the
   followed agent's current screen through the tmux gateway and emits cleaned,
   escape-free text on stdout. **It takes no pane argument in the normal flow**:
   it resolves the followed pane from the shadow's own `@aitask_shadow_target`
   binding, so the id never has to be transcribed by the model (see "Rule: the
   validated pane binding, not the argument, is the source of truth" below). An
   explicit `<pane_id>` remains supported for manual invocations and for callers
   that are not shadows. It is re-run on demand, so the shadow always reads
   the followed agent's *current* state rather than a frozen launch-time
   snapshot. A `-` argument cleans pre-captured text from stdin (also the test
   seam). All tmux access goes through `lib/tmux_exec.sh`
   (`tests/test_no_raw_tmux.sh`). The deep-analysis sub-procedures
   (`plan-explain` / `plan-challenge` / `plan-socratic` / `plan-assumptions` /
   `impl-challenge`) recapture with `--deep` (the script's
   `SHADOW_PLAN_CAPTURE_LINES`, default
   400) because a whole plan can exceed the 200-line default and be truncated to
   its tail; ordinary reads (explain-output, help-answer-prompt,
   diagnose-errors) stay at the default depth to stay cheap. Minimonitor's own
   capture of the *shadow* pane (the concern picker and its auto-offer) also
   uses `--deep`, for the same reason from the other side: what it is reading is
   plan-review output, and at the narrow width a shadow pane runs at, the
   200-line window can start inside the concern block and clip its opening
   fence (t1187).
2. **Context-fetch** — `.aitask-scripts/aitask_shadow_context.sh <task_id>`
   resolves the followed agent's task file and most-recent plan, emitting
   `TASK_FILE:` / `PLAN_FILE:` lines (`--siblings` adds `SIBLING:` lines). For
   deeper / historical plan content the skill calls the established public helper
   `aitask_explain_context.sh --max-plans N <files>`. Context is fetched only
   when the request needs it (most importantly when the screen shows an
   `AskUserQuestion` without its source task/plan visible); a `NOT_FOUND` or
   unknown task id degrades gracefully rather than blocking.
3. **Skill** — `/aitask-shadow`, a **user-invocable** static command (see "The
   skill" below) that ties the two helpers together and serves the user's
   free-form request.

## The skill (`/aitask-shadow`)

Source: `.claude/skills/aitask-shadow/` — the `SKILL.md.j2` authoring template
plus nine sub-procedure `.md` files (five `plan-*.md`, `impl-challenge.md`,
`impl-review-angles.md`, `concern-format.md`, `spawn-learn-skill.md`).

It is **user-invocable** (`user-invocable: true`) **and profile-aware** — the
canonical stub + `.md.j2` pair of `aidocs/framework/stub-skill-pattern.md`,
resolver key `shadow`. The two properties are independent, and it is worth
naming the confusion this doc used to encode: the skill's user-invocability
follows from the spawn path (a spawned agent CLI can only be triggered
non-headlessly by a slash command on argv, and a freshly spawned shadow has no
parent skill to read-and-follow a non-invocable one), but that argues **only**
for `user-invocable: true` — it never implied staticness. `aitask-explore` is
likewise both user-invocable and templated. The conversion also means the nine
sub-procedures are rendered into the Codex and OpenCode trees, which the former
"Source of Truth" redirects never reached.

Argument contract (unchanged by the conversion — the stub forwards ARGUMENTS
verbatim after stripping an optional `--profile <name>`):

```
/aitask-shadow <followed_pane_id> [<source_task_id>]
```

The launcher passes only the pane id (argv-safe) and, when known, the task id;
the skill self-captures the screen on demand — argv cannot carry 100+ KB of
screen text.

The skill runs **one instruction-driven flow** (no mode selector); the user's
free-form ask once it is running decides which capability applies:

- **Step 0 — greeting.** On startup, before any capture or fetch, it greets the
  user and presents its capability list. The list is **derived from Step 3**,
  which is the single source of truth — a maintainer note in `SKILL.md` forbids
  hardcoding a second copy (the drift this design exists to prevent).
- **Step 1 — capture, with a proactive suggestion.** After *every* capture (the
  first and each refetch) the shadow takes a lightweight look at what is
  *visibly* on screen and, if a capability is obviously useful, offers it
  unprompted (e.g. an `AskUserQuestion` is up → offer to help decide; a plan
  awaits approval → offer to explain / challenge / surface assumptions). This is
  explicitly **not** a workflow-phase classifier and never gates what the user
  can ask — it is one advisory suggestion they can take or ignore.
- **Step 2 — context-fetch** as described above, only when the request needs it.
  It is also where a source task id is picked up when the launch arguments did
  not carry one — the id the rejection store is keyed by (see "Concern rejection
  store").
- **Step 3 — serve.** Simple, free-form-expressible asks are handled **inline**
  (explain the output / "what is the agent doing?"; help answer an
  `AskUserQuestion` by laying out the options and *suggesting* an answer the user
  types themselves). Several **structured analyses** each live in a
  read-and-follow sub-procedure with a defined methodology (four review a plan;
  one reviews the implementation; one diagnoses the followed agent's errors):
  - `plan-explain.md` — explain a plan to a non-expert: surface the technical
    subjects the plan rests on and offer per-subject introduction + motivation
    (multiSelect), then a plain-language walkthrough.
  - `plan-challenge.md` — adversarial stress-test: attack regressions, edge
    cases, wrong-shape, blast-radius / "edited unaware", verification gaps, and
    unstated dependencies; produce a prioritized list and separate fatal from
    fixable.
  - `plan-socratic.md` — open-ended, non-leading questions (2–4 at a time) that
    lead the user to examine the plan's own reasoning.
  - `plan-assumptions.md` — enumerate the plan's assumptions
    (environment / data / behavior / sequencing / intent) and flag the
    load-bearing-and-unverified ones first.
  - `impl-challenge.md` — adversarially review the **implementation** (the code
    actually written), at one of four effort tiers (quick / default / advanced /
    deep) whose angle texts live in `impl-review-angles.md`. It opens with a
    **review-state assessment**: resolve the plan, resolve the diff as the
    *composite* of four channels (committed / staged / unstaged / untracked),
    list the included paths, and state the attribution limit. The assessment
    **states, never prompts** — see the anti-gating note below. Tier resolution
    is: a tier named in the user's ask, else the profile's
    `shadow_impl_review_tier`, else a 4-option prompt.
  - `plan-diagnose-errors.md` — diagnose skill/helper errors the followed agent
    hit (tool-call errors / retries), present candidate concerns for the user to
    pick from, and offer to spin chosen ones into `/aitask-explore` fix-tasks.
    On-request only — never offered proactively. (Detailed signal list lives in
    the sub-procedure, not here.)

  Every sub-procedure that emits a concern block —
  `plan-challenge.md`, `plan-assumptions.md`, `plan-diagnose-errors.md` and
  `impl-challenge.md` — first consults the per-task rejection store and drops
  concerns the user already rejected, reporting how many it suppressed (see
  "Concern rejection store").

  A broad ask ("review this plan") runs several sub-procedures in sequence.

## Spawn path and binding

The shadow is launched with the `e` key (`E` to pick the code agent / model
first) from **two** surfaces: **minimonitor** (`action_launch_shadow` in
`monitor/minimonitor_app.py`, acting on the followed agent) and **`ait monitor`**
(`monitor/monitor_app.py`, acting on the *selected* agent). Each resolves the
agent's pane id and task id, builds the command via the `shadow` codeagent
operation (`aitask_codeagent.sh`), and delegates the mechanics to the shared
`spawn_shadow` in `monitor/monitor_core.py` — by default a split in the **same
window**, configurable to a separate window.

Each app keeps a thin `_spawn_shadow` method. These are **policy adapters, not
pass-through seams**: the two decisions below differ per app, and inlining them
at both call sites in each app would replicate them four times instead of twice.

The spawn glue sets the pane-scoped tmux user option
`@aitask_shadow_target = <followed_pane_id>` (constant `SHADOW_TARGET_OPTION` in
`monitor/monitor_core.py`) on the new shadow pane. That option is the
**authoritative** classifier *and* lifecycle binding: it drives exclusion from
agent lists, the `kill_agent_pane_smart` real-agent count, and the
`aitask_companion_cleanup.sh` auto-kill when the followed agent dies. Because an
unstamped shadow is indistinguishable from a real agent *forever* — it lists as
an agent, is targeted by `k` / `n`, counts as a real sibling, evades the
duplicate guard, and is never cleaned up (job 1 matches on the marker) — a stamp
failure is retried once and then the just-created pane is **killed**; no cleanup
hook is installed and the caller reports an error. See `tui_conventions.md`
(companion-pane section) and `tmux_gateway.md` (multi-agent per window).

### Rule: the validated pane binding, not the argument, is the source of truth

A pane id that travels through a model can be mangled — a Codex shadow was
observed transcribing `%237` as `%7`. The dangerous case is not a mistyped id
that fails: it is a mangled id that happens to name a **live** pane, because the
capture then *succeeds*, raises nothing, and the shadow advises on another
agent's work. `aitask_shadow_capture.sh` closes that structurally (t1319).

- **No argument ⇒ resolve from the binding.** The helper reads
  `@aitask_shadow_target` off its own `$TMUX_PANE` and captures that. The
  skill's Step 1 and every `--deep` sub-procedure use this form, so in the
  spawned flow the id never enters the model's token stream at all.
- **The binding counts only if it is on the gateway server.** `ait_tmux`
  addresses the dedicated `ait` socket while `$TMUX_PANE` names a pane on
  whatever server the *caller* is attached to, and **pane ids collide across
  servers**. One `display-message` fetches `#{socket_path}` and the option
  together and compares the socket against `$TMUX`'s; a mismatch yields
  `cross-server`, never a binding. Without this the helper could read an
  unrelated gateway pane's binding and capture *its* followed agent.
- **Four states, deliberately not three.** `shadow_self_target` returns `""`
  (no `TMUX_PANE`), `unbound`, `bound:<id>`, or `cross-server`. "Verified
  unbound" and "could not verify" must stay distinct — collapsing them is what
  reopens the hole on the explicit-argument path.
- **An explicit `<pane_id>` is checked against that state.** Allowed with no
  tmux context, or same-server-unbound, or same-server-and-matching; **refused
  with exit 2** when the binding names a different pane, and when the caller is
  `cross-server`. `--any-pane` overrides.
- **A bounded wait bridges the stamp race.** `spawn_shadow` stamps the option
  only *after* `launch_in_tmux` returns, so a shadow's first capture can outrun
  its own binding. The no-argument path polls for `SHADOW_BIND_WAIT_MS`
  (default 2000) and then **fails closed** — it never falls back to a guess.
  Only `unbound` is waited on; `""` and `cross-server` are properties of where
  the process runs and cannot change. The explicit path never waits, so the
  per-tick TUI capture is not slowed.

**One sanctioned opt-out.** `capture_shadow_text` (`monitor/monitor_core.py`)
passes `--any-pane`, for two independent reasons: its pane id comes from
`find_shadow_pane`, so there is no transcription to guard; and a TUI run from the
user's personal tmux while the framework is on `-L ait` is a cross-server caller,
whose refusal would reach the user as a silent "no concerns" (the call sends
stderr to `DEVNULL` and maps a non-zero exit to `None`). Do not copy the flag to
any caller whose pane id is model-supplied — the learner spawned by
`spawn-learn-skill.md` deliberately does **not** use it.

`tests/test_shadow_capture.sh` proves each guard against live tmux, including a
two-server fixture with **colliding pane ids** and a launch-order fixture that
stamps only after the capturing pane has started.

### Rule: `companion_pane` is per-app policy, never `TMUX_PANE`

`spawn_shadow` takes `companion_pane` as an explicit keyword parameter and
**never reads `TMUX_PANE` itself**. The value is the pane
`aitask_companion_cleanup.sh` despawns once the followed agent's window holds no
real agent besides the dying one — and that script's job-2 `kill-pane` has **no
marker check and no confirmation**.

- **minimonitor passes its own `TMUX_PANE`.** It *is* the followed agent's
  companion and shares its window, so it should be despawned with the agent.
- **monitor passes `None`** (meaning "bind to the newly created shadow pane").
  The monitor is not the agent's companion and normally lives in another window;
  passing its own pane would make the agent's exit **kill the monitor**, on an
  arbitrary delay, after the session that armed the hook has ended.

The shadow itself is cleaned up either way: job 1 kills every pane in the session
whose `@aitask_shadow_target` matches the dying agent, regardless of what
`companion` names.

### Rule: the cleanup hook is append-only, never an overwrite

A bare `set-hook -p … pane-died` writes index `[0]` and therefore *replaces*
whatever sits there. Two panes can each be a companion of the same agent (a
minimonitor arms it, then a monitor-side spawn arms it again), so
`attach_companion_cleanup_hook` (`lib/agent_launch_utils.py`) never overwrites. It
returns which of three things happened:

- `"existing"` — a `pane-died` hook already invokes
  `aitask_companion_cleanup.sh`; nothing is installed. Complete because job 1 is
  marker-driven, so the new shadow is still cleaned up and the prior companion
  contract survives.
- `"unverified"` — the `show-hooks` probe failed, so "no hook" cannot be
  distinguished from "someone else's hook". **Fails closed**: installs nothing.
  Overwriting is silent and persistent; skipping merely leaves a shadow to close
  by hand, which is bounded and visible. Callers surface this as a warning.
- `"installed"` — appended at the first free `pane-died` index, so an unrelated
  `pane-died` hook is preserved rather than destroyed.

`remain-on-exit on` is set in every case (idempotent, and the pane should still
fire `pane-died` for a hook someone else armed).

Because the hook is append-only, its `companion_pane` argument is a
**best-effort hint, not the cleanup authority** — it can only ever name whichever
companion armed the hook first, and `spawn_shadow` passes
`companion_pane or shadow_pane`, so from the full monitor (where `companion_pane`
is `None`) it names the shadow's own pane. `aitask_companion_cleanup.sh`
therefore discovers *both* companion kinds from their markers —
`@aitask_shadow_target` for shadows, `@aitask_monitor_kind` for
monitor/minimonitor companions — and falls back to the argument only for a pane
predating the markers. See "Companion pane auto-despawn" in
`tui_conventions.md`.

### Where these two rules are proven

`tests/test_monitor_shadow_pick.py` pins them through mocks — it can show which
arguments the monitor passes, not what they do. The executable proof of the
*effect* is `tests/test_monitor_shadow_spawn_live.sh`: it spawns a shadow from
the real `MonitorApp` action against a throwaway tmux server, lets the
`pane-died` hook fire, and watches the shadow die while a monitor stand-in pane
in another window survives — plus the `"existing"` / append-at-`[1]` branches and
the focus-retention contract on both placements.

That test is **tmux-destructive** and calls `require_clean_ait_server`
(`tests/lib/tmux_isolation.sh`) *before* `require_isolated_tmux`: isolation alone
cannot contain `aitask_companion_cleanup.sh`, which reaches tmux with raw,
un-flagged calls by design.

### Rule: creating a shadow uses a live lookup, not the snapshot cache

`find_shadow_pane` (and `_current_shadow_pane_id` in the monitor) answer *"is
there a shadow to **read**"* — the preview, key forwarding and the concern
picker, where lagging a refresh tick is the intended cheapness. They cannot
answer *"may I **create** one"*: the cache can only report a shadow it has
already observed, leaving a multi-second double-spawn window. The launch guards
therefore use `find_shadow_pane_status`, which discriminates a failed query from
a verified absence, and **refuse on both** a found shadow and an unverifiable
one. `spawn_shadow` re-checks immediately before launching, so the seconds an
`E` picker dialog stays open are covered too.

### Rule: monitor-side spawns must not steal window focus

Both `launch_in_tmux` placement branches select the new pane's window by default
(`select-window` after the split; `new-window` without `-d` creates *and*
selects). `TmuxLaunchConfig.select_window` (default `True`, preserving every
pre-existing caller) turns that off: **minimonitor passes `True`** (its client is
already on that window, so the argv is unchanged) and **monitor passes `False`**,
because being yanked to the shadow's window would defeat the shadow preview
column the monitor exists to show.

## Feedback freshness (staleness detection)

When many agents are followed in parallel, the followed agent can race ahead —
often *while the shadow is still thinking* — so the shadow's advice silently
becomes stale. This is surfaced by comparing **times** (t1104): *when* the shadow
last read the followed pane vs *when* the followed pane last changed. A
timestamp is used rather than a content signature deliberately — an exact
snapshot hash of a live terminal is too brittle (a render settling by a single
character reads as "stale" even when the agent is idle).

- **Stamp (in `aitask_shadow_capture.sh`).** On every capture, when the helper detects
  it is running *inside a shadow pane* (its own `$TMUX_PANE` carries a
  gateway-validated `@aitask_shadow_target` — the same `shadow_self_target`
  lookup the resolution rule above uses) and is capturing that bound followed agent, it stamps the
  current wall-clock epoch onto its own pane:
  `@aitask_shadow_analyzed_at = <epoch>` (`SHADOW_ANALYZED_AT_OPTION` in
  `monitor/monitor_core.py`). Automatic (no flag, no skill-markdown change) and
  self-guarding: minimonitor's own captures run from a non-shadow pane and never stamp;
  the `-`/no-`TMUX_PANE` paths never stamp. Best-effort — a stamp failure never breaks
  the capture.
- **Compare (`monitor_core.compute_shadow_staleness`, driven by minimonitor).** On every
  *other* refresh tick (~6 s at the 3 s default — the concern auto-offer still runs every
  tick), once a shadow pane is bound, the comparison reads the cheap
  `@aitask_shadow_analyzed_at`, then compares it to when the followed pane
  last changed (`TmuxMonitor.get_last_change_wall`, derived from monitor_core's existing
  change detection). If the followed pane changed **after** the stamp (beyond a
  one-refresh-tick epsilon that absorbs detection lag) ⇒ **stale**. The comparison itself
  is shared in `monitor_core` (a tri-state `True` / `False` / `None`, where `None` means
  "could not tell") so any monitoring surface can reuse it; the caller owns the display.
  Minimonitor shows a live
  `#mini-shadow-stale` warning line — including how old the shadow's read is
  ("analyzed Ns ago") — appends a STALE marker to the concern auto-offer, and passes
  `stale=` to `ConcernPickerModal` (a red banner) so stale concerns are not forwarded
  unaware. Failure-safe: an unreadable/malformed stamp or a not-yet-observed followed
  pane *preserves* the previous state and never clears a standing warning; an absent
  stamp (shadow has not analyzed yet) shows nothing.

An idle agent (e.g. sitting at a plan-approval prompt the shadow just read) has not
changed since the stamp, so it correctly reads **current**; an agent that emits new
output after the shadow read it reads **stale**.

### Block age vs read recency (t1493)

Read recency answers *"did the shadow look recently?"* — never *"was the block on
screen produced by that look?"*. A shadow that refetches the pane and then answers
in **prose** restamps `@aitask_shadow_analyzed_at` without emitting anything, so
read recency clears while the previous round's concerns sit there being re-offered
as current. That is not hypothetical: a recheck round can produce no block at all
(prose only), and a concern raised in such a round never reaches the picker — which
is why the routing rule below and this signal exist together.

So there are **three** freshness signals, and every surface must say which it uses:

| signal | question | implementation |
|---|---|---|
| **block identity** | has *this block's text* changed? | `concern_parser.concern_block_signature` |
| **read recency** | did the shadow *look* after the agent's last change? | `monitor_core.compute_shadow_staleness` |
| **block age** | was this block *produced* after the agent's last change? | `monitor_core.compute_block_age_staleness` |

- **Source.** The block's own `Round: <N> @ <ts>` header (t1159_1).
  `concern_parser.parse_reviewed_at_epoch` converts `<ts>` to an epoch —
  strictly, via a canonical round-trip, returning `None` for anything but the
  documented shape.
- **Clock trust.** The producer shell-sources `date -u +%Y-%m-%dT%H:%M:%SZ` in
  the shadow pane; `get_last_change_wall` derives from `time.time()` in the
  monitor process. **Same host**, so the epochs are directly comparable. This
  assumption is stated rather than implicit: it is what makes a bare subtraction
  legitimate.
- **Applicability is a third state, not uncertainty.** `BlockAge.applicable` is
  false when the capture shows no block at all, and `combine_staleness` then
  returns read recency untouched. Without that, a shadow used only to explain the
  screen would show "freshness unknown" forever, about feedback that does not
  exist. A block that *is* present but whose age cannot be established (no
  header, clipped header, unparseable timestamp) yields `None` — real
  uncertainty, which never clears a standing warning and never reads as current.
- **Join.** `monitor_core.combine_staleness` — `True` wins, then `None`, then
  `False`.

**Two derived attributes in minimonitor, deliberately distinct:**
`_shadow_read_recency` is a `ReadRecency(stale, analyzed_at)` tuple written only
by the throttled compare (the verdict and the stamp that produced it, bound
together so they cannot desync; `_shadow_feedback_stale` is a read-only property
over its verdict). `_shadow_stale_combined` is the joined verdict every
user-facing surface reads. Anything choosing a trigger — including the review-loop
automation — should pick between them deliberately.

**Surface ownership.** The minimonitor `#mini-shadow-stale` banner owns the
continuous warning **including the became-stale transition**, recomputed every
tick. The concern picker owns the actionable warning and recomputes from its own
capture (never the tick cache — a newer round may have arrived, or the action may
have taken a deeper re-capture). The auto-offer toast is one-shot: both apps
return early on an unchanged block, so a block that goes stale in place can never
re-toast, and that is correct — a toast announces arrival, not ageing. `ait
monitor` has no continuous banner, so its picker is the sole owner there; the `!`
badge's clearing edge is t1448's.

**Canonical recheck phrase.** The shadow entry point (`SKILL.md.j2` Step 3) routes
re-review asks, and the phrase any automation should inject is **`refetch and
recheck round N`**. That routing is what makes a recheck re-enter the review
sub-procedure and emit a fresh block instead of answering conversationally.

## Concern rejection store

A per-task record of the concerns the user has rejected, so the shadow can drop
them from later review rounds instead of re-raising the same items every time.

**This is producer-side filtering, never a gate.** It changes only what the
shadow puts in its *own* output; it never inspects the followed agent's state,
never decides whether the user may proceed, and has no refusal path. The store
also cannot become a block: `add` accepts only canonical `- [` marker lines, so
a `===AITASK-CONCERNS===` fence can never be written into it, and echoing `list`
output carries item lines with neither sentinel. See the anti-gating rule under
"Phase detection (advisory)" for the shape this deliberately avoids.

**Store.** `.aitask-shadow/<task_id>/rejected.md`, mirroring `.aitask-gates/`:
bare task id (no `t` prefix), lazily created by the writer, git-ignored, never
committed. The gitignore rule is installed by `setup_shadow_store_gitignore()`
in `aitask_setup.sh`. Records are markdown so they can be handed to an agent as
prompt context verbatim:

```markdown
<!-- next_id: 3 -->

### r1 | 2026-08-05T14:02:11Z | producer: plan-challenge
- [high | Step 7 guard] The guard double-commits when the lock was held.
```

The header is a never-decreasing high-water mark: entry ids are assigned from it
and never reused, which is what makes a pre-fetched id safe to act on. Removing
the last entry keeps a header-only file rather than deleting it.

**Helper — `aitask_shadow_rejected.sh`, internal machinery, not a user CLI.**
Invoked by path. `add <task_id> [--producer <name>]` (markers on stdin),
`list <task_id> [--machine]`, `remove <task_id> <id>...`, `prune <task_id>`.
Exit codes are load-bearing and must stay distinct: `0` success, `2` bad request,
`3` `LOCK_BUSY` (another writer — retryable), `4` the store is unusable (do
**not** retry; it will not fix itself). Every mutation holds the
`registry_lock.sh` mutex and lands through the atomic-write helper — appending a
rejection is a read-modify-write, which atomic-write alone does not serialize.
`list` takes no lock. Because `registry_lock_acquire` cannot tell "busy" from
"impossible", every path validates the store path before acquiring.

**TUI write path.** Both apps mix in `ShadowRejectionsMixin`. The picker's `r`
marks a row rejected and `R` opens the rejected-store view; both are **staged**
— the modals write nothing. The store is touched only when the *picker* is
confirmed (`ConcernPickResult` carries `forwarded` / `rejected` / `unrejected`;
`None` is the sole cancel signal), at which point rejections go in via
`add … --producer picker` and un-rejections via `remove`. Cancelling the picker
discards both staged sets. Outcomes are always visible: a success toast per
operation, a warning when the pane has no task id (`Rejections not persisted`),
and distinct messages for exit 3 vs. exit 4 — conflating them would turn a
permanent misconfiguration into an endless retry. `list --machine` emits
`REJECTED:r<id>|<ts>|<producer>|<marker line>` — ids are `r`-prefixed on the
wire; parse with `split('|', 3)`, the marker last because it may itself contain
`|`. The empty signal is the single line `NO_REJECTIONS`, for a missing store and
a drained one alike, so check for it before parsing.

**Producer consult path.** Every emitting sub-procedure runs plain
`list <task_id>` before emitting a block. Exactly three outcomes are defined: the
single line `NO_REJECTIONS` means nothing is rejected; a printed body is the
rejected set; **anything else** — non-zero exit, empty output, or unrecognized
output — means the store could not be consulted, so the producer emits every
fresh concern and states that suppression was skipped. An error is never read as
"nothing was rejected", and the decision is never made on exit status alone.
Matching is **semantic**, performed by the agent: concerns have no stable
identity across rounds and the shadow re-words bodies, so no consumer-side hash
could serve. Whenever N ≥ 1 were dropped the producer reports
`Suppressed N previously-rejected concern(s).` in the prose before the block;
when unsure whether a fresh concern matches a rejected one it **keeps** the
concern and says why (fail-open, matching `needs_addressing()`'s treatment of an
unspecified disposition). The rule is stated in `concern-format.md` and inlined
**twice** in each producer — a bolded pre-emit directive and a parser-rules entry
— because producers are prompt files read at runtime and an extra file read is a
rule the agent may skip; `tests/test_concern_parser.py` fails the build if either
copy is dropped. There is deliberately **no producer filter**: rejection is a
judgement about the concern, not about which round raised it.

**Lifetime.** Pruned at archive by `prune_shadow_rejections()` in
`aitask_archive.sh`, wired at every `release_lock` site. Prune is
lock-coordinated, guards that the directory resolves under its own root, removes
regular files and then `rmdir`s — never `rm -rf`.

## Configuration

- `defaults.shadow` in `codeagent_config.json` — the agent+model used for the
  shadow companion, editable in `ait settings` → Agent Defaults (project layer +
  `.local` user override) like any other operation default.
- `tmux.shadow_same_window` in `project_config.yaml` (TMUX schema) — `true`
  (default) spawns the shadow as a split in the followed agent's window; `false`
  spawns it in a separate `agent-shadow-*` window.
- `shadow_impl_review_tier` in an **execution profile**
  (`aitasks/metadata/profiles/<name>.yaml`) — the default effort tier for
  `impl-challenge` (`quick` | `default` | `advanced` | `deep`). When set, a
  generic "review the implementation" runs at that tier and the 4-option tier
  prompt is skipped; unset keeps the prompt. A tier named in the user's ask
  overrides it either way. **It only takes effect once `default_profiles.shadow`
  names that profile** — the shadow resolves its profile through
  `aitask_skill_resolve_profile.sh shadow` like any other skill, which returns
  `default` when the mapping is absent, so shipping the key in `fast.yaml`
  without the mapping leaves it inert. Add it in `project_config.yaml` (team) or
  `userconfig.yaml` (personal):

  ```yaml
  default_profiles:
    shadow: fast
  ```

- `@aitask_shadow_phase` — pane option on the **shadow** pane carrying the
  advisory workflow-phase signal (t1420), written at spawn by
  `monitor_core.spawn_shadow` and re-stamped every tick by both monitor TUIs via
  `refresh_shadow_phase_stamp`. Not user configuration: it is machinery, listed
  here beside the other `@aitask_shadow_*` options so the family is discoverable.
  Read with `aitask_shadow_capture.sh --phase`.

## Phase detection (advisory)

Detecting the followed agent's *workflow phase* was deferred for a long time,
and shipped in t1420 **in the sanctioned shape only**: a hint that changes a
*default*, never a check that changes what is *permitted*. The rule the deferral
protected is now a live constraint:

> Phase detection must never become a flow step, a prerequisite, or a gate on
> what the user can ask. Every shadow capability is available at every phase,
> including `UNKNOWN` and a phase that is simply wrong. A wrong or unavailable
> phase costs the user at most one extra keystroke.

It is enforced, not merely stated: `tests/test_shadow_phase_advisory.sh` sweeps
every rendered shadow closure for a phase-conditioned refusal and drives every
phase value — including a deliberately wrong one — through the read path.

### The signal

`lib/workflow_phase.py` is the seam; `PhaseSignal` carries a phase
(`PLAN` / `IMPLEMENT` / `POSTIMPL` / `UNKNOWN`), a separate `waiting` state, the
`source` that answered, and the provenance behind it. `UNKNOWN` is a **first
class answer** meaning "cannot tell" — deliberately distinct from `PLAN`,
because `resume_point`'s empty-ledger default is `PLAN` and a consumer that
inherited it would confidently report "planning" for every task forever under a
profile that does not set `record_gates`.

Three sources, in precedence order:

1. **Tier A — workflow prompts** (agent-neutral). The checkpoint questions
   task-workflow authors itself ("Plan saved to …", "Implementation complete.
   Please review and test the changes.", …). These read identically under every
   code agent because the framework, not the agent, writes them.
2. **Tier B — native dialogs** (per-agent), keyed on the monitor's
   `awaiting_input_kind`. A *generic* confirmation is deliberately not a key, so
   it contributes nothing.
3. **The ledger** — `gate_ledger.resume_point_from_text` over the recorded
   `## Gate Runs` checkpoints, plus `has_gate_markers` to tell "no ledger" from
   "in planning".

### Currency: why the screen tiers are gated

`capture-pane -S -<n>` reads **scrollback**, so an *answered* checkpoint sits in
the tail long after the agent moved on — measured at 26 stale occurrences in one
real session's history, against zero live prompt markers (a live prompt exists
only in the visible region; answered ones collapse to a summary line). Matching
a bare anchor would therefore be almost entirely false positives.

So the screen tiers require **both**: the pane is blocked on input, **and** the
anchor sits inside the **current question block**. `awaiting_input` alone is not
enough — it proves *a* prompt is live, not that the matched one is.

The block boundary is structural, not a distance: an `AskUserQuestion` renders a
header chip (`` ☐ <Header> ``) directly above its question text, exactly once,
and only while it is live. Everything above that chip belongs to an earlier,
already-answered prompt. A proximity bound cannot do this job — the widget's own
inner rule sits *below* its question, and a stale anchor can fall within any
fixed number of lines of the bottom once a later, unrelated question renders
under it. Anything ambiguous (no block, no anchor in it, a different prompt kind)
suppresses in favour of the ledger and says which condition failed.

### Per-agent availability — do not read more coverage than exists

Tier A's *anchors* are agent-neutral, but establishing that a prompt is
**current** needs per-agent markers, and those are not uniform:

| agent | ledger half | Tier A (live) | Tier B (native) |
|---|---|---|---|
| Claude Code | yes | yes | yes (`claude_plan_approval`) |
| Codex CLI | yes | no markers yet — **t1467** | no — **t1467** |
| OpenCode | yes | no markers at all — **t1467** | no — **t1467** |

An agent without markers degrades to the ledger-derived phase, or `UNKNOWN` —
never to a guess. Ask `workflow_phase.live_tiers_available(agent)` rather than
assuming; the signal's own `detail` names t1467 when that is the reason.

### Transport and consumption

The monitor TUIs compose the signal per tick and stamp it on the shadow pane's
`@aitask_shadow_phase` (see Configuration). It is written **inside**
`spawn_shadow`, before control returns to the app — the per-tick re-stamp alone
would leave a window in which a user launches a shadow, it reads `--phase`
before the next tick, and it misses the very checkpoint it was spawned for. A **pane option, not argv**: argv
would freeze at spawn, while the shadow re-reads on every refetch.
`monitor_core.refresh_shadow_phase_stamp` is shared because *both* TUIs spawn
shadows — and unlike the `@aitask_shadow_target` stamp, which kills the pane on
failure, it is best-effort: an advisory hint must never be able to destroy a
shadow.

The shadow reads it with `aitask_shadow_capture.sh --phase [<task_id>]` — one
line, always exit 0, never refusing — and uses it as the middle rung of
**explicit user wording > detected phase > ask**, announcing what it resolved
and how to override.

**The same principle removed `impl-challenge`'s "too early to review" gate.**
That gate refused to start a review until the plan carried a
`## Final Implementation Notes` section, on the premise that its absence meant
the implementation phase had not finished. The premise was backwards:
task-workflow writes those notes inside the **"Commit changes"** branch of Step
8, *after* the Step-8 review prompt — so at the single most common moment a user
reaches for a shadow implementation review (the followed agent parked at
"Implementation complete. Please review and test the changes.") the notes are
absent **by construction**. The gate therefore fired on the normal path and
charged an abort/proceed confirmation for doing exactly the intended thing. It
is now a **review-state assessment** that states what it resolved instead of
asking permission to proceed. Only a genuinely un-reviewable state — all four
diff channels empty — stops the run, and that is a report, not a prompt. A
missing plan degrades the run (angles S1/S2 go unavailable) rather than blocking
it. Anything that inspects the followed agent's state to decide whether the user
may proceed is the shape this rule forbids.
