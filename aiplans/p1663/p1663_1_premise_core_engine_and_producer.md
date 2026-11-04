---
Task: t1663_1_premise_core_engine_and_producer.md
Parent Task: aitasks/t1663_advisory_task_premise_staleness.md
Sibling Tasks: aitasks/t1663/t1663_2_premise_baseline_field_end_to_end.md, aitasks/t1663/t1663_3_creation_time_seeding_and_carryover.md, aitasks/t1663/t1663_4_workflow_check6_premise_procedure.md, aitasks/t1663/t1663_5_website_docs_premise_staleness.md, aitasks/t1663/t1663_6_retrospective_prompt_rate_evaluation.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-04 19:09
---

# t1663_1 — Premise-staleness core engine and producer

## Context

A task can sit `Ready` for months while the code its premise depends on moves
underneath it. `aidocs/framework/task_premise_staleness.md` (the t1561 decision
record, corrected by t1673 in 594c5875b) fixes an **advisory** mechanism that
detects this and fixes its protocol; t1663 is the tree that lands it. This child
builds the **engine only** — nothing prompts a user yet, and nothing invokes the
helper from a skill yet:

- `.aitask-scripts/lib/task_premise.py` — the **pure** verdict core, generalizing
  `lib/roadmap_premise.py`'s `baseline_for` + `check`. t1655 later swaps the
  roadmap onto it and deletes `roadmap_premise.py`, so its public surface is a
  substitution contract, frozen in `__all__`.
- `.aitask-scripts/aitask_premise_stale.sh check <task_file>` — the **impure**
  git-facing producer, generalizing `aitask_verification_stale.sh`'s shape from
  manual-verification tasks to ordinary ones.
- An opt-in `--encode-paths` mode on the batch map (`lib/task_file_sets.py`,
  passed through by `aitask_revert_analyze.sh --batch-map`) so the Tier-B origin
  surface survives arbitrary filenames.

Out of scope (owned by siblings): the `premise_baseline:` writer flag and merge
rule (t1663_2), creation-time seeding and carryover (t1663_3), the task-workflow
Step 3 premise check **and the helper's 5-touchpoint allowlist registration**
(t1663_4 — the child that makes the helper skill-invoked), website docs
(t1663_5). Also consumed later by t1981_6 (obsolescence layer) as one evidence
row; t1663 owns "needs refresh", t1981 owns "still worth doing".

**The governing invariant.** `FRESH` is a *positive* claim, never the absence of
a failure: it requires every scope path to be present at both ends **and** to
carry a successful, count-attested history query that returned zero commits.
Every probe failure, every malformed or missing row, every unrepresentable name,
every baseline that is not an immutable commit id maps to evidence (`UNKNOWN`/`DELETED`/`CHANGED` → `ASK_STALE`) or to `SKIP` —
never to the no-evidence branch.

## Verification pass (2026-11-04, tree at c0a6bbd40)

The plan was written 2026-09-01 and never verified. Checked against the current
tree and the t1673-corrected record:

- **Still holds:** the record's protocol block, the Tier-A/Tier-B/baseline
  axes, and every input this child builds on are unchanged since 2026-09-01:
  `roadmap_premise.py`, `followup_origin.py` (5-field tab row, `exact` only
  from `verifies:`), `aitask_verification_stale.sh`, `test_roadmap_premise.py`,
  `test_parallel_admission_purity.py`. t1673's correction touches only Tier-B
  *eligibility/seeding* prose (owned by t1663_3); the producer already resolves
  Tier B for any task with an `exact` origin.
- **Corrected in this revision:**
  1. **Allowlist registration moved to t1663_4** (user decision): the five
     touchpoint files carry uncommitted hunks of live task t2198, and
     `aitasks_extension_points.md` whitelists only skill-invoked helpers.
  2. **Glue bug:** `check()` returns a `PremiseResult`; the glue joins `.lines`.
  3. **`CHECKED:NONE`** is defined for SKIPs reached before the rev is pinned.
  4. **Tier-B subprocess failure** (PyYAML missing, batch-map framing error) was
     unhandled under `set -e` → now `SKIP`/`scope_error`.
  5. **`--ids-from` takes a file or `-`**; `--batch-map` walks `git log --all`
     and resolves its root from cwd, so it runs with cwd = repo root.
  6. **Purity suite:** `PURE_MODULES` feeds the AST scan only; the poisoned
     import names two modules by hand → generalized to loop.
  7. **Bash test conventions:** `scratch_cwd.sh` (t1826) and `fixture_root.sh`
     (t2055), as `tests/test_verification_stale.sh` uses them now.
  8. **`python_unavailable` control** needs a shim `PATH` (all executables but
     `python*`/`pypy*`) and `_AIT_RESOLVED_PYTHON` unset.
  9. Line numbers: `get_file_references` `lib/task_utils.sh:3381`,
     `_ait_detect_data_worktree` `:77`, `read_yaml_field` `lib/yaml_utils.sh:172`.
