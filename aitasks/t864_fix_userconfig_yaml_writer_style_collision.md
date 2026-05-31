---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tui, custom_shortcuts, crash_recovery]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-05-31 09:08
updated_at: 2026-05-31 10:37
---

## Origin

Discovered via `/aitask-explore` on 2026-05-31 while investigating "all TUIs
(`ait board`, etc.) crash immediately on startup". Root cause traced to a
collision between two writers of the per-user (gitignored)
`aitasks/metadata/userconfig.yaml`. The live file was found corrupted and the
corruption was reproduced byte-for-byte (see below).

Related: **t863** (`fix_keybinding_registry_yaml_guard`) hardens only the
*reader*; this task fixes the *corruption source*. Kept as separate tasks by
explicit decision — do not fold. Both should land.

## Symptom

A malformed `userconfig.yaml` makes `yaml.safe_load()` raise
`yaml.parser.ParserError` at module import time. Because
`tui_switcher.py`'s module-level `_register_shared_bindings(...)` →
`register_app_bindings` → `keybinding_registry.load_user_overrides()` reads
the file at import, **every** board/TUI crashes before drawing anything.

Live corrupted content found:

```yaml
email: dario-e@beyond-eye.com
last_used_labels: [codexcli]
- agentcrew
```

## Root cause: two writers, incompatible YAML styles

1. `set_last_used_labels()` — `.aitask-scripts/lib/task_utils.sh:384-411`.
   Writes **flow** style (`last_used_labels: [a, b]`) and, when the field
   already exists, replaces **only the `last_used_labels:` line** via
   `sed_inplace "s|^last_used_labels:.*$|last_used_labels: [..]|"`.
   `get_last_used_labels()` (`task_utils.sh:366-378`) likewise reads only the
   single flow-style line.

2. `shortcut_persist._atomic_dump()` —
   `.aitask-scripts/lib/shortcut_persist.py:39-63` (the t848 customizable-
   shortcuts feature). Round-trips the **whole file** with
   `yaml.safe_dump(..., default_flow_style=False, ...)`, which rewrites
   `last_used_labels: [codexcli]` (flow) as a multi-line **block** list:

   ```yaml
   last_used_labels:
   - codexcli
   ```

When the Python writer runs first (file becomes block style) and a later
bash `set_last_used_labels` runs, its `sed` rewrites only the
`last_used_labels:` header line and **orphans the `- item` continuation
lines** — producing invalid YAML.

### Reproduction (confirmed)

```bash
cat > userconfig.yaml <<'EOF'
email: x@example.com
last_used_labels:
- agentcrew
EOF
# Exactly task_utils.sh:407 (set labels to "codexcli"):
sed -i "s|^last_used_labels:.*\$|last_used_labels: [codexcli]|" userconfig.yaml
# Result is the corrupted file:
#   last_used_labels: [codexcli]
#   - agentcrew
python3 -c "import yaml; yaml.safe_load(open('userconfig.yaml'))"   # ParserError
```

## Suggested fix

Make the two writers agree on a single representation and stop line-based
editing of a multi-line YAML value. Options (pick during planning):

- **Preferred:** route `last_used_labels` reads/writes through a yaml-aware
  helper that round-trips the whole file safely (mirroring
  `shortcut_persist._load_full()` / `_atomic_dump()`), so bash and Python
  never edit the file with mismatched assumptions. Consider sharing one
  Python persistence module for all `userconfig.yaml` top-level keys.
- **Minimal:** if `set_last_used_labels()` must stay bash, make it tolerate
  block style — rewrite the whole `last_used_labels` value (including
  removing any following `- item` continuation lines) instead of `sed`-ing a
  single line; and make `get_last_used_labels()` read block style too.

## Acceptance criteria

The fix MUST land with a new regression test (no fix without a test). The
test must reproduce the writer collision and assert it can no longer corrupt
the file:

- **Block-then-bash:** write a block-style `last_used_labels` to
  `userconfig.yaml`, run `set_last_used_labels`, then assert the file still
  parses as valid YAML and the labels round-trip (read back equals what was
  written).
- **Python-then-bash end-to-end:** simulate a shortcut-save (the Python
  `shortcut_persist` writer) followed by an `ait create` (the bash
  `set_last_used_labels` writer) on the same file, and assert the file
  remains valid YAML afterward.
- `get_last_used_labels()` correctly reads labels regardless of whether the
  file is flow style or block style.
- The test fails against the current (unfixed) code and passes after the fix.

Place the test under `tests/` following the existing self-contained bash test
convention (`assert_eq`/`assert_contains`, PASS/FAIL summary).

## Notes

- `userconfig.yaml` is gitignored and per-user, so this corruption is silent
  in CI and only bites real users who have used the t848 shortcut editor and
  then run a label-writing command.
- This is the upstream corruption source; t863's reader try/except is the
  complementary defense-in-depth so a future corruption degrades to "no
  overrides" instead of a crash.
