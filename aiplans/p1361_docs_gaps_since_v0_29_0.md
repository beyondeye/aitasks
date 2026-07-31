---
Task: t1361_docs_gaps_since_v0_29_0.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1361 — Documentation gaps since v0.29.0

## Context

`/aitask-docs-gap` analysed the v0.29.0..HEAD release window (43 task-tagged
tasks: 18 already documented, 21 not doc-relevant) and found **4 shipped
features with no user-facing documentation**. Each is a real discoverability
hole: a user hitting the symptom the feature exists to fix has nothing on the
site to send them to the fix.

Scope decided with the user: **one task covering all four gaps**, with the gates
CLI getting its **own new page** under Command Reference.

This is a documentation-only change. No framework code is modified.

Doc rules that govern the prose (`aidocs/framework/documentation_conventions.md`):
current-state-only (no "previously…" / "until that ships"), and genericize the
supported-agent set in blurb prose.

---

## Gap 1 — `ait gate` / `ait gates` CLI (t635_34)

**Problem:** the site has **zero** documentation for the gates CLI. Grep over
`website/content` finds no hit for `ait gates`, `sync-registry`, `gates run`,
`gates status`, `gates list`, `gate log`, or `gate fail`. The only mentions of
`ait gate` anywhere are one line in `skills/aitask-resume.md:59` and one blog
paragraph. Meanwhile the gate *data model* is already fully documented in
`development/task-format.md:60-65` — so only the CLI is missing.

The motivating symptom is the claim-time stderr warning
(`.aitask-scripts/aitask_gate.sh:696`), which names a command the site never
explains:

```
Warning: materialize-active: active gate 'risk_evaluated' has no verifier configured in
aitasks/metadata/gates.yaml — it will block archival. Run `ait gates sync-registry` to
reconcile the registry.
```

### 1a. New page `website/content/docs/commands/gates.md`

Front matter (matching `commands/lock.md` / `crew.md` conventions; weight 38
slots it between `lock` 36 and `issue-integration` 40):

```
---
title: "Gates"
linkTitle: "Gates"
weight: 38
description: "ait gates and ait gate — run, inspect, sign off, and reconcile task verification gates"
depth: [advanced]
---
```

Page structure — follow `crew.md`'s multi-verb shape (one `## ait <verb>` H2 per
verb, bash fence + option table each) and `sync.md`'s `| Code | Meaning |` table
for exit codes:

1. **Intro** — what a gate is in one paragraph, linking to the existing
   [`gates` / `active_gates` field definitions](../../development/task-format/)
   rather than restating them. State the split: `ait gates` (plural) operates on
   a task's whole gate set; `ait gate` (singular) acts on one named gate.
2. `## ait gates run` — dispatches unlocked machine-gate verifiers within their
   retry budgets, observes human gates, stops. Flags `--gate <name>`, `--dry-run`.
   Document the output lines users actually see: `No gates declared; nothing to
   do.`, `All gates satisfied. Task ready for archive (suggest status: Done — not
   auto-applied).`, `  <gate>: <status> (attempt <n>)`, and the `blocked:` family
   — especially **`blocked: no verifier configured (deferred)`**, the runtime twin
   of the claim-time warning. **Exit 0 for every completed run** (a `fail` is a
   recorded result, not a process error).
3. `## ait gates list` / `## ait gates status` / `## ait gates unlocked` — short
   section; `list` = declared intent, `status` = derived per-gate state
   (last-run-wins), `unlocked` = runnable right now.
4. `## ait gate pass` — **the human's sign-off tool.** Writes a witness at the
   gate's `signal_target` and records the pass through the orchestrator.
   Document the three refusals verbatim in prose: unknown gate, machine gate
   (`gate pass refuses machine gate … run 'ait gates run'`), and a human gate
   with no file-touch signal (attended-only checkpoint, e.g. `plan_approved`).
   Note signatures are **code-bound** — a witness stamped against different code
   re-pends. Do **not** describe agent self-signing as an option.
5. `## ait gate fail` / `## ait gate log` — `fail <task-id> <gate> [--reason …]`;
   `log` prints the latest run's sidecar and **exits 0 even when absent**.
