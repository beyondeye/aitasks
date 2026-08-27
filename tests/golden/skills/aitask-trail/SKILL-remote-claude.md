---
name: aitask-trail-remote
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
- **Depth changes how much is analyzed, never whether the write is
  confirmed.** Lite (the default) and `--deep` share every invariant in this
  list, the non-skippable confirmations, the pre-write validation and the
  refresh stale-base guard.
- The trail JSON never contains an `anchor` key anywhere (the validator
  rejects it).
- `./.aitask-scripts/aitask_artifact.sh` is the only write path — never
  touch `artifacts/` manifests or blobs directly.
- Anti-fabrication: no time estimates, no progress claims, no commitments;
  every observation cites evidence; `narrative.method_note` states what was
  NOT verified.
- **Latency rule:** perform no I/O before the first `AskUserQuestion` beyond
  what the opening question itself needs.


**Headless profile guard:** this profile runs without an interactive user.
`--show` works normally (read-only). The create and refresh flows REQUIRE an
interactive confirmation before their single write; in a headless session,
run the full read-only analysis, print the proposal, and then STOP with the
message "trail write requires interactive confirmation — re-run
`/aitask-trail` in an attended session". Never write the artifact headless.


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
MEMBER:<ref>|<status>|<priority>|<effort>|<boardcol>|<labels csv>|<followup_kind>|<path>
MEMBER_EXT:<ref>|<created_at>|<anchor>|<verifies csv>|<risk_code_health>|<risk_goal_achievement>
INPUT:task_file|<exists>|<status>|<depends csv>|<gates csv>|<ref>
INPUT:plan_file|<exists>|<content_hash>|<ref>
DIGEST:<hex>
ERROR:<kind>:<id>
```

Adding `--with-inflight` emits four further prefixes:

```
INFLIGHT_SOURCE:<gate|lock|tracked>|<ok|degraded|unavailable|not_consulted>|<age_seconds|->|<reason|->
INFLIGHT:<ref>|<gate|lock|both>|<PLAN|IMPLEMENT|POSTIMPL|->|<archive_status>
INFLIGHT_PATH:<ref>|<tracked|planned_new|phantom|malformed|no_tokens|unreadable|no_plan|unclassified>|<path|->
INFLIGHT_SCAN:<n_tasks>|<corpus_status>|<source_status>
```

**All five new prefixes are digest-excluded**, but they differ in
availability: `MEMBER_EXT:` is always emitted, while the four `INFLIGHT*`
lines appear **only** under `--with-inflight`. The compatibility guarantee
is therefore *digest* identity, **not** whole-output identity — a default
snapshot is not byte-identical to one from before these lines existed, but
its `DIGEST:` is, so every stored trail stays comparable.

`INFLIGHT:`'s fourth field is the **archive status**, republished from the
producer: `NO_GATES` / `ALL_PASS` / `BLOCKED:<csv>`, plus `unknown` for a
lock-only task. It is *not* a gate state, and the `unknown` sentinel is
part of the enum.

`INFLIGHT_SOURCE:tracked` reports the **classification evidence**
(`git ls-files`) and is **always emitted** — with `not_consulted` when
there was no in-flight task to classify, because absence is never the
signal in this contract. When it is `unavailable`, every task gets an
`unclassified` sentinel and `corpus_status` is `unclassifiable`.
Never synthesise a classification from absent git evidence:
every path would read `phantom`, and the result would look both
complete and healthy while resting on nothing.

`source_status` covers **only the two enumeration probes** (`gate`,
`lock`) — the ones answering *which tasks are in flight*. It says
nothing about `tracked`, which answers a different question, so
`both_enumeration_ok` can accompany a failed `tracked` source. Read the
two axes separately; never take `source_status` alone as a clean bill of
health.

**A healthy probe is not a complete one.** `source_status`
(`both_enumeration_ok` / `one_enumeration_ok` / `no_enumeration`) reports **only which
probes ran cleanly**. The gated source requires a `## Gate Runs` ledger and
the lock source tracks locks rather than execution, so neither — nor their
union — enumerates every running task. Never read `both_enumeration_ok` as
"nothing else is in flight".

