# BWV Invoke Task Generator

Automated task generation system for Bach score processing using Mermaid diagrams and ANTLR parsing.

## Quick Start

1. **Generate ANTLR parsers** (required after grammar changes):
   ```bash
   cd invoke/antlr
   source build_antlr.sh
   ```

2. **Generate tasks** from Mermaid diagram:
   ```bash
   cd invoke
   python tasks_mermaid_generator.py -i TASKS.mmd -o tasks_generated.py
   ```

   ```bash
   % alias b  
   b='invoke --search-root /Users/christophe.thiebaud/github.com/musicollator/bwv-zeug/invoke'
   ```

3. **Run tasks** (from a BWV project directory, bwv1006, bwv543, etc.):
   ```bash
   b pdf  
   ```

## Files

### Source Files (commit to git)
- `antlr/build_antlr.sh` - ANTLR build script
- `antlr/MermaidPipelineLexer.g4` - ANTLR lexer grammar with whitespace preservation
- `antlr/MermaidPipelineParser.g4` - ANTLR parser grammar
- `tasks_mermaid_generator.py` - Parser and task generator
- `tasks_utils.py` - Task utilities and smart caching system
- `TASKS.mmd` - Mermaid diagram defining the build pipeline
- `tasks.py` - Main task file (includes generated tasks)

### Generated Files (don't commit)
- `antlr/MermaidPipeline*.py` - Generated ANTLR parsers
- `antlr/.antlr/` - ANTLR cache directory
- `tasks_generated.py` - Generated Invoke tasks (imported by tasks.py)
- `.build_cache.json` - Task build cache 

## Workflow

1. **Edit pipeline**: Modify `TASKS.mmd` with new tasks/dependencies
2. **Regenerate tasks**: `python tasks_mermaid_generator.py -i TASKS.mmd -o tasks_generated.py`
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
