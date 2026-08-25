---
Task: t1609_yaml_block_list_items_keep_quotes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1609 — Block-list items keep their surrounding quotes

## Context

`read_yaml_list` (`.aitask-scripts/lib/yaml_utils.sh`) resolves a YAML list
field through two branches that disagree about quoting:

| form | code | `"make -j4"` resolves to |
|---|---|---|
| inline `[a, b]` | `yaml_utils.sh:277` — `${value//[\[\]\'\"]/}` deletes **every** `[`, `]`, `'`, `"` in the whole value | `make -j4` |
| block `- a` | `yaml_utils.sh:304` — emits `${BASH_REMATCH[1]}` **verbatim** | `"make -j4"` (quotes kept) |

The two forms are documented as interchangeable — `seed/project_config.yaml:116`
says "Accepts a single command string or a YAML list of commands", and
`:99-107` / `:137-139` show the block form with quoted multi-word commands. But
only the inline one works: a project copying the seed's own `- "cmake -B build"`
example gets `bash -c '"cmake -B build"'` → exit 127, recorded by
`run_command_gate` (`.aitask-scripts/lib/gate_verifier_lib.sh:120`, `:154`) as a
gate **FAIL**.

**It is reachable without anyone hand-writing YAML.** The settings TUI saves
`verify_build` via `config_utils.save_yaml_config` → `yaml.safe_dump(
default_flow_style=False)` (`.aitask-scripts/lib/config_utils.py:326-345`) —
block form — and PyYAML single-quotes any scalar starting `[`, `*`, `#` or
containing `: `. So `[ -f Makefile ] && make` round-trips through the TUI as
`- '[ -f Makefile ] && make'` and then fails at exec.

**Why the suite missed it** (both need saying, because both are still in the
tree): `tests/test_gate_verifiers.sh:155-162` tests block form with `- "true"`
— a *single-word* item, which bash's own quote removal rescues, so that test is
structurally incapable of failing. And Test 2's multi-word `- "touch
SHOULD_NOT_RUN"` (`:175`) is *asserted absent* — it sits after a
short-circuiting failure and never runs.

Two live workarounds paper over the defect: `gate_verifier_lib.sh:127-129`
re-strips quotes off every `gate_command_exit_contract` entry, and
`tests/test_gate_verifiers.sh:352-357` tells future authors to write fixtures
unquoted.

t1605 declined to patch this inside `_gate_config_values`, because that would
have moved command resolution its pre-phase mitigation had just pinned as
unchanged. The fix belongs in the shared reader.

**Outcome:** both list forms resolve to the same values; the seed's own
documented form works; and the quoting rule has exactly one definition, so the
branches cannot drift again.

## Approach

### Pre-phase (risk mitigations)

**`baseline_capture`** — runs *before* any edit to `yaml_utils.sh`, so every
later difference is a deliberate diff rather than a guess:

1. Record verbatim, to a scratch file, the current output of the three t1444
   pins about to be repointed — `read_yaml_list` over the `block_shapes`,
   `[a[1], b]` and `[it's, fine]` fixtures (`tests/test_yaml_utils.sh:236-283`).
2. Record, for every task file carrying one, its `active_gates_digest` and the
   verdict of `_digest_halves_ok` (`aitask_gate.sh:817-834`) — the baseline the
   post-phase compares against.

### 1. `.aitask-scripts/lib/yaml_utils.sh` — one shared per-item normalizer

Add beside `_read_yaml_list_impl`:

