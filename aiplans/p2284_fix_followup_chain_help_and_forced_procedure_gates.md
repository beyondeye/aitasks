---
Task: t2284_fix_followup_chain_help_and_forced_procedure_gates.md
Base branch: main
Output branch: main
---

# t2284 — Fix follow-up anchor chaining, forced procedure gates, and stale docs

## Context

The t2258_3 concept-page audit checked facts against the code and found five
defects where the code and its docs disagree. This task fixes all five:

1. **`--followup-of` chains.** `aitask_create.sh --help` says "Flattened — never
   chains", and so do the `aitask-create` skill, `task-creation-batch.md`, and the
   design ("an anchor always points at the topic ROOT", `resolve_anchor()`
   comment). `resolve_anchor()` copies **one hop** of a stored anchor, so it
   chains whenever the anchor it reads is stale. `ait update --anchor` re-anchors
   a task without cascading to its children or follow-ups, so stale anchors arise
   through the normal flow. There are two reachable shapes:
   - **Normally created child.** A child created under anchorless parent 70 stores
     `anchor: 70` (the `--parent` branch). Re-anchor 70 to 42 and the child still
     says 70, so `--followup-of 70_1` copies 70: a chain. (This came from the user
     review; it was reproduced in scratch fixtures.)
   - **Anchorless child (legacy).** The fallback uses the bare parent id even when
     the parent has an anchor, and a longer chain (parent → intermediate → root)
     stops at an intermediate.
   The same one-hop copy is in the `--parent` branch (a child of a parent whose
   anchor is stale inherits the stale value).
   Only `commands/task-management.md:68` (rewritten by t2258_3) documents the
   chaining.
   **Decision: fix the code, not the help text.** Resolve every derived anchor
   (`--followup-of` and `--parent`) through to the actual topic root by
   following `anchor:` links, with cycle protection. That makes the stated
   invariant true for every task these flags create. The help text, the skill, the
   procedure and the design all stay correct, and the one doc sentence that
   describes chaining is rewritten. `--anchor ID` is an explicit user choice and
   stays stored as given, so this fix covers the derived paths only. That also
   matches the doc wording ("rooted at task `ID`").
2. **A forced procedure gate records `error`.** In
   `gate_orchestrator.py` `_force_one`, a `kind: procedure` gate falls through to
   `elif meta.get("verifier")` and runs `_run_machine_gate`. `resolve_verifier`
   maps `aitask-gate-docs-updated` to a non-existent `aitask_gate_docs_updated.sh`,
   so a `running` block and then an `error` block are appended. The unforced path
   excludes procedure gates from `machine` and reports `blocked_reason` →
   "needs agent …", appending nothing.
3. **Stale aidocs.** `skill_authoring_conventions.md`, `stub-skill-pattern.md` and
   `agent_runtime_guards_audit.md` still list `.gemini/` trees and "four agents".
   The real set is claude, codex and opencode (`aitask_skill_verify.sh:116`:
   `agents=(claude codex opencode)`; `.gemini/` does not exist; agy is a future
   agent sharing `.agents/skills`). The verify-script description also needs to
   say what it actually renders: the **default profile only**, plus a walk-verify
   of committed headless prerenders.
4. **`task-format.md:47`** names `ait archive --superseded/--obsolete`. There is
   no `ait archive` verb; the flags belong to `./.aitask-scripts/aitask_archive.sh`.
5. **`crash-recovery.md:71`** says a session re-claiming its own lock "refreshes it
   silently". The refresh itself is silent (no refusal), but
   `aitask_pick_own.sh:782-806` still emits `RECLAIM_STATUS:` when the task is
   already `Implementing` by the same email. So a same-session re-pick still asks
   the anomaly question.

Working on the current branch (`main`), profile `fast`.

## Implementation steps

### 1. Walk to the topic root — `.aitask-scripts/aitask_create.sh`

Add a helper just above `resolve_anchor()`:

```bash
# Follow stored `anchor:` links from task <id> to its topic root and print it:
# the first task on the path with no anchor (or a self-anchor). A hop whose task
# file cannot be resolved is printed as-is: it is the furthest known root, and
# it is what the one-hop copy produced before. A malformed stored anchor stops the
# walk at the current id with a warning. A revisit (a cycle written by hand, or a
# chain of re-anchors that loops) stops at the revisited id with a warning. Ids
# are finite, so the visited set alone guarantees termination; no hop cap is
# needed. Never dies: a malformed graph must not fail a create.
resolve_topic_root() {
    local cur="$1" next file seen=" "
    while :; do
        case "$seen" in
            *" $cur "*) warn "anchor cycle through t$cur — using t$cur as the topic root"; break ;;
        esac
        seen+="$cur "
        file=$(resolve_task_file "$cur" 2>/dev/null || true)
        [[ -n "$file" && -f "$file" ]] || break
        next=$(read_yaml_field "$file" "anchor")
        next="${next#t}"
        [[ -n "$next" && "$next" != "$cur" ]] || break
        if [[ ! "$next" =~ ^[0-9]+(_[0-9]+)?$ ]]; then
            warn "t$cur has a malformed anchor '$next' — using t$cur as the topic root"
            break
        fi
        cur="$next"
    done
    printf '%s\n' "$cur"
}
```

`warn` is in `lib/terminal_compat.sh` (stderr). Check that `aitask_create.sh`
already sources it (it uses `die`). Each `[[ … ]] || break` is a list, so it is
`set -e`-safe. The bare `[[ ! … ]]` sits inside `if`.

Rewrite the two derived branches of `resolve_anchor()`:

```bash
    elif [[ -n "$BATCH_FOLLOWUP_OF" ]]; then
        local src_bare src_parent src_file src_anchor="" start
        src_bare=$(normalize_anchor_id "$BATCH_FOLLOWUP_OF")
        # Walk from the SOURCE itself, so the helper reads and validates its
        # first stored link like every later one. The only exception is an
        # anchorless child: its topic is its parent's, so start there.
        start="$src_bare"
        if [[ "$src_bare" =~ ^([0-9]+)_[0-9]+$ ]]; then
            src_parent="${BASH_REMATCH[1]}"
            src_file=$(resolve_task_file "$src_bare" 2>/dev/null || true)
            if [[ -n "$src_file" && -f "$src_file" ]]; then
                src_anchor=$(read_yaml_field "$src_file" "anchor")
            fi
            [[ -n "$src_anchor" ]] || start="$src_parent"
        fi
        # A stored anchor may be stale (a re-anchor never cascades), so walk it
        # to the root rather than copying one hop.
        RESOLVED_ANCHOR=$(resolve_topic_root "$start")
    elif [[ -n "$BATCH_PARENT" ]]; then
        RESOLVED_ANCHOR=$(resolve_topic_root "${BATCH_PARENT#t}")
    fi
```

