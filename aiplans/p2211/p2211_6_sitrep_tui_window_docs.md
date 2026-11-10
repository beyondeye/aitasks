---
Task: t2211_6_sitrep_tui_window_docs.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_7_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-10 17:40
---

# t2211_6 — Docs for the sitrep window, the sitrep TUI and the slim skill

## Context

t2211 split sitrep into a three-pane window: the sitrep agent, the new sitrep
TUI below it, and a minimonitor column. The TUI does the deterministic work
itself (harvest + refresh, dismiss, restore, pick, board/trails jumps, push
command), and it types requests into the agent only on a key press, through
guarded delivery. The skill was slimmed to the agentic work. Siblings _1.._5 and
_8.._10 landed the code. The user kept the docs for this task because the
feature was still in flux, so they now describe the **landed** behaviour, read
from HEAD (82f5351bc), not from the task description.

Verified against HEAD (verify path):
- `aidocs/framework/sitrep.md` already has the window section (layout, four-way
  spawn, the two predicates, races, "The TUI's actions", trail membership) from
  _2/_3/_10. Still missing: a TUI section (views, reload, pointers, requests and
  delivery), the slim skill (L361-395 still describes harvest+refresh at start
  and dismissals), the new test files, and the user-facing page list.
- `aidocs/framework/tmux_gateway.md` already has rows for
  `@aitask_sitrep_tui_root`, `@aitask_dispatch_ack`, `@aitask_board_app` /
  `@aitask_board_focus` and `@aitask_trails_card_focus` / `@aitask_trails_focus`
  (L403-409). **No change.**
- The website pages are stale: `workflows/sitrep.md` and `skills/aitask-sitrep.md`
  still list `>s` / `>r` / `>x`, the two-pane window and the agent's start-up
  harvest. `website/content/docs/tuis/sitrep/` does not exist. The board docs do
  not mention `--focus`, and the trails reference does not mention `--task`.
- None of the target files is dirty in the shared worktree (other sessions'
  uncommitted changes are elsewhere: `commands/_index.md`, `skills/_index.md`,
  …). Those files are not touched.

The fact sheet below comes from the code (`.aitask-scripts/sitrep_tui/*.py`,
`monitor/agent_request_delivery.py`, `board/aitask_board.py` `main`,
`board/trails_app.py` `main`, `board/board_focus_request.py`). Every
user-visible string is copied from there, never paraphrased into a different
claim.

## Reader levels (doc guide `aitasks/metadata/doc_update_guide.md`)

| Page | type | depth |
|---|---|---|
| `tuis/sitrep/_index.md` | overview | `intermediate` |
| `tuis/sitrep/how-to.md` | how-to | `intermediate`: no status lines, no vocabularies, no outcome tables; failure cases in prose |
| `tuis/sitrep/reference.md` | reference | `advanced`: key tables, result codes, refusal vocabulary, timing |
| `workflows/sitrep.md` | how-to | `intermediate` (unchanged) |
| `skills/aitask-sitrep.md` | reference | `intermediate` (unchanged) |

Code mechanism (tmux guards, nonce, `load-buffer -`, digests, workers) goes only
to `aidocs/framework/sitrep.md`.

Term rule: the group is **Now** in the TUI and "Pick now" in the store / the
agent's greeting / the monitor's `sitrep N now`. Each page says "**Now** (Pick
now)" once and then uses one term.

## Steps

### 1. `aidocs/framework/sitrep.md` (framework doc)

- **L13-14 user-facing pages:** add `website/content/docs/tuis/sitrep/`.
- **Components table:** add a row:
  `| TUI | ait sitrep tui → .aitask-scripts/aitask_sitrep_tui.sh | sitrep_tui/ (app, model, widgets, actions, requests, trails); delivery in monitor/agent_request_delivery.py | the list's read views, the deterministic actions, the guarded requests into the agent |`.
  Agent row: change "dismissals" to "answers, Q&A log, and the requests the TUI
  types", because the TUI now dismisses.
