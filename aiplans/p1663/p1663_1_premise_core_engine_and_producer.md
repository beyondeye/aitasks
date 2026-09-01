---
Task: t1663_1_premise_core_engine_and_producer.md
Parent Task: aitasks/t1663_advisory_task_premise_staleness.md
Sibling Tasks: aitasks/t1663/t1663_2_premise_baseline_field_end_to_end.md, aitasks/t1663/t1663_3_creation_time_seeding_and_carryover.md, aitasks/t1663/t1663_4_workflow_check6_premise_procedure.md, aitasks/t1663/t1663_5_website_docs_premise_staleness.md, aitasks/t1663/t1663_6_retrospective_prompt_rate_evaluation.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1663_1 — Premise-staleness core engine and producer

## Context

A task can sit `Ready` for months while the code its premise depends on moves
underneath it. `aidocs/framework/task_premise_staleness.md` (the t1561 decision
record) fixes an **advisory** mechanism that detects this and fixes its protocol;
t1663 is the tree that lands it. This child builds the **engine only** — nothing
prompts a user yet:

- `.aitask-scripts/lib/task_premise.py` — the **pure** verdict core, generalizing
  `lib/roadmap_premise.py`'s `baseline_for` + `check`. t1655 later swaps the
  roadmap onto it and deletes `roadmap_premise.py`, so its public surface is a
  substitution contract, frozen in `__all__`.
- `.aitask-scripts/aitask_premise_stale.sh check <task_file>` — the **impure**
  git-facing producer, generalizing `aitask_verification_stale.sh`'s shape from
  manual-verification tasks to ordinary ones.

Out of scope (owned by siblings): the `premise_baseline:` writer flag and merge
rule (t1663_2), creation-time seeding and carryover (t1663_3), task-workflow
Step 3 Check 6 (t1663_4), website docs (t1663_5).

## The split (confirmed with the user)

The shell does git; the pure core decides and emits. One verdict engine, so the
published protocol and t1655's future consumer cannot drift.

```
aitask_premise_stale.sh check <task_file>
  git only: cat-file -e probes, log :(literal), origin file surface
    │  interchange rows (stdin) — distinct vocabulary from the published protocol:
    │    REV:<sha>            BASE:<enc sha>|<ts>|<reason-or-empty>
    │    TIER:<A|B|NONE>      ORIGIN:<id>|<FILES|NO_FILES|UNKNOWN_HISTORY>
    │    PATH:<enc path>|<ok|deleted|absent_at_baseline|no_index_history|invalid_reference>
    │    LOG:<enc path>|<sha>|<enc task-ids csv>
    │    GONE:<enc path>|<culprit>|<sanitized subject>
    ▼
  python3 → task_premise.check(rows)                      [PURE]
    │  published protocol lines, fixed order:
    │    BASELINE / CHECKED / FINGERPRINT / FILES /
    │    CHANGED* / DELETED* / UNKNOWN* / DISPLAY / DECISION
    ▼
  shell prints them verbatim, exits 0
```

`CHECKED:` is passed in as `REV:` and echoed — the core never computes it — so
**the core is the single emitter** and the whole protocol is pinnable in one
place. The only lines the shell formats itself are the `python_unavailable` and
`engine_error` SKIPs, because at those points the core is unreachable or
untrusted.

## Implementation

### Pre-phase (risk mitigations)

**`engine_error_fail_open`** — the producer must fail **open**, never loudly,
and must not trust a verdict merely because a `DECISION:` line exists. Add
`engine_error` to `ENV_REASONS`; capture with `out=$("$py" … ) || rc=$?` rather
than letting `set -euo pipefail` abort the script, and never read that status
through a pipeline (`$(… | …)` reports only the last element, and `PIPESTATUS`
inside a command substitution is always 0).

**Structural validation, not a `DECISION:` sniff.** A broken core that emits
malformed content *plus* `DECISION:FRESH` would otherwise become a false
all-clear — precisely the outcome the record forbids. Accept the output only if
all of these hold, else emit the `engine_error` SKIP:

- exit status 0 and non-empty output;
- lines 1–4 are exactly `BASELINE:`, `CHECKED:`, `FINGERPRINT:`,
  `FILES:<digits>`, in that order;
- the last line is `DECISION:` carrying a member of `DECISIONS`; the one before
  it is `DISPLAY:`;
- every line in between starts with `CHANGED:`, `DELETED:` or `UNKNOWN:` and
  nothing else;
