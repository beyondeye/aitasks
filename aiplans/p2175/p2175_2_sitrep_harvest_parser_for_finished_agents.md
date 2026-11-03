---
Task: t2175_2_sitrep_harvest_parser_for_finished_agents.md
Parent Task: aitasks/t2175_sitrep_repo_todo_list_steward.md
Sibling Tasks: aitasks/t2175/t2175_3_sitrep_deterministic_refresh_of_todo_part1.md, aitasks/t2175/t2175_4_sitrep_skill_and_window_with_minimonitor.md, aitasks/t2175/t2175_5_sitrep_monitor_key_harvest_and_close.md
Archived Sibling Plans: aiplans/archived/p2175/p2175_1_sitrep_todo_format_locked_writer_backup.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2175_2 — Sitrep harvest parser: items and context entries from finished agents

## Context

Sitrep (t2175) keeps one persisted todo list per repo, so finished or frozen
agent windows can be closed without losing their follow-up information. t2175_1
built the store and its only writer (`.aitask-scripts/aitask_sitrep_todo.sh` +
`lib/sitrep_todo.py`, contract fixture `tests/fixtures/sitrep/`). This task fills
that store from finished agents. It harvests a frozen agent's capture, or the
closing message plus banner that a live agent pipes in at workflow end. It makes
deterministic items and stub context entries and retains every passage a context
entry points at. **No route may delete a frozen agent's text before it has been
harvested.**

Decisions settled with the user (2026-11-02):
- **Ignore rule:** if a repo's `.gitignore` does not cover `.aitask-sitrep/`,
  harvest appends it to that repo's local, never-committed
  `--git-path info/exclude`. Today thinking_backend, thinking_app and aitasks_go
  lack the rule.
- **Prose:** one script **triage item** per wrap-up run (`kind=question`,
  `derived=script`). Its context points at the retained closing passage. The
  sitrep agent (t2175_4) turns that prose into agent-derived action/watch items.
- **Workflow-end trigger:** `workflow-end.md` gains one best-effort step. The
  agent pipes its **closing prose plus the banner** into the harvest just before
  displaying them. A failed harvest still blocks drop.
- **Review round 1** (four concerns, all verified in the code; addressed below):
  - purge bypass
  - worktree roots
  - wrap-up identity
  - caller time budgets
