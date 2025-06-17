#!/usr/bin/env python3
"""
sync_with_audio.py

Audio-Synced YAML Generation for Dynamic Tempo Synchronization
=============================================================

This script creates audio-synchronized timing data by combining:
1. Bar-aligned noteheads from BWV000_note_heads.csv (with bar/bar_moment)
2. Existing MIDI-based sync data from BWV000.yaml
3. Detected audio beats from detected_beats.yaml

The result is an alternate BWV000_audio.yaml file with dynamic tempo timing
that can sync score animation with real performance audio containing tempo changes.

Input Files:
- BWV000_note_heads.csv: Noteheads with bar timing attributes
- BWV000.yaml: Existing MIDI-based sync data
- detected_beats.yaml: Audio beat detection results

Output:
- BWV000_audio.yaml: Audio-synchronized timing data for dynamic tempo playback
"""

import argparse
import csv
import yaml
import pandas as pd
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple
import re

def load_noteheads_with_bars(csv_file: Path) -> Dict[str, Dict]:
    """
    Load notehead data with bar timing from CSV file.
    
    Returns:
        Dictionary mapping data_ref to notehead info including bar timing
    """
    noteheads = {}
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data_ref = row['data_ref']
                
                # Parse bar timing (may be empty strings)
                bar_moment = row.get('bar_moment', '').strip()
                bar = row.get('bar', '').strip()
                
                noteheads[data_ref] = {
                    'snippet': row['snippet'],
                    'x': float(row['x']),
                    'y': float(row['y']),
                    'bar_moment': bar_moment if bar_moment else None,
                    'bar': float(bar) if bar else None
                }
                
        print(f"Loaded {len(noteheads)} noteheads from {csv_file}")
        bar_count = sum(1 for n in noteheads.values() if n['bar_moment'] is not None)
        print(f"Found {bar_count} noteheads with bar timing")
        
        return noteheads
        
    except Exception as e:
        print(f"Error loading noteheads CSV {csv_file}: {e}")
        return {}

def load_detected_beats(yaml_file: Path) -> List[float]:
    """Load detected beats from YAML file."""
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
        
        # Handle different possible YAML structures
        if 'concatenated' in data and 'beats' in data['concatenated']:
            beats = data['concatenated']['beats']
        elif 'beats' in data:
            beats = data['beats']
        else:
            raise ValueError(f"Unexpected YAML structure in {yaml_file}")
            
        print(f"Loaded {len(beats)} detected beats from {yaml_file}")
        return beats
        
    except Exception as e:
        print(f"Error loading detected beats {yaml_file}: {e}")
        return []

def load_sync_data(yaml_file: Path) -> Dict:
    """Load existing MIDI-based sync data."""
    try:
        with open(yaml_file, 'r') as f:
            sync_data = yaml.safe_load(f)
            
        print(f"Loaded sync data from {yaml_file}")
        flow_items = len(sync_data.get('flow', []))
        print(f"Found {flow_items} flow items")
        
        return sync_data
        
    except Exception as e:
        print(f"Error loading sync data {yaml_file}: {e}")
        return {}

def calculate_anacrusis_info(bars_info: Dict) -> Dict:
    """
    Calculate anacrusis (pickup bar) information by working backwards from bar 1.
    
    Args:
        bars_info: Bar analysis from calculate_bar_durations
    
    Returns:
        Anacrusis information or None if no anacrusis
    """
    if 1.0 not in bars_info:
        return None
    
    bar1_info = bars_info[1.0]
    bar1_start_tick = bar1_info['start_tick']
    bar1_moment = bar1_info['start_moment']
    
    # Parse bar 1 moment to determine anacrusis length
    def parse_moment_to_quarters(moment_str):
        if '/' in moment_str:
            num, den = moment_str.split('/')
            return int(num)
        return int(float(moment_str) * 4)
    
    bar1_quarter = parse_moment_to_quarters(bar1_moment)
    
    # Anacrusis has (bar1_quarter) beats before bar 1
    # Each beat = 384 ticks (from bar analysis)
    ticks_per_beat = 384  # We know this from our analysis
    anacrusis_duration_ticks = bar1_quarter * ticks_per_beat
    anacrusis_start_tick = bar1_start_tick - anacrusis_duration_ticks
    
    anacrusis_info = {
        'bar_number': 0.0,
        'start_tick': anacrusis_start_tick,
        'duration_ticks': anacrusis_duration_ticks,
        'duration_beats': bar1_quarter,
        'start_moment': "0/4",
        'end_moment': bar1_moment
    }
    
    print(f"\n📈 Anacrusis Analysis:")
    print(f"   Bar 1 starts at tick {bar1_start_tick} with moment {bar1_moment}")
    print(f"   Anacrusis: {anacrusis_duration_ticks} ticks = {bar1_quarter} beats")
    print(f"   Anacrusis range: tick {anacrusis_start_tick} to {bar1_start_tick}")
    
    return anacrusis_info

