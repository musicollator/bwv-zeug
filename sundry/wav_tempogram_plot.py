import librosa
import librosa.display
import matplotlib.pyplot as plt

# --- Load audio file ---
filename = "VID20250326172717.wav"  # Replace with your actual file path
y, sr = librosa.load(filename)

# --- Calculate onset strength envelope ---
onset_env = librosa.onset.onset_strength(y=y, sr=sr)

# --- Compute the tempogram ---
tempo_gram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)

# --- Plotting ---
plt.figure(figsize=(10, 6))

# 1. Plot the onset strength
plt.subplot(2, 1, 1)
librosa.display.waveshow(y, sr=sr, alpha=0.4)
plt.title("Waveform")

plt.subplot(2, 1, 2)
librosa.display.specshow(tempo_gram, sr=sr, hop_length=512, x_axis='time', y_axis='tempo')
plt.title("Tempogram")
plt.colorbar(label='Autocorrelation')
plt.tight_layout()
plt.show()
