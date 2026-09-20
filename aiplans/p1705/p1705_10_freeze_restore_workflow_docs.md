---
Task: t1705_10_freeze_restore_workflow_docs.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_1_*.md … aitasks/t1705/t1705_9_*.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-20 08:56
---

# t1705_10: Freeze/restore workflow and framework-session concept docs

## Context

The user asked for the freeze feature to be documented **as a workflow**, not
only as the TUI reference that t1705_9 already landed
(`website/content/docs/tuis/frozenagent/{_index,how-to,reference}.md`, plus
freeze sections in the monitor and minimonitor how-tos). This child adds
four things: a workflow page (when/why to freeze, restore, re-pick or drop), a
concept page for the framework session store, a "Session hooks" section on
the setup page, and cross-links. Prose describes current state only, and every
fact comes from the landed code.

**Verified against the tree (2026-09-19). These corrections to the original
plan also follow the 5 inbox notes, each checked:**
- Freeze uses **`f`** in monitor and minimonitor, not `z` (`z` cycles the
  monitor preview size). Freeze-All is **`Z`** and covers every project and
  parked agents.
- There is **no `ait frozen` verb** (`ait` dispatches only `frozenagent`).
  Reconcile and Restore-All go through
  `./.aitask-scripts/aitask_frozen.sh reconcile` and
  `./.aitask-scripts/aitask_frozen.sh restore --all [--repick]`. That runs
  sequentially, and one failure does not stop the batch
  (`agent_restore.restore_all`). No TUI key runs Restore-All.
- A record whose window is closed or whose tmux server restarted **does
  restore** (t1773/t1784 landed). It comes back in a new window named after the
  recorded one; `unique_window_name` adds `-2`, `-3` if that name is taken. The
  project session is created the way `ait ide` would create it. Those routes
  are documented in `tuis/frozenagent/how-to.md` § "Bring an agent back", so
  **link there rather than restating them**.
- A restore ends one of two ways. `hook` is verified and deletes the capture;
  `liveness` is unverified and keeps it. A verified re-pick also deletes the
  capture. Re-pick needs a task id; restore needs a session id. Opencode
  refuses resume (`resume_unsupported:opencode`), so re-pick is its only route
  back.
- Codex: the SessionStart hook fires only under `codex exec`, not in the TUI.
  The Codex session id is captured at **freeze** time instead (t1804: from the
  rollout its process holds open). An interactive Codex restore therefore
  always ends unverified. A Codex agent that never took a turn can only
  re-pick.
- `capture_max_lines` (default 50000) sets **scrollback depth**. A capture holds
  about cap + pane height lines, and it is the *tail* of the scrollback.
  `frozen.stale_op_grace` is **not** a config key. It is a test-only env
  variable, and the lease grace is fixed at 60 s.
- Setup (`aitask_setup.sh` `setup_claude_hooks`, ~2613-2664):
  - The Claude hook has its **own [Y/n] prompt**, separate from the
    permissions prompt. A decline is not remembered and is asked again on every
    `ait setup`; a non-interactive setup auto-accepts.
  - The hook is written to **`.claude/settings.json`**, not
    `settings.local.json`, with matcher `startup|resume`. A new file is copied
    from the seed. An existing file gets only `hooks.SessionStart` merged in,
    deduped by (matcher, script path), and every other key is kept.
  - Opting out means **answering n**. Deleting the entry does not work: the next
    accepted setup adds it back.
  - The Codex hook is part of the "Install Codex CLI skills and config?" prompt
    (shown only when codex is installed). It is merged into `.codex/config.toml`
    by `tomllib` load plus re-serialisation, **so comments in that file are
    lost**. It also needs the project marked `trust_level = "trusted"` in
    `$CODEX_HOME/config.toml`, which setup never writes.
- `concepts/agent-memory.md` and `concepts/locks.md` list no per-user state. A
  pointer there would be forced, so the concept page is linked from
  `concepts/_index.md` and from the "See also" in `concepts/ide-model.md`
  instead.
