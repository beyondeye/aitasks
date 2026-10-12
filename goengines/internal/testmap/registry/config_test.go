package registry

import (
	"errors"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap"
)

func TestConfigDefaults(t *testing.T) {
	root := t.TempDir()
	cfg, err := LoadConfig(root) // no aitestmap/ at all
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(cfg, Defaults()) {
		t.Fatalf("absent config.yaml is not Defaults():\n%+v", cfg)
	}
	d := Defaults()
	golden := []struct {
		key  string
		got  any
		want any
	}{
		{"unit_covers_max", d.UnitCoversMax, 8},
		{"suite_budget_s", d.SuiteBudgetS, 600},
		{"bootstrap_until", d.BootstrapUntil, ""},
		{"require_stamp", d.RequireStamp, false},
		{"broad_review_days", d.BroadReviewDays, 0},
		{"concurrency", d.Concurrency, "serial"},
		{"broad_after_unit", d.BroadAfterUnit, true},
		{"device_policy", d.DevicePolicy, "filter_by_resource"},
		{"host_class", d.HostClassName, ""},
		{"flake_threshold", d.FlakeThreshold, 0.2},
		{"symbol_scanners", d.SymbolScanners, []string{}},
		{"run_gate_admission.approved_by", d.RunGateAdmission.ApprovedBy, (*Approval)(nil)},
		{"completion", d.Completion, Completion{Mode: "auto", FullRunEvery: FullRunEvery{Tasks: 5, SelectionRatioAbove: 0.60, Days: 7}, Deferred: "run", OnEmptySelection: "skip", EngineAbsent: "error"}},
		{"agent_review", d.AgentReview, AgentReview{Enabled: true, Confidence: 0.90, AcceptMin: 0.85, CalibrationMin: 30, Batch: 20, PacketLines: 120, MaxPairsPerRun: 400, Author: true}},
		{"readiness", d.Readiness, Readiness{MinScoredFullRuns: 20, MaxFalseNegatives: 0, RequireOpaqueProofs: true, MinFullRunsSinceMapChange: 3}},
		{"conventions", d.Conventions, []Convention{}},
		{"helper_roots", d.HelperRoots, []string{"tests/lib/**", "**/testing/**", "**/testdata/**"}},
		{"helper_fanin", d.HelperFanin, 0.05},
		{"exclude", d.Exclude, []string{}},
		{"docs", d.Docs, []string{}},
		{"notes", d.Notes, ""},
		{"broad_threshold_s", d.BroadThresholdS, 60},
	}
	for _, g := range golden {
		if !reflect.DeepEqual(g.got, g.want) {
			t.Errorf("%s default = %#v, want %#v", g.key, g.got, g.want)
		}
	}
}

func TestParseConfigOverridesAndKeepsDefaults(t *testing.T) {
	cfg, err := ParseConfig([]byte(`contract: 1
bootstrap_until: 2027-01-10
require_stamp: true
completion:
  mode: full
agent_review:
  measured_confidence: 0.91
exclude: ["tests/golden/**"]
notes: |
  line one
  line two
some_future_key: {anything: 1}
`))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.BootstrapUntil != "2027-01-10" || !cfg.RequireStamp || cfg.Completion.Mode != "full" {
		t.Fatalf("overrides lost: %+v", cfg)
	}
	if cfg.Completion.Deferred != "run" || cfg.Completion.FullRunEvery.Tasks != 5 {
		t.Fatalf("sibling defaults inside a set block lost: %+v", cfg.Completion)
	}
	if cfg.AgentReview.MeasuredConfidence == nil || *cfg.AgentReview.MeasuredConfidence != 0.91 || cfg.AgentReview.Batch != 20 {
		t.Fatalf("agent_review: %+v", cfg.AgentReview)
	}
	if !cfg.Excluded("tests/golden/a/b.md") || cfg.Excluded("tests/test_a.sh") {
		t.Fatal("Excluded")
	}
}

func TestParseConfigRefusals(t *testing.T) {
	for _, tc := range []struct{ yaml, want string }{
		{"concurrency: lots", "concurrency"},
		{"completion: {mode: sometimes}", "completion.mode"},
		{"completion: {deferred: drop}", "completion.deferred"},
		{"completion: {on_empty_selection: none}", "completion.on_empty_selection"},
		{"completion: {engine_absent: ignore}", "completion.engine_absent"},
		{"device_policy: ''", "device_policy"},
		{"unit_covers_max: -1", "unit_covers_max"},
		{"flake_threshold: 1.5", "flake_threshold"},
		{"agent_review: {accept_min: -0.1}", "agent_review.accept_min"},
		{"agent_review: {measured_confidence: 2}", "measured_confidence"},
		{"completion: {full_run_every: {selection_ratio_above: 3}}", "selection_ratio_above"},
		{"bootstrap_until: next week", "bootstrap_until"},
		{"bootstrap_until: 2027-13-40", "bootstrap_until"},
		{"exclude: ['a/[']", "exclude"},
		{"conventions: [{test: x}]", "conventions"},
		{"notes: |\n" + strings.Repeat("  n\n", MaxNotesLines+1), "notes"},
		{"unit_covers_max: many", "line 1"}, // a YAML type error names the line
		{"a: 1\na: 2", "a"},
		{"- not\n- a mapping", "mapping"},
	} {
		_, err := ParseConfig([]byte(tc.yaml))
		var ie *InvalidError
		if !errors.As(err, &ie) || ie.Path != ConfigPath || !strings.Contains(ie.Error(), tc.want) {
			t.Errorf("%q: err %v, want *InvalidError mentioning %q", tc.yaml, err, tc.want)
			continue
		}
		l, lerr := ie.Line()
		if lerr != nil || !strings.HasPrefix(l, "REGISTRY_INVALID:"+ConfigPath+"|") || ie.ExitCode() != 3 {
			t.Errorf("%q: line %q (%v), exit %d", tc.yaml, l, lerr, ie.ExitCode())
		}
	}
	// exactly the ceiling is accepted
	if _, err := ParseConfig([]byte("notes: |\n" + strings.Repeat("  n\n", MaxNotesLines))); err != nil {
		t.Fatalf("%d notes lines refused: %v", MaxNotesLines, err)
	}
}

func TestParseConfigNewerContract(t *testing.T) {
	_, err := ParseConfig([]byte("contract: 2\n"))
	var cm *testmap.ContractMismatchError
	if !errors.As(err, &cm) || cm.Path != ConfigPath || cm.File != 2 {
		t.Fatalf("err %v", err)
	}
}

func TestPastBootstrap(t *testing.T) {
	day := func(s string) time.Time { tm, _ := time.Parse(time.DateOnly, s); return tm }
	cfg := Defaults()
	if !cfg.PastBootstrap(day("2026-01-01")) {
		t.Fatal("no bootstrap_until must mean no bootstrap window")
	}
	cfg.BootstrapUntil = "2026-06-30"
	for _, tc := range []struct {
		today string
		want  bool
	}{{"2026-06-29", false}, {"2026-06-30", false}, {"2026-07-01", true}} {
		if got := cfg.PastBootstrap(day(tc.today)); got != tc.want {
			t.Errorf("%s: %v", tc.today, got)
		}
	}
}
