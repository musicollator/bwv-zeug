#!/usr/bin/env python3
"""
remove_tied_note_heads.py

Remove Secondary Tied Noteheads from SVG Data
==============================================

This script removes secondary tied noteheads from SVG notehead data, leaving only
primary noteheads for alignment. In musical notation, tied notes connect multiple 
noteheads but represent a single sustained sound, so only the first (primary) 
notehead should be used for MIDI-to-SVG alignment.

Process:
1. Load SVG noteheads CSV and ties relationships CSV
2. Identify all secondary (tied-to) noteheads from ties data
3. Filter SVG noteheads to remove secondary tied noteheads
4. Export filtered SVG noteheads CSV with only primary noteheads

Input Files Required:
- SVG noteheads CSV (with all noteheads including tied ones)
- Ties relationships CSV (primary -> secondary mappings)

Output:
- Filtered SVG noteheads CSV (secondary tied noteheads removed)
"""

import pandas as pd
import argparse
import sys
import os
from _scripts_utils import save_dataframe_with_lilypond_csv

def setup_argument_parser():
    """Setup command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Remove secondary tied noteheads from SVG notehead data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python remove-tied-note-heads.py -i noteheads.csv -t ties.csv -o filtered_noteheads.csv
  python remove-tied-note-heads.py --input score_noteheads.csv --ties score_ties.csv --output score_noteheads_filtered.csv
        """
    )
    
    parser.add_argument('-i', '--input', 
                       required=True,
                       help='Input SVG noteheads CSV file path (required)')
    
    parser.add_argument('-t', '--ties',
                       required=True,
                       help='Input ties relationships CSV file path (required)')
    
    parser.add_argument('-o', '--output',
                       required=True, 
                       help='Output filtered SVG noteheads CSV file path (required)')
    
    return parser.parse_args()

def main():
    """Main function with command line argument support."""
    
    print("🎵 Remove Secondary Tied Noteheads")
    print("=" * 50)
    
    # Parse arguments
    args = setup_argument_parser()
    
    svg_csv = args.input
    ties_csv = args.ties
    output_csv = args.output
    
    print(f"📄 Input SVG noteheads: {svg_csv}")
    print(f"🔗 Input ties: {ties_csv}")
    print(f"📊 Output filtered noteheads: {output_csv}")
    print()
    
    try:
        print("📁 Loading input data files...")
        
        # Verify input files exist
        for file_path, file_type in [(svg_csv, "SVG noteheads"), (ties_csv, "Ties")]:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"{file_type} file not found: {file_path}")
        
        # Load data files
        svg_df = pd.read_csv(svg_csv) 
        ties_df = pd.read_csv(ties_csv)

        print(f"   📊 Loaded {len(svg_df)} SVG noteheads")
        print(f"   📊 Loaded {len(ties_df)} tie relationships")

        # Verify expected CSV formats
        expected_svg_columns = {"snippet", "href", "x", "y"}
        if not expected_svg_columns.issubset(set(svg_df.columns)):
            raise ValueError(f"SVG CSV missing required columns. Expected: {expected_svg_columns}, Found: {set(svg_df.columns)}")
            
        expected_ties_columns = {"primary", "secondary"}
        if not expected_ties_columns.issubset(set(ties_df.columns)):
            raise ValueError(f"Ties CSV missing required columns. Expected: {expected_ties_columns}, Found: {set(ties_df.columns)}")

        # =================================================================
        # STEP 1: CLEAN SVG HREF PATHS
        # =================================================================

        # Remove LilyPond editor artifacts from href paths to normalize references
        # Example: "textedit:///work/file.ly:10:5" -> "file.ly:10:5"
        print("🧹 Normalizing SVG href paths...")
        svg_df["href"] = (
            svg_df["href"]
            .str.replace("textedit://", "", regex=False)  # Remove protocol prefix
            .str.replace("/work/", "", regex=False)       # Remove workspace path
        )

        # =================================================================
        # STEP 2: REMOVE SECONDARY TIED NOTEHEADS
        # =================================================================

        # In musical notation, tied notes connect multiple noteheads but represent
        # a single sustained sound. We only want the primary (first) notehead for
        # alignment, so we filter out secondary tied noteheads.
        print("🎵 Filtering out secondary tied noteheads...")
        
        # Get all secondary (tied-to) hrefs from the ties data
        secondary_hrefs = set(ties_df["secondary"])
        print(f"   Found {len(secondary_hrefs)} secondary tied noteheads to remove")
        
        # Filter SVG noteheads to keep only primary noteheads
        original_count = len(svg_df)
        svg_df_filtered = svg_df[~svg_df["href"].isin(secondary_hrefs)].copy()
        filtered_count = len(svg_df_filtered)
        removed_count = original_count - filtered_count
        
        print(f"   Removed {removed_count} secondary noteheads")
        print(f"   Kept {filtered_count} primary noteheads")

        # =================================================================
        # STEP 3: SORT FILTERED NOTEHEADS
        # =================================================================

        print("📐 Sorting filtered noteheads by visual position...")

        # Sort noteheads by visual reading order:
        # 1. Primary sort: x-coordinate (left to right across the staff)  
        # 2. Secondary sort: y-coordinate (top to bottom, hence descending)
        svg_df_filtered = svg_df_filtered.sort_values(
            by=["x", "y"], 
            ascending=[True, False]
        ).reset_index(drop=True)

        print(f"   🎯 Sorted {len(svg_df_filtered)} filtered noteheads in reading order")

        # =================================================================
        # OUTPUT GENERATION
        # =================================================================

        print(f"💾 Writing filtered noteheads to {output_csv}...")

        # Use utility function to handle LilyPond notation CSV quoting
        save_dataframe_with_lilypond_csv(svg_df_filtered, output_csv)

        # Summary statistics
        if len(svg_df_filtered) > 0:
            unique_pitches = svg_df_filtered["snippet"].nunique()
            x_range = svg_df_filtered["x"].max() - svg_df_filtered["x"].min()
            y_range = svg_df_filtered["y"].max() - svg_df_filtered["y"].min()
            
            print(f"✅ Export complete!")
            print(f"   📁 File: {output_csv}")
            print(f"   🎵 Filtered noteheads: {len(svg_df_filtered)}")
            print(f"   🎼 Unique pitches: {unique_pitches}")
            print(f"   📏 Coordinate range: {x_range:.1f} x {y_range:.1f}")
            print(f"   🔗 Removed tied secondaries: {removed_count}")
        else:
            print(f"⚠️  Warning: No noteheads remaining after filtering!")

        print()
        print("🎉 Tie filtering completed successfully!")
        print("🎯 Ready for MIDI-to-SVG alignment in next pipeline stage")

    except FileNotFoundError as e:
        print(f"❌ File error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()