- **Move** the two TUI bullets out of "The sitrep window" ("The TUI's actions",
  "Trail membership", L152-186) into the new section below. Leave a one-line
  pointer in the window section ("The TUI itself: see *The sitrep TUI*").
- **The window section, small additions:** the CLI wire lines for the
  four-way spawn (from the `aitask_sitrep.sh` header): `SITREP_SPAWNED:`,
  `SITREP_ADDED_TUI:`, `SITREP_RESPAWNED_AGENT:`, `SITREP_FOCUSED:`,
  `SITREP_FOCUS_FAILED:`, `SITREP_REFUSED:`, `SITREP_WARN:`, mapped onto the
  status column of the existing table.
- **NEW `## The sitrep TUI`** (after the window section), as subsections:
  - *Reads.* `ait sitrep tui [--root]` (`root_arg`; `ROOT_FAILED:` exit 1);
    `<canonical root>/.aitask-sitrep`. One synchronous read at mount, then a
    poll every `RELOAD_INTERVAL` 2.0 s, off the event loop: sha256 of
    `todo.md` + `qa.md`. An unchanged digest re-renders only the age labels; a
    changed one parses the bytes it hashed. The last good parse is kept on
    failure, with the banner lines and `R`.
  - *Views.* The main list (groups from `sitrep_todo` GROUPS, Now/Next/Waiting
    always shown, Recently done/Dismissed behind `d`; fixed column header Item
    / Checked / Pri/Eff / Created / What to do), item details, the source
    viewer, the Q&A log and entry. `NEXT_STEPS` / `classify` in
    `sitrep_tui_model.py` is the single source of the "What to do" / "How"
    texts; `{k_*}` placeholders resolve to the effective (remapped) keys.
    Task fields (priority, effort, status, created) are read from the task
    files and never copied into the store. Clicks only select; Enter opens
    (`widgets.py`).
  - *Pointers.* How the source kinds map to labels and viewer modes: Markdown
    for task/plan/`.md`, raw with line numbers for a `#L` pointer or an error,
    links never followed, KEY receipts hidden, raw input re-hashed, a 256 KiB
    cap, URL shown never opened, `Not followed: <why>` on a refused pointer.
  - *Actions* (the moved bullets, unchanged) plus the label filter (`f` / `F`,
    per-session, never written) and `d`.
  - *Requests into the agent.* `AGENT_REQUESTS` (`sitrep_tui_requests.py`) is
    the one table: key → typed line (`t` `>t c<N>`, `a` `>q c<N> <text>`, `w`
    `>w <theme>`, `T` `>tr c<N>`, `n` `>p`), item fit, and the parity with the
    skill's documented codes (the skill-parity test). Shown only while the agent
    runs; one request at a time. Delivery (`agent_request_delivery.py`) in three
    phases:
    1. readiness: two captures 0.5 s apart, both an empty idle composer, the
       pane not in a mode;
    2. guarded paste: stdin `load-buffer -`, then one `if-shell -F` on run
       identity + `pane_in_mode`, acked through `@aitask_dispatch_ack`
       (`<nonce>:sent|skipped`);
    3. submission: before every Enter the composer's whole payload must equal
       the request (only justified display wraps allowed) and the mode is read
       last; the Enter itself is guarded and acked.
    The result table (`submitted`, `typed_not_submitted[:in_mode|:mode_unreadable]`,
    `refused:<reason>`, `skipped`, `unknown`, where `unknown` never reads as
    sent), and the UI mapping (toast always, a result panel for anything but
    `submitted`). Supported agents are `review_loop.PAYLOAD_GRAMMAR_AGENTS`
    (claude, codex, opencode); any other is refused before typing
    (`refused:not_ready:unknown`, detail `agent:<key>`).