- **Review round (user, 2026-11-04) — three blocking findings, all verified in
  code and addressed:**
  10. **Malformed evidence could produce `FRESH`.** The draft skipped malformed
      `PATH:`/`LOG:`/`GONE:` rows, so a dropped `LOG:` row erased the only
      change evidence while the output stayed structurally valid. → strict
      parsing + count attestation (core §1, "Row integrity").
  11. **A failed `git log` read as unchanged.** The template's
      `log_out=$(git … log …) || log_out=""` maps exit 128 to "no commits"; the
      reviewer showed `log.date=invalid-date-mode` passes both `cat-file -e`
      probes while `git log` exits 128. → explicit status, `history_unavailable`
      (producer step 8).
  12. **`--batch-map` is not lossless at its output.** `task_file_sets.py`
      `_emit` writes raw paths into newline-framed `TASKFILES:`/`COMMIT:`/
      `TRACKED:` records, so one newline-bearing filename *anywhere* in the
      walked history splits a record or forges a `TASKFILES:` row. →
      `--encode-paths` mode, LF/CR-aware encoding end to end (§3, step 7B).
  13. **A symbolic baseline reads `FRESH`** (second review round). The template
      split passes any stored text to `merge-base`; `HEAD` is an ancestor of the
      pinned rev, so `HEAD..<rev>` is empty even when watched files changed. Task
      files are editable, so t1663_2's writer validation cannot protect the
      reader. → an immutable commit-ID grammar enforced by the reader *before
      any probe* and again by the core (step 4, §1), `SKIP`/`invalid_baseline`
      otherwise.
- **Session note:** the before-mitigation `tier_b_reachability_correction`
  (t1673) has **landed**, so Step 7 finds a landed witness and does not stop.

## The split (confirmed with the user)

The shell does git; the pure core decides and emits. One verdict engine, so the
published protocol and t1655's future consumer cannot drift.

```
aitask_premise_stale.sh check <task_file>
  git only: cat-file -e probes, log :(literal), origin file surface
    │  interchange rows (stdin) — distinct vocabulary from the published protocol:
    │    REV:<sha>
    │    BASE:<enc sha>|<ts>|<reason-or-empty>
    │    TIER:<A|B|NONE>|<n_paths>|<n_origins>          (counts attest the rows below)
    │    ORIGIN:<id>|<FILES|NO_FILES|UNKNOWN_HISTORY>
    │    PATH:<enc path>|ok|<n_log>                    (n_log attests its LOG rows)
    │    PATH:<enc path>|<deleted|absent_at_baseline|history_unavailable|invalid_reference>
    │    LOG:<enc path>|<40-hex sha>|<task-ids csv>
    │    GONE:<enc path>|<culprit>|<sanitized subject>
    ▼
  python3 → task_premise.check(rows).lines                [PURE]
    │  published protocol lines, fixed order:
    │    BASELINE / CHECKED / FINGERPRINT / FILES /
    │    CHANGED* / DELETED* / UNKNOWN* / DISPLAY / DECISION
    ▼
  shell validates, prints them verbatim, exits 0
```

**Encoding (interchange and published protocol alike):** `%`→`%25` first, then
`|`→`%7C`, LF→`%0A`, CR→`%0D`; decode in reverse with `%25` last. It extends
`parallel_admission_vocab.encode_path` (composed on it, not a copy) so a
newline-bearing name stays one field on one line; injective because `%` is
encoded first. `DISPLAY:` is free text with raw paths **except** LF/CR, which it
shows as `%0A`/`%0D` so the line framing can never break.

`CHECKED:` is passed in as `REV:` and echoed (`CHECKED:NONE` when no `REV:` row)
— the core never computes it — so **the core is the single emitter**. The only
lines the shell formats itself are the `python_unavailable` and `engine_error`
SKIPs, because there the core is unreachable or untrusted.

The `BASE:` row's reason field carries **whichever precondition failed**
(`not_a_git_repo`, `no_stored_baseline`, `history_rewritten`, `scope_error`) —
the core's rule is generic: a known reason → `SKIP` with that reason (the sha,
when present, still shows in `BASELINE:`).

## Implementation

**Shared-file gate (every existing file, before its first edit):** run
`git diff --quiet HEAD -- <file>` immediately before the first write to each of
`.aitask-scripts/lib/task_file_sets.py`, `.aitask-scripts/aitask_revert_analyze.sh`,
`tests/test_task_file_sets.py`, `tests/test_revert_analyze_batch.sh`,
`tests/test_parallel_admission_purity.py`,
`aidocs/framework/task_premise_staleness.md`; record its sha256 after each of my
writes and re-check it (plus `HEAD:<file>` unchanged and
`git diff --cached --quiet -- <file>`) before every later write and before the
commit. A foreign hunk → stop and ask. New files need no gate. The five
allowlist files are **not touched** by this child. (At plan time none of the six
is dirty or claimed by an `Implementing` task; t1555_2 only *reads*
`--task-files`.)

### Pre-phase (risk mitigations)

