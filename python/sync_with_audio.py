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

def parse_moment(moment_str):
    """Parse moment string like '1/4' or '5/4' to decimal."""
    if '/' in moment_str:
        num, den = moment_str.split('/')
        return float(num) / float(den)
    return float(moment_str)

def merge_overlapping_bars(bars_info: Dict) -> Dict:
    """
    Merge bars that start at the same tick position into logical units.
    
    Args:
        bars_info: Original bar information
    
    Returns:
        Dictionary of merged bar information
    """
    # Group bars by start_tick
    tick_groups = {}
    for bar_num, bar_info in bars_info.items():
        start_tick = bar_info['start_tick']
        if start_tick not in tick_groups:
            tick_groups[start_tick] = []
        tick_groups[start_tick].append((bar_num, bar_info))
    
    merged_bars = {}
    sorted_ticks = sorted(tick_groups.keys())
    
    print(f"\n🔄 Merging Overlapping Bars:")
    merge_count = 0
    
    for i, tick in enumerate(sorted_ticks):
        bars_at_tick = tick_groups[tick]
        
        if len(bars_at_tick) == 1:
            # Single bar - no merging needed
            bar_num, bar_info = bars_at_tick[0]
            merged_bars[bar_num] = bar_info.copy()
            merged_bars[bar_num]['original_bars'] = [bar_num]
        else:
            # Multiple bars at same tick - merge them
            bars_at_tick.sort(key=lambda x: x[0])  # Sort by bar number
            first_bar_num = bars_at_tick[0][0]
            last_bar_num = bars_at_tick[-1][0]
            
            # Calculate total duration from all bars
            total_duration_ticks = 0
            total_duration_beats = 0
            original_bars = []
            
            for bar_num, bar_info in bars_at_tick:
                if bar_info.get('duration_ticks'):
                    total_duration_ticks += bar_info['duration_ticks']
                if bar_info.get('duration_beats'):
                    total_duration_beats += bar_info['duration_beats']
                original_bars.append(bar_num)
            
            # Create merged bar entry using first bar number as key
            merged_bars[first_bar_num] = {
                'start_tick': tick,
                'start_moment': bars_at_tick[0][1]['start_moment'],  # Use first bar's moment
                'duration_ticks': total_duration_ticks,
                'duration_beats': total_duration_beats,
                'original_bars': original_bars,
                'noteheads': []
            }
            
            # Combine all noteheads from merged bars
            for bar_num, bar_info in bars_at_tick:
                if 'noteheads' in bar_info:
                    merged_bars[first_bar_num]['noteheads'].extend(bar_info['noteheads'])
            
            print(f"   Merged bars {original_bars} → Bar {first_bar_num} "
                  f"(tick {tick}, {total_duration_ticks} ticks = {total_duration_beats} beats)")
            merge_count += 1
    
    # Calculate end moments for merged bars
    sorted_merged = sorted(merged_bars.keys(), key=lambda x: merged_bars[x]['start_tick'])
    
    for i, bar_id in enumerate(sorted_merged):
        if i < len(sorted_merged) - 1:
            # Calculate end moment based on duration
            current_bar = merged_bars[bar_id]
            start_moment = parse_moment(current_bar['start_moment'])
            duration_quarters = current_bar['duration_beats']
            end_moment_quarter = int(start_moment * 4) + duration_quarters
            current_bar['end_moment'] = f"{end_moment_quarter}/4"
        else:
            # Last bar
            current_bar = merged_bars[bar_id]
            start_moment = parse_moment(current_bar['start_moment'])
            duration_quarters = current_bar['duration_beats']
            end_moment_quarter = int(start_moment * 4) + duration_quarters
            current_bar['end_moment'] = f"{end_moment_quarter}/4"
    
    print(f"   ✅ Merged {merge_count} bar groups, total bars after merge: {len(merged_bars)}")
    return merged_bars

