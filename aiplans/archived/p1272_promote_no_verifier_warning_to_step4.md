---
Task: t1272_promote_no_verifier_warning_to_step4.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1272 — Promote the "no verifier configured" warning into the Step-4 parse contract

## Context

t635_34 added an early warning at task-claim time: when a task's **enforced**
active-gate set contains a gate that can never be satisfied (no registry entry,
or a machine command gate with no `verifier`), `aitask_gate.sh
materialize-active` emits a `Warning:` line. That gate will block Step-9
archival forever, so the user needs to know at pick time.

The warning goes to **stderr only** — deliberately, to take zero render/goldens
blast radius at the time. But no skill instructs the agent to surface it, so an
agent may see it in tool output and never pass it on. That is the
goal-achievement risk recorded in p635_34, and this task is its "after"
mitigation: document the warning in the parse contract so surfacing it becomes a
skill instruction rather than a hope.

The task's stated precondition ("verify the `output_branch` work has cleared")
is **satisfied** — `.claude/skills/task-workflow/SKILL.md`,
`tests/golden/procs/task-workflow/`, and all nine tracked `*-remote-*` prerender
trees are clean, and the git index is empty.

### Scope extension agreed during planning

The task's Scope names only `task-workflow/SKILL.md`. Planning found the parse
contract is **duplicated**: `.claude/skills/aitask-pickrem/materialize-active.md`
carries the same five bullets and states it "mirrors the attended workflow's
Step 4". t635_34's recorded risk — quoted in this task's own Origin — is that the
warning "reaches **every lane** via stderr, but no skill instructs the agent to
surface it", and the remote lane is where an unsurfaced warning is least likely
to be noticed. The user confirmed **both surfaces** are in scope. Implementation
step 0 updates the task file's Scope section to record this before any code
changes (no silent AC deviation).

### Facts established during planning

- Emission site: `_warn_unverifiable_active` at `.aitask-scripts/aitask_gate.sh:758-772`,
  called on both the `NOOP` path (line 885) and the `MATERIALIZED` path (line 907).
- `warn()` (`.aitask-scripts/lib/terminal_compat.sh:21`) prefixes `Warning: ` and writes to stderr.
- Full emitted text:
  `Warning: materialize-active: active gate '<gate>' has <reason> in <registry> — it will block archival. Run \`ait gates sync-registry\` to reconcile the registry.`
- `<reason>` has **two** variants, from `gate_ledger.unverifiable_reason`
  (`.aitask-scripts/lib/gate_ledger.py:1137-1158`): `no verifier configured` and
  `no registry entry`. The task text names only the first; the bullet must cover both.
- Target blocks are both **Jinja-free** in the region being edited, so the
  addition renders identically in every profile:
  `.claude/skills/task-workflow/SKILL.md:209-224` and
  `.claude/skills/aitask-pickrem/materialize-active.md:12-35`.
- `aitask_skill_rerender.sh remote` re-renders **38 (skill, agent) pairs**; **9
  trees are git-tracked** (`task-workflow`, `aitask-pickrem`, `aitask-pickweb` ×
  claude/codex/opencode). This breadth is why step 4 below uses a hard allowlist.
- `aitask-pickrem`'s only golden is `tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md`,
  which renders `SKILL.md.j2` — **not** `materialize-active.md`. So the pickrem
  edit changes no golden.

## Implementation

### 0. Record the scope extension in the task file (first, before any edit)

Append the `aitask-pickrem/materialize-active.md` surface to the task's `## Scope`
item 1 and to its `## Verification` list, then commit via `./ait git` (task data
lives on the aitask-data branch — never mix it with the code commit):

```bash
./ait git add aitasks/t1272_promote_no_verifier_warning_to_step4.md
./ait git commit -m "ait: Extend t1272 scope to the aitask-pickrem mirrored contract"
```

### 1. Add the bullet to `.claude/skills/task-workflow/SKILL.md`

In Step 4's "Materialize the active-gates tuple" block, append one bullet to the
end of the `Parse the single stdout line:` list — immediately after the existing
`Nonzero exit` bullet (currently line 220), **outside any Jinja conditional**:

```markdown
  - **Also on stderr (advisory — not part of the stdout status line):** a
    `Warning: materialize-active: active gate '<gate>' has no verifier configured in <registry> — it will block archival.`
    line (or its `… has no registry entry in <registry> …` variant) means an
    **enforced** gate can never be satisfied, so the Step-9 archival guard will
    hold the task in-flight indefinitely. The exit status is still 0 and stdout
    still reports `MATERIALIZED:` / `NOOP:` — **continue** — but **surface the
    warning to the user** and suggest `ait gates sync-registry` to reconcile the
    registry. Same warn-and-continue shape as `MATERIALIZED_UNCOMMITTED` /
    `NOOP_UNCOMMITTED` above; the exit-code contract is unchanged (a nonzero exit
    still aborts).
```

