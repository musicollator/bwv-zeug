\version "2.25.26"

% docker run -v ".:/work" codello/lilypond:dev --svg -I /work/includes test/test_ties.ly 1>logs/test_ties.log 2>&1 && mv test_ties*.* target

\include "test-main.ly"
\include "tie-attributes.ily"

\header {
  title = "Test Ties with Data Attributes"
  subtitle = "Testing data-tie attributes on tied note heads with grouped staves"
}

\book {
  \paper {
    indent = 0
    line-width = 20000\mm       % absurdly wide
    page-breaking = #ly:one-line-breaking
    systems-per-page = 1
    print-page-number = ##f
  }

  \score {
    \Qwe
    \layout {
      \context {
        \Voice
        \consists \Tie_grob_engraver
      }
    }

    \midi { }
  }

}
