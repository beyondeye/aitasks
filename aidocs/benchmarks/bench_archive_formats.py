#!/usr/bin/env python3
"""Benchmark archive formats for aitasks archived task/plan bundles.

Compares tar.gz (current), tar.zst, zip, tar.xz, and uncompressed tar
across five operations: list files, check file existence, extract single
file, create archive, and compression ratio.

Uses existing old*.tar.gz archives as test data.

Usage:
    python3 aidocs/benchmarks/bench_archive_formats.py
    python3 aidocs/benchmarks/bench_archive_formats.py --iterations 100
    python3 aidocs/benchmarks/bench_archive_formats.py --formats tar.gz zip
    python3 aidocs/benchmarks/bench_archive_formats.py --operations list exists size
"""
from __future__ import annotations

import argparse
import os
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WARMUP_DEFAULT = 3
ITERATIONS_DEFAULT = 50


# ---------------------------------------------------------------------------
# Dependency detection
# ---------------------------------------------------------------------------

@dataclass
class Capabilities:
    has_zstd_cli: bool = False
    has_tar_zstd: bool = False
    has_zip_cli: bool = False
    has_unzip_cli: bool = False

    def summary(self) -> str:
        lines = ["Detected capabilities:"]
        lines.append(f"  zstd CLI:       {'yes' if self.has_zstd_cli else 'NO'}")
        lines.append(f"  tar --zstd:     {'yes' if self.has_tar_zstd else 'NO (will use pipe fallback)'}")
        lines.append(f"  zip CLI:        {'yes' if self.has_zip_cli else 'NO'}")
        lines.append(f"  unzip CLI:      {'yes' if self.has_unzip_cli else 'NO'}")
        return "\n".join(lines)


def detect_capabilities() -> Capabilities:
    caps = Capabilities()
    caps.has_zstd_cli = shutil.which("zstd") is not None
    caps.has_zip_cli = shutil.which("zip") is not None
    caps.has_unzip_cli = shutil.which("unzip") is not None

    if caps.has_zstd_cli:
        try:
            with tempfile.NamedTemporaryFile(suffix=".txt") as f:
                f.write(b"test")
                f.flush()
                archive = f.name + ".tar.zst"
                r = subprocess.run(
                    ["tar", "--zstd", "-cf", archive, "-C",
                     os.path.dirname(f.name), os.path.basename(f.name)],
                    capture_output=True, timeout=5,
                )
                caps.has_tar_zstd = r.returncode == 0
                if os.path.exists(archive):
                    os.unlink(archive)
        except Exception:
            caps.has_tar_zstd = False

    return caps


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

