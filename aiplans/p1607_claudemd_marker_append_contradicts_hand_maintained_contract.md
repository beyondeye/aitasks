---
Task: t1607_claudemd_marker_append_contradicts_hand_maintained_contract.md
Branch: main
Base branch: main
Output branch: main
---

# t1607 — Restore the hand-maintained `CLAUDE.md` contract in `ait setup`

## Context

`aidocs/framework/aitasks_extension_points.md:96-97` documents `CLAUDE.md` as
hand-maintained and markerless, and this repo's `CLAUDE.md` agrees
(`grep -c '>>>aitasks' CLAUDE.md` → 0). The code does not agree:
`update_claudemd_git_section` (`.aitask-scripts/aitask_setup.sh:1352`) hands the
file to `insert_aitasks_instructions`, whose `else` branch **appends** a full
marked block to any markerless file. A real `ait setup` reaching
`setup_data_branch` Step 8 would therefore grow `CLAUDE.md` a duplicate of its
hand-written `### Task File Format`, `### Task Hierarchy`,
`## Git Operations on Task/Plan Files`, `## Commit Message Format` and
`### Folded Task Semantics` sections.

**This is a regression, not a design disagreement.** The original function
(t221_3, `52837495f`) opened with a content-based skip guard:

```bash
local section_header="## Git Operations on Task/Plan Files"
if [[ -f "$claudemd" ]] && grep -qF "$section_header" "$claudemd"; then
    return
fi
```

That guard is *why* this repo's `CLAUDE.md` is markerless — setup ran and
correctly declined. t130_2 (`3b7de3531`) generalized the function to the
`>>>aitasks` marker system and replaced the guard with the marker check **inside**
`insert_aitasks_instructions`, silently dropping the escape hatch for a
hand-maintained file. The documented contract has been true by accident ever
since (this repo only survives because `setup_data_branch` early-returns when
`.aitask-data/.git` already exists).

**Decision (user-confirmed):** the documented contract is real. Restore the skip
guard, keep bootstrap behavior for ordinary/absent `CLAUDE.md`, and add
regression coverage for the markerless-but-already-instructed case.

The guard also fixes a second population generically: projects set up **between
t221_3 and t130_2** carry a markerless `## Git Operations on Task/Plan Files`
section, and today's code would append a duplicate marked block on top of it.

## Design

`CLAUDE.md` is the only instruction surface that is **project-owned mixed
content**. `AGENTS.md`, `.codex/instructions.md` and `.opencode/instructions.md`
are framework-owned files whose entire body *is* the marked block, so appending
to a markerless one of those is correct bootstrap. The guard therefore lives in
`update_claudemd_git_section` only — `insert_aitasks_instructions` stays generic
and untouched.

Three-way behavior after the change:

| `CLAUDE.md` state | action |
|---|---|
| absent | create with markers (unchanged — T10) |
| present, no markers, no aitasks prose | append marked block (unchanged — T11) |
| present, markers | replace between markers (unchanged — T12) |
| **present, no markers, already carries aitasks prose** | **skip + tell the user how to opt in (new)** |

Marker check runs **first**: a marker-managed block necessarily contains the
sentinel, so guard-before-marker would freeze every legitimate refresh.

## Implementation

### 1. `.aitask-scripts/aitask_setup.sh` — the guard

Add a named constant immediately above `update_claudemd_git_section` (:1351),
following the file's existing plain-uppercase-global style (no `readonly` — the
script is sourced repeatedly by the test scaffold):

```bash
# Sentinel proving a markerless CLAUDE.md already documents the aitasks
# conventions by hand. The shared seed's most aitasks-specific heading; pinned
# to the live seed by tests/test_agent_instructions.sh T39.
CLAUDEMD_HAND_MAINTAINED_SENTINEL="## Git Operations on Task/Plan Files"
```

In `update_claudemd_git_section`, between the `content=` assignment and the
`insert_aitasks_instructions` call:

```bash
    # CLAUDE.md is the one project-OWNED instruction surface (AGENTS.md and the
    # two mirrors are framework-owned files whose whole body is the block). A
    # markerless CLAUDE.md that already documents the aitasks conventions is
    # hand-maintained -- this repo's own, and every project set up before the
    # markers existed -- so appending would duplicate prose the project owns.
    # Markers win: a marker-managed block contains the sentinel and must refresh.
    if [[ -f "$claudemd" ]] \
        && ! grep -qF ">>>aitasks" "$claudemd" \
        && grep -qF "$CLAUDEMD_HAND_MAINTAINED_SENTINEL" "$claudemd"; then
        info "  CLAUDE.md documents the aitasks conventions and has no >>>aitasks markers — leaving it hand-maintained."
        info "  To let 'ait setup' manage a block here, add an EMPTY '>>>aitasks' / '<<<aitasks' line pair where you want it."
        info "  Everything between those markers is overwritten on every setup — never wrap prose you wrote yourself."
        return 0
    fi
```

The opt-in wording is load-bearing, not decoration. `insert_aitasks_instructions`
(:1334-1341) implements its replace branch as:

```awk
$0 == start { print block; skip=1; next }
$0 == end && skip { skip=0; next }
!skip { print }
```

— it prints the generated block at `>>>aitasks` and then **discards every line
until `<<<aitasks`**. So "wrap your existing block in markers" would literally
instruct the user to destroy their own prose on the next `ait setup`. The safe
opt-in is an **empty marker pair** (a `>>>aitasks` line immediately followed by
`<<<aitasks`): the same awk prints the block at the start marker and consumes
only the end marker, filling the region in place with nothing lost. Hence the
third message line, which states the region is generated-and-replaceable.

`info()` (:137) writes to **stdout**, so these lines are capturable by the tests
below — see T12b.

No other call site changes. `update_agentsmd`, `setup_codex_cli` and
`setup_opencode` keep the unguarded append.

### 2. `tests/test_agent_instructions.sh` — coverage

Three behavioral tests appended to the existing
`--- update_claudemd_git_section() ---` section (after T12, using the file's
established letter-suffix convention so no renumbering is needed).
`setup_tmpdir`'s mock seed already contains the sentinel heading, so the
fixtures work as-is:

- **T12b — hand-maintained file untouched, *and* the skip is announced.**
  Markerless `CLAUDE.md` containing the sentinel plus custom prose. Assert the
  file is byte-identical before/after and that no `>>>aitasks` was added — then
  **capture the function's stdout and assert all three message fragments**:
  `leaving it hand-maintained`, `'>>>aitasks' / '<<<aitasks' line pair`, and
  `overwritten on every setup`. The file assertions alone cannot distinguish the
  intended guard from a bare `return 0`: a regression that silently no-ops
  passes every byte-identity check while destroying both the discoverability and
  the data-loss warning that make a content-sniffing skip safe. The two
  opt-in fragments are asserted separately from the reason fragment so trimming
  the destructive warning down to "wrap it in markers" — the exact wording this
  plan rejects above — fails the test rather than merely reading differently.
- **T12c — negative control: the guard is not a blanket skip.** Markerless
  `CLAUDE.md` *without* the sentinel still gets the block appended. T11 covers
  the same path but not the discriminating dimension; T12c pins it explicitly so
  a widened sentinel cannot silently disable bootstrap.
- **T12d — marker precedence.** A marker-managed `CLAUDE.md` whose block
  *contains* the sentinel is still refreshed. T12's fixture body is
  `OLD INSTRUCTIONS HERE` (no sentinel), so it cannot catch an inverted
  condition order; T12d can.

Two guards appended after T37, in the seed→mirror drift-guard section (the
"fourth surface" assertion the task asks for):

- **T38 — committed `CLAUDE.md` intended state.** Assert **zero**
  `^>>>aitasks$` and zero `^<<<aitasks$` lines in `$PROJECT_DIR/CLAUDE.md`, *and*
  that it contains the sentinel. Both halves matter: markers-absent alone would
  still pass if someone deleted the `## Git Operations` section, which would
  quietly make the file append-eligible again. Mirrors the existing
  `assert_marker_pair` helper inverted (written inline with `assert_eq`, since
  that helper hardcodes 1/1).