**Path evidence covers only `.sh .py .md .yaml .yml .json .toml`.** A plan
written in any other language contributes no paths, and its absence of
overlap is **not** evidence of safety; that case is reported on the
`corpus_status` axis (`no_extractable_paths`), which is independent of
probe health. `corpus_status` also carries `unread_io` (plans exist, none
readable), `no_plans`, `not_scanned` (**no task enumerated at all**),
`unclassifiable` (**tasks enumerated, but the git evidence to classify
them was unavailable**) and `truncated` (a budget expired). These last
two are opposites and must not be conflated: one means there is no
in-flight work, the other that there is and its surface is unknown.
Evaluate the field as reported, never inferred from the absence of
`INFLIGHT_PATH:` lines.

`INFLIGHT_SOURCE:`'s age is **integer seconds** since this clone last
updated the ref, or `-` when it cannot be established (`no_reflog`,
`clock_skew`).
An unknown age is never rendered as `0` — `-` is the only sentinel.

**`planned_new` means "a plausibly-createable location", not "confirmed new
work".** A file that MOVED away lands there too, and a genuine planned
top-level file classifies `phantom` rather than `planned_new`.

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

**Do not apply the grammar below by hand — run the resolver.** Forward this
invocation's arguments verbatim:

```bash
./.aitask-scripts/aitask_trail_depth.sh resolve -- <the invocation's arguments>
```

Parse its stdout (`MODE:`, `DEPTH:`, optional `HANDLE:` / `TOPICS:` /
`TARGET:` / `NOTE:`) and use those values for the rest of the run. Exit 1 with
a single `ERROR:<kind>` line is a grammar violation — surface it verbatim and
stop; exit 2 is a usage error in your own call.

**`MODE:ambiguous_handle` is not a runnable mode — it comes back with
`DEPTH:unresolved`.** A bare `trail-*` token was given, so ask show-or-refresh
(as described below), and then **re-run the resolver** on a rewritten argument
list: **replace** the bare handle token with `--show <handle>` or
`--refresh <handle>`, and preserve the original depth flags. Nothing else
carries over — the bare token is *consumed* by the rewrite, not kept alongside
it:

```bash
./.aitask-scripts/aitask_trail_depth.sh resolve -- --show <handle> <original depth flags>
# or
./.aitask-scripts/aitask_trail_depth.sh resolve -- --refresh <handle> <original depth flags>
```

So `trail-x --deep` becomes `--show trail-x --deep`, **not**
`--show trail-x trail-x --deep` — that would keep the bare token as a second
mode selector and the resolver rejects it with
`ERROR:conflicting_modes:--show,trail-x`.

Use the **second** run's `MODE:` / `DEPTH:` / `NOTE:` for the rest of the flow.
Do not carry the first run's values forward: the first call could not know
whether depth applies, and reusing it is how a supplied `--deep` reaches a
`--show` the user only chose afterwards — the case the re-resolve exists to
prevent. The resolver withholds a usable depth here so this cannot be skipped
by accident.

**`DEPTH:` is the AUTHORING depth for this run** — on create and refresh,
write it into `rendering_hints.depth` and pass the same value to
`--expect-depth` at pre-write validation. Do not re-derive it, and do not
substitute your own reading of the arguments: deciding the depth yourself and
then asserting that same decision is a claim with only one source, which is
what the resolver exists to remove.

On `MODE:show` the resolver emits **`DEPTH:n/a`** — show authors nothing, so
there is no authoring depth. Report the artifact's **stored**
`rendering_hints.depth` instead (`unrecorded` when it carries none). A
`NOTE:depth_ignored_for_show` line means a depth flag was supplied and
dropped; say so, and never echo it back as the artifact's depth.

