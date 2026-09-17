---
priority: medium
effort: high
depends: [t1823_1]
issue_type: feature
status: Ready
labels: [ait_brainstorm, skills, codeagent]
gates: [risk_evaluated]
anchor: 1823
created_at: 2026-09-17 09:50
updated_at: 2026-09-17 09:50
---

## Context

Parent t1823 adds a brainstorm-TUI node operation that launches an interactive,
**strictly advisory / read-only** code agent over the proposal file(s) of the
selected node(s), so the user can compare proposals (simple words or in depth),
ask questions, get a plain-language-but-complete explanation, and have them
checked for structural design flaws and risks. This child authors the skill that
agent runs: `aitask-brainstorm-discuss`. It is modelled on the shadow agent's
stub + `.md.j2` profile-aware shape, but anchored on brainstorm proposals instead
of a followed pane.

Sibling t1823_1 (landed first) provides
`./.aitask-scripts/aitask_brainstorm_context.sh [--lineage] <task_num> [<node_id>...]`
— read its archived plan's Final Implementation Notes for the final output
grammar (`SESSION_PATH:` / `TASK_FILE:` / `NODE:…|PROPOSAL:…|META:…|PARENTS:…` /
`ANCESTOR:…`, always exit 0, parse lines).

Parent plan: `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.
**Read first:** `aidocs/framework/skill_authoring_conventions.md`,
`aidocs/framework/stub-skill-pattern.md`.

## Settled decisions (do not re-litigate)

- Authority: advisory only. Never edit proposal files, node YAML (`br_nodes/`),
  session state, and never run a mutating `ait brainstorm` command.
- argv: `<task_num> <node_id>...` (ids only). 1 or more nodes.
- Context is **lazy**: node YAML, the brainstormed task file, ancestor proposals
  (`--lineage`) are read on demand, NOT at startup.
- **Own procedure files with NO cross-skill reference into `aitask-shadow/`.**
  `skill_template.py` `discover_refs`/`walk_closure` scan whole files and follow
  every filename that resolves — a "sections 1-2 only" restriction does not
  restrict the closure. Shadow's `round-preamble.md` names `plan-challenge.md`,
  `plan-assumptions.md`, `impl-challenge.md`, `plan-diagnose-errors.md`,
  `concern-format.md` (all carrying `===AITASK-CONCERNS===` fences wired to
  minimonitor concern-forwarding) — referencing it would drag them in. Adapt the
  small audience rules locally instead.
- Jinja surface: `{{ profile.name }}` only. No new profile key. Do NOT set
  `prerender_for_headless`.

## Key files to create / modify

Authoring (committed):
- `.claude/skills/aitask-brainstorm-discuss/SKILL.md` — stub; resolver key
  `brainstorm-discuss` (the default `${skill#aitask-}`; do NOT add a
  `resolver_key.txt` sidecar — `tests/test_opencode_skill_legacy_pointers.sh`
  ignores sidecars).
- `.claude/skills/aitask-brainstorm-discuss/SKILL.md.j2`
- `.claude/skills/aitask-brainstorm-discuss/discuss-compare.md` (simple / detailed)
- `.claude/skills/aitask-brainstorm-discuss/discuss-explain.md`
- `.claude/skills/aitask-brainstorm-discuss/discuss-flaws.md`
- `.claude/skills/aitask-brainstorm-discuss/discuss-audience.md`
- **All 4 stub surfaces in the FIRST commit** (the trail skill shipped 3 and broke
  parity for 5 days): `.agents/skills/aitask-brainstorm-discuss/SKILL.md`
  (`--agent codex`, reads `…-<profile>-codex-/`), `.opencode/commands/aitask-brainstorm-discuss.md`,
  `.opencode/skills/aitask-brainstorm-discuss/SKILL.md`. Generate with
  `./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper <tree> aitask-brainstorm-discuss`.
  These are dispatch stubs, not the behavioural ports (ports are follow-ups).
Registration:
- `.aitask-scripts/settings/settings_app.py` `VALID_PROFILE_SKILLS` (~:272) + the
  prose copy (~:263); `seed/project_config.yaml` valid-name comment (~:391).
  Check `tests/test_settings_default_profiles_unknown_keys.py`.
