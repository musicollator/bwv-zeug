#!/usr/bin/env python3
"""
Tasks Mermaid Generator - Focused on task generation from mermaid files
"""

import argparse
import sys
import textwrap
from pathlib import Path
from antlr4 import *

# Import generated ANTLR classes
try:
    from antlr.MermaidPipelineLexer import MermaidPipelineLexer
    from antlr.MermaidPipelineParser import MermaidPipelineParser
    from antlr.MermaidPipelineParserListener import MermaidPipelineParserListener
except ImportError as e:
    print(f"❌ Error importing ANTLR classes: {e}")
    sys.exit(1)

# Import the existing listener from tasks_mermaid_utils
try:
    from tasks_mermaid_utils import MermaidDisplayListener
except ImportError as e:
    print(f"❌ Error importing MermaidDisplayListener: {e}")
    print("   Make sure tasks_mermaid_utils.py is in the same directory")
    sys.exit(1)

# =============================================================================
# TASK GENERATION FUNCTIONS
# =============================================================================

def get_node_by_id(nodes, node_id):
    """Get node by its ID."""
    return next((n for n in nodes if n['id'] == node_id), None)

def get_nodes_by_type(nodes, node_type):
    """Get all nodes of a specific type."""
    return [n for n in nodes if n['type'] == node_type]

def get_final_tasks_from_listener(listener):
    """Get list of task names that produce final exports from a parsed listener."""
    final_tasks = []
    
    # Find all export nodes (E*)
    export_nodes = [node['id'] for node in listener.nodes if node['type'] == 'E']
    
    # For each export, trace back to find the task that produces it
    for export_id in export_nodes:
        # Find runnable that produces this export (R -> E)
        producing_runnable = None
        for from_node, to_node in listener.edges:
            if to_node == export_id and from_node.startswith('R'):
                producing_runnable = from_node
                break
        
        if producing_runnable:
            # Find task that produces this runnable (T -> R)
            for from_node, to_node in listener.edges:
                if to_node == producing_runnable and from_node.startswith('T'):
                    task_node = get_node_by_id(listener.nodes, from_node)
                    if task_node:
                        final_tasks.append(task_node['content'])
                    break
    
    # Remove duplicates and return
    return list(set(final_tasks))

def trace_task_dependencies(task_id, edges, nodes):
    """
    Trace task dependencies by following the graph.
    Returns list of task function names that this task depends on.
    """
    dependencies = []
    
    # Strategy: Follow the pipeline flow backwards
    # For each task, find what it needs to run before it
    
    # Method 1: Direct task dependencies (T -> T)
    for from_node, to_node in edges:
        if to_node == task_id and from_node.startswith('T'):
            dep_task = get_node_by_id(nodes, from_node)
            if dep_task:
                dependencies.append(dep_task['content'])
    
    # Method 2: Dependencies through outputs (O -> T means T depends on whatever creates O)
    for from_node, to_node in edges:
        if to_node == task_id and from_node.startswith('O'):
            # Find what runnable creates this output
            for r_from, r_to in edges:
                if r_to == from_node and r_from.startswith('R'):
                    # Find what task creates this runnable
                    for t_from, t_to in edges:
                        if t_to == r_from and t_from.startswith('T'):
                            dep_task = get_node_by_id(nodes, t_from)
                            if dep_task:
                                dependencies.append(dep_task['content'])
    
    # Remove duplicates and return
    return list(set(dependencies))

