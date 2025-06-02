#!/usr/bin/env python3
"""
midi_to_wav.py

Convert MIDI files to WAV audio using FluidSynth
================================================

Usage:
    python midi_to_wav.py input.midi
    
Output:
    Creates input.wav in the same directory
"""

from midi2audio import FluidSynth
import os
import sys
import argparse

def setup_argument_parser():
    """Setup command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Convert MIDI files to WAV audio using FluidSynth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python midi_to_wav.py song.midi          # Creates song.wav
  python midi_to_wav.py bwv1006.midi       # Creates bwv1006.wav
  python midi_to_wav.py ../test.midi       # Creates ../test.wav
        """
    )
    
    parser.add_argument('midi_file', 
                       help='Input MIDI file path')
    
    return parser.parse_args()

def main():
    """Main function."""
    print("🎵 MIDI to WAV Converter")
    print("=" * 30)
    
    # Parse arguments
    args = setup_argument_parser()
    midi_file = args.midi_file
    
    # Validate input file
    if not os.path.exists(midi_file):
        print(f"❌ Error: MIDI file not found: {midi_file}")
        sys.exit(1)
    
    if not midi_file.lower().endswith(('.mid', '.midi')):
        print(f"⚠️  Warning: File doesn't have .mid or .midi extension: {midi_file}")
    
    # Generate output filename (same name but .wav extension)
    base_name = os.path.splitext(midi_file)[0]  # Remove existing extension
    wav_file = f"{base_name}.wav"
    
    print(f"📄 Input:  {midi_file}")
    print(f"📊 Output: {wav_file}")
    
    # SoundFont configuration
    soundfont_path = "/usr/local/share/soundfonts/Definitive_Guitar_Kit.sf2"
    
    # Verify SoundFont exists
    if not os.path.exists(soundfont_path):
        print(f"❌ Error: SoundFont not found at: {soundfont_path}")
        print("   Please install a SoundFont or update the path in the script.")
        sys.exit(1)
    
    print(f"🎼 Using SoundFont: {soundfont_path}")
    print()
    
    try:
        # Initialize FluidSynth
        print("🔧 Initializing FluidSynth...")
        fs = FluidSynth(sound_font=soundfont_path)
        
        # Convert MIDI to WAV
        print("🎵 Converting MIDI to WAV...")
        fs.midi_to_audio(midi_file, wav_file)
        
        # Verify output was created
        if os.path.exists(wav_file):
            file_size = os.path.getsize(wav_file)
            print(f"✅ Conversion successful!")
            print(f"   📁 Output file: {wav_file}")
            print(f"   📊 File size: {file_size:,} bytes")
        else:
            print(f"❌ Error: Output file was not created: {wav_file}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error during conversion: {e}")
        sys.exit(1)
    
    print()
    print("🎉 MIDI to WAV conversion completed successfully!")

if __name__ == "__main__":
    main()