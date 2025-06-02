#!/usr/bin/env python3
"""
svg_optimize.py - Minimal SVGO wrapper with project context support

This script optimizes SVG files using SVGO with automatic project-aware file naming.

Usage modes:
1. Build system mode (PROJECT_NAME environment variable set):
   python svg_optimize.py
   → Uses project naming conventions automatically

2. Standalone mode (explicit arguments):
   python svg_optimize.py input.svg output.svg
   → Uses specified files

Features:
- Project-aware file naming (bwv1006_*, bwv543_*, etc.)
- Automatic output directory creation
- File size reporting with reduction percentage
- Graceful fallback when _scripts_utils not available
"""

import subprocess
import sys
from pathlib import Path

def optimize_svg(input_file, output_file):
    """
    Core SVG optimization logic using SVGO.
    
    Args:
        input_file (str): Path to input SVG file
        output_file (str): Path to output optimized SVG file
        
    Returns:
        bool: True if optimization succeeded, False otherwise
    """
    input_path = Path(input_file)
    output_path = Path(output_file)
    
    print(f"🎯 Optimizing SVG: {input_path.name}")
    print(f"   📤 Input: {input_path}")
    print(f"   📥 Output: {output_path}")
    
    # Validate input file exists
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        return False
    
    # Get original size for comparison
    original_size = input_path.stat().st_size
    print(f"   📏 Original size: {original_size:,} bytes")
    
    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Run SVGO optimization
    print(f"   🔧 Running SVGO optimization...")
    result = subprocess.run([
        'npx', 'svgo', str(input_path), '--output', str(output_path)
    ], capture_output=True, text=True)
    
    # Check if optimization succeeded
    if result.returncode == 0 and output_path.exists():
        optimized_size = output_path.stat().st_size
        reduction = ((original_size - optimized_size) / original_size) * 100
        
        print(f"✅ Optimization complete: {output_path.name}")
        print(f"   📊 Size: {original_size:,} → {optimized_size:,} bytes ({reduction:.1f}% reduction)")
        return True
    else:
        print(f"❌ SVGO optimization failed:")
        if result.stderr:
            print(f"   Error: {result.stderr}")
        return False

def main():
    """Main function handling both build system and standalone modes."""
    
    try:
        # Try to use project context system
        from _scripts_utils import get_io_files
        
        input_file, output_file = get_io_files(
            "Optimize SVG files using SVGO",
            "{project}_no_hrefs_in_tabs_swellable.svg",
            "exports/{project}_optimized.svg"
        )
        
    except ImportError:
        # Fallback for standalone use without _scripts_utils
        if len(sys.argv) != 3:
            print("Usage: python svg_optimize.py <input.svg> <output.svg>")
            print("")
            print("Description: Optimize SVG files using SVGO")
            print("")
            print("Examples:")
            print("  python svg_optimize.py score.svg score_optimized.svg")
            print("  python svg_optimize.py input/*.svg output/")
            print("")
            print("Or run from build system with PROJECT_NAME environment variable")
            sys.exit(1)
        
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    
    # Run the optimization
    success = optimize_svg(input_file, output_file)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()