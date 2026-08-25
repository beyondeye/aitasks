---
Task: t1601_resync_codex_opencode_instruction_mirrors.md
Branch: main
Base branch: main
Output branch: main
---

# t1601 — Resync the Codex / OpenCode instruction mirrors + add a content drift guard

## Context

`seed/aitasks_agent_instructions.seed.md` is the single source for the
`>>>aitasks` … `<<<aitasks` instruction block. Exactly three tracked files mirror
it (confirmed — no fourth surface; `CLAUDE.md` is deliberately markerless and
hand-maintained):

| surface | layers | generator | gated? |
|---|---|---|---|
| `AGENTS.md` | shared seed only | `update_agentsmd` | **no** — always runs |
| `.codex/instructions.md` | shared + `seed/codex_instructions.seed.md` tail | `setup_codex_cli` | **yes** |
| `.opencode/instructions.md` | shared + `seed/opencode_instructions.seed.md` tail | `setup_opencode` | **yes** |

All three go through `assemble_aitasks_instructions()` +
`insert_aitasks_instructions()` (`.aitask-scripts/aitask_setup.sh:1276-1348`) —
the only call sites in the tree; `install.sh` never calls either.

The two mirror regenerations are skipped whenever **any** of these hold:
`_is_agent_installed` is false (`aitask_setup.sh:215-222`, dispatched at
`2538-2546`); the `aitasks/metadata/{codex,opencode}_skills` staging dir is
absent (`2300-2305` / `2442-2447`, "No … staging files found — skipping"); or
the user declines the interactive prompt (`2326-2328` / `2467-2469`).
`update_agentsmd` has no such guard — which is exactly why `AGENTS.md` stays
current while the two mirrors rot silently.

Measured drift today: both mirrors are missing the **same 10 lines** relative to
the seed; everything else is byte-identical (verified by `diff`).

- the 5 gate lines in the `## Task File Format` YAML block — `gates:` plus the
  four `active_gates*` lines;
- the 4-line paragraph explaining the derived `active_gates*` tuple, plus its
  preceding blank line.

Existing coverage does not catch this. `tests/test_agent_instructions.sh:480-506`
(T22/T23, the t1028 guard) asserts the committed mirrors carry exactly one marker
**pair** — it never looks at what is *between* the markers. Nothing anywhere
compares mirror content against the seed.

Outcome wanted: the mirrors match what `ait setup` would generate, and this class
of silent, install-dependent drift becomes a failing test instead of something
noticed by accident during an unrelated task.

## Approach

### Part A — Resync the mirrors through the canonical generator

The task file's "Suggested fix" says to copy the block out of `AGENTS.md`
verbatim. **Deliberate deviation: don't.** `AGENTS.md` carries the shared layer
only, so a verbatim copy would destroy each mirror's per-agent
`## Agent Identification` tail. Drive the same two functions `ait setup` calls,
so the result is byte-identical to a real setup run on a machine that *does*
have the CLIs:

```bash
source .aitask-scripts/aitask_setup.sh --source-only
for agent in codex opencode; do
  case "$agent" in
    codex)    target=.codex/instructions.md ;;
    opencode) target=.opencode/instructions.md ;;
  esac
  content="$(assemble_aitasks_instructions . "$agent")"
  insert_aitasks_instructions "$target" "$content"
done
```

Pre-verified in this session: this reproduces each mirror exactly, restoring the
10 drifted lines and preserving the per-agent tail (`diff` of regenerated content
vs. the current block shows *only* those 10 additions, nothing else).

Files changed: `.codex/instructions.md`, `.opencode/instructions.md`.

### Part B — Content drift guard

**Home: append to `tests/test_agent_instructions.sh`**, immediately after the
t1028 block (`:480-506`), as a new `--- seed → mirror content drift (t1601) ---`
section. That file already sources `aitask_setup.sh --source-only` and already
asserts *real repo artifacts* (T22/T23), so the new tests sit beside the guard
they extend rather than in a new file that would duplicate the harness.

