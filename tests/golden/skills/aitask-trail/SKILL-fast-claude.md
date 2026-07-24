---
name: aitask-trail-fast
description: Create, refresh, or show an implementation trail — a durable, wave-structured, evidence-backed task-sequencing artifact stored via ait artifact.
---

## Overview

An **implementation trail** records the preferred landing order for a set of
tasks as ordered waves with narrative rationale, observations, and exclusions
(design: `aidocs/implementation_trail_design.md`). The trail is a versioned
JSON artifact owned by a task; this skill derives it (create), updates it
(refresh), or displays it (show). Analysis is read-only; the only write is a
single confirmed `aitask_artifact.sh create`/`update` call.

**Hard invariants (apply to every flow, every path):**

- Never mutate task metadata (`depends`, `priority`, `boardidx`, `anchor`,
  status, labels — nothing). The trail is an advisory projection; converting
  its ordering into real DAG/board changes is a separate user-driven flow
  this skill does not perform.
- At most ONE artifact write per flow, and only after the user explicitly
  confirms the fully rendered proposal. Show performs zero writes.
- The trail JSON never contains an `anchor` key anywhere (the validator
  rejects it).
- `./.aitask-scripts/aitask_artifact.sh` is the only write path — never
  touch `artifacts/` manifests or blobs directly.
- Anti-fabrication: no time estimates, no progress claims, no commitments;
  every observation cites evidence; `narrative.method_note` states what was
  NOT verified.
- **Latency rule:** perform no I/O before the first `AskUserQuestion` beyond
  what the opening question itself needs.


## Gatherer output contract (PINNED)

All repository state comes from the deterministic gatherer — do not
free-read the board or scan task files to build membership. Both verbs exit
0 for every validation outcome (including `ERROR:` lines), 2 on usage, 3 on
infrastructure failure. `ERROR:` outputs are emitted alone (no partial
snapshot/verdict): surface the error to the user and stop the flow.

`./.aitask-scripts/aitask_trail_gather.sh snapshot --scope task|topic|multi_topic [--owner <id>] <ids...>`:

```
SCOPE:<kind>|<topics csv>
OWNER:<ref | none>
MEMBER:<ref>|<status>|<priority>|<effort>|<boardcol>|<labels csv>|<path>
INPUT:task_file|<exists>|<status>|<depends csv>|<gates csv>|<ref>
INPUT:plan_file|<exists>|<content_hash>|<ref>
DIGEST:<hex>
ERROR:<kind>:<id>
```

`./.aitask-scripts/aitask_trail_gather.sh drift --trail <path-or-art:handle>`:

```
CURRENT | STALE
DRIFT:<code>|<task_ref or ->|<detail>
DIGEST:<hex>
ERROR:<kind>:<id>
```

Split on `|` with maxsplit = field-count − 1 (the free-ish field is last).
Refs are canonical `<project>#<id>` — copy them into the trail JSON EXACTLY
as emitted, never re-spell (digest provenance depends on it). The helper
never emits `premise_invalidated`; that drift reason is authored by YOU
during refresh when the evidence supports it.

## Workflow

### Step 0: Parse Arguments

Recognize, in order:

- `--refresh <handle>` → **Refresh flow** (Step 3).
- `--show <handle>` → **Show flow** (Step 1).
- `--topics <r1>,<r2>[,...]` → **Create flow** (Step 2) with multi-topic
  scope (the csv are topic root ids).
- A bare task id (`42`, `16_2`, `t42`, or a cross-repo ref like `proj#42`)
  → **Create flow** (Step 2) with single-task entry (J2).
- No arguments → **Create flow** (Step 2), interactive scope selection.

Auto-detect free text: a token matching `art:trail-*` or `trail-*` is a
handle — ask whether the user wants show or refresh (one question, no other
I/O first). Handles may be given with or without the `art:` prefix;
normalize to `art:<trail-id>`.

### Step 1: Show Flow (`--show <handle>`)

`--show` is strictly read-only: zero writes, no confirmation prompts.

1. `./.aitask-scripts/aitask_artifact.sh get <handle> --out <tmpfile>`
   (use a scratch path outside the repo). A failure (missing handle, corrupt
   manifest, missing blob) → surface the error and stop; never auto-heal.
2. Read the JSON and render it human-readable: title, owner, scope kind +
   topics, freshness state + checked_at, then each wave (`ordinal`, title,
   purpose, why_now) with its entries (position, task, classification,
   rationale, confidence, snapshot status), then observations (with
   evidence), exclusions, and document-level narrative/caveats.