### 2. Add the mirrored bullet to `.claude/skills/aitask-pickrem/materialize-active.md`

Same semantics, adapted to that file's voice (the remote lane is
non-interactive — it *displays*, there is no user to prompt). Append after its
`Nonzero exit` bullet (currently ends line 35):

```markdown
- **Also on stderr (advisory — not part of the stdout status line):** a
  `Warning: materialize-active: active gate '<gate>' has no verifier configured
  in <registry> — it will block archival.` line (or its `… has no registry entry
  …` variant) means an **enforced** gate can never be satisfied, so the Step 10
  archival guard will hold the task in-flight indefinitely. The exit status is
  still 0 and stdout still reports `MATERIALIZED:` / `NOOP:` — **continue** — but
  **display the warning verbatim in the run output** and note that
  `ait gates sync-registry` reconciles the registry. Same warn-and-continue shape
  as `MATERIALIZED_UNCOMMITTED` / `NOOP_UNCOMMITTED` above; the exit-code
  contract is unchanged (a nonzero exit still aborts).
```

Neither edit touches exit-code semantics (task Scope item 2).

### 3. Regenerate the three `task-workflow` SKILL.md goldens

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/SKILL.md \
    "aitasks/metadata/profiles/$profile.yaml" claude \
    > "tests/golden/procs/task-workflow/SKILL-${profile}.md"
done
```

The golden diff MUST be the added bullet and nothing else, identical in all
three files (the block is Jinja-free). No `aitask-pickrem` golden changes.

### 4. Refresh the committed remote prerenders — with a hard allowlist gate

```bash
./.aitask-scripts/aitask_skill_rerender.sh remote
```

Because that sweep touches 38 render targets across 9 tracked trees, a
concurrent session's template edit can produce tracked drift in the same run.

Containment is **one executable gate script**, not a set of prose checks. Every
detection exits **nonzero**, and staging happens *inside* the same guarded script
so there is no window in which a detected problem can be stepped past. Write it
to the scratchpad and run it with `bash`; only proceed to step 5 if it exits 0
and prints `GATE_OK`.

```bash
#!/usr/bin/env bash
set -euo pipefail

# The allowlist paths are repo-relative; the script lives in the scratchpad.
cd "$(git rev-parse --show-toplevel)"

ALLOWLIST=(
  .claude/skills/task-workflow/SKILL.md
  .claude/skills/aitask-pickrem/materialize-active.md
  tests/golden/procs/task-workflow/SKILL-default.md
  tests/golden/procs/task-workflow/SKILL-fast.md
  tests/golden/procs/task-workflow/SKILL-remote.md
  .claude/skills/task-workflow-remote-/SKILL.md
  .agents/skills/task-workflow-remote-codex-/SKILL.md
  .opencode/skills/task-workflow-remote-/SKILL.md
  .claude/skills/aitask-pickrem-remote-/materialize-active.md
  .agents/skills/aitask-pickrem-remote-codex-/materialize-active.md
  .opencode/skills/aitask-pickrem-remote-/materialize-active.md
)

# (a) The index must be empty. A non-empty index means another session staged
#     work; a shared index cannot be safely partitioned. ABORT.
if [ -n "$(git diff --cached --name-only)" ]; then
  echo "ABORT: index not empty before staging — another session staged:" >&2
  git diff --cached --name-only >&2
  exit 1
fi

# (b) Stage exactly the allowlist. No globs, no `git add -A`, no directory adds.
#     `set -e` makes a missing path abort here rather than silently under-stage.
git add -- "${ALLOWLIST[@]}"

# (c) The staged set must EQUAL the allowlist — no more, no fewer. ABORT on drift.
if ! diff <(git diff --cached --name-only | sort) \
          <(printf '%s\n' "${ALLOWLIST[@]}" | sort); then
  echo "ABORT: staged set != allowlist (see diff above)" >&2
  exit 1
fi

# (d) The change is a pure insertion in every one of the 11 files (verified:
#     the golden baseline is green at 181/181, so regeneration only inserts).
#     Any deletion line is therefore foreign — a concurrent edit to an
#     allowlisted file, which (b)'s whole-file staging would otherwise sweep in.
#     (Captured to a variable rather than piped into `if`: with `pipefail` a
#     SIGPIPE from an early-exiting `grep -q` would itself trip the condition.)
dels="$(git diff --cached -U0 | grep -E '^-' | grep -v '^---' || true)"
if [ -n "$dels" ]; then
  echo "ABORT: staged diff contains deletions — expected pure insertion:" >&2
  printf '%s\n' "$dels" >&2
  exit 1
