---
Task: t1156_manual_verification_tasks_must_not_get_risk_gate.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

# Plan: manual_verification tasks must not receive planning-derived gates

## Context

**Problem.** When the active execution profile declares `default_gates`, the
Batch Task Creation Procedure (`task-creation-batch.md`) auto-injects
`--gates "<default_gates>"` onto **every** task it creates. The `fast` profile
declares `default_gates: [risk_evaluated]`. A `manual_verification` task runs
the Manual Verification Procedure and **skips Steps 6–8** (planning, risk
evaluation, review) entirely — so `risk_evaluated` (whose verifier requires a
plan `## Risk` section + the two `risk_*` frontmatter levels) can never be
satisfied. With `max_retries: 0`, the gate is immediately exhausted and
`aitask_archive.sh` refuses to archive (`GATE_PENDING:risk_evaluated`, exit 2).
The task can never archive. This surfaced on t1141 (fixed there by hand).

**Principle (from the user).** A `manual_verification` task is not supposed to
carry a risk gate. More generally, gates that are only ever recorded in the
planning/review steps a manual_verification task skips must not be stamped onto
it.

**Intended outcome.** A `manual_verification` task created under any profile
(including one with `default_gates: [risk_evaluated]`) is archivable — it never
declares a gate it structurally cannot reach.

## Investigation findings (already confirmed)

- **Injection surfaces for manual_verification.** Gates land on a task via
  (1) `aitask_create.sh --gates` at creation, and (2) the Step-7
  gate-declaration backfill. Surface (2) is **structurally unreachable** for
  manual_verification: Step 3 Check 3 routes these tasks to the Manual
  Verification Procedure and skips Steps 6–8, so the Step-7 backfill never runs.
  → Fixing the **creation sink** (`aitask_create.sh`) covers every caller (the
  risk-mitigation "after" follow-up, the manual-verification follow-up, and the
  `aitask_create_manual_verification.sh` seeder all funnel through
  `aitask_create.sh --batch`). Within the sink there are **two write paths**:
  `run_batch_mode()` (used by the `--commit` fast-path the bug travels — it never
  creates a draft) and `finalize_draft()` (the `--finalize`/draft flow, which
  `sed`-copies a draft and currently re-filters nothing). Both are filtered
  (see Approach §2/§2c).
- **The injected CLI shape is confirmed.** The rendered `fast` golden of
  `task-creation-batch.md` emits `--gates "risk_evaluated"` verbatim — the exact
  shape the sink receives. The template is unconditional (it cannot see
  `issue_type` at render time), which is *why* the fix belongs at the sink; a
  golden-grep test pins this equivalence (Approach §4).
- **Archive guard reads the LITERAL `gates:` field** (`aitask_gate.sh
  archive-ready` → `archive_status`, not `effective_gates`). So a
  manual_verification task with **no** injected `gates:` field yields `NO_GATES`
  and archives cleanly. Preventing the literal injection is sufficient — no
  archive-script change needed.
- **Reachable gate set (what to KEEP) = the machine gates recorded in Step 9**,
  the only step manual_verification reaches (it skips Steps 6–8):
  `build_verified`, `tests_pass`, `lint`. Everything else is stripped — the
  planning/review gates (`plan_approved`, `risk_evaluated`, `review_approved`,
  `docs_updated`) and also `merge_approved` (a profile-conditional human gate,
  never auto-injected; see the allowlist rationale in Approach). Expressing the
  rule as this KEEP-set (allowlist) rather than a strip-set is the fail-safe
  choice — see Approach.
- **Sweep for already-affected tasks is clean.** No **active**
  manual_verification task declares any gate in its frontmatter. The three
  "live-verify" tasks (t1109, t1015, t635_27) only mention gates in prose and
  create *scratch* tasks at runtime — they do not self-declare gates. t1141
  (archived) was already corrected by removing its gate.

## Approach

A **structural, fail-safe fix at the creation sink** (makes the bad state
impossible rather than relying on every caller to filter): `aitask_create.sh`
keeps, for a `--type manual_verification` task, **only the gates that flow can
actually reach**, and strips the rest. This is unconditional (covers both
auto-injected and explicitly-passed gates) and warns about what it stripped.

