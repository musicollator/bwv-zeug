"""
LILYPOND MUSIC SCORE SYNCHRONIZATION GENERATOR
==============================================

This script processes LilyPond-generated musical scores to create synchronized playback data.
It combines timing information from JSON notes, musical structure from YAML config, and 
visual elements from SVG notation to generate files suitable for real-time music playback 
with visual highlighting.

WORKFLOW OVERVIEW:
1. Load input files (SVG notation, JSON notes with timing, YAML config)
2. Extract timing metadata and calculate tick-to-second conversions
3. Process musical notes with channel information for multi-track playback
4. Extract bar positions and timing from SVG elements
5. Clean and optimize SVG for web playback (remove unnecessary attributes, add CSS)
6. Generate unified sync data combining notes and bars in chronological order
7. Output cleaned SVG and sync YAML for use in music players

INPUT FILES:
- SVG: LilyPond-generated notation with embedded timing data attributes
- JSON: Note timing data with MIDI-style ticks and LilyPond references
- YAML: Musical structure configuration (measures, duration, etc.)

OUTPUT FILES:
- Cleaned SVG: Optimized for web with CSS styling and note head z-ordering
- Sync YAML: Unified timeline with notes and bars for synchronized playback

USAGE EXAMPLE:
python generate_sync.py \
  -is input_score.svg \
  -in timing_notes.json \
  -ic score_config.yaml \
  -os output_score.svg \
  -on sync_data.yaml
"""

import argparse
import json
import yaml
import xml.etree.ElementTree as ET
from pathlib import Path

### python ../../../python/generate_sync.py \
###   -is test_optimized.svg \
###   -in test_json_notes.json \
###   -ic test.config.yaml \
###   -os test.svg \
###   -on test.yaml

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

