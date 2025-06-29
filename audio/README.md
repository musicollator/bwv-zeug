# Classical Music Audio Processing Pipeline

A Python toolkit for intelligent audio segmentation, beat detection, and click track generation, specifically designed for classical music analysis. This project automatically detects fermatas (musical pauses), segments audio accordingly, and generates synchronized click tracks with comprehensive visualization tools.

## 🎵 Features

- **Automated Fermata Detection**: Intelligently identifies fermatas using energy analysis and spectral stability
- **Smart Audio Segmentation**: Splits audio files at detected fermata points for natural musical phrases
- **Beat Detection & Click Tracks**: Uses advanced neural networks (madmom) for precise beat timing
- **Comprehensive Visualization**: Plots waveforms with beat overlays and timing analysis
- **Multi-format Support**: Works with both WAV and MP3 audio files
- **YAML Export**: Detailed beat timing data export for further analysis
- **Dual Environment Setup**: Optimized dependencies for different processing stages

## 🏗️ Architecture

The pipeline consists of three main stages:

```
Audio File → Fermata Detection → Audio Segments → Beat Detection → Click Tracks + Visualization
    ↓              ↓                  ↓               ↓              ↓
fermata_chopper.py  │            add_clicks.py      │       visualize_beats.py
(librosa env)       │            (madmom env)       │       (madmom env)
                    ↓                                ↓
              segments/*.wav                detected_beats.yaml
```

## 📁 Project Structure

```
├── fermata_chopper.py          # Main fermata detection and audio segmentation
├── add_clicks.py              # Beat detection and click track generation
├── add_clicks_utils.py        # Utility functions for click processing
├── visualize_beats.py         # Waveform and beat visualization
├── sanity.py                  # Quick madmom functionality test
├── requirements_librosa.txt   # Dependencies for fermata detection
├── requirements_madmom.txt    # Dependencies for beat detection
├── environment_librosa.yml    # Conda environment for librosa
├── fermata_chopper.md         # Detailed usage examples
└── README.md                  # This file
```

## 🚀 Installation

This project requires two separate Python environments due to conflicting dependencies between librosa and madmom.

### Environment 1: Fermata Detection (Librosa)

```bash
# Using conda (recommended)
conda env create -f environment_librosa.yml
conda activate base

# Or using pip
pip install -r requirements_librosa.txt
```

### Environment 2: Beat Detection (Madmom)

```bash
# Create virtual environment
python -m venv ~/.venvs/madmom
source ~/.venvs/madmom/bin/activate  # Linux/Mac
# or
~/.venvs/madmom/Scripts/activate     # Windows

# Install dependencies
pip install -r requirements_madmom.txt
```

## 🎯 Quick Start

### Step 1: Segment Audio by Fermatas

```bash
conda activate base
cd your_project_directory

python fermata_chopper.py \
  -i exports/your_audio.wav \
  --energy-percentile 10 \
  --stability-percentile 90 \
  --min-duration 0.1 \
  -o segments \
  --plot
```

### Step 2: Generate Click Tracks

```bash
conda deactivate
source ~/.venvs/madmom/bin/activate

python add_clicks.py segments/ --clean
```

### Step 3: Visualize Results

```bash
python visualize_beats.py \
  --audio-dir segments \
  --beats-yaml detected_beats.yaml
```

## 📖 Detailed Usage

### Fermata Detection Options

The `fermata_chopper.py` script offers two detection methods:

#### Simple Energy Method (Recommended)
```bash
# Detect low energy regions as fermata candidates
python fermata_chopper.py -i chorale.wav \
  --energy-percentile 10 \      # Regions below 10th percentile energy
  --stability-percentile 90 \   # Ignore harmony requirements  
  --min-duration 0.1 \          # Minimum 0.1s low energy duration
  -o segments \
  --preserve-sr                 # Maintain original sample rate
```

#### Energy Drop Method
```bash
# Detect significant energy drops (valleys)
python fermata_chopper.py -i chorale.wav \
  --drop-threshold 0.3 \        # 30% energy drop required
  --min-low-duration 0.5 \      # 0.5s minimum sustained low energy
  --min-gap 2.0 \              # 2s minimum between fermatas
  -o segments
```