**Derive, don't duplicate.** Nothing is hardcoded: each surface is compared
against what the **live** generator produces from the **live** seeds.

One non-asserting predicate, asserted in both directions:

```bash
# block_status <project_dir> <file> <workdir> [agent]
#   -> MATCH | MISMATCH | ASSEMBLE_FAILED | NO_SUCH_FILE
#      NO_START_MARKER | NO_END_MARKER | MULTIPLE_BLOCKS | MARKERS_OUT_OF_ORDER
```

- structural verdict first, resolved by a **single `awk` pass** that both extracts
  the body and classifies the file (`_extract_marked_block`). Counting markers
  with `grep -c` and extracting with a *separate* pass cannot express **order**:
  a file whose `<<<aitasks` precedes its `>>>aitasks` counts 1 and 1, and a
  start-to-EOF extraction then yields the whole tail, so an unterminated block
  compares equal and returns `MATCH` (confirmed live during Step 8 review). One
  state machine has no second pass to disagree with. Sentinels: missing file,
  missing start marker, missing end marker, more than one pair, markers out of
  order;
- then **byte-preserving comparison via files — never `$( )`**. Both sides are
  produced by redirection into `$workdir/expected` and `$workdir/actual` and
  compared with `cmp -s`:

  ```bash
  assemble_aitasks_instructions "${args[@]}" > "$work/expected" 2>"$work/assemble.err" || rc=$?
  awk '/^>>>aitasks$/{f=1;next} /^<<<aitasks$/{f=0} f' "$file" > "$work/actual"
  cmp -s "$work/expected" "$work/actual" && echo MATCH || echo MISMATCH
  ```

  **Capturing either side through a command substitution would fail open.** Bash
  strips *all* trailing newlines from `$( )`, on both sides of the comparison, so
  a hand-added blank line immediately before `<<<aitasks` would compare equal.
  Reproduced: a block with two trailing blank lines reads `MATCH` under `$( )`
  capture and `differs` under `cmp` on files. Leading and interior differences
  were never affected — only the trailing edge — but a guard whose entire job is
  byte equality must not have a blind edge. `args` is built as an array so the
  agent layer can be omitted without an unquoted expansion;
- **fails closed** everywhere else: a non-zero assemble or an empty
  `$work/expected` yields `ASSEMBLE_FAILED`, never a silent `MATCH`. Because the
  structural sentinels return *before* the comparison, an unextractable block can
  never reach `cmp` and read as equal.

Note on the trailing byte: all three seeds end with a newline today (verified),
and `insert_aitasks_instructions` strips trailing newlines from the content it
writes, so both sides end with exactly one `\n`. A future seed added without a
final newline would make `expected` one byte shorter than `actual` and turn the
guard red — noisy, but fail-closed, and a seed missing its final newline is worth
surfacing anyway.

Positive assertions (T25–T27), one per surface:

| test | file | agent layer |
|---|---|---|
| T25 | `AGENTS.md` | *(none — shared only)* |
| T26 | `.codex/instructions.md` | `codex` |
| T27 | `.opencode/instructions.md` | `opencode` |

Each asserts `MATCH`; a wrapper dumps `diff <(expected) <(actual)` on failure so
the message names the drifted lines instead of dumping two 100-line blobs.

Negative controls (T28–T34) — **one per advertised sentinel**, so every outcome
the helper's contract names is executable and none is advertised-but-unproven.
All run against throwaway copies under `mktemp -d`; the tracked files are never
mutated:

| test | fixture | expected |
|---|---|---|
| T28 | mirror copy with `gates: [risk_evaluated]` deleted | `MISMATCH` |
| T29 | mirror copy with an extra line inserted | `MISMATCH` |
| T30 | copy with `<<<aitasks` removed | `NO_END_MARKER` |
| T31 | copy with no markers at all | `NO_START_MARKER` |
| T32 | assemble against a fixture dir holding neither `aitasks/metadata/*.seed.md` nor `seed/*.seed.md` | `ASSEMBLE_FAILED` |
| T33 | a path that does not exist | `NO_SUCH_FILE` |
| T34 | copy with the marked block duplicated (two marker pairs) | `MULTIPLE_BLOCKS` |
| T35 | copy with a blank line inserted immediately before `<<<aitasks` | `MISMATCH` |
| T36 | `<<<aitasks` first, then `>>>aitasks` + the real content, nothing closing it | `MARKERS_OUT_OF_ORDER` |
| T37 | a stray `<<<aitasks` prepended to a well-formed block | `MULTIPLE_BLOCKS` |

T34 is not hypothetical: a duplicated block is the exact t1028 failure mode that
T22/T23 exist to catch, and `block_status` must report it as its own state rather
than silently extracting the first block and comparing it as `MATCH`.

**T36 pins the marker-ordering gap.** Its fixture has marker counts of exactly
1 and 1, so it passes every count-based check while having no closing marker at
all — it is the fixture that fails the moment anyone reintroduces
count-plus-separate-extraction. T37 pins the *precedence* between the structural
verdicts so it is asserted rather than incidental.

**T35 pins the trailing-newline gap specifically** — it is the one fixture that
distinguishes the file-based comparison from a `$( )` one, so it fails if anyone
later "simplifies" `block_status` back to command substitution.

**T28 is the proof that this guard would have caught t1601.** It copies the real
tracked `.codex/instructions.md` and deletes the exact line the drift was missing,
so the demonstration lives entirely in a temp fixture — no tracked file is ever
put into a corrupt state, and no restore step has to survive an interrupt.

#### Post-phase (risk mitigations)

**`report_resolved_seed_source`** — runs after the guard section above is
written. `assemble_aitasks_instructions` resolves its shared seed by preference
(`aitasks/metadata/aitasks_agent_instructions.seed.md`, else
`seed/aitasks_agent_instructions.seed.md`), so a red guard could mean "the mirror
drifted" *or* "this checkout's metadata seed copy drifted" — and the diff alone
does not distinguish them. Add a `resolved_shared_seed()` helper mirroring that
same precedence, and have the T25–T27 failure dump print the path it returns
alongside `diff -u "$work/expected" "$work/actual"`. It is diagnostic only: it
changes no verdict, and the positive/negative controls above are unaffected.

Conventions: the file's existing `set -e` stays; every command substitution that
may fail is written `x="$(…)" || rc=$?` and every `grep -c` gets `|| true`, so no
negative control aborts the run. Test bodies stay at top level (no `( … )`
subshells), so the file-backed counter opt-in is not needed. Reuse
`assert_eq` from `tests/lib/asserts.sh`, already sourced at `:24`.

No test registration is needed — shell tests are discovered by
`.aitask-scripts/aitask_gate_tests_pass.sh`, and this is an existing file.

### Part C — Correct the extension-points doc

`aidocs/framework/aitasks_extension_points.md:44-62` is the only place that
documents this regeneration duty. Two edits in that passage:

1. **Fix the wrong recovery recipe.** "copy the generated block out of `AGENTS.md`
   verbatim" is wrong for the mirrors — it drops the per-agent tail. Replace it
   with the `assemble_aitasks_instructions` + `insert_aitasks_instructions`
   recipe from Part A.
2. **Point at the guard**, so the checklist tells the author how to *detect* the
   drift instead of relying on a manual `grep` of three files.

Deliberately **not** touching `CLAUDE.md`: it is always-loaded context, and the
extension-points doc is already the pointer target it names for this checklist.

## Risk