- **Review round 2** (two concerns, both verified):
  - purge's **live** branch (`dead_window` / `dead_pane`) also deletes retained
    text, for example after a liveness-only `restore-confirm` that keeps
    captures. Every purge deletion is now gated.
  - approximate similarity suppressed opposite instructions ("Deploy dev" vs "Do
    not deploy dev" scores 0.97). It is replaced by a confirmed run key and an
    **exact** comparison that ignores rendering only.
- **Review round 3** (two concerns, both verified):
  - removing all whitespace merged `"release candidate.env"` with
    `"releasecandidate.env"`. Normalization is now restricted to the measured
    rendering set.
  - the restore exception made an unchanged capture re-add items after each
    dismissal. Identity no longer depends on item state, and unchanged captures
    short-circuit on the receipt.
- **Review round 4** (verified): the remaining reductions (`**x**`, line-break
  whitespace) still collapse literal commands. Normalization is removed from
  identity entirely. Identity is now an explicit run id (the harvest's
  `HARVEST_RUN:` marker), the archival commit, or byte-exact passage bytes, and
  anything uncertain is added as a linked item.

Verified facts that shape the design:
- Task files do **not** record their creating skill. Created ids come from
  `aitask_create.sh`'s fixed `Created: aitasks/<path>` line. The record's
  `operation` (`pick` / `explore` / `raw`) names the agent kind.
- Real captures show the banner indented by 2 spaces (`  ✔ aitask workflow
  complete — t153 …`, `    outcome: …`), lines padded with trailing spaces,
  sometimes with conversation after the banner, and status-bar lines at the end.
  11 of the 21 captures have a banner. The agent's own text (in the transcript)
  carries the banner inside a ```` ```text ```` fence, with raw markdown prose.
- Trail handles are `art:trail-<id>`. The writer accepts any whitespace-free
  `trail:` pointer.
- **Every route that deletes captures**, from `lib/agent_sessions.py`:
  - `drop` (line ~1446). Reached via `agent_freeze.drop_record` /
    `aitask_frozen.sh drop`, and via the **monitor kill path**
    `monitor_core._drop_session_record` → `aitask_agent_sessions.sh drop`
    (`timeout=10`).
  - **`purge()`** (~1581). Removes a `frozen` record when `capture_ansi` is
    empty or missing, **even if `capture.txt` survives**.
  - `freeze_abort` (~1167). The agent never stopped.
  - verified restore `_drop_captures` (974/1015/1300). The agent is live again,
    holding its conversation.

  The last two lose nothing and stay ungated. This rationale goes in the
  helper's header.
- `frozen_ops.store()` defaults to `timeout=20`.
- **Record roots can be linked worktrees.** `aitask_session_hook.sh` and
  `agent_freeze._walk_up_to_project` choose the nearest ancestor with
  `aitasks/metadata/project_config.yaml`, which inside `aiwork/<task>` is the
  worktree.

## Design

### Units
- **`.aitask-scripts/lib/sitrep_harvest.py`** (stdlib only). Pure parsing,
  identity and item-building functions, plus an orchestrator that calls the
  writer as a subprocess. It imports `sitrep_todo` only to parse Part 2 for
  de-duplication.
- **`.aitask-scripts/aitask_sitrep_harvest.sh`**. The bash entry: argument
  validation, canonical root, the ignore rule, the **harvest mutex**
  (`registry_lock.sh` on `<store>/.harvest.lockd`, separate from the writer's
  `.lockd`, so writer subprocesses never deadlock against it) and receipts. It
  sources `terminal_compat.sh`, `registry_lock.sh`, `atomic_write.sh` and
  `python_resolve.sh` (not `task_utils.sh`, for t2175_1's EXIT-trap reason).
- **`lib/agent_sessions.py`** gains `capture_harvested(rec) -> bool`, the one
  receipt check that both gated routes use.

### One canonical store per repository (concern 2)
`canonical_root(path)` is used by **every** verb (`record`, `all`, `banner`,
`capture`):
- `path` inside a git work tree: the main worktree is the first `worktree` line
  of `git -C <path> worktree list --porcelain`. This works for linked worktrees
  and submodules.
- `path` missing (for example a removed `aiwork/<task>`): try the nearest
  existing ancestor. Accept it **only if** that ancestor's main worktree `M`
  satisfies `path` under `M/aiwork/`. Otherwise `HARVEST_FAILED:root_missing`.
  This never attributes a deleted standalone repo to an enclosing one.
- Not a git work tree: the path itself, with no ignore rule needed.

The store is always `<canonical>/.aitask-sitrep`, and the mutex is that store's.
The original path (worktree) is kept only as an extra lookup location for
task/plan files. `task:`/`plan:` pointers stay relative to the canonical root,
and retained passages live in the canonical store, so removing a worktree
affects nothing.

### Harvest receipts and the destructive-route gate (concerns 1 and 4)
A successful `record` harvest, including `HARVEST_NONE:nothing_found`, writes
`<capture dir>/harvested` atomically, containing `sha256=<hex of capture.txt>` and
`store=<abs store>`. The receipt lives in the capture dir on purpose: it dies
with the capture, and a re-freeze that rewrites `capture.txt` invalidates it
through the sha.

`capture_harvested(rec)` returns true when `capture_txt` is empty or absent
(nothing to lose), or when the receipt exists and its sha matches the current
`capture.txt`. It is a file read plus a hash, a few milliseconds, with no lock
and no subprocess.

The gates sit where captures are deleted, in the library, so every caller is
covered:
- **`drop`** (the library verb behind `aitask_agent_sessions.sh drop`): refuse
  when not harvested. It raises a new `HarvestRequired`, which the wrapper maps
  to `HARVEST_REQUIRED:<id>` with new **exit 9**; nothing is written and the
  capture survives. The `--skip-harvest` flag is the explicit user escape (for
  example a repo deleted for good), documented in the header and the exit table.
- **`purge()`**: **every** removal (any state, any reason: `dead_window`,
  `dead_pane`, `capture_missing`) happens only if `capture_harvested(rec)`.
  - A record with surviving unharvested `capture.txt` is **kept** and reported as
    `KEPT:<id>|unharvested_text`, with no record or capture change.
  - A record without text stays eligible for normal cleanup.
  - A kept record is released by a successful harvest (`record <id>` or `all`,
    which cover every record holding capture text, not just `frozen`), or
    explicitly discarded with `drop <id> --skip-harvest`. The library `drop`
    accepts any state.
  - The verified-restore `_drop_captures` paths (hook / late-hook / rollout ack)
    and `freeze_abort` stay ungated: the conversation is confirmed back, or the
    agent never stopped.

Execution boundaries and budgets:

| route | harvest work | budget |
|---|---|---|
| freeze (`agent_freeze.main`, after printing `FROZEN:` lines) | full `record` harvest, best-effort | 60 s (`AITASK_SITREP_HARVEST_TIMEOUT`); a timeout writes no receipt |
| `drop_record` step **0a** (after the lease claim, **before** the survivor scan and kill) | full harvest; failure or timeout ⇒ release lease, `DROP_REFUSED:<id>\|harvest:<reason>` | 120 s; runs in the detached `run-shell -b` coordinator |
| store `drop` (step 3 of `drop_record`; the monitor kill path) | receipt check only | well inside the 20 s / 10 s caller budgets |
| `purge` | receipt check only | under the store lock, milliseconds |

The harvest's own mutex wait (`AITASK_SITREP_HARVEST_LOCK_TIMEOUT`, default 20 s)
always stays below its caller's timeout.

Cancellation at any point leaves no receipt. That only ever makes the gates
refuse, so the record and capture survive. Writer calls are atomic, and partly
written items are completed idempotently by the next harvest.

The monitor kill path needs no code change (exit 9 is its existing best-effort
non-zero result). The record stays `frozen` with its pane gone, which is
reconcile's benign `KEEP` row. Add a comment there naming the receipt gate.

### Verbs (header documents the wire contract)
- `record <id>`: read via `aitask_agent_sessions.sh show <id> --json`, harvest
  its `capture_txt`, write the receipt.
- `all [--root <path>]`: every record holding capture text (any state), grouped
  by canonical root.
- `banner --task <id> [--skill <name>]`: the workflow-end path. Stdin carries the
  closing prose plus the banner; root is `canonical_root(cwd)`. The agent name
  comes from `$TMUX_PANE`'s window through `lib/tmux_exec.sh`, best-effort.
- `capture --root R [--agent W] [--task T] [--operation op]`: generic stdin,
  for t2175_5's live-pane harvest-and-close.
- Output: `HARVEST_ITEM:<src>|c<N>|added|exists|<kind>|<ref or ->`, and
  `HARVEST_WARN:<src>|<reason>`. The final line is one of
  `HARVESTED:<src>|added=<a>|existing=<e>`,
  `HARVEST_NONE:<src>|no_capture|nothing_found`, or
  `HARVEST_FAILED:<src>|<reason>`.
- Exit codes: 0 / 1 / 2.
- The harvest writes nothing at all (no store dir, no exclude line) when the
  parse finds nothing. It still writes the receipt.

### Parser
- **Banner.** Regexes allow leading whitespace, trailing padding and an optional
  surrounding ```` ```text ```` fence (the piped form). The first line is `✔ aitask
  workflow complete — t<id> <name>` or `■ aitask workflow stopped — t<id> <name>`.
  Field lines are `outcome:` (with ` · pushed:` inline), `follow-ups created:`,
  `reason:` and `next:`. A deeper-indented non-field line continues the previous
  field, which handles terminal wrapping. Every banner in a capture is parsed.
- **Parsed fields:** kind, task, name, outcome (closed vocabulary for Stopped;
  `archived (commit <sha>)` with an optional `· parent archived`, or pickweb's
  alternate line), commit, pushed, follow-ups, reason, next. A banner whose field
  lines are missing gives `HARVEST_WARN:banner_incomplete`, and its follow-ups are
  skipped.
- **Wrap-up passage.**
  - In a capture: scan backwards from the banner to the nearest `●`/`⏺` line that
    is not a tool call (`● Name(`). Stop at a user prompt (`❯ ` / `> `), cap at
    200 lines, and end at the banner's last line.
  - In a pipe: the stdin as-is.
  - The range is **advisory** (a pointer, never evidence), as stated in the
    module header.
- **Created lines.** `Created: aitasks/(t\d+(_\d+)?_[^\s/]+\.md|t\d+/t\d+_\d+_[^\s/]+\.md)`.
- **Trail handles.** `art:trail-[A-Za-z0-9._-]+`.
- **Follow-up tokens.** `t?N[_M]` and `<project>#t?N[_M]`. A malformed token gives
  `HARVEST_WARN:bad_followup`.

### Wrap-up run identity (concern 3, rounds 2–4)
**No text normalization is ever used as proof of identity.** Every rendering
reduction (glyph, `**`, backticks, line-break whitespace, NBSP) can collapse
different literal content: `find . -name '**cache**'` vs `'cache'`, and
newline-separated vs joined shell commands. So two wrap-ups are the same run only
on **explicit identity** or **byte-exact content**.

Identity keys are retained, content-addressed key files `sources/<hex>.txt`, each
pointed at by the triage item's context as a `capture:` source. A run matches
when **any** of its keys is already pointed at by any Part 2 entry, **whatever
that item's state** (open, done, dismissed). Identity never depends on item
disposition, so dismissals stick and an unchanged capture is a no-op.

| key | content | produced by | why it is safe |
|---|---|---|---|
| **run id** | `sitrep wrap-up run v2` / `run=<16 hex>` / `banner=<hex of the canonical banner>` | the `banner` (pipe) verb, which generates `run` randomly and prints `HARVEST_RUN:<16 hex>` as its **first** stdout line | an explicit token, never derived from text |
| **complete** | `sitrep wrap-up complete v1` / `task=t<id>` / `commit=<sha>` | both paths, Complete banners only | the archival commit is unique per run, and both values are grammar-checked tokens (`t\d+(_\d+)?`, hex), not free text |
| **passage** | `sitrep wrap-up passage v1` / `record=<id>` / `sha=<sha256 of the exact retained passage bytes>` / `seq=<k>` | both paths | byte-exact: identical bytes are identical content |

- **Pipe path.** Always a new run: write the run-id key (and the complete key for
  a Complete banner) and add the item. The record id comes from the pane's
  `@aitask_record` stamp (through `lib/tmux_exec.sh`, validated as 8-hex), or is
  `none` headless.
- **Capture path, confirmed.** Claude Code shows a tool call's first output line
  even when it collapses the rest, so the harvest call's `HARVEST_RUN:<id>` line
  appears in the capture just before the closing message. For each banner,
  search back from the start of its closing message to the previous banner (at
  most 80 lines) for that line. The marker **confirms** this banner only if its
  run-id key file exists and its `banner=` field equals this banner's canonical
  banner. The canonical banner is a consistency check here, never the identity
  itself. A marker for a different banner (for example a pipe for a run whose
  banner was never shown) does not confirm, and the capture falls back to the
  unconfirmed path.
- **Capture path, unconfirmed** (no visible marker, or one that does not
  confirm). Match only on the complete key or the byte-exact passage key, where
  `seq=k` for the k-th byte-identical passage of this record's capture.
  Otherwise **add** a new item. That gives at most a discoverable duplicate,
  never a suppression.
- **Unchanged capture short-circuit.** `record` and `all` skip the parse when the
  capture's receipt is valid (same sha, same store), and report
  `HARVEST_NONE:<id>|already_harvested`. `--force` re-parses, which is still
  idempotent through the keys.
- **Links.** Every new triage item's `related:` lists the earlier triage items
  with the same canonical banner, so a duplicate (an unconfirmed capture of a run
  that was also piped) is discoverable from the original.

Consequences:
- Any literal difference in the closing text is a different run unless an
  explicit run id or the archival commit says otherwise. Asterisks, line breaks,
  quoting, case and arguments are all literal. A new run is added even after the
  earlier one was dismissed.
- The same capture harvested again writes nothing, in any item state.
- Piped then captured: Complete runs always match (commit). Stopped runs match
  when the marker line is visible, and otherwise give one linked duplicate.

**Residual, accepted and documented.** After a restore, a re-frozen capture may
replay earlier scrollback.
- Under the same terminal geometry, a replayed passage is byte-identical and is
  skipped by its passage key (correct).
- Under a different geometry, the replay's bytes differ and it is added once as a
  linked duplicate. This only happens once per new capture, because the receipt
  then short-circuits.
- No path can merge two runs whose closing text differs in any byte.

### Items (order: triage, then task items, so `related:` names existing ids)
Per banner run:
1. **Triage item** (unless matched).
   - `kind=question group=now state=open derived=script`, no ref, titled
     `Triage wrap-up of t<id> <name>: turn its closing notes into action/watch items`.
   - Context: background (1–2 sentences: the outcome, and that the prose may name
     actions or things to watch); origin `agent= task= commit= date= skill=
     [pane=]`.
   - Sources: `capture:` (the passage), `capture:` (the canonical banner),
     `capture:` (each identity key it has: run id / complete / passage), and
     `task:`/`plan:` of the origin task when found
     (canonical root first, then the worktree path), `commit:`, and `trail:` for
     every handle in the passage.
2. **Follow-up items** (Complete banners): for each id,
   `add --ref <id> --kind task --group next --context-file -`. `EXISTS:` means
   idempotent, and dismissals stick.
   - Title: `t<id> <name> — follow-up of t<origin>`.
   - State is `open` when the task file is found (active or archived), otherwise
     `unknown`.
   - **Cross-repo** `<p>#t…`: if `ait projects resolve <p>` gives
     `RESOLVED:<path>` and the task file is found there, the state is `open`;
     otherwise `unknown`, with `(cross-repo, unverified)` in the title.
   - Sources: `task:` (local), `capture:` (the banner lines within the passage),
     `commit:`; `related:` is the run's triage item.
3. **The task itself** for a Stopped banner with outcome `in-flight` (group now)
   or `ready`/`split` (group next): a task item `ref=t<id>`.

Per capture:
4. **`Created:` tasks:** a task item `ref=t<id>` in group next, titled
   `… — created by <agent>`. Its capture source is a retained 5-line window.
   Banner follow-ups come first, so a shared id gives `EXISTS:`.
5. **Trail handles outside every wrap-up passage:** one `kind=watch
   group=waiting` item per handle, with a `trail:` pointer (never a copy). It is
   skipped when any Part 2 entry already carries that pointer.

Every `capture:` pointer is `retain`ed first. Values are pre-checked against the
writer's limits (no `|` or newlines, the title limit, a context entry of at most
2000 bytes). A writer exit 3 or 4 gives `HARVEST_FAILED:writer:lock_busy` or
`writer:store_unusable`, and no receipt.