Goldens + tests:
- `tests/golden/skills/aitask-brainstorm-discuss/SKILL-{default,fast,remote}-claude.md`
- `tests/golden/procs/aitask-brainstorm-discuss/<proc>-default.md` (procedures are
  profile-invariant → single `-default` golden + byte-equality invariance assertion)
- `tests/test_skill_render_aitask_brainstorm_discuss.sh`
- `tests/test_brainstorm_discuss_skill_contract.sh`

## Reference files for patterns

- `.claude/skills/aitask-shadow/SKILL.md` (22-line stub — copy the shape exactly)
  and `SKILL.md.j2`: "What this is" with the advisory contract up front (:7-18);
  Arguments (:20-38); Step 0 greeting + capability menu **derived at runtime from
  the capability section**, with the maintainer HTML comment forbidding a
  hardcoded copy (:40-72); shortcode grammar (:223-253 — `>` always required,
  `>?` reprints, "embedded is fine; mentioned is not", "a shortcode carries no
  authority the same request in words would not have"); capability catalogue
  bullets of the form "`>code` — **Title** ("synonyms…") → read and follow
  `<file>.md`" (:216-357); trailing "Guardrail — advisory only (load-bearing)" (:359-364).
- Content to ADAPT (copy the ideas, not the file references):
  `aitask-shadow/plan-explain.md` steps 2-6 → `discuss-explain.md`;
  `plan-challenge.md` six attack axes (regressions, missed edge cases, wrong shape,
  blast radius, verification gaps, unstated dependencies) + impact vector
  (`Improves:`/`Worsens:`/`Effort:`) and `plan-assumptions.md` five buckets
  (environment/tooling, data/inputs, behaviour of other code, sequencing, intent/scope)
  → `discuss-flaws.md`, re-framed for a *design proposal* (not an implementation
  plan), **plain prose output — no concern fences, no round snapshots**;
  `round-preamble.md` §1 audience rule + §2 "In plain words:" derivation order →
  `discuss-audience.md`.
- `tests/test_skill_render_aitask_trail.sh`, `tests/test_skill_render_aitask_shadow.sh`
  (Test 0 procedure inventory, Test 1 golden diff ×3 profiles, 1b agent
  invariance, 1p procedure goldens, 1i Jinja-free invariance, Test 4 per-agent ref
  rewrites, Test 5 stub markers); `tests/test_trail_skill_contract.sh`.
- Goldens regeneration loop: `skill_authoring_conventions.md` "Regenerate goldens
  after any `.md.j2` or closure edit" (:484-497). Goldens land in the SAME commit
  as the template.

## Implementation plan

1. Write the four procedure files. Each opens with a two-line `**Advisory-only:**`
   header restating the contract in THIS task's terms (proposal files, node YAML,
   session state) so it survives a partial read.
2. Write `SKILL.md.j2`:
   - **Step 0 — fast start.** Run the context helper ONCE for the passed ids. For
     each proposal read only enough for a short differentiating title (first
     heading / first lines — a skim, not an analysis). List them with a handle
     (`A`, `B`, …) plus node id. With ONE proposal, skip the list ceremony. Then
     present the capability menu built by reading the skill's own capability
     section, each entry led by its `>` shortcode. **Do not process/analyse
     proposals up front.** Handle `SESSION_PATH:NOT_FOUND` / `PROPOSAL:NOT_FOUND`
     gracefully (say so, continue with what resolved).
   - **Lazy context section**: node YAML (dimensions, parents), the brainstormed
     task (`TASK_FILE:`), ancestor proposals via `--lineage` — each fetched only
     when a request needs it. Explain that `ANCESTOR:` lines carry `PARENTS:` so a
     synthesis node's contributing branches can be told apart.
   - **Capability catalogue** (single source of truth for the menu): `>c` compare
     in simple words, `>cd` compare in depth, `>e` explain a proposal in simple
     words but fully, `>q` free-form Q&A (inline), `>f` structural design-flaw &
     risk check, `>h` how this proposal evolved (lineage; inline), `>?` reprint.
     Accept handles (`>e B`) and node ids.
   - **Guardrail — advisory only (load-bearing)** as the closing section.
