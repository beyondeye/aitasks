---
Task: t2153_wrapper_dirs_beyond_local_bin.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2153 — Do `mise x` wrappers appear outside `~/.local/bin`? (measure first)

## Context

t2144 (`230234839`) narrowed spawn-PATH normalization
(`lib/tmux_exec.py::normalize_spawn_path`,
`lib/spawn_path.sh::ait_spawn_path_normalize`) so it moves only
`$HOME/.local/bin` behind the last mise entry. It left a stated residual: a
self-referential `mise x <n> -- <n>` wrapper in any **other** dir ahead of mise
is not protected. This task measures whether that happens, and extends
protection only if it does.

**Decision (user, at planning):** explicitly accept custom wrappers outside
`~/.local/bin` as a remaining limitation. No code change. Conclusions are
limited to the host and installer sources actually examined. The doc records the
exact reproduced ordering and conditions, including the working
counterexamples. It must **not** claim that no installer on any supported
platform (macOS, Linux, WSL) writes such wrappers.

## Measurement (done during planning, all read-only)

Scope examined: **one Omarchy (Arch Linux) host**, the Omarchy scripts installed
on it, the `mise` 2026.10.12 CLI help, and upstream jdx/mise#8560. macOS, WSL
and other Linux distributions were **not** examined.

**1. This host: 20 self-referential wrappers, all in `~/.local/bin`, none
anywhere else.** I scanned every PATH dir plus `~/bin`, `/usr/local/{bin,sbin}`,
`/usr/bin`, `/opt/*/bin` and `~/.*/bin`. The test was a file of at most 64 KiB
whose first 4 KiB mention `mise use|x|exec`, classified SELF when it `exec`s its
own basename, directly or through `mise x|exec … --`. Results:

- SELF: 20, all in `~/.local/bin`.
- The other hits are not loop-prone:
  - `~/.local/bin/{gemini,playwright-cli}` exec absolute paths from
    `mise where node@latest`.
  - `/usr/bin` and `/usr/share/omarchy/bin` hold the generator, a detector, and
    dev-env scripts running `mise x <other-tool>`.

**2. The Omarchy sources examined write wrappers only to `$HOME/.local/bin`.**

- `omarchy-mise-install` hard-codes `$HOME/.local/bin/$command` and ignores
  `XDG_BIN_HOME`.
- `omarchy-install-{hermes,openclaw}-cli`, `omarchy-default-agent` and
  `omarchy-upgrade-to-quattro` all target `~/.local/bin`.
- The wrapper-regeneration migration `migrations/1787573629.sh` scans only that
  dir.
- Omarchy's PATH setup (`default/bash/env-bootstrap`, the pam_env line) puts the
  shims ahead of `~/.local/bin`.

**3. mise's own generators examined don't exec a tool by name through PATH.**
`mise generate tool-stub` runs through `mise tool-stub`, and `task-stubs` runs
`mise run`.

**4. Upstream report: a wrapper outside `~/.local/bin` exists in the wild.**
jdx/mise#8560 (fixed in mise 2026.3.8) is a user-authored
`.devcontainer/bin/gitleaks` (`mise x -- gitleaks`) placed ahead of the shims.
It is a counterexample to "wrappers only live in `~/.local/bin`", and it stays
uncovered by the explicit decision above.

**5. Reproduced orderings.** The probe below ran on mise 2026.10.12, this host.
The wrapper is an omarchy-shaped `exec mise x "gh" -- "gh" "$@"` (no
`mise use -g` line, plus a depth guard) in a scratch dir `O`. `gh` is installed
by mise (`SH` = `<data>/shims`, `I` = `<data>/installs/gh/latest/*/bin`,
`C` = `<data>/command-wrappers/bin`). Each run uses `env -i`, so **no `__MISE_*`
session variables** are set, the way a tmux pane receives them.

