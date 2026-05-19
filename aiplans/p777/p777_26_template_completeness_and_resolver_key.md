---
Task: aitasks/t777/t777_26_template_completeness_and_resolver_key.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*.md
Archived Sibling Plans: aiplans/archived/p777/p777_*_*.md
Worktree: (current branch — profile fast, create_worktree: false)
Branch: main
Base branch: main
---

# Plan: t777_26 — Template Completeness + Resolver-Key Fix

## Context

A live `/aitask-pickn 741` session surfaced two distinct bugs in the
t777_6 pilot conversion:

**Bug A — Resolver key mismatch (stub vs body).** The stub calls
`aitask_skill_resolve_profile.sh aitask-pickn` (full slug). The
rendered body's Step 0a calls the same resolver with `pick` (short
name, the convention enshrined in `task-workflow/SKILL.md`'s
`skill_name` context variable). They look up different keys in
`userconfig.default_profiles:`, so the stub resolves to `default`
while the rendered body silently flips to `fast` mid-flow.

**Bug B — Template completeness.** The rendered body should NEVER
re-resolve the profile at runtime — the entire point of templated
dispatch is that profile is baked in at render time. But the source
templates still contain three runtime profile-resolution sites:

- `aitask-pickn/SKILL.md.j2` — Step 0 (`--profile` extract) and
  Step 0a ("Select Execution Profile").
- `task-workflown/SKILL.md` — Step 3b ("refresh execution profile").

These must be **deleted outright** from the source templates, not
wrapped in `{% if not profile %}` guards. Profile is mandatory at
render time (`skill_template.py::render_skill` always passes a
profile binding), so the no-profile path is dead code. The
authoring-reference doc in `aidocs/stub-skill-pattern.md` is the
canonical record of *why* these steps no longer exist; the template
itself stays lean.

The fix lands BEFORE t777_24 (manual re-verification of t777_6), so
the new test assertions become the regression gate.

## Approach

1. **Delete Step 0 and Step 0a** from
   `aitask-pickn/SKILL.md.j2`. Rewrite the Step 3 hand-off bullets
   for `active_profile` / `active_profile_filename` as render-time
   constants.
2. **Delete Step 3b** from `task-workflown/SKILL.md`.
3. **Fix the 4 stubs** to call the resolver with the short name
   (`pick`) instead of the full slug.
4. **Update `aidocs/stub-skill-pattern.md`** — §3b/§3c/§3d resolver
   examples use a `<resolver_key>` placeholder distinct from the
   slug; §3f checklist enshrines the short-name convention; new
   §3j codifies the template-completeness rule and its
   forbidden-token list.
5. **Regenerate the 12 + 3 affected goldens.**
6. **Tighten the two render tests** with forbidden-token
   `assert_not_contains` assertions and a stub short-name
   assertion.

## Key files to modify

- `.claude/skills/aitask-pickn/SKILL.md.j2` — delete Step 0 + Step
  0a (lines ~8–24); rewrite Step 3 hand-off constants.
- `.claude/skills/task-workflown/SKILL.md` — delete Step 3b (lines
  ~79–82).
- `.claude/skills/aitask-pickn/SKILL.md` — resolver call uses `pick`.
- `.agents/skills/aitask-pickn/SKILL.md` — same.
- `.gemini/commands/aitask-pickn.toml` — same.
- `.opencode/commands/aitask-pickn.md` — same.
- `aidocs/stub-skill-pattern.md` — §3b/§3c/§3d resolver placeholder,
  §3f checklist bullet, new §3j (template completeness).
- `tests/test_skill_render_aitask_pickn.sh` — forbidden-token Test
  3b + short-name assertion in Test 5.
- `tests/test_skill_render_task_workflown.sh` — forbidden-token
  Test 3b scoped to SKILL.md.
- 12 × `tests/golden/skills/aitask-pickn/SKILL-*-*.md` —
  regenerated.
- 3 × `tests/golden/procs/task-workflown/SKILL-*.md` — regenerated
  (claude only; the file uses sibling refs and is agent-byte-
  identical per existing Test 2).

## Implementation steps

### Step 1 — Edit `aitask-pickn/SKILL.md.j2`

Delete lines 8–24 of the template (the entire `### Step 0
(pre-parse): Extract --profile argument` and `### Step 0a: Select
Execution Profile` sections). The first surviving heading after the
deletion is `### Step 0b: Check for Direct Task Selection`.

Also delete the IMPORTANT note in Step 0b that references Step 0a:

```
**IMPORTANT:** Step 0a (profile selection) MUST complete before
Step 0b begins. Step 0b's behavior depends on the profile (e.g.,
`skip_task_confirmation`). Do NOT parallelize these steps.
```

— the dependency no longer exists; profile is baked in.

In the Step 3 hand-off (currently lines 213–214), replace:

