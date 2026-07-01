---
Task: t1071_6_configurable_skill_authoring_conventions.md
Parent Task: aitasks/t1071_shadow_error_diagnosis_and_learn_skill_command.md
Sibling Tasks: aitasks/t1071/t1071_7_website_docs_learn_and_shadow.md
Archived Sibling Plans: aiplans/archived/p1071/p1071_2_learn_skill_standalone_command.md
Base branch: main
---

# Plan — t1071_6: Configurable skill-authoring-conventions source for `aitask-learn-skill`

## Context

`aitask-learn-skill/generate.md` (the shared "content → static SKILL.md" core) currently
**hard-codes** the skill-authoring-conventions source it applies:
`aireviewguides/aiagents/skill_authoring_best_practices.md` (the generic guide `ait setup`
installs from `seed/`). t1071_2's Change Request 1 established that a user's own generated
skill must follow this **generic** guide — never the framework-internal
`aidocs/framework/skill_authoring_conventions.md` — and flagged that the source should
become **configurable**. This task adds that configurability layer.

Depends on `t1071_2` (Done), which authored `generate.md` and left the "meant to be
configurable — a follow-up task adds a setting" note this task now discharges.

**Generalized per review.** A settings-defined **file path with a seeded-default fallback,
consumed by a skill** is not unique to this task: the framework already has one such key,
`doc_update.guide`, read by the `docs_updated` gate skill
(`.claude/skills/aitask-gate-docs-updated/SKILL.md`) via a fragile inline
`grep -A3 '^doc_update:'`. There is **no** shared path-resolution helper today
(`read_yaml_field` is top-level-only and strips neither quotes nor comments;
`config_utils.load_yaml_config` returns the whole dict). So this task adds a **general**
resolver as the canonical seam and wires `generate.md` onto it. **Per the user's scope
decision, the existing `docs_updated` gate is left on its current read here** (it is
behavior-sensitive and owned by t635_19); a coordinated follow-up migrates it onto the new
helper.

## Design decisions

- **Shared resolver = the canonical seam** (`config_utils.py`), not a one-off script.
  `resolve_config_path()` reads with PyYAML — the **same parser the settings TUI writes
  with** — so quotes, inline `# comments`, whitespace, dotted/nested keys, and any valid
  YAML are handled uniformly (a raw `grep` in markdown handles none of these, which was the
  review concern). A thin `aitask_resolve_config_path.sh` CLI lets skills shell out; Python
  consumers can import the function directly.
- **Flat top-level config key** `learn_skill_authoring_guide`.
  - *Why flat, not nested like `doc_update.guide`?* The settings TUI's Project Config tab is
    **schema-driven over top-level keys** (`_populate_project_tab` iterates
    `PROJECT_CONFIG_SCHEMA`; `save_project_settings` writes `data[key] =
    yaml.safe_load(raw)` — flat only; `default_profiles` is the lone special-cased nest). A
    flat key renders an editable control and round-trips with **zero TUI special-casing**.
    The resolver still supports dotted keys, so the future `doc_update.guide` migration is
    unaffected by this key being flat.
- **Scope-honest name.** `learn_skill_authoring_guide` names its sole consumer
  (`aitask-learn-skill`), not a generic "skill_authoring_guide" mistakable for the
  framework-internal conventions.
- **Fail-safe three-tier resolution**, encapsulated in the resolver: configured value (if
  it names a readable file) → seeded generic default (if readable) → empty (agent uses its
  own knowledge). Missing/blank key or missing file never breaks the flow. cwd-independent:
  the CLI derives the repo root from its own `BASH_SOURCE` location.
- **Claude-only edit for generate.md.** Only `.claude/skills/aitask-learn-skill/generate.md`
  exists on disk (cross-agent trees carry wrappers pointing at it). Precedent: `generate.md`
  already shells to `./.aitask-scripts/aitask_learn_wrappers.sh`, so a second helper call
  fits.

## Files to change

