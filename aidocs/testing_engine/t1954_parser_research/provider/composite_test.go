package provider

import (
	"strings"
	"testing"
)

// An unavailable part makes the native composite refuse, instead of silently
// handing that part's languages to the landed lexer under the part's name.
func TestCompositeRefusesAMissingPart(t *testing.T) {
	t.Setenv("T1954_PYTHON", "/nonexistent/python3")
	c, err := NewComposite()
	if err == nil || !strings.Contains(err.Error(), "pytokenize") {
		t.Fatalf("composite %v, err %v: want a refusal naming pytokenize", c, err)
	}
	CloseAll()
}
