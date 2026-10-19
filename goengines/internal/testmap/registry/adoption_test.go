package registry

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap"
)

// noLock replaces the adoption lock for tests that do not exercise it (the
// lock needs a git repository; it is pinned in adoption_write_test.go).
func noLock(t testing.TB) {
	t.Helper()
	old := lockAdoption
	lockAdoption = func(context.Context, string) (func() error, error) { return func() error { return nil }, nil }
	t.Cleanup(func() { lockAdoption = old })
}

const fixtureScanned = "contract: 1\nunits:\n" +
	"  - test: tests/t.sh\n    covers:\n" +
	"      - source: src/a.sh\n        line: 2\n        stamped_at: \"2026-10-01\"\n        stamped_blob: \"0123456789\"\n" +
	"      - source: src/b.sh\n        line: 3\n" +
	"  - test: tests/u.sh\n    covers:\n" +
	"      - source: src/c.sh\n        line: 2\n        stamped_at: \"2026-10-01\"\n        stamped_blob: \"abcdef0123\"\n"

const loadSeeded = "contract: 1\nseeds:\n" +
	"  - {test: tests/t.sh, covers: src/a.sh, origin: [static:invocation], confidence: 0.9, proposed_at: 2026-10-02}\n" +
	"  - {test: tests/t.sh, covers: src/b.sh, origin: [convention], confidence: 0.4, proposed_at: 2026-10-02," +
	" evidence: {convention: 'tests/t.sh->src/b.sh', agent_review: {verdict: drives, by: 'agent:x', run: r1, packet_sha: p1, test_blob: tb1}}, verdict: drives}\n" +
	"  - {test: tests/r.sh, covers: src/r.sh, origin: [cochange], confidence: 0.3, proposed_at: 2026-10-02}\n" +
	"  - {test: tests/z.sh, covers: src/z.sh, origin: [static:import], confidence: 0.8, proposed_at: 2026-10-02, future_field: kept}\n"

const loadAdopted = "contract: 1\nadopted:\n" +
	"  - {test: tests/u.sh, source: src/c.sh, origin: [static:invocation, agent:review], confidence: 0.99, adopted_at: 2026-10-03," +
	" by: 'agent:claudecode/opus5_5', run: review-1, packet_sha: pk, test_blob: tb2, stamp: 2026-10-01/abcdef0123}\n" +
	"  - {test: tests/t.sh, source: src/b.sh, origin: [coverage], confidence: 0.95, adopted_at: 2026-10-03, by: auto}\n" +
	"  - {test: tests/t.sh, source: src/a.sh, origin: [static:import], adopted_at: 2026-10-03, by: 'human:p@example.invalid'}\n"

const loadOnboard = "contract: 1\ntask: 42\nlevel: 1\nphases: {seed: {status: done}}\n" +
	"rejections:\n" +
	"  - {test: tests/r.sh, source: src/r.sh, reason: fixture only}\n" +
	"  - {test: tests/q.sh, source: src/q.sh, reason: helper, by: 'human:p@example.invalid'}\n" +
	"reviews:\n" +
	"  - {test: tests/t.sh, source: src/a.sh, verdict: unsure, test_blob: tb0, packet_sha: p0, run: r0, by: 'agent:x'}\n" +
	"kind_proposals:\n  - {test: tests/e2e.sh, kind: e2e, reason: 'resource:tmux'}\n" +
	"calibration:\n  - {run: c1, agree: 9, disagree: 1, ratio: 0.9}\n"

// adoptionRepo writes the load fixture: annotation edges (one stamped and one
// unstamped for tests/t.sh), a hand file sorting after seeded.yaml, and the
// three adoption files.
func adoptionRepo(t testing.TB) string {
	t.Helper()
	root := t.TempDir()
	writeTree(t, root, map[string]string{
		ConfigPath:               "contract: 1\n",
		ScannedPath:              fixtureScanned,
		RegistryDir + "/zz.yaml": "contract: 1\nowns: [\"src/**\"]\nedges: [{test: tests/z.sh, covers: src/z.sh}]\n",
		SeededPath:               loadSeeded,
		AdoptedPath:              loadAdopted,
		OnboardPath:              loadOnboard,
		"src/a.sh":               "a\n",
		"src/b.sh":               "b\n",
		"src/c.sh":               "c\n",
		"tests/t.sh":             "#!/bin/sh\n",
	})
	return root
}

