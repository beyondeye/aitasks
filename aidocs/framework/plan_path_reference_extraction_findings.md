# Plan path-reference extraction: verified findings

How the framework decides which files a plan "references" — and the ways that
decision is currently wrong. Written as an input to **t1561** (generalize task
staleness detection), whose decision record has to answer the same question for
task premises: *given a task or plan, which files is it about, and have they
changed?*

The grammar these findings are about lives in
`.aitask-scripts/lib/plan_paths.py`, whose `extract()` returns every distinct
matching token, `./`-stripped and codepoint-sorted:

```python
_EXTENSIONS = ("sh", "py", "md", "yaml", "yml", "json", "toml")
_TOKEN = re.compile(
    r"[A-Za-z0-9_./-]+\.(?:" + "|".join(_EXTENSIONS) + r")")
```

**It is not the only extractor in the repository.** `aitask_change_surface.sh`
carries its own, deliberately broader one (t1263) with no extension allowlist —
so the findings below are about *this* grammar, not about the framework's every
notion of "which files does a text mention". The module docstring is the
authority on that split.

Its consumers are `lib/parallel_admission.py`,
`lib/parallel_admission_collect.py` and `lib/trail_gather.py` — which is why the
grammar is centralized rather than forked per call site. The remote drift check
was its first consumer and now uses the inverted search below instead (§7).

The same module also carries the **inverted** search that §3 below specifies:
`find_references(text, candidates)` (and `find_dir_references` for explicit
`<dir>/` mentions) tests each path git reported for a reference, with the §3
delimiter set, the §4 NFC mapping back to the original path and the §5
`surrogateescape` handling, and reports the section heading each mention sits
under. It has no extension list, so findings 1 and 2 do not apply to it.
`reference_kinds()` tiers its hits (full / bare / suffix). Its consumers are the
shadow's ownership-evidence helper (`lib/shadow_scope.py`) and the remote drift
check (`plan_paths.py --references`, through the lazy `lib/plan_paths_sh.sh`
bridge). The three consumers above still use `extract()`, for the reasons in §7.

The findings below were originally measured against the equivalent shell
pipeline this module replaced (`grep -oE … | sed 's|^\./||' | sort -u`); the
regex is byte-identical in meaning, so every one of them still reproduces. The
one behavioral difference is ordering — codepoint here, locale-collated `sort -u`
before — which no verdict depends on.

Before §7 the drift check intersected that output with
`git diff --name-only <base>...origin/<base>` by
exact full-line match (`grep -Fxf`). The intersection is what makes the stage
safe: a token that is not a real remote-changed path is discarded there. It is
also what makes every finding below a **false negative** — a file the framework
believes the plan does not mention.

Each finding was executed, not reasoned about. The commands reproduce them.

## 1. The extension list excludes most languages

The regex requires one of `sh|py|md|yaml|yml|json|toml`. A plan referencing Go,
Kotlin, Rust, TypeScript, C# or Java sources yields **zero** tokens, so every
consumer of this grammar has no path evidence for those projects' primary
sources. The drift check no longer uses it (§7); parallel admission and the
trail gatherer still do, and report the empty case as `no_extractable_paths`.

```bash
printf 'We modify `internal/pkg/server.go`.\n' \
  | grep -oE '[A-Za-z0-9_./-]+\.(sh|py|md|yaml|yml|json|toml)'   # -> no output
```

This is a sibling of the root-directory allowlist removed in t1275: the same
mistake on the other axis. It was left in place deliberately to keep that fix
surgical.

## 2. The token character class silently truncates real paths

`[A-Za-z0-9_./-]` excludes characters git permits in filenames. The failure is
not a clean miss — it emits a **wrong** path that can never match, with no
signal that anything was dropped:

```bash
printf 'node_modules/@scope/pkg.js app/x.storyboardc\n' \
  | grep -oE '(\./)?([A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]*\.[A-Za-z0-9]{1,10}'
# -> scope/pkg.js
# -> app/x.storyboard
```

Dropped entirely: paths containing spaces, non-ASCII, `+`, `@`; and every
extensionless file (`bin/run`, `src/Makefile`), which is structurally invisible.

