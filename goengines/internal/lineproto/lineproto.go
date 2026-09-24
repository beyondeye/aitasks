// Package lineproto writes the engine's machine-readable output: one
// `CLASS:field|field…` line per record on stdout, or a single JSON document
// when a verb runs with --json. It also holds the exit codes every verb speaks
// and the per-verb exit-contract enforcement (exit.go).
//
// Line classes are consumed by bash with `IFS='|'` and `${line#CLASS:}`, so a
// field may never carry the field separator or a line break. Line refuses
// such a field rather than emitting a line that parses into the wrong fields.
package lineproto

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
)

// ErrUnsafeField is returned by Line when a field contains '|', '\n' or '\r'.
var ErrUnsafeField = errors.New("lineproto: field contains '|' or a line break")

// ErrUnsafeClass is returned by Line when a class is empty or contains ':',
// '|' or a line break.
var ErrUnsafeClass = errors.New("lineproto: class is empty or contains ':', '|' or a line break")

// Writer emits line-protocol records, or JSON documents when JSON is set.
type Writer struct {
	out  io.Writer
	JSON bool
}

// NewWriter returns a Writer on out. json selects the --json form.
func NewWriter(out io.Writer, json bool) *Writer {
	return &Writer{out: out, JSON: json}
}

// Format returns `CLASS:f1|f2|…` without the trailing newline, or an error
// when the class or a field cannot travel in a line. Every line the engine
// prints — directly or as a string another package hands back — goes through
// it.
func Format(class string, fields ...string) (string, error) {
	if class == "" || strings.ContainsAny(class, ":|\n\r") {
		return "", fmt.Errorf("%w: %q", ErrUnsafeClass, class)
	}
	for _, f := range fields {
		if strings.ContainsAny(f, "|\n\r") {
			return "", fmt.Errorf("%w: %s field %q", ErrUnsafeField, class, f)
		}
	}
	return class + ":" + strings.Join(fields, "|"), nil
}

// Line writes Format(class, fields…) and a newline. With no fields it writes
// `CLASS:`.
func (w *Writer) Line(class string, fields ...string) error {
	l, err := Format(class, fields...)
	if err != nil {
		return err
	}
	_, err = io.WriteString(w.out, l+"\n")
	return err
}

// Emit writes v as one JSON document followed by a newline.
func (w *Writer) Emit(v any) error {
	enc := json.NewEncoder(w.out)
	enc.SetEscapeHTML(false)
	return enc.Encode(v)
}