- **verdict/evidence consistency** — `FRESH` and `SKIP` require **zero**
  evidence lines, `ASK_STALE` requires **at least one**; `SKIP` additionally
  requires `FINGERPRINT:NONE`. This is what closes the malformed-but-`FRESH`
  hole: the verdict must agree with the evidence that justifies it.

**Silent means silent on both streams.** Every subprocess this helper runs has
its stderr captured, never left to reach the terminal — the core (a traceback),
`followup_origin.py`, and `aitask_revert_analyze.sh`, whose `cmd_task_files`
`warn`s "No commits found for task <id>" on a perfectly ordinary Tier-B miss.
Captured is not discarded: on `engine_error` the first stderr line, sanitized
(`|` → space, single line, truncated to ~120 chars), is folded into the
`DISPLAY:` field, so the diagnostic survives for anyone running the helper
directly while the pick path stays quiet.

Proven by faults injected through the documented `PYTHONPATH` seam — a
`task_premise.py` whose `check` (a) raises, (b) returns `DECISION:FRESH`
alongside a `CHANGED:` line, (c) returns garbage lines then `DECISION:FRESH`,
(d) omits `DISPLAY:` — each asserting `DECISION:SKIP`, exit 0, and that no
`FRESH` ever escapes.

### 1. `.aitask-scripts/lib/task_premise.py` (new, pure)

Module docstring carries both vocabularies (interchange rows in, protocol lines
out) and the t1655 substitution contract, in the shape of `roadmap_premise.py`'s
header. **No `os`/`time`/`subprocess`/`datetime`/`pathlib` imports** — only
`dataclasses`, `hashlib`, and `parallel_admission_vocab` (already pure) for
`encode_path`/`decode_path`. Do **not** modify `roadmap_premise.py`; t1655
deletes it.

`__all__`, pinned by a `PublicSurfaceTests` clone:

```python
__all__ = [
    "FRESH", "ASK_STALE", "SKIP", "DECISIONS",
    "BASELINE_REASONS", "PATH_REASONS", "SCOPE_REASONS", "ENV_REASONS", "REASONS",
    "PATH_STATES", "TIERS", "DEFAULT_DATA_PREFIXES", "FINGERPRINT_VERSION",
    "ROW_PREFIXES", "LINE_PREFIXES", "ORIGIN_STATUSES",
    "Baseline", "PremiseResult",
    "baseline_for", "check", "fingerprint",
]
```

Closed vocabularies — each value a distinct remedy, never one "cannot tell"
bucket:

| tuple | values |
|---|---|
| `BASELINE_REASONS` | `no_origin`, `unknown_history`, `metadata_only` (carried from `roadmap_premise`, kept for `baseline_for`/t1655) + `no_stored_baseline`, `history_rewritten` |
| `PATH_REASONS` | `no_index_history`, `absent_at_baseline`, `invalid_reference` |
| `ORIGIN_STATUSES` | `FILES`, `NO_FILES`, `UNKNOWN_HISTORY` (mirrors the `--batch-map` `STATUS:` vocabulary) |
| `SCOPE_REASONS` | `empty_scope` |
| `ENV_REASONS` | `not_a_git_repo`, `python_unavailable`, `engine_error` |
| `PATH_STATES` | `ok`, `deleted`, + the three `PATH_REASONS` |
| `TIERS` | `A` (curated `file_references:`), `B` (derived origin surface), `NONE` |

`python_unavailable` and `engine_error` live here even though the **shell**
emits them: one closed vocabulary, one source of truth, with the shell citing
this module by name.

Functions:

- `baseline_for(origin_ids, commit_lines, data_prefixes=DEFAULT_DATA_PREFIXES)`
  — **unchanged semantics** from `roadmap_premise`: newest commit naming an
  origin id AND touching a path outside `data_prefixes`, ties broken on sha.
  The v1 producer does not call it (v1 is stored-baseline-only); its named
  consumers are t1655 and the deferred computed-baseline tier, and its
  landing-commit property is the one the record says must survive the swap
  unchanged — so it ships with the carried-over unit tests, not untested.
- `check(rows)` → `PremiseResult` with `.lines` = the full protocol. Verdict is
  an **emptiness test over one evidence list** that `CHANGED`, `DELETED` and
  `UNKNOWN` all append to, so they cannot drift apart. Ordered outcomes:
  unusable baseline → `SKIP` with its reason; resolved baseline + zero paths →
  `SKIP`/`empty_scope` (**never `FRESH`** — nothing was compared); evidence →
  `ASK_STALE`; otherwise `FRESH`.