func dumpJSON(t testing.TB, v any) []byte {
	t.Helper()
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	return append(b, '\n')
}

// The two adoption-table merges into the loaded registry, the shadow rule
// (a stamped edge shadows; an unstamped annotation edge and a declared edge
// from a hand file loaded after seeded.yaml do not), the rejected-seed rule,
// orphans, absent-by-is-human on a rejection, the counts and the derived
// review records.
func TestAdoptionLoadGolden(t *testing.T) {
	reg, err := Load(adoptionRepo(t))
	if err != nil {
		t.Fatal(err)
	}
	a := AdoptionOf(reg)
	seeded, counts := a.Counts()
	type actor struct {
		Test     string `json:"test"`
		By       string `json:"by"`
		Kind     ByKind `json:"kind"`
		Recorded bool   `json:"recorded"`
	}
	var actors []actor
	for _, r := range a.Onboard.Rejections {
		b, rec := r.Actor()
		actors = append(actors, actor{r.Test, b.String(), b.Kind, rec})
	}
	golden(t, "adoption/load.golden", dumpJSON(t, map[string]any{
		"tables":     a,
		"seeded":     seeded,
		"adopted":    counts,
		"rejectors":  actors,
		"reviews":    a.Reviews(),
		"unrecorded": a.Unrecorded(),
		"summary":    AdoptionSummary(a),
	}))
	if !a.NeedsReview("tests/z.sh", "src/z.sh", "tb", "agent:x") {
		t.Error("a live seed nobody read needs review")
	}
	if a.NeedsReview("tests/t.sh", "src/b.sh", "tb1", "agent:x") {
		t.Error("a parked seed with that reader's record for these test bytes was re-selected")
	}
	if !a.NeedsReview("tests/t.sh", "src/b.sh", "tb-new", "agent:x") {
		t.Error("new test bytes must make a parked seed eligible again")
	}
	if a.NeedsReview("tests/r.sh", "src/r.sh", "tb", "agent:x") || a.NeedsReview("tests/t.sh", "src/a.sh", "tb", "agent:y") {
		t.Error("a rejected or shadowed seed is never a candidate")
	}
	if r, ok := a.AdoptedFor(MustParseID("tests/u.sh"), "src/c.sh"); !ok || r.By != "agent:claudecode/opus5_5" {
		t.Errorf("AdoptedFor: %+v %v", r, ok)
	}
	if _, ok := a.AdoptedFor(MustParseID("tests/t.sh"), "src/b.sh"); ok {
		t.Error("an orphan row is not the provenance of a stamped edge")
	}
}

// Absent files read as empty tables; a registry with no registry/ directory
// still reads onboard.yaml.
func TestAdoptionAbsentAndOnboardOnly(t *testing.T) {
	root := t.TempDir()
	writeTree(t, root, map[string]string{ConfigPath: "contract: 1\n", OnboardPath: loadOnboard})
	reg, err := Load(root)
	if err != nil {
		t.Fatal(err)
	}
	a := AdoptionOf(reg)
	if len(a.Seeds)+len(a.Adopted)+len(a.Orphans) != 0 || len(a.Onboard.Rejections) != 2 {
		t.Fatalf("%+v", a)
	}
	if got := AdoptionSummary(a); fmt.Sprint(got) != "[[SEEDED 0] [ADOPTED 0 human 0 agent 0 auto 0]]" {
		t.Errorf("summary %v", got)
	}
}