A *longer* extension was a third failure of the same kind, and it hit tracked
files: `x/SKILL.md.j2` extracted as `x/SKILL.md`. `extract()`'s right boundary
fixes that one (§7). The charset gaps above remain.

## 3. Inverting the search removes the grammar but needs a delimitation rule

Scanning the plan for each **remote-changed** path (rather than extracting
candidates from the plan) eliminates the filename grammar entirely — the
candidate set becomes whatever git reports, byte for byte. It then requires
deciding which characters delimit a reference, which is a design question with
verified traps:

- A delimiter set of `[A-Za-z0-9_./-]` reports `src/app.py` as referenced by the
  text `src/app.py@v2`, and `src/a` by `src/a+b.py` — `@` and `+` are path
  characters, not delimiters.
- The same set splits two equivalent anchor forms, accepting `src/app.py:42`
  while rejecting `src/app.py#L20`.

A workable set is *whitespace plus prose punctuation*, `#` included — treating
everything else (`@ + ~ %`, alphanumerics, non-ASCII) as path continuation:

```bash
D='[][:space:]'"'"'"`(){}<>,;:!?|=*#[]'
esc=$(printf '%s' "$p" | sed 's/[][\.^$*+?(){}|]/\\&/g')
grep -qE "(^|${D})(\./)?${esc}(${D}|\.(${D}|\$)|\$)" "$PLAN_FILE"
```

One residual is undecidable: whitespace must delimit bare references, so a
remote path that is a whitespace-delimited prefix of a longer quoted path
(remote `src/my`, plan `` `src/my file.py` ``) over-reports. Over-reporting
costs one advisory prompt; under-reporting costs the whole signal.

## 4. Unicode normalization is a correctness gap, not a test-harness quirk

APFS/HFS+ store filenames decomposed, so `git diff` reports NFD while a plan
authored in an editor carries NFC. Comparison is byte-exact, so the file drops
out silently:

```bash
NFC=$(printf 'src/caf\303\251.py'); NFD=$(printf 'src/cafe\314\201.py')
printf 'edit `%s`\n' "$NFC" | grep -qF "$NFD" || echo "no match"
```

It reproduces on any NFD-on-disk repository, so it is testable on Linux — a
fixture that commits an NFD filename and references it in NFC is the macOS shape
without needing macOS.

Reconciling the forms requires normalizing both sides **and an explicit
normalized-to-original mapping**: `grep -oFf` emits the matched normalized
string with no link to the pattern that produced it, so the obvious loop reports
the NFC form instead of the path git named. Keep a parallel array and emit the
original by index. Two paths colliding under NFC should report *both* originals;
picking one silently drops a real remote change.

## 5. Git paths may not be valid UTF-8, and this helper must never fail

`aitask_remote_drift_check.sh` documents "always exit 0; never fails the
workflow". A strict decode breaks that contract:

```bash
printf 'src/caf\351.py\n' \
  | python3 -c 'import sys,unicodedata; sys.stdout.write(unicodedata.normalize("NFC", sys.stdin.read()))'
# UnicodeDecodeError, exit 1
```

and under `set -e` a bare `x=$(python3 …)` **aborts the script**. Any
normalization work needs `surrogateescape` on both decode and encode (verified
to round-trip the invalid byte exactly) plus an errexit-suppressing guard:

```bash
if ! normalized=$(… 2>/dev/null); then norm_ok=false; fi
```

## 6. Tooling caveat when testing any of this

`grep` is not necessarily GNU grep. On a machine where it resolves to
**ugrep**, `[^[:cntrl:][:print:]]` is rejected as an empty character class,
though GNU grep accepts it. A portable non-ASCII probe:

```bash
[ -n "$(LC_ALL=C tr -d '\000-\177' < "$file" | head -c 1)" ]
```

Both greps the helper actually uses were re-run under GNU grep and agree, but
verify any new bracket expression against both.

## 7. Consumer adoption: which consumers switched to the inverted search

Measured 2026-09-25 (t1877) on this repository's live corpus: every archived plan
(`aiplans/archived/**/*.md`, 331 files) against three deterministic windows of
10 consecutive first-parent `main` commits each (993 windows). A window stands
in for "the remote is ahead by these commits". It is a proxy, not recorded drift
history: it tells you how often a plan cites a file that a typical batch of
landed commits touches. Each window goes through the drift check's own path,
`plan_paths.py --references` fed NUL-delimited candidates, then the shell's
`full` → strong / `bare|suffix` → weak mapping:

```bash
python3 - <<'EOF'
import collections, glob, subprocess, sys
sys.path.insert(0, '.aitask-scripts/lib'); import plan_paths as pp
CLI = ['python3', '.aitask-scripts/lib/plan_paths.py', '--references', '--']
log = subprocess.run(['git', 'log', '--first-parent', 'main', '-n', '3000',
      '--name-only', '--format=@@%H'], capture_output=True, text=True, check=True).stdout
