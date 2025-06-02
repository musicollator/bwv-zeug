import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import csv

# Load the audio
filename = "VID20250326172717_percussive.wav"
y, sr = librosa.load(filename)

# Extract onset strength envelope
onset_env = librosa.onset.onset_strength(y=y, sr=sr)

# Detect onset frames (tune delta/wait for sensitivity)
onset_frames = librosa.onset.onset_detect(
    onset_envelope=onset_env,
    sr=sr,
    delta=0.1,
    wait=1
)

# Convert frames to times (in seconds)
onset_times = librosa.frames_to_time(onset_frames, sr=sr)

# Save to CSV
with open("VID20250326172717_percussive_onset_times.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["onset_time_seconds"])
    for t in onset_times:
        writer.writerow([round(t, 6)])

# Plot waveform with onset markers
plt.figure(figsize=(14, 5))
librosa.display.waveshow(y, sr=sr, alpha=0.6)
for t in onset_times:
    plt.axvline(x=t, color='r', linestyle='--', alpha=0.7)
plt.title("Waveform with Detected Onsets")
plt.xlabel("Time (s)")
plt.tight_layout()
plt.show()