def calculate_bar_durations(noteheads: Dict[str, Dict], sync_data: Dict, config_data: Dict = None) -> Dict:
    """
    Calculate bar durations in both ticks and beats by analyzing bar structure.
    Now with overlapping bar merging support.
    
    Args:
        noteheads: Notehead data with bar timing information
        sync_data: MIDI sync data with tick timing
        config_data: Configuration data (for lastMeasureDuration)
    
    Returns:
        Dictionary with merged bar analysis
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
    
    # Now merge overlapping bars
    merged_bars = merge_overlapping_bars(bars_info)
    
    print(f"\n📊 Bar Analysis (after merging):")
    for bar_num in sorted(merged_bars.keys(), key=lambda x: merged_bars[x]['start_tick']):
        info = merged_bars[bar_num]
        original_count = len(info.get('original_bars', [bar_num]))
        if original_count > 1:
            print(f"   Merged Bar {bar_num}: tick {info['start_tick']}, moment {info['start_moment']}, "
                  f"duration: {info['duration_ticks']} ticks = {info['duration_beats']} beats "
                  f"(contains {original_count} original bars)")
        else:
            print(f"   Bar {bar_num}: tick {info['start_tick']}, moment {info['start_moment']}, "
                  f"duration: {info['duration_ticks']} ticks = {info['duration_beats']} beats")
    
    return merged_bars

def calculate_all_beat_positions(merged_bars: Dict, anacrusis_info: Dict = None) -> List[int]:
    """
    Calculate tick positions for ALL theoretical beats, whether they have noteheads or not.
    
    Args:
        merged_bars: Merged bar analysis
        anacrusis_info: Anacrusis information
    
    Returns:
        Sorted list of all theoretical beat tick positions
    """
    all_beat_ticks = []
    
    # Add anacrusis beats if present
    if anacrusis_info and anacrusis_info['duration_beats'] > 0:
        ticks_per_beat = 384  # Standard from our analysis
        for beat in range(anacrusis_info['duration_beats']):
            beat_tick = anacrusis_info['start_tick'] + (beat * ticks_per_beat)
            all_beat_ticks.append(beat_tick)
    
    # Add regular bar beats
    for bar_id in sorted(merged_bars.keys(), key=lambda x: merged_bars[x]['start_tick']):
        bar_info = merged_bars[bar_id]
        start_tick = bar_info['start_tick']
        duration_ticks = bar_info['duration_ticks']
        duration_beats = bar_info['duration_beats']
        
        if duration_ticks and duration_beats:
            ticks_per_beat = duration_ticks // duration_beats
            for beat in range(duration_beats):
                beat_tick = start_tick + (beat * ticks_per_beat)
                all_beat_ticks.append(beat_tick)
    
    all_beat_ticks = sorted(set(all_beat_ticks))  # Remove duplicates and sort
    
    print(f"\n🎯 All Theoretical Beat Positions:")
    print(f"   Total theoretical beats: {len(all_beat_ticks)}")
    print(f"   First 10 beats: {all_beat_ticks[:10]}")
    if len(all_beat_ticks) > 10:
        print(f"   Last 10 beats: {all_beat_ticks[-10:]}")
        print(f"   Range: tick {all_beat_ticks[0]} to {all_beat_ticks[-1]}")
    
    return all_beat_ticks

def assign_noteheads_to_beats(noteheads: Dict[str, Dict], sync_data: Dict, merged_bars: Dict, anacrusis_info: Dict = None) -> Tuple[Dict[str, Dict], List[Dict]]:
    """
    Assign beat_moment to each notehead based on its tick position within merged bars.
    
    Args:
        noteheads: Notehead data 
        sync_data: MIDI sync data with tick timing
        merged_bars: Merged bar analysis from calculate_bar_durations
        anacrusis_info: Anacrusis information
    
    Returns:
        Tuple of (updated noteheads with beat_moment assigned, beat assignments list)
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
        
        # Find which merged bar this notehead belongs to
        assigned_bar = None
        for bar_id, bar_info in merged_bars.items():
            if bar_info['duration_ticks'] is None:  # Last bar
                if notehead_tick >= bar_info['start_tick']:
                    assigned_bar = bar_id
                    break
            else:
                if bar_info['start_tick'] <= notehead_tick < (bar_info['start_tick'] + bar_info['duration_ticks']):
                    assigned_bar = bar_id
                    break
        
        if assigned_bar is None:
            notehead['beat_moment'] = None
            continue
            
        bar_info = merged_bars[assigned_bar]
        
        # Skip if bar has no duration info (shouldn't happen now)
        if bar_info['duration_ticks'] is None or bar_info['duration_beats'] is None:
            notehead['beat_moment'] = None
            continue
        
        # Calculate beat position within the merged bar
        ticks_into_bar = notehead_tick - bar_info['start_tick']
        ticks_per_beat = bar_info['duration_ticks'] // bar_info['duration_beats']
        beat_in_bar = ticks_into_bar // ticks_per_beat  # 0, 1, 2, 3... for merged bar
        
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