6. `## ait gates sync-registry` — the centrepiece. Cover:
   - What it reconciles: the project's `aitasks/metadata/gates.yaml` against the
     framework's `gates_reference.yaml`.
   - **Only fills textually-absent keys**; a key present with a different value
     is *reported, never overwritten*. Comments and formatting are preserved.
   - `--dry-run` (preview), `--registry <file>`, `--reference <file>`, and the
     `AIT_GATES_REFERENCE` env override.
   - Report vocabulary as a `| Line | Meaning |` table: `FILLED:<gate>.<key>=<value>`,
     `NEW_GATE:<gate>`, `CONFLICT:<gate>.<key>:<project>|<reference>`,
     `PROFILE_UNKNOWN:<profile>.<key>:<gate>` (report-only — profiles are never
     edited), `NOOP`.
   - **Commits nothing** — the registry change stays review-worthy; a stderr hint
     names `./ait git add aitasks/metadata/gates.yaml`, and fires only when the
     file actually changed.
   - A caution that filling `timeout_seconds` gives a previously unbounded gate a
     wall-clock ceiling and filling `blocks_dependents: true` makes it hold
     dependent tasks — both visible as `FILLED:` lines, so use `--dry-run` first.
   - Exit codes table: `0` every completed run (NOOP / applied / conflicts),
     `3` could not read (must never render as NOOP), `4` parsed but untrustworthy
     to edit, `5` another sync holds the registry lock, `6` post-write
     self-verification mismatch.
   - **`NOOP` means "verified in sync"**, never "could not read" — that
     distinction is the whole point of the command.
7. `## When to run sync-registry` — the symptom→fix passage: the claim-time
   warning above, or `blocked: no verifier configured (deferred)` from
   `ait gates run`, or a task that will not archive. Quote the warning verbatim.
8. Footer `---` + `**Next:** [Issue Integration & Utilities]({{< relref … >}})`
   following the house pattern.

**Scope guard:** document only the verbs exposed through the `ait` dispatcher.
The workflow seams reachable only via `./.aitask-scripts/aitask_gate.sh`
(`materialize-active`, `resume-point`, `should-self-record`, `archive-ready`,
`procedure-gates`, `begin-procedure`, …) are agent-facing and stay undocumented.
`gate append` is exposed but labelled "used by verifiers" — mention it once as
such, do not give it a full section.

### 1b. `website/content/docs/commands/_index.md`

Add a `### Gates` group after **Agent Orchestration** (~line 54) with rows for
`ait gates run`, `ait gates status`, `ait gates sync-registry`, and `ait gate
pass`, each linking into `gates/#…`. Add 3-4 aligned lines to the
`## Usage Examples` block (`ait gates run 42`, `ait gates sync-registry --dry-run`,
`ait gate pass 42 review_approved`).

### 1c. `website/content/docs/workflows/risk-evaluation.md`

The page explains risk evaluation but never names the `risk_evaluated` gate that
verifies its output — and that gate is exactly the one whose stale registry
entry motivated `sync-registry`. Add a short paragraph at the end of
`## Enabling Risk Evaluation` connecting the two, and a `## See Also` bullet
linking to the new gates page.

### 1d. `website/content/docs/skills/aitask-resume.md` (correctness fix)

Lines 57-58 currently read "Automated per-gate verifier execution is handled by
the gate orchestrator; **until that ships**, `--gate` reports state only and runs
no verifier." The orchestrator **has** shipped as `ait gates run`. Rewrite to
current-state-only: `--gate` reports recorded state and runs no verifier; to run
verifiers use `ait gates run`. Link the new page.

*(Explicit scope note: this is a correction adjacent to Gap 1, not in the
docs-gap task text. Included because the new page would directly contradict it.)*

---

## Gap 2 — board By-Trail view (t1268)

**Problem:** By-Trail is **entirely absent from `/docs`** — the only site mention
is one blog line. The reference page's View Selector block and base-filter table
stop at By-Topic even though `z By-Trail` has shipped, so the documented key list
is actively wrong. On top of that the t1268 refresh ladder (`r`/`d`/`R`), `S`,
and the hidden `C` are undocumented.

The real rendered selector (generated from `ViewSelector.BASES`,
`.aitask-scripts/board/aitask_board.py:1522-1529`) is:

```
[a All | l Locked | f Free | i In-Flight | y By-Topic | z By-Trail]   g Git   t Type
```

### 2a. `website/content/docs/tuis/board/reference.md`

- **Line 134** — update the render block to the real string above.
- **Base-filter table (141-147)** — add a `By-Trail | z` row after By-Topic:
  trail members laid out as **wave columns** (`W1 · …`), each card showing its
  classification glyph, confidence, and any drift marker; `enter` opens the full
  narrative.
