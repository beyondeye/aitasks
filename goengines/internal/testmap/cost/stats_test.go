package cost

import (
	"math"
	"math/rand/v2"
	"slices"
	"testing"

	"gopkg.in/yaml.v3"
)

func TestWelfordMatchesDirect(t *testing.T) {
	rng := rand.New(rand.NewPCG(1, 2))
	var w Welford
	var xs []float64
	for range 1000 {
		x := rng.Float64() * 5000
		xs = append(xs, x)
		w.Add(x)
	}
	var sum float64
	for _, x := range xs {
		sum += x
	}
	mean := sum / float64(len(xs))
	var ss float64
	for _, x := range xs {
		ss += (x - mean) * (x - mean)
	}
	variance := ss / float64(len(xs)-1)
	if math.Abs(w.Mean-mean) > 1e-9*mean || math.Abs(w.Var()-variance) > 1e-9*variance {
		t.Fatalf("welford mean %v var %v, direct %v %v", w.Mean, w.Var(), mean, variance)
	}
	if (Welford{N: 1}).Var() != 0 {
		t.Fatal("one observation has no variance")
	}
}

// exact95 is the nearest-rank 95th percentile.
func exact95(xs []float64) float64 {
	s := slices.Clone(xs)
	slices.Sort(s)
	return s[int(math.Ceil(0.95*float64(len(s))))-1]
}

func TestP2WithinTolerance(t *testing.T) {
	rng := rand.New(rand.NewPCG(7, 9))
	dists := map[string]func() float64{
		"uniform":     func() float64 { return 1 + rng.Float64()*999 },
		"exponential": func() float64 { return rng.ExpFloat64() * 200 },
		"bimodal": func() float64 {
			if rng.Float64() < 0.8 {
				return 100 + rng.NormFloat64()*10
			}
			return 2000 + rng.NormFloat64()*100
		},
	}
	for name, draw := range dists {
		var p P2
		var xs []float64
		for range 5000 {
			x := draw()
			xs = append(xs, x)
			p.Add(x)
		}
		got, want := p.Value(), exact95(xs)
		if math.Abs(got-want) > 0.05*want {
			t.Errorf("%s: P² p95 %v, exact %v (>5%%)", name, got, want)
		}
	}
}

func TestP2ExactBelowFive(t *testing.T) {
	var p P2
	for i, x := range []float64{30, 10, 20, 40} {
		p.Add(x)
		xs := []float64{30, 10, 20, 40}[:i+1]
		if p.Value() != exact95(xs) {
			t.Fatalf("n=%d: %v want %v", i+1, p.Value(), exact95(xs))
		}
	}
	if (P2{}).Value() != 0 {
		t.Fatal("empty P2 is 0")
	}
}

// A state persisted mid-stream (YAML, as the host table stores it) resumes
// to exactly the estimate of an uninterrupted stream: desired positions are
// derived from Count, never accumulated.
func TestP2RoundTripMidStream(t *testing.T) {
	rng := rand.New(rand.NewPCG(3, 4))
	xs := make([]float64, 400)
	for i := range xs {
		xs[i] = rng.ExpFloat64() * 100
	}
	var whole, first Stat
	for _, x := range xs {
		whole.Add(int64(x))
	}
	for _, x := range xs[:137] {
		first.Add(int64(x))
	}
	data, err := yaml.Marshal(first)
	if err != nil {
		t.Fatal(err)
	}
	var resumed Stat
	if err := yaml.Unmarshal(data, &resumed); err != nil {
		t.Fatal(err)
	}
	for _, x := range xs[137:] {
		resumed.Add(int64(x))
	}
	if resumed.P2.Value() != whole.P2.Value() || resumed.Welford != whole.Welford || resumed.P95MS != whole.P95MS {
		t.Fatalf("resumed %+v\nwhole %+v", resumed, whole)
	}
}