```
- **active_profile**: The execution profile loaded in Step 0a (or null if no profile)
- **active_profile_filename**: The `<filename>` value from the scanner output for the selected profile (e.g., `fast.yaml` or `local/fast.yaml`), or null if no profile
```

with:

```
- **active_profile**: `{ name: {{ profile.name }} }` (baked in at render time)
- **active_profile_filename**: `{{ profile.name }}.yaml`
```

### Step 2 — Edit `task-workflown/SKILL.md`

Delete lines 79–82 (the `### Step 3b: refresh execution profile`
heading and its two paragraphs). Step 3 flows directly into Step 4.

Also clean the trailing References list — line ~596 currently reads:

```
- **Execution Profile Selection Procedure** (`execution-profile-selection.md`) — Interactive profile scan and selection. Referenced from Step 0a in calling skills and Step 3b.
```

Drop the "and Step 3b" suffix (the procedure is still referenced
from the source-of-truth `task-workflow/` files via Step 0a in
calling skills — that part stays accurate).

### Step 3 — Update the 4 stubs

In each stub file below, change:

```
./.aitask-scripts/aitask_skill_resolve_profile.sh aitask-pickn
```

to:

```
./.aitask-scripts/aitask_skill_resolve_profile.sh pick
```

Files:

- `.claude/skills/aitask-pickn/SKILL.md`
- `.agents/skills/aitask-pickn/SKILL.md`
- `.gemini/commands/aitask-pickn.toml`
- `.opencode/commands/aitask-pickn.md`

The render call `aitask_skill_render.sh aitask-pickn …` is
unchanged — that script keys off the slug, not the resolver key.

### Step 4 — Update `aidocs/stub-skill-pattern.md`

4a. **§3b/§3c/§3d resolver-call placeholder.** Update the resolver
invocation example in each stub-body code block from:

```
./.aitask-scripts/aitask_skill_resolve_profile.sh <skill_short_name>
```

to:

```
./.aitask-scripts/aitask_skill_resolve_profile.sh <resolver_key>
```

The render call still uses `<skill_short_name>` (the slug —
`aitask-pick`). Add a short note clarifying the two are distinct:

> Substitutions per stub:
> - `<skill_short_name>` — the skill slug, e.g., `aitask-pick`
>   (matches the dir name, the `name:` frontmatter, the slash
>   command).
> - `<resolver_key>` — the task-workflow short name used by the
>   rendered body to look up `userconfig.default_profiles.<key>`.
>   For `aitask-pick`/`aitask-pickn` this is `pick`. See §3f for
>   the full mapping rule.
> - `<agent_literal>` — `claude` for the Claude stub; `codex` for
>   the Codex stub (etc.).
> - `<agent_root>` — `.claude/skills` for Claude; `.agents/skills`
>   for Codex (etc.).

4b. **§3f checklist.** Append a new bullet:

> - **Resolver key uses the task-workflow short name** (`pick`,
>   `explore`, `qa`, `fold`, `review`, `pr-import`, `revert`, …),
>   NOT the full skill slug. The short name MUST match the
>   `skill_name` value that the body passes to
>   `execution-profile-selection.md`, so the stub and the rendered
>   body resolve the same `userconfig.default_profiles.<key>`
>   entry. Without this match, the stub picks one profile and the
>   body silently overrides to another at runtime.

4c. **New §3j — Template completeness (rendered body must not
re-resolve profile).** Add a new section after §3i:

> ## 3j. Template completeness — rendered body must not re-resolve profile
>
> The point of templated dispatch is that the rendered variant has
> the profile baked in at render time. The rendered body must
> therefore NEVER re-resolve the profile at runtime. In particular,
> the following procedures must NOT appear in the source templates
> (and consequently must not appear in any rendered output):
>
> - Step 0 / Step 0a "Select Execution Profile" — would re-run
>   `aitask_scan_profiles.sh`.
> - task-workflown Step 3b "refresh execution profile" — would
>   re-read the profile YAML.
> - Any equivalent "Execute the Execution Profile Selection
>   Procedure" hand-off inside the rendered closure.
>
> Profile is mandatory at render time — `skill_template.py` always
> passes a non-empty `profile` binding. The no-profile fallback is
> dead code and must be **deleted outright** from source templates,
> not wrapped in `{% if not profile %}…{% endif %}` guards (which
> just preserves dead documentation in the rendered output).
>
> **Forbidden tokens.** The following strings must NOT appear in
> any rendered output:
>
> - `aitask_scan_profiles.sh`
> - `Execute the Execution Profile Selection Procedure`
> - `Select Execution Profile`
> - `refresh execution profile`
>
> The two render tests
> (`tests/test_skill_render_aitask_pickn.sh`,
> `tests/test_skill_render_task_workflown.sh`) enforce this with
> `assert_not_contains` over all rendered combos. New skill
> conversions (t777_8..15) MUST extend these assertions to cover
> their entry-point goldens.

