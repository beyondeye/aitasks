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
