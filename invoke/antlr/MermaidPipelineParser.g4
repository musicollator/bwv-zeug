parser grammar MermaidPipelineParser;

options {
    tokenVocab = MermaidPipelineLexer;
}

// =============================================================================
// PARSER RULES
// =============================================================================

diagram
    : graphDeclaration statement*
    ;

graphDeclaration
    : FLOWCHART direction
    | GRAPH direction
    ;

direction
    : TD | TB | BT | RL | LR
    ;

statement
    : nodeDeclaration
    | edge
    | classDef
    | classAssignment
    | initBlock
    | comment
    ;

nodeDeclaration
    : nodeId nodeShape?
    ;

nodeShape
    : LSQUARE nodeContent RSQUARE     // [content]
    | LPAREN nodeContent RPAREN       // (content)
    | LBRACE nodeContent RBRACE       // {content}
    ;

nodeContent
    : NODE_CONTENT
    | PAREN_CONTENT  
    | BRACE_CONTENT
    ;

edge
    : nodeId edgeType nodeId
    ;

edgeType
    : ARROW
    | ARROW_LABELED
    ;

nodeId
    : IDENTIFIER
    ;

classDef
    : CLASSDEF IDENTIFIER cssContent
    ;

cssContent
    : CSS_CONTENT+
    ;

classAssignment
    : CLASS classNodeList IDENTIFIER
    ;

classNodeList
    : nodeId (COMMA nodeId)*
    ;

initBlock
    : INIT_START initContent INIT_END
    ;

initContent
    : INIT_CONTENT
    ;

comment
    : COMMENT_LINE
    ;