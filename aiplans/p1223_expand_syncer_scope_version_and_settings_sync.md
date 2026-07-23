---
Task: t1223_expand_syncer_scope_version_and_settings_sync.md
Worktree: (none — profile 'fast': current branch)
Branch: main
Base branch: main
---

# t1223 — Expand syncer scope: cross-repo version + settings sync

## Context

`ait syncer` today answers exactly one question: *"which of my repos are out of
sync with `origin`?"* It already knows about **every** registered aitasks repo
(t1138 made it cross-repo), but it only ever acts on git refs.

Two other things are per-repo state a user has to chase manually, one repo at a
time:

1. **Which framework version is each repo on?** Today: `cd` into each repo and
   run `ait --version`, then `ait upgrade` + `ait setup` in each.
2. **Do my repos agree on settings that ought to match?** Concretely the default
   code agent per operation — repo A explores with `claudecode/opus4_8`, repo B
   silently still uses whatever was seeded. There is no surface that shows the
   divergence, let alone fixes it.

The syncer already owns the repo-discovery, per-repo action-targeting, and
bounded-polling machinery those need. The goal is to make it the **cross-repo
sync console** — branches, versions, settings — rather than build two new TUIs.

**Scope decisions (confirmed with the user):**
- Settings v1 covers **only** the default code agent per operation. The seam is
  built generically so adding a setting is a config-list edit, but no other
  setting ships in v1.
- A settings push **asks** which layer to write (project/git-tracked vs
  local/gitignored) at push time — no silent default.
- Upgrade acts on **one repo at a time** (highlighted row + confirm), matching
  t1138's deliberate no-batch-fan-out posture for repo-mutating actions.

## Background from exploration

### What already exists (reuse, do not reinvent)

| Need | Existing seam |
|---|---|
| Discover all repos | `syncer_app.discover_syncer_sessions()` → `agent_launch_utils.discover_aitasks_sessions(include_registered=True)` (`syncer_app.py:119`) |
| Per-repo row model | `RowSpec` / `ActionTarget` / `resolve_action_target()` (`syncer_app.py:90`, `:107`, `:263`) |
| Bounded polling across N repos | `least_recent_fetch_key()` (`syncer_app.py:187`), `coalesce_request()` (`:240`) |
| Read a repo's installed version | `<root>/.aitask-scripts/VERSION` (one-line semver) |
| Resolve the latest release | `lib/github_release.sh` → `github_resolve_latest_version` (`:101`), REST with `git ls-remote` fallback (`:36`, `:91`) |
| Spawn a shell in another repo's root | `agent_launch_utils.launch_in_tmux()` (`:1188`) + `TmuxLaunchConfig.cwd` (`:89`); all raw tmux via `lib/tmux_exec.py` |
| Read a repo's default agent per op | `agent_launch_utils.resolve_agent_string(project_root, operation)` (`:232`) — already root-parameterized |
| Read a repo's model catalog | `agent_model_picker.load_all_models(project_root)` (`:44`) |
| Layered config read / merge / write | `config_utils.load_layered_config` (`:91`), `deep_merge` (`:63`), `save_project_config` / `save_local_config` (`:132`, `:141`) |
| Cross-repo config file I/O | `config_utils.export_all_configs` / `import_all_configs` (`:258`, `:373`) — **already take `metadata_dir` as a parameter** |
| Project-write clears shadowing local key | `settings_app._handle_agent_pick` (`:2299-2306`) — the existing masked-override semantic |
| Atomic file write | `gate_ledger.py:358`, `attachment_meta.atomic_write` (`:65`) — temp + `os.replace` |
| Tabs in a framework TUI | `settings_app.py:1578` (`TabbedContent` + `TabPane`), `brainstorm/nav_mixin.py` |
| Remappable keys | `ShortcutsMixin`, scope `"syncer"` (`syncer_app.py:317`, registered `lib/shortcut_scopes.py:56`) |

### The three real gaps

1. **No tabs.** `syncer_app.compose()` (`:384-401`) yields one `DataTable`
   (`#branches`) + a `Static` detail pane. Version and settings are per-**repo**
   data, not per-`(repo, ref)`, so they cannot be columns on the existing table.