def verify_beat_counts_with_interpolation(all_beat_ticks: List[int], detected_beats: List[float], beat_assignments: List[Dict]) -> Dict:
    """
    Verify beat counts using theoretical beats vs detected beats (not notehead beats).
    
    Args:
        all_beat_ticks: All theoretical beat positions
        detected_beats: List of detected audio beats
        beat_assignments: Beat assignment data for anchoring
    
    Returns:
        Verification analysis dictionary
    """
    # Get distinct ticks where noteheads are exactly on beats (for anchoring)
    notehead_beat_ticks = set()
    for assignment in beat_assignments:
        if assignment['on_beat']:
            notehead_beat_ticks.add(assignment['tick'])
    
    theoretical_beat_count = len(all_beat_ticks)
    detected_beat_count = len(detected_beats)
    notehead_anchor_count = len(notehead_beat_ticks)
    
    print(f"\n🔍 Beat Count Verification (Interpolation Method):")
    print(f"   Theoretical beats (from bar structure): {theoretical_beat_count}")
    print(f"   Detected audio beats: {detected_beat_count}")
    print(f"   Notehead anchors available: {notehead_anchor_count}")
    
    if theoretical_beat_count == detected_beat_count:
        print(f"   ✅ Perfect match: theoretical beats = detected beats")
        match = True
    else:
        print(f"   ⚠️  Mismatch: {theoretical_beat_count} theoretical vs {detected_beat_count} detected beats")
        difference = theoretical_beat_count - detected_beat_count
        print(f"      Difference: {difference}")
        match = False
    
    # Show anchor coverage
    anchor_coverage = (notehead_anchor_count / theoretical_beat_count) * 100
    print(f"   📍 Anchor coverage: {anchor_coverage:.1f}% ({notehead_anchor_count}/{theoretical_beat_count})")
    
    if anchor_coverage >= 90:
        print(f"   ✅ Excellent anchor coverage - interpolation should work well")
    elif anchor_coverage >= 70:
        print(f"   ⚠️  Good anchor coverage - interpolation should work")
    else:
        print(f"   ❌ Poor anchor coverage - interpolation may be unreliable")
    
    return {
        'theoretical_beats': theoretical_beat_count,
        'detected_beats': detected_beat_count,
        'notehead_anchors': notehead_anchor_count,
        'match': match,
        'difference': theoretical_beat_count - detected_beat_count,
        'all_beat_ticks': all_beat_ticks,
        'anchor_ticks': sorted(notehead_beat_ticks)
    }

