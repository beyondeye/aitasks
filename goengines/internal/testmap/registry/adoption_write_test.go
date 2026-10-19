package registry

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
)

var bgctx = context.Background()

func conf(c float64) *float64 { return &c }

func seedRow(test, covers string) SeedRow {
	return SeedRow{Test: test, Covers: covers, Origin: []string{"static:invocation"}, Confidence: conf(0.9), ProposedAt: "2026-10-02"}
}

// txRepo is a registry directory for write tests that do not exercise the
// lock.
func txRepo(t *testing.T, files map[string]string) string {
	t.Helper()
	noLock(t)
	root := t.TempDir()
	all := map[string]string{ConfigPath: "contract: 1\n"}
	for p, c := range files {
		all[p] = c
	}
	writeTree(t, root, all)
	return root
}

func openTx(t *testing.T, root string, r Route) *AdoptionTx {
	t.Helper()
	tx, err := OpenAdoption(bgctx, root, r)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { tx.Close() })
	return tx
}

func commit(t *testing.T, tx *AdoptionTx) []string {
	t.Helper()
	wrote, err := tx.Commit()
	if err != nil {
		t.Fatal(err)
	}
	return wrote
}

func readF(t *testing.T, root, p string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(root, p))
	if err != nil {
		return "<absent>"
	}
	return string(b)
}

// writeSeam records the files each commit writes (relative to root) and fails
// a write to a path with the suffix failOn.
func writeSeam(t *testing.T, root string) (calls *[]string, failOn *string) {
	t.Helper()
	var c []string
	var f string
	old := writeFile
	writeFile = func(p string, data []byte) (bool, error) {
		rel, _ := filepath.Rel(root, p)
		rel = filepath.ToSlash(rel)
		c = append(c, rel)
		if f != "" && strings.HasSuffix(rel, f) {
			return false, errors.New("disk full")
		}
		return old(p, data)
	}
	t.Cleanup(func() { writeFile = old })
	return &c, &f
}

func reload(t *testing.T, root string) *Adoption {
	t.Helper()
	reg, err := Load(root)
	if err != nil {
		t.Fatal(err)
	}
	return AdoptionOf(reg)
}

// The routing table, pinned: each route performs exactly these ops.
func TestRouteTable(t *testing.T) {
	want := map[Route][]Op{
		RouteOnboardSeed:        {OpSeedPut},
		RouteAttributePropose:   {OpSeedPut},
		RouteAdoptAgentVerdicts: {OpRecordVerdict},
		RouteCalibrate:          {OpCalibrationAdd},
		RouteAdoptClass:         {OpSeedRemove, OpAdoptedPut},
		RouteAdoptRow:           {OpSeedRemove, OpAdoptedDelete},
		RouteAnnotateAuthor:     {OpAdoptedPut},
		RouteOnboardReject:      {OpSeedRemove, OpRejectionAdd},
		RouteClassifyPropose:    {OpKindProposalAdd},
		RouteRestamp:            {OpAdoptedPut, OpAdoptedRefresh, OpAdoptedDelete, OpRestamps},
	}
	if !reflect.DeepEqual(want, routeOps) || len(AllRoutes) != len(want) {
		t.Fatalf("routing table drifted:\n%v", routeOps)
	}
}

// Every op outside its route is ADOPTION_ROUTE; inside it, never.
func TestRouteRefusesOpsOutsideIt(t *testing.T) {
	calls := map[Op]func(*AdoptionTx) error{
		OpSeedPut:    func(tx *AdoptionTx) error { _, err := tx.PutSeed(seedRow("tests/t.sh", "src/a.sh")); return err },
		OpSeedRemove: func(tx *AdoptionTx) error { _, err := tx.RemoveSeed("tests/t.sh", "src/a.sh"); return err },
		OpAdoptedPut: func(tx *AdoptionTx) error {
			return tx.PutAdopted(AdoptedRow{Test: "tests/t.sh", Source: "src/a.sh", Origin: []string{"coverage"}, AdoptedAt: "2026-10-02", By: "auto"})
		},
		OpAdoptedRefresh: func(tx *AdoptionTx) error {
			_, err := tx.RefreshAdopted("tests/t.sh", "src/a.sh", "2026-10-02/0123456789")
			return err
		},
		OpAdoptedDelete: func(tx *AdoptionTx) error { _, err := tx.DeleteAdopted("tests/t.sh", "src/a.sh"); return err },
		OpRejectionAdd: func(tx *AdoptionTx) error {
			return tx.AddRejection(Rejection{Test: "tests/t.sh", Source: "src/a.sh", Reason: "r"})
		},
		OpKindProposalAdd: func(tx *AdoptionTx) error {
			return tx.AddKindProposal(KindProposal{Test: "tests/t.sh", Kind: "e2e", Reason: "r"})
		},
		OpCalibrationAdd: func(tx *AdoptionTx) error { return tx.AddCalibration(Calibration{Run: "c1", Agree: 1}) },
		OpRecordVerdict: func(tx *AdoptionTx) error {
			return tx.RecordVerdict(VerdictRecord{Test: "tests/t.sh", Covers: "src/a.sh",
				Review: SeedReview{Verdict: VerdictDrives, By: "agent:x", Run: "r", PacketSHA: "p", TestBlob: "tb"}})
		},
		OpRestamps: func(tx *AdoptionTx) error { return tx.ApplyRestamps(PhasePost, By{Kind: ByAuto}, true, nil) },
	}
	if len(calls) != len(AllOps) {
		t.Fatal("an op has no probe")
	}
	for _, r := range AllRoutes {
		for _, op := range AllOps {
			root := txRepo(t, map[string]string{SeededPath: "seeds:\n  - " + seedYAML("tests/t.sh", "src/a.sh") + "\n"})
			tx := openTx(t, root, r)
			err := calls[op](tx)
			var re *RouteError
			if got := errors.As(err, &re); got == RouteAllows(r, op) {
				t.Errorf("%s / %s: allowed=%v, err %v", r, op, RouteAllows(r, op), err)
			}
			if re != nil {
				if l, _ := re.Line(); l != "ADOPTION_ROUTE:"+string(r)+"|"+string(op) {
					t.Errorf("line %q", l)
				}
			}
			tx.Close()
		}
	}
}

