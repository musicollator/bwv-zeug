\version "2.25.26"

\include "bwv-zeug.ily"

\include "test-main.ly"

% Formatted one-pager for display
\book {
  \bookOutputName "test"
  \onePagePaper
  \score {
    \bwv
    \layout {
      \onePageLayout
    }
  }
}
