#!/usr/bin/env python3
"""
extract_note_events.py

MIDI Note Event Extractor
=========================

This module extracts note events from MIDI files preserving their original 
MIDI timing for real-time synchronization in JavaScript/frontend applications.

Key Features:
- Extracts note on/off events with precise MIDI tick timing
- Handles overlapping notes and note stacking
- Preserves original MIDI timing data (ticks)
- Converts MIDI pitches to LilyPond notation (with proper CSV quoting for comma-containing notation)
- Outputs timing data suitable for real-time score animation

Workflow:
1. Parse MIDI file to extract all note events
2. Keep original MIDI tick timing (no tempo conversion)
3. Convert MIDI pitches to LilyPond notation (properly quoted for CSV format)
4. Export raw timing data as CSV for frontend processing

Example CSV Output:
pitch,midi,channel,on_tick,off_tick,ticks_per_beat
"c",60,1,0,960,480
"cis",61,1,960,1920,480
"c,",48,1,1920,2880,480
"""

from mido import MidiFile
import pandas as pd
import csv
import argparse
import sys
import os
from _scripts_utils import midi_pitch_to_lilypond

def extract_note_intervals(midi_path):
    """
    Extract note events from a MIDI file preserving original MIDI timing.
    
    This function processes a MIDI file to create a timeline of note events
    with their original MIDI tick timing preserved. The timing synchronization
    is left to be handled in real-time by JavaScript/frontend code.
    
    CORE ALGORITHM: Note Stack for Overlapping Notes
    ================================================
    Uses a FIFO stack per pitch to handle overlapping notes correctly:
    
    Example: Piano with sustain pedal
    Time 0: C4 pressed    → Stack: [(0, channel)]
    Time 100: C4 pressed  → Stack: [(0, channel), (100, channel)]  
    Time 200: C4 released → Pop (0), create note (0-200)
    Time 300: C4 released → Pop (100), create note (100-300)
    
    Without the stack, note-offs would match incorrect note-ons.
    
    Args:
        midi_path (str): Path to the MIDI file to process
        
    Returns:
        tuple: (pandas.DataFrame, int) where:
            DataFrame contains note events with columns:
                - pitch: LilyPond notation string (e.g., "cis'", "f,,") - quoted in CSV due to commas
                - midi: Original MIDI note number (0-127)
                - on_tick: Start time in MIDI ticks (int)
                - off_tick: End time in MIDI ticks (int) 
                - channel: MIDI channel number
            int: ticks_per_beat from the MIDI file
    """
    
    print(f"🎵 Loading MIDI file: {midi_path}")
    
    # =================================================================
    # STEP 1: LOAD MIDI FILE AND EXTRACT TIMING INFORMATION
    # =================================================================
    
    midi_file = MidiFile(midi_path)
    ticks_per_beat = midi_file.ticks_per_beat  # MIDI timing resolution
    
    print(f"   📊 MIDI resolution: {ticks_per_beat} ticks per beat")
    
    # Data structures for note tracking
    note_stack = {}      # Track overlapping notes: {pitch: [(start_tick, channel), ...]}
    note_events = []     # Final list of completed note events
    current_tick = 0     # Running total of elapsed MIDI ticks
    max_tick = 0         # Total duration of MIDI file in ticks
    
    print("🔍 Analyzing MIDI events...")
    
    # =================================================================
    # STEP 2: CONVERT DELTA TIMES TO ABSOLUTE TIMES AND COLLECT MESSAGES
    # =================================================================
    
    # CRITICAL: MIDI stores relative timing (deltas), but we need absolute timing
    # for chronological processing across multiple tracks
    
    # Collect all messages from all tracks with their absolute tick times
    all_messages = []
    
    for track_idx, track in enumerate(midi_file.tracks):
        current_tick = 0
        for message in track:
            # Advance timeline by message's delta time (in raw ticks)
            current_tick += message.time
            
            # Only process note events (skip meta messages)
            if hasattr(message, 'note'):
                all_messages.append((current_tick, message))
            
            # Track maximum tick value across all tracks
            max_tick = max(max_tick, current_tick)
    
    # Sort all messages by absolute tick time for chronological processing
    all_messages.sort(key=lambda x: x[0])
    
    print(f"   🎵 Processing {len(all_messages)} note messages from {len(midi_file.tracks)} tracks")
    
    # =================================================================
    # STEP 3: PROCESS MESSAGES WITH NOTE STACK ALGORITHM
    # =================================================================
    
    # Process messages in chronological order
    for abs_tick, message in all_messages:
        # Handle note start events
        if message.type == 'note_on' and message.velocity > 0:
            # Push note onto stack (handles multiple simultaneous notes of same pitch)
            if message.note not in note_stack:
                note_stack[message.note] = []
            note_stack[message.note].append((abs_tick, message.channel))
            
        # Handle note end events (note_off OR note_on with velocity=0)
        elif message.type in ('note_off', 'note_on') and message.velocity == 0:
            # Pop matching note from stack (FIFO order for overlapping notes)
            if note_stack.get(message.note):
                start_tick, channel = note_stack[message.note].pop(0)  # FIFO: first in, first out
                
                # Create completed note event with original MIDI timing
                note_event = {
                    "midi": message.note,           # Original MIDI pitch number
                    "on_tick": int(start_tick),     # Start time in MIDI ticks (ensure integer)
                    "off_tick": int(abs_tick),      # End time in MIDI ticks (ensure integer)
                    "channel": channel
                }
                note_events.append(note_event)
    
    print(f"   🎹 Extracted {len(note_events)} note events")
    print(f"   ⏱️  MIDI duration: {max_tick} ticks")
    
    # Verify all tick values are integers
    if note_events:
        sample_note = note_events[0]
        print(f"   🔍 Tick verification: on_tick={sample_note['on_tick']} (type: {type(sample_note['on_tick'])})")
        print(f"   🔍 Tick verification: off_tick={sample_note['off_tick']} (type: {type(sample_note['off_tick'])})")
        
        # Check for any non-integer values
        non_integers = []
        for i, note in enumerate(note_events[:10]):  # Check first 10 notes
            if not isinstance(note['on_tick'], int) or not isinstance(note['off_tick'], int):
                non_integers.append(i)
        
        if non_integers:
            print(f"   ⚠️  Warning: Found non-integer tick values in notes: {non_integers}")
        else:
            print(f"   ✅ All tick values are integers")
    
    # =================================================================
    # STEP 4: CONVERT MIDI PITCHES TO LILYPOND NOTATION
    # =================================================================
    
    print("🎼 Converting MIDI pitches to LilyPond notation...")
    
    for note_event in note_events:
        # Convert MIDI pitch to LilyPond notation
        note_event["pitch"] = midi_pitch_to_lilypond(note_event["midi"])
    
    # =================================================================
    # STEP 5: SORT AND ORGANIZE RESULTS
    # =================================================================
    
    # Convert to DataFrame for easier manipulation and export
    note_events_df = pd.DataFrame(note_events)
    
    # Reorder columns to match format: pitch, midi, channel, on_tick, off_tick
    note_events_df = note_events_df[["pitch", "midi", "channel", "on_tick", "off_tick"]]
    
    # Sort by musical priority:
    # 1. Start time (chronological order)
    # 2. Channel (higher channels first - often melody vs accompaniment)
    # 3. MIDI pitch (ascending - bass to treble within simultaneous events)
    note_events_df = note_events_df.sort_values(
        by=["on_tick", "channel", "midi"], 
        ascending=[True, False, True]
    )
    
    print(f"✅ Extracted {len(note_events_df)} notes with original MIDI timing")
    
    # Timing information
    if len(note_events_df) > 0:
        final_tick = note_events_df["off_tick"].max()
        print(f"   📏 Final timing: {final_tick} ticks")
        print(f"   🎯 Resolution: {ticks_per_beat} ticks per beat")
        
        # Show some examples of the pitch conversion
        print("   🎼 Sample pitch conversions:")
        sample_notes = note_events_df.head(5)
        for _, note in sample_notes.iterrows():
            print(f"      MIDI {note['midi']} -> '{note['pitch']}' ({note['on_tick']}-{note['off_tick']} ticks)")
    
    return note_events_df, ticks_per_beat

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def setup_argument_parser():
    """Setup command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract MIDI note events with original timing preserved",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python extract_note_events.py -i music.midi -o note_events.csv
  python extract_note_events.py --input bwv1006.midi --output bwv1006_notes.csv
        """
    )
    
    parser.add_argument('-i', '--input', 
                       required=True,
                       help='Input MIDI file path (required)')
    
    parser.add_argument('-o', '--output',
                       required=True, 
                       help='Output CSV file path for note events (required)')
    
    return parser.parse_args()

