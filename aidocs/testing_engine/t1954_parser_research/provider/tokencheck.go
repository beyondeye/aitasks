package provider

import (
	"bytes"
	"errors"
	"fmt"
)

// Layer 1 of the t1954_3 adapter contract: every token a tool emits is
// validated against the ORIGINAL bytes before anything reaches the seam.
// Delimiter shape is deliberately not checked here — tokens are often
// legitimate fragments (`"`, `abc`, `"`) — that stays the runner's range
// metric on construct-level comment spans, scored as a candidate defect.

// ErrAdapterConversion marks a failure of the adapter (offset conversion,
// decoding), never a deficiency of the candidate: the analysis fails and the
// findings list it apart.
var ErrAdapterConversion = errors.New("adapter-conversion")

func adapterErr(format string, a ...any) error {
	return fmt.Errorf("%w: "+format, append([]any{ErrAdapterConversion}, a...)...)
}

// RawToken is one token as the tool reported it, already converted to byte
// offsets of the original source, with the token text the tool reported
// (re-encoded to the original codec by the helper).
type RawToken struct {
	Start, End int
	Text       []byte
	Type       string // the tool's own token type / scope, for coalescing
}

// GapPolicy is what a tool documents about completeness.
type GapPolicy struct {
	// Total: the tool turns every input byte into a token (an unmatched
	// character included, as an error token); any gap is an adapter bug.
	Total bool
	// SkipRules: the grammar has `-> skip` rules, so a gap with no
	// diagnostic is a documented omission, not a bug.
	SkipRules bool
}

// Gap is an uncovered byte range and why it is acceptable.
type Gap struct {
	Start, End int
	Why        string // "diag" | "skip" | "bom"
}

// ValidateTokens checks every token independently of completeness — text
// equal to the original bytes, in bounds, sorted, non-overlapping — then
// classifies every gap:
//   - a leading UTF-8 BOM the tool never saw is accepted;
//   - a gap that holds (or starts at) a diagnostic's offset is explained by
//     that diagnostic (ANTLR's safeMatch → Recover consumes the offending
//     character without a token), and the diagnostic is kept;
//   - otherwise, under SkipRules, a documented omission;
//   - otherwise an adapter failure (always so for a Total tool).
func ValidateTokens(src []byte, toks []RawToken, diags []Diag, pol GapPolicy) ([]Gap, error) {
	pos := 0
	if bytes.HasPrefix(src, BOM) && (len(toks) == 0 || toks[0].Start >= len(BOM)) {
		pos = len(BOM)
	}
	var gaps []Gap
	if pos > 0 {
		gaps = append(gaps, Gap{0, pos, "bom"})
	}
	explain := func(a, b int) error {
		if a == b {
			return nil
		}
		if pol.Total {
			return adapterErr("gap [%d,%d) in the output of a total tokeniser", a, b)
		}
		for _, d := range diags {
			if d.Start >= a && d.Start <= b {
				gaps = append(gaps, Gap{a, b, "diag"})
				return nil
			}
		}
		if pol.SkipRules {
			gaps = append(gaps, Gap{a, b, "skip"})
			return nil
		}
		return adapterErr("unexplained gap [%d,%d) (no diagnostic, grammar has no skip rules)", a, b)
	}
	for i, t := range toks {
		if t.Start < 0 || t.End > len(src) || t.Start > t.End {
			return nil, adapterErr("token %d [%d,%d) out of bounds (len %d)", i, t.Start, t.End, len(src))
		}
		if t.Start < pos {
			return nil, adapterErr("token %d [%d,%d) overlaps or is out of order (previous end %d)", i, t.Start, t.End, pos)
		}
		if !bytes.Equal(src[t.Start:t.End], t.Text) {
			return nil, adapterErr("token %d [%d,%d) is %q in the source but the tool reported %q", i, t.Start, t.End, clip(src[t.Start:t.End]), clip(t.Text))
		}
		if err := explain(pos, t.Start); err != nil {
			return nil, err
		}
		pos = t.End
	}
	if err := explain(pos, len(src)); err != nil {
		return nil, err
	}
	return gaps, nil
}

func clip(b []byte) []byte {
	if len(b) > 30 {
		return b[:30]
	}
	return b
}

// LeavesOf is the raw tokens as Result.Leaves (for a FullCover provider).
func LeavesOf(toks []RawToken) []Span {
	out := make([]Span, len(toks))
	for i, t := range toks {
		out[i] = Span{t.Start, t.End, Other}
	}
	return out
}

// ValidateSpanTexts is Layer 1 for a provider that reports constructs
// rather than a token stream (tsnative: AST comments and literals, which may
// nest — a comment inside a template's interpolation): every span in
// bounds, its reported text equal to the original bytes. Completeness and
// order do not apply.
func ValidateSpanTexts(src []byte, toks []RawToken) error {
	for i, t := range toks {
		if t.Start < 0 || t.End > len(src) || t.Start > t.End {
			return adapterErr("span %d [%d,%d) out of bounds (len %d)", i, t.Start, t.End, len(src))
		}
		if !bytes.Equal(src[t.Start:t.End], t.Text) {
			return adapterErr("span %d [%d,%d) is %q in the source but the tool reported %q", i, t.Start, t.End, clip(src[t.Start:t.End]), clip(t.Text))
		}
	}
	return nil
}