The grammar it implements, for reference (the resolver is the authority; this
table documents it and `tests/test_trail_depth_resolve.sh` pins it):

Arguments carry **two independent axes** — the mode, and the depth. Depth is
never a mode, and a mode selector never consumes a depth flag.

**Axis 1 — mode.** Recognize, in order:

- `--refresh <handle>` → **Refresh flow** (Step 3).
- `--show <handle>` → **Show flow** (Step 1).
- `--topics <r1>,<r2>[,...]` → **Create flow** (Step 2) with multi-topic
  scope (the csv are topic root ids).
- A bare task id (`42`, `16_2`, `t42`, or a cross-repo ref like `proj#42`)
  → **Create flow** (Step 2) with single-task entry (J2).
- No arguments → **Create flow** (Step 2), interactive scope selection.

Mode selectors are **mutually exclusive**: a repeated one, or two different
ones (`--refresh X --show Y`), is a usage error — stop and say so.

**Axis 2 — depth.** Recognize anywhere in the argument list, before or after
the mode selector and its operand:

- `--deep` → the full analysis (Step 2c / Step 3 in their entirety).
- `--lite` → the default, stated explicitly.
- Neither → **lite**. **Absence means lite**, for create and refresh alike,
  including the board's `R` refresh key.

Accepted grammar:

| Invocation | Mode | Depth |
|---|---|---|
| `--refresh <handle> --deep` | refresh | deep |
| `--deep --refresh <handle>` | refresh | deep |
| `--refresh <handle>` | refresh | **lite** |
| `<task_id> --deep` / `--deep <task_id>` | create (task) | deep |
| `--topics <csv> --deep` (either order) | create (multi-topic) | deep |
| `--deep` alone | create (interactive scope) | deep |
| no arguments | create (interactive scope) | **lite** |
| `--show <handle>` | show | n/a — reports the **stored** depth |

- A depth flag is **never** consumed as a mode operand: `--refresh --deep`
  with no handle is a usage error, not a refresh of a handle named `--deep`.
- **`--deep` and `--lite` together is an error — stop and say so.** Do not
  silently prefer one and do not prefer the last occurrence: the flag exists
  precisely so the user's intent about cost is explicit, and guessing it
  defeats the purpose.
- **`--show` with a depth flag:** show is strictly read-only and authors
  nothing, so depth does not apply. Do NOT silently ignore it — print a
  one-line note that depth flags do not apply to `--show`, then continue the
  read-only flow and report the artifact's **stored** depth.

Record the resolved depth in the document as `rendering_hints`:
`{"depth": "lite"}` or `{"depth": "deep"}` — **exactly those two lowercase
strings**, on every create and every refresh, at both depths. Any other value
is silently unrecognised by the board's depth label and states nothing.

Auto-detect free text: a token matching `art:trail-*` or `trail-*` is a
handle — ask whether the user wants show or refresh (one question, no other
I/O first). Handles may be given with or without the `art:` prefix;
normalize to `art:<trail-id>`. A depth flag alongside it applies if the user
picks refresh, and falls under the `--show` note above if they pick show.

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
4. **Print the run summary** — see **Run summary print** below. Show states
   the artifact's **stored** depth (a document with no `rendering_hints.depth`
   states "unrecorded", never "deep").
5. Stop. Do not offer to write anything from the show flow.

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

**Depth decides how much is analyzed — never whether the write is
confirmed.** Every invariant in the Overview, the non-skippable confirmation
in 2d, the pre-write validation in 2e.3, and the complete-snapshot rules in
the authoring section apply identically at both depths.

**At lite depth (the default), do this and stop:**

- Classify every member and form ordered waves, exactly as below — each wave
  with `title` + `purpose`, each entry with `classification`, `confidence`, a
  **complete `snapshot`** (including `followup_kind` whenever the MEMBER
  record reports one) and a short `rationale`.
- Author `narrative.problem_statement`, `recommendation_summary`,
  **`overview`** and `method_note`.