commits = []
for l in log.splitlines():
    if l.startswith('@@'): commits.append([])
    elif l.strip(): commits[-1].append(l.strip())
c = collections.Counter(); W = 10
for i, plan in enumerate(sorted(glob.glob('aiplans/archived/**/*.md', recursive=True))):
    ext = set(pp.extract(open(plan, encoding='utf-8', errors='surrogateescape').read()))
    for w in range(3):
        s = (i * 37 + w * 997) % (len(commits) - W)
        remote = sorted({f for cm in commits[s:s + W] for f in cm})
        out = subprocess.run(CLI + [plan], input=b'\0'.join(p.encode() for p in remote),
                             capture_output=True, check=True).stdout.decode()
        kinds = dict(reversed(l.split('\t', 1)) for l in out.splitlines())
        strong = any(k == 'full' for k in kinds.values())
        weak = {k for k in kinds.values() if k != 'full'}
        old = bool(ext & set(remote))
        c['windows'] += 1; c['old'] += old; c['strong'] += strong
        if not strong and weak:
            c['weak_only'] += 1
            c['weak_only_' + ('both' if len(weak) == 2 else weak.pop())] += 1
            c['downgraded'] += old
        c['lost'] += old and not kinds
print(dict(c))
EOF
```

**Drift check (switched).** The remote-changed set is exactly what
`find_references` wants: paths git reported. Result per window:

| | windows | share |
|---|---|---|
| old: `extract()` ∩ changed ≥ 1 | 277 | 27.9% |
| **strong** (≥ 1 `OVERLAP`) — prompts under every profile | 279 | 28.1% |
| **weak-only** (0 strong, ≥ 1 `WEAK_OVERLAP`) — shown under `warn` only | 155 | 15.6% |
| — of which bare-name only | 112 | 11.3% |
| — of which suffix only | 32 | 3.2% |
| — of which both | 11 | 1.1% |
| downgraded (old overlap → weak-only) | 0 | 0% |
| lost (old overlap → neither tier) | 2 | 0.2% |

- **Both lost windows are `extract()` false positives, not lost references.** The
  plans (`p1595`, `p635_35`) cite only `…/aitask-pick/SKILL.md.j2` and
  `…/aitask-pick{rem,web}/SKILL.md.j2`, the templates. `extract()` truncated those
  to `…/SKILL.md`, the rendered stubs the window's commits touched. At the
  reference level, all 32 references across all 21 plans that `extract()` found
  and the inverted search did not are the same truncation.
- **Why a bare tier exists.** Plain `find_references` flags 39.3% of windows. Of
  the windows only it flags, 106 of 108 are the command name `ait` in prose
  ("run `ait setup`"), which matches the root dispatcher file `ait`. Every bare
  hit in the table above is `ait` (186 of 186). A full reference to a
  single-component name with no `.` is therefore `WEAK_OVERLAP`. The accepted
  cost is that in a consumer project a real root `Makefile` / `Dockerfile` is
  weak too, and a `strong-only` profile does not show it. A `Makefile` under a
  directory (`src/Makefile`) stays strong.
- **Suffix tier.** A module-relative mention (`internal/x/main.go` for
  `goengines/internal/x/main.go`) is weak because a short suffix is ambiguous
  across modules. Here the top hits are real files cited by a shorter sub-path,
  plus old-layout paths (`aiscripts/lib/task_utils.sh`, cited in plans written
  before the `.aitask-scripts/` rename).
- Net: the strong (always-prompt) rate is unchanged within 0.2 points, and the
  real gains — `.md.j2`, `.gitignore`, `VERSION`, `Dockerfile`, `.go`, `go.mod`,
  and the NFD/undecodable handling of §4–§5 — are strong.

**Parallel admission and the trail gatherer (kept on `extract()`).** Neither
switches, and no hybrid was built:

- They need candidates **from** the plan. The question is "which files does this
  plan intend to touch", not "which of these changed files does it mention".
- No consumer has a changed-path set for an in-flight task. Nothing in
  `parallel_admission*.py` or `trail_gather.py` diffs a worktree, lists dirty
  files or reads tagged commits. A hybrid (`find_references` of the candidate
  plan against each in-flight task's committed/dirty set, as `shadow_scope.py`
  builds it) would add git calls per in-flight task on the pick path. Its
  evidence would also be empty most of the time, because an in-flight task has
  no tagged commits before its Step 8 commit.
- Admission already ships `off` in every committed profile because it prompts on
  34% of picks (`aitasks/metadata/profiles/fast.yaml`, measured 2026-09-17). More
  path evidence would raise that rate, not lower it.
- The `.md.j2` truncation false positive above no longer reaches them: the
  shared grammar now has a right boundary (next block).

**Right boundary on `extract()` (t1889).** `_TOKEN` gained a negative lookahead,
`(?![A-Za-z0-9_/-]|\.[A-Za-z0-9_./-])`. A match must not be followed by a token
character, except one sentence-final `.` that is not itself followed by one. On
those cases (an ASCII token character after the extension, and the sentence
period) `extract()` now agrees with `find_references`' right edge (§3).
They agree only there. `find_references` also treats `@`, `+` and non-ASCII
characters as part of the path, while `extract()`'s charset (§2) does not:
`a.md@v2` still extracts `a.md`, where the search reports no reference. This fix
does not change that.

| text | before | after |
|---|---|---|
| `x/SKILL.md.j2` | `x/SKILL.md` | — |
| `a.mdx`, `out.jsonl`, `foo.json.tmp` | `a.md`, `out.json`, `foo.json` | — |
| `x/a.py/b` (a directory named `a.py`) | `x/a.py` | — |
| `a.md.` / `` `a.md`. `` / `a.md,` | `a.md` | `a.md` |
| `a.md..` (ellipsis) | `a.md` | — |

Measured 2026-10-05. Both grammars were scored **in one process against one frozen
snapshot**. The "before" grammar is `git show <pre-edit sha>:…/plan_paths.py`,
loaded as a throwaway module. Every volatile input goes through the reference the
code actually calls: admission's import-time bound seams (`_GATE_PROBE`,
`_LOCK_PROBE`, `_STATUS_PROBE`, `_LIVENESS`, `_TRACKED_SETS`, `_DATA_TREE`,
`_FETCH`, `_BATCH_MAP`), its call-time globals (`locks_cache_age`,
`resolve_corpora`, `_active_plan_ids`, `_archived_plan_paths`), the trail
gatherer's `_GATE_PROBE` / `_LOCK_PROBE` and `plan_paths.tracked_sets`. Each is
recorded on the first run and replayed on the second, and the second run raises
on any miss. `now` and the local host are pinned. The run counts only if three
things match across it: a fingerprint (code HEAD, task-data HEAD,
`origin/aitask-locks`, a sha256 over all 1353 task and plan files); the
`AdmissionInput` projected to every non-path field (claims, sources, liveness,
same-host, claim times, lock and corpus evidence, touch counts); and the trail's
`INFLIGHT:` / `INFLIGHT_SOURCE:` lines. All three matched. An earlier draft that
patched `probe_*_source` / `lock_holder_liveness` by name would have left the
live calls in place, because `collect` calls the bound copies.

- **Fixed corpus** (455 loose archived + active plans): 52 plans change and 73
  distinct tokens are removed. No token is added and no plan's surface becomes
  empty. Cut-off occurrences by what followed: `.ext` 102 (almost all `.j2`,
  plus `.orig`, `.tmp`, `.lockd`, `._attr`), a word 33 (`.jsonl`,
  `.sh` + `adow…` from `.shadow_*`, `.sha256`), `/…` 5 (`brew.sh/Taps`,
  `…md/seed`), `-…` 1.
- **Replay** (`--candidates auto`, 119 active plans, `--from plan`,
  `allow-cached`): unchanged. `RATES:119|0|100|5|14` (CLEAR / CLEAR_CAVEATED /
  CONFLICT / UNCHECKABLE) and every `CAUSE_RATE:` line are identical, and no
  candidate's verdict moved. A second valid snapshot, taken after another session
  had claimed a task (`RATES:120|0|92|14|14`, 11 in flight), also showed no
  verdict moving. The run before it had been rejected because the task-data HEAD
  moved mid-run: the script exits 3 and reports nothing when any validity check
  fails.
- **Sweep** (`--source plan`, threshold 10, cohort `e1f66b44d822930c|320`, the
  same under both grammars). Columns: CLEAR | CLEAR_CAVEATED | CONFLICT |
  UNCHECKABLE | pred_conflict | tp_conflict | tp_caveated | missed.

  | | row | precision | recall |
  |---|---|---|---|
  | before | `36602\|11633\|2805\|0\|2805\|1109\|2274\|734` | 0.3954 | 0.8217 |
  | after  | `36607\|11638\|2795\|0\|2795\|1104\|2278\|735` | 0.3950 | 0.8215 |

  20 archived plans' surfaces changed, and 15 pairs moved: 10 CONFLICT →
  CLEAR_CAVEATED and 5 CLEAR_CAVEATED → CLEAR. **Every moved pair lost exactly
  one plan overlap, a template's rendered stub**: `aitask-trail/SKILL.md` (10),
  `aitask-pick/SKILL.md` (4), `aitask-explore/SKILL.md` (1), each followed by
  `.j2` in the plan. Six of the 15 pairs really did land on a common file, and
  in all six it was a *different* file (`tests/test_trail_gather.py` ×5,
  `task-workflow/planning.md` ×1). So those old CONFLICT verdicts were right only
  by coincidence. Five of them are still flagged as CLEAR_CAVEATED. One
  (`t1595 × t369_3`) is now missed: that is the whole recall change.
- **Trail gatherer** (`snapshot --with-inflight`, 10 in-flight tasks):
  `INFLIGHT_SCAN:10|extractable|both_enumeration_ok` before and after. The only
  `INFLIGHT_PATH:` change is three `phantom` tokens (`brew.sh`, `file.py`,
  `x.py`) dropped from t1889's own plan, which quotes the truncation examples.
  No task's surface became `no_extractable_paths`.
- **Accepted cost.** A real file named right before more token characters is
  lost: `module.py._attr` (two occurrences in the corpus) and a path followed by
  an ellipsis. `find_references` already drops both, for the same reason.

Reproduction (run from the repo root; `python3 <script> <pre-edit sha>
[trail task id]`):

```python
"""t1889: score the pre- and post-boundary extraction grammars against ONE
frozen snapshot, in one process. Run from the repo root:

    python3 t1889_paired.py <pre-edit-sha> [trail-task-id]

Run A (old grammar) RECORDS every volatile seam; run B (new grammar) only
REPLAYS them and raises on any miss, so run B cannot read live state.
"""
import collections, contextlib, copy, glob, hashlib, io, json, os, re
import subprocess, sys, time, types