### Click Track Configuration

Control click generation with YAML configuration (`click_limits.yaml`):

```yaml
# Limit clicks for specific segments
segment-1.wav: 8                    # Maximum 8 clicks
segment-2.wav:
  max_clicks: 12                   # Maximum 12 clicks  
  last_beat: 25.5                  # Force beat at 25.5 seconds
segment-3.wav: 0                    # No clicks (skip segment)
```

### Beat Detection Parameters

```bash
python add_clicks.py segments/ \
  --clean \                       # Remove existing click files
  --export-beats timing.yaml      # Custom export filename
```

### Visualization Options

```bash
python visualize_beats.py \
  --audio-dir segments \
  --beats-yaml detected_beats.yaml \
  --yaml-timing original_score.yaml \  # Overlay original timing
  --output analysis.png               # Save plot
```

## 🎼 Output Files

### Generated Segments
- `segments/original-1.wav` - First musical phrase
- `segments/original-2.wav` - Second musical phrase  
- `segments/original-N.wav` - Nth musical phrase

### Click Tracks
- `segments/original-1_with_clicks.wav` - Segment with click overlay
- `segments/original-2_with_clicks.wav` - etc.

### Analysis Data
- `detected_beats.yaml` - Complete beat timing data with metadata
- `analysis.png` - Waveform visualization with beat markers

## 🔧 Advanced Configuration

### Custom Beat Parameters

The beat detection uses RNN + DBN processing with these defaults:
- **fps**: 100 (frames per second for analysis)
- **min_bpm**: 40 (minimum tempo)
- **max_bpm**: 140 (maximum tempo)  
- **transition_lambda**: 15 (tempo change sensitivity)

### Energy Detection Tuning

For difficult audio, adjust sensitivity:
```bash
# Very sensitive detection
--energy-percentile 5 --stability-percentile 95

# Conservative detection  
--energy-percentile 20 --stability-percentile 70
```

## 🎵 Example Workflow: Bach BWV 245

```bash
# 1. Activate librosa environment and segment the chorale
conda activate base
cd bwv245
python ../fermata_chopper.py \
  -i exports/bwv245.wav \
  --energy-percentile 10 \
  --stability-percentile 90 \
  --min-duration 0.1 \
  -o segments \
  --plot

# 2. Switch to madmom environment and generate clicks  
conda deactivate
source ~/.venvs/madmom/bin/activate
python ../add_clicks.py segments/ --clean

# 3. Visualize the results
python ../visualize_beats.py \
  --audio-dir segments \
  --beats-yaml detected_beats.yaml

cd ..
deactivate
```

## 🛠️ Troubleshooting

### Common Issues

**"Chipmunk Effect" (accelerated playback)**
- Solution: Use `--preserve-sr` flag to maintain original sample rate

**No fermatas detected**
- Lower `--energy-percentile` (try 5-15)
- Increase `--stability-percentile` (try 80-95)
- Reduce `--min-duration` (try 0.05-0.2)

**madmom import errors**
- Ensure you're in the correct virtual environment
- Reinstall madmom: `pip install --force-reinstall madmom`

**Memory issues with large files**
- Process shorter segments
- Reduce analysis frame rate in beat detection

## 📊 Output Analysis

The `detected_beats.yaml` contains:
- **segments**: Individual segment beat data
- **concatenated**: Combined timeline with proper offsets  
- **meta**: Statistics and processing parameters

Example structure:
```yaml
meta:
  total_segments: 8
  total_duration: 180.5
  total_beats: 245
  
segments:
  segment-1.wav:
    beats: [0.0, 0.52, 1.04, 1.56]
    duration: 8.2
    num_beats: 15
    
concatenated:
  beats: [0.0, 0.52, 1.04, ..., 178.9, 179.4]
  total_duration: 180.5
```

## 🤝 Contributing

This project is designed for classical music analysis research. Contributions welcome for:
- Additional detection algorithms
- Support for other audio formats
- Improved visualization options
- Performance optimizations

## 📄 License

This project processes classical music using open-source audio analysis libraries. Please ensure appropriate licensing for any audio content you process.

---

*Optimized for Bach chorales and similar classical music with clear fermata patterns.*