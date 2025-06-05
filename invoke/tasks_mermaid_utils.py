#!/usr/bin/env python3
"""
Minimal Mermaid Utils - Parse .mmd files and generate Invoke tasks
"""

VERSION = "4.0.0"

import textwrap
import sys
from pathlib import Path
from antlr4 import *

# Import generated ANTLR classes
try:
    from antlr.MermaidPipelineLexer import MermaidPipelineLexer
    from antlr.MermaidPipelineParser import MermaidPipelineParser
    from antlr.MermaidPipelineParserListener import MermaidPipelineParserListener
except ImportError as e:
    print(f"❌ Error importing ANTLR classes: {e}")
    print("💡 Make sure you have generated the ANTLR classes with:")
    print("   source build_antlr.sh")
    print("")
    print("📁 Required files:")
    print("   - MermaidPipelineLexer.py")
    print("   - MermaidPipelineParser.py") 
    print("   - MermaidPipelineParserListener.py")
    sys.exit(1)

# =============================================================================
# ANTLR LISTENER WITH LEXER MODE SUPPORT
# =============================================================================

class MermaidDisplayListener(MermaidPipelineParserListener):
    """ANTLR listener that extracts mermaid content with proper whitespace preservation."""
    
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.class_defs = []
        self.class_assignments = []
        self.graph_direction = None
        self.init_content = None
    
    def enterGraphDeclaration(self, ctx):
        """Extract graph direction."""
        try:
            if hasattr(ctx, 'direction') and ctx.direction():
                self.graph_direction = ctx.direction().getText()
        except Exception as e:
            print(f"⚠️ Warning in enterGraphDeclaration: {e}")
    
    def enterInitBlock(self, ctx):
        """Extract init block content."""
        try:
            if hasattr(ctx, 'initContent') and ctx.initContent():
                self.init_content = ctx.initContent().getText()
        except Exception as e:
            print(f"⚠️ Warning in enterInitBlock: {e}")
    
    def enterNodeDeclaration(self, ctx):
        """Extract node declarations with preserved whitespace from lexer modes."""
        try:
            # Get node ID
            node_id = None
            if hasattr(ctx, 'nodeId') and ctx.nodeId():
                node_id = ctx.nodeId().getText()
            else:
                print(f"⚠️ No nodeId found")
                return
            
            # Get node content from the shape (brackets, parens, braces)
            content = ""
            shape_type = "none"
            
            if hasattr(ctx, 'nodeShape') and ctx.nodeShape():
                shape_ctx = ctx.nodeShape()
                
                # The content should be available via nodeContent()
                if hasattr(shape_ctx, 'nodeContent') and shape_ctx.nodeContent():
                    content_ctx = shape_ctx.nodeContent()
                    content = content_ctx.getText()  # This should now preserve whitespace!
                    
                    # Detect shape type from the shape context
                    if hasattr(shape_ctx, 'LSQUARE') and shape_ctx.LSQUARE():
                        shape_type = "square"
                    elif hasattr(shape_ctx, 'LPAREN') and shape_ctx.LPAREN():
                        shape_type = "round"  
                    elif hasattr(shape_ctx, 'LBRACE') and shape_ctx.LBRACE():
                        shape_type = "diamond"
                else:
                    print("⚠️ No nodeContent found in nodeShape")
            else:
                # Node without explicit shape - just the ID
                content = node_id
            
            # Split content by <br/> if present
            if '<br/>' in content:
                parts = content.split('<br/>')
                main_content = parts[0].strip()
                description = parts[1].strip() if len(parts) > 1 else ""
            else:
                main_content = content.strip()
                description = ""
            
            self.nodes.append({
                'id': node_id,
                'type': node_id[0] if node_id else 'U',
                'content': main_content,
                'description': description
            })
            
        except Exception as e:
            print(f"❌ Error processing node {ctx.getText()}: {e}")
            import traceback
            traceback.print_exc()
    
    def enterEdge(self, ctx):
        """Extract edge relationships."""
        try:
            if hasattr(ctx, 'nodeId'):
                # Get the two node IDs
                node_ids = []
                for i in range(ctx.getChildCount()):
                    child = ctx.getChild(i)
                    if hasattr(child, 'getText'):
                        child_text = child.getText()
                        # Check if this looks like a node ID
                        if len(child_text) > 0 and child_text[0] in 'ITORE':
                            node_ids.append(child_text)
                
                if len(node_ids) >= 2:
                    from_node = node_ids[0]
                    to_node = node_ids[1]
                    self.edges.append((from_node, to_node))
                
        except Exception as e:
            print(f"❌ Error processing edge: {e}")
    
    def enterClassDef(self, ctx):
        """Extract classDef statements."""
        try:
            class_name = ""
            properties = ""
            
            if hasattr(ctx, 'IDENTIFIER') and ctx.IDENTIFIER():
                class_name = ctx.IDENTIFIER().getText()
            
            if hasattr(ctx, 'cssContent') and ctx.cssContent():
                properties = ctx.cssContent().getText()
            
            if class_name:
                self.class_defs.append((class_name, properties))
                
        except Exception as e:
            print(f"❌ Error processing classDef: {e}")
    
    def enterClassAssignment(self, ctx):
        """Extract class assignments."""
        try:
            class_name = ""
            nodes = []
            
            if hasattr(ctx, 'classNodeList') and ctx.classNodeList():
                node_list = ctx.classNodeList()
                # Get all node IDs from the list
                for child in node_list.getChildren():
                    if hasattr(child, 'getText') and child.getText() not in [',']:
                        text = child.getText()
                        if len(text) > 0 and text[0] in 'ITORE':
                            nodes.append(text)
            
            if hasattr(ctx, 'IDENTIFIER') and ctx.IDENTIFIER():
                class_name = ctx.IDENTIFIER().getText()
            
            if class_name and nodes:
                self.class_assignments.append((nodes, class_name))
                
        except Exception as e:
            print(f"❌ Error processing class assignment: {e}")
    
    def enterComment(self, ctx):
        """Handle comments (mostly ignore but could log)."""
        pass

