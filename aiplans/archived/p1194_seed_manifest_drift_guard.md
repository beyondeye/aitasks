---
Task: t1194_seed_manifest_drift_guard.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# t1194 — Seed manifest drift guard

## Context

t1185 added `ensure_agent_config_seeds()` to `.aitask-scripts/aitask_setup.sh`
with its own `pairs=()` list of seed→metadata filenames, alongside the
pre-existing `install_seed_*()` family in `install.sh`. The t1185 risk
evaluation flagged this as a code-health risk: two manifests encoding the same
mapping (including the non-identity `claude_settings.local.json` →
`claude_settings.seed.json` rename) drift silently.

Exploration made the invariant sharper than the task statement assumed. The two
manifests are **not** peers over the same set — they are the **two mutually
exclusive delivery paths** for `aitasks/metadata/`:

- `install.sh` runs `rm -rf "$INSTALL_DIR/seed"` (`install.sh:1153`) after all
  `install_seed_*` calls. In a **tarball-installed project** `seed/` no longer
  exists, so every setup-side seed path is dead — `install.sh` is the only
  delivery mechanism.
- In the **framework source tree / clean clone**, `install.sh` never runs.
  Delivery is the union of two setup sites:
  1. the seed-copy block inside `setup_data_branch()`
     (`aitask_setup.sh:1338-1352`), and
  2. `ensure_agent_config_seeds()` (`aitask_setup.sh:1641-1682`, added by t1185).

So the real invariant is: **the metadata set delivered by `install.sh` must
equal the set delivered by the setup path.** A guard scoped only to the four
`ensure_agent_config_seeds` pairs cannot see the direction that actually
matters (`install.sh` gains a seed, `ensure_agent_config_seeds` does not).

A behavioral dry-run of both derivations against a temp fixture confirmed the
current delta is exactly two files:

```
install-only : (none)
setup-only   : code_areas.yaml, doc_update_guide.md
```

Both are generic downstream templates, so tarball-installed projects are
missing them today. `doc_update_guide.md` is load-bearing: the `docs_updated`
gate skill (`.claude/skills/aitask-gate-docs-updated/SKILL.md:51`) resolves
`aitasks/metadata/doc_update_guide.md` and explicitly says "on a fresh install
this is the generic guide the setup flow installed there" — and warns that
`seed/` is gone at runtime. `code_areas.yaml` backs `/aitask-contribute`
(`aitask_contribute.sh:70`).

User decision: fix both gaps in this task so the guard can assert strict set
equality (rather than carrying an allowlist or deferring).

**Rejected alternative — single shared manifest.** Collapsing both sides onto
one manifest file consumed by `install.sh` and `aitask_setup.sh` would make the
guard unnecessary, but `install.sh`'s installers are not uniform copies: they
select per-seed merge strategies (`merge_seed yaml` / `json` / `json-models` /
`text-union`, plain `cp`, and never-overwrite-prose). A shared manifest must
encode a strategy column and rewrite ~330 lines of the bootstrap path — the one
script that must stay standalone and that is hardest to verify in the field.
The behavioral guard gets the drift protection at a fraction of that risk, and
auto-extends to new `install_seed_*` functions without editing the guard.

## Approach

Derive both manifests **behaviorally from live source** — source each script
with its existing `--source-only` guard, run its populate functions against a
throwaway fixture, and snapshot the resulting `aitasks/metadata/` tree. No
hardcoded expected list (which would just become a third manifest to drift).

The install side is derived from the installers `main()` **actually calls**, not
merely from those that exist: the set is
`declare -F | grep '^install_seed_'` **intersected with** names appearing in
`declare -f main`. `declare -f` reproduces the parsed function with comments
stripped, so this is a true call-site check. An installer that exists but was
never wired into `main()` therefore does not contribute to the manifest — which
is exactly right, since a tarball install would not deliver its file either.
A separate assertion reports any unwired installer by name, so "added
`install_seed_foo()`, updated setup parity, forgot the `main()` call" fails
loudly rather than passing silently. Both halves auto-extend with no test edit.

