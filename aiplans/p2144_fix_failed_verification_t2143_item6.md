---
Task: t2144_fix_failed_verification_t2143_item6.md
Base branch: main
Output branch: main
---

# t2144 — Spawn-PATH normalization must not reorder a healthy mise shell (t2143 item 6)

## Context

t1689 (`86b4b96af`) normalizes the PATH every framework-spawned tmux client
carries. The aim is that a pane never runs a `mise x <agent> -- <agent>` wrapper
ahead of mise's own entries; with no `__MISE_*` vars set, that wrapper re-execs
itself forever. The t1689 rule is: if PATH holds a mise entry
(`<data>/shims`, `<data>/installs/*`), emit the leading framework bins, then
every mise entry, then everything else.

t2143 item 6 failed: a normal mise-activated shell gets reordered too. A fresh
capture on this host (`bash -ic 'eval "$(mise hook-env -s bash)"; echo $PATH'`,
saved in the scratchpad) reads:

```
~/.opencode/bin : ~/flutter/bin : <data>/command-wrappers/bin : <data>/shims : <data>/command-wrappers/bin :
~/.aitask/bin : <data>/installs/{java,antigravity-cli,claude,codex,gh,go,node,opencode}… : ~/.opencode/bin :
~/flutter/bin : /usr/share/omarchy/bin : ~/Android/flutter/bin : /usr/local/sbin : /usr/local/bin : /usr/bin :
~/.local/bin : /usr/lib/jvm/default/bin : /usr/bin/{site,vendor,core}_perl
```

`~/.bashrc` prepends `~/.opencode/bin` and `~/flutter/bin` **after** mise
activates. That is deliberate: `~/.opencode/bin/opencode` is a real 185 MB
binary that is meant to win over mise's `installs/opencode/.../opencode`. Any
"hoist the mise block" rule changes that (opencode resolves to
`<data>/shims/opencode`, `~/.aitask/bin` moves 6 → 18), and so does the first
draft of this plan ("trust a mise-led PATH"), because this PATH is not mise-led.

### What actually separates the hazard from the healthy order

- **PATH shape alone can't.** Both the healthy capture and the t1689/t2143 bad
  order (`~/.local/bin:/usr/share/omarchy/bin:<data>/shims:/usr/bin`) put a
  non-mise entry first.
- **Shadowing can't either.** In the healthy order `~/.opencode/bin/opencode`
  shadows a mise-managed name too.