func seedYAML(test, covers string) string {
	return "{test: " + test + ", covers: " + covers + ", origin: [static:invocation], confidence: 0.9, proposed_at: 2026-10-02}"
}

// Each op applied twice leaves the files exactly as applying it once.
func TestOpsAreIdempotent(t *testing.T) {
	adoptRow := AdoptedRow{Test: "tests/t.sh", Source: "src/a.sh", Origin: []string{"coverage"}, AdoptedAt: "2026-10-02", By: "auto"}
	cases := []struct {
		route Route
		do    func(*AdoptionTx) error
	}{
		{RouteOnboardSeed, func(tx *AdoptionTx) error { _, err := tx.PutSeed(seedRow("tests/n.sh", "src/n.sh")); return err }},
		{RouteOnboardReject, func(tx *AdoptionTx) error {
			if _, err := tx.RemoveSeed("tests/t.sh", "src/a.sh"); err != nil {
				return err
			}
			return tx.AddRejection(Rejection{Test: "tests/t.sh", Source: "src/a.sh", Reason: "r", By: "human:p@example.invalid"})
		}},
		{RouteAdoptClass, func(tx *AdoptionTx) error {
			if _, err := tx.RemoveSeed("tests/t.sh", "src/a.sh"); err != nil {
				return err
			}
			return tx.PutAdopted(adoptRow)
		}},
		{RouteClassifyPropose, func(tx *AdoptionTx) error {
			return tx.AddKindProposal(KindProposal{Test: "tests/t.sh", Kind: "e2e", Reason: "r"})
		}},
		{RouteCalibrate, func(tx *AdoptionTx) error { return tx.AddCalibration(Calibration{Run: "c1", Agree: 3, Ratio: 1}) }},
		{RouteAdoptAgentVerdicts, func(tx *AdoptionTx) error {
			return tx.RecordVerdict(VerdictRecord{Test: "tests/t.sh", Covers: "src/a.sh",
				Review: SeedReview{Verdict: VerdictDrives, By: "agent:x", Run: "r", PacketSHA: "p", TestBlob: "tb"}})
		}},
	}
	for _, c := range cases {
		snap := func(root string) string {
			return readF(t, root, SeededPath) + readF(t, root, AdoptedPath) + readF(t, root, OnboardPath)
		}
		files := map[string]string{SeededPath: "contract: 1\nseeds:\n  - " + seedYAML("tests/t.sh", "src/a.sh") + "\n"}
		once, twice := txRepo(t, files), txRepo(t, files)
		for _, root := range []string{once, twice} {
			n := 1
			if root == twice {
				n = 2
			}
			for i := 0; i < n; i++ {
				tx := openTx(t, root, c.route)
				if err := c.do(tx); err != nil {
					t.Fatalf("%s: %v", c.route, err)
				}
				commit(t, tx)
			}
		}
		if snap(once) != snap(twice) {
			t.Errorf("%s: twice differs from once:\n%s\n---\n%s", c.route, snap(once), snap(twice))
		}
	}
}

