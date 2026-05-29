---
Task: t852_fix_add_model_default_agent_string_target.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

# Plan: Fix add-model `promote-default-agent-string` for relocated `DEFAULT_AGENT_STRING` (t852)

## Context

The `aitask-add-model` skill's **promote mode** is broken. Its helper
`.aitask-scripts/aitask_add_model.sh`, subcommand `promote-default-agent-string`,
patches `DEFAULT_AGENT_STRING` in `.aitask-scripts/aitask_codeagent.sh`
(`src_rel` at line 239, sed/grep at 249–259). But that variable was since
**extracted into `.aitask-scripts/lib/agent_string.sh:26`** —
`aitask_codeagent.sh` now only *sources* it (lines 17–18) and no longer
contains a `DEFAULT_AGENT_STRING="..."` line. So the post-write grep check at
line 252 fails and the subcommand `die`s with "anchor pattern did not match".

This blocks promoting **any** new model (including the upcoming Opus 4.8,
t853) to the framework default. It must be fixed first.

A second wrinkle: the form in `lib/agent_string.sh` is a parameter-expansion
default —

```bash
DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_7_1m}"
```

— so the old sed `s|^DEFAULT_AGENT_STRING="\.\*"|...|` (greedy `.*"`) would
collapse it to a bare `DEFAULT_AGENT_STRING="claudecode/opus4_8"`, destroying
the caller-override capability documented at `agent_string.sh:24`
(`caller may pre-set any of these to override`). The replacement must
**preserve** the `${DEFAULT_AGENT_STRING:-<value>}` shape.

Meanwhile the resolution-chain help note `4. Hardcoded default: ...` *does*
still live in `aitask_codeagent.sh` (line 540). So after the fix the
subcommand patches **two files**: the variable in `lib/agent_string.sh` and
the note in `aitask_codeagent.sh`.

## Files to modify

1. `.aitask-scripts/aitask_add_model.sh` — rewrite `cmd_promote_default_agent_string` (lines ~219–272).
2. `tests/test_add_model.sh` — fixture + Test 4 + Test 5 dry-run assertion.
3. `.claude/skills/aitask-add-model/SKILL.md` — references to which file holds the var.
4. `aidocs/model_reference_locations.md` — section 3 ("Hardcoded source-code defaults").

## Step 1 — `aitask_add_model.sh::cmd_promote_default_agent_string`

Replace the single-file body (current lines 239–271) with a two-file patch.
Keep the arg parsing, `validate_*`, and the `claudecode`-only guard as-is.

```bash
    local new_value="${agent}/${name}"

    # DEFAULT_AGENT_STRING lives in lib/agent_string.sh as a parameter-expansion
    # default: DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-<value>}". The
    # resolution-chain help note still lives in aitask_codeagent.sh.
    local lib_rel=".aitask-scripts/lib/agent_string.sh"
    local note_rel=".aitask-scripts/aitask_codeagent.sh"
    local lib_file="$REPO_ROOT/$lib_rel"
    local note_file="$REPO_ROOT/$note_rel"
    [[ -f "$lib_file" ]]  || die "Source file not found: $lib_rel"
    [[ -f "$note_file" ]] || die "Source file not found: $note_rel"

    # --- Patch 1: DEFAULT_AGENT_STRING in lib/agent_string.sh ---
    local tmp_lib
    tmp_lib=$(mktemp "${TMPDIR:-/tmp}/aitask_add_model_lib_XXXXXX.sh")
    cp "$lib_file" "$tmp_lib"
    sed_inplace "s|^DEFAULT_AGENT_STRING=\"\${DEFAULT_AGENT_STRING:-.*}\"|DEFAULT_AGENT_STRING=\"\${DEFAULT_AGENT_STRING:-${new_value}}\"|" "$tmp_lib"
    if ! grep -q "^DEFAULT_AGENT_STRING=\"\${DEFAULT_AGENT_STRING:-${new_value}}\"\$" "$tmp_lib"; then
        rm -f "$tmp_lib"
        die "Failed to update DEFAULT_AGENT_STRING in $lib_rel (anchor pattern did not match)"
    fi

    # --- Patch 2: resolution-chain note in aitask_codeagent.sh ---
    local tmp_note
    tmp_note=$(mktemp "${TMPDIR:-/tmp}/aitask_add_model_note_XXXXXX.sh")
    cp "$note_file" "$tmp_note"
    sed_inplace "s|^\(  4\. Hardcoded default: \).*|\1${new_value}|" "$tmp_note"
    if ! grep -q "^  4\. Hardcoded default: ${new_value}\$" "$tmp_note"; then
        rm -f "$tmp_lib" "$tmp_note"
        die "Failed to update resolution-chain note in $note_rel (anchor pattern did not match)"
    fi

    if $dry_run; then
        print_diff "$lib_rel" "$tmp_lib"
        print_diff "$note_rel" "$tmp_note"
        rm -f "$tmp_lib" "$tmp_note"
        return 0
    fi

    # Preserve each file's mode (executable bit) by rewriting content in place
    # rather than mv-ing a non-executable tempfile over it.
    cat "$tmp_lib"  > "$lib_file"
    cat "$tmp_note" > "$note_file"
    rm -f "$tmp_lib" "$tmp_note"
    info "Updated DEFAULT_AGENT_STRING to $new_value in $lib_rel (resolution-chain note in $note_rel)"
```

