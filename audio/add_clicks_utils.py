# add_clicks_utils.py - Updated with MP3 support

from pathlib import Path
import soundfile as sf
import numpy as np
import yaml
import os


def segment_key_from_path(path):
    """Get segment key from file path (works with any audio format)."""
    return Path(path).name


def default_click_sample(sample_rate=44100, duration=0.02, frequency=1000):
    """Generate a short click sound."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    click = 0.5 * np.sin(2 * np.pi * frequency * t)
    return click


def load_click_limits(yaml_path="click_limits.yaml"):
    """Load click limits and overrides from a YAML file, fallback to empty."""
    if Path(yaml_path).exists():
        with open(yaml_path) as f:
            raw = yaml.safe_load(f) or {}
    else:
        return {}

    parsed = {}
    for k, v in raw.items():
        if isinstance(v, int):
            parsed[k] = {"max_clicks": v}
        elif isinstance(v, dict):
            parsed[k] = {
                "max_clicks": v.get("max_clicks", float("inf")),
                "last_beat": v.get("last_beat", None),
            }
    return parsed


def clean_click_outputs(directory):
    """Delete all *_with_clicks.wav files in the directory (from both .wav and .mp3 processing)."""
    print("🧹 Cleaning up *_with_clicks.wav files...")
    
    click_files = list(Path(directory).glob("*_with_clicks.wav"))
    
    if not click_files:
        print("   📂 No *_with_clicks.wav files found to clean")
        return
    
    for path in click_files:
        print(f"   🗑️ Removed: {path.name}")
        os.remove(path)
    
    print(f"   ✅ Cleaned {len(click_files)} files")