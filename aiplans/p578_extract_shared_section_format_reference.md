---
Task: t578_extract_shared_section_format_reference.md
Base branch: main
plan_verified: []
---

## Context

The section format reference block (HTML comment section markers syntax) is duplicated across three brainstorm agent templates: explorer.md, synthesizer.md, and detailer.md (introduced in t571_2). The detailer already drifted ("plan" vs "proposal"). This refactoring extracts the block into a shared file and adds a general-purpose template include mechanism to `ait crew addwork`, making it available to **all** crews — not just brainstorm.

## Approach

Add `<!-- include: filename -->` directive support at the `ait crew addwork` level. When `addwork` reads a `--work2do` file, it resolves include directives before writing to `_work2do.md`. The resolver lives in `agentcrew_utils.sh` (shared crew library). This is a one-level (non-recursive) resolution — simple, predictable, sufficient.

## Steps

### 1. Add `resolve_template_includes()` to `agentcrew_utils.sh`

Location: `.aitask-scripts/lib/agentcrew_utils.sh`, after the existing `write_yaml_file()` function (line ~138).

```bash
# resolve_template_includes <base_dir>
# Reads template content from stdin, writes resolved content to stdout.
# Resolves <!-- include: filename --> directives relative to base_dir.
# One-level only (included files are not scanned for further includes).
# Missing includes emit a warning and preserve the directive line as-is.
resolve_template_includes() {
    local base_dir="$1"
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ \<\!--[[:space:]]+include:[[:space:]]+([^[:space:]]+)[[:space:]]+--\> ]]; then
            local inc_file="$base_dir/${BASH_REMATCH[1]}"
            if [[ -f "$inc_file" ]]; then
                cat "$inc_file"
            else
                warn "Template include not found: $inc_file"
                printf '%s\n' "$line"
            fi
        else
            printf '%s\n' "$line"
        fi
    done
}
```

### 2. Integrate resolver into `aitask_crew_addwork.sh`

After line 155 (end of "Read work2do content" block), add:

```bash
# --- Resolve template includes ---
if [[ "$WORK2DO_FILE" != "-" && "$WORK2DO_FILE" != "/dev/null" && -n "$WORK2DO_CONTENT" ]]; then
    WORK2DO_DIR="$(cd "$(dirname "$WORK2DO_FILE")" && pwd)"
    WORK2DO_CONTENT="$(printf '%s\n' "$WORK2DO_CONTENT" | resolve_template_includes "$WORK2DO_DIR")"
fi
```

Only resolves includes for file-based input (not stdin or /dev/null), since directory context is needed.

### 3. Update `ait crew addwork --help`

Add to the help text after the `--work2do` line:

```
Template includes:
  Work2do files may contain <!-- include: filename --> directives.
  These are resolved relative to the work2do file's directory before
  the content is written to the agent's _work2do.md file.
  Includes are one-level only (included files are not scanned for
  further includes). Missing files emit a warning and keep the
  directive line as-is.
```

### 4. Create shared partial: `.aitask-scripts/brainstorm/templates/_section_format.md`

```markdown
### Section Format
Wrap each major section of your output in structured section markers using HTML comments:
  Opening: `<!-- section: name [dimensions: dim1, dim2] -->`
  Closing: `<!-- /section: name -->`
Dimensions reference the dimension keys from the "Dimension Keys" block in your input (if present).
Section names must be lowercase_snake_case.
```

Uses "output" as generic term (instead of "proposal"/"plan") since all agents write to `_output.md`.

### 5. Replace duplicated blocks in three templates

Replace the 6-line `### Section Format ... Section names must be lowercase_snake_case.` block with a single include directive in each:

- **`explorer.md`** (lines 22–27) → `<!-- include: _section_format.md -->`
- **`synthesizer.md`** (lines 20–25) → `<!-- include: _section_format.md -->`
- **`detailer.md`** (lines 21–26) → `<!-- include: _section_format.md -->`

### 6. Create test: `tests/test_crew_template_includes.sh`

Follow the existing pattern from `test_crew_init.sh` (setup_test_repo, assert helpers, cleanup).

**Test cases:**
1. **Basic include**: Template with `<!-- include: _partial.md -->` resolves to partial content in `_work2do.md`
2. **Multiple includes**: Template with two include directives resolves both
3. **No includes**: Template without includes passes through unchanged
4. **Missing include file**: Emits warning to stderr, preserves directive line in output
5. **Stdin input skips resolution**: `--work2do -` (stdin) does not attempt include resolution
6. **Brainstorm integration**: Template that mirrors the actual `_section_format.md` usage resolves correctly

### 7. Verify brainstorm templates still work

Run existing tests:
```bash
python3 -m unittest discover -s tests -p 'test_brainstorm_*.py'
```

Manual verification: run `resolve_template_includes` on each template and confirm the section format block appears in the output.

## Files Modified

| File | Action |
|------|--------|
| `.aitask-scripts/lib/agentcrew_utils.sh` | Add `resolve_template_includes()` function |
| `.aitask-scripts/aitask_crew_addwork.sh` | Call resolver after reading content; update help text |
| `.aitask-scripts/brainstorm/templates/_section_format.md` | CREATE — shared section format reference |
| `.aitask-scripts/brainstorm/templates/explorer.md` | Replace 6-line block → 1 include directive |
| `.aitask-scripts/brainstorm/templates/synthesizer.md` | Replace 6-line block → 1 include directive |
| `.aitask-scripts/brainstorm/templates/detailer.md` | Replace 6-line block → 1 include directive |
| `tests/test_crew_template_includes.sh` | CREATE — test suite for include resolution |

## Verification

1. `bash tests/test_crew_template_includes.sh` — all tests pass
2. `python3 -m unittest discover -s tests -p 'test_brainstorm_*.py'` — existing tests still pass
3. `shellcheck .aitask-scripts/aitask_crew_addwork.sh .aitask-scripts/lib/agentcrew_utils.sh` — no new warnings
4. Read resolved templates to confirm section format block appears

## Step 9 (Post-Implementation)

Archive task t578, push changes.

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned. Added `resolve_template_includes()` to `agentcrew_utils.sh`, integrated it into `aitask_crew_addwork.sh`, created shared `_section_format.md` partial, updated 3 brainstorm templates to use include directives, created comprehensive test suite.
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** None. All existing tests continued to pass.
- **Key decisions:** Used "output" as the generic term in `_section_format.md` (replacing both "proposal" from explorer/synthesizer and "plan" from detailer) since all agents write to `_output.md`. Include resolution placed in shell layer (`agentcrew_utils.sh` + `aitask_crew_addwork.sh`) rather than Python layer (`brainstorm_crew.py`) to make it available to all crews.
