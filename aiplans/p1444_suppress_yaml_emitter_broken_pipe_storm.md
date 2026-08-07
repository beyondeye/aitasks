---
Task: t1444_suppress_yaml_emitter_broken_pipe_storm.md
Worktree: (none — current-branch mode)
Branch: main
Base branch: main
Output branch: main
---

# t1444 — Suppress the YAML emitter broken-pipe diagnostic storm

## Context

Every streaming emitter in `.aitask-scripts/lib/yaml_utils.sh` writes
diagnostics to stderr when its downstream consumer stops early. The structured
result the helper exists to produce is correct — only stderr is polluted, and
the real output gets buried.

**Root cause.** These helpers stream into consumers that legitimately stop once
they have their value: `read_yaml_field` `return`s mid-stream (`yaml_utils.sh:83`)
while `join_yaml_flow_lists` is still writing into the process substitution at
line 87; `| head -1` and `| grep -q` consumers do the same for `read_yaml_list`
and `read_yaml_mappings` (a live example: `aitask_fold_mark.sh:536`,
`read_yaml_mappings … | grep -q '^hash='`). Under a **default** SIGPIPE
disposition the producer is killed silently, which is why this never appears in
an interactive shell. Agent harnesses built on Node/Python leave **SIGPIPE as
`SIG_IGN`**, and children inherit that disposition — so the producer is *not*
killed: every remaining write returns `EPIPE`, and bash (or `sed`/`tr`/`grep`)
reports it. A script cannot repair this from the inside: a signal inherited as
`SIG_IGN` cannot be trapped or reset, so `trap - PIPE` does not help.

**Reproduction confirmed on this machine** (fixtures + a `preexec_fn` setting
`SIGPIPE` to `SIG_IGN`, against the *unpatched* lib). All four paths storm —
including the one the task description believed was clean:

| Path | stdout | stderr | writer |
|---|---|---|---|
| `read_yaml_field` (200-key frontmatter) | `high` ✓ | 77 lines | bash `printf`, `yaml_utils.sh:39` |
| `read_yaml_list` block `\| head -1` (200 items) | `item_0` ✓ | 199 lines | `sed: couldn't flush stdout` |
| `read_yaml_mappings \| head -1` (80 records) | `hash=…` ✓ | 237 lines | bash `printf`, lines 174 **and** 213 |
| `read_yaml_list` **inline** `\| head -1` (324 KB) | `entry_00000…` ✓ | **6 lines** | `grep` + 2×`sed` + 2×`tr` + bash `echo` (line 122) |

Exit status was `0` in every case. Intended outcome: stdout, exit status and
parsing behaviour stay **byte-identical**, and stderr goes to zero on all four.

### Three measured facts that shape the design

**(a) The inline path is NOT clean — the earlier verdict was a fixture
artifact.** With a 400-entry (2.3 KB) inline list it emitted no diagnostics; at
324 KB it storms with 6 lines from five different processes — **8 of 8** runs
driving the pipeline in isolation, and **10 of 10** driving the real entry point
`read_yaml_list inline_big.md depends | head -1`. The
`echo | tr | tr | sed | sed | grep` pipeline at line 122 must be fixed too, not
merely locked as clean.

**(b) EPIPE at small volume is a race.** Measured (pipe capacity 64 KiB): a
producer emitting ~1.6 KB into `| head -1` under `SIG_IGN` storms in only
**24 of 25** runs — in 1 run it finished before `head` closed the read end, so
*no* diagnostic was ever emitted. Once total output exceeds the pipe buffer the
producer *blocks* in `write()` and is guaranteed to be sitting there when the
reader exits: **6 of 6** at 70 KB, **8 of 8** at 324 KB. Fixtures must exceed
pipe capacity, and an empty-stderr assertion must be backed by proof that the
trigger fired at all.

**(c) `read_yaml_list`'s capture loop is quadratic in the value's length**, so
fixture size is not free. Its `${value//[^\[]/}` bracket counting on a single
long line costs **2.1 s at 70 KB, 8.3 s at 140 KB, 34.5 s at 324 KB**. This is a
**pre-existing perf defect**, out of scope here — record it in the Final
Implementation Notes — but it caps the inline fixture just above pipe capacity
rather than at a comfortable multiple.

