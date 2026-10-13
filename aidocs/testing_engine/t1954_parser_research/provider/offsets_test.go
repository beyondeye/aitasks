package provider

import "testing"

// Hand-computed offsets (t1954_3 position-conversion contract): é is 2 bytes
// / 1 UTF-16 unit, € 3 bytes / 1 unit, 😀 4 bytes / 2 units (a surrogate
// pair).
func TestOffsetConversions(t *testing.T) {
	src := []byte("aé€😀b")
	//            bytes: a=0 é=1-2 €=3-5 😀=6-9 b=10 end=11
	runes := NewRuneOffsets(src, 0)
	for r, want := range []int{0, 1, 3, 6, 10, 11} {
		got, err := runes.Byte(r)
		if err != nil || got != want {
			t.Fatalf("rune %d: got %d,%v want %d", r, got, err, want)
		}
	}
	if _, err := runes.Byte(6); err == nil {
		t.Fatalf("rune index past the end accepted")
	}
	u16 := NewUTF16Offsets(src, 0)
	//            units: a=0 é=1 €=2 😀=3,4 b=5 end=6
	for u, want := range map[int]int{0: 0, 1: 1, 2: 3, 3: 6, 5: 10, 6: 11} {
		got, err := u16.Byte(u)
		if err != nil || got != want {
			t.Fatalf("utf16 %d: got %d,%v want %d", u, got, err, want)
		}
	}
	if _, err := u16.Byte(4); err == nil {
		t.Fatalf("an index inside a surrogate pair was accepted")
	}
}

func TestOffsetBaseAndStrict(t *testing.T) {
	src := append(append([]byte{}, BOM...), []byte("é\n😀x")...)
	body, bom, err := StrictUTF8(src)
	if err != nil || bom != 3 {
		t.Fatalf("StrictUTF8: bom=%d err=%v", bom, err)
	}
	runes := NewRuneOffsets(body, bom)
	if got, _ := runes.Byte(2); got != 6 { // é(3-4) \n(5) 😀(6)
		t.Fatalf("rune 2 with BOM base: got %d want 6", got)
	}
	if _, _, err := StrictUTF8([]byte{'a', 0xE9, 'b'}); err == nil {
		t.Fatalf("Latin-1 byte accepted as UTF-8")
	}
}

func TestLinePosition(t *testing.T) {
	src := []byte("x\n😀// c\n")
	starts := LineStarts(src)
	// line 1: 😀 is bytes 2-5, "//" at byte 6; UTF-16 char 2, UTF-8 char 4, UTF-32 char 1.
	for enc, char := range map[string]int{"utf-16": 2, "utf-8": 4, "utf-32": 1} {
		got, err := LinePosition(src, starts, 1, char, enc)
		if err != nil || got != 6 {
			t.Fatalf("%s: got %d,%v want 6", enc, got, err)
		}
	}
	if _, err := LinePosition(src, starts, 1, 1, "utf-16"); err == nil {
		t.Fatalf("utf-16 position inside a surrogate pair accepted")
	}
	if got, err := LinePosition(src, starts, 2, 0, "utf-16"); err != nil || got != len(src) {
		t.Fatalf("end position: got %d,%v", got, err)
	}
}