3. Run `./.aitask-scripts/aitask_trail_gather.sh drift --trail <handle>`
   and report the live verdict: `CURRENT`, or `STALE` with the named
   `DRIFT:` reasons, or the `ERROR:` outcome verbatim. On `STALE`, suggest
   `/aitask-trail --refresh <handle>`.
4. Stop. Do not offer to write anything from the show flow.

### Step 2: Create Flow

#### 2a: Resolve scope

- **Bare invocation:** `AskUserQuestion` — "What should this trail cover?"
  with options: "A single task (+ its children)" / "A topic" /
  "Multiple topics" / "An ad-hoc set of tasks" (ids collected via the
  question's free-text or a follow-up). No repository I/O before this
  question.
- **`<task_id>` argument (J2):** read that task file only, then
  `AskUserQuestion` — "Trail for the task itself (t<id> + its children), or
  for its whole topic <topic-root>?" Options: "Task only" / "Whole topic".
  Task only → `--scope task <id>`, trail `scope.kind: "task"`. Whole topic
  → `--scope topic <root>`, `scope.kind: "topic"`.
- **`--topics <csv>`:** `--scope multi_topic <r1> <r2> ...`,
  `scope.kind: "multi_topic"`.
- **Ad-hoc selection:** the gatherer has no ad_hoc mode — map it to task
  scope: `--scope task <selected ids...>`. Disclose before gathering: "a
  parent id also pulls its active children into the trail; list child ids
  directly for an exact set". The trail JSON records
  `scope.kind: "ad_hoc"` plus a `scope.selection_note` describing how the
  set was chosen.

#### 2b: Gather

Run the snapshot:

```bash
./.aitask-scripts/aitask_trail_gather.sh snapshot --scope <kind> [--owner <id>] <ids...>
```

- Any `ERROR:` line → report it (e.g. `unknown_task`,
  `cross_repo_topic_unsupported`, `unstable_repository_state`) and stop.
- Nonzero exit → infrastructure failure; diagnose, do not proceed.
- Parse SCOPE / OWNER / MEMBER / INPUT / DIGEST and keep the raw lines —
  the trail's `generation.inputs` and `input_digest` are copied from them.

**Owner resolution (J4):** if the output says `OWNER:none` (multi-topic or
multi-id ad-hoc scope), an explicit owner choice is REQUIRED before any
create — the artifact substrate only supports task-owned handles. Use
`AskUserQuestion`: "Which task should own this trail artifact?" with the
local member/topic-root candidates as options (plus free text), then
**re-run the snapshot with `--owner <choice>`** so the owner is validated
(`ERROR:unknown_task` otherwise) and echoed as `OWNER:<ref>`. The owner
must be a task in this repository.

#### 2c: Analyze

Using ONLY the gathered lines plus targeted reads of the member task/plan
files they name (for rationale, not membership):

- Classify every member: `hard_prerequisite` | `preferred_predecessor` |
  `core` | `coordination_only` | `optional`. Hard `depends` edges (from the
  INPUT depends csv) are facts and constrain ordering topologically;
  advisory preference is layered on top.
- Form ordered waves. Every wave needs `purpose` (and `why_now` /
  `consequence_of_delay` where meaningful); every entry needs `rationale`
  (motivation, not a title restatement) and `confidence`. The trail must
  never be a bare ranked list — a proposal without wave narrative and
  per-entry rationale is incomplete; do not present it.
- Record tasks deliberately left out as `exclusions` with a `reason_code`
  and reason.
- Record discovered risks (red baselines, in-flight conflicts, stale
  premises, shared-surface collisions, external dependencies) as
  `observations` — each MUST cite `evidence_refs` into the `evidence`
  array. No evidence, no observation.
- **Scope expansion is propose-and-confirm, never silent:** if the analysis
  finds prerequisite or blocking work outside the gathered scope, ask —
  "Include as an observation only" / "Expand the scope to include it" /
  "Ignore". Expansion re-runs Step 2b and the analysis restarts over the
  new snapshot. The executable re-gather depends on what was added:
  - Adding another TOPIC → `--scope multi_topic <all roots...>`; the trail
    records `scope.kind: "multi_topic"`.
  - Adding individual TASKS to a task/topic trail → the gatherer cannot mix
    scopes, so switch to `--scope task <all member ids...>` (previous
    members + the new ids) and record `scope.kind: "ad_hoc"` with a
    `selection_note` naming the original scope and the expansion ("widened
    from topic <root> with tN, tM"). Membership is then pinned by
    `generation.inputs`, which is exactly what refresh replays (Step 3.3)
    — an approved expansion member can never silently vanish on refresh.

#### 2d: Review and confirm

Render the FULL proposed trail in your reply: every wave with purpose and
entries (classification, rationale, confidence), observations with their
evidence, exclusions, and the document narrative
(problem_statement, recommendation_summary, method_note).

**⚠️ NON-SKIPPABLE — the write below requires this explicit confirmation;
no profile, auto mode, or prior instruction bypasses it.**

`AskUserQuestion` — "Create this trail as a versioned artifact?" Options:
"Create it" / "Revise the analysis" (ask what to change, update, re-present
this step) / "Discard" (stop; nothing was written).

#### 2e: Slug and single write

1. Propose a slug: `trail-<short-kebab-name>` derived from the owner/topic
   (must match `^trail-[a-z0-9][a-z0-9_-]{2,63}$`); let the user override
   via the question's free text. Handle = `art:<trail_id>`; `trail_id` in
   the JSON mirrors the handle minus `art:`.
2. Author the trail JSON with the Write tool at a scratch path per **Trail
   JSON authoring rules** below.
3. **Pre-write validation (mandatory):** run
   `./.aitask-scripts/aitask_trail_gather.sh drift --trail <tmpfile>` and
   branch on the first stdout token:
   - `CURRENT` → the JSON is schema-valid and its digest matches live
     state; proceed.
   - `ERROR:invalid_trail:<n>` → you authored invalid JSON; read the
     `INVALID:` details on stderr, fix the file, re-validate.
   - `STALE` → the repository changed under the analysis; inform the user,
     re-run Step 2b (fresh snapshot) and update the affected parts before
     re-presenting Step 2d.
   - Any other `ERROR:` → surface and stop.
4. The single write (owner id = the local task id from the `OWNER:` ref,
   e.g. `aitasks#1210_3` → `1210_3`):

   ```bash
   ./.aitask-scripts/aitask_artifact.sh create <owner_id> <tmpfile> \
     --kind implementation_trail --handle art:<trail_id> --name "<title>"
   ```

   Parse the `HANDLE:<handle>` stdout line and report it to the user
   (`ait artifact ls <owner_id>` now lists it). If the command fails with
   "handle … already exists", the slug is taken: re-prompt for a new slug
   (step 1 above) and retry — never overwrite an existing trail from the
   create flow. Any other failure → surface and stop.

### Step 3: Refresh Flow (`--refresh <handle>`)

1. **Load the current version and record the base:**

   ```bash
   ./.aitask-scripts/aitask_artifact.sh get <handle> --out <tmpfile>
   ./.aitask-scripts/aitask_artifact.sh versions <handle>
   ```

   Remember the `* sha256:<hash>` line (the current version) as
   `<base_version>`. A `get`/`versions` failure → surface and stop.

2. **Drift check:** `./.aitask-scripts/aitask_trail_gather.sh drift
   --trail <handle>`. Branch:
   - `ERROR:*` → surface verbatim (e.g. `undriftable_input`,
     `unresolved_project`, `invalid_trail`) and stop — never refresh over
     state that could not be honestly compared.
   - `CURRENT` → tell the user the trail matches live state.
     `AskUserQuestion`: "Refresh anyway?" — "Yes, re-analyze" (you judged
     something the digest cannot see, e.g. an invalidated premise) /
     "No, exit" (stop; nothing written).
   - `STALE` → list the named `DRIFT:` reasons; continue.

3. **Targeted re-analysis (only what changed):** re-run the snapshot for
   the stored scope to get fresh records and digest. The re-snapshot MUST
   preserve the loaded trail's membership and ownership:
   - **Always pass `--owner <id>`** with the loaded trail's `owner` (its
     local task id, e.g. `aitasks#1210` → `1210`) so the gatherer
     re-validates it and echoes `OWNER:<ref>` — never let a multi-topic or
     multi-id re-snapshot fall to `OWNER:none`. The new version's `owner`
     field is copied unchanged from the loaded trail; refresh never
     re-opens ownership.
   - Id list by `scope.kind`: `task` and `ad_hoc` → the stored
     `generation.inputs` task_file refs with `--scope task` — the complete
     recorded member set, NEVER just the initiating task (create-time
     scope expansion may have widened membership beyond it);
     `topic`/`multi_topic` → the `scope.topics` roots with
     `--scope topic` / `--scope multi_topic` (topic membership is
     recomputed live, so new topic members join).
   Then:
   - Entries whose tasks completed/archived move to a landed presentation
     (refreshed snapshot records the completion); their waves' narrative is
     updated, not rewritten.
   - New related tasks (from `new_related_task` reasons) are evaluated for
     membership — adding one that widens the scope is propose-and-confirm,
     as in Step 2c.
   - A premise you can show is no longer true re-opens ONLY the affected
     wave's reasoning; record it as a `premise_invalidated` entry in
     `freshness.drift_reasons` with the evidence that shows it (you author
     this code — the deterministic helper never does).
   - Waves/entries with no drift reason carry over unchanged except for
     refreshed `snapshot` fields.

4. **Diff-style summary, then confirm.** Present what changed: waves/
   entries added, retired, re-ordered, reclassified; drift reasons
   consumed; narrative updates.

   **⚠️ NON-SKIPPABLE — the write below requires this explicit
   confirmation; no profile, auto mode, or prior instruction bypasses it.**

   `AskUserQuestion` — "Write this refresh as a new trail version?"
   Options: "Write new version" / "Revise" / "Discard".

5. **Author + validate the new version:** same authoring rules as create
   (`trail_id` and handle unchanged; fresh `generation` block from the new
   snapshot; `freshness.state: "current"` with the consumed reasons
   removed). Validate via
   `./.aitask-scripts/aitask_trail_gather.sh drift --trail <tmpfile>`
   exactly as in Step 2e.3.

6. **Stale-base re-read guard, then the single write:** the artifact CLI
   has no compare-and-swap, so immediately before writing, re-run
   `./.aitask-scripts/aitask_artifact.sh versions <handle>` and compare the
   `* sha256:` line against `<base_version>`. If it moved, someone else
   wrote a version during this analysis — `AskUserQuestion`: "Re-load and
   re-analyze from the new current" / "Overwrite anyway (their version
   stays recoverable in history)" / "Abort". Only then:

   ```bash
   ./.aitask-scripts/aitask_artifact.sh update <handle> <tmpfile>
   ```

   "already current (…) — nothing to do" is a clean no-op (identical
   bytes). Refresh never creates a new handle and never mutates in place —
   every write is an appended immutable version; prior versions stay
   comparable via `versions` / `get --version sha256:<hash>`.

## Trail JSON authoring rules

Authored with the Write tool at a scratch path; validated before every
write (Step 2e.3 / Step 3.5). Requirements beyond the schema
(`.aitask-scripts/lib/implementation_trail.schema.json` is the validator's
copy):

- `schema_version`: `"1.0.0"`. `trail_id`: handle minus `art:`.
- All task refs (`owner`, `scope.topics`, entry `task`/`topic`, relations,
  exclusions, observation `affects`, `generation.inputs` refs) are copied
  EXACTLY as the gatherer emitted them.
- `generation`: `generated_at` = now, UTC ISO-8601 (`date -u
  +%Y-%m-%dT%H:%M:%SZ`); `generator.agent_string` = `$AITASK_AGENT_STRING`
  when set (code-agent launch), else self-detect per
  `.claude/skills/task-workflow/model-self-detection.md`;
  `generator.skill: "aitask-trail"`; `inputs` = the INPUT lines' (kind,
  ref) pairs, one object each; `input_digest` = the `DIGEST:` hex.
