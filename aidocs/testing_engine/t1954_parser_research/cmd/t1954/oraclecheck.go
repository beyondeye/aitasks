package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"go/parser"
	"go/token"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/oracle"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

// ocRow is one fixture's native cross-check.
type ocRow struct {
	lang, name, origin string
	expect, native     string // expectation: valid | invalid | lexically-valid | fragment ; native: accept | reject:<why> | none:<why>
	match              string // yes | NO | n/a
	comments           string // comment-line agreement
	exec               string
	notes              []string
}

func cmdOracleCheck(args []string) int {
	fs := flag.NewFlagSet("oraclecheck", flag.ExitOnError)
	out := fs.String("out", "results/oracle_check.md", "output file")
	lang := fs.String("lang", "", "corpus languages")
	_ = fs.Parse(args)
	cases, err := corpus.Load("corpus")
	if err != nil {
		fail(1, err)
	}
	cases = filterLangs(cases, *lang)
	defer oracle.Close()
	scratch, err := os.MkdirTemp("", "t1954-oc-")
	if err != nil {
		fail(1, err)
	}
	defer os.RemoveAll(scratch)
	var rows []ocRow
	for _, c := range cases {
		rows = append(rows, check(c, scratch))
	}
	report := ocReport(rows)
	if err := os.WriteFile(*out, []byte(report), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\n", *out)
	bad := 0
	for _, r := range rows {
		if r.match == "NO" || strings.Contains(r.comments, "DISAGREE") || strings.HasPrefix(r.exec, "FAIL") {
			bad++
		}
	}
	fmt.Printf("ORACLECHECK:%d fixtures, %d with a disagreement\n", len(rows), bad)
	return 0
}

func originOf(c corpus.Case) string {
	for _, n := range c.Exp.Notes {
		if strings.HasPrefix(n, "origin: M2.2") {
			return "M2.2"
		}
	}
	return "hand"
}

func expectation(c corpus.Case) string {
	switch {
	case strings.HasPrefix(c.Name, "syntax_error_lexically_valid"):
		return "lexically-valid"
	case c.Exp.Uncertain:
		return "invalid"
	case strings.HasPrefix(c.Name, "lex_") || strings.HasPrefix(c.Name, "doc_shape_") || strings.HasPrefix(c.Name, "docvalue_") || c.Exp.Refuse != "":
		return "fragment"
	}
	return "valid"
}

func check(c corpus.Case, scratch string) ocRow {
	l, _ := provider.LangOfPath(c.Name, c.Data)
	r := ocRow{lang: c.Lang, name: c.Name, origin: originOf(c), expect: expectation(c)}
	dir, err := os.MkdirTemp(scratch, "fx-")
	if err != nil {
		r.native = "none:" + err.Error()
		return r
	}
	file := filepath.Join(dir, c.Name)
	_ = os.WriteFile(file, c.Data, 0o644)
	_ = os.Chmod(file, c.Mode)
	r.native = validity(l.Name, file, c, dir)
	differs := c.Exp.Extra["x-native-differs"]
	switch {
	case differs == "validity":
		r.match = "explained"
		r.notes = append(r.notes, "validity: explained in the fixture notes")
	case strings.HasPrefix(r.native, "none"):
		r.match = "n/a"
	case r.expect == "valid":
		r.match = yesNo(r.native == "accept")
	case r.expect == "invalid", r.expect == "lexically-valid":
		r.match = yesNo(strings.HasPrefix(r.native, "reject"))
	default:
		r.match = "n/a"
	}
	r.comments = commentAgreement(l.Name, c, &r)
	if c.Exp.Exec != "" {
		r.exec = runOnce(c.Exp.Exec, file)
	}
	return r
}

func yesNo(b bool) string {
	if b {
		return "yes"
	}
	return "NO"
}

func run(dir string, timeout time.Duration, name string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Dir = dir
	out, err := cmd.CombinedOutput()
	return string(out), err
}

func firstLine(s string) string {
	s = strings.TrimSpace(s)
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		s = s[:i]
	}
	if len(s) > 140 {
		s = s[:140] + "…"
	}
	return strings.ReplaceAll(s, "|", "/")
}

