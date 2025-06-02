% tie-error-detection.ily
% Error detection engraver for unsupported full chord ties
% Use this alongside tie-attributes.ily to catch problematic chord ties

#(define (make-tie-error-detection-engraver)
   "Engraver that detects unsupported full chord ties and throws clear errors"
   (lambda (context)
     (let ((ties-per-moment 0)
           (notes-per-moment 0)
           (notes-with-ties-per-moment 0)
           (current-moment #f))
       (make-engraver
        (acknowledgers
         ((tie-interface engraver grob source-engraver)
          (let ((moment (ly:context-current-moment context)))
            (when (not (equal? current-moment moment))
              (set! current-moment moment)
              (set! ties-per-moment 0)
              (set! notes-per-moment 0)
              (set! notes-with-ties-per-moment 0))
            
            (set! ties-per-moment (+ ties-per-moment 1))))
         
         ((note-head-interface engraver grob source-engraver)
          (let* ((moment (ly:context-current-moment context))
                 (cause (ly:grob-property grob 'cause))
                 (music-cause (and cause (ly:event-property cause 'music-cause #f)))
                 (music-articulations (and music-cause (ly:music-property music-cause 'articulations '())))
                 (has-tie (any (lambda (art)
                                 (and (ly:music? art)
                                      (eq? (ly:music-property art 'name) 'TieEvent)))
                               music-articulations)))
            
            (when (not (equal? current-moment moment))
              (set! current-moment moment)
              (set! ties-per-moment 0)
              (set! notes-per-moment 0)
              (set! notes-with-ties-per-moment 0))
            
            (set! notes-per-moment (+ notes-per-moment 1))
            (when has-tie
              (set! notes-with-ties-per-moment (+ notes-with-ties-per-moment 1)))))
        
        ((end-translation-timestep engraver)
         (when (and (> ties-per-moment 1)                    ; Multiple ties exist
                    (= notes-with-ties-per-moment 0)         ; No notes have TieEvents  
                    (= ties-per-moment notes-per-moment))    ; Same number of ties as notes
           (ly:error "Full chord ties are not supported!

Found ~a tied notes in chord at measure ~a.

Use individual note ties instead:
❌ BAD:  <c' e' g'>2~ <c' e' g'>2
✅ GOOD: <c'~ e'~ g'~>2 <c' e' g'>2

Or use partial chord ties:
✅ GOOD: <c' e'~ g'>2 <c' e' g'>2

Full chord ties cannot be processed by the tie-attributes engraver.
Please rewrite using individual ties or partial chord ties."
                     ties-per-moment
                     (ly:context-property context 'currentBarNumber 1)))
         
         (set! ties-per-moment 0)
         (set! notes-per-moment 0)
         (set! notes-with-ties-per-moment 0)))))))

Tie_error_detection_engraver = #(make-tie-error-detection-engraver)

% Usage:
% \layout {
%   \context {
%     \Voice
%     \consists \Tie_grob_engraver           % Main functionality
%     \consists \Tie_error_detection_engraver % Error detection
%   }
% }