**(d) `[[ -f /dev/fd/1 ]]` cleanly identifies regular-file stdout.** Probed:
pipeline / `$(…)` / `<(…)` / socketpair → false; `> file`, `>> file` → true.
This is what lets the write guard be scoped to closeable stdout instead of
applied blindly. There is currently **no `/dev/fd` usage anywhere in the repo**
— this introduces the first, so the assumption is pinned by a test with a
fail-safe default.

---

## Implementation

### Pre-phase (risk mitigations)

Runs **before** any edit to `yaml_utils.sh`.

1. `[characterize_list_reader_shapes]` *(broadened from
   `characterize_block_list_shapes` — same inline pre-phase disposition; scope
   now covers the inline branch too, because fact (a) puts that branch under
   rewrite as well.)* In `tests/test_yaml_utils.sh`, pin the current
   `read_yaml_list` output as characterization assertions over every supported
   shape:

   - **block items:** `- a`, `-   a` (multi-space), `- ` (empty item), `-a`
     (not a list item → terminates the list), `  - b` (indented), `-  `,
     `- a  ` (trailing whitespace preserved), `-<TAB>c`, `- - nested`.
   - **inline lists:** `[1, 2, 3]`, `[a,b,c]`, `[ a , b ]`, `[]`, `[ ]`,
     `['x', 'y']`, `["p", "q"]`, `[a,,b]`, `[a, b,]`, `[,a]`,
     `[t900_1, t900_2,   t900_3]`, `[foo bar, baz qux]`, `[a[1], b]`,
     `[it's, fine]`, `[  spaced  ,  out  ]`, `[single]`.
   - plus the already-covered wrapped-flow and quoted/comment/`url: null`
     shapes.

   **These must pass against the unpatched lib**; they are the ground truth
   that neither rewrite (steps 4 and 4b) may move. Both rewrites have already
   been verified byte-identical against these exact shapes during planning —
   these assertions make that permanent.

2. `[epipe_trigger_positive_control]` Make the SIGPIPE harness self-proving. An
   empty-stderr assertion alone cannot distinguish "the guard suppressed the
   storm" from "EPIPE never happened", so before the guarded cases run, put a
   **deliberately unguarded reference producer** at the same output volume
   through the identical harness:

   ```bash
   # positive control: proves the harness can actually create EPIPE
   for ((i = 0; i < N; i++)); do printf '%s_%s\n' "$i" "$PAD"; done | head -1
   ```

   If that produces **no** stderr, fail with `harness cannot trigger EPIPE —
   fixture too small or SIGPIPE not ignored` and treat every empty-stderr
   assertion in this file as unproven. This is the guard against a vacuously
   green suite, and it is **platform-independent** — it is what carries the
   proof wherever pipe capacity cannot be measured (see step 1a).