`BASH_REMATCH[1]` is captured into `src_parent` straight after its own
`[[ =~ ]]`, before `resolve_task_file` (which runs regexes of its own) is called.
On data without stale links the results are the same as before:
- an anchored source → its anchor;
- a root → itself;
- an anchorless child → its parent (or the parent's root);
- a child of an anchored parent → the parent's anchor.

Both derived paths now enter the walker at a task whose own `anchor:` the helper
reads, so a malformed first link is caught (warning, stop at the source) instead
of being copied verbatim.

Help text (lines 106-109):

```
  --followup-of ID       Anchor this task to the topic root of source task ID:
                         follows ID's anchor (for an anchorless child source,
                         its parent) through to the root, so a stale anchor
                         left by a re-anchor is not copied. Never chains.
```

Update the `resolve_anchor()` header comment to say that the derived paths walk
to the root and `--anchor` stores its value as given.

### 2. Regression tests — `tests/test_anchor_create.sh`

In `test_followup_flatten`, add:
- **Normally created child, then parent re-anchored (the user-review scenario).**
  Seed anchorless `t70` and root `t42`. Create the child for real with
  `aitask_create.sh --batch --silent --parent 70 --name kid --desc x --commit`.
  Assert that it stored `anchor: 70`. Then re-anchor the parent in place with a
  frontmatter edit that adds `anchor: 42` to `t70`, the same non-cascading state
  `ait update --anchor` leaves (the fixture does not ship `aitask_update.sh`).
  Assert `--followup-of 70_1` → `42`.
- **Anchorless child whose parent is anchored to a follow-up (longer chain).**
  Seed `t50` (`anchor: 42`, already seeded), `t80` (`anchor: 50`), and an
  anchorless child `t80/t80_1`. Assert `--followup-of 80_1` → `42`.
- **Stale anchor on a plain follow-up.** Seed `t85` (`anchor: 80`).
  Assert `--followup-of 85` → `42`.
- **Cycle terminates.** Seed `t90` (`anchor: 91`) and `t91` (`anchor: 90`).
  Assert `--followup-of 90` exits 0 and yields `90`, with "anchor cycle" on
  stderr. The walk starts at 90, so 90 is the revisited id.
- **Malformed source anchor.** Seed `t95` with `anchor: bogus`. Assert
  `--followup-of 95` exits 0 and yields `95` (stop at the source), with
  "malformed anchor" on stderr. Capture stderr separately: `make_draft` discards
  it, so run `aitask_create.sh` directly with `2>"$errf"` and read the draft path
  from stdout.

Keep the existing `42 → 42`, `50 → 42` and `60_1 → 60` cases. They show
unchanged behaviour on clean data.

In `test_child_inherit`, add a parent whose anchor is stale: `t62` with
`anchor: 50` (and `t50` with `anchor: 42`). Assert that its new child gets `42`.
The existing `60 → 60` and `61 (anchor 42) → 42` cases stay.

Update the file's header comment list. **Pre-fix control:** run the new
assertions against the pre-edit `aitask_create.sh` from a scratch copy
(`git show HEAD:.aitask-scripts/aitask_create.sh` into the scratchpad, then point
a copy of the test at it). Never revert in the shared worktree (memory: never
stash or git-restore a probe). Expected baseline values, each a discriminating
failure:
- re-anchored child → `70`
- longer chain → `80`
- stale follow-up → `80`
- stale-parent child → `50`
- cycle → `91` (one-hop copy)
- malformed source → `bogus`, with no warning

The existing `42`/`50`/`60_1`/`60`/`61` cases pass on both the baseline and the
fix. They are unchanged-behaviour checks, not discriminators. Classify each
assertion that way in the record.

### 3. Rewrite the chaining sentence — `website/content/docs/commands/task-management.md:68`

Replace the middle of the `--followup-of` row with: "Put the task in the topic of
source task `ID`, flattened to the root: the new task follows the source's
`anchor` (or, for an anchorless child such as `130_2`, its parent) through to the
topic root, so an anchor left stale by a later re-anchor is never copied. A
follow-up of an anchored follow-up therefore points at the same root." Keep the
existing tail. The `--parent` row (line 65) says nothing about anchors, so it
needs no edit. `concepts/topic-anchoring.md` ("it finds the root for you") is correct as it
stands.

Skill-side statements (`.claude/skills/aitask-create/SKILL.md:284`,
`task-workflow/task-creation-batch.md:152-156`) say "anchor = source.anchor if
present … never chains". The invariant they promise now holds. Their one-hop
phrasing is only imprecise for stale data, so leave them, which avoids a golden
regen and ported copies. Mention it in the Step 8 summary as a candidate wording
follow-up.

### 4. Forced procedure gate defers — `.aitask-scripts/lib/gate_orchestrator.py`

- Hoist the message into a module constant near `blocked_reason`:
  `PROCEDURE_NEEDS_AGENT = ("needs agent (procedure-backed gate — run via task-workflow / aitask-resume)")`
  and have `blocked_reason` return it, so the output is unchanged byte for byte.
- In `_force_one`, add a branch before `elif meta.get("verifier")`:
  ```python
  elif meta.get("kind") == "procedure":
      # Never shell-execute a procedure gate, forced or not: its verifier
      # names a skill the attended agent runs (gates_reference.yaml `kind`).
      self.reports.append(f"{gate}: {PROCEDURE_NEEDS_AGENT}")
  ```
  It appends nothing to the ledger, exactly like the unforced path. The
  predecessor and active-set checks above it stay in force, and so does the
  `type: human` arm ahead of it: a procedure gate is `type: machine`.
- Update the `_force_one` docstring to say that procedure gates are reported, not
  run.

### 5. Forced-run test — `tests/test_gate_procedure_docs.sh`

After section 2, add a section 2b on a fresh fixture: run
`run aitasks/t11_x.md --gate docs_updated`. Assert exit 0, output contains
`needs agent`, and `grep -c 'gate:docs_updated'` is 0. Update the header comment.
Pre-fix control: the same three assertions on the pre-edit `_force_one` (scratch
copy of the orchestrator) must fail the append count (2: `running` + `error`).

### 6. Gate docs

- `website/content/docs/development/gates.md` (~line 178): "forcing a
  procedure-backed gate such as `docs_updated` does not run its skill and records
  an `error`" → "forcing a procedure-backed gate such as `docs_updated` records
  nothing: it reports that the gate needs an agent, and the attended workflow runs
  it at review time".
- `website/content/docs/commands/gates.md:58` `--gate` row: add "or the gate is
  procedure-backed (it reports `needs agent`)" to "Reports rather than runs if …".
- `website/content/docs/skills/aitask-run-gates.md:31` `--gate` row: add the same
  clause.
- `website/content/docs/concepts/gates.md:52-56` already says such a gate "cannot
  be run that way". Re-read it after the change; edit only if it implies an
  error is recorded.

### 7. Aidocs: agent set and verify scope

`aidocs/framework/skill_authoring_conventions.md`:
- l.3-5: tree list → `.claude/skills/`, `.agents/skills/`, `.opencode/skills/`,
  or `.opencode/commands/`.
- l.12-13: stub surfaces → `.claude/skills/<skill>/SKILL.md`,
  `.agents/skills/<skill>/SKILL.md`, `.opencode/commands/<skill>.md`,
  `.opencode/skills/<skill>/SKILL.md`.
- l.20-25: "renders every `.j2` against `default.yaml` for the 3 supported agents
  (claude, codex, opencode) — the default profile only; other profiles are not
  rendered, except that skills marked `prerender_for_headless` also have their
  committed headless-profile prerenders walk-verified against the source", then
  the existing closure-walk, stub-marker and wrapper-parity sentences.
- l.45, l.106, l.172: drop the `.gemini/` entries.
- l.232-235: "The sibling stubs (Codex `SKILL.md` per §3b; the OpenCode command
  MD and OpenCode skill-dir stub per §3d) …". "all 4 stub surfaces" stays: there
  are 4 surfaces.
