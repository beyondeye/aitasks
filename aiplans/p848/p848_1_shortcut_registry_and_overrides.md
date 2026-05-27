---
Task: t848_1_shortcut_registry_and_overrides.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_2_*.md, aitasks/t848/t848_3_*.md, aitasks/t848/t848_4_*.md, aitasks/t848/t848_5_*.md, aitasks/t848/t848_6_*.md
Archived Sibling Plans: aiplans/archived/p848/p848_*_*.md
Worktree: (current directory — fast profile)
Branch: main
Base branch: main
---

# p848_1 — Shortcut registry + user-overrides layer

## Goal

Library-only foundation: a registry that records every TUI's bindings
and a persistence layer that reads/writes per-user overrides in
`aitasks/metadata/userconfig.yaml`. No TUI is touched in this task.

## Files

**New:**

- `.aitask-scripts/lib/keybinding_registry.py`
- `.aitask-scripts/lib/shortcut_persist.py`
- `tests/test_keybinding_registry.sh`

**Modified:** none.

## Step-by-step

### 1. `keybinding_registry.py`

Module state:

```python
_DEFAULTS: dict[tuple[str, str], tuple[str, str]] = {}  # (scope, action_id) -> (default_key, label)
_OVERRIDES_CACHE: dict[str, dict[str, str]] | None = None  # scope -> {action_id: key}
```

API:

```python
def register_app_bindings(scope: str, bindings: list[Binding]) -> list[Binding]:
    """Record defaults from bindings; return a new list with user overrides applied."""

def load_user_overrides() -> dict[str, dict[str, str]]:
    """Read userconfig.yaml `shortcuts:` key. Cached. Returns {} if absent."""

def resolve_key(scope: str, action_id: str, default_key: str | None = None) -> str | None:
    """Look up the effective key. Returns override, else recorded default, else default_key arg, else None."""

def coherence_lint(scopes_to_check: list[str] | None = None) -> list[str]:
    """For each SHARED_ACTION_IDS entry, group scopes by effective key; emit warning if >1 group."""

def refresh(scope: str | None = None) -> None:
    """Invalidate the override cache; next call to load_user_overrides re-reads disk."""

SHARED_ACTION_IDS = frozenset({"quit", "tui_switcher", "refresh", "shortcuts_editor"})
```

Binding mutation: Textual's `Binding` is a frozen dataclass; use
`dataclasses.replace(b, key=new_key)`. (Confirmed via Textual source.)

### 2. `shortcut_persist.py`

```python
def save_override(scope: str, action_id: str, key: str) -> None: ...
def clear_override(scope: str, action_id: str) -> None: ...
def reset_scope(scope: str) -> None: ...
```

Implementation:

- Read existing `userconfig.yaml` via `yaml.safe_load` (or fall back
  to `{}` if file missing — but the file should already exist since
  it has `email:` / `last_used_labels:` from picker workflow).
- Deep-merge the shortcut change into `data.setdefault("shortcuts", {})[scope]`.
- Atomic write: `yaml.safe_dump` into a tempfile in the same dir, then
  `os.replace(tmp, path)`.
- After write, call `keybinding_registry.refresh(scope)`.

### 3. `tests/test_keybinding_registry.sh`

Use `tests/lib/test_scaffold.sh` + small Python `-c` invocations. One
temp `userconfig.yaml` per case. Assertions cover the six cases listed
in the task description.

Confirm whether `./ait` sources `lib/keybinding_registry.py` at startup
(it should not — only TUIs need it). If it does **not**, no
`tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` update is
needed. If it does, add `keybinding_registry.py` to the scaffolded
`.aitask-scripts/lib/` (per CLAUDE.md baseline rule).

## Verification

```bash
bash tests/test_keybinding_registry.sh    # all PASS
shellcheck tests/test_keybinding_registry.sh
```

## Verification (for the t848_7 manual-verification sibling)

- None — pure library task; covered by unit tests.

## Step 9 — Post-implementation

Standard archival. Plan + code commit separated per CLAUDE.md.