Verified working during planning: both derivations run clean (`rc=0`) and
produce the delta quoted above; the wiring check reports all 16 current
installers as wired.

## Implementation

### 1. `.aitask-scripts/aitask_setup.sh` — extract the data-branch seed block

The metadata-population block at `aitask_setup.sh:1338-1360` is inline inside
`setup_data_branch()` (which does git work), so it is not independently
callable. Extract it into a function taking explicit args, placed near
`ensure_agent_config_seeds()`.

**Structural detail that must be preserved (t1147).** In the current source the
`gates_reference.yaml → gates.yaml` copy (`:1356-1360`) sits **outside** the
`if [[ -d "$project_dir/seed" ]]` guard, precisely because the gate registry is
canonical under `.aitask-scripts/` and ships downstream even when `seed/` is
gone. The extracted function therefore takes the gates-reference path as a
third argument and copies it **before** the seed-dir early return — an
extraction that opened with `[[ -d "$seed_dir" ]] || return 0` and then did the
gates copy inside would silently drop `gates.yaml` on every seedless run.

```bash
# Populate a data-branch metadata dir. Extracted from setup_data_branch so the
# seed→metadata mapping is callable (and testable) on its own —
# tests/test_seed_manifest_drift.sh derives this side of the manifest by
# calling it directly.
populate_data_branch_seed_metadata() {
    local seed_dir="$1" dest_dir="$2" gates_reference="$3"

    # Gate registry is canonical under .aitask-scripts/ and ships downstream
    # even when seed/ is absent — copied independent of the seed guard (t1147).
    if [[ -f "$gates_reference" ]]; then
        cp "$gates_reference" "$dest_dir/gates.yaml" 2>/dev/null || true
    fi

    [[ -d "$seed_dir" ]] || return 0

    cp "$seed_dir/task_types.txt" "$dest_dir/" 2>/dev/null || true
    ... (the existing lines, unchanged, incl. the models_*.json,
         *_instructions.seed.md and profiles/ globs)
    return 0
}
```

Replace the inline block in `setup_data_branch()` with a single call:

```bash
populate_data_branch_seed_metadata \
    "$project_dir/seed" \
    "$project_dir/.aitask-data/aitasks/metadata" \
    "$project_dir/.aitask-scripts/gates_reference.yaml"
```

Preserve the existing `2>/dev/null || true` tolerance on every copy — this runs
under `set -e`. Behavior is unchanged: a pure move with the three paths passed
in, and the seed/gates independence kept intact.

### 2. `install.sh` — close the two delivery gaps

Add two installers alongside the existing family (§`install_seed_*`,
`install.sh:378-709`), following the established shapes:

Both are **install-if-missing / never-overwrite**, following
`install_seed_reviewguides` (`install.sh:518-548`) rather than `merge_seed`:

- `doc_update_guide.md` is prose; there is no merge mode for markdown.
- `code_areas.yaml` is *not* a config file the framework owns. Its seed is 45
  lines of format documentation plus `version: 1` / `areas: []`, and the
  project fills in `areas:` via `aitask_codemap.sh` (which refuses to write
  when the file already exists, `aitask_codemap.sh:102-105`) and
  `/aitask-contribute` (`aitask_contribute.sh:70`). `merge_seed yaml` would
  route an `ait upgrade --force` through `aitask_install_merge.py`, whose yaml
  path ends in `yaml.safe_dump` (`aitask_install_merge.py:72`) — silently
  destroying the user's comment header and hand-formatting to add nothing
  (the seed contributes no keys the dest lacks). Never-overwrite is both safer
  and consistent with the other new installer.

