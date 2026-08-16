---
Task: t1263_docs_updated_gate_changesurface_has_no_pertask_attribution.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1263 — Per-task attribution for the `docs_updated` gate's change surface

## Context

`.claude/skills/aitask-gate-docs-updated/SKILL.md` §2 gathers the gated task's
change surface with three raw git commands:

```bash
git log -F --grep="(t<task-id>)" ...     # committed — correctly task-scoped
git diff --name-only HEAD                # uncommitted — NOT task-scoped
git ls-files --others --exclude-standard # untracked — NOT task-scoped
```

Only the committed half is attributed (by the `(t<id>)` commit tag). Procedure
gates deliberately run at **Step 8, before the review/commit**, so the
uncommitted half is the *primary* signal — and it returns the **entire dirty
tree**. Observed live during the t635_27 verification: four unrelated
pre-existing dirty paths (`.claude/settings.local.json`, `.antigravitycli/`,
`.opencode/package-lock.json`, `aidocs/slack/`) **plus a concurrent session's
syncer edits**, filtered only by agent judgement.

**Impact:** on a shared or busy checkout the gate can infer doc obligations for
another task's change and propose or apply unrelated doc edits, with no
mechanism to notice.

**Outcome:** the gate reasons over a *classified* surface. Only paths with a
real ownership signal drive doc inference; paths provably belonging to other
work are excluded; everything else is surfaced to the user rather than silently
treated as in-scope.

### Why a claim-time baseline is necessary but NOT sufficient

A claim-time snapshot of the working-tree dirty set answers exactly one
question: *was this path already dirty before the task started?* A "yes" is a
**proven negative** — the path is not this task's work.

It cannot produce a positive. Verified against a scratch repo:

```
t1 claims  → baseline = {}          # nothing dirty yet
t1 edits a.md
t2 claims  → baseline = {a.md}
t2 edits b.md                       # concurrent session, AFTER t1's claim
list 1     → dirty = {a.md, b.md}, baseline(t1) = {} ⇒ BOTH are "new"
```

`b.md` is indistinguishable from `a.md` by baseline alone. That is precisely the
second half of the observed incident, so the baseline alone must not be called
attribution.

### The ownership signals

| Signal | Kind | Source |
|---|---|---|
| **P1 — commit tag** | proven positive | path appears in a commit tagged `(t<id>)` |
| **P2 — plan scope** | declared positive | the task's own plan file names the path (fix direction 1) |
| **N1 — claim baseline** | proven negative | path was already dirty when the task was claimed |

Nothing else attributes. A path with no positive signal is **`UNKNOWN:`** and is
escalated, never assumed. Structural (worktree) isolation is deliberately **not**
used as a signal — see "Rejected: worktree inference" below.

---

## Design

| Piece | File | Role |
|---|---|---|
| Attribution engine | `.aitask-scripts/aitask_change_surface.sh` (new) | `capture` / `list` verbs — the canonical "what did task t\<id\> change?" scanner |
| Baseline capture (N1) | `.aitask-scripts/aitask_pick_own.sh` | calls `capture` on a **fresh** claim (Step 4) |
| Consumer | `.claude/skills/aitask-gate-docs-updated/SKILL.md` §2/§4 | calls `list`, uses the classes, escalates `UNKNOWN:` |

### Pre-phase (risk mitigations)

1. `[bound_claim_path_cost]` Before wiring `capture` into `aitask_pick_own.sh`,
   pin its placement and cost: put the call at the very **end** of `main()`
   (after the `RECLAIM_*` signal block, not before `echo "OWNED:"`), with
   stdout+stderr redirected and `|| true`. Measure claim latency with and
   without the call on this repo and record both numbers in the Final
   Implementation Notes. Add a test assertion that the `OWNED:` / `RECLAIM_*`
   stdout of `aitask_pick_own.sh` is **byte-identical** with capture enabled and
   with the helper absent, so the claim path's output contract is pinned.

### 1. `aitask_change_surface.sh` (new helper)

Follows `aitask_query_files.sh`'s shape: `set -euo pipefail`, sources
`lib/terminal_compat.sh` + `lib/task_utils.sh`, all subcommands exit 0, status
carried by **output lines**.

**`capture <task-id>`** — writes `.aitask-gates/<task-id>/change_baseline`
atomically via `lib/atomic_write.sh::ait_atomic_write_text`:

```
version=1
task=1263
toplevel=/home/ddt/Work/aitasks
head=<sha>
captured_at=2026-08-16T09:12:44Z
paths:
.claude/settings.local.json
.opencode/package-lock.json
```

`paths:` is the sentinel; everything after it is the dirty ∪ untracked set at
capture time (signal N1). Prints `CAPTURED:<n-paths>`, or
`CAPTURE_SKIPPED:<reason>` when git is unavailable / the repo has no commits.
`.aitask-gates/` is already gitignored (`.gitignore`, seeded by
`aitask_setup.sh:1957`), so this is local-only ephemeral state.

**`list <task-id>`** — prints **two** header lines naming which signals were
available, then the tagged-commit set, then one classified line per dirty path:

```
BASELINE:ok|missing|foreign      # N1 available?
PLANSCOPE:ok|missing             # P2 available?
COMMITTED:<path>                 # P1 — proven this task's
TASK:<path>                      # P2 and not N1 — declared this task's
OTHER:<path>                     # N1 and not P2 — proven other work
UNKNOWN:<path>                   # no positive signal, or signals conflict
```

Both headers are always printed: a missing signal is its own state, not a
silent negative. The consumer must not treat `PLANSCOPE:missing` as "nothing is
this task's".

**Emission is two independent passes, in this order:**

**Pass A — the tagged-commit set (P1), emitted unconditionally.** Every path in
a commit tagged `(t<id>)` is emitted as `COMMITTED:`, **whether or not it is
currently dirty**. A task that committed code earlier in the session and left
that file clean still contributes it to doc inference — that is what the
original skill did (`git log -F --grep` is independent of the dirty scan) and it
must not regress. This pass does not consult the dirty set at all.

**Pass B — the dirty ∪ untracked set, classified.** Paths already emitted in
Pass A are **skipped** (de-duplication: `COMMITTED:` is the strongest signal, so
a path that is both tagged-committed and dirty is reported once, as
`COMMITTED:`). Each remaining path is emitted exactly once, first match wins:

| # | Condition | Class |
|---|---|---|
| 1 | P2 **and** N1 (plan names it, but it was already dirty at claim) | `UNKNOWN:` — signals conflict, never guess |
| 2 | P2 | `TASK:` |
| 3 | N1 | `OTHER:` |
| 4 | neither | `UNKNOWN:` — appeared after the claim, unnamed by the plan |

Row 4 is what closes the concurrent-session hole: another session's post-claim
edit has no positive signal, so it lands in `UNKNOWN:` and is escalated or
excluded — never silently attributed. Row 1 applies the same rule to a genuine
conflict rather than picking a winner.

Pass A is unaffected by either header. Within Pass B, `BASELINE:missing` (a task
claimed before this feature shipped) makes rows 1 and 3 unavailable — P2 still
attributes, everything else is `UNKNOWN:`. `PLANSCOPE:missing` makes rows 1 and
2 unavailable — the surface degrades to `OTHER:` / `UNKNOWN:`, which escalates
rather than misattributes.

**P2 — plan-scope extraction. Exact file matches only.** Resolve the plan via
`lib/task_utils.sh::resolve_plan_file` (line 1196 — handles parent, child and
archived plans). From its text extract candidate path tokens with a **portable
ERE** (`grep -oE`, never `grep -P` — see `sed_macos_issues.md`), strip wrapping
backticks / quotes / trailing punctuation, normalize a leading `./`, and keep a
token **only if it names an existing regular file** (or a path that is currently
dirty/untracked — a file the plan creates does not exist until it does). A dirty
path is in scope **only when it equals a token exactly**.

**Directory tokens never attribute.** A plan legitimately names broad
directories in prose — this very plan yields `.aitask-scripts/`, `tests/`,
`.claude/`, `seed/`, `aidocs/framework/` — and treating them as recursive scope
prefixes would attribute nearly the whole repo, reopening the exact
shared-checkout failure this task exists to close. Directory tokens are
therefore **discarded during extraction**. A dirty file beneath a plan-named
directory but not itself named falls to Pass B row 4 (`UNKNOWN:`) and is
escalated; the escalation text may *mention* the enclosing plan-named directory
as the reason it is plausible, but that never promotes it to `TASK:`. Recursive
ownership is not inferable from prose, so it is not inferred.

