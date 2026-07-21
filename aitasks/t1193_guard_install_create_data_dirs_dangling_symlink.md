---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1171
created_at: 2026-07-20 23:13
updated_at: 2026-07-21 06:23
boardidx: 40
---

## Origin

Spawned from t1185 during Step 8b upstream-defect review.

## Upstream defect

- `install.sh:338-344 — create_data_dirs() runs unguarded mkdir -p on aitasks/ and aiplans/, which fails ("File exists") when either is a dangling symlink, aborting the install under set -e.`

## Diagnostic context

While verifying t1185 through the full install flow, `install.sh --local-tarball`
aborted with:

```
mkdir: cannot create directory '<dir>/aitasks': File exists
```

The tarball contained the repository's `aitasks` / `aiplans` symlinks (which
point at `.aitask-data/…`). In the fresh install dir that target does not exist
yet, so the symlink is dangling — and `mkdir -p` through a dangling symlink
fails rather than succeeding.

This is the same defect class t1185 guarded against in
`ensure_agent_config_seeds()`: an unguarded `mkdir -p` on a path that may be a
dangling symlink is a hard abort under `set -euo pipefail`.

**Severity is low / latent:** a genuine release tarball excludes the `aitasks`
and `aiplans` symlinks, so this is not a live user-facing failure. It was
reached only via a hand-built tarball. It is worth guarding because the failure
mode is a total install abort with a confusing "File exists" message.

## Suggested fix

Guard `create_data_dirs()` so a dangling symlink is either replaced or reported
clearly instead of aborting. Mirror the pattern added in
`.aitask-scripts/aitask_setup.sh` `ensure_agent_config_seeds()`:

```bash
if [[ ! -d "$dir" ]] && ! mkdir -p "$dir" 2>/dev/null; then
    # handle: warn, or remove the dangling link and retry
fi
```

Decide deliberately whether install should repair (unlink + mkdir) or fail with
a clear diagnostic — repairing is likely right for install, since a dangling
data symlink in a fresh install dir is meaningless state.

Add a regression test covering install into a dir containing a dangling
`aitasks` symlink.