- `evidence` = **exactly** the one gatherer-snapshot record.
- **OMIT `observations`, `relations`, `exclusions` and per-entry
  `evidence_refs` entirely.** Omit means the key is absent — an empty list is
  not omission, and the validator rejects one (`lite_shape`).
- **SKIP**: the evidence-record-per-rationale requirement; the
  belt-and-braces `verifies` / `risk_mitigation_tasks` sweep (Step 3, deep
  only); and propose-and-confirm scope expansion — at lite depth, name
  out-of-scope prerequisite work **in the `overview` prose** instead of
  restarting the analysis over a new snapshot.

Everything from here to the end of 2c is the **deep** contract (`--deep`).

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
(problem_statement, recommendation_summary, overview, method_note). At lite
depth there are no observations or exclusions to render — the waves, entries
and narrative are the whole proposal.

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
3. **Pre-write validation (mandatory) — two commands, both required.**

   First, **assert the depth this run actually resolved in Step 0** (not the
   one you believe you wrote):

   ```bash
   ./.aitask-scripts/aitask_trail_depth.sh validate <tmpfile> \
     --expect-depth lite|deep
   ```

   Pass the depth from Step 0's argument parsing. Exit 0 and `VALID:<trail_id>`
   → proceed. Exit 1 → one `INVALID:<path>|<rule>|<message>` line per problem;
   fix the file and re-run. Two rules matter here:
   - `depth_marker` — the document does not record the depth this run
     authored. Write `rendering_hints.depth` accordingly.
   - `lite_shape` — a lite run kept a section the lite contract omits.

   **This flag is not optional and not a formality.** `rendering_hints.depth`
   is authored by you, so a rule that only reads the marker is one you can
   silently opt out of by omitting it — a lite run that forgets the marker
   would keep every heavy section and still validate. `--expect-depth` is the
   run asserting its own mode from the parsed arguments, which is the only
   side of this the document cannot restate.

   Then run the drift/digest check:

   ```bash
   ./.aitask-scripts/aitask_trail_gather.sh drift --trail <tmpfile>
   ```

   and branch on the first stdout token:
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

