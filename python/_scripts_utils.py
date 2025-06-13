#!/usr/bin/env python3
"""
_scripts_utils.py - Project context utilities for BWV scripts

This module provides utilities for BWV musical score processing scripts,
handling file naming conventions, argument parsing patterns, and musical notation conversion.
"""

import os
import sys
import argparse
import csv
import pandas as pd
import subprocess
import yaml
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=None)
def get_project_name():
    """Detect project name from git repository root directory, fallback to current directory."""
    project_name = None
    
    # Try git first
    try:
        result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], 
                              capture_output=True, text=True, check=True)
        git_project_name = Path(result.stdout.strip()).name
        
        # Check if the main .ly file exists with git name
        main_ly_file = f"{git_project_name}.ly"
        if Path(main_ly_file).exists():
            print(f"🎼 Detected project from git: {git_project_name}")
            return git_project_name
        else:
            print(f"⚠️  Git repo name '{git_project_name}' doesn't match .ly file, trying directory name...")
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ℹ️  Not in a git repository, trying directory name...")
    
    # Fallback to current directory name
    project_name = Path.cwd().name
    main_ly_file = f"{project_name}.ly"
    
    if Path(main_ly_file).exists():
        print(f"🎼 Detected project from current directory: {project_name}")
        return project_name
    
    # If we get here, neither git name nor directory name worked
    raise RuntimeError(
        f"Main LilyPond file not found. Tried:\n"
        f"  - {Path.cwd().name}.ly (current directory)\n"
        f"Make sure you're in a directory containing a .ly file matching the directory name."
    )

@lru_cache(maxsize=None)
def get_project_config(project_name):
    """Load and cache project configuration from exports subdirectory"""
    project_name = get_project_name()
    config_file = Path("exports") / f"{project_name}.config.yaml"
    
    if config_file.exists():
        with open(config_file) as f:
            return yaml.safe_load(f)
    return {}

def get_io_files(description, input_pattern, output_pattern):
    """
    Simple 1 input → 1 output file resolver.
    
    Args:
        description: Script description for help text
        input_pattern: Input file pattern with {project} placeholder
        output_pattern: Output file pattern with {project} placeholder
    
    Returns:
        tuple: (input_file, output_file) as strings
    """
    project_name = get_project_name()
    
    if project_name:
        # Build system mode - use project conventions
        return (
            input_pattern.format(project=project_name),
            output_pattern.format(project=project_name)
        )
    else:
        # Standalone mode - require explicit arguments
        if len(sys.argv) != 3:
            print(f"Usage: python {sys.argv[0]} <input> <output>")
            print(f"Description: {description}")
            print("Or run from build system with PROJECT_NAME environment variable")
            sys.exit(1)
        return sys.argv[1], sys.argv[2]

def setup_project_context(script_purpose, input_pattern=None, output_pattern=None, extra_args=None):
    """
    Setup project context and argument parsing for BWV scripts.
    
    Relies on PROJECT_NAME environment variable set by build system.
    If not set, requires explicit file arguments.
    
    Args:
        script_purpose: Description for help text
        input_pattern: Format string for input file (e.g., "{project}_input.svg") or None
        output_pattern: Format string for output file (e.g., "{project}_output.svg") or None
        extra_args: List of additional argument definitions [(name, kwargs), ...]
    
    Returns:
        argparse.Namespace: Parsed arguments with input/output paths
    """
    project_name = get_project_name()
    
    parser = argparse.ArgumentParser(description=script_purpose)
    
    # Handle input file argument
    if input_pattern:
        if project_name:
            input_default = input_pattern.format(project=project_name)
            input_required = False
        else:
            input_default = None
            input_required = True
        
        parser.add_argument('--input', default=input_default, required=input_required,
                           help='Input file path')
    
    # Handle output file argument  
    if output_pattern:
        if project_name:
            output_default = output_pattern.format(project=project_name)
            output_required = False
        else:
            output_default = None
            output_required = True
            
        parser.add_argument('--output', default=output_default, required=output_required,
                           help='Output file path')
    
    # Handle positional arguments (for scripts that take them directly)
    if not input_pattern and not output_pattern:
        parser.add_argument('input_file', nargs='?', help='Input file')
        parser.add_argument('output_file', nargs='?', help='Output file')
    
    # Add any extra arguments
    if extra_args:
        for arg_name, arg_kwargs in extra_args:
            parser.add_argument(arg_name, **arg_kwargs)
    
    args = parser.parse_args()
    
    # For positional args, validate we have what we need
    if not input_pattern and not output_pattern:
        if not project_name and (not args.input_file or not args.output_file):
            parser.error("When PROJECT_NAME is not set, both input_file and output_file are required")
        elif project_name and not args.input_file:
            # Use project context to generate default positional args
            setattr(args, 'input_file', input_pattern.format(project=project_name) if input_pattern else None)
            setattr(args, 'output_file', output_pattern.format(project=project_name) if output_pattern else None)
    
    return args