def get_task_sources(task_id, edges, nodes):
   """
   Determine source files for a task based on input dependencies.
   Returns the complete sources expression as a string for direct use in code generation.
   """
   print(f"🔍 DEBUG get_task_sources for {task_id}")
   path_sources = []
   
   # Find inputs that flow to this task
   for from_node, to_node in edges:
       if to_node == task_id:
           print(f"   Found edge: {from_node} -> {to_node}")
           if from_node.startswith('I'):
               print(f"   Processing Input: {from_node}")
               # Direct input files (I -> T)
               input_node = get_node_by_id(nodes, from_node)
               if input_node:
                   filename = input_node['content']
                   if 'BWV000' in filename:
                       filename = filename.replace('BWV000', '{PROJECT_NAME}')
                       path_sources.append(f'Path(f"{filename}")')
                   else:
                       path_sources.append(f'Path("{filename}")')
           elif from_node.startswith('O'):
               print(f"   Processing Output: {from_node}")
               # Output files from previous tasks (O -> T)
               output_node = get_node_by_id(nodes, from_node)
               if output_node:
                   filename = output_node['content']
                   if 'BWV000' in filename:
                       filename = filename.replace('BWV000', '{PROJECT_NAME}')
                       path_sources.append(f'Path(f"{filename}")')
                   else:
                       path_sources.append(f'Path("{filename}")')
                       
   print(f"   Final path_sources: {path_sources}")
   # Rest stays the same...
   
   # Check if we have .ly files to determine if we need shared sources
   has_ly_files = any('.ly' in src for src in path_sources)
   
   # Build the complete sources expression as a string
   if path_sources and has_ly_files:
       path_list = ', '.join(path_sources)
       return f'[{path_list}] + shared_ly_sources()'
   elif path_sources:
       path_list = ', '.join(path_sources)
       return f'[{path_list}]'
   elif has_ly_files:
       return 'shared_ly_sources()'
   else:
       return '[]'

def get_task_targets(task_id, edges, nodes):
    """
    Determine target files for a task based on runnable->output/export dependencies.
    """
    targets = []
    
    # Find the runnable that this task produces (T -> R)
    runnable_id = None
    for from_node, to_node in edges:
        if from_node == task_id and to_node.startswith('R'):
            runnable_id = to_node
            break
    
    # Find outputs/exports that this runnable produces (R -> O or R -> E)
    if runnable_id:
        for from_node, to_node in edges:
            if from_node == runnable_id and (to_node.startswith('O') or to_node.startswith('E')):
                target_node = get_node_by_id(nodes, to_node)
                if target_node:
                    # Extract filename from content and fix BWV000 placeholder
                    filename = target_node['content']
                    filename = filename.replace('BWV000', '{PROJECT_NAME}')
                    targets.append(f'f"{filename}"')
    
    # If no targets found through runnables, check if task has direct input connections
    # that might indicate file generation (like extract_ties creating CSV files)
    if not targets:
        # Look for any python_func commands that include "-o" output flags
        command = get_task_command(task_id, edges, nodes)
        if command and 'run_bwv_script' in command and '"-o"' in command:
            # Extract output filename from the command
            # Pattern: run_bwv_script("script.py", "-i", "input.svg", "-o", "output.csv")
            import re
            output_match = re.search(r'"-o",\s*f?"([^"]+)"', command)
            if output_match:
                filename = output_match.group(1)
                targets.append(f'f"{filename}"')
    
    return targets

def get_task_command(task_id, edges, nodes):
    """
    Get the command for a task by finding its corresponding runnable.
    """
    # Find the runnable that this task maps to (T -> R)
    for from_node, to_node in edges:
        if from_node == task_id and to_node.startswith('R'):
            runnable_node = get_node_by_id(nodes, to_node)
            if runnable_node:
                command = runnable_node['content']
                print(f"   Raw command: '{command}'")
                
                # Check if it's a Docker command or Python script
                if 'docker' in command.lower() and 'run' in command.lower():
                    # Handle Docker command (fix spacing issues if needed)
                    # Replace project name placeholder and fix path
                    command = command.replace('BWV000', '{PROJECT_NAME}')
                    command = command.replace('PWD', f'{{Path.cwd()}}')

                    # Add lilypond includes volume mount to /work/includes
                    lilypond_includes_path = Path(__file__).parent / ".." / "lilypond" / "includes"
                    lilypond_includes_abs = lilypond_includes_path.resolve()
                    
                    # Insert the lilypond volume right after "docker run"
                    command = command.replace('docker run', f'docker run -v {lilypond_includes_abs}:/work/includes')
                    
                    # Replace INCLUDES marker with the actual include flag
                    command = command.replace('INCLUDES', '-I /work/includes')
                                            
                    return f'f"{command}"'
                
                elif command.startswith('bwv_script:'):
                    # Extract script name and arguments  
                    # Format: "bwv_script:script_name.py arg1 arg2 ..."
                    parts = command.split()
                    script_part = parts[0]  # "bwv_script:script_name.py"
                    script_name = script_part.replace('bwv_script:', '')
                    args = parts[1:] if len(parts) > 1 else []
                    
                    # Replace project name in arguments
                    args = [arg.replace('BWV000', '{PROJECT_NAME}') for arg in args]
                    
                    if args:
                        args_str = ', '.join(f'f"{arg}"' for arg in args)
                        return f'run_bwv_script("{script_name}", {args_str})'
                    else:
                        return f'run_bwv_script("{script_name}")'
    
    return None

