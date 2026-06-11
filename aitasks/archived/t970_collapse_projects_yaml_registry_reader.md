---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [tmux, ait_bridge]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-11 08:17
updated_at: 2026-06-11 09:17
completed_at: 2026-06-11 09:17
---

## Origin

Split out from **t952_5** at pick time (2026-06-10). t952_5's job (a) — the
duplicate `projects.yaml` registry-reader collapse — was the only **non-routing**
part of the t952 tmux-centralization umbrella (scope item 4: single registry
authority) and carries the highest behavior-change risk. To land the t952_5
anti-regression guard + Layer-A discovery-walk migration cleanly, job (a) was
peeled into this standalone follow-up. It does **not** block the guard and is
**not** a t952 child (different axis: data-layer dedup, not tmux-spawn routing).

## Goal

Collapse the duplicated `~/.config/aitasks/projects.yaml` **file reader** to a
single Python authority, exposed via a thin CLI, with the bash side shelling out
to it — without behavior change. (Only the file reader is duplicated; the
live-tmux scan path is already single-authority Python.)

## Scope

1. Make Python the single registry-file authority. Extend the reader near
   `agent_launch_utils.py:261-320` (`_read_registry_index`) and expose a CLI
   surface (`--list-registry` / `--resolve <name>`). Honor `AITASKS_PROJECTS_INDEX`
   in the one Python place.
2. Replace the bash awk parsers with thin shell-outs:
   - `aitask_project_resolve.sh:160-205` (`index_lookup_path`).
   - `aitask_projects.sh:157-206` (`list_registry_entries`) and its registry
     readers (~157-292).
3. Keep the `RESOLVED:` / `STALE:` sentinel contract byte-identical.

## CRITICAL parity gap (the reason for the split / the main risk)

`agent_launch_utils._read_registry_index` currently returns only
**(name, path, status)** triples. But bash `list_registry_entries` emits **4
fields** — `name|path|git_remote|last_opened` — and feeds the registry **write**
operations (project add / remove / rename in `aitask_projects.sh`, which
re-serialize the full file). A naive shell-out to the 3-field Python reader would
**drop `git_remote` and `last_opened` on every registry mutation** — silent data
loss.

Therefore the Python authority MUST be extended to capture and emit all four
fields, OR the write path must keep its own full-fidelity reader and only the
read/resolve paths shell out. Decide at plan time.

## Risks

- **awk-vs-Python parity:** quoting, STALE detection, `AITASKS_PROJECTS_INDEX`
  override precedence — real behavior-change risk. Golden-corpus test it
  (quoted / unquoted / stale / comment / override cases) byte-for-byte against
  the pre-change baseline.
- **git_remote / last_opened preservation** through the write path (see above).
- **bash hot-path latency:** `index_lookup_path` is on the resolve hot path and
  would now pay Python startup. Measure; may justify keeping a fast bash reader
  for resolve while only list/mutation paths shell out. Do not regress resolve
  latency silently.

## Verification

- Golden-corpus `projects.yaml` fixture asserting the unified reader matches the
  pre-change bash+Python baseline byte-for-byte, **including a round-trip through
  add/remove/rename that preserves `git_remote` + `last_opened`**.
- Resolve-latency measurement before/after.

## Cross-references

- Parent umbrella: t952 (`aitasks/t952_centralize_tmux_invocations_shared_gateway.md`),
  scope item 4 (single registry authority).
- Split-from: t952_5 (`aitasks/t952/t952_5_collapse_registry_and_lint_guard.md`).
- Live-scan single-authority precedent: `aitask_project_resolve.sh` heredoc
  shelling to `discover_aitasks_sessions`.