```bash
# --- Install seed code areas map (t1194) ---
# Project-owned content (/aitask-contribute maintains areas:) — never overwrite
# an existing map, even on --force. Mirrors install_seed_reviewguides.
install_seed_code_areas() {
    local src="$INSTALL_DIR/seed/code_areas.yaml"
    local dest="$INSTALL_DIR/aitasks/metadata/code_areas.yaml"
    if [[ ! -f "$src" ]]; then
        warn "No seed/code_areas.yaml in tarball — skipping code areas installation"
        return
    fi
    if [[ -f "$dest" ]]; then
        info "  Code areas map exists (kept): code_areas.yaml"
        return
    fi
    cp "$src" "$dest"
    info "  Installed code areas map: code_areas.yaml"
}

# --- Install generic doc-update guide (t1194) ---
# User-editable prose (the docs_updated gate's default spec) — never overwrite
# an existing guide, even on --force. Mirrors install_seed_reviewguides.
install_seed_doc_update_guide() {
    local src="$INSTALL_DIR/seed/doc_update_guide.md"
    local dest="$INSTALL_DIR/aitasks/metadata/doc_update_guide.md"
    if [[ ! -f "$src" ]]; then
        warn "No seed/doc_update_guide.md in tarball — skipping doc-update guide installation"
        return
    fi
    if [[ -f "$dest" ]]; then
        info "  Doc-update guide exists (kept): doc_update_guide.md"
        return
    fi
    cp "$src" "$dest"
    info "  Installed doc-update guide: doc_update_guide.md"
}
```

Wire both into `main()` next to the other seed installers (`install.sh:1108-1120`
region), each with its `info "Installing …"` line, **before** the
`rm -rf "$INSTALL_DIR/seed"` at `install.sh:1153`. The guard's wiring assertion
(§3) fails if this step is missed.

### 3. `tests/test_seed_manifest_drift.sh` — the guard (new file)

Follows the repo test conventions: `#!/usr/bin/env bash`, `set -euo pipefail`,
sources `tests/lib/asserts.sh`, self-contained `PASS`/`FAIL`/`TOTAL` counters,
`mktemp -d` + `trap` cleanup, PASS/FAIL summary, exits non-zero on failure.
Pattern reference: `tests/test_setup_agent_config_seeds.sh` and
`tests/test_packaging_cleanup.sh` (the `source install.sh --source-only`
precedent).

**Isolation.** `install.sh` and `aitask_setup.sh` both define `info`/`warn`/
`die`/`success`, so each derivation runs in its **own `bash -c` process**
(never both sourced into one shell).

Structure:

- `make_fixture <name>` — temp dir with `seed/` copied whole from the repo,
  `.aitask-scripts/gates_reference.yaml`, and `aitasks/metadata/`.
- `derive_install_manifest <fixture> [probe_fn_src] [probe_wiring]` — in a
  subprocess: `source install.sh --source-only`, set `INSTALL_DIR`,
  `create_data_dirs`, then call only the **wired** installers:
  ```bash
  [[ -n "$probe_fn_src" ]] && eval "$probe_fn_src"
  main_body="$(declare -f main)${probe_wiring}"
  for fn in $(declare -F | awk '{print $3}' | grep '^install_seed_'); do
      grep -qE "(^|[^[:alnum:]_])${fn}([^[:alnum:]_]|$)" <<< "$main_body" || continue
      "$fn"
  done
  ```
  `probe_fn_src` defines *only* a synthetic installer — it must **never**
  redefine `main`, which would clobber the real one and collapse the wired set
  to the probe alone (turning the negative control into a wall of unrelated
  `SETUP_ONLY` lines that proves nothing). The synthetic **call site** is
  supplied separately via `probe_wiring`, a string appended to the real
  `declare -f main` output. That models "real `main()` plus one newly wired
  installer", which is the actual future change being simulated. Verified
  during planning: 17 installers run (16 real + probe), the real manifest is
  unchanged, and the probe file is the sole extra entry.
- `list_unwired_installers` — same subprocess shape, but emits every
  `install_seed_*` **not** referenced in `declare -f main`. Backs the wiring
  assertion.
- `derive_setup_manifest <fixture>` — in a subprocess:
  `source .aitask-scripts/aitask_setup.sh --source-only`, then
  `populate_data_branch_seed_metadata "$fx/seed" "$fx/aitasks/metadata" "$fx/.aitask-scripts/gates_reference.yaml"`
  and (with `SCRIPT_DIR="$fx/.aitask-scripts"`) `ensure_agent_config_seeds`.
