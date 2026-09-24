package testmap

import (
	"errors"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/lineproto"
)

func TestCheckContract(t *testing.T) {
	for _, tc := range []struct {
		name   string
		doc    string
		refuse bool
	}{
		{"absent", "units: []\n", false},
		{"empty document", "", false},
		{"equal", "contract: 1\n", false},
		{"older", "contract: 0\n", false},
		{"newer", "contract: 2\nby: x\n", true},
		{"newer via merge key", "defaults: &defaults {contract: 2}\n<<: *defaults\n", true},
		{"newer via merge list", "a: &a {x: 1}\nb: &b {contract: 2}\n<<: [*a, *b]\n", true},
		{"newer via alias", "v: &v 2\ncontract: *v\n", true},
		{"explicit key overrides merged newer", "defaults: &defaults {contract: 2}\n<<: *defaults\ncontract: 1\n", false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			err := CheckContract("aitestmap/units.yaml", []byte(tc.doc))
			var cm *ContractMismatchError
			if tc.refuse != errors.As(err, &cm) {
				t.Fatalf("got %v, refuse=%v", err, tc.refuse)
			}
			if !tc.refuse && err != nil {
				t.Fatalf("unexpected error %v", err)
			}
			if tc.refuse {
				if l, err := cm.Line(); err != nil || l != "CONTRACT_MISMATCH:aitestmap/units.yaml|2|1" {
					t.Fatalf("line %q, %v", l, err)
				}
				if cm.ExitCode() != 3 {
					t.Fatalf("exit %d", cm.ExitCode())
				}
			}
		})
	}
}

// Every input here must be an error, never a mismatch and never a pass: a
// float that truncates to a valid contract, a null that reads as "absent", a
// second document or a trailing malformed one that the first decode would
// never look at.
func TestCheckContractErrors(t *testing.T) {
	for _, doc := range []string{
		"contract: [1\n",
		"contract: two\n",
		"contract: 1.5\n",
		"contract: 2.0\n",
		"contract: null\n",
		"contract: ~\n",
		"contract:\n",
		"contract: \"1\"\n",
		"contract: -1\n",
		"contract: [1]\n",
		"contract: 1\ncontract: 2\n",
		"defaults: &d {contract: 1.5}\n<<: *d\n",
		"defaults: &d {contract: null}\n<<: *d\n",
		"contract: 1\n---\ncontract: 2\n",
		"contract: 1\n---\n: : [bad\n",
		"- contract: 1\n",
		"just a scalar\n",
	} {
		err := CheckContract("f.yaml", []byte(doc))
		var cm *ContractMismatchError
		if err == nil || errors.As(err, &cm) {
			t.Errorf("%q: got %v, want an error that is not a mismatch", doc, err)
		}
	}
}

func TestReadContractFound(t *testing.T) {
	for doc, want := range map[string]int{"contract: 1\n": 1, "units: []\ncontract: 0\n": 0, "---\ncontract: 3\n": 3} {
		c, found, err := ReadContract([]byte(doc))
		if err != nil || !found || c != want {
			t.Errorf("%q: got %d %v %v, want %d", doc, c, found, err, want)
		}
	}
	if _, found, err := ReadContract([]byte("# only a comment\n")); found || err != nil {
		t.Errorf("comment-only file: found %v err %v", found, err)
	}
}

func TestContractMismatchLineRefusesUnsafePath(t *testing.T) {
	for _, p := range []string{"a|b.yaml", "a\nb.yaml", "a\rb.yaml"} {
		err := CheckContract(p, []byte("contract: 2\n"))
		var cm *ContractMismatchError
		if !errors.As(err, &cm) {
			t.Fatalf("%q: %v", p, err)
		}
		if l, lerr := cm.Line(); !errors.Is(lerr, lineproto.ErrUnsafeField) || l != "" {
			t.Errorf("%q: line %q err %v, want ErrUnsafeField", p, l, lerr)
		}
		if cm.Error() == "" {
			t.Errorf("%q: the error must still be reportable", p)
		}
	}
}

func TestCacheDir(t *testing.T) {
	t.Setenv("XDG_CACHE_HOME", "")
	t.Setenv("HOME", "/home/u")
	got, err := CacheDir()
	if err != nil || got != "/home/u/.cache/aitasks/testmap" {
		t.Fatalf("got %q, %v", got, err)
	}
	t.Setenv("XDG_CACHE_HOME", "/x")
	if got, _ := CacheDir(); !strings.HasSuffix(got, "/aitasks/testmap") || got != "/x/aitasks/testmap" {
		t.Fatalf("got %q", got)
	}
}