- l.506, l.510: `codex`/`opencode`; "regenerate goldens for all 3 agents".
- l.644: "all three agents (Claude, Codex, OpenCode)".

`aidocs/framework/stub-skill-pattern.md` l.96-100: "all four agents" → "every
supported agent". Drop Gemini from the "Codex / Gemini / OpenCode" list.

`aidocs/framework/agent_runtime_guards_audit.md` l.27
(`codex/gemini/opencode` → `codex/opencode`) and l.55 ("all four agents" → "every
supported agent"). Check the Test 1b loop in a cited test
(`tests/test_skill_render_aitask_fold.sh`) for the actual agent list and match
it.

Run `grep -rn -i gemini aidocs/framework/{skill_authoring_conventions,stub-skill-pattern,agent_runtime_guards_audit}.md`
afterwards. Expected: no hits other than deliberate historical mentions (there
should be none, under the current-state-only rule).

### 8. `website/content/docs/development/task-format.md:47`

"Written only by `ait archive --superseded` or `--obsolete`" → "Written only by
`./.aitask-scripts/aitask_archive.sh --superseded` or `--obsolete`".

### 9. `website/content/docs/workflows/crash-recovery.md:71`

Replace the bullet with: "**Your own session re-claiming.** The lock records the
process, not just the email, so a session recognises its own lock and refreshes
it without refusing. When the task is already `Implementing`, the pick still asks
the reclaim question (the anomaly prompt), so a re-pick is confirmed rather than
silent. Without the refresh, the ownership guard, an in-pane re-pick, and every
resume of an in-flight task would lock you out of your own work."

### Post-phase (risk mitigations)

1. [scan_existing_chained_anchors] Do a read-only scan of `aitasks/**/*.md` and
   `aitasks/archived/**/*.md` (loose files only; skip bundles). Build a map from
   bare task id to `anchor:`. List every task whose anchor `A` resolves to a task
   that itself carries a non-empty `anchor:`, i.e. a chain. Use the frontmatter
   reader approach from `tests/test_anchor_create.sh` (awk over the `---` block),
   or one Python pass via the venv interpreter. Write nothing. Report the list
   (or "no chained anchors found") in the Step 8 change summary. If any are
   found, offer to re-anchor them with `aitask_update.sh --batch <id> --anchor <root>`
   as a separate, user-confirmed action. It is not part of this commit.

## Out of scope (hand to an owner at Step 8)

`ait archive <N>` also appears in `.claude/skills/aitask-wrap/SKILL.md.j2:349`
and `.claude/skills/aitask-web-merge/materialize-gates.md:33`. Those are skill
sources with goldens and ported copies. Offer an `upstream_defect` follow-up
(`--followup-of 2284`) rather than widening this task.

## Verification

- `bash tests/test_anchor_create.sh` — all pass, including the new `70_1 → 42`
  case.
- `bash tests/test_gate_procedure_docs.sh` and `bash tests/test_gate_orchestrator.sh`
  — all pass.
- Pre-fix controls from steps 2 and 5 fail as described (run in scratch copies).
- `shellcheck .aitask-scripts/aitask_create.sh`.
- `bash .aitask-scripts/aitask_create.sh --help | sed -n '/--followup-of/,/--followup-kind/p'`
  — check the wording.
- `cd website && python3 check_links.py --build` (website pages edited).
- Grep check in step 7.

## Risk

### Code-health risk: medium
- The `resolve_anchor()` edit runs under `set -euo pipefail`, and `BASH_REMATCH`
  could be clobbered by `resolve_task_file`'s own regex before it is read ·
  severity: low · → mitigation: none (`BASH_REMATCH` is read straight after its own
  match, and the step 2 regression tests cover it)
- Every `--parent` and `--followup-of` create now runs `resolve_topic_root`, a
  loop over `resolve_task_file`. A hop into an archive bundle extracts from the
  tarball, and a malformed graph must never hang or fail a create. The loop is
  bounded by the visited set; on clean data it is 1–2 hops, the same resolves the
  one-hop code already did. It never dies (a malformed or cyclic anchor gives a
  warning and stops) · severity: medium · → mitigation: none (covered by the
  cycle and stale-chain cases in plan step 2, and the existing `test_child_inherit`
  and `--finalize` cases for unchanged behaviour on clean data)
- The forced-gate branch must not change what the unforced path reports, which
  is now a shared constant · severity: low · → mitigation: none (the existing
  `needs agent` assertion in section 2 still runs)

### Goal-achievement risk: low
- Choosing to change behaviour (flatten) rather than reword the help text means
  any existing task already created with a chained anchor stays chained. The fix
  only prevents new ones (from `--followup-of` and `--parent`; an explicit
  `--anchor` and `ait update --anchor` store what they are given) · severity: low (residual — addressed by inline
  post-phase scan_existing_chained_anchors, which surfaces any existing chains) ·
  → mitigation: inline post-phase scan_existing_chained_anchors

### Planned mitigations
- timing: post-phase | name: scan_existing_chained_anchors | type: chore | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: existing chained anchors persist after the flatten fix | desc: read-only scan of task frontmatter for anchors pointing at anchored tasks; report at Step 8

## Step 9 (Post-Implementation)

Current-branch mode: commit code and docs as `bug: … (t2284)` with explicit
paths, then archive via the workflow's Step 9.
