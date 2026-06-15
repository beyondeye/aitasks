# The shadow companion agent

Specialist guidance for the **shadow** agent — an advisory companion coding agent
that watches another running agent (the *followed agent*) and helps the user
reason about what it is doing. Read this when editing the `aitask-shadow` skill,
its capture / context helpers, the minimonitor trigger, or any code that
classifies or cleans up shadow panes.

The shadow is **advisory-only**: it is read-only with respect to the followed
agent and never sends keystrokes, answers, or any input into the followed pane.
It explains and suggests; the user acts.

## Pipeline: capture → context-fetch → skill

The shadow is built from three composable pieces. There is no workflow-phase
detection stage (that idea is deferred — see "Phase detection" below).

1. **Capture** — `.aitask-scripts/aitask_shadow_capture.sh <pane_id>` reads the
   followed agent's current screen through the tmux gateway and emits cleaned,
   escape-free text on stdout. It is re-run on demand, so the shadow always reads
   the followed agent's *current* state rather than a frozen launch-time
   snapshot. A `-` argument cleans pre-captured text from stdin (also the test
   seam). All tmux access goes through `lib/tmux_exec.sh`
   (`tests/test_no_raw_tmux.sh`).
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

Source: `.claude/skills/aitask-shadow/` — `SKILL.md` plus four `plan-*.md`
sub-procedures. It is **user-invocable** (`user-invocable: true`) and **static**
(no profile / `.j2` / stub machinery, modeled on `aitask-contribute`): a spawned
agent CLI can only be triggered non-headlessly by a slash command on argv, and a
freshly spawned shadow has no parent skill to read-and-follow a non-invocable
one. Argument contract:

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
  types themselves). Four **structured plan analyses** each live in a
  read-and-follow sub-procedure with a defined methodology:
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

## Configuration

- `defaults.shadow` in `codeagent_config.json` — the agent+model used for the
  shadow companion, editable in `ait settings` → Agent Defaults (project layer +
  `.local` user override) like any other operation default.
- `tmux.shadow_same_window` in `project_config.yaml` (TMUX schema) — `true`
  (default) spawns the shadow as a split in the followed agent's window; `false`
  spawns it in a separate `agent-shadow-*` window.

## Phase detection (deferred)

Detecting the followed agent's *workflow phase* (planning / review /
AskUserQuestion / …) was scoped out: the shadow's value is to spawn fast, be
immediately available, and answer any question without needing to know the
phase. Phase autodetection remains a possible future advisory-only enhancement;
it must never become a flow step, a prerequisite, or a gate on what the user can
ask.