func verdict(out string, err error) string {
	if err == nil {
		return "accept"
	}
	if _, ok := err.(*exec.ExitError); ok {
		return "reject:" + firstLine(out)
	}
	return "none:" + err.Error()
}

// validity asks the language's own tool whether the file is well-formed.
func validity(lang, file string, c corpus.Case, dir string) string {
	base := filepath.Base(file)
	switch lang {
	case "bash":
		out, err := run(dir, 30*time.Second, "bash", "-n", base)
		if err == nil && strings.Contains(out, "warning: here-document") {
			// bash accepts an unterminated heredoc with only a warning; the
			// corpus classes it malformed (fail closed)
			return "reject:" + firstLine(out[strings.Index(out, "warning:"):])
		}
		return verdict(out, err)
	case "python":
		p, err := provider.New("pytokenize")
		if err != nil {
			return "none:" + err.Error()
		}
		res, err := p.Analyze(lang, c.Data)
		if err != nil {
			return "none:" + err.Error()
		}
		if len(res.Diags) > 0 {
			return "reject:" + firstLine(res.Diags[0].Reason)
		}
		return "accept"
	case "go":
		if _, err := parser.ParseFile(token.NewFileSet(), base, c.Data, parser.ParseComments|parser.AllErrors); err != nil {
			return "reject:" + firstLine(err.Error())
		}
		return "accept"
	case "typescript", "javascript":
		if ok, why := oracle.TSAvailable(); !ok {
			return "none:" + why
		}
		cmd := exec.Command("node", filepath.Join(id.Root, "oracle", "ts_oracle.js"), "--file", file)
		cmd.Env = append(os.Environ(), "NODE_PATH="+os.Getenv("T1954_TS_NODE_MODULES"))
		out, err := cmd.Output()
		if err != nil {
			return "none:ts oracle: " + err.Error()
		}
		var r struct {
			Diags       [][2]any `json:"diags"`
			Unaccounted []int    `json:"unaccounted"`
		}
		if err := json.Unmarshal(out, &r); err != nil {
			return "none:" + err.Error()
		}
		if len(r.Unaccounted) > 0 {
			return "none:ts oracle full-cover check failed"
		}
		if len(r.Diags) > 0 {
			return "reject:" + firstLine(fmt.Sprint(r.Diags[0][1]))
		}
		return "accept"
	case "java":
		if _, err := exec.LookPath("javac"); err != nil {
			return "none:javac not installed"
		}
		return verdict(run(dir, 120*time.Second, "javac", "-d", filepath.Join(dir, "classes"), base))
	case "rust":
		if _, err := exec.LookPath("rustc"); err != nil {
			return "none:rustc not installed"
		}
		return verdict(run(dir, 120*time.Second, "rustc", "--edition", "2021", "--crate-type=lib", "--emit=metadata", "-A", "warnings", "-o", filepath.Join(dir, "out.rmeta"), base))
	case "kotlin":
		kc := os.Getenv("T1954_KOTLINC")
		if kc == "" {
			return "none:T1954_KOTLINC not set (kotlinc not obtained)"
		}
		var out string
		var err error
		if strings.HasSuffix(base, ".kts") {
			out, err = run(dir, 300*time.Second, kc, "-script", base)
		} else {
			out, err = run(dir, 300*time.Second, kc, "-nowarn", "-d", filepath.Join(dir, "classes"), base)
		}
		if err != nil && onlySemanticErrors(out) {
			// kotlinc has no parse-only mode: errors that are all unresolved
			// references (imports of absent libraries) mean the syntax parsed
			return "accept"
		}
		return verdict(out, err)
	case "swift":
		img := os.Getenv("T1954_SWIFT_DOCKER")
		if img == "" {
			return "none:T1954_SWIFT_DOCKER not set (no Swift toolchain)"
		}
		return verdict(run(dir, 300*time.Second, "docker", "run", "--rm", "-v", dir+":/w:ro", img, "swiftc", "-parse", "-enable-bare-slash-regex", "/w/"+base))
	}
	return "none:no tool"
}