def calculate_bar_durations(noteheads: Dict[str, Dict], sync_data: Dict, config_data: Dict = None) -> Dict:
    """
    Calculate bar durations in both ticks and beats by analyzing bar structure.
    
    Args:
        noteheads: Notehead data with bar timing information
        sync_data: MIDI sync data with tick timing
    
    Returns:
        Dictionary with bar analysis: {bar_number: {'start_tick': int, 'start_moment': str, 'duration_ticks': int, 'duration_beats': int}}
    """
    # Extract all bars that have noteheads assigned to them
    bars_info = {}
    
    # First, collect all bar information from noteheads
    for data_ref, notehead in noteheads.items():
        if notehead['bar'] is not None and notehead['bar_moment'] is not None:
            bar_num = notehead['bar']
            bar_moment = notehead['bar_moment']
            
            # Find corresponding tick information from sync_data
            # Look for this data_ref in the flow to get tick timing
            for flow_item in sync_data.get('flow', []):
                if len(flow_item) >= 4 and isinstance(flow_item[3], list):
                    if data_ref in flow_item[3]:  # found matching href
                        start_tick = flow_item[0]
                        
                        if bar_num not in bars_info:
                            bars_info[bar_num] = {
                                'start_tick': start_tick,
                                'start_moment': bar_moment,
                                'noteheads': []
                            }
                        
                        bars_info[bar_num]['noteheads'].append({
                            'data_ref': data_ref,
                            'tick': start_tick,
                            'moment': bar_moment
                        })
                        break
    
    # Parse moments as fractions and calculate durations
    def parse_moment(moment_str):
        """Parse moment string like '1/4' or '5/4' to decimal."""
        if '/' in moment_str:
            num, den = moment_str.split('/')
            return float(num) / float(den)
        return float(moment_str)
    
    # Sort bars and calculate durations
    sorted_bars = sorted(bars_info.keys())
    
    # First, calculate durations for all bars except the last
    standard_duration_ticks = None
    standard_duration_beats = None
    
    for i, bar_num in enumerate(sorted_bars):
        if i == len(sorted_bars) - 1:
            # Last bar - will handle separately
            continue
        else:
            # Calculate duration to next bar
            next_bar_num = sorted_bars[i + 1]
            next_bar_info = bars_info[next_bar_num]
            
            current_start_tick = bars_info[bar_num]['start_tick']
            next_start_tick = next_bar_info['start_tick']
            
            current_start_moment = parse_moment(bars_info[bar_num]['start_moment'])
            next_start_moment = parse_moment(next_bar_info['start_moment'])
            
            duration_ticks = next_start_tick - current_start_tick
            duration_beats = int(round((next_start_moment - current_start_moment) * 4))  # Assuming 4/4 time for now
            
            bars_info[bar_num]['duration_ticks'] = duration_ticks
            bars_info[bar_num]['duration_beats'] = duration_beats
            bars_info[bar_num]['end_moment'] = next_bar_info['start_moment']
            
            # Store standard duration for last bar
            if standard_duration_ticks is None:
                standard_duration_ticks = duration_ticks
                standard_duration_beats = duration_beats
    
    # Handle last bar: check for lastMeasureDuration in config, otherwise assume same duration as other bars
    if len(sorted_bars) > 0:
        last_bar_num = sorted_bars[-1]
        
        # Check config for last measure duration
        last_measure_duration = None
        if config_data and 'musicalStructure' in config_data and 'lastMeasureDuration' in config_data['musicalStructure']:
            last_measure_duration_str = config_data['musicalStructure']['lastMeasureDuration']
            # Parse fraction like "3/4"
            if '/' in str(last_measure_duration_str):
                num, den = str(last_measure_duration_str).split('/')
                last_measure_duration = int(num)  # beats in last measure
            else:
                last_measure_duration = int(float(last_measure_duration_str) * 4)  # convert to beats
        
        if standard_duration_ticks is not None:
            if last_measure_duration is not None:
                # Use custom last measure duration from config
                ticks_per_beat = standard_duration_ticks // standard_duration_beats
                last_bar_duration_ticks = last_measure_duration * ticks_per_beat
                last_bar_duration_beats = last_measure_duration
                
                bars_info[last_bar_num]['duration_ticks'] = last_bar_duration_ticks
                bars_info[last_bar_num]['duration_beats'] = last_bar_duration_beats
                
                # Calculate end moment
                current_start_moment = parse_moment(bars_info[last_bar_num]['start_moment'])
                end_moment_quarter = int(current_start_moment * 4) + last_bar_duration_beats
                bars_info[last_bar_num]['end_moment'] = f"{end_moment_quarter}/4"
                
                print(f"   Last bar {last_bar_num}: Using config lastMeasureDuration ({last_bar_duration_ticks} ticks = {last_bar_duration_beats} beats)")
            else:
                # Fallback to standard duration
                bars_info[last_bar_num]['duration_ticks'] = standard_duration_ticks
                bars_info[last_bar_num]['duration_beats'] = standard_duration_beats
                
                # Calculate end moment
                current_start_moment = parse_moment(bars_info[last_bar_num]['start_moment'])
                end_moment_quarter = int(current_start_moment * 4) + standard_duration_beats
                bars_info[last_bar_num]['end_moment'] = f"{end_moment_quarter}/4"
                
                print(f"   Last bar {last_bar_num}: Assuming standard duration ({standard_duration_ticks} ticks = {standard_duration_beats} beats)")
        else:
            # Fallback if we couldn't determine standard duration
            bars_info[last_bar_num]['duration_ticks'] = None
            bars_info[last_bar_num]['duration_beats'] = None
            bars_info[last_bar_num]['end_moment'] = None
    
    print(f"\n📊 Bar Analysis:")
    for bar_num in sorted_bars:
        info = bars_info[bar_num]
        print(f"   Bar {bar_num}: tick {info['start_tick']}, moment {info['start_moment']}, "
              f"duration: {info['duration_ticks']} ticks = {info['duration_beats']} beats")
    
    return bars_info

