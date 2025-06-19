# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BWV-Zeug is a Bach Works processing toolkit that creates animated score-following from Bach compositions. It combines LilyPond notation software with Python processing scripts to generate synchronized audio-visual presentations.

The system transforms LilyPond-generated musical scores into data suitable for animated score following applications, where every visual notehead is mapped to its corresponding MIDI timing and pitch data.

## Build System

### Task Generation and Execution

The project uses a custom build system based on Python Invoke with auto-generated tasks from Mermaid diagrams:

```bash
# Generate ANTLR parsers (after grammar changes)
cd invoke/antlr
source build_antlr.sh

# Generate tasks from Mermaid diagram
cd invoke
python tasks_mermaid_generator.py -i TASKS.mmd -o tasks_generated.py

# Set up build alias (recommended)
alias b='invoke --search-root /Users/christophe.thiebaud/github.com/musicollator/bwv-zeug/invoke'

# Run tasks from a BWV project directory (e.g., bwv245/, bwv543/)
b pdf        # Generate PDF
b svg        # Generate SVG 
b sync       # Generate complete synchronized data
```

### Key Build Commands

- `b pdf` - Generate print-ready PDF score
- `b svg` - Generate web-ready SVG with interactive elements
- `b sync` - Complete pipeline: generates PDF, SVG, and synchronized YAML data
- `b noteheads` - Extract notehead positions from SVG
- `b events` - Extract MIDI timing events
- `b align` - Synchronize MIDI and SVG data

## Architecture

### Directory Structure

- **`lilypond/`** - Shared LilyPond includes, templates, and notation definitions
  - `includes/` - Reusable LilyPond components (.ily files)
  - `test/` - Test scores and examples
- **`invoke/`** - Build system orchestration using Python Invoke
  - `TASKS.mmd` - Mermaid diagram defining build pipeline
  - `tasks.py` - Main task file (imports generated tasks)
  - `antlr/` - ANTLR grammar for parsing Mermaid diagrams
- **`python/`** - Core processing pipeline scripts
- **`audio/`** - Audio processing tools using librosa/madmom
- **`scripts/`** - Build automation scripts
- **`sundry/`** - Utility scripts for various processing tasks

### LilyPond Score Architecture

Each musical piece requires **three coordinated files** for the interactive system:

1. **`BWV000_ly_main.ly`** - Pure musical content (no layout/formatting)
2. **`BWV000.ly`** - Display wrapper with interactive highlighting
3. **`BWV000_ly_one_line.ly`** - Single-line version for data extraction

**Critical**: All three files must contain identical musical content for synchronization.

### Processing Pipeline

The complete workflow transforms LilyPond scores through these stages:

1. **LilyPond Compilation** - PDF, SVG, and MIDI generation via Docker
2. **SVG Processing** - Link cleanup, animation preparation, optimization
3. **Data Extraction** - Noteheads, ties, and MIDI events
4. **Data Alignment** - Synchronize MIDI timing with visual positions
5. **Sync Generation** - Create unified YAML timing data

## Dependencies

### Core Requirements
- **LilyPond** (via Docker for consistent rendering)
- **Python 3.12+** with pandas, PyYAML, xml processing
- **Python Invoke** for build orchestration
- **ANTLR4** for Mermaid diagram parsing

### Audio Processing (Optional)
- **Conda environment** with librosa for audio segmentation
- **Virtual environment** with madmom for beat detection

### Python Packages
Key packages include: invoke, antlr4-python3-runtime, pandas, pyyaml, lxml

## Development Workflow

### Working with BWV Projects

1. Navigate to a BWV project directory (e.g., `audio/bwv245/`)
2. Ensure configuration file exists (`exports/BWV000.config.yaml`)
3. Run build commands using the `b` alias
4. Check `exports/` directory for generated outputs

### Testing Changes

- Use `lilypond/test/` for testing LilyPond includes and templates
- The test project demonstrates the complete three-file architecture
- Generated outputs appear in `test/exports/`

### File Generation Patterns

**Never commit these generated files:**
- `invoke/tasks_generated.py`
- `invoke/antlr/` compiled parsers
- `*/exports/` directories
- `.build_cache.json`

**Always commit:**
- Source `.ly` files
- Configuration `.yaml` files  
- `TASKS.mmd` pipeline definitions
- Python processing scripts

## Configuration

Each BWV project can be fine-tuned with YAML configuration:

```yaml
# exports/bwv000.config.yaml
tolerance: 2.5        # X-coordinate tolerance for chord grouping
noDuplicates: false   # Preserve multiple noteheads at identical positions
```

The pipeline automatically detects project-specific settings and falls back to sensible defaults.

## Output Format

Final outputs are optimized for web-based score animation:

- **`exports/BWV000.svg`** - Clean SVG with `data-ref` attributes for JavaScript targeting
- **`exports/BWV000.yaml`** - Unified synchronization data with tick-based timing
- **`exports/BWV000.pdf`** - Print-ready score

The YAML format enables real-time score animation where JavaScript can highlight noteheads and synchronize audio playback with the unified flow timeline.