func onlySemanticErrors(out string) bool {
	n := 0
	for _, l := range strings.Split(out, "\n") {
		if strings.Contains(l, "error:") {
			n++
			if !strings.Contains(l, "unresolved reference") {
				return false
			}
		}
	}
	return n > 0
}

// commentAgreement compares the hand marks with the native oracle's line
// comments that start at a line's first non-blank byte (the only lines
// annot can class Comment).
func commentAgreement(lang string, c corpus.Case, r *ocRow) string {
	if c.Exp.Uncertain {
		return "n/a (malformed)"
	}
	spans, name, err := oracle.Comments(c.Name, lang, c.Data)
	if name == "" {
		return "n/a (no comment oracle)"
	}
	if err != nil {
		return "none (" + name + ": " + firstLine(err.Error()) + ")"
	}
	l, _ := provider.LangByName(lang)
	starts := provider.LineStarts(c.Data)
	native := map[int]bool{}
	for _, s := range spans {
		if !bytes.HasPrefix(c.Data[s.Start:], []byte(l.Leader)) {
			continue
		}
		ln := provider.LineOf(starts, s.Start)
		f := starts[ln-1]
		for f < len(c.Data) && (c.Data[f] == ' ' || c.Data[f] == '\t') {
			f++
		}
		if f == s.Start {
			native[ln] = true
		}
	}
	explained := map[int]bool{}
	for _, k := range []string{"x-native-differs", "x-policy"} {
		if ls, err := corpus.ParseLines(c.Exp.Extra[k]); err == nil {
			for _, n := range ls {
				explained[n] = true
			}
		}
	}
	var dis []string
	nexp := 0
	hand := map[int]bool{}
	for _, n := range c.Exp.Comments {
		hand[n] = true
		if !native[n] {
			if explained[n] {
				nexp++
				continue
			}
			dis = append(dis, fmt.Sprintf("line %d: hand comment, %s not", n, name))
		}
	}
	for _, n := range c.Exp.Lookalikes {
		if native[n] {
			if explained[n] {
				nexp++
				continue
			}
			dis = append(dis, fmt.Sprintf("line %d: hand look-alike, %s line comment", n, name))
		}
	}
	for _, n := range c.Exp.Readonly {
		if native[n] {
			dis = append(dis, fmt.Sprintf("line %d: hand docstring, %s line comment", n, name))
		}
	}
	var extra []int
	for n := range native {
		if !hand[n] {
			extra = append(extra, n)
		}
	}
	sort.Ints(extra)
	for _, n := range extra {
		// an unmarked plain comment is fine; an unmarked token line cannot exist (generator lint)
		_ = n
	}
	if len(dis) > 0 {
		r.notes = append(r.notes, dis...)
		return fmt.Sprintf("DISAGREE %d (%s)", len(dis), name)
	}
	if nexp > 0 {
		r.notes = append(r.notes, fmt.Sprintf("%d line(s) differ from %s as explained in the fixture notes", nexp, name))
		return fmt.Sprintf("agree (%s, %d comment lines; %d explained)", name, len(c.Exp.Comments), nexp)
	}
	return fmt.Sprintf("agree (%s, %d comment lines)", name, len(c.Exp.Comments))
}

func runOnce(cmdline, file string) string {
	dir := filepath.Dir(file)
	cmdline = strings.ReplaceAll(cmdline, "{file}", filepath.Base(file))
	if _, err := exec.LookPath(strings.Fields(cmdline)[0]); err != nil {
		return "none:tool missing"
	}
	out, err := run(dir, 120*time.Second, "bash", "-c", cmdline)
	if err != nil {
		return "FAIL:" + firstLine(out)
	}
	return "ok"
}

