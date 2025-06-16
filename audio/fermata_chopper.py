"""
Automated Fermata Detection and Audio Chopping
Detects fermatas using energy drop analysis - finds significant drops in RMS energy
followed by sustained low energy periods, which typically indicate fermata endings.
"""

import argparse
import os
import shutil
import numpy as np
import librosa
import soundfile as sf
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks


def detect_fermatas_by_energy(y, sr, frame_length=2048, hop_length=512, 
                             energy_percentile=30, stability_percentile=25,
                             min_duration=2.0, min_gap=1.0):
    """
    Detect fermatas by analyzing energy patterns and spectral stability
    
    Parameters:
    -----------
    y : np.array
        Audio time series
    sr : int
        Sample rate
    frame_length : int
        Frame length for RMS analysis
    hop_length : int
        Hop length for analysis
    energy_percentile : float
        Minimum energy percentile for sustained sections
    stability_percentile : float
        Maximum chroma stability percentile (lower = more stable)
    min_duration : float
        Minimum duration (seconds) for a sustained region to be considered
    min_gap : float
        Minimum gap (seconds) between detected fermatas
    
    Returns:
    --------
    fermata_times : list
        List of fermata end times
    debug_info : dict
        Debug information for analysis
    """
    
    print(f"Analyzing audio with:")
    print(f"  Frame length: {frame_length}, Hop length: {hop_length}")
    print(f"  Energy threshold: {energy_percentile}th percentile")
    print(f"  Stability threshold: {stability_percentile}th percentile")
    print(f"  Min duration: {min_duration}s, Min gap: {min_gap}s")
    
    # Calculate RMS energy
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    
    # Calculate chroma (harmonic content)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    chroma_stability = np.std(chroma, axis=0)  # Low values = stable harmony
    
    # Calculate spectral centroid for additional stability measure
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
    spectral_stability = np.std(np.diff(spectral_centroid))  # Overall spectral stability
    
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    
    # Calculate thresholds
    energy_threshold = np.percentile(rms, energy_percentile)
    stability_threshold = np.percentile(chroma_stability, stability_percentile)
    
    print(f"  Energy threshold value: {energy_threshold:.4f}")
    print(f"  Stability threshold value: {stability_threshold:.4f}")
    
    # Find sustained sections with stable harmony
    sustained_mask = (
        (rms > energy_threshold) &  # Sufficient energy
        (chroma_stability < stability_threshold)  # Stable harmony
    )
    
    print(f"  {np.sum(sustained_mask)} / {len(sustained_mask)} frames marked as sustained")
    
    # Find sustained regions
    sustained_regions = []
    in_sustained = False
    start_time = None
    
    for i, is_sustained in enumerate(sustained_mask):
        if is_sustained and not in_sustained:
            start_time = times[i]
            in_sustained = True
        elif not is_sustained and in_sustained:
            end_time = times[i]
            duration = end_time - start_time
            if duration > min_duration:
                sustained_regions.append((start_time, end_time, duration))
            in_sustained = False
    
    # Handle case where audio ends while still sustained
    if in_sustained and start_time is not None:
        end_time = times[-1]
        duration = end_time - start_time
        if duration > min_duration:
            sustained_regions.append((start_time, end_time, duration))
    
    print(f"  Found {len(sustained_regions)} sustained regions:")
    for i, (start, end, duration) in enumerate(sustained_regions):
        print(f"    Region {i+1}: {start:.2f}s - {end:.2f}s (duration: {duration:.2f}s)")
    
    # Extract fermata candidates from sustained regions (use end times)
    fermata_candidates = [end_time for start_time, end_time, duration in sustained_regions]
    
    # Remove fermatas that are too close together
    if len(fermata_candidates) > 1:
        filtered_fermatas = [fermata_candidates[0]]
        for candidate in fermata_candidates[1:]:
            if candidate - filtered_fermatas[-1] > min_gap:
                filtered_fermatas.append(candidate)
        fermata_candidates = filtered_fermatas
    
    debug_info = {
        'rms': rms,
        'times': times,
        'chroma_stability': chroma_stability,
        'sustained_mask': sustained_mask,
        'sustained_regions': sustained_regions,
        'energy_threshold': energy_threshold,
        'stability_threshold': stability_threshold
    }
    
    return fermata_candidates, debug_info