// A fresh file renders canonically, sorted; a table that ends empty never
// creates a file.
func TestFreshRenderAndNoEmptyFile(t *testing.T) {
	root := txRepo(t, nil)
	tx := openTx(t, root, RouteOnboardSeed)
	for _, s := range []SeedRow{seedRow("tests/z.sh", "src/z.sh"), seedRow("tests/a.sh", "src/b.sh"), seedRow("tests/a.sh", "src/a.sh")} {
		if _, err := tx.PutSeed(s); err != nil {
			t.Fatal(err)
		}
	}
	if w := commit(t, tx); !reflect.DeepEqual(w, []string{SeededPath}) {
		t.Fatalf("wrote %v", w)
	}
	golden(t, "adoption/seeded_fresh.golden", []byte(readF(t, root, SeededPath)))

	tx = openTx(t, root, RouteRestamp)
	if err := tx.ApplyRestamps(PhaseIntent, By{Kind: ByAgent, Value: "claudecode/opus5_5"}, true,
		[]RestampEdge{{Test: "tests/a.sh#M", Source: "src/a.sh", After: "2026-10-19/0123456789", Origin: "scanner:from-body"}}); err != nil {
		t.Fatal(err)
	}
	commit(t, tx)
	golden(t, "adoption/adopted_fresh.golden", []byte(readF(t, root, AdoptedPath)))

	empty := txRepo(t, nil)
	tx = openTx(t, empty, RouteOnboardReject)
	if _, err := tx.RemoveSeed("tests/t.sh", "src/a.sh"); err != nil {
		t.Fatal(err)
	}
	if w := commit(t, tx); len(w) != 0 || readF(t, empty, SeededPath) != "<absent>" || readF(t, empty, OnboardPath) != "<absent>" {
		t.Errorf("an empty table created a file: %v", w)
	}
}

// A seed for a rejected pair is never re-proposed.
func TestPutSeedSkipsRejectedPair(t *testing.T) {
	root := txRepo(t, map[string]string{OnboardPath: "rejections: [{test: tests/t.sh, source: src/a.sh, reason: r}]\n"})
	tx := openTx(t, root, RouteOnboardSeed)
	if put, err := tx.PutSeed(seedRow("tests/t.sh", "src/a.sh")); err != nil || put {
		t.Fatalf("put %v err %v", put, err)
	}
	if w := commit(t, tx); len(w) != 0 {
		t.Errorf("wrote %v", w)
	}
}

// Cooperating writers are serialised by the lock: the second writer reads
// the first one's committed state, so no update is lost. The control runs
// the same interleaving with the lock removed: the second writer then read
// the old state, and only the snapshot check stops it from overwriting.
func TestAdoptionLockSerialises(t *testing.T) {
	interleave := func(t *testing.T, locked bool) (bErr error, seeds string) {
		r := fixture.New(t)
		root := r.Dir
		writeTree(t, root, map[string]string{ConfigPath: "contract: 1\n"})
		if !locked {
			noLock(t)
		}
		opened := make(chan Route, 2)
		oldAfter := afterOpen
		afterOpen = func(rt Route) { opened <- rt }
		t.Cleanup(func() { afterOpen = oldAfter })

		a := openTx(t, root, RouteOnboardSeed)
		<-opened
		proceed := make(chan struct{})
		done := make(chan error, 1)
		go func() {
			b, err := OpenAdoption(bgctx, root, RouteAttributePropose)
			if err != nil {
				done <- err
				return
			}
			defer b.Close()
			<-proceed
			if _, err := b.PutSeed(seedRow("tests/y.sh", "src/y.sh")); err != nil {
				done <- err
				return
			}
			_, err = b.Commit()
			done <- err
		}()
		if locked {
			select {
			case <-opened:
				t.Fatal("the second writer read the files while the first held the lock")
			default:
			}
		} else {
			<-opened // the control: B has read the old state before A commits
		}
		if _, err := a.PutSeed(seedRow("tests/x.sh", "src/x.sh")); err != nil {
			t.Fatal(err)
		}
		commit(t, a)
		close(proceed)
		return <-done, readF(t, root, SeededPath)
	}
	t.Run("locked", func(t *testing.T) {
		err, seeds := interleave(t, true)
		if err != nil || !strings.Contains(seeds, "tests/x.sh") || !strings.Contains(seeds, "tests/y.sh") {
			t.Fatalf("err %v, seeded.yaml:\n%s", err, seeds)
		}
	})
	t.Run("control-without-lock", func(t *testing.T) {
		err, seeds := interleave(t, false)
		var ce *AdoptionConflictError
		if !errors.As(err, &ce) || strings.Contains(seeds, "tests/y.sh") || !strings.Contains(seeds, "tests/x.sh") {
			t.Fatalf("without the lock the second writer must fail, not succeed: err %v\n%s", err, seeds)
		}
	})
}

