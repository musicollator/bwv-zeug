#!/bin/bash
set -e

# Parse script path
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/$(basename "$0")"

# Validate arguments
if [ $# -eq 0 ]; then
    echo "Usage: $SCRIPT_PATH <command> [args...]"
    echo ""
    echo "Examples:"
    echo "  $SCRIPT_PATH invoke --search-root /Users/christophe.thiebaud/github.com/musicollator/bwv-zeug/invoke clean all"
    echo "  $SCRIPT_PATH $SCRIPT_DIR/git-autopush.sh 'update message'"
    exit 1
fi

# Capture build command and arguments
BUILD_CMD="$1"
shift
BUILD_ARGS=("$@")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

START_DIR=$(pwd)
> ALL.LOG
> ERR.LOG

echo -e "${BLUE}🎼 BWV Build Pipeline${NC}"
echo "==============================================="
echo "📁 Starting directory: $START_DIR"
echo "🔨 Build command: $BUILD_CMD ${BUILD_ARGS[*]}"
echo "📝 Logs: ALL.LOG (stdout) and ERR.LOG (stderr)"
echo ""

# Check if command exists
echo "🧪 Testing build command availability..."
if ! command -v "$BUILD_CMD" >/dev/null 2>&1; then
    echo -e "${RED}❌ Build command '$BUILD_CMD' not found in PATH${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Build command available${NC}"
echo ""

# Discover BWV directories
BWV_DIRS=($(find . -maxdepth 1 -type d | grep -E "^\./bwv[0-9]+$" | sort))
if [ ${#BWV_DIRS[@]} -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No BWV directories found${NC}"
    exit 0
fi

echo -e "${GREEN}Found ${#BWV_DIRS[@]} BWV directories:${NC}"
for dir in "${BWV_DIRS[@]}"; do
    echo "  $(basename "$dir")"
done
echo ""

SUCCESSFUL_BUILDS=()
FAILED_BUILDS=()

for BWV_DIR in "${BWV_DIRS[@]}"; do
    BWV_NAME=$(basename "$BWV_DIR")

    echo -e "${BLUE}🎵 $BWV_NAME${NC}"
    echo "============================================="

    if ! cd "$BWV_DIR"; then
        echo -e "${RED}❌ Failed to enter directory: $BWV_DIR${NC}"
        FAILED_BUILDS+=("$BWV_NAME (directory access)")
        continue
    fi

    echo "" >> "$START_DIR/ALL.LOG"
    echo "========================================" >> "$START_DIR/ALL.LOG"
    echo "🎵 $BWV_NAME" >> "$START_DIR/ALL.LOG"
    echo "📅 $(date)" >> "$START_DIR/ALL.LOG"
    echo "🔨 Command: $BUILD_CMD ${BUILD_ARGS[*]}" >> "$START_DIR/ALL.LOG"
    echo "========================================" >> "$START_DIR/ALL.LOG"

    echo "  🔨 Running: $BUILD_CMD ${BUILD_ARGS[*]}"

    stdbuf -oL -eL timeout 300 "$BUILD_CMD" "${BUILD_ARGS[@]}" \
      > >(tee -a "$START_DIR/ALL.LOG") \
      2> >(tee -a "$START_DIR/ERR.LOG" >&2)

    STATUS=$?
    if [ $STATUS -eq 0 ]; then
      echo -e "${GREEN}  ✅ Build completed successfully${NC}"
      SUCCESSFUL_BUILDS+=("$BWV_NAME")
    elif [ $STATUS -eq 124 ]; then
      echo -e "${RED}  ⏰ Build timed out (300s) for $BWV_NAME${NC}"
      FAILED_BUILDS+=("$BWV_NAME (timeout)")
    else
      echo -e "${RED}  ❌ Build failed${NC}"
      FAILED_BUILDS+=("$BWV_NAME (failed)")
    fi

    cd "$START_DIR"
    echo ""
done

# Summary
echo ""
echo "==============================================="
echo -e "${BLUE}🎼 Build Summary${NC}"
echo "==============================================="

if [ ${#SUCCESSFUL_BUILDS[@]} -gt 0 ]; then
    echo -e "${GREEN}✅ Successful builds (${#SUCCESSFUL_BUILDS[@]}):${NC}"
    for build in "${SUCCESSFUL_BUILDS[@]}"; do echo "  $build"; done
    echo ""
fi

if [ ${#FAILED_BUILDS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Failed builds (${#FAILED_BUILDS[@]}):${NC}"
    for build in "${FAILED_BUILDS[@]}"; do echo "  $build"; done
    echo ""
fi

echo "📊 Statistics:"
echo "  Total BWV directories: ${#BWV_DIRS[@]}"
echo "  Successful builds: ${#SUCCESSFUL_BUILDS[@]}"
echo "  Failed builds: ${#FAILED_BUILDS[@]}"

if [ ${#SUCCESSFUL_BUILDS[@]} -eq ${#BWV_DIRS[@]} ]; then
    echo -e "${GREEN}🎉 All builds completed successfully!${NC}"
    exit 0
elif [ ${#SUCCESSFUL_BUILDS[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Some builds failed. Check ERR.LOG for details.${NC}"
    exit 1
else
    echo -e "${RED}💥 All builds failed. Check ERR.LOG for details.${NC}"
    exit 1
fi