## Implementation steps

1. **`lib/sitrep_harvest.py`.** Implement the parser, `canonical_root`, the run
   identity, the item builders, the orchestrator and the CLI the wrapper calls.
   The writer call is one helper with an absolute `AITASK_SITREP_DIR`, its result
   line parsed per the writer header.
2. **`aitask_sitrep_harvest.sh`.** Implement the verbs, the validation (`..`
   refused before any filesystem access), the canonical root, the ignore rule
   (`git check-ignore -q .aitask-sitrep/todo.md`; append to the absolute
   `--git-path info/exclude`; re-check, and fail with `store_not_ignorable` if it
   is still not ignored), the mutex and the atomic receipt write. The header
   documents the verbs, wire lines, exit codes, the receipt contract, the
   gated/ungated route table with its rationale, and the budgets.
3. **`lib/agent_sessions.py`.** Add `capture_harvested()`, `HarvestRequired` and
   the `drop` gate with `skip_harvest`. Gate **every** `purge()` removal, any
   state and any reason, so unharvested text is kept
   (`KEPT:<id>|unharvested_text`). Thread `--skip-harvest` and exit 9 through the
   `main` drop verb and `aitask_agent_sessions.sh` (usage, header, exit table).
   Check the existing callers of purge's output lines (`monitor` purge consumers,
   `tests/test_monitor_sessions_purge.py`) and extend them for `KEPT:`.
