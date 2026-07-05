---
Task: t1119_shadow_implementation_challenge_subprocedure.md
Worktree: (none — current branch, profile 'fast')
Branch: (current)
Base branch: main
---

# t1119 — Shadow implementation-challenge sub-procedure

## Context

The `aitask-shadow` skill already adversarially reviews a *plan* before approval
(`plan-challenge.md`). There is no companion pass that reviews the **code that was
actually written** for a task. This task adds `impl-challenge.md` — an adversarial
review of the implementation (real diff + the plan's own `## Final Implementation
Notes`) — emitting the same machine-parseable `===AITASK-CONCERNS===` block so
minimonitor's existing concern picker forwards it unchanged. The shadow stays
**advisory-only**.

A second, coupled problem is fixed in the same task: the concern-format single-
source-of-truth doc lives at `aidocs/framework/shadow_concern_format.md`, but the
framework sync ships only `.claude/skills/` and `.aitask-scripts/` — **not**
`aidocs/framework/`. So every skill-local reference to that path dangles in every
install. The doc is relocated **into the shadow skill directory** so it travels
with the skill, and all references are repointed.

This is a **framework-source change** (aitasks repo). It ships downstream to all
installs via `ait: Update aitasks framework` commits — editing a consumer only
would be overwritten.

## Scope decision — reference enumeration (all 8 sites, not the task's literal "5")

The task body says "all 5 in-repo references dangle." First-hand grep found **8
reference sites across 7 files**. Splitting them by whether they ship to installs:

**Distributed (dangle in installs — the task's "5"):**
- `.claude/skills/aitask-shadow/plan-challenge.md:61`
- `.claude/skills/aitask-shadow/plan-assumptions.md:65`
- `.claude/skills/aitask-shadow/plan-diagnose-errors.md:55`
- `.aitask-scripts/monitor/concern_parser.py:15` **and** `:17` (two occurrences)
- `.aitask-scripts/aitask_shadow_capture.sh:32`

**Framework-repo-only (not distributed, but break if the doc is deleted/moved):**
- `aidocs/framework/shadow_agent.md:15` — a *same-directory* relative link
  (`shadow_concern_format.md`)
- `tests/test_concern_parser.py:4` — docstring citing the path

Because the aidocs doc is **deleted** (below), the two framework-repo-only sites
must be repointed too, or they dangle after the move. The plan repoints **all 8**
plus the new `impl-challenge.md`. (Ref: memory *Enumerate full injection surface*
— don't over-claim coverage / handle every sink.)

## Decision — fate of `aidocs/framework/shadow_concern_format.md`: **delete + redirect**

No website/Hugo dependency (`grep website/` is clean); the only non-distributed
referrers are `shadow_agent.md` and the test docstring. Per
`aidocs/framework/documentation_conventions.md` ("Delete X … means redirect
cross-refs now"), the doc is **deleted** and every reference is repointed to the
new skill-local path, giving a single source of truth.

- **Rejected alternative — keep a thin pointer stub in aidocs:** would let
  `shadow_agent.md`'s sibling link keep resolving without change, but adds a
  redirect-only file and a second doc path; the conventions favor
  redirect-refs-on-delete over leaving stubs. Not chosen.

New home: **`.claude/skills/aitask-shadow/concern-format.md`**.
Uniform repoint string (repo-root-relative, matching existing citation style):
`aidocs/framework/shadow_concern_format.md` → `.claude/skills/aitask-shadow/concern-format.md`.

## Changes

### 1. New file — `.claude/skills/aitask-shadow/impl-challenge.md`

Modeled directly on `plan-challenge.md`. Full content (shown inside a 4-backtick
fence so the procedure's own nested ```` ``` ```` blocks display intact — the real
file uses ordinary triple-backtick fences):

````markdown
# Implementation Challenge (adversarial)

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user wants
the **code actually written** for a task stress-tested — "review the
implementation", "did it actually do what the plan said", "check the code that was
written". This is the implementation-side companion to `plan-challenge.md` (which
reviews the *plan*). Your job is to be a constructive adversary against the
**implementation**: actively look for where the code, as written, is wrong — not
to reassure.

