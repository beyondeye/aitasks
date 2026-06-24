# Releases

## v0.26.0

v0.26.0 is a big one — it lands a full gate-driven verification system, brings the mobile companion's live-terminal data plane online, and adds project groups plus a bunch of brainstorm TUI polish.

## Gate orchestration, end to end

Tasks now run their declared verification gates through a real orchestrator that handles retries, parallelism, and even detects when a gate is stuck. You can resume an interrupted task right where it left off with `aitask-resume`, `aitask-pick` surfaces in-flight tasks as resume candidates, and both the board (a new In-Flight view) and the monitor (a compact pass/pending/failed summary) show you gate progress at a glance.

## Your terminals, on your phone

The mobile companion's data plane is here. Applink streams live terminal output to the companion app as compact binary frames — full keyframes, row-level deltas for small changes, and an append fast path that sends only new lines for scrolling logs. A new headless bridge mode (`ait monitor --headless-for-applink`) runs the whole thing without a terminal UI, and a built-in firewall doctor diagnoses and offers to fix LAN issues so pairing just works.

## Project groups

You can now organize your projects into named groups with `ait projects group`. The TUI switcher and stats view gained group-aware navigation so you can cycle by group as well as by session, and there's a dedicated Project Groups tab in settings to assign, rename, and sync them.

## A calmer, sharper brainstorm TUI

The brainstorm TUI got a major layout pass: the list and graph views merged into one Browse tab, operations moved into a unified dialog and a Node Hub overlay, compare became an on-demand overlay, and session and running actions each got their own home. You can now restart or retry a whole operation group from the Running tab, and marked nodes show a clean ☑/☐ checkbox everywhere.

## Hardened mobile security

Applink got a thorough security pass — a TLS 1.2+ floor, per-IP connection and rate caps, input validation on every command verb, secure on-disk permissions, and audit logging — so the convenience of phone access doesn't come at the cost of safety.

---

## v0.25.0

v0.25.0 is a big one — it lands a whole task-gating system, opens the door to the mobile companion app, and introduces an advisory "shadow" agent that watches over your coding agents.

## Task gates that actually drive the workflow

Tasks can now carry named approval checkpoints — gates like *plan approved*, *build verified*, and *merge approved* — recorded in a durable ledger. Once you turn on `record_gates`, those gates aren't just notes: they decide when dependent tasks unblock, hold a task back from archival until everything's green, and let you pick up an in-flight task right where you left off instead of starting over. It's the connective tissue that makes the workflow resumable and dependency-aware.

## Your phone can now talk to your workspace

The new applink WebSocket listener brings up a paired, TLS-secured connection that the mobile companion app connects to over your LAN. Pairing is QR-bootstrapped, and a dedicated Devices screen lets you see what's connected and revoke any device with a keystroke.

## Meet the shadow companion

`/aitask-shadow` is a new advisory sidekick. It reads the terminal output of an agent you're following and — on demand — explains what's happening, helps you answer a prompt it's stuck on, or critically challenges its plan before you commit to it. Launch one straight from the minimonitor with the `e` key, in its own pane next to the agent it's shadowing. It's read-only and advisory by design: it never touches your work, it just makes you a better-informed driver.

## Smoother upgrades

Upgrading no longer clobbers your local model configuration. New seed models are merged in alongside whatever you've customized, so your own entries survive and the new ones simply get appended.

---

## v0.24.0

v0.24.0 is a big one — 49 tasks landed, headlined by a ground-up tmux gateway, a much nicer brainstorm experience, and some quality-of-life wins for keyboard-driven workflows.

## See your proposal while you work

The brainstorm TUI now shows the relevant proposal side-by-side as you configure your next step — in the explore wizard, in module-decompose, with a section minimap and adjustable split ratios. You can hit `Ctrl+Shift+L` to flip the preview into a syntax-highlighted, line-numbered source view. No more bouncing between screens to remember what you were building on.

## Your tmux sessions stop dying

If you've ever had a Wayland compositor restart take your agent sessions down with it, that's fixed. `ait` now runs its sessions on a dedicated, persistent tmux server placed in a systemd user slice, so they survive session teardowns and stay isolated from your everyday tmux. Under the hood this rides on a brand-new tmux gateway that centralizes every tmux call behind one chokepoint — more robust, more consistent, and guarded against regressions.

## Smarter module decomposition

module_decompose got two upgrades you'll feel immediately. There's a new "Review before apply" gate, so you can preview the proposed breakdown — and re-run it with steering notes — before anything lands. And a new "Agent-proposed" mode infers the module set straight from your plan, so you don't have to name every module up front.

## Find any shortcut, fast

Both the shortcut editor and the Settings Shortcuts tab now have a fuzzy filter box. Start typing and the keybinding you want surfaces instantly. App-scope rebinds also take effect on the live keymap right away now, instead of quietly needing a restart.

## A more capable minimonitor

The minimonitor learned two new tricks: `k` to kill the followed agent and `n` to launch its next sibling task, both right from the panel. The followed agent also gets its own dedicated card, separate from the general list, and the companion pane now holds its width when you resize the terminal.

---

## v0.23.1

v0.23.1 is a small housekeeping release that smooths out installs and setup.

## Installs that just re-run cleanly

Running the installer again won't trip over itself anymore. If the global `ait` shim is already in place, setup quietly moves on instead of bailing out — and any stray `packaging/` directory the installer used to leave behind now gets cleaned up on its own.

## Less untracked clutter from generated skills

`ait setup` now lays down the right gitignore rules so the skill variants your tools render locally stay out of your way, while the committed headless prerenders are still tracked. Your `git status` stays clean.

---

## v0.23.0

v0.23.0 is a big one — two major new capabilities land, plus a pile of macOS/portability fixes and UI polish.

## Brainstorm module decomposition

You can now split a brainstorm design into independent module subgraphs and work each one on its own track. Decompose a design into modules, merge or sync them as first-class brainstorm operations, and watch each module's status update live. When a module is ready to build, "Fast-track this module" extracts it into a linked aitask in a single pass.

## Risk evaluation in planning

Planning now sizes up risk along two separate axes — how risky the change is to code health, and how likely it is to actually hit its goal. It records both on the task, proposes mitigation follow-ups (before or after the main work), and automatically re-verifies a plan when one of those mitigations lands.

## Cross-repo planning, straight from explore

`aitask-explore` now notices when your description spans more than one repo and offers to create a cross-repo paired task — no manual wiring, the cross-repo planning flow is inherited automatically.

## A friendlier brainstorm node picker

The node action dialog now shows every operation available on a node, complete with relevance hints, and cascade delete previews exactly which nodes would go with it before you confirm.

## Smoother on macOS

