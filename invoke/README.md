# BWV Invoke Task Generator

Automated task generation system for Bach score processing using Mermaid diagrams and ANTLR parsing.

## Quick Start

1. **Generate ANTLR parsers** (required after grammar changes):
   ```bash
   source build_antlr.sh
   ```

2. **Generate tasks** from Mermaid diagram:
   ```bash
   python tasks_mermaid_utils.py tasks.mmd --generate-tasks
   ```

3. **Run tasks** (from BWV project directory):
   ```bash
   invoke build_pdf  # uses tasks.py which includes tasks_generated.py
   ```

## Files

### Source Files (commit to git)
- `MermaidPipelineLexer.g4` - ANTLR lexer grammar with whitespace preservation
- `MermaidPipelineParser.g4` - ANTLR parser grammar
- `tasks.mmd` - Mermaid diagram defining the build pipeline
- `tasks_mermaid_utils.py` - Parser and task generator
- `tasks_utils.py` - Task utilities and smart caching system
- `tasks.py` - Main task file (includes generated tasks)
- `build_antlr.sh` - ANTLR build script

### Generated Files (don't commit)
- `MermaidPipeline*.py` - Generated ANTLR parsers
- `tasks_generated.py` - Generated Invoke tasks (imported by tasks.py)
- `.antlr/` - ANTLR cache directory
- `.build_cache.json` - Task build cache

## Workflow

1. **Edit pipeline**: Modify `tasks.mmd` with new tasks/dependencies
2. **Regenerate tasks**: `python tasks_mermaid_utils.py tasks.mmd --generate-tasks`
3. **Use tasks**: `invoke <task_name>` (tasks.py imports generated tasks)

## Features

- ✅ **Smart caching** - Only rebuild when sources change
- ✅ **Dependency tracking** - Automatic task prerequisites  
- ✅ **Docker & Python** - Unified handling of shell commands and Python scripts
- ✅ **Project detection** - Automatic BWV project name resolution
- ✅ **Whitespace preservation** - Proper Docker command parsing

## Requirements

```bash
pip install antlr4-python3-runtime invoke
```