---
Task: t1672_fix_failed_verification_t1670_item7.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1672 — Stop the Settings TUI re-parsing string config values as YAML

## Context

`t1670` item 7 asked whether the `resource_admission_command` row added by
t1597 renders, edits, and **saves back to `project_config.yaml` losslessly**.
Rendering and editing are correct. The save is not.

`.aitask-scripts/settings/settings_app.py:2590` (`save_project_settings`) does:

```python
data[key] = yaml.safe_load(raw_value)
```

Every Project Config editor string is re-parsed as a YAML *document*. Any value
containing `: ` therefore becomes a **dict**:

```
typed : sh -c "echo ADMISSION_REASON: no memory; exit 2"
stored: {'sh -c "echo ADMISSION_REASON': 'no memory; exit 2"'}
```

`safe_dump` writes that as a nested block, and on reload
`aitask_resource_admission.sh` sees no scalar and reports:

```
VERDICT:admit / REASON:none_configured   (exit 0)
```

Reproduced end-to-end against the real helper before planning: a config whose
value is a nested block admits silently, exit 0, with no log and no message —
`resource-admission.md` step 2 displays *nothing* for `none_configured`. The
user configured a hook, the TUI said "Project config saved", and the framework
behaves as if no hook existed. That inverts the feature's stated fail-closed
posture into a fail-open one, and this key's own documented reason convention
(`ADMISSION_REASON: <text>`) makes a colon-space the *normal* case for it.

Line 2590 is pre-existing and applies to all six string-typed project-config
keys; t1597 is what made it reachable and harmful.

Intended outcome: a string-typed key stores exactly what the user typed (the
pre-existing trim of surrounding whitespace aside — see step 3), and a
non-scalar value can never again be read as "not configured".

## Approach

Two independent changes, each closing one half of the fail-open path.

**Part 1 (the defect): type the schema, stop re-parsing.** `TMUX_CONFIG_SCHEMA`
already carries a per-key `"type"` and `save_tmux_settings` stores strings
verbatim — `PROJECT_CONFIG_SCHEMA` is the odd one out. Adopt the same
convention rather than inventing a new mechanism.

**Part 2 (defense in depth): make a non-scalar loud.** Even with Part 1, an
already-corrupted config, or any hand edit, still resolves to nothing and
silently admits. The helper already refuses every **list** form with
`REASON:not_scalar` + exit 3; a nested **mapping** slips through that check
because `read_yaml_list` does not witness it. Extend the existing shape check
rather than adding a verdict.

---

## Implementation

### 1. `.aitask-scripts/settings/settings_app.py` — schema types

Add a `"type"` entry to each `PROJECT_CONFIG_SCHEMA` value (the dict is typed
`dict[str, dict[str, str]]`; all values stay `str`):

| key | type |
|---|---|
| `codeagent_coauthor_domain` | `"string"` |
| `verify_build` | `"string_or_list"` |
| `test_command` | `"string_or_list"` |
| `lint_command` | `"string_or_list"` |
| `resource_admission_command` | `"string"` |
| `learn_skill_authoring_guide` | `"string"` |
| `default_profiles` | `"mapping"` |

`default_profiles` never reaches the coercion (its rows carry the
`project_dp_` id prefix and are collected separately); the entry documents the
type for the same reason the others do.

### 2. `.aitask-scripts/settings/settings_app.py` — the coercion helper

New module-level function placed **immediately after** `_format_yaml_value`
(~line 333), of which it is the exact inverse.

**The list-intent rule must be unambiguous, and "starts with `[`" is not.**
Bracket-leading shell commands are ordinary `verify_build` values, and they
break a naive rule in *both* directions — measured, not assumed:

| typed value | `yaml.safe_load` |
|---|---|
| `[ -f Makefile ] && make` | `ScannerError` |
| `[ -d build ] \|\| mkdir build` | `ScannerError` |
| `[[ -n "$CI" ]] && pytest` | `ScannerError` |
| `[ -f Makefile ]` | **`['-f Makefile']` — a clean list** |

