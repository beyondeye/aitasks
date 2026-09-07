---
name: aitask-backlog-roadmap
description: Rank the background-work backlog into a durable, conflict-aware implementation trail — an advisory estimate of what is worth picking up alongside work already in flight.
---

## Usage

Publish or refresh the background-work roadmap: a ranked, conflict-aware
ordering of Ready follow-up work and small genuine tasks, stored as a versioned
`implementation_trail` artifact so the board's By-Trail view, `drift` and
versioning all work unchanged.

```bash
/aitask-backlog-roadmap            # rescan the corpus and publish a new version
/aitask-backlog-roadmap --show     # render the current version, write nothing
```

The ranking, hedging and lane assignment are computed by
`.aitask-scripts/lib/roadmap_policy.py` — **do not re-derive any of them.** Your
authorship is the two prose fields in step 3 and the run summary in step 9.

Design record: `aidocs/framework/background_work_roadmap.md`. Read it before
changing anything about how this skill reports its results.

## What this roadmap is, and is not

These are correctness constraints, not tone. Every one of them has a failure
mode attached.

- The output is an **estimate**: origin/topic evidence plus in-flight state as
  of the run, **reserving nothing**. `/aitask-pick` runs the live
  parallel-admission preflight before implementation; this does not.
- **Never say "safe to run in parallel".** Say **"no known conflict at check
  time"**. The checker observes; it does not reserve, and overlapping work can
  begin the instant after a `CLEAR`.
- A `CURRENT` drift verdict has **two** limits, and both must be stated: it
  speaks only for the **published members**, and it covers **task-record inputs
  only** — it never validates the in-flight or admission evidence the lanes were
  scored from. That evidence is refreshed only by re-running this skill.
- This skill's rerun is a **rescan**, not a replay-refresh. It recomputes the
  whole corpus and **may change membership** — unlike the generic trail refresh
  in `/aitask-trail`, which replays recorded inputs.

## Procedure

### 1. Resolve mode

`--show` → fetch and render the current version, write nothing, stop:

```bash
./.aitask-scripts/aitask_artifact.sh get art:trail-backlog-roadmap --out <tmp.json>
```

Otherwise continue: the default mode is rescan-and-update.

### 2. Detect existence, capture the base version and the previous members

```bash
./.aitask-scripts/aitask_artifact.sh versions art:trail-backlog-roadmap
```

**Branch on the exit status, and never through a pipe** — a pipe returns the
pipe's status, so `versions … | grep` reports success for a handle that does not
exist:

- **exit 1** → no manifest. This run will `create`; `previous_members` is empty
  and the delta is "first publication".
- **exit 0** → it exists. This run will `update`. Record the `* sha256:` line as
  `base_version`, then fetch the current document **before** recomputation:

  ```bash
  ./.aitask-scripts/aitask_artifact.sh get art:trail-backlog-roadmap --out <prev.json>
  ```

  Collect `previous_members` = every `waves[].entries[].task`. Neither
  `versions` nor the newly encoded document carries the old member list, so
  without this fetch the join/leave delta in step 6 cannot be produced
  truthfully — it would have to be guessed or silently dropped.

### 3. Author the narrative

Write a JSON file with exactly two keys (a third, `overview`, is optional):

```json
{
  "problem_statement": "...",
  "recommendation_summary": "..."
}
```

Both must be non-empty. **Do not write `method_note`** — the driver composes it
from the measured corpus and refuses the key by name, because a hand-written one
would need counts you have not been told and would drift from the document it
describes. `recommendation_summary` must carry the estimate/reserves-nothing
framing above.

This happens **before** the driver runs: the encoder takes `narrative` as an
argument, so there is no post-hoc injection point.

### 4. Run the driver

```bash
./.aitask-scripts/aitask_backlog_roadmap.sh \
  --narrative <narrative.json> --owner aitasks#1718 --out <tmp.json>
```

`aitasks#1718` is the standing holder task — it owns the handle so the roadmap
outlives the tree that built it. Do not substitute a different owner.

Exit statuses: **0** every content state (an empty corpus is an answer), **2**
CLI misuse, **3** a refusal to publish on evidence that cannot be hedged per
candidate (an unavailable corpus, or a candidate with no `ORIGIN_FACT` row). On
a **3**, report the named cause and stop — do not publish.

Parse these report lines for the summary:

| line | meaning |
|---|---|
| `CORPUS:<scanned>\|<published>` | corpus size and how many were published |
| `LANES:` / `PUBLISHED_LANES:` | `safe=`/`coordination=`/`unresolvable=`, every lane named even at zero |
| `ORIGIN_QUALITY:<exact>\|<topic>\|<unknown>` | mutually exclusive histogram |
| `DEGRADED:<n>\|<causes>` | UNCHECKABLE count with named causes |
| `CONFLICT_WITH:<ref>\|<n>` | the in-flight tasks the conflicts are against |
| `UNPARSABLE_TASK_FILE:<name>` | a listed task file with no task number |
| `MEMBER:<ref>` | one per published member |

### 5. Validate

```bash
./.aitask-scripts/aitask_trail_depth.sh validate <tmp.json> --expect-depth deep
```

Expect `VALID:trail-backlog-roadmap`. Anything else: stop and report.

### 6. Compute the membership delta

Diff the encoded document's `waves[].entries[].task` set against
`previous_members`: **joined** (in new, not old) and **left** (in old, not new).

### 7. Confirm before writing — NON-SKIPPABLE

The default mode persists an artifact version. Ask before it does, stating
**create vs update**, the `base_version` on the update path, and the membership
delta (counts plus the joined/left ids).

`AskUserQuestion` — "Publish this roadmap?" — options "Publish" / "Discard".
`--show` never reaches this step.

### 8. Write, once

**Create path:**

```bash
./.aitask-scripts/aitask_artifact.sh create 1718 <tmp.json> \
  --kind implementation_trail --handle art:trail-backlog-roadmap \
  --name "Background-work roadmap"
```

Parse the `HANDLE:` line from stdout.

**Update path — stale-base guard first.** Re-run `versions` and compare its
`* sha256:` line against `base_version`. The artifact CLI has no
compare-and-swap, so this is the only thing between a concurrent refresh and a
silent overwrite. If it moved, `AskUserQuestion`: "Re-run the analysis against
the new current" / "Overwrite anyway (their version stays recoverable via
`artifact versions`)" / "Abort".

**"Overwrite anyway" must re-derive the delta before writing.**
`previous_members` and the delta shown in step 7 describe the version captured
in step 2, which is no longer the one being superseded — reporting them would
name joins and leaves against a predecessor that never sat in the version chain.
So on that branch: `get` the newly current document, recompute
`previous_members` and the step-6 diff against it, and present a **fresh**
confirmation with the new base version. Do **not** rebuild the document — the
corpus facts did not change because someone else published, and "Overwrite
anyway" is precisely the statement that this run's analysis stands.

Then:

```bash
./.aitask-scripts/aitask_artifact.sh update art:trail-backlog-roadmap <tmp.json>
```

No `HANDLE:` line on update.

### 9. Run summary

Report, in plain prose:

- The corpus size and that only the top N were published.
- **The lane composition, including a lane that is empty.** The lane is not part
  of the sort key (by design — affinity must never outrank risk), so a capped
  run can legitimately publish no parallel-safe entry at all. An empty safe lane
  reported only by its absence reads as "nothing to worry about" rather than
  "nothing was startable".
- `UNCHECKABLE` counts **with their named causes**, and the in-flight tasks the
  conflicts are against (`CONFLICT_WITH:`) — a conflict count with no
  counterparty invites the reader to assume a diffuse problem when it is usually
  one broad in-flight surface.
- The origin-quality histogram, so the persisted-origin-field question stays
  evidence-backed. It is **mutually exclusive** — never quote a raw signal
  population.
- The membership delta from step 6.
- Any `UNPARSABLE_TASK_FILE:` lines, as a data defect worth fixing.
- Both limits of a `CURRENT` verdict, and that this run rescanned the corpus.

## Notes

- **Nothing here re-derives a collision verdict.** The lanes *are* the checker's
  verdicts (`CLEAR` / `CLEAR_CAVEATED` → parallel-safe, `CONFLICT` →
  coordination, `UNCHECKABLE` → unresolvable). A second opinion would be a
  second definition of "safe".
- **`followup_kind` is not ordering-relevant** and is never read by the scorer.
  Do not introduce it as a ranking signal.
- The parallel-safe lane may be empty for reasons of **evidence availability**,
  not ranking: an in-flight claim's surface is read from its plan file, and most
  `Implementing` tasks carry no plan (t1688 owns that gap). Report the cause;
  do not work around it.