- **`## The skill`** (L361-395): start = `root`, then `list` + `read todo`,
  then the greeting; no harvest or refresh. Writer verbs `add`, `set-state`,
  `situation`, `upsert-context`, `qa`, plus `case review`: no `dismiss`, no
  `restore`. The codes `>t [c<N>]` (bare = whole batch, `c<N>` = that item only),
  `>w [<theme>]`, `>q [c<N>]`, `>tr [c<N>]`, `>p`, `>c`, `>?`. New bullets
  "Requests from the sitrep TUI" (same authority as typed input, still
  confirmed; a fresh `list` / `context` before each, with per-code checks) and
  "Done in the TUI" (the agent names `r` / `x` / `R` instead of acting).
  Guardrail: the TUI may type into the agent at the user's request, never the
  reverse. Keep the triage / trail-watch / push / answers bullets that still hold.
- **`## Tests`:** add rows for `tests/test_sitrep_tui_app.py` (read views),
  `test_sitrep_tui_actions.py` (actions), `test_sitrep_tui_requests.py` (request
  keys, app side), `test_sitrep_request_delivery.py` (with
  `tests/sitrep_request_fixtures.py`) and `test_sitrep_request_delivery_live.sh`
  (delivery, pure and real tmux), `test_sitrep_tui_trails.py` and
  `test_sitrep_tui_trails_actions.py` (trail membership, `z`),
  `test_sitrep_window_hook_live.sh` (the real cleanup hook), and the
  board/trails focus tests (`test_board_focus*.py`,
  `test_board_focus_mailbox_live.py`, `test_trails_focus_writer.py`,
  `test_trails_focus_mailbox_live.py`). One-line "Covers" each, taken from the
  files' docstrings.

### 2. NEW `website/content/docs/tuis/sitrep/_index.md` (overview, intermediate)

Front matter: `title: "Sitrep"`, `linkTitle: "Sitrep"`, `weight: 19`,
`description: "The sitrep window's list view — the repository's todo list, with keys for the routine work and for requests to the sitrep agent"`,
`maturity: [experimental]`, `depth: [intermediate]`.

Body:
- What it is, in the opening sentences: the list view of the [sitrep] workflow,
  in the pane below the sitrep agent. It shows the list and does the
  deterministic work itself (collect and re-check, dismiss, restore, pick, open
  in board or trails, show a push command). For the agent's work (triage,
  questions, situation text, trail refresh, pick advice) it types a request into
  the agent when you press a key.
- The window layout (the ASCII diagram from the framework doc, in user words)
  and the roles of the three panes.
- `> **Customizable keys:**` note (the trails page pattern), scope `sitrep_tui`.
- **Launching:** `ait sitrep` opens the window with the TUI in it, and adds a
  missing TUI under a running agent; `ait sitrep tui` runs it alone (e.g. in a
  plain pane), where requests and the agent's state are unavailable outside
  tmux.
- One paragraph on what it never does: no push, no commit, no task edits; it
  writes the list only through the list's writer; it types only into the sitrep
  agent and only on your key.
- `**Next:** [How-To Guides](how-to/)`.

### 3. NEW `tuis/sitrep/how-to.md` (how-to, intermediate)

`title: "How-To Guides"`, weight 10, description, maturity, depth. Sections:
- **How to Read the List.** The groups (Now (Pick now), Next, Waiting; `d` for
  done/dismissed, the footer reads Show done / Hide done, hidden counts in the
  header); the columns (Checked age, Pri/Eff, Created, What to do); the header
  line (item counts, agent running / not running / unknown, last refresh); the
  situation pane (`s`).
- **How to Open an Item and Its Sources.** Enter opens details: What to do /
  How / About, task fields, Trails, Checked, Outcome, the Context map; the links
  list (Tab moves between text and links; Enter opens a link). The viewer:
  Markdown for task and plan files, `m` for raw with line numbers; a pointer to
  a line opens raw at that line; links inside are never opened. Related /
  Mentioned-by rows jump to other items. `l` opens the Q&A log.
- **How to Collect New Wrap-ups and Re-check the List.** It runs once at start
  (toast) and on `r` (a result panel: what the harvest added, what refresh
  changed). One run at a time.
