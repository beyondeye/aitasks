package provider

import (
	"errors"
	"testing"
)

func tok(src string, s, e int) RawToken { return RawToken{Start: s, End: e, Text: []byte(src[s:e])} }

func TestValidateFragments(t *testing.T) {
	src := `x = "abc"`
	// Pygments splits the literal into `"`, `abc`, `"`: legitimate fragments.
	toks := []RawToken{tok(src, 0, 1), tok(src, 1, 2), tok(src, 2, 3), tok(src, 3, 4), tok(src, 4, 5), tok(src, 5, 8), tok(src, 8, 9)}
	if _, err := ValidateTokens([]byte(src), toks, nil, GapPolicy{Total: true}); err != nil {
		t.Fatal(err)
	}
}

func TestValidateTextMismatchIsAdapterFailure(t *testing.T) {
	src := "é // c"
	// A converter that used code points as bytes puts the comment at 2.
	bad := []RawToken{{Start: 0, End: 2, Text: []byte("é")}, {Start: 2, End: 6, Text: []byte(" // ")}}
	_, err := ValidateTokens([]byte(src), bad, nil, GapPolicy{})
	if !errors.Is(err, ErrAdapterConversion) {
		t.Fatalf("want adapter-conversion failure, got %v", err)
	}
}

func TestValidateGapAtDiagIsKept(t *testing.T) {
	src := "a # b"
	// ANTLR: recognition error at '#' (offset 2), Recover consumed it; no token.
	toks := []RawToken{tok(src, 0, 1), tok(src, 1, 2), tok(src, 3, 5)}
	diags := []Diag{{Start: 2, End: 3, Reason: "token recognition error at: '#'"}}
	gaps, err := ValidateTokens([]byte(src), toks, diags, GapPolicy{})
	if err != nil || len(gaps) != 1 || gaps[0] != (Gap{2, 3, "diag"}) {
		t.Fatalf("gaps %v err %v", gaps, err)
	}
}

func TestValidateSkipGapOnlyWithSkipRules(t *testing.T) {
	src := "a  b"
	toks := []RawToken{tok(src, 0, 1), tok(src, 3, 4)}
	gaps, err := ValidateTokens([]byte(src), toks, nil, GapPolicy{SkipRules: true})
	if err != nil || len(gaps) != 1 || gaps[0].Why != "skip" {
		t.Fatalf("with skip rules: gaps %v err %v", gaps, err)
	}
	if _, err := ValidateTokens([]byte(src), toks, nil, GapPolicy{}); !errors.Is(err, ErrAdapterConversion) {
		t.Fatalf("an unexplained gap was accepted: %v", err)
	}
}

func TestValidateTotalTokeniserGapFails(t *testing.T) {
	src := "ab"
	diags := []Diag{{Start: 1, End: 2}}
	if _, err := ValidateTokens([]byte(src), []RawToken{tok(src, 0, 1)}, diags, GapPolicy{Total: true}); !errors.Is(err, ErrAdapterConversion) {
		t.Fatalf("a total tokeniser's gap was accepted: %v", err)
	}
}

func TestValidateOrderAndBounds(t *testing.T) {
	src := "abc"
	for _, toks := range [][]RawToken{
		{tok(src, 1, 2), tok(src, 0, 1)},
		{{Start: 2, End: 4, Text: []byte("c?")}},
	} {
		if _, err := ValidateTokens([]byte(src), toks, nil, GapPolicy{SkipRules: true}); !errors.Is(err, ErrAdapterConversion) {
			t.Fatalf("%v accepted: %v", toks, err)
		}
	}
}

func TestValidateLeadingBOM(t *testing.T) {
	src := string(BOM) + "a"
	gaps, err := ValidateTokens([]byte(src), []RawToken{tok(src, 3, 4)}, nil, GapPolicy{Total: true})
	if err != nil || len(gaps) != 1 || gaps[0].Why != "bom" {
		t.Fatalf("gaps %v err %v", gaps, err)
	}
}