# =============================================================================
# LILYPOND HREF CLEANING UTILITIES
# =============================================================================

def clean_lilypond_href(href):
    """
    Clean and simplify LilyPond href references to a consistent format.
    
    This function consolidates all href cleaning operations used throughout
    the pipeline to ensure consistency. It handles both textedit prefix
    removal and column format simplification.
    
    Process:
    1. Remove textedit protocol prefix: "textedit://" -> ""
    2. Remove workspace path: "/work/" -> ""  
    3. Simplify column format: "file.ly:line:start:end" -> "file.ly:line:end"
    
    Args:
        href (str): Original LilyPond href reference
        
    Returns:
        str: Cleaned and simplified href reference
        
    Examples:
        "textedit:///work/test.ly:37:20:21" -> "test.ly:37:21"
        "test.ly:37:20:21" -> "test.ly:37:21"
        "file.ly:10:5" -> "file.ly:10:5" (no change needed)
    """
    if not href:
        return href
        
    # Step 1: Remove textedit protocol and workspace path
    cleaned = href.replace("textedit://", "").replace("/work/", "")
    
    # Step 2: Simplify column format (4 parts -> 3 parts)
    parts = cleaned.split(':')
    if len(parts) == 4:
        # Convert "file.ly:line:start_col:end_col" -> "file.ly:line:end_col"
        return f"{parts[0]}:{parts[1]}:{parts[3]}"
    
    # Return as-is if not 4-part format
    return cleaned

# =============================================================================
# MUSICAL NOTATION CONVERSION UTILITIES
# =============================================================================

def midi_pitch_to_lilypond(midi_pitch):
    """
    Convert MIDI pitch number to LilyPond note notation.
    
    LilyPond Notation System:
    ========================
    - Base notes: c, d, e, f, g, a, b (letter names)
    - Sharps: add 'is' (cis = C#, fis = F#)
    - Octaves up: add apostrophes (c' = C5, c'' = C6)
    - Octaves down: add commas (c, = C3, c,, = C2)
    
    This function uses sharps rather than flats for simplicity and consistency.
    The octave system follows LilyPond's standard where middle C (MIDI 60) = 'c'.
    
    Args:
        midi_pitch (int): MIDI pitch number (0-127)
        
    Returns:
        str: LilyPond notation (e.g., "cis'", "c,", "bes")
        
    Examples:
        60 -> "c" (C4/middle C in MIDI)
        61 -> "cis" (C#4)  
        48 -> "c," (C3)
        72 -> "c'" (C5)
    """
    if midi_pitch < 0 or midi_pitch > 127:
        return f"invalid_pitch_{midi_pitch}"
    
    # Base note names with sharps preferred over flats
    pitch_class_to_note = {
        0: 'c',    # C
        1: 'cis',  # C# (prefer over des)
        2: 'd',    # D
        3: 'dis',  # D# (prefer over ees)
        4: 'e',    # E
        5: 'f',    # F
        6: 'fis',  # F# (prefer over ges)
        7: 'g',    # G
        8: 'gis',  # G# (prefer over aes)
        9: 'a',    # A
        10: 'ais', # A# (prefer over bes)
        11: 'b'    # B
    }
    
    # Calculate pitch class (0-11) and octave
    pitch_class = midi_pitch % 12
    octave = midi_pitch // 12
    
    # Get base note name
    base_note = pitch_class_to_note[pitch_class]
    
    # LilyPond's reference octave is 4 (where C4 = MIDI 60 = "c")
    # This aligns with LilyPond's default middle octave
    reference_octave = 4
    octave_difference = octave - reference_octave
    
    # Add octave modifiers
    if octave_difference > 0:
        # Higher octaves: add apostrophes
        octave_suffix = "'" * octave_difference
    elif octave_difference < 0:
        # Lower octaves: add commas
        octave_suffix = "," * abs(octave_difference)
    else:
        # Reference octave: no modifier
        octave_suffix = ""
    
    return base_note + octave_suffix

