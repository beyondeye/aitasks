---
Task: t1879_document_brainstorm_recovery_and_delete_subcommands.md
Base branch: main
Output branch: main
---

# t1879 — Document `ait brainstorm delete` and the three `apply-*` recovery subcommands

## Context

Four `ait brainstorm` subcommands appear in the dispatcher (`ait`, `brainstorm)` case)
and its `--help` text, but nowhere on the website: `delete`, `apply-initializer`,
`apply-explorer`, `apply-synthesizer`. The TUI already *tells* users to run the
`apply-*` commands (its failure banner says "run `ait brainstorm apply-explorer <N>
<agent>` to retry", `brainstorm_app.py:3641/3803/4412/6057`), so a user who hits that
banner today finds no page explaining what the command does. The Session tab's
**Delete** row is documented; the CLI form and its exact effect are not.

Intended outcome: the brainstorm how-to page gains a recovery procedure and the
CLI form of delete; the reference page gains the full CLI subcommand table, the
undocumented Running-tab `i` key, and the per-agent files the recovery procedure
points at. Docs only — no code change.

## Facts verified in the code (the basis for every sentence below)

**`delete`** (`.aitask-scripts/aitask_brainstorm_delete.sh`, `brainstorm_session.delete_session`):
- `ait brainstorm delete <task_num> [--yes|-y]`; without `--yes` it prompts `Are you sure? [y/N]`; prints `DELETED:<task_num>`. Fails with "No brainstorm session found for task N" when there is none.
- Removes the whole crew worktree `.aitask-crews/crew-brainstorm-<N>/` (`shutil.rmtree`), then deletes the local `crew-brainstorm-<N>` branch and *tries* to delete it on `origin` (best-effort, failure silent).
- Does not check for running agents. Touches neither the task file nor `aiplans/`.
- Not reversible. (If the remote delete failed, a pushed copy of the branch may survive on `origin` — say only that, no recovery recipe.)
- Session-tab **Delete** runs exactly `ait brainstorm delete <N> --yes` (`brainstorm_app.py:5801`).
- Session-tab **Pause** only writes `status: paused` — "Agents will not be dispatched" (`brainstorm_app.py:5470/5541`). It does **not** stop agents already running, so it is not advice for "before you delete".

**Apply — what the studio does on its own** (`brainstorm_app.py`):
- *Initializer:* applied on session load (`_load_existing_session` → `_try_apply_initializer_if_needed`), on initializer completion, and by **Ctrl+R**. The automatic attempts are gated by `n000_needs_apply`: only while `n000_init` is still the import placeholder ("Imported proposal (awaiting reformat): …") **and** the output has all four delimiters. No periodic retry. **Ctrl+R and the CLI bypass that gate** (`force=True` / the CLI calls `apply_initializer_output` directly).
- *Explorer / synthesizer:* on session load `_scan_existing_explorers/_synthesizers` start tracking every in-flight agent and every `Completed` agent whose output still needs applying; a 5 s poll applies them. A failed apply leaves the agent tracked, so an open studio keeps retrying it. Agents whose status is `Error` / `Aborted` are never tracked (`_agent_apply_scan_should_track`) and the poll drops them, so the studio never applies their output.
- *Running tab `i`* on a group row (`_retry_group_apply`, `brainstorm_app.py:2775`) force-re-applies the group's **Completed** agents (explore / synthesize / compare groups). Not documented anywhere today. (Source comment at 2351 says `S`; the handler is `i` — doc follows the handler.)

**Apply — the CLI** (`aitask_brainstorm_apply_*.sh` → `brainstorm_session.apply_*_output`):
- `apply-initializer <task_num>` (also accepts `brainstorm-<N>`): re-parses `initializer_bootstrap_output.md`, validates, then **unconditionally overwrites** `br_nodes/n000_init.yaml` and `br_proposals/n000_init.md`. Any edit made to the first node or its proposal since the import is replaced.
- `apply-explorer <task_num> <agent_name>`: re-parses `<agent>_output.md`, creates one new node, merges new dimensions, moves HEAD to it. `apply-synthesizer` is the same, with the node parented on every source node it merged.
- Explorer/synthesizer refuse with "node <id> already exists" — a second run never duplicates a node. That is a *different* guarantee from the initializer's (which replaces).
- Works whatever the agent's status, so it is the only route for an `Error` / `Aborted` agent that still wrote a complete output.
- Output: `APPLIED:<node_id>` (stdout) / `APPLY_FAILED:<error>` (stderr, exit 1).
- **Error logs exist only for some failures.** Initializer: `initializer_bootstrap_apply_error.log` is written only on a YAML parse error; missing delimiters and node/proposal validation failures write no log. Explorer/synthesizer: `<agent>_apply_error.log` is written for failures inside the apply (parse, validation, existing node) but not for a missing output file. A log is overwritten by the next logged failure and never removed on success, so an existing log may describe an older failure. → The banner / `APPLY_FAILED:` message is the primary diagnosis; the log is supplementary.
- Agent names (`explorer_001a`, …) appear in the banner, on the Running tab, and as `<agent>_output.md` filenames in the crew worktree.
- **Do not document `--help` for the three apply commands**: `apply-initializer --help` treats `--help` as a task number (`APPLY_FAILED:No initializer output at .aitask-crews/crew-brainstorm---help/…`); the other two print a usage line on stderr with exit 2. (Follow-up bug, below.)

## Implementation

### 1. `website/content/docs/tuis/brainstorm/how-to.md`

**a. "How to Manage Sessions"** — replace the closing CLI sentence (line 150) with:

> The same actions are available from the command line: `ait brainstorm status <task_num>`, `ait brainstorm list`, `ait brainstorm archive <task_num>`, and `ait brainstorm delete <task_num>`.
>
> Deleting cannot be undone. It removes the session's worktree (`.aitask-crews/crew-brainstorm-<task_num>/`, with every node and proposal in it) and its `crew-brainstorm-<task_num>` branch, locally and, when it can, on the remote. The task file and any plan you already finalized into `aiplans/` stay. On the command line, `delete` asks for confirmation; `--yes` skips the question. It does not check for running agents, and pausing the session only stops new ones from starting, so wait until the Running tab shows no agent at work.

**b. New section "How to Recover a Stuck Apply"**, after "How to Manage Sessions", before "tmux integration". Draft:

> When an agent finishes, the studio reads the agent's output file and adds the result to the graph. This step is called *apply*. The studio only applies while it is open. When you reopen a session, it applies the output of every explorer and synthesizer that finished in the meantime, and the initializer's output if the first node is still waiting for it. You need to act yourself in three cases: an apply failed and a banner shows the error, an agent ended with status Error or Aborted after writing its output, or you want to re-import the initializer's output over a first node that already has one.
>
> 1. Read the error in the banner (the command line prints it as `APPLY_FAILED:<error>`). Some failures also leave a log in `.aitask-crews/crew-brainstorm-<task_num>/`: `<agent>_apply_error.log` for an explorer or synthesizer, `initializer_bootstrap_apply_error.log` for the initializer. A log is not written for every failure and is kept after a later success, so trust the current message over an old log.
> 2. If the agent's output is at fault, fix it: `<agent>_output.md` in the same directory, or `initializer_bootstrap_output.md` for the initializer. The agent's name, such as `explorer_001a`, is in the banner and on the Running tab.
> 3. Apply the output again:
>    - explorer or synthesizer: while the studio is open it retries a failed apply by itself; press **i** on the agent's group in the Running tab to retry at once. For an agent that ended with Error or Aborted, only the command line applies it: `ait brainstorm apply-explorer <task_num> <agent_name>` or `ait brainstorm apply-synthesizer <task_num> <agent_name>`.
>    - initializer (the import of a draft into the first node): press **Ctrl+R** on the Running tab, or run `ait brainstorm apply-initializer <task_num>`.
>
>    The commands print `APPLIED:<node_id>` on success.
> 4. If you applied from the command line while the studio was open, close and reopen it (`ait brainstorm <task_num>`) to load the new node.
>
> Retrying an explorer or synthesizer is safe: the apply refuses to create a node that already exists. Retrying the initializer is different. Ctrl+R and `apply-initializer` replace the first node and its proposal with the initializer's output, discarding any change made to them since the import, so copy anything you want to keep first.

(Step 4: during implementation confirm whether the open studio reloads the graph after an external CLI apply — the poll drops an already-applied agent without calling `_load_existing_session`, so the reopen advice is expected to stand. If a reload does happen, drop step 4.)

Prose-rule pass (`doc_update_guide.md` "Prose rules"): no staged contrast, no em dash as connector, no bold for emphasis (bold only for keys and on-screen labels), "apply" defined once and used consistently. `depth: intermediate` stays. The how-to keeps only the commands its steps use; the full table goes to the reference page.

### 2. `website/content/docs/tuis/brainstorm/reference.md`

**a. Key table** (line 28 area) — add after the `Ctrl+R` row:

| `i` | Retry applying the output of the focused group's completed agents | Running tab (group row) |

and reword the `Ctrl+R` row's action to "Retry applying the initializer output (replaces the first node)".

**b. New section "### Command-line subcommands"** immediately before "### Session files and layout": one sentence ("Each subcommand takes the session's task number.") then a table built from each script's usage/help output:

| Command | What it does | Prints |
|---|---|---|
| `ait brainstorm <task_num>` | Open the studio for the task | — |
| `ait brainstorm init <task_num> [--proposal-file <path>]` | Create the session; with a draft, start an initializer agent that imports it | `INITIALIZED:<task_num>` (+ `INITIALIZER_AGENT:` / `RUNNER_STARTED:` with a draft) |
| `ait brainstorm status <task_num>` | Show the session's metadata | — |
| `ait brainstorm list` | List all sessions | — |
| `ait brainstorm archive <task_num>` | Export HEAD's proposal to `aiplans/`, mark the session archived, remove its worktree | `PLAN:<path>`, `ARCHIVED:<task_num>` |
| `ait brainstorm delete <task_num> [--yes]` | Permanently remove the session's worktree and branch | `DELETED:<task_num>` |
| `ait brainstorm apply-initializer <task_num>` | Rewrite the first node and its proposal from `initializer_bootstrap_output.md` | `APPLIED:n000_init` / `APPLY_FAILED:<error>` |
| `ait brainstorm apply-explorer <task_num> <agent_name>` | Add the explorer's node from `<agent>_output.md` | `APPLIED:<node_id>` / `APPLY_FAILED:<error>` |
| `ait brainstorm apply-synthesizer <task_num> <agent_name>` | Add the synthesizer's merged node from `<agent>_output.md` | `APPLIED:<node_id>` / `APPLY_FAILED:<error>` |

Followed by: "When to use the `apply-*` commands: [How to Recover a Stuck Apply]({{< relref "/docs/tuis/brainstorm/how-to#how-to-recover-a-stuck-apply" >}})."

**c. "Session files and layout" table** — add two rows:

| `<agent>_output.md` | An agent's raw output, which apply reads (`initializer_bootstrap_output.md` for the initializer) |
| `<agent>_apply_error.log` | Written by some apply failures for that agent (`initializer_bootstrap_apply_error.log` for the initializer); kept after a later success |

**d.** No change to `_index.md` (it lists Session-tab actions only).

### 3. Step 9 (Post-Implementation)

Commit the two website pages with `documentation: Document brainstorm delete and apply recovery subcommands (t1879)`, then archive per task-workflow Step 9.

## Verification

```bash
cd website && hugo build --gc --minify && python3 check_links.py --build
```
- `check_links.py` must pass (new relref + new `#how-to-recover-a-stuck-apply` anchor).
- Offer `python3 check_link_relevance.py` (report only) since a new internal link is added.
- Re-read both sections against "Facts verified" above: every command line must match the script's usage string; the initializer-replaces vs explorer-refuses distinction, the reopen catch-up, and the log-is-partial caveat must each be present.

## Follow-ups to offer at Step 8 (not in scope here)

- Bug: the dispatcher advertises "Run 'ait brainstorm <subcommand> --help'", but `apply-initializer --help` is parsed as task number `--help` (`APPLY_FAILED`), and `apply-explorer` / `apply-synthesizer --help` print only a stderr usage line with exit 2. Give the three scripts a real `--help` like `aitask_brainstorm_delete.sh`'s `show_help`.
- Possibly fold into the same task: the `apply-initializer` CLI has no guard against overwriting an edited first node (no `n000_needs_apply` check, no confirmation); and `brainstorm_app.py:2351` names the group retry key `S` where the handler binds `i`.

## Risk

### Code-health risk: low
None identified. Two documentation pages change; no code, scripts or tests are touched.

### Goal-achievement risk: low
None identified. Every documented behaviour, including the three corrections from plan review (initializer retry replaces the first node; reopening catches up automatically; error logs are partial), was read from the scripts and the TUI/session code cited above. The one remaining unconfirmed point (whether an open studio reloads after a CLI apply) has its fallback wording fixed in the plan.

## Post-Review Changes

### Change Request 1 (2026-11-15 17:40)
- **Requested by user:** The recovery intro promised automatic catch-up for every finished explorer/synthesizer, but a Completed agent whose output lacks a delimiter block is silently skipped (`_explorer_needs_apply` → False; never tracked on reopen, dropped by the poller, no banner; synthesizers share the predicate). Add "Completed but no new node appeared" as a case, qualify the catch-up, and point at Running-tab `i` / the apply CLI to surface the error.
- **Changes made:** Intro now states the four required block markers and that catch-up applies only to complete output. Replaced the inline case sentence with a bullet list of four cases, including "Completed but no new node appeared / first node still shows the imported placeholder" (the initializer's `n000_needs_apply` checks the same four markers). Restructured the steps: find the name; get the error (run the apply yourself for a skipped agent); fix the output; apply again (`i` for Completed explorer/synthesizer, which also runs for skipped output; CLI for Error/Aborted and also Completed; Ctrl+R / CLI for the initializer); reopen. Narrowed the Error/Aborted case to explorer/synthesizer, because the initializer makes one best-effort apply attempt on failure (`brainstorm_app.py:6043`).
- **Files affected:** website/content/docs/tuis/brainstorm/how-to.md

## Final Implementation Notes
- **Actual work done:** `website/content/docs/tuis/brainstorm/how-to.md`: "How to Manage Sessions" now lists `ait brainstorm delete <task_num>` and a paragraph on what delete removes (worktree, local branch, best-effort remote branch), what it keeps (task file, finalized `aiplans/` plan), `--yes`, irreversibility, and that it does not check for running agents (Pause only stops new dispatches). New section "How to Recover a Stuck Apply": defines *apply*, the four required block markers, reopen catch-up, four cases needing manual action, and a five-step procedure (find name, get error, fix output, apply again via `i` / CLI / Ctrl+R, reopen), ending with the explorer/synthesizer-refuse vs initializer-overwrite distinction. `reference.md`: `i` key row (Running tab group row), Ctrl+R row notes it overwrites the first node, new "Command-line subcommands" table for all nine subcommands with their output lines and a relref to the how-to, and two rows in the session-files table (`<agent>_output.md`, `<agent>_apply_error.log`).
- **Deviations from plan:** Plan-review corrections (before approval): the initializer retry replaces the first node, reopening catches up automatically, error logs exist only for some failures, and Pause does not stop running agents. Post-review Change Request 1: a Completed agent whose output is missing a block marker is skipped silently, so it became its own recovery case. The Error/Aborted case was narrowed to explorer/synthesizer.
- **Issues encountered:** Confirmed the open studio does not reload the graph after an external CLI apply (the poller drops an already-applied agent without `_load_existing_session`; `_refresh_runtime` refreshes only the status strip and Running tab), so the "close and reopen" step stays.
- **Key decisions:** The full CLI table lives on the reference page, and the how-to keeps only the commands its steps use (doc_update_guide page-type rule). `--help` is not documented for the three apply commands because it does not work for them (see below). `_index.md` is unchanged.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_brainstorm_apply_initializer.sh:29-35 — no --help handling: \`ait brainstorm apply-initializer --help\` treats "--help" as a task number and prints APPLY_FAILED (crew-brainstorm---help), although the dispatcher (ait:326) advertises \`<subcommand> --help\``
  - `.aitask-scripts/aitask_brainstorm_apply_explorer.sh:30-33 / aitask_brainstorm_apply_synthesizer.sh:30-33 — --help prints only a stderr usage line and exits 2 instead of help text with exit 0`
  - `.aitask-scripts/brainstorm/brainstorm_app.py:2351 — comment names the group retry-apply key \`S\`; the handler at :2775 binds \`i\``
