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

## Pipeline: capture → context-fetch → skill

The shadow is built from three composable pieces. There is no workflow-phase
detection stage (that idea is deferred — see "Phase detection" below).

1. **Capture** — `.aitask-scripts/aitask_shadow_capture.sh <pane_id>` reads the
   followed agent's current screen through the tmux gateway and emits cleaned,
   escape-free text on stdout. It is re-run on demand, so the shadow always reads
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

  A broad ask ("review this plan") runs several sub-procedures in sequence.

## Spawn path and binding

The shadow is launched from **minimonitor** with the `e` key
(`action_launch_shadow` in `monitor/minimonitor_app.py`): it resolves the
followed agent's pane id and task id, builds the command via the `shadow`
codeagent operation (`aitask_codeagent.sh`), and launches the companion — by
default a split in the **same window**, configurable to a separate window.

The spawn glue sets the pane-scoped tmux user option
`@aitask_shadow_target = <followed_pane_id>` (constant `SHADOW_TARGET_OPTION` in
`monitor/monitor_core.py`) on the new shadow pane. That option is the
**authoritative** classifier *and* lifecycle binding: it drives exclusion from
agent lists, the `kill_agent_pane_smart` real-agent count, and the
`aitask_companion_cleanup.sh` auto-kill when the followed agent dies. See
`tui_conventions.md` (companion-pane section) and `tmux_gateway.md` (multi-agent
per window).

## Feedback freshness (staleness detection)

When many agents are followed in parallel, the followed agent can race ahead —
often *while the shadow is still thinking* — so the shadow's advice silently
becomes stale. This is surfaced by comparing **times** (t1104): *when* the shadow
last read the followed pane vs *when* the followed pane last changed. A
timestamp is used rather than a content signature deliberately — an exact
snapshot hash of a live terminal is too brittle (a render settling by a single
character reads as "stale" even when the agent is idle).

- **Stamp (in `aitask_shadow_capture.sh`).** On every capture, when the helper detects
  it is running *inside a shadow pane* (its own `$TMUX_PANE` carries
  `@aitask_shadow_target`) and is capturing that bound followed agent, it stamps the
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

## Phase detection (deferred)

Detecting the followed agent's *workflow phase* (planning / review /
AskUserQuestion / …) was scoped out: the shadow's value is to spawn fast, be
immediately available, and answer any question without needing to know the
phase. Phase autodetection remains a possible future advisory-only enhancement;
it must never become a flow step, a prerequisite, or a gate on what the user can
ask.

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
