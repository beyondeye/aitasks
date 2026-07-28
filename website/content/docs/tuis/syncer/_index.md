---
title: "Syncer"
linkTitle: "Syncer"
weight: 40
description: "Cross-repo sync console for branch desync, framework versions, and shared settings"
maturity: [stabilizing]
depth: [intermediate]
---

`ait syncer` is a Textual TUI that surfaces per-repo **state** across **every discovered aitasks repo** — how far each repo's tracked branches have drifted from `origin`, which framework version it has installed, and whether its shared settings agree with the others — and acts on the repo you highlight. It is organized into three tabs: **Branches**, **Versions**, and **Settings**. With a single repo it shows just that repo; when two or more are discovered — live tmux sessions plus the [cross-repo project registry]({{< relref "/docs/workflows/multi_project" >}}) — the tables gain a per-project dimension and every action targets the highlighted row's repo.

> **Customizable keys:** every shortcut here can be rebound. Press `?` in this
> TUI for the in-place editor, or open
> [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).

## Purpose

Cross-machine, multi-repo workflows accumulate drift of several kinds. Another PC pushes commits to `origin/main`; a mobile session lands a task on `origin/aitask-data`; one project sits three framework releases behind the others; a repo you set up months ago still defaults to a different code agent than the rest. The syncer makes each kind of drift visible and resolvable from one place without leaving tmux. Pair it with [monitor]({{< relref "/docs/tuis/monitor" >}}) and [minimonitor]({{< relref "/docs/tuis/minimonitor" >}}), which surface a compact one-line desync summary in their session bar fed by the same data helper.

## Launching

```bash
ait syncer                # manual launch
ait syncer --interval 30  # override the automatic refresh interval (seconds)
ait syncer --no-fetch     # offline mode — skip git fetch
```