- **How to Hand Work to the Sitrep Agent.** `t` triage (one item; typing `>t`
  in the agent triages all), `a` ask (one line), `w` situation text, `T` trail
  refresh, `n` pick advice. Keys show only while the agent runs. What you see:
  "Sent to the sitrep agent", or a panel saying why nothing was sent. Nothing is
  typed while the agent is working, is waiting at a dialog, holds text you have
  typed, or is scrolled back. The agent still asks before it writes anything.
  In prose, no codes. Recovery, by what the TUI reported:
  - **Typed but not submitted.** Go to the agent's pane and read its whole
    composer before you press anything. If the pane is scrolled back (in tmux
    copy mode), leave that mode first. Press Enter only when the composer holds
    exactly the request line. When it holds anything else (text you or someone
    else typed before or after it, or a changed line), edit or clear it first:
    the TUI deliberately withheld the Enter because the composer no longer
    matched.
  - **Could not verify what happened.** The request may already have been
    sent. Read the agent's conversation before you press the key again, or the
    agent gets the request twice.
  - **Not sent.** Nothing was submitted. Fix the cause the panel names (wait
    until the agent finishes, answer its dialog, clear or send your own draft,
    leave copy mode), then press the key again. When the panel says the agent
    was replaced before the Enter, the line had already been typed: look at the
    agent's composer first, and clear any leftover line before pressing the key
    again.
- **How to Act on an Item.** `p` pick (pick items; switches to a running
  agent for the task), `b` show in the board, `z` show in trails (picker for
  2+ trails), `P` show and copy a push command (never run), `x` dismiss with
  a reason (the item stays dismissed; when it changed meanwhile you are asked
  again).
- **How to Filter by Label.** `f` picker (Space, Enter/Apply, Clear, Esc), task
  items with any checked label; other items hidden while it is on; `F` clears;
  not saved.
- **How to Recover.** Agent closed: `A` (or `ait sitrep`) restarts it above the
  TUI. Damaged store: the red banner keeps the last good view; `R` restores the
  last good copy and keeps the damaged one.

### 4. NEW `tuis/sitrep/reference.md` (reference, advanced)

`title: "Feature Reference"`, `linkTitle: "Reference"`, weight 20, depth
`[advanced]`. Sections:
- **Keybindings**: the main list (every key from the app's `BINDINGS` +
  `ACTION_BINDINGS` + `AGENT_REQUESTS`, with label and "Context" = its
  `check_action` condition); item details; source viewer; Q&A log / entry; the
  dialogs (dismiss, confirm, push, label filter, ask, trail picker, result).
  Mouse: a click selects, Enter opens.
- **Shortcut scope**: `sitrep_tui`, `sitrep_tui.detail`, `sitrep_tui.viewer`,
  `sitrep_tui.qa`, `sitrep_tui.qa_entry`; the dialogs have none; the pick
  dialog is the shared agent-command screen. A rebind shows in the How texts.
- **Header and columns**: the header fields; the Checked / Pri/Eff / Created
  formats (`—`, `?`, `HH:MM` today, `MM-DD`, `YYYY-MM-DD`, `invalid`,
  `future`); the groups and their order.
- **What to do**: a table of item kinds → What to do / How (from `NEXT_STEPS`,
  with the default keys).
- **Item details**: the fields; the link kinds → label → what Enter opens.
- **Requests**: a table of key → typed line → items it applies to; the ask
  dialog's limits (one line, 300 characters, no control characters, no trailing
  @mention); "shown only while the agent runs; one at a time".
