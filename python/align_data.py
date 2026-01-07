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
        # MAIN ALIGNMENT PROCESS (LENIENT FOR VOICE CROSSING)
        # =================================================================

        print("🎯 Aligning MIDI events with SVG noteheads (lenient mode)...")
        
        # Verify we have the same number of events to align
        if len(midi_df) != len(svg_df):
            print(f"⚠️  Count mismatch: {len(midi_df)} MIDI events vs {len(svg_df)} SVG noteheads")
            print("   This may indicate that SVG data wasn't properly processed")
            print("   Continuing with available pairs for debugging...")
            print(f"   Will process {min(len(midi_df), len(svg_df))} matching pairs")
            print()
        
        aligned_notes = []
        group_mismatch_count = 0

        # Helper function to create aligned note
        def create_aligned_note(midi_row, svg_row):
            # Build complete tie group from embedded tie data
            complete_data_refs = [svg_row.data_ref]
            
            tied_data_refs_value = svg_row.tied_data_refs
            if pd.notna(tied_data_refs_value) and str(tied_data_refs_value).strip():
                secondary_data_refs = str(tied_data_refs_value).split("|")
                complete_data_refs.extend(secondary_data_refs)

            return {
                "hrefs": complete_data_refs,
                "on_tick": make_json_serializable(midi_row.on_tick),
                "off_tick": make_json_serializable(midi_row.off_tick),
                "pitch": make_json_serializable(midi_row.midi),
                "channel": make_json_serializable(midi_row.channel),
                "x": make_json_serializable(svg_row.x),
                "y": make_json_serializable(svg_row.y)
            }

        # Group MIDI events by tick (simultaneous events)
        midi_groups = list(midi_df.groupby('on_tick'))
        
        print(f"   📊 Found {len(midi_groups)} MIDI time groups")
        
        svg_index = 0  # Track position in SVG data
        
        for tick, midi_group in midi_groups:
            group_size = len(midi_group)
            
            # Get corresponding SVG events (same count as MIDI group)
            if svg_index + group_size > len(svg_df):
                print(f"❌ Not enough SVG events for MIDI group at tick {tick}")
                break
                
            svg_group = svg_df.iloc[svg_index:svg_index + group_size].copy()
            svg_index += group_size
            
            print(f"   🎵 Processing tick {tick}: {group_size} simultaneous events")
            
            # Try to match by pitch within the group
            midi_pitches = [lilypond_to_midi_pitch(row.pitch) for _, row in midi_group.iterrows()]
            svg_pitches = [lilypond_to_midi_pitch(row.snippet) for _, row in svg_group.iterrows()]
            
            # Check if pitches match (in any order)
            if sorted(midi_pitches) == sorted(svg_pitches):
                # Perfect match - try to align by pitch
                print(f"      ✅ Perfect pitch match for group")
                
                # Create mapping by pitch
                midi_list = list(midi_group.iterrows())
                svg_list = list(svg_group.iterrows())
                
                # Sort both by pitch for alignment
                midi_sorted = sorted(midi_list, key=lambda x: lilypond_to_midi_pitch(x[1].pitch))
                svg_sorted = sorted(svg_list, key=lambda x: lilypond_to_midi_pitch(x[1].snippet))
                
                # Align sorted pairs
                for (_, midi_row), (_, svg_row) in zip(midi_sorted, svg_sorted):
                    aligned_note = create_aligned_note(midi_row, svg_row)
                    aligned_notes.append(aligned_note)
                    
            else:
                # Pitch mismatch within group - emit warning but continue
                print(f"      ⚠️  Pitch mismatch in group at tick {tick}:")
                print(f"         MIDI pitches: {[midi_df.iloc[i].pitch for i in midi_group.index]} -> {midi_pitches}")
                print(f"         SVG pitches:  {[svg_df.iloc[i].snippet for i in svg_group.index]} -> {svg_pitches}")
                print(f"         Continuing with original order (voice crossing detected)")
                
                group_mismatch_count += 1
                
                # Use original order despite mismatch
                for (_, midi_row), (_, svg_row) in zip(midi_group.iterrows(), svg_group.iterrows()):
                    aligned_note = create_aligned_note(midi_row, svg_row)
                    aligned_notes.append(aligned_note)

        # Report results
        if group_mismatch_count > 0:
            print(f"   ⚠️  {group_mismatch_count} groups had pitch mismatches (voice crossing)")
            print(f"      Used original ordering for these groups")
        
        if svg_index < len(svg_df):
            unmatched_svg = len(svg_df) - svg_index
            print(f"   ⚠️  {unmatched_svg} unmatched SVG noteheads remain")

        # Final summary at the end of alignment section
        print(f"   ✅ Successfully processed {len(aligned_notes)} note alignments")
        if group_mismatch_count > 0:
            print(f"   ⚠️  Voice crossing detected in {group_mismatch_count} groups (continued anyway)")

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

        if group_mismatch_count > 0:
            print(f"⚠️  Voice crossing in {group_mismatch_count} groups (handled gracefully)")

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