def assign_noteheads_to_beats(noteheads: Dict[str, Dict], sync_data: Dict, bars_info: Dict, anacrusis_info: Dict = None) -> Dict[str, Dict]:
    """
    Assign beat_moment to each notehead based on its tick position within bars.
    
    Args:
        noteheads: Notehead data 
        sync_data: MIDI sync data with tick timing
        bars_info: Bar analysis from calculate_bar_durations
    
    Returns:
        Updated noteheads with beat_moment assigned
    """
    # Create a mapping from data_ref to tick position
    tick_map = {}
    for flow_item in sync_data.get('flow', []):
        if len(flow_item) >= 4 and isinstance(flow_item[3], list):
            start_tick = flow_item[0]
            for href in flow_item[3]:
                tick_map[href] = start_tick
    
    # Parse moment to get quarter note position
    def parse_moment_to_quarters(moment_str):
        """Parse '1/4' to 1, '5/4' to 5, etc."""
        if '/' in moment_str:
            num, den = moment_str.split('/')
            return int(num)
        return int(float(moment_str) * 4)
    
    updated_noteheads = noteheads.copy()
    beat_assignments = []
    
    # For each notehead, calculate its beat_moment
    for data_ref, notehead in updated_noteheads.items():
        if data_ref not in tick_map:
            notehead['beat_moment'] = None
            continue
            
        notehead_tick = tick_map[data_ref]
        
        # Check if this notehead belongs to anacrusis first
        if anacrusis_info and anacrusis_info['start_tick'] <= notehead_tick < anacrusis_info['start_tick'] + anacrusis_info['duration_ticks']:
            # Handle anacrusis
            ticks_into_anacrusis = notehead_tick - anacrusis_info['start_tick']
            ticks_per_beat = 384  # Known from our analysis
            beat_in_anacrusis = ticks_into_anacrusis // ticks_per_beat
            beat_moment = f"{beat_in_anacrusis}/4"  # 0/4 for first anacrusis beat
            
            notehead['beat_moment'] = beat_moment
            
            # Check if exactly on beat
            expected_beat_tick = anacrusis_info['start_tick'] + (beat_in_anacrusis * ticks_per_beat)
            is_on_beat = (notehead_tick == expected_beat_tick)
            
            beat_assignments.append({
                'data_ref': data_ref,
                'tick': notehead_tick,
                'bar': 0.0,  # Anacrusis
                'beat_in_bar': beat_in_anacrusis,
                'beat_moment': beat_moment,
                'on_beat': is_on_beat
            })
            continue
        
        # Find which regular bar this notehead belongs to
        assigned_bar = None
        for bar_num, bar_info in bars_info.items():
            if bar_info['duration_ticks'] is None:  # Last bar
                if notehead_tick >= bar_info['start_tick']:
                    assigned_bar = bar_num
                    break
            else:
                if bar_info['start_tick'] <= notehead_tick < (bar_info['start_tick'] + bar_info['duration_ticks']):
                    assigned_bar = bar_num
                    break
        
        if assigned_bar is None:
            notehead['beat_moment'] = None
            continue
            
        bar_info = bars_info[assigned_bar]
        
        # Skip if bar has no duration info (shouldn't happen now)
        if bar_info['duration_ticks'] is None or bar_info['duration_beats'] is None:
            notehead['beat_moment'] = None
            continue
        
        # Calculate beat position within the bar
        ticks_into_bar = notehead_tick - bar_info['start_tick']
        ticks_per_beat = bar_info['duration_ticks'] // bar_info['duration_beats']
        beat_in_bar = ticks_into_bar // ticks_per_beat  # 0, 1, 2, 3 for 4-beat bar
        
        # Calculate the beat_moment (quarter note position)
        bar_start_quarter = parse_moment_to_quarters(bar_info['start_moment'])
        beat_moment_quarter = bar_start_quarter + beat_in_bar
        beat_moment = f"{beat_moment_quarter}/4"
        
        notehead['beat_moment'] = beat_moment
        
        # Check if this notehead is exactly on a beat boundary
        expected_beat_tick = bar_info['start_tick'] + (beat_in_bar * ticks_per_beat)
        is_on_beat = (notehead_tick == expected_beat_tick)
        
        beat_assignments.append({
            'data_ref': data_ref,
            'tick': notehead_tick,
            'bar': assigned_bar,
            'beat_in_bar': beat_in_bar,
            'beat_moment': beat_moment,
            'on_beat': is_on_beat
        })
    
    # Display beat assignments
    print(f"\n🎵 Beat Assignment Analysis:")
    on_beat_count = sum(1 for b in beat_assignments if b['on_beat'])
    print(f"   Total noteheads processed: {len(beat_assignments)}")
    print(f"   Noteheads exactly on beats: {on_beat_count}")
    
    # Show some examples
    print(f"   Examples:")
    for assignment in beat_assignments[:10]:  # Show first 10
        status = "ON BEAT" if assignment['on_beat'] else "off beat"
        print(f"      Tick {assignment['tick']}: Bar {assignment['bar']}, Beat {assignment['beat_in_bar']}, "
              f"Moment {assignment['beat_moment']} ({status})")
    
    if len(beat_assignments) > 10:
        print(f"      ... and {len(beat_assignments) - 10} more")
    
    return updated_noteheads, beat_assignments

