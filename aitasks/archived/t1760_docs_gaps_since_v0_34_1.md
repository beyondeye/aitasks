---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: documentation
status: Done
labels: [docs, web_site]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: docs_gap
implemented_with: claudecode/opus5
created_at: 2026-09-09 10:31
updated_at: 2026-09-09 19:36
completed_at: 2026-09-09 19:36
---

Documentation gaps found by /aitask-docs-gap for the release window v0.34.1..HEAD.
Each section below is self-contained and can become its own child task at
decomposition time.

## Gap: `ait upgrade` version-check timeout knob (t1244)

- **Target doc page(s):** `website/content/docs/commands/setup-install.md`
  (the `## ait upgrade` section). Consider a cross-reference from
  `website/content/docs/installation/known-issues.md` if the hang symptom
  belongs there.
- **What shipped:** The GitHub release fallback used by the version check now
  hard-bounds its `git ls-remote` call with a watchdog and reaps the whole
  process tree, instead of hanging indefinitely on an unreachable or slow
  remote. The bound is configurable through the `AIT_GIT_LSREMOTE_TIMEOUT`
  environment variable, and `install.sh` carries the same behavior in its
  mirrored `resolve_latest_version_gittags()`.
- **What to write:** The `## ait upgrade` section is currently silent about the
  version check reaching the network at all. Document that the check is bounded,
  name `AIT_GIT_LSREMOTE_TIMEOUT` with its default and its unit, and say what a
  user sees when the bound trips (the check fails rather than hangs; the upgrade
  path degrades rather than blocking). Match the house treatment of the sibling
  knob `AIT_GIT_SKIP_STATE_CHECK`, which is already documented at
  `website/content/docs/commands/sync.md:252` — the omission here is an
  inconsistency between two neighbouring git-timeout/escape-hatch knobs, not a
  new documentation pattern. Read the landed code
  (`.aitask-scripts/lib/github_release.sh`) for the real default and variable
  semantics rather than this description. Current-state prose only.
  Run `python3 check_links.py --build` in `website/` after the edit.
- **Sources:** `aiplans/archived/p1244_bound_git_lsremote_in_github_release_fallback.md`;
  commits: 3e89490fc

## Gaps deliberately excluded — already owned

Two larger gaps were found in the same window and are **not** included here,
because dedicated `Ready` documentation tasks already specify them in more
detail than this task could. Do not re-create them:

- **`ait note` mailbox / live delivery / `aitask-note` skill** (t1657_3, t1657_4,
  t1657_5). The site has no `commands/note.md`, no `skills/aitask-note.md`, and
  no mention of `ait note` anywhere under `website/content/docs/`.
  Owned by **t1657_6**.
- **Frozen code agents** (t1705_2 .. t1705_6): the `ait frozenagent` viewer TUI
  (registered in `TUI_REGISTRY`, reachable via the switcher `f` key), the
  framework session store, the freeze/restore engines, and the `SessionStart`
  hook installed by `ait setup` / `install.sh`. The site is silent and
  `website/content/docs/tuis/_index.md` does not list the TUI.
  Owned by **t1705_9** (TUI surfaces) and **t1705_10** (workflow / concept /
  setup surfaces).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-09T12:11:16Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-09T16:22:08Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-09T16:35:55Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:a194eb04ae8f44f4

> **✅ gate:risk_evaluated** run=2026-09-09T16:35:55Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1760/risk_evaluated_2026-09-09T16:35:55Z-risk_evaluated-a1.log`
