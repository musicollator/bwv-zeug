lexer grammar MermaidPipelineLexer;

// =============================================================================
// DEFAULT MODE (outside brackets/parens/braces)
// =============================================================================

// Skip whitespace in default mode
WS : [ \t\r\n]+ -> skip ;

// Keywords
FLOWCHART : 'flowchart' ;
GRAPH : 'graph' ;
CLASSDEF : 'classDef' ;
CLASS : 'class' ;

// Directions
TD : 'TD' ;
TB : 'TB' ;
BT : 'BT' ;
RL : 'RL' ;
LR : 'LR' ;

// Brackets - enter special modes
LSQUARE : '[' -> pushMode(INSIDE_BRACKETS) ;
LPAREN : '(' -> pushMode(INSIDE_PARENS) ;
LBRACE : '{' -> pushMode(INSIDE_BRACES) ;

// Arrows
ARROW : '-->' ;
ARROW_LABELED : '-->|' (~'|')* '|' ;

// Comments
COMMENT_LINE : '%%' ~[\r\n]* ;

// Init blocks
INIT_START : '%%{init:' -> pushMode(INSIDE_INIT) ;

// Punctuation
COMMA : ',' ;
COLON : ':' ;
SEMICOLON : ';' ;

// Identifiers (node IDs, class names, etc.)
IDENTIFIER : [a-zA-Z_][a-zA-Z0-9_]* ;

// CSS-like content for classDef
CSS_CONTENT : 'fill:' ~[ \t\r\n,;]+
            | 'stroke:' ~[ \t\r\n,;]+
            | 'stroke-width:' ~[ \t\r\n,;]+
            | 'color:' ~[ \t\r\n,;]+
            | '#' [0-9a-fA-F]+
            | [a-zA-Z0-9#.-]+
            ;

// =============================================================================
// INSIDE_BRACKETS MODE
// =============================================================================

mode INSIDE_BRACKETS;

// Preserve ALL content inside brackets, including whitespace
NODE_CONTENT : (~']')+ ;

// Exit brackets mode
RSQUARE : ']' -> popMode ;

// =============================================================================
// INSIDE_PARENS MODE  
// =============================================================================

mode INSIDE_PARENS;

// Preserve ALL content inside parentheses
PAREN_CONTENT : (~')')+ ;

// Exit parens mode
RPAREN : ')' -> popMode ;

// =============================================================================
// INSIDE_BRACES MODE
// =============================================================================

mode INSIDE_BRACES;

// Preserve ALL content inside braces
BRACE_CONTENT : (~'}')+ ;

// Exit braces mode  
RBRACE : '}' -> popMode ;

// =============================================================================
// INSIDE_INIT MODE
// =============================================================================

mode INSIDE_INIT;

// Preserve content inside init blocks
INIT_CONTENT : (~'}')+ ;

// Exit init mode
INIT_END : '}%%' -> popMode ;