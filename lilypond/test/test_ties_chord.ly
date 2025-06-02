\version "2.24.0"

% docker run -v ".:/work" codello/lilypond:dev --svg test_ties_simple.ly 1>test_ties_simple.log 2>&1


\include "_tie-attributes-chords-experimental.ily"
\include "_tie-attributes-chords-error-detection-experimental.ily"

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