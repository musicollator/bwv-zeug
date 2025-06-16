\version "2.25.26"

\include "bwv-zeug.ily"

\include "bwv245-main.ly"

% One-line score for notehead extraction
\book {
  \oneLinePaper
  \score {
    {
      \tempo 4 = 70
      \bwv
    }
    \oneLineLayout
    \midiStaffPerformerToVoiceContext
  }
}