### Step 5 — Regenerate goldens

Use the same Python interpreter the tests use:

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
RENDER="$PYTHON .aitask-scripts/lib/skill_template.py"
PROFILES=(default fast remote)
AGENTS=(claude codex gemini opencode)

# aitask-pickn: 12 goldens (3 profiles × 4 agents)
for p in "${PROFILES[@]}"; do
  for a in "${AGENTS[@]}"; do
    $RENDER .claude/skills/aitask-pickn/SKILL.md.j2 \
      aitasks/metadata/profiles/$p.yaml $a \
      > tests/golden/skills/aitask-pickn/SKILL-$p-$a.md
  done
done

# task-workflown: 3 SKILL.md goldens (claude only — agent-byte-
# identical via existing Test 2). The 12 procs goldens for
# planning/satisfaction-feedback/etc are unaffected by this task.
for p in "${PROFILES[@]}"; do
  $RENDER .claude/skills/task-workflown/SKILL.md \
    aitasks/metadata/profiles/$p.yaml claude \
    > tests/golden/procs/task-workflown/SKILL-$p.md
done
```

### Step 6 — Tighten the tests

6a. In `tests/test_skill_render_aitask_pickn.sh`, insert (after
the existing Test 3, before Test 4):

```bash
# === Test 3b: rendered body must NOT re-resolve profile ===
echo "=== Test 3b: rendered body has no runtime profile-resolution tokens ==="
FORBIDDEN_TOKENS=(
    "aitask_scan_profiles.sh"
    "Execute the Execution Profile Selection Procedure"
    "Select Execution Profile"
    "refresh execution profile"
)
for profile in "${PROFILES[@]}"; do
    for agent in "${AGENTS[@]}"; do
        rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        for token in "${FORBIDDEN_TOKENS[@]}"; do
            assert_not_contains "rendered $profile × $agent has no '$token'" \
                "$token" "$rendered"
        done
    done
done
```

In existing Test 5, tighten the resolver assertion. Replace:

```bash
    assert_contains "$stub: resolve_profile invocation present" \
        "aitask_skill_resolve_profile.sh aitask-pickn" "$body"
```

with:

```bash
    assert_contains "$stub: resolve_profile uses short name 'pick'" \
        "aitask_skill_resolve_profile.sh pick" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use full slug" \
        "aitask_skill_resolve_profile.sh aitask-pickn" "$body"
```

6b. In `tests/test_skill_render_task_workflown.sh`, insert (after
existing Test 3):

```bash
# === Test 3b: rendered SKILL.md must NOT include Step 3b ===
echo "=== Test 3b: SKILL.md rendered output has no Step 3b ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$STAGED_DIR/SKILL.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_not_contains "SKILL.md $profile: no Step 3b heading" \
        "Step 3b: refresh execution profile" "$rendered"
    assert_not_contains "SKILL.md $profile: no scan-profiles call" \
        "aitask_scan_profiles.sh" "$rendered"
    assert_not_contains "SKILL.md $profile: no refresh profile prose" \
        "refresh execution profile" "$rendered"
done
```

### Step 7 — Verification

1. `bash tests/test_skill_render_aitask_pickn.sh` — passes (incl.
   new Test 3b + tightened Test 5).
2. `bash tests/test_skill_render_task_workflown.sh` — passes (incl.
   new Test 3b).
3. `./.aitask-scripts/aitask_skill_verify.sh` — passes (structural
   integrity across rendered tree).
4. **Manual** (deferred to t777_24, the regression-gate
   manual-verification task per the task notes): live
   `/aitask-pickn --profile default 16` and `/aitask-pickn
   --profile fast 16` — confirm no `aitask_scan_profiles.sh` or
   "refresh execution profile" appears in the tool-call log; stub
   and rendered-body profile resolution agree end-to-end.

## Notes for sibling tasks

- "Drop legacy no-profile path outright" is the canonical
  refactoring pattern for runtime profile-resolution dead code in
  templated skills. No `{% if not profile %}` wraps — the
  template stays lean, and the *why* lives in
  `aidocs/stub-skill-pattern.md` §3j.
- The short-name resolver-key convention is now part of the §3f
  authoring checklist. Every per-skill conversion (t777_8..15)
  needs to know the short name (e.g., `explore` for
  `aitask-explore`, `qa` for `aitask-qa`) before authoring its
  stubs.
- The forbidden-token assertions become a shared regression gate.
  Future per-skill conversion tests SHOULD copy the Test 3b block
  from `test_skill_render_aitask_pickn.sh`.

## Reference to Step 9 (Post-Implementation)

Standard task-workflow Step 9 applies: archival via
`aitask_archive.sh 777_26`, plan file consolidation with "Final
Implementation Notes". No separate branch (profile
`create_worktree: false`), so the Step 9 merge approval is a no-op.