- **What does separate them is the dir holding the looping wrapper.** All 23
  `mise use -g … && exec mise x <n> -- <n>` wrappers on this host (`claude`,
  `codex`, `opencode`, `gh`, `gemini`, `grok`, …) live in `~/.local/bin`; they are
  written there by `omarchy-mise-install`. t1689's incident was `~/.local/bin`
  ahead of the shims dir. The user's `~/.bashrc` says the same: "`~/.local/bin`
  … Do NOT prepend it: ahead of mise's shims dir it shadows the mise tool
  installs and the omarchy-mise-install wrappers … exec themselves forever
  (omacom/omarchy#7360)". In the healthy order `~/.local/bin` already comes after
  every mise entry.

## New rule (minimal displacement)

```
mise entry  = anything under <mise_data>/       (prefix "<data>/"; shims, installs, command-wrappers, …)
hazard dir  = $HOME/.local/bin                  (entries compare with trailing "/" stripped)
L           = index of the LAST mise entry
if no mise entry, or no hazard entry before L:   unchanged, byte for byte
else: entries[0..L] with the hazard entries taken out (order kept),
      then those hazard entries (order kept),
      then entries[L+1..] verbatim
```

- **Healthy activated shell → unchanged.** `~/.local/bin` sits behind the last
  mise entry, so `spawn_env()` returns `None` and every tool keeps the caller's
  precedence, `~/.opencode/bin` and `~/.aitask/bin` included.
- **Bad order → protected.** `~/.local/bin` is moved behind every mise entry;
  nothing else moves:
  `~/.local/bin:/usr/share/omarchy/bin:shims:/usr/bin` →
  `/usr/share/omarchy/bin:shims:~/.local/bin:/usr/bin`.
- **Past the last mise entry, not the first.** This closes a gap: a leading
  mise dir that does not provide the agent (`command-wrappers/bin` is empty on
  this host right now), followed by `~/.local/bin`, followed by the dir that
  does provide it, is still fixed. It is also never worse than the activated
  shell, which puts `~/.local/bin` behind all mise entries anyway.
- **The framework-bin hoist goes away.** It existed only so the hoisted mise
  block would not shadow `~/.aitask/bin/python3`. Now no mise entry moves
  forward, so a framework bin's position relative to mise never changes. With
  it go the `AITASKS_HOME` input and the `lead` group.
- **Item 6 wording.** The item says the pane PATH "still starts with
  `~/.aitask/bin`". On this host the healthy PATH starts with
  `~/.opencode/bin`, so the satisfiable form is "the pane PATH equals the
  caller's PATH". This plan verifies that form.
- **Idempotent.** After one pass no hazard entry sits before the last mise
  entry. Empty entries survive, and the function is still pure string work:
  `lru_cache`, the no-fork shell mirror and `TestShellParity` all keep working.
  An empty data dir (`MISE_DATA_DIR=/`) or an unset `HOME` returns the PATH
  unchanged: a bare `/` prefix would match everything, and with no `HOME` there
  is no hazard dir.

## Implementation steps

1. **`.aitask-scripts/lib/tmux_exec.py`**, `_normalize_cached` and
   `normalize_spawn_path`:
   ```python
   @functools.lru_cache(maxsize=32)
   def _normalize_cached(path, home, mise_data_dir, xdg_data_home):
       if mise_data_dir:   data = mise_data_dir.rstrip("/")
       elif xdg_data_home: data = xdg_data_home.rstrip("/") + "/mise"
       elif home:          data = home.rstrip("/") + "/.local/share/mise"
       else:               return path
       if not data or not home:
           return path
       prefix, hazard = data + "/", home.rstrip("/") + "/.local/bin"
       entries = path.split(":")
       norms = [_strip_entry(e) for e in entries]
       last = max((i for i, n in enumerate(norms) if n.startswith(prefix)), default=-1)
       if last < 0:
           # No mise entry: identity. Must come first: entries[:-1] and
           # entries[0:] would otherwise duplicate a ~/.local/bin entry.
           return path
       # Through `last` INCLUSIVE, the same span `kept` filters: a custom data
       # root (MISE_DATA_DIR=$HOME/.local) makes ~/.local/bin a mise entry too,
       # and it can be the last one; an exclusive bound would drop it.
       moved = [e for i, e in enumerate(entries[:last + 1]) if norms[i] == hazard]
       if not moved:
           return path
       kept = [e for i, e in enumerate(entries[:last + 1]) if norms[i] != hazard]
       return ":".join(kept + moved + entries[last + 1:])
   ```
   `normalize_spawn_path` stops passing `AITASKS_HOME`. Rewrite its docstring:
   state the rule, drop "the order a mise-activated interactive shell already
   has", and say why `~/.local/bin` is the one hazard dir (wrapper location,
   t1689 incident, t2144 counterexample). Check module-docstring policy 4 for any
   restated rule. Today it only says "normalized PATH", which stays true.
2. **`.aitask-scripts/lib/spawn_path.sh`**, `ait_spawn_path_normalize`: make
   the same change in the existing no-fork style. Pass 1 walks
   `${s%%:*}`/`${s#*:}` to find the index of the last mise entry and to check
   whether a hazard entry comes at or before it. If there is no mise entry, return
   right after pass 1 with `AIT_SPAWN_PATH` still the input. This is the same
   guard as Python's `last < 0`, and it runs before any group is built. Pass 2 builds `kept` / `moved` /
   `tail` as `:`-joined strings with counts, as today. Drop `fw1`/`fw2` and
   `AITASKS_HOME`. Rewrite the header "Rule:" comment.
