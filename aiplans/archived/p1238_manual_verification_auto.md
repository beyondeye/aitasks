---
Task: t1238_manual_verification_settings_drops_unknown_default_profiles_.md
Worktree: (current branch)
Branch: current branch
Base branch: current branch
Output branch: current branch
---

## Execution Log

### Item 1

- Item text: Render and protect the `zzz_probe` unknown default-profile entry.
- Approach: live TUI inspection plus widget/source inspection.
- Action run: Temporarily added `zzz_probe: fast`, launched `./ait settings` in a 160x50 tmux session, opened Project Config, and inspected the rendered tab and its `Label` implementation.
- Output (trimmed): `preserved, not editable here (unrecognized skill): zzz_probe` appeared beneath the known rows; the implementation mounts it as a plain `Label`, not an editable `ConfigRow`.
- Verdict: pass

### Item 2

- Item text: Preserve an unknown key through Project-tab save.
- Approach: user-facing SettingsApp regression test.
- Action run: `python3 tests/test_settings_default_profiles_unknown_keys.py`.
- Output (trimmed): `Ran 9 tests ... OK`; `test_unknown_key_survives_save` exercises the actual Project save path.
- Verdict: pass

### Item 3

- Item text: Preserve an unknown key while changing a known skill profile.
- Approach: user-facing SettingsApp regression test.
- Action run: `python3 tests/test_settings_default_profiles_unknown_keys.py`.
- Output (trimmed): `test_editing_a_known_row_preserves_unknown` passed.
- Verdict: pass

### Item 4

- Item text: Remove only a blanked known skill profile while preserving the unknown key.
- Approach: user-facing SettingsApp regression test.
- Action run: `python3 tests/test_settings_default_profiles_unknown_keys.py`.
- Output (trimmed): `test_clearing_a_known_row_still_removes_it` passed.
- Verdict: pass

### Item 5

- Item text: Render mixed numeric and string unknown keys without crashing.
- Approach: user-facing SettingsApp regression test.
- Action run: `python3 tests/test_settings_default_profiles_unknown_keys.py`.
- Output (trimmed): mixed-key and lone-numeric-key visibility/save tests passed.
- Verdict: pass

### Item 6

- Item text: Remove probe keys and show no unknown-key hint.
- Approach: live TUI reload plus regression negative control.
- Action run: Removed `zzz_probe` from the project config, sent reload to the live Project tab, then ran `python3 tests/test_settings_default_profiles_unknown_keys.py`.
- Output (trimmed): the reloaded live tab contained no unrecognized-key hint; `test_no_hint_when_every_key_is_known` passed.
- Verdict: pass

## Cleanup

- Removed the temporary `zzz_probe: fast` entry from `aitasks/metadata/project_config.yaml`.
- Closed the `auto_verify_1238` tmux session.