- Both snapshot with `find aitasks/metadata -type f | sed 's#^aitasks/metadata/##' | sort`.
  (`find -printf` is GNU-only — BSD/macOS `find` has no such primary — so the
  prefix is stripped with `sed`. Verified byte-identical to the GNU form,
  including the nested `profiles/*.yaml` paths.)
- `compare_manifests <fileA> <fileB>` — the oracle. Prints
  `INSTALL_ONLY:<path>` / `SETUP_ONLY:<path>` lines; returns 0 iff both empty.

Tests:

1. **Oracle unit test (both directions).** Feed `compare_manifests` synthetic
   lists — one with an extra entry on each side — and assert it returns
   non-zero and names the exact entry with the right prefix. Also assert it
   returns 0 on identical lists.
2. **Live parity (the guard itself).** Derive both manifests from real source
   and assert `compare_manifests` reports zero drift. Failure output must print
   the offending filenames and name both edit sites.
3. **Negative control — install-only drift, live surface.** Re-derive the
   install side with `probe_fn_src` defining `install_seed_drift_probe()`
   (copies a fixture-injected `seed/drift_probe.yaml` into metadata) and
   `probe_wiring` supplying its call site, leaving the real `main()` intact.
   Assert the guard reports `INSTALL_ONLY:drift_probe.yaml` — and, to prove
   the real sequence still ran rather than being replaced, assert that this is
   the **only** drift line and that the derived install manifest still contains
   a real seed (e.g. `codex_config.seed.toml`). This simulates exactly the
   future change the guard exists to catch (a new `install_seed_*` wired into
   `main()` with no setup counterpart) and proves the *derivation*, not just
   the comparator, is sensitive.
4. **Negative control — setup-only drift, live surface, zero synthetic code.**
   Inject `seed/probe_instructions.seed.md` into the setup fixture only. The
   real `*_instructions.seed.md` glob in `populate_data_branch_seed_metadata`
   picks it up; `install.sh` has no matching installer. Assert the guard
   reports `SETUP_ONLY:probe_instructions.seed.md`.
5. **Rename pin.** Assert both derived manifests contain
   `claude_settings.seed.json` and neither contains
   `claude_settings.local.json` — the non-identity rename is the specific
   mapping t1185 introduced.
