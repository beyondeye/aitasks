---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [claudeskills, cross_repo]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2258
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-27 00:46
updated_at: 2026-11-27 14:41
---

## Origin

Spawned from t2258_10 (docs audit of the cross-project and remote workflow pages) during Step 8b review.

## Upstream defect

- `.claude/skills/aitask-web-merge/SKILL.md:157-190` — the `GATE_PENDING` backstop does not say to skip Step 6, so the run can push and `git push origin --delete` the branch the prescribed re-run needs.
- `.claude/skills/aitask-web-merge/SKILL.md:87-101` — on a re-run after a stop the merge is `Already up to date` and the unconditional Step 3d `git commit` fails; no skip rule (confirmed by a user fixture, exit 1).
- `.claude/skills/aitask-web-merge/materialize-gates.md:33` — the Abort-this-branch repair text offers "re-run (no-op merge)" and omits the `implemented_with` write and the linked-issue update.
- `.aitask-scripts/aitask_archive.sh:106-108` — exit 2 also covers VERIFICATION_PENDING / VERIFICATION_DEFERRED, but web-merge handles only `GATE_PENDING`.
- `.claude/skills/aitask-pickweb/SKILL.md:12-16` — the profile is resolved before the data-branch init, so on a fresh Claude Code Web clone of a data-branch repo `default_profiles.pickweb` is invisible and `default` (not committed, cannot render there) is chosen; pickweb fails without `--profile remote`.
- `.claude/skills/aitask-pickweb/SKILL.md.j2:376-385` — the Profile Schema says `name`/`description` are "shown during profile load" and `post_plan_action` is used at the checkpoint; neither is true.
- `.claude/skills/aitask-pickweb-remote-/SKILL.md:134-147` — Done / orphaned-parent tasks are told to use aitask-web-merge locally, which only handles marker-bearing remote branches.
- `.claude/skills/task-workflow/execution-profile-selection-auto.md:4-5` — claims pickweb's Step 1 references it; pickweb has no such step.
- `.aitask-scripts/aitask_update.sh:311-324` — help says only administrative fields are allowed cross-repo, but `main()` (L2470-2524) enforces only the refusals, so any other flag is applied in the other project.
- `.aitask-scripts/lib/task_utils.sh:3017-3019` — `validate_xdeps_pair` says "is not registered" for any `NOT_FOUND`, though resolution also covers tmux and the env tier.
- `.aitask-scripts/aitask_create.sh:133-135` — help says `--xdeps`/`--xdeprepo` are "required together"; `--xdeprepo` alone is accepted.
- `.aitask-scripts/aitask_ls.sh:68-71` — help says `--project` must come first; `lib/cross_repo_reexec.sh:35-56` accepts it anywhere.
- `.aitask-scripts/aitask_explain_context.sh:312-314` — without `--max-plans` it exits 0 silently although its help calls the flag required.
- `.aitask-scripts/aitask_projects.sh:222-237` — with no Python, `list` blames the registry file ("Cannot read the project registry … Fix or remove it").
- `.aitask-scripts/aitask_project_resolve.sh:89` — `--help` still says NOT_FOUND means "No registered project matched".
- `seed/project_config.yaml:444` — says the profile fallback is "interactive selection / auto-select"; the resolver falls back to `default`.

## Diagnostic context

Found while fact-checking moved docs claims against the code in t2258_10 (archived plan: `aiplans/archived/p2258/p2258_10_audit_workflows_cross_project.md`, "Final Implementation Notes" and "Post-Review Changes"). The web-merge docs now document the manual finish as the dependable recovery *because* of the first three defects; once the skill skips Step 6 after `GATE_PENDING` and tolerates an `Already up to date` re-merge, `website/content/docs/skills/aitask-web-merge.md#when-archival-stops` and `workflows/claude-web.md` "If something goes wrong" should be revisited. The `aitask_update.sh --project` allow-list gap is documented as-is on `commands/task-management.md#updating-a-task-in-another-project` ("Only those refusals are checked").

## Suggested fix

Split by area if useful: (1) web-merge skill stop paths (skip Step 6 on GATE_PENDING / VERIFICATION_*; skip the 3d commit when the merge is a no-op; complete the Abort repair text) — then update the two docs pages; (2) pickweb profile resolution order vs data-branch init, and its stale schema text; (3) the cross-repo CLI help/messages and the unenforced `--project` allow-list. Skill changes start in `.claude/skills/` and need follow-up ports to the other agent trees.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-27T12:41:03Z status=pass attempt=1 type=human