2. **`ait upgrade` / `ait setup` have no `--dir`.** Both derive their target from
   their own script location (`aitask_upgrade.sh:7-8`; `aitask_setup.sh` uses
   `$SCRIPT_DIR/..`). Cross-repo upgrade must therefore invoke
   `<root>/ait upgrade …` with `cwd=<root>`. `ait upgrade` supports pinning
   (`aitask_upgrade.sh:83-89`) and is non-interactive; `ait setup` prompts only
   when stdin is a TTY, so a *visible* spawned shell is the right host for it.

3. **No path-parameterized settings writer anywhere.** `aitask_codeagent.sh` is
   read-only (`resolve` / `list-models` / `check` / `invoke` — no setter), and
   `settings_app.ConfigManager` is cwd-bound. The only root-aware helpers are
   read-side.

### Design call: extend `import_all_configs`, don't fork it

`planning_conventions.md` ("User-facing features … reuse export/import") requires
routing config persistence through `export_all_configs` / `import_all_configs`
rather than a parallel helper. Those already accept `metadata_dir`, so they work
cross-repo as-is — but they are **whole-file replace**, which would clobber the
destination's other operations.

The fix is an extension by parameter, not a fork: give `import_all_configs` a
`merge=` mode (deep-merge bundle content into the existing target) and a
`bundle=` in-memory alternative to `input_path`. A key-level push becomes a
partial in-memory bundle:

```python
import_all_configs(
    bundle={"files": {"codeagent_config.json": {"defaults": {"explore": "claudecode/opus4_8"}}}},
    metadata_dir=dest_root / "aitasks" / "metadata",
    overwrite=True, merge=True,
)
```

This inherits the existing path-traversal guard (`config_utils.py:411-413`) and
the bundle format, and is merge-based — the failure mode behind the known
`t1219` defect (rebuild-from-widgets drops unknown keys) is structurally
impossible. The full contract is specified in **§Safety contracts / E** below;
it is not "deep_merge and hope".

## Safety contracts

These seven contracts are binding; each child implements and tests the ones it
owns. They exist because the naive version of each is unsafe.

### A. Self-upgrade — the syncer must not rewrite itself while running

`ait upgrade` runs `install.sh --force --dir "$AIT_DIR"`, replacing everything
under `.aitask-scripts/`. The running Python process survives (its modules are
already imported), but **every subsequent subprocess the syncer shells out to** —
`aitask_sync.sh`, `github_release.sh`, `agent_launch_utils.py --list-registry`,
`aitask_codeagent.sh` — would be the *new* version, in a session whose in-memory
state came from the old one. A confirmation dialog does not make that safe.

**Contract:** the syncer never spawns a concurrent upgrade of the repo it is
running from. Instead, **exit-then-upgrade handoff**:

- `is_self_target(root, cwd)` compares `os.path.realpath` on both sides (matching
  `AitasksSession.key` semantics). Pure, unit-tested.
- On a self-target upgrade, the app writes a **handoff request** (protocol **B**)
  and calls `app.exit()`. It does **not** call `launch_in_tmux`, and no framework
  file is touched while the TUI is alive.
- `aitask_syncer.sh` drops `exec` (`:23`), runs the app, and **after Python has
  fully exited** reads the request and runs the upgrade in the same window. No
  request ⇒ normal exit.
- **Fail-closed:** if no wrapper-provided request path is present (app launched
  directly, not via `ait syncer`), the self-target upgrade is refused with a
  message naming the fix (`run ait upgrade from a shell`) — never a spawn, never
  a silent no-op.

### B. Handoff request protocol — data-only, wrapper-owned, revalidated

The handoff crosses a Python→shell boundary and ends in a command that rewrites
framework files, so the request is treated as untrusted input even though we
write it ourselves.

- **The wrapper owns the path.** `aitask_syncer.sh` creates a private directory
  with `mktemp -d` (mode `0700`, request file `0600`) and exports
  `AIT_SYNCER_HANDOFF` **unconditionally**, ignoring and overwriting any inbound
  value. The app can never choose or influence the path, and an externally
  supplied `AIT_SYNCER_HANDOFF` has no effect.
- **Data only, never code.** The request is a single JSON object with exactly two
  members, `root` and `version`. It carries **no command string**. The wrapper
  parses it with the aitasks Python (`json.load`) — it is never `source`d, never
  `eval`ed, and never interpolated unparsed.
