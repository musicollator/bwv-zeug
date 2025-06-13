#!/usr/bin/env python3
"""
squash-tied-note-heads.py

Squash Tied Noteheads for Score Alignment
==========================================

This script processes SVG noteheads and ties data to create a squashed dataset
where only primary noteheads remain, but each primary includes a list of all
its tied secondary noteheads. It also handles duplicate noteheads (same pitch 
and position) by merging them into a single entry.

IMPORTANT: This script preserves the ordering from the input CSV, which should
already have the correct tolerance-based chord grouping from extract_note_heads.py.

Process:
1. Load SVG noteheads CSV and ties relationships CSV (both already normalized)
2. Identify all secondary (tied-to) noteheads from ties data
3. For each primary notehead, collect all tied secondary data-refs
4. Optionally squash duplicate noteheads (same snippet, x, y) by merging data-refs
5. Filter SVG noteheads to keep only primaries, adding tied_data_refs column
6. Export squashed noteheads CSV with embedded tie group information (preserving order)

Configuration System:
- no-duplicates can be specified via CLI argument (-nd/--no-duplicates)
- If no CLI no-duplicates provided, looks for noDuplicates in project-specific YAML config
- Falls back to default no-duplicates of true if no config found
- This allows per-project duplicate handling without complicating the build system

Input Files Required:
- SVG noteheads CSV (with normalized data_ref column, pre-sorted with tolerance)
- Ties relationships CSV (primary -> secondary mappings, already normalized)

Output:
- Squashed SVG noteheads CSV (format: snippet,data_ref,x,y,tied_data_refs)
  where tied_data_refs contains pipe-separated secondary data-refs and duplicate data-refs

Note: This script expects normalized input from upstream processing. No additional
cleaning is performed since data-ref values are already clean.
"""

import pandas as pd
import argparse
import sys
import os
from pathlib import Path
from _scripts_utils import save_dataframe_with_lilypond_csv, get_project_name

# =============================================================================
# PROJECT CONFIGURATION LOADING
# =============================================================================

def load_project_no_duplicates():
    """
    Load no-duplicates configuration from project-specific YAML file.
    
    This function implements a graceful configuration loading system:
    1. Uses the existing get_project_name() from _scripts_utils
    2. Looks for PROJECT_NAME.yaml in the current directory
    3. Extracts noDuplicates value from YAML if file exists
    4. Falls back to default no-duplicates of True if no config or errors
    
    The YAML file format expected:
        noDuplicates: false
        # Other project settings can be added here
    
    Returns:
        bool: Whether to remove duplicate noteheads (default: True)
    """
    project_name = get_project_name()
    config_file = Path(f"{project_name}.yaml")
    
    print(f"🔍 Looking for project config: {config_file}")
    
    if config_file.exists():
        try:
            import yaml
            print(f"📄 Loading config from: {config_file}")
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                no_duplicates = config.get('noDuplicates', True)
                print(f"⚙️  Using noDuplicates from config: {no_duplicates}")
                return no_duplicates
        except ImportError:
            print(f"⚠️  Warning: PyYAML not installed, cannot read {config_file}")
            print(f"   Install with: pip install PyYAML")
        except Exception as e:
            print(f"⚠️  Warning: Could not load {config_file}: {e}")
            print(f"   Using default noDuplicates")
    else:
        print(f"📝 No config file found, using default noDuplicates")
    
    return True  # Default no-duplicates

def setup_argument_parser():
    """Setup command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Squash tied noteheads into primary noteheads with embedded tie groups",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use automatic duplicate handling from project config:
  python squash-tied-note-heads.py -i noteheads.csv -t ties.csv -o squashed_noteheads.csv
  
  # Override to disable duplicate squashing:
  python squash-tied-note-heads.py -i noteheads.csv -t ties.csv -o squashed_noteheads.csv --no-duplicates
  
  # Enable duplicate squashing explicitly:
  python squash-tied-note-heads.py -i noteheads.csv -t ties.csv -o squashed_noteheads.csv -nd

Configuration Files:
  Create PROJECT_NAME.yaml in the working directory to set project-specific duplicate handling:
  
  # Example bwv659.yaml:
  noDuplicates: false
  
  # Example bwv543.yaml:
  noDuplicates: true

Pipeline Integration:
  This script expects normalized input from upstream processing:
  - Noteheads CSV with clean data_ref column (no textedit prefixes)
  - Ties CSV with already clean primary/secondary references
  - No additional cleaning is performed
        """
    )
    
    parser.add_argument('-i', '--input', 
                       required=True,
                       help='Input SVG noteheads CSV file path (required, should be normalized)')
    
    parser.add_argument('-t', '--ties',
                       required=True,
                       help='Input ties relationships CSV file path (required, should be normalized)')
    
    parser.add_argument('-o', '--output',
                       required=True, 
                       help='Output squashed SVG noteheads CSV file path (required)')
    
    parser.add_argument('-nd', '--no-duplicates',
                       action='store_true',
                       default=None,  # None means "auto-detect from config"
                       help='Remove duplicate noteheads at same position '
                            '(default: auto-detect from project config or true)')
    
    return parser.parse_args()