So raising on a parse failure rejects three valid commands, and trusting
`isinstance(parsed, list)` silently stores the fourth as a one-element list —
the same class of corruption as the bug being fixed, moved to another key.

**The unambiguous signal is round-trip canonicality:** text is a list only when
it is *exactly* what the app itself would render for that list. `[ -f Makefile ]`
renders as `[-f Makefile]` — not what the user typed — so it is a command.

That rule is needed at **three** places, not one, and each is a real bug today:

| call site | direction | what it gets wrong now |
|---|---|---|
| `save_project_settings` | text → stored | re-parses everything (**the reported defect**) |
| `_to_compact_yaml` | editor text → `raw_value` | canonicalizes any parse-as-list, and YAML-decodes scalars |
| `_to_block_yaml` | `raw_value` → editor text | expands any parse-as-list into block form |

**The ambiguity is flow-form-only, and the rule must say so.** A shell command
can look exactly like a YAML *flow* sequence (`[ -f Makefile ]`), which is why
those need the provenance check. Nothing comparable is true of **block** form:
a line opening with `- ` is not a shell command, and the multi-line editor's
documented input syntax *is* a block list. Applying canonicality to block text
would reject every ordinary hand edit — measured:

| user edits the list as | under a block-canonicality rule |
|---|---|
| `- "make build"` | stored as the scalar string `- "make build"` |
| `- make build  # release` | stored as a scalar string |
| `- a` / `-   b` (re-indented) | stored as a scalar string |

That would break the editor's documented list input and the task's own
"must not regress `verify_build`'s list form" obligation. So: **block form is
accepted on sight; flow form must be canonical.**

Three copies of one rule is how they drifted apart in the first place, so state
it **once** as a shared predicate and give the two renderings names. Add beside
`_format_yaml_value` (~line 333):

```python
def _format_yaml_block(value) -> str:
    """Render a YAML list into the readable block form the editor shows."""
    return yaml.safe_dump(
        value, default_flow_style=False, sort_keys=False, allow_unicode=True,
    ).strip()


_BLOCK_LIST_OPENER = re.compile(r"^-(\s|$)")


def _looks_like_block_list(text: str) -> bool:
    """True when text's first content line opens a YAML block sequence.

    Block form is UNAMBIGUOUS -- no shell command opens a line with `- ` --
    so a block edit is taken as a list whatever its spelling: quoted items,
    trailing comments and re-indentation all stay lists. Only FLOW form is
    ambiguous with a command, and only that goes through _list_if_canonical.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return bool(_BLOCK_LIST_OPENER.match(stripped))
    return False


def _list_if_canonical(text: str, renderer):
    """The list `text` is the canonical `renderer` output for -- else None.

    THE single list-intent test, shared by the save path and both directions
    of the multi-line editor. Parsing alone is not enough: `[ -f Makefile ]`
    is a shell test command and a perfectly good verify_build, yet it parses
    to the list ['-f Makefile']. It is only a LIST if the text is byte-for-byte
    what we would have written for that list -- which it is not, since we
    render `[-f Makefile]`. Provenance, not intent-guessing: every list
    reaching these call sites was rendered by one of the two renderers.

    ONLY for FLOW-form text, where the ambiguity actually lives. A block-form
    edit (`- item` lines) is unambiguous and is handled by
    _looks_like_block_list instead -- canonicality there would reject a
    perfectly good `- "make build"`.
    """
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if isinstance(parsed, list) and renderer(parsed) == text.strip():
        return parsed
    return None


def _coerce_project_config_value(key: str, raw_value: str):
    """Turn a Project Config editor string into the value that is stored.

    raw_value arrives ALREADY TRIMMED by the caller (see
    save_project_settings) and is otherwise stored EXACTLY as given -- no
    re-parsing, no re-rendering. Only a key the schema declares
    `string_or_list` may become a list, and only when _list_if_canonical says
    raw_value IS the canonical flow rendering of one.

    Re-parsing a string-typed key as a YAML document is what stored
    `sh -c "echo ADMISSION_REASON: x; exit 2"` as a nested mapping, which the
    admission hook then read as "not configured" (t1672).
    """
    if PROJECT_CONFIG_SCHEMA.get(key, {}).get("type") != "string_or_list":
        return raw_value
    parsed = _list_if_canonical(raw_value, _format_yaml_value)
    return raw_value if parsed is None else parsed
```

