// Package runner scores a subject — the landed baseline or a candidate
// provider — on one corpus case, at every level of the t1954 shared design:
// lexical (line classes), records (ParseFile vs .expect read:), placement,
// edits (ParseFile → PlanCovers → Apply on a scratch copy, through the seam),
// range evidence and controlled behaviour. Nothing is re-implemented: every
// record, placement, refusal and write comes from the real annot snapshot.
package runner

import (
	"errors"
	"fmt"
	"sort"
	"strings"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/seam"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

// Subject is what is being evaluated. P == nil is the baseline: the real
// annot with both hooks nil.
type Subject struct {
	Name string
	P    provider.Provider
	// Delegate hands the languages P does not support to the landed lexer
	// (bench only: an end-to-end scan covers every language of a repository).
	Delegate bool
}

// Baseline is the landed M2.2 lexers.
var Baseline = Subject{Name: "baseline"}

// IsBaseline reports whether s is the landed baseline.
func (s Subject) IsBaseline() bool { return s.P == nil }

// Supports reports whether s handles lang at all.
func (s Subject) Supports(lang string) bool {
	if s.IsBaseline() {
		return !provider.IsResearch(lang)
	}
	for _, l := range s.P.Langs() {
		if l == lang {
			return true
		}
	}
	return false
}

// Caps is the subject's capabilities for lang (the baseline's are what
// annot.Context exposes; it has no token ranges).
func (s Subject) Caps(lang string) provider.Capabilities {
	if s.IsBaseline() {
		return provider.Capabilities{Errors: true, DocLiterals: lang == "python", Anchors: provider.RequiredAnchors(lang)}
	}
	return s.P.Caps(lang)
}

// Row is one subject × case result. Counters are "must be 0" (safety) or
// recall/cost; Notes carry the per-finding detail.
type Row struct {
	Lang, Case string
	Status     string // ok | unsupported:<why> | error:<msg>

	// Safety (must be 0).
	FPWritable, DocstringWrite, SilentUncertain, RecordCorruption int
	// Recall / cost.
	MissedWritable, MissedComment, ReadMismatch, OverRefusal, PlacementMiss int
	// File fidelity and behaviour, on applied edits; BehaviourNotMeasured
	// counts applied edits whose before/after run could not happen.
	Fidelity, Behaviour, BehaviourNotMeasured int
	// Range evidence: "n/a — not exposed", "pass", or "fail:<n>".
	Range string
	// Edit-suite accounting. RecordsNotVerified counts ops whose post-op
	// record list could not be read back (the subject failed on re-read).
	Ops, OpsApplied, OpsRefused, OpsUnsupported, OpsNotMeasured, RecordsNotVerified int

	SilentUncertainNA bool // the subject cannot report errors at all
	Classes           []annot.LineClass
	Notes             []string
}

func (r *Row) note(format string, a ...any) { r.Notes = append(r.Notes, fmt.Sprintf(format, a...)) }

// Options tune a run.
type Options struct {
	Oracle    func(name, lang string, src []byte) ([]provider.Span, string, error) // comment ranges from a native oracle; oracle name; nil = none
	Behaviour bool                                                                 // run .expect exec: commands
	Scratch   string                                                               // scratch parent dir ("" = os temp)
}

// Run scores s on c.
func Run(s Subject, c corpus.Case, opt Options) Row {
	row := Row{Lang: c.Lang, Case: c.Name, Status: "ok", Range: "n/a — not exposed"}
	lang, ok := langOf(c)
	if !ok {
		row.Status = "error:no language for " + c.Name
		return row
	}
	if !s.Supports(lang) {
		row.Status = "unsupported:language"
		return row
	}
	caps := s.Caps(lang)

	// Lexical level.
	ctx, res, err := s.context(lang, c.Data, provider.NeedLexical)
	if err != nil {
		row.Status = statusOf(err)
		return row
	}
	row.Classes = ctx.Class
	lexical(&row, c, ctx, caps)

	// Range level.
	if !s.IsBaseline() && caps.TokenRanges {
		rangeLevel(&row, lang, c, res, s, opt)
	}

	// Record and placement levels.
	records(&row, s, c, lang)

	// Edit suite.
	if len(c.Edits) > 0 {
		edits(&row, s, c, lang, opt)
	}
	return row
}

func langOf(c corpus.Case) (string, bool) {
	l, ok := provider.LangOfPath(c.Name, c.Data)
	return l.Name, ok
}

func statusOf(err error) string {
	var u *provider.UnsupportedCapabilityError
	if errors.As(err, &u) {
		return u.Error()
	}
	return "error:" + oneLine(err.Error())
}

func oneLine(s string) string { return strings.NewReplacer("\n", " ", "|", "/").Replace(s) }

// context classifies data as the subject would hand it to annot.
func (s Subject) context(lang string, data []byte, need provider.Need) (annot.Context, provider.Result, error) {
	if s.IsBaseline() {
		var ctx annot.Context
		err := seam.With(nil, nil, func() error {
			l, _ := provider.LangByName(lang)
			ctx = annot.Classify(l, data)
			return nil
		})
		return ctx, provider.Result{}, err
	}
	res, err := s.P.Analyze(lang, data)
	if err != nil {
		return annot.Context{}, res, fmt.Errorf("provider: %w", err)
	}
	ctx, err := provider.ToContext(lang, data, s.P.Caps(lang), res, need)
	return ctx, res, err
}

// hooks returns the seam hooks for s at need, recording provider failures in
// *fails. A provider that fails or lacks a capability yields an Uncertain
// context: annot then refuses rather than trusting it (fail closed).
func (s Subject) hooks(need provider.Need, fails *[]string) (func(annot.Lang, []byte) annot.Context, func(string, []byte) (annot.Lang, bool)) {
	if s.IsBaseline() {
		return nil, nil
	}
	classify := func(l annot.Lang, data []byte) annot.Context {
		if s.Delegate && !s.Supports(l.Name) {
			return seam.Landed(l, data)
		}
		ctx, _, err := s.context(l.Name, data, need)
		if err != nil {
			*fails = append(*fails, statusOf(err))
			n := len(provider.LineStarts(data))
			cls := make([]annot.LineClass, n)
			for i := range cls {
				cls[i] = annot.Literal
			}
			return annot.Context{Class: cls, Uncertain: &annot.Unclosed{Line: 1, Construct: "provider: " + statusOf(err)}}
		}
		return ctx
	}
	return classify, provider.ResearchLangOf
}

// withSubject runs fn with s's hooks installed at need.
func (s Subject) withSubject(need provider.Need, fails *[]string, fn func() error) error {
	c, l := s.hooks(need, fails)
	return seam.With(c, l, fn)
}

func lexical(row *Row, c corpus.Case, ctx annot.Context, caps provider.Capabilities) {
	class := func(n int) annot.LineClass {
		if n < 1 || n > len(ctx.Class) {
			return annot.Code
		}
		return ctx.Class[n-1]
	}
	// When the subject declares the file uncertain its classes are never
	// used (ParseFile and Apply refuse), so they are not scored; the refusal
	// itself is scored below (correct, or over-refusal).
	certain := ctx.Uncertain == nil
	policy, _ := corpus.ParseLines(c.Exp.Extra["x-policy"])
	for _, n := range policy {
		if certain && class(n) == annot.Comment {
			row.note("policy divergence: line %d classed Comment (a real comment the M2.2 policy never treats as an annotation line)", n)
		}
	}
	for _, n := range append(append([]int(nil), c.Exp.Lookalikes...), c.Exp.Readonly...) {
		if contains(policy, n) {
			continue
		}
		if certain && class(n) == annot.Comment {
			row.FPWritable++
			row.note("FP-writable: line %d classed Comment (look-alike/read-only)", n)
		}
	}
	for _, n := range c.Exp.Writable {
		if certain && class(n) != annot.Comment {
			row.MissedWritable++
			row.note("missed-writable: line %d classed %s", n, className(class(n)))
		}
	}
	if certain {
		for _, n := range c.Exp.Comments {
			if class(n) != annot.Comment && !contains(c.Exp.Writable, n) {
				row.MissedComment++
				row.note("missed-comment: line %d classed %s", n, className(class(n)))
			}
		}
	}
	switch {
	case c.Exp.Uncertain && ctx.Uncertain == nil && !caps.Errors:
		row.SilentUncertainNA = true
		row.note("silent-uncertain: n/a — subject cannot report errors")
	case c.Exp.Uncertain && ctx.Uncertain == nil:
		row.SilentUncertain++
		row.note("silent-uncertain: expect uncertain, got certain")
	case !c.Exp.Uncertain && ctx.Uncertain != nil:
		row.OverRefusal++
		row.note("over-refusal: valid file uncertain at line %d (%s)", ctx.Uncertain.Line, ctx.Uncertain.Construct)
	}
}

func className(c annot.LineClass) string {
	switch c {
	case annot.Comment:
		return "Comment"
	case annot.Literal:
		return "Literal"
	}
	return "Code"
}

// ClassString renders classes compactly (C=code, #=comment, L=literal).
func ClassString(cls []annot.LineClass) string {
	var b strings.Builder
	for _, c := range cls {
		b.WriteByte("C#L"[c])
	}
	return b.String()
}

// parse runs ParseFile through the seam.
func (s Subject) parse(name string, data []byte, need provider.Need) (*annot.File, []string, error) {
	var f *annot.File
	var perr error
	var fails []string
	err := s.withSubject(need, &fails, func() error {
		f, perr = annot.ParseFile(name, data)
		return nil
	})
	if err != nil {
		return nil, fails, err
	}
	return f, fails, perr
}

func refusalOf(err error) string {
	var se *annot.SyntaxError
	switch {
	case err == nil:
		return ""
	case errors.Is(err, annot.ErrNoLeader):
		return "no-leader"
	case errors.As(err, &se):
		if strings.HasPrefix(se.Reason, "cannot determine comment context") {
			return fmt.Sprintf("uncertain@%d", se.Line)
		}
		return fmt.Sprintf("syntax@%d", se.Line)
	}
	return "error:" + oneLine(err.Error())
}

func records(row *Row, s Subject, c corpus.Case, lang string) {
	caps := s.Caps(lang)
	if err := provider.Check(lang, caps, provider.NeedRecords); err != nil {
		row.note("records: %s", statusOf(err))
		return
	}
	f, fails, err := s.parse(c.Name, c.Data, provider.NeedRecords)
	for _, fl := range fails {
		row.note("provider: %s", fl)
	}
	got := refusalOf(err)
	if !sameRefusal(got, c.Exp.Refuse) {
		if strings.HasPrefix(got, "error:") && !strings.HasPrefix(got, "error:provider") {
			row.Status = got
			return
		}
		row.ReadMismatch++
		row.note("refusal: got %q, want %q", got, c.Exp.Refuse)
		// An uncertain-context refusal was already scored at the lexical
		// level; only a grammar refusal of a valid file is counted here.
		if strings.HasPrefix(got, "syntax") && c.Exp.Refuse == "" && !c.Exp.Uncertain {
			row.OverRefusal++
		}
	}
	if err != nil {
		return
	}
	want := map[string]int{}
	for _, r := range c.Exp.Read {
		want[r.String()]++
	}
	for _, r := range corpus.Records(f) {
		k := r.String()
		if want[k] > 0 {
			want[k]--
			continue
		}
		row.ReadMismatch++
		row.note("read: extra %s", k)
		policy, _ := corpus.ParseLines(c.Exp.Extra["x-policy"])
		if r.Origin == "comment" && !contains(policy, r.Line) && (contains(c.Exp.Lookalikes, r.Line) || contains(c.Exp.Readonly, r.Line)) {
			row.FPWritable++
			row.note("FP-writable: look-alike/read-only line %d read as a comment annotation", r.Line)
		}
	}
	var missing []string
	for k, n := range want {
		for ; n > 0; n-- {
			missing = append(missing, k)
		}
	}
	sort.Strings(missing)
	for _, k := range missing {
		row.ReadMismatch++
		row.note("read: missing %s", k)
	}
	placement(row, s, c, lang, f)
}

// sameRefusal compares refusals; an uncertain-context refusal is compared
// without its line (providers report the diagnostic at different points of
// the same construct), a grammar refusal (syntax@N) exactly.
func sameRefusal(got, want string) bool {
	if strings.HasPrefix(got, "uncertain") && strings.HasPrefix(want, "uncertain") {
		return true
	}
	if !strings.Contains(want, "@") && want != "" {
		kind, _, _ := strings.Cut(got, "@")
		return kind == want // the oracle pins the refusal, not its line
	}
	return got == want
}

func contains(xs []int, x int) bool {
	for _, v := range xs {
		if v == x {
			return true
		}
	}
	return false
}

func placement(row *Row, s Subject, c corpus.Case, lang string, f *annot.File) {
	members := make([]string, 0, len(c.Exp.Placement))
	for m := range c.Exp.Placement {
		members = append(members, m)
	}
	sort.Strings(members)
	for _, m := range members {
		want := c.Exp.Placement[m]
		u, ok := f.Unit(m)
		if !ok {
			row.PlacementMiss++
			row.note("placement %q: no such block", m)
			continue
		}
		fresh := m == "" && u.Last == 0
		if fresh {
			if err := provider.Check(lang, s.Caps(lang), provider.NeedFreshFileInsert); err != nil {
				row.note("placement file: %s", statusOf(err))
				continue
			}
		}
		var got int
		if fresh && provider.IsResearch(lang) {
			def, _, _, _ := f.Placement("")
			anchors, err := s.anchors(lang, c.Data)
			if err != nil {
				row.note("placement file: %s", statusOf(err))
				continue
			}
			got, _ = provider.ProposedFilePlacement(f, lang, provider.Mask(anchors, s.Caps(lang).Anchors))
			row.note("placement file (proposed rule): %d; landed default fixedPosition: %d", got, def)
		} else {
			var err error
			got, _, _, err = f.Placement(m)
			if err != nil {
				row.PlacementMiss++
				row.note("placement %q: %v", m, err)
				continue
			}
		}
		if got != want {
			row.PlacementMiss++
			row.note("placement %q: got after %d, want %d", blockName(m), got, want)
		}
	}
}

func blockName(m string) string {
	if m == "" {
		return "file"
	}
	return "member:" + m
}

// anchors returns the provider's anchors (the baseline has none to give for
// the research languages, which it does not support).
func (s Subject) anchors(lang string, data []byte) (provider.Anchors, error) {
	if s.IsBaseline() {
		return provider.Anchors{}, &provider.UnsupportedCapabilityError{Missing: []string{"anchors(baseline)"}}
	}
	res, err := s.P.Analyze(lang, data)
	if err != nil {
		return provider.Anchors{}, err
	}
	return res.Anchors, nil
}

// ContextOf is the context the subject hands annot for data (NeedLexical).
func ContextOf(s Subject, lang string, data []byte) (annot.Context, error) {
	ctx, _, err := s.context(lang, data, provider.NeedLexical)
	return ctx, err
}

// ParseOf runs ParseFile through the seam with the subject's hooks (NeedRecords).
func ParseOf(s Subject, path string, data []byte) (*annot.File, error) {
	f, _, err := s.parse(path, data, provider.NeedRecords)
	return f, err
}

// Hooks returns the seam hooks of s for a whole-repository scan (NeedRecords).
func Hooks(s Subject, fails *[]string) (func(annot.Lang, []byte) annot.Context, func(string, []byte) (annot.Lang, bool)) {
	return s.hooks(provider.NeedRecords, fails)
}
