conda activate unified-env    
python ../bwv-zeug/audio/fermata_chopper.py \
  -i exports/bwv245.wav \
  --energy-percentile 10 \
  --stability-percentile 90 \
  --min-duration 0.1 \
  -o segments \
  --plot

  
## Option 2: Simple Energy Method (what you wanted)
```bash
# Find regions below 10th percentile energy, clean output directory first
python fermata_chopper.py -i chorale.wav \
  --energy-percentile 10 \
  --stability-percentile 90 \
  --min-duration 0.1 \
  -o segments \
  --plot

# Preserve original sample rate (avoid chipmunk effect)
python fermata_chopper.py -i chorale.wav \
  --energy-percentile 10 \
  --stability-percentile 90 \
  --min-duration 0.1 \
  -o segments \
  --preserve-sr
```

## More examples for the simple energy method:
```bash
# Very low energy threshold (should catch all valleys)
python fermata_chopper.py -i chorale.wav \
  --energy-percentile 5 \
  --stability-percentile 95 \
  --min-duration 0.05 \
  --min-gap 1.0 \
  -o segments \
  --preserve-sr

# Don't clean output directory (keep existing files)
python fermata_chopper.py -i chorale.wav \
  --energy-percentile 15 \
  --stability-percentile 80 \
  --min-duration 0.2 \
  -o segments \
  --no-clean \
  --preserve-sr
```

## Key Parameters for Simple Energy Method:

**For detection sensitivity:**
- `--energy-percentile`: Lower = detects higher energy as "low" (try 5-20 to catch obvious valleys)
- `--stability-percentile`: Higher = ignores harmony requirements (try 80-95 to focus only on energy)
- `--min-duration`: Minimum time for a low energy region (try 0.05-0.5 seconds)

**For output management:**
- `-o segments`: Save to specific directory (automatically cleaned before saving)
- `--no-clean`: Keep existing files in output directory (don't clean first)
- `--preserve-sr`: Load and save at original sample rate (prevents chipmunk/accelerated playback)

**The script automatically chooses:**
- **Simple Energy Method** when you specify `--energy-percentile` 
- **Energy Drop Method** when you specify `--drop-threshold`

**IMPORTANT:** Use `--preserve-sr` to avoid the "chipmunk effect" - by default librosa resamples to 22050 Hz which can cause accelerated playback if your original file was at a different sample rate.

The script will automatically clean the output directory before saving new segments to avoid leftover files from previous runs. Use `--no-clean` if you want to preserve existing files.

Try the first example - it should catch those obvious energy valleys and create clean segments at the correct playback speed!#!/usr/bin/env python3
