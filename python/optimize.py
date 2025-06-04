#!/usr/bin/env python3
"""
optimize.py - SVG optimization using SVGO

This script optimizes SVG files using SVGO with automatic file size reporting
and reduction percentage calculations.

Features:
- SVG optimization using SVGO (Node.js package)
- File size reporting with reduction percentage
- Automatic output directory creation
- Command line interface with required input/output arguments
"""

import subprocess
import sys
import argparse
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
    
    try:
        result = subprocess.run([
            'npx', 'svgo', str(input_path), '--output', str(output_path)
        ], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        print(f"❌ SVGO optimization timed out after 60 seconds")
        return False
    except FileNotFoundError:
        print(f"❌ SVGO not found. Please install with: npm install -g svgo")
        return False
    
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
        if result.stdout:
            print(f"   Output: {result.stdout}")
        return False

def setup_argument_parser():
    """Setup command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Optimize SVG files using SVGO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python optimize.py -i score.svg -o score_optimized.svg
  python optimize.py --input music.svg --output exports/music_optimized.svg

Requirements:
  - Node.js and npm installed
  - SVGO package: npm install -g svgo
        """
    )
    
    parser.add_argument('-i', '--input', 
                       required=True,
                       help='Input SVG file path (required)')
    
    parser.add_argument('-o', '--output',
                       required=True, 
                       help='Output SVG file path (required)')
    
    return parser.parse_args()

def main():
    """Main function with command line argument support."""
    
    print("🚀 SVG Optimization Pipeline")
    print("=" * 30)
    
    # Parse arguments
    args = setup_argument_parser()
    
    input_file = args.input
    output_file = args.output
    
    print(f"📄 Processing file:")
    print(f"   Input: {input_file}")
    print(f"   Output: {output_file}")
    print()
    
    # Validate input file exists
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        print("💡 Usage: python optimize.py -i INPUT.svg -o OUTPUT.svg")
        return 1
    
    # Run the optimization
    try:
        success = optimize_svg(input_file, output_file)
        
        if success:
            print("\n🎉 Optimization completed successfully!")
            return 0
        else:
            print("\n💥 Optimization failed")
            return 1
            
    except Exception as e:
        print(f"❌ Error during optimization: {e}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)