4. **`lib/agent_freeze.py`.**
   - `main`: run the best-effort freeze harvest after printing `FROZEN:` lines.
     It never changes the exit status.
   - `drop_record`: add step 0a, the harvest with its budget. On refusal, release
     the lease and do not kill. Accept `skip_harvest`.
   - `aitask_frozen.sh drop <id> [--skip-harvest]`: relax the arity check.
   - `drop_record`'s store call passes `--skip-harvest` only when the user did.
5. **Workflow-end step** (`.claude/skills/task-workflow/workflow-end.md`).
   - Add a `## Sitrep harvest (best-effort)` section. Before displaying the
     closing message and banner, pipe exactly that text through a quoted heredoc:
     `./.aitask-scripts/aitask_sitrep_harvest.sh banner --task <task_id> --skill <skill_name> <<'SITREP_EOF' … SITREP_EOF`.
     Ignore its output and exit status, never prompt, and the step works headless.
     The agent does not read the output. The harvest prints `HARVEST_RUN:<id>` as
     its first stdout line so that the tool-call display records the run id in the
     pane, and that line is what a later capture uses to confirm the run.
   - Reword "No tool, TUI or gate reads it" to: the sitrep harvest parses it, its
     format is pinned by the contract test, and the workflow never branches on it.
     Avoid phrases the `test_workflow_end_banner_contract.sh` exit scanner matches.
   - Re-render, run `./.aitask-scripts/aitask_skill_verify.sh`, and regenerate any
     changed goldens in the same commit.
