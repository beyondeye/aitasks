---
Task: t1918_fix_claude_coauthor_label_1m_and_major_only_ids.md
Base branch: main
Output branch: main
---

# Plan: t1918 — Claude co-author label for `[1m]` and major-only cli_ids

## Context

`format_claude_model_label()` (`.aitask-scripts/aitask_codeagent.sh:163`) turns a
Claude `cli_id` into the human label used in the `Co-Authored-By:` trailer
(`get_agent_coauthor_name`, same file ~L231 → `ait codeagent coauthor`). Its regex
`^claude-([a-z]+)-([0-9]+)-([0-9]+)(-[0-9]+)?$` requires a minor version and
rejects a `[1m]` suffix, so these registered ids fall through to the raw id:

- `claude-opus-5-5[1m]`, `claude-sonnet-5-5[1m]`, `claude-haiku-5-5[1m]`,
  `claude-opus-4-7[1m]`, `claude-opus-4-8[1m]` → `Claude Code/claude-…[1m]`
- major-only `claude-opus-5`, `claude-sonnet-5`, `claude-fable-5`,
  `claude-opus-5[1m]` → raw id

Every commit from a 1M-context or major-only Claude session therefore carries the
raw id in its trailer. `aitask_codeagent.sh` is the only producer of the label;
no script parses it back (grepped `Co-Authored-By` / `AGENT_COAUTHOR_NAME` /
`Claude Code/` under `.aitask-scripts/`). The file and `tests/test_codeagent.sh`
are currently clean in git (the concurrent edits mentioned in the task are gone).

## Implementation

### 1. `.aitask-scripts/aitask_codeagent.sh` — `format_claude_model_label()`

Replace the body with:

```bash
format_claude_model_label() {
    local raw_model="$1"

    # claude-<family>-<major>[-<minor>][-<date>][\[1m\]] → <Family> <major>[.<minor>]
    # The [1m] suffix names a context window, not a different model, so it is
    # dropped. The minor is 1-2 digits so an 8-digit date on a major-only id
    # (claude-opus-5-20251001) is read as the date, not as the minor.
    local re='^claude-([a-z]+)-([0-9]+)(-([0-9]{1,2}))?(-[0-9]+)?(\[1m\])?$'
    if [[ "$raw_model" =~ $re ]]; then
        local family="${BASH_REMATCH[1]}"
        local version="${BASH_REMATCH[2]}"
        [[ -n "${BASH_REMATCH[4]}" ]] && version+=".${BASH_REMATCH[4]}"
        # Capitalize family name
        local cap_family
        cap_family="$(tr '[:lower:]' '[:upper:]' <<< "${family:0:1}")${family:1}"
        echo "$cap_family $version"
        return
    fi

    echo "$raw_model"
}
```

Notes:
- Regex kept in a variable (needed for the literal `[`/`]` in `\[1m\]` under `[[ =~ ]]`).
- Date group stays `(-[0-9]+)?` as today, so every id the old regex accepted
  still yields the same label (`claude-haiku-4-5-20251001` → `Haiku 4.5`,
  Test 21 unchanged).
- **`[1m]` is stripped, not labelled** (user decision): opus5_5, sonnet5_5 and
  opus5 always run with 1M context, so `opus5_5` and `opus5_5_1m` are the same
  model in practice and must produce the same trailer name. Self-detection
  sometimes resolves to the formal `_1m` variant; after this fix that no longer
  changes the attribution. Applied uniformly (also to 4.x `[1m]` ids) — the
  trailer names the model, and the context window is a session setting.
- Probed (read-only) against all registry shapes: `claude-opus-5` → Opus 5,
  `claude-opus-5[1m]` → Opus 5, `claude-opus-5-5[1m]` → Opus 5.5,
  `claude-fable-5-1` → Fable 5.1, `claude-opus-5-20251001` → Opus 5;
  non-claude ids still unmatched.

### 2. `tests/test_codeagent.sh` — new assertions after Test 21

Add a "Test 21b" block right after Test 21. Every new case asserts the **exact**
`AGENT_COAUTHOR_NAME:` line with `assert_eq` — never `assert_contains_ci`, whose
case-insensitive substring match would accept `Opus 5.5` for an expected
`Opus 5`, or `Sonnet 5.5 (1M context)` for `Sonnet 5.5`.

