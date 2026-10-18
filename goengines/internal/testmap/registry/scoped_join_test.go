package registry

import (
	"errors"
	"reflect"
	"testing"
)

func joinFixture() *Scoped {
	s := &Scoped{Areas: map[string]*Area{}}
	s.addArea("r/areas.yaml", "board", []string{".aitask-scripts/board/**"})
	s.addRow(ScopedRow{Test: MustParseID("tests/test_board_live.py"), Kind: KindIntegration, Areas: []string{"board", "undeclared"}, File: ScopedPath})
	s.addRow(ScopedRow{Test: MustParseID("tests/test_flow.sh#e2e"), Kind: KindE2E, Globs: []string{".aitask-scripts/aitask_*.sh"}, Triggers: []string{"lib/launch_modes*.py"}, File: ScopedPath})
	s.addRow(ScopedRow{Test: MustParseID("tests/test_dev.kt"), Kind: KindDevice, Triggers: []string{"lib/launch_modes.py"}, File: "r/h.yaml"})
	s.Reads = []ReadsRow{{Helper: "tests/lib/fixture.py", Globs: []string{"tests/*.sh"}, File: ScopedPath}}
	return s
}

func TestJoin(t *testing.T) {
	s := joinFixture()
	closure := func(test string) ([]string, error) {
		switch test {
		case "tests/test_unit.py", "tests/test_board_live.py":
			return []string{"src/x.py", "tests/lib/fixture.py"}, nil
		}
		return nil, nil
	}
	changed := []string{".aitask-scripts/board/app.py", ".aitask-scripts/aitask_pick.sh", "lib/launch_modes.py", "tests/test_x.sh", "README.md"}
	hits, err := s.Join(changed, []ID{MustParseID("tests/test_unit.py")}, closure)
	if err != nil {
		t.Fatal(err)
	}
	want := []JoinHit{
		{Test: MustParseID("tests/test_unit.py"), Kind: KindUnit, Distance: 1, Via: ViaReads, Ref: "tests/lib/fixture.py", Path: "tests/test_x.sh", BudgetExempt: true},
		{Test: MustParseID("tests/test_board_live.py"), Kind: KindIntegration, Distance: 1, Via: ViaArea, Ref: "board", Path: ".aitask-scripts/board/app.py"},
		{Test: MustParseID("tests/test_board_live.py"), Kind: KindIntegration, Distance: 1, Via: ViaReads, Ref: "tests/lib/fixture.py", Path: "tests/test_x.sh", BudgetExempt: true},
		{Test: MustParseID("tests/test_flow.sh#e2e"), Kind: KindE2E, Distance: 1, Via: ViaScope, Ref: ".aitask-scripts/aitask_*.sh", Path: ".aitask-scripts/aitask_pick.sh"},
		{Test: MustParseID("tests/test_flow.sh#e2e"), Kind: KindE2E, Distance: 1, Via: ViaTrigger, Ref: "lib/launch_modes*.py", Path: "lib/launch_modes.py", BudgetExempt: true},
		{Test: MustParseID("tests/test_dev.kt"), Kind: KindDevice, Distance: 1, Via: ViaTrigger, Ref: "lib/launch_modes.py", Path: "lib/launch_modes.py", BudgetExempt: true},
	}
	if !reflect.DeepEqual(hits, want) {
		t.Fatalf("got\n%+v\nwant\n%+v", hits, want)
	}
	for _, h := range hits {
		if h.Kind != s.KindOf(h.Test) {
			t.Fatalf("%s: hit kind %s, KindOf %s", h.Test, h.Kind, s.KindOf(h.Test))
		}
	}
}

func TestJoinNeedsClosureForReads(t *testing.T) {
	s := joinFixture()
	if _, err := s.Join([]string{"tests/x.sh"}, nil, nil); !errors.Is(err, ErrNoClosure) {
		t.Fatalf("err %v", err)
	}
	s.Reads = nil
	if _, err := s.Join([]string{"tests/x.sh"}, nil, nil); err != nil {
		t.Fatalf("no reads, no closure needed: %v", err)
	}
	boom := errors.New("closure failed")
	s = joinFixture()
	if _, err := s.Join(nil, nil, func(string) ([]string, error) { return nil, boom }); !errors.Is(err, boom) {
		t.Fatalf("a closure error is returned, never a partial join: %v", err)
	}
}