6. **Permission touchpoints** for `aitask_sitrep_harvest.sh` (the 5 files in
   `aidocs/framework/aitasks_extension_points.md`), each next to the
   `aitask_shadow_capture.sh` entry.
7. **Fixtures** `tests/fixtures/sitrep_harvest/`, trimmed real captures. Text
   from other projects is replaced by neutral words, keeping layout, padding,
   glyphs, wrapping and status-bar lines:
   - `pick_complete_nofollowups.txt` (t2175_1, this repo)
   - **`pick_complete_piped.txt`**: t2175_1's real final message, extracted once
     from its transcript into the fixture. It is the piped form of the same run;
     runtime code never reads transcripts.
   - **`pick_stopped_marker.txt`**: a stopped run whose capture shows the
     harvest tool call and its `HARVEST_RUN:` first output line before the
     closing message. It is **synthesized** in Claude Code's real tool-call
     layout (`● Bash(…)` / `⎿  …`) and labeled as such in the fixtures README,
     since no real capture has the step yet. `harvest_other_agent_captures`
     replaces it with real captures once they exist.
   - `pick_complete_followups.txt` (wrapped, redacted)
   - `pick_stopped_a.txt` / `pick_stopped_b.txt` (identical banner fields,
     different prose)
   - `explore_created.txt` (redacted)
   - `raw_no_banner.txt`
   - `truncated_top.txt`
   - `truncated_banner.txt`
   - `trail_mention.txt`

   Check them for secrets and host details before committing.
8. **`tests/test_sitrep_harvest.py`** (unittest). Covers:
   - banner parse for every fixture, wrapping and continuation, the fence, the
     pickweb line, multiple banners
   - passage detection and the stop at a user prompt
   - Created/trail/follow-up grammars, including negatives
   - **identity keys:**
     - The complete key comes from grammar-checked tokens only.
     - The passage key is the sha of the exact bytes.
     - The marker search is bounded by the previous banner.
     - A marker whose `banner=` differs does not confirm.
     - Pairs that any rendering reduction would collapse get **distinct** passage
       keys:
       - `find . -name '**cache**'` vs `find . -name 'cache'`
       - `printf one` / `printf two` on two lines vs `printf one printf two` on
         one line
       - `cp "release candidate.env" .env` vs `cp "releasecandidate.env" .env`
       - "Deploy dev." vs "Do not deploy dev."
       - `push main` vs `push dev`
       - `` `x` `` vs `x`
       - NBSP vs space
     - A guard test asserts that no function on the identity path calls a
       normalizer (a mutant re-adding one turns the collision cases red).
   - `canonical_root`: main repo, linked worktree, removed `aiwork/` worktree,
     removed standalone repo (fails), non-git
   - **contract:** extract the `## Complete` / `## Stopped` templates from
     `workflow-end.md`, instantiate, parse, and assert every field and the label
     set
9. **`tests/test_sitrep_harvest.sh`** (bash, `tests/lib/asserts.sh`, file-backed
   counters if any body is in a subshell). Uses a scratch `HOME` and
   `AITASKS_AGENT_SESSIONS_FILE`, scratch git roots, and touches no real
   `~/.config`. Cases:
   - `record` → expected `list --machine` and contexts; the receipt is written.
   - Re-harvest leaves `todo.md` byte-identical.
   - **Piped then captured:**
     - Complete (t2175_1 pair) → one triage item, matched by the complete key.
     - Stopped with a visible marker (`pick_stopped_marker.txt`, piped with that
       run id) → one item.
     - Stopped with no marker → two items linked by `related:`.
   - Stopped run A, dismiss, then stopped run B (same banner, different prose)
     → a new triage item with `related:` to A; A stays dismissed.
     Re-harvesting B adds nothing.
   - **Identical repeats:** two byte-identical stopped wrap-ups in one capture →
     two items (seq 1, 2). Dismiss the first, then pipe an identical third → a new
     item (a fresh run id).
   - **Literal-content collisions** (each pair has the same banner and record,
     with the second as a new capture after the first was harvested and
     dismissed) → two triage items, never a skip:
     - `find . -name '**cache**'` vs `'cache'`
     - newline-separated vs one-line `printf one` / `printf two`
     - `cp "release candidate.env"` vs `cp "releasecandidate.env"`
   - **Restored record, repeated cycles:** a record with `restore_attempts > 0`.
     Harvest, dismiss its triage item, harvest the same capture again → nothing
     added. Repeat three cycles, with `--force` (parse path) and without (receipt
     short-circuit); `todo.md` stays byte-identical after each dismiss. Then a
     re-freeze with a new capture holding one new run → exactly one new item.
   - **Worktree:** a record rooted in a linked worktree plus `banner` run from
     that worktree → one store at the main root. After `git worktree remove`,
     `check-sources` is all `SOURCE_OK` and the passages are readable.
   - Ignore rule: `info/exclude` gains the line and `git status` stays clean.
   - Non-git root; removed standalone root → `HARVEST_FAILED`, no receipt.
   - Nothing found → no store dir, but a receipt.
   - Writer lock held → `writer:lock_busy`, no receipt.
   - Cross-repo follow-up with an unresolved project or a scratch registry.
   - Concurrent `record` + `banner` → one triage item.
   - **Purge:**
     - Frozen record, ANSI capture missing, `capture.txt` holding a wrap-up,
       harvest failed (no receipt) → `purge` keeps the record and the text.
     - **Live branch:** harvest failed, then a liveness-only `restore-confirm`
       (no `--rollout-session`, so captures are kept, state `live`, `ack=liveness`).
       After the window or pane is gone, the `dead_window` and `dead_pane` purges
       both report `KEPT:<id>|unharvested_text`, and the record and text survive.
     - A later `record <id>` harvest lets purge remove it, and so does
       `drop --skip-harvest`.
     - A live record without capture text is still purged as before.
   - **Store drop:** no receipt → exit 9 `HARVEST_REQUIRED`, record and capture
     intact. A stale receipt (`capture.txt` changed) → exit 9. With a receipt, it
     drops. `--skip-harvest` drops.
   - **Acceptance:** harvest → store `drop` (capture dir deleted) →
     `check-sources` all `SOURCE_OK`; `context c<N>` plus the retained file still
     show the passage.
   - `..` root → exit 2 before any filesystem access.