- **New `#### By-Trail` subsection** after the By-Topic prose (~line 170),
  carrying: a one-sentence definition of an implementation trail (a durable,
  wave-structured, evidence-backed task-sequencing artifact created by
  `/aitask-trail`), the refresh ladder table, `S`, and drift markers.

  Refresh ladder as a `| Key | Does | Cost |` table:

  | `r` | Re-reads task files from disk and re-projects the cached trail | instant; no subprocess |
  | `d` | Re-fetches the stored artifact and re-runs the read-only drift check | ~0.5 s; never writes the artifact |
  | `R` | Launches `/aitask-trail --refresh` to re-author the trail | minutes; agent-authored |
  | `s` | Choose which trail the view shows | discovery rescan |
  | `S` | `ait sync`, then the local recompute | full remote sync |

  Explain **why `S` matters**: task data lives on the `aitask-data` branch, so a
  status changed by another machine or a remote agent only reaches this checkout
  via a sync. Explain the `R` follow-up behaviour in user terms: after a
  confirmed refresh the view watches the stored artifact and reloads on its own
  when a new version lands ("Trail artifact updated — reloading"), giving up
  after roughly half an hour.

  **Drift markers:** a card whose recorded snapshot no longer matches live task
  state shows an amber `⚠ <code>: <detail>` line (up to two reasons, `(+N more)`
  beyond that; full list in the detail screen). Name the user-meaningful codes —
  `status_changed`, `task_completed`, `task_archived`, `task_folded`,
  `task_deleted`, `dependency_changed`, `gate_state_changed`, `plan_changed` —
  without reproducing the internal trigger matrix.
