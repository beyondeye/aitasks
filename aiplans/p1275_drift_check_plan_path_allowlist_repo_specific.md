---
Task: t1275_drift_check_plan_path_allowlist_repo_specific.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1275 — Drop the repo-specific root allowlist from the drift check

## Context

`.aitask-scripts/aitask_remote_drift_check.sh` decides which files a plan
"references" in two steps: extract path-shaped tokens with a known extension,
then **keep only those rooted in a hardcoded allowlist of this repository's own
top-level directories** (`:217`):

```
aitask-scripts|aitasks|aiplans|claude/skills|opencode/skills|gemini/skills|agents/skills|website|seed|tests
```

The framework is installed into projects whose source trees share no top-level
directory with this one, so the intersection there is always empty and the helper
emits `NO_OVERLAP` on every run. `AHEAD` + `OVERLAP` is the *strong* half of the
signal — the only half a `remote_drift_check: strong-only` profile acts on — so
the check silently degrades to a no-op rather than failing visibly. The allowlist
is also wrong *for this repo*: `aidocs/` is missing from it, so the routine
`aidocs/framework/*.md` reference has never produced an overlap.

**Scope decision (user, this session): keep t1275 surgical.** Exploration turned
up several deeper defects in how plan references are recognized. Those are *not*
fixed here — they are recorded below as explicit inputs for **t1561**'s decision
record, which is the task that owns "what evidence shows a task's premise has
drifted". t1561 needs no formal `depends:` on t1275 and can begin now; it would
only acquire one if its implementation elects to reuse this helper.

## The change

### `.aitask-scripts/aitask_remote_drift_check.sh` (`:210`–`:220`)

**Delete one pipeline stage** — the root-allowlist `grep`. Extraction, `./`
stripping, dedupe, and the exact `grep -Fxf` full-line intersection are all
untouched:

```bash
# --- Plan-referenced paths ---
# Step 1: pull every token shaped like a relative path with a known extension.
# Step 2: strip leading './' and dedupe.
#
# There is deliberately no allowlist of directory roots. OVERLAP is produced by
# an exact full-line intersection with the remote-changed file list below, so a
# token that is not a real remote-changed path is discarded there anyway: a root
# filter can only remove TRUE positives, never false ones. The list removed here
# was this repository's own top-level directories, which made the overlap signal
# unreachable in every consumer project -- and missed aidocs/ even here (t1275).
#
# The extension list below is a KNOWN remaining narrowing, deliberately left in
# place; see "Deferred - inputs for t1561" in aiplans/p1275_*.md.
plan_paths=""
if [[ -r "$PLAN_FILE" ]]; then
    plan_paths=$(grep -oE '[A-Za-z0-9_./-]+\.(sh|py|md|yaml|yml|json|toml)' "$PLAN_FILE" 2>/dev/null \
        | sed 's|^\./||' \
        | sort -u || true)
fi
```

**The change is strictly widening** — verified by diffing the old and new token
sets over a representative plan body: every token the allowlist admitted is still
admitted, and `src/app/service.py` plus `aidocs/framework/notes.md` are newly
admitted. That is what makes "the existing repo-shaped overlap test still passes"
structurally guaranteed rather than merely observed.

One behavior note: bare root-level filenames (`CLAUDE.md`, `README.md`) can now
produce `OVERLAP` when the remote changes them and the plan names them. Under the
old allowlist they never could. This is a real widening, in the safe direction
(an extra advisory prompt), and it is what deleting a root filter necessarily
means.

No other call site exists — the allowlist appears at exactly one line repo-wide,
and there is no copy under `seed/`.

## Tests — `tests/test_remote_drift_check.sh`, new Test 13

Built on the existing `make_branch_mode_pair` / `mark_branch_mode` /
`register_cleanup` helpers, with a `write_consumer_plan_file()` whose body
references `src/app/service.py` and `aidocs/framework/notes.md` and **never
mentions** `src/app/unreferenced.py` in any form. (The negative-control path must
be absent from the text entirely — a plan sentence like "we do not touch X" still
yields X as a token, so a negatively-phrased mention would not discriminate.)

A second clone pushes remote-only commits touching all three paths. Legs:

| leg | assertion | pins |
|---|---|---|
| 13a | `OVERLAP:src/app/service.py` present | consumer-shaped root, the task's headline case |
| 13b | `OVERLAP:aidocs/framework/notes.md` present | the same defect inside this repo |
| 13c | `OVERLAP:src/app/unreferenced.py` **absent** | the intersection still filters |
| 13d | `NO_OVERLAP` absent | — |

Existing Tests 4 and 5 (repo-shaped non-overlap and overlap) are untouched and
carry the "existing behavior preserved" acceptance criterion.

## Verification

