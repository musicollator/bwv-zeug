import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

# Load first 60 seconds of audio
y, sr = librosa.load("VID20250326172717.wav")

# Apply Harmonic–Percussive Source Separation
y_harmonic, y_percussive = librosa.effects.hpss(y, margin=16)

# Save WAV files
sf.write("VID20250326172717_harmonic.wav", y_harmonic, sr)
sf.write("VID20250326172717_percussive.wav", y_percussive, sr)

# Plot waveforms
plt.figure(figsize=(12, 8))

plt.subplot(3, 1, 1)
librosa.display.waveshow(y, sr=sr, alpha=0.6)
plt.title('Original Audio')

plt.subplot(3, 1, 2)
librosa.display.waveshow(y_harmonic, sr=sr, color='b', alpha=0.6)
plt.title('Harmonic Component')

plt.subplot(3, 1, 3)
librosa.display.waveshow(y_percussive, sr=sr, color='r', alpha=0.6)
plt.title('Percussive Component')

plt.tight_layout()
plt.show()
