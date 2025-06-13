#!/usr/bin/env python3
"""
remove_unwanted_hrefs.py

Musical Score Link Cleanup and Normalization Utility
====================================================

This script performs comprehensive href cleaning and normalization for LilyPond-generated 
SVG files. It serves as the single normalization point for the entire pipeline, ensuring
all downstream scripts receive clean, consistent data-ref attributes.

Centralized Processing:
1. NAMESPACE CLEANUP: Convert legacy xlink:href to modern href attributes
2. HREF CLEANING: Normalize LilyPond references using clean_lilypond_href()
3. ATTRIBUTE RENAME: Convert href → data-ref for downstream consistency  
4. SELECTIVE REMOVAL: Remove unwanted links (tablature, grace notes, annotations)

This approach follows "clean once, use everywhere" - all downstream scripts can simply
read clean data-ref attributes without needing their own cleaning logic.

Problem Addressed:
LilyPond embeds cross-reference links (href attributes) in ALL clickable elements,
including tablature numbers, fingering annotations, grace notes, and text markings.
For score animation applications, we typically only want links on actual noteheads,
as other links can interfere with user interaction and animation logic.

Selective Link Removal:
- REMOVES links from: <text> elements WITHOUT <path> or tie attributes (pure annotations)
- REMOVES links from: <rect> elements WITHOUT <path> or tie attributes (pure backgrounds)  
- REMOVES links to: grace-init.ly and other unwanted LilyPond system files (UNLESS they have tie attributes)
- PRESERVES links on: ANY anchor containing <path> elements (noteheads)
- PRESERVES links on: ANY anchor with tie-related data attributes (tie starts/ends)

This ensures that musical noteheads and tie relationships always retain their links,
even if they also contain additional text or rect elements for accidentals, articulations, etc.

Output Format:
All preserved links become data-ref attributes with clean, normalized references:
- Input:  xlink:href="textedit:///work/file.ly:37:20:21"
- Output: data-ref="file.ly:37:21"

This creates cleaner SVG files optimized for musical score interaction with consistent
data format throughout the entire processing pipeline.
"""

from xml.etree import ElementTree as ET
from pathlib import Path
import re
import argparse
import sys
from _scripts_utils import clean_lilypond_href

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
# UNWANTED HREF PATTERNS
# =============================================================================

# Patterns for href values that should be removed
UNWANTED_HREF_PATTERNS = [
    r".*grace-init\.ly.*",          # Grace notes
    r".*chord-repetition\.ly.*",    # Chord repetitions
    r".*trill-init\.ly.*",          # Trills and ornaments
    r".*music-functions\.ly.*",     # Music function definitions
    r".*predefined-guitar-fretboards\.ly.*",  # Guitar tablature
    r".*articulate\.ly.*",          # Articulation marks
    r".*ly/[^/]*\.ly.*",           # Any other LilyPond system files
]

# =============================================================================
# LINK CLEANUP ENGINE
# =============================================================================

def is_unwanted_href(href_value: str) -> bool:
    """
    Check if an href value matches unwanted patterns.
    
    Args:
        href_value (str): The href attribute value to check
        
    Returns:
        bool: True if href should be removed, False if it should be preserved
    """
    if not href_value:
        return False
        
    # Check against all unwanted patterns
    for pattern in UNWANTED_HREF_PATTERNS:
        if re.match(pattern, href_value, re.IGNORECASE):
            return True
    
    return False

