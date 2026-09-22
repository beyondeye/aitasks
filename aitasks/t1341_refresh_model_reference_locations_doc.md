---
priority: low
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [docs, codeagent]
gates: [risk_evaluated]
anchor: 1307
followup_kind: risk_mitigation
created_at: 2026-07-29 21:38
updated_at: 2026-08-13 23:06
boardidx: 100352
---

## Origin

Risk-mitigation ("after") follow-up for t1318, created at Step 8d after
implementation landed.

## Risk addressed

*Goal-achievement risk (low) — partly-untrustworthy promotion checklist:*

> The promotion checklist is only **partially** refreshed: registering these
> three files in a doc whose other `opus4_*` line references are stale leaves
> the next promoter with a partly-untrustworthy checklist.

`aidocs/framework/model_reference_locations.md` is the canonical "what to touch
when promoting a model to default" registry. Its omission of three test files is
exactly why t1241 promoted the defaults to `claudecode/opus5` and left them red
(fixed in t1318). t1318 registered those three files but deliberately scoped out
the rest of the doc's staleness.

## Known stale content

- Line-number references to `opus4_6` / `opus4_7` / `opus4_8` throughout —
  reported stale at (approximately) lines 36, 44-49, 74, 85-90, 109-115, 228,
  354-355. **Re-derive these; do not trust the list.** Line numbers shift, and
  t1318 already inserted rows into §7.
- §7 classifies `tests/test_codeagent.sh` lines 127-144 etc. as
  `needed_for_promote` using line numbers that predate several edits.
- The §1 registry tables and the "Summary matrix" counts should be re-checked
  against the current `models_*.json` (12 claudecode models registered today).

## Sweep both spellings

**Critical, learned the hard way in t1318:** a model reference appears in two
distinct spellings and a sweep must cover both.

- Agent-string form: `claudecode/opus4_8`
- **cli_id form: `claude-opus-4-8`** (dashes)

t1318's planning sweep searched only the first form and consequently missed two
live stale assertions (`tests/test_codeagent_trail.sh:88`,
`tests/test_codeagent_work_report.sh:80`), which surfaced only when the suite was
run. Any audit driven by this doc must grep for both, e.g.:

```bash
grep -rnE 'claudecode/(opus|sonnet|haiku)4_[0-9]|claude-(opus|sonnet|haiku)-4-[0-9]' \
  tests/ .aitask-scripts/ aidocs/ website/content/ seed/
```

## Goal

Refresh the doc so a future promoter can trust it end to end:

1. Re-derive every line reference against current file contents.
2. Re-check each `needed_for_promote` / `informational_only` / `needed_for_add`
   tag — some entries have since become promotion-proof.
3. Add the two-spelling sweep guidance above to the doc itself, so the next audit
   does not repeat t1318's miss.
4. Preserve the t1318 note in §7 and its cross-reference to
   `aidocs/framework/testing_conventions.md` (see t1339, which adds the
   testing-conventions side of that link).

## Verification

- Every line number cited in the doc resolves to the content it claims (spot-check
  each cited file:line).
- The two-spelling grep above is documented in the doc and returns no
  *default-coupled assertion* hits that the doc does not list.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1762** id=2026-09-10T08:46:47Z.db2d1bd560c75378fbaa58db from=t1762 from_verified=yes at=2026-09-10T08:46:47Z base=2c255e2287aa0828eb919c0c0ce39bcb71e3ecbc base_branch=main dirty=yes host=omg16
>
> | Context from t1762 (scoping plain `git commit` instructions on main; code commit 2c255e228). Two spots in aidocs/framework/model_reference_locations.md look stale and fall inside your refresh. Line numbers are as of this note's base commit.
> | 
> | - Promote-mode step 8 (~lines 227-229) commits aitask_codeagent.sh, brainstorm/brainstorm_crew.py, aitask_brainstorm_init.sh and seed/codeagent_config.json. For the same promote step, .claude/skills/aitask-add-model/SKILL.md:164-168 commits lib/agent_string.sh and aitask_codeagent.sh, and uses a `refactor:` subject where the doc uses `feature:`.
> | - Promote-mode step 6 locates DEFAULT_AGENT_STRING at aitask_codeagent.sh line 21. The add-model skill (lines 14, 107, 193) says it lives in .aitask-scripts/lib/agent_string.sh.
> | 
> | One of the two sources is stale; I did not determine which. t1762 only added a `--` pathspec to the existing file lists and did not change which files they name.

