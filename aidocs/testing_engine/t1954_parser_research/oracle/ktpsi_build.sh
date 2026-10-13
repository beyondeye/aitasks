#!/usr/bin/env bash
# ktpsi_build.sh - compile oracle/KtPsiOracle.java against the kotlinc
# release's own compiler jar into the git-ignored .ktpsi/ (t1954_3 `ktpsi`).
#
#   oracle/ktpsi_build.sh          uses $T1954_KOTLINC (the kotlinc binary of
#                                  an unpacked kotlinc release zip)
# Needs javac (JDK 17+). Nothing is installed system-wide.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kc="${T1954_KOTLINC:?set T1954_KOTLINC to the kotlinc binary of an unpacked kotlinc release}"
lib="$(cd "$(dirname "$kc")/../lib" && pwd)"
cp="$lib/kotlin-compiler.jar:$lib/kotlin-stdlib.jar:$lib/kotlinx-coroutines-core-jvm.jar"
rm -rf "$here/.ktpsi"
mkdir -p "$here/.ktpsi"
javac -nowarn -cp "$cp" -d "$here/.ktpsi" "$here/oracle/KtPsiOracle.java"
printf '%s\n' "$cp" > "$here/.ktpsi/CLASSPATH"
echo "KTPSI:$here/.ktpsi|kotlinc=$("$kc" -version 2>&1 | tail -1)"