def remove_unwanted_hrefs(input_path: Path, output_path: Path):
    """
    Comprehensive href cleaning and normalization for SVG musical scores.
    
    This function serves as the single normalization point for the entire pipeline,
    performing all href-related processing in one place:
    
    1. NAMESPACE CLEANUP: Convert legacy xlink:href to modern href
    2. HREF CLEANING: Normalize using clean_lilypond_href()  
    3. ATTRIBUTE RENAME: Convert href → data-ref
    4. SELECTIVE REMOVAL: Remove unwanted system file links
    
    Args:
        input_path (Path): Path to input SVG file with embedded links
        output_path (Path): Path where cleaned SVG will be written
        
    Process:
    1. Parse SVG file and convert all xlink:href to href (namespace cleanup)
    2. Clean and normalize all href content using centralized function
    3. Rename href attributes to data-ref for pipeline consistency
    4. Remove href/data-ref attributes based on content type and target patterns
    5. Preserve data-ref attributes on genuine musical notation elements
    6. Write cleaned SVG with normalized data-ref attributes
    
    Target Elements for Link Removal:
    - Pure annotations: <text> elements without <path> or tie attributes
    - Pure backgrounds: <rect> elements without <path> or tie attributes
    - System files: Links to grace-init.ly etc. (UNLESS they have tie attributes)
    
    Preserved Elements:
    - Noteheads: ANY anchor containing <path> elements (musical notation)
    - Tie elements: ANY anchor with data-tie-* attributes (tie relationships)
    - Mixed content: Anchors with both text/rect AND path/tie elements
    - User content: Links that don't match unwanted patterns
    
    Output Format:
    All preserved links become clean data-ref attributes:
    - Input:  xlink:href="textedit:///work/file.ly:37:20:21"
    - Output: data-ref="file.ly:37:21"
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
    # STEP 1: NAMESPACE CLEANUP - CONVERT xlink:href TO href
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
    # STEP 2: HREF CLEANING AND NORMALIZATION
    # =================================================================
    
    print("   🧹 Cleaning and normalizing href content...")
    
    href_cleaned_count = 0
    
    # Clean and normalize all href attributes using centralized function
    for element in svg_root.iter():
        if "href" in element.attrib:
            original_href = element.attrib["href"]
            cleaned_href = clean_lilypond_href(original_href)
            
            # Only update if cleaning actually changed something
            if cleaned_href != original_href:
                element.attrib["href"] = cleaned_href
                href_cleaned_count += 1
    
    print(f"   ✅ Cleaned {href_cleaned_count} href references")
    
    # =================================================================
    # STEP 3: ATTRIBUTE RENAME - href TO data-ref
    # =================================================================
    
    print("   🔄 Renaming href attributes to data-ref...")
    
    href_renamed_count = 0
    
    # Rename all href attributes to data-ref for pipeline consistency
    for element in svg_root.iter():
        if "href" in element.attrib:
            # Move href content to data-ref
            href_value = element.attrib["href"]
            del element.attrib["href"]
            element.attrib["data-ref"] = href_value
            href_renamed_count += 1
    
    print(f"   ✅ Renamed {href_renamed_count} href attributes to data-ref")
    
    # =================================================================
    # STEP 4: SELECTIVE LINK REMOVAL
    # =================================================================
    
    print("   🔍 Analyzing anchor elements for selective link removal...")
    
    # Build parent map for walking up the DOM tree
    parent_map = {child: parent for parent in svg_root.iter() for child in parent}
    
    removed_link_count = 0
    total_anchor_count = 0
    text_anchor_count = 0
    rect_anchor_count = 0
    pattern_anchor_count = 0
    grace_note_count = 0
    
    # Find all anchor elements using XPath with proper namespaces
    for anchor_element in svg_root.findall(".//svg:a", NAMESPACE_MAP):
        total_anchor_count += 1
        
        # Check for different element types
        contains_text = anchor_element.find(".//svg:text", NAMESPACE_MAP) is not None
        contains_rect = anchor_element.find(".//svg:rect", NAMESPACE_MAP) is not None
        contains_path = anchor_element.find(".//svg:path", NAMESPACE_MAP) is not None
        
        # Check for tie-related data attributes (preserve these!)
        # Check the anchor itself, its children, AND its parents
        has_tie_attributes = any(
            attr.startswith('data-tie-') for attr in anchor_element.attrib.keys()
        ) or any(
            any(attr.startswith('data-tie-') for attr in child.attrib.keys())
            for child in anchor_element.iter()
        )
        
        # ALSO check parent elements for tie attributes (important!)
        if not has_tie_attributes:
            parent = parent_map.get(anchor_element)
            while parent is not None:
                if any(attr.startswith('data-tie-') for attr in parent.attrib.keys()):
                    has_tie_attributes = True
                    break
                parent = parent_map.get(parent)
        
        # Check data-ref value for unwanted patterns (now data-ref instead of href)
        data_ref_value = anchor_element.attrib.get("data-ref", "")
        matches_unwanted_pattern = is_unwanted_href(data_ref_value)
        
        # Track statistics for reporting
        if contains_text:
            text_anchor_count += 1
        if contains_rect:
            rect_anchor_count += 1
        if matches_unwanted_pattern:
            pattern_anchor_count += 1
            if "grace-init.ly" in data_ref_value:
                grace_note_count += 1
        
        # CONSERVATIVE LOGIC: Only remove data-ref if:
        # 1. It matches unwanted patterns (system files) AND has no tie attributes, OR
        # 2. It contains text/rect BUT NO path elements AND NO tie attributes (pure annotations)
        # PRESERVE: Any anchor with path elements OR tie attributes
        is_pure_annotation = (contains_text or contains_rect) and not contains_path and not has_tie_attributes
        should_remove = (matches_unwanted_pattern and not has_tie_attributes) or is_pure_annotation
        
        if should_remove and "data-ref" in anchor_element.attrib:
            del anchor_element.attrib["data-ref"]
            removed_link_count += 1
                
    print(f"   📊 Link removal analysis:")
    print(f"      Total anchors found: {total_anchor_count}")
    print(f"      Anchors with text elements: {text_anchor_count}")
    print(f"      Anchors with rect elements: {rect_anchor_count}")
    print(f"      Anchors matching unwanted patterns: {pattern_anchor_count}")
    print(f"      Grace note links removed: {grace_note_count}")
    print(f"      Links removed: {removed_link_count}")
    print(f"      ℹ️  Preserved anchors with path elements OR tie attributes")
    
    # =================================================================
    # CLEANED SVG OUTPUT
    # =================================================================
    
    print(f"   💾 Writing normalized SVG to: {output_path.name}")
    
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
        
        print(f"✅ Normalization complete: {output_path}")
        print(f"   🔧 Converted {xlink_conversion_count} legacy xlink:href to modern href")
        print(f"   🧹 Cleaned {href_cleaned_count} href references")
        print(f"   🔄 Renamed {href_renamed_count} attributes to data-ref")
        print(f"   🗑️  Removed {removed_link_count} unwanted links")
        print(f"   🎵 Removed {grace_note_count} grace note links")
        print(f"   📏 File size change: {original_size:,} → {cleaned_size:,} bytes ({size_change:+,})")
        
        # Provide guidance on what was preserved
        preserved_links = total_anchor_count - removed_link_count
        if preserved_links > 0:
            print(f"   🎵 Preserved {preserved_links} musical noteheads as clean data-ref attributes")
            print(f"   🔧 Downstream scripts can now read normalized data-ref attributes")
        
    except Exception as write_error:
        print(f"   ❌ Failed to write output file: {write_error}")
        return

def setup_argument_parser():
    """Setup command line argument parser."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Comprehensive href cleaning and normalization for SVG musical scores",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python remove_unwanted_hrefs.py -i score.svg -o clean_score.svg
  python remove_unwanted_hrefs.py --input music.svg --output music_clean.svg

