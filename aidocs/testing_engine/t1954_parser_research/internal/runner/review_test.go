package runner

import (
	"errors"
	"os"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

const execSh = "#!/bin/sh\n# testmap:covers src/a.sh\necho hi\n"

func shCase(mode os.FileMode, exec string) corpus.Case {
	return corpus.Case{Lang: "bash", Name: "m.sh", Data: []byte(execSh), Mode: mode,
		Exp: corpus.Expect{Lang: "bash", Exec: exec, Placement: map[string]int{}, Extra: map[string]string{}},
		Edits: []corpus.Op{{Kind: "annotate", Outcome: "applied", Text: "annotate",
			Args: map[string]string{"member": "", "source": "src/b.sh", "stamp": "@2026-02-02/bbbbbbbbbb"},
			After: []corpus.Record{
				{Line: 2, Key: "covers", Value: "src/a.sh", Origin: "comment"},
				{Line: 3, Key: "covers", Value: "src/b.sh", Stamp: "@2026-02-02/bbbbbbbbbb", Origin: "comment"},
			}}}}
}

// Fidelity compares the mode BEFORE the op with the mode after it: a write
// that turns 0755 into 0600 is reported (it used to compare two post-edit
// stats and miss it).
func TestFidelityCatchesPermissionLoss(t *testing.T) {
	r := Run(Baseline, shCase(0o755, ""), Options{})
	if r.OpsApplied != 1 || r.Fidelity != 0 {
		t.Fatalf("control: applied %d fidelity %d notes %v", r.OpsApplied, r.Fidelity, r.Notes)
	}
	afterApply = func(abs string) { _ = os.Chmod(abs, 0o600) }
	defer func() { afterApply = nil }()
	r = Run(Baseline, shCase(0o755, ""), Options{})
	if r.Fidelity != 1 || !strings.Contains(strings.Join(r.Notes, "\n"), "mode -rwxr-xr-x -> -rw-------") {
		t.Fatalf("permission loss not reported: fidelity %d notes %v", r.Fidelity, r.Notes)
	}
}

// A behaviour check that cannot run is "not measured", never "unchanged".
func TestBehaviourNotRunIsNotMeasured(t *testing.T) {
	r := Run(Baseline, shCase(0o644, "t1954-no-such-tool {file}"), Options{Behaviour: true})
	if r.OpsApplied != 1 || r.Behaviour != 0 || r.BehaviourNotMeasured != 1 ||
		!strings.Contains(strings.Join(r.Notes, "\n"), "behaviour not measured — before the edit: tool missing") {
		t.Fatalf("applied %d behaviour %d not-measured %d notes %v", r.OpsApplied, r.Behaviour, r.BehaviourNotMeasured, r.Notes)
	}
	r = Run(Baseline, shCase(0o644, "sh {file}"), Options{Behaviour: true})
	if r.Behaviour != 0 || r.BehaviourNotMeasured != 0 {
		t.Fatalf("control: behaviour %d not-measured %d notes %v", r.Behaviour, r.BehaviourNotMeasured, r.Notes)
	}
}

func TestExecResultDiff(t *testing.T) {
	ok := &execResult{out: "x"}
	if d, nm := ok.diff(&execResult{note: "tool missing: z"}); d != "" || nm == "" {
		t.Fatalf("after-run failure: diff %q not-measured %q", d, nm)
	}
	if d, nm := ok.diff(&execResult{out: "y"}); d == "" || nm != "" {
		t.Fatalf("output change: diff %q not-measured %q", d, nm)
	}
}

// FullCover is an exact partition, not just a byte-equal reconstruction.
func TestPartitionViolations(t *testing.T) {
	src := []byte("aa")
	sp := func(a, b int) provider.Span { return provider.Span{Start: a, End: b} }
	cases := []struct {
		name   string
		leaves []provider.Span
		bad    bool
	}{
		{"exact", []provider.Span{sp(0, 1), sp(1, 2)}, false},
		{"duplicate leaves reconstruct 'aa' but overlap", []provider.Span{sp(0, 1), sp(0, 1)}, true},
		{"gap", []provider.Span{sp(0, 1)}, true},
		{"out of bounds", []provider.Span{sp(0, 1), sp(1, 3)}, true},
		{"not from zero", []provider.Span{sp(1, 2)}, true},
		{"none for non-empty", nil, true},
	}
	for _, tc := range cases {
		if got := partitionViolations(tc.leaves, src); (len(got) > 0) != tc.bad {
			t.Errorf("%s: violations %v", tc.name, got)
		}
	}
}

func TestFailErr(t *testing.T) {
	var u *provider.UnsupportedCapabilityError
	if err := failErr([]string{"unsupported:Errors"}); !errors.As(err, &u) || u.Missing[0] != "Errors" {
		t.Fatalf("unsupported: %v", err)
	}
	var pe *ProviderError
	if err := failErr([]string{"error:provider: boom"}); !errors.As(err, &pe) {
		t.Fatalf("provider error: %v", err)
	}
	if failErr(nil) != nil {
		t.Fatal("no failures must be nil")
	}
}

// Behaviour verification switched off is "not measured" for every applied
// edit of an exec: fixture, never silently "unchanged".
func TestDisabledBehaviourIsNotMeasured(t *testing.T) {
	r := Run(Baseline, shCase(0o644, "sh {file}"), Options{Behaviour: false})
	if r.OpsApplied != 1 || r.Behaviour != 0 || r.BehaviourNotMeasured != 1 ||
		!strings.Contains(strings.Join(r.Notes, "\n"), "behaviour not measured — disabled") {
		t.Fatalf("applied %d behaviour %d not-measured %d notes %v", r.OpsApplied, r.Behaviour, r.BehaviourNotMeasured, r.Notes)
	}
	r = Run(Baseline, shCase(0o644, ""), Options{Behaviour: false})
	if r.BehaviourNotMeasured != 0 {
		t.Fatalf("no exec: expectation means nothing to measure: %d", r.BehaviourNotMeasured)
	}
}

// A refusal for a different reason than expected writes nothing, so it is
// not record corruption (it used to fall through to the corruption default).
func TestRefusalReasonMismatchIsNotCorruption(t *testing.T) {
	c := corpus.Case{Lang: "bash", Name: "u.sh", Data: []byte("x='open\n# testmap:covers src/a.sh\n"), Mode: 0o644,
		Exp: corpus.Expect{Lang: "bash", Placement: map[string]int{}, Extra: map[string]string{}},
		Edits: []corpus.Op{{Kind: "annotate", Outcome: "refused:not-comment", Text: "annotate",
			Args: map[string]string{"member": "", "source": "src/b.sh", "stamp": "@2026-02-02/bbbbbbbbbb"}}}}
	r := Run(Baseline, c, Options{})
	if r.OpsRefused != 1 || r.RecordCorruption != 0 ||
		!strings.Contains(strings.Join(r.Notes, "\n"), "refused for a different reason; file untouched") {
		t.Fatalf("refused %d corruption %d notes %v", r.OpsRefused, r.RecordCorruption, r.Notes)
	}
}
