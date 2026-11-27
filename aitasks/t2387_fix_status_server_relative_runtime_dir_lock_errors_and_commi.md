---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [monitor]
followup_kind: upstream_defect
created_at: 2026-11-27 14:25
updated_at: 2026-11-27 14:25
---

## Origin

Spawned from aitasks_go#t47_5 (the Go `ait-monitord` lifecycle and server skeleton) during its Step 8b review. The Go port reproduces `status_server.py`; these three defects in the Python server were found while porting it and checked against aitasks `72bdd15db` (the files are unchanged at main `eec4dee54`). Advisory: re-verify the line numbers before relying on them.

## Upstream defect

- `.aitask-scripts/monitor/status_server.py:368-399 — ensure_server keeps a relative XDG_RUNTIME_DIR (or HOME) socket path and _spawn_server passes it to a child whose cwd is project_root, so the child binds a different (often missing) directory and ensure reports server_failed`
- `.aitask-scripts/monitor/status_server.py:227-234,384 — _try_lock re-raises a non-contention flock error (ENOLCK, EBADF), so ensure_server raises out of its "never raises" contract and `ensure` prints a traceback instead of an UNAVAILABLE line`
- `.aitask-scripts/monitor/status_server.py:1029-1044 — _commit advances the StreamEncoder (update) before sp.encode checks the line limit; an oversized frame leaves every subscriber with a generation gap while _tick_locked reports "tick failed"`

## Diagnostic context

- **Relative runtime dir:**
  - `runtime_dir()` returns `Path(xdg) / "aitasks"` for any existing directory, relative or not, and `os.path.expanduser("~/.aitask/run")` keeps a relative HOME relative.
  - `ensure_server` probes and locks that relative path in its own working directory. `_spawn_server` then starts `serve --socket <relative>` with `cwd=project_root`.
  - The Go port reproduced this as `UNAVAILABLE:server_failed` (a bind ENOENT) when the binary ran with `XDG_RUNTIME_DIR=runtime` and a different project root. Go now resolves the directory against the working directory before the split (aitasks_go `lifecycle.EffectiveRuntimeDir`).
- **flock errors:** `_try_lock` returns False only for EWOULDBLOCK / EAGAIN / EACCES and raises otherwise. Nothing in `ensure_server` catches it, so the `ensure` CLI dies with no status line. Go returns `UNAVAILABLE:lock_failed:<detail>`.
- **Commit gap:** `self._encoder.update(...)` moves the encoder to the next gen, then `sp.encode(delta)` can raise `FramingError` (a frame over 64 MiB). The exception escapes `_commit` into `_tick_locked`'s handler, so no subscriber got that gen and the next delta is a gap. Go updates a clone, requires the delta and the full snapshot to encode, and only then adopts it.

## Suggested fix

- Absolutize the runtime dir in `ensure_server` (and the `path` verb) before `server_paths`.
- Map a non-contention flock error to `UNAVAILABLE:lock_failed:<strerror>`.
- In `_commit`, encode the new delta (and a full snapshot) before committing the encoder state, for example by updating a copy. On failure, treat it as a failed tick.
