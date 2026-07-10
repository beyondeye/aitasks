---
Task: t1120_7_chatlink_docs.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_8_manual_verification_discord_bug_report_channel_integration.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_*_*.md
Worktree: (none — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-07-10 17:39
---

# Plan: t1120_7 — Chatlink user documentation

## Context

All six feature children of t1120 (`t1120_1`..`t1120_6`) have landed: the chat
bug-report intake gateway exists and works, but **no user-facing documentation
describes it anywhere**. A grep of `website/` for `chatlink` / `discord` returns
zero hits in authored content. Chat-platform user docs were deliberately deferred
to this task — `aidocs/chat/discord_bot_setup.md` says so in its own header
("User-facing website docs are derived from this page later ... e.g. the t1120
bug-report channel").

The outcome: a reporter-facing workflow page on the website, plus the one
maintainer-facing runtime doc the landed code still lacks.

This plan was **verified against the landed source**, not the sibling plans. The
verification corrected several assumptions — see "Plan corrections" below.

## Plan corrections (from verifying against landed source)

1. **`~~Final child~~`** — the previous plan text said t1120_7 is the final child
   and the parent archives when it completes. It is **not**: the parent's
   `children_to_implement` is `[t1120_7, t1120_8]`, and `t1120_8` (manual
   verification) remains. The parent will **not** archive on this task.
2. **Slack is out of scope, definitively.** A `slack_adapter.py` exists, but
   `daemon.py:772,789` hard-imports and connects `DiscordAdapter` with no adapter
   selection seam, and the launcher preflight only checks for `discord`
   (`aitask_chatlink.sh:33`). Intake is Discord-only in practice. The page must
   not imply Slack intake works.
3. **`aidocs/chat/chatlink_runtime.md` IS warranted** (plan Step 3 was
   gap-conditional). The relay spool is documented in `qa_relay_protocol.md` and
   the reaper in `chatlink_sandbox.md`, but the **daemon session state machine**
   (`spawning → asking → working → awaiting_payload → done|failed`), the audit
   log, the startup validate-then-serve refusals, the config-key reference, and
   the token file are documented **nowhere**.
4. **TUI enumerations are in scope** per the task's binding conventions
   ("+ chatlink once landed"). Scoped precisely: `chatlink` **is** in the TUI
   switcher registry (`tui_registry.py:24`, key `l`) and its app mixes in
   `SWITCHER_BINDINGS` (`chatlink_app.py:61`), so `j` works — but it is **not**
   part of `ait ide`. So it gets added to the switcher/TUI lists and **not** to
   the `ait ide` homepage prose, `pypy.md`, or `macos.md`.
5. The seed's "gitignored" claim for `chatlink_sessions/` is **true** —
   `.aitask-data/.gitignore:17` ignores it (`aitasks/` is a symlink). Safe to
   state.

## Step 1 — Website workflow page

Create `website/content/docs/workflows/bug-report-intake.md`.

Front matter (matching sibling pages — 5-key set):

```yaml
---
title: "Bug-Report Intake from Chat"
linkTitle: "Bug-Report Intake"
weight: 76
description: "Turn a Discord channel into a bug-report intake: an authorized report opens a thread, a sandboxed agent explores the repo, asks the reporter questions, and files a task"
depth: [intermediate]
---
```

`weight: 76` is an unused slot placing it right after `exploration-driven` (75),
which it is the chat-native cousin of.

Sections (all facts below are source-verified):

- **What it is** — message in the intake channel → thread → sandboxed exploring
  agent → Q&A in-thread → committed aitask, with reactions as status.
- **Prerequisites** —
  - `ait setup --with-chat` (installs the chat SDK tier).
  - Docker installed, **and the sandbox image built manually — it is not
    auto-built**: `docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/`.
    Cross-link `aidocs`-level detail rather than duplicating it.
  - A Discord bot. Condense the setup from `aidocs/chat/discord_bot_setup.md`
    into end-user steps, current-state prose: create the application; enable
    **both** privileged intents (Server Members, Message Content — without the
    latter message text arrives empty); invite with scopes `bot` +
    `applications.commands` and the minimum permission set (View Channels, Send
    Messages, Send Messages in Threads, Create Public/Private Threads, Manage
    Threads, Read Message History, Attach Files, Embed Links, Add Reactions);
    copy the guild + channel IDs via Developer Mode.
- **Configure** — `aitasks/metadata/chatlink_config.yaml` (seeded by `ait setup`).
  A key table: `intake_channel` (provider/workspace_id=guild/conversation_id=channel),
  `allowed_user_ids` / `allowed_role_ids` (**deny-by-default — both empty means
  nobody**), `deny_message_mode` (`ignore` | `ephemeral`), `repo_name` (display
  only), and the ceilings (`max_concurrent_sandboxes` 2, `intake_rate_per_user_per_hour`
  4, `sandbox_memory` 2g, `sandbox_cpus` 2, `sandbox_pids` 512,
  `sandbox_wall_clock_s` 1800) with their clamp ranges. Use an invented project
  name (e.g. `backend`) in examples.
- **Token placement** — the bot token is **not** in the config. It goes in
  `aitasks/metadata/chatlink_sessions/bot_token`, file mode `0600`, parent dir
  `0700`; gitignored. The daemon refuses to start without it.
- **Run** — `ait chatlink --headless` (the gateway daemon) and `ait chatlink`
  (the read-only status TUI: sessions table + audit tail; `r` refresh, `q` quit,
  `j` switcher). Note the startup refusals: missing/invalid config, unset
  `intake_channel`, missing token, unresolvable agent command. Docker missing is
  a warning, not a refusal — launches then fail honestly.
- **The reporter's experience** — post a report in the channel; the bot opens a
  thread named `bug: <first 48 chars>`; the agent asks **at most 3** clarifying
  questions plus **one always-asked final confirmation**, rendered as a select
  menu (with `Prev`/`Next` buttons past 25 options) and/or an **`Answer…`** button
  opening a free-text modal; **only the reporter may answer** (anyone else gets
  an ephemeral "Only the user who opened this bug report can answer."); answered
  questions are disabled and marked `*(answered)*`; unanswered questions time out
  (~9 min) into a documented conservative default. Ends with
  `✅ Task created: **<id>** — <title>` posted to the thread.
- **Reactions-as-status legend** (on the original message): ⏳ working ·
  ❓ awaiting your answer · ✅ task created · ❌ session failed.
- **Limits & safety** — deny-by-default allowlist; the sandboxed agent runs in a
  disposable, committed-HEAD-only workspace copy with no `.git` and no repo write
  access (its only output is a payload the gateway validates fail-closed and
  commits); the bot token and git credentials are never passed into the sandbox;
  per-user rate and concurrency ceilings.
- **Walkthrough: from zero to a filed task** — one continuous narrative for a
  first-time operator, using the invented `backend` project:
  1. `ait setup --with-chat`; build the image.
  2. Create + invite the bot (intents, scopes, permissions); copy guild/channel
     IDs with Developer Mode.
  3. A **complete, copy-pasteable `chatlink_config.yaml`** (uncommented, with
     placeholder snowflake IDs and one allowed user) — the seed ships fully
     commented out, so the first real config is exactly what a new operator is
     missing.
  4. `printf '%s' '<token>' > aitasks/metadata/chatlink_sessions/bot_token && chmod 600 …`
     (show the directory being created `0700`).
  5. `ait chatlink --headless` → expected line
     `chatlink gateway running (headless) — SIGINT/SIGTERM to stop.`
  6. A **sample thread transcript**: reporter's message → ⏳ → the agent's
     clarifying question rendered as a select + `Answer…` → the reporter answers
     → ❓ flips back to ⏳ → `✅ Task created: **t412** — Fix login timeout`.
  7. `ait chatlink` to watch the session table and audit tail.
- **Troubleshooting** — a symptom → cause → fix table, each row sourced from the
  code path that emits it:
  - `no gateway config found …` → run `ait setup`, or point `chatlink.config` in
    `project_config.yaml` elsewhere.
  - `gateway config … is missing or malformed` → invalid YAML (the loader
    fail-closes on a non-mapping / unparseable file; individual *bad values* only
    warn and clamp).
  - `config has no valid intake_channel` → `intake_channel` unset or missing one
    of `provider` / `workspace_id` / `conversation_id`.
  - `no bot token at … (0600)` → token file absent/empty.
  - `could not resolve the explore-relay agent command` → run
    `ait codeagent invoke explore-relay --headless --dry-run` to diagnose.
  - `warning — 'docker' not found` → daemon still serves, but every launch fails;
    install Docker **and** build the image (it is not auto-built).
  - **Bot is in the channel but nothing happens** → the allowlist is
    deny-by-default: both `allowed_user_ids` and `allowed_role_ids` empty means
    nobody may initiate. Also check `deny_message_mode: ephemeral` to make denials
    visible while testing.
  - **Bot reacts but the report looks empty** → the **Message Content** privileged
    intent is off; message events arrive with empty text.
  - **Members/roles don't resolve** → the **Server Members** privileged intent is off.
  - **"Only the user who opened this bug report can answer."** → expected: answers
    are gated to the initiating reporter.
  - **`All bug-report slots are busy` / `Rate limit reached`** → the
    `max_concurrent_sandboxes` and `intake_rate_per_user_per_hour` ceilings.

Body cross-references use `{{< relref "/docs/..." >}}`.

## Step 2 — `_index.md` bullet

Add to the **`## Tasks`** group of `website/content/docs/workflows/_index.md`,
immediately after the `Exploration-Driven` bullet (matching the em-dash format):

```
- [Bug-Report Intake](bug-report-intake/) — Turn a Discord channel into a bug-report intake: a sandboxed agent explores the repo, asks the reporter questions in-thread, and files a task.
```

## Step 3 — TUI enumerations (scoped)

Only where `chatlink` genuinely belongs:

- `website/content/docs/tuis/_index.md` — add a **Chat Link** bullet to
  `## Available TUIs`. Since no per-TUI page is being created, link the name to
  the new workflow page (`{{< relref "/docs/workflows/bug-report-intake" >}}`)
  rather than a nonexistent `chatlink/` page. Also add "Chat Link" to the
  switcher-members sentence ("Monitor, Board, Code Browser, Settings, Stats,
  Syncer" → include Chat Link).
- `website/content/docs/installation/terminal-setup.md` — add `ait chatlink` to
  the `j`-switcher TUI list.

**Not touched** (chatlink is not in `ait ide`, and these lists are about the
`ait ide` session / runtime perf / macOS): `content/_index.md`,
`installation/pypy.md`, `installation/macos.md`.

`diffviewer` is not added anywhere.

## Step 4 — `aidocs/chat/chatlink_runtime.md` (maintainer)

New, tight, no duplication — it **cross-links** the spool layout to
`qa_relay_protocol.md` and the reaper to `chatlink_sandbox.md` instead of
restating them. Owns only what is currently undocumented:

- **Session lifecycle**: states `spawning`, `asking`, `working`,
  `awaiting_payload`, `done`, `failed`; terminal set `{done, failed}`;
  `spawning` is persisted *before* launch so a crash fail-closes on restart
  (`sessions_store.py:35-36`).
- **Startup (validate-then-serve)**: the four hard refusals and the Docker
  warn-not-block (`daemon.py`), plus startup reconciliation fail-closing every
  non-terminal record absent from the live set.
- **Audit log**: `aitasks/metadata/chatlink_sessions/chatlink_audit.log`, no
  rotation; ids truncated, secrets never logged (`audit.py`).
- **Deny / ceiling reasons**: `policy.REASON_*` vs `ceiling_sandboxes` /
  `ceiling_user_rate` (`intake.py`).
- **Config reference** pointer + token file (`0600` / dir `0700`).
- **Status TUI**: read-only, never commands the daemon.
- Module map table (one line per `chatlink/*.py`).

## Verification

- `cd website && hugo build --gc --minify` passes (hugo v0.161.1+extended is
  installed at `/usr/bin/hugo`).
- The new page appears in the `_index.md` Tasks group; every `relref` resolves
  (a bad `relref` fails the Hugo build, so the build is the link check).
- `grep -rin "sister" website/content/docs/workflows/bug-report-intake.md aidocs/chat/chatlink_runtime.md` → empty.
- No real repo names (`beyondeye`, `aitasks_mobile` as an *example*): examples use
  invented placeholders.
- No version-history phrasing ("previously", "used to", "now supports").
- `grep -ri "diffviewer" website/content/docs/tuis/_index.md website/content/docs/installation/terminal-setup.md` → unchanged/absent.
- Spot-check every command and path stated in the page against the source
  (`ait chatlink --headless`, image name `ait-chatlink-agent`, token path/mode,
  the four emoji, the config keys and clamp defaults).
- Every error string quoted in the Troubleshooting table is grep-confirmed to
  exist verbatim in `chatlink/daemon.py` or `chatlink/intake.py`.
- The walkthrough's sample `chatlink_config.yaml` is validated by loading it
  through `chatlink.config.load_config` (a throwaway invocation), so the
  copy-pasteable config is known to parse and not silently clamp.

## Trade-offs and rejected alternatives

- **Rejected: splitting setup onto its own page.** The guide is long, but sibling
  workflow pages (`issue-tracker.md`, `manual-verification.md`) are comparably
  long and self-contained; one page means one place to keep current.
- **Rejected: a full `docs/tuis/chatlink/` per-TUI reference page.** The chatlink
  TUI is a ~180-line read-only status screen (sessions table + audit tail, two
  keys). A dedicated page would be mostly empty and would duplicate the workflow
  page. The `Available TUIs` bullet links to the workflow page instead.
- **Rejected: documenting Slack intake.** The adapter exists but no chatlink code
  path constructs it. Documenting it would be an over-claim.
- **Rejected: folding the runtime doc into `qa_relay_protocol.md`.** That file is
  a pinned *protocol contract* doc (contracts 1-12); daemon lifecycle is a
  different concern and would blur its ownership.
- **Rejected: restating the reaper/spool in the runtime doc.** Cross-link instead
  — three docs restating the same mechanism drift apart.

## Risk

### Code-health risk: low
- Documentation-only change: two new files, three edited prose files, zero source
  or test changes. No runtime path is touched, so there is no regression surface
  and the blast radius is confined to `website/content/` and `aidocs/chat/`. · severity: low · → mitigation: none needed

### Goal-achievement risk: medium
- The page documents a **security-sensitive setup** (bot-token file mode, minimum
  Discord permission set, deny-by-default allowlist). An inaccuracy here does not
  just read badly — it can lead a user into an over-permissioned bot or an
  exposed token. · severity: medium · → mitigation: every security-relevant value is transcribed from the landed source (`paths.py`, `discord_bot_setup.md`, `config.py`) and re-checked in the Verification step above; no value is written from memory or from the sibling plans.
- Chatlink's surface is young and its docs are split across three files; a reader
  could be sent to a doc that does not actually own the answer. · severity: low · → mitigation: the runtime doc's module map and explicit cross-links pin exactly one owner per concern.
- The troubleshooting table quotes daemon error strings verbatim; if those strings
  are reworded later the table silently goes stale (no test binds prose to
  source). · severity: low · → mitigation: accepted — each quoted string is grep-confirmed at write time, and the symptom/fix column stays useful even if the exact wording drifts. A prose-to-source assertion is not worth a test here.

## Step 9 reference

Post-implementation follows task-workflow Step 9. **The parent t1120 does not
archive with this task** — `children_to_implement` is `[t1120_7, t1120_8]`, and
the manual-verification sibling `t1120_8` remains after this one archives.
