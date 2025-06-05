# BWV-Zeug

Bach Works processing toolkit - the complete gear for processing BWV scores.

A comprehensive pipeline for creating animated score-following from Bach compositions, combining LilyPond notation software with Python processing scripts to generate synchronized audio-visual presentations.

## What it does

BWV-Zeug transforms LilyPond-generated musical scores into data suitable for animated score following applications. The toolkit handles the complete workflow from musical notation to synchronized multimedia:

- **Extracts notehead positions** from LilyPond-generated SVG files with precise coordinate mapping
- **Processes MIDI timing data** to create temporal event sequences  
- **Aligns visual and temporal elements** using tolerance-based chord detection
- **Handles musical complexities** like tied notes, multi-voice scores, and chord groupings
- **Generates structured datasets** (JSON/CSV) for use in score-following applications

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

The complete "usine à gaz" consists of several interconnected processing stages:

### 1. Score Generation (`lilypond/`)
- LilyPond templates and includes for consistent Bach score rendering
- Generates SVG files with embedded cross-references to source notation
- Produces MIDI files with precise timing information

### 2. Visual Processing (`python/extract_note_heads.py`)
- Parses LilyPond-generated SVG to locate clickable notehead elements
- Extracts pitch information by following href links back to source `.ly` files
- Groups simultaneous notes (chords) using configurable x-coordinate tolerance
- Sorts noteheads by visual appearance (left-to-right, top-to-bottom)
- Outputs CSV with format: `snippet,href,x,y`

### 3. Temporal Processing (`python/extract_note_events.py`)
- Processes MIDI files to extract note events with precise timing
- Handles multi-channel/multi-voice compositions
- Converts timing to tick-based format for accuracy
- Outputs CSV with format: `pitch,midi,channel,on_tick,off_tick`

### 4. Tie Resolution (`python/squash-tied-note-heads.py`)
- Identifies tied note groups in the SVG data
- Removes secondary noteheads from tied sequences
- Embeds tie group information in primary noteheads
- Preserves visual-temporal relationships for tied notes

### 5. Data Alignment (`python/align_data.py`)
- Synchronizes MIDI timing data with SVG notehead positions
- Performs pitch verification to ensure proper alignment
- Handles tolerance-based ordering from previous pipeline stages
- Generates final JSON dataset with complete notehead-to-timing mapping

### 6. Configuration & Utilities
- **Project-specific tolerance settings** via YAML configuration files
- **Build orchestration** through Python Invoke tasks
- **LilyPond notation utilities** for pitch conversion and CSV handling
- **Quality assurance** with alignment verification and mismatch detection

## Configuration

Each BWV project can be fine-tuned with a YAML configuration file:

```yaml
# bwv543.yaml
tolerance: 2.5        # X-coordinate tolerance for chord grouping
```

The pipeline automatically detects and uses project-specific settings, falling back to sensible defaults when no configuration is provided.

## Output

The final output is a structured JSON dataset where each musical event contains:

```json
{
  "hrefs": ["primary_notehead.svg#ref", "tied_secondary.svg#ref"],
  "on_tick": 480,
  "off_tick": 960, 
  "pitch": 60,
  "channel": 1
}
```

This format enables score-following applications to highlight the appropriate visual noteheads in perfect synchronization with audio playback.

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