5. **Print the run summary** after the `HANDLE:` line — see **Run summary
   print** below. This is what removes the board round-trip from the loop.

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
   - **Belt-and-braces follow-up sweep — `--deep` only.** Skip this entire
     sweep at lite depth (the default); it is one of the two costs the lite
     contract exists to remove. For every member that completed or
     was archived since the loaded version, run BOTH halves — the two
     post-landing relations point in opposite directions, so one re-read
     cannot find both:
     - *Outgoing* (`risk_mitigation_tasks`) — read that member's own task
       file (active tree or `aitasks/archived/`) and take the ids its
       `risk_mitigation_tasks:` list names.
     - *Incoming* (`verifies`) — the member does NOT record who verifies it,
       so re-reading the member can never surface this edge. Look on the
       other side, with an over-inclusive prefilter confirmed by reading:
       ```bash
       { grep -rl --include='t*.md' '^verifies:' aitasks || [ "$?" = 1 ]; } |
         { rc=0
           while IFS= read -r f; do
             grep_rc=0
             grep -q -- '<member bare id>' "$f" || grep_rc=$?
             case "$grep_rc" in
               0) printf '%s\n' "$f" ;;                            # candidate
               1) ;;                                  # no match: expected, ok
               *) printf 'sweep: cannot read %s\n' "$f" >&2; rc=2 ;;
             esac
           done
           exit "$rc"; }
       ```
       A nonzero exit means the sweep is INCOMPLETE — re-run it before
       trusting the candidate list, and never treat that run as "no
       candidates found".

       Four exit-status properties, all load-bearing — do not "simplify"
       them back:
       - **No `xargs -r`.** BSD/macOS `xargs` has no `-r` and exits with an
         error, aborting the whole sweep and silently dropping every
         candidate. It also already skips empty input, so the loop is the
         portable form of both behaviours.
       - **`grep`'s no-match exit 1 is normalized to success.** Finding no
         verifier is the common, expected outcome; left as-is it returns 1 and
         (under `pipefail`, or any runner that treats nonzero as failure)
         looks like a broken command and invites a spurious retry.
       - **A per-file read failure propagates.** If a file vanishes or turns
         unreadable between the prefilter and the confirmation scan, that
         candidate is silently omitted — the exact loss this sweep exists to
         prevent. Reporting it on stderr is not enough, because the loop's
         own status would still be 0; `rc=2` plus the trailing `exit "$rc"`
         is what makes the omission visible to the caller.
       - **The confirmation `grep`'s status is captured with `|| grep_rc=$?`,
         never read as a bare `$?` on the next line.** No-match (exit 1) is the
         *common* outcome here, so under `set -e` a bare `grep -q …` aborts the
         loop before the `case` can reach its `1)` arm — the whole classifier
         becomes unreachable and the sweep silently returns nothing. The `||`
         suspends errexit; `build-verification.md` records the same rule for
         command-substitution captures (t1621).
       Then open each hit and keep only those whose `verifies:` list really
       names the member. Confirming by reading is required, not optional:
       the field is spelled `[1039]`, `['1074_2']` and `[t1018_1, t1018_2]`
       in practice, so no single regex decides membership, and the id can
       also occur in body prose.

     Feed whatever survives into the same propose-and-confirm path as the
     `new_related_task` reasons. This does not reopen the PINNED "don't scan
     task files to build membership" rule: the sweep is a bounded lookup of
     two named relations against an already-fixed member list, and nothing it
     finds joins the trail without the user's confirmation. The gatherer
     reports both edges too — this is the backstop for what its scan
     deliberately skips (a follow-up that is itself archived, a target in an
     unscoped project), not a replacement for it.
   - A premise you can show is no longer true re-opens ONLY the affected
     wave's reasoning; record it as a `premise_invalidated` entry in
     `freshness.drift_reasons` with the evidence that shows it (you author
     this code — the deterministic helper never does).
   - Waves/entries with no drift reason carry over unchanged except for
     refreshed `snapshot` fields.

4. **Diff-style summary, then confirm.** Present what changed: waves/
   entries added, retired, re-ordered, reclassified; drift reasons
   consumed; narrative updates.

   **Downgrade preflight — when this run is lite and the loaded trail is
   not.** Refresh defaults to lite, so the flag-free path is the one that
   discards content. Before the confirmation below, enumerate **every**
   dimension being discarded, each with its count from the loaded document:

   - `observations` — N records dropped
   - `relations` — N records dropped
   - `exclusions` — N records dropped
   - `evidence` — N records reduced to 1 (state the number being discarded,
     not just the survivor)
   - per-entry `evidence_refs` — N citations across M entries, all removed

   Then state that the prior version stays recoverable:
   `./.aitask-scripts/aitask_artifact.sh versions <handle>` lists it and
   `get --version sha256:<hash>` retrieves it. The counts and the recovery
   route are what make the confirmation informed consent rather than a
   surprise — a bare "some sections will be dropped" hides the two largest
   losses, which are the evidence records and their citations.

   A loaded trail with **no** `rendering_hints.depth` is treated as deep for
   this preflight: an absent marker means the document predates the hint, not
   that it is already lite.

   Re-run with `--deep` is the way to keep everything; say so.

   **⚠️ NON-SKIPPABLE — the write below requires this explicit
   confirmation; no profile, auto mode, or prior instruction bypasses it.**

   `AskUserQuestion` — "Write this refresh as a new trail version?"
   Options: "Write new version" / "Revise" / "Discard".

