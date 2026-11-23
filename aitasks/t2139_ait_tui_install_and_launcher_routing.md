---
priority: medium
effort: medium
depends: [2138]
issue_type: feature
status: Ready
labels: [go_engine, install, tui]
created_at: 2026-10-25 09:36
updated_at: 2026-10-25 09:36
---

Install the Go multi-app TUI binary **`ait-tui`** and route TUI launchers to it,
with a guaranteed Python fallback. Decision record:
`aidocs/aitasks_go/ship_path.md` in aitasks_go (aitasks_go#t15). `ait-tui` is
developed in the private aitasks_go repo and exported into `goengines/`, so
`build.sh` / `release.yml` produce `ait-tui_<V>_<os>_<arch>` +
`ait-tui_<V>_SHA256SUMS.txt` automatically.

## Binary contract (from aitasks_go)

- `ait-tui version` prints `VERSION:<v>`, `COMMIT:<sha>`,
  `SOURCE:aitasks_go@<sha>`.
- `ait-tui has-app <name>` exits 0 only if the app is compiled in, otherwise 1,
  with no stdout.
- `ait-tui apps` lists the compiled-in apps.
- `ait-tui <app> [args]` runs the app.

Apps are exported independently, so a correctly versioned binary may lack a
given app.

## Work

1. **Resolver:** generalize `testmap_resolve_engine`
   (`.aitask-scripts/aitask_testmap.sh:111`) into `lib/engine_resolve.sh`:
   `engine_resolve <name> <OVERRIDE_ENV>` with the same tiers (override env >
   `AIT_ENGINE=dev` slot requiring `<V>-dev+<sha>` >
   `$AITASKS_HOME/engine/v<V>/<name>` requiring `== VERSION`). Keep
   `aitask_testmap.sh` behaviour byte-identical; its tests must stay green.
2. **Install:** extend `install_engine_binary()` (`aitask_setup.sh:2676`) to
   also install `ait-tui` into `engine/v<V>/`, verified against its SUMS
   (same source tiers, `.sha256` sidecar, `.dev` protection). A missing TUI
   asset prints `TUI_BINARY:missing` as a warning and is **never fatal**. Add a
   `--no-go-tui` opt-out to both parsers.
3. **Launcher routing** in `aitask_monitor.sh` and `aitask_stats_tui.sh`:
   - a framework-shipped per-TUI default, **off** until that TUI's manual
     verification passes;
   - `AIT_GO_TUI=<name,…>|all` opts in and `AIT_GO_TUI=0` forces Python. This
     has the same shape as `AIT_USE_PYPY`; see
     `aidocs/framework/python_tui_performance.md`;
   - after `engine_resolve ait-tui AIT_TUI_BIN` succeeds, run
     `"$bin" has-app <name>`, and exec `"$bin" <name> "$@"` only on exit 0;
   - otherwise exec the Python TUI as today. Print
     `GO_TUI_FALLBACK:<name>|<binary-missing|version-mismatch|app-missing>` to
     stderr **only when the user explicitly opted in**;
   - keep the existing tmux and terminal checks in front of both paths.
4. Docs: `aidocs/framework/go_engine.md` (ait-tui install + routing) and a
   cross-reference in `python_tui_performance.md`.

## Tests (in the style of `tests/test_install_engine_binary.sh`, with an `AITASKS_HOME` sandbox)

- Install: present asset, missing asset (warning, rc 0), `--no-go-tui`.
- Routing fallback — each case must exec Python:
  - binary absent;
  - version mismatch;
  - **a matching-version binary that lacks the requested app** (a stub whose
    `has-app monitor` exits 1).

  The notice appears only with `AIT_GO_TUI` set.
- Routing success: a stub with `has-app` exit 0 is exec'd with the args
  forwarded.
- `AIT_GO_TUI=0` beats a per-TUI default of on.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:24:34Z.26e93b8bca8e2c9db678e041 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:34Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:17:12Z.4a7dd15bca0e45327b2ca969 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:17:12Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task has no engine part and stays here unchanged.

> **✉ note:t25** id=2026-11-22T16:29:35Z.5feac0c996653f07cf37b3c3 from=aitasks_go#t25 from_verified=yes at=2026-11-22T16:29:35Z base=d5527c324a9394065791353ac7a9427cf7b3c68d base_branch=main dirty=yes host=omg16
>
> | Advisory, from aitasks_go#t25. As of public aitasks de83356bf (pushed; origin/main d5527c324, Go engines check run 45043762483 green: mode + export-integrity):
> | - ait-tui is now exported into goengines/ from aitasks_go@bcf2e6de5e56 (EXPORT.txt source:). New public paths: goengines/tui/..., goengines/cmd/ait-tui/, and goengines/tmux/ (shared package, first public now; ait-testmap does not import it).
> | - goengines/build.sh all produces ait-tui_<V>_{linux,darwin}_{amd64,arm64} + ait-tui_<V>_SHA256SUMS.txt next to the ait-testmap ones (checked locally at V=0.42.0).
> | - ait-tui version prints VERSION:/COMMIT:/SOURCE:aitasks_go@<sha>; has-app <name> exits 0/1 with no stdout. Only app shipped: stats (seeded data).
> | - The stats routing default should stay off: it has no real data source yet (ship_path.md open item).
> | - Known gap: aitasks_go t103 (force UTF-8 tmux clients, so session discovery works under a non-UTF-8 locale) is NOT in this export. It changes goengines/tmux shared with the testmap closure, and it arrives with the next full export.

> **✉ note:t2348** id=2026-11-23T10:27:06Z.6dcd8ac63ecd0e01047fd0a6 from=t2348 from_verified=yes at=2026-11-23T10:27:06Z base=aa782387bde43a4019203e07f7a93a1fc6df3091 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2348 (commit aa782387b, landed on main). This task
> | plans to generalise testmap_resolve_engine into lib/engine_resolve.sh, extend
> | install_engine_binary(), and keep the existing ait-testmap resolver behaviour
> | byte-identical. That behaviour now includes the points below. Re-verify them
> | against the tree; this is a claim, not an instruction.
> | 
> | 1. Root loading order in testmap_resolve_engine (aitask_testmap.sh):
> |    - lib/aitasks_home.sh is no longer sourced at file top. It is sourced
> |      inside the resolver, after the VERSION check and BEFORE Tier 1, with
> |      its stderr dropped.
> |    - An override engine therefore still inherits AITASKS_HOME and
> |      AITASKS_HOME_LOCK whenever a root can be established.
> |    - A load failure is acted on only AFTER Tier 1, so AIT_TESTMAP_BIN works
> |      with no HOME.
> | 2. Failure mapping, read from the lib's AITASKS_HOME_REFUSAL:
> |    - home-unset -> ENGINE_HOME_UNSET:AITASKS_HOME|set AITASKS_HOME, or a
> |      non-empty HOME (rc 3), or USAGE/64 when AIT_ENGINE is invalid. This
> |      keeps the old order, in which the mode check answered before any slot.
> |    - empty (the lib never ran) -> ENGINE_LIB_FAILED:<lib>|run 'ait setup'
> |      to repair the install (rc 3).
> |    - any other reason -> ENGINE_ROOT_INVALID:AITASKS_HOME|<reason> (rc 3).
> |    - In every case no slot is probed. _tm_check_slot runs `$bin version`,
> |      so a root-level /.aitasks fallback would execute host files.
> | 3. lib/aitasks_home.sh now:
> |    - validates the candidate root and lock before publishing either one;
> |    - refuses a readonly empty AITASKS_HOME, or a readonly AITASKS_HOME_LOCK
> |      holding another value;
> |    - exports values that are already correct without reassigning them;
> |    - sets _AITASKS_HOME_LOADED last.
> |    lib/engine_install.sh propagates a refusal with
> |    `|| { unset _ENGINE_INSTALL_LOADED; return 1; }`, because install.sh
> |    calls install_engine_binary with errexit off (`|| true`).
> | 4. Pinned by tests/test_aitasks_home_unset_home.sh. Under a blank HOME, that
> |    file only runs stubbed-probe or HOME-absent CLI forms; its header says
> |    why, and a generalised resolver's tests should follow the same rule.
