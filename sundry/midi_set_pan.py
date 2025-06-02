import sys
import os
from mido import MidiFile, MidiTrack, Message

# Check command-line arguments
if len(sys.argv) < 2:
    print("Usage: python set_pan.py <input_file.mid>")
    sys.exit(1)

input_file = sys.argv[1]

# Derive output filename
base, _ = os.path.splitext(input_file)
output_file = f"{base}_panned.midi"

# Define pan positions: MIDI channel (0–15) → pan value (0–127)
pan_by_channel = {
    0: 32,   # left
    1: 96,   # right
    # Add more if needed
}

# Load MIDI file
mid = MidiFile(input_file)
for i, track in enumerate(mid.tracks):
    new_track = MidiTrack()
    used_channels = set()

    for msg in track:
        # Inject pan message once per channel
        if msg.type in ('note_on', 'program_change') and msg.channel not in used_channels:
            print(msg.channel)
            pan = pan_by_channel.get(msg.channel)
            if pan is not None:
                new_track.append(Message('control_change', control=10, value=pan, channel=msg.channel, time=0))
                used_channels.add(msg.channel)
        new_track.append(msg)

    mid.tracks[i] = new_track

# Save the modified file
mid.save(output_file)
print(f"💾 Saved: {output_file}")
