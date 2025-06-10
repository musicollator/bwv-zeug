#!/usr/bin/env python3
"""
extract_ties.py - Extract tie relationships from SVG files

SVG Tie Relationship Extractor
==============================

This script extracts musical tie relationships from LilyPond-generated SVG files.
Ties connect notes of the same pitch across time, indicating sustained sound without
re-articulation. These relationships are crucial for accurate MIDI playback timing.

Key Features:
- Extracts tie start/end relationships from SVG grob attributes
- Validates ties go forward in musical time (essential for proper sequencing)
- Handles both modern href and legacy xlink:href formats
- Merges with existing tie data while removing invalid relationships

MUSICAL CONTEXT:
A tie connects two noteheads of the same pitch where the second note extends
the first note's duration without re-striking. In MIDI terms, this means the
first note's off-time extends to cover the second note's duration.

Example: C quarter note tied to C half note = C dotted half note in playback

Updated version that works with both modern href and legacy xlink:href formats.
"""

import xml.etree.ElementTree as ET
import csv
import os
import sys
import argparse
from pathlib import Path

def extract_ties_from_svg(svg_file_path):
    """
    Extract tie relationships from SVG using LilyPond's tie grob attributes.
    
    ALGORITHM: SVG Grob-Based Tie Extraction
    ========================================
    LilyPond embeds tie information directly in SVG elements using custom attributes:
    - data-tie-role: "start", "end", or "both" (indicates tie participation)
    - data-tie-to: "#element-id" (points to the target notehead)
    
    This approach is more reliable than geometric analysis since it uses
    LilyPond's internal knowledge of musical relationships.
    """
    print(f"📖 Reading SVG file: {svg_file_path}")
    
    if not os.path.exists(svg_file_path):
        raise FileNotFoundError(f"SVG file not found: {svg_file_path}")
    
    try:
        tree = ET.parse(svg_file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ET.ParseError(f"Failed to parse SVG file {svg_file_path}: {e}")
    
    ties = []
    
    # Look for elements with tie data attributes
    for element in root.iter():
        tie_role = element.get('data-tie-role')
        
        # Process elements that START ties (role = "start" or "both")
        if tie_role in ['start', 'both']:
            tie_to = element.get('data-tie-to')
            if tie_to:
                # Get href for this element
                start_href = find_element_href(element)
                if start_href:
                    start_clean = clean_href_path(start_href)
                    
                    # Find the target element
                    target_id = tie_to[1:] if tie_to.startswith('#') else tie_to
                    target_element = find_element_by_id(root, target_id)
                    
                    if target_element is not None:
                        end_href = find_element_href(target_element)
                        if end_href:
                            end_clean = clean_href_path(end_href)
                            
                            # VALIDATION: Ensure ties are within the same file and go forward in time
                            start_file = get_file_from_href(start_clean)
                            end_file = get_file_from_href(end_clean)
                            
                            if start_file == end_file:
                                # Additional validation: ties must go forward in musical time
                                if is_valid_forward_tie(start_clean, end_clean):
                                    ties.append((start_clean, end_clean))
                                    print(f"🔗 Found tie: {start_clean} → {end_clean}")
                                else:
                                    print(f"⚠️  Ignoring invalid backward tie: {start_clean} → {end_clean}")
                                    print(f"    (Ties must go forward in musical time)")
                            else:
                                print(f"⚠️  Ignoring invalid cross-file tie: {start_clean} → {end_clean}")
                                print(f"    (Ties cannot span different files: {start_file} vs {end_file})")
                        else:
                            print(f"⚠️  Could not find href for target element {target_id}")
                    else:
                        print(f"⚠️  Could not find target element with id {target_id}")
                else:
                    print(f"⚠️  Could not find href for tie start element")
    
    print(f"✅ Extracted {len(ties)} valid tie relationships")
    return ties

def get_file_from_href(href):
    """Extract the file part from an href reference."""
    # href format: "file.ly:line:col:col"
    return href.split(':')[0] if ':' in href else href

def is_valid_forward_tie(start_href, end_href):
    """
    Validate that a tie goes forward in musical time.
    
    CRITICAL ALGORITHM: Musical Time Validation
    ===========================================
    Ties must connect notes in chronological order (forward in time).
    This validation prevents malformed ties that would break MIDI sequencing.
    
    Validation Rules:
    1. End note must be on a line number GREATER than start note line
    2. If same line, end note must be at column GREATER than start note
    
    Why This Matters:
    - MIDI playback depends on chronological ordering
    - Backward ties would create impossible timing relationships
    - Same-position ties would create zero-duration notes
    
    Args:
        start_href (str): Starting notehead href (e.g., "file.ly:10:4:5")
        end_href (str): Ending notehead href (e.g., "file.ly:12:8:9")
        
    Returns:
        bool: True if tie goes forward in time, False otherwise
    """
    try:
        # Parse href format: "file.ly:line:start_col:end_col"
        start_parts = start_href.split(':')
        end_parts = end_href.split(':')
        
        if len(start_parts) < 3 or len(end_parts) < 3:
            return False  # Invalid href format
        
        start_line = int(start_parts[1])
        start_col = int(start_parts[2])
        end_line = int(end_parts[1])
        end_col = int(end_parts[2])
        
        # Rule 1: End line must be greater than start line
        if end_line > start_line:
            return True
        
        # Rule 2: If same line, end column must be greater than start column
        if end_line == start_line and end_col > start_col:
            return True
        
        # All other cases are invalid (backward or same position)
        return False
        
    except (ValueError, IndexError):
        # If we can't parse the href format, assume invalid
        return False

def find_element_by_id(root, element_id):
    """Find an element by its ID attribute."""
    for element in root.iter():
        if element.get('id') == element_id:
            return element
    return None

def find_element_href(element):
    """
    Find href attribute supporting both modern and legacy SVG formats.
    
    COMPATIBILITY ALGORITHM: Dual Format Support
    ============================================
    LilyPond SVG output varies between versions:
    - Modern: href="textedit://..." 
    - Legacy: xlink:href="textedit://..."
    
    This function checks both formats to ensure compatibility across
    different LilyPond versions and processing pipelines.
    """
    # Check if element itself has an href (modern format)
    href = element.get('href')
    if href:
        return href
    
    # Check if element itself has an href (legacy format)
    href = element.get('{http://www.w3.org/1999/xlink}href')
    if href:
        return href
    
    # Look for href in child elements (both formats)
    for child in element.iter():
        # Try modern format first
        child_href = child.get('href')
        if child_href:
            return child_href
            
        # Try legacy format
        child_href = child.get('{http://www.w3.org/1999/xlink}href')
        if child_href:
            return child_href
    
    return None

def clean_href_path(href):
    """Clean href path by removing LilyPond editor artifacts."""
    # Remove textedit protocol and workspace path
    cleaned = href.replace("textedit://", "").replace("/work/", "")
    return cleaned

def load_existing_ties(csv_file_path):
    """Load existing tie relationships from CSV file."""
    existing_ties = set()
    
    if os.path.exists(csv_file_path):
        print(f"📂 Loading existing ties from: {csv_file_path}")
        try:
            with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                
                # Skip header if present
                first_row = next(reader, None)
                if first_row and (first_row[0].lower() == 'primary'):
                    # Header row detected, continue reading data
                    pass
                else:
                    # No header, treat first row as data
                    if first_row and len(first_row) >= 2:
                        # Validate existing ties too
                        primary, secondary = first_row[0], first_row[1]
                        if (get_file_from_href(primary) == get_file_from_href(secondary) and 
                            is_valid_forward_tie(primary, secondary)):
                            existing_ties.add((primary, secondary))
                        else:
                            print(f"⚠️  Removing invalid existing tie: {primary} → {secondary}")
                
                # Read remaining rows
                for row in reader:
                    if len(row) >= 2:
                        primary, secondary = row[0], row[1]
                        # Validate existing ties too
                        if (get_file_from_href(primary) == get_file_from_href(secondary) and
                            is_valid_forward_tie(primary, secondary)):
                            existing_ties.add((primary, secondary))
                        else:
                            print(f"⚠️  Removing invalid existing tie: {primary} → {secondary}")
                        
        except Exception as e:
            print(f"⚠️  Error reading existing CSV: {e}")
    else:
        print(f"📝 CSV file doesn't exist, will create new: {csv_file_path}")
    
    print(f"📊 Found {len(existing_ties)} valid existing tie relationships")
    return existing_ties

def save_ties_to_csv(ties, csv_file_path, existing_ties=None):
    """Save tie relationships to CSV file, merging with existing ties."""
    if existing_ties is None:
        existing_ties = set()
    
    # Combine new and existing ties, removing duplicates
    all_ties = existing_ties.union(set(ties))
    new_ties_count = len(all_ties) - len(existing_ties)
    
    print(f"💾 Saving {len(all_ties)} total ties ({new_ties_count} new) to: {csv_file_path}")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(csv_file_path) if os.path.dirname(csv_file_path) else '.', exist_ok=True)
    
    try:
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['primary', 'secondary'])
            
            # Write ties sorted for consistency
            for primary, secondary in sorted(all_ties):
                writer.writerow([primary, secondary])
                
        print(f"✅ Successfully saved ties to {csv_file_path}")
        
    except Exception as e:
        print(f"❌ Error saving CSV file: {e}")
        raise

