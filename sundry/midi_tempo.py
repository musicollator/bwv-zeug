from mido import MidiFile, tempo2bpm

midi_file = MidiFile("bwv1006_ly_one_line.midi")

tempos = []
for track in midi_file.tracks:
    for msg in track:
        if msg.type == 'set_tempo':
            tempos.append(msg.tempo)

tempos_bpm = [tempo2bpm(t) for t in tempos]
print("First few tempo changes (BPM):", tempos_bpm[:10])
print("Total tempo change events:", len(tempos_bpm))