3. `[enforce_pipe_contract]` Make the "stdout is a pipe" premise **enforced
   rather than surveyed**. The in-tree sweep (30+ call sites: all `$(…)`, `<(…)`
   or pipelines, none a regular file) cannot bind installer-synced downstream
   consumers or future callers, and for those a blanket `2>/dev/null` would
   convert a genuine `ENOSPC`/quota failure into **successful silent
   truncation**. So scope the guard by stdout type, decided **once per call**:

   ```bash
   # Decide whether the closed-pipe write guard applies. It applies only when
   # stdout can actually be closed by a reader. If stdout is a REGULAR FILE a
   # failed write means a genuine error (ENOSPC, quota) that MUST stay loud —
   # suppressing it there would turn a real failure into silent truncation.
   # Assigns the caller's dynamically-scoped `_yaml_guard_writes` local (same
   # pattern as _read_yaml_mappings_set's f_*/p_* locals).
   _yaml_init_write_guard() {
       _yaml_guard_writes=1
       if [[ -f /dev/fd/1 ]]; then _yaml_guard_writes=""; fi
       return 0
   }

   # Single write seam for every streaming emitter below.
   # Returns 1 only when the write failed AND the guard is active — i.e. the
   # reader is gone and the caller should stop emitting.
   _yaml_emit() {
       if [[ -n "${_yaml_guard_writes:-}" ]]; then
           printf '%s\n' "$1" 2>/dev/null || return 1
           return 0
       fi
       # Unguarded (regular-file stdout): let the diagnostic through and keep
       # today's continue-on-error behaviour, so a real failure is never
       # converted into silent truncation.
       printf '%s\n' "$1" || true
       return 0
   }
   ```

   Each public reader opens with `local _yaml_guard_writes=""` +
   `_yaml_init_write_guard`. `join_yaml_flow_lists` runs inside a process
   substitution and re-decides in its own subshell — correct, since each
   function must judge *its own* stdout.

   **Fail-safe direction:** if `/dev/fd/1` is unavailable on some platform the
   test is false → guard **active** → the storm fix still works; only the
   regular-file `ENOSPC` nicety is lost. Pin both directions with an explicit
   test (pipe → guard active; `> file` → guard inactive) so the platform
   assumption fails loudly rather than degrading silently.

   Record the contract in the `yaml_utils.sh` header: the inherited-`SIG_IGN`
   condition stated **once**, the sweep result, and the fact that the boundary
   is now enforced by stdout type rather than by convention. Per-site comments
   point back here instead of repeating it.

### 1. Reproduction harness in `tests/test_yaml_utils.sh`

Extend the existing file (it already sources both libs and `tests/lib/asserts.sh`
and keeps `PASS`/`FAIL`/`TOTAL` counters) — do not add a new file.

**1a. SIGPIPE runner and its portability envelope.** Write a
`$TMP/sigpipe_run.py` helper and a `run_ignoring_sigpipe <snippet-file>` bash
wrapper:

```python
import signal, subprocess, sys
sys.exit(subprocess.call(["bash", sys.argv[1]],
    preexec_fn=lambda: signal.signal(signal.SIGPIPE, signal.SIG_IGN)))
```

Test infrastructure must never fail the suite for environment reasons:

- **`python3` absent** → print `SKIP: python3 absent — SIGPIPE cases not run`
  and skip **only** the SIGPIPE cases. The characterization assertions,
  `set -e` smoke and non-truncation guard all still run.
- **`fcntl.F_GETPIPE_SZ` is Linux-only.** Measure pipe capacity inside a
  `try/except (AttributeError, OSError)`; on failure fall back to a fixed
  128 KB sizing target and **skip the size assertion**, leaving the
  platform-independent positive control (pre-phase 2) to carry the proof.
  Never fail for a missing `F_GETPIPE_SZ`.
- **Fixture generation runs in `python3`**, not shell loops, so the hot paths
  are not shell at all. (`seq` needs no fallback — it is already used in 13
  test files here and ships on macOS; the bash producers use bash-3.2-safe
  `for ((…))` regardless.)
- **bash 3.2 construct audit.** Everything added is already used in this file:
  `${var//pat/}`, the nested trim idiom `${x#"${x%%[![:space:]]*}"}`
  (lines 118, 156-163), and **unquoted** `=~` with `BASH_REMATCH`
  (lines 134, 186, 296). No `mapfile`, associative arrays, `local -n`, or
  `${var^^}`.

**1b. Fixtures sized past the pipe buffer — per case, because cost differs.**
Target `2 × measured capacity` (default 128 KB when unmeasurable), **except the
inline case**, which is quadratic per fact (c) and so uses capacity + ~10%:

| Fixture | Shape | Emitted | Cost |
|---|---|---|---|
| `big.md` | frontmatter, `priority` first, then padded keys | ~128 KB | linear |
| `list.md` | block list, padded items | ~128 KB | linear |
| `attach.md` | attachment records, padded `name` | ~128 KB | linear |
| `inline.md` | one inline flow list | ~72 KB (capacity + 10%) | ~2.1 s (quadratic) |

70 KB was measured **6/6** reliable, so capacity + 10% is above the race
threshold; 140 KB would cost 8.3 s and 324 KB 34.5 s for no added confidence.