6. **Wiring assertion.** Assert `list_unwired_installers` emits nothing. On
   failure, print each unwired name and the remedy ("define
   `install_seed_<x>()` *and* call it from `main()` before the
   `rm -rf "$INSTALL_DIR/seed"`"). Covers the case a wired-set-derived manifest
   cannot see on its own: an installer added and paired with a setup entry but
   never called.
7. **Wiring assertion negative control.** Feed `list_unwired_installers` a
   `probe_fn_src` defining `install_seed_unwired_probe()` and **no**
   `probe_wiring` (the "defined but never called from `main()`" case); assert
   it is reported by name, and that no real installer is reported alongside it.
8. **Extraction smoke — three cases** (the §1 seed/gates independence is the
   invariant most at risk from the refactor):
   - **8a** `seed_dir` + gates reference both present → seed files *and*
     `gates.yaml` populated.
   - **8b** `seed_dir` absent, gates reference present → `gates.yaml` **is
     still copied** (the t1147 invariant), no seed files appear, return 0.
   - **8c** both absent → clean no-op, return 0, nothing created.

## Verification

```bash
bash tests/test_seed_manifest_drift.sh          # new guard
bash tests/test_setup_agent_config_seeds.sh     # t1185 coverage still passes
bash tests/test_packaging_cleanup.sh            # install.sh --source-only precedent
bash tests/test_install_merge.sh
bash tests/test_install_tarball_download.sh
shellcheck install.sh .aitask-scripts/aitask_setup.sh tests/test_seed_manifest_drift.sh
```

Plus two direct checks:
- derive the install manifest by hand into a scratch fixture and confirm
  `doc_update_guide.md` and `code_areas.yaml` now appear;
- run `populate_data_branch_seed_metadata` with an absent `seed_dir` but a
  present gates reference and confirm `gates.yaml` still lands (t1147
  regression check on the §1 extraction — also test 8b).

Then **Step 9 (Post-Implementation)**: gate run, archival via
`./.aitask-scripts/aitask_archive.sh 1194`.

## Out of scope (recorded as an upstream defect)

`seed/crew_runner_config.yaml` is delivered by **neither** path, yet
`aidocs/agentcrew/agentcrew_architecture.md:245` claims "`ait setup` seeds this
file from `seed/crew_runner_config.yaml`" and
`.aitask-scripts/agentcrew/agentcrew_runner.py:68` reads
`aitasks/metadata/crew_runner_config.yaml`. The guard does not flag it (absent
on both sides ⇒ no drift). To be reported in the plan's Final Implementation
Notes and offered as a Step 8b follow-up.

## Risk

### Code-health risk: medium
- `install.sh` and `setup_data_branch()` are the bootstrap paths; a mistake in
  either surfaces only for downstream users doing a fresh install, where it is
  expensive to diagnose. The changes are shallow (two installers mechanically
  identical to the existing sixteen; one function extraction with explicit
  args) and the new guard exercises both on every run, but automated tests
  cannot run a real end-to-end tarball install. · severity: medium · → mitigation: t1198
- The §1 extraction must preserve the t1147 seed/gates independence — the
  gate-registry copy is deliberately outside the `seed/` guard, and an
  extraction that folded it inside would silently drop `gates.yaml` on every
  seedless run. Structurally addressed (gates path as an explicit third arg,
  copied before the early return) and pinned by test 8b. · severity: medium ·
  → mitigation: TBD (covered in-task)
- The guard's install-side discovery couples the test to the `install_seed_*`
  naming convention. A future seed installer named off that prefix would be
  invisible to both the manifest derivation and the wiring assertion.
  · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The approach was validated during planning by running both derivations for
  real; the delta matched the prediction exactly, so the guard's shape and the
  two install.sh gaps are confirmed rather than assumed. Both required
  acceptance criteria (negative control for drift; existing t1185 test still
  passing) are covered by tests 3/4 and the verification block.
  · severity: low · → mitigation: TBD

### Planned mitigations
- timing: after | name: t1198 (manual_verification_fresh_install_seed_delivery) | type: manual_verification | priority: medium | effort: low | addresses: code-health — bootstrap-path change unverifiable by automated tests | desc: Run install.sh --local-tarball into a scratch project and confirm aitasks/metadata/ receives doc_update_guide.md and code_areas.yaml alongside the pre-existing seeds, then run ait setup in a clean clone and confirm the same set.

## Final Implementation Notes

- **Actual work done:** Implemented as planned, in three parts.
  1. `.aitask-scripts/aitask_setup.sh` — extracted the data-branch metadata
     block out of `setup_data_branch()` into
     `populate_data_branch_seed_metadata(seed_dir, dest_dir, gates_reference)`.
  2. `install.sh` — added `install_seed_code_areas()` and
     `install_seed_doc_update_guide()` (install-if-missing, never overwrite),
     wired into `main()` between `install_seed_reviewguides` and
     `install_seed_codeagent_config`, well before the `rm -rf "$INSTALL_DIR/seed"`.
  3. `tests/test_seed_manifest_drift.sh` — the guard, 28 assertions, all passing.

- **Deviations from plan:** Two, both from review feedback, neither changing the
  design.
  - The snapshot helper originally used `find -printf '%P\n'`, which is
    GNU-only and would fail outright on macOS/BSD. Replaced with
    `find … | sed 's#^aitasks/metadata/##' | sort`, verified byte-identical to
    the GNU form on the real manifest (including nested `profiles/` paths).
    `find -printf` appeared nowhere else in the repo, confirming it was against
    convention.
  - Test 8's single "absent seed_dir is a clean no-op" case was split into 8a /
    8b / 8c during planning after review, because it contradicted the t1147
    gate-registry invariant. 8b is now the explicit pin: seed absent + gate
    reference present must still deliver `gates.yaml`.

- **Issues encountered:**
  - `set -euo pipefail` aborted the run at Test 1: `compare_manifests` returns
    non-zero *by design* (it is the guard's verdict) and the negative controls
    invoke it expecting failure. Relaxed to `set +eu` after the fixture setup,
    matching `tests/test_setup_agent_config_seeds.sh`.
  - The first patch-staging attempt failed with "patch with only garbage"
    because the repo renders diffs with `i/`…`w/` mnemonic prefixes; regenerated
    with `--src-prefix=a/ --dst-prefix=b/`.

- **Key decisions:**
  - **Guard scope = full install-vs-setup parity, not the four t1185 pairs.**
    Exploration showed the two sides are not peers over one set but the two
    mutually exclusive delivery paths for `aitasks/metadata/` (install.sh
    deletes `seed/`; the setup paths need it). A four-pair check cannot see the
    direction that matters — install.sh gains a seed and the setup side does
    not.
  - **Derive the install side from the installers `main()` actually calls**
    (`declare -F` ∩ `declare -f main`), not merely from those that exist, plus a
    standalone wiring assertion. An installer defined but never wired would
    otherwise pass the guard while a real tarball install skipped the file.
  - **Closed the two live gaps rather than allowlisting them.** `install.sh`
    was not delivering `doc_update_guide.md` (which the `docs_updated` gate
    resolves at runtime, after `seed/` is gone) or `code_areas.yaml`. An
    allowlist would have been a third manifest to drift.
  - **Never-overwrite over `merge_seed yaml` for `code_areas.yaml`.** A yaml
    merge routes `--force` through `aitask_install_merge.py`'s `yaml.safe_dump`,
    destroying the seed's 45-line format header while contributing no keys the
    destination lacks.
  - **Kept the duplication and guarded it** rather than collapsing both sides
    onto one shared manifest: install.sh's installers select per-seed merge
    strategies and must stay standalone for bootstrap.

- **Attribution proof:** re-running the derivation against
  `git show HEAD:install.sh` reports exactly `SETUP_ONLY:code_areas.yaml` and
  `SETUP_ONLY:doc_update_guide.md`, confirming the guard genuinely fails
  pre-fix and that Test 2's pass is attributable to the change rather than to a
  vacuous comparison.

- **Known limitation (follow-up):** the wiring assertion accepts an
  `install_seed_*` call anywhere in `main()`, including *after* the
  `rm -rf "$INSTALL_DIR/seed"` cleanup. Such an installer would pass the guard
  (the test fixture still has `seed/`) while a real tarball install delivered
  nothing. `declare -f main` renders the cleanup verbatim as
  `rm -rf "$INSTALL_DIR/seed";`, so truncating `main_body` at that line is a
  small change. Dispositioned as a follow-up task at review time, not folded in
  here.

- **Concurrency note:** a parallel session held uncommitted work in `install.sh`
  (`ensure_data_root()` + a rewritten `create_data_dirs()`) plus untracked
  `tests/test_install_create_data_dirs.sh` and chat/chatlink files. Only this
  task's two `install.sh` hunks were staged, via a filtered patch applied with
  `git apply --cached`; the staged blob was verified to contain no
  `ensure_data_root` and to pass `bash -n`. `test_install_create_data_dirs.sh`
  fails at `T9b` on that session's in-flight code (it asserts a "Cannot replace
  dangling symlink" diagnostic their `install.sh` does not yet emit) — unrelated
  to this task and left alone.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:1340-1352 — seed/crew_runner_config.yaml is delivered by neither install.sh nor the setup path, yet aidocs/agentcrew/agentcrew_architecture.md:245 states "ait setup seeds this file from seed/crew_runner_config.yaml" and .aitask-scripts/agentcrew/agentcrew_runner.py:68 reads aitasks/metadata/crew_runner_config.yaml. The drift guard cannot flag it (absent on both sides means no drift), so it needs its own fix.`
