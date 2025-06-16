# visualize_beats.py - Visualize audio waveform with detected beats

import yaml
import numpy as np
import matplotlib.pyplot as plt
import soundfile as sf
from pathlib import Path
import argparse

def load_detected_beats(beats_yaml_path):
    """Load detected beats from YAML file."""
    with open(beats_yaml_path) as f:
        beat_data = yaml.safe_load(f)
    
    return beat_data

def load_yaml_timing_marks(yaml_path):
    """Load timing marks from YAML file (original or warped)."""
    if not yaml_path or not Path(yaml_path).exists():
        return None
    
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    
    meta = data['meta']
    flow = data['flow']
    tick_to_second = meta['tickToSecondRatio']
    
    # Extract bar positions and quarter note beats
    bar_times = []
    quarter_note_times = []
    
    for event in flow:
        tick, channel, end_tick, info = event
        time_seconds = tick * tick_to_second
        
        # Bar markers
        if info == 'bar':
            bar_times.append(time_seconds)
        
        # Note onsets (rough quarter note approximation)
        if channel is not None and isinstance(info, list):
            quarter_note_times.append(time_seconds)
    
    # Remove duplicates and sort
    bar_times = sorted(set(bar_times))
    quarter_note_times = sorted(set(quarter_note_times))
    
    # Estimate quarter note grid from bar positions
    if len(bar_times) > 1:
        estimated_quarter_notes = []
        for i in range(len(bar_times) - 1):
            start_bar = bar_times[i]
            next_bar = bar_times[i + 1]
            bar_duration = next_bar - start_bar
            
            # Assume 4/4 time - 4 quarter notes per bar
            quarter_interval = bar_duration / 4
            for q in range(4):
                estimated_quarter_notes.append(start_bar + q * quarter_interval)
        
        # Add quarter notes for final bar
        if len(bar_times) >= 2:
            last_bar = bar_times[-1]
            avg_bar_duration = np.mean(np.diff(bar_times))
            quarter_interval = avg_bar_duration / 4
            for q in range(4):
                estimated_quarter_notes.append(last_bar + q * quarter_interval)
    else:
        estimated_quarter_notes = quarter_note_times
    
    return {
        'bars': bar_times,
        'quarter_notes': sorted(set(estimated_quarter_notes)),
        'tick_to_second': tick_to_second,
        'total_duration': max(quarter_note_times + bar_times) if (quarter_note_times + bar_times) else 0
    }

def concatenate_audio_segments(audio_dir, beats_data, default_sr=44100):
    """Concatenate audio segments in the same order as beat detection."""
    segments = beats_data['segments']
    
    concatenated_audio = []
    segment_boundaries = [0]  # Start positions of each segment
    segment_info = []
    
    # Get sample rate from first available audio file
    sr = None
    for segment_key in sorted(segments.keys()):
        audio_file = Path(audio_dir) / segment_key
        if audio_file.exists():
            _, sr = sf.read(str(audio_file), frames=1)  # Just read 1 frame to get sr
            break
    
    if sr is None:
        print(f"⚠️  No audio files found, using default sample rate: {default_sr} Hz")
        sr = default_sr
    else:
        print(f"Using sample rate: {sr} Hz")
    
    # Sort segments by filename to ensure same order as beat detection
    for segment_key in sorted(segments.keys()):
        segment = segments[segment_key]
        audio_file = Path(audio_dir) / segment_key
        
        if audio_file.exists():
            print(f"Loading: {audio_file}")
            audio, file_sr = sf.read(str(audio_file))
            
            # Ensure same sample rate
            if file_sr != sr:
                print(f"⚠️  Sample rate mismatch: {file_sr} vs {sr}")
                sr = file_sr  # Use the actual file's sample rate
            
            # Ensure mono
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
                
        else:
            # Only create silence if file actually doesn't exist
            print(f"⚠️  Audio file not found: {audio_file}, creating silence")
            duration = segment['duration']
            silence_samples = int(duration * sr)
            audio = np.zeros(silence_samples)
        
        concatenated_audio.extend(audio)
        segment_boundaries.append(len(concatenated_audio))
        
        segment_info.append({
            'key': segment_key,
            'start_sample': segment_boundaries[-2],
            'end_sample': segment_boundaries[-1],
            'duration': len(audio) / sr,
            'original_duration': segment['duration'],
            'has_beats': segment['has_beats'],
            'num_beats': segment['num_beats'],
            'is_quiet': not segment['has_beats']  # Quiet segment = no beats detected
        })
    
    return np.array(concatenated_audio), sr, segment_info

