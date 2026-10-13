package main

import (
	"flag"
	"fmt"
	"os"
	"strings"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

// cmdLocalPolicy scores an ALTERNATIVE refusal policy, as a comparison with
// the default whole-file refusal (M2.2 D9), which the matrix scores. Under
// the local policy a file with diagnostics is not refused as a whole. Only
// the lines a diagnostic spans, plus one line on each side, are refused;
// every other line keeps the provider's class. The report counts what that
// would cost in safety (look-alike or read-only lines that become writable)
// and gain in recall (writable lines kept). It is an alternative only,
// never the policy the harness applies.
func cmdLocalPolicy(args []string) int {
	fs := flag.NewFlagSet("localpolicy", flag.ExitOnError)
	prov := fs.String("provider", "gotreesitter", "providers (comma list)")
	out := fs.String("out", "results/ts_local_error_policy.md", "output file")
	_ = fs.Parse(args)
	cases, err := corpus.Load("corpus")
	if err != nil {
		fail(1, err)
	}
	defer provider.CloseAll()
	var b strings.Builder
	fmt.Fprintf(&b, "# Local-error refusal policy — an alternative (t1954_2)\n\n%s\n\n", id.Header())
	b.WriteString("The harness and M2.2 refuse a file **as a whole** when the provider reports any diagnostic (D9); the matrices score that policy. This report scores the alternative: refuse only the lines a diagnostic spans, plus one line on each side, and keep the provider's class elsewhere. **FP-writable (local)**: look-alike or read-only lines (`x-policy` lines excluded) that would be classed Comment outside the refused zone. Each one is a write the whole-file policy prevents. **Writable kept / lost**: the fixture's writable lines that stay writable, or are lost to the zone or to the class. Whole-file refusal keeps none of these lines and has 0 FP-writable by construction. Only files on which the provider reports a diagnostic are counted. Rerun: `go run ./cmd/t1954 localpolicy --provider <p,…>`.\n\n")
	b.WriteString("| provider | lang | files with diagnostics | FP-writable (local) | writable kept / lost |\n|---|---|---|---|---|\n")
	var notes []string
	for _, name := range strings.Split(*prov, ",") {
		p, err := provider.New(name)
		if err != nil {
			fmt.Fprintf(&b, "| %s | — | error: %s | | |\n", name, esc(err.Error()))
			continue
		}
		type agg struct{ files, fp, kept, lost int }
		aggs := map[string]*agg{}
		for _, c := range cases {
			l, ok := provider.LangOfPath(c.Name, c.Data)
			if !ok || !supports(p, l.Name) {
				continue
			}
			res, err := p.Analyze(l.Name, c.Data)
			if err != nil || len(res.Diags) == 0 {
				continue
			}
			ctx, err := provider.ToContext(l.Name, c.Data, p.Caps(l.Name), res, provider.NeedLexical)
			if err != nil {
				continue
			}
			a := aggs[c.Lang]
			if a == nil {
				a = &agg{}
				aggs[c.Lang] = a
			}
			a.files++
			starts := provider.LineStarts(c.Data)
			refused := map[int]bool{}
			for _, d := range res.Diags {
				lo := provider.LineOf(starts, d.Start)
				hi := provider.LineOf(starts, max(d.End-1, d.Start))
				for n := lo - 1; n <= hi+1; n++ {
					refused[n] = true
				}
			}
			isComment := func(n int) bool { return n >= 1 && n <= len(ctx.Class) && ctx.Class[n-1] == annot.Comment }
			policy, _ := corpus.ParseLines(c.Exp.Extra["x-policy"])
			for _, n := range append(append([]int(nil), c.Exp.Lookalikes...), c.Exp.Readonly...) {
				if !containsInt(policy, n) && isComment(n) && !refused[n] {
					a.fp++
					notes = append(notes, fmt.Sprintf("- %s %s/%s: line %d (look-alike/read-only) writable under the local policy", name, c.Lang, c.Name, n))
				}
			}
			for _, n := range c.Exp.Writable {
				if isComment(n) && !refused[n] {
					a.kept++
				} else {
					a.lost++
				}
			}
		}
		for _, lang := range corpusLangs {
			if a := aggs[lang]; a != nil {
				fmt.Fprintf(&b, "| %s | %s | %d | %d | %d / %d |\n", name, lang, a.files, a.fp, a.kept, a.lost)
			}
		}
	}
	b.WriteString("\n## FP-writable lines under the local policy\n\n")
	if len(notes) == 0 {
		b.WriteString("None.\n")
	} else {
		b.WriteString(strings.Join(notes, "\n") + "\n")
	}
	if err := os.WriteFile(*out, []byte(b.String()), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\n", *out)
	return 0
}

func supports(p provider.Provider, lang string) bool {
	for _, l := range p.Langs() {
		if l == lang {
			return true
		}
	}
	return false
}

func containsInt(xs []int, n int) bool {
	for _, x := range xs {
		if x == n {
			return true
		}
	}
	return false
}
