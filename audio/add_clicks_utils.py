# utils.py

from pathlib import Path
import soundfile as sf
import numpy as np
import yaml
import os


def segment_key_from_path(path):
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
    """Delete all *_with_clicks.wav files in the directory."""
    print("🧹 Cleaning up *_with_clicks.wav files...")
    for path in Path(directory).glob("*_with_clicks.wav"):
        print(f"   🗑️ Removed: {path.name}")
        os.remove(path)
