# Workflow End Banner Procedure

The one fixed-format message that tells the user a task-workflow run is **over**,
and how it ended. Every run ends with exactly one banner, which is also its last
output:

- `## Complete` — the run reached its final step. Shown by `SKILL.md` **Step 10**
  after archival and push, and by `aitask-pickrem` / `aitask-pickweb` at their
  own final step.
- `## Stopped` — the run ended somewhere else. Shown at every early or alternate
  exit: a deferral, a revert to `Ready`, an abort, a split into children, or a
  stop that left the task as it was.

Before this procedure existed, a run had no closing message. Under a
feedback-disabled profile the last line on screen was a profile note, and every
early exit printed its own ad-hoc text or nothing at all. The banners are defined
here once, and every exit site *references* this file instead of copying the
text. A reference cannot drift or drop a line the way a copy can.

**The banner is a message for the user, nothing more.** No tool, TUI or gate
reads it. The monitor's COMPLETED badge is derived from the task file, not from
this text, so the badge's timing is unaffected by the banner. Display it; never
branch on it.

This procedure never prompts and is the same under every profile. It is safe to
reference from headless (`remote`) runs.

## Rules

- **Display the banner as a fenced `text` block, its first line verbatim.** The
  fence keeps markdown rendering from joining its lines into one paragraph. Copy
  the first line exactly as written below: no paraphrase, no reflow, no
  translation. It is the line a user scans for.
- **Exactly one banner per run, and it is the last thing you output.** Display it
  **after** the exit's own message (a closing message, a recovery hint, a
  verdict's required wording) and never **instead of** that message. If you
  display a banner and the run then continues (it should not), the next ending
  shows its own banner. A banner never ends a run that was not ending.
- **The outcome describes the task's actual state, not the exit's label.**
  `unchanged` is reserved for a run that made **no** change: nothing claimed, no
  status written, no plan saved or committed. Any exit reached after the run
  claimed the task or saved a plan takes its outcome from the task's state at
  the moment it ends. When the exit site cannot know that state statically,
  re-read `status` from the task file. Name any work that was kept, such as a
  committed plan or a retained `aitask/<task_name>` branch, in `reason` or
  `next`. Reading state for the banner is **read-only**: never release, take or
  rewrite another session's lock or assignment in order to describe it.
- **`<name>`** is the task file's stem without its `t<id>_` prefix (e.g.
  `t42_add_login.md` → `add_login`). When an exit fires before a task file was
  resolved but a task number was requested (a pre-claim refusal in
  `aitask-pickrem` / `aitask-pickweb`), use the requested `t<N>` and omit the
  name. An exit with no task number at all, such as a profile-resolution failure,
  is not a workflow run and shows no banner.

## Complete

**Input:**

| Variable | Description |
|----------|-------------|
| `task_id` | The task that completed (`16` or `16_2`). |
| `task_name` | Its name, per the Rules above. |
| `commit` | The archival commit hash, from the archive script's `COMMITTED:<hash>` line. |
| `pushed` | `yes` when the push after archival succeeded, otherwise `no`. |
| `follow_ups` | Task ids this run created: the Step 8b upstream-defect, Step 8c manual-verification and Step 8d risk-mitigation follow-ups. `none` when there are none. |

Display:

```text
✔ aitask workflow complete — t<task_id> <task_name>
  outcome: archived (commit <commit>) · pushed: <pushed>
  follow-ups created: <follow_ups>
```

When the archive script also printed `PARENT_ARCHIVED:`, append
` · parent archived` to the `outcome:` line.

**`aitask-pickweb` alternate outcome.** pickweb never archives. Its final step
writes a completion marker for `aitask-web-merge` to apply later, so its
`outcome:` line reads
`outcome: implemented on branch <branch> · archive pending (run aitask-web-merge)`
and `pushed:` is omitted. The first line is unchanged.

## Stopped

**Input:**

| Variable | Description |
|----------|-------------|
| `task_id` | The task the run was working on, or the requested `t<N>` (see Rules). |
| `task_name` | Its name, per the Rules above. |
| `outcome` | One value from the outcome table below. |
| `reason` | One line saying why the run ended here. |
| `next` | What the user does to continue: the re-pick command, the manual step, or `nothing — the task is unchanged`. |

`outcome` is a closed vocabulary:

| `outcome` | The task after this run |
|-----------|-------------------------|
| `in-flight` | Still `Implementing` and re-enterable, e.g. archival deferred, a merge stopped, or a paused checklist. |
| `ready` | Reverted to `Ready`. `reason` says whether the approved plan was kept. |
| `aborted` | Ended by an Abort Procedure (Task Abort, or the pickrem/pickweb Abort Procedure): returned to its pre-run status. pickweb's abort has nothing to revert, because it never changed the task file. |
| `split` | Decomposed into child tasks; the parent stays `Ready` with pending children. |
| `unchanged` | Nothing was claimed or changed by this run (see the outcome-accuracy rule). |

Display:

```text
■ aitask workflow stopped — t<task_id> <task_name>
  outcome: <outcome>
  reason: <reason>
  next: <next>
```

Then **end the workflow**. Nothing runs after the banner.