def setup_argument_parser():
    """Setup command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract tie relationships from SVG and update ties CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python extract_ties.py -i score.svg -o ties.csv
  python extract_ties.py --input music.svg --output music_ties.csv
        """
    )
    
    parser.add_argument('-i', '--input', 
                       required=True,
                       help='Input SVG file path (required)')
    
    parser.add_argument('-o', '--output',
                       required=True, 
                       help='Output CSV file path for ties (required)')
    
    return parser.parse_args()

def main():
    """Main function with project context support."""
    
    print("🎼 SVG Tie Extractor (Tie Grob Version)")
    print("=" * 50)
    
    # Parse arguments
    args = setup_argument_parser()
    
    svg_file = args.input
    csv_file = args.output
    
    print(f"📄 Input SVG: {svg_file}")
    print(f"📊 Output CSV: {csv_file}")
    print()
    
    try:
        # Load existing ties from CSV (with validation)
        existing_ties = load_existing_ties(csv_file)
        
        # Extract ties from SVG (with validation)
        new_ties = extract_ties_from_svg(svg_file)
        
        if not new_ties:
            print("⚠️  No tie relationships found in SVG file")
            print("   Make sure the SVG was generated with tie-attributes.ily")
            print("   and that the Tie_grob_engraver is properly applied")
        
        # Save combined ties to CSV
        save_ties_to_csv(new_ties, csv_file, existing_ties)
        
        print()
        print("🎉 Tie extraction completed successfully!")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()