10. **Real-caller tests (concern 4).**
    - In `tests/test_agent_freeze.py`, `drop_record` with mocked `frozen_ops` and
      the real harvest script:
      - harvest refused (mutex held, short `AITASK_SITREP_HARVEST_LOCK_TIMEOUT`)
        → `DROP_REFUSED:…|harvest:`, lease released, no kill, capture intact;
      - harvest exceeding `AITASK_SITREP_HARVEST_TIMEOUT` (paused through a test
        seam `AITASK_SITREP_HARVEST_PAUSE_FIFO`) → refused, no receipt, capture
        intact;
      - success → the store drop passes the receipt gate within its 20 s call.
    - Freeze `main` keeps exit 0 when the harvest fails or times out.
    - A monitor test drives `monitor_core._drop_session_record` (its real 10 s
      subprocess call) on an unharvested record → returns `False` quickly, record
      and capture intact. On a harvested one → `True`.
11. **Regression runs.**
    - `tests/test_frozen_agents_acceptance.sh`, `tests/test_freeze_engine_live.sh`,
      `tests/test_agent_sessions_transitions.py`,
      `tests/test_monitor_sessions_purge.py`, `tests/test_workflow_end_banner_contract.sh`
      and the restore/reopen suites.
    - Fixtures that create frozen records with real `capture.txt` and drop them
      without a freeze now need a receipt. Give them one by running the real
      harvest (scratch roots, no banner ⇒ NONE plus receipt). Use `--skip-harvest`
      only where a case is explicitly about the escape. Never weaken a test's
      assertions.
    - If a live boot budget moves, measure it rather than widening it blindly.
12. Run shellcheck on the new and changed `.sh` files. Send a note to t2175_5:
    - the `capture` verb is its live-pane entry
    - `HARVEST_REQUIRED`/exit 9, `DROP_REFUSED:…|harvest:` and purge's `KEPT:`
      are new results its TUI must show
    - `--skip-harvest` exists
    - the monitor maintenance tick should run `aitask_sitrep_harvest.sh all`,
      which releases records that purge kept

    (t2175_4 also gets the `all`-on-start point.)

    Send a note to t2175_4:
    - the triage item's contract: kind=question, two capture sources (passage and
      banner key), `related:` between runs sharing a banner
    - mark the triage item done after creating the agent-derived items

    Suggest codex/opencode follow-ups if their `workflow-end.md` copies are not
    rendered from the Claude source.

### Post-phase (risk mitigations)
1. [harvest_guard_mutants] Run one mutant per guard, each in a fresh
   `mktemp -d` copy. Each must turn its test red, and the evidence goes in the
   plan's Final Implementation Notes:
   - the store `drop` receipt gate
   - the `purge` keep-unharvested rule, on both the frozen and the live branch
   - the receipt sha check
   - the `drop_record` pre-kill harvest
   - the canonical-root worktree mapping
   - byte-exact identity (mutated four ways: banner-only key, `**`/backtick
     stripping, line-break collapse, whitespace removal), each of which must turn
     a literal-content collision test red
   - the marker's `banner=` consistency check
   - the per-record `seq`
   - the receipt short-circuit
   - the ignore-rule re-check
   - the continuation-line join
   - the banner label set in `workflow-end.md`

## Verification
- `python3 -m unittest tests.test_sitrep_harvest tests.test_agent_freeze`
- `bash tests/test_sitrep_harvest.sh`, `bash tests/test_sitrep_todo.sh`,
  `bash tests/test_workflow_end_banner_contract.sh`,
  `bash tests/test_frozen_agents_acceptance.sh`
- `bash tests/run_all_python_tests.sh`; read only its last line for the verdict
- `./.aitask-scripts/aitask_skill_verify.sh`; shellcheck
- Manual smoke against a **copy** of a real frozen record (`record`, then
  `read`). Never drop real records.

## Post-implementation
Step 9 of the task workflow: commit, archive t2175_2, push via `./ait git`.

## Risk

