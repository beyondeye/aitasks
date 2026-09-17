---
Task: t1823_2_brainstorm_discuss_skill.md
Parent Task: aitasks/t1823_brainstorm_discuss_proposals_interactive_agent.md
Sibling Tasks: aitasks/t1823/t1823_1_*.md, aitasks/t1823/t1823_3_*.md, aitasks/t1823/t1823_4_*.md, aitasks/t1823/t1823_5_*.md
Archived Sibling Plans: aiplans/archived/p1823/p1823_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-17 14:45
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

## Verification notes (2026-09-17, against current main `aab0d5706`)

Confirmed: shadow `SKILL.md.j2` section line refs (What this is :7, Arguments :20,
Step 0 + maintainer comment :40-42, Shortcodes :223, Guardrail :359); shadow
procedures `plan-explain.md` / `plan-challenge.md` / `plan-assumptions.md` /
`round-preamble.md` exist; `VALID_PROFILE_SKILLS` at `settings_app.py:271-274`
with the prose copy at :263; `seed/project_config.yaml:391-392` valid-name comment;
`aitask_skill_resolve_profile.sh` needs no registry (any key resolves, default
`default`); rendered `*-/` dirs are gitignored; `aitask_audit_wrappers.sh`
tree names are `agents` / `opencode-skill` / `opencode-command`; nothing
`aitask-brainstorm-discuss` exists yet. Helper `--help` matches the t1823_1
grammar. Refinements folded in:

1. **Helper grammar is the final one** (t1823_1 note, acknowledged): token fields
   may be `!INVALID` / `!MISSING`; `MODULE:_umbrella` when unset; `TASK_FILE` may
   be `INVALID`; exit **2** (stderr, no stdout) for a malformed task num
   (`^[0-9]+(_[0-9]+)?$`) or node id. Step 0 must handle exit 2 (report the bad
   argument, stop) and must never pass zero node ids (that lists every node).
2. **`walk-check` prints nothing** — it only proves the closure renders. The
   closure-set assertion therefore imports `walk_closure(..., write=False)` from
   `.aitask-scripts/lib/skill_template.py` via `python -c` and prints each plan
   source path.
3. **`apply-wrapper` reads the description from the Claude stub**
   (`Error: Cannot read description … source SKILL.md missing`) — write
   `.claude/skills/aitask-brainstorm-discuss/SKILL.md` before generating the
   three other surfaces.
4. **Closure walker resolves refs against a repo root** (`discover_refs`: a
   `aitask-shadow/<f>.md` skill-relative ref resolves under
   `<repo_root>/.claude/skills/`). The negative-control mutant therefore needs a
   temp repo root holding a copy of BOTH the discuss skill dir and the shadow skill
   dir (plus `aitasks/metadata/profiles/default.yaml`), else the mutant ref would
   not resolve and the control would pass vacuously. The contract test asserts the
   mutant's walked closure actually contains a shadow source before asserting the
   checks fail (proves the control is live).
5. Our procedure files are referenced from `SKILL.md.j2` as **siblings** (bare
   `discuss-*.md`), which the walker leaves unrewritten — so Test 4 checks closure
   completeness per agent, not full-path rewrites.

## Steps

1. **Procedure files** in `.claude/skills/aitask-brainstorm-discuss/`, each opening
   with a two-line `**Advisory-only:**` header (proposal files, node YAML, session
   state are never edited; mutating `ait brainstorm` commands are never run). All
   Jinja-free.
   - `discuss-audience.md` — audience rule (the reader will not open the proposal:
     no file paths, function names or framework terms in simple-words output) and
     the "In plain words:" derivation order (compose the full answer first, then
     restate *that answer*). Adapted locally from the shadow companion's audience
     rules; provenance stated in words only.
   - `discuss-compare.md` — two depths. Simple: what each proposal is betting on,
     the one or two differences that matter, who should prefer which. Detailed:
     per-dimension table (reads node YAML dimensions lazily), trade-offs, what each
     makes easy/hard later, where they are actually equivalent. Needs ≥2 proposals;
     with one, say so and offer `>e` / `>h` instead.
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
   What this is (advisory contract up front) → Arguments (`<task_num> <node_id>...`,
   ≥1 node id required) → **Step 0 fast start** (run
   `./.aitask-scripts/aitask_brainstorm_context.sh <task_num> <node_id>...` once;
   parse lines per the final grammar; exit 2 → report and stop; skim each proposal
   only for a short differentiating title; list `A`, `B`, … + node id; skip the list
   for a single proposal; then the menu built by reading the capability section
   below, each entry led by its `>` shortcode; maintainer HTML comment forbidding a
   hardcoded copy; `SESSION_PATH:NOT_FOUND` / `PROPOSAL:NOT_FOUND` /
   `TASK_FILE:NOT_FOUND|INVALID` degrade gracefully) → Lazy context (node YAML via
   `META:`, `TASK_FILE:`, `--lineage` ancestors with `PARENTS:` per ancestor so
   synthesis branches stay distinguishable; `!INVALID` ancestors reported, never
   read — each fetched only when a request needs it) → Shortcode grammar (`>`
   required; `>?` reprints; embedded is fine, mentioned is not; a shortcode carries
   no extra authority) → Capability catalogue (`>c`, `>cd`, `>e`, `>q` inline,
   `>f`, `>h` inline lineage, `>?`; handles and node ids accepted as operands.
   **Ambiguous operand rule:** node ids share the handle charset
   (`SAFE_NODE_ID_RE` = `[A-Za-z0-9_.-]+` accepts a literal `A`), so when an
   operand matches a display handle of one proposal AND the node id of a
   *different* proposal, do not pick either — ask which one is meant (name both:
   "handle A → `<node_x>`" / "node id `A`") before reading anything. One short
   instruction; no new selector syntax or parser) →
   "Guardrail — advisory only (load-bearing)".
