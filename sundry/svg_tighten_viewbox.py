#!/usr/bin/env python3
"""
svg_tighten_viewbox.py

SVG ViewBox Optimization for Musical Scores
===========================================

This script automatically calculates and applies optimal viewBox dimensions to
SVG musical scores by analyzing the actual content boundaries. It eliminates
excessive whitespace while preserving visual margins needed for comfortable
music reading.

Problem Addressed:
LilyPond often generates SVG files with oversized viewBox dimensions that include
large amounts of empty space around the actual musical content. This results in:
- Inefficient screen space usage in web applications
- Poor zoom/scaling behavior in browsers
- Suboptimal presentation in responsive layouts

Solution:
The script analyzes all graphical elements' positions to determine the true
content boundaries, then creates a tight-fitting viewBox with appropriate
musical margins.

Process:
1. Parse SVG and find all positioned graphical groups
2. Extract translate(x,y) coordinates from transform attributes  
3. Calculate bounding box of all musical content
4. Add comfortable margins for musical readability
5. Update viewBox to optimal dimensions
"""

from xml.etree import ElementTree as ET
from pathlib import Path
import re
import sys

# =============================================================================
# CONFIGURATION AND SETUP
# =============================================================================

# Regular expression to extract translation coordinates from SVG transform attributes
# Matches: translate(x, y) or translate(x,y) formats with integer/decimal numbers
TRANSLATE_PATTERN = re.compile(r"translate\(([-\d.]+),\s*([-\d.]+)\)")

# Register SVG namespaces for clean output without ns0: prefixes
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

# Musical layout margins (in SVG coordinate units)
VERTICAL_MARGIN = 5.0      # Space above/below staff systems
HORIZONTAL_MARGIN = 0.0    # Space left/right of notation (can be increased if needed)

# =============================================================================
# VIEWBOX CALCULATION ENGINE
# =============================================================================

