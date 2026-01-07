"""
LILYPOND MUSIC SCORE SYNCHRONIZATION GENERATOR
==============================================

This script processes LilyPond-generated musical scores to create synchronized playback data.
It combines timing information from JSON notes, musical structure from YAML config, and 
visual elements from SVG notation to generate files suitable for real-time music playback 
with visual highlighting.

WORKFLOW OVERVIEW:
1. Load input files (SVG notation, JSON notes with timing, YAML config, optional fermata CSV)
2. Extract timing metadata and calculate tick-to-second conversions
3. Process musical notes with channel information for multi-track playback
4. Extract bar positions and timing from SVG elements
5. Process fermata data and match to note timing
6. Clean and optimize SVG for web playback (remove unnecessary attributes, add CSS)
7. Generate unified sync data combining notes, bars, and fermatas in chronological order
8. Output cleaned SVG and sync YAML for use in music players

INPUT FILES:
- SVG: LilyPond-generated notation with normalized data-ref attributes (from upstream processing)
- JSON: Note timing data with clean data_ref values in hrefs arrays and spatial coordinates (x, y)
- YAML: Musical structure configuration (measures, duration, etc.)
- CSV (optional): Fermata data with clean data_ref references and positions

OUTPUT FILES:
- Cleaned SVG: Optimized for web with CSS styling and note head z-ordering
- Sync YAML: Unified timeline with notes, bars, and fermatas for synchronized playback

Note: This script expects normalized input from upstream processing. All data_ref values
are already clean and no additional processing is performed.

USAGE EXAMPLE:
python generate_sync.py \
  -is input_score.svg \
  -in timing_notes.json \
  -ic score_config.yaml \
  -os output_score.svg \
  -on sync_data.yaml \
  -if fermata_data.csv
"""

import argparse
import json
import yaml
import xml.etree.ElementTree as ET
import csv
from pathlib import Path

### python ../../../python/generate_sync.py \
###   -is test_optimized.svg \
###   -in test_json_notes.json \
###   -ic test.config.yaml \
###   -os test.svg \
###   -on test.yaml \
###   -if test_note_heads_fermata.csv

# =============================================================================
# SVG NAMESPACE CONFIGURATION
# =============================================================================
# Register XML namespaces to prevent ElementTree from adding ns0: prefixes
# to output SVG elements. This keeps the SVG clean and readable.

# Register XML namespaces to prevent ns0: prefixes in output
ET.register_namespace('', 'http://www.w3.org/2000/svg')
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

# =============================================================================
# UTILITY FUNCTIONS FOR DATA PROCESSING
# =============================================================================

def parse_fraction(fraction_str):
    """
    Parse LilyPond fractional time values into decimal numbers.
    
    LilyPond represents musical time as fractions (e.g., '3/2' for dotted half note,
    '1' for whole note). This converts them to decimal for mathematical operations.
    
    Args:
        fraction_str (str): Fraction like '3/2' or whole number like '1'
        
    Returns:
        float: Decimal representation of the fraction
    """
    if '/' in fraction_str:
        num, den = fraction_str.split('/')
        return float(num) / float(den)
    return float(fraction_str)

def collect_unique_moments(svg_root):
    """
    Extract all unique musical moment values from SVG bar elements.
    
    SVG rect elements with data-bar-moment-main attributes contain timing
    information that corresponds to musical positions within the score.
    This function collects all unique moments for timing calculations.
    
    Args:
        svg_root: ElementTree root of the SVG document
        
    Returns:
        list: Sorted list of unique moment values as floats
    """
    moments = set()
    
    # Find all rect elements with data-bar-moment-main
    for rect in svg_root.findall('.//*[@data-bar-moment-main]'):
        moment_str = rect.get('data-bar-moment-main')
        if moment_str is not None:
            moment = parse_fraction(moment_str)
            moments.add(moment)
    
    return sorted(moments)

# =============================================================================
# FERMATA PROCESSING
# =============================================================================