3. **Closure hygiene.** No file may contain a filename resolving under
   `.claude/skills/aitask-shadow/` (`aitask-shadow/<x>.md` or full path) — the
   closure walker follows every resolvable filename in the whole file.
4. **Stub `SKILL.md`** first (copy `.claude/skills/aitask-shadow/SKILL.md` shape;
   resolver key `brainstorm-discuss`; renderer slug `aitask-brainstorm-discuss`),
   then the three other surfaces via
   `./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper {agents,opencode-skill,opencode-command} aitask-brainstorm-discuss`
   — all four in the first commit.
5. **Registration**: `settings_app.py` `VALID_PROFILE_SKILLS` + prose copy;
   `seed/project_config.yaml` valid-name comment; add
   `test_brainstorm_discuss_is_a_known_skill` to
   `tests/test_settings_default_profiles_unknown_keys.py` (mirrors the shadow one).
6. **Goldens** (same commit): entry-point ×3 profiles (claude) under
   `tests/golden/skills/aitask-brainstorm-discuss/`, procedures `-default` under
   `tests/golden/procs/aitask-brainstorm-discuss/`, using the regeneration loop in
   `skill_authoring_conventions.md`.
7. **`tests/test_skill_render_aitask_brainstorm_discuss.sh`** modelled on
   `tests/test_skill_render_aitask_shadow.sh`: Test 0 inventory
   (`PROC_FILES_INVARIANT=(discuss-audience discuss-compare discuss-explain
   discuss-flaws)`), Test 1 entry goldens ×3, 1b agent invariance, 1p procedure
   `-default` goldens + profile×agent byte-equality, 2s shortcodes present and
   the ambiguous-operand clarification sentence present in every render, 3 no
   Jinja leaks, 3b no profile re-resolution tokens, 4 closure completeness per agent
   via `aitask_skill_render.sh --force`, 5 stub markers on 4 surfaces (resolver
   key `brainstorm-discuss`, `ARGUMENTS unchanged`), **plus a closure-set
   assertion**: `walk_closure(write=False)` sources == exactly the 5 authoring files.

### Post-phase (risk mitigations)
1. [skill_contract_test] `tests/test_brainstorm_discuss_skill_contract.sh`: `walk-write`
   the `default` variant into a temp root and assert — guardrail section names
   proposal files / node YAML / session state; Step 0 invokes
   `aitask_brainstorm_context.sh` and forbids up-front analysis; menu-derivation
   comment present and Step 0 holds no hardcoded shortcode list; every procedure has
   the `**Advisory-only:**` header; `===AITASK-CONCERNS===` absent from the whole
   rendered tree; no `aitask-shadow-*` dir rendered. Checks run as a function that
   returns a violation count (main shell, no `( … )` bodies). Negative control: a
   temp repo root with copies of the discuss AND shadow skill dirs, whose
   `discuss-audience.md` mentions `aitask-shadow/round-preamble.md`; assert the
   mutant's closure contains a shadow source (control is live) and the violation
   count is > 0 (mutant in isolation — never edit the real file).

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes (4 stub surfaces + wrapper parity)
- `bash tests/test_skill_render_aitask_brainstorm_discuss.sh` and `bash tests/test_brainstorm_discuss_skill_contract.sh` pass
- `bash tests/test_skill_dispatch_contract.sh`, `bash tests/test_opencode_skill_legacy_pointers.sh`, `bash tests/test_opencode_setup.sh` pass
- `bash tests/test_skill_render_aitask_shadow.sh` still passes (shadow untouched)
- `python -m pytest tests/test_settings_default_profiles_unknown_keys.py`, then `bash tests/run_all_python_tests.sh` — read only the last `PYTHON SUITE:` line
- Manual (t1823_6 covers it): `/aitask-brainstorm-discuss <N> <node_a> <node_b>` lists `A`/`B` with titles and the `>` menu before reading proposals in depth; after `>cd` and `>f`, the crew worktree `git status` is unchanged

## Post-implementation

Step 9 of the task workflow. Suggest separate aitasks for the Codex CLI and
OpenCode behavioural ports. Record final shortcodes in Final Implementation Notes
(t1823_5 documents them).

## Risk

### Code-health risk: low
- A future edit to a discuss file could name a shadow procedure path, silently dragging concern-fenced shadow procedures (wired to minimonitor concern forwarding) into this skill's rendered closure · severity: low (residual — addressed by inline post-phase skill_contract_test) · → mitigation: inline post-phase skill_contract_test
- Registration touches shared files (`settings_app.py`, `seed/project_config.yaml`) that concurrent sessions may edit; one-line additive edits, commit by path · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The skill's defining behaviours (fast start with no up-front analysis, lazy context, menu derived from the capability section, advisory-only guardrail) are prose with no mechanical guard; a later edit can silently drop them, and a contract test pins wording, not the live agent's behaviour · severity: low (residual — addressed by inline post-phase skill_contract_test) · → mitigation: inline post-phase skill_contract_test
- Operand ambiguity: a display handle (`A`) can equal a literal node id belonging to a different proposal, so the wrong proposal could be analysed · severity: low · → mitigation: none (designed in — Step 2 ambiguous-operand clarification rule, pinned by render Test 2s)
- Real agent behaviour (skim-only start, read-only discipline) is only observable live · severity: medium · → mitigation: none (manual-verification sibling t1823_6)

### Planned mitigations
- timing: post-phase | name: skill_contract_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: skill's defining behaviours are prose-only; shadow procedures could leak into the closure | desc: contract test pinning the rendered skill's load-bearing guardrail, fast-start and menu-derivation properties, closure hygiene, with a live negative control