3. **`tests/test_tmux_exec.py`**:
   - Rewrite `_NORMALIZE_CASES`. `test_table`, `test_idempotent` and
     `TestShellParity.test_table` run every case through both implementations.
     `C` = `<data>/command-wrappers/bin`, `I` = `<data>/installs`. Cases:
     1. no mise entry, `LOCAL` first → unchanged: `LOCAL:/usr/bin` →
        `LOCAL:/usr/bin`. This is the regression case for the identity guard:
        without it, the draft returned `LOCAL:LOCAL:/usr/bin` and added another
        copy on each pass, which `test_idempotent` also catches. Also
        `/usr/bin:LOCAL` and `LOCAL:/usr/bin:LOCAL` → unchanged.
     2. empty path → `""`
     3. `LOCAL:SHIMS:/usr/bin` → `SHIMS:LOCAL:/usr/bin` (the t1689 order)
     4. the t2143 bad env:
        `LOCAL:/usr/share/omarchy/bin:SHIMS:/usr/bin` →
        `/usr/share/omarchy/bin:SHIMS:LOCAL:/usr/bin` (only `LOCAL` moves)
     5. `LOCAL` goes behind the **last** mise entry:
        `FW:LOCAL:/usr/share/omarchy/bin:SHIMS:I/node/20/bin:/usr/bin` →
        `FW:/usr/share/omarchy/bin:SHIMS:I/node/20/bin:LOCAL:/usr/bin`
     6. **regression, the fresh activated capture** (reduced, same shape):
        `/h/.opencode/bin:/h/flutter/bin:C:SHIMS:C:FW:I/java/21/bin:I/opencode/latest/node_modules/.bin:/h/.opencode/bin:/usr/share/omarchy/bin:/usr/bin:LOCAL:/usr/bin/core_perl`
        → unchanged
     7. the t2143-finding activated order:
        `C:FW:/h/.opencode/bin:/h/flutter/bin:I/java/21/bin:/usr/bin:LOCAL` →
        unchanged
     8. command-wrappers counts as mise: `LOCAL:C:/usr/bin` → `C:LOCAL:/usr/bin`
     9. `LOCAL` between mise entries still moves past the last one:
        `C:LOCAL:SHIMS:/usr/bin` → `C:SHIMS:LOCAL:/usr/bin`
     10. a non-hazard dir ahead of mise keeps its place:
         `/usr/bin:FW:SHIMS` → unchanged
     11. duplicates move in order, and one already behind stays:
         `LOCAL:SHIMS:LOCAL/` → `SHIMS:LOCAL:LOCAL/`
     12. empty entries survive: `LOCAL::SHIMS:` → `:SHIMS:LOCAL:`
     13. trailing slashes compare equal and are kept: `LOCAL/:SHIMS/` →
         `SHIMS/:LOCAL/`
     14. `MISE_DATA_DIR=/m/`: `LOCAL:/m/shims:SHIMS` → `/m/shims:LOCAL:SHIMS`
         (the default dir is no longer mise)
     15. `XDG_DATA_HOME=/x`: `LOCAL:/x/mise/shims` → `/x/mise/shims:LOCAL`
     16. a sibling dir sharing the prefix is not mise:
         `LOCAL:/h/.local/share/mise-old/bin` → unchanged
     17. `MISE_DATA_DIR=/` → unchanged
     18. no `HOME` (with or without `MISE_DATA_DIR`) → unchanged
     19. overlapping roles (`MISE_DATA_DIR=/h/.local`, so `~/.local/bin` is a
         mise entry as well): `LOCAL:/h/.local/shims:LOCAL/` →
         `/h/.local/shims:LOCAL:LOCAL/`. No entry is dropped. The
         exclusive-bound draft returned `/h/.local/shims:LOCAL`.
   - Add `test_preserves_entries`: for every table case, check that the output
     is a permutation of the input (`sorted(split(":"))` is equal), which
     guards against dropped or duplicated entries. Run it through Python and
     the shell mirror. Pre-plan fuzzing of the corrected algorithm (15k random
     PATHs over the default, `$HOME/.local` and `$HOME` data roots) found no
     multiset or idempotence violations.
   - `TestResolveSpawnExe`: today the fixture's working `tmux` lives in a plain
     `sys/` dir, which the new rule no longer moves. Move it to
     `<home>/.local/bin` (orig `<home>/.local/bin:<shims>:/usr/bin`), so
     normalization still puts the failing shims `tmux` first and the pin is
     still exercised. Update the expected normalized string and the case
     labels.
   - `_BAD_PATH` → `_GOOD_PATH` (`LOCAL:SHIMS:/usr/bin` → `SHIMS:LOCAL:/usr/bin`)
     is unchanged, so `TestSpawnEnvPlumbing` and `TestPersistentPrefixSetenv`
     keep passing as written.
4. **`tests/test_tmux_spawn_path_live.sh`**:
   - Decoy section: make the decoy realistic for the new rule. Put a symlink to
     `$TMUX_BIN` in `$LOCALBIN/tmux` and set
     `DECOY_PATH="$LOCALBIN:$SHIMS:$TMUX_DIR:/usr/bin:/bin"`. The control
     `command -v tmux` then expects `$LOCALBIN/tmux`. Remove the symlink with
     `$SHIMS/tmux` at the end of the section.
   - New "activated order" section after "Healthy order". Add a user tool dir
     `$FIX/userbin` whose `fakeagent` writes `USER`, then
     `ACTIVATED_PATH="$FIX/userbin:$TMUX_DIR:$FHOME/.local/share/mise/command-wrappers/bin:$SHIMS:/usr/bin:/bin:$LOCALBIN"`.
     Through both `TmuxClient.run` and `ait_tmux`, assert (a) the pane PATH
     equals `ACTIVATED_PATH` verbatim and (b) `fakeagent` in the pane runs the
     user's binary (`USER`). Under t1689 the mise entries are hoisted, so both
     assertions fail on the old code.