def map_beats_with_interpolation(verification: Dict, detected_beats: List[float]) -> Dict[int, int]:
    """
    Map all theoretical beats to detected beats using notehead anchors and interpolation.
    
    Args:
        verification: Verification results with theoretical beats and anchors
        detected_beats: List of detected audio beats
    
    Returns:
        Dictionary mapping all theoretical beat ticks -> audio time ticks
    """
    all_beat_ticks = verification['all_beat_ticks']
    anchor_ticks = verification['anchor_ticks']
    
    if not verification['match']:
        print(f"❌ Error: Beat counts don't match - cannot proceed")
        return {}
    
    print(f"\n🎯 Beat Mapping with Interpolation:")
    print(f"   Mapping {len(all_beat_ticks)} theoretical beats to {len(detected_beats)} detected beats")
    print(f"   Using {len(anchor_ticks)} notehead anchors for interpolation")
    
    # Create mapping for all beats
    beat_mapping = {}
    time_scale_factor = 1000  # 1 tick = 1 millisecond in output
    
    for i, (theoretical_tick, detected_beat_time) in enumerate(zip(all_beat_ticks, detected_beats)):
        # Map to millisecond-based tick system
        new_tick = int(round(detected_beat_time * time_scale_factor))
        beat_mapping[theoretical_tick] = new_tick
        
        # Show examples, highlighting anchored vs interpolated beats
        if i < 10 or i >= len(all_beat_ticks) - 5:
            is_anchor = theoretical_tick in anchor_ticks
            status = "ANCHOR" if is_anchor else "INTERP"
            print(f"   Beat {i:3d}: tick {theoretical_tick:5d} → {new_tick:5d} ({detected_beat_time:.3f}s) [{status}]")
        elif i == 10:
            anchor_count = sum(1 for tick in all_beat_ticks[:i] if tick in anchor_ticks)
            interp_count = i - anchor_count
            print(f"   ... showing {anchor_count} anchors, {interp_count} interpolated ...")
    
    # Show interpolation statistics
    total_anchors = sum(1 for tick in all_beat_ticks if tick in anchor_ticks)
    total_interpolated = len(all_beat_ticks) - total_anchors
    
    print(f"   📊 Final mapping: {total_anchors} anchored + {total_interpolated} interpolated = {len(beat_mapping)} total beats")
    
    return beat_mapping

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
        detected_beats: List of detected beats for metadata updates
    
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
    
    print("🎵 Audio Sync Generator (Interpolation Method)")
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
    
    print("\n🔧 Implementing interpolation-based beat mapping...")
    
    # Step 1: Calculate bar durations with merging to understand beat structure
    print("Step 1: Analyzing bar structure and calculating beat durations...")
    merged_bars = calculate_bar_durations(noteheads, sync_data, config_data)
    
    # Step 1b: Calculate anacrusis (pickup bar) information
    print("Step 1b: Analyzing anacrusis (pickup bar)...")
    # Simple implementation - no anacrusis detected for this piece
    anacrusis_info = None
    
    # Step 2: Calculate ALL theoretical beat positions
    print("Step 2: Calculating all theoretical beat positions...")
    all_beat_ticks = calculate_all_beat_positions(merged_bars, anacrusis_info)
    
    # Step 3: Assign noteheads to beats for anchoring
    print("Step 3: Assigning noteheads to beats for anchoring...")
    _, beat_assignments = assign_noteheads_to_beats(noteheads, sync_data, merged_bars, anacrusis_info)
    
    # Step 4: Verify theoretical beats vs detected beats
    print("Step 4: Verifying theoretical vs detected beat counts...")
    verification = verify_beat_counts_with_interpolation(all_beat_ticks, detected_beats, beat_assignments)
    
    if not verification['match']:
        print("❌ Beat count mismatch - cannot proceed with beat mapping")
        sys.exit(1)
    
    # Step 5: Map all theoretical beats to detected beats using interpolation
    print("Step 5: Mapping theoretical beats to detected beats...")
    beat_tick_mapping = map_beats_with_interpolation(verification, detected_beats)
    
    # Step 6: Interpolate tick mappings for non-beat noteheads
    print("Step 6: Interpolating ticks for noteheads between beats...")
    complete_tick_mapping = interpolate_non_beat_ticks(sync_data, beat_tick_mapping)
    
    # Step 7: Apply complete tick mappings to create final audio-synced YAML
    print("Step 7: Applying complete tick mappings to create audio-synced YAML...")
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
    print(f"   Theoretical beats: {verification['theoretical_beats']}")
    print(f"   Detected beats: {len(detected_beats)}")
    print(f"   Notehead anchors: {verification['notehead_anchors']}")
    print(f"   Output file: {output_yaml}")

if __name__ == '__main__':
    main()