package lineproto

import (
	"fmt"
	"io"
	"slices"
)

// Exit codes, from the proposal's Run Surface exit table. Every verb's exit
// contract is a subset of these.
const (
	ExitOK         = 0  // every selected unit passed / the verb succeeded
	ExitFail       = 1  // a unit failed, or a mechanism failure
	ExitNothingRan = 2  // nothing ran: empty selection
	ExitFramework  = 3  // framework error: engine mismatch, CONTRACT_MISMATCH, bad intake
	ExitUsage      = 64 // usage: bad flag, unknown verb, a verb not implemented yet
	ExitRefused    = 75 // admission refused after the in-engine deferral
)

// ExitContract is the set of exit codes a verb may return.
type ExitContract []int

// Allows reports whether code is in the contract.
func (c ExitContract) Allows(code int) bool {
	return slices.Contains(c, code)
}

// Enforce returns code when the verb's contract allows it. Any other code is a
// defect in the verb: it prints EXIT_CONTRACT_VIOLATION:<verb>|<code> on
// stderr and returns ExitFramework, so a caller parsing the exit status never
// acts on a code the verb does not promise.
func Enforce(verb string, c ExitContract, code int, stderr io.Writer) int {
	if c.Allows(code) {
		return code
	}
	fmt.Fprintf(stderr, "EXIT_CONTRACT_VIOLATION:%s|%d\n", verb, code)
	return ExitFramework
}

// Usage prints USAGE:<msg> on stderr and returns ExitUsage.
func Usage(stderr io.Writer, msg string) int {
	fmt.Fprintf(stderr, "USAGE:%s\n", msg)
	return ExitUsage
}