Prose that does not name a real file never enters scope.

**Tokens are compared as fixed strings, never as patterns.** Plan text is
agent/user-authored; every comparison binds the token to a variable and uses
`[[ "$p" == "$tok" ]]` / `grep -F`, never `eval`, never a token interpolated
into a regex. A plan containing `.*` or `$(id)` must be inert.

**Excluded from every listing:** `aitasks/**`, `aiplans/**`, `.aitask-data/**` —
the same set `gate_ledger.py::_DIGEST_EXCLUDES` (line 1538) uses. Defined once
as a named array with a comment naming that canonical site; a drift guard in the
test compares the two lists so they cannot silently diverge.

**Rejected: worktree inference.** An earlier draft classified everything as
`TASK:` when the tree was a linked worktree on an `aitask/*` branch. That is an
*inference* about how the worktree was created, not a proof — a reused or
hand-made linked worktree can hold foreign dirt, and it would bypass the
`UNKNOWN:` escalation entirely. Dropped. In a task worktree the plan-scope
signal does the work, and unnamed dirt escalates like anywhere else. Proving
freshness would need framework-created-worktree metadata written at
task-workflow Step 5; that is the spawned `worktree_freshness_metadata`
mitigation below.

**Whitelisting** (7-touchpoint checklist,
`aidocs/framework/aitasks_extension_points.md`):

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_change_surface.sh
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_change_surface.sh   # must print nothing
```

Touchpoints 1/3/4/6/7: `.claude/settings.local.json`,
`.codex/rules/default.rules`, `seed/claude_settings.local.json`,
`seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`. **No `ait`
dispatcher entry** — nobody types this at a prompt.

### 2. Baseline capture at claim time — `aitask_pick_own.sh`

At the **end** of `main()` (after the `RECLAIM_*` block, per the pre-phase
above), on a **fresh** claim only:

```bash
# Fresh claim only: a reclaim/resume must keep the original baseline, or this
# session's own in-progress work would be re-baselined as "other work".
if [[ "$prev_status" != "Implementing" ]]; then
    "$SCRIPT_DIR/aitask_change_surface.sh" capture "$TASK_ID" >/dev/null 2>&1 || true