An unknown key defaults to string semantics (verbatim) — the lossless
direction.

### 2a. `.aitask-scripts/settings/settings_app.py` — the editor, both directions

The save-path rule is worthless on its own: the editor sits on both sides of
it, and today each side breaks a different value. **Neither direction may be
skipped.** Rewrite both `EditVerifyBuildScreen` statics against the shared
predicate:

```python
    @staticmethod
    def _to_block_yaml(value: str) -> str:
        """Expand a canonical flow list into block form for editing."""
        if not value:
            return ""
        parsed = _list_if_canonical(value, _format_yaml_value)
        return value if parsed is None else _format_yaml_block(parsed)

    @staticmethod
    def _to_compact_yaml(text: str) -> str:
        """Convert edited text back to the canonical storage form."""
        text = text.strip()
        if not text:
            return ""
        if _looks_like_block_list(text):
            # Unambiguous list intent: accept any spelling -- quoted items,
            # trailing comments, re-indentation.
            try:
                parsed = yaml.safe_load(text)
            except yaml.YAMLError:
                return text
            return _format_yaml_value(parsed) if isinstance(parsed, list) else text
        # Flow form is ambiguous with a shell command; require provenance.
        parsed = _list_if_canonical(text, _format_yaml_value)
        return text if parsed is None else _format_yaml_value(parsed)
```

Both directions use the **flow** renderer for the canonicality check, because
in both the text under test is flow form: `raw_value` on the way in, and (in
the non-block branch) whatever the user typed on the way back. `_format_yaml_block`
is used only to *render*, never to gate.

A block edit's YAML comments are dropped, because `safe_load` drops them — the
inherent behavior of a YAML editor, and the command itself is preserved. Note
it in the docstring so it is not discovered as a surprise.

Four defects close here, all measured:

1. **`_to_block_yaml` expands a scalar into a list (the display path).**
   `_to_block_yaml("[ -f Makefile ]")` returns `- -f Makefile` today. Saving
   that then yields canonical `[-f Makefile]`, which the save rule *correctly*
   accepts as a list — so a stored command silently becomes a list by being
   looked at. The save-path fix alone does not catch this; the provenance
   check must run before the value is expanded, not only after.

2. **`_to_compact_yaml` YAML-decodes scalars**, stripping shell-significant
   quoting. `"$HOME/with space/run"` → `$HOME/with space/run`, which
   word-splits when run; `'pytest -k "a b"'` → `pytest -k "a b"`. This needs
   no edit to fire — opening the editor and pressing save is enough. Dropping
   the `isinstance(parsed, str): return parsed` branch (there is no such branch
   above) preserves the text.

3. **A block-form edit must stay a list whatever its spelling.** Gating block
   text on canonicality (the obvious symmetric move, and wrong) turns
   `- "make build"`, `- make build  # release` and a re-indented
   `- a` / `-   b` into scalar strings — silently replacing a command list
   with a broken command. `_looks_like_block_list` is what keeps the
   provenance check confined to the flow form that actually needs it.

4. **The dumpers disagree on `allow_unicode`.** `_format_yaml_value` passes it
   and the old `_to_compact_yaml` / `_to_block_yaml` did not, so
   `["café", "naïve"]` rendered as `[café, naïve]` in one place and
   `["caf\xE9", "na\xEFve"]` in the other — an edited Unicode list would fail
   the canonicality check and be stored as a string, and the editor would show
   escapes. Routing every dump through the two named renderers removes the
   possibility rather than re-syncing options by hand.

Scope check: `EditStringScreen`
(`.aitask-scripts/lib/profile_editor.py:573`) returns its `Input.value`
verbatim, so the `"string"`-typed keys — `resource_admission_command`
included — never had defects 2–4. All of them are confined to the three
`string_or_list` keys, which is exactly what this step touches. `re` is not
currently imported by `settings_app.py` — add it to the stdlib import block
(line 9–12).