### Code-health risk: low
- The guard resolves its seed through `assemble_aitasks_instructions`, which
  prefers `aitasks/metadata/*.seed.md` over `seed/*.seed.md`. In this repo the
  data-branch metadata dir holds no instruction seeds so it resolves to `seed/`,
  but a checkout whose metadata copy drifted would send the guard red for a
  reason unrelated to the tracked mirrors · severity: low · → mitigation: inline post-phase report_resolved_seed_source
- Blast radius is two generated instruction files (restored to their generator's
  own output), one additive test section, and one doc passage. No production code
  path changes; the mirrors are agent-facing prose, not executed code · severity:
  low · → mitigation: none needed

### Goal-achievement risk: low
- The task asks for exactly two things — resync the mirrors, and "consider a
  drift guard". Both are delivered, plus the doc correction the task's own
  diagnostic section implies. Feasibility is not assumed: the regeneration was
  already diffed against the live mirrors in this session · severity: low ·
  → mitigation: none needed
- One deliberate deviation from the task's stated "Suggested fix" (copy from
  `AGENTS.md`), because that recipe would drop the per-agent tail. Flagged here
  rather than made silently · severity: low · → mitigation: none needed

### Planned mitigations
- timing: post-phase | name: report_resolved_seed_source | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — seed-precedence ambiguity in the guard | desc: report which shared seed path assemble_aitasks_instructions resolved, so a drifted metadata seed copy is diagnosable instead of reading as mirror drift

## Verification

```bash
# 0. BEFORE editing anything: capture the baseline assertion count, so step 2's
#    "did the new tests actually run" check has something to compare against.
bash tests/test_agent_instructions.sh | tail -3   # record the TOTAL

# 1. Whole instruction suite green after Part A + B.
bash tests/test_agent_instructions.sh

# 2. Proof the guard can fail on the t1601 drift comes from T28, which performs
#    that deletion on a COPY of the tracked mirror. No step here mutates a
#    tracked file — a manual "break it, run the suite, restore it" dance would
#    leave the working tree corrupt if the shell were interrupted before the
#    restore, and it would only re-prove what T28 already asserts.
#    The negative controls are self-proving: each asserts a SPECIFIC sentinel,
#    so a block_status that stopped discriminating (always MATCH, or always the
#    same sentinel) turns T28-T34 red rather than green. Confirm they actually
#    EXECUTED — a skipped block is invisible in a green run — by checking the
#    summary's TOTAL grew by the number of assertions added:
bash tests/test_agent_instructions.sh | tail -3   # "PASS: N / TOTAL"; TOTAL must
                                                  # exceed the pre-change count

# 2b. The mirrors really are byte-identical to the generator (independent of the
#     suite, using process substitution — which does NOT strip trailing bytes):
source .aitask-scripts/aitask_setup.sh --source-only
diff <(assemble_aitasks_instructions . codex) \
     <(awk '/^>>>aitasks$/{f=1;next} /^<<<aitasks$/{f=0} f' .codex/instructions.md)
diff <(assemble_aitasks_instructions . opencode) \
     <(awk '/^>>>aitasks$/{f=1;next} /^<<<aitasks$/{f=0} f' .opencode/instructions.md)
diff <(assemble_aitasks_instructions .) \
     <(awk '/^>>>aitasks$/{f=1;next} /^<<<aitasks$/{f=0} f' AGENTS.md)
# all three MUST print nothing and exit 0
git status --porcelain    # MUST show only the files this task intends to change

# 3. No regression in the neighbouring seed/setup tests.
bash tests/test_setup_agent_config_seeds.sh
bash tests/test_opencode_setup.sh
bash tests/test_seed_manifest_drift.sh

# 4. Lint.
shellcheck tests/test_agent_instructions.sh

# 5. Spot-check the restored content and the surviving per-agent tail.
grep -c 'active_gates' .codex/instructions.md .opencode/instructions.md   # 5 each
grep -c '## Agent Identification' .codex/instructions.md .opencode/instructions.md
```

Step 9 (Post-Implementation) handles cleanup, archival, and the merge.