| PATH (then `/usr/bin:/bin`) | result |
|---|---|
| **`O:SH:I`** | **LOOP** (depth > 4) |
| `O:SH` | ok |
| `O:/usr/share/omarchy/bin:SH` (t2143 bad-env shape) | ok |
| `O:I` | ok |
| `O:C:SH` | ok |
| `SH:O:I` | ok |
| `I:O:SH` | ok (counterexample: `O` precedes `SH` with an installs entry present, yet no loop) |
| `SH:I:O` (what t2144 emits for a `~/.local/bin` hazard) | ok |

Only `O:SH:I` was shown to fail. No general rule is inferred beyond the tested
rows. This host's real activated PATH
(`~/.opencode/bin:~/flutter/bin:C:SH:C:~/.aitask/bin:I…`) has the same
"user dir, then shims, then installs" shape. It doesn't loop because
`~/.opencode/bin/opencode` is a real binary.

## Implementation steps

1. **`aidocs/framework/tmux_gateway.md`**, the "Why only `~/.local/bin`"
   bullet (~l.158-166). Replace its last sentence ("A `mise x` wrapper in any
   other dir ahead of mise is not covered.") with current-state text saying:
   - **Accepted limitation:** a self-referential wrapper in any other dir ahead
     of mise (for example a user-authored project `bin/`, as in jdx/mise#8560)
     is not covered. Covering it would mean either reordering legitimate tool
     dirs or sniffing file contents.
   - **Bounded evidence:** on the Omarchy host and sources examined (t2153), all
     wrappers were in `~/.local/bin`, and `omarchy-mise-install` hard-codes that
     dir. Other platforms were not examined.
   - **Reproduced trigger:** on mise 2026.10.12 with no `__MISE_*` session
     variables and the tool installed by mise, a wrapper dir loops in the order
     `wrapper:shims:installs/<tool>/…/bin`. `wrapper:shims` alone,
     `wrapper:installs`, `installs:wrapper:shims` and `shims:installs:wrapper`
     do not loop. Point at the archived t2153 plan for the full matrix and
     probe.

   Keep it to about 6-9 lines and current-state wording. No narrative of past
   versions beyond naming the measured mise version.
2. **No code or test changes.** `tmux_exec.py`, `spawn_path.sh` and
   `aitask_codeagent.sh` stay as they are.
3. **Step 9 (Post-Implementation):** archive via the shared workflow. Final
   Implementation Notes carry the scope statement, the table above and the
   probe script below verbatim, as durable closure evidence.

### Probe script (closure evidence)

```bash
S=$(mktemp -d); MD=$HOME/.local/share/mise; mkdir -p "$S/otherbin"
cat > "$S/otherbin/gh" <<'EOF'
#!/bin/bash
d=$(( ${PROBE_DEPTH:-0} + 1 )); export PROBE_DEPTH=$d
echo "wrapper depth=$d" >&2
(( d > 4 )) && { echo "LOOP" >&2; exit 99; }
exec mise x "gh" -- "gh" "$@"
EOF
chmod +x "$S/otherbin/gh"
O=$S/otherbin SH=$MD/shims C=$MD/command-wrappers/bin I=$(ls -d $MD/installs/gh/latest/*/bin)
run() { r=$(env -i HOME="$HOME" TERM=dumb PATH="$2" MISE_QUIET=1 timeout 20 gh --version 2>&1)
  if grep -q LOOP <<<"$r"; then v=LOOP; elif grep -q '^gh version' <<<"$r"; then v=ok; else v='?'; fi
  echo "$v  $1"; }
run "O:SH:I" "$O:$SH:$I:/usr/bin:/bin";   run "O:SH"   "$O:$SH:/usr/bin:/bin"
run "O:I"    "$O:$I:/usr/bin:/bin";       run "O:C:SH" "$O:$C:$SH:/usr/bin:/bin"
run "SH:O:I" "$SH:$O:$I:/usr/bin:/bin";   run "I:O:SH" "$I:$O:$SH:/usr/bin:/bin"
run "SH:I:O" "$SH:$I:$O:/usr/bin:/bin"
```

## Verification

- Re-run the probe script. Expected: `LOOP O:SH:I`, `ok` for every other row,
  matching the table.
- Re-read the edited bullet in context. It must agree with the "The rule"
  bullet above it and with the `normalize_spawn_path` docstring (unchanged). It
  must make no cross-platform universal claim, and every ordering it names must
  appear in the measured table.
- `git diff --stat` touches only `aidocs/framework/tmux_gateway.md`. No website
  page changes, so `check_links.py` does not apply.

## Risk

### Code-health risk: low
None identified. A single internal-doc bullet changes, with no code or test
change.

### Goal-achievement risk: low
- Custom wrappers outside `~/.local/bin` stay unprotected, and macOS, WSL and
  other distros weren't measured. This is accepted by explicit user decision
  and documented as a limitation with its reproduced trigger · severity: low ·
  → mitigation: none

## Final Implementation Notes
- **Actual work done:** I measured whether self-referential `mise x` wrappers
  appear outside `~/.local/bin`, then closed with an explicit acceptance of the
  uncovered case. The only change is in `aidocs/framework/tmux_gateway.md`:
  - The "Why only `~/.local/bin`" bullet is now scoped to Omarchy's writer.
    It previously read "that is where the wrappers live", a universal claim.
  - A new "Accepted limitation: wrappers in other dirs" bullet records the
    bounded evidence (one Omarchy host plus the Omarchy sources examined; other
    platforms not examined), the jdx/mise#8560 counterexample, and the
    reproduced orderings. Every ordering it names appears in the table above.
  - `tmux_exec.py`, `spawn_path.sh`, `aitask_codeagent.sh` and the tests are
    unchanged.
- **Deviations from plan:** One addition. The plan said the "Why only" bullet
  could stay as it was, but its first sentence was a universal claim that the
  new limitation bullet contradicts, so it was reworded to name Omarchy's
  writer.
- **Issues encountered:** The user rejected the first plan draft for two
  reasons:
  - It concluded "never on supported hosts" from one Omarchy host, while
    setting aside the upstream `.devcontainer/bin` wrapper as "off Omarchy".
  - Its documented trigger ("precedes shims with installs present") was
    contradicted by the plan's own `I:O:SH` row.

  Both were fixed. Claims are now bounded to what was examined, the user
  explicitly accepted the limitation (rather than adding an invoke pre-exec
  guard), and the doc names the tested orderings instead of inferring a rule.
- **Key decisions:**
  - No hazard-dir extension: no examined source writes wrappers to another
    fixed dir, and moving user tool dirs behind mise re-breaks t2144.
  - No `ait codeagent invoke` pre-exec guard, by user decision. The guard would
    protect agent launches only; it was offered and declined.
- **Verification:** the plan's probe script, re-run verbatim at implementation
  time on mise 2026.10.12 (`env -i`, so no `__MISE_*` variables; `gh`
  installed by mise):
  ```
  LOOP  O:SH:I
  ok  O:SH
  ok  O:I
  ok  O:C:SH
  ok  SH:O:I
  ok  I:O:SH
  ok  SH:I:O
  ok  O:omarchy:SH
  ```
  The host scan found 20 SELF wrappers, all in `~/.local/bin`. The other
  `mise`-mentioning scripts (2 in `~/.local/bin`, 8 in `/usr/bin`, 8 in
  `/usr/share/omarchy/bin`) don't loop. `git diff --stat` shows only
  `aidocs/framework/tmux_gateway.md` (14+/4-).
- **Upstream defects identified:**
  - jdx/mise (`src/cli/exec.rs`, per #8560's description): the #8560 fix
    builds its lookup PATH as "entries not in the pristine PATH, then the
    original entries minus shims". Without `__MISE_*` session variables, an
    inherited `installs/<tool>/…/bin` entry counts as original, so a
    self-referential wrapper ordered `wrapper:shims:installs` still recurses on
    mise 2026.10.12. This is external, not an aitasks defect.