**Allowlist, not denylist (addresses the blast-radius concern).** The reachable
set is the small, stable set of gates the manual-verification flow records in
**Step 9** — `build_verified`, `tests_pass`, `lint` — the only gates it reaches
(it skips Steps 6–8). Anything else is stripped. Framing it as an **allowlist**
is deliberately **fail-safe**: if a future planning/review gate is ever added to
a profile's `default_gates`, it is *unknown to the allowlist and therefore
stripped automatically* — a new gate can never silently make a
manual_verification task unarchivable again. The failure mode inverts to the
harmless direction (a genuinely-new *reachable* gate would be stripped until
added to the allowlist, but that only forgoes an optional check — the task still
archives — and the strip is **warned**, not silent). This is strictly more
robust than enumerating the planning gates to remove. (`merge_approved` is
intentionally **not** in the allowlist: it is a human gate, never auto-injected,
and only recorded when a worktree/branch exists — profile-dependent — so
treating it as non-reachable is the fail-safe default; the interactive merge
approval at Step 9 is unaffected, only its ledger record.)

### 1. Filter helper — `.aitask-scripts/lib/task_utils.sh`

Add the allowlist constant + a pure function (bash-native, consistent with the
bash-first gate tooling in `aitask_gate.sh`; sourced by `aitask_create.sh`;
trivially unit-testable by sourcing `task_utils.sh` — no Python dependency, so
it works even when the Python gate backend is unavailable):

```bash
# Gates a `manual_verification` task can actually REACH: the machine gates
# recorded in task-workflow Step 9. Manual verification skips Steps 6-8
# (plan/risk/review), so any gate whose checkpoint lives there is unreachable.
# ALLOWLIST (not a denylist) on purpose: an unknown/new gate is stripped by
# default, so a future planning gate added to a profile's default_gates can
# never make a manual_verification task unarchivable. See
# .claude/skills/task-workflow/manual-verification.md (Steps 6-8 skipped) and
# aitasks/metadata/gates.yaml. merge_approved is excluded (profile-conditional
# human gate, never auto-injected).
MANUAL_VERIFICATION_REACHABLE_GATES="build_verified tests_pass lint"

# filter_gates_for_issue_type <issue_type> <csv-gates>
#   Echoes the kept gates as CSV on stdout. Echoes "STRIPPED:<csv>" on stderr
#   iff any unreachable gate was removed. Only manual_verification filters;
#   every other issue_type passes its gates through unchanged.
filter_gates_for_issue_type() {
    local issue_type="$1" csv="$2"
    if [[ "$issue_type" != "manual_verification" || -z "$csv" ]]; then
        printf '%s' "$csv"; return 0
    fi
    local kept=() stripped=() g
    IFS=',' read -ra _gates <<< "$csv"
    for g in "${_gates[@]}"; do
        g="${g// /}"; [[ -z "$g" ]] && continue
        if [[ " $MANUAL_VERIFICATION_REACHABLE_GATES " == *" $g "* ]]; then
            kept+=("$g")
        else
            stripped+=("$g")
        fi
    done
    local IFS=','
    printf '%s' "${kept[*]}"
    [[ ${#stripped[@]} -gt 0 ]] && printf 'STRIPPED:%s\n' "${stripped[*]}" >&2
    return 0
}
```

### 2. Call the filter in `run_batch_mode()` — `.aitask-scripts/aitask_create.sh`

Immediately after `validate_task_type "$BATCH_TYPE"` (~line 1930), before any
file is written (this is upstream of BOTH the parent and child create paths,
which all read `BATCH_GATES`):

```bash
# Keep only gates a manual_verification task can reach (it skips Steps 6-8).
if [[ -n "$BATCH_GATES" ]]; then
    local _stripped
    _stripped=$(filter_gates_for_issue_type "$BATCH_TYPE" "$BATCH_GATES" 2>&1 >/dev/null)
    BATCH_GATES=$(filter_gates_for_issue_type "$BATCH_TYPE" "$BATCH_GATES" 2>/dev/null)
    [[ -n "$_stripped" ]] && info "manual_verification: dropped unreachable gate(s): ${_stripped#STRIPPED:} (recorded in planning/review steps this task type skips)"
fi
```

(Uses the existing `info` helper. Two calls keep the stdout CSV and the stderr
notice cleanly separated; the filter is a cheap pure function.)

### 2c. Close the finalize path — `.aitask-scripts/aitask_create.sh`

`finalize_draft()` returns before `run_batch_mode()`'s filter, so a
**pre-existing or hand-edited** draft with `issue_type: manual_verification` +
`gates: [risk_evaluated]` would finalize into the bad state. The `--commit` bug
path never creates a draft, so this is a low-severity edge — but closing it
keeps the invariant global. After the draft is copied to `$filepath` (both the
child and parent branches, before `task_git add "$filepath"`), re-filter in
place using the finalized file's own frontmatter:

```bash
# Enforce the manual_verification gate invariant on finalized drafts too.
local _dtype _dgates _kept _stripped
_dtype=$(read_yaml_field "$filepath" issue_type)
_dgates=$(read_yaml_field "$filepath" gates)   # e.g. "[risk_evaluated, build_verified]"
if [[ "$_dtype" == "manual_verification" && -n "$_dgates" ]]; then
    _dgates="${_dgates#[}"; _dgates="${_dgates%]}"      # strip brackets → CSV
    _stripped=$(filter_gates_for_issue_type "$_dtype" "$_dgates" 2>&1 >/dev/null)
    if [[ -n "$_stripped" ]]; then
        _kept=$(filter_gates_for_issue_type "$_dtype" "$_dgates" 2>/dev/null)
        sed_inplace "s/^gates:.*/gates: $(format_yaml_list "$_kept")/" "$filepath"
        info "manual_verification: dropped unreachable gate(s) from finalized draft: ${_stripped#STRIPPED:}"
    fi
fi
```

(`read_yaml_field` and `sed_inplace` are existing shared helpers; `format_yaml_list`
re-emits the canonical `[]`/`[a, b]` shape. Factor the copy-then-fixup into a
small local so the child and parent branches share it rather than duplicating.)

### 3. No skill-template change (no goldens regen)

`task-creation-batch.md`'s unconditional Jinja injection is left as-is — the
sink now makes it safe. Item 2 of the task explicitly sanctions fixing "the
create script" as an alternative to the template. Because no `.md.j2`/skill
surface changes, **no goldens regeneration and no cross-agent (Codex/OpenCode)
port are required** — the fix lives entirely in framework-shared
`.aitask-scripts/` files consumed identically by every agent. (Website docs
below are separate from skill goldens.)

### 3b. Website documentation (current-state framing, no version history)

Per `documentation_conventions.md` — describe the behavior as it now *is*, not
as a change. Two pages:

- **`website/content/docs/skills/aitask-create.md`** — in the **Batch Mode**
  section, document the `--gates` flag and its one special case: a
  `--type manual_verification` task keeps only the gates it can reach
  (the Step-9 machine gates `build_verified` / `tests_pass` / `lint`); any other
  gate — e.g. a profile-injected `risk_evaluated` — is dropped automatically,
  since manual verification skips the planning/review steps that record them.

- **`website/content/docs/workflows/manual-verification.md`** — in **Running a
  Manual-Verification Task** (right after the sentence noting Steps 6–8 are
  replaced), add that a manual-verification task therefore never carries
  planning/review-phase gates: any that a profile's `default_gates` would
  otherwise inject are stripped at creation, so the task's archival is never
  blocked by a gate it cannot satisfy. Reachable post-verification gates
  (build/tests/lint) are unaffected.

The website currently documents neither `default_gates` nor the `gates:`
frontmatter field (the gate system is still maturing under t635), so these two
targeted additions stay self-contained and do not require a new gates concept
page or a `task-format.md` frontmatter-field row.

### 4. Tests — new `tests/test_create_manual_verification_gates.sh`

- **Unit (source `task_utils.sh`, call the function directly):**
  - `filter_gates_for_issue_type manual_verification "risk_evaluated"` → stdout
    empty, stderr `STRIPPED:risk_evaluated`.
  - `... manual_verification "risk_evaluated,build_verified"` → stdout
    `build_verified`, stderr `STRIPPED:risk_evaluated` (**mixed-set control**).
  - `... manual_verification "build_verified"` → stdout `build_verified`, no
    stderr (**reachable-gate kept**).
  - `... manual_verification "review_approved,docs_updated,plan_approved"` →
    stdout empty, all three in stderr (**future/other planning gates stripped by
    the allowlist**).
  - `... bug "risk_evaluated"` → stdout `risk_evaluated`, no stderr
    (**negative control: other issue_types untouched**).
  - `... manual_verification ""` → empty, no stderr.
- **Allowlist ⊆ registry guard (rename/typo tripwire, addresses blast-radius):**
  assert every gate in `MANUAL_VERIFICATION_REACHABLE_GATES` exists as a key in
  `aitasks/metadata/gates.yaml` (parse via `aitask_gate.sh` / grep). A rename in
  the registry that isn't mirrored here fails loudly instead of silently
  stripping a now-misspelled reachable gate.