def collect_full_tie_group(primary_data_ref, ties_df):
    """
    Collect all noteheads connected by ties, starting from a primary notehead.
    
    Musical ties can form chains: Note A -> Note B -> Note C, where each
    arrow represents a tie. This function follows the entire chain to collect
    all connected noteheads for a single sustained musical event.
    
    Args:
        primary_data_ref (str): Starting notehead reference (already normalized)
        ties_df (DataFrame): Tie relationships with 'primary' and 'secondary' columns
        
    Returns:
        list: All secondary data-ref references in the tie group (excluding the primary)
        
    Example:
        If Note A ties to B, and B ties to C:
        collect_full_tie_group("A", ties_df) -> ["B", "C"]
    """
    tied_secondaries = []  # Only secondary data-refs (primary not included)
    visited = set([primary_data_ref])  # Track visited notes to prevent infinite loops
    processing_queue = [primary_data_ref]  # Notes whose ties we still need to check

    # Breadth-first search through the tie network
    while processing_queue:
        current_data_ref = processing_queue.pop(0)
        
        # Find all notes that this current note ties TO
        direct_secondaries = ties_df.loc[
            ties_df["primary"] == current_data_ref, 
            "secondary"
        ].tolist()
        
        # Add newly discovered tied notes to our group
        for secondary_data_ref in direct_secondaries:
            if secondary_data_ref not in visited:
                tied_secondaries.append(secondary_data_ref)
                visited.add(secondary_data_ref)
                processing_queue.append(secondary_data_ref)  # Check its ties too

    return tied_secondaries

