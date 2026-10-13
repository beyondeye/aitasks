package runner

import (
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

// fakeTS reports one line comment; shares optionally names the oracle whose
// extraction it wraps (t1954_3: tsnative shares ts-parser's).
type fakeTS struct {
	name, shares string
}

func (f fakeTS) Name() string    { return f.name }
func (f fakeTS) Langs() []string { return []string{"typescript"} }
func (f fakeTS) Caps(string) provider.Capabilities {
	return provider.Capabilities{TokenRanges: true, Errors: true}
}
func (f fakeTS) Analyze(string, []byte) (provider.Result, error) {
	return provider.Result{Spans: []provider.Span{{Start: 0, End: 4, Kind: provider.LineComment}}}, nil
}

type fakeShared struct{ fakeTS }

func (f fakeShared) SharesOracle() string { return f.shares }

const tsSrc = "// c\nconst x = 1;\n"

func tsCase() corpus.Case {
	return corpus.Case{Lang: "typescript", Name: "a.ts", Data: []byte(tsSrc),
		Exp: corpus.Expect{Lang: "typescript", Placement: map[string]int{}, Extra: map[string]string{}}}
}

func tsParserOracle(string, string, []byte) ([]provider.Span, string, error) {
	return []provider.Span{{Start: 0, End: 4, Kind: provider.LineComment}}, "ts-parser", nil
}

// A provider that wraps the oracle's own extraction agrees with it by
// construction: its range cell must say self-consistency and never present
// the agreement as an independent "vs ts-parser" comparison.
func TestSharedOracleIsSelfConsistencyNotValidation(t *testing.T) {
	opt := Options{Oracle: tsParserOracle}
	shared := Subject{Name: "tsnative", P: fakeShared{fakeTS{name: "tsnative", shares: "ts-parser"}}}
	r := Run(shared, tsCase(), opt)
	if !strings.Contains(r.Range, "self-consistency: shares the ts-parser extraction") || strings.Contains(r.Range, "vs ts-parser") {
		t.Fatalf("shared provider range %q", r.Range)
	}
	// Negative control: the same agreement from an independent provider is
	// a real comparison.
	indep := Subject{Name: "other", P: fakeTS{name: "other"}}
	if r := Run(indep, tsCase(), opt); !strings.Contains(r.Range, "vs ts-parser: 0 differing") {
		t.Fatalf("independent provider range %q", r.Range)
	}
	// The pre-existing label (a provider that IS the oracle) is unchanged.
	same := Subject{Name: "ts-parser", P: fakeTS{name: "ts-parser"}}
	if r := Run(same, tsCase(), opt); !strings.Contains(r.Range, "provider is the oracle (ts-parser)") {
		t.Fatalf("provider-is-oracle range %q", r.Range)
	}
}
