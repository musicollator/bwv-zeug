#!/bin/bash

# build_every_bwv.sh
# 
# Build script for all BWV projects
# Processes each subdirectory starting with "bwv" (case-sensitive)
# and runs the build pipeline, logging all output
#
# Usage: ./build_every_bwv.sh <build_command>
# Example: ./build_every_bwv.sh "invoke --search-root /Users/christophe.thiebaud/github.com/musicollator/bwv-zeug/invoke"

set -e  # Exit on any error

# Check if build command was provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <build_command>"
    echo ""
    echo "Examples:"
    echo "  $0 'invoke --search-root /Users/christophe.thiebaud/github.com/musicollator/bwv-zeug/invoke'  # Full invoke command"
    echo "  $0 make                                                                                       # If using make instead"
    echo ""
    exit 1
fi

# Get the build command from the first argument
BUILD_CMD="$1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the starting directory
START_DIR=$(pwd)

# Initialize log files
> ALL.LOG  # Clear/create ALL.LOG
> ERR.LOG  # Clear/create ERR.LOG

echo -e "${BLUE}🎼 BWV Build Pipeline${NC}"
echo "==============================================="
echo "📁 Starting directory: $START_DIR"
echo "🔨 Build command: $BUILD_CMD"
echo "📝 Logs: ALL.LOG (stdout) and ERR.LOG (stderr)"
echo ""

# Test if the build command is available
echo "🧪 Testing build command availability..."
if ! command -v ${BUILD_CMD%% *} >/dev/null 2>&1; then
    echo -e "${RED}❌ Build command '${BUILD_CMD%% *}' not found in PATH${NC}"
    echo "   Make sure the command is installed and available"
    exit 1
fi
echo -e "${GREEN}✅ Build command available${NC}"
echo ""

# Find all directories starting with "bwv" followed by numbers only
BWV_DIRS=($(find . -maxdepth 1 -type d | grep -E "^\./bwv[0-9]+$" | sort))

if [ ${#BWV_DIRS[@]} -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No BWV directories found${NC}"
    exit 0
fi

echo -e "${GREEN}Found ${#BWV_DIRS[@]} BWV directories:${NC}"
for dir in "${BWV_DIRS[@]}"; do
    echo "   $(basename "$dir")"
done
echo ""

# Track build results
SUCCESSFUL_BUILDS=()
FAILED_BUILDS=()

# Process each BWV directory
for BWV_DIR in "${BWV_DIRS[@]}"; do
    BWV_NAME=$(basename "$BWV_DIR")
    
    echo -e "${BLUE}🎵 Processing: $BWV_NAME${NC}"
    echo "============================================="
    
    # Change to BWV directory
    if ! cd "$BWV_DIR"; then
        echo -e "${RED}❌ Failed to enter directory: $BWV_DIR${NC}"
        FAILED_BUILDS+=("$BWV_NAME (directory access)")
        continue
    fi
    
    # Log the start of this build
    echo "" >> "$START_DIR/ALL.LOG"
    echo "========================================" >> "$START_DIR/ALL.LOG"
    echo "🎵 Building: $BWV_NAME" >> "$START_DIR/ALL.LOG"
    echo "📅 $(date)" >> "$START_DIR/ALL.LOG"
    echo "========================================" >> "$START_DIR/ALL.LOG"
    
    echo "" >> "$START_DIR/ERR.LOG"
    echo "========================================" >> "$START_DIR/ERR.LOG"
    echo "🎵 Building: $BWV_NAME (ERRORS)" >> "$START_DIR/ERR.LOG"
    echo "📅 $(date)" >> "$START_DIR/ERR.LOG"
    echo "========================================" >> "$START_DIR/ERR.LOG"
    
    # Run clean command with timeout
    echo "   🧹 Running clean..."
    if timeout 60 $BUILD_CMD clean >> "$START_DIR/ALL.LOG" 2>> "$START_DIR/ERR.LOG"; then
        echo "   ✅ Clean completed"
    elif [ $? -eq 124 ]; then
        echo -e "${RED}   ⏰ Clean timed out (60s) for $BWV_NAME${NC}"
        FAILED_BUILDS+=("$BWV_NAME (clean timeout)")
        cd "$START_DIR"
        continue
    else
        echo -e "${RED}   ❌ Clean failed for $BWV_NAME${NC}"
        FAILED_BUILDS+=("$BWV_NAME (clean)")
        cd "$START_DIR"
        continue
    fi
    
    # Run build command with timeout
    echo "   🔨 Running build..."
    if timeout 300 $BUILD_CMD all >> "$START_DIR/ALL.LOG" 2>> "$START_DIR/ERR.LOG"; then
        echo -e "${GREEN}   ✅ Build completed successfully${NC}"
        SUCCESSFUL_BUILDS+=("$BWV_NAME")
    elif [ $? -eq 124 ]; then
        echo -e "${RED}   ⏰ Build timed out (300s) for $BWV_NAME${NC}"
        FAILED_BUILDS+=("$BWV_NAME (build timeout)")
    else
        echo -e "${RED}   ❌ Build failed${NC}"
        FAILED_BUILDS+=("$BWV_NAME (build)")
    fi
    
    # Return to starting directory
    cd "$START_DIR"
    echo ""
done

# Summary report
echo ""
echo "==============================================="
echo -e "${BLUE}🎼 Build Summary${NC}"
echo "==============================================="

if [ ${#SUCCESSFUL_BUILDS[@]} -gt 0 ]; then
    echo -e "${GREEN}✅ Successful builds (${#SUCCESSFUL_BUILDS[@]}):${NC}"
    for build in "${SUCCESSFUL_BUILDS[@]}"; do
        echo "   $build"
    done
    echo ""
fi

if [ ${#FAILED_BUILDS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Failed builds (${#FAILED_BUILDS[@]}):${NC}"
    for build in "${FAILED_BUILDS[@]}"; do
        echo "   $build"
    done
    echo ""
fi

# Final statistics
TOTAL_DIRS=${#BWV_DIRS[@]}
SUCCESS_COUNT=${#SUCCESSFUL_BUILDS[@]}
FAIL_COUNT=${#FAILED_BUILDS[@]}

echo "📊 Statistics:"
echo "   Total BWV directories: $TOTAL_DIRS"
echo "   Successful builds: $SUCCESS_COUNT"
echo "   Failed builds: $FAIL_COUNT"

if [ $SUCCESS_COUNT -eq $TOTAL_DIRS ]; then
    echo -e "${GREEN}🎉 All builds completed successfully!${NC}"
    exit 0
elif [ $SUCCESS_COUNT -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Some builds failed. Check ERR.LOG for details.${NC}"
    exit 1
else
    echo -e "${RED}💥 All builds failed. Check ERR.LOG for details.${NC}"
    exit 1
fi