3. **Closure hygiene (load-bearing).** No file in this skill may contain a filename
   that resolves under `.claude/skills/aitask-shadow/` — never
   `aitask-shadow/<file>.md`, never a full `.claude/skills/aitask-shadow/...` path.
   State provenance in words ("adapted from the shadow companion's audience
   rules") without a resolvable path. Shadow's files are NOT edited, so shadow's
   goldens stay untouched.
4. Stubs ×4, registration edits, goldens, tests.
5. Post-phase risk mitigation **[skill_contract_test]** (from the parent plan's
   `### Planned mitigations`): `tests/test_brainstorm_discuss_skill_contract.sh`
   renders the `default` variant via `walk-write` into a temp root and asserts:
   the "Guardrail — advisory only (load-bearing)" section names proposal files /
   node YAML / session state; Step 0 runs `aitask_brainstorm_context.sh` and
   forbids up-front analysis; the menu-derivation maintainer comment is present
   and Step 0 contains no hardcoded shortcode list; every procedure file carries
   the `**Advisory-only:**` header; the string `===AITASK-CONCERNS===` appears
   nowhere in the **walked closure** (iterate the rendered per-profile tree, not
   just the authoring dir) and no `aitask-shadow-*` directory is rendered as a
   side effect. **Negative control:** a temp copy of the skill whose
   `discuss-audience.md` mentions `aitask-shadow/round-preamble.md` must make the
   test fail (run the mutant in isolation; never edit the real file to prove it).

## Verification

- **Verify the actual closure inventory, not the intent:** `skill_template.py
  walk-check` for the template; assert the closure's resolved source set is
  exactly `{SKILL.md.j2, discuss-compare.md, discuss-explain.md, discuss-flaws.md,
  discuss-audience.md}` — any `aitask-shadow` path in the walked set is a failure.
- `./.aitask-scripts/aitask_skill_verify.sh` (4-surface stub check + wrapper parity)
- `bash tests/test_skill_render_aitask_brainstorm_discuss.sh`
- `bash tests/test_brainstorm_discuss_skill_contract.sh`
- `bash tests/test_skill_dispatch_contract.sh`,
  `bash tests/test_opencode_skill_legacy_pointers.sh`, `bash tests/test_opencode_setup.sh`
- `bash tests/test_skill_render_aitask_shadow.sh` still passes (shadow untouched)
- `bash tests/run_all_python_tests.sh` — read only the last `PYTHON SUITE:` line

## Follow-ups to suggest at the end (per CLAUDE.md)

Separate aitasks for the Codex CLI and OpenCode behavioural ports of this skill.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1823_1** id=2026-09-17T09:52:49Z.05cbd47b937116aeb739d292 from=t1823_1 from_verified=yes at=2026-09-17T09:52:48Z base=aab0d57067adfae49af46312c376529721b2c6e3 base_branch=main dirty=yes host=omg16
>
> | The resolver's output format changed from the one quoted in your task body, as of commit aab0d5706 (t1823_1). The final format is recorded in the "Notes for sibling tasks" bullet of t1823_1's plan, in Final Implementation Notes (aiplans/archived/p1823/p1823_1_discuss_context_helper.md once archived). What changed:
> | 
> | - Token fields (an ancestor id, each PARENTS entry, MODULE) are either an id matching [A-Za-z0-9_.-]+ or a "!"-prefixed marker: "!INVALID" (the value exists but is unsafe) or "!MISSING" (MODULE only: the ancestor's YAML can't be read). MODULE is "_umbrella" when unset.
> | - An unsafe ancestor always prints as: ANCESTOR:<node>|!INVALID|DEPTH:<n>|MODULE:!MISSING|PARENTS:|PROPOSAL:NOT_FOUND
> | - TASK_FILE is <path>|NOT_FOUND|INVALID. It is INVALID unless it is exactly the task's own file (aitasks/t<N>_<slug>.md or aitasks/t<P>/t<P>_<C>_<slug>.md).
> | - NODE lines always have 4 |-separated fields and ANCESTOR lines 6; no field can contain "|", "," or a newline.
> | - Exit 0 for every lookup result. Exit 2 (stderr message, no stdout) for a malformed task number (must match ^[0-9]+(_[0-9]+)?$) or node id. With no node ids, every node is listed. Paths are repo-relative and the helper works from any directory.
> | 
> | This is advisory: check the format against the helper's header comment or `--help` before relying on it.
