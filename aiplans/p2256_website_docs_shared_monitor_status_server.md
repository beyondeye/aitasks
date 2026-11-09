---
Task: t2256_website_docs_shared_monitor_status_server.md
Base branch: main
Output branch: main
---

# t2256 — Website docs for the shared monitor status server

## Context

The shared monitor status server (t2037, restart verbs t2246) is almost
undocumented on the website. A user whose monitor or minimonitor shows
behaviour a recent framework change should have fixed has no page that explains
why (the server still runs the code it started with) or how to fix it. Today the
only mentions are three short items on `website/content/docs/tuis/monitor/reference.md`.
This task adds a user-level explanation, a troubleshooting entry, a minimonitor
pointer and the `ait upgrade` behaviour, all describing current state only.

### Facts verified against source (planning-time)

| Claim in the new prose | Source |
|---|---|
| monitor and minimonitor are clients (`build_monitor_client`) | `monitor/monitor_app.py:895`, `monitor/minimonitor_app.py:2022` |
| **applink is NOT a client yet** — builds its own `TmuxMonitor` | `applink/server.py:194` at HEAD; t2037_4 (subscription) is `Implementing` |
| one server per (tmux server, framework `VERSION`); each project's `tmux.monitor` config applied per session | protocol doc "Scope", "Ticks" |
| idle exit after 30 s with no subscriber | `status_server.py:114` `DEFAULT_GRACE = 30.0` |
| unreachable → in-process fallback, then reconnect loop (backoff up to 30 s — not promised in prose) | protocol "Modes" |
| `AITASKS_MONITOR_SERVER=0` → always in-process | protocol "Modes" |
| monitor `--interval`/`--lines`, minimonitor `--interval` → that instance in-process | `monitor_app.py:894`, `minimonitor_app.py:2019` |
| `--server-status` line `SERVER:<sock>\|pid=…\|started=<ps lstart>\|version=…\|script=…` or `NO_SERVER` | `status_server.py:1280-1292`; live run printed `SERVER:/run/user/1000/aitasks/monitor-…-0.40.1.sock\|pid=820754\|started=Mon Nov 9 12:34:55 2026\|version=0.40.1\|script=…/status_server.py` |
| `--restart-server` prints `RETIRED:`/`NO_SERVER:` → `STARTED:`/`RUNNING:` → `REPLACEMENT:`; any `RETIRE_FAILED:` stops before starting anything | `status_server.py:1238-1277` |
| `RETIRE_FAILED:<sock>\|pid=<p>\|still_running` = SIGTERM sent, still alive after the 5 s wait; no SIGKILL | `status_restart.py:223`, protocol "The procedure" |
| a SIGKILLed server is safe to replace: `flock` released on exit, stale socket removed by `ensure` (restart path sees `STALE:` then ensures) | protocol "The lock means…", `status_restart.py:190` |
| `--restart-server --version V` starts **this checkout's** script under V's key → the how-to advises running the restart from a project on that version instead | `_cmd_restart` → `ensure_server(version=…)` |
| `ait upgrade` (install.sh, existing install) stops every server at any tmux server/version started from this project's `status_server.py`, prints `MONITOR_SERVER:` per RETIRED / RETIRE_FAILED, plus a hint line on failure; `AIT_MONITOR_RESTART=0` opts out; `ait setup` has no hook | `install.sh:1988-1998`, `aitask_setup.sh:2585-2615` |
| `--server-status` lists every socket of this tmux server; a field it cannot read is `-` (no matching process, unreadable `ps`) | `status_restart.py:227-243` `describe()` |
| the replacement after `--restart-server` / `ait upgrade` is whatever `ensure` finds or starts — a reconnecting client of another checkout at the same `VERSION` can start it from that checkout's script | protocol "Restart" → "Limits" |

**Deviation from the task text:** gap 1 says "Monitor, minimonitor and applink
share one background scanner". At HEAD applink does not subscribe — t2037_4,
which makes it subscribe, is `Implementing` in another session right now — so the
docs name monitor and minimonitor only. Step 8e sends t2037_4 a note naming the
sentences to extend when it lands.

## Implementation

Working on the current branch (`main`, profile `fast`). Docs only — no code.

### 1. `website/content/docs/tuis/monitor/how-to.md` — concept section

