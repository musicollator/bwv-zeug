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

# Register XML namespaces to prevent ns0: prefixes in output
ET.register_namespace('', 'http://www.w3.org/2000/svg')
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

def simplify_href(href):
    """Convert 'test-main.ly:37:20:21' to 'test-main.ly:37:21'"""
    parts = href.split(':')
    if len(parts) == 4:
        return f"{parts[0]}:{parts[1]}:{parts[3]}"
    return href

def parse_fraction(fraction_str):
    """Parse LilyPond fraction like '3/2' or '1'"""
    if '/' in fraction_str:
        num, den = fraction_str.split('/')
        return float(num) / float(den)
    return float(fraction_str)

def collect_unique_moments(svg_root):
    """Collect unique LilyPond moments from SVG"""
    moments = set()
    
    # Find all rect elements with data-bar-moment-main
    for rect in svg_root.findall('.//*[@data-bar-moment-main]'):
        moment_str = rect.get('data-bar-moment-main')
        if moment_str is not None:
            moment = parse_fraction(moment_str)
            moments.add(moment)
    
    return sorted(moments)

def calculate_channel_stats(notes_data):
    """Calculate min/max pitch and count for each channel"""
    channel_stats = {}
    
    for note in notes_data:
        channel = note.get('channel', 0)
        pitch = note.get('pitch', 60)  # Default to middle C if missing
        
        if channel not in channel_stats:
            channel_stats[channel] = {
                'minPitch': pitch,
                'maxPitch': pitch,
                'count': 0
            }
        
        stats = channel_stats[channel]
        stats['minPitch'] = min(stats['minPitch'], pitch)
        stats['maxPitch'] = max(stats['maxPitch'], pitch)
        stats['count'] += 1
    
    # Log channel stats for debugging
    print(f"📊 Channel statistics:")
    for channel in sorted(channel_stats.keys()):
        stats = channel_stats[channel]
        avg_pitch = (stats['minPitch'] + stats['maxPitch']) / 2
        print(f"  Channel {channel}: {stats['minPitch']}-{stats['maxPitch']} (avg: {avg_pitch:.1f}), {stats['count']} notes")
    
    return channel_stats

def extract_meta(notes_data, config_data):
    """Extract metadata from notes and config"""
    # Get tick range from notes
    all_ticks = []
    for note in notes_data:
        all_ticks.extend([note['on_tick'], note['off_tick']])
    
    min_tick = min(all_ticks)
    max_tick = max(all_ticks)
    
    # Calculate rough conversion ratio (will be refined with actual audio data)
    total_duration = config_data['musicalStructure']['totalDurationSeconds']
    tick_to_second_ratio = total_duration / (max_tick - min_tick)
    
    # Calculate channel statistics
    channel_stats = calculate_channel_stats(notes_data)
    
    return {
        'totalMeasures': config_data['musicalStructure']['totalMeasures'],
        'minTick': min_tick,
        'maxTick': max_tick,
        'minMoment': 0,  # Will be updated from SVG
        'maxMoment': config_data['musicalStructure']['totalMeasures'],  # Rough estimate
        'musicStartSeconds': 0.0,  # Will be refined
        'tickToSecondRatio': tick_to_second_ratio,
        'channels': channel_stats
    }