**1c. Four SIGPIPE cases**, each asserting **stdout value**, **empty stderr**,
and **exit 0** — the inline case now on the same footing as the others:

1. `read_yaml_field big.md priority` (covers `join_yaml_flow_lists`).
2. `read_yaml_list list.md labels | head -1` (block branch).
3. `read_yaml_mappings attach.md attachments | head -1`.
4. `read_yaml_list inline.md depends | head -1` (inline branch).

**1d. Negative control — run 1c against the unpatched lib first.** Before any
edit to `yaml_utils.sh`, run `bash tests/test_yaml_utils.sh` and confirm **all
four** cases fail on the empty-stderr assertion with **non-empty stderr**.
Assert non-emptiness, **not** a fixed storm count — counts vary with scheduling,
buffering and fixture size, and case 4's count (6) is nothing like case 2's
(199). Record the observed counts in the Final Implementation Notes as an
observation only.

### 2. `join_yaml_flow_lists` — route both writes through the seam (`38-45`)

```bash
        if [[ $depth -le 0 ]]; then
            _yaml_emit "$buffer" || return 0    # reader gone — stop cleanly
            buffer=""
            depth=0
        fi
    done
    if [[ -n "$buffer" ]]; then
        _yaml_emit "$buffer" || return 0
    fi
    return 0
```

### 3. `read_yaml_field` — route the two single writes (`82, 89`)

```bash
            _yaml_emit "$value" || true
            return 0        # was a bare `return`, which propagated echo's status
```

and at the not-found tail:

```bash
    _yaml_emit "" || true
    return 0
```

### 4. `read_yaml_list` block emitter — drop the `sed` fork (`133-139`)

`sed`'s own `couldn't flush stdout` error cannot be suppressed from inside the
loop, so remove the fork and use the regex capture the loop already computes:

```bash
        if $in_list; then
            if [[ "$fline" =~ ^[[:space:]]*-[[:space:]]+(.*)$ ]]; then
                # Byte-identical to the former
                # `sed 's/^[[:space:]]*-[[:space:]]*//'` (POSIX ERE
                # leftmost-longest makes `[[:space:]]+` greedy).
                _yaml_emit "${BASH_REMATCH[1]}" || break
            else
                break
            fi
        fi
