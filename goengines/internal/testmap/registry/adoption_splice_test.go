package registry

import (
	"errors"
	"reflect"
	"strings"
	"testing"
)

// A noncanonical unrelated row: a head comment, an inline comment, double
// quoted values, fields out of schema order and an unknown field.
const noncanonicalRow = "  # kept: hand-reviewed provenance\n" +
	"  - source: \"src/keep.sh\"   # inline\n" +
	"    by: \"auto\"\n" +
	"    test: \"tests/keep.sh\"\n" +
	"    future_field: {nested: true}\n" +
	"    origin: [\"coverage\"]\n" +
	"    adopted_at: \"2026-09-01\"\n"

const targetRow = "  - {test: tests/t.sh, source: src/a.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto, stamp: 2026-10-01/0123456789}\n"

func spliceFixture(rowsBefore, rowsAfter string) string {
	return "# provenance of machine-adopted edges\ncontract: 1\n\nadopted:\n" + rowsBefore + targetRow + rowsAfter + "\n# trailing note\n"
}

func applyRestamp(t *testing.T, root string, by By, before, after string) {
	t.Helper()
	tx := openTx(t, root, RouteRestamp)
	if err := tx.ApplyRestamps(PhasePost, by, true, []RestampEdge{{Test: "tests/t.sh", Source: "src/a.sh", Before: before, After: after}}); err != nil {
		t.Fatal(err)
	}
	commit(t, tx)
}

// Refreshing and then deleting a row leaves every untouched block row — and
// every byte outside the touched row — exactly as it was, whether the
// unrelated row comes before or after the target.
func TestSplicePreservesUntouchedBlockRows(t *testing.T) {
	for _, order := range []struct{ before, after string }{{noncanonicalRow, ""}, {"", noncanonicalRow}} {
		orig := spliceFixture(order.before, order.after)
		root := txRepo(t, map[string]string{AdoptedPath: orig})
		applyRestamp(t, root, By{Kind: ByAuto}, "2026-10-01/0123456789", "2026-10-19/9876543210")
		got := readF(t, root, AdoptedPath)
		touched := "  - test: tests/t.sh\n    source: src/a.sh\n    origin: [coverage]\n    adopted_at: \"2026-10-01\"\n    by: auto\n    stamp: 2026-10-19/9876543210\n"
		if want := strings.Replace(orig, targetRow, touched, 1); got != want {
			t.Fatalf("refresh:\n%s\nwant\n%s", got, want)
		}
		applyRestamp(t, root, By{Kind: ByHuman, Value: "p@example.invalid"}, "2026-10-19/9876543210", "2026-10-19/9876543210")
		if want := strings.Replace(orig, targetRow, "", 1); readF(t, root, AdoptedPath) != want {
			t.Fatalf("delete:\n%s\nwant\n%s", readF(t, root, AdoptedPath), want)
		}
		if a := reload(t, root); len(a.RawAdopted) != 1 || a.RawAdopted[0].Extra["future_field"] == nil {
			t.Fatalf("unrelated row: %+v", a.RawAdopted)
		}
	}
}

// A new row lands in sorted position; its neighbours keep their bytes.
func TestSpliceInsertsSorted(t *testing.T) {
	orig := "contract: 1\nadopted:\n" +
		"  - {test: tests/a.sh, source: src/a.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto}\n" +
		"  # second\n  - {test: tests/z.sh, source: src/z.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto}\n"
	root := txRepo(t, map[string]string{AdoptedPath: orig})
	tx := openTx(t, root, RouteAnnotateAuthor)
	if err := tx.PutAdopted(AdoptedRow{Test: "tests/m.sh", Source: "src/m.sh", Origin: []string{"agent:author"}, AdoptedAt: "2026-10-19", By: "agent:x"}); err != nil {
		t.Fatal(err)
	}
	commit(t, tx)
	want := "contract: 1\nadopted:\n" +
		"  - {test: tests/a.sh, source: src/a.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto}\n" +
		"  - test: tests/m.sh\n    source: src/m.sh\n    origin: ['agent:author']\n    adopted_at: \"2026-10-19\"\n    by: agent:x\n" +
		"  # second\n  - {test: tests/z.sh, source: src/z.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto}\n"
	if got := readF(t, root, AdoptedPath); got != want {
		t.Fatalf("got\n%s\nwant\n%s", got, want)
	}
}

// An indentless block sequence (`- ` at the key's column) is spliced at its
// own indentation.
func TestSpliceIndentlessSequence(t *testing.T) {
	orig := "contract: 1\nadopted:\n- {test: tests/keep.sh, source: src/keep.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto}\n" +
		"- {test: tests/t.sh, source: src/a.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto}\n"
	root := txRepo(t, map[string]string{AdoptedPath: orig})
	applyRestamp(t, root, By{Kind: ByHuman, Value: "p@example.invalid"}, "", "")
	if got, want := readF(t, root, AdoptedPath), "contract: 1\nadopted:\n- {test: tests/keep.sh, source: src/keep.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto}\n"; got != want {
		t.Fatalf("got\n%q\nwant\n%q", got, want)
	}
}

