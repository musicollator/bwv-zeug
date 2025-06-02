import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np

# Load the audio file
y, sr = librosa.load("VID20250326172717.wav")
tempo, beats = librosa.beat.beat_track(y=y, sr=sr)

if isinstance(tempo, (np.ndarray, list)):
    tempo = float(tempo[0])

times = librosa.frames_to_time(beats, sr=sr)

# Compute onset envelope
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
onset_strengths = onset_env[beats]

# Define a threshold to filter strong beats (e.g. 75% of the max strength)
threshold = 0.15 * np.max(onset_strengths)
strong_beats = beats[onset_strengths >= threshold]
strong_times = librosa.frames_to_time(strong_beats, sr=sr)
print(strong_beats.size)

# Plot waveform and strong beats only
plt.figure(figsize=(14, 5))
librosa.display.waveshow(y, sr=sr, alpha=0.6)
plt.vlines(strong_times, -1, 1, color='r', linestyle='-', label='Strong Beats')
plt.title(f"Strong Beats (tempo: {tempo:.1f} BPM, threshold: {threshold:.2f})")
plt.xlabel("Time (s)")
plt.legend()
plt.tight_layout()
plt.show()
