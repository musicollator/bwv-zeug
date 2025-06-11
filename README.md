# BWV-Zeug

Bach Works processing toolkit - the complete gear for processing BWV scores.

A comprehensive pipeline for creating animated score-following from Bach compositions, combining LilyPond notation software with Python processing scripts to generate synchronized audio-visual presentations.

## What it does

BWV-Zeug transforms LilyPond-generated musical scores into data suitable for animated score following applications. The toolkit handles the complete workflow from musical notation to synchronized multimedia:

- **Extracts notehead positions** from LilyPond-generated SVG files with precise coordinate mapping
- **Processes MIDI timing data** to create temporal event sequences  
- **Aligns visual and temporal elements** using tolerance-based chord detection
- **Handles musical complexities** like tied notes, multi-voice scores, and chord groupings
- **Generates structured datasets** (YAML) for use in score-following applications

The result is a synchronized dataset where every visual notehead in the score is mapped to its corresponding MIDI timing and pitch data, enabling real-time animated score following.

## Structure

- **`lilypond/`** - Shared LilyPond includes, templates, and notation definitions for consistent score generation
- **`invoke/`** - Build system orchestration using Python Invoke (tasks.py, project utilities, configuration management)  
- **`python/`** - Core processing pipeline scripts (*see The Pipeline section for the full complexity*)

## Quick Start

The build system orchestrates the complete pipeline through Python Invoke tasks.

**For current build commands and usage, see [`tasks.mmd`](invoke/tasks.mmd)** - the authoritative source for all available operations.

Each BWV project can have its own configuration file (e.g., `bwv543.yaml`) to tune parameters like chord tolerance for optimal results.

## The Pipeline

**For complete workflow documentation, see [`invoke/TASKS.README.md`](invoke/TASKS.README.md)**

The processing pipeline transforms LilyPond scores through multiple stages:
- LilyPond compilation (PDF, SVG, MIDI generation)
- SVG optimization for web animation
- Data extraction (noteheads, ties, MIDI events)
- MIDI-SVG alignment and synchronization
- Final sync data generation

## Configuration

Each BWV project can be fine-tuned with a YAML configuration file:

```yaml
# bwv543.yaml
tolerance: 2.5        # X-coordinate tolerance for chord grouping
noDuplicates: false   # Preserve multiple noteheads at identical positions (default: true merges duplicates)
```

The pipeline automatically detects and uses project-specific settings, falling back to sensible defaults when no configuration is provided.

## Output

The final pipeline outputs are optimized for web-based score animation:

**`exports/BWV000.svg`** - Clean SVG with interactive noteheads:
```xml
<path data-ref="file.ly:12:34" d="..." />
```

**`exports/BWV000.yaml`** - Unified synchronization data:
```yaml
meta:
  totalMeasures: 32
  tickToSecondRatio: 0.00125
  channels:
    0: {minPitch: 48, maxPitch: 84, count: 245}

flow:
- [0, null, 1, bar]           # Bar 1 at tick 0
- [120, 0, 480, ["file.ly:5:8"]]  # Note: start_tick, channel, end_tick, hrefs
- [480, 0, 960, ["file.ly:6:12", "file.ly:6:20"]]  # Tied note with secondary refs
```

This format enables real-time score animation where JavaScript can:
- Target noteheads via `data-ref` attributes for highlighting
- Synchronize audio playback with the unified flow timeline
- Handle tied notes and measure boundaries seamlessly

## Technical Notes

The pipeline handles numerous musical and technical complexities:

- **Tolerance-based chord detection** to group simultaneous notes with slight visual offsets
- **Multi-voice score processing** with proper channel separation
- **Tied note consolidation** while preserving all visual references
- **Coordinate system transformations** from LilyPond's internal positioning
- **Cross-reference resolution** between SVG elements and LilyPond source files
- **MIDI timing precision** using tick-based rather than time-based calculations

## Dependencies

- **LilyPond** (music notation software)
- **Python 3.x** with pandas, PyYAML, xml processing
- **Python Invoke** for build orchestration

---

**tl;dr**: Converts LilyPond Bach scores into datasets for animated score-following applications.