1. [engine_error_fail_open] The producer must fail **open**, never loudly,
   and must not trust a verdict merely because a `DECISION:` line exists. Add
   `engine_error` to `ENV_REASONS`; capture with `out=$("$py" … ) || rc=$?`
   rather than letting `set -euo pipefail` abort the script, and never read that
   status through a pipeline.

   **Structural validation, not a `DECISION:` sniff.** Accept the core's output
   only if all of these hold, else emit the `engine_error` SKIP:

   - exit status 0 and non-empty output;
   - lines 1–4 are exactly `BASELINE:` (`NONE` or `<40|64 lowercase hex>|<ts>`),
     `CHECKED:` (`NONE` or 40/64 lowercase hex), `FINGERPRINT:` (`NONE` or 16
     hex), `FILES:<digits>`, in that order;
   - the last line is `DECISION:` carrying a member of `DECISIONS`; the one
     before it is `DISPLAY:`;
   - every line in between starts with `CHANGED:`, `DELETED:` or `UNKNOWN:`;
   - **verdict/evidence consistency** — `FRESH` and `SKIP` require **zero**
     evidence lines, `ASK_STALE` requires **at least one**; `SKIP` requires
     `FINGERPRINT:NONE`; `FRESH`/`ASK_STALE` require a hex `BASELINE:`, a hex
     `CHECKED:` and a 16-hex `FINGERPRINT:`.

   The validator cannot see evidence the core already discarded — that hole is
   closed inside the core by "Row integrity" (§1), not here.

   The accepted prefixes live in one single-line bash array
   (`_PREMISE_LINE_PREFIXES=(BASELINE CHECKED FINGERPRINT FILES CHANGED DELETED UNKNOWN DISPLAY DECISION)`)
   so the post-phase drift guard can pin it against `LINE_PREFIXES`.

   **Silent means silent on both streams.** Every subprocess's stderr is
   captured (the core's traceback, `followup_origin.py`, `--batch-map`'s
   `FRAMING_ERROR:`, failing `git log`s), never left to reach the terminal.
   On `engine_error` / `scope_error` the first captured line, sanitized
   (`|` → space, single line, ~120 chars), is appended to `DISPLAY:`.

   Proven by faults injected through the documented `PYTHONPATH` seam — a
   `task_premise.py` whose `check` (a) raises, (b) returns `DECISION:FRESH`
   alongside a `CHANGED:` line, (c) returns garbage lines then `DECISION:FRESH`,
   (d) omits `DISPLAY:` — each asserting `DECISION:SKIP`, exit 0, no `FRESH`.

### 1. `.aitask-scripts/lib/task_premise.py` (new, pure)

Module docstring carries both vocabularies, the encoding rule, the governing
invariant, and the t1655 substitution contract, in the shape of
`roadmap_premise.py`'s header. **No `os`/`time`/`subprocess`/`datetime`/`pathlib`
imports** — only `dataclasses`, `hashlib`, `re`, and `parallel_admission_vocab`
(already pure). Do **not** modify `roadmap_premise.py`; t1655 deletes it.

`__all__`, pinned by a `PublicSurfaceTests` clone:

```python
__all__ = [
    "FRESH", "ASK_STALE", "SKIP", "DECISIONS",
    "BASELINE_REASONS", "PATH_REASONS", "SCOPE_REASONS", "ENV_REASONS", "REASONS",
    "PATH_STATES", "TIERS", "DEFAULT_DATA_PREFIXES", "FINGERPRINT_VERSION",
    "ROW_PREFIXES", "LINE_PREFIXES", "ORIGIN_STATUSES",
    "Baseline", "PremiseResult",
    "baseline_for", "check", "fingerprint", "encode_field", "decode_field",
]
```

(`encode_field`/`decode_field` are public because the producer's shell twin and
t1663_4's procedure must reproduce them; the drift guard pins the shell twin.)

Closed vocabularies — each value a distinct remedy:

| tuple | values |
|---|---|
| `BASELINE_REASONS` | `no_origin`, `unknown_history`, `metadata_only` (carried for `baseline_for`/t1655) + `no_stored_baseline`, `invalid_baseline`, `history_rewritten` |
| `PATH_REASONS` | `no_index_history`, `absent_at_baseline`, `invalid_reference`, `history_unavailable`, `malformed_row` |
| `ORIGIN_STATUSES` | `FILES`, `NO_FILES`, `UNKNOWN_HISTORY` |
| `SCOPE_REASONS` | `empty_scope`, `scope_error` |
| `ENV_REASONS` | `not_a_git_repo`, `python_unavailable`, `engine_error` |
| `PATH_STATES` | `ok`, `deleted`, `absent_at_baseline`, `history_unavailable`, `invalid_reference`, `no_index_history` |
| `TIERS` | `A` (curated `file_references:`), `B` (derived origin surface), `NONE` |

Functions:

- `baseline_for(origin_ids, commit_lines, data_prefixes=DEFAULT_DATA_PREFIXES)`
  — **unchanged semantics** from `roadmap_premise` (landing-commit rule, sha
  tie-break). No v1 production caller; ships with the carried-over unit tests.
- `check(rows)` → `PremiseResult` with `.lines` = the full protocol. Verdict is
  an **emptiness test over one evidence list** that `CHANGED`, `DELETED` and
  `UNKNOWN` all append to.

  **Row integrity — every row is parsed or it poisons the result; every count is
  attested.** The interchange has exactly one producer per consumer, so a row
  that does not parse is a defect report, never noise to skip:

  | condition | outcome |
  |---|---|
  | a line with no known `ROW_PREFIXES` prefix; `REV:`/`BASE:`/`TIER:` missing, duplicated or malformed; unknown reason/state/tier token; an `ORIGIN:` row that does not parse | `SKIP`/`engine_error` |
  | `BASE:` with an empty reason whose sha field is not a full 40- or 64-hex object id (`HEAD`, a branch name, an abbreviation) — the core re-checks the reader's grammar so no producer (t1655's adapter included) can smuggle a symbol through | `SKIP`/`invalid_baseline`, `BASELINE:NONE` |
  | `REV:` not a full 40- or 64-hex object id | `SKIP`/`engine_error` |
  | parsed `PATH:` rows ≠ `TIER` `n_paths`, or parsed `ORIGIN:` rows ≠ `n_origins`, or a path with two `PATH:` rows | `SKIP`/`engine_error` (the scope itself is unknown) |
  | a `LOG:`/`GONE:` row whose path field decodes but whose other fields do not parse (sha not 40-hex, wrong field count) | `UNKNOWN:<path>|malformed_row` for that path |
  | a `LOG:`/`GONE:` row whose path field does not decode, or names no `PATH:` row | `SKIP`/`engine_error` |
  | `PATH:…|ok|<n>` with a non-integer `n`, or parsed `LOG:` count for that path ≠ `n` | `UNKNOWN:<path>|malformed_row` |
  | `PATH:…|deleted` with no/malformed `GONE:` | still `DELETED:` (culprit `unknown`) |

  So a dropped or mangled `LOG:` row can only *add* evidence (via the count
  mismatch), and a dropped `PATH:` row can only produce `SKIP`. Ordered outcomes
  after integrity: a precondition reason on `BASE:` → `SKIP` with that reason;
  zero paths → `SKIP`/`empty_scope` (**never `FRESH`**, regardless of `ORIGIN:`
  unknowns); evidence (incl. one `UNKNOWN:<origin id>|unknown_history` per
  `UNKNOWN_HISTORY` origin, only when ≥1 path was checked) → `ASK_STALE`;
  otherwise `FRESH`. `CHANGED:` carries the attested count and the deduped,
  sorted task-id union.