# =============================================================================
# PARSER FUNCTIONS
# =============================================================================

def parse_and_display_mermaid(mermaid_file: str):
    """Parse mermaid file and display its contents using ANTLR."""
    print(f"🚀 Mermaid Utils v{VERSION}")
    print(f"📄 Processing file: {mermaid_file}")
    
    mermaid_path = Path(mermaid_file)
    
    if not mermaid_path.exists():
        print(f"❌ Mermaid file not found: {mermaid_path}")
        return
    
    try:
        # Read and parse with ANTLR
        content = mermaid_path.read_text()
        print(f"📏 File size: {len(content)} characters")
        
        # Create ANTLR input stream
        input_stream = InputStream(content)
        lexer = MermaidPipelineLexer(input_stream)
        
        # Set up error handling
        lexer.removeErrorListeners()
        
        stream = CommonTokenStream(lexer)
        parser = MermaidPipelineParser(stream)
        
        # Remove default error listeners to avoid spam
        parser.removeErrorListeners()
        
        # Parse the content
        tree = parser.diagram()
        
        # Extract information using listener
        listener = MermaidDisplayListener()
        walker = ParseTreeWalker()
        walker.walk(listener, tree)
        
        # Display results
        display_full_parsed_content(listener)
        
    except Exception as e:
        print(f"❌ Error parsing mermaid file: {e}")
        import traceback
        traceback.print_exc()

def display_full_parsed_content(listener):
    """Display complete parsed content including styles."""
    print("🔍 Complete Mermaid Analysis")
    print("=" * 60)
    
    # Graph info
    if listener.graph_direction:
        print(f"📊 Graph Direction: {listener.graph_direction}")
    
    if listener.init_content:
        print(f"⚙️ Init Config: {listener.init_content}")
    
    # Nodes by type
    node_types = {'I': 'Inputs', 'T': 'Tasks', 'O': 'Outputs', 'R': 'Runnables', 'E': 'Exports'}
    
    for node_type, type_name in node_types.items():
        type_nodes = [n for n in listener.nodes if n['type'] == node_type]
        if type_nodes:
            print(f"\n📋 {type_name}:")
            for node in type_nodes:
                print(f"   {node['id']}: {node['content']}")
                if node['description']:
                    print(f"      └─ {node['description']}")
                
                # Add input/output info for Tasks and Runnables
                if node_type in ['T', 'R']:
                    # Show inputs (what flows into this node)
                    inputs = [from_node for from_node, to_node in listener.edges if to_node == node['id']]
                    if inputs:
                        print(f"      📥 Inputs: {', '.join(inputs)}")
                    
                    # Show outputs (what flows out of this node)  
                    outputs = [to_node for from_node, to_node in listener.edges if from_node == node['id']]
                    if outputs:
                        print(f"      📤 Outputs: {', '.join(outputs)}")
    
    # Edges
    if listener.edges:
        print(f"\n🔗 Relationships:")
        for from_node, to_node in listener.edges:
            print(f"   {from_node} --> {to_node}")
    
    # Class definitions
    if listener.class_defs:
        print(f"\n🎨 Style Definitions:")
        for class_name, properties in listener.class_defs:
            print(f"   {class_name}: {properties}")
    
    # Class assignments
    if listener.class_assignments:
        print(f"\n🏷️ Style Assignments:")
        for nodes, class_name in listener.class_assignments:
            print(f"   {class_name}: {', '.join(nodes)}")
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"   Total nodes: {len(listener.nodes)}")
    print(f"   Total edges: {len(listener.edges)}")
    print(f"   Style definitions: {len(listener.class_defs)}")
    print(f"   Style assignments: {len(listener.class_assignments)}")
    for node_type, type_name in node_types.items():
        count = len([n for n in listener.nodes if n['type'] == node_type])
        if count > 0:
            print(f"   {type_name}: {count}")