@dataclass
class TestData:
    source_dir: Path
    files: List[str]
    total_bytes: int
    sample_file: str
    archive_sources: List[Path]

    @staticmethod
    def prepare(project_root: Path, tmp_dir: Path) -> TestData:
        source = tmp_dir / "source"
        source.mkdir()

        archive_dirs = [
            project_root / "aitasks" / "archived" / "_b0",
            project_root / "aiplans" / "archived" / "_b0",
        ]

        archives_found: List[Path] = []
        for d in archive_dirs:
            resolved = d.resolve()
            if not resolved.is_dir():
                continue
            for f in sorted(resolved.iterdir()):
                if f.name.endswith(".tar.gz") and f.name.startswith("old"):
                    archives_found.append(f)

        if not archives_found:
            print(f"ERROR: No old*.tar.gz files found in {archive_dirs}",
                  file=sys.stderr)
            sys.exit(1)

        print(f"Found {len(archives_found)} source archives:")
        for a in archives_found:
            print(f"  {a} ({a.stat().st_size // 1024}KB)")

        for archive in archives_found:
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(path=source, filter="data")

        files: List[str] = []
        total = 0
        for root, _dirs, fnames in os.walk(source):
            for fn in fnames:
                fp = Path(root) / fn
                rel = str(fp.relative_to(source))
                files.append(rel)
                total += fp.stat().st_size

        files.sort()
        sample = files[len(files) // 2] if files else files[0]

        print(f"Extracted {len(files)} files, {total // 1024}KB uncompressed")
        print(f"Sample file for single-file ops: {sample}")
        return TestData(
            source_dir=source,
            files=files,
            total_bytes=total,
            sample_file=sample,
            archive_sources=archives_found,
        )


# ---------------------------------------------------------------------------
# Format abstraction
# ---------------------------------------------------------------------------

class ArchiveFormat(ABC):
    name: str
    extension: str

    @abstractmethod
    def create(self, source_dir: Path, output_path: Path) -> None: ...

    @abstractmethod
    def list_files(self, archive_path: Path) -> List[str]: ...

    @abstractmethod
    def check_file_exists(self, archive_path: Path, filename: str) -> bool: ...

    @abstractmethod
    def extract_single(self, archive_path: Path, filename: str) -> bytes: ...


def _normalize_tar_name(name: str) -> str:
    """Strip ./ prefix and trailing / from tar member names."""
    if name.startswith("./"):
        name = name[2:]
    return name.rstrip("/")


class TarPython(ArchiveFormat):
    """Python tarfile-based format (tar, tar.gz, tar.xz)."""

    def __init__(self, name: str, extension: str, write_mode: str, read_mode: str):
        self.name = name
        self.extension = extension
        self._wmode = write_mode
        self._rmode = read_mode

    def create(self, source_dir: Path, output_path: Path) -> None:
        with tarfile.open(output_path, self._wmode) as tf:
            for root, _dirs, fnames in os.walk(source_dir):
                for fn in fnames:
                    fp = Path(root) / fn
                    arcname = str(fp.relative_to(source_dir))
                    tf.add(fp, arcname=arcname)

    def list_files(self, archive_path: Path) -> List[str]:
        with tarfile.open(archive_path, self._rmode) as tf:
            return [_normalize_tar_name(n) for n in tf.getnames()]

    def check_file_exists(self, archive_path: Path, filename: str) -> bool:
        with tarfile.open(archive_path, self._rmode) as tf:
            names = {_normalize_tar_name(n) for n in tf.getnames()}
            return filename in names

    def extract_single(self, archive_path: Path, filename: str) -> bytes:
        with tarfile.open(archive_path, self._rmode) as tf:
            for member in tf.getmembers():
                if _normalize_tar_name(member.name) == filename and member.isfile():
                    fobj = tf.extractfile(member)
                    if fobj is not None:
                        return fobj.read()
            raise FileNotFoundError(f"{filename} not in {archive_path}")


class TarGzCLI(ArchiveFormat):
    name = "tar.gz (CLI)"
    extension = ".tar.gz"

    def create(self, source_dir: Path, output_path: Path) -> None:
        subprocess.run(
            ["tar", "-czf", str(output_path), "-C", str(source_dir), "."],
            check=True, capture_output=True,
        )

    def list_files(self, archive_path: Path) -> List[str]:
        r = subprocess.run(
            ["tar", "-tzf", str(archive_path)],
            check=True, capture_output=True, text=True,
        )
        return [_normalize_tar_name(l) for l in r.stdout.strip().splitlines() if l]

    def check_file_exists(self, archive_path: Path, filename: str) -> bool:
        r = subprocess.run(
            ["tar", "-tzf", str(archive_path)],
            check=True, capture_output=True, text=True,
        )
        names = {_normalize_tar_name(l) for l in r.stdout.strip().splitlines()}
        return filename in names

    def extract_single(self, archive_path: Path, filename: str) -> bytes:
        # tar CLI expects the exact member name including ./ prefix
        r = subprocess.run(
            ["tar", "-xzf", str(archive_path), "-O", "./" + filename],
            capture_output=True,
        )
        if r.returncode != 0:
            r = subprocess.run(
                ["tar", "-xzf", str(archive_path), "-O", filename],
                check=True, capture_output=True,
            )
        return r.stdout


class TarZstNative(ArchiveFormat):
    """tar.zst using GNU tar's native --zstd flag (Linux only)."""
    name = "tar.zst (native)"
    extension = ".tar.zst"

    def create(self, source_dir: Path, output_path: Path) -> None:
        subprocess.run(
            ["tar", "--zstd", "-cf", str(output_path),
             "-C", str(source_dir), "."],
            check=True, capture_output=True,
        )

    def list_files(self, archive_path: Path) -> List[str]:
        r = subprocess.run(
            ["tar", "--zstd", "-tf", str(archive_path)],
            check=True, capture_output=True, text=True,
        )
        return [_normalize_tar_name(l) for l in r.stdout.strip().splitlines() if l]

    def check_file_exists(self, archive_path: Path, filename: str) -> bool:
        return filename in set(self.list_files(archive_path))

    def extract_single(self, archive_path: Path, filename: str) -> bytes:
        for name in ["./" + filename, filename]:
            r = subprocess.run(
                ["tar", "--zstd", "-xf", str(archive_path), "-O", name],
                capture_output=True,
            )
            if r.returncode == 0:
                return r.stdout
        raise FileNotFoundError(f"{filename} not in {archive_path}")


class TarZstPipe(ArchiveFormat):
    """tar.zst using pipe approach (cross-platform: Linux + macOS)."""
    name = "tar.zst (pipe)"
    extension = ".pipe.tar.zst"

    def create(self, source_dir: Path, output_path: Path) -> None:
        with open(output_path, "wb") as out:
            tar_proc = subprocess.Popen(
                ["tar", "-cf", "-", "-C", str(source_dir), "."],
                stdout=subprocess.PIPE,
            )
            zstd_proc = subprocess.Popen(
                ["zstd", "-q"],
                stdin=tar_proc.stdout, stdout=out,
            )
            tar_proc.stdout.close()
            zstd_proc.wait()
            tar_proc.wait()

    def list_files(self, archive_path: Path) -> List[str]:
        zstd_proc = subprocess.Popen(
            ["zstd", "-dc", str(archive_path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        tar_proc = subprocess.Popen(
            ["tar", "-tf", "-"],
            stdin=zstd_proc.stdout,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        zstd_proc.stdout.close()
        out, _ = tar_proc.communicate()
        return [_normalize_tar_name(l) for l in out.strip().splitlines() if l]

    def check_file_exists(self, archive_path: Path, filename: str) -> bool:
        return filename in set(self.list_files(archive_path))

    def extract_single(self, archive_path: Path, filename: str) -> bytes:
        for name in ["./" + filename, filename]:
            zstd_proc = subprocess.Popen(
                ["zstd", "-dc", str(archive_path)],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
            tar_proc = subprocess.Popen(
                ["tar", "-xf", "-", "-O", name],
                stdin=zstd_proc.stdout,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            zstd_proc.stdout.close()
            out, _ = tar_proc.communicate()
            if tar_proc.returncode == 0:
                return out
        raise FileNotFoundError(f"{filename} not in {archive_path}")


class ZipPython(ArchiveFormat):
    name = "zip (Python)"
    extension = ".zip"

    def create(self, source_dir: Path, output_path: Path) -> None:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, fnames in os.walk(source_dir):
                for fn in fnames:
                    fp = Path(root) / fn
                    arcname = str(fp.relative_to(source_dir))
                    zf.write(fp, arcname)

    def list_files(self, archive_path: Path) -> List[str]:
        with zipfile.ZipFile(archive_path, "r") as zf:
            return zf.namelist()

    def check_file_exists(self, archive_path: Path, filename: str) -> bool:
        with zipfile.ZipFile(archive_path, "r") as zf:
            return filename in zf.namelist()

    def extract_single(self, archive_path: Path, filename: str) -> bytes:
        with zipfile.ZipFile(archive_path, "r") as zf:
            return zf.read(filename)


class ZipCLI(ArchiveFormat):
    name = "zip (CLI)"
    extension = ".cli.zip"

    def create(self, source_dir: Path, output_path: Path) -> None:
        subprocess.run(
            ["zip", "-r", "-q", str(output_path), "."],
            cwd=str(source_dir),
            check=True, capture_output=True,
        )

    def list_files(self, archive_path: Path) -> List[str]:
        r = subprocess.run(
            ["unzip", "-l", str(archive_path)],
            check=True, capture_output=True, text=True,
        )
        lines = r.stdout.strip().splitlines()
        result = []
        for line in lines[3:-2]:  # skip header/footer
            parts = line.split()
            if len(parts) >= 4:
                result.append(parts[-1])
        return result

    def check_file_exists(self, archive_path: Path, filename: str) -> bool:
        r = subprocess.run(
            ["unzip", "-l", str(archive_path)],
            check=True, capture_output=True, text=True,
        )
        return filename in r.stdout

    def extract_single(self, archive_path: Path, filename: str) -> bytes:
        r = subprocess.run(
            ["unzip", "-p", str(archive_path), filename],
            check=True, capture_output=True,
        )
        return r.stdout


# ---------------------------------------------------------------------------
# Timing engine
# ---------------------------------------------------------------------------

def time_operation(func, iterations: int, warmup: int) -> List[int]:
    """Run func with warmup, then return list of elapsed nanoseconds."""
    for _ in range(warmup):
        func()
    times = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        times.append(elapsed)
    return times


@dataclass
class BenchResult:
    format_name: str
    operation: str
    times_ns: List[int]

    @property
    def mean_us(self) -> float:
        return statistics.mean(self.times_ns) / 1000

    @property
    def median_us(self) -> float:
        return statistics.median(self.times_ns) / 1000

    @property
    def stddev_us(self) -> float:
        return statistics.stdev(self.times_ns) / 1000 if len(self.times_ns) > 1 else 0

    @property
    def min_us(self) -> float:
        return min(self.times_ns) / 1000

    @property
    def p5_us(self) -> float:
        s = sorted(self.times_ns)
        idx = max(0, int(len(s) * 0.05))
        return s[idx] / 1000

    @property
    def p95_us(self) -> float:
        s = sorted(self.times_ns)
        idx = min(len(s) - 1, int(len(s) * 0.95))
        return s[idx] / 1000


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_benchmarks(
    data: TestData,
    formats: List[ArchiveFormat],
    ops: List[str],
    iterations: int,
    warmup: int,
    tmp_dir: Path,
) -> Tuple[List[BenchResult], Dict[str, int]]:
    """Run all benchmarks. Returns (results, archive_sizes)."""

    archives_dir = tmp_dir / "archives"
    archives_dir.mkdir(exist_ok=True)
    archive_paths: Dict[str, Path] = {}
    archive_sizes: Dict[str, int] = {}

    # Create archives for each format
    print("\n--- Creating test archives ---")
    for fmt in formats:
        path = archives_dir / f"bench{fmt.extension}"
        print(f"  Creating {fmt.name} ... ", end="", flush=True)
        start = time.perf_counter()
        fmt.create(data.source_dir, path)
        elapsed = time.perf_counter() - start
        size = path.stat().st_size
        archive_paths[fmt.name] = path
        archive_sizes[fmt.name] = size
        print(f"{size // 1024}KB ({elapsed:.3f}s)")

    results: List[BenchResult] = []

    for fmt in formats:
        path = archive_paths[fmt.name]
        print(f"\nBenchmarking {fmt.name}:")

        if "list" in ops:
            print(f"  list_files ({warmup}w + {iterations}i) ... ", end="", flush=True)
            times = time_operation(
                lambda p=path, f=fmt: f.list_files(p),
                iterations, warmup,
            )
            r = BenchResult(fmt.name, "list_files", times)
            results.append(r)
            print(f"median {r.median_us:.0f}us")

        if "exists" in ops:
            print(f"  check_exists ({warmup}w + {iterations}i) ... ", end="", flush=True)
            times = time_operation(
                lambda p=path, f=fmt, s=data.sample_file: f.check_file_exists(p, s),
                iterations, warmup,
            )
            r = BenchResult(fmt.name, "check_exists", times)
            results.append(r)
            print(f"median {r.median_us:.0f}us")

        if "extract" in ops:
            print(f"  extract_single ({warmup}w + {iterations}i) ... ", end="", flush=True)
            times = time_operation(
                lambda p=path, f=fmt, s=data.sample_file: f.extract_single(p, s),
                iterations, warmup,
            )
            r = BenchResult(fmt.name, "extract_single", times)
            results.append(r)
            print(f"median {r.median_us:.0f}us")

        if "create" in ops:
            out_path = archives_dir / f"create_bench{fmt.extension}"
            print(f"  create ({warmup}w + {iterations}i) ... ", end="", flush=True)
            times = time_operation(
                lambda o=out_path, f=fmt, d=data.source_dir: f.create(d, o),
                iterations, warmup,
            )
            r = BenchResult(fmt.name, "create", times)
            results.append(r)
            print(f"median {r.median_us:.0f}us")

    return results, archive_sizes


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_us(val: float) -> str:
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f}s"
    if val >= 1000:
        return f"{val / 1000:.1f}ms"
    return f"{val:.0f}us"


def print_results(
    results: List[BenchResult],
    sizes: Dict[str, int],
    data: TestData,
    iterations: int,
) -> None:
    print("\n" + "=" * 70)
    print("ARCHIVE FORMAT BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Test data: {len(data.archive_sources)} source archives, "
          f"{len(data.files)} files, "
          f"{data.total_bytes / 1024:.0f}KB uncompressed")
    print(f"Iterations: {iterations}")
    print()

    # Sizes table
    if sizes:
        print("--- Archive Sizes ---")
        print(f"  {'Format':<25} {'Size':>10} {'Ratio':>8}")
        print(f"  {'-' * 25} {'-' * 10} {'-' * 8}")
        ref = data.total_bytes
        for name, sz in sorted(sizes.items(), key=lambda x: x[1], reverse=True):
            ratio = sz / ref if ref else 0
            print(f"  {name:<25} {sz // 1024:>7}KB {ratio:>7.2f}x")
        print(f"  {'(uncompressed)':<25} {ref // 1024:>7}KB {1.0:>7.2f}x")
        print()

    # Group results by operation
    ops_seen: List[str] = []
    for r in results:
        if r.operation not in ops_seen:
            ops_seen.append(r.operation)

    for op in ops_seen:
        op_results = [r for r in results if r.operation == op]
        op_results.sort(key=lambda r: r.median_us)

        label = {
            "list_files": "List All Files",
            "check_exists": "Check File Exists",
            "extract_single": "Extract Single File",
            "create": "Create Archive",
        }.get(op, op)

        print(f"--- {label} ---")
        print(f"  {'Format':<25} {'Median':>10} {'Mean':>10} "
              f"{'StdDev':>10} {'Min':>10} {'p5':>10} {'p95':>10}")
        print(f"  {'-' * 25} {'-' * 10} {'-' * 10} "
              f"{'-' * 10} {'-' * 10} {'-' * 10} {'-' * 10}")
        for r in op_results:
            print(f"  {r.format_name:<25} "
                  f"{format_us(r.median_us):>10} "
                  f"{format_us(r.mean_us):>10} "
                  f"{format_us(r.stddev_us):>10} "
                  f"{format_us(r.min_us):>10} "
                  f"{format_us(r.p5_us):>10} "
                  f"{format_us(r.p95_us):>10}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_project_root(start: Optional[Path] = None) -> Path:
    """Walk up from start to find directory containing .aitask-scripts/."""
    p = (start or Path(__file__)).resolve()
    while p != p.parent:
        if (p / ".aitask-scripts").is_dir():
            return p
        p = p.parent
    print("ERROR: Could not find project root (no .aitask-scripts/ found)",
          file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark archive formats for aitasks")
    parser.add_argument("--iterations", "-n", type=int, default=ITERATIONS_DEFAULT,
                        help=f"Timed iterations (default: {ITERATIONS_DEFAULT})")
    parser.add_argument("--warmup", "-w", type=int, default=WARMUP_DEFAULT,
                        help=f"Warmup iterations (default: {WARMUP_DEFAULT})")
    parser.add_argument("--formats", nargs="+",
                        choices=["tar", "tar.gz", "tar.zst", "tar.xz", "zip"],
                        help="Only benchmark these formats (default: all available)")
    parser.add_argument("--operations", nargs="+",
                        choices=["list", "exists", "extract", "create", "size"],
                        help="Only benchmark these operations (default: all)")
    parser.add_argument("--project-root", type=Path, default=None,
                        help="Project root (auto-detected if omitted)")
    args = parser.parse_args()

    root = args.project_root or find_project_root()
    print(f"Project root: {root}")

    caps = detect_capabilities()
    print(caps.summary())

    selected_ops = args.operations or ["list", "exists", "extract", "create", "size"]

    with tempfile.TemporaryDirectory(prefix="aitask_bench_") as tmp:
        tmp_dir = Path(tmp)
        data = TestData.prepare(root, tmp_dir)

        # Build format list
        all_formats: List[ArchiveFormat] = []

        want = args.formats  # None means all

        if not want or "tar" in want:
            all_formats.append(TarPython("tar (Python)", ".tar", "w:", "r:"))
        if not want or "tar.gz" in want:
            all_formats.append(TarPython("tar.gz (Python)", ".tar.gz", "w:gz", "r:gz"))
            all_formats.append(TarGzCLI())
        if not want or "tar.zst" in want:
            if caps.has_zstd_cli:
                if caps.has_tar_zstd:
                    all_formats.append(TarZstNative())
                all_formats.append(TarZstPipe())
            else:
                print("WARN: zstd CLI not found, skipping tar.zst")
        if not want or "tar.xz" in want:
            all_formats.append(TarPython("tar.xz (Python)", ".tar.xz", "w:xz", "r:xz"))
        if not want or "zip" in want:
            all_formats.append(ZipPython())
            if caps.has_zip_cli and caps.has_unzip_cli:
                all_formats.append(ZipCLI())
            else:
                print("WARN: zip/unzip CLI not found, skipping zip CLI variant")

        if not all_formats:
            print("ERROR: No formats to benchmark", file=sys.stderr)
            sys.exit(1)

        results, sizes = run_benchmarks(
            data, all_formats, selected_ops,
            args.iterations, args.warmup, tmp_dir,
        )

        print_results(results, sizes, data, args.iterations)


if __name__ == "__main__":
    main()