### Code-health risk: medium
- Gates on the irreversible drop and purge paths in the session-store library: a wrong gate either loses captures or makes records undroppable or unpurgeable · severity: medium · → mitigation: inline post-phase harvest_guard_mutants
- Existing frozen-record fixtures that drop real captures must now carry receipts, a broad test-fixture touch · severity: low · → mitigation: none (they get receipts via the real harvest; assertions are never weakened)
- The `workflow-end.md` edit reaches every workflow exit under every profile and agent · severity: low · → mitigation: none (skill_verify, the banner contract test and the goldens catch drift)
- The harvest writes into other repos (store plus `info/exclude`) · severity: low · → mitigation: none (local-only exclude, re-checked; nothing written when nothing is found)

### Goal-achievement risk: medium
- The passage-start detection and the marker search are tuned on Claude Code's tool-call layout. On codex/opencode captures the passage range may be wrong, or the marker invisible; the result is a linked duplicate triage item, never suppressed advice · severity: medium · → mitigation: t2182
- A Stopped run that was piped but whose marker line is not visible in the capture (an agent other than Claude Code, or a display change) shows twice, as two linked items · severity: low · → mitigation: none (duplicates are the designed uncertain-case outcome; the Complete-run majority match by commit)
- Records with unharvested text are now kept by purge and refused by drop until harvested or explicitly discarded, so they can accumulate if no harvest runs · severity: low · → mitigation: none (freeze harvests automatically; `all` releases them; t2175_4/5 get notes to run `all` on start and on the maintenance tick)
- Claude Code collapses long tool output (`… +N lines`), so a hidden `Created:` line is not harvested · severity: low · → mitigation: none (advisory, documented; banner follow-ups cover pick runs)
- A frozen record that can never be harvested (repo gone) stays until the user passes `--skip-harvest` · severity: low · → mitigation: none (intended fail-closed; the escape is documented and named in the refusal line)

### Planned mitigations
- timing: post-phase | name: harvest_guard_mutants | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — gates on the drop and purge paths | desc: one mutant per guard (receipt gate, purge keep on frozen and live branches, sha check, pre-kill harvest, canonical root, byte-exact identity (4 normalizer mutants), marker banner check, per-record seq, receipt short-circuit, ignore re-check, continuation join, banner labels) must turn its test red
- timing: after | name: harvest_other_agent_captures | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — heuristics tuned on Claude Code rendering | desc: once codex/opencode finished-pick captures exist, add them as fixtures and fix the banner, passage and identity heuristics they break | created: t2182

## Post-Review Changes

### Change Request 1 (2026-11-03)
- **Requested by user:** verify and address three review findings: (1) the
  UIs' 10 s `drop_verdict` grace reported a drop as failed while its
  coordinator was still harvesting (up to 120 s); (2) the plan→wrapper `WORK:`
  line split root and store on `|`, so a root containing `|` harvested into the
  wrong directory; (3) freeze `main` harvested synchronously (up to 60 s) inside
  the monitor's 90 s whole-freeze budget, and a timed-out caller left the
  harvest running untracked.
- **Changes made:** (1) `drop_verdict` treats a record leased by a LIVE owner as
  in progress (every refusal path of `drop_record` releases its lease first),
  up to `DROP_OBSERVE_CEILING` = 180 s, pinned above the 120 s drop harvest
  budget; both UIs use that one interpreter, so neither UI changed. (2) `WORK:`
  carries only the root and the wrapper takes the whole remainder; roots with
  control characters fail closed (`root_unsupported`) before anything is
  created. (3) freeze spawns the harvest detached (`harvest-after-freeze`,
  `start_new_session`, stdio on /dev/null) and returns right after its
  `FROZEN:` lines; the detached verb enforces its own budget with the
  process-group kill. New test seam `AITASK_SITREP_HARVEST_CMD` (helper path).
- **Tests:** a drop observed mid-harvest at 25 s reads "still working" and its
  DROPPED is then observed; a refused drop reads as failed; live / dead /
  ceiling lease cases; a `|` root (capture and record) lands in that exact repo
  and a line-break root is refused; a caller-level subprocess test (2 s slow
  freeze + 30 s slow harvest, stdout read to EOF) returns in < 8 s while the
  detached harvest runs in its own session and is killed by its own 12 s
  budget. Mutants: lease-blind verdict, pipe-split root, inline freeze harvest
  — each RED.
- **Files affected:** `.aitask-scripts/lib/agent_sessions.py`,
  `.aitask-scripts/lib/agent_freeze.py`, `.aitask-scripts/lib/sitrep_harvest.py`,
  `.aitask-scripts/aitask_sitrep_harvest.sh`, `tests/test_agent_freeze.py`,
  `tests/test_frozen_restore_verdict.py`, `tests/test_sitrep_harvest.sh`.

### Change Request 2 (2026-11-03)
- **Requested by user:** the control-character check ran on the supplied root
  only; a symlink resolving to a path with a line break was serialized into
  `WORK:` and harvested into the truncated prefix (reproduced).
- **Changes made:** `_safe_root()` validates the FINAL root at every return of
  `canonical_root` (after realpath and main-worktree resolution) and again in
  `_work()` just before serialization; `_main_worktree` reads
  `git worktree list --porcelain -z`, so a line-break path comes back whole and
  is refused instead of truncated.