Insert a new section **after "How to Refresh the Pane List"** (before "How to
Toggle Auto-Switch Mode"):

```markdown
### How the Shared Status Server Works

Monitor and minimonitor do not each scan the tmux panes on their own. One
background **status server** does the scanning — it finds the panes, captures
their output and decides whether each agent is busy, idle or waiting for input
— and every open monitor and minimonitor reads its results. However many of
them you have open, the panes are scanned once per refresh.

- **One per tmux server and framework version.** The sessions of all your
  projects on the same tmux server share it, and it applies each project's own
  `tmux.monitor` settings from `project_config.yaml`. Projects on a different
  framework version get a server of their own.
- **Started on demand.** The first monitor or minimonitor you open starts it.
  When nothing has been connected to it for about 30 seconds, it exits by itself.
- **Fallback.** When the server cannot be started or reached, each monitor and
  minimonitor scans the panes by itself, and switches back to the server
  automatically once it is available again. Set `AITASKS_MONITOR_SERVER=0` to
  make them always scan by themselves.
- **Per-instance overrides.** Starting `ait monitor` with `--interval` or
  `--lines`, or `ait minimonitor` with `--interval`, makes that one instance
  scan on its own: the shared server uses the values in `project_config.yaml`
  and cannot honour an override for a single instance.

The server keeps running the code it was started with for as long as anything
is connected to it. When a framework change does not seem to reach your
monitors, see [How to Restart the Shared Status Server](#how-to-restart-the-shared-status-server).
```

### 2. `website/content/docs/tuis/monitor/how-to.md` — troubleshooting section

Append a new last section **after "How to Handle a Session-Name Mismatch"**
(before the `---` / `**Next:**` footer):

````markdown
### How to Restart the Shared Status Server

**When to do this:** monitor or minimonitor keeps behaving the way it did before
a framework change that should have changed it — for example, it still lists a
pane it should hide, or shows a status the change was meant to correct.

**Why it happens:** the [shared status server](#how-the-shared-status-server-works)
runs the code it was started with, and it does not exit while any monitor or
minimonitor is connected. Editing or pulling framework code in a checkout
leaves it running the old code. [`ait upgrade`]({{< relref "/docs/commands/setup-install" >}}#ait-upgrade)
restarts it for you.

**1. List the status servers:**

```bash
ait monitor --server-status
```

It prints one line per status-server socket it finds for this tmux server:

```text
SERVER:<socket>|pid=<pid>|started=<start time>|version=<version>|script=<path>
```

- `started=` is when the server process started. If that is earlier than the
  framework change, it is running the old code.
- `script=` is the copy of the framework it was started from. Projects on the
  same framework version share one server, so this can be another checkout.
- A `-` in a field means the process details could not be read.

`NO_SERVER` means no socket was found: the next monitor or minimonitor you open
starts a fresh server.

**2. Restart it:**

```bash
ait monitor --restart-server
```

This stops the server for this tmux server and for the framework version of the
project you run it in, then makes sure a fresh one is running:

```text
RETIRED:<socket>|pid=<old pid>
STARTED:<socket>|<new pid>
REPLACEMENT:<socket>|pid=<new pid>|version=<version>
```

Open monitors and minimonitors reconnect to the new server automatically; you do
not need to restart them. The replacement is normally started from this
project's files, but another checkout on the same framework version can start it
first — if the behaviour still looks stale, run `--server-status` again and check
`script=`. A server listed with another framework version belongs to the
projects on that version: run `ait monitor --restart-server` from one of those
projects.

**If the old server does not stop**, the command prints:

```text
RETIRE_FAILED:<socket>|pid=<pid>|still_running
```

The server was asked to stop but was still running after a few seconds, so
nothing new was started — a fresh start would only find the old server again.
End that process by hand, then restart again:

```bash
kill <pid>
ait monitor --server-status   # still listed with that pid a few seconds later? then:
kill -9 <pid>
ait monitor --restart-server
```

Any other `RETIRE_FAILED:` line also means nothing was stopped and nothing was
started; the text after the last `|` says why.
````

### 3. `website/content/docs/tuis/monitor/_index.md` — one-sentence pointer

In "Understanding the Layout", after the paragraph that starts "Each card in the
pane list shows the window name…", add:

```markdown
Monitor does not scan the panes itself: it reads their status from a background
status server that it shares with every other monitor and minimonitor on the
same tmux server. See [How the Shared Status Server Works]({{< relref "/docs/tuis/monitor/how-to" >}}#how-the-shared-status-server-works).
```

### 4. `website/content/docs/tuis/monitor/reference.md` — NOT edited (shared-file gate)

In-flight t2037_4 (applink subscribes to the server, `Implementing`) holds an
uncommitted edit of this file (the `AITASKS_MONITOR_SERVER` row now names "the
App Linker"). Editing it here would entangle the two sessions' hunks in one file,
so this task leaves it alone. The two small edits planned for it — "per tmux
server" → "per tmux server and framework version" in the paragraph under the
Command-line Options table, and links from its two paragraphs to the new how-to
sections — go to t2037_4 as advisory context in the Step 8e note.

### 5. `website/content/docs/tuis/minimonitor/how-to.md` — one sentence + link

Append to "How the Agent List Refreshes":

```markdown
Minimonitor reads the agent list from the same [shared status server]({{< relref "/docs/tuis/monitor/how-to" >}}#how-the-shared-status-server-works)
as monitor, so `ait monitor --restart-server` refreshes it too — run it when the
list still behaves the way it did before a framework change.
```

### 6. `website/content/docs/commands/setup-install.md` — `ait upgrade`

- "How it works" list: insert a new step 7 — "Stops the monitor status servers
  started from this project, so open monitors pick up the new code (see
  **Monitor status servers** below)" — and renumber "Clears the update check
  cache" to 8.
- Add a block after the "Superseded model defaults" paragraph:

````markdown
**Monitor status servers:**

Monitor and minimonitor read pane status from a [shared background status server]({{< relref "/docs/tuis/monitor/how-to" >}}#how-the-shared-status-server-works),
which keeps running the code it was started with. After installing the new
files, `ait upgrade` stops every status server that was started from this
project, on any tmux server, and prints a `MONITOR_SERVER:` line for each server
it stops or fails to stop. Open monitors and minimonitors reconnect
automatically to a fresh server. Another checkout on the same framework version
can start that replacement first, so if monitor behaviour still looks stale
afterwards, check `script=` in `ait monitor --server-status`. Servers started
from other projects keep running. When a server does not stop, the output ends with a hint
line; [How to Restart the Shared Status Server]({{< relref "/docs/tuis/monitor/how-to" >}}#how-to-restart-the-shared-status-server)
explains how to end it by hand.

To leave the servers running, set `AIT_MONITOR_RESTART=0`:

```bash
AIT_MONITOR_RESTART=0 ait upgrade latest
```

`ait setup` does not restart status servers. Run `ait monitor --restart-server`
when you need one replaced.
````

### Constraints honoured

- Current-state only; no version history in page bodies.
- No reconnect timing promised — "automatically".
- All new internal links use `{{< relref >}}` (same-page `#anchor` links inside
  `how-to.md` are fragment-only).
- Do not touch `website/content/docs/workflows/contribute-and-manage/contribution-flow.md`
  (another session's uncommitted edit), nor `monitor/reference.md` /
  `applink/reference.md` (t2037_4's uncommitted edits) — commit only the five
  paths of steps 1–3, 5 and 6.
- Per user review: never guarantee that a restart or upgrade loads *this*
  checkout's code (another checkout on the same `VERSION` can start the
  replacement first — say to check `script=`), and describe `--server-status`
  lines as server socket entries, with `-` meaning process details unavailable.

## Verification

1. `cd website && python3 check_links.py --build` → exit 0 (catches broken
   relrefs **and** dead `#fragment`s, including the two new anchors
   `#how-the-shared-status-server-works` / `#how-to-restart-the-shared-status-server`).
2. Grep the built page for both new heading ids to confirm the anchors Hugo
   generated match the links (check_links covers this; spot-check once).
3. Re-read each changed paragraph against the "Facts verified" table — no
   applink claim, no timing promise, `--version` advice per the table.
4. Offer `python3 check_link_relevance.py` (report-only) since new internal
   links were added.
5. Step 8e, after the commit (cite its SHA): `./ait note 2037_4 --from 2256
   --with-live` naming the new sentences that should add applink once it
   subscribes (monitor how-to concept section, `_index.md` pointer, minimonitor
   how-to sentence, setup-install block), plus the two reference.md edits from
   step 4 as optional context.

Then Step 9 (Post-Implementation): commit `documentation: … (t2256)` with only
the five website paths (steps 1–3, 5, 6), archive the task and plan.

## Risk

### Code-health risk: low
None identified. Docs-only change to five pages; no code, scripts or tests touched.
The one shared file with another session's uncommitted edit (`monitor/reference.md`)
is deliberately left out of scope.
Broken links/anchors are caught by the mandatory `check_links.py --build` step.

### Goal-achievement risk: low
None identified. Every behavioural claim was traced to source during planning
(table above), the one task-text inaccuracy (applink) is corrected rather than
copied, and all four gaps in the task map to steps 1–6.