def debug_task_mapping(task_id, edges, nodes):
    """Debug function to see what's happening with task mapping."""
    print(f"\n🔍 Debug task {task_id}:")
    
    # Show edges from this task
    task_edges = [(f, t) for f, t in edges if f == task_id]
    print(f"   Edges from {task_id}: {task_edges}")
    
    # Show edges to this task  
    to_task_edges = [(f, t) for f, t in edges if t == task_id]
    print(f"   Edges to {task_id}: {to_task_edges}")
    
    # Try to find runnable
    runnable = None
    for from_node, to_node in edges:
        if from_node == task_id and to_node.startswith('R'):
            runnable = get_node_by_id(nodes, to_node)
            break
    
    print(f"   Found runnable: {runnable['id'] if runnable else 'None'}")
    if runnable:
        print(f"   Runnable content: {runnable['content']}")
    
    return runnable

# =============================================================================
# TEMPLATE GENERATION FUNCTIONS
# =============================================================================

def generate_status_task(listener):
    """Generate the status task based on parsed mermaid content."""
    # Extract file information from nodes
    status_files = []
    
    # Get export nodes
    export_nodes = get_nodes_by_type(listener.nodes, 'E')
    for node in export_nodes:
        filename = node['content'].replace('BWV000', '{PROJECT_NAME}')
        description = node.get('description', node['content'])
        status_files.append(('Export', description, filename))
    
    # Get output nodes
    output_nodes = get_nodes_by_type(listener.nodes, 'O')
    for node in output_nodes:
        filename = node['content'].replace('BWV000', '{PROJECT_NAME}')
        description = node.get('description', node['content'])
        status_files.append(('Output', description, filename))
    
    # Get input nodes that are generated (like ties.csv)
    input_nodes = get_nodes_by_type(listener.nodes, 'I')
    for node in input_nodes:
        filename = node['content'].replace('BWV000', '{PROJECT_NAME}')
        # Only include generated input files (not source files)
        if filename.endswith('.csv') or 'generated' in filename.lower():
            description = node.get('description', node['content'])
            status_files.append(('Input', description, filename))
    
    # Generate status_files list entries
    status_entries = []
    for category, description, filename in status_files:
        status_entries.append(f"        ('{category}', '{description}', f'{filename}'),")
    status_list = '\n'.join(status_entries)
    
    return f"""@task
def status(c):
    \"\"\"Show build status of all files.\"\"\"
    print(f"🎼 Detected project: {{PROJECT_NAME}}")
    
    # File information extracted from mermaid diagram
    status_files = [
{status_list}
    ]
    
    # Get file info and sort by timestamp
    file_infos = []
    for category, description, filename in status_files:
        file_infos.append(get_file_info(filename, description))
    
    # Sort by timestamp (missing files first, then by modification time)
    file_infos.sort(key=lambda x: x[0])
    
    print("📊 Build Status:")
    for mtime, name, filename, size, exists in file_infos:
        if exists:
            mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"   ✅ {{name:<18}}: {{filename:<75}} ({{size:>10,}} bytes, {{mtime_str}})")
        else:
            print(f"   ❌ {{name:<18}}: {{filename:<75}} (missing)")"""

