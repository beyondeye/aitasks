---
Task: t1684_add_model_preserve_destination_file_mode.md
Branch: main
Base branch: main
Output branch: main
---

# t1684 — `aitask_add_model.sh` must preserve each destination's file mode

## Context

`aitask_add_model.sh` writes every file it touches by building content in a
`mktemp` file under `$TMPDIR` and `mv`-ing it over the destination. `mktemp`
creates `0600`, and the rename hands that mode to the destination. Git tracks
only the executable bit, so the narrowing is invisible in `git diff`,
`git status`, and every review — the residue just accumulates in each local
checkout.

Confirmed empirically against an isolated fixture (pre-fix behavior):

```
BEFORE: 644 aitasks/metadata/{models_claudecode,codeagent_config}.json
        600 seed/{models_claudecode,codeagent_config}.json
AFTER:  600 aitasks/metadata/{models_claudecode,codeagent_config}.json
        600 seed/{models_claudecode,codeagent_config}.json
```

Both directions matter: a hardcoded `chmod 644` would be just as wrong, because
it would *widen* a destination that was deliberately narrow. The fix must
preserve **each destination's own pre-existing mode**.

Two corrections to the task's premise, both verified:

- `cmd_promote_default_agent_string` does **not** use the tempfile-`mv` pattern.
  It already writes `cat "$tmp" > "$file"`, which preserves the mode but
  truncates the destination before writing a byte — the reader-visible window
  `lib/atomic_write.sh` exists to close. It is in scope for the same reason,
  via the same fix.
- Three files in this checkout are already at `0600`, not two:
  `seed/models_claudecode.json`, `seed/codeagent_config.json`, **and**
  `aitasks/metadata/codeagent_config.json`.

**Symlinks are not incidental here.** `aitasks` is itself a directory symlink
(`aitasks -> .aitask-data/aitasks`), and the three write paths do not agree on
file-symlink semantics today: `mv` **replaces** a symlinked destination,
orphaning the backing file, whereas `cat > "$dest"` **follows** it. So
`promote-default-agent-string` currently preserves links and must not regress,
while the two `mv` paths currently destroy them. `ait_atomic_resolve`
(`lib/atomic_write.sh:71`) walks the file-symlink chain and renames onto the
*resolved* path, which unifies all three on the follow-the-link behavior — an
improvement on the `mv` paths and a no-regression requirement on the `cat >`
one. That is a real behavior change on two subcommands, so it is pinned by a
test rather than asserted (post-phase 3).

The repo already has the canonical seam for exactly this. `aidocs/framework/shell_conventions.md:42`
mandates it in so many words — *"Replacing a file in place: use
`lib/atomic_write.sh`, never `> "$file"` or a `mv` from `$TMPDIR`"* — and
`ait_atomic_tmp` (`.aitask-scripts/lib/atomic_write.sh:117`) chmods its staging
temp to `ait_file_mode "$dest"` before the rename. So this is not a new
mechanism: it is bringing the last hold-out call sites onto the existing one.
`atomic_write.sh` is already in the `tests/lib/test_scaffold.sh` baseline, so no
scaffold change is owed.

## Implementation

### Pre-phase (risk mitigations)

1. `[negative_control_pre_fix]` **Write Test 7 (spec in step 4) first, and run
   it against the unchanged helper**, before editing
   `.aitask-scripts/aitask_add_model.sh` at all. `bash tests/test_add_model.sh`
   MUST report Test 7 **failing**, with
   `aitasks/metadata/models_claudecode.json` and
   `aitasks/metadata/codeagent_config.json` coming back `600` against a `644`
   baseline. Record that output. If Test 7 passes here, the fixture is not
   discriminating and would pass just as vacuously after the fix — fix the
   fixture before writing any production change. The same command must pass
   once the fix lands (Verification 2); that before/after pair *is* the
   negative control, so no copy of the helper is made (a copy would `die` on
   its relative `lib/terminal_compat.sh` source anyway).
2. `[negative_control_pre_fix]` Capture the **real** repo baseline —
   `stat -c '%a %n'` over the six paths named in Verification 5 — into
   `<scratchpad>/real_modes_before.txt`. Nothing in this task may change them;
   that file is what Verification 5 compares against.

### 1. Source the seam — `.aitask-scripts/aitask_add_model.sh:20-22`

After the existing `terminal_compat.sh` source, matching the repo idiom
(`aitask_gate_pass.sh:30-31`, `aitask_projects.sh:44-45`):

```bash
# shellcheck source=lib/atomic_write.sh
source "$SCRIPT_DIR/lib/atomic_write.sh"
```

### 2. Add one `commit_staged` helper next to `print_diff` (~line 70)

The `$TMPDIR` staging temps stay — they are also the `--dry-run` diff inputs,
and the "validate **both** files, then write **both**" ordering depends on
them. What changes is that they are now only ever *read*:

