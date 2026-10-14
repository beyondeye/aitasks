---
Task: t1982_manual_verification_jump_to_linked_trail_action_followup.md
Base branch: main
Output branch: main
---

# t1982 — Manual verification of t1957_4's `L` Linked Trails jump: auto-execution record

Strategy: autonomous. Code under test: `main` at `aa6b5fb2a` (t1957_4) with an
unrelated dirty working tree (goengines/, archive_iter.py — not touched by this
verification). All six items passed.

## Why a fixture replaced `aitasks_mobile`

The checklist assumed an `aitasks_mobile` trail linked to a trail here. That link
cannot exist on this host: `aitasks_mobile` is on framework **0.27.0**
(`.aitask-scripts/VERSION`), has no `ait artifact` command, and its export
(`trail_links.py export` run in its root) returns `trails: []`. A real-registry
scan of every local trail (11 trails) returned **no links at all**, only the two
`partial` rows for thinking_app / thinking_backend (t1978).

So two scratch projects were built and added to a **copy** of the registry
(`AITASKS_PROJECTS_INDEX`, the real `~/.config/aitasks/projects.yaml` was never
written):

- `verify_ymob` (session `vf_ymob`): `.aitask-scripts` symlinked to this checkout
  (current framework); trail `art:trail-vf-ymob` whose member `t7` has
  `xdeprepo: aitasks`, `xdeps: [1118]` → rev-xdeps link to the local
  `art:trail-mobile-shadow-driving` (members aitasks#1118, #1118_1..5).
- `verify_zold` (session `vf_zold`): same, but `board/trails_app.py` is a copy
  with every `--trail` rewritten to `--xtrail` (version skew; `grep -c -- --trail`
  → 0).

The real thinking_app / thinking_backend registry entries were kept, so the
incomplete-scan rows are real data, not fixtures.

## Isolation

- Private tmux server `-L ait_verify_1982 -f /dev/null`; every pane got
  `AITASKS_TMUX_SOCKET=ait_verify_1982`, `AITASKS_PROJECTS_INDEX=<fixture>`,
  `AIT_NO_SYSTEMD_RUN=1` (session `-e` and `set-environment -g`).
- A **real attached client** (`script` pty running `tmux -L … attach`), so
  `switch-client` had a client to move and its effect was observable with
  `list-clients` (client `/dev/pts/68`). Nothing was stubbed: the real
  `ait trails` / `ait board` ran in the real repo.
- The user's `ait` server was never addressed (every call went through
  `env -u TMUX -u TMUX_PANE tmux -L ait_verify_1982`).

## Execution Log

### Item 1
- Item text: From `ait trails`, `L` on a trail with cross-repo members lists the linked trail, error rows for thinking_app / thinking_backend, and the incomplete note
- Approach: TUI interaction (isolated tmux)
- Action run: `./ait trails --trail art:trail-mobile-shadow-driving`; footer showed `L Linked Trails`; send `L`
- Output (trimmed): toast "Searching for linked trails in other projects…", then the dialog:
  ```
  Linked trails — ↑/↓ move · Enter jump · Esc cancel
  verify_ymob · art:trail-vf-ymob · t1982 fixture trail (ymob)
    └ rev-xdeps: verify_ymob#7 xdeps aitasks#1118
  verify_zold · art:trail-vf-zold · t1982 fixture trail (zold)
    └ rev-xdeps: verify_zold#7 xdeps aitasks#1118
  Some projects could not be fully searched — the list may be incomplete:
  thinking_app: searched in part (unloadable trail(s): art:trail-build-test-speed, art:trail-localization-programme)
  thinking_backend: searched in part (unloadable trail(s): art:trail-new-prod-and-dev-servers)
  Cancel
  ```
- Verdict: pass (with `verify_ymob` standing in for `aitasks_mobile`, see above)

### Item 3 (run before item 2: it needs the session absent)
- Item text: with the target session stopped, the jump starts it first, then switches and opens the trail
- Approach: TUI interaction
- Action run: Enter on the `verify_ymob` row with no `vf_ymob` session on the server
- Output (trimmed): within 2s `list-clients` → `/dev/pts/68 session=vf_ymob`; windows
  `vf_ymob:0 monitor start="ait monitor"`, `vf_ymob:1 trails start=./ait trails --trail art:trail-vf-ymob`;
  active window `trails`, header `By-Trail: "t1982 fixture trail (ymob)"`
- Verdict: pass