- `fingerprint(baseline_sha, tier, paths, origin_ids)` → 16-hex digest of a
  canonicalized tuple: `FINGERPRINT_VERSION`, `stored`, sha, tier, sorted
  paths, sorted origin ids — each field `encode_path`-encoded and `|`-joined,
  sha256'd. **Excludes** the checked rev and the baseline timestamp: it binds
  the *metadata* inputs a decision depended on, so ordinary new commits do not
  void a confirmation but a concurrent edit to `file_references:` / origins /
  the stored baseline does. `FINGERPRINT:NONE` on every SKIP.

`DISPLAY:` carries **raw** paths (free-form human text); every other
variable-content field is `encode_path`-encoded; the `DELETED` subject is
sanitized (`|` → space), not encoded — verbatim the `aitask_verification_stale.sh`
parse contract.

### 2. `.aitask-scripts/aitask_premise_stale.sh` (new, impure)

`#!/usr/bin/env bash`, `set -euo pipefail`, sources `lib/terminal_compat.sh`,
`lib/task_utils.sh`, `lib/python_resolve.sh`. Header comment carries the ordered
evaluation and the parse contract, as its template does. Verb `check <task_file>`;
`die` on CLI misuse (a typo'd path must never read as `SKIP`); **exit 0 for every
content state**.

**Ordered evaluation (normative).** The baseline precondition is checked
*before* scope resolution — the reverse of the t1555 helper's order. In v1 nearly
every task lacks a stored baseline, and Tier B costs a `git log --grep` pass;
this ordering keeps the common case at zero git-history work. Consequence to
pin: that SKIP reports `FILES:0`.

1. args → `die` on misuse
2. `resolve_python` empty → shell-formatted SKIP, reason `python_unavailable`
3. no repo root / no HEAD → core with `BASE:||not_a_git_repo`.
   **Contract: cwd must be inside the *code* repository**, and the header says
   so. The root is `git rev-parse --show-toplevel` from the process cwd — it is
   deliberately **not** derived from `dirname "$task_file"`, which would be
   wrong under the data-branch layout: `aitasks/` resolves into the
   `.aitask-data` worktree whose HEAD is the `aitask-data` branch and which
   carries no code paths, so the root would name a tree in which every scope
   path is absent. Cwd is the framework's own convention here — `ait` cds to
   the repo root before dispatching, and `_ait_detect_data_worktree`
   (`lib/task_utils.sh:34`) is itself cwd-relative — so this helper inherits it
   rather than inventing a second rule.
4. `read_yaml_field "$task_file" premise_baseline` empty → core with
   `BASE:||no_stored_baseline`
5. `rev=$(git -C "$repo_root" rev-parse HEAD)` — `-C` here too, like every
   other git call; **pin the rev once** and use that literal sha in
   every probe instead of the moving `HEAD` symbol, so `CHECKED:` is honest
   about what was actually evaluated (a deliberate improvement on the template)
6. `git -C "$repo_root" merge-base --is-ancestor "$sha" "$rev"` fails (exit 1 or
   128 alike) → core with `BASE:<sha>|<ts>|history_rewritten` (the sha still
   shows in `BASELINE:`)
7. **scope**, tier A first:
   - **A** — `get_file_references` (`lib/task_utils.sh:1581`), `_strip_ranges`,
     dedupe on a **newline**-delimited seen-set (a path may legally contain
     `|`); empty-after-strip → `PATH:<raw>|invalid_reference` (required guard:
     `git cat-file -e "<sha>:"` resolves the root tree and exits 0)
   - **B** — only when A is empty: `"$py" "$SCRIPT_DIR/lib/followup_origin.py"
     "$task_file"` → tab-separated row; **`exact` quality only** (`topic` /
     `unknown` refuse to claim causation). Then resolve the origin file surface
     through `aitask_revert_analyze.sh --batch-map --ids-from <origin ids>`,
     reading its `TASKFILES:<id>|<path>` rows — **not `--task-files`**, whose
     `FILE|…` emitter is lossy: `aitask_revert_analyze.sh:390` iterates an
     *unquoted* `$(echo "${!file_ins[@]}" | tr ' ' '\n' | sort)`, so a path
     containing a space is split into two and one containing `*`/`?` is
     glob-expanded against the cwd, and the record itself never encodes `|`.
     `--batch-map` is the lossless seam: its paths come from NUL-framed
     `git log -z --name-only` (no `core.quotePath` escaping, no whitespace
     splitting), and `TASKFILES:` splits on its **first** `|` only, so the path
     is the verbatim remainder. Measured cost 0.77s whole-corpus vs 0.10s, paid
     only on Tier B. Then drop paths under the data prefixes, built from
     `${TASK_DIR}/`, `${PLAN_DIR}/`, `.aitask-gates/` (**injected, not
     hardcoded** — those dirs are configurable).

     **Fail closed on anything this seam cannot state cleanly.** A
     `TASKFILES:` line with no `|` after the id is unparseable → emit
     `PATH:<raw>|invalid_reference`, never drop it silently. `--batch-map` also
     emits `STATUS:<id>|<FILES|NO_FILES|UNKNOWN_HISTORY>` for every queried id
     (never inferred from absence): forward it as `ORIGIN:<id>|<status>` and let
     the core treat an `UNKNOWN_HISTORY` origin as an `UNKNOWN` evidence entry
     keyed by the origin id — a scope that covers less than it claims must not
     read `FRESH`. **Ordering rule, pinned by a test:** if *zero* paths resolved
     the verdict is `SKIP`/`empty_scope` regardless of origin-status unknowns
     ("a task the mechanism cannot evaluate reads `SKIP`"); origin unknowns
     drive `ASK_STALE` only when at least one path was actually checked.
   - neither → `TIER:NONE`, zero `PATH:` rows; the core returns
     `SKIP`/`empty_scope`
8. classify each candidate against **committed trees only**, so a dirty worktree
   is invisible by construction:
   - `git cat-file -e "$sha:$p"` fails → `PATH:…|absent_at_baseline`
   - `git cat-file -e "$rev:$p"` fails → `PATH:…|deleted` + `GONE:` row whose
     culprit comes from `git log --diff-filter=D -M -n1 --format='%s'`
   - both present → `PATH:…|ok` + one `LOG:` row per commit from
     `git log --format='%H|%s' "$sha..$rev" -- ":(literal)$p"`
   `:(literal)` on **every** history query (a curated `docs/a[bc].md` would
   otherwise fnmatch-glob onto `docs/ab.md`); `-C "$repo_root"` on every git call
   (`log` pathspecs are cwd-relative, `<rev>:<path>` is root-relative).
9. hand the rows to the core and **validate its answer before trusting it**
   (see step 10). The glue must put the lib directory on `sys.path` itself —
   verified: a `-c` / stdin program gets `sys.path[0] == ''`, so from the repo
   root `import task_premise` fails outright with no extra setup. The directory
   arrives as `argv[1]` (the glue is single-quoted, so the shell interpolates
   nothing into the program) and is **appended**, never `insert(0)`:

   ```bash
   # The glue is the PROGRAM, so it must not travel on stdin -- stdin is the
   # data channel. `"$py" - <<'PY'` was verified to hand the core an empty
   # stdin (the heredoc replaces the pipe), which would have made every check
   # resolve zero rows and read a silent SKIP/empty_scope.
   _PREMISE_GLUE='
   import sys
   sys.path = [p for p in sys.path if p not in ("", ".")]
   sys.path.append(sys.argv[1])
   import task_premise
   sys.stdout.write("\n".join(task_premise.check(sys.stdin)) + "\n")
   '
   rows=$(printf '%s\n' "${rows[@]}")
   # `$( )` captures stdout ONLY. Without this redirect a raising core prints a
   # full Python traceback to the user's terminal on every pick -- the exact
   # opposite of the silent SKIP the record requires. Capture, do not discard:
   # the diagnostic is folded into DISPLAY: below.
   err_file=$(mktemp); trap 'rm -f "$err_file"' EXIT
   out=$("$py" -c "$_PREMISE_GLUE" "$SCRIPT_DIR/lib" <<< "$rows" 2>"$err_file") || rc=$?
   ```

   A here-string, not a pipeline: `$(a | b)` would report only `b`'s status,
   and `PIPESTATUS` inside a command substitution is always 0 — the redirection
   form leaves `$?` unambiguously the core's. (Single-quoted glue, so the shell
   interpolates nothing into the program; the lib directory arrives as `argv[1]`
   because a quoted body cannot carry `$SCRIPT_DIR`.)

   Resulting order: `PYTHONPATH` dirs, stdlib, then `<SCRIPT_DIR>/lib`. Both
   properties are pinned by tests — production import works from an arbitrary
   cwd, and a `PYTHONPATH` shadow still wins.