- **T39 — sentinel drift guard.** Assert
  `$CLAUDEMD_HAND_MAINTAINED_SENTINEL` appears in the seed resolved by the
  existing `resolved_shared_seed "$PROJECT_DIR"` helper. Canonical-site +
  drift-guard: the constant is a single named string, and this test fails the
  moment the seed renames that heading.

### 3. `aidocs/framework/aitasks_extension_points.md` — the doc

Rewrite the `CLAUDE.md` bullet (:96-97) so the documented contract states *why*
it holds and *what enforces it*, instead of asserting a fact that used to be
accidental:

- hand-maintained, edit directly — unchanged guidance;
- `CLAUDE.md` is project-owned mixed content, unlike the three framework-owned
  marker surfaces above it;
- `update_claudemd_git_section` skips a markerless `CLAUDE.md` carrying the
  aitasks conventions, detected via `CLAUDEMD_HAND_MAINTAINED_SENTINEL`;
- the opt-in path — **add an empty `>>>aitasks` / `<<<aitasks` line pair** where
  the generated block should go, with the explicit warning that the marked
  region is generated-and-replaceable: `insert_aitasks_instructions` discards
  everything between the markers on every run, so marking existing hand-authored
  prose silently destroys it;
- a project with no aitasks prose in `CLAUDE.md` still gets the block on first
  setup;
- T38/T39 pin both halves (t1607).

The same replace-everything-between-markers caveat applies to the three
framework-owned marker surfaces listed above it, but is harmless there: their
whole body *is* the generated block. It is called out on the `CLAUDE.md` bullet
because that is the only surface where a human's own prose can sit next to the
markers.

## Verification

```bash
shellcheck .aitask-scripts/aitask_setup.sh
bash -n .aitask-scripts/aitask_setup.sh
bash tests/test_agent_instructions.sh     # T10-T12d, T22-T39
bash tests/test_data_branch_setup.sh      # Tests 6/7/8 exercise the same function
bash tests/test_opencode_setup.sh         # insert_aitasks_instructions unchanged
```

All three existing `update_claudemd_git_section` fixture sets are
guard-compatible by construction and must stay green:
`test_agent_instructions.sh` T10 (absent) / T11 (`# My Project`) / T12 (markers),
and `test_data_branch_setup.sh` Tests 6 / 7 / 8.

Manual end-to-end (the reported scenario, on a throwaway copy — the real
`ait setup` cannot reach Step 8 in this repo because `.aitask-data/.git` exists):

```bash
work=$(mktemp -d); mkdir -p "$work/aitasks/metadata"
cp seed/aitasks_agent_instructions.seed.md "$work/aitasks/metadata/"
cp CLAUDE.md "$work/CLAUDE.md"
before=$(md5sum < "$work/CLAUDE.md")
source .aitask-scripts/aitask_setup.sh --source-only
update_claudemd_git_section "$work"
[ "$before" = "$(md5sum < "$work/CLAUDE.md")" ] && echo "PASS: untouched" || echo "FAIL: modified"
grep -c '>>>aitasks' "$work/CLAUDE.md"   # expect 0
rm -rf "$work"
```

Two positive controls on the same fixture, so the PASS above is not vacuous and
the advice the message gives is not merely plausible:

1. Strip the sentinel section → confirm the block *is* appended.
2. **Exercise the documented opt-in end to end.** Append an empty
   `>>>aitasks` / `<<<aitasks` line pair to the fixture, run
   `update_claudemd_git_section` twice, and confirm the generated block lands
   *between* those markers, the surrounding hand-written prose survives both
   runs, and the marker count stays at 1/1. If the instruction the guard prints
   does not actually work, the message is worse than no message.

## Risk

### Code-health risk: low
- The guard reintroduces content sniffing into a bootstrap path: a project whose
  `CLAUDE.md` contains `## Git Operations on Task/Plan Files` for unrelated
  reasons would silently not receive the block. · severity: low · → mitigation:
  inline post-phase `announce_skip_with_opt_in` — the skip is announced with the
  marker opt-in path, so it is never silent.