A small local helper keeps it readable:

```bash
coauthor_name_line() {
    (cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor "$1" 2>&1) \
        | grep '^AGENT_COAUTHOR_NAME:'
}
```

**Fixture ids.** The registry has no dated major-only id, so the 1–2-digit
minor rule (the part that tells a date apart from a minor) is otherwise never
tested. Back up `$TMPDIR_TEST/aitasks/metadata/models_claudecode.json`, then use jq
to append two test-only entries to the temp copy (jq → tmp file → mv):
`{"name":"t1918_opus5_dated","cli_id":"claude-opus-5-20251001"}` and
`{"name":"t1918_opus5_dated_1m","cli_id":"claude-opus-5-20251001[1m]"}`.
Restore the backup at the end of the block, so later tests see the unmodified
registry copy.

Exact assertions (`assert_eq "<desc>" "AGENT_COAUTHOR_NAME:Claude Code/<label>" "$(coauthor_name_line <agent>)"`):

| agent string | cli_id | expected label |
|---|---|---|
| `claudecode/opus5_5_1m` | `claude-opus-5-5[1m]` | `Opus 5.5` |
| `claudecode/sonnet5_5_1m` | `claude-sonnet-5-5[1m]` | `Sonnet 5.5` |
| `claudecode/opus5` | `claude-opus-5` | `Opus 5` |
| `claudecode/opus5_1m` | `claude-opus-5[1m]` | `Opus 5` |
| `claudecode/t1918_opus5_dated` | `claude-opus-5-20251001` | `Opus 5` |
| `claudecode/t1918_opus5_dated_1m` | `claude-opus-5-20251001[1m]` | `Opus 5` |

Plus one exact trailer line for `opus5_5_1m`:
`AGENT_COAUTHOR_TRAILER:Co-Authored-By: Claude Code/Opus 5.5 <claudecode@aitasks.io>`.

**Negative control:** before committing, temporarily revert the function to the
old regex in the working copy and confirm that every row above fails. Then
restore the fix. (A dated row that passes under the old regex would mean the
fixture is not exercising the date/minor split.)

Do not renumber later tests.

## Verification

- `bash tests/test_codeagent.sh` — all pass, including Test 21 (haiku date strip)
  and the new 21b assertions.
- `bash tests/test_resolve_detected_agent.sh` (other coauthor consumer test).
- `shellcheck .aitask-scripts/aitask_codeagent.sh`.
- Spot check: `./ait codeagent coauthor claudecode/haiku5_5_1m` →
  `Claude Code/Haiku 5.5`.

## Step 9

Post-implementation: commit code (`bug: … (t1918)`), then archival per
task-workflow Step 9 (current-branch mode, no merge).

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** `format_claude_model_label()` (`.aitask-scripts/aitask_codeagent.sh`) now accepts `claude-<family>-<major>[-<minor>][-<date>][[1m]]`, drops `[1m]`, and emits `<Family> <major>[.<minor>]`. Test 21b in `tests/test_codeagent.sh` adds seven exact-line `assert_eq` checks (six name lines + one trailer), including two test-only dated major-only registry entries appended to the temp `models_claudecode.json` copy and restored afterwards.
- **Deviations from plan:** None beyond the two review rounds folded in before approval: (1) `[1m]` is stripped, not labelled `(1M context)` — the user confirmed opus5_5 / sonnet5_5 / opus5 always run with 1M context, so the `_1m` entries are the same model; (2) every new case asserts the exact line, and dated major-only fixtures exercise the 1-2-digit minor rule.
- **Issues encountered:** None. Negative control (test suite run against the HEAD version of the script in a symlinked scratch tree) failed all 7 new assertions and passed the 236 existing ones. It also exposed that the old regex labelled `claude-opus-5-20251001` as `Opus 5.20251001` (the date read as a minor).
- **Key decisions:** The date group stays `(-[0-9]+)?` so every id the old regex accepted still yields its old label (Test 21 haiku date strip unchanged). `[1m]` stripping applies to 4.x ids too: the trailer names the model, and the context window is a session setting.
- **Upstream defects identified:** None