`ait ide` can also launch a singleton `syncer` window automatically — see [`ait ide` autostart](#ait-ide-autostart) below.

## Layout

The syncer window stacks vertically:

1. **Header** — application title and a subtitle showing the repo count (multi-repo mode), the refresh interval, and the fetch state (e.g., `repos=3  interval=60s  fetch=on`).
2. **Tab bar** — Branches, Versions, Settings.
3. **Active tab's content** — a table, plus a detail panel on the Branches tab.
4. **Footer** — dynamic keybinding hints for the active tab.

### Branches tab

One row per repo × tracked ref (`main`, `aitask-data`).

| Column | Meaning |
|--------|---------|
| Project | Repo the row belongs to (multi-repo mode only) |
| Branch | Tracked ref — `main` or `aitask-data` |
| Status | Sync state of that ref against `origin` |
| Ahead | Local commits not on `origin` |
| Behind | Remote commits not pulled |
| Fetched | Age since that repo's last successful fetch (`32s`, `5m`, `—` if never) |

Below the table, a **detail panel** lists the subjects of remote commits not yet pulled for the selected row, and the affected file paths. With a single repo the Project column is omitted and the last column shows the wall-clock time of the last refresh instead of an age.

In multi-repo mode the repo you launched from is always listed first, even if it is not in the registry. Repos sharing a name are disambiguated with a compact path suffix.

### Versions tab

One row per repo (not per ref).

| Column | Meaning |
|--------|---------|
| Project | Repo the row belongs to |
| Installed | Framework version read from that repo's `.aitask-scripts/VERSION` |
| Latest | Latest published framework release — resolved once and shared by every row |
| Status | `up_to_date`, `behind`, `ahead`, or `unknown` |
| State | Progress of an upgrade launched from this TUI — see [Result reporting](#result-reporting) |

### Settings tab

One row per synced setting, one column per repo.

| Column | Meaning |
|--------|---------|
| `≠` | Marks a row whose repos do not all agree |
| Operation | The setting — currently one row per code-agent operation |
| *(one per repo)* | That repo's effective value plus a provenance marker |

### Moving around

The tabs have no individual hotkeys; navigate with the arrow keys:

| Key | Action |
|-----|--------|
| **←** / **→** | Previous / next tab — works from anywhere, including inside a table |
| **↓** | From the tab bar, enter the active tab's table at the first row |
| **↑** | On the first row of a table, return focus to the tab bar |

Within a table, **↑** / **↓** move the row cursor as usual.

## Polling and refresh

**Only the Branches tab is polled automatically.** It refreshes every 60 seconds by default. To keep network traffic bounded with many repos, each tick runs `git fetch` for **one** repo — the one whose last successful fetch is oldest (never-fetched repos first) — while every repo's ahead/behind state is recomputed from local git data. The **Fetched** column shows each repo's age since its last successful fetch, so you can always see how current a row is. With a single repo, every tick fetches it.

**The Versions and Settings tabs load on first visit and refresh only on demand.** Opening the Versions tab is what pays for the release lookup, and opening the Settings tab is what pays for reading each repo's configuration — a session that never visits them pays neither. Press `c` on either tab to reload it. The Settings tab also reloads itself after a push.

| Key | Tab | Action |
|-----|-----|--------|
| **r** | Branches | Refresh now — fetches the highlighted row's repo immediately |
| **f** | Branches | Toggle `git fetch` on/off (offline mode) |
| **c** | Versions | Re-read every repo's installed version, and the latest release when fetching |
| **c** | Settings | Re-read the settings matrix |

A manual `r` also pushes that repo to the back of the automatic fetch queue (the scheduler simply picks whichever repo is least recently fetched). The CLI flags `--interval SECS` and `--no-fetch` set the initial values; the `f` toggle changes the fetch state at runtime and the subtitle updates accordingly. With fetch off, all state is local-only, the Fetched ages keep growing, and the version lookup makes no network call at all.

## Mouse Support

The Syncer TUI supports full mouse interaction in addition to the keyboard shortcuts:

- **Click a tab** — switch to Branches, Versions, or Settings.
- **Click a row in any table** — select it (mirrors ↑ / ↓ navigation).
- **Scroll wheel** — scroll the detail panel, table content, and dialog bodies.
- **Click dialog buttons** — every confirmation, refusal, and wizard button is clickable.

All keyboard actions documented below remain available.

## Branch actions

Actions on the Branches tab always target the **highlighted row's repo** — highlight another project's `aitask-data` row and press `s` to sync that repo without leaving the TUI.

| Key | Target ref | Action |
|-----|-----------|--------|
| **s** | `aitask-data` | Sync via that repo's `ait sync --batch` (auto-merges frontmatter conflicts) |
| **u** | `main` | Pull with `git pull --ff-only` in that repo |
| **p** | `main` | Push to `origin main:main` from that repo |
| **a** | (last failure) | Re-open the most recent failure modal |

The syncer scopes each action to the appropriate ref: `s` only operates on `aitask-data` rows, `u` and `p` only on `main` rows — the footer hints follow the highlighted row. Before running anything, the syncer verifies the target repo still resolves (and, for pull/push, that a status snapshot exists so the branch is derived from the right repo); failures surface as a notification naming the project. There is no batch fan-out: each action affects exactly one repo.

The `u` action refuses to pull on a dirty working tree or when HEAD is not on `main`. The `s` action runs the same code path as the [`ait sync`]({{< relref "/docs/commands/sync" >}}) CLI in batch mode; if `aitask_merge.py` cannot resolve a conflict automatically, the syncer pushes a conflict-resolution screen that can hand off to interactive sync.

## Framework versions

The Versions tab shows which framework version each discovered repo has installed, compares it to the latest published release, and can upgrade a repo from the TUI.

**Installed** is read from each repo's own `.aitask-scripts/VERSION`. **Latest** is resolved **once per refresh and shared by every row**, so the network cost does not grow with the number of repos.

### Reading the version cells

A trailing `*` marks a value that was not confirmed by the most recent refresh. The two columns are marked under **different** conditions:

| Cell | `*` means |
|------|-----------|
| **Installed** | An upgrade launched from this TUI is in flight for that repo. The value shown is the last one actually read from disk — never the version you asked for. |
| **Latest** | The shared value was not confirmed this refresh: either fetch is off (`f`), or the lookup failed and the previous value was kept. Also marked while that row's upgrade is in flight. |

Turning fetch off never marks the **Installed** column — that value is read from the local filesystem and needs no network. A `—` means the value has never been resolved. When a lookup fails the last known value is kept and marked, but the reason is not shown in the table.

### Upgrading a repo (`U`)

Press **`U`** on a version row. The key is uppercase on purpose: the action rewrites framework files in another repository, so it deliberately does not share the muscle memory of the lowercase Branches keys (`u` is Pull).

A dialog asks for the target version — either the **latest release** or a **pinned version** (`0.28` or `0.28.0`; anything else is rejected in the dialog). After you confirm, the syncer opens a new tmux window named `upgrade-<project>`, rooted in the target repo, running:

```bash
./ait upgrade <version> && ./ait setup
```

Neither `ait upgrade` nor `ait setup` takes a target-directory flag — each operates on the repo it was invoked from. That is why the syncer spawns a shell **inside** the target repo rather than calling them with a path, and it is also why `ait setup` can still prompt you in that window: it has a terminal, so its questions are answerable. The `&&` is deliberate — a failed upgrade is not followed by `ait setup`.

If tmux is not available, the upgrade is refused with a message telling you to run `ait upgrade` in that repo from a shell.

### When an upgrade is refused

Upgrading a repo that is actively being used can replace the framework scripts a running TUI or code agent is in the middle of calling. Before launching, the syncer inspects the target — but **what it inspects depends on the target**, and the four cases behave differently:

| Target | What is inspected | Outcome |
|--------|-------------------|---------|
| A repo with a **live tmux session** and no framework windows | That session's windows are enumerated and classified | Proceeds to the confirmation dialog |
| A repo with a live session holding a framework TUI window, or an `agent-`, `create-`, or `brainstorm-` companion window | Same, and the offending windows are identified | **Refused** — the dialog names each window so you know exactly what to close |
| A repo with a live session whose window list or window classifier could not be read | The failure itself | **Refused** — an inconclusive check is treated as busy, never as idle |
| A repo known only from the **cross-repo registry** (`~/.config/aitasks/projects.yaml`), with no live tmux session | **Nothing — no enumeration or classification is performed at all** | Proceeds to the confirmation dialog |

The refusal is a refusal, not a warning: the confirmation dialog is not offered. The refusal screen does carry a **`Force…`** button, which re-inspects the target and — if it is still busy — raises a **separate, explicitly destructive confirmation** naming the freshly detected windows. Only that second confirmation launches the upgrade anyway. Two dialogs rather than one is intentional: the button that starts a risky upgrade is never the same keystroke as the button that merely asks to consider it.

For a registry-only repo the syncer creates that project's configured tmux session to run the upgrade in.

### What the activity check cannot see

The check has a **declared bound**, and it is narrower than it may appear:

- It only ever examines the windows of the **target repo's own tmux session**. An `ait` command running in an unrelated terminal, a detached background process, or a session on another machine that shares the same checkout is invisible to it.
- A repo with no live tmux session is **not inspected at all** (the last row above). Nothing was checked, so nothing was ruled out.

Treat a clean check as "no framework windows were found in that repo's tmux session", not as "nothing is using that repo". Before upgrading, make sure you know what else is running against it.

### Upgrading the repo the syncer is running from

Upgrading your *own* repo cannot be done in the background: the upgrade replaces the very framework files the running TUI shells out to, so every subprocess afterwards would be new code driven by stale in-memory state.

Instead, the syncer **exits first**. It shows you what is currently live in the session as an *advisory* — not a refusal, since the repo you work in almost always has framework windows open — and on confirmation writes an upgrade request and quits. The `ait syncer` launcher then runs the upgrade in the window the TUI just vacated. This path requires that the syncer was started via `ait syncer`; started any other way it refuses and tells you to run `ait upgrade` from a shell.

Note that the *other* framework windows in the session are not exited. The syncer's advisory lists them precisely so you can close them yourself first.

### Result reporting

The **State** column reports only what the syncer actually observed:

| State | Meaning |
|-------|---------|
| *(empty)* | No upgrade has been launched from this TUI for that repo |
| `upgrading…` | The spawned upgrade window is still alive |
| `re-check needed` | The upgrade window is gone, or the syncer never managed to attach to it — either way the outcome is unknown |

There is deliberately **no "succeeded" state**. The syncer's spawn returns as soon as the window exists, `ait setup` may sit at a prompt for minutes, and nothing reports back — so the TUI never claims a result it did not see. Press `c` to re-read the installed version and find out what actually landed.

## Cross-repo settings

The Settings tab compares one shared setting across every discovered repo and can propagate one repo's value to the others.

**What is synced today: the default code agent per operation** — nothing else. Each row is one operation (`pick`, `explain`, `qa`, …), and the rows are derived from the operations the repos themselves configure, so a repo that does not set an operation another repo does still gets a cell for it.

### Reading the matrix

Each cell shows that repo's **effective** value plus a marker naming where it came from:

| Cell | Meaning |
|------|---------|
| `claudecode/opus5` | Resolved from the repo's project-level config |
| `claudecode/opus5 (local)` | Resolved from a per-user override in that repo |
| `claudecode/opus5 (default)` | No config sets it; this is the built-in fallback |
| `conflict` | The config files and the repo's own resolver disagree — the syncer reports the disagreement rather than guessing which is right |
| `unavailable` | That repo's configuration could not be read |

A **`≠`** in the first column marks a row whose repos do not all agree. It is computed over the **readable** repos only — an unreadable repo's agreement is unknowable, so one broken repo does not flag every row. A `conflict` cell always flags its row: something in that repo is genuinely wrong.

### Where a value comes from

There are **two stored layers plus a built-in fallback**, consulted in this order:

1. `aitasks/metadata/codeagent_config.local.json` — per-user, gitignored, personal to that checkout
2. `aitasks/metadata/codeagent_config.json` — per-project, git-tracked, shared with that repo's team
3. The built-in default compiled into the framework

These three are the only persistent state, and they are what the provenance markers above report.

The `--agent-string` flag accepted by `ait codeagent` is **not** one of these layers. It is a per-invocation override: it wins for that single command, is written nowhere, and changes nothing a later command or another repo sees. It also cannot affect this tab — `ait syncer` takes no such flag, and the syncer deliberately strips agent-string and metadata-path variables from the environment it resolves each repo with, so every repo is read in its own terms rather than inheriting yours.

`seed/` is **not** a layer either. It is a setup-time copy source that `ait setup` copies into `aitasks/metadata/`; an installed project has no `seed/` directory at its root, and there is no `(seed)` provenance marker.

### Pushing a value to other repos (`p`)

Press **`p`** on a settings row. The action only exists when two or more repos are discovered — with a single repo the key is absent from the footer entirely.

The push is a four-step wizard. **Back** (or **Esc**) steps backward through the first three, keeping your earlier choice selected; on the first step it cancels the push:

1. **Source** — which repo's value to copy. Only repos holding a usable value are offered; a `conflict` or `unavailable` repo has nothing coherent to propagate.
2. **Destinations** — which repos to write it into. Every other repo is offered, *including* conflicted ones — a repo whose configuration disagrees with itself is often the one most worth fixing.
3. **Layer** — always asked, and with **no default selected**. `project` writes `codeagent_config.json` (git-tracked, shared with that repo's team); `local` writes `codeagent_config.local.json` (gitignored, personal to that checkout). Pressing Enter on an untouched dialog asks you to choose rather than picking one for you.
4. **Results** — one line per destination saying what happened.

### When a project write would be masked

Because the local layer wins, writing the project layer into a repo whose local layer already sets that operation would change a file and change nothing the repo actually uses. The syncer detects this before writing and asks, once per affected destination:

| Choice | What it leaves on disk |
|--------|------------------------|
| **Skip** | Nothing is written to that repo |
| **Write local** | That repo's *local* layer is set to the pushed value; its project layer is untouched |
| **Clear + project** | The local override for that operation is removed and the project layer is written |

These prompts appear after the layer step, one destination at a time. **Esc** here means *skip this repository* rather than going back — the destinations are being drained in sequence, so there is no earlier step to return to mid-queue.

**Clear + project** writes the project layer first and clears the override second. If the clear fails, the override is still in place, so the repo's effective value is exactly what it was before and nothing has silently swung to a value you did not choose — the result line says so, and running the push again converges.

### When a push is rejected

Model catalogs are per-repo. A value naming a model that is not in the destination's `models_<agent>.json` is rejected with a reason rather than written, as are a malformed agent string and a destination whose configuration cannot be read. Rejections are reported per destination, so one bad target does not abort the rest of the push.

### The push writes files but commits nothing

A successful push leaves an **uncommitted change in the destination repo** that you must review and commit there.

If the destination uses a separate `aitask-data` branch, that change is not visible from its main checkout: `aitasks/metadata/` is a symlink into `.aitask-data/`, which is a worktree on the data branch and is ignored by the main one. `git status` and `git diff` in the destination's main checkout will show nothing at all. Use [`ait git`]({{< relref "/docs/commands/sync" >}}#ait-git-push) in that repo to see and commit it.

### Extending the synced set

There is no list of synced settings to edit. The operation rows are the union of the `defaults` keys every repo sets across both of its config layers, so configuring an operation in any one repo adds a row for all of them. Syncing a genuinely *different* setting — board configuration, tmux integration, anything outside `defaults` — means extending the read/diff/plan/apply seam in `.aitask-scripts/lib/cross_repo_settings.py`, which is where every repo-rooted read and write for this tab lives.

## Keyboard shortcuts

| Key | Scope | Action |
|-----|-------|--------|
| **r** | Branches | Refresh the highlighted row's repo |
| **s** | Branches (`aitask-data` rows) | Sync task data |
| **u** | Branches (`main` rows) | Pull |
| **p** | Branches (`main` rows) | Push |
| **f** | Branches | Toggle fetch on/off |
| **a** | Branches | Re-open the most recent failure modal |
| **U** | Versions | Upgrade the highlighted repo's framework |
| **c** | Versions | Re-check installed and latest versions |
| **p** | Settings | Push the highlighted setting to other repos |
| **c** | Settings | Reload the settings matrix |
| **←** / **→** / **↑** / **↓** | Any tab | Navigate tabs and rows — see [Moving around](#moving-around) |
| **j** | Any tab | Open the TUI switcher |
| **?** | Any tab | Open the shortcut editor |
| **q** | Any tab | Quit |

Keys are scoped to their tab. The Branches keys are **inert** on the Versions and Settings tabs — they disappear from the footer rather than firing an action that does not belong to what you are looking at. `p` and `c` are each shared between two tabs and resolve to the action belonging to the active one; the footer relabels as you switch. `j`, `?`, and `q` work everywhere.

## Failure handling

When sync, pull, or push exits with an error, the syncer captures the command, status, and tail of the output and shows a modal:

- **Launch agent to resolve** — opens an `AgentCommandScreen` that dispatches a code agent in a sibling tmux pane (`agent-syncfix-<action>`) with a prompt summarizing the failure. The agent is rooted in the repo the failed action targeted and launched using the configured default model from [Settings]({{< relref "/docs/tuis/settings" >}}). Minimonitor auto-spawns alongside the agent pane.
- **Dismiss** — closes the modal. The most recent failure stays available via `a` so you can re-open it later.

## TUI switcher integration

Press **`y`** from any switcher-aware TUI ([board]({{< relref "/docs/tuis/board" >}}), [monitor]({{< relref "/docs/tuis/monitor" >}}), [minimonitor]({{< relref "/docs/tuis/minimonitor" >}}), [codebrowser]({{< relref "/docs/tuis/codebrowser" >}}), [settings]({{< relref "/docs/tuis/settings" >}}), brainstorm, syncer itself) to focus the existing `syncer` window or create a new one. The switcher modal also shows a one-line desync summary for the selected session — handy for spotting drift before you switch in.

## `ait ide` autostart

Set the `tmux.syncer.autostart` key in `aitasks/metadata/project_config.yaml` to have [`ait ide`]({{< relref "/docs/installation/terminal-setup" >}}) open a singleton `syncer` window alongside the `monitor` window:

```yaml
tmux:
  syncer:
    autostart: true
```

Default is `false` (key omitted, blank, or explicitly `false`). When enabled, `ait ide` creates the `syncer` window if one does not already exist; if a `syncer` window is already running in the session, it is reused.

## Relationship to `ait sync`

[`ait sync`]({{< relref "/docs/commands/sync" >}}) is the underlying CLI that the syncer's `s` action invokes in batch mode. The CLI is the single source of truth for the bidirectional task-data sync — auto-merge rules, network timeout, batch protocol, and exit codes are documented there. The syncer adds an interactive surface, the `main` pull/push actions, the agent escape hatch on failure, and the version and settings tabs, none of which have a CLI equivalent.

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tmux.syncer.autostart` | bool | `false` | When `true`, `ait ide` opens a singleton `syncer` window inside the project session. |

For the full `tmux.*` schema (default session, monitor cadence, agent prefixes, etc.) see the [Monitor reference]({{< relref "/docs/tuis/monitor/reference" >}}#configuration). The [Settings TUI]({{< relref "/docs/tuis/settings" >}}) → Tmux tab edits the same keys interactively.

The Settings tab reads and writes `aitasks/metadata/codeagent_config.json` and `codeagent_config.local.json` in each repo — the same files the [Settings TUI]({{< relref "/docs/tuis/settings" >}}) → Agent Defaults tab edits for the current repo.

---

**Next:** [Settings]({{< relref "/docs/tuis/settings" >}}) for editing the configuration, or back to [TUIs]({{< relref "/docs/tuis" >}}) for the full TUI list.
