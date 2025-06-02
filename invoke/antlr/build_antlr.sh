#!/bin/bash

# Build script for ANTLR grammar files
echo "🚀 Building ANTLR Grammar Files"
echo "================================"

# Clean up old generated files
echo "🧹 Cleaning up old generated files..."
rm -f MermaidPipeline*.py *.tokens *.interp

# Generate lexer classes
echo "📝 Generating lexer classes..."
antlr4 -Dlanguage=Python3 MermaidPipelineLexer.g4

# Generate parser classes  
echo "📝 Generating parser classes..."
antlr4 -Dlanguage=Python3 MermaidPipelineParser.g4

# List generated files
echo "✅ Generated files:"
ls -la MermaidPipeline*.py

echo ""
echo "🎉 Build complete!"
echo "💡 You can now run: python tasks_mermaid_generator.py"
echo ""
echo "📝 Note: Run this script with 'source build_antlr.sh' to use shell aliases"