% BWV 245 - O große Lieb, o Lieb ohn alle Maße
% Arranged for SATB (4 staves)
\version "2.25.26"

% Global settings
global = {
  \key g \minor
  \time 4/4
  \tempo 4 = 70
}

% Soprano
sopranoMusic = {
  \global
  {
    \partial 4
    g'4
    | % 2
    g' g' fis' \fermata d'
    | % 3
    g' a' bes' bes'
    | % 4
    c'' bes' a' \fermata a'
    | % 5
    bes' c'' d''8 c'' bes'4
    | % 6
    ees'' ees'' d'' des''8 c''
    | % 7
    c''2 bes'4 \fermata bes'
    | % 8
    a' g' f' d'8 ees'
    | % 9
    f'4 f' g' f'
    | % 10
    ees'2 d'4 \fermata d''
    | % 11
    c'' bes'8 a' a'2
    | % 12
    g'2. \fermata \bar "|."
  }
}

sopranoLyrics = \lyricmode {
  O
  gro -- ße Lieb, o
  Lieb' ohn al -- le
  Ma -- a -- ße, die
  dich ge -- bra -- cht -- auf
  die -- se Mar -- te -- r stra -- ße, ich
  leb -- te mit de -- r
  Welt in Lust und
  Freu -- den, und
  du muß -- t -- lei --
  den.
}

% Alto
altoMusic = {
  \global
  {
    \partial 4
    d'4
    | % 2
    ees'8 d' c'4 d' a
    | % 3
    d'8 e' fis'4 g' g'
    | % 4
    a' g' fis' fis'
    | % 5
    g' a' bes' f'
    | % 6
    g'8 a' bes'4 bes' bes'
    | % 7
    bes' a' f' g'8 f'
    | % 8
    ees' d' e'4 d' a
    | % 9
    d'8 ees' f'4 f'8 ees' ees' d'
    | % 10
    d' c'16 bes c'4 bes bes'
    | % 11
    a' g' g' fis'
    | % 12
    d'2.
  }
}

% Tenor
tenorMusic = {
  \global
  {
    \partial 4
    bes4
    | % 2
    bes a8 g a4 fis
    | % 3
    g c' d' d'
    | % 4
    ees' d' d' d'
    | % 5
    d' ees' f'8 ees' d' c'
    | % 6
    bes4 bes8 c' d' bes g'4
    | % 7
    f'4. ees'8 d'4 d'
    | % 8
    c' bes a f
    | % 9
    bes bes bes a
    | % 10
    bes f f f'
    | % 11
    ees' d' e' d'8 c'
    | % 12
    b2.
  }
}

% Bass
bassMusic = {
  \global
  {
    \partial 4
    g4
    | % 2
    c8 d ees4 d c
    | % 3
    bes, a, g, g
    | % 4
    fis g d d
    | % 5
    g c' bes aes
    | % 6
    g fis f e
    | % 7
    f2 bes,4 g,
    | % 8
    c cis d d8 c
    | % 9
    bes, c d bes, ees4 f
    | % 10
    g a bes bes
    | % 11
    fis g cis d
    | % 12
    g,2.
  }
}

% Score layout
bwv =
\new ChoirStaff <<
  \new Staff \with {
    instrumentName = "Soprano"
    shortInstrumentName = "S."
  } {
    \new Voice = "soprano" {
      \set Voice.midiInstrument = #"flute"
      \sopranoMusic
    }
  }

  \new Staff \with {
    instrumentName = "Alto"
    shortInstrumentName = "A."
  } {
    \new Voice = "alto" {
      \set Voice.midiInstrument = #"oboe"
      \altoMusic
    }
  }

  \new Staff \with {
    instrumentName = "Tenor"
    shortInstrumentName = "T."
    \clef "treble_8"
  } {
    \new Voice = "tenor" {
      \set Voice.midiInstrument = #"clarinet"
      \tenorMusic
    }
  }

  \new Staff \with {
    instrumentName = "Bass"
    shortInstrumentName = "B."
    \clef bass
  } {
    \new Voice = "bass" {
      \set Voice.midiInstrument = #"bassoon"
      \bassMusic
    }
  }

  \new Lyrics \lyricsto "soprano" \sopranoLyrics
>>

