---
priority: medium
effort: medium
depends: [2143]
issue_type: bug
status: Implementing
labels: [verification, bug]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1689
followup_kind: verification_failure
implemented_with: claudecode/opus5_5
created_at: 2026-10-26 09:38
updated_at: 2026-10-26 14:43
---

## Failed verification item from t2143

> Healthy-order behaviour is unchanged: from a normal mise-activated interactive shell, pane PATH still starts with `~/.aitask/bin` and agents boot as before

### Source

- **Manual-verification task:** `aitasks/t2143_verify_on_mise_linux_host.md` (item #6)
- **Origin feature task:** t2143

### Commits that introduced the failing behavior

_(none detected — no commits matched (t2143))_

### Files touched by those commits

_(none)_

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t2143 item #6.

## Findings (t2143 auto-verification, 2026-10-26, Omarchy/mise host)

The failing behaviour was introduced by **t1689** (commit `86b4b96af`), not by
t2143 (which is only the verification task). Files:
`.aitask-scripts/lib/tmux_exec.py` (`normalize_spawn_path`),
`.aitask-scripts/lib/spawn_path.sh` (`ait_spawn_path_normalize`).

**Observed.** mise 2026.10.12 on this host puts
`~/.local/share/mise/command-wrappers/bin` *first* in an activated shell's PATH
(its entries — `claude`, `codex`, `grok` — are symlinks to `/usr/bin/mise`,
i.e. mise-managed shims like `shims/`). The healthy caller PATH is:

```
mise/command-wrappers/bin : ~/.aitask/bin : ~/.opencode/bin : ~/flutter/bin : mise/installs/java/21/bin : … mise/installs/* … : /usr/share/omarchy/bin : … : /usr/bin : ~/.local/bin : …
```

Both normalizers return `CHANGED` for it (shell and Python agree). Panes
spawned through `ait_tmux` and through `TmuxClient.run` from that shell got
a PATH starting with `mise/installs/java/21/bin`; `command-wrappers/bin` moved
1 → 9 and `~/.aitask/bin` 2 → 10. The agent still booted the real binary.

**Why.** `command-wrappers/bin` is not in the mise set (only `<mise_data>/shims`
and `<mise_data>/installs/*` are), so it counts as the first "other" entry;
`~/.aitask/bin` then no longer precedes the first other entry and is not
kept in front.

**Impact.** Today: `claude`/`codex` in spawned panes bypass mise's
command-wrappers and resolve straight to the install binaries. Latent: a
mise-installed `python`/`python3` would shadow the framework's
`~/.aitask/bin/python3` venv shim in every gateway-spawned pane.

**Note for the fix (unmeasured — verify before relying on it).** Adding
`command-wrappers/bin` to the mise set alone looks insufficient: by the rule
as written, `~/.opencode/bin` and `~/flutter/bin` would still move behind the
installs, so a healthy activated shell would still be reordered. The t1689
plan's premise "the result is the order a mise-activated interactive shell
already has" does not hold on this host. Consider a narrower precondition
(reorder only when a non-mise entry that shadows a mise-managed name precedes
every mise entry) rather than another set addition. Repro and evidence
commands are in `aiplans/p2143_manual_verification_auto.md` (item 6).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-26T12:43:38Z status=pass attempt=1 type=human