- **The opt-in guidance can itself destroy user prose.** The marked region is
  overwritten wholesale by `insert_aitasks_instructions` on every setup, so a
  message reading "wrap your block in markers" would talk a user into losing the
  very hand-maintained content this task exists to protect. · severity: medium ·
  → mitigation: inline post-phase `announce_skip_with_opt_in` — the message
  directs users to an *empty* marker pair and states the region is
  generated-and-replaceable; T12b pins that wording.
- The sentinel is a hardcoded string that can drift from the seed. · severity:
  low · → mitigation: inline post-phase `pin_sentinel_to_seed` (T39).

### Goal-achievement risk: medium
- The guard is **unreachable in this repo and in every already-configured
  project**: `update_claudemd_git_section` is called only from
  `setup_data_branch` Step 8 (`aitask_setup.sh:1661`), which early-returns when
  `.aitask-data/.git` exists and when the user declines the data branch. So the
  fix is verified by direct function invocation and fixtures, not by running
  `ait setup`, and the underlying lifecycle defect (CLAUDE.md never refreshed on
  re-runs, never written at all in legacy mode — unlike `AGENTS.md`, regenerated
  unconditionally by `update_agentsmd` from `setup_code_agents`) survives this
  task. · severity: medium · → mitigation: t1612
- The task's alternative resolution (marker-manage `CLAUDE.md` everywhere) is
  foreclosed by this change. · severity: low · → mitigation: none — the user
  chose the hand-maintained contract explicitly, and the doc records why.

### Planned mitigations
- timing: post-phase | name: announce_skip_with_opt_in | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: silent-skip on an unrelated heading match, and opt-in guidance that would destroy user prose | desc: the skip prints the reason plus a safe opt-in (add an EMPTY marker pair) and warns the marked region is overwritten every setup; T12b asserts all three fragments on captured stdout
- timing: post-phase | name: pin_sentinel_to_seed | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: hardcoded sentinel drifting from the shared seed | desc: T39 asserts CLAUDEMD_HAND_MAINTAINED_SENTINEL appears in the seed resolved by resolved_shared_seed
- timing: after | name: t1607_placement_followup | type: bug | priority: medium | effort: low | inline_risk: medium | added_complexity: medium | addresses: guard unreachable on already-configured and legacy-mode projects | desc: move update_claudemd_git_section out of setup_data_branch Step 8 to beside update_agentsmd in setup_code_agents so CLAUDE.md is regenerated on every setup, with coverage for re-runs and legacy mode | created: t1612

### Post-phase (risk mitigations)

- **`announce_skip_with_opt_in`** — part of Implementation §1: the guard's three
  `info` lines state the reason, the *empty-marker-pair* opt-in, and the
  overwrite warning before `return 0`. Pinned by T12b (Implementation §2), which
  asserts all three on captured stdout.
- **`pin_sentinel_to_seed`** — part of Implementation §2: test T39.

## Post-Implementation

See `task-workflow` **Step 9** for cleanup, archival, and merge. Current-branch
mode (profile `fast`): nothing to merge; Step 9 archives `t1607` and this plan.
Step 8d creates the `t1607_placement_followup` "after" mitigation.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, in three files.
  `.aitask-scripts/aitask_setup.sh` (+20): added the
  `CLAUDEMD_HAND_MAINTAINED_SENTINEL` constant above
  `update_claudemd_git_section` and a marker-first guard inside it that returns
  early — with three `info` lines — for a markerless `CLAUDE.md` already
  carrying the sentinel. `tests/test_agent_instructions.sh` (+109): T12b/T12c/T12d
  in the existing `update_claudemd_git_section` section, and T38/T39 in a new
  "CLAUDE.md hand-maintained contract" section after T37.
  `aidocs/framework/aitasks_extension_points.md` (+34/-2): rewrote the
  `CLAUDE.md` bullet.