# =============================================================================
# MERMAID FILE ANALYSIS HELPERS
# =============================================================================

def get_all_file_nodes(mermaid_file):
    """
    Parse mermaid file and return all file-related nodes (I, O, E).
    Returns dict with categorized file information.
    """
    mermaid_path = Path(mermaid_file)
    if not mermaid_path.exists():
        return {}
    
    try:
        content = mermaid_path.read_text()
        input_stream = InputStream(content)
        lexer = MermaidPipelineLexer(input_stream)
        lexer.removeErrorListeners()
        
        stream = CommonTokenStream(lexer)
        parser = MermaidPipelineParser(stream)
        parser.removeErrorListeners()
        
        tree = parser.diagram()
        
        listener = MermaidDisplayListener()
        walker = ParseTreeWalker()
        walker.walk(listener, tree)
        
        # Categorize file nodes
        file_info = {
            'inputs': [],
            'outputs': [], 
            'exports': []
        }
        
        for node in listener.nodes:
            filename = node['content'].replace('BWV000', '{PROJECT_NAME}')
            file_data = {
                'id': node['id'],
                'filename': filename,
                'description': node.get('description', ''),
                'category': node['type']
            }
            
            if node['type'] == 'I':
                file_info['inputs'].append(file_data)
            elif node['type'] == 'O':
                file_info['outputs'].append(file_data)
            elif node['type'] == 'E':
                file_info['exports'].append(file_data)
        
        return file_info
        
    except Exception as e:
        print(f"❌ Error parsing mermaid file: {e}")
        return {}

def get_all_target_files(mermaid_file):
    """
    Get list of all target files (outputs + exports) that can be cleaned.
    Returns list of filename strings with PROJECT_NAME placeholder.
    """
    file_info = get_all_file_nodes(mermaid_file)
    targets = []
    
    for output in file_info['outputs']:
        targets.append(output['filename'])
    
    for export in file_info['exports']:
        targets.append(export['filename'])
    
    return targets

def get_final_tasks(mermaid_file):
    """
    Get list of task names that produce final exports.
    These are tasks that connect to runnables that produce export nodes.
    """
    mermaid_path = Path(mermaid_file)
    if not mermaid_path.exists():
        return []
    
    try:
        content = mermaid_path.read_text()
        input_stream = InputStream(content)
        lexer = MermaidPipelineLexer(input_stream)
        lexer.removeErrorListeners()
        
        stream = CommonTokenStream(lexer)
        parser = MermaidPipelineParser(stream)
        parser.removeErrorListeners()
        
        tree = parser.diagram()
        
        listener = MermaidDisplayListener()
        walker = ParseTreeWalker()
        walker.walk(listener, tree)
        
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
                        # Get node by ID
                        task_node = next((n for n in listener.nodes if n['id'] == from_node), None)
                        if task_node:
                            final_tasks.append(task_node['content'])
                        break
        
        # Remove duplicates and return
        return list(set(final_tasks))
        
    except Exception as e:
        print(f"❌ Error parsing mermaid file for final tasks: {e}")
        return []
    
def get_status_file_info(mermaid_file):
    """
    Get structured file information for status display.
    Returns list of (category, description, filename) tuples.
    """
    file_info = get_all_file_nodes(mermaid_file)
    status_files = []
    
    # Add outputs
    for output in file_info['outputs']:
        status_files.append(('Output', output['description'], output['filename']))
    
    # Add exports  
    for export in file_info['exports']:
        status_files.append(('Export', export['description'], export['filename']))
    
    return status_files            

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tasks_mermaid_utils.py <mermaid_file.mmd>")
        sys.exit(1)
    
    mermaid_file = sys.argv[1]
    
    parse_and_display_mermaid(mermaid_file)