def tighten_viewbox(input_svg_path, output_svg_path):
    """
    Calculate optimal viewBox dimensions based on actual musical content boundaries.
    
    This function analyzes all positioned elements in an SVG musical score to
    determine the minimal bounding rectangle that contains all notation, then
    applies appropriate margins for readability.
    
    Args:
        input_svg_path (str): Path to input SVG file with oversized viewBox
        output_svg_path (str): Path for output SVG with optimized viewBox
        
    Process Details:
    1. Load and parse the SVG file structure
    2. Scan all <g> elements for transform="translate(x,y)" attributes
    3. Build coordinate dataset from all positioned elements
    4. Calculate bounding box encompassing all content
    5. Add musical margins for comfortable reading
    6. Update root SVG element's viewBox attribute
    7. Save optimized SVG with new dimensions
    
    Coordinate System:
    - SVG uses top-left origin (0,0)
    - X increases left-to-right (→)
    - Y increases top-to-bottom (↓) 
    - Musical content positioning is relative to page layout
    """
    
    input_path = Path(input_svg_path)
    output_path = Path(output_svg_path)
    
    print(f"🎼 Optimizing viewBox: {input_path.name}")
    
    # =================================================================
    # SVG LOADING AND PARSING
    # =================================================================
    
    try:
        print("   📖 Loading SVG structure...")
        svg_tree = ET.parse(input_path)
        svg_root = svg_tree.getroot()
        
    except ET.ParseError as parse_error:
        print(f"   ❌ SVG parsing failed: {parse_error}")
        return
    except FileNotFoundError:
        print(f"   ❌ Input file not found: {input_path}")
        return
    
    # =================================================================
    # COORDINATE EXTRACTION FROM POSITIONED ELEMENTS
    # =================================================================
    
    print("   🔍 Analyzing element positions...")
    
    # Initialize boundary tracking variables
    min_x_coord = float("inf")    # Leftmost content position
    min_y_coord = float("inf")    # Topmost content position  
    max_x_coord = float("-inf")   # Rightmost content position
    max_y_coord = float("-inf")   # Bottommost content position
    
    positioned_elements_count = 0
    total_groups_scanned = 0
    
    # Scan all group elements for position information
    # LilyPond places musical elements in <g> tags with translate transforms
    for group_element in svg_root.findall(".//{http://www.w3.org/2000/svg}g"):
        total_groups_scanned += 1
        
        # Extract transform attribute (contains positioning data)
        transform_attribute = group_element.get("transform")
        
        if transform_attribute:
            # Parse translate(x, y) coordinates using regex
            coordinate_match = TRANSLATE_PATTERN.search(transform_attribute)
            
            if coordinate_match:
                x_position = float(coordinate_match.group(1))
                y_position = float(coordinate_match.group(2))
                
                # Update bounding box coordinates
                min_x_coord = min(min_x_coord, x_position)
                min_y_coord = min(min_y_coord, y_position)
                max_x_coord = max(max_x_coord, x_position)
                max_y_coord = max(max_y_coord, y_position)
                
                positioned_elements_count += 1
    
    print(f"   📊 Coordinate analysis:")
    print(f"      Groups scanned: {total_groups_scanned}")
    print(f"      Positioned elements found: {positioned_elements_count}")
    
    # =================================================================
    # VIEWBOX CALCULATION AND APPLICATION
    # =================================================================
    
    if min_x_coord < float("inf") and min_y_coord < float("inf"):
        print("   📐 Calculating optimal viewBox dimensions...")
        
        # Apply margins for comfortable musical reading
        adjusted_min_x = min_x_coord - HORIZONTAL_MARGIN
        adjusted_min_y = min_y_coord - VERTICAL_MARGIN
        
        # Calculate content dimensions with margins
        content_width = (max_x_coord - min_x_coord) + (2 * HORIZONTAL_MARGIN)
        content_height = (max_y_coord - min_y_coord) + (2 * VERTICAL_MARGIN)
        
        # Format viewBox string: "min_x min_y width height"
        optimized_viewbox = f"{adjusted_min_x:.4f} {adjusted_min_y:.4f} {content_width:.4f} {content_height:.4f}"
        
        # Apply new viewBox to root SVG element
        svg_root.set("viewBox", optimized_viewbox)
        
        result_message = f"[ Updated viewBox: {optimized_viewbox} ]"
        
        # Report optimization statistics
        print(f"   🎯 ViewBox optimization:")
        print(f"      Content bounds: X({min_x_coord:.1f} to {max_x_coord:.1f}), Y({min_y_coord:.1f} to {max_y_coord:.1f})")
        print(f"      Final dimensions: {content_width:.1f} × {content_height:.1f}")
        print(f"      Margins applied: H={HORIZONTAL_MARGIN}, V={VERTICAL_MARGIN}")
        
    else:
        # No positioned elements found - likely an issue with the SVG structure
        result_message = "[ ⚠️ Warning: No positioned elements found - viewBox unchanged ]"
        print("   ⚠️  No valid transform=translate(x, y) coordinates found")
        print("      This may indicate:")
        print("      • SVG uses different positioning method")
        print("      • File structure differs from expected LilyPond format")
        print("      • All content is positioned at origin")

    # =================================================================
    # OPTIMIZED SVG OUTPUT
    # =================================================================
    
    print(f"   💾 Writing optimized SVG...")
    
    try:
        # Write SVG with proper XML declaration and UTF-8 encoding
        svg_tree.write(output_path, encoding="utf-8", xml_declaration=True)
        
        # File size comparison for optimization validation
        original_size = input_path.stat().st_size
        optimized_size = output_path.stat().st_size
        
        print(f"✅ ViewBox optimization complete: {output_path}")
        print(f"   📊 {result_message}")
        print(f"   📏 File size: {original_size:,} → {optimized_size:,} bytes")
        
        # Note about further optimizations
        if positioned_elements_count > 0:
            print(f"   🎵 SVG now optimally sized for musical content")
        
    except Exception as write_error:
        print(f"   ❌ Failed to write optimized file: {write_error}")

