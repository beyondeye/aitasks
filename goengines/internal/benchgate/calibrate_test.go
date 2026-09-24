package benchgate

import (
	"crypto/sha1"
	"os/exec"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/gitx"
)

// calibrateSink keeps the calibration loop's result observable, so the
// compiler cannot drop the work.
var calibrateSink uint64

// calibrate is a fixed amount of CPU-bound, allocation-free, I/O-free work: a
// xorshift/multiply chain whose every step depends on the previous one.
func calibrate() uint64 {
	x := uint64(0x9e3779b97f4a7c15)
	for range 1 << 20 {
		x ^= x << 13
		x ^= x >> 7
		x ^= x << 17
		x *= 0xbf58476d1ce4e5b9
	}
	return x
}

// BenchmarkCalibrate is the host-speed reference named by Calibration. Its
// work must never change: a different amount of work re-scales every
// comparison until the baseline is re-recorded.
func BenchmarkCalibrate(b *testing.B) {
	for b.Loop() {
		calibrateSink += calibrate()
	}
}

// BenchmarkCalibrateSpawn is the host-speed reference for process-bound
// benchmarks (CalibrationSpawn): one fork/exec of git doing no repository
// work, the fixed cost every gitx query pays.
func BenchmarkCalibrateSpawn(b *testing.B) {
	for b.Loop() {
		cmd := exec.Command("git", "--version")
		cmd.Env = gitx.Env()
		if err := cmd.Run(); err != nil {
			b.Fatal(err)
		}
	}
}

// calibrateHashData is the fixed input of BenchmarkCalibrateHash.
var calibrateHashData = func() []byte {
	d := make([]byte, 64<<10)
	for i := range d {
		d[i] = byte(i * 7)
	}
	return d
}()

// BenchmarkCalibrateHash is the host-speed reference for hashing benchmarks
// (CalibrationHash, class sha1): SHA-1 over a fixed 64 KiB buffer. Hash throughput
// depends on hardware acceleration and microarchitecture far more than
// general CPU work, so digest benchmarks cannot be scaled by the cpu class.
func BenchmarkCalibrateHash(b *testing.B) {
	for b.Loop() {
		s := sha1.Sum(calibrateHashData)
		calibrateSink += uint64(s[0])
	}
}
