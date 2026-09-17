---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [skills, codeagent]
gates: [risk_evaluated]
anchor: 1823
followup_kind: upstream_defect
created_at: 2026-09-17 23:09
updated_at: 2026-09-17 23:09
---

## Origin

Spawned from t1831 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_audit_wrappers.sh:245,~250,~357` (`render_agents_skill`,
  `render_opencode_skill`, `render_opencode_command`) — all three derive the
  resolver key as `${skill#aitask-}` and ignore the `resolver_key.txt` sidecar
  that `aitask_skill_verify.sh::_resolver_key_for()` honours. No skill ships a
  sidecar today, so the two agree by accident; the first one to do so would get
  generated wrappers whose resolver call fails the verifier's
  `aitask_skill_resolve_profile.sh <key>` grep.
- `.opencode/commands/aitask-pick.md`, `aitask-pickrem.md`, `aitask-pickweb.md` —
  the committed `description:` has backticks stripped relative to the source
  `.claude/skills/<skill>/SKILL.md` description, so a regenerated command differs
  from the committed file in the frontmatter. Cosmetic (dispatch is unaffected),
  but it blocks a byte-exact regeneration check over the whole templated set —
  `tests/test_audit_wrappers_render_opencode_command.sh` Test 2 therefore compares
  bodies rather than whole files, and only Test 1 pins two files byte-for-byte.

## Diagnostic context

t1831 added the `_skill_is_templated` branch to `render_opencode_command` so a
templated skill's OpenCode command is a profile-aware stub rather than the legacy
`@`-include of the Claude stub. While pinning the generated output against the 14
committed `.opencode/commands/aitask-*.md` files, two things showed up:

- The resolver key is derived in two places with two different rules. The
  verifier has a sidecar override (`.claude/skills/<skill>/resolver_key.txt`,
  documented in `aidocs/framework/stub-skill-pattern.md` §3f); the three wrapper
  renderers hardcode the prefix strip. `ls .claude/skills/*/resolver_key.txt`
  currently matches nothing, which is the only reason `aitask_skill_verify.sh`
  passes on generated wrappers.
- Three committed commands differ from a fresh render in the description only.
  Confirmed with
  `diff <(./.aitask-scripts/aitask_audit_wrappers.sh render-wrapper opencode-command aitask-pick) .opencode/commands/aitask-pick.md`
  → the committed line reads `... from the aitasks/ directory.` where the source
  SKILL.md reads `` ... from the `aitasks/` directory. ``.

## Suggested fix

Factor the resolver-key derivation into one shared helper that reads the sidecar
(the verifier's `_resolver_key_for()` is the existing implementation — consider
moving it into `.aitask-scripts/lib/` so both callers use it) and have the three
renderers call it. Then decide the description question: either regenerate the
three drifted commands so the whole templated set is byte-exact (and tighten
`tests/test_audit_wrappers_render_opencode_command.sh` Test 2 from body to
whole-file comparison), or record why the stripped form is intentional.