def verify_beat_tick_counts(sync_data: Dict, detected_beats: List[float], beat_assignments: List[Dict]) -> Dict:
    """
    Verify that the number of detected beats matches the number of distinct ticks where noteheads are on beats.
    
    Args:
        sync_data: MIDI sync data with tick timing
        detected_beats: List of detected audio beats
        beat_assignments: List of beat assignment data from assign_noteheads_to_beats
    
    Returns:
        Verification analysis dictionary
    """
    # Get distinct ticks where noteheads are exactly on beats
    on_beat_ticks = set()
    for assignment in beat_assignments:
        if assignment['on_beat']:
            on_beat_ticks.add(assignment['tick'])
    
    detected_beat_count = len(detected_beats)
    distinct_beat_ticks = len(on_beat_ticks)
    
    print(f"\n🔍 Beat-Tick Verification:")
    print(f"   Detected audio beats: {detected_beat_count}")
    print(f"   Distinct ticks with noteheads on beats: {distinct_beat_ticks}")
    
    if detected_beat_count == distinct_beat_ticks:
        print(f"   ✅ Perfect match: detected beats = distinct beat ticks")
    else:
        print(f"   ⚠️  Mismatch: {detected_beat_count} detected vs {distinct_beat_ticks} distinct beat ticks")
        difference = detected_beat_count - distinct_beat_ticks
        print(f"      Difference: {difference}")
        
        if difference > 0:
            print(f"      → More detected beats than beat ticks (missing {difference} beat positions)")
        else:
            print(f"      → More beat ticks than detected beats (extra {-difference} beat positions)")
    
    # Show the distinct beat ticks for analysis
    sorted_ticks = sorted(on_beat_ticks)
    print(f"   Distinct beat ticks found:")
    print(f"      First 10: {sorted_ticks[:10]}")
    if len(sorted_ticks) > 10:
        print(f"      Last 10: {sorted_ticks[-10:]}")
        print(f"      Total range: {sorted_ticks[0]} to {sorted_ticks[-1]}")
    
    return {
        'detected_beats': detected_beat_count,
        'distinct_beat_ticks': distinct_beat_ticks,
        'match': detected_beat_count == distinct_beat_ticks,
        'difference': detected_beat_count - distinct_beat_ticks,
        'beat_ticks': sorted_ticks
    }

