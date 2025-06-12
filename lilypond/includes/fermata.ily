#(define-public simple-fermata-data-engraver
  (lambda (context)
    (let ((current-fermata #f)
          (current-notes '()))
      
      `((listeners
         ;; Listen for note events
         (note-event . ,(lambda (engraver event)
                         (set! current-notes (cons event current-notes))))
         
         ;; Listen for script/articulation events  
         (script-event . ,(lambda (engraver event)
                           (if (eq? (ly:event-property event 'articulation-type) 'fermata)
                               (set! current-fermata #t)))))
        
        (acknowledgers
         ;; Mark note heads when fermata is present
         (note-head-interface . ,(lambda (engraver grob source-engraver)
                                  (if current-fermata
                                      (begin
                                        (ly:message "Marking note head with fermata data")
                                        (ly:grob-set-property! grob 'output-attributes
                                                               `((data-fermata . "true"))))))))
        
        (stop-translation-timestep . ,(lambda (engraver)
                                       ;; Reset for next timestep
                                       (set! current-fermata #f)
                                       (set! current-notes '())))))))
