package cost

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

// rb builds one run's ledger batch for the fold tests.
type rb struct {
	runID, hc, at string
	all           bool
	invs          []InvocationRow
	res           []ResultRow
}

func newRB(runID, hc, at string) *rb { return &rb{runID: runID, hc: hc, at: at} }

func (b *rb) inv(n int, group string, elapsed, overhead int64, cause string, refused bool) *rb {
	b.invs = append(b.invs, InvocationRow{Row: RowInvocation, RunID: b.runID, Surface: Surface(b.runID), HostClass: b.hc, At: b.at,
		Invocation: n, Group: group, Runner: "r", ElapsedMS: elapsed, OverheadMS: overhead, Cause: cause, Refused: refused, All: b.all})
	return b
}

// result: anchor = clean && pass, like the hook.
func (b *rb) result(n int, id, status string, ms int64, parent, sha string, clean bool) *rb {
	b.res = append(b.res, ResultRow{Row: RowResult, RunID: b.runID, Surface: Surface(b.runID), HostClass: b.hc, At: b.at,
		Invocation: n, Group: "g", ID: id, Parent: parent, Status: status, DurationMS: ms, HeadSHA: sha,
		Clean: clean, Anchor: clean && status == "pass"})
	return b
}

func (b *rb) bytes(t *testing.T) []byte {
	t.Helper()
	for i := range b.invs {
		b.invs[i].All = b.all
	}
	data, err := Batch(b.invs, b.res, RunEndRow{Row: RowRunEnd, RunID: b.runID, HostClass: b.hc, At: b.at, Invocations: len(b.invs), Results: len(b.res)})
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func (b *rb) append(t *testing.T, root string) {
	t.Helper()
	if err := Append(root, b.bytes(t)); err != nil {
		t.Fatal(err)
	}
}

func update(t *testing.T, root string) *UpdateResult {
	t.Helper()
	res, err := Update(root)
	if err != nil {
		t.Fatal(err)
	}
	return res
}

func load(t *testing.T, root, hc string) *Table {
	t.Helper()
	tb, err := Load(root, hc)
	if err != nil {
		t.Fatal(err)
	}
	return tb
}

const at1, at2, at3 = "2026-10-20T10:00:00Z", "2026-10-20T11:00:00Z", "2026-10-20T12:00:00Z"

// Disjoint accounting: a 100 s suite parent with 40 s and 60 s child rows in
// a 105 s invocation counts 105 s, never 205 s; the children keep their own
// statistics and anchors.
func TestFullSuiteDisjoint(t *testing.T) {
	root := t.TempDir()
	b := newRB("full-1", "ci", at1)
	b.all = true
	b.inv(1, "g", 105000, 5000, "", false).
		result(1, "suite.cfg", "pass", 100000, "", "s1", true).
		result(1, "tests/a.sh", "pass", 40000, "suite.cfg", "s1", true).
		result(1, "tests/b.sh", "pass", 60000, "suite.cfg", "s1", true).
		append(t, root)
	update(t, root)
	tb := load(t, root, "ci")
	fs := FullSuiteP95(tb)
	if !fs.OK || fs.MS != 105000 || fs.RunID != "full-1" || fs.Unmeasured != 0 {
		t.Fatalf("full suite %+v, want 105000 from full-1", fs)
	}
	for id, want := range map[string]int64{"tests/a.sh": 40000, "tests/b.sh": 60000} {
		r, _ := tb.ID(id)
		if r.Stat.P95MS != want || r.FullTop != "" || r.LastPass == nil || r.LastPass.RunID != "full-1" {
			t.Errorf("child %s: %+v", id, r)
		}
	}
	if GateTimeoutS(fs.MS) != 600 || GateTimeoutS(400000) != 1200 || GateTimeoutS(200001) != 601 {
		t.Fatalf("gate timeout %d %d %d", GateTimeoutS(fs.MS), GateTimeoutS(400000), GateTimeoutS(200001))
	}
}

// Only a complete, cause-free, unrefused `full-` --all run with a timed
// top-level result becomes the baseline.
func TestFullRunQualification(t *testing.T) {
	root := t.TempDir()
	b := newRB("full-1", "ci", at1)
	b.all = true
	b.inv(1, "g", 10, 1, "", false).result(1, "t.sh", "pass", 9, "", "s", true).append(t, root)
	update(t, root)
	if tb := load(t, root, "ci"); tb.FullRun == nil || tb.FullRun.RunID != "full-1" {
		t.Fatalf("baseline %+v", tb.FullRun)
	}
	for _, c := range []struct {
		name string
		b    *rb
	}{
		{"timeout", newRB("full-2", "ci", at2).inv(1, "g", 9000, 0, "timeout", false).result(1, "t.sh", "timeout", 0, "", "s", false)},
		{"refused", newRB("full-3", "ci", at2).inv(1, "g", 5, 5, "", true).result(1, "t.sh", "refused", 0, "", "s", false)},
		{"all-skip", newRB("full-4", "ci", at2).inv(1, "g", 5, 5, "", false).result(1, "t.sh", "skip", 0, "", "s", true)},
		{"not-all", newRB("full-5", "ci", at2).inv(1, "g", 5, 5, "", false).result(1, "t.sh", "pass", 5, "", "s", true)},
		{"not-full", newRB("test-6", "ci", at2).inv(1, "g", 5, 5, "", false).result(1, "t.sh", "pass", 5, "", "s", true)},
		// Only child rows were timed: the suite parent itself measured nothing.
		{"child-only-timed", newRB("full-7", "ci", at2).inv(1, "g", 5, 5, "", false).result(1, "suite.cfg", "skip", 0, "", "s", true).result(1, "t.sh", "pass", 5, "suite.cfg", "s", true)},
	} {
		c.b.all = c.name != "not-all"
		before := load(t, root, "ci")
		gb, _ := before.Group("g")
		c.b.append(t, root)
		update(t, root)
		tb := load(t, root, "ci")
		if tb.FullRun.RunID != "full-1" {
			t.Errorf("%s: became the baseline: %+v", c.name, tb.FullRun)
		}
		if g, _ := tb.Group("g"); c.name == "refused" && g.Stat.N != gb.Stat.N {
			t.Errorf("refused invocation fed overhead: %d → %d", gb.Stat.N, g.Stat.N)
		}
	}
}

// Membership is recorded apart from timing: a known slow unit that skips in
// the newest full run still counts its earlier p95; a unit never timed counts
// the median fallback and is reported unmeasured.
func TestFullSuiteSkippedMembers(t *testing.T) {
	root := t.TempDir()
	b := newRB("full-1", "ci", at1)
	b.all = true
	b.inv(1, "g", 51100, 100, "", false).result(1, "slow.sh", "pass", 50000, "", "s", true).result(1, "fast.sh", "pass", 1000, "", "s", true).append(t, root)
	b = newRB("full-2", "ci", at2)
	b.all = true
	b.inv(1, "g", 1100, 100, "", false).result(1, "slow.sh", "skip", 0, "", "s", true).result(1, "fast.sh", "pass", 1000, "", "s", true).result(1, "new.sh", "skip", 0, "", "s", true).append(t, root)
	update(t, root)
	fs := FullSuiteP95(load(t, root, "ci"))
	// overhead 100 + slow 50000 + fast 1000 + new: median of {1000, 50000} = 50000
	if !fs.OK || fs.RunID != "full-2" || fs.MS != 100+50000+1000+50000 || fs.Unmeasured != 1 {
		t.Fatalf("full suite %+v", fs)
	}
}

// The unmeasured-id fallback is the median over ids timed as top-level
// units: a suite's 1 ms child rows never set it.
func TestFallbackMedianIgnoresChildOnlyIDs(t *testing.T) {
	root := t.TempDir()
	b := newRB("full-1", "ci", at1)
	b.all = true
	b.inv(1, "g", 100000, 0, "", false).
		result(1, "suite.cfg", "pass", 100000, "", "s", true).
		result(1, "tests/a.sh", "pass", 1, "suite.cfg", "s", true).
		result(1, "tests/b.sh", "pass", 1, "suite.cfg", "s", true).
		result(1, "x.sh", "skip", 0, "", "s", true).
		append(t, root)
	tb := load(t, root, "ci")
	if fs := FullSuiteP95(tb); fs.MS != 200000 || fs.Unmeasured != 1 {
		t.Fatalf("full suite %+v, want 200000 with one unmeasured", fs)
	}
	invs := runner.Group([]runner.Unit{{ID: registry.MustParseID("new.sh"), Runner: "r", BatchNo: true}}, nil)
	if e := Estimate(tb, invs, nil); e.ByKind[""] != 100000 || e.Unknown != 1 {
		t.Fatalf("estimate %+v", e)
	}
}

func TestLastPassAndSameSecond(t *testing.T) {
	root := t.TempDir()
	newRB("test-1", "ci", at1).inv(1, "g", 2, 1, "", false).result(1, "t.sh", "pass", 1, "", "sha1", true).append(t, root)
	newRB("test-2", "ci", at1).inv(1, "g", 2, 1, "", false).result(1, "t.sh", "pass", 1, "", "sha2", true).append(t, root)
	// A non-anchor pass and a fail never move last_pass.
	newRB("test-3", "ci", at2).inv(1, "g", 2, 1, "", false).result(1, "t.sh", "pass", 1, "", "sha3", false).append(t, root)
	newRB("test-4", "ci", at3).inv(1, "g", 2, 1, "", false).result(1, "t.sh", "fail", 1, "", "sha4", true).append(t, root)
	lp, ok := load(t, root, "ci").LastPass("t.sh")
	if !ok || lp != (LastPass{SHA: "sha2", At: at1, RunID: "test-2"}) {
		t.Fatalf("last_pass %+v", lp)
	}
}

func TestFlakeRate(t *testing.T) {
	root := t.TempDir()
	add := func(id, run, status, sha string, clean bool) {
		newRB(run, "ci", at1).inv(1, "g", 2, 1, "", false).result(1, id, status, 1, "", sha, clean).append(t, root)
	}
	add("flip.sh", "test-1", "pass", "s1", true)
	add("flip.sh", "test-2", "fail", "s1", true)
	add("flip.sh", "test-3", "pass", "s1", true)
	add("flip.sh", "test-4", "fail", "s1", false) // not clean: never compared
	add("moves.sh", "test-5", "pass", "s1", true)
	add("moves.sh", "test-6", "fail", "s2", true) // another commit: no pair
	add("broken.sh", "test-7", "fail", "s1", true)
	add("broken.sh", "test-8", "fail", "s1", true)
	add("broken.sh", "test-9", "skip", "s1", true) // skips are not compared
	tb := load(t, root, "ci")
	for id, want := range map[string][2]float64{"flip.sh": {1, 2}, "moves.sh": {0, 0}, "broken.sh": {0, 1}} {
		rate, pairs := tb.FlakeRate(id)
		if rate != want[0] || float64(pairs) != want[1] {
			t.Errorf("%s: rate %v pairs %d, want %v", id, rate, pairs, want)
		}
	}
	if !tb.Flaky("flip.sh", 0.2) || tb.Flaky("broken.sh", 0.2) || tb.Flaky("moves.sh", 0.2) {
		t.Fatal("flaky threshold")
	}
}

// --update folds into sorted output, writes nothing when nothing is new
// (byte-identical), truncates, and Load sees pending runs before any update.
func TestUpdateFoldsTruncatesAndIsIdempotent(t *testing.T) {
	root := t.TempDir()
	newRB("test-1", "ci", at1).inv(1, "g", 5, 2, "", false).result(1, "b.sh", "pass", 2, "", "s", true).result(1, "a.sh", "pass", 1, "", "s", true).append(t, root)
	if tb := load(t, root, "ci"); tb.Pending != 1 || len(tb.IDs) != 2 {
		t.Fatalf("pending fold: %+v", tb)
	}
	res := update(t, root)
	if res.Folded["ci"] != 1 || len(res.Wrote) != 1 || res.Truncated != 4 {
		t.Fatalf("update %+v", res)
	}
	if fi, err := os.Stat(filepath.Join(root, LedgerPath)); err != nil || fi.Size() != 0 {
		t.Fatalf("ledger not truncated: %v %v", fi, err)
	}
	path := filepath.Join(root, TablePath("ci"))
	first, _ := os.ReadFile(path)
	if !bytes.HasPrefix(first, []byte(TableHeader)) || strings.Index(string(first), "id: a.sh") > strings.Index(string(first), "id: b.sh") {
		t.Fatalf("table:\n%s", first)
	}
	if res := update(t, root); len(res.Wrote) != 0 || res.Truncated != 0 {
		t.Fatalf("second update wrote %+v", res)
	}
	if again, _ := os.ReadFile(path); !bytes.Equal(first, again) {
		t.Fatal("second update changed the table")
	}
	if tb := load(t, root, "ci"); tb.Pending != 0 || len(tb.IDs) != 2 {
		t.Fatalf("after update: %+v", tb)
	}
}

// Complete-run framing: a batch torn at a row boundary before its run_end,
// or midway through a result row, is skipped whole — no statistic, anchor
// or baseline — and the next complete run folds normally.
func TestTornBatchIsSkippedWhole(t *testing.T) {
	for name, cut := range map[string]func([]byte) []byte{
		"row-boundary": func(b []byte) []byte { // drop the run_end line
			i := bytes.LastIndexByte(b[:len(b)-1], '\n')
			return b[:i+1]
		},
		"mid-row": func(b []byte) []byte { // cut inside the second result row
			lines := bytes.SplitAfter(b, []byte{'\n'})
			return append(bytes.Join(lines[:2], nil), lines[2][:10]...)
		},
	} {
		t.Run(name, func(t *testing.T) {
			root := t.TempDir()
			torn := newRB("full-1", "ci", at1)
			torn.all = true
			torn.inv(1, "g", 9, 1, "", false).result(1, "a.sh", "pass", 5, "", "s", true).result(1, "b.sh", "pass", 3, "", "s", true)
			if err := os.MkdirAll(filepath.Join(root, runner.StateDir), 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(root, LedgerPath), cut(torn.bytes(t)), 0o644); err != nil {
				t.Fatal(err)
			}
			newRB("test-2", "ci", at2).inv(1, "h", 2, 1, "", false).result(1, "c.sh", "pass", 1, "", "s", true).append(t, root)
			res := update(t, root)
			var runSkips []string
			for _, s := range res.Skipped {
				if s.Run != "" {
					runSkips = append(runSkips, s.Run+":"+s.Reason)
				}
			}
			if strings.Join(runSkips, ",") != "full-1:incomplete" || res.Folded["ci"] != 1 {
				t.Fatalf("update %+v", res)
			}
			tb := load(t, root, "ci")
			if _, ok := tb.ID("a.sh"); ok || tb.FullRun != nil {
				t.Fatalf("torn run leaked: %+v", tb)
			}
			if _, ok := tb.ID("c.sh"); !ok {
				t.Fatal("the complete run after the tear was not folded")
			}
		})
	}
}

func TestCountMismatchSkipsRun(t *testing.T) {
	root := t.TempDir()
	b := newRB("test-1", "ci", at1).inv(1, "g", 2, 1, "", false).result(1, "a.sh", "pass", 1, "", "s", true)
	data, _ := Batch(b.invs, b.res, RunEndRow{Row: RowRunEnd, RunID: "test-1", HostClass: "ci", At: at1, Invocations: 1, Results: 2})
	if err := Append(root, data); err != nil {
		t.Fatal(err)
	}
	if res := update(t, root); len(res.Skipped) != 1 || res.Skipped[0] != (Skipped{Run: "test-1", Reason: SkipCountMismatch}) {
		t.Fatalf("skips %+v", res.Skipped)
	}
}

// An append after a torn line starts on a line of its own.
func TestAppendHealsTornLine(t *testing.T) {
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, runner.StateDir), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, LedgerPath), []byte(`{"row":"result","run_id":"x`), 0o644); err != nil {
		t.Fatal(err)
	}
	newRB("test-1", "ci", at1).inv(1, "g", 2, 1, "", false).result(1, "a.sh", "pass", 1, "", "s", true).append(t, root)
	res := update(t, root)
	if res.Folded["ci"] != 1 || len(res.Skipped) != 1 || res.Skipped[0].Line != 1 {
		t.Fatalf("update %+v", res)
	}
}