fi

echo "GATE_OK"
```

**(e) Final hunk read (backstop, not automatable).** Gate (d) catches a foreign
*deletion* in an allowlisted file but not a foreign pure *addition* to one. So
after `GATE_OK`, read `git diff --cached` in full and confirm every staged hunk
is the new bullet (in the two authoring files) or its rendered copy (goldens,
prerenders). Anything else → `git restore --staged` that path, stop, and report.
Do not commit on an unresolved hunk.

### 5. Commit (single commit — both templates + goldens + prerenders)

Per `aidocs/framework/skill_authoring_conventions.md`, goldens and the template
edit land in the same commit. Use the task's `issue_type` (`enhancement`):

```
enhancement: Document the no-verifier warning in the materialize-active parse contract (t1272)
```

## Verification

1. The bullet renders in **all three** task-workflow profiles and is not
   profile-conditional:
   ```bash
   for p in default fast remote; do
     grep -c "Also on stderr" "tests/golden/procs/task-workflow/SKILL-${p}.md"
   done   # must print 1, 1, 1
   ```
2. It reached all six committed remote prerenders:
   ```bash
   grep -l "Also on stderr" \
     .claude/skills/task-workflow-remote-/SKILL.md \
     .agents/skills/task-workflow-remote-codex-/SKILL.md \
     .opencode/skills/task-workflow-remote-/SKILL.md \
     .claude/skills/aitask-pickrem-remote-/materialize-active.md \
     .agents/skills/aitask-pickrem-remote-codex-/materialize-active.md \
     .opencode/skills/aitask-pickrem-remote-/materialize-active.md
   ```
   must list all six.
3. `bash tests/test_skill_render_task_workflow.sh` — passes (Test 1's golden
   `assert_eq` is what catches a stale golden).
4. `./.aitask-scripts/aitask_skill_verify.sh` — passes.
5. The step-4 gate script exited **0** and printed `GATE_OK` (a nonzero exit is
   a hard stop, not a warning), and the step-4e hunk read found only expected
   hunks.
6. `git show --stat HEAD` on the code commit lists exactly the 11 allowlisted
   paths.

**Note for Final Implementation Notes:** the duplicated parse contract (two
hand-maintained copies of the same five-bullet list, now six) is a pre-existing
drift hazard with no guard. Record it under "Upstream defects identified" — it is
a candidate for a canonical-site + drift-guard follow-up, out of scope here.

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`, `create_worktree: false`) — no worktree or
branch cleanup. Merge target resolves from the plan header. The `risk_evaluated`
gate is the task's only active gate; the Step-9 orchestrator records it.

## Risk

### Code-health risk: low
- The rerender in step 4 is a repo-wide `remote`-profile sweep across 38 render
  targets and 9 tracked trees, so a concurrent session's template edit — or an
  unrelated edit to one of the 11 allowlisted files — could be swept into this
  commit. · severity: low (residual — addressed by inline pre-phase
  allowlist_containment_gate, which fails closed on both path and hunk drift)
  · → mitigation: inline pre-phase allowlist_containment_gate
- Documentation-only edits to Jinja-free regions; no executable code, no
  exit-code semantics, and every rendered artifact is mechanically derived. · severity: low
  · → mitigation: none
- The change adds a sixth bullet to a contract that is duplicated in two
  hand-maintained files, deepening an existing drift hazard. · severity: low
  · → mitigation: none here — recorded as an upstream observation for a
  canonical-site + drift-guard follow-up

### Goal-achievement risk: low
- The emitted warning has two reason variants (`no verifier configured`,
  `no registry entry`); documenting only the one named in the task text would
  leave the second undocumented and the agent silent about it. · severity: low
  · → mitigation: none needed — both bullets cover both variants explicitly
- The task's written Scope named one of two agreeing surfaces; implementing it
  literally would have left the remote lane — the lane the original risk called
  out — undocumented. · severity: low (residual — resolved during planning: the
  user confirmed both surfaces and step 0 records the extension in the task
  file) · → mitigation: none
- Every scope item has a direct executable check, so "did it land in all
  profiles and all lanes" is decidable rather than assumed. · severity: low
  · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: allowlist_containment_gate | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: rerender sweep can include concurrent sessions' generated drift | desc: perform staging inside a single `set -euo pipefail` gate script that exits nonzero on a non-empty index, a missing path, staged-set != allowlist, or any deletion line, followed by a manual hunk read as the pure-addition backstop

