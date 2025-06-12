\version "2.24.0"

% docker run -v ".:/work" codello/lilypond:dev --svg ties_chord.ly

\include "tie-attributes-chords.ily"
\include "tie-attributes-chords-error-detection.ily"

\header {
  title = "Chord Tie Investigation"
  subtitle = "Debugging how chord ties work in LilyPond"
}

\score {
  {
    \clef treble
    \time 2/4
    
    % Single note tie for comparison
    c'2~ | c'2 |
    
    % Simple chord tie (all notes tied, should raise exception)
    <c' e' g'>2~ | <c' e' g'>2 |
    
    % Internal notes in chord tie (only some notes tied)
    <c' e'~ g'>2 | <c' e' g'>2 |
    
    \bar "|."
  }
  
  \layout {
    \context {
      \Voice
      \consists \Chord_tie_debug_engraver
      \consists \Tie_error_detection_engraver
    }
  }
}