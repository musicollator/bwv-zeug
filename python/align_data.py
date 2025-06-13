#!/usr/bin/env python3
"""
align-data.py

Musical Score Alignment Pipeline
================================

This script aligns MIDI note events with squashed SVG noteheads from LilyPond-generated 
musical scores, creating a synchronized dataset for score animation. It expects that
the SVG data has been pre-processed with squash-tied-note-heads.py to embed tie
group information directly in the CSV.

Input Files Required:
- MIDI timing and pitch data CSV with tick format (on_tick/off_tick columns)
- Squashed SVG notehead data CSV (with embedded tied_data_refs column and normalized data_ref)

Output:
- Aligned notes with tick timing, pitch, SVG references, and spatial coordinates JSON

The alignment process ensures that visual noteheads in the SVG match their
corresponding MIDI events for precise animated score following. Spatial coordinates
are preserved for downstream fermata interpolation and visual positioning.

Pipeline:
1. extract_note_heads.py (extracts all noteheads from SVG with data_ref)
2. squash-tied-note-heads.py (removes secondaries, embeds tie groups in primaries)
3. align-data.py (this script - alignment with tick timing and spatial data preserved)

Note: This script expects normalized input from upstream processing. All data_ref
values are already clean and no additional processing is performed.
"""

import pandas as pd
import json
import argparse
import sys
import os
from _scripts_utils import lilypond_to_midi_pitch

def setup_argument_parser():
    """Setup command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Align MIDI note events with squashed SVG noteheads for score animation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python align-data.py -im notes.csv -is squashed_heads.csv -o output.json
  python align-data.py --input-midi bwv1006_note_events.csv --input-svg bwv1006_squashed.csv --output exports/bwv1006_json_notes.json

Pipeline Integration:
  This script expects normalized input from upstream processing:
  - MIDI CSV with tick format (on_tick/off_tick columns)
  - SVG CSV with clean data_ref column (no textedit prefixes)
  - SVG CSV with embedded tied_data_refs (pre-processed by squash-tied-note-heads.py)
  - Spatial coordinates (x, y) preserved for downstream processing

Note: The SVG noteheads CSV should be pre-processed with squash-tied-note-heads.py
      The MIDI CSV must use tick format (on_tick/off_tick columns)
      Spatial coordinates (x, y) are preserved for downstream processing
        """
    )
    
    parser.add_argument('-im', '--input-midi', 
                       required=True,
                       help='Input MIDI note events CSV file path (required)')
    
    parser.add_argument('-is', '--input-svg',
                       required=True,
                       help='Input squashed SVG noteheads CSV file path (required - should be pre-processed)')
    
    parser.add_argument('-o', '--output',
                       required=True, 
                       help='Output JSON file path for aligned notes (required)')
    
    return parser.parse_args()

def make_json_serializable(obj):
    """Convert numpy types to JSON-serializable Python types"""
    import numpy as np
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    else:
        return obj