- **Injection-equivalence pin (addresses the verification concern):** grep the
  rendered `fast` golden
  `.claude/skills/task-workflow-fast-/task-creation-batch.md` and assert its
  create commands emit `--gates "risk_evaluated"` — i.e. the exact CLI shape the
  integration test feeds the sink. This ties the profile→template injection path
  to the sink test without executing the agent-followed template. (If the golden
  ever changes shape, this test flags that the equivalence must be re-checked.)
- **Integration — real `aitask_create.sh --batch --commit`** (isolated repo,
  `test_create_manual_verification.sh` scaffolding):
  - `--type manual_verification --gates "risk_evaluated"` → created file has
    **no** `risk_evaluated`; `aitask_gate.sh archive-ready <id>` → `NO_GATES`
    (**primary bug fixed, end-to-end**).
  - `--type manual_verification --gates "risk_evaluated,build_verified"` → file
    declares only `build_verified` (reachable gate survives end-to-end).
  - `--type bug --gates "risk_evaluated"` → file **does** declare
    `risk_evaluated` (**end-to-end negative control**).
- **Finalize-path coverage (addresses concern 3):** hand-write a draft in the
  drafts dir with `issue_type: manual_verification` + `gates: [risk_evaluated]`,
  run `aitask_create.sh --batch --finalize <draft>`, assert the finalized task
  has no `risk_evaluated`.

### 5. Sweep documentation

Record in Final Implementation Notes: no active manual_verification task carries
a frontmatter gate; t1141 already corrected; no data migration needed.

### Trade-offs / rejected alternatives

- **Denylist of planning gates (`plan_approved risk_evaluated review_approved
  docs_updated`)** — rejected: it is the new hard-coded source of truth the
  blast-radius concern warns about (goes stale → unarchivable) when a future
  Step 6–8 gate joins `default_gates`. The allowlist fails safe instead.
- **Registry `phase:` taxonomy (derive the set from per-gate metadata in
  `gates.yaml`/`gates_reference.yaml`)** — considered and deferred (YAGNI). It is
  the most "derived" option and the drift test would guard it, but it adds a new
  registry schema field, a `read_registry()` parse branch, edits to both
  canonical copies (data-branch ceremony), and a Python round-trip in the create
  hot path — disproportionate to a 3-item allowlist that already fails safe. The
  allowlist + `⊆ registry` guard test captures the realistic regression path at a
  fraction of the surface. Revisit if a real gate-phase taxonomy is needed
  elsewhere.

### Scope / effort note

The minimal one-line create filter grew (in response to review) to: a fail-safe
allowlist helper, **two** enforced sink paths (batch + finalize), a golden
equivalence pin, a registry guard test, and two doc pages. Effort is now
**medium**, not low — I'll bump `effort` on the task file at implementation and
call it out rather than deviate silently.

## Files to modify

- `.aitask-scripts/lib/task_utils.sh` — add `MANUAL_VERIFICATION_REACHABLE_GATES` + `filter_gates_for_issue_type()`.
- `.aitask-scripts/aitask_create.sh` — call the filter in `run_batch_mode()` (after `validate_task_type`) **and** in `finalize_draft()` (post-copy fixup, shared local for child/parent branches).
- `tests/test_create_manual_verification_gates.sh` — new test (unit, allowlist⊆registry guard, golden-equivalence pin, integration, finalize path).
- `website/content/docs/skills/aitask-create.md` — document `--gates` + the manual_verification allowlist (Batch Mode section).
- `website/content/docs/workflows/manual-verification.md` — note that these tasks only carry gates they can reach; planning/review gates are stripped at creation (Running section).
- `aitasks/t1156_*.md` — bump `effort: low` → `medium` (scope note above).

## Verification

1. `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/lib/task_utils.sh`
2. `bash tests/test_create_manual_verification_gates.sh` — all PASS (unit,
   allowlist⊆registry guard, golden-equivalence pin, integration, finalize).
3. `bash tests/test_create_manual_verification.sh`, `bash tests/test_gate_guarded_archival.sh`,
   and `bash tests/test_create_silent_stdout.sh` — no regression (the filter must
   not add stray stdout that would corrupt `Created:` parsing).
4. **Live end-to-end (real sink):** in a scratch repo,
   `aitask_create.sh --batch --commit --type manual_verification --gates
   "risk_evaluated" ...`, then confirm `aitask_gate.sh archive-ready <id>` →
   `NO_GATES` and `aitask_archive.sh <id>` does **not** emit
   `GATE_PENDING:risk_evaluated`. Repeat via a hand-written draft + `--finalize`.
