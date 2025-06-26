# add_clicks.py - COMPLETE VERSION with beat timing export and MP3 support

import argparse
from pathlib import Path
import numpy as np
import soundfile as sf
import yaml

from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
from add_clicks_utils import (
    segment_key_from_path,
    default_click_sample,
    load_click_limits,
    clean_click_outputs,
)

# Global variables for beat timing collection
beat_data = {}
chunk_durations = {}

# Functions for beat timing export
def get_audio_duration(audio_path):
    """Get duration of audio file (supports .wav and .mp3)."""
    info = sf.info(str(audio_path))
    return info.frames / info.samplerate

def save_beat_timing(audio_path, beats):
    """Save beat timing and duration to global dict."""
    global beat_data, chunk_durations
    
    segment_key = segment_key_from_path(audio_path)
    duration = get_audio_duration(audio_path)
    
    beat_data[segment_key] = {
        'file': str(audio_path),
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

def get_output_path(audio_path):
    """Generate output path for processed audio (always .wav output)."""
    path = Path(audio_path)
    # Remove original extension and add _with_clicks.wav
    stem = path.stem
    return path.parent / f"{stem}_with_clicks.wav"

def process_file(audio_path, processor, click, click_limits):
    """Process audio file (supports .wav and .mp3 input, always outputs .wav)."""
    segment_key = segment_key_from_path(audio_path)
    limits = click_limits.get(segment_key, {})
    max_clicks = limits.get("max_clicks", float("inf"))
    last_beat_override = limits.get("last_beat")

    # Extract beat times
    act = RNNBeatProcessor()(str(audio_path))
    beats = processor(act)

    # Save beat timing BEFORE early return for no beats
    if len(beats) == 0:
        print(f"⚠️  Skipping (no beats found): {audio_path}")
        save_beat_timing(audio_path, beats)  # Save empty beats for quiet segments
        return

    if beats[0] > 0.5:
        print("⚠️  Inserting synthetic first beat at 0.0")
        beats = np.insert(beats, 0, 0.0)

    if len(beats) > max_clicks:
        beats = beats[:max_clicks]

    if last_beat_override is not None:
        print(f"⏱️  Appending manual last beat at {last_beat_override:.2f}s")
        beats = np.append(beats, last_beat_override)

    # Save beat timing for segments WITH beats
    save_beat_timing(audio_path, beats)

    # Read original audio (soundfile handles both .wav and .mp3)
    y, sr = sf.read(str(audio_path))
    output = np.copy(y)

    # Mix in clicks
    for t in beats:
        i = int(t * sr)
        if i + len(click) <= len(output):
            output[i : i + len(click)] += click[: len(output) - i]

    # Generate output path (always .wav)
    out_path = get_output_path(audio_path)
    sf.write(str(out_path), output, sr)
    print(f"✅ Saved: {out_path}")

def get_audio_files(directory):
    """Get all supported audio files (.wav and .mp3) from directory."""
    audio_files = []
    
    # Collect .wav files
    wav_files = list(directory.glob("*.wav"))
    audio_files.extend(wav_files)
    
    # Collect .mp3 files
    mp3_files = list(directory.glob("*.mp3"))
    audio_files.extend(mp3_files)
    
    # Sort by filename to ensure consistent processing order
    audio_files.sort(key=lambda x: x.name)
    
    print(f"📁 Found {len(wav_files)} .wav and {len(mp3_files)} .mp3 files")
    return audio_files

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add click tracks to audio files (.wav and .mp3 supported)")
    parser.add_argument("directory", type=str, help="Directory containing audio files")
    parser.add_argument("--clean", action="store_true", help="Clean up existing *_with_clicks.wav files")
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

    # Get all supported audio files
    audio_files = get_audio_files(directory)
    
    if not audio_files:
        print("⚠️  No supported audio files found (.wav or .mp3)")
        exit(1)

    for audio_path in audio_files:
        key = segment_key_from_path(audio_path)
        if click_limits.get(key, {}).get("max_clicks", float("inf")) == 0:
            print(f"⏩ Skipping (explicit 0 clicks): {audio_path}")
            # Save timing data even for explicitly skipped files
            save_beat_timing(audio_path, np.array([]))  # Save empty beats array
            continue

        print(f"🎧 Processing: {audio_path}")
        process_file(audio_path, processor, click, click_limits)

    # Export beat data at the end
    print(f"\n📊 BEAT TIMING SUMMARY:")
    export_beat_data(args.export_beats)