**Advisory-only:** present the findings to the user; never drive the followed
agent's pane. (Reading local git state — commits, diffs — is fine; "advisory-only"
governs the *followed pane*, not your own repo reads.)

## Inputs

1. **Task definition + plan** — via `./.aitask-scripts/aitask_shadow_context.sh <task_id>`
   (`TASK_FILE:` + active `PLAN_FILE:`). This is "what was supposed to be built."
   Resolve `<task_id>` as in the shadow SKILL.md Step 2 if it wasn't passed.
2. **The actual code changes (real diff)** — first discover the task's commits:
   ```bash
   ./.aitask-scripts/aitask_revert_analyze.sh --task-commits <task_id>
   ```
   Each `COMMIT|<hash>|<date>|<subject>|<ins>|<del>|<matched-id>` line names a
   commit; read their diff (`git show <hash>`, or `git diff <first>^..<last>`).

   **Working-tree fallback (important — this is often the live case).** The task
   workflow commits the code *and* writes Final Implementation Notes only **after**
   the Step 8 review prompt. So at the common pre-commit review moment there may be
   **no task commit yet**, with all real changes sitting in the working tree /
   index. If `--task-commits` returns nothing (or only older sessions' commits),
   inspect the uncommitted state instead:
   ```bash
   git status --short   # what changed
   git diff             # unstaged changes
   git diff --cached    # staged changes
   ```
   Review whichever of committed / staged / unstaged actually carries this task's
   changes. **Tell the user which source you reviewed** (committed vs
   working-tree) — a working-tree review is of in-progress, not-yet-final state.
3. **The plan's `## Final Implementation Notes`** — the agent's own narrative
   (*Actual work done*, *Deviations from plan*, *Issues encountered*, *Key
   decisions*), written by task-workflow Step 8 at end of implementation. This is
   where deviations are *justified*.

When you (re)capture the followed pane to read long content, use the deep
plan-review capture — `./.aitask-scripts/aitask_shadow_capture.sh --deep <followed_pane_id>` —
so a long diff or notes section isn't truncated to the default window's tail.

## "Too early to review" gate (required — run first)

If the resolved plan does **not** contain a `## Final Implementation Notes`
section, the implementation phase of the task workflow has not completed. Before
doing anything else, **warn the user**: it is probably too early to review the
implementation — the task workflow likely has not finished, so the diff may be
partial and no deviations have been narrated yet. Let the user decide: **abort**,
or **proceed anyway** against the partial state. Do not silently continue. If the
user proceeds anyway, the diff to review is necessarily the **working-tree /
index** state (input 2's fallback), not committed history — review that and say so.

## Attack the implementation along these axes

(Skip any that don't apply; add others the change invites.)

- **Implementation flaws** — bugs, missed cases, incorrect logic, off-by-ones,
  mishandled error/empty/edge inputs, or regressions in the code *as actually
  written*, checked against the plan/task intent and the real diff.
- **Risks left unmitigated** — cross-reference the plan's `## Risk` section and
  Final Implementation Notes. Do **NOT** re-flag a risk the implementation
  explicitly addressed/mitigated; surface only risks that remain **open** in the
  landed code.
- **Unjustified deviations from the plan** — compare the diff against the plan. A
  deviation the Final Implementation Notes justify is fine. Flag only
  deviations that are unexplained or whose justification does not hold up.

## Produce a prioritized list, then stay honest

Produce a prioritized list of concrete problems. For each: a one-line statement,
*why* it bites (the triggering scenario), and severity (high / medium / low).
Order by severity. Separate fatal (should block acceptance) from fixable
(follow-up). **Stay honest** (same rule as `plan-challenge.md`): if a dimension is
genuinely clean, say so briefly — a short list of real problems beats a long list
of weak ones. No generic "consider adding tests" filler.

## Also emit the structured concern block (for pick-and-forward)

After the human-readable list, append a machine-parseable copy of the *same*
concerns so the user can tick a subset and forward them to the followed agent via
minimonitor's concern picker. This block is **additive** and does **not** relax
the advisory-only guardrail (it is text for the *user* to copy).

Emit exactly this fenced format (single source of truth:
`.claude/skills/aitask-shadow/concern-format.md`):

```
===AITASK-CONCERNS===
- [high | path/to/file.ext:120] The new guard compares the raw email instead of the normalized one, so a task assigned with a trailing-space email never matches and re-locks every resume. It bites on the common reclaim path. Normalizing both sides before compare would fix it — exact form your call.
- [medium | unmitigated risk] The plan's Risk section flagged concurrent writers to the ledger, but the diff adds no locking around the append, so two resumes can interleave and drop one run. The Final Implementation Notes don't mention it, so it looks unaddressed rather than deliberately deferred.
===END-CONCERNS===
```

Rules — all load-bearing for minimonitor's parser; match them exactly:
- One concern per line, in the form `- [priority | region] body`.
- The leading `- ` (dash **and** space) is **MANDATORY** on every concern line —
  it is the wrap-collision guard (a soft-wrapped continuation line never carries
  it, so the parser can't mistake wrapped text for a new item).
- `priority` is one of `high`, `medium`, `low` — reuse the severity you assigned.
- `region` for implementation concerns should identify the **code locus**
  (e.g. `path/to/file.ext:LINE`) or the **axis** (`unmitigated risk`,
  `unjustified deviation`, `correctness`).
- `body` carries the **full framing** — the problem, *why it bites*, and enough
  context for the receiving agent to choose **how** to fix it. Do **not** compress
  it to a bare one-liner. "One logical line" is a **parser constraint** (emit no
  literal newline mid-concern — let the terminal soft-wrap), not a brevity
  constraint.
- Order items by severity, matching the prose list.
- **Always emit the closing `===END-CONCERNS===` fence** — minimonitor's
  auto-offer only fires on a complete block.
- Emit the block **only when you have at least one concern**. If the
  implementation is genuinely clean, omit the block entirely.
````

### 2. Relocate the concern-format doc → `.claude/skills/aitask-shadow/concern-format.md`

Move the content of `aidocs/framework/shadow_concern_format.md` into the new
skill-local file, with these in-file fixes (its old refs were same-directory
siblings in `aidocs/framework/`, now they must be repo-root-relative):

- Every `shadow_agent.md` link (lines ~6, ~96, ~99 of the source) →
  `aidocs/framework/shadow_agent.md`.
- **Fix the stale "Where it lives → Producer" bullet.** The source currently reads
  "`plan-challenge.md` (and peers …), mirrored across the `.agents/` and
  `.opencode/` shadow trees" — but verified: `.agents/skills/aitask-shadow/` and
  `.opencode/skills/aitask-shadow/` contain **only `SKILL.md`**, no mirrored
  sub-procedures (wrapper-only convention). Rewrite the bullet to name the
  `.claude` sub-procedures as the producers and describe the other trees as
  wrappers only:
  > **Producer:** the `.claude/skills/aitask-shadow/` plan-review sub-procedures
  > that emit concern lists — `plan-challenge.md`, `impl-challenge.md`,
  > `plan-assumptions.md`, `plan-diagnose-errors.md`. These live **only** in the
  > Claude tree; the `.agents/` and `.opencode/` shadow trees carry a `SKILL.md`
  > wrapper only (no mirrored sub-procedure files).

Then **delete** `aidocs/framework/shadow_concern_format.md`.

### 3. Repoint all references (uniform string swap)

Replace `aidocs/framework/shadow_concern_format.md` →
`.claude/skills/aitask-shadow/concern-format.md` in each of:

- `.claude/skills/aitask-shadow/plan-challenge.md:61`
- `.claude/skills/aitask-shadow/plan-assumptions.md:65`
- `.claude/skills/aitask-shadow/plan-diagnose-errors.md:55`
- `.aitask-scripts/monitor/concern_parser.py:15` and `:17`
- `.aitask-scripts/aitask_shadow_capture.sh:32`
- `tests/test_concern_parser.py:4`
- `aidocs/framework/shadow_agent.md:15` — currently the bare sibling
  `shadow_concern_format.md`; repoint to
  `.claude/skills/aitask-shadow/concern-format.md`.

New `impl-challenge.md` already cites the new path (see content above).

### 4. Register `impl-challenge.md` in the shadow SKILL.md

In `.claude/skills/aitask-shadow/SKILL.md`, Step 3 "Structured analyses", add one
bullet after the `plan-challenge.md` bullet (do **not** edit the Step 0 greeting —
it is auto-derived from Step 3 per the maintainer note):

```markdown
- **Adversarially challenge the implementation** ("review the implementation",
  "did it actually do what the plan said", "check the code that was written") →
  read and follow `impl-challenge.md`.
```

## Cross-agent port

Per project convention (memory *Shadow skill = wrapper, no cross-agent port*), the
`plan-*.md`/`impl-challenge.md` sub-procedures live **only** under
`.claude/skills/aitask-shadow/`; `.agents/` and `.opencode/` carry only a `SKILL.md`
wrapper that redirects here. No fork into other agent trees. The `.claude`
SKILL.md is a plain file (no `.j2`/goldens for aitask-shadow — verified), so no
rerender/golden regeneration is needed. Suggest a **separate follow-up** only if
the Codex/OpenCode `SKILL.md` wrappers enumerate capabilities and need the new
bullet mirrored (to check at implementation time).

## Risk

### Code-health risk: low
- Missing one of the 8 reference sites would leave a dangling ref in installs ·
  severity: low · → mitigation: enumerated all sites up front + a final
  `grep -rn shadow_concern_format` must return **zero** hits (verification below).

### Goal-achievement risk: low
- None identified. All consumed interfaces (`aitask_shadow_context.sh`,
  `aitask_revert_analyze.sh --task-commits`, `aitask_shadow_capture.sh --deep`,
  the concern block + `concern_parser.py`) verified present; no new machinery.

`risk_mitigations_planned = false` (both dimensions low; no before/after follow-up
tasks warranted — the one low bullet is covered by in-task grep verification, not
a separate task).

## Verification

1. **No dangling references in shipped/source files** — scope the grep to the
   source and shipped locations, *not* a bare `.` (which also matches legitimate
   historical/data records that mention the old name: task/plan descriptions under
   `.aitask-data/`, the `.aitask-explain/` codebrowser cache, `.aitask-history/`,
   and archived plans about *other* shadow tasks — none of which are dangling refs
   to fix):
   ```bash
   grep -rn "shadow_concern_format" \
     .claude/skills/ .aitask-scripts/ aidocs/framework/ tests/ website/
   ```
   Must print **nothing**.
2. **New doc resolves from every citation:**
   ```bash
   test -f .claude/skills/aitask-shadow/concern-format.md && echo OK
   grep -rln "\.claude/skills/aitask-shadow/concern-format\.md" \
     .claude/skills/aitask-shadow/ .aitask-scripts/ aidocs/framework/ tests/
   ```
3. **Balanced code fences in every edited/created markdown** — the new
   `impl-challenge.md` and the relocated `concern-format.md` each contain multiple
   nested example blocks; a stray fence would render instructions as code. Assert
   an even count of fence lines per file:
   ```bash
   for f in .claude/skills/aitask-shadow/impl-challenge.md \
            .claude/skills/aitask-shadow/concern-format.md; do
     n=$(grep -cE '^```' "$f"); [ $((n % 2)) -eq 0 ] && echo "$f: OK ($n)" || echo "$f: UNBALANCED ($n)"
   done
   ```
   Both must report `OK`, and a quick visual scan should confirm the prose
   sections render as prose (not swallowed into a code block).
4. **Parser tests still green** (no logic changed, only a docstring path):
   ```bash
   python3 tests/test_concern_parser.py   # or: bash tests/run_all_python_tests.sh
   ```
5. **Registration lands in the greeting:** the shadow greeting is derived from
   Step 3, so confirm the new bullet is present in `SKILL.md` Step 3 and reads as
   a single short capability phrase.
6. **(Optional follow-up) live manual verification** — per the task's
   Verification note (cf. t1053): launch a completed task's agent, invoke the
   implementation review, confirm the emitted block parses and forwards via
   minimonitor's concern picker, and confirm the shadow stayed advisory-only.
   Offered as a standalone manual-verification task at Step 8c, not done inline.

## Post-Implementation

Follow **Step 9** of the shared task-workflow: user review → commit (code files
via `git`; this task touches no `aitasks/`/`aiplans/` files except the plan, which
commits via `./ait git`) → gate run (`risk_evaluated`) → archive.

## Post-Review Changes

### Change Request 1 (2026-07-05 09:25)
- **Requested by user:** Also update the website documentation for the shadow
  agent skill and associated workflow docs to cover the new implementation-review
  capability.
- **Changes made:** Added a new "Review the implementation" section to the shadow
  agent workflow page (its own capability, distinct from plan review — reviews the
  real diff / working-tree state + Final Implementation Notes, with the too-early
  gate); threaded implementation review into the concern-forwarding section and
  the page's frontmatter description; updated the workflows `_index.md` shadow
  bullet; and broadened the two minimonitor how-to enumerations (shadow summary +
  concern-picker trigger) to include implementation review.
- **Files affected:** `website/content/docs/workflows/shadow-agent.md`,
  `website/content/docs/workflows/_index.md`,
  `website/content/docs/tuis/minimonitor/how-to.md`.

### Change Request 2 (2026-07-05 09:40)
- **Requested by user (live test of the shadow impl-challenge):** two concerns +
  a picker symptom.
- **Concern 1 (archived-plan fallback) — valid, fixed:** `impl-challenge.md`
  resolved the plan only via `aitask_shadow_context.sh`, which returns only the
  *active* plan and never scans the archive, so a committed/archived task tripped
  the "too early" gate and missed the archived plan's Final Implementation Notes.
  Added an archived-plan fallback (`aiplans/archived/p<N>_*.md` /
  `aiplans/archived/p<parent>/p<parent>_<child>_*.md`) to input 1 and gated the
  too-early warning behind it.
- **Concern 2 (over-broad verification grep) — valid, fixed:** the `grep -rn
  shadow_concern_format .` verification also matched legitimate historical/data
  records (`.aitask-data/` task+plan descriptions, `.aitask-explain/` cache,
  `.aitask-history/`), so "must print nothing" was false even with source refs
  correctly repointed. Scoped the grep to `.claude/skills/ .aitask-scripts/
  aidocs/framework/ tests/ website/`.
- **Picker symptom (minimonitor `c` showed an earlier block, not the new impl
  concerns):** analysis — capture *depth* is not the cause (the tail capture always
  includes the freshly-emitted block; a deeper window only adds older lines).
  For an older block to win, the new block's `===AITASK-CONCERNS===` fence must be
  absent from the pane — i.e. the shadow did not emit the fenced block (or emitted
  trailing content after it) on that run. Hardened `impl-challenge.md` to emit the
  concern block as the **final** output with nothing after it. Did **not**
  guess-patch minimonitor/parser; a definitive fix there is gated on confirming
  whether the block was actually emitted on the failing run.
- **Files affected:** `.claude/skills/aitask-shadow/impl-challenge.md`,
  `aiplans/p1119_shadow_implementation_challenge_subprocedure.md` (verification).

### Change Request 3 (2026-07-05 10:05) — picker mis-parse root cause + shared fix
- **User confirmed the fenced block WAS emitted, yet `c` forwarded a different
  (older/template) block.** Reproduced deterministically against `concern_parser`:
  the shadow sub-procedure docs embed a **literal, parser-live** example concern
  block. Because the shadow reads/quotes these docs at runtime, the example lands
  in the shadow pane, and minimonitor (which parses the *whole* pane, last block
  wins via `rfind`) can select the doc's placeholder items — exactly the
  "concerns written before" symptom.
- **Latent shared bug (t1037), not impl-challenge-specific.** Enumerated the full
  surface: 4 runtime-read docs were parser-live — `impl-challenge.md`,
  `plan-challenge.md`, `plan-assumptions.md`, `plan-diagnose-errors.md`.
  (`concern-format.md` was only *accidentally* safe.)
- **Structural fix (all 4):** present the format WITHOUT a contiguous
  `open→items→close` block — name the exact sentinels inline (`===AITASK-CONCERNS===`
  / `===END-CONCERNS===`) and show the `- [priority | region] body` item lines
  separately. No parser/minimonitor logic changed; the agent still learns the
  exact literals. Also hardened `impl-challenge.md` to emit the real block as the
  final output.
- **Guard test (enforces the convention):** `TestShadowDocsNotParserLive` in
  `tests/test_concern_parser.py` scans every `.claude/skills/aitask-shadow/*.md`
  and asserts none is `has_concern_block`-live, so a future edit cannot silently
  reintroduce the hazard. Suite now 13/13.
- **Scope note (explicit):** this fix touches three t1037-owned sibling docs
  beyond t1119's original "add impl-challenge + relocate doc" charter, because a
  correct fix must cover the whole shared surface (half-fixing impl-challenge
  alone would leave the other three hazardous). No cross-agent port needed
  (Claude-only sub-procedures).
- **Files affected:** `.claude/skills/aitask-shadow/impl-challenge.md`,
  `plan-challenge.md`, `plan-assumptions.md`, `plan-diagnose-errors.md`,
  `tests/test_concern_parser.py`.

## Final Implementation Notes
- **Actual work done:** Added `.claude/skills/aitask-shadow/impl-challenge.md`
  (adversarial implementation review: task+plan+real-diff/working-tree +
  Final Implementation Notes, too-early gate with archived-plan fallback, same
  `===AITASK-CONCERNS===` output). Relocated the concern-format SoT doc to
  `.claude/skills/aitask-shadow/concern-format.md` (ships to installs), deleted
  `aidocs/framework/shadow_concern_format.md`, and repointed all 8 references +
  the new file. Registered impl-challenge in `SKILL.md` Step 3. Added website
  docs for the new capability. Root-caused and fixed a live picker mis-parse.
- **Deviations from plan:** (1) Website docs (shadow-agent workflow page,
  workflows `_index.md`, minimonitor how-to) added at user request (CR1).
  (2) Scope expanded to fix a **pre-existing t1037 latent bug**: the shadow
  sub-procedure docs embedded parser-live example concern blocks that minimonitor
  could forward as real concerns. Fixed across all 4 runtime-read docs
  (`impl-challenge`, `plan-challenge`, `plan-assumptions`, `plan-diagnose-errors`)
  by presenting the format with inline sentinels + separate item lines, plus a
  guard test (`TestShadowDocsNotParserLive`). (3) Added an archived-plan fallback
  and scoped the verification grep (CR2).
- **Issues encountered:** The picker forwarded template placeholders ("concerns
  written before") because `concern_parser` scans the whole shadow pane
  (last-block-wins) and the docs' literal examples were themselves parseable
  blocks. Reproduced deterministically, then removed the hazard at the source.
  Capture *depth* was ruled out (the freshly-emitted block always sits at the
  pane tail). No `concern_parser.py`/minimonitor logic was changed.
- **Key decisions:** Delete-and-redirect the concern doc (single SoT) over a
  thin-pointer stub. Fix the parser-live hazard structurally (doc presentation +
  enforcing guard test) rather than a fragile ordering trick or a minimonitor
  patch that cannot distinguish a real emission from a quoted example.
- **Upstream defects identified:** The parser-live-example hazard was a
  pre-existing defect in the t1037 shadow concern infrastructure (present since
  `plan-challenge.md` shipped), not seeded by this task — it was fixed here in
  full rather than deferred. None other.
- **Manual-verification failure:** item "Launch a completed task's agent + shadow; ask "review the implementation" and confirm the emitted ===AITASK-CONCERNS=== block forwards via minimonitor's 'c' picker showing the REAL concerns (not the doc's placeholder example" failed; follow-up task t1123.
