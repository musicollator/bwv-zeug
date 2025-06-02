% tie-attributes-chords.ily
% Investigation of chord tie behavior in LilyPond
% Separate file to debug chord ties without breaking single-note functionality

#(define (make-chord-tie-debug-engraver)
   "Debug engraver to investigate how chord ties work"
   (lambda (context)
     (let ((note-counter 0))
       (make-engraver
        (acknowledgers
         ((note-head-interface engraver grob source-engraver)
          (display (format #f ">>> CHORD DEBUG: Note head found: ~a\n" grob))
          (let* ((cause (ly:grob-property grob 'cause))
                 (pitch (and cause (ly:event-property cause 'pitch #f)))
                 (articulations (and cause (ly:event-property cause 'articulations '())))
                 (music-cause (and cause (ly:event-property cause 'music-cause #f)))
                 (music-articulations (and music-cause (ly:music-property music-cause 'articulations '())))
                 (parent-event (and cause (ly:event-property cause 'parent-event #f)))
                 (chord-elements (and music-cause (ly:music-property music-cause 'elements '()))))
            
            (display (format #f ">>> CHORD DEBUG: Pitch: ~a\n" pitch))
            (display (format #f ">>> CHORD DEBUG: Stream articulations: ~a\n" articulations))
            (display (format #f ">>> CHORD DEBUG: Music articulations: ~a\n" music-articulations))
            (display (format #f ">>> CHORD DEBUG: Parent event: ~a\n" parent-event))
            (display (format #f ">>> CHORD DEBUG: Music cause type: ~a\n" 
                             (and music-cause (ly:music-property music-cause 'name))))
            (display (format #f ">>> CHORD DEBUG: Chord elements count: ~a\n" (length chord-elements)))
            
            ;; Look for ties in chord elements
            (when (> (length chord-elements) 0)
              (display ">>> CHORD DEBUG: Examining chord elements:\n")
              (for-each (lambda (element)
                          (display (format #f ">>>   Element: ~a\n" (ly:music-property element 'name)))
                          (display (format #f ">>>   Element articulations: ~a\n" 
                                          (ly:music-property element 'articulations '()))))
                        chord-elements))
            
            ;; Check if this note head is part of an EventChord
            (let ((music-name (and music-cause (ly:music-property music-cause 'name))))
              (when (eq? music-name 'EventChord)
                (display ">>> CHORD DEBUG: This note is part of an EventChord!\n")
                (display (format #f ">>> CHORD DEBUG: EventChord articulations: ~a\n" music-articulations))))))
         
         ((tie-interface engraver grob source-engraver)
          (display ">>> CHORD DEBUG: Tie grob found!\n")
          (display (format #f ">>> CHORD DEBUG: Tie cause: ~a\n" (ly:grob-property grob 'cause)))
          (display (format #f ">>> CHORD DEBUG: Tie details: ~a\n" (ly:grob-property grob 'details))))
         
         ((event-chord-interface engraver grob source-engraver)
          (display ">>> CHORD DEBUG: EventChord interface found!\n")))))))

#(define (make-simple-chord-test-engraver)
   "Simple test to see what gets acknowledged during chord ties"
   (lambda (context)
     (make-engraver
      (acknowledgers
       ((note-head-interface engraver grob source-engraver)
        (display ">>> SIMPLE: Note head\n"))
       
       ((tie-interface engraver grob source-engraver)
        (display ">>> SIMPLE: Tie\n"))
       
       ((chord-interface engraver grob source-engraver)
        (display ">>> SIMPLE: Chord interface\n"))
       
       ((event-chord-interface engraver grob source-engraver)
        (display ">>> SIMPLE: EventChord interface\n"))))))

Chord_tie_debug_engraver = #(make-chord-tie-debug-engraver)
Simple_chord_test_engraver = #(make-simple-chord-test-engraver)