5. **Author + validate the new version:** same authoring rules as create
   (`trail_id` and handle unchanged; fresh `generation` block from the new
   snapshot; `freshness.state: "current"` with the consumed reasons
   removed). Validate with **both** commands of Step 2e.3 — the
   `--expect-depth <this run's depth>` assertion first, then
   `./.aitask-scripts/aitask_trail_gather.sh drift --trail <tmpfile>`.
   Refresh is the path where the depth assertion matters most: it is the flow
   whose default silently downgrades an existing deep trail, so the run must
   prove it wrote the depth it claims.

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

7. **Print the run summary** after the write — see **Run summary print**
   below. Refresh prints it exactly as create does.

## Run summary print

Printed at the end of **every** flow — create (2e.5), refresh (3.7) and show
(1.4) — so the user can decide what to pick next without opening the board.
Two lines, in this order:

1. **The depth**, stated plainly (`lite` / `deep`; `unrecorded` when the
   document carries no `rendering_hints.depth`), so a lite artifact is never
   mistaken for a deep one.
2. **The summary**: `narrative.overview`, falling back to
   `narrative.recommendation_summary` when `overview` is absent or holds only
   whitespace, printed with **surrounding whitespace stripped** and interior
   formatting preserved. Print nothing for this line if neither field carries
   text.

That resolution order and that stripping are not a local choice — they are
exactly what the board's `trail_summary_text()` does for the By-Trail summary
pane. The two surfaces read the same field on the same artifact, so they must
render it identically; do not print the raw value, and do not reorder the
fallback.

## Trail JSON authoring rules

Authored with the Write tool at a scratch path; validated before every
write (Step 2e.3 / Step 3.5). Requirements beyond the schema
(`.aitask-scripts/lib/implementation_trail.schema.json` is the validator's
copy):

- `schema_version`: `"1.1.0"`. `trail_id`: handle minus `art:`.
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
  INPUT task_file line and `priority`, `effort`, `boardcol`, `followup_kind`
  from the MEMBER line — complete snapshots are the drift anchor; incomplete
  ones degrade future drift attribution.
- **OMIT any optional `snapshot` field whose MEMBER value is `unknown` or
  `invalid`.** Those two are transport sentinels, not values: `unknown` means
  the task had no such field and `invalid` means it could not be transported.
  Writing either into a schema-`enum` property (`priority`, `effort`,
  `followup_kind`) fails validation and invalidates the WHOLE document. For
  `followup_kind` this is the common path — most tasks are genuine new work
  and carry no kind — so a stored `unknown` would break every ordinary trail.
- `relations` with `type: hard_depends` MUST have `provenance: "fact"` and
  mirror a recorded `depends` edge (prerequisite `from` → dependent `to`);
  advisory ordering uses `advisory_precedes` with `provenance: "advisory"`.
- `evidence` (required, ≥1): include at least the gatherer snapshot run
  (`source_type: "command_output"`, ref = the command line, `observed_at`,
  summary), plus one entry per task/plan file a rationale or observation
  leans on (`ref` is a locator, never copied content).
- `freshness`: `{"state": "current", "checked_at": <now>}` at write time.
- `rendering_hints`: `{"depth": "lite"}` or `{"depth": "deep"}` per Step 0 —
  written on every create and refresh, at both depths.
- `narrative.overview` is authored at **both** depths. It is the prose answer
  the user actually reads: which tasks to pick next and why, what blocks
  what, what is in flight, what changed since last time — **not** a
  restatement of the wave table. The anti-fabrication rules still apply: no
  time estimates, no progress claims, no commitments. A **whitespace-only
  `overview` is a hard validation failure** (`pattern: "\\S"`), not a
  silently-ignored value — omit the key rather than write a blank one.
- **At `depth: "lite"` the shape is enforced, not merely requested.** The
  validator rejects `observations`, `relations`, `exclusions` or a per-entry
  `evidence_refs` key (present at all, even empty), and any `evidence` length
  other than 1, with rule `lite_shape`. Omit the keys. Under
  `--expect-depth lite` that rejection applies **whether or not you wrote the
  depth marker**, so omitting the marker is not an escape from the lite
  contract — it is its own `depth_marker` failure.

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