// A hand edit since Open is ADOPTION_CONFLICT and nothing is written — even
// when only the last file in the route's order changed.
func TestHandEditConflictWritesNothing(t *testing.T) {
	root := txRepo(t, map[string]string{
		SeededPath:  "contract: 1\nseeds:\n  - " + seedYAML("tests/t.sh", "src/a.sh") + "\n",
		AdoptedPath: "contract: 1\nadopted:\n  - {test: tests/t.sh, source: src/a.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto}\n",
	})
	tx := openTx(t, root, RouteAdoptRow)
	tx.DeleteAdopted("tests/t.sh", "src/a.sh")
	tx.RemoveSeed("tests/t.sh", "src/a.sh")
	adopted := readF(t, root, AdoptedPath)
	hand := "contract: 1\nseeds: []\n# edited by hand\n"
	writeTree(t, root, map[string]string{SeededPath: hand})
	calls, _ := writeSeam(t, root)
	_, err := tx.Commit()
	var ce *AdoptionConflictError
	if !errors.As(err, &ce) || ce.Path != SeededPath || len(*calls) != 0 {
		t.Fatalf("err %v, writes %v", err, *calls)
	}
	if l, _ := ce.Line(); l != "ADOPTION_CONFLICT:"+SeededPath || ce.ExitCode() != 75 {
		t.Errorf("line %q", l)
	}
	if readF(t, root, AdoptedPath) != adopted || readF(t, root, SeededPath) != hand {
		t.Error("a file was written")
	}
}

// Every multi-file route writes in its order; a carrier-preservation write
// goes first.
func TestRouteWriteOrder(t *testing.T) {
	parked := "contract: 1\nseeds:\n  - {test: tests/t.sh, covers: src/a.sh, origin: [convention], confidence: 0.4, proposed_at: 2026-10-02," +
		" evidence: {agent_review: {verdict: drives, by: 'agent:x', run: r1, packet_sha: p1, test_blob: tb1}}, verdict: drives}\n" +
		"  - " + seedYAML("tests/t.sh", "src/b.sh") + "\n"
	adoptedCarrier := "contract: 1\nadopted:\n  - {test: tests/t.sh, source: src/a.sh, origin: [static:invocation, agent:review], adopted_at: 2026-10-01, by: 'agent:x', run: r7, packet_sha: p7, test_blob: tb7}\n"
	cases := []struct {
		name  string
		files map[string]string
		route Route
		do    func(*AdoptionTx) error
		want  []string
	}{
		{"reject", map[string]string{SeededPath: parked}, RouteOnboardReject, func(tx *AdoptionTx) error {
			tx.RemoveSeed("tests/t.sh", "src/b.sh")
			return tx.AddRejection(Rejection{Test: "tests/t.sh", Source: "src/b.sh", Reason: "r"})
		}, []string{OnboardPath, SeededPath}},
		{"reject-with-preservation", map[string]string{SeededPath: parked}, RouteOnboardReject, func(tx *AdoptionTx) error {
			tx.RemoveSeed("tests/t.sh", "src/a.sh")
			return tx.AddRejection(Rejection{Test: "tests/t.sh", Source: "src/a.sh", Reason: "r"})
		}, []string{OnboardPath, SeededPath}},
		{"verdicts", map[string]string{SeededPath: parked}, RouteAdoptAgentVerdicts, func(tx *AdoptionTx) error {
			return tx.RecordVerdict(VerdictRecord{Test: "tests/t.sh", Covers: "src/b.sh", Review: SeedReview{Verdict: VerdictVerifies, By: "agent:x", Run: "r2", PacketSHA: "p2", TestBlob: "tb2"},
				Adopt: &AdoptedRow{Test: "tests/t.sh", Source: "src/b.sh", Origin: []string{"agent:review"}, AdoptedAt: "2026-10-19", By: "agent:x", Run: "r2", PacketSHA: "p2", TestBlob: "tb2"}})
		}, []string{AdoptedPath, SeededPath, OnboardPath}},
		{"verdicts-with-preservation", map[string]string{SeededPath: parked}, RouteAdoptAgentVerdicts, func(tx *AdoptionTx) error {
			return tx.RecordVerdict(VerdictRecord{Test: "tests/t.sh", Covers: "src/a.sh", Review: SeedReview{Verdict: VerdictVerifies, By: "agent:x", Run: "r2", PacketSHA: "p2", TestBlob: "tb2"},
				Adopt: &AdoptedRow{Test: "tests/t.sh", Source: "src/a.sh", Origin: []string{"agent:review"}, AdoptedAt: "2026-10-19", By: "agent:x", Run: "r2", PacketSHA: "p2", TestBlob: "tb2"}})
		}, []string{OnboardPath, AdoptedPath, SeededPath, OnboardPath}},
		{"class", map[string]string{SeededPath: parked}, RouteAdoptClass, func(tx *AdoptionTx) error {
			tx.RemoveSeed("tests/t.sh", "src/b.sh")
			return tx.PutAdopted(AdoptedRow{Test: "tests/t.sh", Source: "src/b.sh", Origin: []string{"coverage"}, AdoptedAt: "2026-10-19", By: "auto"})
		}, []string{AdoptedPath, SeededPath}},
		{"row-with-preservation", map[string]string{SeededPath: parked, AdoptedPath: adoptedCarrier}, RouteAdoptRow, func(tx *AdoptionTx) error {
			tx.DeleteAdopted("tests/t.sh", "src/a.sh")
			_, err := tx.RemoveSeed("tests/t.sh", "src/b.sh")
			return err
		}, []string{OnboardPath, AdoptedPath, SeededPath}},
		{"restamp-with-preservation", map[string]string{AdoptedPath: adoptedCarrier}, RouteRestamp, func(tx *AdoptionTx) error {
			return tx.ApplyRestamps(PhasePost, By{Kind: ByHuman, Value: "p@example.invalid"}, true,
				[]RestampEdge{{Test: "tests/t.sh", Source: "src/a.sh", Before: "2026-10-01/0123456789", After: "2026-10-01/0123456789"}})
		}, []string{OnboardPath, AdoptedPath}},
	}
	for _, c := range cases {
		root := txRepo(t, c.files)
		tx := openTx(t, root, c.route)
		if err := c.do(tx); err != nil {
			t.Fatalf("%s: %v", c.name, err)
		}
		calls, _ := writeSeam(t, root)
		commit(t, tx)
		if !reflect.DeepEqual(*calls, c.want) {
			t.Errorf("%s: wrote %v, want %v", c.name, *calls, c.want)
		}
	}
}