def generate_clean_task(listener):
    """Generate the clean task that only deletes intermediate files (not exports)."""
    # Get intermediate files (outputs and generated inputs, but NOT exports)
    target_files = []
    
    # Get output nodes (intermediate files)
    output_nodes = get_nodes_by_type(listener.nodes, 'O')
    for node in output_nodes:
        filename = node['content'].replace('BWV000', '{PROJECT_NAME}')
        target_files.append(filename)
    
    # Get generated input files (like ties.csv)
    input_nodes = get_nodes_by_type(listener.nodes, 'I')
    for node in input_nodes:
        filename = node['content'].replace('BWV000', '{PROJECT_NAME}')
        # Only include generated input files
        if filename.endswith('.csv') or 'generated' in filename.lower():
            target_files.append(filename)
    
    # Generate target_files list entries
    target_entries = []
    for filename in target_files:
        target_entries.append(f"        f'{filename}',")
    target_list = '\n'.join(target_entries)
    
    return f"""@task
def clean(c):
    \"\"\"Delete intermediate files (preserves final exports).\"\"\"
    print(f"🎼 Detected project: {{PROJECT_NAME}}")
    
    # Intermediate files extracted from mermaid diagram (excludes exports)
    target_files = [
{target_list}
    ]
    
    # Delete files
    deleted = []
    for filename in target_files:
        path = Path(filename)
        if path.exists():
            path.unlink()
            deleted.append(path.name)
    
    print("🗑️ Deleted intermediate files:", end="")
    if deleted:
        print()
        for d in deleted:
            print(f"   └── {{d}}")
    else:
        print(" ∅")
    
    # Also clean build cache
    cache_file = Path('.build_cache.json')
    if cache_file.exists():
        cache_file.unlink()
        print("🗑️ Deleted build cache")"""

def generate_clean_all_task(listener):
    """Generate the clean_all task that deletes all generated files including exports."""
    # Get all target files (outputs, exports, and generated inputs)
    target_files = []
    
    # Get export nodes
    export_nodes = get_nodes_by_type(listener.nodes, 'E')
    for node in export_nodes:
        filename = node['content'].replace('BWV000', '{PROJECT_NAME}')
        target_files.append(filename)
    
    # Get output nodes
    output_nodes = get_nodes_by_type(listener.nodes, 'O')
    for node in output_nodes:
        filename = node['content'].replace('BWV000', '{PROJECT_NAME}')
        target_files.append(filename)
    
    # Get generated input files (like ties.csv)
    input_nodes = get_nodes_by_type(listener.nodes, 'I')
    for node in input_nodes:
        filename = node['content'].replace('BWV000', '{PROJECT_NAME}')
        # Only include generated input files
        if filename.endswith('.csv') or 'generated' in filename.lower():
            target_files.append(filename)
    
    # Generate target_files list entries
    target_entries = []
    for filename in target_files:
        target_entries.append(f"        f'{filename}',")
    target_list = '\n'.join(target_entries)
    
    return f"""@task
def clean_all(c):
    \"\"\"Delete all generated files including final exports.\"\"\"
    print(f"🎼 Detected project: {{PROJECT_NAME}}")
    
    # All target files extracted from mermaid diagram
    target_files = [
{target_list}
    ]
    
    # Delete files
    deleted = []
    for filename in target_files:
        path = Path(filename)
        if path.exists():
            path.unlink()
            deleted.append(path.name)
    
    print("🗑️ Deleted all generated files:", end="")
    if deleted:
        print()
        for d in deleted:
            print(f"   └── {{d}}")
    else:
        print(" ∅")
    
    # Also clean build cache
    cache_file = Path('.build_cache.json')
    if cache_file.exists():
        cache_file.unlink()
        print("🗑️ Deleted build cache")"""