**Verified end to end** (stored → displayed → saved → persisted), the whole
point of doing all three sites together:

| stored | displayed | saved as | persisted |
|---|---|---|---|
| `[ -f Makefile ]` | unchanged | unchanged | `str`, intact |
| `[ -f Makefile ] && make` | unchanged | unchanged | `str`, intact |
| `"$HOME/with space/run"` | unchanged | unchanged | `str`, quotes intact |
| `[a, b]` | `- a` / `- b` | `[a, b]` | `list ['a','b']` |
| `[café, naïve]` | `- café` / `- naïve` | `[café, naïve]` | `list` |
| `[-f Makefile]` | `- -f Makefile` | `[-f Makefile]` | `list` — a genuine 1-item list still works |

### 3. `.aitask-scripts/settings/settings_app.py` — the call site (~line 2586)

```python
            data[key] = _coerce_project_config_value(key, raw_value)
```

**The stored value is trimmed, and that is deliberate — say so, don't claim
otherwise.** The loop already reads `raw_value = row.raw_value.strip()`
(line 2585) and that line is **unchanged**, so a string-typed value is stored
exactly as entered *apart from surrounding whitespace*. Every "verbatim" /
"lossless" claim in this plan and in the new docstrings is scoped that way;
the promise must not outrun the code.

The alternative — keeping the untrimmed text for storage and a trimmed copy
only for the `if not raw_value` blank-removes-key test — was considered and
**rejected**: surrounding whitespace on a shell command or a path is invisible
in the row that redisplays it, has no effect on any consumer, forces the
YAML writer to quote the value, and would make a stray typed space durable
project state. It is also a behavior change wider than this bug, which is
about *interior* content (`: `), not the edges. The narrowed contract is
pinned by a test (post-phase step 9) rather than left as prose.

The `try` / `except yaml.YAMLError` / `self.notify(...)` / `return` block is
**removed**, not narrowed. Under the rule above there is no longer any value
for which a parse failure means an error: a string-typed key accepts any text,
and a `string_or_list` key whose text is not the canonical flow form is a
command string. Keeping the guard would mean rejecting
`[ -f Makefile ] && make`.

**What that costs, stated plainly:** a user who mistypes a flow list as
`[a, b` no longer gets an error dialog and no longer has the whole save
aborted — the value is stored as the literal string `[a, b`. The row then
redisplays that text verbatim, so the mistake is visible on the tab and one
re-edit fixes it. That is the right trade against silently rejecting valid
commands, and it removes the "one bad row aborts every other edit in the tab"
behavior as a side effect.

### 4. `.aitask-scripts/aitask_resource_admission.sh` — refuse a nested block

Add a shape helper beside `sanitize_line`:

```bash
# yaml_key_has_block_child <file> <key>
# True when <key> is a TOP-LEVEL key whose inline value is empty and whose next
# content line is indented -- i.e. its value is a nested block, not a scalar.
# An empty `key:` with no indented body is NOT a block: that is the documented
# way to disable the hook and must stay "not configured".
yaml_key_has_block_child() {
    local file="$1" key="$2" answer
    [[ -f "$file" ]] || return 1
    answer="$(LC_ALL=C awk -v key="$key" '
        seen == 0 {
            if (index($0, key ":") == 1 &&
                substr($0, length(key) + 2) ~ /^[[:space:]]*$/) seen = 1
            next
        }
        /^[[:space:]]*$/ { next }
        /^[[:space:]]*#/ { next }
        /^[[:space:]]/   { print "block"; exit }
        { exit }
    ' "$file")"
    [[ "$answer" == "block" ]]
}
```

Call it immediately **after** the existing `read_yaml_list` refusal (a block
*list* is caught there first) and **before** the `${#cmds[@]} -eq 0`
`none_configured` branch, reusing the established reason token and exit-3 shape:

```bash
if yaml_key_has_block_child "$CONFIG_FILE" "$RESOURCE_ADMISSION_KEY"; then
    printf 'REASON:not_scalar\n'
    diag_exit "$RESOURCE_ADMISSION_KEY must be a single command string, but its value in $CONFIG_FILE is an indented block, not a scalar -- put the command on the key line (quote it if it contains a colon)"
fi
```

Extend the header's `REASON:` comment block only where it names what
`not_scalar` covers.

### 5. Docs — `website/content/docs/skills/aitask-pick/resource-admission.md`

The existing sentence says only a *list* is refused. Extend it to state that
any non-scalar value — a list of any length, or an indented block — is
refused, and that a command containing a colon must be quoted. Current-state
prose only; no version history.

---

## Tests

### 6. New: `tests/test_settings_project_config_value_types.py`

Modeled on `tests/test_settings_learn_skill_guide.py` — mounts the **real**
`SettingsApp`, edits real `ConfigRow`s, calls the app's own
`save_project_settings()`, and reloads with `config_utils.load_yaml_config`.

- `resource_admission_command` set to `sh -c "echo ADMISSION_REASON: no memory; exit 2"`
  reloads as a **`str`** equal to the typed text (the defect).
- **Independent ground truth, end-to-end:** in that same fixture directory,
  run the real `.aitask-scripts/aitask_resource_admission.sh` via `subprocess`
  and assert `REASON:refused` / exit 1 — not `none_configured` / exit 0. This
  is the assertion that actually proves the fail-open is gone; a
  string-equality check alone would not.
- `learn_skill_authoring_guide` with a colon-space in the value round-trips as
  a string.

### 7. New: `tests/test_resource_admission.sh` — block-value cases

Added to Section 1 beside the existing `list_case` battery, reusing
`fresh_project` / `run_helper` / `field` and `assert_exit3`:

- a nested-block value ⇒ exit 3, `REASON:not_scalar`, `LOG:(none)`, no
  `.aitask-gates/` directory created.

### Post-phase (risk mitigations)

Both blocks are negative controls: they must **fail** if the corresponding
change over-reaches. Neither is optional.

**8. `negative_control_shape_check`** — in `tests/test_resource_admission.sh`,
beside the new block case, assert every shape that must **not** be read as a
block. Each must produce its ordinary verdict, never exit 3:

| config | expected |
|---|---|
| key absent entirely | `none_configured`, exit 0 |
| no `project_config.yaml` at all | `none_configured`, exit 0 |
| `resource_admission_command:` (empty, no body) | `none_configured`, exit 0 |
| `resource_admission_command:` + a following **top-level** key | `none_configured`, exit 0 |
| `resource_admission_command: 'sh -c "echo ADMISSION_REASON: no memory; exit 2"'` | `refused`, exit 1, `DETAIL:no memory` |
| a scalar whose value contains a comma | `refused`, exit 1 (the existing control, still passing) |

The last two are the ones that matter most: they are the *correct* uses of a
colon and a comma, and the shape check must leave them alone. The
empty-then-top-level-key row is the one that separates "empty scalar" from
"nested block" — the distinction the whole helper turns on.

**9. `negative_control_list_form`** — in
`tests/test_settings_project_config_value_types.py`, through the same real
`SettingsApp` save path. The bracket-leading rows are the ones that discriminate
the canonicality rule from a naive `startswith("[")` / `isinstance(list)` rule;
without them a regression here is invisible:

| `verify_build` typed as | reloads as |
|---|---|
| `[a, b]` | **`list`** `["a", "b"]` — the carve-out still works |
| `[ -f Makefile ] && make` | **`str`**, exact text (parse failure ⇒ string, no save abort) |
| `[[ -n "$CI" ]] && pytest` | **`str`**, exact text |
| `[ -f Makefile ]` | **`str`**, exact text — *parses* as a list but is not canonical |
| `make build: release` | **`str`**, exact text — a colon in a `string_or_list` key |
| `[café, naïve]` | **`list`** `["café", "naïve"]` — the step-2a Unicode case |
| `"$HOME/with space/run"` | **`str`**, quotes intact — the step-2a quoting case |
| `[a, b` | **`str`** `[a, b`, and the save is **not** aborted (other rows in the same save still persist) |