> **✉ note:t1865** id=2026-09-22T20:49:28Z.8c6b09cd83078bc07cd6a436 from=t1865 from_verified=yes at=2026-09-22T20:49:28Z base=85abc421765ad61c70875a1caf72b00d55ab2902 base_branch=main dirty=yes host=omg16
>
> | Findings from a full-repo sweep of `opus5` / `claude-opus-5` run while
> | promoting `claudecode/opus5_5` to the default (t1865). These are inputs for
> | your refresh of `aidocs/framework/model_reference_locations.md`; treat them as
> | advisory, and re-derive before acting — line numbers move.
> | 
> | **Live sites the audit doc does not list at all:**
> | 
> | 1. `.aitask-scripts/lib/roadmap_run.py` — a SECOND hardcoded default
> |    (`run()`'s `agent_string=` keyword default, and the `--agent-string`
> |    argparse default). `aitask_add_model.sh promote-default-agent-string`
> |    patches only `lib/agent_string.sh` + `aitask_codeagent.sh`, and
> |    `.claude/skills/aitask-backlog-roadmap/SKILL.md` invokes the driver with no
> |    `--agent-string`, so the published roadmap artifact's
> |    `generator.agent_string` silently kept the old model across the last
> |    promotion. §3 claims exactly three hardcoded-default files and this is not
> |    one of them. t1865 has now updated both lines, so the CODE is current — what
> |    remains stale is the audit's inventory.
> | 2. `website/content/docs/tuis/syncer/_index.md` — the "Reading the matrix"
> |    legend, one of whose cells labels the value as "the built-in fallback".
> |    (t1865 updated it.)
> | 3. `.aitask-scripts/lib/agent_string.sh` header comment — it named
> |    `claudecode/opus4_7_1m` as the default, wrong for at least two promotions.
> |    Not grep-findable by the current model name, which is likely why it was
> |    missed. (t1865 corrected it.)
> | 4. `tests/lib/branch_mode_repo.py` — a shared fixture factory that fabricates
> |    its own `DEFAULT_AGENT_STRING=...` line and a hardcoded model-name list.
> | 5. An entire generation of suites §7 predates: the cross-repo, agent-freeze,
> |    agent-restore, agent-sessions, frozen*, roadmap_*, live-endpoint,
> |    session-hook and restore-flows files. All are stable fixtures (none blocks a
> |    promote), but "many stable fixtures" understates the surface considerably.
> | 
> | **Two places the audit OVER-states:**
> | 
> | 6. `tests/test_brainstorm_crew.py` is tagged `needed_for_promote`. It is not.
> |    `TestGetAgentTypes.FULL_DEFAULTS` is written into a tmpdir by
> |    `_write_full_config`, and every `get_agent_types` call in the file passes
> |    `config_root=Path(self.tmpdir)` — the assertions read back what the test
> |    itself wrote, so it never reads the shipped config. Verified statically and
> |    confirmed empirically: t1865 promoted the defaults and left this file
> |    untouched, and it stays green. It should be reclassified as a fixture.
> |    Note this claim also propagated into `.claude/skills/aitask-add-model/`
> |    SKILL.md's Step 5 manual-review block.
> | 7. The §4 entry for `.aitask-scripts/aitask_brainstorm_init.sh` ("these ARE
> |    live defaults") no longer holds — that file has no model reference at all
> |    now.
> | 
> | **The real red-test file is `tests/test_codeagent.sh`**, which the audit and
> | the add-model skill both name but t1865's own task body did not: its fixture
> | installs `seed/codeagent_config.json` as the project config, so promoting
> | seed's `pick` broke five literal assertions. t1865 converted them to the t1318
> | derive idiom (`tests/lib/codeagent_defaults.sh`) and adopted
> | `codeagent_fixture_metadata` there, so the file now carries the
> | `AIT_CODEAGENT_FIXTURE_OMIT_OPS` negative control.
> | 
> | **Hedge:** items 1-3 and the test_codeagent.sh conversion are described as of
> | t1865's working tree, which is NOT yet committed as I write this — if t1865 is
> | later aborted or reworked, re-check those files rather than trusting this note.
> | Items 4-7 are observations about files t1865 did not modify.