// M6.1's keys and comments in onboard.yaml survive a rejection being added.
func TestSpliceOnboardKeepsOtherKeys(t *testing.T) {
	head := "# onboarding ledger\ncontract: 1\ntask: 42   # the level task\nlevel: 1\nphases:\n  seed: {status: done, at: 2026-10-01}\n  # adopt runs next\n  adopt: {status: pending}\n"
	tail := "calibration:\n  - {run: c1, agree: 9, disagree: 1, ratio: 0.9}\n"
	root := txRepo(t, map[string]string{OnboardPath: head + "rejections:\n  - {test: tests/q.sh, source: src/q.sh, reason: helper}\n" + tail})
	tx := openTx(t, root, RouteOnboardReject)
	if err := tx.AddRejection(Rejection{Test: "tests/r.sh", Source: "src/r.sh", Reason: "fixture", By: "human:p@example.invalid"}); err != nil {
		t.Fatal(err)
	}
	commit(t, tx)
	want := head + "rejections:\n  - {test: tests/q.sh, source: src/q.sh, reason: helper}\n" +
		"  - test: tests/r.sh\n    source: src/r.sh\n    reason: fixture\n    by: human:p@example.invalid\n" + tail
	if got := readF(t, root, OnboardPath); got != want {
		t.Fatalf("got\n%s\nwant\n%s", got, want)
	}
	// An absent table key is appended as a new block; nothing else moves.
	tx = openTx(t, root, RouteClassifyPropose)
	tx.AddKindProposal(KindProposal{Test: "tests/e.sh", Kind: KindE2E, Reason: "resource:tmux"})
	commit(t, tx)
	if got := readF(t, root, OnboardPath); got != want+"kind_proposals:\n  - test: tests/e.sh\n    kind: e2e\n    reason: resource:tmux\n" {
		t.Fatalf("append:\n%s", got)
	}
}

// A flow-style table is normalised when edited (user decision): every
// unrelated row keeps all its values, unknown fields included; bytes outside
// the table stay; formatting inside the table is the documented loss.
func TestSpliceFlowTableKeepsValues(t *testing.T) {
	orig := "# header comment\ncontract: 1\nadopted: [{test: tests/t.sh, source: src/a.sh, origin: [coverage], adopted_at: 2026-10-01, by: auto, stamp: 2026-10-01/0123456789},\n" +
		"  {source: \"src/keep.sh\", test: 'tests/keep.sh', by: auto, origin: [coverage], adopted_at: \"2026-09-01\", future_field: kept}]\n"
	root := txRepo(t, map[string]string{AdoptedPath: orig})
	before := reload(t, root).RawAdopted[1]
	applyRestamp(t, root, By{Kind: ByAuto}, "2026-10-01/0123456789", "2026-10-19/9876543210")
	got := readF(t, root, AdoptedPath)
	if !strings.HasPrefix(got, "# header comment\ncontract: 1\nadopted:\n  - ") {
		t.Fatalf("bytes outside the table moved:\n%s", got)
	}
	a := reload(t, root)
	if !reflect.DeepEqual(a.RawAdopted[1], before) || a.RawAdopted[0].Stamp != "2026-10-19/9876543210" {
		t.Fatalf("values: %+v\nwant unrelated %+v", a.RawAdopted, before)
	}
	applyRestamp(t, root, By{Kind: ByHuman, Value: "p@example.invalid"}, "", "")
	if a := reload(t, root); len(a.RawAdopted) != 1 || !reflect.DeepEqual(a.RawAdopted[0], before) {
		t.Fatalf("after delete: %+v", a.RawAdopted)
	}
}

// A flow-style onboard table is normalised alone: phases and the other three
// tables keep their bytes.
func TestSpliceFlowOnboardTableOnly(t *testing.T) {
	phases := "contract: 1\nphases: {seed: {status: done}}  # flow on purpose\n"
	others := "reviews:\n  - {test: tests/t.sh, source: src/a.sh, verdict: unsure, test_blob: t, packet_sha: p, run: r, by: auto}\n"
	root := txRepo(t, map[string]string{OnboardPath: phases + "rejections: [{test: tests/q.sh, source: src/q.sh, reason: helper}]\n" + others})
	tx := openTx(t, root, RouteOnboardReject)
	tx.AddRejection(Rejection{Test: "tests/r.sh", Source: "src/r.sh", Reason: "fixture"})
	commit(t, tx)
	got := readF(t, root, OnboardPath)
	want := phases + "rejections:\n  - test: tests/q.sh\n    source: src/q.sh\n    reason: helper\n  - test: tests/r.sh\n    source: src/r.sh\n    reason: fixture\n" + others
	if got != want {
		t.Fatalf("got\n%s\nwant\n%s", got, want)
	}
}