// A write failure after one host table stops before the truncation; the
// retry (with a new append in between) folds nothing twice.
func TestUpdateRetryConverges(t *testing.T) {
	root := t.TempDir()
	newRB("test-1", "ci-a", at1).inv(1, "g", 2, 1, "", false).result(1, "a.sh", "pass", 1, "", "s", true).append(t, root)
	newRB("test-2", "ci-b", at1).inv(1, "g", 2, 1, "", false).result(1, "b.sh", "pass", 1, "", "s", true).append(t, root)
	orig := writeFile
	writeFile = func(p string, d []byte) (bool, error) {
		if strings.HasSuffix(p, "ci-b.yaml") {
			return false, errors.New("disk full")
		}
		return orig(p, d)
	}
	_, err := Update(root)
	writeFile = orig
	if err == nil {
		t.Fatal("update did not fail")
	}
	if fi, _ := os.Stat(filepath.Join(root, LedgerPath)); fi.Size() == 0 {
		t.Fatal("ledger truncated after a failed write")
	}
	newRB("test-3", "ci-a", at2).inv(1, "g", 2, 1, "", false).result(1, "a.sh", "pass", 3, "", "s", true).append(t, root)
	if tb := load(t, root, "ci-a"); tb.Pending != 1 {
		t.Fatalf("read after the crash re-folds the marked prefix: pending %d", tb.Pending)
	}
	update(t, root)
	for hc, want := range map[string]int64{"ci-a": 2, "ci-b": 1} {
		r, _ := load(t, root, hc).ID(map[string]string{"ci-a": "a.sh", "ci-b": "b.sh"}[hc])
		if r.Stat.N != want {
			t.Errorf("%s: N %d want %d", hc, r.Stat.N, want)
		}
	}
}

