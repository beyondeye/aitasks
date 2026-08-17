---
Task: t1505_4_trail_skill_lite_default.md
Parent Task: aitasks/t1505_lite_trail_mode_and_trail_summary_pane.md
Sibling Tasks: aitasks/archived/t1505/t1505_1_bytrail_summary_pane.md, aitasks/archived/t1505/t1505_2_trail_detail_modal_entry_first.md, aitasks/archived/t1505/t1505_3_trail_narrative_overview_field.md, aitasks/t1505/t1505_5_manual_verification_lite_trail_mode_and_trail_summary_pane.md
Archived Sibling Plans: aiplans/archived/p1505/p1505_*_*.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-17 08:18
---

# p1505_4 — Lite by default, `--deep` opt-in, end-of-run summary

## Context

`/aitask-trail` produces a good artifact, but the create/refresh run is so
expensive that the feature goes unused — the same question gets asked
conversationally instead. The deterministic half is not the cost
(`aitask_trail_gather.sh drift` runs in 0.85s); the cost is a 433-line template
that mandates an evidence record per rationale, a belt-and-braces
`verifies` / `risk_mitigation_tasks` sweep on refresh, and propose-and-confirm
scope expansion. The output is not proportional to trail size:
`art:trail-shadow-review-loop` is 138,879 B for **10** entries (evidence 33.5KB
+ observations 28.5KB + narrative 9.2KB).

Every heavy section — `observations`, `relations`, `exclusions` — is optional in
the schema, and the board reads them defensively. Lanes come only from
waves → entries → `task`/`classification`/`snapshot`. **A lite trail is a
first-class trail, not a degraded one.**

This child is the point of the parent task: make a trail cheap to produce by
default, and print its summary at the end of the run so no board round-trip is
needed to decide what to pick next.

## Rebase check — RESOLVED during planning (was Step 0 of the prior plan)

The prior plan opened with "t1468_5 is editing this same template right now".
**It is not — it landed.** Verified:

- t1468_5 is `status: Done`, archived at
  `aitasks/archived/t1468/t1468_5_followup_kind_remaining_read_surfaces.md`;
  its template edit is commit `b25bb4893`, the most recent commit touching
  `.claude/skills/aitask-trail/SKILL.md.j2`. Goldens were regenerated in the
  same commit and are in sync.
- What it left behind, which this task must **carry, not drop**:
  - `SKILL.md.j2:403-406` — entry `snapshot`s populate `priority`, `effort`,
    `boardcol`, `followup_kind` from the MEMBER line.
  - `SKILL.md.j2:407-413` — the OMIT-sentinel rule (`unknown`/`invalid` are
    transport sentinels; writing either into an enum property invalidates the
    whole document).
  - `SKILL.md.j2:393` — `schema_version` is **`"1.1.0"`**, not `1.0.0`.
- t1505_3 landed `narrative.overview` (commit `8a67fa8ac`) as an **optional**
  `narrative` property with `minLength: 1` **and** `pattern: "\\S"` — a
  whitespace-only value is a hard validation failure, not a blank render.
  `trail_schema.py` needed no change (it is a schema-driven interpreter).
