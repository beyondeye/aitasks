package registry

import (
	"reflect"
	"testing"
)

// adoptionCheckRepo is cleanRepo (the stamped edge tests/test_a.sh ->
// src/a.sh, scanned into _scanned.yaml) plus a second stamped annotation
// edge -> src/b.sh the scan has not persisted yet, and adoption tables
// covering every M2.6 report.
func adoptionCheckRepo(t *testing.T) (string, Inputs) {
	t.Helper()
	root, in := cleanRepo(t)
	in.Annotations = fakeAnns{{Path: "tests/test_a.sh", Units: []UnitAnnotation{{Covers: []Cover{cover("src/a.sh", 2), cover("src/b.sh", 3)}}}}}
	writeTree(t, root, map[string]string{
		SeededPath: "contract: 1\nseeds:\n" +
			"  - " + seedYAML("tests/test_a.sh", "src/a.sh") + "\n" + // shadowed (persisted and live stamp)
			"  - " + seedYAML("tests/test_a.sh", "src/b.sh") + "\n" + // shadowed by the live stamp only
			"  - " + seedYAML("tests/test_a.sh", "src/d.sh") + "\n" + // live
			"  - " + seedYAML("tests/test_r.sh", "src/r.sh") + "\n" + // rejected
			"  - {test: tests/test_p.sh, covers: src/p.sh, origin: [convention], confidence: 0.4, proposed_at: 2026-10-02," +
			" evidence: {agent_review: {verdict: drives, by: 'agent:x', run: r1, packet_sha: p1, test_blob: tb1}}, verdict: drives}\n",
		AdoptedPath: "contract: 1\nadopted:\n" +
			"  - {test: tests/test_a.sh, source: src/a.sh, origin: [static:invocation], adopted_at: 2026-10-01, by: 'agent:x'}\n" +
			"  - {test: tests/test_a.sh, source: src/c.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto}\n",
		OnboardPath: "contract: 1\nrejections: [{test: tests/test_r.sh, source: src/r.sh, reason: fixture}]\n",
	})
	return root, in
}

// The load-rule reports judge the live edges (a stamp an annotation gained
// since the last scan already shadows its seed), are Info (never failing)
// and the counts are summary lines outside the CHECK: totals.
func TestAdoptionCheckRules(t *testing.T) {
	root, in := adoptionCheckRepo(t)
	for _, strict := range []bool{false, true} {
		res := runCheck(t, root, in, strict)
		for rule, want := range map[string][]string{
			RuleSeedShadowed:     {"SEED_SHADOWED:tests/test_a.sh|src/a.sh", "SEED_SHADOWED:tests/test_a.sh|src/b.sh"},
			RuleSeedRejected:     {"SEED_REJECTED:tests/test_r.sh|src/r.sh"},
			RuleAdoptedOrphan:    {"ADOPTED_ORPHAN:tests/test_a.sh|src/c.sh"},
			RuleReviewUnrecorded: {"REVIEW_UNRECORDED:tests/test_p.sh|src/p.sh|tb1|agent:x"},
		} {
			if got := only(t, res, rule); !reflect.DeepEqual(got, want) {
				t.Errorf("strict=%v %s: %v, want %v", strict, rule, got, want)
			}
		}
		for _, f := range res.Findings {
			if f.Fail && (f.Rule == RuleSeedShadowed || f.Rule == RuleSeedRejected || f.Rule == RuleAdoptedOrphan || f.Rule == RuleReviewUnrecorded) {
				t.Errorf("%s fails", f.Rule)
			}
		}
		if got := lines(t, res.Summary); !reflect.DeepEqual(got, []string{"SEEDED:2", "ADOPTED:1|human 0|agent 1|auto 0"}) {
			t.Errorf("summary %v", got)
		}
		for _, f := range res.Findings {
			if f.Rule == SummarySeeded || f.Rule == SummaryAdopted {
				t.Error("a summary line was counted as a finding")
			}
		}
	}
	// Load alone judges the persisted edges: the src/b.sh stamp is not in
	// _scanned.yaml yet, so its seed still reads as live there.
	reg, err := Load(root)
	if err != nil {
		t.Fatal(err)
	}
	if a := AdoptionOf(reg); len(a.Shadowed) != 1 || len(a.Seeds) != 3 || len(a.Orphans) != 1 {
		t.Errorf("persisted classification: shadowed %d seeds %d orphans %d", len(a.Shadowed), len(a.Seeds), len(a.Orphans))
	}
}

// A registry with no adoption files still prints both summary lines.
func TestAdoptionSummaryWithoutTables(t *testing.T) {
	root, in := cleanRepo(t)
	res := runCheck(t, root, in, false)
	if got := lines(t, res.Summary); !reflect.DeepEqual(got, []string{"SEEDED:0", "ADOPTED:0|human 0|agent 0|auto 0"}) {
		t.Errorf("summary %v", got)
	}
}
