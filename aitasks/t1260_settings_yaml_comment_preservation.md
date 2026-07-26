---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [ait_settings]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-07-26 23:00
updated_at: 2026-07-26 23:00
---

## Origin

Risk-mitigation ("after") follow-up for t1231, created at decomposition time.
t1231 was split into children, so its Step 8d never runs — the mitigation is
created here instead, with `depends: [1231]` preserving the "after" ordering.

## Risk addressed

Code-health risk (severity: low) from `p1231`:

> A ninth tab in a shipped 3907-line single-file Textual app, whose save path
> destroys the seeded comments in `project_config.yaml`.

## The defect

`.aitask-scripts/lib/config_utils.py:167-172`:

```python
def save_yaml_config(path: str | Path, data: dict) -> None:
    """Write a project-level YAML config with stable key ordering."""
    yaml_path = Path(path)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
```

`yaml.safe_dump` round-trips **values only** — every `#` comment in the file is
destroyed on write. `aitasks/metadata/project_config.yaml` is heavily commented
(the doc_update spec, the applink `advertised_*` block, the monitor
`compare_mode` notes), and `seed/project_config.yaml` ships a 37-line commented
`artifacts:` documentation block at L189-225.

Any Save from the **Project Config** tab (`settings_app.py:2534-2581`), the
**Tmux** tab (`save_tmux_settings`, L2904-2960), or the **Artifacts** tab added
by t1231_2 silently erases all of it. This is long-standing behavior, not a
regression introduced by t1231 — t1231_2 explicitly decided to accept it rather
than fix it as a side effect, and to state it in the pane hint.

Consequence: a user who opens the settings TUI once loses the inline
documentation that the seed file exists to provide, and `ait setup` will not put
it back (the file already exists).

## Goal

Make settings saves comment-preserving.

Considerations for planning:

1. **Round-tripper choice.** `ruamel.yaml` preserves comments and ordering but is
   a new dependency; the framework currently depends only on PyYAML and resolves
   its interpreter through `.aitask-scripts/lib/python_resolve.sh`. Weigh
   ruamel-if-available-else-safe_dump (graceful degradation, two code paths)
   against a hard dependency, against a targeted surgical writer that edits only
   the changed keys' lines in place.
2. **Blast radius.** `save_yaml_config` is the shared seam
   (`config_utils.py:167`); changing it affects every caller, not just settings.
   Enumerate them before changing the function rather than after.
3. **Failure mode must be safe.** If the round-tripper cannot parse a file, it
   must fail closed (refuse to write) rather than fall back to a lossy dump —
   silently discarding comments is the very defect being fixed.
4. **Do not reorder or reformat** untouched regions; a settings save should
   produce a minimal diff.

## Verification

- Write a fixture `project_config.yaml` carrying comments in three positions
  (leading block, inline trailing a key, between sections); save through the real
  `SettingsApp` Project / Tmux / Artifacts save paths; assert **every comment
  survives** and only the intended key changed (`git diff` is minimal).
- Negative control: prove the guard bites — the same test against the current
  `safe_dump` implementation must fail.
- Existing settings tests stay green:
  `python3 tests/test_settings_learn_skill_guide.py`,
  `python3 tests/test_settings_default_profiles_unknown_keys.py`,
  `python3 tests/test_settings_project_groups_tab.py`,
  `python3 tests/test_settings_shortcuts_tab.py`.
- Unknown-key preservation (already pinned by
  `test_settings_default_profiles_unknown_keys.py`) still holds.