- **The app writes it atomically** (temp + `os.replace` in the same private dir)
  so the wrapper can never read a partially written request.
- **The wrapper revalidates before constructing anything.** `root` must be an
  absolute, existing directory containing the canonical aitasks marker
  `aitasks/metadata/project_config.yaml` (the same check as
  `path_is_aitasks_project`, `aitask_project_resolve.sh:207-211`) plus an
  executable `<root>/ait`; `version` must match
  `^(latest|[0-9]+\.[0-9]+(\.[0-9]+)?)$`. Any failure ⇒ refuse, print the reason,
  run nothing. Validation is re-done wrapper-side even though the app already
  validated — the app's check is UX, the wrapper's is the security boundary.
- **The wrapper builds the command from validated parts** (properly quoted), so
  the only thing that crosses the boundary is two validated scalars.
- **Cleared on every exit path.** The wrapper unlinks the request immediately
  after reading it (before running the upgrade, so a crash cannot re-trigger it)
  and removes the private directory via a `trap ... EXIT INT TERM` so normal
  exits, errors, and signals all clean up.

### C. Active target — refuse to upgrade a repo with live framework processes

Contract **A** protects the syncer's own repo, but upgrading *another* registered
repo that has its own live `ait` session produces exactly the same mixed-version
hazard one level removed — that repo's running TUIs and agents would keep
shelling out to a `.aitask-scripts/` being replaced underneath them. Because the
action stays available, a documentation warning is not a control.

**Contract:** the upgrade action is **refused** for a target with detected live
framework processes.

- `AitasksSession.is_live` (`agent_launch_utils.py:120`) is already carried by
  every syncer row: `is_live=False` (registry-synthesized) short-circuits to
  `idle` with no tmux calls.
- For a live target, enumerate its windows with `get_tmux_windows(session)`
  (`:267`) and classify: a window whose name is in `KNOWN_TUIS`
  (`tui_switcher.py:155`) or starts with a companion/agent prefix
  (`agent-` / `create-`, `agent_launch_utils.py:1393`) marks the target **busy**.
- `detect_target_activity(session, windows)` is a **pure** function returning
  `idle` or `busy:<window names>`; window enumeration is the impure part, wired
  in the TUI layer.
- On `busy`, the action refuses and names the offending windows so the user knows
  exactly what to close. There is no override flag — re-check after closing them.
  The gate keys on *detected framework windows*, not on mere session existence,
  so a session holding only plain shells does not block a legitimate upgrade.
- **Declared bound (best-effort, stated honestly):** this detects framework TUIs
  and agent panes in the target's tmux session. It cannot detect an `ait` command
  running in an unrelated terminal, a detached process, or another machine
  sharing the checkout. That residual is documented; it is not silently implied
  to be covered.

### D. Settings — effective value, provenance, and masked writes

`load_layered_config` merges `defaults ← project ← local` (`config_utils.py:114-121`),
so **local wins**. Pushing to the project layer of a destination that already has
a local override for that operation therefore changes a file and changes nothing
the destination actually uses.

**Contract:**

- The reader returns, per `(repo, operation)`: `effective` (ground truth from
  `resolve_agent_string(root, op)` — an independent path, not our own merge),
  the raw `project_value` / `local_value`, and a derived `provenance` ∈
  `{local, project, seed, builtin}`. If provenance-derived effective disagrees
  with `resolve_agent_string`, the cell renders `conflict` — never a guess.
- The matrix shows **effective value + provenance marker**, not the project file's
  contents.
- `plan_push(value, dest_root, operation, layer)` returns a typed outcome:
  `ok` · `noop` (dest effective already equals value) · `masked` (layer=project
  and a local override exists for that operation; carries the masking value) ·
  `rejected:<reason>` (model absent from dest's `models_<agent>.json`, malformed
  agent string, unreadable/invalid dest config). Reasons are distinct and each is
  tested.
- On `masked` the confirmation offers exactly three resolutions and no default:
  **Cancel** · **Write to the local layer instead** · **Clear the local override
  and write project**. The third mirrors the existing in-repo semantic in
  `settings_app._handle_agent_pick:2299-2306` (project write deletes the
  shadowing local key, dropping `defaults` and the file when empty) — reused, not
  reinvented.