func TestAdoptionLoadRefusals(t *testing.T) {
	for _, tc := range []struct{ file, body, want string }{
		{SeededPath, "contract: 1\nqueue: []\n", "unknown key queue"},
		{SeededPath, "seeds: [{test: 'a@v', covers: b, origin: [x], confidence: 1, proposed_at: 2026-10-01}]\n", "no variant fragment"},
		{SeededPath, "seeds: [{test: a, covers: ../b, origin: [x], confidence: 1, proposed_at: 2026-10-01}]\n", "covers"},
		{SeededPath, "seeds: [{test: a, covers: b, confidence: 1, proposed_at: 2026-10-01}]\n", "origin is required"},
		{SeededPath, "seeds: [{test: a, covers: b, origin: [x], proposed_at: 2026-10-01}]\n", "confidence is required"},
		{SeededPath, "seeds: [{test: a, covers: b, origin: [x], confidence: 1.5, proposed_at: 2026-10-01}]\n", "outside [0,1]"},
		{SeededPath, "seeds: [{test: a, covers: b, origin: [x], confidence: 1, proposed_at: soon}]\n", "proposed_at"},
		{SeededPath, "seeds: [{test: a, covers: b, origin: [x], confidence: 1, proposed_at: 2026-10-01, verdict: maybe}]\n", "invalid verdict"},
		{SeededPath, "seeds: [{test: a, covers: b, origin: [x], confidence: 1, proposed_at: 2026-10-01, evidence: {agent_review: {verdict: drives, by: 'agent:x'}}}]\n", "run, packet_sha and test_blob"},
		{SeededPath, "seeds: [{test: a, covers: b, origin: [x], confidence: 1, proposed_at: 2026-10-01}, {test: a, covers: b, origin: [y], confidence: 1, proposed_at: 2026-10-01}]\n", "duplicate pair"},
		{SeededPath, "seeds: [{test: a, covers: b, origin: [x], confidence: .nan, proposed_at: 2026-10-01}]\n", "outside [0,1]"},
		{AdoptedPath, "adopted: [{test: a, source: b, origin: [x], confidence: .nan, adopted_at: 2026-10-01, by: auto}]\n", "outside [0,1]"},
		{OnboardPath, "calibration: [{run: c1, agree: 1, disagree: 0, ratio: .nan}]\n", "not a number"},
		{AdoptedPath, "adopted: [{test: a, source: b, origin: [x], adopted_at: 2026-10-01}]\n", "invalid by"},
		{AdoptedPath, "adopted: [{test: a, source: b, origin: [x], adopted_at: 2026-10-01, by: 'robot:x'}]\n", "invalid by"},
		{AdoptedPath, "adopted: [{test: a, source: b, origin: [x], adopted_at: 2026-10-01, by: auto, stamp: today}]\n", "stamp"},
		{AdoptedPath, "adopted: [{test: a, source: b, origin: [x], adopted_at: 2026-10-01, by: auto}, {test: a, source: b, origin: [x], adopted_at: 2026-10-01, by: auto}]\n", "duplicate pair"},
		{OnboardPath, "rejections: [{test: a, source: b, reason: r, by: 'someone'}]\n", "invalid by"},
		{OnboardPath, "reviews: [{test: a, source: b, verdict: ok, test_blob: t, packet_sha: p, run: r, by: auto}]\n", "invalid verdict"},
		{OnboardPath, "reviews: [{test: a, source: b, verdict: drives, by: auto}]\n", "required"},
		{OnboardPath, "kind_proposals: [{test: a, kind: huge, reason: r}]\n", "invalid kind"},
		{OnboardPath, "calibration: [{agree: 1, disagree: 0, ratio: 1}]\n", "run is required"},
	} {
		root := t.TempDir()
		writeTree(t, root, map[string]string{ConfigPath: "contract: 1\n", tc.file: tc.body})
		_, err := Load(root)
		var ie *InvalidError
		if !errors.As(err, &ie) || ie.Path != tc.file || !strings.Contains(ie.Reason, tc.want) {
			t.Errorf("%s %q: %v, want REGISTRY_INVALID containing %q", tc.file, tc.body, err, tc.want)
		}
	}
}

// Each of the three files carries its own contract; a newer one is refused by
// the loader and by the writer (which never overwrites it).
func TestAdoptionContractRefusal(t *testing.T) {
	noLock(t)
	for _, p := range []string{SeededPath, AdoptedPath, OnboardPath} {
		root := t.TempDir()
		writeTree(t, root, map[string]string{ConfigPath: "contract: 1\n", p: "contract: 2\n"})
		var cm *testmap.ContractMismatchError
		if _, err := Load(root); !errors.As(err, &cm) {
			t.Errorf("load %s: %v", p, err)
		}
		if _, err := OpenAdoption(context.Background(), root, RouteRestamp); !errors.As(err, &cm) {
			t.Errorf("open %s: %v", p, err)
		}
		if b, _ := os.ReadFile(filepath.Join(root, p)); string(b) != "contract: 2\n" {
			t.Errorf("%s rewritten", p)
		}
	}
}