- t1505_1 landed the consumer for the depth marker: `_trail_depth_note()`
  (`.aitask-scripts/board/aitask_board.py:8748-8763`). **It recognises exactly
  the strings `"lite"` and `"deep"`**; an absent hint renders nothing and never
  defaults to "deep". (The prior plan called this `label_trail_depth` — that is
  the mitigation's name, not the identifier.)
- t1505_2 landed `test_lite_trail_reads_as_complete_and_is_genuinely_unscoped`
  in `tests/test_board_bytrail_view.py`, which already encodes the lite shape
  this task must produce: no observations/exclusions/relations, **no per-entry
  `evidence_refs`**, exactly one evidence record.
- t1508 landed, so both live handles validate again (`drift` on
  `art:trail-shadow-review-loop` returns `STALE`, not `ERROR:invalid_trail`).

## Decisions taken during planning

1. **Depth rule: always lite unless `--deep`** — for create *and* refresh,
   including the board's `R` key. Refreshing a deep trail without `--deep`
   therefore produces a lite version and drops its heavy sections; the deep
   version stays recoverable via `aitask_artifact.sh versions` /
   `get --version sha256:<hash>`. Because that is a destructive-by-default
   path, the refresh confirmation must **enumerate every discarded dimension
   with counts — including the evidence reduction and the removed per-entry
   `evidence_refs`, which are the largest losses and the easiest to hide** —
   before the write (Step 4 below).
2. **"Lite" is enforced by the validator, not by prose.** A hand-coded phase-2
   semantic rule in `trail_schema.py` — the same place that already rejects an
   `anchor` key anywhere. The template already mandates a pre-write
   `drift --trail <tmpfile>` validation on both create (2e.3) and refresh
   (3.5), so the rule is enforced on every write for free, with the existing
   `ERROR:invalid_trail` → read `INVALID:` → fix → re-validate loop as
   recovery. This replaces the prior plan's `assert_lite_shape` post-phase.

## Files to modify

| File | Change |
|---|---|
| `.aitask-scripts/lib/trail_schema.py` | new phase-2 `lite_shape` rule |
| `tests/test_trail_schema.py` | new `LiteShapeRule` test class |
| `.claude/skills/aitask-trail/SKILL.md.j2` | depth flag, lite contract, `overview`, end-of-run print |
| `tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md` | regenerated, never hand-edited |
| `tests/test_trail_skill_contract.sh` | new depth pins |
| `aidocs/implementation_trail_design.md` | §3, §6, §8 |

---

## Implementation steps

### Pre-phase (risk mitigations)

1. `[baseline_green]` Before any edit, run `bash tests/test_trail_skill_contract.sh`,
   `bash tests/test_skill_render_aitask_trail.sh`, and
   `bash tests/run_all_python_tests.sh --test-dir tests` narrowed to
   `test_trail_schema.py` (or the module directly under the resolved
   interpreter). Record the pass/fail of each. A red baseline would otherwise be
   misread later as damage from this change — in particular the newline- and
   indentation-sensitive pin at `tests/test_trail_skill_contract.sh:118-119`.

### 1. The `lite_shape` validator rule (build FIRST)

Riskiest and most load-bearing piece, so it lands before the writer is told to
depend on it.

In `.aitask-scripts/lib/trail_schema.py`, add `_check_lite_shape(doc, issues)`
next to `_check_no_anchor` (`:294-305`) and call it from the same place
(`:410`, inside `validate_trail`'s phase-2 block). Phase-2 discipline applies:
type-guarded, never crashes on untrusted JSON, skips what phase 1 already
flagged.

It fires **only** when `doc["rendering_hints"]["depth"]` is a string whose
`.strip().lower()` is `"lite"` — mirroring `_trail_depth_note`'s normalization,
so producer and consumer agree on what counts as lite. Then it appends a
`TrailIssue` with rule `lite_shape` for each of:

- `$.observations` **present at all**
- `$.relations` **present at all**
- `$.exclusions` **present at all**
- any `$.waves[*].entries[*].evidence_refs` **present at all**
- `$.evidence` whose length is not exactly 1

Emitted as the existing `INVALID:<path>|lite_shape|<message>` line shape, with a
message naming the remedy (omit the key, or re-run with `--deep`).

**Key presence, not emptiness — deliberate.** An earlier draft allowed
present-but-empty containers on the theory that the rule should target content.
That is wrong here, for a reason the source settles: the consumer's canonical
lite fixture `_lite_doc()` (`tests/test_board_bytrail_view.py:3994-4011`) omits
those keys **entirely** — its docstring reads *"no observations, relations or
exclusions, NO per-entry `evidence_refs`"*. Permitting `observations: []` would
let the producer emit a shape the consumer's own definition of "lite" does not
model, and would leave the template's word **"Omits"** meaning two different
things. The producer predicate and the consumer guard must be the same
predicate. The board renders both identically (`doc.get("observations") or []`),
so nothing breaks visually either way — which is exactly why the ambiguity would
survive undetected without this rule being exact.

**No schema JSON edit.** Both schema copies stay byte-identical,
`schema_version` stays `1.1.0`, and the contract test's `schema_version` pin is
untouched. No stored document carries `rendering_hints.depth`, so this rejects
nothing that exists today — the only moment such a tightening is free.

### 2. Validator tests

New class in `tests/test_trail_schema.py`, alongside `NarrativeOverviewProperty`
(`:149-210`) and following its `_doc` / `assert_rule` helper style:

- a clean `depth: "lite"` document validates — build it from the same shape as
  the consumer's `_lite_doc()` so the two fixtures agree by construction;
- each of the five violations is rejected, asserting the exact `lite_shape` rule
  **and path** — not merely "invalid";
- **empty containers are rejected too**, as their own cases: `observations: []`,
  `relations: []`, `exclusions: []`, and an entry with `evidence_refs: []` each
  fail. This is the pair of tests that pins presence-not-emptiness as the
  intended contract rather than an accident of implementation;
- a `depth: "deep"` document carrying observations, relations, exclusions and
  many evidence records validates (the rule must not fire);
- **back-compat control:** a document with no `rendering_hints` at all
  validates unchanged (every pre-t1505_4 trail);
- an unrecognised depth (`"medium"`) does not fire the rule, and `"  LITE "`
  does (normalization parity with `_trail_depth_note`).

### 3. Template: depth selection (`SKILL.md.j2` Step 0, `:79-95`)

Step 0 today is a single ordered list of **mutually exclusive mode selectors**
(`--refresh` / `--show` / `--topics` / bare id / nothing). Depth is a **second,
orthogonal axis**, so the step must be restructured to parse two things rather
than extended with a sixth alternative — otherwise the advertised deep opt-in
can be silently swallowed by whichever selector matched first.

Rewrite Step 0 as: **first resolve the mode, then resolve the depth**, with
depth parsed independently of position.

- `--deep` → full analysis depth.
- `--lite` → the default, stated explicitly (no behavior change), so a shared
  command line or a board launch can say what it means.
- **Absence means lite**, for create and refresh alike, including the board's
  `R` key.

**Accepted grammar — pin this matrix in the template, not just the two flags:**

| Invocation | Mode | Depth |
|---|---|---|
| `--refresh <handle> --deep` | refresh | deep |
| `--deep --refresh <handle>` | refresh | deep |
| `--refresh <handle>` | refresh | **lite** |
| `<task_id> --deep`, `--deep <task_id>` | create (task) | deep |
| `--topics <csv> --deep` (either order) | create (multi-topic) | deep |
| `--deep` alone | create (interactive scope) | deep |
| no arguments | create (interactive scope) | **lite** |
| `--show <handle>` | show | n/a — reports the **stored** depth |

Rules that make the matrix decidable, all of which must be stated in the
template:

- **Depth flags are position-independent** and may appear before or after the
  mode selector and its operand. A depth flag is never consumed as a mode
  operand: `--refresh --deep` (no handle) is a usage error, not a refresh of a
  handle named `--deep`.
- **`--deep --lite` together is an error — stop and say so.** Do not silently
  prefer one, do not prefer the last occurrence. The whole point of the flag is
  that the user's intent about cost is explicit; guessing it defeats that.
  Same for a repeated mode selector or two different mode selectors
  (`--refresh X --show Y`): mutually exclusive, so stop.
- **`--show` with a depth flag:** `--show` is strictly read-only and authors
  nothing, so depth is not applicable. Do **not** silently ignore it — print a
  one-line note that depth flags do not apply to `--show`, then continue the
  read-only flow and report the artifact's **stored** depth. (Silently accepting
  it would teach the user that `--show --deep` "worked".)
- The existing free-text auto-detect (a bare `art:trail-*` / `trail-*` token
  asks show-or-refresh) is unchanged; a depth flag present alongside it applies
  only if the user picks refresh, and falls under the `--show` note above if
  they pick show.

**Contract pin (step 7):** pin the deep-refresh accepted form
`--refresh <handle> --deep` explicitly. It is the central path the parent task
asks for — the escape hatch from the new lite default — and it is the one a
future template edit is most likely to break while leaving `--deep` on create
still working, so a pin on the flag alone would not catch it.

Record the depth in the document as
`rendering_hints: {"depth": "lite"}` / `{"depth": "deep"}` — **exactly those two
lowercase strings**, on every write at both depths. `rendering_hints` already
accepts it (`additionalProperties: {"type": ["string","number","boolean"]}`),
so no schema edit is needed.

No launch plumbing is needed, and this is verified rather than assumed:
`_launch_trail` (`aitask_board.py:11255`) → `aitask_codeagent.sh:476-478`
(`CMD+=("/aitask-trail ${args[*]}")`) forwards free-form args, and the guard at
`aitask_codeagent.sh:421-437` only rejects args containing whitespace. A
single-token `--deep` passes unchanged, and `["--refresh", handle, "--deep"]`
is three whitespace-free argv elements, so the deep-refresh form would forward
too. (Note the guard would reject a single `"--depth lite"` element — which is
why the flag is a bare token, not a `--depth <value>` pair.)

**Board consequence, stated rather than discovered later:** `R` calls
`_launch_trail(["--refresh", self.active_trail_handle], …)`
(`aitask_board.py:8980-9005`) with no depth flag, so it refreshes **lite** —
which is the intended default. The board therefore has no affordance for a deep
refresh; that is a UI gap, not a defect in this change, and it is listed as a
follow-up below rather than added here.

### 4. Template: the lite authoring contract

**Writes:** waves with `title` + `purpose`; entries with `classification`,
`confidence`, a **complete `snapshot`** (including `followup_kind` whenever the
gatherer's `MEMBER:` record reports one) and a short `rationale`;
`narrative.problem_statement` + `recommendation_summary` + **`overview`** +
`method_note`; `evidence` = exactly the one gatherer-snapshot record.

**Omits:** `observations`, `relations`, `exclusions`, per-entry `evidence_refs`.
"Omits" means the **keys are absent**, not present-and-empty — the validator
rule in step 1 enforces exactly that, so say it in the template rather than
leaving a writer to guess that `"observations": []` would do.

**Skips:** the evidence-record-per-rationale requirement (`:417-420`); the
belt-and-braces `verifies` / `risk_mitigation_tasks` sweep (`:288-344`, deep
only); propose-and-confirm scope expansion (`:180-194`) — out-of-scope
prerequisite work is **named in the `overview` prose** instead of restarting the
analysis over a new snapshot.

**Keeps, unchanged, at both depths:** exactly one artifact write per flow; the
non-skippable confirmation before it; pre-write validation; the refresh
stale-base re-read guard; the no-metadata-mutation invariant; the
anti-fabrication rules; and the complete-snapshot + OMIT-sentinel rules.
**Depth changes how much is analyzed, never whether the write is confirmed.**

**Refresh downgrade preflight (new).** When this run is lite and the loaded
trail carries anything the lite shape does not, Step 3.4's diff-style summary
MUST enumerate **every discarded dimension with its count**, before the existing
non-skippable confirmation:

- `observations` — N records
- `relations` — N records
- `exclusions` — N records
- `evidence` — **N records reduced to 1** (the gatherer snapshot); name the
  number being discarded, not just the survivor
- per-entry `evidence_refs` — N citations across M entries, all removed

The evidence dimensions are the ones a "sections are being dropped" phrasing
hides, and they are the largest: `art:trail-gates-framework-landing` carries 56
evidence records and 52 relations, `art:trail-shadow-review-loop` 41 and 15. A
lite refresh of the former discards 55 evidence records and every citation into
them. Silently is not acceptable when the flag-free path is the one that does it.

The summary must also state that the prior version stays recoverable via
`aitask_artifact.sh versions <handle>` / `get --version sha256:<hash>` — the
recovery route is what makes the confirmation informed consent rather than a
surprise, so it belongs in the same message as the counts.

A legacy trail with no `rendering_hints.depth` is treated as deep for this
preflight: absence must not be read as "already lite, nothing to warn about".

**Do not reflow `:403-406` or `:393`.** `tests/test_trail_skill_contract.sh:118-119`
asserts a two-line literal spanning `followup_kind` / `  from the MEMBER line`
including the newline and its exactly-two leading spaces; `:133` pins
`` `schema_version`: `"1.1.0"` ``.

### 5. `overview` content — authored at BOTH depths

`SKILL.md.j2:199-200` currently names only
`problem_statement, recommendation_summary, method_note`; add `overview`.

It is the deliverable the user judges the feature by: it should read like the
good conversational answer it replaces — which tasks to pick next and why, what
blocks what, what is in flight, what changed since last time — prose, not a
restatement of the wave table. Anti-fabrication still applies: no time
estimates, no progress claims, no commitments.

State explicitly that a **whitespace-only `overview` is a hard validation
failure** (`pattern: "\\S"`), not a silently-ignored value.

It is authored at deep depth too, because Step 6 prints it on every run.

### 6. End-of-run print

Print, after the `HANDLE:` line on create (`:236`), after the `update` on
refresh (`:377-379` — refresh has **no** end-of-run print today), and at the end
of `--show`:

- the depth (`lite` / `deep`), so a lite artifact is never mistaken for a deep
  one; and
- the summary, resolved and normalized **exactly as `trail_summary_text()`
  does** (`aitask_board.py:800-822`): prefer `narrative.overview`, fall back to
  `narrative.recommendation_summary`, treat whitespace-only as absent, and print
  the value **stripped of surrounding whitespace**.

**This deliberately deviates from the task text, which says "print the summary
verbatim".** Verbatim and shared-helper output are not the same thing and cannot
both be specified: `trail_summary_text` returns `value.strip()` (`:821`), and the
schema admits `"  padded  "` as valid (`pattern: "\\S"` only requires one
non-whitespace character). t1505_3 settled this direction deliberately — its
plan records that renderers display the field's *content*, "with surrounding
whitespace insignificant — never 'verbatim'", and landed a test pinning it.
Printing raw here would make the CLI and the By-Trail pane disagree about the
same field on the same artifact, which is the one property this step exists to
guarantee. So: one normalization, the shared one. Interior formatting
(paragraphs, line breaks, indentation within the prose) is preserved — only
leading and trailing whitespace is trimmed.

### 7. Contract test pins (`tests/test_trail_skill_contract.sh`)

Add pins, each asserted per profile against the three goldens as the file
already does. At minimum:

- lite is the default and `--deep` restores the full analysis;
- the **deep-refresh form** `--refresh <handle> --deep` is spelled out, and
  depth flags are position-independent;
- `--deep --lite` together is an error rather than a silent preference;
- "Depth changes how much is analyzed, never whether the write is confirmed" —
  the single-write confirmation is stated on **both** depth paths (the existing
  `NON-SKIPPABLE >= 2` count check already covers create + refresh);
- the lite contract's `snapshot` is complete **including `followup_kind`** —
  this is the pin that fails if the snapshot rule is ever moved into a
  deep-only block;
- the recorded depth values are exactly `"lite"` / `"deep"`;
- the lite contract omits the four keys **entirely** rather than emitting empty
  containers;
- the end-of-run print exists, states the depth, and resolves the summary with
  the same preference order and whitespace handling as the By-Trail pane;
- the refresh downgrade preflight enumerates **all five** discarded dimensions
  with counts — including the evidence reduction and the removed
  `evidence_refs` — and names the version-recovery route.

### 8. Regenerate goldens in the same commit

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/aitask-trail/SKILL.md.j2 \
    "aitasks/metadata/profiles/$profile.yaml" claude \
    > "tests/golden/skills/aitask-trail/SKILL-${profile}-claude.md"
done
./.aitask-scripts/aitask_skill_rerender.sh default
./.aitask-scripts/aitask_skill_rerender.sh fast
./.aitask-scripts/aitask_skill_rerender.sh remote
./.aitask-scripts/aitask_skill_verify.sh
```

One call per profile — the script takes a single profile name. Review the golden
diff; it is the audit signal, not a rubber stamp. **Stage by explicit path** —
the rerender sweep touches many generated targets and `git add -A` would pull in
unrelated ones. Tracked paths for this change:

```
.aitask-scripts/lib/trail_schema.py
.claude/skills/aitask-trail/SKILL.md.j2
tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md
tests/test_trail_schema.py
tests/test_trail_skill_contract.sh
aidocs/implementation_trail_design.md
```

(The `.claude/skills/aitask-trail-*-/`, `.agents/skills/`, `.opencode/skills/`
rendered variant dirs are untracked build output.)

### 9. Docs — `aidocs/implementation_trail_design.md`

- **§3 User journeys and invocation matrix** (`:78-107`) — the depth flag and
  the lite-by-default rule for create and refresh.
- **§6 Schema walkthrough** — the `rendering_hints` one-liner (`:225`) gains
  `depth` as the recorded marker; the narrative bullet notes `overview` is
  authored at both depths.
- **§8 Freshness and refresh** (`:262-324`) — refresh defaults to lite, a
  downgrade drops the heavy sections, and the prior version stays recoverable.

### Post-phase (risk mitigations)

1. `[lite_shape_negative_control]` A guard never seen failing is not a guard.
   Comment out the `_check_lite_shape` call site in `validate_trail`, re-run the
   new test class, and record the **named failing test ids** — one per violation
   dimension. Restore the call and confirm green. A negative control that passes
   is itself the failure: if any lite-shape test still passes with the rule
   disabled, that test is asserting something else and must be rewritten.

2. `[consumer_shape_parity]` Re-run
   `test_lite_trail_reads_as_complete_and_is_genuinely_unscoped`
   (`tests/test_board_bytrail_view.py:4132`) and diff its fixture `_lite_doc()`
   (`:3994-4011`) against the five dimensions `_check_lite_shape` enforces —
   including no per-entry `evidence_refs` and **key-absence rather than empty
   containers**. Record the comparison explicitly; if they differ, one of the
   two is wrong and the divergence must be resolved, not noted.

3. `[refresh_downgrade_preflight_check]` On a real deep→lite refresh (create a
   trail with `--deep`, then refresh it with no flag), confirm the Step 3.4
   summary enumerates **every** discarded dimension with its count —
   observations, relations, exclusions, the evidence reduction stated as
   "N records → 1", and the removed per-entry `evidence_refs` — states the
   `aitask_artifact.sh versions <handle>` / `get --version sha256:<hash>`
   recovery path, and appears **before** the non-skippable confirmation. Then
   confirm the prior deep version is genuinely retrievable, and that no
   dimension present in the loaded document is missing from the warning.

## What this plan deliberately does NOT build

The prior plan's **`producer_test_both_depths`** post-phase said to "extend
t1468_5's existing test to run at both depths". **That test does not exist.**
t1468_5 explicitly dropped it (`p1468_5…md:575-580`): *"The trail's snapshot
producer is agent-authored prose, so no unit test can drive it."* Its coverage
is three-part instead — gatherer unit test, skill-contract prose pin, schema
round-trip. The same reasoning applies here: no test in this repository can
drive the lite or deep writer, so no automated guard can catch a writer that
silently stops emitting `entry.snapshot.followup_kind`.

What covers it instead, honestly stated:

- the contract pin in step 7 (the *instruction* is depth-invariant);
- the schema round-trip in `FollowupKindSnapshotProperty`
  (`tests/test_trail_schema.py:76-147`);
- **the already-written checklist item in t1505_5**: *"A task with a known
  followup_kind still has it in the STORED entry.snapshot after both a lite run
  and a `--deep` run."* That is the real end-to-end, and it is already queued.

Writing a fourth artifact that only re-asserts the schema would be a guard that
cannot fail on the thing it names.

## Verification

- `bash tests/test_trail_skill_contract.sh`
- `bash tests/test_skill_render_aitask_trail.sh`
- `bash tests/test_codeagent_trail.sh`
- `./.aitask-scripts/aitask_skill_verify.sh` clean.
- `python3 .aitask-scripts/lib/trail_schema.py validate <file>` on a hand-authored
  lite fixture and a deep fixture — prints `VALID:<trail_id>` or
  `INVALID:<path>|<rule>|<message>`, exits 0/1/2. (`drift --trail` returns
  `ERROR:undriftable_input` for corpus fixtures, so the validator CLI is the
  right instrument here.)
- The `lite_shape` negative control fails as described in the post-phase, with
  named test ids, then passes when restored.
- The empty-container cases (`observations: []` and friends) are **rejected** —
  run them explicitly; they are the tests that distinguish the chosen contract
  from the one an earlier draft would have shipped.
- The end-of-run print and `trail_summary_text()` return the same string for the
  same artifact, including for a trail whose `overview` carries leading/trailing
  whitespace and for a legacy trail with no `overview` at all (fallback path).
- **Walk the argument matrix on the rendered skill**, not just the template:
  `--refresh <handle> --deep`, `--deep --refresh <handle>`, `--refresh <handle>`,
  `<task_id> --deep`, `--deep` alone, `--show <handle> --deep`, and the
  `--deep --lite` conflict. Each must land on the mode and depth the matrix
  states, and the conflict must stop rather than pick one.
- `bash tests/run_all_python_tests.sh` — read **only the last line** for the
  verdict; piping discards the exit status (`set -o pipefail` or check
  `${PIPESTATUS[0]}`).
- Both live handles still validate:
  `./.aitask-scripts/aitask_trail_gather.sh drift --trail art:trail-shadow-review-loop`
  and `…--trail art:trail-gates-framework-landing` return `CURRENT`/`STALE`,
  never `ERROR:invalid_trail`.
- **End-to-end, on a real task:** run `/aitask-trail <id>` with no depth flag.
  Confirm it completes materially faster than `--deep`; that the artifact
  validates; that the summary and the depth are printed at the end of the run;
  and that the trail renders correctly in the board's By-Trail view, including
  t1505_1's pane and the `· lite` banner note.

## Follow-ups to suggest at completion (not done here)

- **Codex CLI / OpenCode ports** of this skill — a separate task per CLAUDE.md.
- **No board affordance for a deep refresh.** `R` forwards no depth flag, so
  every board-initiated refresh is lite. A deep refresh requires running the
  skill by hand. Worth a small board task (a modifier key, or a choice in the
  existing `AgentCommandScreen` confirmation) once the lite default has been
  lived with.
- **Website board docs are stale from t1505_1 / t1505_2**, independently of this
  change: `website/content/docs/tuis/board/reference.md` and `how-to.md` never
  mention the By-Trail summary pane, the `v` key, the `a` reveal key or the
  depth banner label, and the literal footer transcript at `reference.md:299` is
  now wrong (missing `v Summary`). Pre-existing gap, inherited by any future
  `--deep` docs pass.

## Risk

### Code-health risk: medium
- A new rejection path lands in a **fail-closed** consumer — the board blanks
  By-Trail on a schema-invalid document — so a bug in `_check_lite_shape` could
  hide a trail rather than warn about it. Bounded: the rule fires only on
  `rendering_hints.depth == "lite"`, and no stored document carries that key,
  so nothing existing can regress. · severity: medium (residual — addressed by
  inline post-phase `lite_shape_negative_control`) · → mitigation: inline
  post-phase `lite_shape_negative_control`
- Restructuring a 433-line template guarded by ~24 exact-phrase pins, one of
  which (`:118-119`) is newline- and indentation-sensitive, invites a
  reflow-induced failure. · severity: low (residual — addressed by inline
  pre-phase `baseline_green`) · → mitigation: inline pre-phase `baseline_green`
- Producer-side rule and t1505_2's consumer-side expectation encode the same
  five-dimension shape in two places and can drift apart. · severity: medium
  (residual — addressed by inline post-phase `consumer_shape_parity`) ·
  → mitigation: inline post-phase `consumer_shape_parity`

### Goal-achievement risk: medium
- The headline deliverable — "materially faster" — is a property of model
  behavior driven by prose, not of any code this task writes. Nothing in this
  repository can test it. · severity: medium · → mitigation: none (covered by
  t1505_5's existing timing checklist item; not re-spawned)
- The `overview` prose quality ("reads like the good conversational answer")
  is likewise unverifiable automatically. · severity: medium · → mitigation:
  none (covered by t1505_5's existing `overview` checklist item)
- Refresh defaulting to lite silently downgrades a deep trail; a user pressing
  `R` on a 19-observation trail gets a lite version back. Chosen deliberately,
  but it is the one path where the default is destructive. · severity: medium
  (residual — addressed by inline post-phase `refresh_downgrade_preflight_check`)
  · → mitigation: inline post-phase `refresh_downgrade_preflight_check`

### Planned mitigations
- timing: pre-phase | name: baseline_green | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — reflow breaks a whitespace-sensitive contract pin | desc: record that the three trail test files pass before any edit, so a pre-existing red is not misread as damage from this change
- timing: post-phase | name: lite_shape_negative_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — new rejection path in a fail-closed consumer | desc: disable the _check_lite_shape call, record the named failing test ids per violation dimension, restore and confirm green
- timing: post-phase | name: consumer_shape_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — producer rule and t1505_2 consumer expectation encode one shape twice | desc: diff the five dimensions _check_lite_shape enforces against test_lite_trail_reads_as_complete_and_is_genuinely_unscoped and resolve any divergence
- timing: post-phase | name: refresh_downgrade_preflight_check | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — refresh's lite default is the one destructive default | desc: on a real deep to lite refresh, confirm the preflight names each dropped section with counts and the version-recovery path before the non-skippable confirmation

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.

## Post-Review Changes

### Change Request 1 (2026-08-17 09:22) — mode-aware pre-write validation

- **Requested by user (blocking, CONFIRMED):** `_check_lite_shape` ran only
  when `rendering_hints.depth` said `lite`, but that hint is authored by the
  same model whose lite output the guard is meant to validate. A default-lite
  writer could omit the hint (or write an unrecognised value) and retain
  observations, relations, exclusions, citations and many evidence records —
  `validate_trail` then accepted the full document. Make pre-write validation
  mode-aware so a lite run cannot bypass its own shape contract.

- **Reproduced before fixing** (the guard was genuinely opt-in):

  | document | issues (before) |
  |---|---|
  | deep fixture, no hint | **0** |
  | deep fixture, hint `"medium"` | **0** |
  | deep fixture, hint `"lite"` | 10 |

- **Changes made.** The fix had to come from the *caller*: the validator is a
  pure function of the document and cannot know what mode the run was in, and
  the marker cannot police itself.

  - `.aitask-scripts/lib/trail_schema.py`
    - `validate_trail(doc, schema=None, expect_depth=None)` — `expect_depth`
      is the authoring depth taken from the RUN's argument parsing, not read
      out of the document. `None` (default) preserves the previous
      self-declared behaviour exactly, which is what keeps every stored
      pre-t1505_4 trail valid.
    - New phase-2 rule `depth_marker`: under an asserted depth the document
      must record a matching `rendering_hints.depth`. This binds **both**
      directions — an unmarked *deep* trail is also rejected, so the marker
      the board's label depends on cannot go missing.
    - `_check_lite_shape(doc, issues, force=False)` — the lite shape now
      applies when the caller asserted lite, whether or not the marker was
      written.
    - `DEPTH_LITE` / `DEPTH_DEEP` / `DEPTHS` constants; an out-of-vocabulary
      `expect_depth` raises `ValueError` rather than silently degrading to the
      unenforced path.
    - `load_trail(..., expect_depth=None)` and CLI
      `validate <file> [--expect-depth lite|deep]` (exit 2 on a bad value).
  - `.claude/skills/aitask-trail/SKILL.md.j2` — Step 2e.3 is now **two
    required commands**, the `--expect-depth` assertion first, then the drift
    check; Step 3.5 requires both explicitly. The template states why the flag
    is not a formality.
  - `tests/test_trail_schema.py` — new `CallerAssertedDepth` class (9 cases),
    including the exact reported bypass and a control that
    `expect_depth=None` still validates a deep document.
  - `tests/test_trail_skill_contract.sh` — five new pins (v) so the
    instruction cannot be dropped from the template.

- **Verification.** Bypass closed:

  | assertion | issues (after) |
  |---|---|
  | no hint, `expect lite` | 11 (`depth_marker` + `lite_shape`) |
  | hint `"medium"`, `expect lite` | 11 (`depth_marker` + `lite_shape`) |
  | no hint, `expect deep` | 1 (`depth_marker`) |
  | hint `"deep"`, `expect deep` | 0 |
  | no hint, `expect None` | 0 (back-compat control) |

  CLI exit codes verified unpiped: 1 on mismatch, 0 on match, 2 on a bad depth
  value. Negative control re-run for the new rule: disabling
  `_check_depth_contract` + `force` fails exactly the 4 assertion tests and
  leaves the 5 validity tests passing.

- **Files affected:** `.aitask-scripts/lib/trail_schema.py`,
  `.claude/skills/aitask-trail/SKILL.md.j2`,
  `tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`,
  `tests/test_trail_schema.py`, `tests/test_trail_skill_contract.sh`.

### Change Request 2 (2026-08-17 09:37) — deterministic depth resolution; depth is reserved metadata

**Concern A (blocking, PLAUSIBLE → CONFIRMED):** `--expect-depth` was still
typed by the same model that authors the document. A flag-free (lite)
invocation could assert `--expect-depth deep`, write `rendering_hints.depth`
`"deep"`, and validate clean — CR1 closed *omission and mismatch*, not a
*wrong-but-self-consistent* assertion. Reproduced: full deep fixture + marker
`"deep"` + `--expect-depth deep` → **0 issues**.

**Changes made.**

- **New `.aitask-scripts/aitask_trail_depth.sh`** — a deterministic resolver
  that parses the invocation and *decides*, emitting
  `MODE:` / `DEPTH:` / `HANDLE:` / `TOPICS:` / `TARGET:` / `NOTE:`, or a single
  `ERROR:<kind>` line (exit 0 resolved, 1 grammar violation, 2 usage). The
  skill forwards its arguments verbatim and copies `DEPTH:` into **both**
  `rendering_hints.depth` and `--expect-depth`, so those two no longer have a
  single shared source in the model's head.
- **`tests/test_trail_depth_resolve.sh`** (new, 26 cases) makes the Step 0
  grammar executable for the first time — it previously existed only as prose
  and substring pins, which can prove a sentence is present but never what
  `--refresh X --deep` resolves to.
- Template Step 0 now leads with "Do not apply the grammar below by hand";
  three further contract pins (w) guard the resolver call and the both-sinks
  rule.
- 5 whitelist touchpoints added for the new skill-invoked helper (runtime +
  seed, per `aidocs/framework/aitasks_extension_points.md`); no `ait`
  dispatcher entry, since it is a helper rather than a user-facing command.

**A bug this caught in itself.** The first resolver captured operands via
`handle="$(take_operand …)"`; `fail()`'s `ERROR:` line was swallowed into the
variable and `set -e` killed the script — exit 1 with **empty stdout**, the
silent-abort shape `shell_conventions.md` documents. Fixed to set a global.
`assert_error` pins stdout *and* status precisely so a status-only assertion
cannot pass on it again.

**Residual limit — stated, not papered over.** A run that *declines to call the
resolver* and asserts an inconsistent depth is still not caught: every side of
that claim comes from one model, and the skill is prose a model executes. The
resolver removes the *interpretation* step (where a wrong-but-consistent depth
actually originates) and makes the grammar testable, but it does not eliminate
model mediation. Closing it fully needs the invocation depth bound outside the
prompt (e.g. the codeagent launch layer), which is larger than the depth
feature itself and is deliberately not attempted here. The three-tier guarantee
is documented in `aidocs/implementation_trail_design.md` §3.

**Concern B (CONFIRMED, disposition follow-up — done now instead):** both
schema copies described `rendering_hints` as advisory and ignorable while
`depth` had become load-bearing, so a consumer following the declared
extension-point semantics could legitimately strip it. Fixed in place rather
than deferred, because leaving a documented falsehood in the file this change
just made load-bearing is worse than a description edit: both copies now carve
`depth` out as **reserved semantic metadata** (producers must write it,
consumers must not strip or rewrite it, absent/unrecognised never defaults to
`"deep"`), and §6 of the design doc says the same plus a placement note on why
it lives in `rendering_hints` and what promoting it to top-level would cost.
Description-only edit: annotation keywords, no validation or digest impact, and
the two copies remain byte-identical.

- **Files affected:** `.aitask-scripts/aitask_trail_depth.sh` (new),
  `tests/test_trail_depth_resolve.sh` (new),
  `.aitask-scripts/lib/implementation_trail.schema.json`,
  `aidocs/implementation_trail.schema.json`,
  `aidocs/implementation_trail_design.md`,
  `.claude/skills/aitask-trail/SKILL.md.j2`,
  `tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`,
  `tests/test_trail_skill_contract.sh`, and the 5 whitelist files.

### Change Request 3 (2026-08-17 09:58) — resolver operand hygiene and show-depth protocol

Both CONFIRMED by reproduction against the resolver added in CR2.

**A — dash-leading operands were accepted (`aitask_trail_depth.sh`).**
`take_operand` refused only depth flags, so `--refresh --`, `--refresh --bogus`,
`--show --` and `--topics --` resolved **successfully** to values like
`HANDLE:art:--bogus` / `TOPICS:--`. The resolver is the grammar authority and
promises that a violation arrives as an `ERROR:` line, so normalizing an
option-looking token into a handle sent a malformed request downstream instead
of stopping. Now **any** dash-leading token in operand position (including a
bare `--`) fails with `ERROR:missing_operand:<flag>`; a handle or task id never
begins with `-`. Six new cases pin it.

Removing the now-redundant `is_depth_flag()` was prompted by shellcheck
(SC2329, never invoked) — the dash-leading test subsumes it, and a dead guard
is worse than no guard because it reads as coverage.

**B — `--show` reported the caller's depth flag.** `--show <handle> --deep`
emitted `DEPTH:deep` alongside `NOTE:depth_ignored_for_show`, while Step 0
calls `DEPTH:` the depth for the run. A model following the protocol could
print "deep" for a lite or entirely unmarked artifact — directly contradicting
the show flow's contract to state the **stored** depth. Show now always emits
`DEPTH:n/a` (the NOTE still fires when a flag was supplied and dropped), and
Step 0 says to read the stored `rendering_hints.depth`, reporting
`unrecorded` when absent. Three cases pin it.

**Verification.** Resolver suite 26 → **33 cases**; contract 147 → **153**
(one pin was rewritten: `pass the same value to \`--expect-depth\`` spanned a
line wrap in the rendered golden and was silently unmatched — replaced with two
single-line pins plus a new show-depth pin). Per-fix negative controls, run
separately: mutating the operand check away fails **9** named cases, mutating
the show branch away fails **3**; both green on restore. shellcheck clean.
Full sweep green: `PYTHON SUITE: PASSED (runner=pytest, exit=0)`, render 52/52,
codeagent 27/27, `skill_verify` clean, schema copies byte-identical, both live
handles `STALE`.

- **Files affected:** `.aitask-scripts/aitask_trail_depth.sh`,
  `tests/test_trail_depth_resolve.sh`,
  `.claude/skills/aitask-trail/SKILL.md.j2`,
  `tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`,
  `tests/test_trail_skill_contract.sh`.

### Change Request 4 (2026-08-17 10:12) — ambiguous handle must re-resolve after the choice

CONFIRMED by reproduction: `trail-x --deep` resolved to
`MODE:ambiguous_handle | DEPTH:deep | HANDLE:art:trail-x`. Step 0 said to use
that output "for the rest of the run", so a user who then chose **show** kept a
usable `DEPTH:deep` and never reached the show branch's `DEPTH:n/a` /
`NOTE:depth_ignored_for_show`. The leak CR3-B closed for an explicit
`--show <handle> --deep` reopened through the ambiguous path — the same defect
by a different route, which is exactly why it was worth chasing.

**Structural half (so it cannot be skipped by accident).** The resolver now
emits **`DEPTH:unresolved`** for `MODE:ambiguous_handle`, with or without a
depth flag. The mode is not decided yet, so there is no authoring depth to
report — and withholding a usable value makes the re-resolve *necessary* rather
than merely instructed. A prose "remember to re-run it" would have left the
stale `deep` sitting there for anyone who forgot.

**Instruction half.** Step 0 states that `ambiguous_handle` is not a runnable
mode: after the show-or-refresh question, re-run the resolver with the chosen
selector inserted before the handle, keeping every original argument, and use
the **second** run's values. Three contract pins guard it.

**Both branches pinned** (they must differ — refresh honours the flag, show
discards it and says so):

| re-resolved as | MODE | DEPTH | NOTE |
|---|---|---|---|
| `--refresh trail-x --deep` | refresh | deep | — |
| `--show trail-x --deep` | show | n/a | depth_ignored_for_show |
| `--refresh trail-x` | refresh | lite | — |
| `--show trail-x` | show | n/a | — |

**Verification.** Resolver suite 33 → **39 cases**; contract 153 → **162**.
Negative control: deleting the `ambiguous_handle` arm fails the 3 named
withholding cases, green on restore. shellcheck clean. Full sweep green:
`PYTHON SUITE: PASSED (runner=pytest, exit=0)`, render 52/52, codeagent 27/27,
`skill_verify` clean.

- **Files affected:** `.aitask-scripts/aitask_trail_depth.sh`,
  `tests/test_trail_depth_resolve.sh`,
  `.claude/skills/aitask-trail/SKILL.md.j2`,
  `tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`,
  `tests/test_trail_skill_contract.sh`.

### Change Request 5 (2026-08-17 10:32) — the re-resolve is a REPLACEMENT, not an append

CONFIRMED. CR4's wording said to re-run "with the chosen selector inserted
before the handle, **keeping every original argument**". Read literally that
retains the bare token, so `trail-x --deep` becomes
`--show trail-x trail-x --deep`, which the resolver rejects:

    ERROR:conflicting_modes:--show,trail-x        (exit 1)
    ERROR:conflicting_modes:--refresh,trail-x     (exit 1)

The code examples showed only the depth flags carrying over, so the prose and
the examples contradicted each other — and the prose is what a model follows.

**Changes made.** Step 0 now says to **replace** the bare handle token with
`--show <handle>` / `--refresh <handle>` while preserving the original depth
flags, states that the bare token is *consumed* by the rewrite, and shows the
wrong form by name with the exact error it produces. Two pins guard the wording
and two resolver cases pin both wrong transformations as hard errors — so the
next person to reword this cannot quietly reintroduce the append reading.

**A pin caught the reword itself.** `**re-run the resolver** with the chosen
selector` stopped matching when the sentence changed — the guard working as
intended.

**Wrap-spanning pin audit (root cause, fixed for the whole set).** Three times
in this task a contract pin silently spanned a line wrap in the rendered
golden: a multi-line literal only matches by luck of where the renderer breaks.
All **32** t1505_4 pins are now verified to match within a single rendered
line, checked by extracting each literal from the test source and asserting it
appears in some one line of the golden. (The one deliberate multi-line pin is
t1468_5's, which is intentionally newline- and indentation-sensitive.)

**Verification.** Resolver 39 → **41 cases**; contract 162 → **168**. Full
sweep green: `PYTHON SUITE: PASSED (runner=pytest, exit=0)`, render 52/52,
codeagent 27/27, `skill_verify` clean, schema copies byte-identical.
shellcheck: clean on the resolver; the test file reports only the pre-existing
`SC1091` info for sourcing `tests/lib/asserts.sh`, as every test file does.

- **Files affected:** `.claude/skills/aitask-trail/SKILL.md.j2`,
  `tests/test_trail_depth_resolve.sh`,
  `tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`,
  `tests/test_trail_skill_contract.sh`.

## Final Implementation Notes

- **Actual work done.** Lite is now the default depth for create and refresh
  (`--deep` opts out, `--lite` states the default), the depth is recorded as
  `rendering_hints.depth`, `narrative.overview` is authored at both depths, and
  every flow ends with a run summary print. Three enforcement layers landed
  rather than the planned one:
  1. `trail_schema.py` phase-2 `lite_shape` rule — a `depth: lite` document must
     omit `observations`/`relations`/`exclusions`/per-entry `evidence_refs`
     (key presence, not emptiness) and carry exactly one `evidence` record.
  2. `depth_marker` rule + `validate_trail(..., expect_depth=)` — the run
     asserts its own depth from parsed arguments, so omitting or misspelling the
     marker is not an escape from the lite contract.
  3. `.aitask-scripts/aitask_trail_depth.sh` — a deterministic Step 0 resolver,
     so the grammar is decided by a script rather than applied by the model.
  Plus the deep→lite refresh downgrade preflight (all five discarded dimensions
  with counts + the version-recovery route), the sweep gated to `--deep`, and
  §3/§6/§8 of the design doc.

- **Deviations from plan.** Layers 2 and 3 and the whole resolver were **not**
  in the approved plan; they came from review (CR1–CR5), each closing a
  confirmed hole in the layer before it. Two plan items were also corrected on
  evidence rather than followed: the post-phase `producer_test_both_depths` was
  **not built** (see below), and the end-of-run print does **not** print the
  summary "verbatim" as the task text asked — it uses `trail_summary_text()`'s
  normalization so the CLI and the By-Trail pane cannot disagree about the same
  field. Both deviations are argued in place rather than silently taken.

- **Issues encountered.**
  - The plan's `producer_test_both_depths` mitigation was **unbuildable as
    specified**: it said to extend a t1468_5 test that does not exist —
    t1468_5 explicitly dropped it because an agent-authored producer cannot be
    driven by a unit test. Replaced with the enforcement layers above plus the
    already-queued t1505_5 checklist item, and the reasoning recorded under
    "What this plan deliberately does NOT build" instead of quietly skipping it.
  - **My own resolver had the exact bug the conventions warn about**: operands
    captured via `handle="$(take_operand …)"` swallowed the `ERROR:` line into
    the variable and `set -e` killed the script — exit 1, empty stdout. Fixed to
    set a global; `assert_error` now pins stdout *and* status so a status-only
    assertion cannot pass on it again.
  - **Contract pins spanning line wraps, three times.** A multi-line literal
    matches only by luck of where the renderer breaks. Root-caused rather than
    patched case-by-case: all 32 new pins are now verified to match within a
    single rendered line.
  - **Two false negative controls of my own.** One `sed` errored out (unescaped
    `|` delimiter) and one Python mutation aborted on an assertion before
    writing; both reported "0 failures" while having mutated nothing. Redone
    from script files with the mutation confirmed applied. Every guard in this
    task has now been observed failing for a named reason.
  - `is_depth_flag()` became dead code once dash-leading operands were rejected
    wholesale; shellcheck (SC2329) caught it and it was deleted — a dead guard
    is worse than none because it reads as coverage.

- **Key decisions.**
  - **Refresh defaults to lite** (user's call), which makes the flag-free path
    the destructive one — hence the preflight enumerating all five dimensions
    *with counts*. Measured on the live trail: 26 observations, 32 relations,
    14 exclusions, **69 evidence records → 1**, **71 citations across 31
    entries**. The evidence dimensions dominate and were exactly what the first
    draft's wording would have hidden.
  - **Key presence, not emptiness**, for the lite shape — matching t1505_2's
    canonical `_lite_doc()` fixture, so producer predicate and consumer guard
    are the same predicate.
  - **`DEPTH:n/a` for show and `DEPTH:unresolved` for an ambiguous handle** —
    withholding a usable depth is what makes the show path and the re-resolve
    structurally correct instead of relying on the model remembering.
  - **No schema `const` bump and no required-field change**, so all stored
    trails stay valid; `expect_depth=None` preserves the old behaviour for every
    caller that has no mode to assert.
  - `depth` stays inside `rendering_hints` (t1505_1's landed consumer reads it
    there); the description in both copies now carves it out as reserved
    semantic metadata rather than leaving it described as ignorable.

- **Upstream defects identified:**
  - `website/content/docs/tuis/board/reference.md:299 — the literal By-Trail footer transcript is factually wrong since t1505_1: it omits the `v Summary` key. The same file's By-Trail section and how-to.md never mention the summary pane, the `v` key, the `a` reveal key or the depth banner label, all landed by t1505_1/t1505_2.` — **fixed in this task at the user's direction (CR6)** rather than spawned as a follow-up; the bullet is kept as provenance for why the docs were touched.

- **Notes for sibling tasks:**
  - **t1505_5 (manual verification)** — its checklist is still accurate but the
    surface grew. Additional things worth exercising: `--deep` vs no flag;
    `--show` stating the **stored** depth (`unrecorded` for the two live trails,
    which carry no marker); a deep→lite refresh showing all five discarded
    counts *before* the confirmation; and the ambiguous-handle path
    (`/aitask-trail trail-<slug> --deep` → choose show → the `--deep` must be
    announced as dropped, not applied). The board banner shows `· lite` / `· deep`
    only for trails written after this change.
  - **The depth protocol has four values**, not two: `lite`, `deep`, `n/a`
    (show), `unresolved` (ambiguous handle). Anything consuming
    `aitask_trail_depth.sh` must handle all four.
  - **`rendering_hints.depth` is now load-bearing.** Do not strip or rewrite it
    in any consumer, and never default an absent value to `"deep"`.
  - **Codex CLI / OpenCode ports** of this skill remain a separate task per
    CLAUDE.md; the `.j2` grew substantially here, so the port is larger than a
    typical one.

### Change Request 6 (2026-08-17 11:10) — fix the stale By-Trail website docs here

At Step 8b the user chose **"fix now"** over spawning the upstream-defect
follow-up, so the stale By-Trail website documentation was corrected in this
task instead.

**What was stale** (all pre-existing, from t1505_1 / t1505_2): the summary pane,
the `v` key, the detail screen's `a` reveal key and the depth banner label were
undocumented, and the literal footer transcript at
`website/content/docs/tuis/board/reference.md:299` omitted `v Summary`.

**Footer transcript measured, not inferred.** The doc contains a literal
rendering of the footer, which is a claim about output — so it was captured from
a real `run_test` board in By-Trail with a summary-bearing trail rather than
derived from binding order:

    r Refresh   R Agent Refresh   d Freshness   s Select Trail   S Sync   v Summary

The doc also now states that `v Summary` is listed only while the trail actually
has a summary, matching the `check_action` gate.

**Also documented (new in this task, not just the backlog):** `R` re-authors at
the lite depth; on a `deep` trail it says what that discards and asks first, with
the previous version retrievable; `--deep` is how to get the full analysis back.
The `R` cost cell no longer claims "Minutes" — a figure this change invalidates
and which was never measured — and reads "the slowest by far — an agent run".

Written current-state-only per `aidocs/framework/documentation_conventions.md`:
no "previously this page said", and no enumeration of supported agents ("the
trail skill", not a per-agent list).

**Verification.** `hugo build --gc --minify` clean: 236 pages, exit 0, no build
artifacts leaked into the tree.

- **Files affected:** `website/content/docs/tuis/board/reference.md`,
  `website/content/docs/tuis/board/how-to.md`.

### Post-archival fix (2026-08-17) — depth validation goes through a wrapper

Found while checking whether the Codex CLI / OpenCode wrappers needed adapting
to this task's new arguments. **They did not** — the stubs only strip
`--profile` and forward the rest unchanged, the body is rendered from the same
`.md.j2` for all three agents, and the only agent-specific path in it is the
pre-existing `model-self-detection.md` reference that `walk-write` rewrites. But
the check surfaced a defect this task introduced.

The pre-write depth assertion called
`python3 .aitask-scripts/lib/trail_schema.py validate … --expect-depth …`
directly — the **only** direct lib-python invocation in any skill. It bypassed
`python_resolve.sh` (bare `python3` is not the framework's interpreter), broke
the wrapper convention `aitask_trail_gather.sh` exists to uphold, and was on no
agent's permission allowlist: the sole `python3` entry anywhere covers one
unrelated script, and `.codex/rules/default.rules` / `seed/opencode_config.seed.json`
carry **no python entries at all**. Every trail write would have prompted, worst
for Codex and OpenCode users.

Fixed by adding a `validate` verb to `aitask_trail_depth.sh` — already
allowlisted at all five touchpoints, already owns the depth concern — which
resolves the interpreter via `require_ait_python` and passes the validator's
`VALID:` / `INVALID:` protocol and 0/1/2 exit codes straight through. The
template now calls the wrapper. Guarded by two contract pins, one an **absence**
check on `python3 .aitask-scripts/lib/` so the regression cannot return.

Resolver suite 41 → **47 cases**; contract 168 → **174**. Negative controls:
dropping `--expect-depth` forwarding fails 3 named cases; reverting the golden to
the bare `python3` call trips both new pins.

**Note for t1505_5:** the manual-verification checklist should exercise
`./.aitask-scripts/aitask_trail_depth.sh validate <file> --expect-depth lite|deep`,
not the `python3 …` form quoted in this plan's earlier Verification section.