### E. `import_all_configs` merge-mode contract

Extending a shared persistence API used by the settings TUI's export/import
requires the semantics to be stated, not inferred:

- `bundle=` and `input_path=` are mutually exclusive; exactly one is required
  (`ValueError` otherwise). `merge=True` requires `overwrite=True` (`ValueError`).
- `selected_files` filters `bundle=` identically to `input_path=`.
- **Fail closed on a bad destination:** in merge mode the target is read first; if
  it exists but is unreadable or invalid JSON, raise and write **nothing**. A
  malformed destination is never replaced.
- **Type conflicts are rejected, not clobbered:** if the bundle holds a dict where
  the destination holds a non-dict at the same path (or the reverse), reject with
  a named reason rather than letting `deep_merge`'s override-wins rule silently
  drop a subtree.
- **Atomic writes:** all writes go through a new `config_utils` atomic writer
  (temp file in the same directory + `os.replace`), mirroring `gate_ledger.py:358`
  / `attachment_meta.atomic_write:65`, so a concurrent reader never observes a
  partial file and a failed write leaves the original intact.
- Project vs local target is selected by the **filename inside the bundle**
  (`codeagent_config.json` vs `codeagent_config.local.json`) — no new layer arg.
- **Non-merge, path-based behavior is unchanged**: existing
  `tests/test_config_utils.py` and `test_config_utils_shortcuts.py` must pass
  untouched.

### F. Upgrade command — it is a shell string, so quote it

`launch_in_tmux(command: str, …)` passes its argument to tmux, which runs it
through a shell (`agent_launch_utils.py:1188`, `split_args += [… , command]`), so
`&&` chaining works — and quoting is entirely ours.

**Contract:** `build_upgrade_command(root, version)`

- validates `version` against `^(latest|[0-9]+\.[0-9]+(\.[0-9]+)?)$` **before**
  any interpolation (same shape `aitask_upgrade.sh:83-89` accepts) and raises on
  anything else;
- `shlex.quote()`s the `<root>/ait` path;
- returns `<q-ait> upgrade <version> && <q-ait> setup` — the `&&` is load-bearing:
  a failed upgrade must not be followed by `setup`;
- is pure and returns the parts alongside the string so tests assert structure,
  not just text.

### G. Upgrade lifecycle — "launched", never "succeeded"

There is no completion callback: `launch_in_tmux` returns `(pane_pid, error)`
only, and `ait setup` may sit at a prompt for minutes. Re-reading the version on a
later tick therefore cannot report success or failure.

**Contract:** an explicit per-repo `upgrade_state`:

- `idle` — normal version row.
- `launched` — set at spawn with `pane_pid`, `pane_id`
  (`resolve_pane_id_by_pid`), and a timestamp. While the pane is alive the row
  reads `upgrading…`; version columns show the last *read* value with a stale
  marker, never an assumed new one.
- `finished (result unknown)` — pane gone. The row says **re-check needed**. The
  TUI never claims a successful upgrade it did not observe.

An explicit re-check key re-reads `<root>/.aitask-scripts/VERSION` on demand; the
automatic tick may also re-read, but the state label is what communicates truth.
The self-upgrade path has no state (the TUI is gone by then).

## Decomposition

Six implementation children + a docs child + an aggregate manual-verification
sibling, all in scope. Sequential sibling dependencies (the default) are correct:
the tabbed shell is a prerequisite for both feature tabs, and each headless seam
precedes the tab that consumes it.

