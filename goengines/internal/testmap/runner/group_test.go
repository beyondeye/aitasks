package runner

import (
	"math/rand"
	"reflect"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

func unit(id, runner, group string, res []string, batchNo bool) Unit {
	return Unit{ID: registry.MustParseID(id), Runner: runner, Group: group, Resources: res, BatchNo: batchNo, TimeoutS: 1}
}

func invCount(units []Unit, wave func(registry.ID) WaveClass) int { return len(Group(units, wave)) }

// Each key component splits invocations; units equal on every component
// share one.
func TestGroupingKey(t *testing.T) {
	base := func(id string) Unit { return unit(id, "r", "g", []string{"m"}, false) }
	if n := invCount([]Unit{base("a"), base("b")}, nil); n != 1 {
		t.Fatalf("identical keys: %d invocations", n)
	}
	for name, other := range map[string]Unit{
		"runner":    unit("b", "r2", "g", []string{"m"}, false),
		"group":     unit("b", "r", "g2", []string{"m"}, false),
		"resources": unit("b", "r", "g", []string{"m", "n"}, false),
		"batch":     unit("b", "r", "g", []string{"m"}, true),
	} {
		if n := invCount([]Unit{base("a"), other}, nil); n != 2 {
			t.Errorf("%s: %d invocations, want 2", name, n)
		}
	}
	wave := func(id registry.ID) WaveClass {
		if id.Path == "b" {
			return WaveBroad
		}
		return WaveUnit
	}
	if n := invCount([]Unit{base("a"), base("b")}, wave); n != 2 {
		t.Errorf("wave: %d invocations, want 2", n)
	}
}

// Two batch: no units with otherwise identical fields are two singleton
// invocations, keyed by their own ids.
func TestGroupingBatchNoSingletons(t *testing.T) {
	invs := Group([]Unit{unit("a", "r", "", nil, true), unit("b", "r", "", nil, true)}, nil)
	if len(invs) != 2 || len(invs[0].Units) != 1 || invs[0].Key.Batch != "a" || invs[1].Key.Batch != "b" {
		t.Fatalf("%+v", invs)
	}
}

// unit vs broad splits; no kind data (nil classifier or "") means unit.
func TestGroupingWaveClass(t *testing.T) {
	u := []Unit{unit("a", "r", "", nil, false), unit("b", "r", "", nil, false)}
	if invs := Group(u, nil); len(invs) != 1 || invs[0].Key.Wave != WaveUnit {
		t.Fatalf("nil classifier: %+v", invs)
	}
	if invs := Group(u, func(registry.ID) WaveClass { return "" }); len(invs) != 1 || invs[0].Key.Wave != WaveUnit {
		t.Fatalf("empty class: %+v", invs)
	}
	split := Group(u, func(id registry.ID) WaveClass {
		if id.Path == "b" {
			return WaveBroad
		}
		return WaveUnit
	})
	if len(split) != 2 || split[0].Key.Wave == split[1].Key.Wave {
		t.Fatalf("unit vs broad: %+v", split)
	}
}

// The output depends only on the units, never on their order.
func TestGroupingDeterministic(t *testing.T) {
	units := []Unit{
		unit("a", "r", "g1", nil, false), unit("b", "r", "g1", nil, false), unit("c", "r", "g2", nil, false),
		unit("d", "s", "", []string{"x"}, false), unit("e", "s", "", nil, true), unit("f", "s", "", nil, true),
	}
	want := Group(units, nil)
	rng := rand.New(rand.NewSource(1))
	for range 20 {
		p := append([]Unit(nil), units...)
		rng.Shuffle(len(p), func(i, j int) { p[i], p[j] = p[j], p[i] })
		if got := Group(p, nil); !reflect.DeepEqual(got, want) {
			t.Fatalf("order-dependent:\n%+v\n%+v", got, want)
		}
	}
	for i, inv := range want {
		if inv.Index != i+1 {
			t.Fatalf("index %d at %d", inv.Index, i)
		}
	}
	if s := want[0].Key.String(); s != `["r","g1",[],"unit",""]` {
		t.Fatalf("key string %s", s)
	}
}
