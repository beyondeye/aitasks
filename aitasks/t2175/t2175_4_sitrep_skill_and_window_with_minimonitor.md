---
priority: medium
effort: medium
depends: [t2175_3]
issue_type: feature
status: Ready
labels: [sitrep]
anchor: 2175
created_at: 2026-10-31 19:58
updated_at: 2026-11-01 17:40
---


# The sitrep skill and window (with minimonitor companion)

Child of t2175. Depends on the writer, harvest and refresh children.

## Scope
- New profile-aware skill `aitask-sitrep` (Claude Code first, per CLAUDE.md; stub + `.md.j2` pair, see `aidocs/framework/stub-skill-pattern.md` and `skill_authoring_conventions.md`; regenerate goldens; run `aitask_skill_verify.sh`). Advisory-only: never picks, pushes, edits code or sends keystrokes into other panes.
- Launches in its OWN window (not a split like the shadow) and spawns a minimonitor companion in that window; one per repo, guarded against double-spawn with a live lookup (see the shadow spawn rules in `aidocs/framework/shadow_agent.md` and `tmux_gateway.md`; all tmux through the gateways).
- On start: run refresh, read todo.md, greet with its capabilities.
- Capabilities: show Pick now / Next / Waiting; turn harvested prose into agent-derived action/watch items and write the situation text per theme; answer questions FROM THE SOURCES via the context pointers (not remembered summaries), warning when answering from a stale `checked_at`; trail status = report and offer (run `aitask-trail refresh` on user confirmation, never write the trail itself); suggestions via `aitask-backlog-roadmap`, not a reimplemented ranking; dismiss items; append every Q&A to the dated log.
- Document in `aidocs/framework/sitrep.md` and add a pointer in CLAUDE.md; user-facing docs on the website (run `check_links.py`).
- Suggest separate tasks for the codex/opencode ports.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2175_1** id=2026-11-01T20:31:59Z.832b1a0b4cb2e23242b7b45b from=t2175_1 from_verified=yes at=2026-11-01T20:31:59Z base=42b547c679d0a15ccb6ff8b93ade765e53882203 base_branch=main dirty=no host=omg16
>
> | The sitrep store writer landed in 42b547c67: .aitask-scripts/aitask_sitrep_todo.sh (format core: .aitask-scripts/lib/sitrep_todo.py).
> | 
> | 1. Permission touchpoints are owed here. Per aidocs/framework/aitasks_extension_points.md ("Adding a new helper script"), the 5 touchpoints (.claude/settings.local.json, .codex/rules/default.rules, seed/claude_settings.local.json, seed/codex_rules.default.rules, seed/opencode_config.seed.json) apply only once a SKILL.md closure invokes the helper. t2175_1 therefore added none; the sitrep skill is the first such caller.
> | 2. The skill should write only through the helper's verbs (qa, dismiss, add --derived agent, situation <theme>, upsert-context), never by editing .aitask-sitrep/ files: the strict parser refuses any hand edit (exit 4; recover with `restore todo|qa`).
> | 3. Verb list, exit codes and result lines are in the helper's header; the consumer-contract fixture is tests/fixtures/sitrep/. Revs are store-wide stamps (compare for equality only); `--expect-rev` guards agent writes against concurrent refresh.

> **✉ note:t2175_2** id=2026-11-03T09:12:19Z.245f989a719e2d0a28740530 from=t2175_2 from_verified=yes at=2026-11-03T09:12:19Z base=10957dd7286d560c7eb206bf7c25ee1043d40f41 base_branch=main dirty=yes host=omg16
>
> | The sitrep harvest landed in 10957dd72: .aitask-scripts/aitask_sitrep_harvest.sh (core: .aitask-scripts/lib/sitrep_harvest.py; contract in both headers).
> | 
> | 1. Triage items. Every finished run's closing message + banner becomes ONE script item: kind=question, group=now, derived=script, title "Triage wrap-up of t<id> <name>: turn its closing notes into action/watch items". Its context's capture: sources are the retained passage (first), the canonical banner, and identity key files; related: links earlier triage items that share the banner (a re-worded or duplicate run). The skill reads the passage, writes the action/watch items with `add --derived agent`, then marks the triage item done (set-state). Never edit the key files' items away: they are what makes re-harvest a no-op.
> | 2. Run `./.aitask-scripts/aitask_sitrep_harvest.sh all` on start (or `all --root <repo>`): it harvests every record that still holds capture text and releases records purge is keeping (KEPT:<id>|unharvested_text).
> | 3. workflow-end.md now pipes the closing message + banner into `aitask_sitrep_harvest.sh banner` (best-effort), so live agents' wrap-ups arrive without a freeze. The helper is on the five permission allowlists; aitask_sitrep_todo.sh still is not (owed by this task, per the t2175_1 note).

> **✉ note:t2175_3** id=2026-11-03T21:19:27Z.5c42df1cba8a62e9ae591594 from=t2175_3 from_verified=yes at=2026-11-03T21:19:27Z base=df3ee6c58928513c2b2d3b242a2051e8e6d0dc9f base_branch=main dirty=yes host=omg16
>
> | The sitrep refresh landed in df3ee6c58: .aitask-scripts/aitask_sitrep_refresh.sh (core .aitask-scripts/lib/sitrep_refresh.py; contract in both headers).
> | 
> | 1. Push items. The writer accepts a new ref form `push:<branch>@<sha>` (todo.md is now format=2; format=1 stores are read and upgraded on their first changing write). Create push reminders with
> |    `add --kind action --ref push:<branch>@<sha> --derived agent --context-file -`.
> |    Refresh marks them done only when the sha is on the branch's remote push destination (no fetch, push URL must equal the single fetch URL); otherwise open ("not pushed: … ahead/behind … (fetched <date>)") or unknown.
> | 2. Run `aitask_sitrep_refresh.sh --root <repo>` on start, after `aitask_sitrep_harvest.sh all`. Outcomes are the live state shown in Part 1 (status: Ready, archived (completed …), next wave …): read them, never restate task content. unknown means unverified, never done. Done items are never re-checked.
> | 3. Targets are only: task items with a t<N> / <proj>#<N> ref, action items with a push: ref, watch items with trail: sources. Agent action/watch items without these anchors and triage questions are never touched by refresh.
> | 4. A changed context entry (upsert-context created/replaced) now gives the item a fresh rev, so pass a re-read --expect-rev after it.
> | 5. aitask_sitrep_refresh.sh has no code-agent permission entries yet; like the writer, its 5 touchpoints are owed by the first SKILL.md that calls it (this task), per aidocs/framework/aitasks_extension_points.md.