// The prepare step refuses what it cannot splice faithfully, with nothing
// written: a table key that is not a sequence, and a splice whose re-read
// does not hold exactly the intended rows.
func TestSpliceRefusals(t *testing.T) {
	keyOf := nodeKey(func(r AdoptedRow) string { return joinKey(r.Test, r.Source) })
	if _, err := spliceTable([]byte("adopted: {a: 1}\n"), "adopted", keyOf, []rowEdit{{key: "x", row: nil}}, true); err == nil {
		t.Error("a mapping table was spliced")
	}
	row := AdoptedRow{Test: "tests/t.sh", Source: "src/a.sh", Origin: []string{"coverage"}, AdoptedAt: "2026-10-01", By: "auto"}
	other := row
	other.By = "human:p@example.invalid"
	if err := sameRows([]AdoptedRow{row}, []AdoptedRow{other}, func(r AdoptedRow) string { return r.Test }); err == nil {
		t.Error("a differing row passed the round-trip check")
	}
	if err := sameRows([]AdoptedRow{row}, nil, func(r AdoptedRow) string { return r.Test }); err == nil {
		t.Error("an extra row passed the round-trip check")
	}
}

// A flow-style top-level mapping has no row boundaries to splice at: the
// write is refused and the file keeps every byte (a line-based splice once
// replaced the whole document with the edited table).
func TestSpliceRefusesFlowTopLevel(t *testing.T) {
	orig := "{contract: 1, task: 42, level: 1, phases: {seed: {status: done}}, rejections: []}\n"
	root := txRepo(t, map[string]string{OnboardPath: orig})
	tx := openTx(t, root, RouteOnboardReject)
	if err := tx.AddRejection(Rejection{Test: "tests/r.sh", Source: "src/r.sh", Reason: "fixture"}); err != nil {
		t.Fatal(err)
	}
	_, err := tx.Commit()
	var ie *InvalidError
	if !errors.As(err, &ie) || !strings.Contains(ie.Reason, "flow style") {
		t.Fatalf("err %v", err)
	}
	if got := readF(t, root, OnboardPath); got != orig {
		t.Fatalf("written:\n%s", got)
	}
}

// The prepare step's backstop: whatever the splicer did, a top-level key
// other than the touched tables must decode to the same value, and no key
// may appear.
func TestOtherKeysUnchangedGuard(t *testing.T) {
	old := []byte("contract: 1\ntask: 42\nrejections: []\n")
	for _, c := range []struct {
		new string
		ok  bool
	}{
		{"contract: 1\ntask: 42\nrejections: [{test: a}]\n", true},
		{"contract: 1\n# a comment\ntask: 42   # same value\nrejections: []\n", true},
		{"rejections: [{test: a}]\n", false},
		{"contract: 1\ntask: 43\nrejections: []\n", false},
		{"contract: 1\ntask: 42\nlevel: 1\nrejections: []\n", false},
	} {
		if err := otherKeysUnchanged(old, []byte(c.new), keyRejections); (err == nil) != c.ok {
			t.Errorf("%q: %v", c.new, err)
		}
	}
}

// A file whose last row has no final newline: appending after it, and
// refreshing or deleting it, keep the file loadable and the other rows' bytes.
func TestSpliceWithoutFinalNewline(t *testing.T) {
	for _, nl := range []string{"", "\n"} {
		first := "  - " + seedYAML("tests/a.sh", "src/a.sh") + "\n"
		last := "  - " + seedYAML("tests/m.sh", "src/m.sh") + nl
		root := txRepo(t, map[string]string{SeededPath: "contract: 1\nseeds:\n" + first + last})
		tx := openTx(t, root, RouteOnboardSeed)
		if _, err := tx.PutSeed(seedRow("tests/z.sh", "src/z.sh")); err != nil {
			t.Fatal(err)
		}
		commit(t, tx)
		got := readF(t, root, SeededPath)
		if !strings.HasPrefix(got, "contract: 1\nseeds:\n"+first+strings.TrimSuffix(last, "\n")+"\n  - test: tests/z.sh\n") {
			t.Fatalf("final newline %q: append\n%q", nl, got)
		}
		if a := reload(t, root); len(a.RawSeeds) != 3 {
			t.Fatalf("rows %+v", a.RawSeeds)
		}
		root = txRepo(t, map[string]string{SeededPath: "contract: 1\nseeds:\n" + first + last})
		tx = openTx(t, root, RouteAdoptRow)
		tx.RemoveSeed("tests/m.sh", "src/m.sh")
		commit(t, tx)
		if got := readF(t, root, SeededPath); got != "contract: 1\nseeds:\n"+first {
			t.Fatalf("final newline %q: delete\n%q", nl, got)
		}
	}
}