| Child | Scope | Owns |
|---|---|---|
| **t1223_1** | **Tabbed syncer shell** (pure refactor, no new features). `TabbedContent` in `compose()`; existing table+detail become the *Branches* tab; `check_action` becomes tab-aware; bindings/workers/single-repo degradation unchanged. | Render-level tab tests, per-tab gating (`s`/`u`/`p` inert off-tab), single-repo (`<2` repos) regression |
| **t1223_2** | **Version + upgrade-command model** (headless). `lib/framework_version.py`: `read_installed_version(root)`, `resolve_latest_version()` (adapter over `github_release.sh`), `version_status()`, `is_self_target()`, `detect_target_activity()` (contract **C**), `build_upgrade_command()` (contract **F**), `build_handoff_request()` (contracts **A**/**B**). No TUI. | Fixture-root tests (present/missing/malformed VERSION); quoting tests for roots with spaces, `$`, `;`, quotes, backticks; rejected-version raises; **failure-chain test**: run the built string with a stub `ait` that exits 1 and assert the `setup` marker was never created; `detect_target_activity` truth table (registry-only ⇒ idle; TUI window ⇒ busy; `agent-`/`create-` ⇒ busy; shells-only ⇒ idle); offline degradation |
| **t1223_3** | **Version tab + upgrade action + handoff** (TUI + launcher). Per-repo row: project, installed, latest, status, upgrade state. Key → `latest`-or-pinned → **active-target gate (contract C)** → confirm naming the target → `launch_in_tmux(cwd=root)`. **Self-target routes to the exit-handoff** (contracts **A**/**B**), including the `aitask_syncer.sh` change (drop `exec`, wrapper-owned `mktemp -d` request path, JSON parse, revalidation, `trap` cleanup). Lifecycle states + re-check key (contract **G**). | **Active target: assert no `launch_in_tmux` call and a refusal naming the windows**; self-target asserts no spawn + handoff contents; fail-closed when the wrapper path is absent; bash tests that the launcher ignores an inbound `AIT_SYNCER_HANDOFF`, refuses a request with a bad root/version, never sources the file, unlinks it before running, and runs the upgrade only *after* Python exits; state-transition tests (row never claims success); `shellcheck` |
| **t1223_4** | **Cross-repo settings seam** (headless). `config_utils`: atomic writer + `import_all_configs(bundle=, merge=)` per contract **E**. `lib/cross_repo_settings.py`: `read_operation_defaults(root)` with provenance, `diff_across_repos(roots)`, `plan_push(...)` typed outcomes per contract **D**. | Exact target-file diff (only the pushed key changed); unrelated keys/operations preserved; invalid dest JSON leaves the file byte-identical; type-conflict rejected; atomicity (no partial file on simulated failure); each `rejected:` reason distinct; `masked`/`noop` detection; existing `test_config_utils*.py` pass unchanged |
| **t1223_5** | **Settings tab + push action** (TUI). Repo × operation matrix showing **effective value + provenance**, divergence highlighted. Pick source value → select destinations → layer prompt → `plan_push` → resolve `masked` via the three-way prompt → apply → refresh. | Matrix model tests (incl. `conflict` cell), layer-prompt wiring, masked three-way resolution reaches the right writer, rejection surfaced with its reason |
| **t1223_6** | **Docs**: `website/content/docs/tuis/syncer/_index.md` (tabs, version tab incl. the self-upgrade handoff, the active-target refusal **and its declared detection bound**, and the "launched, result unknown" semantics; settings tab incl. layer/provenance/masking), cross-refs in `tuis/_index.md` and `commands/sync.md`; how to add a further synced setting. | — |
| **t1223_7** | **Aggregate manual verification** (seeded by `aitask_create_manual_verification.sh` after the child plans land). | Live TUI flows, real upgrade in a scratch repo, active-target refusal against a repo with a live session, real self-upgrade handoff, real cross-repo push incl. a masked destination |

**v1 exclusions and their dispositions:**
- *Settings beyond default-agent* (tmux prefs, shortcuts, board config) —
  **documented-only**: the seam is generic; t1223_6 documents the addition.
- *Batch upgrade fan-out* — **documented-only** (user chose one-at-a-time).
- *Upgrading a repo that has live framework processes* — **not** deferred: it is
  refused by contract **C** (self-repo by contract **A**). What remains
  documented-only is the **declared detection bound** — activity outside the
  target's tmux session is undetectable and is stated as such, not implied covered.
- *Editing the project registry from the syncer* — out of scope; `ait projects`
  owns it.
- *`t1219`* (settings drops unknown `default_profiles` keys) is a separate
  pre-existing bug; **not** folded in. Contract **E** ensures t1223_4 does not
  reintroduce the same rebuild-from-widgets pattern.

## Verification

Per child (each owns its tests; run individually — no runner):