def calculate_proportional_beat_ticks(verification: Dict, detected_beats: List[float]) -> Dict[int, int]:
    """
    Calculate new tick values for beat positions using proportional mapping.
    
    Formula: [new_tick[i] - first_tick] / [last_tick - first_tick] = [beat[i] - first_beat] / [last_beat - first_beat]
    
    Args:
        verification: Beat-tick verification results
        detected_beats: List of detected audio beats
    
    Returns:
        Dictionary mapping old_tick -> new_tick for beat positions
    """
    beat_ticks = verification['beat_ticks']  # Sorted list of distinct beat ticks
    
    if len(beat_ticks) != len(detected_beats):
        print(f"❌ Error: {len(beat_ticks)} beat ticks vs {len(detected_beats)} detected beats")
        return {}
    
    if len(beat_ticks) < 2:
        print(f"❌ Error: Need at least 2 beat positions for proportional mapping")
        return {}
    
    first_tick = beat_ticks[0]
    last_tick = beat_ticks[-1]
    first_beat = detected_beats[0]
    last_beat = detected_beats[-1]
    
    tick_range = last_tick - first_tick
    beat_range = last_beat - first_beat
    
    print(f"\n🔄 Proportional Beat Tick Calculation:")
    print(f"   First tick: {first_tick} → First beat: {first_beat:.3f}s")
    print(f"   Last tick: {last_tick} → Last beat: {last_beat:.3f}s")
    print(f"   Tick range: {tick_range} ticks")
    print(f"   Beat range: {beat_range:.3f} seconds")
    
    # Calculate new ticks for each beat position using pure proportional mapping
    # Map original tick range [first_tick, last_tick] to detected beat time range [first_beat, last_beat]
    # but keep the result in tick coordinate system (not time-based)
    tick_mapping = {}
    
    for i, (old_tick, detected_beat) in enumerate(zip(beat_ticks, detected_beats)):
        # Map detected beat times to tick values that represent actual time positions
        # Use a time-based tick system where each tick represents a small time unit
        # Scale detected beat time to create meaningful tick values for visualization
        time_scale_factor = 1000  # 1 tick = 1 millisecond
        new_tick = int(round(detected_beat * time_scale_factor))
        
        tick_mapping[old_tick] = new_tick
        
        if i < 5 or i >= len(beat_ticks) - 5:  # Show first and last 5
            print(f"   Tick {old_tick:5d} → {new_tick:5d} (beat {i}: {detected_beat:.3f}s)")
        elif i == 5:
            print(f"   ... ({len(beat_ticks) - 10} intermediate mappings)")
    
    return tick_mapping

def interpolate_non_beat_ticks(sync_data: Dict, beat_tick_mapping: Dict[int, int]) -> Dict[int, int]:
    """
    Interpolate new tick values for noteheads that are not exactly on beats.
    
    Formula: (N.newtick - O0.newtick) / (O1.newtick - O0.newtick) = (N.oldtick - O0.oldtick) / (O1.oldtick - O0.oldtick)
    
    Args:
        sync_data: MIDI sync data with tick timing
        beat_tick_mapping: Dictionary mapping old_tick -> new_tick for beat positions
    
    Returns:
        Complete tick mapping (beat ticks + interpolated ticks)
    """
    # Get all ticks from sync data
    all_ticks = set()
    for flow_item in sync_data.get('flow', []):
        if len(flow_item) >= 4 and isinstance(flow_item[3], list):
            all_ticks.add(flow_item[0])  # start tick
            if flow_item[1] is not None:  # not a bar marker
                all_ticks.add(flow_item[2])  # end tick
    
    # Sort beat ticks for interpolation bounds
    beat_ticks = sorted(beat_tick_mapping.keys())
    complete_mapping = beat_tick_mapping.copy()
    
    # Find ticks that need interpolation
    non_beat_ticks = []
    for tick in all_ticks:
        if tick not in beat_tick_mapping:
            non_beat_ticks.append(tick)
    
    print(f"\n🔄 Interpolating Non-Beat Ticks:")
    print(f"   Beat ticks (anchors): {len(beat_ticks)}")
    print(f"   Non-beat ticks to interpolate: {len(non_beat_ticks)}")
    
    interpolated_count = 0
    
    for old_tick in sorted(non_beat_ticks):
        # Find surrounding beat ticks O0 and O1
        o0_tick = None
        o1_tick = None
        
        for i, beat_tick in enumerate(beat_ticks):
            if beat_tick <= old_tick:
                o0_tick = beat_tick
            elif beat_tick > old_tick and o1_tick is None:
                o1_tick = beat_tick
                break
        
        if o0_tick is None or o1_tick is None:
            # Handle edge cases (before first beat or after last beat)
            if o0_tick is None:
                # Before first beat - extrapolate backwards
                if len(beat_ticks) >= 2:
                    o0_tick = beat_ticks[0]
                    o1_tick = beat_ticks[1]
                    # Use extrapolation logic
                else:
                    complete_mapping[old_tick] = old_tick  # Fallback
                    continue
            elif o1_tick is None:
                # After last beat - extrapolate forwards
                if len(beat_ticks) >= 2:
                    o0_tick = beat_ticks[-2]
                    o1_tick = beat_ticks[-1]
                    # Use extrapolation logic
                else:
                    complete_mapping[old_tick] = old_tick  # Fallback
                    continue
        
        # Get old and new tick values for anchors
        o0_old = o0_tick
        o1_old = o1_tick
        o0_new = beat_tick_mapping[o0_tick]
        o1_new = beat_tick_mapping[o1_tick]
        
        # Apply interpolation formula
        if o1_old != o0_old:  # Avoid division by zero
            # (N.newtick - O0.newtick) / (O1.newtick - O0.newtick) = (N.oldtick - O0.oldtick) / (O1.oldtick - O0.oldtick)
            old_ratio = (old_tick - o0_old) / (o1_old - o0_old)
            new_tick = o0_new + int(round(old_ratio * (o1_new - o0_new)))
        else:
            new_tick = o0_new  # Same position
        
        complete_mapping[old_tick] = new_tick
        interpolated_count += 1
        
        # Show some examples
        if interpolated_count <= 10:
            print(f"   Tick {old_tick:5d} → {new_tick:5d} (between {o0_old}-{o1_old} → {o0_new}-{o1_new})")
        elif interpolated_count == 11:
            print(f"   ... and {len(non_beat_ticks) - 10} more interpolations")
    
    print(f"   ✅ Interpolated {interpolated_count} non-beat ticks")
    
    return complete_mapping