// reject failing on its last file: the rejection is recorded, the seed is
// still in the file but reads as rejected everywhere, and re-running the
// reject converges.
func TestPartialRejectConverges(t *testing.T) {
	root := txRepo(t, map[string]string{SeededPath: "contract: 1\nseeds:\n  - " + seedYAML("tests/t.sh", "src/a.sh") + "\n"})
	reject := func() error {
		tx := openTx(t, root, RouteOnboardReject)
		tx.RemoveSeed("tests/t.sh", "src/a.sh")
		if err := tx.AddRejection(Rejection{Test: "tests/t.sh", Source: "src/a.sh", Reason: "fixture"}); err != nil {
			t.Fatal(err)
		}
		_, err := tx.Commit()
		return err
	}
	_, failOn := writeSeam(t, root)
	*failOn = "seeded.yaml"
	err := reject()
	var pe *AdoptionPartialError
	if !errors.As(err, &pe) {
		t.Fatalf("err %v", err)
	}
	if l, _ := pe.Line(); l != "ADOPTION_PARTIAL:"+SeededPath+"|"+OnboardPath {
		t.Errorf("line %q", l)
	}
	a := reload(t, root)
	if len(a.RawSeeds) != 1 || len(a.Seeds) != 0 || len(a.RejectedSeeds) != 1 || len(a.Onboard.Rejections) != 1 {
		t.Fatalf("partial state: %+v", a)
	}
	if seeded, _ := a.Counts(); seeded != 0 {
		t.Error("a rejected seed is counted")
	}
	*failOn = ""
	if err := reject(); err != nil {
		t.Fatal(err)
	}
	a = reload(t, root)
	if len(a.RawSeeds) != 0 || len(a.Onboard.Rejections) != 1 {
		t.Fatalf("after re-run: %+v", a)
	}
}

const memoScanned = "contract: 1\nunits:\n  - test: tests/t.sh\n    covers:\n" +
	"      - source: src/a.sh\n        line: 2\n        stamped_at: \"2026-10-19\"\n        stamped_blob: \"0123456789\"\n"

func verifiesRecord(covers, run string) VerdictRecord {
	return VerdictRecord{Test: "tests/t.sh", Covers: covers,
		Review: SeedReview{Verdict: VerdictVerifies, By: "agent:x", Run: run, PacketSHA: "p-" + run, TestBlob: "tb1"},
		Adopt: &AdoptedRow{Test: "tests/t.sh", Source: covers, Origin: []string{"static:invocation", "agent:review"}, AdoptedAt: "2026-10-19",
			By: "agent:x", Run: run, PacketSHA: "p-" + run, TestBlob: "tb1", Stamp: "2026-10-19/0123456789"}}
}

func drivesRecord(covers, blob string) VerdictRecord {
	return VerdictRecord{Test: "tests/t.sh", Covers: covers,
		Review: SeedReview{Verdict: VerdictDrives, By: "agent:x", Run: "r-" + blob, PacketSHA: "p-" + blob, TestBlob: blob}}
}

func record(t *testing.T, root string, v VerdictRecord) error {
	t.Helper()
	tx := openTx(t, root, RouteAdoptAgentVerdicts)
	if err := tx.RecordVerdict(v); err != nil {
		t.Fatal(err)
	}
	_, err := tx.Commit()
	return err
}

func memoRepo(t *testing.T) string {
	return txRepo(t, map[string]string{
		ScannedPath: memoScanned,
		SeededPath: "contract: 1\nseeds:\n  - " + seedYAML("tests/t.sh", "src/a.sh") + "\n  - " + seedYAML("tests/t.sh", "src/b.sh") +
			"\n  - " + seedYAML("tests/t.sh", "src/c.sh") + "\n",
	})
}