func TestParseBy(t *testing.T) {
	for in, kind := range map[string]ByKind{"human:a@b.c": ByHuman, "agent:claudecode/opus5_5": ByAgent, "auto": ByAuto} {
		if b, err := ParseBy(in); err != nil || b.Kind != kind || b.String() != in {
			t.Errorf("%s: %+v %v", in, b, err)
		}
	}
	for _, bad := range []string{"", "human:", "robot:x", "agent:a|b", "agent:a b", "human", "auto:x"} {
		if _, err := ParseBy(bad); err == nil {
			t.Errorf("%q accepted", bad)
		}
	}
}

// The by: merge — the provenance rule of the stamping verbs over every
// reachable (phase × existing row × actor × state × prior stamp) cell.
func TestByMergeGolden(t *testing.T) {
	noLock(t)
	const before, after = "2026-10-01/0123456789", "2026-10-19/9876543210"
	type actorCase struct {
		name  string
		by    By
		known bool
	}
	actors := []actorCase{
		{"human", By{Kind: ByHuman, Value: "p@example.invalid"}, true},
		{"agent", By{Kind: ByAgent, Value: "x"}, true},
		{"auto", By{Kind: ByAuto}, true},
		{"unspecified", By{}, false},
	}
	type edgeCase struct{ state, before, after string }
	edges := []edgeCase{
		{"added", "", after},
		{"restamped", "", after}, // a first stamp of an existing unstamped covers line
		{"restamped", before, after},
		{"current", before, before},
	}
	existing := []string{"none", "human:p@example.invalid", "agent:old", "auto"}
	var out strings.Builder
	for _, phase := range []RestampPhase{PhaseIntent, PhasePost} {
		pname := map[RestampPhase]string{PhaseIntent: "intent", PhasePost: "post"}[phase]
		for _, ex := range existing {
			for _, ac := range actors {
				for _, ec := range edges {
					if phase == PhaseIntent && ec.state == "current" {
						continue // a current edge is not written, so it never reaches the intent phase
					}
					root := t.TempDir()
					files := map[string]string{ConfigPath: "contract: 1\n"}
					if ex != "none" {
						files[AdoptedPath] = "contract: 1\nadopted:\n  - {test: tests/t.sh, source: src/a.sh, origin: [coverage], adopted_at: 2026-09-01, by: '" + ex + "', stamp: " + before + "}\n"
					}
					writeTree(t, root, files)
					tx, err := OpenAdoption(context.Background(), root, RouteRestamp)
					if err != nil {
						t.Fatal(err)
					}
					if err := tx.ApplyRestamps(phase, ac.by, ac.known, []RestampEdge{{Test: "tests/t.sh", Source: "src/a.sh", Before: ec.before, After: ec.after, Origin: "scanner:from-body"}}); err != nil {
						t.Fatal(err)
					}
					if _, err := tx.Commit(); err != nil {
						t.Fatal(err)
					}
					reg, err := Load(root)
					if err != nil {
						t.Fatal(err)
					}
					result := "no row"
					if rows := AdoptionOf(reg).RawAdopted; len(rows) == 1 {
						r := rows[0]
						result = fmt.Sprintf("by=%s origin=%s adopted_at=%s stamp=%s", r.By, strings.Join(r.Origin, "+"), r.AdoptedAt, r.Stamp)
					}
					before := "zero"
					if ec.before != "" {
						before = "stamped"
					}
					fmt.Fprintf(&out, "%-6s existing=%-23s actor=%-11s state=%-9s before=%-7s -> %s\n", pname, ex, ac.name, ec.state, before, result)
				}
			}
		}
	}
	golden(t, "adoption/by_merge.golden", []byte(out.String()))
}