def generate_all_task(listener):
    """Generate the 'all' task that runs final export tasks."""
    final_tasks = get_final_tasks_from_listener(listener)
    
    if not final_tasks:
        return ""
    
    final_tasks_list = ', '.join(f"'{task}'" for task in final_tasks)
    
    # Generate pre= dependency list (no quotes for function references)
    pre_dependencies = ', '.join(final_tasks)
    
    return f"""@task(pre=[{pre_dependencies}])
def all(c, force=False):
    \"\"\"Build all final outputs by running the complete pipeline.\"\"\"
    print(f"🎼 Building all outputs for project: {{PROJECT_NAME}}")
    
    # Final tasks that produce exports: {final_tasks_list}
    # Dependencies handled automatically by pre=[{pre_dependencies}]
    print("🎉 All pipeline outputs completed!")"""

def generate_info_task(listener):
    """Generate the info task with pipeline information."""
    # Get all task nodes for listing
    task_nodes = get_nodes_by_type(listener.nodes, 'T')
    
    # Generate pipeline tasks list entries
    pipeline_entries = []
    for task_node in task_nodes:
        task_name = task_node['content']
        description = task_node.get('description', task_name.replace('_', ' ').title())
        pipeline_entries.append(f"        ('{task_name}', '{description}'),")
    pipeline_list = '\n'.join(pipeline_entries)
    
    return f"""@task
def info(c):
    \"\"\"Show information about the build system.\"\"\"
    print("🚀 BWV Build System")
    print("=" * 50)
    print(f"🎼 Project: {{PROJECT_NAME}}")
    print(f"📄 Pipeline: tasks.mmd")
    print(f"🤖 Generated: tasks_generated.py")
    print(f"📋 Available tasks:")
    print("   • status     - Show file status")
    print("   • clean      - Delete intermediate files") 
    print("   • clean_all  - Delete all generated files")
    print("   • all        - Build all final outputs")
    print("   • info       - This information")
    print("   🔧 Pipeline tasks (from tasks.mmd):")
    
    # Pipeline tasks extracted from mermaid diagram
    pipeline_tasks = [
{pipeline_list}
    ]
    
    for task_name, description in pipeline_tasks:
        print(f"      • {{task_name:<20}} - {{description}}")"""

