# add_clicks.py - COMPLETE VERSION with beat timing export

import argparse
from pathlib import Path
import numpy as np
import soundfile as sf
import yaml  # 🟢 NEW: Added for beat export

from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
from add_clicks_utils import (
    segment_key_from_path,
    default_click_sample,
    load_click_limits,
    clean_click_outputs,
)

# 🟢 NEW: Global variables for beat timing collection
beat_data = {}
chunk_durations = {}

# 🟢 NEW: Functions for beat timing export
def get_audio_duration(wav_path):
    """Get duration of audio file."""
    info = sf.info(str(wav_path))
    return info.frames / info.samplerate

def save_beat_timing(wav_path, beats):
    """Save beat timing and duration to global dict."""
    global beat_data, chunk_durations
    
    segment_key = segment_key_from_path(wav_path)
    duration = get_audio_duration(wav_path)
    
    beat_data[segment_key] = {
        'file': str(wav_path),
        'beats': beats.tolist(),
        'num_beats': len(beats),
        'duration': duration,
        'has_beats': len(beats) > 0
    }
    
    chunk_durations[segment_key] = duration

def concatenate_beat_timings():
    """Concatenate beat timings with proper time offsets."""
    concatenated_beats = []
    cumulative_offset = 0.0
    
    # Sort segments by filename to ensure proper order
    for segment_key in sorted(beat_data.keys()):
        segment = beat_data[segment_key]
        
        # Offset beats by cumulative duration of previous chunks
        offset_beats = [beat + cumulative_offset for beat in segment['beats']]
        
        # Add to concatenated list
        concatenated_beats.extend(offset_beats)
        
        # Update cumulative offset for next chunk
        cumulative_offset += segment['duration']
        
        print(f"  📋 {segment_key}: {len(segment['beats'])} beats, duration {segment['duration']:.2f}s, offset +{cumulative_offset:.2f}s")
    
    return concatenated_beats, cumulative_offset

def export_beat_data(output_file="detected_beats.yaml"):
    """Export beat data to YAML with concatenated timing."""
    global beat_data
    
    if not beat_data:
        print("⚠️  No beat data to export")
        return
    
    # Get concatenated beats
    concatenated_beats, total_duration = concatenate_beat_timings()
    
    export_data = {
        'meta': {
            'total_segments': len(beat_data),
            'total_duration': total_duration,
            'total_beats': len(concatenated_beats),
            'description': 'Beat timing detected from audio chunks with concatenated offsets'
        },
        'segments': beat_data,  # Individual chunk data
        'concatenated': {
            'beats': concatenated_beats,  # All beats with proper time offsets
            'total_duration': total_duration
        }
    }
    
    with open(output_file, 'w') as f:
        yaml.dump(export_data, f, default_flow_style=False)
    print(f"✅ Beat data exported to {output_file}")
    print(f"✅ Total: {len(concatenated_beats)} beats across {total_duration:.2f}s")

# ORIGINAL FUNCTION (unchanged except for one line)
def process_file(wav_path, processor, click, click_limits):
    segment_key = segment_key_from_path(wav_path)
    limits = click_limits.get(segment_key, {})
    max_clicks = limits.get("max_clicks", float("inf"))
    last_beat_override = limits.get("last_beat")

    # Extract beat times
    act = RNNBeatProcessor()(str(wav_path))
    beats = processor(act)

    # 🟢 MOVED: Save beat timing BEFORE early return for no beats
    if len(beats) == 0:
        print(f"⚠️  Skipping (no beats found): {wav_path}")
        save_beat_timing(wav_path, beats)  # Save empty beats for quiet segments
        return

    if beats[0] > 0.5:
        print("⚠️  Inserting synthetic first beat at 0.0")
        beats = np.insert(beats, 0, 0.0)

    if len(beats) > max_clicks:
        beats = beats[:max_clicks]

    if last_beat_override is not None:
        print(f"⏱️  Appending manual last beat at {last_beat_override:.2f}s")
        beats = np.append(beats, last_beat_override)

    # 🟢 Save beat timing for segments WITH beats
    save_beat_timing(wav_path, beats)

    # Read original audio
    y, sr = sf.read(str(wav_path))
    output = np.copy(y)

    # Mix in clicks
    for t in beats:
        i = int(t * sr)
        if i + len(click) <= len(output):
            output[i : i + len(click)] += click[: len(output) - i]

    out_path = str(wav_path).replace(".wav", "_with_clicks.wav")
    sf.write(out_path, output, sr)
    print(f"✅ Saved: {out_path}")


# ORIGINAL MAIN (with one new argument and one new line at the end)
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=str)
    parser.add_argument("--clean", action="store_true")
    # 🟢 NEW: Optional argument for beat export file
    parser.add_argument("--export-beats", type=str, default="detected_beats.yaml", 
                       help="Export beat timing to YAML file")
    args = parser.parse_args()

    directory = Path(args.directory)
    click_limits = load_click_limits()
    click = default_click_sample()

    if args.clean:
        clean_click_outputs(directory)

    processor = DBNBeatTrackingProcessor(
        fps=100, min_bpm=40, max_bpm=140, transition_lambda=15
    )

    for wav_path in sorted(directory.glob("*.wav")):
        key = segment_key_from_path(wav_path)
        if click_limits.get(key, {}).get("max_clicks", float("inf")) == 0:
            print(f"⏩ Skipping (explicit 0 clicks): {wav_path}")
            # 🟢 FIXED: Save timing data even for explicitly skipped files
            save_beat_timing(wav_path, np.array([]))  # Save empty beats array
            continue

        print(f"🎧 Processing: {wav_path}")
        process_file(wav_path, processor, click, click_limits)

    # 🟢 NEW: Export beat data at the end
    print(f"\n📊 BEAT TIMING SUMMARY:")
    export_beat_data(args.export_beats)