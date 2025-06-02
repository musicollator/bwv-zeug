#!/usr/bin/env python3
"""
svg_remove_hrefs_in_tabs.py

Musical Score Link Cleanup Utility
==================================

This script removes hyperlinks from non-musical elements in LilyPond-generated
SVG files, specifically targeting tablature numbers and text annotations while
preserving essential notehead links needed for interactive score features.

Problem Addressed:
LilyPond embeds cross-reference links (href attributes) in ALL clickable elements,
including tablature numbers, fingering annotations, and text markings. For score
animation applications, we typically only want links on actual noteheads, as
other links can interfere with user interaction and animation logic.

Selective Link Removal:
- REMOVES links from: <text> elements (numbers, annotations, lyrics)
- REMOVES links from: <rect> elements (boxes, tablature backgrounds)  
- PRESERVES links on: <path> elements (actual noteheads and musical symbols)

Additionally performs namespace cleanup:
- CONVERTS legacy xlink:href to modern href attributes
- ELIMINATES useless xlink namespace declarations

This creates cleaner SVG files optimized for musical score interaction.
"""

from xml.etree import ElementTree as ET
from pathlib import Path

# =============================================================================
# XML NAMESPACE CONFIGURATION
# =============================================================================

# Standard SVG and XLink namespaces used in LilyPond-generated files
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"

# Register namespaces to ensure clean output without ns0: prefixes
ET.register_namespace("", SVG_NAMESPACE)      # SVG as default namespace
ET.register_namespace("xlink", XLINK_NAMESPACE)  # XLink for href attributes

# Namespace map for XPath queries
NAMESPACE_MAP = {
    "svg": SVG_NAMESPACE, 
    "xlink": XLINK_NAMESPACE
}

# =============================================================================
# LINK CLEANUP ENGINE
# =============================================================================