### Item 2
- Item text: Enter switches the client to the project session with the trail focused (running instance, or a new `trails` window)
- Approach: TUI interaction, both sub-cases
- Action run:
  - (a) running instance: `^w` in `vf_ymob:trails` (header → "no trail selected"), `switch-client` back to `aitasks`, `L`, Enter
  - (b) new window: `kill-window -t vf_ymob:trails`, back to `aitasks`, `L`, Enter
- Output (trimmed): (a) client → `vf_ymob`; `trails` pane pid unchanged (3191080), header back to the fixture trail; (b) client → `vf_ymob`; new `trails` window (pid 3202776, `./ait trails --trail art:trail-vf-ymob`), still 2 windows / 1 `vf_ymob` session
- Verdict: pass

### Item 4
- Item text: same flow from `ait board` By-Trail (`z`); `L` absent in other views and while no trail is loaded
- Approach: TUI interaction
- Action run: `./ait board` in a new window; views `l f i y a` then `z` (no trail), `s` → "Mobile shadow-agent driving…" → Enter; `a` and back to `z` with the trail loaded; `L`, Enter on `verify_ymob`
- Output (trimmed): `Linked` count in footer: views l/f/i/y/a = 0; `z` with no trail = 0 (footer `? Keys q Quit ⏎ View/Edit s Select Trail S Sync n New Task O Options`); `z` with trail = 1 (`… v Summary L Linked Trails n New Task …`); `a` with trail loaded = 0. Dialog identical to item 1; client → `vf_ymob`, existing `trails` pane (pid 3202776) re-focused
- Verdict: pass

### Item 5
- Item text: version-skew warning shows in THIS TUI before switching; Stay here / Switch; then `ait projects remove` on the copy
- Approach: TUI interaction + CLI
- Action run: from `ait trails` (aitasks:0), `L`, Down, Enter on `verify_zold`; Tab + Enter ("Stay here"); repeat with Enter ("Switch"); `echo y | AITASKS_PROJECTS_INDEX=<fixture> ./ait projects remove verify_zold`
- Output (trimmed):
  ```
  Before switching to tmux session 'vf_zold':
  • verify_zold runs an older aitasks without trail jumps — run `ait upgrade` there; you will land in its session without
  art:trail-vf-zold opened
       Switch         Stay here
  ```
  While the dialog was up, `/dev/pts/68 session=aitasks` (the prepare step had bootstrapped `vf_zold`, no client effect). Stay here → client stayed on `aitasks`, `vf_zold` still only `0 monitor`. Switch → `/dev/pts/68 session=vf_zold`, windows `0 monitor` only (no trails launched). `Removed verify_zold`; fixture registry count 0; real registry `grep -c verify` → 0
- Verdict: pass

### Item 6
- Item text: from outside the aitasks tmux server, the jump only shows the manual command and starts no session
- Approach: TUI interaction, both "outside" cases the plan names (finding 6)
- Action run: killed `vf_ymob` and `vf_zold` first; (a) `env -u TMUX -u TMUX_PANE ./ait trails --trail art:trail-mobile-shadow-driving`; (b) `AITASKS_TMUX_SOCKET=ait_verify_1982_other ./ait trails …` (gateway names another, absent server); in each `L`, Enter on `verify_ymob`
- Output (trimmed): both cases:
  ```
  Not in an aitasks tmux session — open the trail with: ait
  projects exec verify_ymob -- ./ait trails --trail
  art:trail-vf-ymob
  ```
  `ls` afterwards: only `aitasks` (no `vf_ymob`); `tmux -L ait_verify_1982_other ls` → `error connecting … (No such file or directory)` (no server was started there either); client stayed on `aitasks`
- Verdict: pass

## Cleanup

- `tmux -L ait_verify_1982 kill-server`; the `script`/`sleep` client processes
  are gone (`pgrep -af ait_verify_1982` empty).
- Scratch fixture (`<scratchpad>/fx/`: ymob, zold, projects.yaml) deleted after
  this record was written.
- No files under this repository's `aitasks/` / `aiplans/` were changed other
  than the checklist and this record.

## Fixture scripts (verbatim)

`build_fx.py` (run as `python build_fx.py <scratch>/fx`):

