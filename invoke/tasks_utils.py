#!/usr/bin/env python3
"""
BWV Processing Tasks - Generic build system for Bach scores

Usage from any BWV project:
  invoke -f <abolute path to>/tasks.py build_pdf
"""

import builtins
import hashlib
import inspect
import json
import os
import re
import sys
import subprocess
from collections import defaultdict
from datetime import datetime
from invoke import task
from pathlib import Path

# =============================================================================
# git project detection
# =============================================================================


def detect_project_name():
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


def get_shared_ly_sources_tree(project_name=None):
    """Auto-detect LilyPond dependencies and return as tree structure."""
    if project_name is None:
        project_name = detect_project_name()
    
    main_file = Path(f"{project_name}.ly")
    
    if not main_file.exists():
        return {}
    
    # Build dependency tree
    tree = defaultdict(list)
    processed = set()
    
    def process_file(file_path, parent=None):
        """Recursively process a file and its includes."""
        if file_path in processed:
            return
        processed.add(file_path)
        
        try:
            content = file_path.read_text(encoding='utf-8')
            includes = re.findall(r'\\include\s+"([^"]+)"', content)
            
            for include_file in includes:
                include_path = Path(include_file)
                
                # Handle relative paths
                if not include_path.is_absolute():
                    include_path = file_path.parent / include_path
                
                if include_path.exists():
                    # Add to tree structure
                    tree[file_path].append(include_path)
                    
                    # Recursively process included files
                    if include_path.suffix in ['.ly', '.ily']:
                        process_file(include_path, file_path)
                        
        except Exception as e:
            print(f"⚠️  Warning: Could not parse {file_path}: {e}")
    
    process_file(main_file)
    return dict(tree)

def flatten_tree(tree_dict):
    """
    Flatten a dependency tree into a list of unique Path objects.
    
    Args:
        tree_dict: Dictionary representing tree structure {parent: [children]}
        
    Returns:
        list: All unique Path objects from the tree
    """
    all_paths = set()
    
    # Add all parent files
    all_paths.update(tree_dict.keys())
    
    # Add all child files
    for children in tree_dict.values():
        all_paths.update(children)
    
    return list(all_paths)    


# ==============================================================================
# ENHANCED PRINT FUNCTION WITH CONDITIONAL TIMESTAMPING
# ==============================================================================
# This monkey-patch globally replaces Python's built-in print() function to:
# 1. Always flush output immediately (fixes log ordering issues)
# 2. Add timestamps only when output is redirected to files (preserves clean console output)

# Store reference to original print function before we replace it
_original_print = builtins.print

def smart_print(*args, **kwargs):
    """
    Enhanced print function that conditionally adds timestamps and always flushes.
    
    Behavior:
    - Interactive use: Clean output without timestamps
    - Redirected to file: Timestamped output for debugging
    - Always flushes immediately to prevent output ordering issues
    """
    # Only add timestamps when redirected to a file
    if not os.isatty(1):  # stdout is not a terminal (redirected to file/pipe)
        # Generate timestamp in HH:MM:SS.mmm format (millisecond precision)
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]  # [:-3] truncates microseconds to milliseconds
        
        # Prepend timestamp to all arguments
        if args:
            args = (f"[{timestamp}]", *args)  # Add timestamp as first argument
        else:
            args = (f"[{timestamp}]",)        # Handle edge case of print() with no args
    
    # Call original print with all arguments, forcing flush=True for consistent output ordering
    return _original_print(*args, **kwargs, flush=True)

# Globally replace the built-in print function
# This affects ALL Python code in this process, including imported modules and scripts
# builtins.print = smart_print

# ==============================================================================
# GENTLE ERROR HANDLING
# ==============================================================================

def gentle_exit(message, exit_code=1):
    """
    Exit gracefully with a user-friendly message.
    
    Args:
        message: User-friendly error message
        exit_code: Exit code (default 1 for error)
    """
    print(f"")
    print(f"💔 Build failed:")
    print(f"   {message}")
    print(f"")
    sys.exit(exit_code)

