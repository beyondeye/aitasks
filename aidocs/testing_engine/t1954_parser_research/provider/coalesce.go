package provider

import "sort"

// Layer 2 of the t1954_3 adapter contract: validated raw tokens are
// normalised into the construct-level spans ToContext expects. Highlighters
// split one literal into fragments at newlines (Pygments: `"""a\n# no\nb"""`
// is 7 String tokens), and a continuation line that begins exactly on a
// fragment boundary is not *strictly inside* any fragment, so ToContext
// (insideData's `s.Start < off`) would class it Code. ToContext is not
// changed — that would alter every t1954_1/2 result — so the provider
// coalesces. A construct that genuinely opens at a line start keeps
// Start == lineStart and its class.

// TokClass is a raw token's role, as a provider maps its tool's types.
type TokClass uint8

const (
	TCode TokClass = iota
	TString
	THeredoc
	TLineComment
	TBlockComment
	TInterpOpen  // string-family token that opens an interpolation (`${`, `#{`, `\(`)
	TInterpClose // string-family token that closes one (`}`, `)`)
)

// CTok is a classified raw token.
type CTok struct {
	Start, End int
	Class      TokClass
}

func stringFamily(c TokClass) bool {
	return c == TString || c == THeredoc || c == TInterpOpen || c == TInterpClose
}

// Coalesce merges classified tokens into construct-level spans:
//   - a literal run is a maximal run of contiguous string-family tokens;
//     an interpolation opened inside the run absorbs every token up to its
//     matching close (t1954_2 policy: data across the whole range,
//     interpolations included) — but never a token the tool itself classed
//     as a comment, which ends the run. Heredoc if any token is one, else
//     String;
//   - contiguous block-comment fragments are one BlockComment;
//   - contiguous line-comment fragments are one LineComment, never across a
//     newline, and a trailing newline is trimmed (a line comment ends at the
//     end of its line, not after it).
//
// Token order must already be validated (Layer 1).
func Coalesce(src []byte, toks []CTok) []Span {
	var out []Span
	for i := 0; i < len(toks); {
		t := toks[i]
		switch {
		case stringFamily(t.Class):
			start, end, depth, kind := t.Start, t.End, 0, String
			j := i
			for ; j < len(toks); j++ {
				u := toks[j]
				if j > i && depth == 0 && (!stringFamily(u.Class) || u.Start != end) {
					break
				}
				// Never reclassify a token the tool called a comment: an
				// interpolation the tool left without a closing token ends
				// the run instead of swallowing the rest of the file.
				if u.Class == TLineComment || u.Class == TBlockComment {
					break
				}
				switch u.Class {
				case TInterpOpen:
					depth++
				case TInterpClose:
					if depth > 0 {
						depth--
					}
				case THeredoc:
					kind = Heredoc
				}
				end = u.End
			}
			out = append(out, Span{start, end, kind})
			i = j
		case t.Class == TBlockComment:
			start, end := t.Start, t.End
			j := i + 1
			for ; j < len(toks) && toks[j].Class == TBlockComment && toks[j].Start == end; j++ {
				end = toks[j].End
			}
			out = append(out, Span{start, end, BlockComment})
			i = j
		case t.Class == TLineComment:
			start, end := t.Start, t.End
			j := i + 1
			for ; j < len(toks) && toks[j].Class == TLineComment && toks[j].Start == end && !hasNL(src[start:end]); j++ {
				end = toks[j].End
			}
			for end > start && (src[end-1] == '\n' || src[end-1] == '\r') {
				end--
			}
			out = append(out, Span{start, end, LineComment})
			i = j
		default:
			i++
		}
	}
	return out
}

func hasNL(b []byte) bool {
	for _, c := range b {
		if c == '\n' {
			return true
		}
	}
	return false
}

// Bracketed merges spans for tools whose literals are delimited by distinct
// opener and closer token types (ANTLR Kotlin's QUOTE_OPEN … QUOTE_CLOSE
// with interpolations and nested literals between): one String span from
// each outermost opener to its matching closer, or to the last token when
// the literal is unclosed. isOpen/isClose classify by index.
func Bracketed(n int, at func(i int) (start, end int), isOpen, isClose func(i int) bool) []Span {
	var out []Span
	depth, start, end := 0, 0, 0
	for i := 0; i < n; i++ {
		s, e := at(i)
		switch {
		case isOpen(i):
			if depth == 0 {
				start = s
			}
			depth++
			end = e
		case depth > 0 && isClose(i):
			depth--
			end = e
			if depth == 0 {
				out = append(out, Span{start, end, String})
			}
		case depth > 0:
			end = e
		}
	}
	if depth > 0 {
		out = append(out, Span{start, end, String})
	}
	return out
}

// SortSpans orders spans by start (then end).
func SortSpans(s []Span) {
	sort.Slice(s, func(i, j int) bool {
		if s[i].Start != s[j].Start {
			return s[i].Start < s[j].Start
		}
		return s[i].End < s[j].End
	})
}
