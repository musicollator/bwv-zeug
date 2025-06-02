\version "2.25.26"

% docker run -v ".:/work" codello/lilypond:dev --svg -I /work/includes test/test_ties.ly 1>logs/test_ties.log 2>&1 && mv test_ties*.* target

\include "test-main.ly"

% Display the absolute notation
#(display "=== SOPRANO ABSOLUTE NOTATION ===\n")
\displayLilyMusic \lower
#(display "=== END SOPRANO ===\n")