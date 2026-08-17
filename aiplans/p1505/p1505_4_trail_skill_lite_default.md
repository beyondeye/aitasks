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