func TestSurfaces(t *testing.T) {
	for id, want := range map[string]string{"test-1": "test", "gate-x": "gate", "full-a": "full", "review-b": "review", "run-2026-1": "other", "fullx": "other"} {
		if got := Surface(id); got != want {
			t.Errorf("%s: %s want %s", id, got, want)
		}
	}
}

func TestReservedHostClasses(t *testing.T) {
	for _, hc := range []string{"policy", "Predictions", "POLICY", "-x", "a/b", ""} {
		if ValidHostClass(hc) == nil {
			t.Errorf("%q accepted", hc)
		}
		if _, err := Load(t.TempDir(), hc); err == nil {
			t.Errorf("Load(%q) accepted", hc)
		}
	}
	if err := ValidHostClass("omg16.local"); err != nil {
		t.Fatal(err)
	}
}

func TestLoadAllDiscriminates(t *testing.T) {
	root := fixture.New(t).Dir
	newRB("test-1", "ci", at1).inv(1, "g", 2, 1, "", false).result(1, "a.sh", "pass", 1, "", "s", true).append(t, root)
	update(t, root)
	if _, err := AppendPrediction(root, map[string]any{"run_id": "full-1"}); err != nil {
		t.Fatal(err)
	}
	if _, err := WritePolicy(root, Policy{SelectedSinceFull: 1}); err != nil {
		t.Fatal(err)
	}
	newRB("test-2", "laptop", at1).inv(1, "g", 2, 1, "", false).result(1, "a.sh", "pass", 1, "", "s", true).append(t, root)
	all, err := LoadAll(root)
	if err != nil || len(all) != 2 || all["ci"] == nil || all["laptop"] == nil || all["laptop"].Pending != 1 {
		t.Fatalf("LoadAll %v %v", all, err)
	}
	src, _ := os.ReadFile(filepath.Join(root, TablePath("ci")))
	if err := os.WriteFile(filepath.Join(root, TablePath("rogue")), src, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadAll(root); err == nil || !strings.Contains(err.Error(), "not a host table") {
		t.Fatalf("rogue table: %v", err)
	}
	// A file that names no host class at all is no host table either, under
	// LoadAll and under Load of its own name; an absent file is an empty table.
	if err := os.WriteFile(filepath.Join(root, TablePath("rogue")), []byte("contract: 1\nunrelated: true\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadAll(root); err == nil || !strings.Contains(err.Error(), "not a host table") {
		t.Fatalf("identity-less table accepted by LoadAll: %v", err)
	}
	if _, err := Load(root, "rogue"); err == nil || !strings.Contains(err.Error(), "not a host table") {
		t.Fatalf("identity-less table accepted by Load: %v", err)
	}
	if tb, err := Load(root, "fresh"); err != nil || tb.HostClass != "fresh" || len(tb.IDs) != 0 {
		t.Fatalf("absent table: %+v %v", tb, err)
	}
}

func TestPredictionsKeep200(t *testing.T) {
	root := fixture.New(t).Dir
	for i := range 205 {
		if _, err := AppendPrediction(root, map[string]any{"run_id": fmt.Sprintf("full-%d", i), "n": i}); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := AppendPrediction(root, map[string]any{"run_id": "full-10", "n": 999}); err != nil {
		t.Fatal(err)
	}
	p, err := ReadPredictions(root)
	if err != nil || len(p.Scored) != 200 {
		t.Fatalf("%v %d", err, len(p.Scored))
	}
	if p.Scored[0]["run_id"] != "full-5" || p.Scored[199]["run_id"] != "full-10" || p.Scored[199]["n"] != 999 {
		t.Fatalf("order: first %v last %v", p.Scored[0], p.Scored[199])
	}
	if _, err := AppendPrediction(root, map[string]any{"n": 1}); err == nil {
		t.Fatal("a prediction without run_id was accepted")
	}
}

func TestPolicyRoundTrip(t *testing.T) {
	root := fixture.New(t).Dir
	if _, found, err := ReadPolicy(root); found || err != nil {
		t.Fatalf("absent: %v %v", found, err)
	}
	p := Policy{
		LastFullRun:       &FullRunRef{RunID: "full-1", At: at1, Task: "t1", SHA: "abc"},
		SelectedSinceFull: 2,
		ApprovedBy:        &Approval{Who: "engine:readiness@gate-1", At: at1, Mode: "auto", Statement: "READINESS_DECISION:ADMISSIBLE"},
	}
	if changed, err := WritePolicy(root, p); err != nil || !changed {
		t.Fatalf("write %v %v", changed, err)
	}
	path := filepath.Join(root, PolicyPath)
	data, _ := os.ReadFile(path)
	if err := os.WriteFile(path, append(data, []byte("future_key: 7\n")...), 0o644); err != nil {
		t.Fatal(err)
	}
	got, found, err := ReadPolicy(root)
	if err != nil || !found || got.Contract != testmap.Contract || got.ApprovedBy.Who != p.ApprovedBy.Who || got.Extra["future_key"] != 7 {
		t.Fatalf("read %+v %v %v", got, found, err)
	}
	if _, err := WritePolicy(root, got); err != nil {
		t.Fatal(err)
	}
	if data, _ := os.ReadFile(path); !strings.Contains(string(data), "future_key: 7") {
		t.Fatalf("extra key dropped:\n%s", data)
	}
	if err := os.WriteFile(path, []byte("contract: 2\nselected_since_full: 0\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	var cm *testmap.ContractMismatchError
	if _, _, err := ReadPolicy(root); !errors.As(err, &cm) {
		t.Fatalf("read newer contract: %v", err)
	}
	if _, err := WritePolicy(root, p); !errors.As(err, &cm) {
		t.Fatalf("write over newer contract: %v", err)
	}
	if l, _ := cm.Line(); l != "CONTRACT_MISMATCH:"+PolicyPath+"|2|1" {
		t.Fatalf("line %q", l)
	}
}

func TestEstimate(t *testing.T) {
	root := t.TempDir()
	newRB("test-1", "ci", at1).inv(1, `["r","",[],"unit",""]`, 10, 4, "", false).
		result(1, "tests/a.sh", "pass", 100, "", "s", true).result(1, "tests/b.sh", "pass", 300, "", "s", true).append(t, root)
	tb := load(t, root, "ci")
	units := []runner.Unit{
		{ID: registry.MustParseID("tests/a.sh"), Runner: "r"},
		{ID: registry.MustParseID("tests/b.sh"), Runner: "r"},
		{ID: registry.MustParseID("tests/new.sh"), Runner: "r"},
		{ID: registry.MustParseID("tests/solo.sh"), Runner: "r", BatchNo: true},
	}
	invs := runner.Group(units, nil)
	kind := func(id registry.ID) string {
		if id.Path == "tests/b.sh" {
			return "integration"
		}
		return "unit"
	}
	got := Estimate(tb, invs, kind)
	// a 100 (unit) + b 300 (integration) + new and solo: median {100,300} = 300
	// each (unit); group overhead 4 + the unknown solo group's median 4.
	if got.ByKind["unit"] != 700 || got.ByKind["integration"] != 300 || got.OverheadMS != 8 || got.TotalMS != 1008 || got.Unknown != 2 || got.UnknownGroups != 1 {
		t.Fatalf("estimate %+v", got)
	}
	if e := Estimate(newTableIndexed("ci"), invs, nil); e.TotalMS != 0 || e.Unknown != 4 {
		t.Fatalf("empty table estimate %+v", e)
	}
}

func newTableIndexed(hc string) *Table {
	t := newTable(hc)
	_ = t.index()
	return t
}