- **Deviations from plan:** None.
- **Issues encountered:**
  - **Two plan-review concerns raised by the user before approval, both valid and
    both folded into the plan before implementation.** (1) The first-draft skip
    message told users to "wrap" their existing block in markers — but
    `insert_aitasks_instructions`' awk replace branch discards every line between
    the markers, so that advice would have destroyed the very hand-maintained
    prose this task protects. Corrected to an **empty marker pair** plus an
    explicit generated-and-replaceable warning. (2) The first-draft T12b asserted
    only byte-identity and marker absence, which a guard degraded to a bare
    `return 0` would pass. Corrected to also assert the three messages on
    captured stdout (`info()` writes to stdout, `aitask_setup.sh:137`).
  - **Mutation testing confirmed both fixes were load-bearing** (harness in the
    session scratchpad, run against copies — no tracked file mutated).
    Mutant A (guard degraded to a silent `return 0`): caught **only** by the
    three message assertions — 8/11 otherwise green. Mutant B (guard removed =
    the reported bug): caught by T12b's byte-identity and marker assertions.
    Mutant C (marker check replaced by `true`, i.e. inverted precedence): caught
    **only** by T12d — T12/T12b/T12c all stayed green, confirming T12d is the
    discriminating test and not redundant with T12.
  - T38/T39 negative controls checked on copies: deleting the
    `## Git Operations on Task/Plan Files` heading from `CLAUDE.md` fails T38's
    sentinel half; renaming it in the seed fails T39.
  - Manual end-to-end on a copy of this repo's own `CLAUDE.md`: untouched,
    0 markers, all three messages printed. Positive control 1 (strip the
    sentinel): the block **is** appended. Positive control 2 (perform the exact
    opt-in the message documents): the generated block lands between the markers,
    prose above and below survives, two consecutive runs are idempotent, markers
    stay 1/1 — so the printed instruction actually works.
  - Full suite: `test_agent_instructions.sh` 122/122; all 22 shell suites that
    exercise `aitask_setup.sh` pass; `shellcheck` reports no new findings (every
    reported line is pre-existing and outside the edited region).
  - The working tree carried substantial unrelated dirty state from concurrent
    sessions, so both commits were path-scoped (`git commit -o -- <paths>`)
    rather than staging the index.
- **Key decisions:**
  - **Which contract is real** — user chose the documented hand-maintained
    contract. Tracing settled that this is a *regression*, not a design
    disagreement: t221_3 (`52837495f`) shipped a content-based skip guard on the
    exact same heading, and t130_2 (`3b7de3531`) dropped it while generalizing
    the function to the `>>>aitasks` marker system. The guard restores that
    behavior in a named, tested form.
  - **Guard scoped to `update_claudemd_git_section`, not
    `insert_aitasks_instructions`.** `CLAUDE.md` is the only project-owned
    *mixed-content* surface; the other three are framework-owned files whose
    entire body is the block, where appending is correct bootstrap.
  - **Marker check evaluated before the sentinel check.** A marker-managed block
    necessarily contains the sentinel, so the reverse order would freeze every
    legitimate refresh. T12d exists solely to pin this.
  - **Named constant + drift guard rather than a derived/fuzzy sentinel.** A
    heading-set overlap heuristic needed an arbitrary threshold; one named string
    pinned to the live seed by T39 is reviewable and fails loudly on drift.
  - The guard also generically fixes projects set up **between t221_3 and
    t130_2**, which carry a markerless `## Git Operations on Task/Plan Files`
    section that today's code would append a duplicate marked block on top of.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:1661 — update_claudemd_git_section is called
    only from setup_data_branch Step 8, which early-returns when
    .aitask-data/.git already exists (:1395-1398) and when the user declines the
    data branch (:1438), so CLAUDE.md's block is never refreshed on re-runs and
    never written at all in legacy mode — unlike AGENTS.md, which update_agentsmd
    regenerates unconditionally from setup_code_agents (:2535). Raised during
    planning; the user scoped it out of t1607 and asked for a follow-up, which
    Step 8d creates as t1607_placement_followup.`
