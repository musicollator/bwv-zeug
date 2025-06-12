\version "2.24.0"

% cd lilypond
% docker run -v ".:/work" codello/lilypond:dev --svg -I /work/includes test/test_ties_chain.ly 1>logs/test_ties_chain.log 2>&1 && mv test_ties_chain*.* target
% cd ..
% python python/extract_ties.py -i lilypond/target/test_ties_chain.svg -o ties.csv

\include "tie-attributes.ily"

\header {
  title = "Simple Tie Test"
  subtitle = "Testing ties within measure, across measures, and chords"
}

\score {
  {
    \clef treble
    \time 4/4
    
    % 1. Tie within measure
    c'2~ c'4 d'4 |
    
    % 2. Tie spanning 2 measures  
    e'1~ |
    e'2 f'2 |
    
    % 3. Simple tie chain (3 notes)
    g'2~ g'2~ |
    g'4 a'4 r2 |
    
    % 4. Tie chain spanning 2 measures  
    g'2~ g'2~ |
    g'4 a'4 r2 |

    \bar "|."
  }
  
  \layout {
    \context {
      \Voice
      \consists \Tie_grob_engraver
    }
  }
}