```bash
# _yaml_norm_list_item <raw-item>  ->  sets _yaml_item
# The single definition of "what one list item resolves to", shared by the
# inline and block branches so the two forms cannot disagree again (t1609).
# Trims surrounding whitespace, THEN strips ONE surrounding matching quote
# pair. That order is load-bearing: a CRLF-authored `- "cmd"\r` only unquotes
# because the \r is trimmed first. Inner and unpaired quotes survive —
# `echo "hi"`, `it's` and `a[1]` come back byte-identical.
#
# ONE pair only, never a loop: `""""` -> `""`. A loop here would reproduce the
# over-eager stripping this function exists to remove.
#
# The `-ge 2` guard is redundant TODAY and deliberate anyway: each glob needs
# two literal quote chars, so a lone `"` cannot match and is returned intact.
# But a lone quote IS reachable (`[",", x]` peels to the items `"`, `"`, `x`),
# and the obvious refactor of this `case` into
# `[[ "$v" == \"* && "$v" == *\" ]]` DOES match one — then `${v:1:${#v}-2}`
# aborts the reader with `substring expression < 0`. The guard makes the
# safety explicit instead of leaving it implicit in glob semantics.
# Does not handle YAML escaping inside quotes: `"say \"hi\""` -> `say \"hi\"`,
# `'it''s'` -> `it''s` (same out-of-scope limit _yaml_scalar_value documents).
# NBSP is not whitespace to [[:space:]]; only ASCII blanks/CR/LF/TAB trim.
#
# Returns through a variable, not stdout: a `$(...)` call site would fork once
# per item, re-introducing exactly the per-item forks t1444 removed from this
# path (closed-pipe write contract, top of this file).
_yaml_norm_list_item() {
    local v="$1"
    v="${v#"${v%%[![:space:]]*}"}"
    v="${v%"${v##*[![:space:]]}"}"
    case "$v" in
        '"'*'"') [[ ${#v} -ge 2 ]] && v="${v:1:${#v}-2}" ;;
        "'"*"'") [[ ${#v} -ge 2 ]] && v="${v:1:${#v}-2}" ;;
    esac
    _yaml_item="$v"
}
```

`_yaml_norm_list_item` must end with the assignment (not the `case`), so it
always returns 0 and the `|| break` on the following `_yaml_emit` stays safe.

Declare `_yaml_item` on the **function-scope** `local` line at `:248` — not
inside the `if` — otherwise the block branch assigns a global that outlives the
call.

**Trailing-whitespace trim at `:266`** — currently only *leading* whitespace is
stripped, so `gates: [a, b]···` fails the `^\[.*\]$` guard at `:269`, falls
through to the block branch, and returns **zero items**. Verified live. Add the
trailing trim.

**Inline branch** (`:277`): peel the wrapping brackets *only*.

```bash
local _clean="${value#\[}"; _clean="${_clean%\]}"
```

Deliberately not `${value:1:${#value}-2}`: the arithmetic form is silently
coupled to the guard's exact anchoring, and would eat a space instead of the
`]` if the guard is ever relaxed. Then split on `,`, `_yaml_norm_list_item`
each, skip empties (unchanged), emit.

**Block branch** (`:304`):

```bash
_yaml_norm_list_item "${BASH_REMATCH[1]}"   # arg expands now; BASH_REMATCH is
_yaml_emit "$_yaml_item" || break           # never re-read after the call
```

Empties are still emitted (unchanged). `_yaml_emit`, the write guard and the
`trap '' PIPE` wrapper are untouched; the path stays fork-free.

### 2. `.aitask-scripts/lib/gate_verifier_lib.sh` — an unparseable command is a **fail**, never a skip

A resolved command that cannot even be parsed must not be able to satisfy a
gate. Today `bash -c 'echo "a'` exits **2**, and under an opted-in
`gate_command_exit_contract` that is recorded as *skip* — which can release a
`blocks_dependents` edge for a command that never ran. Pinning that outcome
would only document it; this removes it.

In `run_command_gate`'s loop (`:151-168`), pre-validate each command before
running it:

```bash
if ! bash -n -c "$c" 2>>"$log"; then
    status=fail; code=1
    result="malformed ${config_key} command (cannot parse): ${c}"
    break
fi
```

Verified to discriminate correctly, with no false positives:

| command | `bash -n` | today's `bash -c` exit |
|---|---|---|
| `echo "a` | MALFORMED | 2 → *skip* under opt-in ✗ |
| `echo 'unterminated` | MALFORMED | 2 ✗ |
| `for x in` | MALFORMED | 2 ✗ |
| `pytest -k` | parses | 127 → genuine **fail** ✓ |
| `[ -f Makefile ] && make` | parses | 1 → genuine **fail** ✓ |
| `touch RAN_QUOTED`, `echo ok`, `exit 2`, `true`, `false` | parses | unchanged ✓ |

This is a **deliberate widening**, stated rather than smuggled: it also closes
the *pre-existing* hole where `verify_build: "for x in"` was recorded as a skip
long before this task. `GATE_COMMAND_SKIP_EXIT` keeps its meaning — "the command
ran and reported it did not do the work" — instead of also absorbing "the
command could not be parsed". Cost: one `bash -n` fork per command, negligible
beside running the command itself.

The **empty / literal-`null`** case is different and is **explicitly approved**
rather than fixed: after the reader unquotes, a sole `- "null"` or `- ""` is
dropped by `_gate_config_values:56`, the list resolves empty, and the gate skips
with "no verify_build configured". That is exactly what the scalar forms
`verify_build: null` / `verify_build:` already do, so the list form is becoming
*consistent* with the scalar form, not weaker. Pinned as such.

### 3. `.aitask-scripts/lib/gate_verifier_lib.sh` — retire the workaround

Delete the now-dead single-pair strip and stale comment at `:127-129`. Existing
test (j) at `tests/test_gate_verifiers.sh:413-422` already drives block-form
`gate_command_exit_contract` with quotes, so the removal stays protected.

The **scalar** strip at `:49-51` **stays** — `read_yaml_field`
(`yaml_utils.sh:207-215`) only trims whitespace, it never unquotes. A cleanup
pass must not delete both; say so in the comment.

### 4. Documentation

The fix makes the two list forms interchangeable **except for one thing**, and
that exception must ship with the relaxation — otherwise the docs trade a
false constraint for a false promise, and `test_command: ["pytest -k 'a,b'"]`
becomes a confusing gate failure instead of a documented one. Worded
identically at every site, and **scoped to inline-list items only**:

> An **inline-list item** containing a comma must use the block (`- …`) form
> instead: the inline `[a, b]` form splits on every comma, including one inside
> quotes. A single scalar command is unaffected —
> `test_command: "pytest -k 'a,b'"` is read whole.

The scalar carve-out is not a hedge, it is verified: a scalar value never
reaches the list reader at all (`read_yaml_list` returns zero items, so
`_gate_config_values:46-53` falls through to `read_yaml_field` + its own
quote strip, yielding `pytest -k 'a,b'`). Omitting that half would rule out a
form that works today and will keep working.

Sites:
- `website/content/docs/tuis/settings/how-to.md:71` — drop the "YAML in **flow
  style**" constraint (both forms now work) and add the caveat sentence. This
  line matters most: flow style is what it currently *tells* people to type, so
  it is the likeliest place to hit the comma case.
- `seed/project_config.yaml` — add the caveat beside each "Accepts a single
  command string or a YAML list of commands" statement (`:116`, `:148`, and the
  `verify_build` header at `:73-77`). Its block-with-quotes examples
  (`:99-107`, `:137-139`) need no change — they become correct rather than
  misleading.
- `website/content/docs/skills/aitask-pick/build-verification.md:17-21`,
  `:62-65` — add the caveat where list form is introduced.

Also note in the same breath that an unparseable command is now a **fail**, not
a skip (§2), wherever the exit-contract semantics are documented —
`seed/project_config.yaml:177-182` and
`aidocs/gates/aitask-gate-framework.md:353-358`.

## Behaviour changes (all deliberate, all pinned)

| input | before | after |
|---|---|---|
| block `- "cmake -B build"` | `"cmake -B build"` → 127 | `cmake -B build` ✓ |
| block `- '[ -f Makefile ] && make'` | quoted → 127 | unquoted ✓ |
| block `- d··` | `d··` | `d` |
| block `- "cmd"\r` (CRLF file) | `"cmd"\r` → 127 | `cmd` |
| block `- "null"` / `- ""` | survives → 127 → gate **fail** | dropped by `_gate_config_values:56` → gate **skip** if sole entry (approved: matches the scalar form) |
| any unparseable command (`echo "a`, `for x in`) | exit 2 → **skip** under opt-in | **fail** — "malformed command" (§2; also fixes the pre-existing case) |
| inline `[a, b]···` | **0 items** | `a`, `b` |
| inline `[a[1], b]` | `a1`, `b` | `a[1]`, `b` |
| inline `[it's, fine]` | `its`, `fine` | `it's`, `fine` |
| inline `[","·, x]` | `x` | `"`, `"`, `x` — see residuals |
| block `- echo "hi"`, `["p","q"]`, `[]`, `[ ]`, `[a,,b]`, `[,a]`, `[a, b,]`, `[  spaced  ]`, `- - nested` | — | all unchanged |

## Blast radius (swept, not assumed)

| call site | field | value kind | affected? |
|---|---|---|---|
| `aitask_archive.sh:478` | `children_to_implement` | task ids | no |
| `aitask_gate.sh:582` | `gates` | gate names | no |
| `aitask_risk_mitigation_landed.sh:59` | `risk_mitigation_tasks` | numeric ids | no |
| `lib/agentcrew_utils.sh:234` | `depends_on` | agent names | no |
| `aitask_gate.sh:813` `_yaml_list_csv` → `:827/:831/:843/:845/:1078/:1079/:1148/:1149` | `gates`, `active_gates`, `active_gates_filtered` | gate names, feed a **cross-language digest** | no |
| `gate_verifier_lib.sh:44` → `run_command_gate:120` | `verify_build`, `test_command`, `lint_command` | **shell commands** | **yes — the defect** |
| `gate_verifier_lib.sh:44` → `run_command_gate:135` | `gate_command_exit_contract` | config-key names | no |

**On-disk corpus:** 767 occurrences of these fields across `aitasks/**` (active
+ archived), `.aitask-crews/**`, `aitasks/metadata/`, `seed/`. Filtering for a
quote, an inner bracket, or trailing whitespace yields **zero** hits, and an awk
scan finds **no** block-form `gates:` / `active_gates:` at all. The single
quoted value anywhere (`aitasks/t410_…:8` `folded_tasks: ['263']`) resolves to
`263` under both rules. So no stored `active_gates_digest` churns — worth
stating as measured evidence, because `_digest_halves_ok` failing is **silent**
(it falls back to raw `gates:` at `aitask_gate.sh:838-844`).

**Cross-language parity improves.** Verified live against the Python twin
`gate_ledger.py:524-541`:

| input | bash today | bash after | Python |
|---|---|---|---|
| block `- "a b"`, `- c··` | `"a b"`, `c··` | `a b`, `c` | `a b`, `c` ✓ |
| inline `[a, b]···` | *(nothing)* | `a`, `b` | `a`, `b` ✓ |

The fix moves bash **toward** Python on every realistic case, and away only on
`echo "hi"` (bash keeps it, Python's `.strip("'\"")` mangles it to `echo "hi`).
**Do not "fix" Python to match** — bash is the YAML-correct side, and the
divergence is unreachable for the identifier-only fields the digest reads.
Recorded so a reviewer reading "must match byte-for-byte" doesn't argue the
opposite.

## Declined / out of scope (in writing, so review doesn't re-raise them)

- **Quote-aware comma splitting** in the inline branch. It would need a
  per-character bash loop on the framework's hottest reader — the exact forks
  t1444 removed. Instead: **declare** that the inline flow form splits on every
  comma and an item containing one must use the block form.
- `lib/task_utils.sh:518-521` `parse_yaml_list` and `lib/agentcrew_utils.sh:186`
  keep their `tr -d "[]'\""` idiom — they also delete every space, so they can
  never carry a command.
- The capture loop at `:250-262` counts brackets without quote awareness, so
  `verify_build: ["ls ["]` swallows subsequent lines. Pre-existing; untouched.
- `gate_ledger.py`'s `.strip("'\"")` (see above).

## Accepted residuals (each pinned as a test, not silently left)

- `["a,b"]` splits on the inner comma, so the fragments carry unbalanced quotes
  and the command does not run. It now records a **fail** ("malformed command")
  via §2 — not a skip, and not a misleading 127. The *splitting* stays a
  residual; the dangerous verdict does not. Neither the block form nor the
  scalar form has this limit (neither splits on commas), which is why §4
  documents them as the answer for a comma-containing command rather than
  leaving the residual unstated — and why the caveat is scoped to *inline-list
  items*, not to commands in general.
- Lone-quote items (`"`, `'`) survive the normalizer intact — reachable via
  `[",", x]`, and pinned, because the length guard's correctness is otherwise
  invisible.
- `- "a" "b"` → `a" "b`; `- "say \"hi\""` → `say \"hi\"`; `- 'it''s'` → `it''s`;
  `""""` → `""` (one layer only).
- Inline drops empty items, block emits them. Real YAML yields `null` for both;
  that is null-handling, not quoting.
- No inline `#` comment stripping in either branch — deliberate, it is what
  keeps the two forms in parity.

## Tests

The parity assertion alone is **vacuous**: `inline == block` is satisfied by the
wrong fix (make the block branch globally delete quotes too and every row goes
green while `a[1]` → `a1`). So every table row is a **triple** — `inline ==
EXPECTED` *and* `block == EXPECTED` — and parity is the corollary.

**`tests/test_yaml_utils.sh`**
- **Direct unit rows** for `_yaml_norm_list_item` and for the bracket peel,
  *before* the file-level rows — a file-level row conflates the capture loop,
  the guard and the normalizer, and when it goes red you need to know which.
- **Table-driven triple test**, each row rendered as both `il: [<item>]` and
  `blk:` / `  - <item>`: bare identifier, multi-word unquoted, `"multi word"`,
  `'multi word'`, the literal `"cmake -B build"` from the seed, `echo "hi"`,
  `it's`, `a[1]`, leading/trailing whitespace, CRLF, `""""`, and the lone-quote
  items `"` / `'` / `""` / `''` (reachable via `[",", x]`; they pin the length
  guard, whose correctness is otherwise invisible). A comment states these pin
  *this parser*, not PyYAML conformance.
- **Guard row:** `il: [a, b]···` must yield 2 items (0 today).
- **Rejection probe** against over-eager stripping — `- echo "hi"` and `- a[1]`
  byte-identical. Label it as such in the assertion string: it *passes* today,
  so it is a guard against the wrong fix, **not** the failing-before reproducer.
- **Repoint** the 3 flipped t1444 pins at `:249-252`, `:275`, `:276`, renaming
  the descriptions (`"inner brackets stripped"` → `"inner brackets preserved
  (paired-quote strip only)"`, `"apostrophe in item"` → `"apostrophe
  preserved"`), tagged `# t1609`, and update the block comment at `:264-267`.
  Add an **item-count** assertion beside `:250` so silently dropping the two
  empty items cannot hide inside a reflowed string compare.
- **Residual pins** for every case listed above, including the comma one.
- **Cross-language pin:** a quoted identifier list resolves identically through
  `read_yaml_list` and `gate_ledger._read_frontmatter_list_from_text`.

**`tests/test_gate_verifiers.sh`**
- **Fix the vacuous test in place** at `:155-162`: add a multi-word quoted item
  to the block-list fixture. Leaving it beside a working test invites the next
  author to trust the wrong one.
- **New end-to-end test**, hardened so it can only fail for the right reason:
  block `verify_build:` with `- "touch RAN_QUOTED"` **and** an unquoted
  `- touch RAN_BARE` positive control (a cwd/TASK_DIR slip otherwise yields
  "no verify_build configured" → exit 2 and the new assertion fails for an
  unrelated reason). Assert exit 0, ledger `status=pass`, both files present at
  `$d/…` (Test 2's pattern at `:181`), and the sidecar's `$ touch RAN_QUOTED`
  line (`gate_verifier_lib.sh:150`) — that pins the *normalized string*, which
  is the actual unit under test.
- **Pin the fail→skip flip:** sole entry `- "null"` now yields exit 2 + ledger
  `status=skip`.
- **Re-quote** the Test 8 fixtures (`:368-369`, `:382`, `:396`) and delete the
  now-false NOTE at `:352-357` and the comment at `:413`.
- Test 2's `- "touch SHOULD_NOT_RUN"` (`:175`) stays and stops being vacuous.

### Post-phase (risk mitigations)

**`digest_and_pin_diff_check`** — re-run both `baseline_capture` recordings
against the fixed code and assert, explicitly:
- every difference in the three pin outputs is **exactly** one of the three
  intended flips (`a[1]`, `it's`, block trailing whitespace) — any fourth
  difference is a regression, not a repoint;
- **zero** `active_gates_digest` values changed and no task newly fails
  `_digest_halves_ok`. This is the half that can actually fail: the silent
  fallback at `aitask_gate.sh:838-844` gives no other signal.

**`pin_verdict_softening`** — tests at the `run_command_gate` *verdict* level
(not the `read_yaml_list` level, because that is where the verdict lives). Two
of the three prove the **stronger** outcome §2 introduces, rather than
documenting a weaker one:
- a comma-in-quotes item under an opted-in `gate_command_exit_contract` → ledger
  `status=fail`, result "malformed command", **not** `skip`. Must be observed
  failing (as `skip`) before §2 is applied;
- the pre-existing `verify_build: "for x in"` → `status=fail`, not `skip` —
  proving §2 closes the older hole too;
- a genuine skip still works: `exit 2` under the opt-in stays `status=skip`, so
  §2 cannot be satisfied by simply disabling skip;
- and the approved case: sole entry `- "null"` → exit 2 + `status=skip` with
  "no verify_build configured" (was 127 → `status=fail`).

## Verification

Run the new `tests/test_yaml_utils.sh` parity/guard rows **before** touching
`yaml_utils.sh` and record the failure — that is the acceptance criterion.

```bash
bash tests/test_yaml_utils.sh          # 76 passing today; must stay green
bash tests/test_gate_verifiers.sh
bash tests/test_update_multiline_yaml.sh
bash tests/test_attach_meta.sh
bash tests/test_gate_active_gates.sh
bash tests/test_gate_guarded_archival.sh
bash tests/test_gate_stale_witness_parity.sh
bash tests/test_risk_mitigation_landed.sh
bash tests/test_archive_folded.sh
bash tests/test_crew_status.sh
shellcheck .aitask-scripts/lib/yaml_utils.sh .aitask-scripts/lib/gate_verifier_lib.sh
bash tests/run_all_python_tests.sh     # digest / ledger parity
```

Housekeeping — **inspect before removing.** A review subagent left a stray
untracked file in the repo root whose name contains embedded newlines. The
worktree also carries unrelated in-flight changes from concurrent sessions, so
a pattern-based `find … -delete` is not acceptable: resolve the candidate,
print it, prove it is untracked and is the artifact in question, and only then
remove that one bound path.

```bash
mapfile -d '' cands < <(find . -maxdepth 1 -name '*%s]*' -print0)
printf 'candidates: %d\n' "${#cands[@]}"
printf '  %q\n' "${cands[@]}"                       # exact, unambiguous
git status --porcelain --untracked-files=all -z -- "${cands[@]}" | tr '\0' '\n'
```

Proceed only when there is **exactly one** candidate and git reports it as `??`
(untracked); then `rm -- "${cands[0]}"`. More than one candidate, or any
tracked/modified match, means stop and ask. Note that no commit in this task can
sweep it up regardless — commits use explicit pathspecs (`git commit -o -- …`).

Note also that `aiwork/t1606_…/` is a worktree of this repo carrying its own
copies of both touched files — expect to merge there later.

Post-implementation steps (cleanup, archival, merge) follow **Step 9** of the
shared task workflow.

## Risk

### Code-health risk: medium
- **`fail` → `skip` verdict softening.** Two mechanisms, resolved differently.
  (a) A comma-in-quotes item (`["pytest -k 'a,b'"]`) splits into
  unbalanced-quote fragments whose `bash -c` syntax error exits 2 — read as
  *skip* under an opted-in `gate_command_exit_contract`, releasing a
  `blocks_dependents` edge for a command that never ran. **Removed**, not
  pinned: §2 makes an unparseable command a non-skippable fail. (b) A sole
  `- "null"` / `- ""` entry is dropped and the gate skips — **approved**, it is
  what the scalar `verify_build: null` already does.
  · severity: medium · → mitigation: inline post-phase pin_verdict_softening
- **§2 widens `run_command_gate`'s verdict semantics** beyond this task's
  literal scope: *any* unparseable command now fails instead of skipping,
  including configurations that predate t1609. That is the intended direction,
  but it is a behaviour change a project could be unknowingly relying on to keep
  a broken gate quiet. · severity: medium · → mitigation: inline post-phase pin_verdict_softening
- Widening the inline guard at `yaml_utils.sh:266/269` to tolerate trailing
  whitespace changes what parses on the **cross-language digest** path
  (`_yaml_list_csv` → `_digest_halves_ok`). A mistake there is *silent*: the
  digest simply mismatches and the code falls back to raw `gates:`
  (`aitask_gate.sh:838-844`), under-enforcing the profile with no error.
  · severity: medium · → mitigation: inline pre-phase baseline_capture, inline post-phase digest_and_pin_diff_check
- Repointing three t1444 characterization pins by hand could quietly absorb an
  *unintended* fourth behaviour change into a reflowed expected-string compare
  — exactly what those pins exist to prevent.
  · severity: medium · → mitigation: inline pre-phase baseline_capture, inline post-phase digest_and_pin_diff_check
- The change touches the framework's hottest YAML reader, reached by archival,
  gates, crew status and the digest. Blast radius is wide in principle, though
  the measured on-disk corpus (767 field occurrences, zero affected) bounds it.
  · severity: low · → mitigation: inline pre-phase baseline_capture, inline post-phase digest_and_pin_diff_check

### Goal-achievement risk: low
- The parity assertion could be written vacuously (`inline == block` is
  satisfied by making *both* branches over-strip). Addressed in the plan by
  requiring every table row to be a triple — `inline == EXPECTED` **and**
  `block == EXPECTED`. · severity: low · → mitigation: none needed
- Approach, coverage and feasibility are all confirmed: the normalizer and the
  bracket peel were executed against all 16 existing pinned shapes before this
  plan was written, and every acceptance criterion maps to a named test.

### Planned mitigations
- timing: pre-phase | name: baseline_capture | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: guard-widening digest risk + pin-repointing risk | desc: Record the three t1444 pin outputs and every task's active_gates_digest verbatim before editing yaml_utils.sh.
- timing: post-phase | name: digest_and_pin_diff_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: guard-widening digest risk + pin-repointing risk | desc: Re-run both baselines after the fix; assert exactly the three intended pin flips and zero digest churn.
- timing: post-phase | name: pin_verdict_softening | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: fail-to-skip verdict softening | desc: Pin the `- "null"` and comma-in-quotes fail-to-skip flips at the run_command_gate verdict level.

**Reassessment after inlining** (per `risk-evaluation.md`): code-health stays
**medium**, not low. The dangerous half of the verdict risk is now *eliminated*
(§2) rather than pinned, and the inline phases make the digest and pin risks
*detectable* rather than silent — but §2 itself widens `run_command_gate`'s
semantics for pre-existing configurations, which is a new medium-severity
change of its own. Net: medium, for a different and better-understood reason
than before. Goal-achievement stays **low**.

---

## Implementation record

All four sections landed as planned; no deviations from the approved design.

**Pre-phase `baseline_capture` (done).** Captured before any edit:
- the three t1444 pin outputs (`cat -A`, so whitespace is visible);
- `active_gates_digest` for **171** task files (active + archived) plus each
  one's `active-gates-status` verdict — all `FRESH`.

**§1 `yaml_utils.sh`.** Added `_yaml_norm_list_item` (trim → one surrounding
matching quote pair, `-ge 2` guarded), declared `_yaml_item` at function scope,
added the trailing-whitespace trim to the value capture, replaced the inline
branch's global `${value//[\[\]\'\"]/}` with a `#\[` / `%\]` peel, and routed
the block branch's `${BASH_REMATCH[1]}` through the normalizer.

**§2 `gate_verifier_lib.sh`.** `bash -n -c "$c"` pre-validation: an unparseable
command records `status=fail`, `result=malformed <key> command (cannot parse)`,
and breaks — never a skip.

**§3 `gate_verifier_lib.sh`.** Removed the dead `gate_command_exit_contract`
re-strip at the former `:127-129`; kept and re-documented the scalar strip.

**§4 Docs.** Comma caveat (scoped to *inline-list items*, with the verified
scalar carve-out) added to `seed/project_config.yaml` ×3,
`website/…/build-verification.md` ×2, and `website/…/settings/how-to.md`
(which also lost its now-false "flow style" constraint). The
malformed-command → fail rule added to `seed/project_config.yaml`'s
exit-contract block and `aidocs/gates/aitask-gate-framework.md:358`.

### Observed-failing-first evidence

| stage | result |
|---|---|
| new `test_yaml_utils.sh` rows, **before** §1 | **27 failed** (97/124) |
| after §1 | 121/124 — exactly the 3 predicted characterization flips left |
| after repointing those 3 pins | 125/125 |
| after adding the direct unit layer | **148/148** |
| new `test_gate_verifiers.sh` rows, **before** §2 | **6 failed** (139/145) — both malformed cases recorded `skip` |
| after §2 + §3 | **145/145** |

The rejection probe (`- echo "hi"`, `- a[1]`) passed both before and after, as
designed: it guards against the wrong fix, it is not the reproducer.

### Post-phase `digest_and_pin_diff_check` (done)

- Pin diff is **exactly three lines**: `d  `→`d`, `a1`→`a[1]`, `its`→`it's`.
  No fourth difference — nothing unintended was absorbed into a repointed pin.
- Stored `active_gates_digest` across all 171 tasks: **byte-identical**
  (`diff` empty). All 171 still `FRESH`; none newly fails `_digest_halves_ok`.

### Post-phase `pin_verdict_softening` (done)

Test 2c pins the stronger outcome (comma-split flow item → fail; the
pre-existing `for x in` → fail) with **two negative controls** — a genuine
`exit 2` still skips, and a parseable runtime failure keeps the ordinary
`command failed (exit 7)` wording — so §2 cannot be satisfied by disabling skip
altogether. Test 2d pins the approved `- "null"` → skip.

### Verification run

`test_yaml_utils` 148/148 · `test_gate_verifiers` 145/145 ·
`test_update_multiline_yaml` 23/23 · `test_attach_meta` rc=0 ·
`test_gate_active_gates` 114/114 · `test_gate_guarded_archival` 31/31 ·
`test_gate_stale_witness_parity` 29/29 · `test_risk_mitigation_landed` rc=0 ·
`test_archive_folded` 8/8 · `test_crew_status` rc=0 · shellcheck clean.

Python suite: **5257 passed, 2 failed** — `test_shadow_phase_restamp.py` and
`test_collection_structure.py`. **Neither is this task's.** Both are caused by a
concurrent session's uncommitted edits to `monitor/minimonitor_app.py` and
`tests/test_minimonitor_auto_close_guard.py`; reverting only those two files
makes both tests pass, and restoring them reproduces the failures. This task
touches no Python.

### Notes for review

- `main` advanced during the session (`468d997f8` → `9cda5eb66`, four commits);
  none touched any file this task changes.
- The shared worktree carries unrelated in-flight changes from other sessions,
  so the commit is path-scoped (`git commit -o -- <paths>`).
- A pre-existing `stash@{0}` from 2026-07-19 (different base, unrelated files)
  was left untouched.

## Final Implementation Notes

- **Actual work done:** Exactly the approved four sections. `_yaml_norm_list_item`
  in `yaml_utils.sh` is now the single definition of "what one list item
  resolves to", called by both the inline and block branches; the inline branch
  peels only the wrapping brackets; the value capture also trims trailing
  whitespace. `gate_verifier_lib.sh` gained a `bash -n` pre-validation that makes
  an unparseable command a fail rather than a skip, and lost the dead
  `gate_command_exit_contract` quote-strip. Four docs carry the comma caveat and
  the malformed-command rule. Tests: +371 lines across two files (direct unit
  layer, 16-row triple parity table, guard row, rejection probe, residual pins,
  cross-language pin, hardened e2e, four verdict tests with two negative
  controls), plus three repointed t1444 characterizations.

- **Deviations from plan:** None.

- **Issues encountered:**
  - The baseline digest scan initially found 0 tasks because `aitasks/` is a
    symlink to the data-branch worktree and `find` does not follow symlinks by
    default. Re-run with a `grep -r` enumeration — 171 tasks, all `FRESH`.
  - The first `active-gates-status` pass derived child ids wrongly
    (`t1149_5_…` → `1149`), reporting `ABSENT`. Fixed by deriving the id from
    the containing `t<parent>/` directory.
  - Two Python tests fail in the shared worktree
    (`test_shadow_phase_restamp.py`, `test_collection_structure.py`). Proven
    **not** this task's: reverting only a concurrent session's uncommitted
    `monitor/minimonitor_app.py` and `tests/test_minimonitor_auto_close_guard.py`
    makes both pass, and restoring them reproduces the failures. This task
    touches no Python.

- **Key decisions:**
  - **Both branches, not just the block one.** Fixing only the block branch
    would have satisfied the literal bug report but left the inline branch the
    over-eager side (`[echo "hi"]` → `echo hi`), so true parity — the task's own
    stated test oracle — was unreachable. Cost: three deliberate characterization
    flips, each repointed with its description rewritten and tagged `# t1609`.
  - **Variable-return, not `$(...)`.** A command-substitution call site would
    fork once per list item on the framework's hottest reader, re-introducing the
    forks t1444 removed for the closed-pipe write contract.
  - **`#\[`/`%\]` peel, not `${value:1:${#value}-2}`.** The arithmetic form is
    coupled to the guard's exact anchoring and would eat a space instead of the
    `]` if that guard were ever relaxed.
  - **`-ge 2` guard kept though redundant.** The `case` globs already need two
    quote chars, but lone quotes *are* reachable (`[",", x]` peels to `"`,`"`,`x`)
    and the obvious `[[ ]]` refactor of that `case` matches one and aborts the
    reader with `substring expression < 0`. Pinned by four lone-quote rows.
  - **Trim before unquote.** Load-bearing for CRLF-authored configs; reversing
    the order silently breaks them. Pinned.
  - **Malformed command → fail, never skip.** Pinning the softening would only
    have documented it. `bash -n` separates "could not parse" from "ran and
    reported it did not run", and also closes the pre-existing hole where
    `verify_build: "for x in"` was recorded as a skip.
  - **Declined:** quote-aware comma splitting (needs a per-character bash loop on
    the hottest reader); aligning the Python twin's `.strip("'\"")` — bash is the
    YAML-correct side there, so the divergence is documented, not "fixed".

- **Upstream defects identified:**
  - `.aitask-scripts/lib/gate_ledger.py:531,535-537` — `_read_frontmatter_list_from_text`
    strips a *run* of quote chars off either end via `.strip("'\"")`, so a block
    item `- echo "hi"` becomes `echo "hi` (trailing quote eaten). Deliberately
    not changed here: this reader feeds only identifier-shaped gate fields, and
    bash is now the YAML-correct side. Reachable only if a command-shaped value
    is ever read through it.
  - `.aitask-scripts/lib/yaml_utils.sh:250-262` — the value-capture loop counts
    `[`/`]` without quote awareness, so `verify_build: ["ls ["]` leaves the depth
    counter at 1 and swallows subsequent config lines until a `]` appears.
    Pre-existing; untouched by this task.
  - `.aitask-scripts/lib/config_utils.py:326-345` — the settings TUI saves
    `verify_build` through `yaml.safe_dump(default_flow_style=False)`, which
    single-quotes any scalar starting `[`, `*`, `#` or containing `: `. Harmless
    now that the reader unquotes, but it means the TUI silently changes the
    on-disk quoting of a command the user typed unquoted.