func ocReport(rows []ocRow) string {
	var b strings.Builder
	b.WriteString("# Native cross-checks of the hand oracles (t1954_1 step 3)\n\n")
	fmt.Fprintf(&b, "%s\n\n", id.Header())
	b.WriteString("Rerun: `go run ./cmd/t1954 oraclecheck` (environment: `results/environment.md`; TS oracle needs `T1954_TS_NODE_MODULES`, Kotlin `T1954_KOTLINC`, Swift `T1954_SWIFT_DOCKER`).\n\n")
	b.WriteString("- **expect**: `valid` (a native tool must accept), `invalid` (malformed: must reject), `lexically-valid` (tokenizes, does not parse: the parser must reject), `fragment` (an M2.2 lexical case or docstring fragment, not necessarily a program: informational).\n")
	b.WriteString("- **comments**: hand `comments:` lines must be native line comments starting at the line's first non-blank byte; `lookalikes:` / `readonly:` lines must not be. Comment oracles: go/scanner (Go), Python tokenize, mvdan/sh (bash), the parser-aware TS extractor (TS/JS). Java, Rust, Kotlin and Swift have validity and execution evidence only.\n")
	b.WriteString("- **Self-test rule**: the M2.2 adversarial fixtures (`lex_*`, `lookalikes.*`, docstring cases — origin M2.2) are each comment oracle's self-test; an oracle may override a hand expectation only if it agrees on all of them for its language (summary below).\n\n")
	b.WriteString("## Summary\n\n| lang | fixtures | validity matches / checked | comment agreement (M2.2 self-test) | comment agreement (hand) | exec ok / run | native none |\n|---|---|---|---|---|---|---|\n")
	type agg struct{ n, vm, vc, sa, sn, ha, hn, eo, er, none int }
	by := map[string]*agg{}
	for _, l := range corpusLangs {
		by[l] = &agg{}
	}
	for _, r := range rows {
		a := by[r.lang]
		a.n++
		if r.match == "yes" || r.match == "NO" {
			a.vc++
			if r.match == "yes" {
				a.vm++
			}
		}
		if strings.HasPrefix(r.native, "none") {
			a.none++
		}
		if strings.HasPrefix(r.comments, "agree") || strings.HasPrefix(r.comments, "DISAGREE") {
			if r.origin == "M2.2" {
				a.sn++
				if strings.HasPrefix(r.comments, "agree") {
					a.sa++
				}
			} else {
				a.hn++
				if strings.HasPrefix(r.comments, "agree") {
					a.ha++
				}
			}
		}
		if r.exec != "" {
			a.er++
			if r.exec == "ok" {
				a.eo++
			}
		}
	}
	for _, l := range corpusLangs {
		a := by[l]
		if a.n == 0 {
			continue
		}
		fmt.Fprintf(&b, "| %s | %d | %d / %d | %d / %d | %d / %d | %d / %d | %d |\n", l, a.n, a.vm, a.vc, a.sa, a.sn, a.ha, a.hn, a.eo, a.er, a.none)
	}
	b.WriteString("\n## Per fixture\n\n| lang | case | origin | expect | native | match | comments | exec |\n|---|---|---|---|---|---|---|---|\n")
	for _, r := range rows {
		fmt.Fprintf(&b, "| %s | %s | %s | %s | %s | %s | %s | %s |\n", r.lang, r.name, r.origin, r.expect, esc(r.native), r.match, esc(r.comments), esc(r.exec))
	}
	b.WriteString("\n## Disagreements\n\n")
	any := false
	for _, r := range rows {
		if len(r.notes) == 0 && r.match != "NO" && r.match != "explained" && !strings.HasPrefix(r.exec, "FAIL") {
			continue
		}
		any = true
		fmt.Fprintf(&b, "- `%s/%s`: native %s; exec %s\n", r.lang, r.name, esc(r.native), esc(r.exec))
		for _, n := range r.notes {
			fmt.Fprintf(&b, "  - %s\n", n)
		}
	}
	if !any {
		b.WriteString("None.\n")
	}
	return b.String()
}

func esc(s string) string { return strings.ReplaceAll(s, "|", "\\|") }
