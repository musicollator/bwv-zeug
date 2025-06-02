import mido

mid = mido.MidiFile('bwv1006_ly_one_line.midi')

# Total time in seconds
total_time = sum(msg.time for msg in mid if not msg.is_meta)
print(f"Duration: {total_time:.2f} seconds")