- **Keyboard tables** — Board Navigation (14-34) gains `z`; add `d`, `R`, `S` as
  By-Trail-scoped rows. The `C` row (line 49) and the `w` row (line 51, "hidden
  in In-Flight and By-Topic views") must both name By-Trail. Same for the
  work-report `W` line in how-to.md:238.
- Note the **footer relabels per view**: in By-Trail the footer reads
  `r Refresh  R Agent Refresh  d Freshness  s Select Trail  S Sync`.
- `C` is **hidden** in By-Trail — a trail is a reading projection, not an
  ownership boundary, and "commit all" is repo-wide.

### 2b. `website/content/docs/tuis/board/how-to.md`

Add a `**By-Trail view (`z`):**` passage at ~line 108 (after the In-Flight block,
before "Combining with text search"), mirroring the existing In-Flight passage
shape: how to open a trail (`s`), how to keep it current (the ladder), and what a
drift marker is telling you. Add a cross-note in `### How to Sync with Remote`
(307-335) that By-Trail's sync key is `S`.

### 2c. `website/content/docs/tuis/board/_index.md`

Lines 33 and 51 list base views as only `a / l / f / i`. Extend both to include
By-Topic **and** By-Trail.

*(Explicit scope note: By-Topic is missing from `_index.md` and `how-to.md`
independently of this release window. Adding it alongside By-Trail rather than
knowingly leaving a wrong list — a two-word change in each spot.)*

**No trails page exists.** There is no `/docs` page for implementation trails,
`/aitask-trail`, or `ait artifact` — nothing to cross-link to. This plan carries a
one-sentence inline definition instead; a dedicated trails page is out of scope
and will be offered as a follow-up task at Step 8.

---

## Gap 3 — COMPLETED agent state in monitor / minimonitor (t1322)

**Problem:** the docs describe a **two-state** world (green = active, yellow =
idle). The shipped ladder has **four** states — `PROMPT > COMPLETED > IDLE >
active` (`.aitask-scripts/monitor/monitor_shared.py:94-113`) — so a user seeing a
blue `DONE 42s` badge or a magenta `PROMPT` badge finds nothing on the site.
The monitor how-to has no status list at all; the minimonitor how-to has one
that is actively wrong.

User-facing meaning to document: **"done" is a property of the pane's task, not
its terminal** — the task reads `status: Done` or its file has moved under
`aitasks/archived/`. A still-running agent whose task was archived reads DONE; a
hung agent whose task is still `Implementing` reads IDLE; and a completed agent
parked on a final prompt still reads **PROMPT**, because that is actionable now.
Only task-carrying agent windows (`agent-pick-`, `agent-qa-`, `agent-resume-`)
can ever read DONE — `agent-explore-*` / `agent-raw-*` have no task to finish.

### 3a. `website/content/docs/tuis/monitor/how-to.md`

Replace the single vague "idle indicator" bullet (line 41) with a real
status-badge list covering all four states and their colours:

| Badge | Colour | Means |
|---|---|---|
| `Active` | green | producing output |
| `PROMPT <n>s` | bold magenta | waiting on your input |
| `DONE <n>s` | bold blue | the pane's task is finished |
| `IDLE <n>s` | yellow | quiet longer than `idle_threshold_seconds` |

Also document the `CODE AGENTS (N)` legend row, which renders the same four
dots inline (`● active ● prompt ● idle ● done`) plus a `⟳ AUTO` tag when
auto-switch is on — currently undocumented entirely.

Update `### How to Toggle Auto-Switch Mode` (198-200) to state both real
behaviours: awaiting-input panes are preferred over merely-idle ones, and
**completed panes are excluded** — a finished agent is idle forever and would
otherwise permanently capture focus instead of surfacing a live agent that needs
input.

### 3b. `website/content/docs/tuis/monitor/reference.md`

- Line 49 (`a` key row): note that completed agents are skipped.
- Lines 100-101: the title-bar examples omit the new counters. Update to the
  three-way form, e.g. `tmux Monitor — 2 sessions · 5 panes · multi (attached:
  aitasks)  1 awaiting  2 done  1 idle`, and state that **each counter is
  omitted when zero** and that the three partition the agents on the same
  ladder as the badges (so a completed agent on a prompt is counted once, as
  awaiting).

### 3c. `website/content/docs/tuis/minimonitor/how-to.md`

- **Line 42** is the stale two-state line — replace with the four-state dot
  vocabulary (green active / magenta prompt / blue done / yellow idle).
- **Line 44** — add the `PROMPT <n>s` and `DONE <n>s` badge variants alongside
  `IDLE <n>s`.
- **Line 47** — the header-bar examples need the counters: `multi: 2s · 5a
  1 awaiting 2d 1 idle` and `aitasks  5 agents 2d 1 idle`. Note the narrow bar
  compresses done to `Nd`.
- Add a short note that the pinned `── this agent ──` panel stays static and
  never shows a DONE badge — use the general list (or `ait monitor`) for that.

### 3d. `website/content/docs/tuis/monitor/_index.md`

Line 42 describes the session bar as name + auto-switch state only; line 56
repeats the weak card-anatomy sentence. Bring both in line with 3a/3b.

**Deliberately not documented:** the internal detection mechanism — the
identity-keyed task cache, the `(st_mtime_ns, st_size)` invalidation, and the
`5s → 15s → 60s → 300s` retry decay. The user-facing consequence is one
sentence: the badge is eventually consistent and never permanently wrong — a
task archived while the TUI is open flips to DONE on a later tick, and even a
slow or interrupted archive resolves without restarting the TUI.

---

## Gap 4 — recovering a plain-bullet verification checklist (t1264)

**Problem:** a checklist whose items were written as plain `- text` bullets
(no `[ ]`) is invisible to the parser — the picker sees zero trackable items and
the checklist is a dead end. `convert` fixes it, but the page documents neither
the failure mode nor the recovery.

### 4a. `website/content/docs/workflows/manual-verification.md`

- **Line 35** — the subcommand list reads `(parse, set, summary, terminal_only,
  seed)`. Add `convert`.
- **`## The Checklist Format` (14-35)** — add a short "recovering a plain-bullet
  checklist" passage after the state table:
  - *Symptom:* items written as plain `- text` bullets carry no state, so the
    parser cannot track them and the runner reports no trackable items.
  - *Recovery:* when the runner finds a checklist with zero trackable items it
    offers **Seed from plan**, **Convert existing bullets**, or **Abort**.
    Convert rewrites each plain bullet in the checklist section to a pending
    `- [ ]` item, preserving text and indentation, and leaves any item that is
    already a checkbox untouched.
  - *Command:* `./.aitask-scripts/aitask_verification_parse.sh convert <task_file>`
  - *No-op / error case:* with no checklist section, or a section that has no
    plain bullets, it exits non-zero with `error: …` on stderr and **does not
    modify the file** (no `updated_at` bump). Note the complementary pair:
    `seed` refuses when a section already exists, `convert` refuses when one
    does not — together they cover both empty-checklist shapes.
- **`## Running a Manual-Verification Task` (74-109)** — mention that the runner
  performs this check before the marking loop starts.

**Helper path — checked, no change needed.** The task text asked to verify the
referenced helper path is current. `.aitask-scripts/aitask_verification_parse.sh`
exists and is exactly what the runner invokes (a thin wrapper that execs
`aitask_verification_parse.py`). The page's `.sh` reference is correct and stays;
the only staleness on line 35 is the missing `convert` verb.

---

## Files touched

| File | Change |
|---|---|
| `website/content/docs/commands/gates.md` | **new page** — the whole `ait gates` / `ait gate` CLI |
| `website/content/docs/commands/_index.md` | new `### Gates` group + usage-example lines |
| `website/content/docs/workflows/risk-evaluation.md` | `risk_evaluated` gate paragraph + See Also link |
| `website/content/docs/skills/aitask-resume.md` | current-state rewrite of the stale orchestrator sentence |
| `website/content/docs/tuis/board/reference.md` | By-Trail row + subsection, selector block, key tables |
| `website/content/docs/tuis/board/how-to.md` | By-Trail passage, sync note, `W` hidden-views list |
| `website/content/docs/tuis/board/_index.md` | base-view lists (By-Topic + By-Trail) |
| `website/content/docs/tuis/monitor/how-to.md` | four-state badge list, legend row, auto-switch |
| `website/content/docs/tuis/monitor/reference.md` | counters in title-bar examples, `a` key row |
| `website/content/docs/tuis/monitor/_index.md` | session bar + card anatomy |
| `website/content/docs/tuis/minimonitor/how-to.md` | status dots, badges, header-bar counters |
| `website/content/docs/workflows/manual-verification.md` | `convert` verb + recovery passage |

No files outside `website/content/docs/` are modified.

## Verification

1. **Build the site** — the only mechanical check that matters here:
   ```bash
   cd website && hugo build --gc --minify
   ```
   Must exit 0 with no `REF_NOT_FOUND` warnings (every `{{< relref >}}` and
   relative link added above has to resolve — the new `commands/gates.md` is
   linked from three other pages).
2. **Grep the claims back against source** — each documented render string must
   match the code that produces it:
   - selector block ↔ `aitask_board.py:1522-1529`
   - By-Trail footer labels ↔ `tests/test_board_bytrail_view.py:1120-1145`
   - badge text / counters ↔ `monitor_shared.py:526-536`, `monitor_app.py:1433-1449`
   - `sync-registry` report lines and exit codes ↔ `aitask_gate.sh:1101-1112`,
     `lib/gate_registry_sync.py:43-49`
   - `convert` CLI shape ↔ `aitask_verification_parse.py:381-385`
3. **Verb-list sanity** — confirm every command documented on the new page is
   reachable through the dispatcher (`ait gates --help`, `ait gate --help`), and
   that no agent-only seam leaked into the page.
4. **Local render spot-check** (optional) — `cd website && ./serve.sh`, then read
   the new Gates page and the board reference View Filters section.

No code changes, so no unit tests apply. `shellcheck` and the Python suite are
not affected.

## Risk

### Code-health risk: low
- Documentation-only change confined to `website/content/docs/` — no executable
  code, no shell scripts, no framework behaviour touched · severity: low
- Broken internal links are the only realistic defect class, and `hugo build`
  fails loudly on unresolvable `relref` · severity: low

### Goal-achievement risk: low
- Each gap is enumerated with target pages in the task body, and every factual
  claim is backed by a verbatim source snippet gathered during planning, so the
  prose can be checked against code rather than recalled · severity: low
- Two gaps turned out wider than the task text implied (board key tables and
  `_index.md` beyond the View Filters section; the monitor how-to having no
  status list at all). Both are called out explicitly above with scope notes
  rather than silently expanded or silently dropped · severity: low

### Planned mitigations
- None. Both dimensions are low; a docs-only change with a build-time link
  check needs no before/after mitigation task.

## Step 9 (Post-Implementation)

Standard: merge approval, `ait gates run 1361` (the task's active set contains
`risk_evaluated`, satisfied by the `## Risk` section above plus the risk fields
written at Step 7), then `./.aitask-scripts/aitask_archive.sh 1361`.

## Follow-ups to offer at Step 8

- A dedicated docs page for **implementation trails** (`/aitask-trail`, the trail
  artifact model, `ait artifact`) — nothing on the site covers it, which is why
  the By-Trail section carries an inline definition.
- `ait gate pass` is dispatched at `ait:323` but missing from `ait --help`'s
  Gates block — a known one-line code defect, deliberately deferred by t635_34.
