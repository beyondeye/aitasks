# Archive Format Benchmark Results

Run: 2026-03-26 | Python 3.14.3 | Linux 6.18.13 | 50 iterations, 3 warmup

## Test Data

- 10 source archives (5 task bundles + 5 plan bundles)
- 1039 markdown files, 3286KB uncompressed
- Real production data from `aitasks/archived/_b0/old[0-4].tar.gz` and `aiplans/archived/_b0/old[0-4].tar.gz`

## Archive Sizes

| Format | Size | Ratio |
|--------|-----:|------:|
| tar (uncompressed) | 5110KB | 1.56x |
| zip (CLI) | 1591KB | 0.48x |
| zip (Python) | 1527KB | 0.47x |
| tar.gz (Python) | 1019KB | 0.31x |
| tar.gz (CLI) | 993KB | 0.30x |
| tar.zst (CLI) | 955KB | 0.29x |
| tar.xz (Python) | 724KB | 0.22x |

## List All Files (median)

| Format | Median | vs tar.gz (Python) |
|--------|-------:|-------------------:|
| zip (Python) | 1.3ms | **14x faster** |
| zip (CLI) | 3.4ms | 5.3x faster |
| tar.zst (CLI) | 5.5ms | 3.3x faster |
| tar.gz (CLI) | 10.8ms | 1.7x faster |
| tar.gz (Python) | 18.0ms | baseline |
| tar (Python) | 20.1ms | 1.1x slower |
| tar.xz (Python) | 41.2ms | 2.3x slower |

## Check File Exists (median)

| Format | Median | vs tar.gz (Python) |
|--------|-------:|-------------------:|
| zip (Python) | 1.3ms | **14x faster** |
| zip (CLI) | 3.0ms | 6x faster |
| tar.zst (CLI) | 5.5ms | 3.3x faster |
| tar.gz (CLI) | 10.9ms | 1.7x faster |
| tar.gz (Python) | 18.1ms | baseline |
| tar (Python) | 20.3ms | 1.1x slower |
| tar.xz (Python) | 41.2ms | 2.3x slower |

## Extract Single File (median)

| Format | Median | vs tar.gz (Python) |
|--------|-------:|-------------------:|
| zip (CLI) | 746us | **34x faster** |
| zip (Python) | 1.3ms | 20x faster |
| tar.zst (CLI) | 5.5ms | 4.6x faster |
| tar.gz (CLI) | 10.7ms | 2.4x faster |
| tar (Python) | 20.1ms | 1.3x faster |
| tar.gz (Python) | 25.5ms | baseline |
| tar.xz (Python) | 57.2ms | 2.2x slower |

## Create Archive (median)

| Format | Median | vs tar.gz (CLI) |
|--------|-------:|----------------:|
| tar.zst (CLI) | 19.6ms | **4.2x faster** |
| tar (Python) | 44.2ms | 1.9x faster |
| zip (CLI) | 65.9ms | 1.2x faster |
| zip (Python) | 74.2ms | 1.1x faster |
| tar.gz (CLI) | 82.1ms | baseline |
| tar.gz (Python) | 134.6ms | 1.6x slower |
| tar.xz (Python) | 910.0ms | 11x slower |

## Key Takeaways

1. **zip is the clear winner for listing and existence checks** (the main pain point). The zip central directory allows reading the file list without decompressing any file data. This is 14x faster than tar.gz with Python, and 5x faster via CLI.

2. **tar.zst is the best tar-family format**. It's 2x faster than tar.gz for all operations, has slightly better compression (0.29x vs 0.30x), and is 4x faster to create. On Linux, GNU tar supports `--zstd` natively. On macOS, a pipe through the `zstd` CLI works.

3. **zip's compression is ~50% worse than tar.gz/tar.zst** (0.47x vs 0.29-0.31x ratio). For markdown files, this means zip archives are about 1.6x larger. Given the archives are small (50-160KB), this absolute difference (~30-80KB per bundle) is negligible.

4. **tar.xz has the best compression** (0.22x) but is prohibitively slow: 11x slower to create and 2.3x slower to read compared to tar.gz. Not recommended.

5. **Python tarfile is consistently slower than tar CLI** for the same format (1.5-2x). This is expected overhead from Python's pure-Python gzip implementation vs the optimized C library used by the tar command.

6. **For the aitasks use case** (frequent listing/existence checks, infrequent creates), **zip is the optimal choice** despite worse compression. The 14x speedup on the critical path (checking if a file exists in an archive) far outweighs the minor storage increase.

## Recommendation

**Primary recommendation: zip format** for the numbered archive bundles.
- Fastest for the bottleneck operations (list, exists, extract)
- Cross-platform: Python `zipfile` is stdlib, no external dependencies
- Acceptable compression for small markdown files
- Central directory enables O(1) file listing without decompression

**Alternative: tar.zst** if compression ratio is prioritized and the 4x speed gain over tar.gz is sufficient. Requires `zstd` CLI on the system (available in all major Linux distros and Homebrew on macOS).
