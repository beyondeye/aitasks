//go:build unix && !linux

package hangguard

import "time"

// reapMarked has no process enumeration on this platform: a hang still
// fails fast, but its cleanup is reported unverified rather than claimed.
func reapMarked(string, time.Duration) ([]string, error) { return nil, errNoEnumeration }