Notes:
- sed delimiter `|` keeps the `/` in `new_value` clean.
- `\$` inside the double-quoted grep string is a literal `$` end-anchor; the
  `$` before `{DEFAULT_AGENT_STRING:-` is mid-pattern → literal in BRE.
- `print_diff` (lines 59–67) already takes `(rel_path, tmpfile)` and diffs the
  on-disk file vs tmp; calling it twice emits both diff blocks. CWD is repo
  root under `ait`, matching its `[[ -f "$file" ]]` on the relative path.
- `print_diff` for `lib/agent_string.sh` will now appear in dry-run output —
  this changes the dry-run surface (see Test 5).

## Step 2 — `tests/test_add_model.sh`

**Fixture (`setup_fixture`, lines ~114–131):** the stub writes
`DEFAULT_AGENT_STRING="claudecode/opus4_6"` into the `aitask_codeagent.sh`
stub. Split it:
- Add a `lib/` dir and stub `.aitask-scripts/lib/agent_string.sh` containing
  the parameter-expansion line:
  `DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_6}"`
  (chmod +x it too, to keep the executable-bit assertion meaningful).
- Remove the bare `DEFAULT_AGENT_STRING=...` line from the `aitask_codeagent.sh`
  stub; keep the `  4. Hardcoded default: claudecode/opus4_6` note line there.
- `mkdir -p "$FIXTURE_DIR/.aitask-scripts/lib"` before writing the lib stub.

**Test 4 (lines ~184–205):**
- `line21` grep target → the lib stub; assert the preserved form:
  `assert_eq "DEFAULT_AGENT_STRING updated" 'DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_7}"' "$line21"`
  (grep the lib file: `grep '^DEFAULT_AGENT_STRING=' "$lib"`).
- `resolution_line` grep stays on the `aitask_codeagent.sh` stub (note line).
- Executable-bit check: assert on **both** patched files (lib + codeagent), or
  retarget to the lib file. Keep both meaningful.
- Update the `echo "=== Test 4 ..."` header text (drops the stale "lines 21 & 663").

**Test 5 (dry3, lines ~221–223):** now expect **two** diff headers:
- `assert_contains "...emits lib diff" "+++ b/.aitask-scripts/lib/agent_string.sh" "$dry3"`
- `assert_contains "...emits note diff" "+++ b/.aitask-scripts/aitask_codeagent.sh" "$dry3"`

The md5 "filesystem unchanged after dry-run" check (line 225) still holds since
dry-run writes nothing.

## Step 3 — `.claude/skills/aitask-add-model/SKILL.md`