// The review record survives a memo write that fails, and the next commit on
// the route restores the memo; eligibility is judged by NeedsReview on a
// reloaded registry, never by replaying ops.
func TestMemoRecovery(t *testing.T) {
	t.Run("verifies-memo-fails", func(t *testing.T) {
		root := memoRepo(t)
		_, failOn := writeSeam(t, root)
		*failOn = "onboard.yaml"
		var pe *AdoptionPartialError
		if err := record(t, root, verifiesRecord("src/a.sh", "r1")); !errors.As(err, &pe) {
			t.Fatalf("err %v", err)
		}
		a := reload(t, root)
		if _, ok := a.AdoptedFor(MustParseID("tests/t.sh"), "src/a.sh"); !ok || a.NeedsReview("tests/t.sh", "src/a.sh", "tb1", "agent:x") {
			t.Fatalf("after a failed memo: %+v", a)
		}
		if len(a.Onboard.Reviews) != 0 || len(a.Unrecorded()) != 1 || !a.Reviewed("tests/t.sh", "src/a.sh", "tb1", "agent:x") {
			t.Fatalf("the record must be derived from the adopted row: %+v", a.Reviews())
		}
		*failOn = ""
		if err := record(t, root, drivesRecord("src/b.sh", "tb9")); err != nil {
			t.Fatal(err)
		}
		a = reload(t, root)
		if len(a.Onboard.Reviews) != 2 || len(a.Unrecorded()) != 0 {
			t.Fatalf("re-entry must back-fill the memo: %+v", a.Onboard.Reviews)
		}
	})
	t.Run("verifies-seed-removal-fails", func(t *testing.T) {
		root := memoRepo(t)
		_, failOn := writeSeam(t, root)
		*failOn = "seeded.yaml"
		var pe *AdoptionPartialError
		if err := record(t, root, verifiesRecord("src/a.sh", "r1")); !errors.As(err, &pe) {
			t.Fatalf("err %v", err)
		}
		a := reload(t, root)
		if len(a.Shadowed) != 1 || a.NeedsReview("tests/t.sh", "src/a.sh", "tb1", "agent:x") || !a.Reviewed("tests/t.sh", "src/a.sh", "tb1", "agent:x") {
			t.Fatalf("shadowed seed: %+v", a)
		}
	})
	t.Run("drives-memo-fails", func(t *testing.T) {
		root := memoRepo(t)
		_, failOn := writeSeam(t, root)
		*failOn = "onboard.yaml"
		var pe *AdoptionPartialError
		if err := record(t, root, drivesRecord("src/b.sh", "tb1")); !errors.As(err, &pe) {
			t.Fatalf("err %v", err)
		}
		a := reload(t, root)
		if a.NeedsReview("tests/t.sh", "src/b.sh", "tb1", "agent:x") {
			t.Error("the parked seed's own record must keep it from being re-read")
		}
		if !a.NeedsReview("tests/t.sh", "src/b.sh", "tb2", "agent:x") {
			t.Error("new test bytes must make it eligible")
		}
		*failOn = ""
		if err := record(t, root, drivesRecord("src/c.sh", "tb1")); err != nil {
			t.Fatal(err)
		}
		if a := reload(t, root); len(a.Unrecorded()) != 0 || len(a.Onboard.Reviews) != 2 {
			t.Fatalf("re-entry: %+v", a.Onboard.Reviews)
		}
	})
	t.Run("drives-seed-write-fails", func(t *testing.T) {
		root := memoRepo(t)
		_, failOn := writeSeam(t, root)
		*failOn = "seeded.yaml"
		var pe *AdoptionPartialError
		if err := record(t, root, drivesRecord("src/b.sh", "tb1")); err == nil || errors.As(err, &pe) {
			t.Fatalf("the first write failed, so nothing was written: %v", err)
		}
		if a := reload(t, root); !a.NeedsReview("tests/t.sh", "src/b.sh", "tb1", "agent:x") {
			t.Error("nothing happened, so the pair stays a candidate")
		}
		if readF(t, root, OnboardPath) != "<absent>" {
			t.Error("the memo was written before the verdict")
		}
	})
	t.Run("negative-control", func(t *testing.T) {
		if a := reload(t, memoRepo(t)); !a.NeedsReview("tests/t.sh", "src/b.sh", "tb1", "agent:x") {
			t.Error("a live seed with no review anywhere needs review")
		}
	})
	t.Run("replay-data-required", func(t *testing.T) {
		root := memoRepo(t)
		tx := openTx(t, root, RouteAdoptAgentVerdicts)
		v := verifiesRecord("src/a.sh", "r1")
		v.Review.PacketSHA = ""
		err := tx.RecordVerdict(v)
		var re *RouteError
		if !errors.As(err, &re) || re.Detail != "replay-data" {
			t.Fatalf("err %v", err)
		}
		v = verifiesRecord("src/a.sh", "r1")
		v.Adopt.TestBlob = "other"
		if err := tx.RecordVerdict(v); !errors.As(err, &re) || re.Detail != "replay-data" {
			t.Fatalf("mismatched adopted row: %v", err)
		}
		if w := commit(t, tx); len(w) != 0 {
			t.Errorf("a refused verdict wrote %v", w)
		}
	})
}