def main():
    """Main function with command line argument support."""
    
    print("🎯 Musical Score Alignment Pipeline (Normalized)")
    print("=" * 60)
    
    # Parse arguments
    args = setup_argument_parser()
    
    midi_csv = args.input_midi
    svg_csv = args.input_svg
    output_json = args.output
    
    print(f"📄 Input MIDI CSV: {midi_csv}")
    print(f"📄 Input squashed SVG CSV: {svg_csv}")
    print(f"📊 Output JSON: {output_json}")
    print()
    
    try:
        print("📁 Loading input data files...")
        
        # Verify input files exist
        for file_path, file_type in [(midi_csv, "MIDI"), (svg_csv, "SVG")]:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"{file_type} file not found: {file_path}")
        
        # Load data files
        # Note: MIDI CSV uses quoted fields for LilyPond notation containing commas (e.g., "c,", "c,,")
        midi_df = pd.read_csv(midi_csv)
        svg_df = pd.read_csv(svg_csv) 

        print(f"   📊 Loaded {len(midi_df)} MIDI events")
        print(f"   📊 Loaded {len(svg_df)} squashed SVG noteheads")

        # Verify expected CSV formats (updated for normalized pipeline)
        expected_midi_columns = {"pitch", "midi", "channel", "on_tick", "off_tick"}
        if not expected_midi_columns.issubset(set(midi_df.columns)):
            raise ValueError(f"MIDI CSV missing required columns for tick format. Expected: {expected_midi_columns}, Found: {set(midi_df.columns)}")

        expected_svg_columns = {"snippet", "data_ref", "x", "y", "tied_data_refs"}
        if not expected_svg_columns.issubset(set(svg_df.columns)):
            raise ValueError(f"SVG CSV missing required columns. Expected: {expected_svg_columns}, Found: {set(svg_df.columns)}")

        print("   🕒 Using tick timing format")
        print("   📐 Preserving spatial coordinates (x, y)")
        print("   🔧 Using normalized data_ref attributes from upstream processing")

        # =================================================================
        # STEP 1: SORT MIDI DATA ONLY (PRESERVE SVG ORDER)
        # =================================================================

        # Sort MIDI events chronologically with tie-breaking rules:
        # 1. Primary: onset time (ascending)
        # 2. Secondary: channel (descending - higher channels first)  
        # 3. Tertiary: MIDI pitch (ascending)
        print("📊 Sorting MIDI data for alignment...")
        
        midi_df = midi_df.sort_values(
            by=["on_tick", "channel", "midi"], 
            ascending=[True, False, True]
        ).reset_index(drop=True)

        # DO NOT sort SVG data! It already has the correct tolerance-based ordering
        # from extract_note_heads.py -> squash_tied_note_heads.py pipeline
        print(f"   🎵 Sorted {len(midi_df)} MIDI events chronologically")
        print(f"   📐 Preserved {len(svg_df)} SVG noteheads in tolerance-based order")

        # =================================================================
        # MAIN ALIGNMENT PROCESS
        # =================================================================

        print("🎯 Aligning MIDI events with SVG noteheads...")
        
        # Verify we have the same number of events to align
        if len(midi_df) != len(svg_df):
            print(f"⚠️  Count mismatch: {len(midi_df)} MIDI events vs {len(svg_df)} SVG noteheads")
            print("   This may indicate that SVG data wasn't properly processed")
            print("   Continuing with available pairs for debugging...")
            print(f"   Will process {min(len(midi_df), len(svg_df))} matching pairs")
            print()
        
        aligned_notes = []
        mismatch_count = 0

        # Process each MIDI-SVG pair in synchronized order
        min_count = min(len(midi_df), len(svg_df))
        for index in range(min_count):
            midi_row = midi_df.iloc[index]
            svg_row = svg_df.iloc[index]
            
            # Compare LilyPond notation directly (both sources now have LilyPond format)
            midi_lilypond_pitch = midi_row.pitch  # This is LilyPond notation from extract_note_events.py
            svg_lilypond_pitch = svg_row.snippet  # This is LilyPond notation from SVG extraction
            
            # Verify pitch alignment by comparing LilyPond notation strings
            midi_pitch_num = lilypond_to_midi_pitch(midi_lilypond_pitch)
            svg_pitch_num = lilypond_to_midi_pitch(svg_lilypond_pitch)

            if midi_pitch_num != svg_pitch_num:
                print(f"⚠️  Pitch mismatch at position {index}:")
                print(f"    midi_pitch_num: '{midi_pitch_num}' MIDI: '{midi_lilypond_pitch}' (MIDI number: {midi_row.midi})")
                print(f"    svg_pitch_num : '{svg_pitch_num}' SVG: '{svg_lilypond_pitch}'")
                print(f"    SVG data_ref: {svg_row.data_ref}")
                mismatch_count += 1
                
                # Show some context around the mismatch
                print(f"    Context - MIDI events around position {index}:")
                start_ctx = max(0, index-2)
                end_ctx = min(len(midi_df), index+3)
                for ctx_idx in range(start_ctx, end_ctx):
                    marker = " --> " if ctx_idx == index else "     "
                    ctx_row = midi_df.iloc[ctx_idx]
                    print(f"    {marker}[{ctx_idx}] '{ctx_row.pitch}' (MIDI {ctx_row.midi})")
                
                print(f"    Context - SVG noteheads around position {index}:")
                for ctx_idx in range(start_ctx, end_ctx):
                    if ctx_idx < len(svg_df):
                        marker = " --> " if ctx_idx == index else "     "
                        ctx_row = svg_df.iloc[ctx_idx]
                        print(f"    {marker}[{ctx_idx}] '{ctx_row.snippet}'")
                
                sys.exit(1)  # Stop on first mismatch for debugging

            # Build complete tie group from embedded tie data (normalized)
            complete_data_refs = [svg_row.data_ref]  # Start with primary data_ref
            
            # Add tied secondary data_refs if they exist
            # Handle both empty strings and NaN values from pandas
            tied_data_refs_value = svg_row.tied_data_refs
            if pd.notna(tied_data_refs_value) and str(tied_data_refs_value).strip():
                secondary_data_refs = str(tied_data_refs_value).split("|")
                complete_data_refs.extend(secondary_data_refs)

            # Create aligned note entry with tick timing and spatial coordinates
            aligned_note = {                                                                  
                "hrefs": complete_data_refs,                                   # All SVG noteheads for this musical event (normalized)
                "on_tick": make_json_serializable(midi_row.on_tick),           # Start time in ticks
                "off_tick": make_json_serializable(midi_row.off_tick),         # End time in ticks
                "pitch": make_json_serializable(midi_row.midi),                # MIDI pitch number (for audio playback)
                "channel": make_json_serializable(midi_row.channel),           # MIDI channel (for multi-voice music)
                "x": make_json_serializable(svg_row.x),                        # X coordinate from SVG (for spatial interpolation)
                "y": make_json_serializable(svg_row.y)                         # Y coordinate from SVG (for future use)
            }                                                                  
            
            aligned_notes.append(aligned_note)

        # Report if there were unmatched events
        if len(midi_df) != len(svg_df):
            unmatched_midi = len(midi_df) - min_count
            unmatched_svg = len(svg_df) - min_count
            if unmatched_midi > 0:
                print(f"   ⚠️  {unmatched_midi} unmatched MIDI events")
            if unmatched_svg > 0:
                print(f"   ⚠️  {unmatched_svg} unmatched SVG noteheads")

        # =================================================================
        # OUTPUT GENERATION
        # =================================================================

        print(f"💾 Writing aligned data to {output_json}...")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_json) if os.path.dirname(output_json) else '.', exist_ok=True)

        with open(output_json, "w") as output_file:
            json.dump(aligned_notes, output_file, indent=2)

        # Summary statistics
        note_count = len(aligned_notes)
        total_data_refs = sum(len(note["hrefs"]) for note in aligned_notes)
        tie_count = total_data_refs - note_count
        notes_with_ties = sum(1 for note in aligned_notes if len(note["hrefs"]) > 1)

        print(f"✅ Successfully aligned {note_count} musical events")
        print(f"   📊 {total_data_refs} total SVG noteheads")
        print(f"   🔗 {tie_count} tied noteheads")
        print(f"   🎵 {notes_with_ties} notes have ties")
        print(f"   🕒 Timing format: ticks (preserved)")
        print(f"   📐 Spatial coordinates: x, y (preserved)")
        print(f"   🔧 Using normalized data_ref attributes")
        print(f"   💾 Saved: {output_json}")

        if mismatch_count > 0:
            print(f"⚠️  {mismatch_count} pitch mismatches detected")

        print()
        print("🎉 Alignment completed successfully!")
        print("🔧 All data processed using normalized pipeline - no cleaning performed")

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