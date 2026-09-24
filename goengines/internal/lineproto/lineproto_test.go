package lineproto

import (
	"bytes"
	"errors"
	"testing"
)

func TestLine(t *testing.T) {
	var b bytes.Buffer
	w := NewWriter(&b, false)
	if err := w.Line("ENGINE", "/a/b"); err != nil {
		t.Fatal(err)
	}
	if err := w.Line("PAIR", "x", "", "y"); err != nil {
		t.Fatal(err)
	}
	if err := w.Line("EMPTY"); err != nil {
		t.Fatal(err)
	}
	want := "ENGINE:/a/b\nPAIR:x||y\nEMPTY:\n"
	if b.String() != want {
		t.Fatalf("got %q want %q", b.String(), want)
	}
}

func TestLineRefusesUnsafe(t *testing.T) {
	var b bytes.Buffer
	w := NewWriter(&b, false)
	for _, f := range []string{"a|b", "a\nb", "a\rb"} {
		if err := w.Line("C", f); !errors.Is(err, ErrUnsafeField) {
			t.Errorf("field %q: got %v, want ErrUnsafeField", f, err)
		}
	}
	for _, c := range []string{"", "A:B", "A|B", "A\n"} {
		if err := w.Line(c, "x"); !errors.Is(err, ErrUnsafeClass) {
			t.Errorf("class %q: got %v, want ErrUnsafeClass", c, err)
		}
	}
	if b.Len() != 0 {
		t.Fatalf("refused lines must write nothing, got %q", b.String())
	}
}

func TestEmit(t *testing.T) {
	var b bytes.Buffer
	w := NewWriter(&b, true)
	if err := w.Emit(map[string]any{"engine": "/a&b", "contract": 1}); err != nil {
		t.Fatal(err)
	}
	want := "{\"contract\":1,\"engine\":\"/a&b\"}\n"
	if b.String() != want {
		t.Fatalf("got %q want %q", b.String(), want)
	}
}

func TestEnforce(t *testing.T) {
	c := ExitContract{ExitOK, ExitUsage}
	var e bytes.Buffer
	if got := Enforce("v", c, ExitUsage, &e); got != ExitUsage || e.Len() != 0 {
		t.Fatalf("allowed code: got %d stderr %q", got, e.String())
	}
	if got := Enforce("v", c, ExitFail, &e); got != ExitFramework {
		t.Fatalf("disallowed code: got %d, want %d", got, ExitFramework)
	}
	if e.String() != "EXIT_CONTRACT_VIOLATION:v|1\n" {
		t.Fatalf("stderr %q", e.String())
	}
}

func TestUsage(t *testing.T) {
	var e bytes.Buffer
	if got := Usage(&e, "ait-testmap <verb>"); got != ExitUsage {
		t.Fatalf("got %d", got)
	}
	if e.String() != "USAGE:ait-testmap <verb>\n" {
		t.Fatalf("stderr %q", e.String())
	}
}

func TestFormat(t *testing.T) {
	if l, err := Format("A", "x", "y"); err != nil || l != "A:x|y" {
		t.Fatalf("%q %v", l, err)
	}
	if l, err := Format("A", "x|y"); !errors.Is(err, ErrUnsafeField) || l != "" {
		t.Fatalf("%q %v", l, err)
	}
}