def apply_tick_mappings_to_flow(sync_data: Dict, complete_tick_mapping: Dict[int, int], detected_beats: List[float] = None) -> Dict:
    """
    Apply complete tick mappings to create final audio-synced flow data.
    
    Args:
        sync_data: Original MIDI sync data
        complete_tick_mapping: Complete mapping from old_tick -> new_tick
    
    Returns:
        Audio-synced sync data with transformed timing
    """
    audio_sync_data = sync_data.copy()
    
    if 'flow' not in audio_sync_data:
        return audio_sync_data
    
    print(f"\n🔄 Applying Tick Mappings to Flow Data:")
    print(f"   Total tick mappings available: {len(complete_tick_mapping)}")
    
    transformed_items = 0
    unchanged_items = 0
    
    # Transform each flow item
    for i, flow_item in enumerate(audio_sync_data['flow']):
        if len(flow_item) >= 4:
            start_tick = flow_item[0]
            channel = flow_item[1]
            end_tick = flow_item[2]
            info = flow_item[3]
            
            # Transform start tick
            new_start_tick = complete_tick_mapping.get(start_tick, start_tick)
            
            # Transform end tick (if not None and not a bar marker)
            if channel is not None and end_tick is not None:
                new_end_tick = complete_tick_mapping.get(end_tick, end_tick)
            else:
                new_end_tick = end_tick
            
            # Update flow item
            audio_sync_data['flow'][i] = [new_start_tick, channel, new_end_tick, info]
            
            # Track changes
            if new_start_tick != start_tick or (new_end_tick != end_tick and end_tick is not None):
                transformed_items += 1
                
                # Show some examples of transformations
                if transformed_items <= 5:
                    if end_tick is not None:
                        print(f"   Item {i}: [{start_tick}, {channel}, {end_tick}] → [{new_start_tick}, {channel}, {new_end_tick}]")
                    else:
                        print(f"   Item {i}: [{start_tick}, {channel}, {end_tick}] → [{new_start_tick}, {channel}, {new_end_tick}]")
                elif transformed_items == 6:
                    print(f"   ... and {len(audio_sync_data['flow']) - 5} more transformations")
            else:
                unchanged_items += 1
    
    print(f"   ✅ Transformed {transformed_items} flow items")
    print(f"   📌 {unchanged_items} items unchanged (no mapping needed)")
    
    # Remove tickToSecondRatio from metadata as it's no longer relevant
    if 'meta' in audio_sync_data and 'tickToSecondRatio' in audio_sync_data['meta']:
        del audio_sync_data['meta']['tickToSecondRatio']
        print(f"   🗑️  Removed obsolete tickToSecondRatio from metadata")
    
    # Update metadata to reflect new time-based tick system
    if 'meta' in audio_sync_data and complete_tick_mapping:
        all_new_ticks = list(complete_tick_mapping.values())
        if all_new_ticks:
            audio_sync_data['meta']['minTick'] = min(all_new_ticks)
            audio_sync_data['meta']['maxTick'] = max(all_new_ticks)
            print(f"   🔄 Updated metadata: minTick={audio_sync_data['meta']['minTick']}, maxTick={audio_sync_data['meta']['maxTick']}")
    
    # Update musicStartSeconds based on first detected beat
    if 'meta' in audio_sync_data and detected_beats and len(detected_beats) > 0:
        first_beat_time = detected_beats[0]
        audio_sync_data['meta']['musicStartSeconds'] = first_beat_time
        print(f"   🎵 Updated musicStartSeconds to {first_beat_time:.3f}s (first detected beat)")
    
    return audio_sync_data