Update wording that says the variable lives in `aitask_codeagent.sh`:
- Header blurb ("Promote mode … update `DEFAULT_AGENT_STRING` in
  `.aitask-scripts/aitask_codeagent.sh`") → point at `lib/agent_string.sh`
  (note the resolution-chain note still lives in `aitask_codeagent.sh`).
- Step 3 dry-run / Step 4 apply comments and Step 6 commit group
  (`git add .aitask-scripts/aitask_codeagent.sh`) → the variable patch now
  touches `lib/agent_string.sh`; the same subcommand may also touch
  `aitask_codeagent.sh` for the note, so the commit group should `git add`
  **both** files when they change.
- The Notes line "`promote-default-agent-string` is `claudecode`-only because
  only `.aitask-scripts/aitask_codeagent.sh` hardcodes a default fallback" →
  correct the file name to `lib/agent_string.sh`.

## Step 4 — `aidocs/model_reference_locations.md`

Section 3 "Hardcoded source-code defaults" lists
`.aitask-scripts/aitask_codeagent.sh | 21 | DEFAULT_AGENT_STRING=... | needed_for_promote`.
Update that row to `.aitask-scripts/lib/agent_string.sh:26` (parameter-expansion
form). Keep a row noting the resolution-chain help note (`4. Hardcoded default:`)
still lives in `aitask_codeagent.sh`. (This file is an aidocs audit, not a
runtime skill closure — edit in place; no goldens.)

## Out of scope / hand-offs

- No `.md.j2`/closure edits here → no golden regeneration, no
  `aitask_skill_verify.sh` requirement for this task. (SKILL.md for add-model
  is a plain skill, not templated.)
- Per CLAUDE.md "skill changes in Claude Code first": if the add-model guidance
  is mirrored in Codex/OpenCode trees, suggest a follow-up to port the
  file-name correction. (Verify during impl whether add-model exists in those
  trees; add-model may be Claude-only.)
- Opus 4.8 add+promote = t853; stale user-facing docs/tests = t854.

## Verification

```bash
shellcheck .aitask-scripts/aitask_add_model.sh
bash tests/test_add_model.sh          # all groups PASS, incl. Test 4 & 5
# real-tree dry-run no longer dies, emits two diffs:
./.aitask-scripts/aitask_add_model.sh promote-default-agent-string --dry-run \
  --agent claudecode --name opus4_7_1m
```
Confirm the dry-run diff shows `lib/agent_string.sh` keeping the
`${DEFAULT_AGENT_STRING:-claudecode/opus4_7_1m}` form (no-op replacement) and
the `aitask_codeagent.sh` note unchanged — i.e. it exits 0 instead of dying.

## Step 9 reference

After approval + implementation, follow task-workflow **Step 8** (review →
commit; framework code committed via plain `git` on `main`, no `aitasks/`
files in the code commit) and **Step 9** (archival via
`./.aitask-scripts/aitask_archive.sh 852`, then `./ait git push`).

## Final Implementation Notes

- **Actual work done:** Exactly as planned. Rewrote
  `cmd_promote_default_agent_string` in `aitask_add_model.sh` to patch two
  files — `DEFAULT_AGENT_STRING` in `lib/agent_string.sh` (preserving the
  `${DEFAULT_AGENT_STRING:-<value>}` parameter-expansion shape) and the
  resolution-chain note in `aitask_codeagent.sh`. Updated the top-of-file
  subcommand comment, `tests/test_add_model.sh` (fixture splits a
  `lib/agent_string.sh` stub out of the codeagent stub; Test 4 asserts the
  preserved shape + exec-bit on both files; Test 5 expects two dry-run diff
  headers), `aitask-add-model/SKILL.md` (4 sites), and
  `aidocs/model_reference_locations.md` section 3.
- **Deviations from plan:** None.
- **Issues encountered:** None. Verified `shellcheck` clean, `bash
  tests/test_add_model.sh` → 31/31 pass, and the real-tree dry-run that
  previously died now exits 0 emitting both file diffs with the override
  shape intact.
- **Key decisions:** Kept the resolution-chain note patch targeting
  `aitask_codeagent.sh` (the note genuinely still lives there) rather than
  moving it — the subcommand legitimately spans two files now.
- **Upstream defects identified:** None. (The original anchor-mismatch bug
  *is* this task's subject, not a separate pre-existing defect in another
  module.)
- **Cross-agent port follow-up (NOT an upstream defect):** The same stale
  guidance exists in the mirrored add-model skills at
  `.agents/skills/aitask-add-model/SKILL.md` (Codex),
  `.opencode/skills/aitask-add-model/SKILL.md`, and
  `.opencode/commands/aitask-add-model.md`. Per CLAUDE.md, skill changes land
  in the Claude Code version first; a separate task should port the
  `lib/agent_string.sh` correction to those trees. Suggested at Step 8b.