def generate_tasks_file(listener):
    """Generate the tasks_generated.py file using a templating approach."""
    
    # Template for each task function
    TASK_TEMPLATE = textwrap.dedent("""\
        {decorator}
        def {task_name}(c, force=False):
            \"\"\"{task_description}.\"\"\"
        {body}
    """)

    HEADER = textwrap.dedent("""\
        #!/usr/bin/env python3
        \"\"\"
        Generated Invoke Tasks - Auto-generated from tasks.mmd

        DO NOT EDIT MANUALLY - This file is auto-generated
        Regenerate with: python tasks_mermaid_generator.py -i tasks.mmd -o tasks_generated.py
        \"\"\"

        from invoke import task
        from pathlib import Path
        from datetime import datetime
        from tasks_utils import smart_task, detect_project_name, flatten_tree, get_shared_ly_sources_tree, run_bwv_script, get_file_info

        # Cache project name at module level - detected only once
        PROJECT_NAME = detect_project_name()


        def shared_ly_sources():
            \"\"\"Get shared LilyPond source dependencies.\"\"\"
            return [Path(p) for p in flatten_tree(get_shared_ly_sources_tree(PROJECT_NAME))]


    """)

    # Get all task nodes
    task_nodes = get_nodes_by_type(listener.nodes, 'T')
    print(f"🔍 Found {len(task_nodes)} task nodes")

    # Sort task nodes to ensure dependencies are defined before they're referenced
    def sort_tasks_by_dependencies(task_nodes, edges):
        """Sort tasks so that dependencies come before dependents."""
        sorted_tasks = []
        remaining_tasks = task_nodes.copy()
        
        while remaining_tasks:
            # Find tasks with no unresolved dependencies
            ready_tasks = []
            for task in remaining_tasks:
                dependencies = trace_task_dependencies(task['id'], edges, task_nodes)
                # Check if all dependencies are already in sorted_tasks
                deps_satisfied = all(
                    any(sorted_task['content'] == dep for sorted_task in sorted_tasks)
                    for dep in dependencies
                )
                if deps_satisfied:
                    ready_tasks.append(task)
            
            if not ready_tasks:
                # If no tasks are ready, just take the first one to avoid infinite loop
                ready_tasks = [remaining_tasks[0]]
                print(f"⚠️  Warning: Potential circular dependency, adding {remaining_tasks[0]['content']} anyway")
            
            # Add ready tasks to sorted list and remove from remaining
            for task in ready_tasks:
                sorted_tasks.append(task)
                remaining_tasks.remove(task)
        
        return sorted_tasks
    
    # Sort tasks by dependencies
    task_nodes = sort_tasks_by_dependencies(task_nodes, listener.edges)
    print(f"🔧 Sorted tasks by dependencies")

    # Generate all pipeline tasks
    pipeline_tasks = []
    for task_node in task_nodes:
        task_id = task_node['id']
        task_name = task_node['content']
        task_description = task_node.get('description', task_name.replace('_', ' ').title())

        debug_task_mapping(task_id, listener.edges, listener.nodes)

        dependencies = trace_task_dependencies(task_id, listener.edges, listener.nodes)
        sources = get_task_sources(task_id, listener.edges, listener.nodes)
        targets = get_task_targets(task_id, listener.edges, listener.nodes)
        command = get_task_command(task_id, listener.edges, listener.nodes)

        decorator = f"@task(pre=[{', '.join(dependencies)}])" if dependencies else "@task"

        if command:
            targets_str = ', '.join(targets) if targets else ''
            
            if command.startswith('run_bwv_script'):
                # Python script
                commands_param = "None"
                python_func_param = f"lambda: {command}"
            else:
                # Docker/shell command  
                commands_param = f"[{command}]"
                python_func_param = "None"
            
            body = textwrap.dedent(f"""\
                smart_task(
                    c,
                    sources={sources},
                    targets=[{targets_str}],
                    commands={commands_param},
                    python_func={python_func_param},
                    force=force,
                )
            """)
        else:
            body = "    # TODO: Add implementation - no command found\n    pass"

        # Indent body to match function block
        indented_body = textwrap.indent(body, '    ')

        task_code = TASK_TEMPLATE.format(
            decorator=decorator,
            task_name=task_name,
            task_description=task_description,
            body=indented_body
        )

        pipeline_tasks.append(task_code)

    # Generate meta-tasks
    print("🔧 Generating meta-tasks...")
    
    # Get all meta-tasks
    status_task = generate_status_task(listener)
    clean_task = generate_clean_task(listener)
    clean_all_task = generate_clean_all_task(listener)
    all_task = generate_all_task(listener)
    info_task = generate_info_task(listener)
    
    # Combine all tasks with proper spacing
    all_pipeline_tasks = '\n\n'.join(pipeline_tasks)
    
    # Build the complete file using template  
    complete_file = f"""{HEADER}
{all_pipeline_tasks}

{status_task}

{clean_task}

{clean_all_task}

{all_task if all_task else ""}

{info_task}
"""

    return complete_file

# =============================================================================
# FILE HEADER GENERATION
# =============================================================================

def generate_file_header():
    """Generate the file header with imports and common functions."""
    return '''#!/usr/bin/env python3
"""
Generated Meta Tasks - Auto-generated from mermaid diagram

DO NOT EDIT MANUALLY - This file is auto-generated
Regenerate with: python tasks_mermaid_generator.py -i tasks.mmd -o meta_tasks.py
"""

from invoke import task
from pathlib import Path
from datetime import datetime
from tasks_utils import get_file_info, detect_project_name

# Cache project name at module level - detected only once
PROJECT_NAME = detect_project_name()

'''

# =============================================================================
# MAIN GENERATION FUNCTION
# =============================================================================

