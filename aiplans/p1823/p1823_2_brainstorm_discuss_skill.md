---
Task: t1823_2_brainstorm_discuss_skill.md
Parent Task: aitasks/t1823_brainstorm_discuss_proposals_interactive_agent.md
Sibling Tasks: aitasks/t1823/t1823_1_*.md, aitasks/t1823/t1823_3_*.md, aitasks/t1823/t1823_4_*.md, aitasks/t1823/t1823_5_*.md
Archived Sibling Plans: aiplans/archived/p1823/p1823_*_*.md
Base branch: main
Output branch: main
---

# t1823_2 — `aitask-brainstorm-discuss` skill (profile-aware, advisory-only)

## Context

The interactive agent launched by the brainstorm TUI's Discuss op runs this skill
with argv `<task_num> <node_id>...`. It must start fast (list proposals with
handles, offer a menu, analyse nothing up front), fetch context lazily through
t1823_1's helper, and never modify proposals, node YAML or session state.

Read first: `aidocs/framework/skill_authoring_conventions.md`,
`aidocs/framework/stub-skill-pattern.md`, and the archived plan of t1823_1 (final
helper output grammar). Parent plan:
`aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.

## Steps

1. **Procedure files** in `.claude/skills/aitask-brainstorm-discuss/`, each opening
   with a two-line `**Advisory-only:**` header (proposal files, node YAML, session
   state are never edited; mutating `ait brainstorm` commands are never run):
   - `discuss-audience.md` — audience rule (the reader will not open the proposal:
     no file paths, function names or framework terms in simple-words output) and
     the "In plain words:" derivation order (compose the full answer first, then
     restate *that answer*). Adapted locally from the shadow companion's audience
     rules; provenance stated in words only.
   - `discuss-compare.md` — two depths. Simple: what each proposal is betting on,
     the one or two differences that matter, who should prefer which. Detailed:
     per-dimension table (reads node YAML dimensions lazily), trade-offs, what each
     makes easy/hard later, where they are actually equivalent.
   - `discuss-explain.md` — adapted from shadow plan-explain steps 2-6: identify the
     technical subjects the proposal rests on → offer per-subject depth
     (`AskUserQuestion`, multiSelect, "All"/"None") → intro + motivation per subject
     → walk the proposal in plain language leading with outcomes → invite follow-ups.
     "Simple words but complete": nothing in the proposal is skipped.
   - `discuss-flaws.md` — structural design-flaw & risk check for a *design
     proposal*: six attack axes (regressions to existing behaviour, missed edge
     cases, wrong shape for the goal, blast radius / parts changed unaware,
     verification gaps, unstated dependencies) + five assumption buckets
     (environment/tooling, data/inputs, behaviour of other code, sequencing, intent/
     scope), each finding with severity, load-bearing-or-peripheral, and an impact
     vector (`Improves:` / `Worsens:` / `Effort:`). **Plain prose/markdown output —
     no sentinel fences, no round snapshots, no rejection store.**
2. **`SKILL.md.j2`** (frontmatter `name: aitask-brainstorm-discuss-{{ profile.name }}`,
   description identical to the stub, `user-invocable: true`; no other Jinja):
   What this is (advisory contract up front) → Arguments → **Step 0 fast start**
   (run `./.aitask-scripts/aitask_brainstorm_context.sh <task_num> <node_id>...` once;
   skim each proposal only for a short differentiating title; list `A`, `B`, … +
   node id; skip the list for a single proposal; then the menu built by reading the
   capability section below, each entry led by its `>` shortcode; maintainer HTML
   comment forbidding a hardcoded copy; NOT_FOUND lines degrade gracefully) →
   Lazy context (node YAML, `TASK_FILE:`, `--lineage` ancestors with `PARENTS:` per
   ancestor so synthesis branches stay distinguishable — each fetched only when a
   request needs it) → Shortcode grammar (`>` required; `>?` reprints; embedded is
   fine, mentioned is not; a shortcode carries no extra authority) → Capability
   catalogue (`>c`, `>cd`, `>e`, `>q` inline, `>f`, `>h` inline lineage, handles and
   node ids accepted as operands) → "Guardrail — advisory only (load-bearing)".
3. **Closure hygiene.** No file may contain a filename resolving under
   `.claude/skills/aitask-shadow/` (`aitask-shadow/<x>.md` or full path) — the
   closure walker follows every resolvable filename in the whole file.
4. **Stub `SKILL.md`** (copy `.claude/skills/aitask-shadow/SKILL.md` shape; resolver
   key `brainstorm-discuss`; renderer slug `aitask-brainstorm-discuss`) and the
   three other surfaces via
   `./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper {agents,opencode-skill,opencode-command} aitask-brainstorm-discuss`
   — all four in the first commit.
5. **Registration**: `settings_app.py` `VALID_PROFILE_SKILLS` + prose copy;
   `seed/project_config.yaml` valid-name comment; adjust
   `tests/test_settings_default_profiles_unknown_keys.py` if it pins the set.
6. **Goldens** (same commit): entry-point ×3 profiles (claude) under
   `tests/golden/skills/aitask-brainstorm-discuss/`, procedures `-default` under
   `tests/golden/procs/aitask-brainstorm-discuss/`, using the regeneration loop in
   `skill_authoring_conventions.md`.
7. **`tests/test_skill_render_aitask_brainstorm_discuss.sh`** modelled on the trail/
   shadow render tests: Test 0 inventory (`PROC_FILES_INVARIANT=(discuss-audience
   discuss-compare discuss-explain discuss-flaws)`), golden diffs, agent invariance,
   Jinja-free invariance, per-agent ref rewrites, stub markers, **plus a closure-set
   assertion**: `walk-check` resolved sources == exactly the 5 authoring files.

### Post-phase (risk mitigations)
1. [skill_contract_test] `tests/test_brainstorm_discuss_skill_contract.sh`: `walk-write`
   the `default` variant into a temp root and assert — guardrail section names
   proposal files / node YAML / session state; Step 0 invokes
   `aitask_brainstorm_context.sh` and forbids up-front analysis; menu-derivation
   comment present and Step 0 holds no hardcoded shortcode list; every procedure has
   the `**Advisory-only:**` header; `===AITASK-CONCERNS===` absent from the whole
   rendered tree; no `aitask-shadow-*` dir rendered. Negative control: a temp copy
   of the skill whose `discuss-audience.md` mentions `aitask-shadow/round-preamble.md`
   makes the test fail (mutant in isolation — never edit the real file).

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes (4 stub surfaces + wrapper parity)
- `bash tests/test_skill_render_aitask_brainstorm_discuss.sh` and `bash tests/test_brainstorm_discuss_skill_contract.sh` pass
- `bash tests/test_skill_dispatch_contract.sh`, `bash tests/test_opencode_skill_legacy_pointers.sh`, `bash tests/test_opencode_setup.sh` pass
- `bash tests/test_skill_render_aitask_shadow.sh` still passes (shadow untouched)
- `/aitask-brainstorm-discuss <N> <node_a> <node_b>` in Claude Code lists `A`/`B` with titles and the `>` menu before reading proposals in depth
- After a full `>cd` and `>f` round, `git status` in `.aitask-crews/crew-brainstorm-<N>` is clean

## Post-implementation

Step 9 of the task workflow. Suggest separate aitasks for the Codex CLI and
OpenCode behavioural ports. Record final shortcodes in Final Implementation Notes
(t1823_5 documents them).
