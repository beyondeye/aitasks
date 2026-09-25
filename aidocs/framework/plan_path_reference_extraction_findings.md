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
- They keep the `.md.j2` truncation false positive above, which can produce an
  admission `CONFLICT` or a trail overlap on the rendered stub instead of the
  template. Fixing that is a change to the shared grammar (a match must not be
  followed by a path character), so it needs its own before/after replay and
  corpus measurement, and is a separate task.

## Related

- `.aitask-scripts/lib/plan_paths.py` — `extract()` (the grammar of §1–§2) and
  `find_references()` / `reference_kinds()` (the inverted search of §3–§5, §7).
- `.aitask-scripts/aitask_remote_drift_check.sh` — the drift check, a
  `find_references` consumer since §7.
- `tests/test_remote_drift_check.sh` — Test 13 covers the consumer-project
  layout; Test 14 the old grammar's golden set plus Go/Rust/TS; Test 16 the
  reference tiers and the §3–§5 edges (the `@`, `.md.j2`, NFD and undecodable
  cases); Test 17 the best-effort `git diff` failure.
- `.claude/skills/task-workflow/remote-drift-check.md` — the consuming procedure
  and the `warn` / `strong-only` profile semantics that make a lost `OVERLAP`
  equivalent to no warning at all.