- **Request results**: a table of result → message (the `DeliveryResult.message()`
  strings) → **what was submitted** → what to do, then the refusal reasons,
  which results open the panel, and the supported agents. The "what was
  submitted" column, per code:
  - `submitted`: yes.
  - `typed_not_submitted`: no, but text is in the composer. `composer_changed`
    means it no longer equals the request; `submit_unconfirmed` means the
    Enter's effect was never confirmed. Inspect the whole composer, leave tmux
    mode for `:in_mode`, and submit only an exact request.
  - `refused:*` and `skipped`: nothing submitted. Nothing was typed either,
    **except** `refused:identity_changed`: the line was pasted into the run that
    was then replaced, and the Enter was withheld (`agent_request_delivery.py`
    ~L395-398). Check the new agent's composer before retrying. Otherwise it is
    safe to retry once the cause is gone.
  - `unknown`: **may or may not have been submitted**. It also covers failures
    after the Enter (`enter_unacknowledged`, `post_enter_*`,
    `composer_changed_after_enter`). Read the conversation before retrying.

  A short "Recovering from a result" paragraph under the table repeats the
  how-to's three rules, linked both ways.
- **Action results**: the refresh / dismiss / restore / respawn / board /
  trails / pick messages that matter for troubleshooting (store unusable, item
  changed — press again, not in tmux → the CLI to run, busy store).
- **Timing**: the list re-reads every 2 s (only when a file changed), the agent
  state every 3 s, trail membership every 60 s, plus after a store change and
  when a task's details open.
- **Launch and environment**: `ait sitrep tui [--root <path>]` (a linked
  worktree maps to the main one; an empty value or a `..` segment is refused),
  the store path, `textual` / `pyyaml` missing → `ait setup`; outside tmux, no
  requests, `agent: unknown`, and `A` / `b` / `z` name the command to run.

### 5. `website/content/docs/tuis/_index.md`

Add a bullet after Scratchpad:
`- **[Sitrep](sitrep/)** (ait sitrep tui) — the list view in the sitrep window: the repository's todo list with keys to re-check it, dismiss items, pick or show a task, and hand triage and questions to the sitrep agent. Opened by ait sitrep. Experimental.`

### 6. `website/content/docs/workflows/sitrep.md` (intermediate)

- Intro paragraph 3 (advisory): the agent never types into another pane; the
  sitrep TUI types into the sitrep agent, only when you press one of its
  request keys.
- **Opening sitrep:** three panes (agent top left, the [sitrep TUI] below it,
  a minimonitor column on the right). Running it again focuses the window;
  when the agent or the TUI is missing it adds the missing one back. When the
  agent exits, the TUI and the minimonitor stay, and `A` in the TUI (or
  `ait sitrep`) restarts it.
- **What happens when it starts:** the TUI collects and re-checks (steps 1-2,
  now attributed to the TUI, with `r` to rerun); the agent reads the list and
  greets.
- **The list:** shown in the TUI, with groups Now (Pick now) / Next / Waiting
  and done/dismissed behind `d`; a link to the TUI how-to.
- **Triage:** press `t` on a triage item in the TUI (that item), or type `>t`
  to the agent (every open wrap-up). The rest stays.
- **Output the harvest could not read:** `>t` / `t` on the review item.
- **Asking questions:** `a` in the TUI on an item, or ask the agent directly.
- **Dismissing items:** `x` in the TUI, with a reason. The agent no longer
  dismisses; it names the key.
- **Shortcodes table:** `>t [c<N>]`, `>w [<theme>]`, `>q [c<N>]`, `>tr [c<N>]`,
  `>p`, `>c`, `>?`, plus a column naming the TUI key that sends each
  (`t`, `w`, `a`, `T`, `n`, —, —).
- **Where the list lives:** damage → the TUI's banner and `R`.
- **See also:** add the Sitrep TUI pages.

### 7. `website/content/docs/skills/aitask-sitrep.md` (intermediate)

- The intro advisory sentence and the Usage paragraph: the three-pane window.
- **Step-by-Step:** 1 root; 2 read the list (the TUI collects and re-checks,
  not the agent); 3 greet.
- **Capabilities:** the slim table (the codes above; `>t` bare vs `c<N>`).
- NEW **Requests from the sitrep TUI:** the five lines it may type; same
  authority as typed input; the agent re-reads the list first and still asks
  before writing.
- NEW **Done in the sitrep TUI:** show, refresh, dismiss, restore are TUI keys
  `r` / `x` / `R`; asked for one, the agent names the key.