def lilypond_to_midi_pitch(note_str):
    """
    Convert LilyPond note notation to MIDI pitch value.
    
    LilyPond Notation System:
    ========================
    - Base notes: c, d, e, f, g, a, b (letter names)
    - Sharps: add 'is' (cis = C#, fis = F#)
    - Flats: add 'es' or 's' (bes = Bb, as = Ab) 
    - Double sharps: add 'isis' (cisis = C##)
    - Double flats: add 'eses' (ceses = Cbb)
    - Octaves up: add apostrophes (c' = C4, c'' = C5)
    - Octaves down: add commas (c, = C2, c,, = C1)
    
    Args:
        note_str (str): LilyPond notation (e.g., "cis'", "bes,,", "f")
        
    Returns:
        int: MIDI pitch number (0-127), or -1 if parsing failed
        
    Examples:
        "c" -> 60 (C4/middle C in MIDI)
        "cis'" -> 73 (C#5)  
        "c," -> 48 (C3)
    """
    # Base MIDI values for middle octave (C4=60 to B4=71)
    # This octave choice aligns with LilyPond's default octave
    base_notes = {
        # Natural notes
        'c': 60, 'd': 62, 'e': 64, 'f': 65, 'g': 67, 'a': 69, 'b': 71,
        
        # Single accidentals (sharps)
        'cis': 61, 'dis': 63, 'fis': 66, 'gis': 68, 'ais': 70,
        
        # Single accidentals (flats) - multiple spellings supported
        'des': 61, 'es': 63, 'ees': 63, 'ges': 66, 'aes': 68, 'as': 68, 'bes': 70,
        
        # Enharmonic edge cases (rare but valid)
        'eis': 65,  # E# = F
        'bis': 72,  # B# = C (next octave)
        'ces': 59,  # Cb = B (previous octave) 
        'fes': 64,  # Fb = E
        
        # Double accidentals (very rare in practice)
        'cisis': 62, 'disis': 64, 'eisis': 66, 'fisis': 67, 'gisis': 69,
        'aisis': 71, 'bisis': 73,
        'ceses': 58, 'deses': 60, 'eses': 62, 'feses': 63, 'geses': 65, 
        'aeses': 67, 'beses': 69
    }
    
    # Generate octave variations - lower octaves (commas)
    # Each comma drops the pitch by one octave (12 semitones)
    base_notes_copy = dict(base_notes)  # Avoid modifying during iteration
    for comma_count in range(1, 4):  # Support up to 3 octaves down
        for base_note, base_pitch in base_notes_copy.items():
            octave_note = base_note + (',' * comma_count)
            octave_pitch = base_pitch - (comma_count * 12)
            if octave_pitch >= 0:  # Stay within MIDI range
                base_notes[octave_note] = octave_pitch
    
    # Generate octave variations - higher octaves (apostrophes)  
    # Each apostrophe raises the pitch by one octave (12 semitones)
    for apostrophe_count in range(1, 8):  # Support up to 7 octaves up
        for base_note, base_pitch in base_notes_copy.items():
            octave_note = base_note + ("'" * apostrophe_count)
            octave_pitch = base_pitch + (apostrophe_count * 12)
            if octave_pitch <= 127:  # Stay within MIDI range
                base_notes[octave_note] = octave_pitch
    
    # Look up the note, returning -1 if not found
    cleaned_note = note_str.strip()
    return base_notes.get(cleaned_note, -1)

def save_dataframe_with_lilypond_csv(dataframe, output_path, **kwargs):
    """
    Save a pandas DataFrame to CSV with proper quoting for LilyPond notation.
    
    This function ensures that LilyPond notation containing commas (like "c,", "c,,")
    is properly quoted in the CSV file to avoid parsing issues.
    
    Args:
        dataframe (pd.DataFrame): DataFrame to save
        output_path (str): Output CSV file path
        **kwargs: Additional arguments to pass to DataFrame.to_csv()
    """
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    
    # Use QUOTE_NONNUMERIC to properly handle LilyPond notation with commas
    # This ensures values like "c," are quoted as "c," in the CSV
    default_kwargs = {
        'index': False,
        'quoting': csv.QUOTE_NONNUMERIC
    }
    default_kwargs.update(kwargs)
    
    dataframe.to_csv(output_path, **default_kwargs)