```

The guard regex widens from `^[[:space:]]*-[[:space:]]` to
`^[[:space:]]*-[[:space:]]+(.*)$`; both accept exactly the same line set,
verified byte-identical over the nine block shapes in pre-phase 1. Bonus:
removes a fork per list item.

### 4b. `read_yaml_list` **inline** emitter — replace the 5-process pipeline (`121-124`)

Per fact (a) this branch storms too, and its five processes each report
independently, so there is no single site to guard — replace the pipeline with
the pure-bash equivalent routed through `_yaml_emit`:

```bash
    if [[ "$value" =~ ^\[.*\]$ ]]; then
        # Pure-bash equivalent of the former
        #   echo | tr -d "[]'\"" | tr ',' '\n' | sed 's/^[[:space:]]*//' \
        #        | sed 's/[[:space:]]*$//' | grep -v '^$'
        # Each of those five processes reported its own EPIPE independently, so
        # the closed-pipe stop is only expressible without the forks.
        local _clean="${value//[\[\]\'\"]/}" _item
        while [[ -n "$_clean" ]]; do
            _item="${_clean%%,*}"
            if [[ "$_item" == "$_clean" ]]; then _clean=""; else _clean="${_clean#*,}"; fi
            _item="${_item#"${_item%%[![:space:]]*}"}"   # trim leading ws
            _item="${_item%"${_item##*[![:space:]]}"}"   # trim trailing ws
            [[ -n "$_item" ]] || continue                # was grep -v '^$'
            _yaml_emit "$_item" || return 0
        done
        return 0
    fi
```

**Verified byte-identical** to the pipeline across all 16 inline shapes listed
in pre-phase 1 (18 inputs total, 0 differences), and verified to emit **0 stderr
in 8/8** runs at the volume where the pipeline emits 6. Bonus: removes five
forks from the most common list-read path (`depends:`, `labels:`, `gates:`).

### 5. `read_yaml_mappings` — stop at the *first* failed write

`_read_yaml_mappings_emit_field` is contractually `set -e`-safe (always returns
0) and must stay that way, so signal back through a `_yaml_pipe_closed=""` local
on `read_yaml_mappings` (same dynamic-scope pattern as the `f_*`/`p_*` locals).
**The flag must short-circuit the helper itself** — a record makes 9 sequential
`_read_yaml_mappings_emit_field` calls, so merely recording the flag would leave
up to 8 further failed writes per record: diagnostics hidden, but not stopped:

```bash
_read_yaml_mappings_emit_field() {
    # Stop at the FIRST failed write: once the reader is gone, no further field
    # of this record — or any later record — is emitted.
    [[ -z "$_yaml_pipe_closed" ]] || return 0
    [[ "$1" == 1 ]] || return 0
    _yaml_emit "$2=$3" || _yaml_pipe_closed=1
    return 0
}

_read_yaml_mappings_flush() {
    [[ "$have_item" == true ]] || return 0
    if [[ -n "$_yaml_pipe_closed" ]]; then have_item=false; return 0; fi
    if [[ "$first_record" == true ]]; then
        first_record=false
    elif ! _yaml_emit ""; then
        _yaml_pipe_closed=1; have_item=false; return 0
    fi
    …existing nine emit_field calls, now self-short-circuiting…
    have_item=false
    return 0
}
```

In the read loop, break out after the per-item flush:

```bash
            _read_yaml_mappings_flush
            if [[ -n "$_yaml_pipe_closed" ]]; then break; fi
```

The final flush (line 315) needs no extra guard — it early-returns on the flag.

**`set -e` discipline:** every new guard uses explicit `if …; then …; fi` or an
`||` guard-return (always exits 0), never `[[ cond ]] && cmd`. An AND-list whose
left operand fails returns non-zero and, as the last command of a function or
loop body, trips `set -e` in the ~40 scripts that source this lib via
`task_utils.sh` / `agentcrew_utils.sh`.

### Post-phase (risk mitigations)

Runs **after** steps 1–5, before final verification.

1. `[set_e_source_smoke]` Add a smoke case that sources `yaml_utils.sh` in a
   subshell under `set -euo pipefail` and exercises all four readers on **both**
   the hit and the miss path (`read_yaml_field` found / not-found,
   `read_yaml_list` inline / block / absent field, `read_yaml_mappings`
   present / absent / empty-inline). Assert exit 0. A new guard idiom that trips
   `set -e` then fails this suite instead of aborting a random production script.

2. `[non_truncation_guard]` Assert that the **unpiped** output of the block-list,
   inline-list and mappings fixtures still yields the full item counts, proving
   the guards stop only on a genuinely closed pipe and never truncate a complete
   read. Additionally assert the enforced boundary from pre-phase 3: with stdout
   redirected **to a regular file**, output is complete and the guard is
   inactive.

---

## Verification

1. `bash tests/test_yaml_utils.sh` — all cases pass, including the four SIGPIPE
   cases that failed in step 1d and the positive control from pre-phase 2.
2. Suites that exercise the touched readers:
   `bash tests/test_update_multiline_yaml.sh` (join_yaml_flow_lists),
   `bash tests/test_attach_scaffold.sh` and `bash tests/test_attach_meta.sh`
   (read_yaml_mappings + `_yaml_scalar_value` shapes: quoted scalars, trailing
   `<ws>#` comment, `bug#3.png`, `url: null`),
   `bash tests/test_artifact_cli.sh`, `bash tests/test_artifact_fold_transfer.sh`.
   The inline rewrite (4b) touches the path every `depends:` / `labels:` /
   `gates:` read uses, so also run `bash tests/test_yaml_utils.sh` alongside a
   broad smoke (item 4).
3. `shellcheck .aitask-scripts/lib/yaml_utils.sh` and
   `bash -n .aitask-scripts/lib/yaml_utils.sh`.
4. End-to-end smoke through the real CLI: `./ait ls -v 5`,
   `./.aitask-scripts/aitask_gate.sh status 1444`,
   `./.aitask-scripts/aitask_query_files.sh inflight` — output unchanged, no
   stderr noise.
5. Step 9 runs the declared `risk_evaluated` gate via `./ait gates run 1444`.

**Record in Final Implementation Notes → Upstream defects identified:**
`.aitask-scripts/lib/yaml_utils.sh:110-113 — read_yaml_list's flow-list bracket
counting (${value//[^\[]/}) is quadratic in the value's length: 2.1 s at 70 KB,
8.3 s at 140 KB, 34.5 s at 324 KB. Harmless for real task frontmatter but a
latent cliff; out of scope here.`

## Post-Implementation

Step 9 of the shared task-workflow handles merge (current-branch mode — no
worktree to clean up), the gate run, and archival.

---

## Risk

*Reassessed after the five inline mitigations were folded in and the inline
branch entered scope. Detection is now strong (shape pins across both branches
+ positive control + `set -e` smoke + non-truncation guard) and the `ENOSPC`
hazard is structurally bounded rather than merely documented. Code-health stays
**medium**: `yaml_utils.sh` is load-bearing for nearly every framework script
and there are now **two** parsing rewrites, so the blast radius is if anything
wider than at first assessment, even though the odds of a silent regression are
much reduced.*

### Code-health risk: medium

- Two rewrites now replace forked text processing with bash string handling — the block emitter's `sed` (step 4) and the inline emitter's five-process pipeline (step 4b). Either could shift parsing on an unenumerated shape, and `yaml_utils.sh` reaches essentially every framework script via `task_utils.sh` / `agentcrew_utils.sh`, making a regression broad and quiet · severity: medium · → mitigation: inline pre-phase characterize_list_reader_shapes
- Suppressing write errors could convert a genuine failure (`ENOSPC`, quota) into successful silent truncation for a file-redirecting caller — and `.aitask-scripts/` is installer-synced into downstream projects, so an in-tree call-site survey cannot bind every consumer · severity: medium · → mitigation: inline pre-phase enforce_pipe_contract
- The new closed-pipe guards add branching to functions sourced into ~40 `set -euo pipefail` scripts; a `[[ cond ]] && cmd` idiom in the wrong position would abort those scripts mid-run · severity: medium · → mitigation: inline post-phase set_e_source_smoke

### Goal-achievement risk: low

- The regression tests could pass vacuously: an empty-stderr assertion cannot distinguish a working guard from an EPIPE that never occurred, and at small fixture sizes the trigger measurably misfires (1 run in 25) — the very error that made the inline branch look clean in the task description · severity: medium · → mitigation: inline pre-phase epipe_trigger_positive_control
- The guards stop emission on the *first* failed write; if a write could fail transiently for a reason other than a closed pipe, a full (unpiped) read would be silently truncated instead of storming · severity: low · → mitigation: inline post-phase non_truncation_guard

### Planned mitigations

- timing: pre-phase | name: characterize_list_reader_shapes | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — parsing regression from the block and inline emitter rewrites | desc: Pin the current read_yaml_list output across all supported block AND inline shapes as assertions that pass against the unpatched lib.
- timing: pre-phase | name: epipe_trigger_positive_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — regression tests passing vacuously | desc: Run a deliberately unguarded reference producer through the same SIGPIPE harness and fail loudly if it does not storm, proving the EPIPE trigger is live; also carries the proof where pipe capacity cannot be measured.
- timing: pre-phase | name: enforce_pipe_contract | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — write suppression masking a genuine ENOSPC as silent truncation | desc: Scope the write guard to non-regular-file stdout via a single _yaml_emit seam decided once per call, pin both directions with a test, and record the contract in the lib header.
- timing: post-phase | name: set_e_source_smoke | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — new guard idioms tripping set -e in sourcing scripts | desc: Source the lib under set -euo pipefail and exercise all four readers on hit and miss paths, asserting exit 0.
- timing: post-phase | name: non_truncation_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — guards truncating a complete read | desc: Assert the unpiped block, inline and mappings reads still yield full item counts, and that a regular-file redirect leaves the guard inactive and output complete.