5. **`aidocs/framework/tmux_gateway.md`** ("The rule" bullet, ~l.150, plus the
   hazard paragraph ~l.143): restate the rule, the reason it moves only
   `~/.local/bin`, and the fact that a healthy activated shell is unchanged.
   Drop the "order a mise-activated shell already has" claim.
6. **Step 9 (Post-Implementation)**: archival via the shared workflow.

### Post-phase (risk mitigations)

1. [verify_on_host_activated_path] On this host:
   - Feed both normalizers (Python `normalize_spawn_path`; shell
     `ait_spawn_path_normalize` via `bash -c 'source …'`) three PATHs:
     - the fresh activated capture (`activated_path.txt` in the scratchpad,
       re-captured with
       `bash -ic 'eval "$(mise hook-env -s bash)"; echo "$PATH"'`)
     - the t2143-finding order
     - the t2143 bad env
   - Pass when the two implementations agree and the first two come back
     byte-for-byte unchanged.
   - Start a scratch tmux server (`-L ait_v2144`; never touch `-L ait`; unset
     `TMUX`/`TMUX_PANE`; `AITASKS_TMUX_SOCKET=ait_v2144`). From each PATH, spawn
     panes through `ait_tmux new-window` and through
     `TmuxClient.run(["new-window", …])`. Each pane records `$PATH` and
     `command -v opencode claude`.
   - Pass when:
     - the activated pane's PATH equals the caller's;
     - `opencode` resolves to `~/.opencode/bin/opencode`;
     - in the bad-env pane, `<data>/shims` comes before `~/.local/bin`, and
       `claude` does not resolve to `~/.local/bin/claude`.
   - Kill only the scratch server. Record the trimmed outputs in Final
     Implementation Notes.

## Verification

- `python3 -m pytest tests/test_tmux_exec.py -q`
- `bash tests/test_tmux_spawn_path_live.sh` (bad-order, control-mode,
  persistence, decoy, healthy, and the new activated-order sections)
- `bash tests/test_codeagent.sh`: Test 32 uses
  `.local/bin:shims:tools`, which is still reordered.
- `shellcheck .aitask-scripts/lib/spawn_path.sh`
- Negative control: copy `git show HEAD:.aitask-scripts/lib/{spawn_path.sh,tmux_exec.py}`
  into a scratch lib dir. Run the new activated-capture case (6) and the live
  activated-order assertions against it. They must fail there. No stash, no
  restore.
- `bash tests/run_all_python_tests.sh`. Read only the final verdict line, and
  check `${PIPESTATUS[0]}` if piping.

## Risk

### Code-health risk: medium
- The output changes for every other-led mise PATH, from a full reorder to
  moving `~/.local/bin` only. Two parity-pinned implementations and three test
  fixtures change (the table, the `TestResolveSpawnExe` fixture, the live
  decoy). Bounded by the shared table running through both implementations,
  plus idempotency and the live tmux test · severity: medium · → mitigation:
  none

### Goal-achievement risk: medium
- **Residual:** a `mise x` wrapper in a dir other than `~/.local/bin`, placed
  ahead of mise entries, is no longer protected. t1689 hoisted mise ahead of
  every dir. All observed wrappers (23 on this host, plus the t1689 incident)
  are in `~/.local/bin`, and the Omarchy docs and the user's rc name that same
  dir. Protecting the general case would mean sniffing file contents on the
  per-call hot path, which t1689 already rejected · severity: medium ·
  → mitigation: wrapper_dirs_beyond_local_bin
- Item 6 is host-specific. The unit table uses reduced copies of the real
  PATHs · severity: low (residual: addressed by inline post-phase
  verify_on_host_activated_path) · → mitigation: inline post-phase
  verify_on_host_activated_path

### Planned mitigations
- timing: post-phase | name: verify_on_host_activated_path | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: item 6 is host-specific; reduced table PATHs may not match the real activated PATH | desc: Normalize this host's fresh activated PATH, the t2143-finding order and the t2143 bad env with both implementations, and spawn panes from each on a scratch tmux server, checking PATH and opencode/claude resolution
- timing: after | name: wrapper_dirs_beyond_local_bin | type: enhancement | priority: low | effort: medium | inline_risk: medium | added_complexity: medium | addresses: residual — `mise x` wrappers outside ~/.local/bin are no longer protected | desc: Record whether self-referential `mise x` wrappers ever appear outside ~/.local/bin (e.g. $XDG_BIN_HOME, /usr/local/bin) on supported hosts; if they do, extend the hazard-dir set (or add a targeted pre-exec guard in ait codeagent invoke) rather than reinstating the full reorder

