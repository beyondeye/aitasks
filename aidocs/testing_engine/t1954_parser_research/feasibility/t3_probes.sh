#!/usr/bin/env bash
# t3_probes.sh - the t1954_3 elimination probes (evidence, not providers):
#   1. scc: count-only output, compared with the hand oracle's line comments;
#   2. gpython: a pure-Go Python lexer — does it accept the corpus, does it
#      emit comments at all?
#   3. Pygments: tokenisation-path normalisation and String.Doc vs the module
#      docstring.
#
#   feasibility/t3_probes.sh <scratch-dir>      writes results/t3_probes.md
# Needs: T1954_SCC (scc v4.1.0 binary), T1954_PYGMENTS_PYTHON (venv python with
# pygments 2.21.0), go and network for `go get` of gpython v0.2.0. Corpus
# fixtures are copied into the scratch dir; nothing is executed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scratch="${1:?usage: t3_probes.sh <scratch-dir>}"
scc="${T1954_SCC:?set T1954_SCC to the scc binary}"
py="${T1954_PYGMENTS_PYTHON:?set T1954_PYGMENTS_PYTHON}"
mkdir -p "$scratch"
out="$here/results/t3_probes.md"
cd "$here"

# 1. scc
rm -rf "$scratch/scc" && mkdir -p "$scratch/scc"
for f in corpus/*/*.in; do
  d=$(basename "$(dirname "$f")"); b=$(basename "$f" .in)
  mkdir -p "$scratch/scc/$d"; cp "$f" "$scratch/scc/$d/$b"
done
"$scc" --by-file --format json "$scratch/scc" > "$scratch/scc.json"
scc_md=$(python3 - "$scratch" <<'PY'
import glob, json, os, re, sys
sp = sys.argv[1]
data = json.load(open(sp + "/scc.json"))
byfile = {os.path.relpath(f["Location"], sp + "/scc"): f["Comment"] for lang in data for f in lang["Files"]}
fields = sorted(data[0]["Files"][0].keys())
per, eq, tot = {}, 0, 0
for exp in sorted(glob.glob("corpus/*/*.expect")):
    d = os.path.basename(os.path.dirname(exp)); n = os.path.basename(exp)[:-7]
    if d + "/" + n not in byfile:
        continue
    m = re.search(r"^comments: (.*)$", open(exp).read(), re.M)
    cnt = 0
    if m and m.group(1).strip():
        for part in m.group(1).split(","):
            a, _, b = part.partition("-"); cnt += (int(b) - int(a) + 1) if b else 1
    ok = byfile[d + "/" + n] == cnt
    tot += 1; eq += ok
    p = per.setdefault(d, [0, 0]); p[0] += ok; p[1] += 1
print("- per-file JSON fields: `" + "`, `".join(fields) + "` — counts only, **no line or byte positions**, so no comment location can be read from it.")
print("- fixtures whose `Comment` count equals the hand oracle's line-comment count: **%d / %d** (%s). The two counts are not the same definition (scc counts block-comment lines too), so this is a coarse indicator only." %
      (eq, tot, ", ".join("%s %d/%d" % (k, v[0], v[1]) for k, v in per.items())))
PY
)

# 2. gpython
g="$scratch/gpython-probe"
rm -rf "$g" && mkdir -p "$g"
cat > "$g/go.mod" <<'GO'
module gpyprobe

go 1.26.0
GO
cat > "$g/main.go" <<'GO'
package main

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/go-python/gpython/parser"
	"github.com/go-python/gpython/py"
)

func main() {
	files, _ := filepath.Glob(filepath.Join(os.Args[1], "*.py.in"))
	lexed, validRej, malRej, valid, mal := 0, 0, 0, 0, 0
	var rej []string
	for _, f := range files {
		data, _ := os.ReadFile(f)
		exp, _ := os.ReadFile(strings.TrimSuffix(f, ".in") + ".expect")
		unc := bytes.Contains(exp, []byte("expect: uncertain"))
		if unc {
			mal++
		} else {
			valid++
		}
		if _, err := parser.Lex(bytes.NewReader(data), "x.py", py.ExecMode); err != nil {
			if unc {
				malRej++
			} else {
				validRej++
				rej = append(rej, filepath.Base(f))
			}
			continue
		}
		lexed++
	}
	fmt.Printf("- fixtures %d (valid %d, malformed %d): lexed %d; valid rejected %d %v; malformed rejected %d.\n", len(files), valid, mal, lexed, validRej, rej, malRej)
}
GO
(cd "$g" && go get github.com/go-python/gpython@v0.2.0 >/dev/null 2>&1 && go mod tidy >/dev/null 2>&1)
gpy_md=$(cd "$g" && go run . "$here/corpus/python")
gpy_src="$(go env GOMODCACHE)/github.com/go-python/gpython@v0.2.0/parser/lexer.go"
gpy_comment=$(grep -c "despaced\[0\] == '#'\|x.line\[0\] == '#'" "$gpy_src" || true)

# 3. Pygments
norm=$("$py" oracle/pygments_oracle.py --normcheck corpus)
doc=$("$py" oracle/pygments_oracle.py --doccheck corpus)
pyg_v=$("$py" -c 'import pygments; print(pygments.__version__)')

{
  echo "# t1954_3 elimination probes"
  echo
  echo "Rerun: \`feasibility/t3_probes.sh <scratch-dir>\` (\`T1954_SCC\`, \`T1954_PYGMENTS_PYTHON\`; network for gpython). Evidence for eliminations and for the Pygments provider's design; nothing here is a provider. Corpus: $(find corpus -mindepth 2 -maxdepth 2 -name "*.in" | wc -l) fixtures."
  echo
  echo "## scc $("$scc" --version | sed 's/scc version //') (count-only line classifier)"
  echo
  echo "$scc_md"
  echo
  echo "## gpython v0.2.0 (github.com/go-python/gpython/parser, pure Go)"
  echo
  echo "$gpy_md"
  echo "- the lexer emits **no comment token**: it skips a line that is only whitespace and a comment, and stops a line at \`#\` (\`parser/lexer.go\`, $gpy_comment such sites); its token set has no COMMENT. So it cannot report comment locations without modifying it — a custom reader by another route. Grammar: Python 3.4 era, last release 2023-06-28, no PEP 701 (3.12) f-string tokenisation."
  echo
  echo "## Pygments $pyg_v"
  echo
  echo "Tokenisation path vs exact reconstruction of the decoded text (\`--normcheck\`):"
  echo
  echo '```json'
  echo "$norm"
  echo '```'
  echo
  echo "\`String.Doc\` vs the Python module docstring (ast) (\`--doccheck\`): Pygments' Python lexer marks a triple-quoted string at a line start as String.Doc wherever it is, and has no statement model — so it cannot supply DocInfo (content bounds + statement end); the provider declares no DocLiterals."
  echo
  echo '```json'
  echo "$doc"
  echo '```'
} > "$out"
echo "WROTE:$out"
