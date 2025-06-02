#!/usr/bin/env python3
"""
BWV Processing Tasks - Complete build system for Bach scores
"""

# Import all generated tasks from the auto-generated file
try:
    from tasks_generated import *
    print("✅ Loaded generated tasks from tasks_generated.py")
except ImportError as e:
    print("⚠️  Warning: Could not import tasks_generated.py")
    print("   Generate it with: python tasks_mermaid_utils.py tasks.mmd --generate-tasks")
    print(f"   Error: {e}")