1. `bash tests/test_remote_drift_check.sh` — old and new tests pass.
2. **Negative controls — two mutations, each with the legs it must break.** The
   legs are not all discriminated by the same mutation:

   | mutation | must break | must NOT break |
   |---|---|---|
   | **M1** restore the root-allowlist `grep` | 13a, 13b **and 13d** | 13c — it passes vacuously under M1, since the allowlist is not what excludes it |
   | **M2** emit every remote-changed path, skipping the intersection | 13c | 13a, 13b, 13d |

   **M1 must break three legs, not two.** Verified: with the allowlist restored
   the consumer plan yields an *empty* `plan_paths` (its only other token,
   `t999_test.md` from the metadata header, is bare and fails the root test), so
   the overlap block is skipped entirely and the helper prints `NO_OVERLAP` —
   failing 13d as well. Recording only 13a/13b would understate the expected
   observation and let a partial control run look complete.

   Report the observed failing assertion names and check them against these
   counts. A leg that fails under no mutation is testing nothing.
3. `shellcheck .aitask-scripts/aitask_remote_drift_check.sh` — clean.
4. `bash tests/test_task_workflow_reentry_drift.sh` — the other suite exercising
   this helper's contract.
5. Live smoke: run the helper in this repo against this task's own plan with
   `--debug` and confirm `aidocs/`-rooted paths now appear in the extracted set.
6. Handoff check: `aidocs/framework/plan_path_reference_extraction_findings.md`
   exists, and `grep -n 't1275\|plan_path_reference_extraction_findings'
   aitasks/t1561_generalize_task_staleness_detection.md` returns the new
   `## Related` bullet — both committed before Step 9 archives the plan. Confirm
   t1561's `depends:` is still `[]`.

No documentation changes: `grep` over `website/`, `aidocs/` and
`.claude/skills/*/remote-drift-check.md` finds no user-facing text describing the
extraction rule; the output protocol those files document is unchanged.

## Deferred — inputs for t1561

**Handoff artifact (must land before t1275 archives).** A plan is not a durable
input: `aiplans/p1275_*.md` moves to `aiplans/archived/` at Step 9, and t1561
today has no link to t1275 at all, so a future t1561 agent could complete its
decision record without ever seeing this evidence. Two additions close that,
both in this task's commit:

1. **`aidocs/framework/plan_path_reference_extraction_findings.md`** — a new
   short reference doc carrying the six findings below verbatim, each with the
   command that reproduces it. `aidocs/framework/` is where t1561's own
   deliverable lands, so this sits beside its output and survives archival.
2. **One additive `## Related` bullet in `aitasks/t1561_generalize_task_staleness_detection.md`**
   pointing at that doc and at t1275, phrased as an input to consult. Nothing
   else in that file changes — in particular **no `depends:` edit**, per the
   explicit decision that t1561 need not depend on t1275.

Addition 2 is a deliberate exception to the usual rule that a task does not edit
a future consumer's task file: without a pointer *from* t1561, a doc in `aidocs/`
is only discoverable by luck, and the rule exists to prevent hidden coupling
rather than to prevent a task from being told what to read. It is additive,
status-neutral, and dependency-neutral.

Each item below was **empirically verified during t1275 planning**, not
hypothesized, and each is a case where the framework silently believes a plan
references no files. They bear on t1561's step 2 ("separate detectable evidence
from heuristic signals") and step 6 ("clean/unknown/stale states").

1. **The extension allowlist is the same defect on the other axis.** After this
   fix the extraction regex still requires `(sh|py|md|yaml|yml|json|toml)`.
   Verified: a plan referencing `internal/pkg/server.go` yields **zero** tokens.
   So for Go, Kotlin, Rust, TypeScript, C# and Java projects the drift check
   remains a no-op for their primary sources — **t1275's acceptance criteria are
   met, but the Impact section's "every consumer project" is only partly
   discharged.** This is a one-line change if it should be pulled forward.
2. **The token character class truncates real paths, silently.** `[A-Za-z0-9_./-]`
   excludes characters git permits. Verified: `node_modules/@scope/pkg.js` is
   extracted as `scope/pkg.js` and `app/x.storyboardc` as `app/x.storyboard` —
   *wrong* paths that can never match, with no signal anything was dropped.
   `src/my file.py`, `src/café.py`, `bin/run`, `src/Makefile` and `src/a+b.py`
   produce nothing at all. Extensionless files are structurally invisible.
3. **Any replacement grammar needs a delimitation rule, which is a design
   problem, not a regex problem.** Inverting the search (scan the plan for each
   remote-changed path) removes the grammar entirely, but then requires deciding
   which characters delimit a reference. Verified pitfalls: an `[A-Za-z0-9_./-]`
   delimiter set reports `src/app.py` as referenced by the text `src/app.py@v2`
   and `src/a` by `src/a+b.py`; and it splits the two equivalent anchor forms,
   accepting `src/app.py:42` while rejecting `src/app.py#L20`. A workable set
   exists (whitespace plus prose punctuation including `#`), but at least one
   residual is undecidable: whitespace must delimit bare references, so a remote
   path that is a whitespace-delimited prefix of a longer quoted path
   over-reports.