- **What it never does:** keep "type into another agent's pane", and add that
  the sitrep TUI types into the sitrep agent only at your request, and refuses
  when the agent is at a dialog, holds a draft, is working, or its pane is
  scrolled back (copy mode). Keep "Dismiss an item on its own" → "Dismiss or
  restore anything: those are the TUI's keys, pressed by you".

### 8. Board and trails launch options

- `tuis/board/_index.md` "Launching the Board": one sentence plus a code line,
  `ait board --focus <id>` (`12`, `t12`, `12_3`) to open with that card
  selected; link to the reference.
- `tuis/board/reference.md`: a new `### Command-Line Options` before
  "Environment Variables": `--focus <id>`; an invalid id is refused; a child's
  parent is expanded. A running board in the session takes the request instead
  (this is what the sitrep TUI's `b` uses): it is held while a dialog is open
  ("t<id> will be shown when this dialog closes"); "t<id> is archived — it is
  not on the board", "t<id> not found", and "t<id> is not visible in the current
  view (a filter, a collapsed column or a trail view hides it)".
- `tuis/trails/reference.md` launch table: add `ait trails --trail <handle> --task <id>`
  (`--task` needs `--trail`; `12`, `t12`, `12_3`). It focuses that member's
  card; the warnings are "t<id> is not in trail <handle> (any more) — trail
  opened" and "… is in trail <handle> but its card is not visible". Add one
  clause to the `_index.md` Launching bullet for `--trail`.

All internal links are `{{< relref "/docs/..." >}}`; links within the new
section are relative (`how-to/`, `../reference/#…`), as on the trails pages.
Current state only, no history, no "previously".

### Post-phase (risk mitigations)

1. [doc_key_crosscheck] In the scratchpad (never committed), write a script
   run with `~/.aitask/venv/bin/python` and `sys.path` set to
   `.aitask-scripts/sitrep_tui` and `.aitask-scripts`. It imports
   `sitrep_tui_app`, `sitrep_tui_actions` and `sitrep_tui_requests`. It builds
   the expected set **per screen** as `(screen, key, action)` triples, never a
   pooled key list:
   - *main list* = `SitrepTuiApp.BINDINGS` (with `ACTION_BINDINGS` and
     `AGENT_REQUESTS` expanded);
   - *item details* = `ItemDetailScreen.BINDINGS` **plus** the app-level
     actions `check_action` (`sitrep_tui_app.py` ~L989-1026) also enables on
     the details screen. That set comes from a small table in the script, which
     cites the `check_action` lines: `harvest_refresh`, the item actions
     `dismiss_item` / `pick_task` / `open_in_board` / `open_in_trails` /
     `show_push`, and the five request actions. It must not contain the
     main-list-only `toggle_closed`, `qa_log`, `toggle_situation`,
     `filter_labels`, `clear_label_filter`, `restore_store`, `respawn_agent`,
     `open_item`;
   - *source viewer*, *Q&A log*, *Q&A entry* = each screen's own `BINDINGS`.
   It parses each per-screen keybinding table of `tuis/sitrep/reference.md`
   (the section heading names the screen) into the same triples, with the
   action matched through the row's footer label. It fails on any triple that
   one side has and the other lacks (`j` and `?` count on the main list as the
   shared actions; a hidden `show=False` binding such as `shift+tab` is allowed
   to be undocumented). Manual check alongside it: each documented "Context"
   condition (item fit, agent running, store error, filter active) is compared
   by hand with `check_action` and `actions.py` ~L620-644 (item fit) and
   `requests.py` (request fit). The result goes in the Final Implementation
   Notes as one line per key. It also extracts
   every double-quoted message on the three new pages, the workflow page and
   the skill page, and greps each in `.aitask-scripts/sitrep_tui/`,
   `monitor/agent_request_delivery.py`, `board/` and `lib/sitrep_cli.py`. A
   message that is not found is fixed, or marked in the page as a pattern (with
   `<id>`-style placeholders matched as wildcards). Fix every mismatch, then
   rerun until it is clean. Negative controls, each on a scratch copy of the
   reference page, each of which must be reported:
   (a) a deleted main-list row;
   (b) `f` moved from the main-list table into the details table;
   (c) `r` dropped from the details table, so it is documented on the main
       list only.
2. [doc_review_pass] Run the `/aitask-docs-review` skill on
   `tuis/sitrep/_index.md`, `how-to.md`, `reference.md`, `workflows/sitrep.md`
   and `skills/aitask-sitrep.md`. Fix every finding about reader level (each
   page against its `depth`) and prose rules. Record anything deliberately left
   as-is, with the reason, in the plan's Final Implementation Notes.

### 9. Verify

- `cd website && hugo build --gc --minify && python3 check_links.py --build`
  (mandatory; both must pass).
- `python3 check_link_relevance.py`: offer it, for the new and retargeted links.
- `git status` / `git diff --stat` show only the 11 files above:
  `aidocs/framework/sitrep.md`; the 3 new `tuis/sitrep/` pages; edits to
  `workflows/sitrep.md`, `skills/aitask-sitrep.md`, `tuis/_index.md`,
  `tuis/board/{_index,reference}.md` and `tuis/trails/{_index,reference}.md`.

### 10. Commit and Step 9

One code commit with named paths only (the shared worktree holds other
sessions' changes):
`git commit -m "documentation: Document the sitrep window, TUI and slim skill (t2211_6)" -- <the files>`.
Then Step 9 (Post-Implementation): plan notes, archival of t2211_6 (its sibling
t2211_7, the manual verification, stays pending).

## Verification

- Hugo build and `check_links.py --build` pass.
- The new TUI pages are reachable from `tuis/_index.md`, and the workflow page
  and skill page link to them.
- Every `(screen, key, action)` on the reference page matches the code's
  bindings and `check_action` availability, and vice versa (post-phase check,
  with its three negative controls).
- The how-to's recovery advice never says to press Enter without first reading
  the whole composer, and it treats "could not verify" as possibly sent.
- No page still lists `>s`, `>r`, `>x` as skill codes, or says the agent
  harvests at start: `grep -nE '>(s|r|x)\b'` over
  `website/content/docs/workflows/sitrep.md` and
  `website/content/docs/skills/aitask-sitrep.md` prints nothing.

## Risk

### Code-health risk: low
- Docs only, no code; the one hazard is the shared dirty worktree: a commit without a pathspec would sweep in other sessions' staged changes · severity: low · → mitigation: none (step 10 commits named paths only)
- A hand-written relative link or a dead `#fragment` builds green · severity: low · → mitigation: none (`check_links.py --build` is mandatory in step 9)

### Goal-achievement risk: low
- The documented keys, conditions and on-screen strings could drift from the code: the surface is large (~4000 lines across six TUI modules plus delivery), and the fact sheet was gathered by reading, not by running · severity: low (residual — addressed by inline post-phase doc_key_crosscheck) · → mitigation: inline post-phase doc_key_crosscheck
- The three new pages could put detail at the wrong reader level (vocabularies on the intermediate how-to, mechanism on the website) or break the guide's prose rules · severity: low (residual — addressed by inline post-phase doc_review_pass) · → mitigation: inline post-phase doc_review_pass
- The user called the feature "still in flux": later TUI changes will stale these pages · severity: low · → mitigation: none (the framework doc names the single sources `NEXT_STEPS` and `AGENT_REQUESTS`)

### Planned mitigations
- timing: post-phase | name: doc_key_crosscheck | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — documented keys/strings drift from the code | desc: scratch script cross-checking the reference's per-screen (screen, key, action) tables against the bindings and check_action availability both ways, plus a manual context-condition check and every quoted message against the source, with three negative controls
- timing: post-phase | name: doc_review_pass | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — wrong reader level / prose-rule breaks | desc: run /aitask-docs-review on the five website pages and fix the findings before committing