- Purge (`agent_sessions.purge`) has three reasons:
  - `dead_window`: a live record whose window is absent from an enumerated root.
  - `dead_pane`: pane gone and pid dead.
  - `capture_missing`: a frozen record whose capture is gone.

  An `INCOMPLETE` observation suppresses all of them, and transitional records
  are never purged. Monitor and minimonitor run purge and then reconcile on
  their maintenance tick, and the freeze and restore coordinator runs reconcile
  after every operation.

## Files

- **New** `website/content/docs/workflows/freeze-and-restore-agents.md`
- **New** `website/content/docs/concepts/framework-session.md`
- **Edit** `website/content/docs/workflows/_index.md` (Parallel group)
- **Edit** `website/content/docs/concepts/_index.md` (Lifecycle and infrastructure group, after the IDE model)
- **Edit** `website/content/docs/concepts/ide-model.md` (See also)
- **Edit** `website/content/docs/commands/setup-install.md` (guided-flow item + `### Session Hooks` section)
- **Edit** `website/content/docs/installation/_index.md` (one bullet each in the Claude and Codex file lists)
- **Edit** `website/content/docs/tuis/frozenagent/_index.md` (link to the workflow page and the concept page)
- **Edit** `website/content/docs/workflows/parallel-development.md`, `crash-recovery.md` (one-line pointers)

## Implementation steps

1. **Workflow page** `workflows/freeze-and-restore-agents.md`.
   - Front matter: `title/linkTitle: "Freeze and Restore Agents"`,
     `weight: 43` (right after Crash Recovery at 42),
     `description: "Freeze finished agents to free their processes while keeping their output readable in place, then bring them back by restore or re-pick"`,
     `depth: [intermediate]`.
   - Internal links use `{{< relref >}}`. Sections, in order:
     - Intro: the motivation of 10–20 agents, most kept only so their summary
       can be read.
     - `## When to freeze`: a table with rows live / parked / frozen and
       columns process · output kept · what it costs · how you come back.
       Parked means the agent still runs and only the monitors ignore it.
     - `## The daily loop`:
       - Press `f` in monitor or minimonitor. The viewer takes over the same
         pane, so the layout is unchanged: agent pane plus minimonitor
         companion.
       - Read, search and copy with `/`, `n`, `shift+↑/↓` and `y`; link to the
         how-to.
       - Restore (`R`) or re-pick (`p`). Re-pick is usually cheaper: the new
         agent reads the task file instead of replaying a long transcript.
         Cover which id each route needs, that opencode can only re-pick, and
         that a verified restore or re-pick deletes the capture, so copy first.
       - Drop (`k`).
     - `## Before shutting down`:
       - `Z` Freeze-All: machine-wide, every project, parked agents included.
       - After tmux comes back, restore per record from `ait frozenagent` list
         mode, or all at once with `aitask_frozen.sh restore --all [--repick]`.
         Agents come back in new windows under their recorded names (`-2` if a
         name is taken), and the project session is created as `ait ide`
         would. Link to how-to § "Bring an agent back".
     - `## What "unverified" means`:
       - Hook-verified versus liveness-only acknowledgement, and why the
         capture is kept in the liveness case.
       - When liveness-only happens: the Claude hook was declined at setup, an
         interactive Codex agent, or an agent CLI that reports no session.
       - `restore_ack_grace` is a waiting period, not an outcome; link to the
         reference Configuration section.
     - `## When something goes wrong`:
       - A failed restore (`agent_exited`, `session_mismatch`) brings the viewer
         back with the capture intact.
       - `restore did not start` covers no recorded session id and opencode.
       - A dead stand-in is respawned by reconcile.
       - A state stuck in `freezing`/`restoring`/`aborting`: reconcile runs
         after every operation and on the monitor/minimonitor maintenance tick.
         Run it by hand with `./.aitask-scripts/aitask_frozen.sh reconcile`,
         and say there is no `ait frozen` command.
       - Closed windows and a session name held by another project: link to
         the how-to rather than restating.
     - `## Marks and frozen agents`:
       - A frozen agent keeps its ★/P mark and gains a cyan `F`.
       - `P` hides parked and frozen agents together.
       - The counters are separate (`N frozen` / `Nf`); an agent that is both
         is counted once, as frozen.
     - `## Limits`:
       - No age-based expiry: a record stays until it is dropped or verified
         restored.
       - Disk: `~/.config/aitasks/frozen/<id>/capture.ansi` + `capture.txt`,
         one per record. `ait frozenagent` list mode shows which records exist.
       - The capture cap is scrollback depth (≈ cap + pane height) and keeps the
         tail; set it with `frozen.capture_max_lines`.
       - Link to the concept page.