5. **Docs:** `cd website && hugo build --gc --minify` succeeds (no broken
   refs); visually confirm both edited pages read as current-state (no "we
   changed" phrasing).

## Risk

### Code-health risk: low
- The filter runs on every batch create and at finalize; a bug could corrupt gates for non-manual_verification tasks · severity: low · → mitigation: both call sites are guarded on `issue_type == manual_verification` (pass-through/no-op otherwise), backed by a negative-control unit test (`bug`+`risk_evaluated` kept) and the finalize/no-regression tests. The finalize fixup only rewrites a `gates:` line for manual_verification drafts, leaving all other finalization untouched.
- Additive and contained: one pure bash helper + two guarded call sites + tests; no change to gate recording, archival, or non-manual_verification creation. Bash-native (no new Python dependency).

### Goal-achievement risk: low
- Approach relies on the create sink being the only reachable gate-injection surface for manual_verification · severity: low · → mitigation: verified against source — the Step-7 backfill is structurally skipped (Check 3 routes manual_verification past Steps 6-8), the archive guard reads the literal `gates:` field, the injection-equivalence golden pin ties the profile path to the sink test, and the integration + finalize tests exercise the real `aitask_create.sh` end-to-end. The allowlist framing makes future-gate regressions fail-safe.
- Requirement coverage confirmed against all task goals (reachable KEEP-set, dual sink fix, tests, clean sweep, docs, no cross-agent port needed).

## Step 9 (Post-Implementation)

Standard cleanup/archival per `task-workflow` Step 9: run gates
(`build_verified` per project `verify_build`, plus this task's `risk_evaluated`
which the plan below satisfies), then archive via `aitask_archive.sh 1156`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Added the fail-safe
  allowlist `MANUAL_VERIFICATION_REACHABLE_GATES="build_verified tests_pass lint"`
  and pure `filter_gates_for_issue_type()` to `.aitask-scripts/lib/task_utils.sh`;
  wired it into `aitask_create.sh` at two sink paths — `run_batch_mode()` (after
  `validate_task_type`, covering all `--batch` creates including `--commit`) and
  a new `enforce_manual_verification_gate_invariant()` called from both branches
  of `finalize_draft()` (covers pre-existing/hand-edited drafts). New test suite
  `tests/test_create_manual_verification_gates.sh` (42 assertions: unit filter
  incl. negative controls, allowlist⊆registry guard, injection-equivalence pin
  against the authoring template + seed fast profile + locally-rendered fast
  variant, 3 integration cases via the real script, finalize-draft case, syntax
  checks). Website docs updated in current-state framing:
  `website/content/docs/skills/aitask-create.md` (new "Declared gates and
  manual-verification tasks" block in Batch Mode) and
  `website/content/docs/workflows/manual-verification.md` (gate note in
  "Running a Manual-Verification Task").
- **Deviations from plan:** None substantive. The finalize fixup was implemented
  as a named function called from both `finalize_draft()` branches (the plan
  suggested "factor into a small local" — a top-level function is cleaner and
  testable). The injection-equivalence pin targets the *tracked* authoring
  template + `seed/profiles/fast.yaml` (asserting the rendered fast variant only
  when locally present), because the rendered `-fast-` variant is not
  git-tracked.
- **Issues encountered:** None. Shellcheck shows only pre-existing findings
  (verified identical finding-profile before/after via stash diff). Live
  end-to-end in a scratch repo confirmed: strip notice emitted, no `gates:`
  line, `archive-ready → NO_GATES`, `aitask_archive.sh` archived cleanly (exit
  0, no `GATE_PENDING`).
- **Key decisions:** (1) Allowlist over denylist — unknown/future gates are
  stripped by default, so a new planning gate added to `default_gates` can never
  re-create the unarchivable state; the harmless inverse failure (a new
  reachable gate is stripped until allowlisted) is warned, not silent, and does
  not block archival. (2) `merge_approved` excluded from the allowlist
  (profile-conditional human gate, never auto-injected). (3) No skill-template
  change — the sink makes the unconditional Jinja injection safe; no goldens
  regen, no cross-agent port (fix lives in framework-shared `.aitask-scripts/`).
  (4) Registry `phase:` taxonomy rejected as disproportionate (see Trade-offs).
- **Sweep result (task goal 4):** No active manual_verification task declares
  any gate in frontmatter — t1109/t1015/t635_27 mention gates only in prose and
  create scratch tasks at runtime; t1141 (archived) was already corrected during
  its verification pick. No data migration needed.
- **Effort bump:** task `effort` raised low → medium to reflect the reviewed
  scope (dual sink paths, five test layers, docs) — explicit, per no-silent-AC-
  deviation.
- **Upstream defects identified:** None