def main():
    """Main function with command line argument support."""
    print("🚀 Starting MIDI note extraction with preserved timing")
    print("=" * 60)
    
    # Parse arguments
    args = setup_argument_parser()
    
    midi_file_path = args.input
    output_file_path = args.output
    
    print(f"📄 Input MIDI: {midi_file_path}")
    print(f"📊 Output CSV: {output_file_path}")
    print()
    
    # Validate input file exists
    if not os.path.exists(midi_file_path):
        print(f"❌ Error: Input MIDI file not found: {midi_file_path}")
        sys.exit(1)
    
    # Process MIDI file
    try:
        note_events_df, ticks_per_beat = extract_note_intervals(midi_file_path)
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_file_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Export results
        print(f"\n💾 Saving note data with original timing...")
        
        # Use QUOTE_NONNUMERIC to properly handle LilyPond notation with commas (e.g., "c,", "c,,")
        # This ensures pitch column values like "c," are quoted as "c," in the CSV
        note_events_df.to_csv(output_file_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
        
        ## # Also save timing metadata as a comment in a separate file for JavaScript to read
        ## metadata_file = output_file_path.replace('.csv', '_metadata.json')
        ## import json
        ## metadata = {
        ##     "ticks_per_beat": ticks_per_beat,
        ##     "total_notes": len(note_events_df),
        ##     "max_tick": int(note_events_df["off_tick"].max()) if len(note_events_df) > 0 else 0,
        ##     "unique_pitches": int(note_events_df["pitch"].nunique()) if len(note_events_df) > 0 else 0,
        ##     "channels_used": int(note_events_df["channel"].nunique()) if len(note_events_df) > 0 else 0
        ## }
        ## 
        ## with open(metadata_file, 'w') as f:
        ##     json.dump(metadata, f, indent=2)
        
        # Summary statistics
        total_notes = len(note_events_df)
        max_tick = note_events_df["off_tick"].max() if total_notes > 0 else 0
        unique_pitches = note_events_df["pitch"].nunique() if total_notes > 0 else 0
        unique_midi_pitches = note_events_df["midi"].nunique() if total_notes > 0 else 0
        channels_used = note_events_df["channel"].nunique() if total_notes > 0 else 0
        
        print(f"✅ Export complete!")
        print(f"   📁 Note data: {output_file_path}")
        ## print(f"   📁 Metadata: {metadata_file}")
        print(f"   🎵 Notes: {total_notes}")
        print(f"   ⏱️  Duration: {max_tick} ticks")
        print(f"   🎯 Resolution: {ticks_per_beat} ticks per beat")
        print(f"   🎹 MIDI pitch range: {unique_midi_pitches} unique pitches")
        print(f"   🎼 LilyPond notation: {unique_pitches} unique representations")
        print(f"   🎚️  Channels: {channels_used}")
        
        print()
        print("💡 Next steps:")
        print("   - Use the CSV data for note events with tick timing")
        print("   - Use the metadata JSON for MIDI timing resolution")
        print("   - Implement real-time synchronization in JavaScript")
        print("   - Convert ticks to seconds using: seconds = (tick / ticks_per_beat) * (60 / bpm)")
        
        print()
        print("🎉 MIDI note extraction completed successfully!")
        
    except Exception as e:
        print(f"❌ Error processing MIDI file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()