// A review record outlives its carrier: every route that destroys or changes
// the carrier first writes the record to the memo.
func TestCarrierPreservation(t *testing.T) {
	parked := "contract: 1\nseeds:\n  - {test: tests/t.sh, covers: src/a.sh, origin: [convention], confidence: 0.4, proposed_at: 2026-10-02," +
		" evidence: {agent_review: {verdict: drives, by: 'agent:x', run: r1, packet_sha: p1, test_blob: tb1}}, verdict: drives}\n"
	carrier := Review{Test: "tests/t.sh", Source: "src/a.sh", Verdict: VerdictDrives, TestBlob: "tb1", PacketSHA: "p1", Run: "r1", By: "agent:x"}
	inMemo := func(a *Adoption, r Review) bool {
		for _, m := range a.Onboard.Reviews {
			if m.Key() == r.Key() {
				return true
			}
		}
		return false
	}
	t.Run("seed-replaced", func(t *testing.T) {
		root := txRepo(t, map[string]string{SeededPath: parked})
		tx := openTx(t, root, RouteOnboardSeed)
		tx.PutSeed(seedRow("tests/t.sh", "src/a.sh"))
		calls, _ := writeSeam(t, root)
		commit(t, tx)
		a := reload(t, root)
		if !reflect.DeepEqual(*calls, []string{OnboardPath, SeededPath}) || !inMemo(a, carrier) || a.RawSeeds[0].Evidence.AgentReview != nil {
			t.Fatalf("writes %v, %+v", *calls, a)
		}
	})
	t.Run("newer-review-replaces-older", func(t *testing.T) {
		root := txRepo(t, map[string]string{SeededPath: parked})
		if err := record(t, root, drivesRecord("src/a.sh", "tb2")); err != nil {
			t.Fatal(err)
		}
		a := reload(t, root)
		if !inMemo(a, carrier) || !a.Reviewed("tests/t.sh", "src/a.sh", "tb2", "agent:x") {
			t.Fatalf("%+v", a.Reviews())
		}
	})
	t.Run("reject-removes", func(t *testing.T) {
		root := txRepo(t, map[string]string{SeededPath: parked})
		tx := openTx(t, root, RouteOnboardReject)
		tx.RemoveSeed("tests/t.sh", "src/a.sh")
		tx.AddRejection(Rejection{Test: "tests/t.sh", Source: "src/a.sh", Reason: "r"})
		commit(t, tx)
		if a := reload(t, root); !inMemo(a, carrier) || len(a.Onboard.Rejections) != 1 {
			t.Fatalf("%+v", a.Onboard)
		}
	})
	t.Run("adopt-row-deletes", func(t *testing.T) {
		root := txRepo(t, map[string]string{AdoptedPath: "contract: 1\nadopted:\n  - {test: tests/t.sh, source: src/a.sh, origin: [agent:review], adopted_at: 2026-10-01, by: 'agent:x', run: r1, packet_sha: p1, test_blob: tb1}\n"})
		tx := openTx(t, root, RouteAdoptRow)
		tx.DeleteAdopted("tests/t.sh", "src/a.sh")
		commit(t, tx)
		want := carrier
		want.Verdict = VerdictVerifies
		if a := reload(t, root); !inMemo(a, want) || len(a.RawAdopted) != 0 {
			t.Fatalf("%+v", a.Onboard.Reviews)
		}
	})
	t.Run("read-edit-put", func(t *testing.T) {
		// Editing a row fetched from the open write must not rewrite the
		// original record carrier preservation compares against.
		root := txRepo(t, map[string]string{SeededPath: parked})
		tx := openTx(t, root, RouteOnboardSeed)
		row := tx.Seeds()[0]
		row.Evidence.AgentReview.TestBlob = "tb2"
		if tx.Seeds()[0].Evidence.AgentReview.TestBlob != "tb1" {
			t.Fatal("Seeds() aliases the open write's rows")
		}
		if _, err := tx.PutSeed(row); err != nil {
			t.Fatal(err)
		}
		row.Evidence.AgentReview.TestBlob = "tb3" // after the put: must change nothing
		commit(t, tx)
		a := reload(t, root)
		if !inMemo(a, carrier) || !a.Reviewed("tests/t.sh", "src/a.sh", "tb2", "agent:x") || a.Reviewed("tests/t.sh", "src/a.sh", "tb3", "agent:x") {
			t.Fatalf("%+v", a.Reviews())
		}
	})
	t.Run("preservation-fails-refuses-the-deletion", func(t *testing.T) {
		root := txRepo(t, map[string]string{SeededPath: parked})
		seeded := readF(t, root, SeededPath)
		tx := openTx(t, root, RouteOnboardSeed)
		tx.PutSeed(seedRow("tests/t.sh", "src/a.sh"))
		_, failOn := writeSeam(t, root)
		*failOn = "onboard.yaml"
		var pe *AdoptionPartialError
		if _, err := tx.Commit(); err == nil || errors.As(err, &pe) {
			t.Fatalf("err %v", err)
		}
		if readF(t, root, SeededPath) != seeded {
			t.Error("the carrier was replaced although its record was not preserved")
		}
	})
	t.Run("negative-control-already-memoized", func(t *testing.T) {
		onboard := "contract: 1\nreviews:\n  - {test: tests/t.sh, source: src/a.sh, verdict: drives, test_blob: tb1, packet_sha: p1, run: r1, by: 'agent:x'}\n"
		root := txRepo(t, map[string]string{SeededPath: parked, OnboardPath: onboard})
		tx := openTx(t, root, RouteOnboardSeed)
		tx.PutSeed(seedRow("tests/t.sh", "src/a.sh"))
		calls, _ := writeSeam(t, root)
		commit(t, tx)
		if !reflect.DeepEqual(*calls, []string{SeededPath}) || readF(t, root, OnboardPath) != onboard {
			t.Fatalf("writes %v", *calls)
		}
	})
}