2. **`workflows/_index.md`**: in the Parallel group, after the Crash Recovery
   bullet: `- [Freeze and Restore Agents](freeze-and-restore-agents/) — Freeze finished agents to free their processes while keeping their output readable in place, and bring them back by restore or re-pick.`
3. **Concept page** `concepts/framework-session.md`.
   - Front matter like `locks.md`: `weight: 95`, `depth: [advanced]`,
     description "The machine-wide record of every running and frozen code
     agent that makes freeze and restore possible."
   - Sections:
     - `## What it is`:
       - The store `~/.config/aitasks/agent_sessions.json` holds one record per
         agent across all projects. It is mode 0600, written atomically by the
         single writer `aitask_agent_sessions.sh` under a lock; readers take no
         lock.
       - Captures live under `~/.config/aitasks/frozen/<id>/` (0700).
     - `### Identity versus location`: identity is (project root, window
       name, slot). Pane id and pid are location data, replaced by a tmux
       restart or a respawn. The `@aitask_record` pane option joins a pane to
       its record.
     - `### States`: an **ASCII state diagram in a ```` ```text ```` fence**.
       The site has no Mermaid support: no config in `hugo.toml`, no
       assets or layouts, and no existing usage. A mermaid fence would publish
       as a raw code block. Existing ASCII diagrams (e.g. `commands/crew.md`)
       use ```` ```text ````. The diagram shows:
       - live → freezing → frozen; freezing → live on abort.
       - frozen → restoring → live, by hook ack or liveness.
       - restoring → aborting → frozen.
       - drop from any state.
     - `### Operation leases`:
       - Each freeze or restore takes a lease (nonce + owner pid).
       - Reconcile leaves a record alone while its owner is alive or the lease
         is younger than 60 s. After that, it settles the record from what
         tmux shows.
       - A coordinator that loses the race fails closed.
     - `### The SessionStart hook`:
       - Records the session id at start.
       - On restore, the replacement agent is launched with the record id and a
         one-time nonce in its environment. The hook sends them back as the
         acknowledgement; the session id is checked in resume mode.
       - That is the `hook` outcome, which deletes the capture.
       - With no acknowledgement within the grace, the record is confirmed on
         liveness and the capture is kept.
     - `### Cleanup rules`:
       - Purge reasons `dead_window`, `dead_pane`, `capture_missing`.
       - Fail-closed on incomplete observation; transitional records are never
         purged.
       - Who runs purge and reconcile.
     - `### Overrides`: `AITASKS_AGENT_SESSIONS_FILE`, `AITASKS_FROZEN_DIR`.
     - `## Why it exists`
     - `## How to use`: links to the workflow page and the TUIs.
     - `## See also`
4. **`concepts/_index.md`**: add a bullet after the IDE model:
   `**[Framework session]** — The machine-wide record of every code agent's pane, session id and freeze state, behind freeze and restore.`
   **`concepts/ide-model.md`**: add a See-also bullet pointing to it.
5. **Setup docs** `commands/setup-install.md`:
   - Add guided-flow item 10, "Session hook — own Y/n prompt …", and renumber
     Version check to 11.
   - Add `### Session Hooks` after Claude Code Permissions:
     - What is written: the `.claude/settings.json` `hooks.SessionStart` entry
       (matcher `startup|resume`, runs `.aitask-scripts/aitask_session_hook.sh`,
       timeout 10).
     - The hook always exits 0 and writes nothing into the session.
     - Merge rules: other keys and hooks are preserved; re-running is
       idempotent, deduped by script path.
     - Codex: part of the Codex install prompt, merged into
       `.codex/config.toml`, comments in that file are dropped. It fires only
       under `codex exec`, and the project must be trusted in
       `$CODEX_HOME/config.toml` (setup does not write that).
     - Opt out by answering n. Deleting the entry gets it re-added by the next
       accepted setup.
     - Link to the workflow page's unverified section.
   - `installation/_index.md`: add the `.claude/settings.json` session-hook
     bullet and amend the `.codex/config.toml` bullet.