def apply_tick_mappings_to_flow_debug_beats_only(sync_data: Dict, complete_tick_mapping: Dict[int, int], beat_assignments: List[Dict]) -> Dict:
    """
    DEBUG VERSION: Apply tick mappings but only include noteheads that are exactly on beats.
    This helps verify that beat-aligned noteheads map correctly to detected beats.
    
    Args:
        sync_data: Original MIDI sync data
        complete_tick_mapping: Complete mapping from old_tick -> new_tick
        beat_assignments: List of beat assignment data for filtering
    
    Returns:
        Audio-synced sync data with only beat-aligned noteheads
    """
    audio_sync_data = sync_data.copy()
    
    if 'flow' not in audio_sync_data:
        return audio_sync_data
    
    print(f"\n🐛 DEBUG: Applying Tick Mappings (BEATS ONLY):")
    print(f"   Total tick mappings available: {len(complete_tick_mapping)}")
    
    # Create a set of ticks that are exactly on beats
    on_beat_ticks = set()
    for assignment in beat_assignments:
        if assignment['on_beat']:
            on_beat_ticks.add(assignment['tick'])
    print(f"   🐛 Found {len(on_beat_ticks)} distinct ticks exactly on beats: {sorted(on_beat_ticks)[:10]}...")
    
    transformed_items = 0
    unchanged_items = 0
    filtered_items = 0
    new_flow = []
    
    # Transform each flow item, filtering to beat-aligned noteheads only
    for i, flow_item in enumerate(audio_sync_data['flow']):
        if len(flow_item) >= 4:
            start_tick = flow_item[0]
            channel = flow_item[1]
            end_tick = flow_item[2]
            info = flow_item[3]
            
            # Keep bars and fermatas
            if info == 'bar' or info == 'fermata':
                new_start_tick = complete_tick_mapping.get(start_tick, start_tick)
                new_end_tick = end_tick  # bars/fermatas don't have end ticks to transform
                new_flow.append([new_start_tick, channel, new_end_tick, info])
                if new_start_tick != start_tick:
                    transformed_items += 1
                else:
                    unchanged_items += 1
                continue
            
            # For noteheads: only keep those exactly on beats
            if channel is not None and isinstance(info, list):
                # This is a notehead - check if it's on a beat
                if start_tick not in on_beat_ticks:
                    filtered_items += 1
                    continue  # Skip this notehead - it's not exactly on a beat
                
                # This notehead is exactly on a beat - keep it
                new_start_tick = complete_tick_mapping.get(start_tick, start_tick)
                new_end_tick = complete_tick_mapping.get(end_tick, end_tick)
                new_flow.append([new_start_tick, channel, new_end_tick, info])
                
                if new_start_tick != start_tick or new_end_tick != end_tick:
                    transformed_items += 1
                    # Show beat mappings for debugging
                    if transformed_items <= 10:
                        print(f"   🐛 Beat notehead {i}: tick {start_tick} → {new_start_tick} (should match detected beat)")
                else:
                    unchanged_items += 1
    
    # Update flow with filtered items
    audio_sync_data['flow'] = new_flow
    
    print(f"   ✅ Transformed {transformed_items} flow items")
    print(f"   📌 {unchanged_items} items unchanged")
    print(f"   🐛 Filtered out {filtered_items} noteheads (not exactly on beats)")
    print(f"   🐛 Final flow contains {len(new_flow)} items ({len([f for f in new_flow if isinstance(f[3], list)])} noteheads)")
    
    # Remove tickToSecondRatio from metadata
    if 'meta' in audio_sync_data and 'tickToSecondRatio' in audio_sync_data['meta']:
        del audio_sync_data['meta']['tickToSecondRatio']
        print(f"   🗑️  Removed obsolete tickToSecondRatio from metadata")
    
    return audio_sync_data

def save_audio_synced_yaml(audio_sync_data: Dict, output_yaml: Path):
    """Save audio-synced data to YAML file with proper formatting."""
    try:
        with open(output_yaml, 'w') as f:
            # Write meta section normally
            meta_data = {k: v for k, v in audio_sync_data.items() if k != 'flow'}
            yaml_content = yaml.dump(meta_data, default_flow_style=False, sort_keys=False)
            f.write(yaml_content)
            
            # Write flow section with custom formatting to match original
            f.write('flow:\n')
            for item in audio_sync_data.get('flow', []):
                # Format each flow item as compact array like original
                # Handle null values (~ in YAML)
                formatted_item = []
                for val in item:
                    if val is None:
                        formatted_item.append('~')
                    elif isinstance(val, list):
                        # Format list with single quotes for strings
                        formatted_list = [f"'{str(v)}'" if isinstance(v, str) else str(v) for v in val]
                        formatted_item.append(f"[{', '.join(formatted_list)}]")
                    else:
                        formatted_item.append(str(val))
                
                f.write(f"- [{', '.join(formatted_item)}]\n")
        print(f"✅ Audio sync data saved to {output_yaml}")
        
    except Exception as e:
        print(f"Error saving output: {e}")
        raise