def remove_href_from_tab_links(input_path: Path, output_path: Path):
    """
    Remove hyperlinks from text and rectangular elements in SVG musical scores,
    and convert all xlink:href attributes to modern href format.
    
    This function processes LilyPond-generated SVG files to:
    1. Convert legacy xlink:href attributes to modern href attributes
    2. Selectively remove href attributes from non-musical elements
    3. Preserve links on actual musical noteheads
    
    Args:
        input_path (Path): Path to input SVG file with embedded links
        output_path (Path): Path where cleaned SVG will be written
        
    Process:
    1. Parse SVG file and convert all xlink:href to href (namespace cleanup)
    2. Locate all anchor (<a>) elements for link processing
    3. Remove href attributes from anchors containing text/rect elements
    4. Preserve href attributes on anchors containing only musical paths
    5. Write cleaned SVG with modern href format and no xlink namespace
    
    Target Elements for Link Removal:
    - <text>: Tablature numbers, fingerings, lyrics, tempo markings
    - <rect>: Background boxes, tablature grids, measure boundaries
    
    Preserved Elements:
    - <path>: Noteheads, stems, beams, slurs (core musical notation)
    - <g>: Grouping elements (structure preservation)
    """
    
    print(f"🎼 Processing musical score: {input_path.name}")
    
    # =================================================================
    # SVG LOADING AND PARSING
    # =================================================================
    
    try:
        print("   📖 Loading SVG file...")
        svg_tree = ET.parse(input_path)
        svg_root = svg_tree.getroot()
        
    except ET.ParseError as parse_error:
        print(f"   ❌ SVG parsing failed: {parse_error}")
        return
    except FileNotFoundError:
        print(f"   ❌ Input file not found: {input_path}")
        return
    
    # =================================================================
    # NAMESPACE CLEANUP: CONVERT xlink:href TO href
    # =================================================================
    
    print("   🔧 Converting legacy xlink:href to modern href...")
    
    xlink_conversion_count = 0
    namespaced_href = f"{{{XLINK_NAMESPACE}}}href"
    
    # Convert xlink:href to href on ALL elements throughout the document
    for element in svg_root.iter():
        if namespaced_href in element.attrib:
            # Get the href value
            href_value = element.attrib[namespaced_href]
            # Remove the namespaced version
            del element.attrib[namespaced_href]
            # Add the modern version
            element.attrib["href"] = href_value
            xlink_conversion_count += 1
    
    print(f"   ✅ Converted {xlink_conversion_count} xlink:href attributes to href")
    
    # =================================================================
    # LINK ANALYSIS AND REMOVAL
    # =================================================================
    
    print("   🔍 Analyzing anchor elements for link removal...")
    
    removed_link_count = 0
    total_anchor_count = 0
    text_anchor_count = 0
    rect_anchor_count = 0
    
    # Find all anchor elements using XPath with proper namespaces
    for anchor_element in svg_root.findall(".//svg:a", NAMESPACE_MAP):
        total_anchor_count += 1
        
        # Check for text content (tablature numbers, annotations, etc.)
        contains_text = anchor_element.find(".//svg:text", NAMESPACE_MAP) is not None
        
        # Check for rectangular elements (backgrounds, grids, etc.)
        contains_rect = anchor_element.find(".//svg:rect", NAMESPACE_MAP) is not None
        
        # Track statistics for reporting
        if contains_text:
            text_anchor_count += 1
        if contains_rect:
            rect_anchor_count += 1
        
        # Remove href if anchor contains text or rect elements
        if contains_text or contains_rect:
            # Since we converted xlink:href to href above, we only need to check href
            if "href" in anchor_element.attrib:
                del anchor_element.attrib["href"]
                removed_link_count += 1
                
    print(f"   📊 Link removal analysis:")
    print(f"      Total anchors found: {total_anchor_count}")
    print(f"      Anchors with text elements: {text_anchor_count}")
    print(f"      Anchors with rect elements: {rect_anchor_count}")
    print(f"      Links removed: {removed_link_count}")
    
    # =================================================================
    # CLEANED SVG OUTPUT
    # =================================================================
    
    print(f"   💾 Writing cleaned SVG to: {output_path.name}")
    
    try:
        # Write cleaned SVG with proper XML declaration and encoding
        svg_tree.write(
            output_path, 
            encoding="utf-8", 
            xml_declaration=True
        )
        
        # Calculate file size change for reporting
        original_size = input_path.stat().st_size
        cleaned_size = output_path.stat().st_size
        size_change = cleaned_size - original_size
        
        print(f"✅ Cleanup complete: {output_path}")
        print(f"   🔗 Converted {xlink_conversion_count} legacy xlink:href to modern href")
        print(f"   🗑️  Removed {removed_link_count} non-musical links")
        print(f"   📏 File size change: {original_size:,} → {cleaned_size:,} bytes ({size_change:+,})")
        
        # Provide guidance on what was preserved
        preserved_links = total_anchor_count - removed_link_count
        if preserved_links > 0:
            print(f"   🎵 Preserved {preserved_links} musical notehead links (now using modern href)")
        
    except Exception as write_error:
        print(f"   ❌ Failed to write output file: {write_error}")
        return

def main():
    """Main function with project context support."""
    
    print("🚀 THE LATEST Musical Score Link Cleanup Utility")
    print("=" * 50)
    
    # Fix path resolution for _scripts_utils
    import sys
    from pathlib import Path
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir))
    
    try:
        # Try to use project context system
        from _scripts_utils import get_io_files
        
        input_file, output_file = get_io_files(
            "Remove hyperlinks from text and rect elements in SVG",
            "{project}.svg",
            "{project}_no_hrefs_in_tabs.svg"
        )
        
    except ImportError as e:
        print("❌ FATAL: _scripts_utils.py not found in script directory")
        print(f"   Looking in: {script_dir}")
        print(f"   Import error: {e}")
        print("   Cannot continue without utilities")
        sys.exit(1)
    
    print(f"📄 Processing file:")
    print(f"   Input: {input_file}")
    print(f"   Output: {output_file}")
    print()
    
    input_path = Path(input_file)
    output_path = Path(output_file)
    
    if input_path.exists():
        remove_href_from_tab_links(input_path, output_path)
    else:
        print(f"❌ Input file not found: {input_path}")
        print("💡 Usage: python svg_remove_hrefs_in_tabs.py")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)