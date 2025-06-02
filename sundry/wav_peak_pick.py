import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import csv

# Load the audio file
y, sr = librosa.load("bwv1006_percussive.wav")

# Compute onset envelope
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
times = librosa.times_like(onset_env, sr=sr)

# Peak picking
peaks = librosa.util.peak_pick(onset_env, pre_max=3, post_max=3, pre_avg=5, post_avg=5, delta=0, wait=20)
peak_times = times[peaks]

# Save peak times to CSV
with open("bwv1006_percussive_peak_pick.csv", "w") as f:
    writer = csv.writer(f)
    writer.writerow(["peak_time"])
    writer.writerows([[round(t, 3)] for t in peak_times])

# Create a spectrogram
D = np.abs(librosa.stft(y))
S_db = librosa.amplitude_to_db(D, ref=np.max)

# Plot onset envelope and spectrogram
fig, ax = plt.subplots(nrows=2, sharex=True, figsize=(14, 6))

# Onset strength with peaks
ax[0].plot(times, onset_env, label='Onset strength', alpha=0.8)
ax[0].vlines(times[peaks], 0, onset_env.max(), color='r', alpha=0.8, label='Selected peaks')
ax[0].legend(loc='upper right', frameon=True)
ax[0].set_ylabel("Onset Strength")
ax[0].set_title("Onset Strength with Detected Peaks")

# Spectrogram
librosa.display.specshow(S_db, sr=sr, x_axis='time', y_axis='log', ax=ax[1])
ax[1].set_title("Log-Frequency Spectrogram (dB)")
fig.tight_layout()
plt.show()
