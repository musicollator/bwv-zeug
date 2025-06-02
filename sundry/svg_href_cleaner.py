#!/usr/bin/env python3
"""
SVG Href Cleaner - Removes unused textedit:///work/ href attributes from SVG files
Based on references found in a JSON notes file.

Usage: python3 svg_href_cleaner.py <svg_file> [json_file] [output_file]

e.g. python3 scripts/svg_href_cleaner.py bwv1006_svg_no_hrefs_in_tabs_bounded_optimized_swellable.svg exports/bwv1006_json_notes.json -o bwv1006_svg_no_hrefs_in_tabs_bounded_optimized_swellable_cleaned_file.svg
"""

import argparse
import json
import sys
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

def load_json_notes(json_file):
    """Load and parse the JSON notes file."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: JSON file '{json_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{json_file}': {e}")
        sys.exit(1)


def extract_valid_hrefs(notes_data):
    """Extract all valid href references from the JSON notes data."""
    valid_hrefs = set()
    
    for note in notes_data:
        if isinstance(note, dict) and 'hrefs' in note:
            hrefs = note['hrefs']
            if isinstance(hrefs, list):
                for href in hrefs:
                    # Convert JSON href format to SVG textedit format
                    # "_1/m001_008.ly:31:4:5" becomes "textedit:///work/_1/m001_008.ly:31:4:5"
                    valid_hrefs.add(f"textedit:///work/{href}")
    
    return valid_hrefs


def clean_svg_hrefs(svg_file, valid_hrefs):
    """Remove unused href attributes from the SVG file."""
    try:
        # Parse the SVG file
        tree = ET.parse(svg_file)
        root = tree.getroot()
        
        # Find all elements with href attributes
        # Note: SVG href attributes might be in different namespaces
        href_attrs = ['{http://www.w3.org/1999/xlink}href', 'href']
        
        elements_with_href = []
        for href_attr in href_attrs:
            elements_with_href.extend(root.findall(f".//*[@{href_attr}]", NAMESPACE_MAP))
        
        # Also search without namespace prefix in case it's not declared
        for elem in root.iter():
            for attr_name in elem.attrib:
                if attr_name.endswith('href') and elem not in elements_with_href:
                    elements_with_href.append(elem)
        
        print(f"Found {len(elements_with_href)} elements with href attributes")
        
        removed_count = 0
        kept_count = 0
        
        # Check each element and remove unused hrefs
        for element in elements_with_href:
            href_value = None
            href_attr_name = None
            
            # Find the href attribute (could be in different namespaces)
            for attr_name, attr_value in element.attrib.items():
                if attr_name.endswith('href') and attr_value.startswith('textedit:///work/'):
                    href_value = attr_value
                    href_attr_name = attr_name
                    break
            
            if href_value and href_attr_name:
                if href_value in valid_hrefs:
                    kept_count += 1
                else:
                    del element.attrib[href_attr_name]
                    removed_count += 1
        
        print(f"Removed {removed_count} unused href attributes")
        print(f"Kept {kept_count} valid href attributes")
        
        return tree, removed_count, kept_count
        
    except ET.ParseError as e:
        print(f"Error: Invalid XML in '{svg_file}': {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: SVG file '{svg_file}' not found.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Remove unused textedit:///work/ href attributes from SVG files"
    )
    parser.add_argument('svg_file', help='Input SVG file path')
    parser.add_argument('json_file', nargs='?', 
                       default='exports/bwv1006_json_notes.json',
                       help='JSON notes file (default: exports/bwv1006_json_notes.json)')
    parser.add_argument('-o', '--output', 
                       help='Output SVG file (default: overwrite input file)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be removed without making changes')
    
    args = parser.parse_args()
    
    # Validate input files
    svg_path = Path(args.svg_file)
    json_path = Path(args.json_file)
    
    if not svg_path.exists():
        print(f"Error: SVG file '{svg_path}' does not exist.")
        sys.exit(1)
    
    if not json_path.exists():
        print(f"Error: JSON file '{json_path}' does not exist.")
        sys.exit(1)
    
    # Load JSON notes data
    print(f"Loading JSON notes from: {json_path}")
    notes_data = load_json_notes(json_path)
    print(f"Loaded {len(notes_data)} note entries")
    
    # Extract valid hrefs
    valid_hrefs = extract_valid_hrefs(notes_data)
    print(f"Found {len(valid_hrefs)} valid href references in JSON")
    
    # Clean the SVG
    print(f"Processing SVG file: {svg_path}")
    tree, removed_count, kept_count = clean_svg_hrefs(svg_path, valid_hrefs)
    
    if args.dry_run:
        print("DRY RUN: No changes were made to the file.")
        return
    
    # Determine output file
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = svg_path
    
    # Save the cleaned SVG
    try:
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        print(f"Cleaned SVG saved to: {output_path}")
        
        # Show file size difference if overwriting
        if output_path == svg_path:
            original_size = svg_path.stat().st_size
            print(f"File size: {original_size:,} bytes")
            if removed_count > 0:
                print(f"Estimated savings: ~{removed_count * 50:,} bytes "
                      f"(assuming ~50 chars per removed href)")
    
    except Exception as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