```python
import json, os, shutil, subprocess, sys
from pathlib import Path
REPO = Path("/home/ddt/Work/aitasks")
sys.path.insert(0, str(REPO / ".aitask-scripts/lib")); sys.path.insert(0, str(REPO / "tests"))
import trail_schema
from test_trail_links import _trail_doc
F = Path(os.path.realpath(sys.argv[1]))
SCRIPTS = REPO / ".aitask-scripts"

def git(root, *a):
    subprocess.run(["git", "-C", str(root), *a], check=True, stdout=subprocess.DEVNULL)

def repo(d, name, sess, skew=False):
    root = F / d
    (root / "aitasks/metadata").mkdir(parents=True)
    (root / "aitasks/archived").mkdir()
    (root / "aitasks/metadata/project_config.yaml").write_text(
        f"project:\n  name: {name}\n  git_remote: none\ntmux:\n  default_session: {sess}\n")
    shutil.copy2(REPO / "ait", root / "ait")
    if not skew:
        (root / ".aitask-scripts").symlink_to(SCRIPTS)
    else:
        sd = root / ".aitask-scripts"; sd.mkdir()
        for p in SCRIPTS.iterdir():
            if p.name != "board":
                (sd / p.name).symlink_to(p)
        bd = sd / "board"; bd.mkdir()
        for p in (SCRIPTS / "board").iterdir():
            if p.name == "trails_app.py":
                (bd / p.name).write_text(p.read_text().replace("--trail", "--xtrail"))
            elif p.name != "__pycache__":
                (bd / p.name).symlink_to(p)
    git(root, "init", "-q")
    for tid, extra in (("5", ""), ("7", "xdeprepo: aitasks\nxdeps: [1118]\n")):
        (root / f"aitasks/t{tid}_vf_task_{tid}.md").write_text(
            f"---\nstatus: Ready\npriority: low\neffort: low\n{extra}---\nfixture task {tid} for t1982\n")
    handle = f"art:trail-vf-{d}"
    doc = _trail_doc(f"{name}#5", [f"{name}#5", f"{name}#7"])
    doc["trail_id"] = f"trail-vf-{d}"; doc["title"] = f"t1982 fixture trail ({d})"
    trail_schema.validate_trail(doc); (F / "chk.json").write_text(json.dumps(doc)); trail_schema.load_trail(str(F / "chk.json"))
    blob = F / f"{d}.json"; blob.write_text(json.dumps(doc))
    git(root, "add", "-A"); git(root, "commit", "-q", "-m", "fixture")
    p = subprocess.run([str(root / ".aitask-scripts/aitask_artifact.sh"), "create", "5", str(blob),
                        "--kind", "implementation_trail", "--handle", handle],
                       capture_output=True, text=True, cwd=root, timeout=120)
    print(d, "artifact rc", p.returncode, p.stdout[-300:], p.stderr[-300:])
    return root

y = repo("ymob", "verify_ymob", "vf_ymob")
z = repo("zold", "verify_zold", "vf_zold", skew=True)
reg = (Path.home() / ".config/aitasks/projects.yaml").read_text()
reg += f"  - name: verify_ymob\n    path: {y}\n  - name: verify_zold\n    path: {z}\n"
(F / "projects.yaml").write_text(reg)
print("OK", y, z)
```

`vt.sh` (sourced; `S` = the session scratchpad):

```bash
# helpers for t1982 isolated tmux verification
SOCK=ait_verify_1982
S=/tmp/claude-1000/-home-ddt-Work-aitasks/28e1afc1-3a2f-41fc-8ee2-fca31c6b48c4/scratchpad
T() { env -u TMUX -u TMUX_PANE tmux -L $SOCK "$@"; }
start_server() {
  T -f /dev/null new-session -d -s aitasks -x 200 -y 50 -c /home/ddt/Work/aitasks      -e AITASKS_TMUX_SOCKET=$SOCK -e AITASKS_PROJECTS_INDEX=$S/fx/projects.yaml -e AIT_NO_SYSTEMD_RUN=1
  T set-environment -g AITASKS_TMUX_SOCKET $SOCK
  T set-environment -g AITASKS_PROJECTS_INDEX $S/fx/projects.yaml
  T set-environment -g AIT_NO_SYSTEMD_RUN 1
  T set-option -g history-limit 5000
}
attach_client() {  # real pty client so switch-client has something to switch
  ( sleep infinity | env -u TMUX -u TMUX_PANE TERM=xterm-256color script -qfc "stty rows 50 cols 200; tmux -L $SOCK attach -t $1" /dev/null >/dev/null 2>&1 & )
}
cap() { T capture-pane -p -t "$1"; }
clients() { T list-clients -F '#{client_name} session=#{client_session}'; }
```
