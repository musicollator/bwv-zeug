# Interactive LilyPond Score System

An advanced LilyPond system for creating **interactive musical scores** with precise **MIDI synchronization** and real-time **visual highlighting**.

## Core Concept

The system generates **two SVG outputs** from the **same musical content**:

1. **Display Score** (`*.ly`) - Interactive score for user viewing with bar highlighting
2. **One-Line Score** (`*_ly_one_line.ly`) - Single-line layout for precise coordinate mapping

**⚠️ CRITICAL**: Both outputs must contain **identical musical content** for synchronization to work.

## File Architecture

### 🔧 Shared Include Files (.ily)
Reusable components for all projects:

- **[`highlight-bars.ily`](includes/highlight-bars.ily)** - Creates SVG rectangles with bar timing data attributes
- **[`tie-attributes.ily`](includes/tie-attributes.ily)** - Generates unique IDs and relationship data for tied notes

### 🎵 Project Files (per musical piece)
Each musical piece requires exactly **three files**:

- **`*_ly_main.ly`** - **Pure musical content only** (no book/score/paper/layout structures) → [**test-main.ly**](test/test-main.ly)
- **`*.ly`** - **Display wrapper** with interactive highlighting features → [**test.ly**](test/test.ly)
- **`*_ly_one_line.ly`** - **Synchronization wrapper** with one-line layout and tie data → [**test_ly_one_line.ly**](test/test_ly_one_line.ly)

**Note**: `*_ly_main.ly` is the **entry point** for musical content that can **differ wildly among projects** - it remains independent of the interactive system and **must not interfere** with wrapper-defined structures.

## Essential Pattern

### 1. Musical Content Definition (`*_ly_main.ly`)
**Pure musical content** with **strict constraints** → [**test-main.ly**](test/test-main.ly):
```lilypond
% ALLOWED: Musical definitions, variables, functions
piece = {
  \key c \major
  \time 4/4
  c'4 d'4 e'4 f'4 |
  g'2 a'2 |
}

otherPart = {
  c2 d2 |
}

% Musical helper functions are OK
myFunction = #(define-music-function () () #{ c'4 d'4 #})

% FORBIDDEN: \book, \score, \paper, \layout, global settings
% NO: \book { ... }
% NO: \score { ... }  
% NO: \paper { ... }
% NO: \layout { ... }
% NO: #(set-global-staff-size 18)
```

### 2. Display Score (`*.ly`)
Embeds the music with **highlighting features** → [**test.ly**](test/test.ly):
```lilypond
\include "*_ly_main.ly"
\include "highlight-bars.ily"

\score {
  \piece
  \layout {
    \context {
      \Staff
      \consists #Simple_highlight_engraver
      \consists Staff_highlight_engraver
      \consists #Bar_timing_collector
    }
    \context {
      \Score
      \override StaffHighlight.after-line-breaking = #add-data-bar-to-highlight
    }
  }
}
```

### 3. One-Line Score (`*_ly_one_line.ly`)
Embeds the **same music** with **tie tracking** and **single-line layout** → [**test_ly_one_line.ly**](test/test_ly_one_line.ly):
```lilypond
\include "*_ly_main.ly"
\include "tie-attributes.ily"

\book {
  \paper {
    indent = 0
    line-width = 20000\mm
    page-breaking = #ly:one-line-breaking
    systems-per-page = 1
    print-page-number = ##f
  }
  
  \score {
    \piece
    \layout {
      \context {
        \Voice
        \consists \Tie_grob_engraver
      }
    }
  }
}
```

## Key Features

### 🎯 Bar Highlighting
- **SVG rectangles** with `data-bar` and timing attributes
- **JavaScript controllable** for real-time highlighting during playback
- **Invisible by default** - styled via CSS/JavaScript

### 🔗 Tie Relationships  
- **Unique hex IDs** for each note based on source location
- **Relationship attributes**: `data-tie-role`, `data-tie-to`, `data-tie-from`
- **Complex chains supported** - notes can be both tie starts and ends

### 📐 Coordinate Synchronization
- **One-line layout** eliminates line-break coordinate complications
- **Precise mapping** between MIDI events and SVG note positions
- **Cross-reference** between display and synchronization layouts