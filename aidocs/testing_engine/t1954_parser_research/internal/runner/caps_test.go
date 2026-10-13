//go:build !unpatched

package runner

import (
	"errors"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

// fakeProvider reports what the landed lexer sees, as spans, with
// configurable capabilities: it isolates the capability rules from any
// candidate's lexing quality.
type fakeProvider struct {
	lang    string
	caps    provider.Capabilities
	anchors provider.Anchors
}

func (f fakeProvider) Name() string                      { return "fake" }
func (f fakeProvider) Langs() []string                   { return []string{f.lang} }
func (f fakeProvider) Caps(string) provider.Capabilities { return f.caps }
func (f fakeProvider) Analyze(lang string, src []byte) (provider.Result, error) {
	l, _ := provider.LangByName(lang)
	// The landed lexer, with the hook that called us cleared (annot.Classify
	// would otherwise delegate straight back here).
	saved := annot.ClassifyHook
	annot.ClassifyHook = nil
	ctx := annot.Classify(l, src)
	annot.ClassifyHook = saved
	starts := provider.LineStarts(src)
	var res provider.Result
	for i, c := range ctx.Class {
		end := len(src)
		if i+1 < len(starts) {
			end = starts[i+1] - 1
		}
		switch c {
		case annot.Comment:
			f := starts[i]
			for src[f] == ' ' || src[f] == '\t' {
				f++
			}
			res.Spans = append(res.Spans, provider.Span{Start: f, End: end, Kind: provider.LineComment})
		case annot.Literal:
			res.Spans = append(res.Spans, provider.Span{Start: starts[i] - 1, End: end, Kind: provider.String})
		}
	}
	res.Anchors = f.anchors
	return res, nil
}

const annotatedKt = `package app

// testmap:covers app/a.kt @2026-01-01/0123456789
object F {
    // testmap:unit Welcome
    // testmap:covers app/w.kt
    fun welcome() = 1
}
`

const freshKt = "class T\n"

func kcase(name, src string, ops ...corpus.Op) corpus.Case {
	return corpus.Case{Lang: "kotlin", Name: name, Data: []byte(src), Mode: 0o644,
		Exp: corpus.Expect{Lang: "kotlin", Placement: map[string]int{}, Extra: map[string]string{}}, Edits: ops}
}

func op(kind, text, outcome string) corpus.Op {
	args := map[string]string{}
	for _, f := range strings.Fields(text) {
		k, v, _ := strings.Cut(f, "=")
		args[k] = v
	}
	args["from"] = "original"
	return corpus.Op{Kind: kind, Args: args, Outcome: outcome, Text: text}
}

const st = "@2026-02-02/bbbbbbbbbb"

// Missing placement anchors block ONLY the fresh file-level insertion: a
// restamp, a member insertion and a file-level append by the same provider
// are measured (applied through the real PlanCovers → Apply).
func TestMissingAnchorsBlockOnlyFreshFileInsertion(t *testing.T) {
	s := Subject{Name: "fake", P: fakeProvider{lang: "kotlin", caps: provider.Capabilities{TokenRanges: true, Errors: true}}}
	annotated := kcase("a.kt", annotatedKt,
		op("annotate", "member= source=app/a.kt stamp="+st, "applied"),
		op("annotate", "member=Welcome source=app/more.kt stamp="+st, "applied"),
		op("annotate", "member= source=app/b.kt stamp="+st, "applied"),
	)
	r := Run(s, annotated, Options{})
	if r.Status != "ok" || r.OpsApplied != 3 || r.OpsUnsupported != 0 {
		t.Fatalf("annotated: status %s applied %d unsupported %d notes %v", r.Status, r.OpsApplied, r.OpsUnsupported, r.Notes)
	}
	fresh := kcase("f.kt", freshKt, op("annotate", "member= source=app/f.kt stamp="+st, "applied"))
	r = Run(s, fresh, Options{})
	if r.OpsUnsupported != 1 || r.OpsApplied != 0 || !strings.Contains(strings.Join(r.Notes, "\n"), "unsupported:APackage,AImportEnd") {
		t.Fatalf("fresh: applied %d unsupported %d notes %v", r.OpsApplied, r.OpsUnsupported, r.Notes)
	}
}

// Declared anchors with value 0 are confirmed-empty: the fresh insertion runs
// and is placed as for a file without package or imports.
func TestDeclaredZeroAnchorsAreAccepted(t *testing.T) {
	s := Subject{Name: "fake", P: fakeProvider{lang: "kotlin",
		caps: provider.Capabilities{TokenRanges: true, Errors: true, Anchors: provider.APackage | provider.AImportEnd}}}
	fresh := kcase("f.kt", freshKt, op("annotate", "member= source=app/f.kt stamp="+st, "applied"))
	fresh.Edits[0].After = []corpus.Record{{Line: 1, Key: "covers", Value: "app/f.kt", Stamp: st, Origin: "comment"}}
	r := Run(s, fresh, Options{})
	if r.OpsApplied != 1 || r.RecordCorruption != 0 {
		t.Fatalf("declared-zero: applied %d corruption %d notes %v", r.OpsApplied, r.RecordCorruption, r.Notes)
	}
}

// Without error reporting every write is unsupported, while line classes
// are still scored.
func TestNoErrorReportingMeansNoWrites(t *testing.T) {
	s := Subject{Name: "fake", P: fakeProvider{lang: "kotlin", caps: provider.Capabilities{TokenRanges: true}}}
	c := kcase("a.kt", annotatedKt,
		op("annotate", "member= source=app/a.kt stamp="+st, "applied"),
		op("annotate", "member=Welcome source=app/more.kt stamp="+st, "applied"),
	)
	c.Exp.Writable = []int{3, 5, 6}
	r := Run(s, c, Options{})
	if r.Status != "ok" || len(r.Classes) == 0 || r.MissedWritable != 0 {
		t.Fatalf("lexical must still score: status %s classes %d missed %d", r.Status, len(r.Classes), r.MissedWritable)
	}
	if r.OpsUnsupported != 2 || r.OpsApplied != 0 || !strings.Contains(strings.Join(r.Notes, "\n"), "unsupported:Errors") {
		t.Fatalf("writes: applied %d unsupported %d notes %v", r.OpsApplied, r.OpsUnsupported, r.Notes)
	}
}

// A Python provider without DocLiterals cannot supply docstring records or
// write, but its classes still score.
func TestPythonWithoutDocLiterals(t *testing.T) {
	s := Subject{Name: "fake", P: fakeProvider{lang: "python", caps: provider.Capabilities{TokenRanges: true, Errors: true}}}
	c := corpus.Case{Lang: "python", Name: "p.py", Data: []byte("\"\"\"Doc.\ntestmap:covers src/a.sh\n\"\"\"\n# testmap:covers src/b.sh\n"), Mode: 0o644,
		Exp:   corpus.Expect{Lang: "python", Writable: []int{4}, Placement: map[string]int{}, Extra: map[string]string{}},
		Edits: []corpus.Op{op("annotate", "member= source=src/b.sh stamp="+st, "applied")}}
	r := Run(s, c, Options{})
	notes := strings.Join(r.Notes, "\n")
	if r.Status != "ok" || r.MissedWritable != 0 || !strings.Contains(notes, "records: unsupported:DocLiterals") || r.OpsUnsupported != 1 {
		t.Fatalf("status %s missed %d unsupported %d notes %v", r.Status, r.MissedWritable, r.OpsUnsupported, r.Notes)
	}
}

// A raw write needs what every write needs: a provider without error
// reporting is unsupported for it (it used to reach Apply through the
// fail-closed context and be mis-scored as refused:uncertain + corruption).
func TestRawOpChecksCapabilities(t *testing.T) {
	s := Subject{Name: "fake", P: fakeProvider{lang: "kotlin", caps: provider.Capabilities{TokenRanges: true}}}
	c := kcase("a.kt", annotatedKt, corpus.Op{Kind: "raw", Outcome: "refused:not-comment", Text: "raw",
		Args: map[string]string{"kind": "replace", "line": "7", "member": "Welcome", "source": "app/x.kt", "new": "    // testmap:covers app/x.kt"}})
	r := Run(s, c, Options{})
	if r.OpsUnsupported != 1 || r.RecordCorruption != 0 || r.OpsRefused != 0 ||
		!strings.Contains(strings.Join(r.Notes, "\n"), "unsupported:Errors") {
		t.Fatalf("unsupported %d corruption %d refused %d notes %v", r.OpsUnsupported, r.RecordCorruption, r.OpsRefused, r.Notes)
	}
}

// failingProvider works for the lexical and record levels, then fails: the
// failure lands inside the edit suite.
type failingProvider struct {
	fakeProvider
	calls *int
}

func (f failingProvider) Analyze(lang string, src []byte) (provider.Result, error) {
	*f.calls++
	if *f.calls > 2 {
		return provider.Result{}, errors.New("boom")
	}
	return f.fakeProvider.Analyze(lang, src)
}

// A provider failure during an edit is "not measured", never a refusal or
// corruption.
func TestProviderFailureIsNotMeasured(t *testing.T) {
	n := 0
	s := Subject{Name: "failing", P: failingProvider{fakeProvider{lang: "kotlin",
		caps: provider.Capabilities{TokenRanges: true, Errors: true}}, &n}}
	c := kcase("a.kt", annotatedKt, op("annotate", "member= source=app/a.kt stamp="+st, "applied"))
	r := Run(s, c, Options{})
	if r.OpsNotMeasured != 1 || r.RecordCorruption != 0 || r.OverRefusal != 0 {
		t.Fatalf("not-measured %d corruption %d over-refusal %d status %s notes %v",
			r.OpsNotMeasured, r.RecordCorruption, r.OverRefusal, r.Status, r.Notes)
	}
}

// flakyProvider works until told to fail.
type flakyProvider struct {
	fakeProvider
	fail *bool
}

func (f flakyProvider) Analyze(lang string, src []byte) (provider.Result, error) {
	if *f.fail {
		return provider.Result{}, errors.New("boom after the write")
	}
	return f.fakeProvider.Analyze(lang, src)
}

// A provider that fails only when the records are read back after a
// successful write: the write stands (applied, fidelity checked), the
// records are "not verified" — never compared as an empty list and scored
// as corruption.
func TestProviderFailingAfterApplyLeavesRecordsUnverified(t *testing.T) {
	fail := false
	s := Subject{Name: "flaky", P: flakyProvider{fakeProvider{lang: "kotlin",
		caps: provider.Capabilities{TokenRanges: true, Errors: true}}, &fail}}
	afterApply = func(string) { fail = true }
	defer func() { afterApply = nil }()
	c := kcase("a.kt", annotatedKt, op("annotate", "member= source=app/a.kt stamp="+st, "applied"))
	r := Run(s, c, Options{})
	if r.OpsApplied != 1 || r.RecordCorruption != 0 || r.RecordsNotVerified != 1 || r.Fidelity != 0 ||
		!strings.Contains(strings.Join(r.Notes, "\n"), "records after not verified") {
		t.Fatalf("applied %d corruption %d not-verified %d fidelity %d notes %v",
			r.OpsApplied, r.RecordCorruption, r.RecordsNotVerified, r.Fidelity, r.Notes)
	}
}
