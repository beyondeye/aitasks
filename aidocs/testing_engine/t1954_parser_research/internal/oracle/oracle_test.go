package oracle

import (
	"os"
	"path/filepath"
	"testing"
)

// The file name reaches the TypeScript oracle: `<number>1` is a type
// assertion in .ts (the comment after it is real) and JSX in .tsx.
func TestTSOracleUsesTheFileName(t *testing.T) {
	if ok, why := TSAvailable(); !ok {
		t.Skip("TypeScript oracle unavailable: " + why)
	}
	// ts_oracle.js is resolved relative to the research dir.
	wd, _ := os.Getwd()
	if err := os.Chdir(filepath.Join(wd, "..", "..")); err != nil {
		t.Fatal(err)
	}
	defer os.Chdir(wd)
	defer Close()
	src := []byte("const x = <number>1;\n// real\n")
	got, name, err := Comments("t.ts", "typescript", src)
	if err != nil || name != "ts-parser" || len(got) != 1 || string(src[got[0].Start:got[0].End]) != "// real" {
		t.Fatalf(".ts: %v %q %v", got, name, err)
	}
	if _, _, err := Comments("", "typescript", src); err == nil {
		t.Fatal("a request without a file name must be refused")
	}
}