```bash
bash tests/test_syncer_rows.py             # extended by t1223_1/_3/_5
python3 tests/test_framework_version.py    # new, t1223_2
bash tests/test_syncer_upgrade_handoff.sh  # new, t1223_3 (launcher ordering)
python3 tests/test_cross_repo_settings.py  # new, t1223_4
python3 tests/test_config_utils.py         # regression, t1223_4
bash tests/test_no_raw_tmux.sh             # t1223_3 must not bypass the tmux gateway
shellcheck .aitask-scripts/aitask_syncer.sh
```

End-to-end (t1223_7, manual):
- `ait syncer` with ≥2 registered repos → tabs render; Branches tab behaves
  exactly as before (`s`/`u`/`p` gated per ref, inert from other tabs).
- Single-repo launch → no regression in layout or actions.
- Version tab shows each repo's real `.aitask-scripts/VERSION`. Upgrading a
  **scratch** repo (no live session) to a pinned version spawns a shell in that
  repo; the row shows `upgrading…` then `re-check needed`, and re-check reports
  the new version.
- Active-target refusal: open `ait board` (or any framework TUI) in the scratch
  repo, retry the upgrade — it is refused and names the offending window; close
  it and the upgrade proceeds.
- Self-upgrade: the TUI exits first, the upgrade runs in the vacated window, and
  nothing under `.aitask-scripts/` changes while the TUI is alive. The temp
  request directory is gone afterwards (also after `Ctrl-C` during the TUI).
- Push `explore`'s default agent from repo A to repo B: layer prompt appears;
  after a project-layer push `git diff` in B shows **only** the one key changed.
- Push into a repo whose `codeagent_config.local.json` masks that operation: the
  three-way prompt appears, and each branch produces the documented on-disk result.
- A value whose model is absent from B's `models_<agent>.json` is refused with a
  named reason.

## Risk

### Code-health risk: medium
- The tabbed refactor rewrites `compose()` and `check_action` in the load-bearing
  `syncer_app.py`, alongside the refresh/coalescing machinery daily git sync
  depends on; a regression breaks a workflow the user relies on. · severity: medium · → mitigation: owned by t1223_1 (per-tab gating + single-repo regression) and t1223_7 (live)
- `config_utils.import_all_configs` is shared with the settings TUI's
  export/import; adding `merge=`/`bundle=` changes a helper that writes config
  files in *any* repo. · severity: medium · → mitigation: contract **E** (fail-closed reads, type-conflict rejection, atomic writes) + t1223_4's exact-diff and unchanged-legacy tests
- A key-level settings writer is the shape that produced `t1219`. · severity: medium · → mitigation: contract **E** merge semantics, proven by t1223_4's unrelated-key negative control
- `aitask_syncer.sh` loses `exec` and gains post-exit logic that ends in a
  framework-rewriting command — a small but security-relevant launcher
  change. · severity: medium · → mitigation: contract **B** (wrapper-owned path, data-only JSON, revalidation, `trap` cleanup) + t1223_3's launcher tests + `shellcheck`

### Goal-achievement risk: medium
- Chaining `ait upgrade` → `ait setup` in a spawned interactive shell is designed
  but not yet demonstrated end-to-end. · severity: medium · → mitigation: t1223_2's failure-chain test + t1223_7 (live scratch-repo upgrade)
- Mixed-version hazard from rewriting `.aitask-scripts/` under a running
  process. · severity: medium (was high; structurally prevented, not confirmed-away) · → mitigation: contract **A** for the self repo, contract **C** refusal for any other live target — both proven by no-spawn tests
- Activity detection is tmux-scoped: an `ait` process running outside the target's
  tmux session is undetectable. · severity: low · → mitigation: bound declared explicitly in contract **C** and documented by t1223_6 — not implied covered
- The upgrade result is genuinely unobservable from the TUI. · severity: low · → mitigation: contract **G** — the UI reports `launched` / `result unknown`, never success
- "Latest version" depends on the GitHub API (rate-limited) with a `git ls-remote`
  fallback; the version tab must degrade cleanly offline and honor the existing
  `f` fetch-off toggle. · severity: low · → mitigation: t1223_2 offline-degradation test

No before/after mitigation tasks were confirmed — each risk is owned by a named
child or a binding contract above.