def process_fermata_csv(fermata_csv_path, notes_data):
    """
    Process fermata CSV data and match to note timing information using spatial interpolation.
    
    The CSV contains fermata positions with clean data_ref references and spatial coordinates.
    For tied notes that don't have direct data_ref matches, spatial interpolation is used
    to calculate reasonable tick positions based on x-coordinates.
    
    Args:
        fermata_csv_path (str): Path to fermata CSV file
        notes_data (list): List of note dictionaries from JSON input (with x, y coordinates)
        
    Returns:
        list: Fermata flow items in format [tick, None, None, 'fermata']
    """
    if not fermata_csv_path or not Path(fermata_csv_path).exists():
        print("No fermata CSV provided or file not found")
        return []
    
    fermata_items = []
    
    # Create a mapping from clean data_refs to notes (including spatial info)
    # Note: JSON hrefs arrays contain clean data_ref values from upstream processing
    data_ref_to_notes = {}
    for note in notes_data:
        for data_ref in note['hrefs']:  # hrefs array contains clean data_ref values
            if data_ref not in data_ref_to_notes:
                data_ref_to_notes[data_ref] = []
            data_ref_to_notes[data_ref].append(note)
    
    print(f"📍 Processing fermata data from {fermata_csv_path}...")
    
    # Read and process fermata CSV
    with open(fermata_csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            data_ref = row.get('data_ref', '').strip()  # Updated: expect data_ref column
            fermata_x = float(row.get('x', 0))
            
            if not data_ref:
                continue
                
            # Data_ref is already clean from upstream processing - use directly
            
            # First try direct match
            if data_ref in data_ref_to_notes:
                # Use the first matching note's on_tick for fermata placement
                note = data_ref_to_notes[data_ref][0]
                fermata_tick = note['on_tick']
                
                fermata_items.append([fermata_tick, None, None, 'fermata'])
                print(f"  Added fermata at tick {fermata_tick} for {data_ref}")
                
            else:
                # No direct match - use spatial interpolation
                print(f"  No direct match for {data_ref}, using spatial interpolation...")
                
                # Sort notes by x coordinate for interpolation
                sorted_notes = sorted(notes_data, key=lambda n: n['x'])
                
                # Find notes before and after the fermata x position
                before_note = None
                after_note = None
                
                for note in sorted_notes:
                    if note['x'] <= fermata_x:
                        before_note = note
                    elif note['x'] > fermata_x and after_note is None:
                        after_note = note
                        break
                
                # Interpolate tick position
                fermata_tick = interpolate_fermata_by_position(
                    fermata_x, before_note, after_note
                )
                
                if fermata_tick is not None:
                    fermata_items.append([fermata_tick, None, None, 'fermata'])
                    print(f"  Added interpolated fermata at tick {fermata_tick} for {data_ref} (x={fermata_x})")
                else:
                    print(f"  Warning: Could not interpolate fermata position for {data_ref}")
    
    print(f"📍 Processed {len(fermata_items)} fermata items")
    return fermata_items

def consolidate_fermatas_by_measure(fermata_items, bars):
    """
    Consolidate multiple fermatas within the same measure into a single fermata.
    
    Musical logic: Multiple fermatas in the same measure represent a single 
    musical gesture. Keep only the fermata with the largest tick position
    (rightmost/latest in the measure).
    
    Args:
        fermata_items (list): List of fermata items [tick, None, None, 'fermata']
        bars (list): List of bar items with tick positions
        
    Returns:
        list: Consolidated fermata items with one fermata per measure max
    """
    if not fermata_items or not bars:
        return fermata_items
    
    print(f"📍 Consolidating {len(fermata_items)} fermatas by measure...")
    
    # First, remove exact duplicates (same tick position)
    unique_fermatas = []
    seen_ticks = set()
    
    for fermata in fermata_items:
        tick = fermata[0]
        if tick not in seen_ticks:
            unique_fermatas.append(fermata)
            seen_ticks.add(tick)
        else:
            print(f"  Removed duplicate fermata at tick {tick}")
    
    if len(unique_fermatas) != len(fermata_items):
        print(f"  Removed {len(fermata_items) - len(unique_fermatas)} exact duplicates")
    
    # Create measure boundaries from bar positions
    bar_ticks = sorted([bar['tick'] for bar in bars])
    print(f"  Bar positions: {bar_ticks}")
    
    # Group fermatas by measure
    measure_fermatas = {}  # measure_index -> list of fermatas in that measure
    
    for fermata in unique_fermatas:
        fermata_tick = fermata[0]
        
        # Find which measure this fermata belongs to
        # Handle edge cases: no bar at beginning/end of timeline
        measure_index = -1  # Default for fermatas before first bar
        
        if not bar_ticks:
            # No bars at all - put all fermatas in measure 0
            measure_index = 0
        else:
            # Check each measure interval
            for i in range(len(bar_ticks)):
                bar_start = bar_ticks[i]
                bar_end = bar_ticks[i + 1] if i + 1 < len(bar_ticks) else float('inf')
                
                if bar_start <= fermata_tick < bar_end:
                    measure_index = i
                    break
            
            # If still -1, fermata is before first bar (pickup measure)
            if measure_index == -1:
                measure_index = -1  # Keep as pickup measure
        
        print(f"  Fermata at tick {fermata_tick} -> measure {measure_index}")
        
        if measure_index not in measure_fermatas:
            measure_fermatas[measure_index] = []
        measure_fermatas[measure_index].append(fermata)
    
    # Consolidate: keep only the fermata with largest tick in each measure
    consolidated_fermatas = []
    
    for measure_index, fermatas_in_measure in measure_fermatas.items():
        measure_name = "pickup" if measure_index == -1 else f"measure {measure_index}"
        
        if len(fermatas_in_measure) == 1:
            # Single fermata - keep as is
            consolidated_fermatas.append(fermatas_in_measure[0])
            print(f"  {measure_name}: kept single fermata at tick {fermatas_in_measure[0][0]}")
        else:
            # Multiple fermatas - keep the one with largest tick (rightmost position)
            latest_fermata = max(fermatas_in_measure, key=lambda f: f[0])
            consolidated_fermatas.append(latest_fermata)
            
            removed_ticks = [f[0] for f in fermatas_in_measure if f != latest_fermata]
            print(f"  {measure_name}: consolidated {len(fermatas_in_measure)} fermatas")
            print(f"    Kept fermata at tick {latest_fermata[0]} (rightmost)")
            print(f"    Removed fermatas at ticks {removed_ticks}")
    
    print(f"📍 Consolidated to {len(consolidated_fermatas)} fermatas ({len(unique_fermatas) - len(consolidated_fermatas)} removed by measure)")
    return consolidated_fermatas

def interpolate_fermata_by_position(fermata_x, before_note, after_note):
    """
    Interpolate fermata tick position based on spatial coordinates.
    
    Args:
        fermata_x (float): X coordinate of fermata
        before_note (dict): Note before fermata position (or None)
        after_note (dict): Note after fermata position (or None)
        
    Returns:
        int: Interpolated tick position for fermata
    """
    try:
        if before_note is None and after_note is None:
            print("    Error: No surrounding notes found for interpolation")
            return None
        elif before_note is None:
            # Fermata is before all notes - place at beginning of first note
            return after_note['on_tick']
        elif after_note is None:
            # Fermata is after all notes - place at end of last note
            return before_note['off_tick']
        else:
            # Interpolate between two notes
            x_span = after_note['x'] - before_note['x']
            if x_span <= 0:
                # Notes at same x position - place at before note
                return before_note['on_tick']
            
            # Calculate relative position (0.0 = before note, 1.0 = after note)
            relative_pos = (fermata_x - before_note['x']) / x_span
            
            # Interpolate between end of before note and start of after note
            tick_span = after_note['on_tick'] - before_note['off_tick']
            fermata_tick = int(before_note['off_tick'] + (relative_pos * tick_span))
            
            print(f"    Interpolated: x={fermata_x} between {before_note['x']} and {after_note['x']} -> tick {fermata_tick}")
            return fermata_tick
            
    except (KeyError, ZeroDivisionError, TypeError) as e:
        print(f"    Error interpolating fermata position: {e}")
        return None

# =============================================================================
# CHANNEL ANALYSIS AND STATISTICS
# =============================================================================

def calculate_channel_stats(notes_data):
    """
    Analyze MIDI channel usage and pitch ranges for multi-track music.
    
    This function processes all notes to determine:
    - Which MIDI channels are used (typically 0-15)
    - Pitch range (min/max MIDI note numbers) for each channel
    - Note count per channel
    
    This information is used for:
    - Instrument assignment in playback
    - Visual layout decisions (staff positioning)
    - Audio mixing and balancing
    
    Args:
        notes_data (list): List of note dictionaries from JSON input
        
    Returns:
        dict: Channel statistics in format:
              {channel_id: {'minPitch': int, 'maxPitch': int, 'count': int}}
    """
    channel_stats = {}
    
    for note in notes_data:
        channel = note.get('channel', 0)  # Default to channel 0 if missing
        pitch = note.get('pitch', 60)  # Default to middle C (MIDI 60) if missing
        
        # Initialize channel statistics if first note on this channel
        if channel not in channel_stats:
            channel_stats[channel] = {
                'minPitch': pitch,
                'maxPitch': pitch,
                'count': 0
            }
        
        # Update channel statistics
        stats = channel_stats[channel]
        stats['minPitch'] = min(stats['minPitch'], pitch)
        stats['maxPitch'] = max(stats['maxPitch'], pitch)
        stats['count'] += 1
    
    # Log channel stats for debugging - helps verify multi-track processing
    print(f"📊 Channel statistics:")
    for channel in sorted(channel_stats.keys()):
        stats = channel_stats[channel]
        avg_pitch = (stats['minPitch'] + stats['maxPitch']) / 2
        print(f"  Channel {channel}: {stats['minPitch']}-{stats['maxPitch']} (avg: {avg_pitch:.1f}), {stats['count']} notes")
    
    return channel_stats

# =============================================================================
# TIMING AND METADATA EXTRACTION
# =============================================================================

def extract_meta(notes_data, config_data):
    """
    Extract comprehensive timing metadata for synchronization calculations.
    
    This function establishes the fundamental structural relationships:
    - MIDI ticks (discrete timing units from note data)
    - Musical moments (fractional measures from LilyPond)
    - Channel statistics for multi-track playback
    - Musical boundaries (measures, moments)
    
    Note: tickToSecondRatio has been removed from the pipeline.
    Timing relationships are now established dynamically using audio detection.
    
    Args:
        notes_data (list): Note timing data from JSON
        config_data (dict): Musical structure configuration from YAML
        
    Returns:
        dict: Comprehensive metadata including musical structure and channel info
    """
    # Collect all tick values (both note-on and note-off events)
    all_ticks = []
    for note in notes_data:
        all_ticks.extend([note['on_tick'], note['off_tick']])
    
    # Musical start is always 0, regardless of when first note occurs
    # This ensures pickup measures and rests are handled correctly
    min_tick = 0  # ← Fixed: don't assume first note = musical start
    max_tick = max(all_ticks)
    
    # Note: tickToSecondRatio has been removed from the pipeline
    # Timing relationships are now established dynamically based on audio detection
    
    # Calculate channel statistics for multi-track support
    channel_stats = calculate_channel_stats(notes_data)
    
    return {
        'totalMeasures': config_data['musicalStructure']['totalMeasures'],
        'minTick': min_tick,
        'maxTick': max_tick,
        'minMoment': 0,
        'maxMoment': config_data['musicalStructure']['totalMeasures'],
        'musicStartSeconds': 0.0,
        'channels': channel_stats
    }

# =============================================================================
# SVG BAR EXTRACTION AND TIMING CONVERSION
# =============================================================================

def extract_bars_from_svg(svg_root, meta, config_data):
    """
    Extract bar/measure timing information from SVG and convert to tick timeline.
    
    This function processes SVG rect elements that represent measure boundaries,
    converting LilyPond's fractional moment system to the tick-based timeline
    used for playback synchronization.
    
    Process:
    1. Find all SVG rect elements with data-bar attributes
    2. Separate pickup bars (no moment data) from regular bars
    3. Calculate musical end point using last measure duration
    4. Scale fractional moments to absolute tick positions
    5. Generate bar events for the unified timeline
    
    Args:
        svg_root: ElementTree root of SVG document
        meta (dict): Timing metadata from extract_meta()
        config_data (dict): Musical structure configuration
        
    Returns:
        list: Bar events sorted by tick position, format:
              [{'number': int, 'moment': float, 'tick': int}, ...]
    """
    # Collect unique bars from SVG rect elements
    unique_bars = {}
    for rect in svg_root.findall('.//*[@data-bar]'):
        bar_num = int(rect.get('data-bar'))
        moment_str = rect.get('data-bar-moment-main')
        if bar_num not in unique_bars:
            unique_bars[bar_num] = moment_str
    
    # Separate pickup bars (null moment) from regular bars
    # Pickup bars occur before the first full measure and have no moment data
    pickup_bar = None
    regular_bars = {}
    
    for bar_num, moment_str in unique_bars.items():
        if moment_str is None:
            pickup_bar = bar_num  # Pickup bar number
        else:
            regular_bars[bar_num] = parse_fraction(moment_str)
    
    # Get sorted moments, remove final end moment if it exceeds total measures
    # LilyPond sometimes generates an extra end-of-piece moment
    moments = sorted(regular_bars.values())
    if len(moments) > meta['totalMeasures']:
        moments = moments[:-1]
    
    # Calculate musical end point for accurate scaling
    # Use last measure duration from config if available, otherwise use max moment
    last_measure_duration_str = config_data.get('musicalStructure', {}).get('lastMeasureDuration')
    if last_measure_duration_str:
        musical_end_moment = moments[-1] + parse_fraction(last_measure_duration_str)
    else:
        musical_end_moment = max(regular_bars.values())
    
    # Scale moments to ticks using absolute positioning from 0
    # This creates the mapping between musical notation and playback timeline
    moment_span = musical_end_moment  # From 0, not from first moment
    tick_span = meta['maxTick'] - meta['minTick'] 
    scale_factor = tick_span / moment_span

    # Generate bar events for timeline
    bars = []

    # Add pickup bar if exists (always at tick 0)
    if pickup_bar is not None:
        bars.append({'number': pickup_bar, 'moment': 0, 'tick': 0})

    # Add regular bars with absolute positioning from start of piece
    for bar_num, moment in regular_bars.items():
        if moment in moments:  # Only bars we want to include
            tick = int(moment * scale_factor)  # Absolute tick position from 0
            bars.append({'number': bar_num, 'moment': moment, 'tick': tick})

    return sorted(bars, key=lambda x: x['tick'])

# =============================================================================
# SVG OPTIMIZATION AND CLEANING
# =============================================================================

def clean_svg(svg_root):
    """
    Optimize SVG for web playback by cleaning attributes and improving structure.
    
    This function performs several optimizations:
    1. Add CSS styling for dynamic note highlighting
    2. Clean bar rectangles (remove unnecessary attributes)
    3. Coalesce note elements (flatten <a><path/></a> to <path data-ref/>)
    4. Reorder note heads for proper z-index (render on top)
    5. Remove redundant fill attributes (handled by CSS)
    
    The result is a cleaner, smaller SVG optimized for JavaScript-based
    music synchronization and highlighting.
    
    Args:
        svg_root: ElementTree root of SVG document (modified in-place)
    """
    
    # =============================================================================
    # ADD CSS STYLING FOR DYNAMIC HIGHLIGHTING
    # =============================================================================
    
    # Add CSS styling to the SVG for dynamic note and bar highlighting
    style_elem = ET.Element('style')
    style_elem.text = """
        /* Bar highlighting rectangles - initially transparent */
        rect[data-bar] {
            fill: none;
        }
        
        /* Note heads and musical symbols */
        path[data-ref] {
            fill: currentColor;
        }
        
        /* Staff lines and other paths */
        path:not([data-ref]) {
            fill: currentColor;
        }
        
        /* Generic rectangles (stems, etc.) */
        rect:not([data-bar]) {
            fill: currentColor;
        }
    """
    
    # Insert style as the first child after any existing style elements
    # This preserves any existing LilyPond-generated styles
    existing_styles = svg_root.findall('.//{http://www.w3.org/2000/svg}style')
    if existing_styles:
        # Insert after the last existing style
        insert_pos = list(svg_root).index(existing_styles[-1]) + 1
    else:
        # Insert as first child
        insert_pos = 0
    
    svg_root.insert(insert_pos, style_elem)
    
    # =============================================================================
    # CLEAN BAR RECTANGLES
    # =============================================================================
    
    # Clean bar rectangles - keep only essential attributes, remove fill
    # This reduces file size and ensures consistent styling via CSS
    for rect in svg_root.findall('.//*[@data-bar]'):
        # Keep only essential attributes for positioning and identification
        essential_attrs = ['x', 'y', 'width', 'height', 'ry', 'transform', 'data-bar']
        attrs_to_remove = []
        
        for attr in rect.attrib:
            if attr not in essential_attrs:
                attrs_to_remove.append(attr)
        
        for attr in attrs_to_remove:
            del rect.attrib[attr]
    
    # =============================================================================
    # COALESCE NOTE ELEMENTS (UPDATED FOR data-ref AND TEXT PRESERVATION)
    # =============================================================================
    
    # Coalesce note <a> elements: move data-ref to contained elements and remove wrapper
    # Normalized pipeline generates: <a data-ref="file.ly:37:21"><path d="..."/></a>
    # We convert to: <path d="..." data-ref="file.ly:37:21"/>
    # IMPORTANT: Also preserve text elements (markup like "sempre")
    
    # Build a parent map for ElementTree (since getparent() doesn't exist)
    parent_map = {c: p for p in svg_root.iter() for c in p}
    
    # Find all <a> elements and collect them for processing
    elements_to_process = []
    
    # Find all <a> elements (they should all have data-ref attributes from upstream processing)
    for a_elem in svg_root.iter():
        if a_elem.tag == 'a' or a_elem.tag.endswith('}a'):  # Handle both namespaced and non-namespaced
            data_ref = a_elem.get('data-ref')
            if data_ref:  # Updated: look for data-ref instead of href
                elements_to_process.append(a_elem)
    
    print(f"Found {len(elements_to_process)} <a> elements to process")
    
    # Process each <a> element to extract note reference and flatten structure
    for a_elem in elements_to_process:
        data_ref = a_elem.get('data-ref')
        # Data_ref is already clean from upstream processing - use directly
        simplified_ref = data_ref  # No additional processing needed
        
        # Count all path elements inside this <a>
        path_elements = []
        text_elements = []
        other_elements = []
        
        for child in a_elem:
            if child.tag == 'path' or child.tag.endswith('}path'):
                path_elements.append(child)
            elif child.tag == 'text' or child.tag.endswith('}text'):
                text_elements.append(child)
            else:
                other_elements.append(child)
        
        total_children = len(path_elements) + len(text_elements) + len(other_elements)
        
        if len(path_elements) == 1 and total_children == 1:
            # Single path only: current behavior (flatten to path with data-ref)
            path_elem = path_elements[0]
            print(f"Processing single path: {data_ref} -> {simplified_ref}")
            
            # Create a new path element with the same attributes
            new_path = ET.Element('path')
            
            # Copy all attributes from original path except fill (handled by CSS)
            for attr, value in path_elem.attrib.items():
                if attr != 'fill':  # Skip fill attribute (will be handled by CSS)
                    new_path.set(attr, value)
            
            # Add data-ref attribute for JavaScript targeting
            new_path.set('data-ref', simplified_ref)
            
            # Replace <a> element with new path element
            parent = parent_map.get(a_elem)
            if parent is not None:
                # Insert new path element at the same position as the <a>
                a_index = list(parent).index(a_elem)
                parent.insert(a_index, new_path)
                # Remove the <a> element
                parent.remove(a_elem)
            else:
                print(f"Warning: Could not find parent for <a> element")
                
        elif total_children > 0:
            # Multiple elements or text elements: convert <a> to <g> (group) and preserve all children
            element_types = []
            if path_elements:
                element_types.append(f"{len(path_elements)} path(s)")
            if text_elements:
                element_types.append(f"{len(text_elements)} text element(s)")
            if other_elements:
                element_types.append(f"{len(other_elements)} other element(s)")
            
            print(f"Processing multiple elements: {data_ref} -> {simplified_ref} ({', '.join(element_types)})")
            
            # Create a new group element
            new_group = ET.Element('g')
            
            # Add data-ref attribute for JavaScript targeting
            new_group.set('data-ref', simplified_ref)
            
            # Move all children from <a> to <g>
            for child in list(a_elem):
                new_group.append(child)
            
            # Replace <a> element with new group element
            parent = parent_map.get(a_elem)
            if parent is not None:
                # Insert new group element at the same position as the <a>
                a_index = list(parent).index(a_elem)
                parent.insert(a_index, new_group)
                # Remove the <a> element
                parent.remove(a_elem)
            else:
                print(f"Warning: Could not find parent for <a> element")
                
        else:
            print(f"Warning: Empty <a> element with data-ref {data_ref} - preserving as group")
            # Convert empty <a> to empty <g> with data-ref (preserve for JavaScript targeting)
            new_group = ET.Element('g')
            new_group.set('data-ref', simplified_ref)
            
            parent = parent_map.get(a_elem)
            if parent is not None:
                a_index = list(parent).index(a_elem)
                parent.insert(a_index, new_group)
                parent.remove(a_elem)
                
    print(f"Successfully processed {len(elements_to_process)} note elements")
    
    # =============================================================================
    # REORDER NOTE HEADS FOR PROPER Z-INDEX
    # =============================================================================
    
    # Move all note heads to end of their parent containers for proper rendering order
    # In SVG, elements that appear later in the DOM render on top
    # This ensures note heads are always visible above staff lines and other elements
    
    # Rebuild parent map after coalescing changes
    parent_map = {c: p for p in svg_root.iter() for c in p}
    
    # Find all note heads (path elements with data-ref)
    note_heads = []
    for path in svg_root.findall('.//path[@data-ref]'):
        parent = parent_map.get(path)
        if parent is not None:
            note_heads.append((path, parent))
    
    print(f"Moving {len(note_heads)} note heads to end of their parents for proper z-order")
    
    # Group by parent to move all children of same parent efficiently
    parents_to_update = {}
    for note_head, parent in note_heads:
        if parent not in parents_to_update:
            parents_to_update[parent] = []
        parents_to_update[parent].append(note_head)
    
    # Move note heads to end of each parent container
    for parent, note_head_list in parents_to_update.items():
        for note_head in note_head_list:
            # Remove from current position
            parent.remove(note_head)
            # Append to end (renders on top)
            parent.append(note_head)
    
    print(f"Successfully reordered note heads in {len(parents_to_update)} parent containers")
    
    # =============================================================================
    # FINAL CLEANUP
    # =============================================================================
    
    # Remove fill="currentColor" from all remaining elements
    # This is now handled by CSS, reducing redundancy
    for elem in svg_root.findall('.//*[@fill="currentColor"]'):
        del elem.attrib['fill']
        
# =============================================================================
# MAIN PROCESSING FUNCTION
# =============================================================================

def generate_sync_files(svg_input, notes_input, config_input, svg_output, notes_output, fermata_input=None):
    """
    Main orchestration function that coordinates the entire sync generation process.
    
    This function ties together all the individual processing steps:
    1. Load and validate input files
    2. Extract timing metadata and channel information
    3. Process notes with simplified references and channel data
    4. Process fermata data if provided
    5. Extract and convert bar timing from SVG
    6. Create unified timeline with proper sorting
    7. Generate output files optimized for web playback
    
    The resulting files enable synchronized audio-visual playback where:
    - Notes can be highlighted as they play
    - Measures can be highlighted for navigation
    - Fermatas can be handled for expressive timing
    - Multi-channel audio can be properly mixed
    - Timing is accurately synchronized between audio and visual
    
    Args:
        svg_input (str): Path to LilyPond-generated SVG file (normalized by upstream processing)
        notes_input (str): Path to JSON file with note timing data (contains clean data_ref values)
        config_input (str): Path to YAML file with musical structure
        svg_output (str): Path for cleaned/optimized SVG output
        notes_output (str): Path for unified sync YAML output
        fermata_input (str, optional): Path to CSV file with fermata data (normalized data_ref)
    """
    
    # =============================================================================
    # LOAD AND VALIDATE INPUT FILES
    # =============================================================================
    
    print(f"Loading {notes_input}...")
    with open(notes_input, 'r') as f:
        notes_data = json.load(f)
    
    print(f"Loading {config_input}...")
    with open(config_input, 'r') as f:
        config_data = yaml.safe_load(f)
    
    print(f"Loading {svg_input}...")
    tree = ET.parse(svg_input)
    root = tree.getroot()
    
    # =============================================================================
    # EXTRACT TIMING METADATA
    # =============================================================================
    
    # Extract comprehensive timing metadata including channel statistics
    # This establishes the fundamental timing relationships for the entire piece
    meta = extract_meta(notes_data, config_data)
    
    # =============================================================================
    # PROCESS NOTES WITH CHANNEL INFORMATION (UPDATED FOR NORMALIZED PIPELINE)
    # =============================================================================
    
    # Process notes into unified flow format with channel information
    # Note: JSON hrefs arrays already contain clean data_ref values from upstream processing
    # New format: [start_tick, channel, end_tick, hrefs_array]
    # This enables multi-track playback and proper channel routing
    flow_items = []
    for note in notes_data:
        # Data_ref values in hrefs array are already clean from upstream processing - use directly
        clean_data_refs = note['hrefs']  # No additional cleaning needed
        
        # Extract channel information (should be present in JSON)
        channel = note.get('channel', 0)  # Default to channel 0 if missing
        
        # Create flow item: [start_tick, channel, end_tick, hrefs]
        flow_items.append([note['on_tick'], channel, note['off_tick'], clean_data_refs])
        
        # Debug: print first few notes to verify channel data integrity
        if len(flow_items) <= 3:
            print(f"  Note: ticks {note['on_tick']}-{note['off_tick']}, channel {channel}, data_refs {clean_data_refs}")
    
    print(f"Processed {len(flow_items)} notes with channel information")
    print("🔧 Using clean data_ref values from upstream processing - no additional cleaning performed")
    
    # =============================================================================
    # EXTRACT BAR TIMING FROM SVG (MOVED BEFORE FERMATA PROCESSING)
    # =============================================================================
    
    # Extract and process bars from SVG, converting to tick timeline
    # This must come before fermata consolidation since consolidation needs bar positions
    bars = extract_bars_from_svg(root, meta, config_data)
    
    # =============================================================================
    # PROCESS FERMATA DATA WITH CONSOLIDATION
    # =============================================================================
    
    # Process fermata CSV if provided
    fermata_items = process_fermata_csv(fermata_input, notes_data)
    
    # CONSOLIDATE fermatas by measure (keeping only the rightmost fermata per measure)
    if fermata_items:
        print(f"🎯 Consolidating fermatas by measure...")
        fermata_items = consolidate_fermatas_by_measure(fermata_items, bars)
    
    # Add consolidated fermata events to flow: [tick, None, None, 'fermata']
    flow_items.extend(fermata_items)
    
    # Add bar events to flow: [tick, None, bar_number, 'bar'] 
    for bar in bars:
        flow_items.append([bar['tick'], None, bar['number'], 'bar'])
    
    # =============================================================================
    # CREATE UNIFIED TIMELINE
    # =============================================================================
    
    # Sort flow items for proper chronological playback order
    # Sorting criteria (in order of priority):
    # 1. Start tick (primary timing)
    # 2. Bars before fermatas before notes (for simultaneous events)
    # 3. Higher channels first (for note priority)
    def sort_key(x):
        tick = x[0]
        if len(x) == 4:
            if x[3] == 'bar':
                return (tick, 0)  # Bars first
            elif x[3] == 'fermata':
                return (tick, 1)  # Fermatas second
            else:
                return (tick, 2, -x[1])  # Notes third, higher channels first
        return (tick, 2, 0)  # Default for other items
    
    flow_items.sort(key=sort_key)
    
    # =============================================================================
    # GENERATE OUTPUT FILES
    # =============================================================================
    
    # Prepare comprehensive sync data structure
    sync_data = {
        'meta': meta,
        'flow': flow_items
    }
    
    # Write sync YAML with properly structured metadata and compact flow format
    print(f"Writing {notes_output}...")
    with open(notes_output, 'w') as f:
        # Write meta section with proper indentation
        f.write("meta:\n")
        for key, value in meta.items():
            if key == 'channels':
                # Write channels section with proper nested structure
                f.write(f"  {key}:\n")
                for channel_id, stats in value.items():
                    f.write(f"    {channel_id}:\n")
                    f.write(f"      minPitch: {stats['minPitch']}\n")
                    f.write(f"      maxPitch: {stats['maxPitch']}\n")
                    f.write(f"      count: {stats['count']}\n")
            else:
                f.write(f"  {key}: {value}\n")
        
        f.write("\nflow:\n")
        
        # Write each flow item as compact YAML list (one line per item)
        # Use ~ (YAML null) instead of None to reduce file size for network transfer
        for item in flow_items:
            # Format based on item type
            if len(item) == 4 and item[3] == 'bar':  # Bar: [tick, ~, bar_number, bar]
                f.write(f"- [{item[0]}, ~, {item[2]}, {item[3]}]\n")
            elif len(item) == 4 and item[3] == 'fermata':  # Fermata: [tick, ~, ~, fermata]
                f.write(f"- [{item[0]}, ~, ~, {item[3]}]\n")
            elif len(item) == 4:  # Note: [start_tick, channel, end_tick, hrefs]
                f.write(f"- [{item[0]}, {item[1]}, {item[2]}, {item[3]}]\n")
            else:  # Legacy format (shouldn't happen with current code)
                # Handle None values in legacy format
                val1 = '~' if item[1] is None else item[1]
                val2 = '~' if item[2] is None else item[2]
                f.write(f"- [{item[0]}, {val1}, {val2}]\n")
                 
    # Write cleaned and optimized SVG
    print(f"Writing {svg_output}...")
    clean_svg(root)
    tree.write(svg_output, encoding='utf-8', xml_declaration=True)
    
    # =============================================================================
    # VALIDATION AND DEBUGGING OUTPUT
    # =============================================================================
    
    total_notes = len([item for item in flow_items if len(item) == 4 and item[3] != 'bar' and item[3] != 'fermata'])
    total_bars = len([item for item in flow_items if len(item) == 4 and item[3] == 'bar'])
    total_fermatas = len([item for item in flow_items if len(item) == 4 and item[3] == 'fermata'])
    
    print(f"✅ Generated {len(flow_items)} flow items ({total_notes} notes, {total_bars} bars, {total_fermatas} fermatas)")
    
    # Debug: Show channel distribution to verify multi-track processing
    channel_counts = {}
    for item in flow_items:
        if len(item) == 4 and item[3] != 'bar' and item[3] != 'fermata':  # Note: [start_tick, channel, end_tick, hrefs]
            channel = item[1]  # Channel is at index 1 in new format
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
    
    if channel_counts:
        print(f"📊 Channel distribution in flow: {channel_counts}")
    else:
        print("⚠️  No channel data found in output")
    
    print("🔧 All processing completed using normalized pipeline - no cleaning performed")

# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """
    Command line interface for the sync generation script.
    
    Defines all required input and output parameters with clear descriptions.
    Most parameters are required to ensure proper file processing, with optional fermata support
    using spatial interpolation for tied notes.
    """
    parser = argparse.ArgumentParser(description='Generate unified sync format with optional fermata support (normalized pipeline)')
    
    # Required inputs - no defaults to ensure explicit file specification
    parser.add_argument('-is', '--svg-input', required=True, 
                       help='Input SVG file with normalized data-ref attributes (e.g. test_optimized.svg)')
    parser.add_argument('-in', '--notes-input', required=True,
                       help='Input notes JSON with clean data_ref values in hrefs arrays (e.g. test_json_notes.json)')  
    parser.add_argument('-ic', '--config-input', required=True,
                       help='Input config YAML (e.g. test.config.yaml)')
    
    # Required outputs - no defaults to prevent accidental overwrites
    parser.add_argument('-os', '--svg-output', required=True,
                       help='Output SVG with data-ref attributes (e.g. test.svg)')
    parser.add_argument('-on', '--notes-output', required=True, 
                       help='Output sync YAML (e.g. test.yaml)')
    
    # Optional inputs for enhanced functionality
    parser.add_argument('-if', '--fermata-input', required=False,
                       help='Input fermata CSV with clean data_ref values (e.g. test_note_heads_fermata.csv)')
    
    args = parser.parse_args()
    
    # Process files using parsed arguments
    generate_sync_files(
        svg_input=args.svg_input,
        notes_input=args.notes_input, 
        config_input=args.config_input,
        svg_output=args.svg_output,
        notes_output=args.notes_output,
        fermata_input=args.fermata_input
    )

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    main()