def main():
    """Main function with command line argument support."""
    
    print("🎵 Squash Tied Noteheads (Normalized Pipeline)")
    print("=" * 50)
    
    # Parse arguments
    args = setup_argument_parser()
    
    svg_csv = args.input
    ties_csv = args.ties
    output_csv = args.output
    
    # CONFIGURATION-AWARE NO-DUPLICATES LOADING
    # Priority: CLI argument > project config > default
    if args.no_duplicates is not None:
        # Explicit no-duplicates provided via CLI - use it
        no_duplicates = args.no_duplicates
        print(f"⚙️  Using no-duplicates from CLI argument: {no_duplicates}")
    else:
        # No CLI no-duplicates - check project configuration
        no_duplicates = load_project_no_duplicates()
    
    print(f"📄 Input SVG noteheads: {svg_csv}")
    print(f"🔗 Input ties: {ties_csv}")
    print(f"📊 Output squashed noteheads: {output_csv}")
    print(f"🔄 Remove duplicates: {no_duplicates}")
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

        # Verify expected CSV formats (updated for normalized pipeline)
        expected_svg_columns = {"snippet", "data_ref", "x", "y"}
        if not expected_svg_columns.issubset(set(svg_df.columns)):
            raise ValueError(f"SVG CSV missing required columns. Expected: {expected_svg_columns}, Found: {set(svg_df.columns)}")
            
        expected_ties_columns = {"primary", "secondary"}
        if not expected_ties_columns.issubset(set(ties_df.columns)):
            raise ValueError(f"Ties CSV missing required columns. Expected: {expected_ties_columns}, Found: {set(ties_df.columns)}")

        # =================================================================
        # STEP 1: VALIDATE NORMALIZED DATA
        # =================================================================

        print("🔧 Validating normalized SVG data...")
        
        # Check for and handle missing data_ref values
        missing_data_ref_count = svg_df['data_ref'].isna().sum()
        if missing_data_ref_count > 0:
            print(f"   ⚠️  Found {missing_data_ref_count} rows with missing data_ref values - removing them")
            svg_df = svg_df.dropna(subset=['data_ref']).reset_index(drop=True)
            print(f"   ✅ Cleaned data: {len(svg_df)} valid noteheads remaining")
        
        # Ensure data_ref column is string type
        svg_df['data_ref'] = svg_df['data_ref'].astype(str)
        
        # No cleaning needed - data is already normalized from upstream processing
        print("   ✅ Data already normalized from upstream processing")

        # =================================================================
        # STEP 2: IDENTIFY PRIMARY AND SECONDARY NOTEHEADS
        # =================================================================

        # Get all secondary (tied-to) data-refs from the ties data
        secondary_data_refs = set(ties_df["secondary"]) if len(ties_df) > 0 else set()
        print(f"   Found {len(secondary_data_refs)} secondary tied noteheads")
        
        # Filter to keep only primary noteheads (not secondary to any tie)
        # IMPORTANT: Use .loc to preserve original order from extract_note_heads.py
        original_count = len(svg_df)
        primary_mask = ~svg_df["data_ref"].isin(secondary_data_refs)
        primary_noteheads = svg_df.loc[primary_mask].copy()
        filtered_count = len(primary_noteheads)
        removed_count = original_count - filtered_count
        
        print(f"   Identified {filtered_count} primary noteheads")
        print(f"   Will embed {removed_count} secondary noteheads in tie groups")

        # =================================================================
        # STEP 3: BUILD TIE GROUPS FOR EACH PRIMARY
        # =================================================================

        print("🔗 Building tie groups for primary noteheads...")
        
        # Add tied_data_refs column to store pipe-separated secondary data-refs
        tied_data_refs_list = []
        
        for index, row in primary_noteheads.iterrows():
            primary_data_ref = row["data_ref"]
            
            # Collect all tied secondary noteheads for this primary
            tied_secondaries = collect_full_tie_group(primary_data_ref, ties_df)
            
            # Convert list to pipe-separated string
            if tied_secondaries:
                tied_data_refs_str = "|".join(tied_secondaries)
            else:
                tied_data_refs_str = ""  # Empty string for notes with no ties
            
            tied_data_refs_list.append(tied_data_refs_str)
        
        # Add the tied_data_refs column to the dataframe
        primary_noteheads["tied_data_refs"] = tied_data_refs_list
        
        # Count tie statistics
        tied_notes_count = sum(1 for data_refs in tied_data_refs_list if data_refs)
        total_tied_data_refs = sum(len(data_refs.split("|")) for data_refs in tied_data_refs_list if data_refs)
        
        print(f"   📊 {tied_notes_count} primary noteheads have ties")
        print(f"   🔗 {total_tied_data_refs} total secondary data-refs embedded")

        # =================================================================
        # STEP 4: OPTIONALLY SQUASH DUPLICATE NOTEHEADS (SAME POSITION & PITCH)
        # =================================================================

        duplicates_squashed = 0
        
        if no_duplicates:
            print("🔄 Squashing duplicate noteheads with same pitch and position...")
            
            # Find duplicate groups by (snippet, x, y)
            primary_noteheads['group_key'] = (
                primary_noteheads['snippet'].astype(str) + '|' + 
                primary_noteheads['x'].round(3).astype(str) + '|' + 
                primary_noteheads['y'].round(3).astype(str)
            )
            
            rows_to_drop = []
            
            # Process each group
            for group_key in primary_noteheads['group_key'].unique():
                group_rows = primary_noteheads[primary_noteheads['group_key'] == group_key]
                
                if len(group_rows) > 1:
                    # Multiple noteheads at same position - squash them
                    duplicates_squashed += len(group_rows) - 1
                    
                    # Get the first occurrence (primary)
                    primary_idx = group_rows.index[0]
                    duplicate_indices = group_rows.index[1:]
                    
                    # Collect duplicate data-refs
                    duplicate_data_refs = group_rows.iloc[1:]['data_ref'].tolist()
                    
                    # Merge with existing tied_data_refs
                    existing_tied = primary_noteheads.loc[primary_idx, 'tied_data_refs']
                    if pd.isna(existing_tied) or existing_tied == "":
                        combined_tied = "|".join(duplicate_data_refs)
                    else:
                        combined_tied = existing_tied + "|" + "|".join(duplicate_data_refs)
                    
                    # Update the primary row
                    primary_noteheads.loc[primary_idx, 'tied_data_refs'] = combined_tied
                    
                    # Mark duplicate rows for removal
                    rows_to_drop.extend(duplicate_indices)
                    
                    snippet = group_rows.iloc[0]['snippet']
                    x = group_rows.iloc[0]['x']
                    y = group_rows.iloc[0]['y']
                    print(f"   🔄 Squashed {len(group_rows)} '{snippet}' notes at ({x:.1f}, {y:.1f})")
            
            # Remove duplicate rows while preserving order
            if rows_to_drop:
                primary_noteheads = primary_noteheads.drop(rows_to_drop).reset_index(drop=True)
            
            # Clean up temporary column
            primary_noteheads = primary_noteheads.drop('group_key', axis=1)
            
            if duplicates_squashed > 0:
                print(f"   📊 Squashed {duplicates_squashed} duplicate noteheads")
                print(f"   ✅ Final count: {len(primary_noteheads)} unique notes")
            else:
                print(f"   ✅ No duplicate noteheads found")
        else:
            print("⏭️  Skipping duplicate squashing (disabled by configuration)")

        # =================================================================
        # PRESERVE ORDERING (NO RE-SORTING)
        # =================================================================

        print("📐 Preserving tolerance-based ordering from input...")
        
        # DO NOT re-sort here! The input noteheads CSV already has the correct
        # tolerance-based ordering from extract_note_heads.py that properly
        # handles chord grouping. Re-sorting would destroy this careful work.

        print(f"   🎯 Preserved order for {len(primary_noteheads)} squashed noteheads")
        print(f"   ℹ️  Ordering was calculated with chord tolerance in extract_note_heads.py")

        # =================================================================
        # OUTPUT GENERATION
        # =================================================================

        print(f"💾 Writing squashed noteheads to {output_csv}...")

        # Reorder columns to match expected format: snippet, data_ref, x, y, tied_data_refs
        output_df = primary_noteheads[["snippet", "data_ref", "x", "y", "tied_data_refs"]]

        # Use utility function to handle LilyPond notation CSV quoting
        save_dataframe_with_lilypond_csv(output_df, output_csv)

        # Summary statistics
        if len(output_df) > 0:
            unique_pitches = output_df["snippet"].nunique()
            x_range = output_df["x"].max() - output_df["x"].min()
            y_range = output_df["y"].max() - output_df["y"].min()
            
            print(f"✅ Export complete!")
            print(f"   📁 File: {output_csv}")
            print(f"   🎵 Primary noteheads: {len(output_df)}")
            print(f"   🎼 Unique pitches: {unique_pitches}")
            print(f"   📏 Coordinate range: {x_range:.1f} x {y_range:.1f}")
            print(f"   🔗 Notes with ties: {tied_notes_count}")
            print(f"   📊 Total embedded secondaries: {total_tied_data_refs}")
            if no_duplicates and duplicates_squashed > 0:
                print(f"   🔄 Duplicates squashed: {duplicates_squashed}")
            print(f"   🎯 Order preserved from extract_note_heads.py")
            print(f"   🔧 Using normalized data from upstream processing")
            
            # Show some examples of tie groups
            tied_examples = output_df[output_df["tied_data_refs"] != ""].head(3)
            if len(tied_examples) > 0:
                print(f"   🔍 Example tie groups:")
                for _, example in tied_examples.iterrows():
                    secondary_count = len(example["tied_data_refs"].split("|"))
                    print(f"      '{example['snippet']}' → {secondary_count} tied secondary(s)")
        else:
            print(f"⚠️  Warning: No noteheads remaining after processing!")

        print()
        print("🎉 Tie squashing and optional duplicate removal completed successfully!")
        print("🎯 Ready for simplified MIDI-to-SVG alignment with preserved chord grouping")
        print("🔧 All data normalized by upstream processing - no cleaning performed")
        if no_duplicates:
            print("📝 Note: Duplicate noteheads at same position were merged into tied_data_refs")
        else:
            print("📝 Note: Duplicate noteheads were preserved (duplicate squashing disabled)")
            
        # Configuration guidance for user
        if args.no_duplicates is None:
            project_name = get_project_name()
            print(f"\n💡 Configuration tip:")
            print(f"   To lock in this duplicate handling ({no_duplicates}) for project {project_name}:")
            print(f"   Create {project_name}.yaml with content:")
            print(f"   noDuplicates: {no_duplicates}")

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