### Pre-phase (risk mitigations)
1. [allowlist_containment_gate] Write the gate script from Implementation step 4
   to the scratchpad. It carries `set -euo pipefail` and **performs the staging
   itself**, so no detection can be stepped past: every check `exit 1`s rather
   than printing a sentinel and returning success.
2. [allowlist_containment_gate] Run it with `bash`. It must exit 0 and print
   `GATE_OK`. Any nonzero exit → stop; do not stage further and do not commit.
   The four in-script aborts are: non-empty index (a), a missing allowlist path
   (b, via `set -e` on `git add`), staged-set ≠ allowlist (c), and any deletion
   line in the staged diff (d).
3. [allowlist_containment_gate] After `GATE_OK`, read `git diff --cached` in
   full as the backstop for a foreign *pure addition* to an allowlisted file —
   the one drift shape (d) cannot see. `git restore --staged` anything
   unexpected, stop, and report.
4. [allowlist_containment_gate] Only then run the commit in step 5. If the gate
   was re-run after a fix, it must print `GATE_OK` again first.

## Final Implementation Notes

- **Actual work done:** Added the stderr warn-and-continue bullet to **two**
  agreeing parse contracts — `.claude/skills/task-workflow/SKILL.md` Step 4
  (single-line bullet, matching that list's style) and
  `.claude/skills/aitask-pickrem/materialize-active.md` (wrapped, matching that
  file's style, and worded for the non-interactive lane: *display* rather than
  *surface to the user*). Both cover **both** `unverifiable_reason` variants
  (`no verifier configured`, `no registry entry`). Regenerated the 3
  `tests/golden/procs/task-workflow/SKILL-*.md` goldens and refreshed the 6
  committed remote prerenders via one `aitask_skill_rerender.sh remote` call.
  Final: 11 files, 51 insertions, 0 deletions, one commit.

- **Deviations from plan:** None in execution. The plan itself deviated from the
  task's written Scope in two user-approved ways, both recorded in the task file
  before implementation (scope items 1b and 3b): (1) the `aitask-pickrem` mirror
  was added to scope after planning found the parse contract duplicated;
  (2) staging was hardened into a fail-closed gate script after the user
  rejected the first two plan revisions.

- **Issues encountered:**
  - *Two plan rejections, both correct.* The first draft named only
    `task-workflow/SKILL.md`; verifying the user's containment concern is what
    surfaced the duplicated contract in `aitask-pickrem/materialize-active.md`.
    The second draft's "gate" was `... || echo SENTINEL`, which returns 0 — a
    detection, not a gate. Replaced with a single `set -euo pipefail` script
    that **performs the staging itself** so no check can be stepped past.
  - *The gate was not theoretical.* At staging time a concurrent session had 8
    worktree-modified `aitask-trail` files (`SKILL.md.j2`, 3 goldens, 4 source
    files). A broad `git add`/`git status` review would plausibly have swept
    them in. The path-explicit staging left all 8 unstaged, and check (c)
    confirmed the staged set equalled the 11-path allowlist exactly.
  - *Check (c) is a positive assertion, not just a negative one.* Because
    staging is path-explicit, (c) can only fail if an allowlisted path did **not**
    change — so its passing proves all 11 files were actually modified, catching
    a rerender that silently missed a target.
  - *`pipefail` interaction.* The deletion check (d) was written as a captured
    variable rather than a pipeline in an `if` condition: with `set -o pipefail`,
    a SIGPIPE from an early-exiting `grep -q` would itself trip the condition and
    produce a false abort.

- **Key decisions:**
  - Bullet placed **last** in the stdout-parse list and lead with "Also on
    stderr" — the list is introduced as "Parse the single stdout line", so the
    stream distinction has to be the first thing read.
  - Kept the exit-code contract untouched (task Scope item 2): advisory warning
    → continue; nonzero exit → still abort. Stated explicitly in both bullets so
    a future editor cannot read the addition as a new abort condition.
  - Each surface got prose in **its own voice** rather than a copy-paste: the
    attended lane surfaces to a user, the remote lane displays into run output,
    and their archival steps differ (Step 9 vs Step 10).

- **Upstream defects identified:**
  `.claude/skills/aitask-pickrem/materialize-active.md:12-46 — the materialize-active stdout-parse contract is duplicated verbatim-in-substance from .claude/skills/task-workflow/SKILL.md Step 4 (now 6 bullets each), hand-maintained in both files with no drift guard. This task's own planning only found the second copy incidentally, while verifying an unrelated concern; t635_34 shipped its warning into neither. A canonical-site + drift-guard follow-up (shared include, or a test asserting bullet-set parity) would prevent the next contract change from landing in one lane only.`
