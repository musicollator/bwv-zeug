# Musical Score Processing Workflow

This document describes the complete processing pipeline that transforms LilyPond musical scores into synchronized audio-visual playback data.

## Overview

The workflow processes LilyPond source files through multiple stages to generate:
- **PDF scores** for printing and viewing
- **Optimized SVG scores** for web animation with interactive noteheads
- **Synchronized timing data** connecting MIDI playback with visual notation

## Input Files

| File | Purpose |
|------|---------|
| `BWV000.ly` | Main musical score source |
| `BWV000_ly_one_line.ly` | Single-line version for data extraction |
| `BWV000_ly_main.ly` | Shared musical dependencies and definitions |
| `exports/BWV000.config.yaml` | Project configuration (timing, structure) |

## Processing Stages

### 1. LilyPond Compilation
**Docker-based LilyPond rendering**
- **PDF Generation**: Compile main score to PDF for printing/viewing
- **SVG Generation**: Compile main score to SVG with embedded cross-references
- **One-line Compilation**: Generate simplified SVG + MIDI for data extraction

### 2. Main SVG Processing Chain
**Transform main SVG for web animation**
- **Link Cleanup**: [`remove_unwanted_hrefs.py`](../python/remove_unwanted_hrefs.py) - Remove unwanted href attributes (tablature, grace notes, annotations)
- **Animation Preparation**: [`ensure_swellable.py`](../python/ensure_swellable.py) - Restructure DOM for CSS transform animations on noteheads  
- **Optimization**: [`optimize.py`](../python/optimize.py) - Apply SVGO to reduce file size and clean markup

### 3. Data Extraction
**Extract timing and visual data from one-line versions**
- **Notehead Extraction**: [`extract_note_heads.py`](../python/extract_note_heads.py) - Parse SVG to extract notehead positions and pitches
- **Tie Extraction**: [`extract_ties.py`](../python/extract_ties.py) - Identify tied note relationships from SVG grob attributes
- **MIDI Event Extraction**: [`extract_note_events.py`](../python/extract_note_events.py) - Parse MIDI file for precise timing data with note stacking algorithm

### 4. Data Processing and Alignment
**Process extracted data for synchronization**
- **Tie Squashing**: [`squash-tied-note-heads.py`](../python/squash-tied-note-heads.py) - Merge tied noteheads into primary notes with embedded secondary references
- **MIDI-SVG Alignment**: [`align_data.py`](../python/align_data.py) - Synchronize MIDI timing events with visual notehead positions

### 5. Final Sync Generation
**Create unified synchronization data**
- **Sync File Generation**: [`generate_sync.py`](../python/generate_sync.py) - Combine optimized SVG, aligned timing data, and configuration into:
  - Clean SVG with `data-ref` attributes for JavaScript targeting
  - YAML timing data with unified note/bar timeline for real-time playback

## Final Outputs

| File | Description |
|------|-------------|
| `exports/BWV000.pdf` | Print-ready musical score |
| `exports/BWV000.svg` | Animation-ready SVG with note references |
| `exports/BWV000.yaml` | Synchronized timing data for audio-visual playback |

## Workflow Characteristics

- **Parallel Processing**: Data extraction tasks run independently for efficiency
- **Dependency Management**: Shared LilyPond files properly cascade to dependent scores
- **Format Optimization**: Each output optimized for its specific use case (print, web, data)
- **Error Isolation**: Independent processing stages prevent cascading failures
- **Docker Integration**: LilyPond compilation containerized for consistent rendering across environments

The pipeline enables interactive musical score applications where noteheads highlight in real-time during MIDI playback, with frame-accurate synchronization between audio and visual elements.