sys.path.insert(0, ".aitask-scripts/lib")
import plan_paths as pp                       # noqa: E402
import parallel_admission_collect as pac      # noqa: E402
import trail_gather as tg                     # noqa: E402

PRE = sys.argv[1]
TRAIL_ID = sys.argv[2] if len(sys.argv) > 2 else "1889"

# --- the two grammars: "before" is the real prior module, not a copied literal
src = subprocess.run(["git", "show", f"{PRE}:.aitask-scripts/lib/plan_paths.py"],
                     capture_output=True, text=True, check=True).stdout
old_mod = types.ModuleType("plan_paths_before")
exec(compile(src, "plan_paths_before", "exec"), old_mod.__dict__)
GRAMMARS = {"before": old_mod._TOKEN, "after": pp._TOKEN}
assert GRAMMARS["before"].pattern != GRAMMARS["after"].pattern


def fingerprint():
    h = hashlib.sha256()
    files = sorted(set(glob.glob("aiplans/**/*.md", recursive=True))
                   | set(glob.glob("aitasks/**/*.md", recursive=True)))
    for f in files:
        h.update(f.encode()); h.update(b"\0")
        with open(f, "rb") as fh:
            h.update(fh.read())

    def rp(*a):
        return subprocess.run(a, capture_output=True, text=True).stdout.strip()
    return {"code_head": rp("git", "rev-parse", "HEAD"),
            "data_head": rp("./ait", "git", "rev-parse", "HEAD"),
            "locks_ref": rp("git", "rev-parse", "origin/aitask-locks"),
            "n_files": len(files), "files_sha256": h.hexdigest()}