The last row also pins the guard removal: assert that a second key edited in
the same save round-trips, so "one bad row aborts the tab" cannot come back.

**The open-and-save cycle, which is where two of the three defects live.** The
save-path table above cannot see them: it never opens the editor. Parametrize
one test over the round trip and assert on the *persisted* value, since that is
what a consumer reads:

```
stored value → _to_block_yaml → (user changes nothing) → _to_compact_yaml
             → save through the real SettingsApp → reload
```

| stored | must reload as |
|---|---|
| `[ -f Makefile ]` | `str`, identical — **the display-path regression**: a scalar must not become a list by being looked at |
| `[ -f Makefile ] && make` | `str`, identical |
| `"$HOME/with space/run"` | `str`, identical — quoting intact |
| `'pytest -k "a b"'` | `str`, identical |
| `[a, b]` | `list ["a", "b"]` |
| `[café, naïve]` | `list ["café", "naïve"]` — Unicode survives both dumpers |
| `[-f Makefile]` | `list ["-f Makefile"]` — a genuine one-item list still round-trips |

Every row must hold for *both* meanings of "unchanged": the reload equals the
stored value, and a second cycle changes nothing again (idempotence), so a
half-canonical form cannot hide behind a single pass.

**Edited block lists stay lists, whatever the spelling.** The cycle table above
only covers a *no-op* edit, so it cannot see the block-form rule at all. Drive
these as actual edited `TextArea` text through `_to_compact_yaml` → save →
reload, asserting the persisted value is a **`list`**:

| edited text | must persist as |
|---|---|
| `- make build` | `["make build"]` — the plain form |
| `- "make build"` | `["make build"]` — **quoted item** |
| `- make build  # release` | `["make build"]` — **trailing comment** (dropped by `safe_load`, as any YAML editor does) |
| `- a` / `-   b` (odd indent) | `["a", "b"]` — **re-indented** |
| `- café` | `["café"]` |
| `- pytest -k "a b"` | `["pytest -k \"a b\""]` — a quoted-argument command as a list item |
| `# note` / `- make build` | `["make build"]` — a leading comment line does not hide the block opener |

And the discriminating negative, in the same test so the pair cannot drift: a
non-block edit that merely *parses* as a list — `[ -f Makefile ]` typed into
the `TextArea` — persists as a **`str`**. That one pair is the whole rule.

**The seam itself, pinned directly**, so a future third dumper or a re-added
scalar branch fails here rather than silently in a user's config:

- `_to_block_yaml("[ -f Makefile ]")` returns the text **unchanged** — not
  `- -f Makefile`;
- `_to_compact_yaml('"$HOME/with space/run"')` returns the text **with its
  quotes**, not the decoded scalar;
- `_to_block_yaml(_format_yaml_value(["café", "naïve"]))` contains `café`
  unescaped, and `_to_compact_yaml` of that returns exactly
  `_format_yaml_value(["café", "naïve"])`;
- `_list_if_canonical("[ -f Makefile ]", _format_yaml_value) is None` while
  `_list_if_canonical("[-f Makefile]", _format_yaml_value) == ["-f Makefile"]`
  — the predicate's discriminating pair, asserted on the predicate itself;
- `_looks_like_block_list` is true for `- a`, `-` alone, `# c\n- a`, and false
  for `[ -f Makefile ]`, `make build`, and a multi-line scalar whose *second*
  line begins with `- ` (`make build \\\n  - foo`) — the opener is decided by
  the first content line, not by any line.

**The whitespace contract, pinned as an assertion rather than a promise.**
`save_project_settings` trims each row before storing, so "verbatim" is scoped
to interior content. Assert the scope in both directions so neither half can
drift:

- `resource_admission_command` given `"  sh -c \"echo ADMISSION_REASON: x; exit 2\"  "`
  reloads as the **trimmed** string — surrounding whitespace is dropped,
  and *nothing else about the value is*;
- the interior is untouched: a value with runs of internal spaces
  (`sh -c  "echo  a: b"`) reloads byte-identical in its interior.