def extract_bars_from_svg(svg_root, meta, config_data):
    # Collect unique bars
    unique_bars = {}
    for rect in svg_root.findall('.//*[@data-bar]'):
        bar_num = int(rect.get('data-bar'))
        moment_str = rect.get('data-bar-moment-main')
        if bar_num not in unique_bars:
            unique_bars[bar_num] = moment_str
    
    # Separate pickup (null moment) from regular bars
    pickup_bar = None
    regular_bars = {}
    
    for bar_num, moment_str in unique_bars.items():
        if moment_str is None:
            pickup_bar = bar_num  # Pickup bar number
        else:
            regular_bars[bar_num] = parse_fraction(moment_str)
    
    # Get sorted moments, remove final end moment
    moments = sorted(regular_bars.values())
    if len(moments) > meta['totalMeasures']:
        moments = moments[:-1]
    
    # Calculate musical end (same logic as before)
    last_measure_duration_str = config_data.get('musicalStructure', {}).get('lastMeasureDuration')
    if last_measure_duration_str:
        musical_end_moment = moments[-1] + parse_fraction(last_measure_duration_str)
    else:
        musical_end_moment = max(regular_bars.values())
    
    # Scale moments to ticks - use absolute positioning from 0
    moment_span = musical_end_moment  # From 0, not from first moment
    tick_span = meta['maxTick'] - meta['minTick'] 
    scale_factor = tick_span / moment_span

    # Generate bars
    bars = []

    # Add pickup bar if exists
    if pickup_bar is not None:
        bars.append({'number': pickup_bar, 'moment': 0, 'tick': 0})

    # Add regular bars with absolute positioning
    for bar_num, moment in regular_bars.items():
        if moment in moments:  # Only bars we want to include
            tick = int(moment * scale_factor)  # Absolute from 0
            bars.append({'number': bar_num, 'moment': moment, 'tick': tick})

    return sorted(bars, key=lambda x: x['tick'])

def clean_svg(svg_root):
    """Clean SVG: remove unnecessary attributes, coalesce note elements, add CSS styling"""
    
    # Add CSS styling to the SVG
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
    existing_styles = svg_root.findall('.//{http://www.w3.org/2000/svg}style')
    if existing_styles:
        # Insert after the last existing style
        insert_pos = list(svg_root).index(existing_styles[-1]) + 1
    else:
        # Insert as first child
        insert_pos = 0
    
    svg_root.insert(insert_pos, style_elem)
    
    # Clean bar rectangles - keep only essential attributes, remove fill
    for rect in svg_root.findall('.//*[@data-bar]'):
        # Keep only essential attributes
        essential_attrs = ['x', 'y', 'width', 'height', 'ry', 'transform', 'data-bar']
        attrs_to_remove = []
        
        for attr in rect.attrib:
            if attr not in essential_attrs:
                attrs_to_remove.append(attr)
        
        for attr in attrs_to_remove:
            del rect.attrib[attr]
    
    # Coalesce note <a> elements: move data-ref to contained path and remove wrapper
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
    
    # Process each <a> element
    for a_elem in elements_to_process:
        href = a_elem.get('href')
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
            
            # Copy all attributes from original path
            for attr, value in path_elem.attrib.items():
                if attr != 'fill':  # Skip fill attribute (will be handled by CSS)
                    new_path.set(attr, value)
            
            # Add data-ref attribute
            new_path.set('data-ref', simplified_ref)
            
            # Get parent of the <a> element using our parent map
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
    
    # Remove fill="currentColor" from all remaining elements
    for elem in svg_root.findall('.//*[@fill="currentColor"]'):
        del elem.attrib['fill']