class Frozen:
    """Record in run A, replay-only in run B."""
    replay = False
    seams = []

    def __init__(self, name, fn):
        self.name, self.fn, self.cache = name, fn, {}
        Frozen.seams.append(self)

    def __call__(self, *a, **k):
        key = repr((a, sorted(k.items())))
        if key in self.cache:
            kind, val = self.cache[key]
        elif Frozen.replay:
            raise RuntimeError(f"seam {self.name} missed in replay: {key}")
        else:
            try:
                kind, val = "ok", self.fn(*a, **k)
            except Exception as exc:          # replay the failure too
                kind, val = "raise", exc
            self.cache[key] = (kind, val)
        if kind == "raise":
            raise val
        return copy.deepcopy(val)


def freeze(mod, *names):
    for n in names:
        setattr(mod, n, Frozen(f"{mod.__name__}.{n}", getattr(mod, n)))


# Admission: the BOUND references collect()/classify_liveness() call, plus the
# globals looked up by name at call time.
freeze(pac, "_GATE_PROBE", "_LOCK_PROBE", "_STATUS_PROBE", "_LIVENESS",
       "_TRACKED_SETS", "_DATA_TREE", "_FETCH", "_BATCH_MAP",
       "locks_cache_age", "resolve_corpora", "_active_plan_ids",
       "_archived_plan_paths")