def detect_fermatas_by_energy(y, sr, frame_length=2048, hop_length=512, 
                             energy_percentile=30, stability_percentile=25,
                             min_duration=2.0, min_gap=1.0):
    """
    Detect fermatas by finding low energy regions (simple approach)
    
    Parameters:
    -----------
    y : np.array
        Audio time series
    sr : int
        Sample rate
    frame_length : int
        Frame length for RMS analysis
    hop_length : int
        Hop length for analysis
    energy_percentile : float
        Energy percentile threshold - regions below this are considered low energy
    stability_percentile : float
        Chroma stability percentile (higher = less strict)
    min_duration : float
        Minimum duration (seconds) for a low energy region
    min_gap : float
        Minimum gap (seconds) between detected fermatas
    
    Returns:
    --------
    fermata_times : list
        List of fermata end times
    debug_info : dict
        Debug information for analysis
    """
    
    print(f"Analyzing low energy regions with:")
    print(f"  Frame length: {frame_length}, Hop length: {hop_length}")
    print(f"  Energy threshold: {energy_percentile}th percentile")
    print(f"  Stability threshold: {stability_percentile}th percentile")
    print(f"  Min duration: {min_duration}s, Min gap: {min_gap}s")
    
    # Calculate RMS energy
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    
    # Calculate chroma (harmonic content) - but make it less strict
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    chroma_stability = np.std(chroma, axis=0)  # Low values = stable harmony
    
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    
    # Calculate thresholds
    energy_threshold = np.percentile(rms, energy_percentile)
    stability_threshold = np.percentile(chroma_stability, stability_percentile)
    
    print(f"  Energy threshold value: {energy_threshold:.4f}")
    print(f"  Stability threshold value: {stability_threshold:.4f}")
    
    # Find low energy sections (BELOW threshold, not above!)
    low_energy_mask = (rms < energy_threshold)  # Changed from > to <
    
    # Make stability requirement very lenient
    if stability_percentile > 50:
        # If percentile is high, ignore stability requirement
        sustained_mask = low_energy_mask
        print(f"  Ignoring chroma stability (percentile too high: {stability_percentile})")
    else:
        sustained_mask = low_energy_mask & (chroma_stability < stability_threshold)
    
    print(f"  {np.sum(sustained_mask)} / {len(sustained_mask)} frames marked as low energy")
    
    # Find low energy regions
    low_energy_regions = []
    in_low_energy = False
    start_time = None
    
    for i, is_low in enumerate(sustained_mask):
        if is_low and not in_low_energy:
            start_time = times[i]
            in_low_energy = True
        elif not is_low and in_low_energy:
            end_time = times[i]
            duration = end_time - start_time
            if duration > min_duration:
                low_energy_regions.append((start_time, end_time, duration))
            in_low_energy = False
    
    # Handle case where audio ends while still in low energy
    if in_low_energy and start_time is not None:
        end_time = times[-1]
        duration = end_time - start_time
        if duration > min_duration:
            low_energy_regions.append((start_time, end_time, duration))
    
    print(f"  Found {len(low_energy_regions)} low energy regions:")
    for i, (start, end, duration) in enumerate(low_energy_regions):
        print(f"    Region {i+1}: {start:.2f}s - {end:.2f}s (duration: {duration:.2f}s)")
    
    # Extract fermata candidates from low energy regions (use end times)
    fermata_candidates = [end_time for start_time, end_time, duration in low_energy_regions]
    
    # Remove fermatas that are too close together
    if len(fermata_candidates) > 1:
        filtered_fermatas = [fermata_candidates[0]]
        for candidate in fermata_candidates[1:]:
            if candidate - filtered_fermatas[-1] > min_gap:
                filtered_fermatas.append(candidate)
        fermata_candidates = filtered_fermatas
    
    debug_info = {
        'rms': rms,
        'times': times,
        'chroma_stability': chroma_stability,
        'sustained_mask': sustained_mask,
        'sustained_regions': low_energy_regions,
        'energy_threshold': energy_threshold,
        'stability_threshold': stability_threshold
    }
    
    return fermata_candidates, debug_info