def generate_sync_files(svg_input, notes_input, config_input, svg_output, notes_output):
    """Main function to generate sync files"""
    
    # 1. Load input files
    print(f"Loading {notes_input}...")
    with open(notes_input, 'r') as f:
        notes_data = json.load(f)
    
    print(f"Loading {config_input}...")
    with open(config_input, 'r') as f:
        config_data = yaml.safe_load(f)
    
    print(f"Loading {svg_input}...")
    tree = ET.parse(svg_input)
    root = tree.getroot()
    
    # 2. Extract timing metadata (now includes channel stats)
    meta = extract_meta(notes_data, config_data)
    
    # 3. Process notes - include channel information from JSON
    flow_items = []
    for note in notes_data:
        simplified_hrefs = [simplify_href(href) for href in note['hrefs']]
        
        # Get channel from JSON (should be there already)
        channel = note.get('channel', 0)  # Default to 0 if missing
        
        # New format: [start_tick, channel, end_tick, hrefs]
        flow_items.append([note['on_tick'], channel, note['off_tick'], simplified_hrefs])
        
        # Debug: print first few notes to verify channel data
        if len(flow_items) <= 3:
            print(f"  Note: ticks {note['on_tick']}-{note['off_tick']}, channel {channel}, hrefs {simplified_hrefs}")
    
    print(f"Processed {len(flow_items)} notes with channel information")
    
    # 4. Extract and process bars from SVG
    bars = extract_bars_from_svg(root, meta, config_data)
    for bar in bars:
        flow_items.append([bar['tick'], None, bar['number'], 'bar'])
    
    # 5. Sort flow: first by start tick, then higher channels first, then bars before notes
    flow_items.sort(key=lambda x: (
        x[0],                              # Primary: start tick
        0 if len(x) == 4 and x[3] == 'bar' else 1,  # Secondary: bars before notes
        -x[1] if len(x) == 4 and x[3] != 'bar' else 0  # Tertiary: higher channels first (for notes)
    ))    
    
    # 6. Generate outputs
    sync_data = {
        'meta': meta,
        'flow': flow_items
    }
    
    # Write sync.yaml with proper meta structure and compact flow
    print(f"Writing {notes_output}...")
    with open(notes_output, 'w') as f:
        # Write meta section properly indented
        f.write("meta:\n")
        for key, value in meta.items():
            if key == 'channels':
                # Write channels section with proper indentation
                f.write(f"  {key}:\n")
                for channel_id, stats in value.items():
                    f.write(f"    {channel_id}:\n")
                    f.write(f"      minPitch: {stats['minPitch']}\n")
                    f.write(f"      maxPitch: {stats['maxPitch']}\n")
                    f.write(f"      count: {stats['count']}\n")
            else:
                f.write(f"  {key}: {value}\n")
        
        f.write("\nflow:\n")
        
        # Write each flow item on one line (compact format)
        for item in flow_items:
            # Format as compact YAML list
            if len(item) == 4 and item[3] == 'bar':  # Bar: [tick, None, bar_number, 'bar']
                f.write(f"- [{item[0]}, {item[1]}, {item[2]}, {item[3]}]\n")
            elif len(item) == 4:  # Note: [start_tick, channel, end_tick, hrefs]
                f.write(f"- [{item[0]}, {item[1]}, {item[2]}, {item[3]}]\n")
            else:  # Legacy format (shouldn't happen now)
                f.write(f"- [{item[0]}, {item[1]}, {item[2]}]\n")
                 
    # Write cleaned SVG
    print(f"Writing {svg_output}...")
    clean_svg(root)
    tree.write(svg_output, encoding='utf-8', xml_declaration=True)
    
    print(f"✅ Generated {len(flow_items)} flow items ({len(notes_data)} notes, {len(bars)} bars)")
    
    # Debug: Show channel distribution
    channel_counts = {}
    for item in flow_items:
        if len(item) == 4 and item[3] != 'bar':  # Note: [start_tick, channel, end_tick, hrefs]
            channel = item[1]  # Channel is now at index 1
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
    
    if channel_counts:
        print(f"📊 Channel distribution in flow: {channel_counts}")
    else:
        print("⚠️  No channel data found in output")

def main():
    parser = argparse.ArgumentParser(description='Generate unified sync format')
    
    # Required inputs - no defaults
    parser.add_argument('-is', '--svg-input', required=True, 
                       help='Input SVG file (e.g. test_optimized.svg)')
    parser.add_argument('-in', '--notes-input', required=True,
                       help='Input notes JSON (e.g. test_json_notes.json)')  
    parser.add_argument('-ic', '--config-input', required=True,
                       help='Input config YAML (e.g. test.config.yaml)')
    
    # Required outputs - no defaults
    parser.add_argument('-os', '--svg-output', required=True,
                       help='Output SVG with IDs (e.g. test.svg)')
    parser.add_argument('-on', '--notes-output', required=True, 
                       help='Output sync YAML (e.g. test.yaml)')
    
    args = parser.parse_args()
    
    # Process files
    generate_sync_files(
        svg_input=args.svg_input,
        notes_input=args.notes_input, 
        config_input=args.config_input,
        svg_output=args.svg_output,
        notes_output=args.notes_output
    )

if __name__ == '__main__':
    main()