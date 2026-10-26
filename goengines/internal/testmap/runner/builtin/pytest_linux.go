//go:build linux

package builtin

// pytest is registered for production only where its real-tool tests run
// (G10): pytest 8.x on CPython >= 3.10, linux. Elsewhere `builtin: pytest`
// stays unresolved.
func init() { Register(pytestAdapter()) }