import platform                               # noqa: E402
pac._LOCAL_HOST = platform.node()
# Trail gatherer: its own bound probes, and tracked_sets by module attribute.
freeze(tg, "_GATE_PROBE", "_LOCK_PROBE")
freeze(pp, "tracked_sets")

NOW = int(time.time())
_collect_population = pac.collect_population
captured = {}


def pinned_collect_population(*a, **k):
    k["now"] = NOW
    pop = _collect_population(*a, **k)
    captured["population"] = pop
    return pop


pac.collect_population = pinned_collect_population
_sweep_population = pac.sweep_population


def captured_sweep_population(*a, **k):
    got = _sweep_population(*a, **k)
    captured["sweep"] = got
    return got


pac.sweep_population = captured_sweep_population


def nonpath(base):
    """Everything in the AdmissionInput except path surfaces/tokens."""
    return repr((base.enumeration, base.locks, base.corpora, base.now,
                 sorted(base.touch_counts.items()), base.hub_threshold,
                 base.max_lock_age_s, base.max_claim_age_s,
                 [(c.ref, c.sources, c.task_status, c.liveness, c.same_host,
                   c.claim_at_s, c.claim_age_reason) for c in base.inflight]))


def run(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a)
    return rc, buf.getvalue().splitlines()


results = {}
fp_a = fingerprint()
for label in ("before", "after"):
    pp._TOKEN = GRAMMARS[label]
    r = {}
    rc, r["replay"] = run(pac._run_replay,
                          pac._parse_args(["replay", "--candidates", "auto"])[1])
    assert rc == 0
    r["nonpath"] = nonpath(captured["population"].base)
    r["surfaces"] = {k: v.paths for k, v in captured["population"].surfaces.items()}
    r["claims"] = {c.ref: (c.surface.paths if c.surface else ())
                   for c in captured["population"].base.inflight}
    rc, r["sweep"] = run(pac._run_sweep,
                         pac._parse_args(["sweep", "--source", "plan"])[1])
    assert rc == 0
    r["sweep_pop"], r["sweep_touch"], _drift = captured["sweep"]
    rc, r["trail"] = run(tg.main, ["snapshot", "--scope", "task", "--with-inflight", TRAIL_ID])
    results[label] = r
    Frozen.replay = True                       # run B: replay only