def plot_waveform_with_beats(audio, sr, beats_data, segment_info, yaml_timing=None, output_file=None):
    """Plot waveform with detected beats and optional YAML timing overlaid."""
    
    # Time axis for audio
    time_axis = np.arange(len(audio)) / sr
    total_duration = len(audio) / sr
    
    # Get concatenated beats
    concatenated_beats = beats_data['concatenated']['beats']
    
    # Create the plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))
    
    # Top plot: Full waveform with beats
    ax1.plot(time_axis, audio, color='lightblue', alpha=0.7, linewidth=0.5)
    
    title = 'Full Audio Waveform with Detected Beats'
    if yaml_timing:
        title += ' + YAML Timing'
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('Amplitude')
    ax1.grid(True, alpha=0.3)
    
    # Get plot limits for half-height detected beats
    y_min, y_max = ax1.get_ylim()
    y_mid = (y_min + y_max) / 2
    
    # Plot segment boundaries and highlight quiet segments
    for i, seg in enumerate(segment_info):
        start_time = seg['start_sample'] / sr
        end_time = seg['end_sample'] / sr
        
        # Segment boundary
        ax1.axvline(x=end_time, color='red', linestyle='--', alpha=0.7, linewidth=1)
        
        # Highlight quiet segments (no beats detected)
        if seg['is_quiet']:
            ax1.axvspan(start_time, end_time, color='gray', alpha=0.3, label='Quiet (No Beats)' if i == 0 else "")
        
        # Add segment labels
        seg_center = (start_time + end_time) / 2
        label_text = f"{seg['key']}\n{seg['num_beats']} beats"
        if seg['is_quiet']:
            label_text += "\n(quiet)"
            
        ax1.text(seg_center, y_max * 0.9, 
                label_text, 
                ha='center', va='top', fontsize=8, 
                bbox=dict(boxstyle='round,pad=0.3', 
                         facecolor='lightgray' if seg['is_quiet'] else 'yellow', 
                         alpha=0.7))
    
    # Plot concatenated beats (detected by madmom) - HALF HEIGHT
    for beat_time in concatenated_beats:
        if beat_time <= total_duration:
            ax1.plot([beat_time, beat_time], [y_min, y_mid], color='green', alpha=0.8, linewidth=2)
    
    # Plot YAML timing marks if provided
    yaml_quarter_count = 0
    if yaml_timing:
        # Plot quarter notes from YAML - FULL HEIGHT
        for quarter_time in yaml_timing['quarter_notes']:
            if quarter_time <= total_duration:
                ax1.axvline(x=quarter_time, color='orange', alpha=0.7, linewidth=1.5, linestyle='-')
                yaml_quarter_count += 1
    
    # Add legend
    legend_items = []
    legend_items.append(([], [], {'color': 'green', 'linewidth': 2, 'label': f'Detected Beats ({len(concatenated_beats)})'}))
    legend_items.append(([], [], {'color': 'red', 'linestyle': '--', 'label': 'Segment Boundaries'}))
    
    if yaml_timing:
        legend_items.append(([], [], {'color': 'orange', 'linewidth': 1.5, 'label': f'YAML Quarter Notes ({yaml_quarter_count})'}))
    
    # Only add quiet legend if there are quiet segments
    if any(seg['is_quiet'] for seg in segment_info):
        legend_items.append(([], [], {'color': 'gray', 'alpha': 0.3, 'linewidth': 10, 'label': 'Quiet Segments'}))
    
    for item in legend_items:
        ax1.plot(item[0], item[1], **item[2])
    ax1.legend()
    
    # Bottom plot: Zoomed view of first 30 seconds
    zoom_duration = min(30, total_duration)
    zoom_samples = int(zoom_duration * sr)
    zoom_time = time_axis[:zoom_samples]
    zoom_audio = audio[:zoom_samples]
    
    ax2.plot(zoom_time, zoom_audio, color='blue', linewidth=0.8)
    ax2.set_title(f'Zoomed View (First {zoom_duration:.1f} seconds)', fontsize=12)
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('Amplitude')
    ax2.grid(True, alpha=0.3)
    
    # Get zoom plot limits for half-height detected beats
    y_min_zoom, y_max_zoom = ax2.get_ylim()
    y_mid_zoom = (y_min_zoom + y_max_zoom) / 2
    
    # Plot quiet segments in zoom window
    for seg in segment_info:
        start_time = seg['start_sample'] / sr
        end_time = seg['end_sample'] / sr
        if seg['is_quiet'] and start_time < zoom_duration:
            ax2.axvspan(start_time, min(end_time, zoom_duration), color='gray', alpha=0.3)
    
    # Plot detected beats in zoom window - HALF HEIGHT
    for beat_time in concatenated_beats:
        if beat_time <= zoom_duration:
            ax2.plot([beat_time, beat_time], [y_min_zoom, y_mid_zoom], color='green', alpha=0.8, linewidth=2)
    
    # Plot YAML timing in zoom window
    if yaml_timing:
        for quarter_time in yaml_timing['quarter_notes']:
            if quarter_time <= zoom_duration:
                ax2.axvline(x=quarter_time, color='orange', alpha=0.7, linewidth=1.5)
    
    # Plot segment boundaries in zoom window
    for seg in segment_info:
        boundary_time = seg['end_sample'] / sr
        if boundary_time <= zoom_duration:
            ax2.axvline(x=boundary_time, color='red', linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✅ Plot saved to {output_file}")
    
    plt.show()
    
    # Print summary statistics
    quiet_segments = [seg for seg in segment_info if seg['is_quiet']]
    audio_segments = [seg for seg in segment_info if not seg['is_quiet']]
    
    print(f"\n📊 SUMMARY:")
    print(f"Total duration: {total_duration:.2f} seconds")
    print(f"Audio segments (with beats): {len(audio_segments)}")
    print(f"Quiet segments (no beats): {len(quiet_segments)}")
    print(f"Detected beats: {len(concatenated_beats)}")
    if yaml_timing:
        print(f"YAML quarter notes: {yaml_quarter_count}")
    
    if len(concatenated_beats) > 1:
        print(f"Average beat interval: {np.mean(np.diff(concatenated_beats)):.3f} seconds")
        print(f"Estimated tempo: {60.0 / np.mean(np.diff(concatenated_beats)):.1f} BPM")
    
    # Per-segment breakdown
    print(f"\n📋 SEGMENT BREAKDOWN:")
    for seg in segment_info:
        status = "QUIET" if seg['is_quiet'] else "WITH BEATS"
        print(f"  {seg['key']}: {seg['num_beats']} beats, {seg['duration']:.2f}s, {status}")

def analyze_beat_consistency(concatenated_beats):
    """Analyze the consistency of beat intervals."""
    if len(concatenated_beats) < 2:
        return
    
    intervals = np.diff(concatenated_beats)
    
    plt.figure(figsize=(12, 4))
    
    plt.subplot(1, 2, 1)
    plt.plot(intervals, 'o-', markersize=3)
    plt.title('Beat Intervals Over Time')
    plt.xlabel('Beat Index')
    plt.ylabel('Interval (seconds)')
    plt.grid(True, alpha=0.3)
    
    plt.subplot(1, 2, 2)
    plt.hist(intervals, bins=20, alpha=0.7, edgecolor='black')
    plt.title('Beat Interval Distribution')
    plt.xlabel('Interval (seconds)')
    plt.ylabel('Frequency')
    plt.grid(True, alpha=0.3)
    
    # Add statistics
    plt.figtext(0.02, 0.02, 
                f'Mean: {np.mean(intervals):.3f}s | '
                f'Std: {np.std(intervals):.3f}s | '
                f'CV: {np.std(intervals)/np.mean(intervals):.3f}',
                fontsize=10)
    
    plt.tight_layout()
    plt.show()
    
    print(f"\n📈 BEAT INTERVAL ANALYSIS:")
    print(f"Mean interval: {np.mean(intervals):.3f} ± {np.std(intervals):.3f} seconds")
    print(f"Tempo range: {60.0/np.max(intervals):.1f} - {60.0/np.min(intervals):.1f} BPM")
    print(f"Coefficient of variation: {np.std(intervals)/np.mean(intervals):.3f}")

def main():
    parser = argparse.ArgumentParser(description="Visualize audio waveform with detected beats")
    parser.add_argument("--beats-yaml", default="detected_beats.yaml", 
                       help="Path to detected beats YAML file")
    parser.add_argument("--audio-dir", default="audio_chunks", 
                       help="Directory containing audio chunks")
    parser.add_argument("--output", default="waveform_with_beats.png", 
                       help="Output plot filename")
    parser.add_argument("--no-save", action="store_true", 
                       help="Don't save plot to file")
    parser.add_argument("--sample-rate", type=int, default=44100,
                       help="Sample rate for silence segments (if no audio files found)")
    parser.add_argument("--yaml-timing", type=str, default=None,
                       help="Path to YAML timing file (original bwv245.yaml or warped bwv245_warped.yaml)")
    args = parser.parse_args()
    
    print("🎵 Loading detected beats...")
    beats_data = load_detected_beats(args.beats_yaml)
    
    print("🎧 Concatenating audio segments (including silence)...")
    audio, sr, segment_info = concatenate_audio_segments(args.audio_dir, beats_data, args.sample_rate)
    
    if audio is None:
        print(f"❌ Failed to load audio")
        return
    
    # Load YAML timing if provided
    yaml_timing = None
    if args.yaml_timing:
        print(f"📄 Loading YAML timing from {args.yaml_timing}...")
        yaml_timing = load_yaml_timing_marks(args.yaml_timing)
        if yaml_timing:
            print(f"✅ Loaded {len(yaml_timing['quarter_notes'])} quarter notes, {len(yaml_timing['bars'])} bars")
        else:
            print(f"❌ Failed to load YAML timing from {args.yaml_timing}")
    
    print("📊 Plotting waveform with beats...")
    output_file = None if args.no_save else args.output
    plot_waveform_with_beats(audio, sr, beats_data, segment_info, yaml_timing, output_file)
    
    print("📈 Analyzing beat consistency...")
    analyze_beat_consistency(beats_data['concatenated']['beats'])

if __name__ == "__main__":
    main()