fi
```

`prev_status` is already computed at line 413. Best-effort per
`shell_conventions.md` — a capture failure must never fail a claim; it degrades
to `BASELINE:missing`. Stale baselines self-heal: every fresh claim (including
after an abort → `Ready` → re-pick) rewrites the file.

### 3. `aitask-gate-docs-updated/SKILL.md` — consume the classified surface

Replace §2 ("Gather the change surface") with a call to the helper and state the
attribution rule:

- In-scope for doc inference = `COMMITTED:` + `TASK:`.
- `OTHER:` — **never** in scope; do not mention it in the proposal.
- `UNKNOWN:` — when non-empty:
  - **Interactive:** before proposing any doc edits, present the paths via
    `AskUserQuestion` — "Include all" / "Choose a subset" (`multiSelect`) /
    "Exclude all". Only chosen paths join the in-scope set. Name *why* each is
    unknown (appeared after the claim and unnamed by the plan / conflicting
    signals) so the choice is decidable from the widget.
  - **Autonomous / non-interactive profiles:** **exclude** them and record
    `attribution=excluded:<n>` plus the path list in the §6 sidecar log.
- Record the full attribution state (both header values, counts per class) in
  the §6 sidecar log line, so a `pass`/`skip` is auditable after the fact.

Add to **MUST NOT**: "Treat an unattributed dirty path as in-scope without the
user's confirmation." The existing "Ignore task/plan data paths" sentence is
dropped — the helper owns that exclusion now.

**No port needed to the other agent trees.**
`.agents/skills/aitask-gate-docs-updated/SKILL.md` and
`.opencode/skills/aitask-gate-docs-updated/SKILL.md` are generated *pointers* to
the Claude body (verified — they contain only a "Source of Truth" redirect); the
body change reaches them for free. The helper whitelist entries are the per-agent
part.

### 4. Docs

- `website/content/docs/skills/aitask-gate-docs-updated.md` — new short section
  after "How it decides what to write": how the skill decides *what your task
  changed*, that it excludes work that was already in progress, and that it asks
  before including paths it cannot attribute. Current-state prose only.
- Helper header comment documents the signal table, the `UNKNOWN:`-is-not-
  negative rule, and the residual limits.

### Post-phase (risk mitigations)

1. `[surface_attributed_set_for_confirmation]` In the gate skill's §4
   confirmation step, present the **`TASK:`-attributed** file list alongside the
   proposed doc edits — not only the `UNKNOWN:` escalation. Plan-scope is a
   *declared* signal, not a proven one: a concurrent edit to a file the plan
   happens to name is classified `TASK:` and is otherwise invisible. Showing the
   attributed set gives the user a chance to catch it before any doc edit lands.

---

## Verification

1. **Fixture — `tests/test_change_surface.sh`** (new). Style follows
   `tests/test_gate_procedure_docs.sh` (`tests/lib/asserts.sh`, `mktemp -d`
   fixture repo, `PASS/FAIL/TOTAL` footer; `assert_counters_init` /
   `assert_counters_load` if any body runs in a `( … )` subshell).

   Base fixture — **two tasks dirty in one tree, interleaved in time**, which is
   the task's stated verification and the shape that exposed the original bug:

   ```
   commit                          # clean tree
   plans: p1 names a.md, p2 names b.md
   capture 1                       # baseline(t1) = {}
   touch/modify a.md
   capture 2                       # baseline(t2) = {a.md}
   touch/modify b.md               # ← concurrent, AFTER t1's claim
   ```

   | Case | Expected |
   |---|---|
   | `list 1` | `TASK:a.md` (P2), `UNKNOWN:b.md` (Pass B row 4) |
   | `list 1` **negative control** | `TASK:b.md` MUST NOT appear — this is the concurrent-after-claim case the baseline cannot assign |
   | `list 2` | `TASK:b.md` (P2), `OTHER:a.md` (N1) |
   | `c.md` dirtied after both claims, in no plan | `UNKNOWN:c.md` for both tasks |
   | `d.md` dirty **before** t3's claim **and** named by p3 | `UNKNOWN:d.md` — conflicting signals; assert it is neither `TASK:` nor `OTHER:` |
   | **p1 names the directory `sub/`; `sub/foreign.md` dirtied by another session** | `UNKNOWN:sub/foreign.md`. **Negative control:** `TASK:sub/foreign.md` MUST NOT appear — directory tokens never attribute |
   | p1 names `sub/mine.md` exactly, both `sub/mine.md` and `sub/foreign.md` dirty | `TASK:sub/mine.md` **and** `UNKNOWN:sub/foreign.md` in the same run |
   | `a.md` committed with `(t1)`, then **left clean** (`git checkout`-clean, not dirty) | `COMMITTED:a.md` still emitted — Pass A is independent of the dirty scan. **Negative control:** a task whose only contribution is a clean tagged commit must not return an empty surface |
   | `a.md` committed with `(t1)` **and** still dirty | `COMMITTED:a.md` exactly once; assert no second line for `a.md` in any class |
   | untracked file in plan scope | classifies identically to a modified one |
   | task with **no plan file** | `PLANSCOPE:missing`; no path is ever `TASK:` |
   | baseline absent | `BASELINE:missing`; P2 still yields `TASK:`, all else `UNKNOWN:` |
   | baseline with a rewritten `toplevel` | `BASELINE:foreign` ⇒ same as missing |
   | linked worktree on `aitask/x`, no baseline | `BASELINE:missing`; unnamed dirt is `UNKNOWN:` — negative control: **no** blanket `TASK:` |
   | plan containing `.*` and `$(id)` as literal text | inert — no path matched by pattern, no command executed |
   | `aitasks/`, `aiplans/`, `.aitask-data/` paths | never appear in any class |
   | **drift guard** | helper's exclude array == `gate_ledger._DIGEST_EXCLUDES` |

2. **Claim seam (prove the writer, not just the reader):** drive
   `aitask_pick_own.sh` in the fixture. A `Ready` claim writes the baseline; a
   second claim while `status: Implementing` leaves it byte-identical. Assert the
   `OWNED:` / `RECLAIM_*` stdout is byte-identical with and without the helper
   present (`bound_claim_path_cost`).
3. **Regression:** `bash tests/test_gate_procedure_docs.sh`; `bash tests/test_pick_own.sh` if present.
4. **Lint:** `shellcheck .aitask-scripts/aitask_change_surface.sh .aitask-scripts/aitask_pick_own.sh`.
5. **Whitelist audit:** `audit-helper-whitelist aitask_change_surface.sh` prints nothing.
6. **Skill surface:** `./.aitask-scripts/aitask_skill_verify.sh`.
7. **Live end-to-end on this checkout** (which is dirty with other sessions'
   work): `./.aitask-scripts/aitask_change_surface.sh list 1263` — this task's
   own files come back `TASK:`/`COMMITTED:`, pre-existing unrelated dirt comes
   back `OTHER:`, and anything a concurrent session touches after the claim comes
   back `UNKNOWN:`. This reproduces the t635_27 scenario end to end, including
   its concurrent half.

---

## Risk

### Code-health risk: medium
- `aitask_pick_own.sh` is the claim path for **every** task pick; adding a subprocess call there puts new work on a load-bearing, universally-executed path. A hang (not just a failure — `|| true` covers failure) would stall claims. · severity: medium · → mitigation: inline pre-phase bound_claim_path_cost
- The exclude set (`aitasks/**`, `aiplans/**`, `.aitask-data/**`) is expressed a second time in bash while `gate_ledger.py::_DIGEST_EXCLUDES` remains the existing Python site — a silent-drift surface. · severity: low · → mitigation: covered by plan (drift guard in `tests/test_change_surface.sh`)
- Plan-scope extraction parses agent-authored prose for path tokens; a sloppy regex could match text that is not a path, interpolate plan text into a pattern, or — the sharpest case — treat a directory named in prose as recursive scope and attribute every dirty file beneath it. · severity: medium · → mitigation: covered by plan (exact file matches only, directory tokens discarded; tokens must resolve against the tree; fixed-string comparison only; directory-token and inert-metacharacter test cases with negative controls)
- The gate SKILL.md rewrite changes behaviour for every `docs_updated`-gated task, and skill prose has no compiler. · severity: low · → mitigation: covered by plan (`aitask_skill_verify.sh` + `tests/test_gate_procedure_docs.sh` regression)

### Goal-achievement risk: medium
- **Plan scope is a *declared* signal, not a proven one.** A concurrent session's edit to a file the plan happens to name is classified `TASK:`. The residual is far narrower than before (it needs a name collision, not merely a dirty tree) but it is real. · severity: medium · → mitigation: inline post-phase surface_attributed_set_for_confirmation
- **Exact-match-only plan scope is deliberately narrow, so `UNKNOWN:` will be non-empty on most real runs** — any file the implementation touched that the plan did not name *by exact path* (including files under a plan-named directory) must be confirmed. In interactive profiles this is a prompt; in autonomous profiles on a *shared* checkout it means a genuine doc obligation could be dropped. This is the accepted trade: over-escalation is recoverable, false attribution is not. · severity: medium · → mitigation: covered by plan (the `UNKNOWN:` prompt states why each path is unknown — including "under plan-named directory X" — and the sidecar log records every exclusion, so a dropped obligation is auditable rather than invisible)
- Worktree isolation — the one signal that could prove ownership structurally — is **not** used, because freshness cannot be proven after the fact. · severity: low · → mitigation: worktree_freshness_metadata

### Planned mitigations
- timing: pre-phase | name: bound_claim_path_cost | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (new work on the universally-executed claim path) | desc: Pin the capture call's placement at the end of main(), measure claim latency with/without, and assert the OWNED:/RECLAIM_* stdout contract is byte-identical.
- timing: post-phase | name: surface_attributed_set_for_confirmation | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risk 1 (plan scope is declared, not proven) | desc: Show the TASK:-attributed file list in the gate skill's §4 confirmation, not only the UNKNOWN: escalation.
- timing: after | name: worktree_freshness_metadata | type: enhancement | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement risk 3 (structural isolation unusable as a signal) | desc: Have task-workflow Step 5 record framework-created-worktree metadata at `git worktree add` time so aitask_change_surface.sh can treat a proven-fresh task worktree as an ownership signal instead of escalating its unnamed dirt. Spawned because it edits the shared task-workflow authoring template and requires goldens regeneration across every profile and agent tree.

---

## Final Implementation Notes

- **Actual work done:** Implemented as planned. New `.aitask-scripts/aitask_change_surface.sh`
  (`capture` / `list`) with the three-signal model (P1 commit tag, P2 exact-file plan
  scope, N1 claim baseline) and the two-pass emission (tagged commits unconditionally,
  then the dirty set classified with those de-duplicated out). `aitask_pick_own.sh`
  captures the baseline at the end of `main()` on fresh claims only.
  `aitask-gate-docs-updated/SKILL.md` §2 rewritten to call the helper, new §2b resolves
  `UNKNOWN:` paths with the user, §4 shows the attributed set (post-phase mitigation),
  §6 logs the attribution state, two MUST NOTs added. Helper whitelisted across all 5
  touchpoints. Website page gained a "How it decides what your task changed" section.
  `tests/test_change_surface.sh`: 50 assertions, all passing.

- **Deviations from plan:** None in design. Two review findings were fixed in-session
  rather than taken as the follow-ups their reviewer disposition suggested, because both
  were cheap and one was actively harmful:
  1. `new_repo` appended to `CLEANUP_DIRS` inside the command substitution of
     `fx="$(new_repo)"`, so the append died in the subshell and every run leaked its
     fixtures (125 stale `/tmp/test_chgsurf_*` dirs found). Replaced with a single
     `FIXTURE_ROOT` created and trapped in the parent shell; stale dirs removed.
  2. The `bound_claim_path_cost` stdout-contract assertion was a text grep of
     `aitask_pick_own.sh`, which would survive a reordering or a broken missing-helper
     path. Replaced with a runtime two-arm comparison (helper copied into the fake repo
     vs. not) over identical state, byte-comparing stdout, with a positive control that
     the claim really produced `OWNED:1` and file-presence assertions so the equality
     cannot be vacuous.

- **Issues encountered:** Three real defects, two found only by running the helper live
  against this checkout rather than against fixtures:
  1. `git show --name-only --format= -- "$sha"` read the SHA as a **pathspec**, so Pass A
     silently returned nothing for every task. Fixed by dropping the `--`. This is
     exactly the clean-committed-file regression the two-pass split exists to prevent,
     and it was invisible while the file was also dirty (plan scope masked it).
  2. The token regex `[A-Za-z0-9_][A-Za-z0-9_./-]*` forbade a **leading dot**, capturing
     `.claude/skills/x/SKILL.md` as `claude/skills/…`, which resolves to nothing. Every
     dot-directory path was permanently unattributable — `.aitask-scripts/`, `.claude/`,
     `.codex/`, `.opencode/`, `.agents/`, i.e. most of this framework. Fixed by admitting
     `.` as a leading character; regression test added.
  3. `current_dirty_set`'s `grep -v '^$'` exits 1 on a clean tree, and under
     `set -o pipefail` that killed `capture` silently inside the command substitution
     (the documented `shell_conventions.md` footgun). Fixed with a trailing `|| true`.

- **Key decisions:**
  - **The baseline produces only a NEGATIVE.** A claim-time snapshot cannot attribute a
    path that appeared after the claim (verified in a scratch repo: t1's baseline is
    empty, so a concurrent `b.md` is indistinguishable from t1's own `a.md`). Positive
    attribution therefore requires the commit tag or the plan, and everything else is
    `UNKNOWN:`. Fix direction 1 was pulled into this task rather than deferred.
  - **Plan scope is exact-file-only; directory tokens are discarded.** Running a
    directory-token extractor over this task's own plan yields `.aitask-scripts/`,
    `tests/`, `.claude/`, `seed/`, `aidocs/framework/` — prefix matching would have
    attributed most of the repo. Two independent defenses (extraction discards
    directories, matching is exact); a mutation test confirmed both must be disabled
    together before the guard fails.
  - **Worktree freshness rejected as a signal.** "Linked worktree on an `aitask/*`
    branch" is an inference about how the tree was created, not a proof, and trusting it
    would bypass the `UNKNOWN:` escalation. Deferred to `worktree_freshness_metadata`,
    which needs metadata written at `git worktree add` time in task-workflow Step 5.
  - **Autonomous profiles exclude `UNKNOWN:` and log it** rather than including it:
    over-escalation is recoverable, false attribution is not.
  - Every guard was proven able to fail by injecting the defect it targets (rejected
    prefix design, Pass A folded into the dirty scan, dotpath regex reverted, fresh-claim
    guard removed).

- **Upstream defects identified:** None.