10. validate the returned protocol (below); on any failure emit the
    `engine_error` SKIP. Otherwise print the lines verbatim; exit 0.

### 3. Registration — the 5 allowlist touchpoints

Run `./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist
aitask_premise_stale.sh`, then verify with `audit-helper-whitelist` that no
`MISSING:` line remains. Touchpoints: `.claude/settings.local.json`,
`.codex/rules/default.rules`, `seed/claude_settings.local.json`,
`seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`.

**Commit hazard — check before committing these five.** They currently carry
another session's uncommitted `aitask_resource_admission.sh` line. Committing a
path commits everything uncommitted in it, so re-run `git diff` on the five at
commit time: if the foreign line has landed on its own by then, commit normally;
if not, keep the allowlist edits out of this task's commit and say so rather
than sweeping a neighbour's work in.

### 4. `tests/test_parallel_admission_purity.py`

One line: add `"task_premise"` to `PURE_MODULES`. `PURE_SOURCES`, the AST scan
and the poisoned-`sys.modules` import check all derive from that tuple.

### Post-phase (risk mitigations)

**`protocol_vocabulary_drift_guard`** — the interchange row names (`REV`,
`BASE`, `TIER`, `ORIGIN`, `PATH`, `LOG`, `GONE`) and the published protocol line
names (`BASELINE`, `CHECKED`, `FINGERPRINT`, `FILES`, `CHANGED`, `DELETED`,
`UNKNOWN`, `DISPLAY`, `DECISION`) are each enumerated by a module constant
(`ROW_PREFIXES` / `LINE_PREFIXES`, both in `__all__`). A test in
`tests/test_task_premise.py` asserts the two sets are **disjoint** and that the
parser and emitter accept/produce nothing outside them, so a later addition to
one vocabulary cannot silently shadow the other. The producer's structural
validator (pre-phase) is a **second** encoding of the line vocabulary in bash,
so `tests/test_premise_stale.sh` also asserts the prefixes that validator
accepts are exactly `LINE_PREFIXES` — the drift this guard exists to catch runs
across the language boundary, not only inside the module.