- `fingerprint(baseline_sha, tier, paths, origin_ids)` → 16-hex digest of the
  canonicalized tuple (`FINGERPRINT_VERSION`, `stored`, sha, tier, sorted paths,
  sorted origin ids — each `encode_field`-encoded, `|`-joined, sha256'd).
  Excludes the checked rev and the baseline timestamp. `FINGERPRINT:NONE` on
  every SKIP.
- `encode_field` / `decode_field` — the LF/CR-aware extension of
  `vocab.encode_path` / `decode_path` described above.

The `DELETED` subject is sanitized (`|` → space), not encoded (`%s` is
single-line).

### 2. `.aitask-scripts/aitask_premise_stale.sh` (new, impure)

`#!/usr/bin/env bash`, `set -euo pipefail`, sources `lib/terminal_compat.sh`,
`lib/task_utils.sh`, `lib/python_resolve.sh`. Header comment carries the
ordered evaluation, the governing invariant, and the parse contract (incl. the
LF/CR encoding). Verb `check <task_file>`; `die` on CLI misuse; **exit 0 for
every content state**. Shell `_enc`/`_dec` implement `encode_field`/
`decode_field` exactly.

**Ordered evaluation (normative).** Baseline before scope, so the common v1
case (no stored baseline) costs zero git-history work; that SKIP reports
`FILES:0`.

1. args → `die` on misuse
2. `resolve_python` empty → shell-formatted SKIP (`BASELINE:NONE`,
   `CHECKED:NONE`, `FINGERPRINT:NONE`, `FILES:0`), reason `python_unavailable`
3. no repo root / no HEAD → core with `BASE:||not_a_git_repo`, `TIER:NONE|0|0`,
   no `REV:`. **Contract: cwd must be inside the *code* repository** (root =
   `git rev-parse --show-toplevel` from cwd, never `dirname "$task_file"`, which
   resolves into the `.aitask-data` worktree; same convention as `ait` and
   `_ait_detect_data_worktree`, `lib/task_utils.sh:77`).
4. `read_yaml_field "$task_file" premise_baseline` empty → core with
   `BASE:||no_stored_baseline`, `TIER:NONE|0|0`, no `REV:`. Stored form
   `<sha> @ <ts>`, split as in the template — then **the immutable commit-ID
   grammar, before any git probe:** the sha half must match
   `^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$` (a full SHA-1 or SHA-256 object id;
   normalized to lowercase). Anything else — `HEAD`, `HEAD~1`, `@{u}`, a branch
   or tag name, an abbreviated sha, `<sha>^`, an empty sha with a timestamp, a
   value with whitespace — → core with `BASE:<enc raw>|<ts>|invalid_baseline`,
   `TIER:NONE|0|0`, no `REV:`. A symbol is never handed to `merge-base` or
   `log`: `HEAD` would pass the ancestry check and make `HEAD..<rev>` empty, a
   false `FRESH`. A well-formed id that is not a reachable commit still falls
   out at step 6 (`history_rewritten`).
5. `rev=$(git -C "$repo_root" rev-parse HEAD)` — pinned once; every probe uses
   the literal sha
6. `git -C "$repo_root" merge-base --is-ancestor "$sha" "$rev"` fails (exit 1 or
   128 alike) → core with `REV:` + `BASE:<sha>|<ts>|history_rewritten`
7. **scope**, tier A first; candidates held as **encoded** strings (the dedupe
   key, newline-free by construction), decoded only at the git probes:
   - **A** — `get_file_references` (`lib/task_utils.sh:3381`), `_strip_ranges`
     (template regex), `_enc`, dedupe on a newline-delimited seen-set of encoded
     keys; empty-after-strip → `PATH:<enc raw>|invalid_reference`.
   - **B** — only when A is empty:
     `"$py" "$SCRIPT_DIR/lib/followup_origin.py" "$task_file"` (stderr captured,
     `|| rc=$?`) → one tab row; **`exact` quality only**. Then
     `printf '%s\n' "${origin_ids[@]}" | ( cd "$repo_root" &&
     "$SCRIPT_DIR/aitask_revert_analyze.sh" --batch-map --encode-paths
     --ids-from - ) > "$map_file" 2> "$err_file" || rc=$?`. Read
     `TASKFILES:<id>|<enc path>` rows (split on the first `|`; the remainder is
     already encoded and is used as-is as the key), and `STATUS:<id>|<status>`
     → `ORIGIN:<id>|<status>`. Drop paths whose **decoded** form starts with
     `${TASK_DIR}/`, `${PLAN_DIR}/`, `.aitask-gates/` (injected, not hardcoded).
     **Fail closed:** either subprocess non-zero → core with `REV:` +
     `BASE:<sha>|<ts>|scope_error` (stderr line appended to DISPLAY); a
     `TASKFILES:` line with no `|` after the id → `PATH:<enc raw>|invalid_reference`;
     a line in the map output matching none of the batch-map record prefixes →
     `scope_error` (with `--encode-paths` this cannot happen, so it signals a
     broken seam rather than a filename). Ordering rule: zero resolved paths →
     `SKIP`/`empty_scope` regardless of origin unknowns.
     Known breadth, accepted: `git log --all` can surface paths from unmerged
     refs → `UNKNOWN:…|absent_at_baseline` (toward `ASK_STALE`, never `FRESH`).
   - neither → `TIER:NONE|0|0`; the core returns `SKIP`/`empty_scope`
   - Emit `TIER:<A|B>|<number of PATH rows that follow>|<number of ORIGIN rows>`.
8. classify each candidate `p` (decoded) against **committed trees only**:
   - `git cat-file -e "$sha:$p"` fails → `PATH:<enc>|absent_at_baseline`
   - `git cat-file -e "$rev:$p"` fails → `PATH:<enc>|deleted` + `GONE:` row from
     `git log --diff-filter=D -M -n1 --format='%s' "$sha..$rev" -- ":(literal)$p"`
     (a failure there leaves the culprit `unknown`; `DELETED` stands)
   - both present → **explicit status, never `|| x=""`:**
     ```bash
     if log_out=$(git -C "$repo_root" log --format='%H|%s' "$sha..$rev" \
             -- ":(literal)$p" 2>>"$err_file"); then
         n=$(count non-empty lines of $log_out)        # 0 = positive "unchanged"
         rows+=("PATH:$key|ok|$n")
         # one LOG:$key|<sha>|<ids> per line
     else
         rows+=("PATH:$key|history_unavailable")      # → UNKNOWN → ASK_STALE
     fi
     ```
     A cat-file failure caused by a broken repository rather than a missing path
     still maps to evidence (`absent_at_baseline` / `deleted`), never to `ok`.

   `:(literal)` on every history query; `-C "$repo_root"` on every git call.
9. hand the rows to the core and validate its answer before trusting it. The
   glue appends the lib dir to `sys.path` (a `-c` program gets
   `sys.path[0] == ''`); single-quoted, so nothing is interpolated into it:

   ```bash
   # The glue is the PROGRAM; stdin is the data channel (`"$py" - <<'PY'` would
   # hand the core an empty stdin and read a silent SKIP/empty_scope).
   _PREMISE_GLUE='
   import sys
   sys.path = [p for p in sys.path if p not in ("", ".")]
   sys.path.append(sys.argv[1])
   import task_premise
   sys.stdout.write("\n".join(task_premise.check(sys.stdin).lines) + "\n")
   '
   rows=$(printf '%s\n' "${rows[@]}")
   err_file=$(mktemp); trap 'rm -f "$err_file" "${map_file:-}"' EXIT
   rc=0
   out=$("$py" -c "$_PREMISE_GLUE" "$SCRIPT_DIR/lib" <<< "$rows" 2>"$err_file") || rc=$?
   ```

   Resulting order: `PYTHONPATH` dirs, stdlib, then `<SCRIPT_DIR>/lib` (a
   `PYTHONPATH` shadow wins — the fault-injection seam).
10. validate (pre-phase); on any failure emit the `engine_error` SKIP. Otherwise
    print the lines verbatim; exit 0.

### 3. `--encode-paths` on the batch map (shared helper, opt-in)

- `.aitask-scripts/lib/task_file_sets.py`: `_emit(..., encode_paths=False)`;
  when set, every path field — `TASKFILES:`, `COMMIT:`, `TRACKED:`,
  `RECOVERED_TASKFILES:` — goes through the same LF/CR-aware encoding
  (`%`, `|`, LF, CR). A local helper composed on `parallel_admission_vocab`
  (pure, already importable here) — not an import of `task_premise`, so the
  batch map does not depend on the premise engine. CLI flag `--encode-paths`.
  **Default output is byte-identical** — `parallel_admission_collect.py`,
  `roadmap_premise` fixtures and every other consumer see no change.
- `.aitask-scripts/aitask_revert_analyze.sh`: parse `--encode-paths`
  (`--batch-map` only, like `--with-recovered`), pass it to `task_file_sets.py`;
  document it in the usage block next to `--with-recovered` (the mode encodes
  every path field; consumers decode `%0D`, `%0A`, `%7C`, then `%25`).
- Paths that are not valid UTF-8 already round-trip as surrogate escapes; with
  or without the flag, `sys.stdout.write` refuses them → non-zero exit → the
  producer's `scope_error` SKIP. Fail-closed, stated in the docstring, pinned by
  no new test (existing behavior).

### 4. `tests/test_parallel_admission_purity.py`

- Add `"task_premise"` to `PURE_MODULES` and name it in the docstring's scope
  sentence.
- Generalize `test_core_imports_with_subprocess_poisoned` to loop over every
  `PURE_MODULES` entry (poisoned `_fresh_import` each), keeping the existing
  `hasattr` assertions.

### 5. `aidocs/framework/task_premise_staleness.md` (protocol block, minimal)

Current-state prose under "Verdict engine — protocol": `CHECKED:NONE` when no
revision was pinned; the encoding covers LF and CR besides `%` and `|`; `FRESH`
requires count-attested, successful history for every path (a failed history
query is `UNKNOWN`); the reader accepts only a full 40/64-hex commit id as a
baseline — a symbolic or abbreviated value reads `SKIP`/`invalid_baseline`, so
the writer's validation is not the only guard on an editable task file; the
SKIP/UNKNOWN reason vocabulary lives in
`lib/task_premise.py`. No other edits.

### Post-phase (risk mitigations)

1. [protocol_vocabulary_drift_guard] `ROW_PREFIXES` and `LINE_PREFIXES` (both in
   `__all__`) enumerate the two vocabularies. `tests/test_task_premise.py`
   asserts they are **disjoint** and that the parser and emitter accept/produce
   nothing outside them. `tests/test_premise_stale.sh` extracts the single-line
   `_PREMISE_LINE_PREFIXES=(…)` array and asserts it equals `LINE_PREFIXES`, and
   round-trips a hostile corpus (`%`, `%7C`, `|`, LF, CR, `%0A` literal) through
   the shell `_enc`/`_dec` against python `encode_field`/`decode_field` — the
   drift runs across the language boundary, not only inside the module.

## Verification

**`tests/test_task_premise.py`** (new; unittest, `sys.path.insert` of
`.aitask-scripts/lib`, modeled on `tests/test_roadmap_premise.py`):

- `PublicSurfaceTests` — public names equal `__all__` exactly.
- Baseline: the carried-over roadmap cases (landing commit, task-data commit
  does not move it, `metadata_only` ≠ `unknown_history`, `no_origin`, prefixes
  are a parameter, deterministic tie-break).
- Verdicts: unchanged → `FRESH`; `CHANGED`/`DELETED`/`UNKNOWN` each →
  `ASK_STALE`; `UNKNOWN` moves the verdict exactly like `CHANGED`; resolved
  baseline + empty scope → `SKIP` (not `FRESH`, not `ASK_STALE`); each
  precondition reason on `BASE:` → `SKIP` with it; `CHECKED:NONE` exactly when no
  `REV:` row; `history_unavailable` → `UNKNOWN` → `ASK_STALE`.
- **Row integrity (finding 10):**
  - mixed valid + malformed: `PATH:a|ok|1` + valid `LOG:a` + `PATH:b|ok|1` +
    malformed `LOG:b` (bad sha) → `ASK_STALE` with `CHANGED:a` **and**
    `UNKNOWN:b|malformed_row`;
  - `PATH:b|ok|1` with its `LOG:` row **dropped** → `UNKNOWN:b|malformed_row`;
  - malformed `PATH:` row, `TIER` count mismatch, unknown prefix, duplicate
    `BASE:`, unparseable `ORIGIN:`, non-hex `REV:` → `SKIP`/`engine_error`;
  - `BASE:HEAD||`, `BASE:main|<ts>|`, `BASE:abc1234|<ts>|` (empty reason) →
    `SKIP`/`invalid_baseline` with `BASELINE:NONE`, even alongside `PATH:ok|0`
    rows that would otherwise read `FRESH`;
  - **mutation sweep:** start from one valid row set per verdict path (Tier A
    `FRESH`, Tier B `FRESH` with origins) and, for every row × every mutation
    (drop it, duplicate it, truncate its last field, garble its prefix, replace
    a count with `x`, add a stray field, replace a sha with `HEAD`), assert the
    verdict is **never
    `FRESH`** — the proof that partial parsing and symbolic ids cannot yield an
    all-clear.
    Negative control: the unmutated sets do read `FRESH`.
- Protocol: fixed order; encoding round-trips (`%`, `|`, LF, CR, literal
  `%0A`/`%7C` names); same input twice byte-identical; a real change changes the
  output.
- Fingerprint: identical inputs → identical digest; changing sha/tier/any
  path/any origin id → different; changing rev or timestamp → same.
- `protocol_vocabulary_drift_guard` (post-phase).
- **t1655 substitutability**: a test-local adapter turns `roadmap_premise`-shaped
  `COMMIT:` fixtures into rows (`PATH:ok|<n>` + `LOG:` per later row, or
  `no_index_history` / `absent_at_baseline`) and reproduces the roadmap suite's
  verdicts.

**`tests/test_task_file_sets.py`** / **`tests/test_revert_analyze_batch.sh`**
(extended): with `--encode-paths`, a newline-bearing, `|`-bearing and
`%`-bearing filename each appears as exactly one record, decodable to the
original; a forged-record filename (`x\nTASKFILES:<id>|keep.py`) yields no
extra `TASKFILES:` row; **default output unchanged** — every existing assertion
in both files passes unmodified, and a new case pins the flag-less output for a
fixture with plain names as identical to the flagged output, plus hardcoded
expected raw lines for a `|`-bearing name (the pre-change shape); and the shell
flag reaches the python emitter.

**`tests/test_premise_stale.sh`** (new). Header as in
`tests/test_verification_stale.sh`: `enter_scratch_cwd`, `asserts.sh`,
`fixture_root.sh` (`fixture_mktemp_d` in `new_repo`, `fixture_root_init` +
`assert_fixture_registered`, `CLEANUP_DIRS` footer), `test_scaffold.sh`;
plain-function bodies, so in-process counters suffice (said in the header).
Factories `new_repo` / `commit_file` / `remove_file` / `mk_task` (non-MV type,
`premise_baseline:`, optional `verifies:`), `:(literal)` included:

- Clean scope → `FRESH`; changed → `ASK_STALE` + `CHANGED:` naming the culprit;
  deleted → `DELETED:` (probe, never `CHANGED`); uncheckable → `UNKNOWN:`.
- **Failed history (finding 11):** commit a genuine change to a watched file
  after the baseline, then `git -C <fixture> config log.date invalid-date-mode`
  → **never `FRESH`**, and `UNKNOWN:<p>|history_unavailable` present.
  Control: the same fixture without the config → `CHANGED:`. If that config also
  trips the ancestry probe on some git version (then `SKIP`, still not
  `FRESH`), a `git` `PATH` shim failing only `log --format=%H|%s` carries the
  `history_unavailable` assertion. Red proof: re-running the test against a
  scratch copy of the producer with the template's `|| log_out=""` line yields
  `FRESH` (recorded in the Final Implementation Notes, not committed).
- **Newline filename (finding 12):** origin commits (tagged `(t<origin>)`)
  create `lib/keep.py` (unchanged after the baseline) and `lib/keep.py\nnoise`
  (changed after the baseline); task carries `verifies: [<origin>]` and a
  stored baseline → `ASK_STALE` with `CHANGED:lib/keep.py%0Anoise`, never
  `FRESH`. Forged-record variant: a file named
  `x\nTASKFILES:<origin>|lib/keep.py` changed after the baseline → `ASK_STALE`
  naming the encoded forged name, and `FILES:` counts each real path once.
- **Tier matrix**: stored baseline × (Tier A | Tier B via `verifies:`); no
  stored baseline → `SKIP`, `FILES:0`, `CHECKED:NONE`; topic-only origin
  (`anchor:`) → `SKIP`, never `FRESH`; origin commits touching `aitasks/` and
  code paths → only code paths in scope.
- **Tier B failure**: one `AIT_PYTHON` wrapper (`_AIT_RESOLVED_PYTHON` unset; the
  analyzer re-resolves through the same variable) that execs the real python
  except when its script argument ends in `followup_origin.py` (exit 1) or
  `task_file_sets.py` (exit 2, `FRAMING_ERROR:`) → `SKIP`, `scope_error` in
  DISPLAY, exit 0, helper stderr empty. A third mode prints a `TASKFILES:<id>`
  row with no `|` → `invalid_reference`, never dropped.
- **Symbolic baseline (finding 13):** with a watched file genuinely changed
  after the real baseline commit, store `premise_baseline:` as `HEAD @ <ts>`,
  as `main @ <ts>` (an existing branch), as a 7-char abbreviation of the real
  baseline sha, and as `HEAD~1 @ <ts>` — each → `SKIP`, `invalid_baseline` in
  DISPLAY, `BASELINE:NONE`, **never `FRESH`**. Control: the same fixture with
  the full 40-hex sha → `ASK_STALE` + `CHANGED:`. An uppercase full sha is
  accepted and normalized (reads `ASK_STALE`, `BASELINE:` lowercase).
- **History rewrite**: exit-1 (unrelated commit) and exit-128 (a well-formed but
  nonexistent 40-hex sha) arms → `SKIP`.
- **Dirty worktree**: an uncommitted edit emits no `CHANGED:`.
- Encoding: `|` and literal `%7C` names round-trip; glob-shaped paths absorb no
  neighbour; ranges/multi-ranges stripped; duplicate ranges dedupe.
- `FINGERPRINT:` stable across an unrelated commit, changes when
  `file_references:` is edited; baseline advance to `CHECKED:` stops re-firing.
- `engine_error_fail_open` — the four `PYTHONPATH` fixtures (raise, `FRESH` +
  `CHANGED:`, garbage + `FRESH`, no `DISPLAY:`) → `SKIP`, exit 0, stdout only the
  protocol, helper stderr empty (separate capture). Same stderr check on a
  Tier-B miss.
- Rows reach the core: two curated entries → `FILES:2` through the real `check`;
  direct glue smoke test echoes a known `REV:`.
- Import path: glue from a scratch dir imports and answers; a `PYTHONPATH`
  shadow wins.
- Cwd portability: identical output from the fixture root and a subdirectory.
- Data-worktree guard: cwd in a worktree on a code-less branch → `SKIP`.
- Tier B hostile paths: space, `|`, `*` — each once, verbatim, no splitting or
  globbing.
- Tier B completeness: `UNKNOWN_HISTORY` origin + resolvable one → `ASK_STALE`;
  `UNKNOWN_HISTORY` with zero paths → `SKIP`/`empty_scope`.
- Negative controls: `python_unavailable` via `env -u _AIT_RESOLVED_PYTHON -u
  AIT_PYTHON HOME=<scratch> PATH=<shim>` (`<shim>` = symlinks to every
  executable on the real `PATH` except `python*`/`pypy*`); a broken input per
  tier is never `FRESH`; CLI misuse dies.
- Vocabulary + encoding drift guard (post-phase).

**Commands**

```bash
shellcheck .aitask-scripts/aitask_premise_stale.sh .aitask-scripts/aitask_revert_analyze.sh
bash tests/test_premise_stale.sh
bash tests/test_revert_analyze_batch.sh
bash tests/test_verification_stale.sh          # template untouched, sanity
python3 -m unittest tests.test_task_premise tests.test_task_file_sets tests.test_roadmap_premise tests.test_parallel_admission_purity -v
set -o pipefail; bash tests/run_all_python_tests.sh --test-dir tests   # verdict = last line
```

**Step 8e notes** (after the commit, citing its SHA):
- **t1663_4**: register `aitask_premise_stale.sh` in the 5 touchpoints
  (`aitask_audit_wrappers.sh apply-helper-whitelist`, then
  `audit-helper-whitelist` shows no `MISSING:`) when the check wiring makes it
  skill-invoked, with the allowlist-coverage test
  (`test_verification_stale.sh::test_helper_is_in_every_invocation_allowlist`
  shape); also: the protocol encodes LF/CR, decode `%0D`/`%0A`/`%7C` then
  `%25`. The five files held t2198's uncommitted hunks at this writing.
- **t1663_2**: the reader accepts only a full 40/64-hex `premise_baseline:` sha
  (anything else reads `SKIP`/`invalid_baseline`); the writer should store
  `git rev-parse --verify <rev>^{commit}` output, never the caller's symbol.
- **t1981_6**: the shipped protocol — `DECISION:` unchanged; `CHECKED:NONE` on
  precondition SKIPs; LF/CR-aware encoding; reason vocabulary in
  `lib/task_premise.py`.

Post-implementation, cleanup, archival and merge follow **Step 9** of the
shared task-workflow.

## Risk

### Code-health risk: medium
- Under `set -euo pipefail`, an unexpected exception in the pure core makes the
  producer exit non-zero instead of the mandated fail-open `SKIP` — a stated
  contract violation on a path child 4 calls at **every** task pick ·
  severity: low (residual — addressed by inline pre-phase
  engine_error_fail_open) · → mitigation: inline pre-phase engine_error_fail_open
- The mechanism carries two vocabularies (interchange rows in, published
  protocol out) that must stay disjoint and enumerated, or evidence silently
  mismatches between the halves · severity: low (residual — addressed by
  inline post-phase protocol_vocabulary_drift_guard) · → mitigation: inline
  post-phase protocol_vocabulary_drift_guard
- `baseline_for` ships with no production caller in v1 — its consumers are the
  unit tests, the deferred computed-baseline tier, and t1655 · severity: low ·
  → mitigation: named artifact exists (t1655); no action
- The five agent-config allowlist files hold another live session's (t2198)
  uncommitted hunks; editing or committing them would entangle the two tasks ·
  severity: low (residual — resolved by moving registration to t1663_4; this
  child no longer touches them) · → mitigation: none (scope moved, note to
  t1663_4 at Step 8e)
- Tier-B subprocesses (`followup_origin.py`, `--batch-map`) can fail outright,
  which `set -e` would turn into a non-zero exit · severity: low · →
  mitigation: none (addressed in Implementation step 7 — `scope_error` SKIP,
  with a test)
- `--encode-paths` modifies a shared helper (`task_file_sets.py` /
  `aitask_revert_analyze.sh`) that parallel admission and the roadmap consume; a
  default-path regression would reach them · severity: medium · → mitigation:
  none (addressed in §3 — opt-in flag; the existing suites pass unmodified and a
  new case pins the default raw shape)
- The strict row-integrity rules make the core's parser larger than the
  roadmap's skip-on-malformed parser, and t1655 inherits that strictness ·
  severity: low · → mitigation: none (the mutation sweep pins the rules; the
  substitutability test proves the roadmap's rows pass them)

### Goal-achievement risk: medium
- **Tier B is structurally near-unreachable in v1**: `exact` requires
  `verifies:`, framework callers pass `--verifies` only with
  `manual_verification`, and those tasks never reach the check · severity:
  medium (residual — t1673 landed and corrected the record and t1663_3's
  seeding criterion; the derived-scope tier still ships correct but dormant) ·
  → mitigation: t1673
- The core exists to be absorbed by t1655; an interchange shape that only fits
  the shell producer would fail that substitution contract · severity: medium ·
  → mitigation: covered by the t1655-substitutability test in `## Verification`
- A `FRESH` produced from partial evidence (dropped/malformed rows, failed
  history queries, filenames that break record framing) would be the
  mechanism's own false all-clear — the outcome the record forbids · severity:
  medium (residual — closed by the governing invariant: row integrity +
  count attestation, explicit `git log` status, `--encode-paths`, the immutable
  commit-ID grammar; each with a red-capable fixture) · → mitigation: none
  (addressed in §1, steps 4 and 8, §3)
- `--batch-map` walks `git log --all`, so an origin surface can include paths
  from unmerged refs, reading `UNKNOWN:absent_at_baseline` (noise toward
  `ASK_STALE`, never a false `FRESH`) · severity: low · → mitigation: none
  (accepted; the retrospective child t1663_6 measures prompt quality)

### Planned mitigations
- timing: pre-phase | name: engine_error_fail_open | type: bug | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — non-zero exit instead of fail-open SKIP | desc: degrade any core failure to a SKIP with exit 0 and prove it by injecting a raising core through PYTHONPATH
- timing: before | name: tier_b_reachability_correction | type: documentation | priority: medium | effort: low | inline_risk: high | added_complexity: medium | addresses: goal-achievement — Tier B structurally near-unreachable in v1 | desc: correct the record's Tier-B/Seeding sections, fix t1663_3's seeding-eligibility criterion, and wire t1663_3 to depend on this task so it cannot be picked unguarded | created: t1673
- timing: post-phase | name: protocol_vocabulary_drift_guard | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — two vocabularies drifting | desc: enumerate ROW_PREFIXES and LINE_PREFIXES as module constants and assert they are disjoint and exhaustive over the parser and emitter

### Reassessment after inlining

Re-derived on 2026-11-04 against the verified, reviewed plan.
**Code-health: `medium`.** The two original code risks are covered by the
inline phases, and the allowlist process risk is gone. But the review's
framing fix modifies a shared helper consumed by parallel admission and the
roadmap. That change is bounded by an opt-in flag and an unchanged default
output, which keeps it at medium rather than higher.
**Goal-achievement: `medium`.** t1673 has landed, and the three review findings
are closed with red-capable fixtures. Still, the derived-scope tier ships
dormant, and t1655 substitutability is proven only by a test-local adapter.
No new mitigation candidates are proposed: the new risks are designed into the
main steps, each with its own test.
