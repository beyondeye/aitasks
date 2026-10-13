package runner

import (
	"bytes"
	"fmt"
	"sort"

	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

// rangeLevel checks a provider's reported ranges (only when it declares
// TokenRanges): spans in bounds; comment spans sorted and disjoint; a line
// comment starts with the leader and ends at end of line; comment ranges
// equal the native oracle's; with FullCover the leaves reproduce the input.
func rangeLevel(row *Row, lang string, c corpus.Case, res provider.Result, s Subject, opt Options) {
	src := c.Data
	l, _ := provider.LangByName(lang)
	viol := 0
	var comments []provider.Span
	for _, sp := range res.Spans {
		if sp.Start < 0 || sp.End > len(src) || sp.Start > sp.End {
			viol++
			row.note("range: span [%d,%d) out of bounds", sp.Start, sp.End)
			continue
		}
		if sp.Kind == provider.LineComment || sp.Kind == provider.BlockComment {
			comments = append(comments, sp)
		}
		if sp.Kind == provider.LineComment {
			if !bytes.HasPrefix(src[sp.Start:], []byte(l.Leader)) {
				viol++
				row.note("range: line comment at %d does not start with %q", sp.Start, l.Leader)
			}
			if !atEOL(src, sp.End) {
				viol++
				row.note("range: line comment [%d,%d) does not end at end of line", sp.Start, sp.End)
			}
		}
	}
	sort.Slice(comments, func(i, j int) bool { return comments[i].Start < comments[j].Start })
	for i := 1; i < len(comments); i++ {
		if comments[i].Start < comments[i-1].End {
			viol++
			row.note("range: comment spans overlap at %d", comments[i].Start)
		}
	}
	caps := s.Caps(lang)
	switch {
	case caps.FullCover && len(res.Leaves) == 0 && len(res.Diags) > 0:
		// A lexer that reports a recognition error may leave the offending
		// input untokenised (ANTLR: Recover skips it); the adapter attributes
		// that gap to the Diag (t1954_3 Layer 1) and sends no partition.
		row.note("range: full cover not checked: uncertain input, recovery gaps attributed to its diagnostics")
	case caps.FullCover:
		for _, v := range partitionViolations(res.Leaves, src) {
			viol++
			row.note("range: full cover: %s", v)
		}
	}
	oracleNote := "no native oracle"
	if opt.Oracle != nil {
		want, name, err := opt.Oracle(c.Name, lang, src)
		switch {
		case err != nil:
			oracleNote = "oracle " + name + " failed: " + oneLine(err.Error())
		case name == s.Name:
			oracleNote = "provider is the oracle (" + name + ")"
		case sharesOracle(s, name):
			oracleNote = "self-consistency: shares the " + name + " extraction, not independent validation"
		case name == "":
			oracleNote = "no native oracle"
		default:
			d := spanDiff(comments, want, src)
			oracleNote = fmt.Sprintf("vs %s: %d differing comment ranges", name, len(d))
			for _, x := range d {
				viol++
				row.note("range vs %s: %s", name, x)
			}
		}
	}
	if viol == 0 {
		row.Range = "pass (" + oracleNote + ")"
	} else {
		row.Range = fmt.Sprintf("fail:%d (%s)", viol, oracleNote)
	}
}

// sharesOracle: the subject wraps the very extraction the oracle uses
// (t1954_3 tsnative vs ts-parser), so agreement proves only consistency.
func sharesOracle(s Subject, name string) bool {
	so, ok := s.P.(provider.SharedOracle)
	return ok && name != "" && so.SharesOracle() == name
}

// partitionViolations requires the leaves to be an exact partition of src:
// in bounds, in order, contiguous, starting at 0 and ending at len(src) —
// and, as a consequence, reproducing the input bytes. Reconstruction alone
// is not enough: [0,1),[0,1) "reproduces" "aa".
func partitionViolations(leaves []provider.Span, src []byte) []string {
	var v []string
	if len(leaves) == 0 {
		if len(src) > 0 {
			v = append(v, "no leaves for a non-empty input")
		}
		return v
	}
	pos := 0
	var b bytes.Buffer
	for i, lf := range leaves {
		switch {
		case lf.Start < 0 || lf.End > len(src) || lf.Start > lf.End:
			v = append(v, fmt.Sprintf("leaf %d [%d,%d) out of bounds", i, lf.Start, lf.End))
			return v
		case lf.Start != pos:
			v = append(v, fmt.Sprintf("leaf %d starts at %d, want %d (gap or overlap)", i, lf.Start, pos))
			return v
		}
		b.Write(src[lf.Start:lf.End])
		pos = lf.End
	}
	if pos != len(src) {
		v = append(v, fmt.Sprintf("leaves end at %d, input is %d bytes", pos, len(src)))
	}
	if len(v) == 0 && !bytes.Equal(b.Bytes(), src) {
		v = append(v, "leaves do not reproduce the input")
	}
	return v
}

func atEOL(src []byte, end int) bool {
	return end == len(src) || src[end] == '\n' || (src[end] == '\r' && end+1 < len(src) && src[end+1] == '\n') || (src[end] == '\r' && end+1 == len(src))
}

func spanDiff(got, want []provider.Span, src []byte) []string {
	key := func(s provider.Span) string { return fmt.Sprintf("[%d,%d)", s.Start, s.End) }
	g := map[string]bool{}
	for _, s := range got {
		g[key(s)] = true
	}
	w := map[string]bool{}
	for _, s := range want {
		w[key(s)] = true
	}
	var out []string
	for _, s := range want {
		if !g[key(s)] {
			out = append(out, "missing "+key(s)+" "+excerpt(src, s))
		}
	}
	for _, s := range got {
		if !w[key(s)] {
			out = append(out, "extra "+key(s)+" "+excerpt(src, s))
		}
	}
	return out
}

func excerpt(src []byte, s provider.Span) string {
	e := s.End
	if e-s.Start > 40 {
		e = s.Start + 40
	}
	if s.Start < 0 || e > len(src) || s.Start > e {
		return ""
	}
	return fmt.Sprintf("%q", src[s.Start:e])
}