def simplify_href(href):
    """
    Convert LilyPond textedit references to a simpler format.
    
    LilyPond generates href attributes like 'test-main.ly:37:20:21' where:
    - test-main.ly: source file
    - 37: line number  
    - 20: column start
    - 21: column end
    
    We simplify this to 'test-main.ly:37:21' (file:line:end_column)
    for more concise note references in the sync data.
    
    Args:
        href (str): Original LilyPond href like 'test-main.ly:37:20:21'
        
    Returns:
        str: Simplified href like 'test-main.ly:37:21'
    """
    parts = href.split(':')
    if len(parts) == 4:
        return f"{parts[0]}:{parts[1]}:{parts[3]}"
    return href

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
    
    This function establishes the fundamental timing relationships between:
    - MIDI ticks (discrete timing units from note data)
    - Musical moments (fractional measures from LilyPond)
    - Real-time seconds (for audio playback synchronization)
    
    Key calculations:
    - Total tick span from first to last note event
    - Tick-to-second conversion ratio for audio sync
    - Channel statistics for multi-track playback
    - Musical boundaries (measures, moments)
    
    Args:
        notes_data (list): Note timing data from JSON
        config_data (dict): Musical structure configuration from YAML
        
    Returns:
        dict: Comprehensive metadata including timing ratios and channel info
    """
    # Collect all tick values (both note-on and note-off events)
    all_ticks = []
    for note in notes_data:
        all_ticks.extend([note['on_tick'], note['off_tick']])
    
    # Musical start is always 0, regardless of when first note occurs
    # This ensures pickup measures and rests are handled correctly
    min_tick = 0  # ← Fixed: don't assume first note = musical start
    max_tick = max(all_ticks)
    
    # Calculate tick-to-second conversion using full musical span from 0
    # This ratio is crucial for synchronizing MIDI playback with visual highlighting
    total_duration = config_data['musicalStructure']['totalDurationSeconds']
    tick_to_second_ratio = total_duration / max_tick  # ← Fixed: use full span from 0
    
    # Calculate channel statistics for multi-track support
    channel_stats = calculate_channel_stats(notes_data)
    
    return {
        'totalMeasures': config_data['musicalStructure']['totalMeasures'],
        'minTick': min_tick,
        'maxTick': max_tick,
        'minMoment': 0,
        'maxMoment': config_data['musicalStructure']['totalMeasures'],
        'musicStartSeconds': 0.0,
        'tickToSecondRatio': tick_to_second_ratio,
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
    # COALESCE NOTE ELEMENTS
    # =============================================================================
    
    # Coalesce note <a> elements: move data-ref to contained path and remove wrapper
    # LilyPond generates: <a href="textedit:///..."><path d="..."/></a>
    # We convert to: <path d="..." data-ref="simplified-ref"/>
    # This simplifies JavaScript targeting and reduces DOM complexity
    
    # Build a parent map for ElementTree (since getparent() doesn't exist)
    parent_map = {c: p for p in svg_root.iter() for c in p}
    
    # Find all <a> elements and collect them for processing
    elements_to_process = []
    
    # Find all <a> elements (they should all have href attributes)
    for a_elem in svg_root.iter():
        if a_elem.tag == 'a' or a_elem.tag.endswith('}a'):  # Handle both namespaced and non-namespaced
            href = a_elem.get('href')
            if href and href.startswith('textedit:///work/'):
                elements_to_process.append(a_elem)
    
    print(f"Found {len(elements_to_process)} <a> elements to process")
    
    # Process each <a> element to extract note reference and flatten structure
    for a_elem in elements_to_process:
        href = a_elem.get('href')
        # Convert textedit href to simplified reference
        lily_ref = href.replace('textedit:///work/', '')
        simplified_ref = simplify_href(lily_ref)
        
        # Find the path element inside this <a> - use simple iteration
        path_elem = None
        for child in a_elem:
            if child.tag == 'path' or child.tag.endswith('}path'):
                path_elem = child
                break
        
        if path_elem is not None:
            print(f"Processing: {href} -> {simplified_ref}")
            
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
        else:
            print(f"Warning: No path found in <a> element with href {href}")
    
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

def generate_sync_files(svg_input, notes_input, config_input, svg_output, notes_output):
    """
    Main orchestration function that coordinates the entire sync generation process.
    
    This function ties together all the individual processing steps:
    1. Load and validate input files
    2. Extract timing metadata and channel information
    3. Process notes with simplified references and channel data
    4. Extract and convert bar timing from SVG
    5. Create unified timeline with proper sorting
    6. Generate output files optimized for web playback
    
    The resulting files enable synchronized audio-visual playback where:
    - Notes can be highlighted as they play
    - Measures can be highlighted for navigation
    - Multi-channel audio can be properly mixed
    - Timing is accurately synchronized between audio and visual
    
    Args:
        svg_input (str): Path to LilyPond-generated SVG file
        notes_input (str): Path to JSON file with note timing data
        config_input (str): Path to YAML file with musical structure
        svg_output (str): Path for cleaned/optimized SVG output
        notes_output (str): Path for unified sync YAML output
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
    # PROCESS NOTES WITH CHANNEL INFORMATION
    # =============================================================================
    
    # Process notes into unified flow format with channel information
    # New format: [start_tick, channel, end_tick, hrefs_array]
    # This enables multi-track playback and proper channel routing
    flow_items = []
    for note in notes_data:
        # Simplify all LilyPond references for cleaner data
        simplified_hrefs = [simplify_href(href) for href in note['hrefs']]
        
        # Extract channel information (should be present in JSON)
        channel = note.get('channel', 0)  # Default to channel 0 if missing
        
        # Create flow item: [start_tick, channel, end_tick, hrefs]
        flow_items.append([note['on_tick'], channel, note['off_tick'], simplified_hrefs])
        
        # Debug: print first few notes to verify channel data integrity
        if len(flow_items) <= 3:
            print(f"  Note: ticks {note['on_tick']}-{note['off_tick']}, channel {channel}, hrefs {simplified_hrefs}")
    
    print(f"Processed {len(flow_items)} notes with channel information")
    
    # =============================================================================
    # EXTRACT BAR TIMING FROM SVG
    # =============================================================================
    
    # Extract and process bars from SVG, converting to tick timeline
    bars = extract_bars_from_svg(root, meta, config_data)
    # Add bar events to flow: [tick, None, bar_number, 'bar']
    for bar in bars:
        flow_items.append([bar['tick'], None, bar['number'], 'bar'])
    
    # =============================================================================
    # CREATE UNIFIED TIMELINE
    # =============================================================================
    
    # Sort flow items for proper chronological playback order
    # Sorting criteria (in order of priority):
    # 1. Start tick (primary timing)
    # 2. Bars before notes (for simultaneous events)
    # 3. Higher channels first (for note priority)
    flow_items.sort(key=lambda x: (
        x[0],                              # Primary: start tick
        0 if len(x) == 4 and x[3] == 'bar' else 1,  # Secondary: bars before notes
        -x[1] if len(x) == 4 and x[3] != 'bar' else 0  # Tertiary: higher channels first (for notes)
    ))    
    
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
        for item in flow_items:
            # Format based on item type
            if len(item) == 4 and item[3] == 'bar':  # Bar: [tick, None, bar_number, 'bar']
                f.write(f"- [{item[0]}, {item[1]}, {item[2]}, {item[3]}]\n")
            elif len(item) == 4:  # Note: [start_tick, channel, end_tick, hrefs]
                f.write(f"- [{item[0]}, {item[1]}, {item[2]}, {item[3]}]\n")
            else:  # Legacy format (shouldn't happen with current code)
                f.write(f"- [{item[0]}, {item[1]}, {item[2]}]\n")
                 
    # Write cleaned and optimized SVG
    print(f"Writing {svg_output}...")
    clean_svg(root)
    tree.write(svg_output, encoding='utf-8', xml_declaration=True)
    
    # =============================================================================
    # VALIDATION AND DEBUGGING OUTPUT
    # =============================================================================
    
    print(f"✅ Generated {len(flow_items)} flow items ({len(notes_data)} notes, {len(bars)} bars)")
    
    # Debug: Show channel distribution to verify multi-track processing
    channel_counts = {}
    for item in flow_items:
        if len(item) == 4 and item[3] != 'bar':  # Note: [start_tick, channel, end_tick, hrefs]
            channel = item[1]  # Channel is at index 1 in new format
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
    
    if channel_counts:
        print(f"📊 Channel distribution in flow: {channel_counts}")
    else:
        print("⚠️  No channel data found in output")

# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """
    Command line interface for the sync generation script.
    
    Defines all required input and output parameters with clear descriptions.
    All parameters are required to ensure proper file processing.
    """
    parser = argparse.ArgumentParser(description='Generate unified sync format')
    
    # Required inputs - no defaults to ensure explicit file specification
    parser.add_argument('-is', '--svg-input', required=True, 
                       help='Input SVG file (e.g. test_optimized.svg)')
    parser.add_argument('-in', '--notes-input', required=True,
                       help='Input notes JSON (e.g. test_json_notes.json)')  
    parser.add_argument('-ic', '--config-input', required=True,
                       help='Input config YAML (e.g. test.config.yaml)')
    
    # Required outputs - no defaults to prevent accidental overwrites
    parser.add_argument('-os', '--svg-output', required=True,
                       help='Output SVG with IDs (e.g. test.svg)')
    parser.add_argument('-on', '--notes-output', required=True, 
                       help='Output sync YAML (e.g. test.yaml)')
    
    args = parser.parse_args()
    
    # Process files using parsed arguments
    generate_sync_files(
        svg_input=args.svg_input,
        notes_input=args.notes_input, 
        config_input=args.config_input,
        svg_output=args.svg_output,
        notes_output=args.notes_output
    )

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    main()