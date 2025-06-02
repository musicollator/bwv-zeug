import librosa
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# === Config ===
AUDIO_FILE = "bwv1006_percussive.wav"
THRESHOLD_RATIO = 0.6   # Adjust for more/less sensitivity
FRAME_LENGTH = 2048
HOP_LENGTH = 512

# === Load audio ===
y, sr = librosa.load(AUDIO_FILE, duration = 20)

# === Compute RMS energy ===
rms = librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0]
times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=HOP_LENGTH)

# === Normalize and threshold ===
norm_rms = rms / np.max(rms)
peak_indices = np.where(norm_rms > THRESHOLD_RATIO)[0]
peak_times = times[peak_indices]

# === Export to CSV ===
df = pd.DataFrame({
    "time": peak_times
})
df.to_csv("bwv1006_percussive_frames_to_time.csv", index=False)

print(f"Detected {len(peak_times)} peaks. Saved to bwv1006_percussive_frames_to_time.csv.")

# Optional: Plot for debug
plt.figure(figsize=(12, 4))
plt.plot(times, norm_rms, label="RMS Energy")
plt.plot(peak_times, norm_rms[peak_indices], "ro", label="Peaks")
plt.xlabel("Time (s)")
plt.ylabel("Normalized RMS")
plt.legend()
plt.title("Audio RMS Peak Detection")
plt.tight_layout()
plt.savefig("bwv1006_rms_plot.png")
plt.show()