// Rows cross the open write's boundary as deep copies, nested unknown fields
// included: editing a row after PutSeed, or a row returned by Seeds() /
// Onboard(), persists nothing.
func TestRowCopiesAreDeep(t *testing.T) {
	root := txRepo(t, nil)
	tx := openTx(t, root, RouteOnboardSeed)
	row := seedRow("tests/t.sh", "src/a.sh")
	row.Extra = map[string]any{"future_field": map[string]any{"keep": "original", "list": []any{"a"}}}
	if _, err := tx.PutSeed(row); err != nil {
		t.Fatal(err)
	}
	row.Extra["future_field"].(map[string]any)["keep"] = "after-put"
	got := tx.Seeds()[0]
	got.Extra["future_field"].(map[string]any)["keep"] = "via-getter"
	got.Extra["future_field"].(map[string]any)["list"].([]any)[0] = "changed"
	commit(t, tx)
	text := readF(t, root, SeededPath)
	if !strings.Contains(text, "keep: original") || !strings.Contains(text, "- a") {
		t.Fatalf("an edit outside the write was persisted:\n%s", text)
	}

	// Caller-built typed containers are detached too, at the setter and at
	// the getter.
	root = txRepo(t, nil)
	tx = openTx(t, root, RouteOnboardSeed)
	typedMap, typedList := map[string]string{"keep": "original"}, []string{"a"}
	row = seedRow("tests/t.sh", "src/a.sh")
	row.Extra = map[string]any{"m": typedMap, "l": typedList}
	if _, err := tx.PutSeed(row); err != nil {
		t.Fatal(err)
	}
	typedMap["keep"], typedList[0] = "after-put", "after-put"
	got = tx.Seeds()[0]
	if m, ok := got.Extra["m"].(map[string]any); !ok {
		t.Fatalf("typed map not normalised: %T", got.Extra["m"])
	} else {
		m["keep"] = "via-getter"
	}
	if l, ok := got.Extra["l"].([]any); !ok {
		t.Fatalf("typed list not normalised: %T", got.Extra["l"])
	} else {
		l[0] = "via-getter"
	}
	commit(t, tx)
	if text := readF(t, root, SeededPath); !strings.Contains(text, "keep: original") || !strings.Contains(text, "- a") ||
		strings.Contains(text, "after-put") || strings.Contains(text, "via-getter") {
		t.Fatalf("a typed container stayed aliased:\n%s", text)
	}
	tx = openTx(t, root, RouteOnboardSeed)
	bad := seedRow("tests/u.sh", "src/u.sh")
	bad.Extra = map[string]any{"f": func() {}}
	if _, err := tx.PutSeed(bad); err == nil {
		t.Error("an unencodable unknown field was stored")
	}
	tx.Close()

	root = txRepo(t, map[string]string{OnboardPath: "rejections: [{test: tests/q.sh, source: src/q.sh, reason: r, note: {keep: original}}]\n"})
	tx = openTx(t, root, RouteOnboardReject)
	tx.Onboard().Rejections[0].Extra["note"].(map[string]any)["keep"] = "via-getter"
	tx.AddRejection(Rejection{Test: "tests/r.sh", Source: "src/r.sh", Reason: "x"})
	commit(t, tx)
	if text := readF(t, root, OnboardPath); !strings.Contains(text, "keep: original") {
		t.Fatalf("onboard getter aliases the open write:\n%s", text)
	}
}