# =============================================================================
# VIEWBOX ANALYSIS UTILITIES
# =============================================================================

def analyze_current_viewbox(svg_path):
    """
    Analyze current viewBox settings and content distribution.
    
    Args:
        svg_path (str): Path to SVG file to analyze
        
    Returns:
        dict: Analysis results including current viewBox and content bounds
    """
    
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        # Get current viewBox
        current_viewbox = root.get("viewBox", "not set")
        
        # Analyze content bounds
        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")
        element_count = 0
        
        for group in root.findall(".//{http://www.w3.org/2000/svg}g"):
            transform = group.get("transform")
            if transform:
                match = TRANSLATE_PATTERN.search(transform)
                if match:
                    x, y = float(match.group(1)), float(match.group(2))
                    min_x, min_y = min(min_x, x), min(min_y, y)
                    max_x, max_y = max(max_x, x), max(max_y, y)
                    element_count += 1
        
        return {
            'current_viewbox': current_viewbox,
            'content_bounds': (min_x, min_y, max_x, max_y) if element_count > 0 else None,
            'positioned_elements': element_count,
            'file_size': Path(svg_path).stat().st_size
        }
        
    except Exception as analysis_error:
        return {'error': str(analysis_error)}

# =============================================================================
# BATCH PROCESSING INTERFACE
# =============================================================================

def process_multiple_files(file_patterns):
    """
    Process multiple SVG files with viewBox optimization.
    
    Args:
        file_patterns (list): List of file paths or glob patterns
        
    Returns:
        dict: Processing statistics and results
    """
    
    processed = []
    failed = []
    
    for pattern in file_patterns:
        pattern_path = Path(pattern)
        
        # Handle direct files vs glob patterns
        if pattern_path.is_file():
            files = [pattern_path]
        else:
            files = list(pattern_path.parent.glob(pattern_path.name))
        
        for input_file in files:
            if input_file.suffix.lower() == '.svg':
                output_file = input_file.parent / f"{input_file.stem}_bounded.svg"
                
                try:
                    tighten_viewbox(str(input_file), str(output_file))
                    processed.append((input_file, output_file))
                except Exception as process_error:
                    print(f"❌ Failed to process {input_file}: {process_error}")
                    failed.append(input_file)
    
    return {
        'processed': processed,
        'failed': failed,
        'success_count': len(processed),
        'failure_count': len(failed)
    }

# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """Main function for command line usage and batch processing."""
    
    print("🚀 SVG ViewBox Optimization for Musical Scores")
    print("=" * 55)
    
    if len(sys.argv) > 1:
        # Process files specified on command line
        file_patterns = sys.argv[1:]
        print(f"📋 Processing {len(file_patterns)} file pattern(s):")
        
        for pattern in file_patterns:
            print(f"   • {pattern}")
        print()
        
        results = process_multiple_files(file_patterns)
        
        # Batch processing summary
        print("=" * 55)
        print(f"🎯 Batch Optimization Complete")
        print(f"   ✅ Successfully processed: {results['success_count']} files")
        print(f"   ❌ Failed: {results['failure_count']} files")
        
        if results['processed']:
            print(f"\n📁 Optimized files created:")
            for input_file, output_file in results['processed']:
                print(f"   {input_file.name} → {output_file.name}")
    
    else:
        # Default single file processing example
        input_svg = "bwv1006_svg_no_hrefs_in_tabs.svg"
        output_svg = "bwv1006_svg_no_hrefs_in_tabs_bounded.svg"
        
        print("📄 Processing default configuration:")
        print(f"   Input: {input_svg}")
        print(f"   Output: {output_svg}")
        print()
        
        if Path(input_svg).exists():
            tighten_viewbox(input_svg, output_svg)
        else:
            print(f"❌ Default input file not found: {input_svg}")
            print("💡 Usage: python svg_tighten_viewbox.py <svg_files...>")
            return 1
    
    return 0

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)