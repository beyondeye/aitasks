//go:build linux

package builtin

// suite is registered for production only where its real-tool tests run
// (G10): GNU bash on linux. Elsewhere `builtin: suite` stays unresolved.
func init() { Register(suiteAdapter()) }