```bash
# Install validated staged content onto its destination, preserving the
# destination's own current mode.
#
# The staging temps live in $TMPDIR and must NOT be `mv`d into place: mktemp
# creates 0600 and the rename hands that mode to the destination, silently
# narrowing files whose read bits git does not track (t1684). A `mv` from
# $TMPDIR also degrades into a non-atomic copy across filesystems, and a `mv`
# REPLACES a symlinked destination instead of writing through it.
#
# ait_atomic_render stages a temp beside the *resolved* destination, chmods it
# to that destination's current mode, and renames it in — so a symlinked
# destination keeps its link and its backing file is the one updated, matching
# what the `cat > "$dest"` in promote-default-agent-string already did.
#
# `cat "$src"` is a single-command renderer, so its status IS the renderer's
# status and ait_atomic_render tests it — the "guard every fallible command"
# rule at the top of lib/atomic_write.sh needs no extra `|| return 1` here.
commit_staged() {
    local src="$1" dest="$2"
    ait_atomic_render "$dest" cat "$src"
}
```

### 3. Replace the three commit blocks

Every call is guarded: `ait_atomic_render` runs with `errexit` disabled inside,
so an unguarded call would continue silently past a failed write.

`cmd_add_json` (currently `:145-146`):

```bash
    commit_staged "$tmp_metadata" "$metadata_file" \
        || { rm -f "$tmp_metadata" "$tmp_seed"; die "Failed to write $metadata_rel"; }
    if [[ -n "$tmp_seed" ]]; then
        commit_staged "$tmp_seed" "$seed_file" \
            || { rm -f "$tmp_seed"; die "Failed to write $seed_rel"; }
    fi
    rm -f "$tmp_metadata" "$tmp_seed"
```

`cmd_promote_config` (currently `:215-216`): identical shape.

`cmd_promote_default_agent_string` (currently `:281-284`): replace the
`cat "$tmp" > "$file"` pair with two guarded `commit_staged` calls and rewrite
the stale comment above them — the mode was already preserved there; what this
buys is atomic visibility and symlink safety.

Note `info` in `cmd_add_json` still reads `${tmp_seed:+ …}` after the `rm -f`;
removing the file does not clear the variable, so that line is unaffected.

### 4. New Test 7 in `tests/test_add_model.sh`

A portable mode reader beside the fixture helpers (the `ait_file_mode` idiom —
GNU `stat -c`, BSD `stat -f`):

```bash
file_mode() { stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null || true; }
```

Then `Test 7: writes preserve each destination's own mode (both directions)`:

1. `setup_fixture`, then pin a deliberate mode split so **both** drift
   directions are discriminating — `mv`-from-mktemp narrows the `644`
   destinations, and a hardcoded `chmod 644` would widen the `600` ones. Only
   true per-file preservation passes both:

   | file | mode |
   |---|---|
   | `aitasks/metadata/models_claudecode.json` | 644 |
   | `seed/models_claudecode.json` | 600 |
   | `aitasks/metadata/codeagent_config.json` | 644 |
   | `seed/codeagent_config.json` | 600 |
   | `.aitask-scripts/lib/agent_string.sh` | 640 |
   | `.aitask-scripts/aitask_codeagent.sh` | 755 |

2. Record each mode, run all three subcommands (`add-json`, `promote-config`,
   `promote-default-agent-string`) against the fixture.
3. **Assert the writes actually landed** before trusting the mode assertions —
   otherwise a subcommand that silently no-ops would satisfy them vacuously:
   `.models | length == 2`, `.defaults.pick == claudecode/opus4_7`, and the
   patched `DEFAULT_AGENT_STRING` line.
4. `assert_eq` the mode of each of the six files against its recorded baseline.

Existing tests 1–6 are untouched: they read content, and Test 5's checksum is
`cat`-based, so neither sees modes.

### 5. The three `0600` files: decided — **do not normalize**

The task asks for an explicit decision on `seed/models_claudecode.json`,
`seed/codeagent_config.json` and `aitasks/metadata/codeagent_config.json`.

**Decision: leave them exactly as they are.** `git ls-files -s` reports
`100644` for all three, but git's mode word records only the *executable* bit —
it says nothing about read bits, so it cannot establish that the current `0600`
is accumulated residue rather than a deliberate local restriction. Forcing them
to `644` would be an unreviewable permission widening that no diff can show,
and it would contradict the exact rule this task installs: preserve each
destination's own pre-existing mode, never impose one. Once the helper stops
rewriting modes, whatever these files are is stable and under the owner's
control — which is the actual fix.

No `chmod` is run against the repo. The real paths are instead *verified*
unchanged (Verification 5).

### Post-phase (risk mitigations)

1. `[assert_no_staged_temp_leak]` After a successful Test 7 run, assert the
   fixture's `aitasks/metadata/`, `seed/` and `.aitask-scripts/lib/` contain no
   leftover dot-prefixed staging temps (`.<basename>.XXXXXX`) — add this as an
   assertion inside Test 7 so it is enforced on every future run, not just once.
   Then confirm `git status --short` lists no such file under the real repo's
   `aitasks/metadata/` or `seed/`.