def detect_fermatas_by_energy_drops(y, sr, frame_length=2048, hop_length=512,
                                   drop_threshold=0.3, min_low_duration=0.5, 
                                   min_gap=2.0, smoothing_window=5):
    """
    Detect fermatas by finding significant energy drops (valleys)
    
    Parameters:
    -----------
    y : np.array
        Audio time series
    sr : int
        Sample rate
    frame_length : int
        Frame length for RMS analysis
    hop_length : int
        Hop length for analysis
    drop_threshold : float
        Minimum energy drop ratio to consider (0.3 = 30% drop)
    min_low_duration : float
        Minimum duration (seconds) of low energy to be considered a fermata
    min_gap : float
        Minimum gap (seconds) between detected fermatas
    smoothing_window : int
        Window size for smoothing energy curve
    
    Returns:
    --------
    fermata_times : list
        List of fermata end times
    debug_info : dict
        Debug information for analysis
    """
    
    print(f"Analyzing energy drops with:")
    print(f"  Frame length: {frame_length}, Hop length: {hop_length}")
    print(f"  Drop threshold: {drop_threshold} ({drop_threshold*100:.0f}%)")
    print(f"  Min low duration: {min_low_duration}s, Min gap: {min_gap}s")
    print(f"  Smoothing window: {smoothing_window}")
    
    # Calculate RMS energy
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    
    # Smooth the energy curve
    rms_smooth = uniform_filter1d(rms, size=smoothing_window)
    
    # Find local maxima and minima
    # Find peaks (local maxima)
    peaks, _ = find_peaks(rms_smooth, height=np.percentile(rms_smooth, 20), distance=int(sr/hop_length*0.5))
    
    # Find valleys (local minima) by inverting
    valleys, _ = find_peaks(-rms_smooth, height=-np.percentile(rms_smooth, 80), distance=int(sr/hop_length*0.5))
    
    print(f"  Found {len(peaks)} energy peaks and {len(valleys)} valleys")
    
    # Look for significant drops: peak followed by valley
    fermata_candidates = []
    drop_regions = []
    
    for valley_idx in valleys:
        valley_time = times[valley_idx]
        valley_energy = rms_smooth[valley_idx]
        
        # Find the nearest peak before this valley
        preceding_peaks = peaks[peaks < valley_idx]
        if len(preceding_peaks) == 0:
            continue
            
        peak_idx = preceding_peaks[-1]
        peak_energy = rms_smooth[peak_idx]
        peak_time = times[peak_idx]
        
        # Calculate drop ratio
        if peak_energy > 0:
            drop_ratio = (peak_energy - valley_energy) / peak_energy
            
            # Check if this is a significant drop
            if drop_ratio >= drop_threshold:
                # Check duration of low energy after valley
                low_duration = 0
                for i in range(valley_idx, min(len(rms_smooth), valley_idx + int(min_low_duration * sr / hop_length))):
                    if rms_smooth[i] <= valley_energy * 1.5:  # Allow some variation
                        low_duration = times[i] - valley_time
                    else:
                        break
                
                if low_duration >= min_low_duration:
                    fermata_candidates.append(valley_time + low_duration)
                    drop_regions.append((peak_time, valley_time, valley_time + low_duration, drop_ratio))
                    print(f"    Drop at {valley_time:.2f}s: {drop_ratio:.2f} ratio, low duration: {low_duration:.2f}s")
    
    # Remove fermatas that are too close together
    if len(fermata_candidates) > 1:
        filtered_fermatas = [fermata_candidates[0]]
        filtered_regions = [drop_regions[0]]
        for i, candidate in enumerate(fermata_candidates[1:], 1):
            if candidate - filtered_fermatas[-1] > min_gap:
                filtered_fermatas.append(candidate)
                filtered_regions.append(drop_regions[i])
        fermata_candidates = filtered_fermatas
        drop_regions = filtered_regions
    
    debug_info = {
        'rms': rms,
        'rms_smooth': rms_smooth,
        'times': times,
        'peaks': peaks,
        'valleys': valleys,
        'drop_regions': drop_regions,
        'peak_times': times[peaks] if len(peaks) > 0 else [],
        'valley_times': times[valleys] if len(valleys) > 0 else []
    }
    
    return fermata_candidates, debug_info