## Verification

**`tests/test_task_premise.py`** (new; unittest, `sys.path.insert` of
`.aitask-scripts/lib`, modeled on `tests/test_roadmap_premise.py`):

- `PublicSurfaceTests` — every non-underscore, non-module attribute equals
  `__all__` exactly (the t1655 substitution pin).
- Baseline: landing-commit rule, a later task-data commit does not move it,
  `metadata_only` ≠ `unknown_history`, `no_origin`, prefixes are a parameter,
  deterministic tie-break — carried over from the roadmap suite.
- Verdicts: unchanged → `FRESH`; `CHANGED`/`DELETED`/`UNKNOWN` each →
  `ASK_STALE`; **`UNKNOWN` moves the verdict exactly like `CHANGED`**; resolved
  baseline + empty scope → `SKIP`, and specifically **not** `FRESH` and **not**
  `ASK_STALE`; each `BASELINE_REASONS`/`ENV_REASONS` value → `SKIP`.
- Protocol: fixed line order; malformed rows skipped, never raised on; delimiter
  and `%` round-trip losslessly; same input twice is byte-identical; **negative
  control** — a real change changes the output.
- Fingerprint: identical inputs → identical digest; changing the baseline sha,
  the tier, any path, or any origin id → **different** digest; changing the
  checked rev or the baseline timestamp → **same** digest.
- `protocol_vocabulary_drift_guard` (post-phase): `ROW_PREFIXES` and
  `LINE_PREFIXES` are disjoint, and the parser/emitter accept/produce nothing
  outside them.
- **t1655 substitutability**: feed `check()` rows derived from
  `roadmap_premise`-shaped `COMMIT:` index fixtures and reproduce the roadmap
  suite's verdicts — the test that proves the core can actually absorb its
  second consumer.

**`tests/test_premise_stale.sh`** (new; plain-function bodies, no `( … )`
subshells, so `tests/lib/asserts.sh`'s in-process counters suffice — same choice
and same stated reason as `tests/test_verification_stale.sh`). Fixture factories
`new_repo` / `commit_file` / `remove_file` / `mk_task` carried over, `:(literal)`
included:

- Clean scope → `FRESH`; changed → `ASK_STALE` + `CHANGED:` naming the culprit
  task; deleted → `ASK_STALE` + `DELETED:` (caught by the probe, never
  mislabeled `CHANGED`); uncheckable entry → `UNKNOWN:` → `ASK_STALE`.
- **Tier matrix**: stored baseline × (Tier A curated | Tier B derived origin);
  no stored baseline → `SKIP`, `FILES:0`; Tier B with a `topic`-quality origin →
  `SKIP`, never `FRESH`; a Tier B fixture whose origin commits touch **both**
  `aitasks/`-prefixed and code paths, asserting only the code paths enter scope.
- **History rewrite**: baseline not an ancestor of the checked rev → `SKIP` —
  both the exit-1 (unrelated commit) and exit-128 (garbage sha) arms.
- **Dirty worktree**: an uncommitted edit to a scope file emits no `CHANGED:`
  and flips no verdict.
- Encoding: `|` in a path encodes; a literal `%7C` filename round-trips;
  glob-shaped paths do not absorb a neighbour's change nor inflate their own
  evidence; ranges stripped, multi-range stripped, duplicate ranges dedupe to
  one `FILES:` unit.
- `FINGERPRINT:` is stable across an unrelated commit but changes when
  `file_references:` is edited.
- Baseline advance to the `CHECKED:` sha stops the prompt re-firing.
- `engine_error_fail_open` (pre-phase), four fixtures through the `PYTHONPATH`
  seam — `check` raises; `FRESH` emitted **alongside** a `CHANGED:` line;
  garbage lines then `FRESH`; `DISPLAY:` omitted — each → `DECISION:SKIP`,
  exit 0, no `FRESH` escaping, stdout carrying **only** the protocol, and
  **the helper's own stderr empty** (assert on a separately redirected stderr
  capture, not merged into stdout — the raising-core fixture would print a
  traceback there otherwise). Same stderr-empty assertion on a Tier-B miss,
  where `aitask_revert_analyze.sh` warns.
- **Rows actually reach the core** — the regression that the heredoc form would
  have caused: a task with two curated scope entries reports `FILES:2` through
  the *real* `check` invocation (not a hand-built call), so an empty-stdin glue
  fails loudly instead of degrading to a plausible `SKIP`. Paired with a direct
  glue smoke test asserting the core echoes back a known `REV:` value.
- **Import path**, tested where it is actually provable: invoke the glue
  directly from `/tmp` (it has no git preconditions) and assert the core
  imports and answers; separately assert a `PYTHONPATH` shadow still wins.
  These are the two halves of the ordering the glue depends on. The *producer*
  is deliberately not tested from an arbitrary cwd — step 3 would emit
  `not_a_git_repo` first, so such a test could only prove the precondition.
- **Cwd portability within the repo**: the producer gives identical output from
  the fixture repo root and from a subdirectory of it — the property `-C
  "$repo_root"` on every git call and root-relative `<rev>:<path>` exist to
  provide.
- **Data-worktree guard**: run with cwd inside a task-data worktree whose HEAD
  is a branch carrying no code. Assert `DECISION:SKIP` — never `FRESH`, never
  `ASK_STALE`. It fails closed through the ancestry check (a code-branch
  baseline is no ancestor of the data branch); this pins that behavior rather
  than leaving it to be inferred.
- **Tier B hostile paths**: an origin whose landed surface includes filenames
  containing a space, a `|`, and a `*`; each must appear once, verbatim
  (`|` encoded), with no splitting, no glob expansion against the cwd, and no
  neighbour absorbed — the case `--task-files` would have failed.
- **Tier B scope completeness**: an `UNKNOWN_HISTORY` origin alongside a
  resolvable one → `ASK_STALE`, never `FRESH`; an `UNKNOWN_HISTORY` origin with
  **zero** resolved paths → `SKIP`/`empty_scope`; an unparseable `TASKFILES:`
  row → `invalid_reference`, never silently dropped.
- **Negative controls**: `python_unavailable` SKIP driven through the real
  `resolve_python` (`env HOME=<empty dir> PATH=<empty dir>`, no `AIT_PYTHON`),
  not a stub; a deliberately broken input per tier must **not** read `FRESH`;
  CLI misuse (missing verb, nonexistent file) **dies** rather than printing
  `SKIP`.