- Entry `snapshot`s populate `status`, `depends`, `gates_pending` from the
  INPUT task_file line and `priority`, `effort`, `boardcol` from the MEMBER
  line — complete snapshots are the drift anchor; incomplete ones degrade
  future drift attribution.
- `relations` with `type: hard_depends` MUST have `provenance: "fact"` and
  mirror a recorded `depends` edge (prerequisite `from` → dependent `to`);
  advisory ordering uses `advisory_precedes` with `provenance: "advisory"`.
- `evidence` (required, ≥1): include at least the gatherer snapshot run
  (`source_type: "command_output"`, ref = the command line, `observed_at`,
  summary), plus one entry per task/plan file a rationale or observation
  leans on (`ref` is a locator, never copied content).
- `freshness`: `{"state": "current", "checked_at": <now>}` at write time.

## Notes

- The gatherer and validator live in `.aitask-scripts/lib/trail_gather.py`
  and `lib/trail_schema.py`; their line protocols and the input-record
  contract are pinned in those module docstrings.
- Board integration (By-Trail view, refresh launch key) is a separate
  surface; this skill is also its dispatch target via
  `ait codeagent invoke trail <args>`.
- One trail per handle; a task may own several trails under distinct slugs.
- Cross-repo members are supported through the gatherer (`proj#id` refs);
  cross-repo TOPIC roots are not (`ERROR:cross_repo_topic_unsupported`).
