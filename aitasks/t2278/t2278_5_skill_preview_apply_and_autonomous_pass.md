---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: high
depends: [t2278_4]
issue_type: feature
status: Implementing
labels: [website, documentation, tui, screenshots, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
implemented_with: claudecode/fable5_2
created_at: 2026-11-15 18:12
updated_at: 2026-11-19 10:07
---

## Context

Child 5 of t2278 (docs TUI screenshot generator). Read the parent plan
`aiplans/p2278_docs_tui_screenshot_generator.md` first; the design was revised
on 2026-11-15 to an agent driving the real TUI in an isolated tmux session.
Read "Roles", "Sample state: the setup contract", "Which journal becomes a
recipe" and "Recipe lifecycle". Children 1-4 delivered the marker grammar and
check, the sample project and session primitives, recipes and replay, crop
and overlays, and multi-pane windows. Every `shot` / `replay` writes a batch
directory with a `manifest.json`.

This child adds `preview` and `apply`, the **skill** that does the discovery
and the repair, the contributor docs, and then runs the pass on the markers
that are still unresolved.

## The skill: two loops

`.claude/skills/aitask-docs-screenshots/SKILL.md` (new, static, Claude-only).
It stops at once when `website/screenshots/` is absent (the skill ships to
user projects like every skill, where the tool does not exist).

- **Discovery loop**, per unresolved marker: read the page section and the
  marker's alt and caption; decide the state that illustrates it; pick or add
  a dataset and run `setup` commands; drive the real TUI with `run`, `screen`,
  `keys`, `wait`; verify the state on screen and in the PNG; `shot`. Then
  start a fresh session, walk the route cleanly, `shot`, and
  `recipe save --illustrates ... --expect ...`.
- **Repair loop**, per existing recipe: `replay`; on `FAILED:` inspect the
  kept session to learn what changed; on a pass, compare the image with the
  page and the alt and caption. For a failure or a mismatch, re-discover in a
  fresh session and `recipe save --replace`. If no route exists, change
  nothing and report the scene with what was found.
- The skill states the setup contract (state = named dataset + `setup`
  commands, nothing else) and the two-pass rule (explore, then a clean walk).
- Then: `preview --batch <id>`, show the user, on approval
  `apply --batch <id>` with the id the user reviewed, report any `REFUSED:`
  scene, run `python3 check_links.py --build` and
  `python3 check_screenshots.py`. A capture made after the review is reviewed
  again before it is applied. The skill never commits, and always ends with
  `session stop --all`.

## `preview` and `apply`

- `preview --batch <id>` writes one HTML contact sheet from that batch only. It
  shows the batch id, each image, and each marker's page, alt and caption.
- `apply --batch <id>` requires the batch id; there is no "latest" default. A
  scene is applied only when all of these hold:
  1. the staged image still hashes to the manifest value;
  2. the destination file is in the state the manifest recorded (still absent,
     or the same hash); a file created or changed since is never overwritten;
  3. each of the scene's markers is still present byte-for-byte in its page.
     Markers are located by text, never by line number.
- For a passing scene it copies the image to the recipe's `output:` and, in
  each page as it is on disk now, substitutes only the marker text with
  `{{< static-img src="imgs/<output>" alt="..." caption="..." >}}`. Every other
  edit made to that page during review is kept.
- A failing scene is left untouched (image and pages) and reported as
  `REFUSED:<scene>|<reason>`. `apply` exits non-zero when any scene was
  refused. A refused scene needs a new capture and a new review.

## Key Files to Modify

- `website/screenshots/cli.py`: `preview`, `apply`.
- `.claude/skills/aitask-docs-screenshots/SKILL.md` (new; no `.j2`, no
  Codex / OpenCode wrappers).
- `website/screenshots/sample_project.py`: the datasets the remaining scenes
  need, each a data builder with a build test: `board_locks` (the base tree
  plus a local bare remote, so the real `./ait lock` works offline), `trails`
  (a trail artifact the real `ait trails` lists), `brainstorm` (a session with
  several proposal nodes). If a dataset cannot be built from data and real
  framework commands, report the scene; do not fake the screen.
- `.claude/settings.local.json`: a repo-local allow entry for
  `website/screenshots.sh`. Not in `seed/`; the tool does not ship.
- `website/content/docs/development/skills/`: a page for the skill, linked
  from that section's `_index.md` under framework-development skills.
- `aidocs/framework/docs_screenshots.md` (new): the design and contract record
  (grammar, recipes, setup contract, journal rule, ownership rule, batch and
  apply rules, isolation rules).
- `CLAUDE.md`: a "Read `aidocs/framework/docs_screenshots.md`" pointer and one
  line in the Website section.
- `website/README.md`: how to run the tool.
- `website/check_screenshots.py`: set `MISSING_SCENE_SEVERITY` to `"error"`.
- The doc pages: markers replaced by `static-img` through `apply`.
- `website/static/imgs/`: the generated images.
- `tests/test_screenshots_apply.py` (new).

## Acceptance of the repair loop: two scenarios, one passing outcome each

Run the skill itself (not the verbs by hand) on each, and record both results
in the plan's Final Implementation Notes.

1. **Reachable destination.** Take a copy of a working recipe in a scratch
   scenes directory and break it (a wrong key and a stale expected text). The
   state it illustrates still exists in the TUI. **Pass only if** the run ends
   with a replaced recipe that replays in a fresh session and whose image
   shows the destination text. A report of "could not repair" fails this
   scenario.
2. **Unavailable destination.** A recipe whose `illustrates` and `expect` name
   a state the sample project cannot reach. **Pass only if** the run reports
   the scene with what it found, the recipe file is byte-identical
   (`sha256sum` before and after), and nothing is staged for it.

## Reference Files for Patterns

- `.claude/skills/aitask-docs-review/SKILL.md`: a static, Claude-only skill.
- `.claude/skills/aitask-screen-recording/SKILL.md`: a skill driving a tool.
- `aidocs/framework/skill_authoring_conventions.md`: read before writing the
  skill. Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.
- `tests/test_helper_whitelist_coverage.sh`: it scans skills for
  `.aitask-scripts/aitask_*.sh` paths only, so a `website/` script path needs
  no seed allowlist entry; confirm the test still passes.
- `website/content/docs/development/skills/_index.md`: the page list.
- `aidocs/framework/documentation_conventions.md` and
  `aitasks/metadata/doc_update_guide.md`: prose rules for the new page and for
  alt / caption text.

## Implementation Plan

See `aiplans/p2278/p2278_5_skill_preview_apply_and_autonomous_pass.md`. Before
`apply` touches any page, run `git status -- website/` and stop on a page with
in-flight edits from another task.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` passes, with `apply`
  tests for: a staged image changed after capture, a destination created after
  capture, a destination modified after capture, and a marker edited after
  capture (each refused, nothing written for that scene); an unrelated edit
  elsewhere in the same page survives a successful apply; two captures produce
  two batches; each new dataset builds.
- Both repair scenarios above end in their one passing outcome.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `bash tests/test_helper_whitelist_coverage.sh` and
  `bash tests/test_release_tarball.sh` pass.
- `python3 website/check_screenshots.py --strict` exits 0: no unresolved
  marker.
- `cd website && python3 check_links.py --build` passes.
- Each generated image is viewed on the local Hugo server (`./serve.sh`).
- Suggest separate tasks to port the skill to Codex CLI and OpenCode.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2278_1** id=2026-11-15T20:17:06Z.0477e15bbc9a9de1508ddb19 from=t2278_1 from_verified=yes at=2026-11-15T20:17:06Z base=56e9dbdf804ad8ceefb6b30b03f87720fd2b1a2d base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2278_1 (committed in f5588aaea), as of that commit:
> | 
> | - The constant to flip once every marker has a scene spec is check_screenshots.MISSING_SCENE_SEVERITY. It is "warning" now; set it to "error". The test CheckerTests.test_missing_scene_severity_error_fails already covers the "error" path.
> | - screenshots.markers.render_static_img(marker) raises ValueError when a value contains a FORBIDDEN_IN_VALUE sequence ('"', "--", "\"). A marker that came through parse_marker never does, but a hand-built Marker can. apply should report it as REFUSED:<scene>|<reason>, not crash.
> | - marker file= and spec output: must both pass markers.path_problem: canonical, relative, each segment only [A-Za-z0-9._-]. apply can therefore copy to static/imgs/<output> and write src="imgs/<file>" with no encoding, and the browser requests exactly that file.
> | - check_screenshots.py checks image shortcode sources at the browser's request path (query and fragment dropped, percent-decoded). An image written by apply that is missing is reported as MISSING_IMAGE.

> **✉ note:t2278_4** id=2026-11-16T17:53:54Z.b5f122f88f8d5c169a0e35d6 from=t2278_4 from_verified=yes at=2026-11-16T17:53:54Z base=7d9572c13ee2cafe6110a585c593c21f9990d7a4 base_branch=main dirty=yes host=omg16
>
> | Two of the remaining markers are NOT captured by t2278_4 and wait for t2320
> | (hide diffviewer from the TUI switcher list): tui_switcher_from_monitor and
> | tui_switcher_from_minimonitor. The real switcher lists "Diff Viewer"
> | (lib/tui_registry.py in_switcher=True), which CLAUDE.md keeps out of docs; the
> | user chose to fix that first. Record those two scenes only after t2320 lands.
> | 
> | What t2278_4 adds that the skill's discovery/repair loop should use (details in
> | aiplans/archived/p2278/p2278_4_*.md "Notes for sibling tasks", once archived):
> | - verbs: session start --window NAME; pane split / window new; --pane on
> |   screen/keys/wait/find/shot; --window on screen/find/shot. Panes are roles or
> |   <window name>.<pane index>, never tmux ids.
> | - every dataset now ships a stand-in `claude` (website/screenshots/standin_agent.py)
> |   pinned first on PATH; a session refuses to start if `claude` resolves anywhere
> |   else, so agent launches never reach a real agent. Dataset `agents` adds the
> |   code-agent config, profiles and a local origin.
> | - launch dialogs: wait for "Pick Task tN", "(R)un in tmux" AND the session name
> |   ("lumen") before pressing r; an earlier r can be refused ("Please select a
> |   session", a race in lib/agent_command_screen.py).
> | - the sample project now holds a COPY of .aitask-scripts (a symlink let the
> |   monitor read the real repo's config and sitrep list).

> **✉ note:t2320** id=2026-11-17T15:21:26Z.351edf46a056fb7372cfc9dc from=t2320 from_verified=yes at=2026-11-17T15:21:26Z base=bcac5c07c6e3a15567128b1cf16cfd5e685d9bc7 base_branch=main dirty=yes host=omg16
>
> | t2320 landed in commit d6e8d1a54: the TUI switcher (j) no longer lists "Diff Viewer".
> | .aitask-scripts/lib/tui_registry.py now registers diffviewer with in_switcher=False, so it is
> | still classified as a TUI window but is absent from switcher_tuis() / tui_switcher.KNOWN_TUIS.
> | The switcher list as of that commit: board, trails, monitor, frozenagent, codebrowser, settings,
> | stats, applink, chatlink, syncer (plus the configured git TUI).
> | 
> | Consequence for this task (advisory): the switcher scenes held back by t2278_4 —
> | tui_switcher_from_monitor, tui_switcher_from_minimonitor — and the tui_switcher_dialog scene on
> | website/content/docs/tuis/_index.md should no longer capture Diff Viewer, so they can be recorded.
> | If a capture session happens to have a diffviewer window open, it is not shown in the switcher
> | either (it is classified as a TUI and skipped from the "Other" group).

> **👁 note:read** id=2026-11-18T21:08:55Z.038185b713aaa9c5c1ec3369 by=t2278_5 at=2026-11-18T21:08:55Z mode=explicit ids=2026-11-15T20:17:06Z.0477e15bbc9a9de1508ddb19,2026-11-16T17:53:54Z.b5f122f88f8d5c169a0e35d6,2026-11-17T15:21:26Z.351edf46a056fb7372cfc9dc

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-19T08:07:26Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-19T23:32:20Z status=pass attempt=1 type=human