fp_b = fingerprint()

A, B = results["before"], results["after"]
print("FINGERPRINT_EQUAL:", fp_a == fp_b)
print("FINGERPRINT:", json.dumps(fp_a))
if fp_a != fp_b:
    print("FINGERPRINT_AFTER:", json.dumps(fp_b))
print("NONPATH_EQUAL:", A["nonpath"] == B["nonpath"])
trail_pop = lambda r: [l for l in r["trail"] if l.startswith(("INFLIGHT:", "INFLIGHT_SOURCE:"))]
print("TRAIL_POPULATION_EQUAL:", trail_pop(A) == trail_pop(B))
print("SEAMS:", ", ".join(f"{s.name}={len(s.cache)}" for s in Frozen.seams))
# Fail closed: a difference in anything but the grammar means the comparison
# below would attribute a world change to extraction. Report nothing.
if not (fp_a == fp_b and A["nonpath"] == B["nonpath"]
        and trail_pop(A) == trail_pop(B)):
    print("INVALID: inputs moved between the two runs -- rerun; no results reported")
    sys.exit(3)

for name in ("replay", "sweep"):
    print(f"\n== {name} ==")
    for la, lb in zip(A[name], B[name]):
        if la.startswith("VERDICT_FOR:"):
            continue
        print(("  " if la == lb else "* ") + la + ("" if la == lb else "   ->   " + lb))

va = dict(l.split(":", 1)[1].split("|") for l in A["replay"] if l.startswith("VERDICT_FOR:"))
vb = dict(l.split(":", 1)[1].split("|") for l in B["replay"] if l.startswith("VERDICT_FOR:"))
print("\n== replay verdict changes ==")
TAIL = re.compile(r"[A-Za-z0-9_./-]*")


def tails(tok):
    """What followed `tok` wherever the old grammar cut it short."""
    out = set()
    for f in glob.glob("aiplans/**/*.md", recursive=True):
        text = open(f, encoding="utf-8", errors="surrogateescape").read()
        for m in re.finditer(re.escape(tok), text):
            t = TAIL.match(text, m.end()).group(0)
            if t and t != ".":
                out.add(t[:12])
    return sorted(out)


for cand in sorted(va):
    if va[cand] == vb.get(cand):
        continue
    ca, cb = set(A["surfaces"][cand]), set(B["surfaces"][cand])
    print(f"t{cand}: {va[cand]} -> {vb.get(cand)}")
    print(f"   candidate tokens removed: {sorted(ca - cb)}")
    for ref, pa_paths in A["claims"].items():
        if ref == cand:
            continue
        lost = (ca & set(pa_paths)) - (cb & set(B["claims"].get(ref, ())))
        if lost:
            print(f"   lost overlap with t{ref}: "
                  + ", ".join(f"{t} (tail {tails(t)})" for t in sorted(lost)))