- **Tests:** symlinked non-git and git roots resolving to line-break paths fail
  closed with `root_unsupported`, and no store appears under the truncated
  prefix or in the target. The input-only mutant turns them RED (and
  reproduces the truncated-prefix store). e2e 125/125.
- **Files affected:** `.aitask-scripts/lib/sitrep_harvest.py`,
  `tests/test_sitrep_harvest.sh`.

## Final Implementation Notes
- **Actual work done:** New `.aitask-scripts/lib/sitrep_harvest.py` (banner
  grammar, advisory wrap-up passage, `HARVEST_RUN` marker search, Created /
  trail / follow-up grammars, identity keys, canonical root, item builders,
  plan/apply CLI) and `.aitask-scripts/aitask_sitrep_harvest.sh` (verbs
  `record` / `all` / `banner` / `capture`, ignore rule via local
  `info/exclude` with re-check, per-store harvest mutex, receipts). Session
  store: `capture_harvested()`, `HarvestRequired` (exit 9) and the `drop` gate
  with `--skip-harvest`; `purge()` keeps unharvested text on every branch
  (`KEPT:<id>|unharvested_text`, `PURGED:` counts drops only); `drop_verdict`
  reads a live lease as "still working" up to `DROP_OBSERVE_CEILING` (180 s).
  Freeze engine: the post-freeze harvest is DETACHED (`harvest-after-freeze`
  verb, own session, no inherited stdio, own group-killing budget);
  `drop_record` step 0a
  (harvest under the lease, before survivor scan and kill; process-group kill on
  timeout); store exit 9 → `DROP_REFUSED:<id>|harvest:required`;
  `aitask_frozen.sh drop <id> [--skip-harvest]`. `workflow-end.md`: new
  "Sitrep harvest (best-effort)" step + reworded reader rule; all rendered
  copies regenerated (codex/opencode copies render from the Claude source, so
  no port tasks are needed for this step). Five permission touchpoints.
- **Deviations from plan:**
  - Fixtures are **synthetic**, not trimmed real captures: copying real frozen
    captures / a transcript into the repo was blocked (they hold other
    projects' content and conversation text). The fixtures reproduce the layout
    measured on real captures (README in `tests/fixtures/sitrep_harvest/`).
  - The cross-repo fixture project is `xproj`, not `aitasks`: the project
    resolver resolves its own repository's name even with an empty registry.
  - Added test seam `AITASK_SITREP_HARVEST_RUN_ID` (pins the pipe's run id).
  - A record that no longer exists harvests as `HARVEST_NONE:<id>|no_record`
    (nothing to lose), distinguished from an unreadable store (fails closed).
  - An added e2e case: a tracked `.gitignore` negation makes the store
    un-ignorable → `HARVEST_FAILED:store_not_ignorable`, nothing written.
- **Issues encountered:** under a scratch `HOME` the `python3` wrapper finds
  its venv through `$HOME`, so the e2e suite pins `AIT_PYTHON` before switching
  HOME. On a fresh store the writer pauses at `init:after_qa` before
  `write:after_backup`, so a lock-holding writer is started on an initialized
  store.
- **Verification:** `tests/test_sitrep_harvest.sh` 118/118;
  `tests/test_sitrep_harvest.py` 43/43; `tests/test_agent_freeze.py` 207/207;
  `test_frozen_restore_verdict.py` + poll characterization 49/49; session /
  monitor / frozen-agent modules 482/482;
  `test_sitrep_todo.sh` 218/218; banner contract 43/43; task-workflow render
  361/361; skill_verify OK; agent-config seeds 22/22; frozen dry-run 15/15, ide
  frozen offer 97/97, stand-in stamp 28/28. `test_frozen_reopen_live.sh`:
  101/47 both with this change and on a clean HEAD worktree (pre-existing
  `unknown_agent` failures in this environment). `test_frozen_agents_acceptance`,
  `test_freeze_engine_live` and `test_restore_flows_live` refuse to run inside
  tmux by design and were NOT run here.
- **Mutants (harvest_guard_mutants):** 16 mutants, each in a fresh
  `mktemp -d` copy, all RED; unmutated control copy GREEN on all three test
  commands. Store drop receipt gate (e2e 15), purge keep all branches / frozen
  only (e2e 14 frozen + live), receipt sha check (e2e 15 stale), drop_record
  pre-kill harvest (RealHarvestCallerTests), canonical-root worktree map
  (CanonicalRootTests), identity banner-only (e2e 4/6), strip markup / collapse
  line breaks / drop whitespace (collision pairs), marker banner consistency,
  per-record seq (e2e 5), receipt short-circuit (e2e 2), ignore re-check (e2e
  9), continuation join, banner labels in workflow-end.md (contract tests).
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t2175_3 (refresh): harvested task items carry `checked_at` of the harvest
    and `state=unknown` when the task file was not found; triage items are
    `kind=question derived=script` and are not refresh targets.
  - t2175_4 (skill): triage item contract — `kind=question`, capture sources =
    passage, canonical banner, identity keys; `related:` links triage items
    sharing a banner; the skill turns the prose into `--derived agent` items and
    marks the triage item done. Run `aitask_sitrep_harvest.sh all` on start.
  - t2175_5 (monitor key): `capture --root` is the live-pane entry; new drop
    results `HARVEST_REQUIRED` (exit 9), `DROP_REFUSED:<id>|harvest:<reason>`,
    purge `KEPT:<id>|unharvested_text`; `--skip-harvest` is the explicit
    discard; the maintenance tick should run `all` to release kept records.