- Allowlist coverage: the helper name appears in all five touchpoint files —
  the hardcoded block mirroring
  `test_verification_stale.sh::test_helper_is_in_every_invocation_allowlist`.

**Commands**

```bash
shellcheck .aitask-scripts/aitask_premise_stale.sh
bash tests/test_premise_stale.sh
bash tests/run_all_python_tests.sh --test-dir tests   # or, narrowed:
python3 -m unittest tests.test_task_premise tests.test_parallel_admission_purity -v
```

Read only the last line of the Python runner for the verdict
(`PYTHON SUITE: PASSED|FAILED`), and do not pipe it without `pipefail`.

Post-implementation, cleanup, archival and merge follow **Step 9** of the
shared task-workflow.

## Risk

### Code-health risk: medium

- Under `set -euo pipefail`, an unexpected exception in the pure core makes the
  producer exit non-zero instead of the mandated fail-open `SKIP` — a stated
  contract violation on a path child 4 calls at **every** task pick · severity:
  medium · → mitigation: inline pre-phase engine_error_fail_open
- The mechanism carries two vocabularies (interchange rows in, published
  protocol out) that must stay disjoint and enumerated, or evidence silently
  mismatches between the halves · severity: low · → mitigation: inline
  post-phase protocol_vocabulary_drift_guard
- `baseline_for` ships with no production caller in v1 — its consumers are the
  unit tests, the deferred computed-baseline tier, and t1655 · severity: low ·
  → mitigation: named artifact exists (t1655); no action
- The five agent-config allowlist files currently hold another session's
  uncommitted `aitask_resource_admission.sh` line; committing those paths would
  sweep a neighbour's work into this task's commit · severity: medium · →
  mitigation: the commit-time re-check written into Implementation step 3

### Goal-achievement risk: medium

- **Tier B is structurally near-unreachable in v1.** Measured on this corpus
  just now: 107 of the 108 active tasks carrying `verifies:` are
  `issue_type: manual_verification`, and task-workflow Step 3 Check 3 routes
  those away *before* the premise check runs. `exact` quality requires
  `verifies:` — `followup_origin.py`'s rule 1 makes `anchor` "never an exact
  origin" by contract, and `--followup-of` writes only `anchor:`. So the
  derived-scope half ships correct but dormant, and t1663_3's `--followup-of`
  seeding trigger would stamp baselines that can never resolve a scope ·
  severity: high · → mitigation: t1673 (spawned
  **before** task — a prerequisite, not a retrospective note)
- The core exists to be absorbed by t1655; an interchange shape that only fits
  the shell producer would fail that substitution contract · severity: medium ·
  → mitigation: covered by the t1655-substitutability test in `## Verification`

### Planned mitigations
- timing: pre-phase | name: engine_error_fail_open | type: bug | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — non-zero exit instead of fail-open SKIP | desc: degrade any core failure to a SKIP with exit 0 and prove it by injecting a raising core through PYTHONPATH
- timing: before | name: tier_b_reachability_correction | type: documentation | priority: medium | effort: low | inline_risk: high | added_complexity: medium | addresses: goal-achievement — Tier B structurally near-unreachable in v1 | desc: correct the record's Tier-B/Seeding sections, fix t1663_3's seeding-eligibility criterion, and wire t1663_3 to depend on this task so it cannot be picked unguarded | created: t1673
- timing: post-phase | name: protocol_vocabulary_drift_guard | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — two vocabularies drifting | desc: enumerate ROW_PREFIXES and LINE_PREFIXES as module constants and assert they are disjoint and exhaustive over the parser and emitter

### Reassessment after inlining

Levels re-derived against the augmented plan. **Code-health stays `medium`**:
the fail-open pre-phase and the drift guard remove the two code risks, but the
shared-allowlist commit hazard is a process risk no inline phase can retire —
it is resolved at commit time or the allowlist edits are held back.
**Goal-achievement stays `medium`**: promoting the Tier-B correction to a
blocking *before* task stops t1663_3 from seeding unusable baselines, but it
does not change the fact that this child ships a correct-and-dormant
derived-scope tier until that correction settles what the seeding rule should
be.

**What approving this plan means for the session:** the confirmed *before*
mitigation is created at Step 7 as an independent task this one depends on, and
this session then **stops** — t1663_1 resumes after `tier_b_reachability_correction`
lands. That is the point of making it a prerequisite: an after-timed note would
leave a window in which `/aitask-pick 1663_3` runs against the uncorrected
criterion.