4. **Unicode normalization is a live correctness gap, not a macOS test quirk.**
   APFS/HFS+ store filenames decomposed, so git reports NFD while a plan authored
   in an editor carries NFC, and comparison is byte-exact. Verified:
   `src/café.py` is `…66 c3 a9…` in NFC versus `…66 65 cc 81…` in NFD, and
   `grep -F` with one against the other does not match. It is reproducible on any
   NFD-on-disk repo, so it is testable on Linux. Reconciling the forms requires
   normalizing both sides and an **explicit** normalized-to-original mapping —
   `grep -oFf` emits the matched normalized string with no link to the pattern
   that produced it, so the naive loop reports the NFC form instead of the path
   git named.
5. **Git paths may not be valid UTF-8, and this helper must never fail.**
   Verified: a path containing a lone `0xE9` byte crashes a strict
   `sys.stdin.read()` decode with exit 1, and a bare `x=$(python3 …)` under
   `set -e` **aborts the script** — which would violate this helper's documented
   "always exit 0; never fails the workflow" contract. Any normalization work
   needs `surrogateescape` decoding plus an errexit-suppressing guard.
6. **Tooling caveat for whoever tests this.** On this machine `grep` is
   **ugrep 7.8.4**, not GNU grep, and it rejects bracket expressions GNU grep
   accepts (`[^[:cntrl:][:print:]]` errors as an empty character class). A
   portable non-ASCII probe is `LC_ALL=C tr -d '\000-\177'`. Both greps used by
   this helper were re-run under `/usr/bin/grep` and agree.

## Risk

### Code-health risk: low

- One pipeline stage is deleted from a single call site; the change is provably
  strictly widening, so no existing detection can regress · severity: low ·
  → mitigation: covered in-plan — Tests 4 and 5 are the untouched repo-shaped
  guards, and M1 is the control for the new legs
- Previously-silent roots — `aidocs/`, `docs/`, `.github/`, and repository-root
  files — can now raise a *strong* warning where `strong-only` profiles saw
  nothing · severity: low · → mitigation: covered in-plan — this is the intended
  fix, and the exact intersection still bounds it to real remote-changed paths

### Goal-achievement risk: low

- The extension allowlist leaves the check a no-op for non-Python/shell/markdown
  projects, so the task's Impact framing is only partly discharged · severity:
  medium · → mitigation: **deliberately deferred by user decision**, recorded as
  t1561 input 1 with the verifying evidence; acceptance criteria are still met
- The remaining extraction defects (items 2–5) are invisible to any test written
  in this repo's own idiom, so they could be re-discovered as new bugs ·
  severity: low · → mitigation: covered in-plan — the deferred-inputs section
  records each with reproduction evidence and names t1561 as the owner
- The handoff itself can fail silently: an archived plan is not a discoverable
  input, and t1561 has no link to t1275 · severity: medium · → mitigation:
  covered in-plan — a named `aidocs/framework/` artifact plus a `## Related`
  pointer from t1561, both landing in this task's commit **before** Step 9
  archives the plan

No residual risk needs a separate mitigation task or phase: the in-scope concerns
are discharged by test legs already in this plan, and the out-of-scope ones are
routed to t1561 by explicit user decision, so
`risk_mitigations_planned = false`.

## Step 9

Post-implementation: commit as `bug: … (t1275)`, then archive the task and plan
per the standard Step 9 flow. The archived plan carries the t1561 inputs.

---

## Implementation record

Implemented as planned; no design deviations. Observations worth keeping:

- **Verification 1** — `bash tests/test_remote_drift_check.sh`: 37/37 pass.
- **Verification 2 (negative controls)** — both matched the predicted legs:
  - **M1** (restore the root-allowlist `grep`) → 3 failures, exactly as the plan
    required: `13a`, `13b` and `13d`. `13c` passed vacuously, as documented.
  - **M2** (replace the `grep -Fxf` intersection with `cat`) → `13c` failed.
    It *also* failed Test 4's two legs (`non-overlapping change emits
    NO_OVERLAP`, `no spurious OVERLAP line`) — expected, since M2 is a global
    mutation rather than a leg-scoped one; the plan's table only claimed which
    Test 13 legs it must and must not break.
  - The script was restored byte-identically after each mutation
    (`diff -q` clean) and the suite re-confirmed at 37/37.
- **Verification 3** — `shellcheck` reports no warnings or errors. It emits two
  **pre-existing** `SC1091` *info* notices for the two `source` lines (`:37`,
  `:39`), which this change does not touch.
- **Verification 4** — `tests/test_task_workflow_reentry_drift.sh`: 57/57 pass.
- **Verification 5** — the live smoke returned `UP_TO_DATE` (local `main` is in
  sync), so the helper short-circuits before the extraction stage. Exercised the
  stage directly against this plan instead: `aidocs/framework/*.md` paths are now
  extracted and were **not** under the old allowlist, confirming the fix on real
  input.
- **Verification 6** — handoff artifacts present; t1561's `depends:` is still
  `[]`, its `status:` still `Ready`, and its diff is a single added line.

Note on the smoke output: this plan is unusually noisy to extract from because it
*discusses* path syntax, so fragments such as `b.py` and `file.py` appear as
tokens. They are inert — the exact full-line intersection with the remote diff
discards anything that is not a real remote-changed path, which is the property
that makes removing the root filter safe.