| File | Change |
|------|--------|
| `.aitask-scripts/lib/config_utils.py` | **NEW fn** `resolve_config_path(config_key, default_rel=None, root=None, check_readable=True)` — reads a dotted key from `project_config.yaml` (PyYAML), applies the seeded-default + readability fallback, returns a repo-root-relative path string or `None`. |
| `.aitask-scripts/aitask_resolve_config_path.sh` | **NEW** thin CLI over the fn: `<dotted.key> [default_rel]` → echoes the resolved readable path (empty line if none). Repo-root from `BASH_SOURCE` (cwd-independent). |
| `.aitask-scripts/settings/settings_app.py` | Add `learn_skill_authoring_guide` to `PROJECT_CONFIG_SCHEMA` (~line 212, after `lint_command`). Auto-renders + auto-saves via the generic project-config machinery. |
| `seed/project_config.yaml` | Add a documented, commented block (after `doc_update`) explaining the key + showing the default value, commented out so absence → default. |
| `.claude/skills/aitask-learn-skill/generate.md` | Replace the hard-coded default prose (lines ~18–32) with a single call to the resolver CLI + the "empty → own knowledge" fallback. |
| `tests/test_resolve_config_path.py` | **NEW** unit test for the resolver fn (nested + flat keys, quoted/commented values, default fallback, missing→None). |
| `tests/test_resolve_config_path_cli.sh` | **NEW** bash test for the CLI (cwd-independence, echo contract, + a `generate.md` consumption guard). |
| `tests/test_settings_learn_skill_guide.py` | **NEW** async app-mount test — proves the real Project Config **row** save persists/removes the key. |
| Follow-up task (created, not implemented) | Migrate the `docs_updated` gate's `doc_update.guide`/`extra_guides` read onto `resolve_config_path`; **coordination link** back to t635_19. |

## Step-by-step

### 1. `resolve_config_path()` in `.aitask-scripts/lib/config_utils.py`

```python
def resolve_config_path(config_key, default_rel=None, root=None, check_readable=True):
    """Resolve a settings-defined file path with a seeded-default fallback.

    config_key : dotted key into project_config.yaml (e.g. "doc_update.guide"
                 or a flat "learn_skill_authoring_guide").
    default_rel: repo-root-relative fallback path used when the key is unset or
                 its file is unreadable.
    Returns a repo-root-relative path string, or None when nothing usable exists.
    Paths are checked/returned relative to `root` (default: cwd).
    """
    base = Path(root) if root else Path.cwd()
    cfg = load_yaml_config(base / "aitasks/metadata/project_config.yaml")  # {} if missing
    # walk the dotted key
    val = cfg
    for part in config_key.split("."):
        val = val.get(part) if isinstance(val, dict) else None
    configured = val.strip() if isinstance(val, str) else None
    for cand in (configured, default_rel):
        if cand and (not check_readable or (base / cand).is_file()):
            return cand
    return None
```

Reuses the existing `load_yaml_config` (canonical loader) — no new YAML parsing. Nested +
flat both covered by the dotted-key walk; quotes/comments are handled by PyYAML upstream.

### 2. `.aitask-scripts/aitask_resolve_config_path.sh` (CLI)

`#!/usr/bin/env bash` + `set -euo pipefail`. Repo root from the script location
(cwd-independent). **Contract: ALWAYS exit 0 and print exactly one line** — the resolved
path, or an empty line if nothing usable exists *or the resolver itself fails* (missing
`python3`, missing PyYAML, import error, etc.). This is what makes the "cannot break the
learn flow" claim true: a broken Python environment yields an empty line, never a nonzero
exit that would abort the caller (review concern 1).

The heredoc lives inside a helper function with **no trailing operators on the `<<'PY'`
line** (that trailing-`2>/dev/null || true`-after-the-delimiter shape is exactly what to
avoid); all error handling is applied to the *function call*, outside the heredoc:

```bash
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
key="${1:?usage: aitask_resolve_config_path.sh <dotted.key> [default_rel]}"
default_rel="${2:-}"

_run_resolver() {
  PYTHONPATH="$REPO_ROOT/.aitask-scripts/lib" python3 - "$REPO_ROOT" "$key" "$default_rel" <<'PY'
import sys
try:
    from config_utils import resolve_config_path
    print(resolve_config_path(sys.argv[2], (sys.argv[3] or None), root=sys.argv[1]) or "")
except Exception:
    print("")
PY
}

out=""
if command -v python3 >/dev/null 2>&1; then
  # 2>/dev/null and || apply to the function CALL, cleanly outside the heredoc.
  out="$(_run_resolver 2>/dev/null)" || out=""
fi
printf '%s\n' "$out"
exit 0
```

Every failure funnels to a single empty line + exit 0: no python3 → the `if` is skipped;
PyYAML/import/parse error → the inner `try` prints empty (python still exits 0); a
catastrophic python crash → `|| out=""` on the substitution. `printf`/`exit 0` are
unconditional.

### 3. generate.md — call the resolver (replace lines ~18–32)

Replace the "By default, read the best-practices guide … a follow-up task adds a setting"
prose with (keeping the "these are NOT framework-internal conventions" framing):