# ==============================================================================
# BUILD CACHE SYSTEM
# ==============================================================================

def hash_file(path):
    """Compute SHA256 hash of a file for change detection."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_cache(cache_file=".build_cache.json"):
    """Load build cache from disk."""
    cache_path = Path(cache_file)
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    return {}

def save_cache(cache, cache_file=".build_cache.json"):
    """Save build cache to disk."""
    cache_path = Path(cache_file)
    cache_path.write_text(json.dumps(cache, indent=2))

def sources_changed(task_name, source_paths, cache_file=".build_cache.json"):
    """
    Check if any input file changed since last build.
    
    Args:
        task_name: Name of the task (for cache key)
        source_paths: List of Path objects to check
        cache_file: Path to cache file
        
    Returns:
        bool: True if any source file changed
    """
    cache = load_cache(cache_file)
    current_hashes = {str(p): hash_file(p) for p in source_paths if p.exists()}
    cached_hashes = cache.get(task_name, {})
    changed = current_hashes != cached_hashes
    if changed:
        cache[task_name] = current_hashes
        save_cache(cache, cache_file)
    return changed

# ==============================================================================
# FILE MANAGEMENT UTILITIES
# ==============================================================================

def remove_outputs(*filenames, force=True):
    """
    Remove output files with nice logging.
    
    Args:
        *filenames: Files to remove
        force: If True, ignore missing files
    """
    deleted = []
    for name in filenames:
        path = Path(name)
        if path.exists():
            path.unlink()
            deleted.append(path.name)

    print("🗑️ Deleted:", end="")
    if deleted:
        print()  # Add newline for multi-line format
        for d in deleted:
            print(f"   └── {d}")
    else:
        print(" ∅")  # Continue on same line

def get_file_info(filename, name):
    """
    Get file information for status reporting.
    
    Args:
        filename: Path to file
        name: Display name for file
        
    Returns:
        tuple: (mtime, name, filename, size, exists)
    """
    path = Path(filename)
    if path.exists():
        mtime = path.stat().st_mtime
        size = path.stat().st_size
        return (mtime, name, filename, size, True)
    else:
        return (0, name, filename, 0, False)  # Missing files sort first

# ==============================================================================
# SMART TASK RUNNER
# ==============================================================================

def smart_task(c, *, sources, targets, commands=None, python_func=None, force=False, cache_file=".build_cache.json"):
    """
    Unified smart task runner with caching and progress reporting.
    
    Args:
        c: Invoke context
        sources: List of source file paths
        targets: List of target file paths/names
        commands: List of shell commands to run (optional if python_func provided)
        python_func: Python function to execute (optional if commands provided)
        force: If True, force rebuild regardless of cache
        cache_file: Path to cache file
    """
    # Validate that exactly one of commands or python_func is provided
    if commands and python_func:
        gentle_exit("Internal error: Cannot specify both 'commands' and 'python_func'")
    if not commands and not python_func:
        gentle_exit("Internal error: Must specify either 'commands' or 'python_func'")
    
    task_name = inspect.stack()[1].function
    print(f"")
    print(f"↓   ↓   ↓   ↓   ↓   ↓   ↓   ↓   ↓   ↓   ↓   ↓   ↓   ↓   [{task_name}]")
    
    if force or sources_changed(task_name, sources, cache_file):
        remove_outputs(*targets)
        print(f"🔄 Rebuilding {task_name}...")
        
        if commands:
            # Execute shell commands
            for cmd in commands:
                # Run subprocess commands with unbuffered output for better logging
                if cmd.startswith('python3 '):
                    cmd = cmd.replace('python3 ', 'python3 -u ')
                print("##############")
                print(f"{cmd}")
                
                try:
                    c.run(cmd)
                except Exception as e:
                    gentle_exit(f"Command failed in task '{task_name}': {cmd}")
        
        elif python_func:
            # Execute Python function with gentle error handling
            try:
                python_func()
            except Exception as e:
                # Try to extract meaningful error message
                error_msg = str(e)
                if "returned non-zero exit status" in error_msg:
                    # Extract the command that failed from subprocess errors
                    if hasattr(e, 'cmd') and e.cmd:
                        cmd_str = ' '.join(e.cmd) if isinstance(e.cmd, list) else str(e.cmd)
                        gentle_exit(f"Python script failed in task '{task_name}': {cmd_str}")
                    else:
                        gentle_exit(f"Python script failed in task '{task_name}': {error_msg}")
                else:
                    gentle_exit(f"Task '{task_name}' failed: {error_msg}")
        
        # Validate that all targets were actually created
        missing_targets = [t for t in targets if not Path(t).exists()]
        if missing_targets:
            target_list = '\n'.join(f"   • {target}" for target in missing_targets)
            gentle_exit(f"Task '{task_name}' completed but some output files were not created:\n{target_list}")
        
        if targets:
            print("✅ Generated:")
            for t in targets:
                print(f"   └── {t}")
    else:
        if targets:
            print("✅ Up to date:")
            for t in targets:
                print(f"   └── {t}")

    print(f"✅ Task {task_name} completed")
        
def print_file_status(file_path, description):
    """Print formatted file status information."""
    if file_path.exists():
        stat = file_path.stat()
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"   ✅ {description:<15}: {file_path} ({size:,} bytes, {mtime})")
    else:
        print(f"   ❌ {description:<15}: {file_path} (missing)")

def print_build_status(files):
    """
    Print formatted build status for a list of files.
    
    Args:
        files: List of (filename, display_name) tuples
    """
    # Get file info and sort by timestamp
    file_infos = [get_file_info(filename, name) for filename, name in files]
    file_infos.sort(key=lambda x: x[0])  # Sort by mtime
    
    print("📊 Build Status:")
    for mtime, name, filename, size, exists in file_infos:
        if exists:
            mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"   ✅ {name:<18}: {filename:<75} ({size:>10,} bytes, {mtime_str})")
        else:
            print(f"   ❌ {name:<18}: {filename:<75} (missing)")

def run_bwv_script(script_name, *args):
    """
    Run a BWV python script with correct path resolution and project context.
    
    Args:
        script_name: Name of the script (e.g., 'no_hrefs_in_tabs.py')
        *args: Arguments to pass to the script
        
    Returns:
        CompletedProcess result
    """
    # Find the script relative to tasks_utils.py location
    tasks_dir = Path(__file__).parent  # where tasks_utils.py is (invoke dir)
    script_path = tasks_dir.parent / 'python' / script_name
    
    if not script_path.exists():
        gentle_exit(f"BWV script not found: {script_path}")
    
    # Get project name from detect_project_name
    project_name = detect_project_name()
    
    # Set up environment with PROJECT_NAME
    env = os.environ.copy()
    env['PROJECT_NAME'] = project_name
    
    cmd = ['python3', str(script_path)] + list(args)
    print(f"🐍 Running: python3 {script_path.name} {' '.join(args)}")
    print(f"🔧 PROJECT_NAME={project_name}")
    
    # Run without capturing output to allow real-time display
    # Only capture output if there's an error for debugging
    result = subprocess.run(cmd, env=env)
    
    if result.returncode != 0:
        print(f"")
        print(f"🚨 Script failed with exit code {result.returncode}")
        
        # Re-run with captured output for error details
        print(f"🔍 Re-running to capture error details...")
        error_result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        print(f"")
        print(f"🚨 Script output (stdout):")
        if error_result.stdout.strip():
            for line in error_result.stdout.strip().split('\n'):
                print(f"   {line}")
        else:
            print(f"   (no stdout)")
            
        print(f"")
        print(f"🚨 Script errors (stderr):")
        if error_result.stderr.strip():
            for line in error_result.stderr.strip().split('\n'):
                print(f"   {line}")
        else:
            print(f"   (no stderr)")
        
        # Create a proper exception that smart_task can catch
        from subprocess import CalledProcessError
        raise CalledProcessError(result.returncode, cmd, error_result.stdout, error_result.stderr)
    
    return result