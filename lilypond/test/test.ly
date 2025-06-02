\version "2.25.26"

% docker run -v ".:/work" codello/lilypond:dev --svg -I /work/includes test/test_ties.ly 1>logs/test_ties.log 2>&1 && mv test_ties*.* target

\include "test-main.ly"
\include "tie-attributes.ily"
\include "highlight-bars.ily"  % ADD THIS LINE!

#(define is-svg?
   (equal? (ly:get-option 'backend) 'svg))

\header {
  tagline = ##f
}

\book {
  \paper {
    indent = 0
    page-breaking = #(if is-svg?
                         ly:one-page-breaking
                         ly:page-turn-breaking)
  }

  \score {
    \Qwe
    \layout {
      \context {
        \Voice
        \consists \Tie_grob_engraver
      }
      \context {
        \Staff
        % Add measure highlighting engravers (creates transparent rectangles with data-bar attributes)
        \consists #Simple_highlight_engraver
        \consists Staff_highlight_engraver
        % Add bar timing collector (adds timing data to SVG attributes)
        \consists #Bar_timing_collector
      }

      \context {
        \Score
        % Add data-bar and data-bar-time attributes to rectangles
        \override StaffHighlight.after-line-breaking = #add-data-bar-to-highlight
      }
    }
  }
}