def load_config_data(config_file: Path) -> Dict:
    """Load configuration data from YAML file."""
    try:
        if config_file and config_file.exists():
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            print(f"Loaded config data from {config_file}")
            return config_data
        else:
            print(f"Config file not provided or doesn't exist: {config_file}")
            return {}
    except Exception as e:
        print(f"Warning: Error loading config file {config_file}: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description='Generate audio-synchronized timing data for dynamic tempo playback')
    parser.add_argument('noteheads_csv', help='Input noteheads CSV with bar timing')
    parser.add_argument('sync_yaml', help='Input MIDI-based sync YAML file')
    parser.add_argument('beats_yaml', help='Input detected beats YAML file')
    parser.add_argument('-c', '--config', help='Configuration YAML file (optional)')
    parser.add_argument('-o', '--output', help='Output audio-synced YAML file (default: sync_yaml with _audio suffix)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--debug-beats-only', action='store_true', help='DEBUG: Only include noteheads exactly on beats (for visualization debugging)')
    
    args = parser.parse_args()
    
    noteheads_csv = Path(args.noteheads_csv)
    sync_yaml = Path(args.sync_yaml)
    beats_yaml = Path(args.beats_yaml)
    config_file = Path(args.config) if args.config else None
    
    if args.output:
        output_yaml = Path(args.output)
    else:
        # Default: add _audio suffix to sync file
        output_yaml = sync_yaml.with_name(sync_yaml.stem + '_audio' + sync_yaml.suffix)
    
    print("🎵 Audio Sync Generator")
    print("=" * 50)
    print(f"📄 Noteheads CSV: {noteheads_csv}")
    print(f"📊 Sync YAML: {sync_yaml}")
    print(f"🎧 Detected beats: {beats_yaml}")
    print(f"⚙️  Config file: {config_file or 'None (using defaults)'}")
    print(f"💾 Output: {output_yaml}")
    print()
    
    # Load input data
    print("Loading input data...")
    noteheads = load_noteheads_with_bars(noteheads_csv)
    sync_data = load_sync_data(sync_yaml)
    detected_beats = load_detected_beats(beats_yaml)
    config_data = load_config_data(config_file)
    
    if not noteheads or not sync_data or not detected_beats:
        print("Error: Failed to load required input data")
        sys.exit(1)
    
    print("\n🔧 Implementing corrected algorithm...")
    
    # Step 1: Calculate bar durations to understand beat structure
    print("Step 1: Analyzing bar structure and calculating beat durations...")
    bars_info = calculate_bar_durations(noteheads, sync_data, config_data)
    
    # Step 1b: Calculate anacrusis (pickup bar) information
    print("Step 1b: Analyzing anacrusis (pickup bar)...")
    anacrusis_info = calculate_anacrusis_info(bars_info)
    
    # Step 2: Assign beat_moment to each notehead based on tick position
    print("Step 2: Assigning noteheads to beats within bars...")
    _, beat_assignments = assign_noteheads_to_beats(noteheads, sync_data, bars_info, anacrusis_info)
    
    # Step 2b: Verify beat counts match
    print("Step 2b: Verifying beat counts...")
    verification = verify_beat_tick_counts(sync_data, detected_beats, beat_assignments)
    
    if not verification['match']:
        print("❌ Beat count mismatch - cannot proceed with proportional mapping")
        sys.exit(1)
    
    # Step 3: Calculate proportional beat tick mappings
    print("Step 3: Calculating proportional beat tick mappings...")
    beat_tick_mapping = calculate_proportional_beat_ticks(verification, detected_beats)
    
    # Step 4: Interpolate tick mappings for non-beat noteheads
    print("Step 4: Interpolating ticks for noteheads between beats...")
    complete_tick_mapping = interpolate_non_beat_ticks(sync_data, beat_tick_mapping)
    
    # Step 5: Apply complete tick mappings to create final audio-synced YAML
    if args.debug_beats_only:
        print("Step 5: DEBUG - Applying tick mappings to BEATS ONLY...")
        audio_sync_data = apply_tick_mappings_to_flow_debug_beats_only(sync_data, complete_tick_mapping, beat_assignments)
    else:
        print("Step 5: Applying complete tick mappings to create audio-synced YAML...")
        audio_sync_data = apply_tick_mappings_to_flow(sync_data, complete_tick_mapping, detected_beats)
    
    # Save audio-synced data
    print(f"\nSaving audio-synced data to {output_yaml}...")
    save_audio_synced_yaml(audio_sync_data, output_yaml)
    
    # Display summary
    original_items = len(sync_data.get('flow', []))
    audio_items = len(audio_sync_data.get('flow', []))
    bar_count = sum(1 for n in noteheads.values() if n['bar_moment'] is not None)
    
    print(f"\n📊 Summary:")
    print(f"   Original flow items: {original_items}")
    print(f"   Audio-synced items: {audio_items}")
    print(f"   Bar anchors available: {bar_count}")
    print(f"   Detected beats: {len(detected_beats)}")
    print(f"   Output file: {output_yaml}")

if __name__ == '__main__':
    main()