## Final Implementation Notes
- **Actual work done:** Replaced t1689's "hoist every mise entry" normalization
  with a minimal displacement. `$HOME/.local/bin` entries that come before the
  LAST mise entry (anything under `<mise_data>/`) move to just after it, and
  nothing else moves. It is implemented in `tmux_exec.py::_normalize_cached`
  and `spawn_path.sh::ait_spawn_path_normalize` (two-pass, no fork), kept in
  parity. The framework-bin hoist and the `AITASKS_HOME` input are removed.
  Updated comments in `tmux_exec.sh` and `aitask_codeagent.sh` and the rule
  in `aidocs/framework/tmux_gateway.md`.
- **Deviations from plan:** Two `TestResolveSpawnExe` tests
  (`test_relative_entry_resolves_from_the_childs_cwd`,
  `test_symlink_dotdot_cwd_keeps_the_kernels_meaning`) depended on the old rule
  moving a *relative* `bin` entry behind the shims. The new rule only ever
  moves the absolute `~/.local/bin` backwards, so a gateway can no longer pin a
  relative entry. Their `resolve_spawn_exe` legs now take an explicit
  reordered spawn PATH. Their gateway legs use a PATH that normalization
  really reorders (an emptied `~/.local/bin` ahead of the relative `bin`).
  `TestShellParity.test_defaults_to_path` now uses `bashdir:LOCAL:SHIMS`.
  The shell mirror also got its own idempotency and entry-preservation test.
- **Issues encountered:** Two plan reviews caught bugs in the draft algorithm,
  and both are now regression cases:
  - no mise entry → `last == -1` → `entries[:-1]` duplicated `~/.local/bin`
    on every pass;
  - an exclusive `moved` bound dropped `~/.local/bin` when it was itself the
    last mise entry (`MISE_DATA_DIR=$HOME/.local`).

  The first plan's "trust a mise-led PATH" rule was also rejected: the real
  activated PATH starts with `~/.opencode/bin` (the rc prepends it after
  activation).
- **Key decisions:** `~/.local/bin` is the only hazard dir. All 23
  self-referential `mise use … && exec mise x <n> -- <n>` wrappers on this host
  live there (`omarchy-mise-install`), and that is also where the t1689
  incident and the user's `~/.bashrc` warning point. PATH shape and shadowing
  cannot separate the two cases, because `~/.opencode/bin/opencode`
  legitimately shadows mise's opencode. Item 6's literal wording ("pane PATH
  still starts with `~/.aitask/bin`") cannot be satisfied on this host. The
  verified form is "pane PATH == caller PATH".
- **Verification:**
  - `test_tmux_exec.py`: 85 passed.
  - `test_tmux_spawn_path_live.sh`: 22/22.
  - `test_codeagent.sh`: 258/258 (Test 32 still reordered).
  - `test_session_hook.sh`: 242/242.
  - `test_setup_tmux_default_session.sh`: 55/55.
  - shellcheck: clean.
  - `run_all_python_tests.sh`: `PYTHON SUITE: PASSED (runner=pytest,
    exit=0)` (9913 passed / 6 skipped, serial carve-out 13 passed).
  - Negative control (`git archive HEAD` copy with the new tests): 4 unit
    tests fail (normalize table, shell table, `test_defaults_to_path`,
    `test_relative_entry_…`) and 4 live activated-order assertions fail (pane
    got shims first and `REAL` instead of `USER`).
- **Post-phase verify_on_host_activated_path** (scratch `-L ait_v2144`, killed
  afterwards; `-L ait` untouched):
  - Fresh activated capture (`bash -ic 'eval "$(mise hook-env -s bash)"'`)
    and the t2143-finding order: Python/shell parity ok, unchanged=yes.
  - t2143 bad env: becomes
    `/usr/share/omarchy/bin:<data>/shims:~/.local/bin:/usr/bin:/bin`.
  - Activated panes through both gateways: pane PATH == caller PATH,
    `opencode` → `~/.opencode/bin/opencode`, `claude` →
    `<data>/command-wrappers/bin/claude`.
  - Bad-env panes: shims@2 before `~/.local/bin`@3, `claude` →
    `<data>/shims/claude` (not the `~/.local/bin` wrapper).
- **Upstream defects identified:** None