def generate_meta_tasks(mermaid_file):
    """Generate meta tasks from mermaid file and return as string."""
    print(f"📄 Processing mermaid file: {mermaid_file}")
    
    mermaid_path = Path(mermaid_file)
    if not mermaid_path.exists():
        print(f"❌ Mermaid file not found: {mermaid_path}")
        return ""
    
    try:
        # Read and parse with ANTLR
        content = mermaid_path.read_text()
        input_stream = InputStream(content)
        lexer = MermaidPipelineLexer(input_stream)
        lexer.removeErrorListeners()
        
        stream = CommonTokenStream(lexer)
        parser = MermaidPipelineParser(stream)
        parser.removeErrorListeners()
        
        tree = parser.diagram()
        
        # Extract information using listener
        listener = MermaidDisplayListener()
        walker = ParseTreeWalker()
        walker.walk(listener, tree)
        
        print(f"✅ Parsed {len(listener.nodes)} nodes and {len(listener.edges)} edges")
        
        # Generate all meta-tasks
        status_task = generate_status_task(listener)
        clean_task = generate_clean_task(listener)
        clean_all_task = generate_clean_all_task(listener)
        all_task = generate_all_task(listener)
        info_task = generate_info_task(listener)
        
        # Generate complete file content
        header = generate_file_header()
        meta_tasks = f"""{header}
{status_task}


{clean_task}


{clean_all_task}


{all_task}


{info_task}
"""
        
        return meta_tasks
        
    except Exception as e:
        print(f"❌ Error parsing mermaid file: {e}")
        import traceback
        traceback.print_exc()
        return ""

def generate_full_tasks(mermaid_file):
    """Generate complete tasks file with both pipeline and meta tasks."""
    print(f"📄 Processing mermaid file for full tasks: {mermaid_file}")
    
    mermaid_path = Path(mermaid_file)
    if not mermaid_path.exists():
        print(f"❌ Mermaid file not found: {mermaid_path}")
        return ""
    
    try:
        # Read and parse with ANTLR
        content = mermaid_path.read_text()
        input_stream = InputStream(content)
        lexer = MermaidPipelineLexer(input_stream)
        lexer.removeErrorListeners()
        
        stream = CommonTokenStream(lexer)
        parser = MermaidPipelineParser(stream)
        parser.removeErrorListeners()
        
        tree = parser.diagram()
        
        # Extract information using listener
        listener = MermaidDisplayListener()
        walker = ParseTreeWalker()
        walker.walk(listener, tree)
        
        print(f"✅ Parsed {len(listener.nodes)} nodes and {len(listener.edges)} edges")
        
        # Generate complete tasks file
        full_tasks = generate_tasks_file(listener)
        
        return full_tasks
        
    except Exception as e:
        print(f"❌ Error parsing mermaid file for full tasks: {e}")
        import traceback
        traceback.print_exc()
        return ""

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate tasks from mermaid pipeline diagrams',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python tasks_mermaid_generator.py -i tasks.mmd -o tasks_generated.py
  python tasks_mermaid_generator.py --input tasks.mmd --output generated_tasks.py
        ''')
    
    parser.add_argument('-i', '--input', 
                        required=True,
                        help='Input mermaid file (.mmd)')
    
    parser.add_argument('-o', '--output', 
                        required=True,
                        help='Output Python file (.py)')
    
    args = parser.parse_args()
    
    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        sys.exit(1)
    
    if not input_path.suffix.lower() in ['.mmd', '.md']:
        print(f"⚠️  Warning: Input file doesn't have .mmd extension: {input_path}")
    
    # Validate output file
    output_path = Path(args.output)
    if not output_path.suffix.lower() == '.py':
        print(f"⚠️  Warning: Output file doesn't have .py extension: {output_path}")
    
    # Generate tasks
    print(f"🚀 Generating tasks file...")
    print(f"   Input:  {input_path}")
    print(f"   Output: {output_path}")
    
    tasks_content = generate_full_tasks(args.input)
    
    if tasks_content:
        # Write to output file
        try:
            output_path.write_text(tasks_content)
            print(f"✅ Successfully generated: {output_path}")
            print(f"📊 File size: {len(tasks_content):,} characters")
            
            # Count lines for summary
            line_count = len(tasks_content.splitlines())
            print(f"📏 Lines generated: {line_count}")
            
        except Exception as e:
            print(f"❌ Error writing output file: {e}")
            sys.exit(1)
    else:
        print(f"❌ Failed to generate tasks")
        sys.exit(1)

if __name__ == "__main__":
    main()