> Apply **generic** skill-authoring best practices throughout. These are NOT the
> aitasks-framework-internal conventions (`aidocs/framework/skill_authoring_conventions.md`
> — stubs, profile variants, goldens — which a user's own skill must not adopt).
>
> Resolve the guide to apply by running, **from the repository root**:
>
> ```bash
> ./.aitask-scripts/aitask_resolve_config_path.sh learn_skill_authoring_guide \
>   aireviewguides/aiagents/skill_authoring_best_practices.md
> ```
>
> It returns the effective guide path — the project's configured
> `learn_skill_authoring_guide` (set via `ait settings` → Project Config) if it names a
> readable file, else the generic guide `ait setup` installs. **Read that file and apply
> it.** **If the command returns nothing OR fails for any reason** (no guide on disk, or
> the helper cannot run), fall back to your own knowledge of good skill authoring (clear
> `name`/`description`, a focused single responsibility, a scannable procedure, no inlined
> long sub-procedures).

Matches how `generate.md` already invokes its sibling helpers (`aitask_learn_wrappers.sh`,
`aitask_skill_verify.sh`) — the aitasks house convention is repo-root cwd (CLAUDE.md: "All
scripts cd to the repo root via `ait`"). The explicit "from the repository root" +
"returns nothing OR fails → fall back" wording closes review concerns 1 & 2. Drops the
now-discharged "a follow-up task adds a setting" sentence.

### 4. `PROJECT_CONFIG_SCHEMA` entry (settings_app.py, after `lint_command`, ~line 212)

```python
    "learn_skill_authoring_guide": {
        "summary": "Skill-authoring guide applied by /aitask-learn-skill",
        "detail": (
            "Path to the skill-authoring best-practices guide that "
            "/aitask-learn-skill (generate.md) applies when writing a generated "
            "skill. Leave blank to use the generic guide installed by ait setup "
            "(aireviewguides/aiagents/skill_authoring_best_practices.md). Never "
            "point this at aidocs/framework/skill_authoring_conventions.md — those "
            "framework-internal conventions must not be adopted by a user's own skill."
        ),
    },
```

No other TUI code needed: `_populate_project_tab` renders it as a `ConfigRow`,
`_handle_project_config_edit` edits it via `EditStringScreen`, `save_project_settings`
persists it (blank value pops the key → "unset" is representable).

### 5. seed/project_config.yaml — documented block (after the `doc_update` block)

```yaml
# ──────────────────────────────────────────────────────────────────────
# learn_skill_authoring_guide — Skill-authoring guide applied by
# /aitask-learn-skill when it generates a new skill (generate.md).
#
# `ait setup` installs the generic default below (from seed/reviewguides/);
# leave this UNSET to use that default. Set it to your project's own house
# guide to override. Do NOT point it at
# aidocs/framework/skill_authoring_conventions.md — those are framework-internal
# (stubs/profiles/goldens) and must not be adopted by a user's own skill.
#
# Example:
#   learn_skill_authoring_guide: aireviewguides/aiagents/skill_authoring_best_practices.md
# ──────────────────────────────────────────────────────────────────────

# learn_skill_authoring_guide:
```

### 6. Follow-up task (created, not implemented) — migrate `docs_updated` gate

Via the Batch Task Creation Procedure: a child/standalone task to rewrite the
`docs_updated` gate's **`doc_update.guide`** read
(`.claude/skills/aitask-gate-docs-updated/SKILL.md` inline `grep -A3`) to call
`aitask_resolve_config_path.sh` / `resolve_config_path`, and re-verify the gate. Add a
**bidirectional coordination link** to t635_19 (which owns that gate) per the coordination
convention. Created here, not implemented.

**Scope-honest limit (review concern 3):** `resolve_config_path` resolves a **single
scalar** path, so it covers `doc_update.guide` but **not** the list-valued
`doc_update.extra_guides`. The follow-up therefore targets `.guide` only; migrating
`extra_guides` (currently documented but unconsumed) would need a separate list-capable
companion resolver — the follow-up notes this as out of scope rather than advertising the
scalar helper as covering it.

### 7. Tests

- **`tests/test_resolve_config_path.py`** (pattern: `tests/test_config_utils.py`) — the
  general fn: flat key resolves; **nested `doc_update.guide` resolves** (proves dotted-key
  support for the future migration); **double-quoted value** and **value + trailing
  `# comment`** resolve to the clean path (PyYAML parity — the cases a grep fails);
  configured-but-missing-file → falls to default; unset + default present → default; unset +
  default absent → `None`.
- **`tests/test_resolve_config_path_cli.sh`** (framework bash style) — against a temp repo
  skeleton:
  - **Successful positive resolution (documented invocation):** run the CLI exactly as
    generate.md tells agents to — relative `./.aitask-scripts/aitask_resolve_config_path.sh
    …` **from the repo root**. Assert BOTH: (a) with `learn_skill_authoring_guide` **set** in
    the temp config to a real file → the CLI echoes that configured path; (b) with the key
    **unset** but the default file present → the CLI echoes the default path. This proves a
    non-empty success path through the CLI, not only the empty/error cases (closes review
    concerns 2 & the "catch a successful resolution" note).
  - **cwd-independence of config resolution:** run the CLI by absolute path from a foreign
    cwd; assert it still resolves the repo's config (the `BASH_SOURCE` root discovery).
  - **Always-exit-0 contract (review concern 1):** simulate a broken resolver — invoke with
    a stubbed `PATH` that hides `python3` — and assert exit status `0` **and** a single
    empty line (never a nonzero abort).
  - **generate.md consumption guard:** `grep -q 'aitask_resolve_config_path.sh' generate.md`
    present AND the old sole-source phrasing (`By default, read the best-practices guide`)
    absent.
- **`tests/test_settings_learn_skill_guide.py`** (async app-mount, per
  `tests/test_settings_project_groups_tab.py`) — mount `SettingsApp`, switch to the Project
  Config tab, set the `learn_skill_authoring_guide` `ConfigRow`'s `raw_value`, invoke
  `save_project_settings()` (the real DOM-row-collection + persist at settings_app.py:2500),
  assert `project_config.yaml` carries the key/value; blank it, save, assert removed; schema
  guard that the key ∈ `PROJECT_CONFIG_SCHEMA`. Exercises the exact code the user edits in
  `ait settings`, not a `config_utils` proxy.

## Verification

- `python3 tests/test_resolve_config_path.py` → PASS (flat + nested + quoted/commented +
  all fallback tiers).
- `bash tests/test_resolve_config_path_cli.sh` → PASS (cwd-independence, echo contract,
  generate.md consumption guard).
- `python3 tests/test_settings_learn_skill_guide.py` → PASS (real TUI row save/remove).
- `./.aitask-scripts/aitask_resolve_config_path.sh learn_skill_authoring_guide aireviewguides/aiagents/skill_authoring_best_practices.md`
  in this repo echoes the default path (key unset → tier 2).
- `shellcheck .aitask-scripts/aitask_resolve_config_path.sh` clean.
- `./.aitask-scripts/aitask_skill_verify.sh` passes (generate.md stays static markdown).
- Live acceptance (task's named criteria): in `ait settings` set the path, Save, confirm it
  lands in `project_config.yaml`, and confirm the resolver returns it — proving "set in
  `ait settings` persists and is read back by generate.md" end-to-end.
- Fresh-repo path: `seed/reviewguides/aiagents/skill_authoring_best_practices.md` exists →
  `ait setup` installs it → key unset → resolver returns the default. No behavior change for
  existing repos that never set the key.
- Confirm the docs-gate migration follow-up was created with the t635_19 coordination link.

## Risk

### Code-health risk: low
- Additive and consolidating: a new `config_utils` fn (reuses `load_yaml_config`), a thin
  CLI, one `PROJECT_CONFIG_SCHEMA` entry, a commented seed block, one `generate.md` call
  swap. No existing code paths change; the resolver reads via the same PyYAML loader the TUI
  writes with (parser parity, no bespoke parser). The general helper reduces future
  duplication (the docs-gate migration will delete its inline grep). · severity: low · →
  mitigation: TBD
- New runtime dependency: `generate.md` shells to the CLI (precedent:
  `aitask_learn_wrappers.sh`). The CLI's **always-exit-0 / single-line contract** (guards
  missing `python3`, swallows PyYAML/import/parse errors) plus generate.md's "returns
  nothing OR fails → own knowledge" wording mean a broken Python environment cannot abort
  the learn flow; both are test-backed (broken-`PATH` case). · severity: low · →
  mitigation: TBD

### Goal-achievement risk: low
- Requirements fully covered and each is test-backed: config key + defaulting (resolver fn +
  py test), `ait settings` control (schema entry + app-mount test), persistence (app-mount
  test), generate.md reads the configured value with fallback (CLI + consumption guard),
  fresh-repo default present & used. · severity: low · → mitigation: TBD
- The final "apply the guide" step is still agent judgment (as the `docs_updated` gate's
  guide-application is), but the *resolution* of which guide — the part this task adds — is
  now deterministic and unit-tested. · severity: low · → mitigation: TBD
- Generalization risk: building the shared helper but migrating only one consumer now could
  drift if the fn's contract is wrong for `doc_update.guide`. Mitigated by the py test
  asserting nested-key resolution explicitly, so the future migration inherits a proven
  contract. · severity: low · → mitigation: TBD

## Post-Implementation

Follow shared workflow **Step 9 (Post-Implementation)** for cleanup, gate verification
(`risk_evaluated`), archival, and merge.