6. **Cross-links**:
   - `tuis/frozenagent/_index.md`: add a line after the intro paragraph
     pointing to the workflow page and the concept page.
   - `parallel-development.md`: one sentence pointing to freezing finished
     agents when many are open.
   - `crash-recovery.md`: add a Tips bullet. Freeze-All (`Z`) before a planned
     shutdown makes agents restorable afterwards; crash recovery covers the
     unplanned case.

### Post-phase (risk mitigations)

1. [fact_check_quoted_strings] For every backticked message, key, path,
   config name and wire token in the new and edited pages, confirm it exists
   verbatim in `.aitask-scripts/` (or in the t1705_9 frozenagent pages for
   viewer messages). Check with `grep -rF`, and fix any mismatch before
   committing.

## Verification

```bash
cd website && hugo build --gc --minify && python3 check_links.py --build
grep -n 'freeze-and-restore-agents' website/content/docs/workflows/_index.md website/content/docs/tuis/frozenagent/_index.md
grep -n 'framework-session' website/content/docs/concepts/_index.md
```
Also check that the state diagram renders as a preformatted block with its
box-drawing characters intact: build into a temporary `--destination`, then
grep the built `concepts/framework-session/index.html` for `<pre` and for
`freezing` / `aborting` inside it. No code changes, no tmux.

## Risk

### Code-health risk: low
- The workflow page could duplicate frozenagent how-to content that later drifts · severity: low · → mitigation: addressed by design (link to the how-to rather than restate the restore routes)

### Goal-achievement risk: low
- The docs could publish wrong or stale behaviour: keys, messages, config knobs or setup semantics (the task body already had four such errors) · severity: medium · → mitigation: inline post-phase fact_check_quoted_strings

### Planned mitigations
- timing: post-phase | name: fact_check_quoted_strings | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risk of publishing wrong behaviour | desc: grep every quoted string in the new and edited pages against the source tree and fix mismatches

## Step 9

Post-implementation: commit the docs (`documentation: … (t1705_10)`), then
archive via the task-workflow Step 9.

## PINNED contracts