2. `[assert_symlink_semantics]` Add `Test 8: writes follow a symlinked
   destination instead of replacing it` to `tests/test_add_model.sh`. After
   `setup_fixture`, create `$FIXTURE_DIR/real/`, move two destinations into it
   and leave **relative** symlinks behind (relative so
   `ait_atomic_resolve`'s non-absolute branch is the one exercised):
   - `aitasks/metadata/models_claudecode.json` → `../../real/models_claudecode.json`
     — an `mv` path, where today's behavior destroys the link;
   - `.aitask-scripts/lib/agent_string.sh` → `../../real/agent_string.sh`
     — the `cat >` path, where preserving the link is a **no-regression**
     requirement.

   `chmod 640` the first backing file and `600` the second, then run `add-json`
   and `promote-default-agent-string` and assert, for each:
   1. the destination is **still a symlink** (`[[ -L … ]]`);
   2. `readlink` returns the original relative target, unchanged;
   3. the **backing file** in `real/` received the update (`.models | length`
      is 2; the patched `DEFAULT_AGENT_STRING` line) — proving the write went
      *through* the link, not merely that the link survived;
   4. the backing file's own mode is unchanged (`640` / `600`) — mode
      preservation must read the resolved path, not the link;
   5. `real/` holds no leftover dot-prefixed staging temp.

## Verification

1. Negative control — `bash tests/test_add_model.sh` run **before** the script
   is edited (pre-phase step 1): Test 7 must FAIL, with the `644` destinations
   reported as `600`.
2. `bash tests/test_add_model.sh` → all eight test groups pass, `0 failed`.
3. `shellcheck .aitask-scripts/aitask_add_model.sh` → clean, plus a manual
   `grep -n 'commit_staged ' .aitask-scripts/aitask_add_model.sh` read-through
   confirming each of the six call sites carries a `|| { … die … }` guard
   (`ait_atomic_render` disables `errexit` inside, so an unguarded call would
   continue past a failed write). A review check, not a test — a source-shape
   assertion here would be brittle and would not prove the guard's effect.
4. Fixture probe reproducing the Context table: `644` destinations stay `644`,
   `600` destinations stay `600`.
5. **Real paths verified against their own recorded pre-run modes, not against
   `644`.** Capture `stat -c '%a %n'` for the six real repo paths *before* any
   edit (alongside the pre-phase snapshot) and re-run it at the end: every mode
   must be byte-identical to its own baseline. This proves the work changed no
   permission on the real checkout — including the three `0600` files, which
   must still read `600`.
6. `git status --short` and `git diff --stat` show only the two edited files
   (`aitask_add_model.sh`, `test_add_model.sh`) — no leaked staging temp.

Step 9 (Post-Implementation) handles archival and the merge back to `main`.

## Risk

### Code-health risk: medium
- Routing the two `mv` call sites through `ait_atomic_render` **changes
  file-symlink semantics**: `mv` replaces a symlinked destination, the seam
  writes through it. That is the better behavior, but it is a real behavior
  change on two of three subcommands, and on the `cat >` path it is instead a
  regression risk — a resolve that failed to follow the link would replace a
  user-managed symlink and strand its backing file, while every mode assertion
  still passed · severity: medium ·
  → mitigation: inline post-phase assert_symlink_semantics
- `ait_atomic_render` runs with `errexit` disabled inside, so a call site left
  unguarded would continue silently past a failed write, leaving the
  destination stale while the command reports success · severity: medium ·
  → mitigation: none — six call sites in one commit, covered by shellcheck and
  the Verification 3 call-site read-through
- Staging moves from `$TMPDIR` into the destination's own directory, i.e. inside
  the repo tree; a leaked temp would surface as an untracked
  `.models_claudecode.json.XXXXXX` in `aitasks/metadata/` or `seed/` ·
  severity: low · → mitigation: inline post-phase assert_no_staged_temp_leak

### Goal-achievement risk: low
- The new mode test can pass vacuously — if the fixture baseline coincides with
  what the buggy code produces (`0600`), or if a subcommand silently no-ops, the
  assertions hold without proving anything · severity: medium ·
  → mitigation: inline pre-phase negative_control_pre_fix

### Planned mitigations
- timing: pre-phase | name: negative_control_pre_fix | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — Test 7 passing vacuously | desc: write Test 7 first and run it against the unchanged helper, requiring it to fail with the 644 destinations coming back 600; require the same run to pass after the fix
- timing: post-phase | name: assert_no_staged_temp_leak | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — staging temp leaked inside the repo tree | desc: assert no dot-prefixed staging temps remain in the fixture dirs (as a Test 7 assertion) or in the real repo's git status
- timing: post-phase | name: assert_symlink_semantics | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — mv→resolve changes file-symlink behavior on two paths and must not regress the third | desc: Test 8 pins that a symlinked destination stays a link, keeps its target, and has its backing file updated and its backing mode preserved, on both an mv path and the cat-> path

**Post-inline reassessment:** the three inline phases add only verification
steps — no production-code surface, no new dependency, no reordering of the main
steps. Goal-achievement stands at **low**. Code-health is **medium**, not
because of the inline phases but because the symlink-semantics change was
surfaced during review; `assert_symlink_semantics` is what keeps it bounded.
