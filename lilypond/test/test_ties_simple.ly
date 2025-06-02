\version "2.25.26"

% docker run -v ".:/work" codello/lilypond:dev --svg test_ties_simple.ly 1>test_ties_simple.log 2>&1

\include "tie-attributes.ily"

\header {
  title = "Simple Tie Test"
  subtitle = "Minimal test for debugging tie attributes"
}

% Very simple test - just one tie
\score {
  {
    \clef treble
    \time 2/4
    
    % Just one simple tie
    c'2~ | c'4 r4 |
    % Just 2 ties
    { c'2~ | c'2~ | c'4 r4 }
    
    \bar "|."
  }
  
  \layout {
    \context {
      \Voice
      \consists \Tie_grob_engraver
    }
  }
}