def create_segments(y, sr, fermata_times, overlap=0.1):
    """
    Create audio segments from fermata times
    
    Parameters:
    -----------
    y : np.array
        Audio time series
    sr : int
        Sample rate
    fermata_times : list
        List of fermata times
    overlap : float
        Overlap time in seconds between segments
    
    Returns:
    --------
    segments : list
        List of audio segments with metadata
    """
    
    # Add start and end times
    total_duration = librosa.get_duration(y=y, sr=sr)
    segment_times = [0.0] + sorted(fermata_times) + [total_duration]
    
    segments = []
    for i in range(len(segment_times) - 1):
        start_time = max(0, segment_times[i] - overlap/2)
        end_time = min(total_duration, segment_times[i+1] + overlap/2)
        
        start_sample = int(start_time * sr)
        end_sample = int(end_time * sr)
        
        segments.append({
            'audio': y[start_sample:end_sample],
            'start_time': start_time,
            'end_time': end_time,
            'segment_index': i + 1,
            'original_start': segment_times[i],
            'original_end': segment_times[i+1]
        })
    
    return segments


def plot_analysis(y, sr, debug_info, fermata_times, output_path=None):
    """
    Create visualization plots of the fermata detection analysis
    """
    
    # Create time axis for full audio
    audio_times = np.linspace(0, len(y)/sr, len(y))
    
    # Extract debug info
    rms = debug_info['rms']
    times = debug_info['times']
    
    # Check which method was used based on available debug info
    if 'drop_regions' in debug_info:
        # Energy drop method
        rms_smooth = debug_info.get('rms_smooth', rms)
        peaks = debug_info.get('peaks', [])
        valleys = debug_info.get('valleys', [])
        drop_regions = debug_info.get('drop_regions', [])
        
        # Create subplots for energy drop method
        fig, axes = plt.subplots(3, 1, figsize=(15, 10))
        fig.suptitle('Fermata Detection Analysis (Energy Drop Method)', fontsize=16, fontweight='bold')
        
        # Plot 1: Waveform
        axes[0].plot(audio_times, y, alpha=0.6, color='blue', linewidth=0.5)
        axes[0].set_ylabel('Amplitude')
        axes[0].set_title('Audio Waveform')
        axes[0].grid(True, alpha=0.3)
        
        # Add fermata markers
        for fermata_time in fermata_times:
            axes[0].axvline(x=fermata_time, color='red', linestyle='--', linewidth=2, alpha=0.8)
        
        # Plot 2: RMS Energy with peaks and valleys
        axes[1].plot(times, rms, color='lightgreen', linewidth=1, alpha=0.7, label='RMS Energy (raw)')
        axes[1].plot(times, rms_smooth, color='green', linewidth=2, label='RMS Energy (smoothed)')
        
        # Mark peaks and valleys
        if len(peaks) > 0:
            axes[1].scatter(times[peaks], rms_smooth[peaks], color='blue', s=50, zorder=5, label='Energy Peaks')
        if len(valleys) > 0:
            axes[1].scatter(times[valleys], rms_smooth[valleys], color='orange', s=50, zorder=5, label='Energy Valleys')
        
        # Highlight drop regions
        for i, (peak_time, valley_time, end_time, drop_ratio) in enumerate(drop_regions):
            axes[1].axvspan(peak_time, end_time, alpha=0.3, color='yellow', 
                           label='Fermata Drop Region' if i == 0 else "")
        
        axes[1].set_ylabel('RMS Energy')
        axes[1].set_title('Energy Analysis with Peak/Valley Detection')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        # Add fermata markers
        for fermata_time in fermata_times:
            axes[1].axvline(x=fermata_time, color='red', linestyle='--', linewidth=2, alpha=0.8)
        
        # Plot 3: Energy drops analysis
        axes[2].plot(times, rms_smooth, color='green', linewidth=1.5, label='RMS Energy')
        if len(drop_regions) == 0:
            axes[2].text(0.5, 0.5, 'No significant energy drops detected', 
                        transform=axes[2].transAxes, ha='center', va='center', fontsize=12,
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        axes[2].set_ylabel('RMS Energy')
        axes[2].set_xlabel('Time (seconds)')
        axes[2].set_title('Energy Drop Analysis')
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)
        
        # Add statistics
        stats_text = f"""Detection Stats:
        Energy peaks found: {len(peaks)}
        Energy valleys found: {len(valleys)}
        Significant drops: {len(drop_regions)}
        Fermatas detected: {len(fermata_times)}"""
        
    else:
        # Original energy method
        chroma_stability = debug_info['chroma_stability']
        sustained_mask = debug_info['sustained_mask']
        sustained_regions = debug_info['sustained_regions']
        energy_threshold = debug_info['energy_threshold']
        stability_threshold = debug_info['stability_threshold']
        
        # Create subplots for original method
        fig, axes = plt.subplots(4, 1, figsize=(15, 12))
        fig.suptitle('Fermata Detection Analysis (Low Energy Method)', fontsize=16, fontweight='bold')
        
        # Plot 1: Waveform
        axes[0].plot(audio_times, y, alpha=0.6, color='blue', linewidth=0.5)
        axes[0].set_ylabel('Amplitude')
        axes[0].set_title('Audio Waveform')
        axes[0].grid(True, alpha=0.3)
        
        # Add fermata markers
        for fermata_time in fermata_times:
            axes[0].axvline(x=fermata_time, color='red', linestyle='--', linewidth=2, alpha=0.8)
        
        # Plot 2: RMS Energy
        axes[1].plot(times, rms, color='green', linewidth=1.5, label='RMS Energy')
        axes[1].axhline(y=energy_threshold, color='orange', linestyle='-', linewidth=2, 
                       label=f'Energy Threshold ({energy_threshold:.4f})')
        axes[1].set_ylabel('RMS Energy')
        axes[1].set_title('Energy Analysis (Looking for LOW energy regions)')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        # Highlight low energy regions
        for start_time, end_time, duration in sustained_regions:
            axes[1].axvspan(start_time, end_time, alpha=0.3, color='yellow', 
                           label='Low Energy Region' if start_time == sustained_regions[0][0] else "")
        
        # Add fermata markers
        for fermata_time in fermata_times:
            axes[1].axvline(x=fermata_time, color='red', linestyle='--', linewidth=2, alpha=0.8)
        
        # Plot 3: Chroma Stability
        axes[2].plot(times, chroma_stability, color='purple', linewidth=1.5, label='Chroma Stability')
        axes[2].axhline(y=stability_threshold, color='orange', linestyle='-', linewidth=2,
                       label=f'Stability Threshold ({stability_threshold:.4f})')
        axes[2].set_ylabel('Chroma Std Dev')
        axes[2].set_title('Harmonic Stability Analysis (lower = more stable)')
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)
        
        # Highlight low energy regions
        for start_time, end_time, duration in sustained_regions:
            axes[2].axvspan(start_time, end_time, alpha=0.3, color='yellow')
        
        # Add fermata markers
        for fermata_time in fermata_times:
            axes[2].axvline(x=fermata_time, color='red', linestyle='--', linewidth=2, alpha=0.8)
        
        # Plot 4: Combined Analysis
        axes[3].plot(times, rms, color='green', linewidth=1.5, label='RMS Energy')
        axes[3].fill_between(times, 0, np.max(rms), where=sustained_mask, alpha=0.3, color='yellow', 
                            label='Low Energy Regions', step='pre')
        axes[3].axhline(y=energy_threshold, color='orange', linestyle='-', linewidth=2, alpha=0.7)
        
        axes[3].set_ylabel('RMS Energy')
        axes[3].set_xlabel('Time (seconds)')
        axes[3].set_title('Low Energy Detection (Yellow areas = detected low energy)')
        axes[3].legend()
        axes[3].grid(True, alpha=0.3)
        
        # Add fermata markers
        for i, fermata_time in enumerate(fermata_times):
            axes[3].axvline(x=fermata_time, color='red', linestyle='--', linewidth=2, alpha=0.8,
                           label='Detected Fermatas' if i == 0 else "")
        
        # Add statistics
        stats_text = f"""Detection Stats:
        Low energy frames: {np.sum(sustained_mask)} / {len(sustained_mask)} ({100*np.sum(sustained_mask)/len(sustained_mask):.1f}%)
        Low energy regions found: {len(sustained_regions)}
        Fermatas detected: {len(fermata_times)}
        Energy threshold: {energy_threshold:.4f}
        Stability threshold: {stability_threshold:.4f}"""
    
    # Add fermata markers to last plot
    for i, fermata_time in enumerate(fermata_times):
        axes[-1].axvline(x=fermata_time, color='red', linestyle='--', linewidth=2, alpha=0.8,
                        label='Detected Fermatas' if i == 0 else "")
    
    # Add statistics text
    axes[-1].text(0.02, 0.98, stats_text, transform=axes[-1].transAxes, 
                 fontsize=9, verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
    
    plt.show()
    
    return fig
    """
    Create audio segments from fermata times
    
    Parameters:
    -----------
    y : np.array
        Audio time series
    sr : int
        Sample rate
    fermata_times : list
        List of fermata times
    overlap : float
        Overlap time in seconds between segments
    
    Returns:
    --------
    segments : list
        List of audio segments with metadata
    """
    
    # Add start and end times
    total_duration = librosa.get_duration(y=y, sr=sr)
    segment_times = [0.0] + sorted(fermata_times) + [total_duration]
    
    segments = []
    for i in range(len(segment_times) - 1):
        start_time = max(0, segment_times[i] - overlap/2)
        end_time = min(total_duration, segment_times[i+1] + overlap/2)
        
        start_sample = int(start_time * sr)
        end_sample = int(end_time * sr)
        
        segments.append({
            'audio': y[start_sample:end_sample],
            'start_time': start_time,
            'end_time': end_time,
            'segment_index': i + 1,
            'original_start': segment_times[i],
            'original_end': segment_times[i+1]
        })
    
    return segments


def save_segments(segments, input_path, sr, output_dir=None, clean_output_dir=True):
    """
    Save audio segments to files
    
    Parameters:
    -----------
    segments : list
        List of audio segments
    input_path : str or Path
        Original input file path
    sr : int
        Sample rate used by librosa
    output_dir : str or Path, optional
        Output directory (default: same as input)
    clean_output_dir : bool
        Whether to clean the output directory before saving
    """
    
    input_path = Path(input_path)
    if output_dir is None:
        output_dir = input_path.parent
        clean_output_dir = False  # Don't clean parent directory
    else:
        output_dir = Path(output_dir)
    
    # Clean output directory if requested and it exists
    if clean_output_dir and output_dir.exists():
        print(f"Cleaning output directory: {output_dir}")
        shutil.rmtree(output_dir)
    
    # Create output directory
    output_dir.mkdir(exist_ok=True, parents=True)
    
    base_name = input_path.stem
    extension = input_path.suffix
    
    saved_files = []
    
    for segment in segments:
        output_filename = f"{base_name}-{segment['segment_index']}{extension}"
        output_path = output_dir / output_filename
        
        # Use the sample rate from librosa.load(), not from the original file
        sf.write(output_path, segment['audio'], samplerate=sr)
        
        saved_files.append(output_path)
        print(f"Saved: {output_filename}")
        print(f"  Duration: {segment['end_time'] - segment['start_time']:.2f}s")
        print(f"  Original range: {segment['original_start']:.2f}s - {segment['original_end']:.2f}s")
    
    return saved_files


def main():
    parser = argparse.ArgumentParser(description="Detect fermatas by analyzing energy drops and chop audio into segments")
    
    # Required arguments
    parser.add_argument('-i', '--input', required=True, 
                       help='Input audio file path')
    
    # Analysis parameters
    parser.add_argument('--frame-length', type=int, default=2048,
                       help='Frame length for RMS analysis (default: 2048)')
    parser.add_argument('--hop-length', type=int, default=512,
                       help='Hop length for analysis (default: 512)')
    
    # Detection thresholds
    parser.add_argument('--drop-threshold', type=float, default=0.3,
                       help='Energy drop ratio threshold (0.3 = 30% drop, default: 0.3)')
    parser.add_argument('--min-low-duration', type=float, default=0.5,
                       help='Minimum duration of low energy after drop (default: 0.5s)')
    parser.add_argument('--smoothing-window', type=int, default=5,
                       help='Window size for energy smoothing (default: 5)')
    
    # Simple energy method parameters
    parser.add_argument('--energy-percentile', type=float, default=30,
                       help='Energy percentile threshold - regions BELOW this are low energy (default: 30)')
    parser.add_argument('--stability-percentile', type=float, default=25,
                       help='Chroma stability percentile - higher values are more permissive (default: 25)')
    
    # Duration parameters
    parser.add_argument('--min-duration', type=float, default=2.0,
                       help='Minimum duration for low energy regions (simple method, default: 2.0s)')
    parser.add_argument('--min-gap', type=float, default=2.0,
                       help='Minimum gap between fermatas (default: 2.0s)')
    parser.add_argument('--overlap', type=float, default=0.1,
                       help='Overlap between segments (default: 0.1s)')
    
    # Output parameters
    parser.add_argument('-o', '--output-dir', 
                       help='Output directory (default: same as input file)')
    parser.add_argument('--debug', action='store_true',
                       help='Save debug information')
    parser.add_argument('--plot', action='store_true',
                       help='Show analysis plot')
    parser.add_argument('--save-plot', 
                       help='Save plot to specified file (e.g., analysis.png)')
    parser.add_argument('--no-clean', action='store_true',
                       help='Do not clean output directory before saving segments')
    parser.add_argument('--preserve-sr', action='store_true',
                       help='Load and save at original sample rate (no resampling)')
    
    args = parser.parse_args()
    
    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist")
        return 1
    
    print(f"Processing: {input_path}")
    print("=" * 50)
    
    try:
        # Load audio
        print("Loading audio...")
        if args.preserve_sr:
            y, sr = librosa.load(str(input_path), sr=None)  # Preserve original sample rate
        else:
            y, sr = librosa.load(str(input_path))  # Default to 22050 Hz
        duration = librosa.get_duration(y=y, sr=sr)
        print(f"Audio loaded: {duration:.2f}s, sample rate: {sr}Hz")
        print()
        
        # Choose detection method based on parameters
        if args.drop_threshold != 0.3 or args.min_low_duration != 0.5:
            # User specified drop parameters, use energy drop method
            print("Detecting fermatas using energy drop analysis...")
            fermata_times, debug_info = detect_fermatas_by_energy_drops(
                y, sr,
                frame_length=args.frame_length,
                hop_length=args.hop_length,
                drop_threshold=args.drop_threshold,
                min_low_duration=args.min_low_duration,
                min_gap=args.min_gap,
                smoothing_window=args.smoothing_window
            )
        else:
            # Use simple energy percentile method
            print("Detecting fermatas using simple energy analysis...")
            fermata_times, debug_info = detect_fermatas_by_energy(
                y, sr,
                frame_length=args.frame_length,
                hop_length=args.hop_length,
                energy_percentile=args.energy_percentile,
                stability_percentile=args.stability_percentile,
                min_duration=args.min_duration,
                min_gap=args.min_gap
            )
        
        print()
        print(f"Detected {len(fermata_times)} fermatas at times: {[f'{t:.2f}s' for t in fermata_times]}")
        
        # Create plot if requested
        if args.plot or args.save_plot:
            print("\nCreating analysis plot...")
            plot_path = args.save_plot if args.save_plot else None
            plot_analysis(y, sr, debug_info, fermata_times, plot_path)
        
        if len(fermata_times) == 0:
            print("No fermatas detected. Creating single segment.")
            fermata_times = []
        
        print()
        
        # Create segments
        print("Creating segments...")
        segments = create_segments(y, sr, fermata_times, overlap=args.overlap)
        print(f"Created {len(segments)} segments")
        print()
        
        # Save segments
        print("Saving segments...")
        clean_output = not args.no_clean
        saved_files = save_segments(segments, input_path, sr, args.output_dir, clean_output_dir=clean_output)
        print()
        print(f"Successfully saved {len(saved_files)} segments")
        
        # Save debug info if requested
        if args.debug:
            debug_path = input_path.parent / f"{input_path.stem}_debug.npz"
            np.savez(debug_path, **debug_info, fermata_times=fermata_times)
            print(f"Debug info saved to: {debug_path}")
        
        return 0
        
    except Exception as e:
        print(f"Error processing audio: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())