See the parent plan `aiplans/p1705_*.md` §A–§D **and its amendments B1–B7**,
which win on any discrepancy. This docs task describes mechanisms at the level
of observable behaviour ("launched with the record id and a one-time nonce in
its environment"). It deliberately avoids the `env`-prefix versus
`respawn-pane -e` detail, so neither the superseded nor the amended wire
contract is published.

## Implementation notes

All six steps landed, plus the post-phase fact check. Deviations from the plan
as written:

- **`installation/_index.md`**: the `.claude/settings.json` hook bullet went
  into the **Per-project files** list, not the Global dependencies list where
  the permissions bullet sits. The hook file is per-project; the existing
  permissions bullet's placement there looks like a pre-existing inaccuracy and
  was left alone rather than widened.
- **`concepts/framework-session.md`** describes the pane options by role
  (`@aitask_record` named; the frozen and stand-in-ready options described, not
  named) rather than tabulating all four. The page is a concept page, and the
  table already exists in the parent plan.
- The state diagram is ASCII in a ```` ```text ```` fence, per the approved
  plan's correction. Verified in the built HTML: one `<pre>` block carrying
  `freezing`, `aborting` and the box-drawing characters intact.

Verification run: `hugo build --gc --minify` clean;
`check_links.py --build` → `resolved 32305, broken 0, SWEEP: PASSED`;
`check_link_relevance.py` → 4 reported links, all pre-existing, none added or
retargeted by this task.

## Post-Review Changes

### Change Request 1 (2026-09-20 06:40)
- **Requested by user:** two confirmed correctness defects. (1) `crash-recovery.md`
  claimed Freeze-All leaves every agent with "its session recorded", but a record
  may carry no session id and an opencode agent cannot resume at all
  (`RESTORE_FAILED:<id>|resume_unsupported:opencode`), so those return only by
  re-pick. (2) The live/parked/frozen table costed a frozen agent as "disk only",
  but the freeze respawns the pane into `ait frozenagent --record <id>` and
  records its `standin_pid` — a viewer process remains.
- **Changes made:** the crash-recovery tip now says the record and capture are
  kept, then splits the route: restore when a session id was recorded, re-pick
  when there is none or the CLI cannot resume. The workflow page's intro and
  cost row now state that the agent process and its context are released while
  the viewer holds the pane and the capture holds disk. The Restore-All
  paragraph gained the same distinction, since the plain form reports those
  records as failures.
- **Files affected:** `website/content/docs/workflows/crash-recovery.md`,
  `website/content/docs/workflows/freeze-and-restore-agents.md`
- **Re-verified:** `hugo build --gc --minify` clean; `check_links.py --build`
  → `SWEEP: PASSED`.

## Final Implementation Notes

- **Actual work done:** Both new pages
  (`workflows/freeze-and-restore-agents.md`, `concepts/framework-session.md`),
  the `### Session Hooks` section and guided-flow item on
  `commands/setup-install.md`, the two index entries, and all five cross-links
  (`tuis/frozenagent/_index.md`, `concepts/ide-model.md`,
  `parallel-development.md`, `crash-recovery.md`, `installation/_index.md`).
  Committed as `3638836ae`.
- **Deviations from plan:** (1) The `.claude/settings.json` bullet in
  `installation/_index.md` went into **Per-project files**, not the Global
  dependencies list where the permissions bullet sits — the hook is a
  per-project file. The existing permissions bullet's placement looks like a
  pre-existing inaccuracy and was left alone rather than widened into this
  task. (2) The concept page describes the pane options by role instead of
  tabulating all four; the full table lives in the parent plan and would date
  quickly in user docs. (3) The state diagram is ASCII in a ```` ```text ````
  fence rather than mermaid — see Issues.
- **Issues encountered:** The original plan specified a mermaid
  `stateDiagram-v2` and a verification that grepped the built HTML for a
  mermaid class. The user blocked the plan on this: `website/hugo.toml` has no
  mermaid config, there are no mermaid assets or layouts, and no content page
  uses a mermaid fence, so Hugo would have published the fence as a plain code
  block with a green build. Replaced with box-drawing ASCII in a ```` ```text ````
  fence (the site's existing convention, e.g. `commands/crew.md`) and a
  verification against the actual rendered `<pre>`.
- **Key decisions:** The restore landing places (closed window, tmux restart,
  session-name conflict) are **linked**, not restated —
  `tuis/frozenagent/how-to.md` § "Bring an agent back" owns them (t1784/t1778),
  and duplicating them would create the drift the code-health risk names.
  Everything written was checked against the landed code rather than the plan
  or the inbox notes; five stale claims in the task body were corrected in the
  process (freeze is `f` not `z`; there is no `ait frozen` verb; closed-window
  restore works now; the hook opt-out is answering `n`, not deleting the entry;
  `frozen.stale_op_grace` is not a config key).
- **Upstream defects identified:**
  - `website/content/docs/installation/_index.md:126 — Claude Code permissions
    (.claude/settings.local.json) were listed under "Global dependencies
    (installed once per machine)", but that file is written per project.`
    **Fixed in this task** at the user's request (commit `813ba9174`) rather
    than spawned as a follow-up: the bullet moved to the Per-project files
    list, beside the session-hook bullet this task added.
- **Notes for sibling tasks:** The division of labour with t1705_9 held up well:
  TUI surface (keys, header fields, messages, exit codes) on the frozenagent
  pages, and when/why plus the cross-cutting concept here. Anything a sibling
  adds about *where a restore lands* belongs in `tuis/frozenagent/how-to.md`;
  the workflow page links to it. Also note that `concepts/agent-memory.md` and
  `concepts/locks.md` list no per-user state, so the planned one-line pointers
  there had no home — `concepts/ide-model.md` took the See-also instead.