If a later change decides to preserve the edges instead, this test is the
thing that must be updated deliberately — which is the point of writing it
down.

---

## Verification

```bash
# unit / integration
python3 tests/test_settings_project_config_value_types.py
bash tests/test_resource_admission.sh
bash tests/test_resource_admission_stop.sh
python3 tests/test_settings_learn_skill_guide.py
python3 tests/test_settings_default_profiles_unknown_keys.py

# regression sweep
bash tests/run_all_python_tests.sh          # read ONLY the last line
shellcheck .aitask-scripts/aitask_resource_admission.sh
```

Manual (the original t1670 item 7, closed properly): in a scratch project with
`aitasks/metadata/project_config.yaml`, run `ait settings` → `c` → Project
Config → `resource_admission_command` → Enter → type
`sh -c "echo ADMISSION_REASON: no memory; exit 2"` → Save. Then:

```bash
grep -n resource_admission_command aitasks/metadata/project_config.yaml
# expect ONE quoted scalar line, no indented continuation
./.aitask-scripts/aitask_resource_admission.sh --task-id 1
# expect VERDICT:refuse / REASON:refused / DETAIL:no memory, exit 1
```

## Risk

### Code-health risk: medium
- The new block-shape check runs at **every** Step-7 pick; an over-triggering check would park every task with an exit-3 config error · severity: medium · → mitigation: inline post-phase negative_control_shape_check
- Dropping the blanket `yaml.safe_load` changes the stored type for all six Project Config keys at once, not only the one that broke · severity: low · → mitigation: inline post-phase negative_control_list_form
- The list-intent rule must hold at **three** call sites (save, editor-display, editor-save), and today all three get it wrong differently — a fix at any one of them is defeated by the other two (expanding `[ -f Makefile ]` into block form makes the *correct* save rule persist a list). Step 2/2a route all three through one predicate; a future fourth site, or a re-added scalar branch, would break it again · severity: medium · → mitigation: inline post-phase negative_control_list_form
- The rule is **asymmetric by necessity** — provenance for flow form, accept-on-sight for block form — so it is easy for a later reader to "tidy" it into symmetry and silently turn every quoted or commented list item into a scalar string · severity: medium · → mitigation: inline post-phase negative_control_list_form
- Removing the `notify` guard means a mistyped flow list saves as a literal string instead of erroring; visible on the row, but no longer refused · severity: low · → mitigation: inline post-phase negative_control_list_form

### Goal-achievement risk: low
- The task explicitly forbids regressing `verify_build`'s list form, and nothing in the current suite pins it · severity: medium · → mitigation: inline post-phase negative_control_list_form

### Planned mitigations
- timing: post-phase | name: negative_control_shape_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (block-shape check over-triggering) | desc: negative-control battery asserting every non-block shape (absent key, no config file, empty key, empty key followed by a top-level key, quoted scalar containing a colon, scalar containing a comma) still yields its ordinary verdict, never exit 3
- timing: post-phase | name: negative_control_list_form | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risk (verify_build list-form regression) plus code-health risks 2-4 | desc: through the real SettingsApp save path, pin that verify_build's canonical flow list still stores a YAML list while every bracket-leading shell command ([ -f Makefile ] && make, [[ -n "$CI" ]] && pytest, and the list-parsing [ -f Makefile ]) stores as an exact string, that a colon-bearing scalar stays a string, that a mistyped flow list saves as a string without aborting the rest of the save, that the stored-value/open-editor/save/reload cycle is lossless and idempotent for every discriminating shape (the scalar [ -f Makefile ] staying a scalar, a quoted path keeping its quotes, Unicode and one-item lists still round-tripping as lists), and that an edited BLOCK list persists as a list whatever its spelling — quoted items, trailing comments, re-indentation — while a flow-form edit that merely parses as a list stays a string

## Out of scope

The second t1670 finding — `yaml.safe_dump` stripping every comment from
`project_config.yaml` on save — is **already owned** by
`aitasks/t1260_settings_yaml_comment_preservation.md` (Ready). No new task;
do not fix it here.

Step 9 (Post-Implementation) handles cleanup, archival, and merge.
