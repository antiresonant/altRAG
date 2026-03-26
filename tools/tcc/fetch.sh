#!/usr/bin/env bash
# fetch.sh — Download Tiny C Compiler (TCC) for the current platform
#
# TCC is a ~100KB self-contained C compiler that compiles C99.
# Bundling it makes scan.c compilable on any machine without
# requiring a system-installed compiler.
#
# Supported platforms: Linux x86_64, Windows x86_64
# macOS: use system clang (xcode-select --install)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM="$(uname -s)"
ARCH="$(uname -m)"

# Use $TMPDIR (macOS/Linux), $TEMP (Windows/MSYS), or /tmp as fallback
WORK_DIR="${TMPDIR:-${TEMP:-/tmp}}"

cleanup() {
    rm -f "$WORK_DIR/tcc.tar.gz" "$WORK_DIR/tcc.zip" 2>/dev/null || true
}
trap cleanup EXIT

echo "[altRAG] Fetching TCC for $PLATFORM-$ARCH..."

case "$PLATFORM" in
    Linux)
        if [ "$ARCH" != "x86_64" ]; then
            echo "TCC prebuilt binary is for x86_64. For $ARCH, build TCC from source:"
            echo "  git clone https://repo.or.cz/tinycc.git && cd tinycc && ./configure && make"
            exit 1
        fi
        TCC_URL="https://download.savannah.gnu.org/releases/tinycc/tcc-0.9.27-linux-x86_64-bin.tar.gz"
        echo "Downloading: $TCC_URL"
        curl -fSL "$TCC_URL" -o "$WORK_DIR/tcc.tar.gz"
        tar -xzf "$WORK_DIR/tcc.tar.gz" -C "$SCRIPT_DIR" --strip-components=1
        chmod +x "$SCRIPT_DIR/tcc"
        echo "[altRAG] TCC installed: $SCRIPT_DIR/tcc"
        ;;

    MINGW*|MSYS*|CYGWIN*)
        TCC_URL="https://download.savannah.gnu.org/releases/tinycc/tcc-0.9.27-win64-bin.zip"
        echo "Downloading: $TCC_URL"
        curl -fSL "$TCC_URL" -o "$WORK_DIR/tcc.zip"
        unzip -o "$WORK_DIR/tcc.zip" -d "$SCRIPT_DIR"
        echo "[altRAG] TCC installed: $SCRIPT_DIR/tcc.exe"
        ;;

    Darwin)
        echo "macOS: TCC has limited macOS support."
        echo "Use system clang instead (usually pre-installed):"
        echo "  xcode-select --install"
        echo ""
        echo "Or install GCC via Homebrew:"
        echo "  brew install gcc"
        exit 0
        ;;

    *)
        echo "Unknown platform: $PLATFORM"
        echo "Download TCC manually from: https://bellard.org/tcc/"
        exit 1
        ;;
esac

# verify
if [ -f "$SCRIPT_DIR/tcc" ] || [ -f "$SCRIPT_DIR/tcc.exe" ]; then
    echo "[altRAG] TCC ready. Run build.sh to compile scan.c."
else
    echo "[altRAG] Warning: TCC binary not found after extraction."
    echo "         Check $SCRIPT_DIR for extracted files."
fi
