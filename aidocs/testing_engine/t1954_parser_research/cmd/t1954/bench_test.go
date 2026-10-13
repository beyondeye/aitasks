package main

import "testing"

// The fastest sample gives the time; the RSS is the peak over ALL samples.
func TestBestKeepsPeakRSS(t *testing.T) {
	b, all := best([]sample{{ns: 200, rss: 100, childRSS: 7}, {ns: 100, rss: 10, childRSS: 3}})
	if b.ns != 100 || b.rss != 100 || b.childRSS != 7 || len(all) != 2 {
		t.Fatalf("best %+v all %v", b, all)
	}
}