Pipeline Integration:
  This script serves as the single normalization point for the entire pipeline.
  All downstream scripts can read clean data-ref attributes without additional processing.
  
  Processing Steps:
  1. Namespace cleanup: xlink:href → href
  2. Content cleaning: "textedit:///work/file.ly:37:20:21" → "file.ly:37:21" 
  3. Attribute rename: href → data-ref
  4. Selective removal: Remove unwanted system/annotation links
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
    
    print("🚀 Musical Score Link Cleanup and Normalization Utility")
    print("=" * 70)
    
    # Parse arguments
    args = setup_argument_parser()
    
    input_file = args.input
    output_file = args.output
    
    print(f"📄 Processing file:")
    print(f"   Input: {input_file}")
    print(f"   Output: {output_file}")
    print()
    
    input_path = Path(input_file)
    output_path = Path(output_file)
    
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        print("💡 Usage: python remove_unwanted_hrefs.py -i INPUT.svg -o OUTPUT.svg")
        return 1
    
    try:
        remove_unwanted_hrefs(input_path, output_path)
        print()
        print("🎉 Link cleanup and normalization completed successfully!")
        print("🔧 All downstream scripts can now read clean data-ref attributes")
        return 0
    except Exception as e:
        print(f"❌ Error during processing: {e}")
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