Several BSD/macOS portability crashes in `ait setup` are fixed, the board now validates its Python dependencies at install time (and falls back gracefully when the fast path can't load), and the board no longer auto-refreshes by default — set an interval only if you want it.

---

## v0.22.1

A focused follow-up to v0.22.0's cross-repo release, this one is all about risk-awareness in your task workflow.

## Track risk on your tasks

Tasks can now carry a `risk` level (high/medium/low) plus a list of `risk_mitigation_tasks`. Set them straight from the CLI with `ait update --risk high`, see risk at a glance in `ait ls`, and edit it right in the board TUI. It's a lightweight way to flag the work that needs extra care before it ships.

## Risk evaluation, when you want it

A new opt-in `risk_evaluation` profile key lets you fold a risk-evaluation step into planning. Flip it on per profile or from the settings TUI — it stays out of your way until you ask for it.

---

## v0.22.0

v0.22.0 is a big one — cross-repo dependencies, fully customizable keyboard shortcuts, autonomous manual verification, and Opus 4.8 as the new default.

## Tasks that span multiple repos

You can now wire up dependencies *between* aitasks projects, not just within one. A task in your frontend repo can declare it's blocked by a task in your backend repo using the new `xdeps` fields, and the board, planner, and blocking logic all understand it. Projects are referenced by a logical name you register once — no fragile `../` paths — so cross-repo planning, task creation, and context lookups just work.

## Make every shortcut your own

The TUIs now have a full customizable-shortcuts layer. Don't like a keybinding? Open the in-TUI shortcut editor, remap it, and your override sticks across every TUI. There's also a dedicated Shortcuts tab in the settings TUI for managing them all in one place.

## Manual verification that runs itself

Manual-verification tasks no longer always need you in the loop. Turn on autonomous mode and the agent can run the checks for you — either improvising the verification on the spot or following a pre-built plan you approve. It's configurable per profile, so you decide how hands-off each workflow should be.

## Opus 4.8 is the new default

Claude Opus 4.8 is now registered and promoted to the default model, so new sessions pick it up automatically.

---

## v0.21.1

v0.21.1 is a small patch — a couple of brainstorm/monitor papercuts and a fix for the v0.21.0 release-post pipeline so the next blog post doesn't break.

## Choose-sibling picker in monitor

The monitor TUI's next-task dialog now lets you pick any ready sibling of the current task from a list, with blocked-by-sibling annotations on each row. Mid-family pivots no longer require backing out to the board.

## Brainstorm retry-apply actually retries

The `ctrl+shift+x/y/d` retry-apply bindings in brainstorm were silently doing nothing once their internal tracking set drained — typically right after the original apply ran. They now rescan the worktree for completed agents on every invocation, and surface a clear notify when there's nothing to retry.

## Release-post YAML hardening

`website/new_release_post.sh` now escapes title and description fields before writing the blog frontmatter and runs a Python YAML smoke check after generation, so a release post with inner quotes can't ship a broken page anymore (and the v0.21.0 post is now repaired).

---

## v0.21.0

v0.21.0 is a big one — a foundational refactor of how skills are authored and dispatched, the brainstorm TUI graduating from "experiment" to a real DAG-driven planning workflow, first-class cross-repo project plumbing, and a fresh mobile-companion bridge.

## Profile-aware skill templating

Every aitask skill is now authored once as a `.md.j2` Jinja template and rendered per execution profile, per agent. You stop maintaining four near-duplicate copies of each skill across Claude, Codex, Gemini, and OpenCode; the renderer fans out per-profile variants behind a thin stub. A new `ait skillrun` command lets you launch any agent with any skill at any profile (with `--profile-override` for ad-hoc tweaks and `--dry-run` previews), and the Per-Run profile editor lets you tweak the active profile right from the launch dialog. Saving a profile invalidates the right rendered variants automatically — running agents pick up the new values on next invocation.

## Brainstorm: auto-apply, DAG navigation, and operation detail

Brainstorm sessions now auto-apply agent outputs as they complete — explorer, synthesizer, and detailer all flow straight into the DAG without manual intervention, with `ctrl+shift+x/y/d` retries for the cases that fail. The Graph tab gained full 2D arrow-key navigation, an inline detail pane, `p`/`l` to peek a node's proposal or plan, `x` to pick a compare-with anchor, and clickable nodes. An `A` keybinding offers context-aware Explore / Detail / Patch actions on the focused node, and a new `OperationDetailScreen` (open with `o`) shows the operation overview plus per-agent Input / Output / log tail tabs.

## Cross-repo project registry

`ait projects` is the new home for working across multiple aitasks repos. Register projects to `~/.config/aitasks/projects.yaml` once (`add`), then list them, resolve names to paths, exec into them, prune stale entries, or run an interactive `doctor` to triage broken registrations. The TUI switcher surfaces registered-but-inactive projects with a `(stale)` marker and spawns tmux sessions on demand. `ait create --project <name>` lets you file a task into a cross-repo registry entry without leaving your current workspace.

## Mobile companion bridge

A new `ait applink` TUI generates a QR code carrying a LAN pairing URI for the mobile companion app (built in the sibling `aitasks_mobile` repo). The QR includes hostname and TLS fingerprint so pairing is one-tap. Full protocol design — WebSocket envelope, pairing flow, connection state machine, permission profiles, verb gating — is documented under `aidocs/applink/`.

## Quality-of-life

The monitor TUI finally distinguishes "agent awaiting user input" from "idle" with per-agent prompt-regex detection, surfaces a separate `awaiting` count, and prefers awaiting panes when auto-switching. Codebrowser gained an `E` keybinding to suspend into `$EDITOR` and now surfaces archived tasks that have no code commits with a dim `[no-code]` marker. `ait create` lets you fzf-pick archived task references into a new task's description. The TUI switcher auto-selects the focused agent pane's session when opened from inside monitor.

---

## v0.20.3

v0.20.3 is mostly a documentation release — a big sweep across the website to make it easier to find what you need, install the framework the way you prefer, and discover features that have been there for a while but weren't obvious.

## Linux install pages unified

The three separate install pages for Arch, Debian, and Fedora are gone. There's now a single **Linux** page with per-distro sections, and the Installation index has been reorganized into clear "Operating systems" and "Setup topics" groups. If you've ever bounced between three near-identical pages trying to find your distro, you'll like this.

## Curl-first install, with native packages as the alternative

The home page and installation pages now lead with the curl one-liner — the fastest path to getting `ait` on your machine. Native packages (Homebrew, AUR, .deb, .rpm) are still documented and recommended where they fit, but as the alternative path rather than the headline. Per-platform "Upgrade" sections now correctly point you to `ait upgrade latest` instead of suggesting (misleading) package-manager upgrades.

## A page on updating model lists

There's a new **Updating Model Lists** subpage under Installation that walks you through refreshing the supported-models list for OpenCode and the other agents, plus how to register a single known model. If you've been waiting for a way to keep your local model list current without spelunking through scripts, that's it.

## Maturity labels and mouse-support, everywhere

The sidebar maturity tag cloud now actually reflects reality: 37 doc pages got their maturity tag added or refreshed, with a new `stable` value introduced. And every TUI doc page now calls out **full mouse support** — click to select, scroll to navigate — as an alternative to keyboard. Both features have been in the framework for a while; now you can find them.

## Home page and About page polish

The home-page tour trimmed from five TUI tiles to the three most-used (Board, Code Browser, Monitor), and the About page got a refresh with a slimmer header, updated stats, and centered author/license blocks. Smaller touch-ups across Getting Started, the TUIs index, and the Overview page round out the docs sweep.

---

## v0.20.2

A polish-focused release. The website got a visual makeover, install instructions now match how you actually want to install software, and a couple of nasty bugs got squashed.

## A redesigned home page

The website home page now leads with a split hero — clear pitch on the left, a screenshot of the Board on the right — and gets straight to the point. Below that, a new "Take the tour" mosaic shows off the suite of TUIs (Board, Code Browser, Monitor, Settings, Stats) at a glance, with each tile linking through to the relevant docs. The top feature cards are clickable too, so you can jump straight into the part of the framework that interests you.

## Native installs for every platform

If you're on macOS, you can `brew install beyondeye/aitasks/aitasks`. On Arch, grab it from the AUR. On Debian/Ubuntu, install the `.deb`; on Fedora/Rocky/Alma, install the `.rpm`. The curl-based installer is still there as a fallback (and remains the recommended path on Ubuntu 20.04 / Debian 11 where Python is older), but it's no longer the only option. Each platform has its own install page now, and there's a maintainer-facing reference doc tracking what's stable, what's in progress, and what's next on the packaging roadmap.

## Code browser History screen no longer crashes

If you opened the Code Browser History screen from a cold start, it would crash with a `NoMatches` error before showing anything. Now it doesn't — the screen waits for its panes to mount before trying to populate them.

---

## v0.20.1

A quick maintenance release. The nfpm GitHub Action we relied on for building Debian and RPM packages was deleted upstream, which broke our release pipeline. v0.20.1 swaps it for a direct Docker invocation of the same tool, so .deb and .rpm packages are once again attached to every release.

---

## v0.20.0

v0.20.0 is a big one — a brand new sync TUI, package-manager installs across four ecosystems, an opt-in PyPy fast-path that makes the long-running TUIs noticeably snappier, and a wave of polish across brainstorm.

## Install via your distro's package manager

Aitasks now ships as proper packages on Homebrew, the AUR, Debian/Ubuntu (`.deb`), and Fedora/RHEL (`.rpm`). Each tag triggers a CI workflow that builds, tests, and publishes the appropriate format, so `brew install aitasks`, `yay -S aitasks`, `apt install ./aitasks_*.deb`, and `dnf install ./aitasks-*.rpm` all just work. The `ait` shim itself was extracted to a single canonical file so every package consumes the same binary.

## A dedicated syncer TUI

Run `ait syncer` and you get a live two-row view of your `main` and `aitask-data` branches: ahead/behind counts, recent commits, and the changed paths. One-key actions sync `aitask-data`, pull `main`, and push `main`; if anything fails, an in-TUI escape hatch lets you dispatch a code agent to resolve the conflict. The syncer is wired into the TUI switcher (`y`), surfaces a desync line in monitor/minimonitor, and can auto-launch via `ait ide` if you opt in.

## Opt-in PyPy fast-path

Run `ait setup --with-pypy` once and six long-running TUIs — board, codebrowser, settings, stats, brainstorm, and syncer — auto-route through PyPy 3.11. Startup and refresh are dramatically faster, with no behavior change for non-PyPy users. The `AIT_USE_PYPY` env var lets you override per invocation. Monitor and minimonitor stay on CPython for now (their bottleneck is fork+exec, not Python execution), and the stats TUI stays on CPython because of its `plotext` dependency.

## Fork-free monitor hot path

`ait monitor` and `ait minimonitor` now talk to tmux through a persistent `tmux -C` control client instead of forking a subprocess on every refresh. On a 5-pane benchmark, that's a ~10× speedup and 100% fork elimination. The control channel is supervised: when it fails, the monitor falls back to subprocess and reconnects with bounded backoff, with a status badge in the session bar showing the current state.

## Smarter agent picker and live usage stats

The agent/model picker dialog learned new tricks: cycle through Top, All, and per-agent modes with Shift+Left/Right; rank "Top by recent" using a rolling window so old high-score incumbents stop dominating; and a brand-new "Top by usage" mode shows what you actually use. Powering this is a new live usage hook that records every task completion independently of satisfaction feedback, with a `prev_month` bucket so recent-window views have data immediately on month rollover.

---

## v0.19.2

v0.19.2 is a reliability-focused release for the everyday setup and release workflows. It fixes a few sharp edges around Python environments, tmux setup, macOS docs, and stale task data during changelog generation.

## Python wrappers that actually stay inside the venv

The framework Python launchers now use wrapper scripts instead of symlink chains. That keeps `ait board` and the other Python tools inside the aitasks virtual environment, so packages like Textual, PyYAML, and linkify-it are found reliably after setup.

## Warnings before you build on stale main

After you approve a task plan, aitasks can now check whether `origin/main` moved ahead while your local branch was stale. If the remote commits touch files your plan also targets, you get a stronger warning before implementation starts, which is a much nicer time to stop and re-sync than during final merge.

## Source-tree setup gets the starter tmux config too

If you run `ait setup` directly from a source checkout, the starter tmux configuration prompt now appears correctly. That means developers working from a clone get the same mouse and truecolor-friendly tmux defaults as users running from an installed framework tree.

## macOS terminal guidance is now explicit

There is a new macOS installation page that calls out Apple Terminal's tmux limitations and points users toward truecolor-capable terminal emulators. The main installation and terminal setup pages now link into that guidance, so macOS users see the caveat before wondering why colors or right-click behavior look wrong.

## Changelog generation handles stale task data better

The changelog gather step no longer falls over when a task archive is missing locally. It falls back gracefully, and it now warns when your local task-data branch appears behind the remote so you know to sync before trusting the release notes.

---

## v0.19.1

v0.19.1 is a quick follow-up to v0.19.0 with two reliability fixes you'll appreciate if you contribute to aitasks itself or develop on macOS.

## Releases and changelogs no longer miss remote tasks

If you cut a release while local `main` was a few commits behind `origin/main`, the changelog could silently skip those tasks and the release tag could land on stale code. The release script and the `/aitask-changelog` skill now fetch and offer to pull before doing anything destructive, so you can run them confidently from any clone.

## macOS test suite is back at parity with Linux

Two long-standing portability bugs in the bash test suite have been fixed — one around BSD `sed -i` in archive-overbreadth tests, and one where macOS' tmpdir resolution made a multi-session test compare paths that should have matched. If you develop aitasks on macOS, the portability-related failures are gone.

---

## v0.19.0

v0.19.0 is mostly an infrastructure release — the Python venv story, `ait setup` on a fresh clone, and brainstorm stability all got a lot of attention. There's also a new audit-wrappers skill that closes a recurring drift class.

## A modern Python venv that installs itself

`ait setup` now requires Python ≥3.11 and will auto-install a modern interpreter for you when the system Python is too old — Homebrew on macOS, uv-managed builds on Linux. Once installed, all aitasks scripts resolve through a single helper (`lib/python_resolve.sh`) and a scoped `~/.aitask/bin` symlink, so the framework picks up the right interpreter without ever touching your shell rc files. If you've been getting "Python too old" failures on Debian or older macOS, this just works now.

## `ait setup` on a fresh clone, polished end-to-end

A whole cluster of paper-cuts in the `ait setup` flow are gone. The task-ID counter now scans the data branch on a fresh clone, so you no longer get duplicate IDs like `t1` colliding with existing tasks. `.gitignore` edits are auto-committed instead of being left dirty in your working tree, and the trailing-slash entries (`aitasks/`, `aiplans/`) that didn't actually match the data-branch symlinks are migrated to the bare form (`aitasks`, `aiplans`) so `git status` stays clean. There's also a new opt-in starter `~/.tmux.conf` for first-time tmux users, and the docs now explain the post-clone setup step explicitly.

## Brainstorm: fewer crashes, more visibility

The brainstorm TUI got a stack of fixes. Agents launched into tmux now record the actual agent PID so the Status tab stops claiming "PID dead" for a running agent. Initializer/explorer/synthesizer outputs missing `created_at` are auto-filled instead of crashing with a parse error. The agent-command screen no longer crashes on Textual ≥8.0 when you open the session/window selector, and the section minimap inside the node-detail modal is crash-free with the section jump landing on the correct row. As a bonus, each running agent now shows a 10-character progress bar in the Status tab.

## Cross-PC lock warnings

If you `ait pick` a task that's already locked by *you* on a different machine, the workflow now prompts you instead of silently re-claiming. This was the most common way to lose half-committed work when bouncing between a laptop and a workstation — now you see a "this is locked on `<other-host>`" warning and can choose whether to take it over or pick a different task.

## New skill: aitask-audit-wrappers

Adding a new skill or helper script used to mean hand-editing four parallel wrapper trees (claude/gemini/codex/opencode) and five permission-touchpoint files. The new `aitask-audit-wrappers` skill audits and ports both layers automatically — wrapper drift across agent trees and helper-script whitelist gaps across runtime/seed configs are now a one-command fix.

---

## v0.18.3

v0.18.3 is mostly a brainstorm release — the TUI got a lot more transparent and a lot more resilient when things flake out. The agent-crew state machine also took a small but breaking turn.

## Brainstorm agents run interactive by default

Every brainstorm agent type — initializer, detailer, explorer, comparator, synthesizer, patcher — now launches in a tmux pane by default instead of headless. You can watch each agent work and step in if you need to, without having to override `launch_mode` in `codeagent_config.json`. There's also a new dim-cycling activity indicator next to the initializer banner and the Status tab that flashes on each poll, so you can tell the agent is alive even when nothing visible has changed.

## Brainstorm sessions that don't get stuck

A handful of failure modes that used to leave brainstorm sessions silently broken are now recoverable. If `ait brainstorm` initializer fails, you get a scrollable error modal with the captured stderr/stdout and a "Delete branch & retry" action that handles the common stale-crew-branch case for you. `ait brainstorm delete` now actually cleans up its stale branches so the next `init` doesn't fail with "branch already exists". And the TUI no longer spuriously prompts you to apply changes on session load before the initializer has actually finished writing them.

## MissedHeartbeat is gone (and that means a small migration)

The `MissedHeartbeat` agent status that shipped in v0.18.2 has been removed. Heartbeat freshness is now decoupled from terminal status entirely — stale heartbeats no longer mutate `_status.yaml`; if you want to know whether an agent is alive, call `get_stale_agents()` or `check_agent_alive()`. **If you have crews in-flight from v0.18.2, run `ait crew cleanup --crew <id>` before resuming work** — the trimmed state machine will reject any `MissedHeartbeat` values written under the old runner.

## A friendlier `install.sh` and a hardened review prompt

`install.sh` now offers an interactive overwrite prompt when it detects an existing install in a TTY, and the non-TTY error message spells out all three recovery paths inline (`ait upgrade latest`, `bash -s -- --force`, `bash install.sh --force`) instead of leaving you to find them in the docs. On the workflow side, the Step 8 user-review prompt is now non-skippable across auto-mode and execution-profile overrides, and the workflow now offers to spin off a follow-up task for any upstream defects you flagged while patching.

---

## v0.18.2

v0.18.2 is mostly a polish release for multi-session — stats picks up every session you've got, and the monitor finally stops mixing up which project a foreign-session agent belongs to. Agent crews and brainstorm sessions also got a lot more forgiving when something flakes.

## Multi-session stats in the TUI

The `ait stats` TUI now picks up every aitasks session on your machine. A new Session panel on the left lets you cycle between them with `←` / `→` or click to jump to one. There's also a new `sessions` preset with a grouped bar chart comparing today / 7-day / 30-day activity across all of them — useful for getting a single read on where your time has been going.

## Monitor and minimonitor handle cross-session agents correctly

Previously the monitor and minimonitor TUIs would resolve task data, log paths, and "next sibling" picks against the local project even when the focused agent was running in a different aitasks session. They now route everything through the foreign session's project root, so logs open the right file and pick-next launches land in the right repo.

## Agent crews that recover instead of erroring out

Agent crews now have a new MissedHeartbeat state for transient stalls. If an agent skips a heartbeat, it goes to MissedHeartbeat first instead of straight to Error, and it'll quietly recover back to Running if the heartbeat resumes within the grace window. Errored agents can also be moved to Completed without a force override, so cleaning up after a flaky run no longer means digging into status files.

## Brainstorm sessions that heal themselves

If the initializer apply fails partway through (em-dashes in YAML were a recurring culprit), the brainstorm TUI now shows a banner instead of getting stuck, retries automatically every 30 seconds and on each reopen, and exposes `ctrl+r` for an immediate manual retry. Behind the scenes the YAML loader auto-quotes problematic scalars, and a new `ait brainstorm apply-initializer <id>` CLI gives you a clean way to recover any session that's still stuck from before this release.

---

## v0.18.1

v0.18.1 is a polish-and-fix release. The headline changes are a faster manual-verification flow, a new issue-type filter in the board, and a fix for branch-mode upgrades that were silently leaving framework files uncommitted.

## Triage manual-verification checklists in batches

Manual-verification tasks used to walk you through items one at a time. Now the skill re-renders the whole numbered checklist with state markers on every turn, and you can answer in batch through the Other field — `1 pass, 3 defer, 5 skip not applicable` lands four state changes in a single response. The single-item Pass/Fail/Skip/Defer prompt is still there for the items that actually need careful thought.

## Filter the board by issue type

The board TUI gains a new `t` view mode. Hit `t` and you get a multi-select dialog of every issue type — `feature`, `bug`, `refactor`, and the rest — pick the ones you care about, and the board narrows to those. Picks persist per project, and a summary line under the view selector tells you what's active. Pressing `t` again reopens the picker if you want to adjust.

## `ait upgrade` actually upgrades branch-mode setups now

If your project uses a separate `aitask-data` branch (the default for new setups), `ait upgrade` was silently skipping the commit of framework files — so your `.aitask-scripts/` and `.claude/` would update on disk but never make it into git. v0.18.1 fixes the symlink-handling bug at the root and adds a dedicated commit pass for the data branch's `aitasks/metadata/` and `aireviewguides/`.

## Setup tells you when there's no remote

Running `ait setup` on a repo without an `origin` remote used to silently configure branch-tracked features that quietly won't sync anywhere. Now setup pauses, explains exactly which features need a remote to work, and waits for you to acknowledge before continuing. Bonus: lock operations now distinguish "the lock branch doesn't exist on origin" from "I can't reach origin right now," so transient network blips no longer look like missing infrastructure.

---

## v0.18.0

v0.18.0 is the multi-session release. If you keep two or three aitasks projects open in separate tmux sessions, every TUI now sees them all at once instead of pretending only the current session exists.

## Your monitor and minimonitor now see every project at once

Both `ait monitor` and `ait minimonitor` now aggregate code-agent panes across every tmux session rooted in an aitasks project. No more switching sessions just to check whether the other project's agent finished — it's all one list, grouped by session under divider rows. Tap `M` in either TUI to flip back to single-session view if you want it.

## The TUI switcher teleports across sessions

The `j` switcher overlay now lists every aitasks session that's running, not just the one you're attached to. Use `←` / `→` to cycle between them, and pressing `Enter` on a TUI row (or hitting any shortcut key) will teleport tmux to that session automatically. Cross-project navigation without leaving the keyboard.

## `ait install` is now `ait upgrade`

Framework updates are now invoked with `ait upgrade` — the name `install` was lying about what it did once your project was already set up. `ait install` still works but prints a deprecation notice. While renaming, we also fixed a packaging bug that was silently omitting shared skills (`task-workflow`, `ait-git`, `user-file-select`) from release tarballs — a long-standing quiet regression now sealed up.

## Per-project tmux launch memory

The agent launch dialog used to remember the last-used tmux session and window globally — so opening project A after using project B gave you project B's session name pre-filled. Now the memory is per-project, and the dialog respects any `default_tmux_window` the caller passes in.

## `gpt-5.5` for codex and opencode

`gpt-5.5` is selectable for the codex agent directly and for the opencode agent via the OpenAI and OpenCode providers.

---

## v0.17.3

v0.17.3 is a small bug-fix release — three quality-of-life fixes aimed at people running the framework across multiple projects or starting fresh ones.

## Task IDs now start at 1

New projects used to begin at t10 because of a buffer that made room for future renumbering. The buffer is gone: `--peek` returns 1, the first `ait claim` returns 1, and fresh projects finally look the way most people expect them to.

## Tmux targeting no longer confuses sibling projects

If you had two aitasks sessions with overlapping name prefixes (e.g. `myproject` and `myproject-old`), a handful of tmux calls could silently target the wrong one because tmux falls back to prefix matching. Every session-denominated tmux command now goes through a helper that forces exact-match targeting, so cross-project bleed-through is no longer possible.

## `ait setup` adds `__pycache__/` to `.gitignore`

Python cache directories used to show up in `git status` after your first board or TUI run. `ait setup` now appends a `__pycache__/` rule to your project's `.gitignore` (or creates the file if missing) and folds it into the same approval-gated framework commit as the rest of the scaffolding.

---

## v0.17.2

v0.17.2 is mostly a stabilization release — a new way to kick off a brainstorm session, plus a handful of install and test-scaffolding fixes that have been biting people trying out the framework for the first time.

## Import a proposal when you start a brainstorm

When you run `ait brainstorm <N>` on a fresh task, the init modal now gives you three choices: Blank, Import Proposal…, or Cancel. Picking Import opens a markdown file picker (filtered to `.md` / `.markdown`), runs an initializer agent over the file you chose, and applies its output to seed the first brainstorm node — so you can bring an existing design doc or proposal straight into the tree instead of starting from scratch.

## Fresh installs actually work now

`install.sh` was shipping without `project_config.yaml` from the seed files, so the very first `ait` run on a new project could trip over missing config. That's fixed. Framework-update commits also no longer get truncated at the 20th file, which is what a lot of people were hitting after `ait update` against bigger trees.

---

## v0.17.1

v0.17.1 is a small but focused release: you can now bring your own proposal into the brainstorm engine, lazygit gets a dashboard companion, and `ait setup` is noticeably more trustworthy.

## Import proposals straight into brainstorm

If you already have a markdown spec for a feature, you no longer have to paste it into a blank brainstorm session by hand. `ait brainstorm init --proposal-file my_proposal.md` now hands the file to a new initializer agent that reformats it into the brainstorm node format — structured sections, dimension metadata, the whole shape — then auto-starts the crew runner so you can jump straight into the interactive flow.

## Lazygit with a built-in dashboard

Launch `git` from the TUI switcher and you'll get a minimonitor companion pane next to lazygit, just like the `create` and `explore` flows. The cleanup is smart about it: if you split off a shell or a codeagent into the same window, the companion sticks around when lazygit exits so your other work isn't interrupted. Close every pane and the window tears itself down cleanly.

## `ait setup` that tells you what's going on

`ait setup` in a fresh project is now a lot more honest. It installs `AGENTS.md` alongside `CLAUDE.md` and `GEMINI.md`, asks for a default tmux session name, and shows a visible three-line banner before committing framework files (with captured git errors so silent failures no longer hide). Config writes go through symlinks instead of replacing the inode, and every write is verified afterward — so if something didn't land, you get a warning pointing at the problem instead of an empty config field.

---

## v0.17.0

v0.17.0 is a workflow-and-UX release: a brand-new manual-verification loop, a full interactive stats TUI, section-aware navigation across three TUIs, and a ground-up rewrite of the website and landing page.

## Manual verification workflow

Some things you just can't test with a bash assertion — you have to load the TUI, click through it, and see whether the row reorders. v0.17.0 gives those checks a proper home: mark a task with `issue_type: manual_verification`, list the items to verify, and `/aitask-pick` walks you through a Pass / Fail / Skip / Defer loop for each one. Failures become linked bug-fix follow-ups automatically, deferred items carry over into a fresh task on archival, and the archival gate makes sure you can't forget half-finished verification runs.

## Stats TUI

`ait stats --plot` is gone. In its place, `ait stats-tui` (or just `t` from the TUI switcher) gives you twelve live stats panes across Overview, Labels, Agents, and Velocity categories — counters, charts, heatmaps, and ranked tables of your most-run operations. An inline layout picker lets you swap between presets or build your own, and layout choices persist to your user-level config without ever touching the shared project config.

## Shared section viewer across TUIs

The structured section markers that shipped in v0.16.1 for brainstorming are now a first-class navigation tool everywhere. Open a plan in the codebrowser, the Brainstorm node-detail modal, or the board's task-detail screen, and you get a minimap of sections you can click to jump to — or press `V` to pop the whole thing fullscreen with keyboard navigation. Long plans stop being a scroll-wall.

## Docs and website overhaul

The landing page, the overview, the README, and a new 12-page Concepts section have all been rewritten around a single framing: aitasks is an agentic IDE that lives in your terminal. On top of that, a systemic consistency sweep caught drift in the TUIs, Skills, Workflows, Concepts, and Commands sections, and every docs page now carries `maturity` and `depth` badges so you can see at a glance whether a feature is experimental or stable and whether a page is main-concept, intermediate, or advanced.

---

## v0.16.1

v0.16.1 ships with Claude Opus 4.7 as the new default and a pile of codebrowser TUI upgrades. Structured brainstorming lands too — you can now zoom brainstorm operations in on individual sections of a plan.

## Claude Opus 4.7 is now the default

Opus 4.7 is registered in two variants — standard and 1M context — and the 1M variant is the new default for pick, explore, and all brainstorm ops. If you want the standard variant or need to swap models later, the new `aitask-add-model` skill registers models and promotes them to defaults with a single command, including dry-run diffs so you can see exactly what it will change.

## Fuzzy file search in the codebrowser

The codebrowser gets a proper fuzzy file search box — just start typing part of a filename and it scores matches with a recursive multi-alignment algorithm borrowed from toad. No more hunting through the file tree.

## Structured brainstorming

Brainstorm plans and proposals now carry structured section markers, and the brainstorm TUI wizard has a new step that lets you pick which sections to explore, compare, detail, or patch. You can refine one part of a design without re-running the whole agent over the entire document.

## Codebrowser polish

Lots of small-but-nice codebrowser improvements: `c` copies the current file path, `w` toggles word wrap, `R` refreshes the file tree against the current tracked-file set, and the `n` shortcut (create task from selection) now works even with no file selected. Launching `ait create` from the board, codebrowser, or TUI switcher also spawns a minimonitor companion pane next to the new window automatically.

## Killable brainstorm sessions

The brainstorm TUI finally grows a "Delete" operation with a double-confirmation modal. Stale sessions are no longer permanent.

---

## v0.16.0

v0.16.0 is a big one — 46 tasks landed, headlined by interactive agents you can actually watch, a file-references system that ties tasks to specific lines of code, and smarter plan verification that stops duplicated work across agents.

## Interactive agent launch mode

You can now run agentcrew agents in `interactive` mode instead of headless, which means they spawn inside a tmux window you can attach to and watch live. Flip the mode per-agent from the brainstorm wizard, from the Status tab with `e`, or via the new `ait crew setmode` CLI — each agent type ships with a sensible default that you can override in the Settings TUI.

## File references on tasks

Tasks can now carry a `file_references` list pointing at specific files and line ranges like `foo.py:10-20^30-40`. Open the codebrowser, select a block, press `n`, and a new task is created pre-seeded with that exact range. If the new task overlaps with an existing pending task's file refs, you'll get offered an auto-merge. The board's task-detail modal shows these refs as a clickable row that jumps straight back into the codebrowser at the right line.

## Plan verification tracking

Plans now record which agents have verified them against the current codebase. Combined with the new `plan_verification_required` and `plan_verification_stale_after_hours` profile keys, a pick can skip re-verification when another agent validated the plan recently — no more repeating the same work across agent runs.

## ANSI log viewer and task restart

A new `ait crew logview` TUI tails agent log files with ANSI color rendering, live search, and a raw-mode toggle. Press `L` from the brainstorm Status tab or monitor to open it for the focused agent. And when an agent goes off the rails, `R` on an idle pane in `ait monitor` now kills the window and restarts the task cleanly.

## Monitor preview that actually stays put

The monitor preview remembers where you scrolled on each pane, freezes with a `PAUSED` badge when you scroll up from the tail, and re-engages with `t`. Tmux refreshes run async now, so arrow keys don't get eaten by refresh ticks and the whole TUI stays responsive even with a lot of agents.

---

## v0.15.1

A quick follow-up to v0.15.0 with one notable feature, a shim fix, and the final piece of the TUI switcher docs.

## Scroll back through your agent's output

The monitor preview has been pretty tight until now — you saw the last few lines and that was it. v0.15.1 gives it real scrollback: mouse-wheel through the last 200 lines, toggle a scrollbar with `b`, or cycle to an XL preset that fills the whole terminal. It still follows the tail automatically, so you only lose the auto-scroll when you actually scroll up to read something.

## `ait ide` from a fresh shell just works

If you ever ran `ait ide` and got a confusing "shim loop" error, that was the global shim leaking its recursion guard into the project-local `ait` it handed off to. That's fixed now. If you installed the shim before this release, re-run `ait setup` once to regenerate it — then it's a one-time thing and you're done.

## TUI switcher, now documented

The `j` TUI switcher shipped a few versions ago but the docs didn't catch up until now. There's a new overview page listing all the TUIs you can jump between, and the board, codebrowser, and settings how-tos each explain how `j` fits into their workflow. The monitor footer also got a small rename — "Jump TUI" is now "TUI switcher", which is what everyone was calling it anyway.

---

## v0.15.0

v0.15.0 is a big release centered on live tmux monitoring. Running several code agents in parallel is now a first-class experience, with two new monitor TUIs, a one-keystroke TUI switcher, and a single `ait ide` command to get everything going.

## One-step startup with `ait ide`

Spinning up your workspace used to take four steps: open a terminal, `cd` into the project, start tmux, then start the monitor. Now it's just `ait ide`. The new command creates (or attaches to) your project's tmux session and opens a monitor window for you — whether you're running it fresh outside tmux, inside an existing session, or on a second terminal to get another view of the same workspace.

## Live monitor TUI for agent panes

`ait monitor` is a full-screen dashboard showing every tmux code-agent pane in your session with a live preview of what each one is doing. You can forward keystrokes straight into a paused agent, kill a runaway session with `k`, pull up task context with `i`, and flip auto-switch on to let the dashboard follow whichever agent needs attention next. Preview size cycles between S/M/L so you can balance overview and detail.

## Minimonitor side panel

Every time you launch an agent, a compact minimonitor now auto-spawns right beside it as a side panel. It lists the agents running in the same window, and two bindings do the heavy lifting: Tab jumps tmux focus to the agent pane next to you, and Enter sends an Enter keystroke to that sibling pane — perfect for unsticking a paused Claude without leaving your current context.

## Jump anywhere with `j`

A new TUI switcher (`j` from any dashboard) gives you a single keystroke to hop between the board, monitor, codebrowser, settings, brainstorm, and your running code agents. It also picks up your configured git TUI (lazygit, gitui, or tig) automatically, with inline key hints showing you the one-letter shortcut for each destination.

## Pick-as-you-go workflows

Several small-but-nice workflow additions land together: press `n` in the monitor to pick the next ready sibling (or first ready child) and close out the finished agent, press `N` in the board to rename a task with a clean git commit, and hit `(A)gent` in the launch dialog to override the model for a single run without touching your defaults.

---

## v0.14.0

v0.14.0 is a big one — headlined by a full history browser, process monitoring, and a unified tmux-aware launch dialog across all TUIs.

## Browse Your Completed Tasks

The codebrowser now has a history screen (press `h`) that lets you browse every archived task. Search and filter by labels, read the full task details and implementation plans, navigate to sibling tasks, and jump straight to the source files that were changed. It's the fastest way to understand why code looks the way it does.

## Process Monitoring and Hard Kill

Both the AgentCrew dashboard and brainstorm TUI now show running agent processes with resource stats. If an agent is stuck, you can pause, kill, or hard-kill it right from the UI — no more hunting for PIDs in a terminal.

## Unified Launch Dialog with tmux Support

Every agent launch action — pick, create, explain, QA — now goes through a shared dialog with Direct and tmux tabs. Configure your preferred tmux session and split settings once in the new Tmux settings tab, and every launch respects them.

## QA Agent from History

Added `qa` as a first-class codeagent operation. Press `a` in the history screen to launch a QA agent for any completed task, or press `H` in the codebrowser to jump directly from an annotated line to its task history.

## Archives Are Now Zstandard

The entire archive system has been migrated from tar.gz to tar.zst. Compression and decompression are noticeably faster, and all existing tar.gz archives are still readable. Run `ait migrate-archives` to convert your repo.

---

## v0.13.0

v0.13.0 is a big one — the diff viewer is fully operational, brainstorming has its own TUI, and there's a dedicated QA skill so you stop forgetting to write tests.

## Diff Viewer TUI

You can now visually compare implementation plans side-by-side (or interleaved) with `ait diffviewer`. It supports classical line-by-line diffs and structural section-aware diffs, word-level highlighting so you can spot exactly what changed within a line, markdown syntax coloring, and a unified mode for comparing multiple plans at once. There's even a merge screen where you can cherry-pick individual hunks from one plan into another.

## Brainstorm Engine & TUI

The brainstorm system is taking shape. You can initialize a brainstorm session for any task, and it creates a DAG of exploration nodes — each produced by a specialized agent (explorer, comparator, synthesizer, detailer, patcher). The TUI gives you a dashboard with node details, an ASCII art DAG graph, a dimension comparison matrix, and a wizard for launching new brainstorm operations. Still a work in progress, but the foundation is solid.

## Standalone QA Skill

`/aitask-qa` replaces the old embedded test-followup step with something much more capable. It analyzes your changes, identifies test coverage gaps, optionally runs your test suite, and produces a health score. Three tiers — quick, standard, and exhaustive — let you choose how deep to go. It can even create follow-up tasks for missing test coverage automatically.

## Default Execution Profiles

Tired of picking the same profile every time you run `/aitask-pick`? You can now set default profiles per skill in your project config, and override them with `--profile` on any command. The settings TUI has a nice per-skill picker for it too.

## Numbered Archives

The archive system got a major overhaul under the hood. Instead of one giant `old.tar.gz` that grows forever, tasks are now stored in numbered per-range archives. Lookups are O(1) instead of scanning the entire archive, and parallel archiving is safe. The migration is transparent — old archives still work.

---

## v0.12.2

A quick patch release focused on macOS compatibility.

## macOS Compatibility Fix

If you're running aitasks on macOS, the codebrowser Python files now include future annotations so they work correctly with the system Python version. A small fix, but one less thing to worry about when setting up on a Mac.

---

## v0.12.1

A smaller release this time with two quality-of-life improvements — one for the board UI and one under the hood for agent reliability.

## View Implementation Plans Right in the Board

You can now toggle between viewing a task and its implementation plan directly in the TUI board detail screen. Hit `v` to switch views — the border turns orange so you always know which file you're looking at. Editing is context-aware too, so pressing edit while viewing a plan opens the plan file, not the task.

## More Reliable Satisfaction Feedback

The satisfaction feedback procedure that agents follow after completing tasks has been simplified from a 3-file chain down to a single script call with `--agent` and `--cli-id` flags. This means agents are far less likely to get lost or hallucinate script names when wrapping up tasks in long conversations.

---

## v0.12.0

v0.12.0 brings multi-agent orchestration and the ability to undo any task you've ever completed. Two big additions that change how you work with aitasks.

## AgentCrew: Run Multiple Agents in Parallel

You can now decompose a large task into subtasks and have multiple AI agents work on them simultaneously — each in its own git worktree. `ait crew init` sets up the session, `ait crew addwork` assigns subtasks with dependencies, and `ait crew runner` handles the rest: launching agents in the right order, monitoring heartbeats, and managing concurrency. There's even a full TUI dashboard (`ait crew dashboard`) so you can watch everything happen in real time.

## Revert Any Completed Task

Made a change three weeks ago that turned out to be a bad idea? `/aitask-revert` analyzes the commits, files, and code areas touched by any task, then lets you choose a complete or partial revert. For parent tasks with children, you can even pick which child tasks to keep and which to undo. The skill creates a fully-documented revert task with all the context an agent needs to safely roll back the changes.

## Smarter Contribution Management

The contribution workflow got several quality-of-life improvements: `list-issues` and `check-imported` subcommands let you query what's pending and what's already been pulled in, several crash-causing pipefail bugs are fixed, and the website now properly lists all three contribution skills in one place.

## Board TUI: Delete and Archive Obsolete Tasks

The board now has a unified Delete/Archive flow for child tasks that have become obsolete. It checks dependencies, warns you about tasks that depend on the one you're removing, and marks archived tasks as "superseded" so you know why they were shelved.

---

## v0.11.0

v0.11.0 is a big one — it introduces a complete contribution management pipeline, a satisfaction feedback system that tracks how well each AI model performs, and a bunch of board and settings TUI improvements.

## Contribution Pipeline

You can now receive external contributions as GitHub/GitLab/Bitbucket issues and have them automatically checked for overlap with your existing tasks. CI/CD templates handle the automation, and a new contribution review skill walks you through analyzing, merging, and importing contributions. You can even merge multiple related issues into a single task or update an existing task with new contribution content.

## Satisfaction Feedback & Verified Scores

Every task completion can now optionally ask you to rate how well the AI did. These ratings feed into per-model verified scores tracked across time windows — all-time, monthly, and weekly. The settings TUI shows you which models perform best for which operations, and `ait stats` now includes verified model rankings with bar chart visualizations. Over time, this helps you pick the right model for the job.

## Explain Context

The explain feature now gathers historical task context automatically. When you ask for an explanation of a file, it pulls in relevant past tasks and plans to give you richer context about why the code looks the way it does.

## Board TUI Polish

The board got several quality-of-life improvements: a pick command dialog that works cleanly in tmux/terminal multiplexers, keyboard shortcuts on all task detail buttons, and better integration with the pick workflow.

---

## v0.10.0

v0.10.0 brings a major new contribution workflow, smarter commit attribution, and a bunch of quality-of-life improvements across the board.

## Contribute Back Without Forking

The new `/aitask-contribute` command lets you open structured issues against upstream repositories directly from your local changes — no fork required. It works with GitHub, GitLab, and Bitbucket, and even parses contributor metadata when issues are imported back. If your project defines `code_areas.yaml`, you get hierarchical area drill-down to scope your contributions precisely.

## Code Agent Commit Attribution

Commit messages now automatically include accurate code-agent and model attribution. Whether you're using Claude Code, Codex CLI, Gemini CLI, or OpenCode, the `Co-Authored-By` trailer reflects the actual agent and model that wrote the code. You can customize the coauthor email domain via `project_config.yaml`.

## Code Agent and Model Statistics

`ait stats` now tracks which code agents and LLM models are doing the work. You get breakdowns by agent, by model, weekly trend tables, and four new plot histograms. Great for understanding how your team's AI tooling usage evolves over time.

## Code Area Maps

A new `code_areas.yaml` file lets you define your project's structure, and the `/aitask-contribute` workflow now supports both framework-level and project-level contributions with automatic codemap generation and area drill-down.

## Python Codemap Scanner

The codemap scanning engine has been rewritten from bash to Python, bringing better performance and new filtering options like `--include-framework-dirs` and `--ignore-file`.

---

## v0.9.0

v0.9.0 is a big one — full Gemini CLI and OpenCode support, a cleaner directory layout, and several workflow fixes that make multi-agent development smoother.

## Gemini CLI and OpenCode Are First-Class Citizens

Both Gemini CLI and OpenCode now have complete skill and command wrapper sets, matching what Claude Code and Codex CLI already had. Run `ait setup` in any project and the framework automatically detects which agents you have installed, configuring each one with the right skills, permissions, and instructions. Gemini CLI commands also moved to TOML format with automatic permission policy merging, so setup is truly hands-off.

## Model Discovery and Status Tracking

The new `ait opencode-models` command scans your OpenCode installation to discover available models and catalog them with provider-prefixed identifiers. Models can now carry an active/unavailable status — unavailable ones are dimmed in the settings TUI and excluded from the model picker, so you never accidentally select a model that's gone offline.

## Directory Rename: aiscripts to .aitask-scripts

The framework's internal scripts directory has been renamed from `aiscripts/` to `.aitask-scripts/`, keeping implementation details hidden as a dotfile. All documentation, skills, tests, and configs have been updated to match. If you have custom scripts referencing the old path, they'll need a quick update.

## Workflow Fixes

Parent tasks no longer get stuck in a locked state after creating child tasks. Child task planning checkpoints work correctly now, and agent attribution properly records which code agent did the work instead of defaulting to "claude". Small fixes, but they add up to a noticeably smoother experience when working with task hierarchies.

---

## v0.8.3

v0.8.3 is a stability and polish release focused on making Codex CLI integration rock-solid and improving the stats experience.

## Python-powered Stats with Charts

The `ait stats` command has been rewritten in Python, making it noticeably faster. Even better, you can now get visual charts right in your terminal with `--plot` — just enable the optional `plotext` dependency during `ait setup`.

## Codex CLI Gets Proper Guardrails

If you're using Codex CLI with aitasks, interactive skills now properly require plan mode before running. No more cryptic failures when Codex tries to prompt you mid-execution. We also fixed broken YAML in skill definitions and added agent attribution tracking across all remote/async workflows.

## Safer Task Ownership

Before diving into implementation, the workflow now double-checks that you actually own the task — both the status and the assigned_to field. This prevents the frustrating scenario where two agents accidentally work on the same task.

---

## v0.8.2

v0.8.2 brings Codex CLI into the aitasks family — if you use OpenAI's Codex CLI, your aitask skills now work there too.

## Codex CLI Support

All 17 aitask skills now have Codex CLI wrappers. Run them with `$skill-name` syntax just like you would in Claude Code. A shared tool mapping file handles the translation between Claude Code and Codex CLI conventions, so skills behave consistently across both agents.

## Unified Install Pipeline

Running `ait setup` now automatically detects which AI code agents you have installed and configures each one. Codex CLI gets its skills, config, and instructions assembled from a layered seed system. A new marker-based system (`>>>aitasks`/`<<<aitasks`) makes instruction injection idempotent — your existing config files stay clean, and aitasks content is neatly delimited and replaceable.

## macOS Compatibility

A sweep of all 33 bash tests on macOS caught and fixed a real symlink path bug in `ait setup` plus several stale test assertions. If you ran into issues with `ait setup` in macOS temp directories, this release fixes it.

---

## v0.8.1

A small but important patch release fixing usability issues when working without a git remote and cleaning up the auto-update experience.

## Works Without a Remote

You can now use `ait create` and task locking in repositories that don't have a remote configured yet. The task ID counter runs locally and seamlessly upgrades to the remote-based atomic counter the moment you add a remote — no manual steps needed.

## Smarter Update Checks

The auto-update notification no longer suggests "upgrading" to an older version. Version comparisons now use proper semver ordering instead of string comparison, so you'll only see update prompts when there's actually a newer release available.

---

## v0.8.0

v0.8.0 is a big one — three major features that change how you work with aitasks day-to-day, plus a ton of polish across the board.

## Pull Request Import Pipeline

You can now import pull requests directly as aitasks. Run `ait primport` and point it at a PR from GitHub, GitLab, or Bitbucket — it creates a structured task with the PR metadata, contributor info, and a ready-to-go implementation plan. When you're done and archive the task, the original PR gets closed automatically. Contributor attribution flows through to your commits too, so the original author gets credit.

## Settings TUI

No more hand-editing JSON config files. The new `ait settings` command opens a full terminal UI where you can manage profiles, board settings, model configurations, and more — all in one place. It supports layered configuration (project vs. user), export/import, and even shows verification scores for AI models so you know which ones have been tested.

## Code Agent Wrapper

aitasks now works with any AI code agent, not just Claude Code. The new `ait codeagent` command is a universal entry point that routes to whichever agent you've configured — Claude Code, Gemini CLI, Codex CLI, or others. The board and settings TUIs use it automatically, and the new `implemented_with` frontmatter field tracks which agent built each task.

## Board View Modes

The board now has All/Git/Implementing view filters so you can quickly focus on what matters — tasks with uncommitted changes, tasks currently being worked on, or everything at once. The search placeholder even updates to tell you what you're filtering by.

## Refresh Models Skill

Keeping model configs up to date used to be manual. The new `/aitask-refresh-code-models` skill researches the latest AI code agent models via the web and updates your configuration files automatically.

---

## v0.7.1

v0.7.1 introduces the code browser — a brand new TUI for exploring your codebase with full task traceability — along with a batch of board improvements and developer experience fixes.

## Code Browser TUI

The headline feature of this release is a full code browser you can launch with `ait codebrowser`. It gives you a file tree on the left and a syntax-highlighted code viewer on the right, complete with task annotation gutters that show exactly which tasks modified each line. Navigate with keyboard or mouse, select code ranges, and jump straight into the explain skill for deeper analysis.

## Task Annotations at a Glance

Every line of code now carries its history. The code browser's gutter column shows color-coded task IDs so you can instantly see who changed what and why. Click any annotated line and a detail pane shows the full task description and implementation plan — no context switching needed.

## Smarter Explain Runs

Explain runs are now automatically named after their source directory and old runs get cleaned up automatically. No more manually tracking or pruning stale explain data — just run the explain pipeline and the system handles the rest.

## Board Quality-of-Life

The board gets column collapse/expand for less clutter, optimized lock refreshes for snappier interactions, and a smarter unlock flow that resets task status and assignment in one step.

## Multi-Platform Repository Support

Review guide imports and the new repo fetch library now work seamlessly across GitHub, GitLab, and Bitbucket with automatic platform detection — no manual configuration needed.

---

## v0.7.0

v0.7.0 is a big one — this release makes aitasks work everywhere: on macOS, on remote servers, and even in Claude Code Web.

## Run Tasks from Anywhere

The new `/aitask-pickrem` skill lets you run task implementation on remote servers, CI pipelines, or SSH sessions — completely hands-free. No interactive prompts, no fzf, just autonomous execution. Pair it with the new `ait sync` command to keep your task files in sync across machines, and the auto-merge engine handles any YAML frontmatter conflicts automatically.

## Claude Code Web Support

You can now implement tasks directly in Claude Code Web with `/aitask-pickweb`. It stores task data locally to avoid branch conflicts, and when you're done, `/aitask-web-merge` brings everything back to main. The board TUI gained lock/unlock controls so you can reserve tasks before starting a Web session, preventing anyone else from grabbing them.

## Full macOS Compatibility

macOS is now fully supported. We fixed every GNU-specific `sed`, `date`, `grep`, and `mktemp` usage across all scripts and tests. A new `sed_inplace()` helper and portable date wrapper ensure everything works with macOS's BSD tools out of the box. `ait setup` now validates your tool versions too.

## Task Data Branch

Task and plan files can now live on a dedicated git branch, so your task metadata doesn't clutter feature branch diffs. The new `./ait git` command routes task file operations through this branch transparently. All scripts, the board TUI, and skills have been updated to use it.

## Smart Sync with Auto-Merge

The new `ait sync` command handles pulling and pushing task data, and when conflicts arise in YAML frontmatter, the auto-merge engine resolves them intelligently using field-specific rules. Press `S` in the board TUI to sync without leaving the interface.

---

## v0.6.0

aitasks v0.6.0 is out, and it's a feature-packed release. Here are the highlights.

## Code Explanation Skill

Ever wanted to document how a piece of code evolved over time? The new `/aitask-explain` skill generates structured code explanations with evolution tracking. Point it at a file or module, and it produces a narrative that captures not just what the code does, but how it got there — complete with data extraction pipelines and run management for iterative analysis.

## Retroactive Task Wrapping

Already made changes but forgot to create a task first? The `/aitask-wrap` skill has you covered. It looks at your uncommitted work, figures out what you did, and retroactively creates a proper task with an implementation plan — so your project history stays clean even when you code first and organize later.

## Smarter File Selection

A new internal `user-file-select` capability makes it easier for other skills to help you find the right files. It combines keyword search, fuzzy name matching, and functionality-based search, and it's already integrated into both the explain and explore workflows.

## Board Auto-Refresh

The board TUI now refreshes itself periodically, with a new settings screen where you can dial in your preferred interval. No more manual refreshes to see what your teammates (or your other Claude sessions) are up to.

---

## v0.5.0

v0.5.0 is the biggest release yet. Code review capabilities, support for all three major git platforms, and a proper documentation website.

## AI-Powered Code Reviews

The `/aitask-review` skill brings structured code reviews to your workflow. Point it at a file, a directory, or your recent changes, and it runs a review using configurable review guides — sets of rules and patterns that define what to look for. It comes with 9 seed templates out of the box, plus Google style guides for 7 languages. Findings become tasks automatically, so nothing falls through the cracks.

There's a whole ecosystem of supporting skills for managing review guides: `/aitask-reviewguide-classify` for tagging guides with metadata, `/aitask-reviewguide-merge` for combining similar ones, and `/aitask-reviewguide-import` for pulling in guides from external sources.

## GitLab and Bitbucket Support

aitasks is no longer GitHub-only. Full issue import and status update support now works with GitLab and Bitbucket too. The framework auto-detects your platform from the git remote URL, so you don't need to configure anything — just use `ait issue-import` and `ait issue-update` as before.

## Documentation Website

The project now has a proper Hugo/Docsy documentation site with structured navigation, search, and a clean landing page. All the docs that used to live in the README have been reorganized into a proper hierarchy.

## Environment Detection

The review system can now auto-detect C#, Dart, Flutter, iOS, Swift, and Hugo projects, making review guide matching smarter across a wider range of tech stacks.

---

## v0.4.0

v0.4.0 is a big one. It makes getting started easier, adds new ways to investigate your codebase, and gives you more control over how you organize tasks.

## Auto-Bootstrap for New Projects

Setting up aitasks used to require downloading the installer manually. Now just run `ait setup` in any directory and it bootstraps everything automatically — the framework files, the task directory structure, all of it. One command, done.

## Interactive Codebase Exploration

The new `/aitask-explore` skill is for when you have a vague idea and need to figure out the right approach. Point it at a problem area, and it guides you through an interactive investigation of your code — asking follow-up questions, exploring related files, and eventually creating a well-scoped task from what you discover. It even checks for existing tasks that might overlap with your idea and offers to fold them together.

## Task Folding

The `/aitask-fold` skill lets you merge related tasks into a single one. If you've accumulated a few tasks that are really about the same thing, fold them together instead of juggling duplicates. The folded tasks get marked with a `Folded` status and a pointer to the primary task, so you can always trace back to the originals.

## Board Column Customization

The board TUI now lets you add, edit, and delete columns via a command palette (Ctrl+P) or by clicking column headers. Pick from 8 colors to make your board visually distinct.

---

## v0.3.0

aitasks v0.3.0 is all about making multi-device and multi-developer workflows rock-solid.

## Atomic Task IDs

Task IDs used to be assigned locally, which meant two people creating tasks at the same time could end up with the same ID. Not anymore. IDs now come from a shared atomic counter on a separate git branch, so every task gets a unique number no matter how many PCs are creating tasks against the same repo. Tasks start as local drafts and get their final ID when you commit.

## Concurrent Task Locking

Here's a scenario that used to be annoying: you pick a task on your laptop, and your coworker picks the same task on their desktop. With the new lock mechanism, that can't happen. When you pick a task, it acquires a lock using compare-and-swap semantics on a dedicated `aitask-locks` git branch. If someone else already grabbed it, you'll know immediately.

## Framework Updater

Keeping aitasks up to date just got easier. The new `ait install` command updates the framework to the latest (or a specific) version. It also runs a daily background check and quietly notifies you when a newer release is available — no nagging, just a heads-up next time you run a command.

---

## v0.2.0

aitasks v0.2.0 lays the groundwork for a polished developer experience. Here's what's new.

## Comprehensive Documentation

The project now ships with full documentation covering installation, command reference, Claude Code skills, platform support, and the task file format. Whether you're setting up for the first time or looking up a specific command, everything is in one place.

## Execution Profiles

Tired of answering the same workflow prompts every time you pick a task? Execution profiles let you pre-configure your answers. The built-in "fast" profile skips confirmations, uses your stored email, and jumps straight to implementation. Create your own profiles by dropping a YAML file in `aitasks/metadata/profiles/`.

## Automatic Changelog Generation

The new `/aitask-changelog` skill harvests your commit messages and archived plan files to generate release notes automatically. Since `/aitask-pick` already enforces a commit convention with task IDs, the raw material for release notes is created as a side effect of your regular development work. No extra documentation effort needed at release time.

## Board Improvements

The task board TUI gets a quality-of-life improvement: pressing `x` when a child card is focused now collapses back to the parent task, making navigation more intuitive.

---
