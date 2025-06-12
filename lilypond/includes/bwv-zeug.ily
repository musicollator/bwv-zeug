\version "2.25.26"

\include "tie-attributes.ily"
\include "highlight-bars.ily"

\header {
  tagline = ##f  % Removes LilyPond version info
}

#(set-global-staff-size 18) % Slightly smaller staff

% Define a helper to detect SVG mode
#(define is-svg?
   (equal? (ly:get-option 'backend) 'svg))

#(if (not is-svg?)
     (set-global-staff-size 16))

onePagePaper = \paper {
  indent = 0
  page-breaking = #(if is-svg?
                       ly:one-page-breaking
                       ly:one-page-breaking) % ly:page-turn-breaking

  line-width = #(if is-svg?
                    (* 260 mm)
                    (* 160 mm))

  paper-width = #(if is-svg?
                     (* 270 mm)
                     (* 210 mm))
}

oneLinePaper = \paper {
  indent = 0
  line-width = 20000\mm       % absurdly wide
  page-breaking = #ly:one-line-breaking
  systems-per-page = 1
  print-page-number = ##f
}

onePageLayout = \layout {
  % Apply larger note heads only for SVG output
  #(if is-svg?
       (ly:parser-include-string
        "\\override NoteHead.font-size = #2")
       )
  \context {
    \Voice
    \override StringNumber.stencil = ##f
  }
  % Apply simple highlighting only for SVG output
  #(if is-svg?
       (ly:parser-include-string
        "\\context {
               \\Staff
               \\consists #Simple_highlight_engraver
               \\consists Staff_highlight_engraver
               \\consists #Bar_timing_collector
             }
             \\context {
               \\Score
               \\override StaffHighlight.after-line-breaking = #add-data-bar-to-highlight
             }")
       )
}

oneLineLayout = \layout {
  \context {
    \Voice
    \override StringNumber.stencil = ##f
  }
  \context {
    \Voice
    \consists \Tie_grob_engraver
  }
}

% Move Staff_performer from Staff to Voice context
midiStaffPerformerToVoiceContext = \midi {
  \context {
    \Staff
    \remove "Staff_performer"
  }
  \context {
    \Voice
    \consists "Staff_performer"
  }
  \context {
    \Score
    midiChannelMapping = #'instrument
  }
}
