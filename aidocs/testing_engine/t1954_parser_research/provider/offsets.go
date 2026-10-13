package provider

import (
	"bytes"
	"fmt"
	"unicode/utf8"
)

// The position-conversion contract (t1954_3): every offset a provider hands
// to ToContext is a byte offset into the ORIGINAL source. Tools report other
// units — ANTLR's Go runtime runes, the JVM / LSP / vscode-textmate UTF-16
// code units — and the conversion happens once, here, against the original
// bytes. Helpers outside Go (Python, JS, Java) convert with the same rule.

// BOM is the UTF-8 byte-order mark.
var BOM = []byte{0xEF, 0xBB, 0xBF}

// StrictUTF8 returns the text a strict UTF-8 tool sees (any leading BOM
// stripped) and the BOM length, or an error when the bytes are not UTF-8: a
// converter must never guess.
func StrictUTF8(src []byte) (body []byte, bom int, err error) {
	if bytes.HasPrefix(src, BOM) {
		bom = len(BOM)
	}
	body = src[bom:]
	if !utf8.Valid(body) {
		return nil, 0, ErrNotUTF8
	}
	return body, bom, nil
}

// ErrNotUTF8 is a strict-UTF-8 tool given other bytes (e.g. a PEP 263
// Latin-1 file): the operation is unsupported for that input, reported as
// such — never decoded by guesswork, never an empty result.
var ErrNotUTF8 = &UnsupportedCapabilityError{Missing: []string{"UTF-8-input"}}

// RuneOffsets maps rune indices of body (valid UTF-8) to byte offsets of the
// original source, base being the offset of body in it (the BOM length).
// The table has one entry per rune plus one for the end.
type RuneOffsets struct {
	at   []int
	base int
}

// NewRuneOffsets builds the table.
func NewRuneOffsets(body []byte, base int) RuneOffsets {
	at := make([]int, 0, len(body)+1)
	for i := 0; i < len(body); {
		at = append(at, base+i)
		_, w := utf8.DecodeRune(body[i:])
		i += w
	}
	at = append(at, base+len(body))
	return RuneOffsets{at: at, base: base}
}

// Byte is the byte offset of rune index r (r == rune count is the end).
func (t RuneOffsets) Byte(r int) (int, error) {
	if r < 0 || r >= len(t.at) {
		return 0, fmt.Errorf("rune index %d out of range [0,%d]", r, len(t.at)-1)
	}
	return t.at[r], nil
}

// UTF16Offsets maps UTF-16 code-unit indices of body (valid UTF-8) to byte
// offsets of the original source. An index that falls between the two units
// of a surrogate pair has no byte offset and is an error.
type UTF16Offsets struct {
	at []int // -1 inside a surrogate pair
}

// NewUTF16Offsets builds the table.
func NewUTF16Offsets(body []byte, base int) UTF16Offsets {
	at := make([]int, 0, len(body)+1)
	for i := 0; i < len(body); {
		r, w := utf8.DecodeRune(body[i:])
		at = append(at, base+i)
		if r >= 0x10000 {
			at = append(at, -1)
		}
		i += w
	}
	at = append(at, base+len(body))
	return UTF16Offsets{at: at}
}

// Byte is the byte offset of UTF-16 unit index u.
func (t UTF16Offsets) Byte(u int) (int, error) {
	if u < 0 || u >= len(t.at) {
		return 0, fmt.Errorf("UTF-16 index %d out of range [0,%d]", u, len(t.at)-1)
	}
	if t.at[u] < 0 {
		return 0, fmt.Errorf("UTF-16 index %d splits a surrogate pair", u)
	}
	return t.at[u], nil
}

// LinePosition converts an LSP-style (line, character) position to a byte
// offset of src, the character counted in enc ("utf-8" bytes, "utf-16" code
// units or "utf-32" code points) from the start of the line. A position
// past the end of its line is an error.
func LinePosition(src []byte, starts []int, line, char int, enc string) (int, error) {
	if line < 0 || line > len(starts) {
		return 0, fmt.Errorf("line %d out of range", line)
	}
	if line == len(starts) { // the position just past the last line
		if char == 0 {
			return len(src), nil
		}
		return 0, fmt.Errorf("line %d out of range", line)
	}
	ls := starts[line]
	le := len(src)
	if line+1 < len(starts) {
		le = starts[line+1]
	}
	text := src[ls:le]
	switch enc {
	case "utf-8":
		if char > len(text) {
			return 0, fmt.Errorf("character %d past line end", char)
		}
		return ls + char, nil
	case "utf-16", "":
		t := NewUTF16Offsets(text, ls)
		return t.Byte(char)
	case "utf-32":
		t := NewRuneOffsets(text, ls)
		return t.Byte(char)
	}
	return 0, fmt.Errorf("unknown position encoding %q", enc)
}