print("\n== sweep pair verdict changes (threshold = default) ==")
import parallel_admission as pa_mod            # noqa: E402
import parallel_admission_sweep as pas         # noqa: E402
popA = {ref: (s, l) for ref, s, l in A["sweep_pop"]}
popB = {ref: (s, l) for ref, s, l in B["sweep_pop"]}
assert set(popA) == set(popB), "sweep cohort differs between grammars"
moved = [r for r in popA if popA[r][0].paths != popB[r][0].paths]
print(f"tasks whose sweep surface changed: {len(moved)}")
seen = set()
for a in sorted(moved):
    for b in sorted(popA):
        if a == b or frozenset((a, b)) in seen:
            continue
        seen.add(frozenset((a, b)))
        va_ = pas.pair_verdict(popA[a][0], b, popA[b][0], A["sweep_touch"], pa_mod.HUB_THRESHOLD)
        vb_ = pas.pair_verdict(popB[a][0], b, popB[b][0], B["sweep_touch"], pa_mod.HUB_THRESHOLD)
        if va_ == vb_:
            continue
        truth = sorted(popA[a][1] & popA[b][1])
        lost = (set(popA[a][0].paths) & set(popA[b][0].paths)) - \
               (set(popB[a][0].paths) & set(popB[b][0].paths))
        print(f"t{a} x t{b}: {va_} -> {vb_}; landed overlap={truth[:3]}{'...' if len(truth) > 3 else ''}")
        print("   lost plan overlap: " + ", ".join(f"{t} (tail {tails(t)})" for t in sorted(lost)))

print("\n== trail INFLIGHT_PATH / INFLIGHT_SCAN diff ==")
ta = {l for l in A["trail"] if l.startswith(("INFLIGHT_PATH:", "INFLIGHT_SCAN:"))}
tb = {l for l in B["trail"] if l.startswith(("INFLIGHT_PATH:", "INFLIGHT_SCAN:"))}
for l in sorted(ta - tb):
    print("  - " + l)
for l in sorted(tb - ta):
    print("  + " + l)
print("  scan before:", [l for l in A["trail"] if l.startswith("INFLIGHT_SCAN:")])
print("  scan after: ", [l for l in B["trail"] if l.startswith("INFLIGHT_SCAN:")])

# --- fixed-corpus extraction diff (population-independent) -------------------
print("\n== fixed corpus: archived (loose) + active plans ==")
plans = sorted(set(glob.glob("aiplans/archived/**/*.md", recursive=True))
               | set(glob.glob("aiplans/p*.md")) | set(glob.glob("aiplans/p*/*.md")))


def ex(rx, text):
    return {pp._strip_dot_slash(m) for m in rx.findall(text)}


changed = removals = added = 0
by_tail = collections.Counter()
emptied = []
for f in plans:
    text = open(f, encoding="utf-8", errors="surrogateescape").read()
    a, b = ex(GRAMMARS["before"], text), ex(GRAMMARS["after"], text)
    added += len(b - a)
    if a != b:
        changed += 1
        removals += len(a - b)
        if a and not b:
            emptied.append(f)
        for tok in a - b:
            for m in re.finditer(re.escape(tok), text):
                t = TAIL.match(text, m.end()).group(0)
                if t and t != ".":
                    by_tail[re.sub(r"[A-Za-z0-9_]+", "w", t[:4])] += 1
print(f"plans={len(plans)} changed={changed} distinct_token_removals={removals} "
      f"tokens_added={added} emptied={emptied}")
print("cut-off occurrences by tail shape:", by_tail.most_common())
```

## Related

- `tests/test_plan_paths.py` — `ExtractionTests` pins the right boundary of §7
  (the `.md.j2`, `.mdx`, `/` and sentence-final-period cases).
- `.aitask-scripts/lib/plan_paths.py` — `extract()` (the grammar of §1–§2) and
  `find_references()` / `reference_kinds()` (the inverted search of §3–§5, §7).
- `.aitask-scripts/aitask_remote_drift_check.sh` — the drift check, a
  `find_references` consumer since §7.
- `tests/test_remote_drift_check.sh` — Test 13 covers the consumer-project
  layout; Test 14 the old grammar's golden set plus Go/Rust/TS (14f pins the
  golden against the live `extract()`); Test 16 the
  reference tiers and the §3–§5 edges (the `@`, `.md.j2`, NFD and undecodable
  cases); Test 17 the best-effort `git diff` failure.
- `.claude/skills/task-workflow/remote-drift-check.md` — the consuming procedure
  and the `warn` / `strong-only` profile semantics that make a lost `OVERLAP`
  equivalent to no warning at all.
