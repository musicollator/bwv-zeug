% bar-timing-exporter.ily
% Export accurate bar timing information from LilyPond compilation

#(define (make-bar-timing-exporter output-filename)
   "Create an engraver that tracks and exports bar timing information.
   output-filename: name of JSON file to create (e.g., 'bar-timings.json')"

   (lambda (context)
     (let ((bar-timings '())
           (last-bar -1))
       (make-engraver
        ((process-music engraver)
         (let* ((raw-bar     (ly:context-property context 'currentBarNumber 0))
                (pos         (ly:context-property context 'measurePosition (ly:make-moment 0)))
                (current-bar (if (negative? (ly:moment-main-numerator pos)) 0 raw-bar))
                (current-moment (ly:context-current-moment context)))

           ;; Record timing when we start a new bar (measurePosition = 0)
           (when (and (> current-bar last-bar)
                      (equal? pos (ly:make-moment 0)))
             (let ((time-seconds (ly:moment-main current-moment)))
               (set! bar-timings (cons (cons current-bar time-seconds) bar-timings))
               (set! last-bar current-bar)))))

        ((finalize engraver)
         ;; Export bar timings to JSON file when compilation finishes
         (let* ((sorted-timings (sort bar-timings (lambda (a b) (< (car a) (car b)))))
                (port (open-output-file output-filename))
                (timing-list (map cdr sorted-timings))
                (bar-numbers (map car sorted-timings)))

           ;; Write JSON format
           (display "{\n" port)
           (display "  \"barNumbers\": [" port)
           (display (string-join (map number->string bar-numbers) ", ") port)
           (display "],\n" port)
           (display "  \"barTimings\": [" port)
           (display (string-join (map number->string timing-list) ", ") port)
           (display "],\n" port)
           (display "  \"totalBars\": " port)
           (display (length timing-list) port)
           (display ",\n" port)
           (display "  \"lastBarTime\": " port)
           (display (if (null? timing-list) 0 (apply max timing-list)) port)
           (display "\n}" port)
           (close-output-port port)

           ;; Also display to console for debugging
           (display (format #f "\n=== Bar Timing Export ===\n"))
;;;; (display (format #f "Exported ~a bar timings to ~a\n"
;;;;           (length timing-list) output-filename))
;;;; (for-each (lambda (timing)
;;;;           (display (format #f "Bar ~a: ~a seconds\n"
;;;;                           (car timing) (cdr timing))))
;;;;         sorted-timings)
;;;; (display (format #f "=========================\n\n"))))))))

           % Convenience engraver for standard usage
           #(define Bar_timing_exporter
             (make-bar-timing-exporter "bar-timings.json"))

           % Optional: Create engraver with custom filename
           #(define (make-custom-timing-exporter filename)
             (make-bar-timing-exporter filename))

           % Optional: Create engraver that also includes tempo information
           #(define (make-detailed-timing-exporter output-filename)
             "Enhanced version that also captures tempo changes"

             (lambda (context)
               (let ((bar-timings '())
                     (tempo-changes '())
                     (last-bar -1))
                 (make-engraver
                  ((process-music engraver)
                   (let* ((raw-bar     (ly:context-property context 'currentBarNumber 0))
                          (pos         (ly:context-property context 'measurePosition (ly:make-moment 0)))
                          (current-bar (if (negative? (ly:moment-main-numerator pos)) 0 raw-bar))
                          (current-moment (ly:context-current-moment context))
                          (tempo       (ly:context-property context 'tempoWholesPerMinute)))

                     ;; Record bar timing
                     (when (and (> current-bar last-bar)
                                (equal? pos (ly:make-moment 0)))
                       (let ((time-seconds (ly:moment-main current-moment)))
                         (set! bar-timings (cons (cons current-bar time-seconds) bar-timings))
                         (set! last-bar current-bar)))

                     ;; Record tempo changes
                     (when (and (number? tempo)
                                (equal? pos (ly:make-moment 0)))
                       (let ((time-seconds (ly:moment-main current-moment)))
                         (set! tempo-changes (cons (cons time-seconds tempo) tempo-changes))))))

                  ((finalize engraver)
                   ;; Export detailed timing information
                   (let* ((sorted-timings (sort bar-timings (lambda (a b) (< (car a) (car b)))))
                          (sorted-tempos (sort tempo-changes (lambda (a b) (< (car a) (car b)))))
                          (port (open-output-file output-filename))
                          (timing-list (map cdr sorted-timings))
                          (bar-numbers (map car sorted-timings)))

                     ;; Write detailed JSON format
                     (display "{\n" port)
                     (display "  \"barNumbers\": [" port)
                     (display (string-join (map number->string bar-numbers) ", ") port)
                     (display "],\n" port)
                     (display "  \"barTimings\": [" port)
                     (display (string-join (map number->string timing-list) ", ") port)
                     (display "],\n" port)
                     (display "  \"totalBars\": " port)
                     (display (length timing-list) port)
                     (display ",\n" port)
                     (display "  \"tempoChanges\": [" port)
                     (for-each (lambda (tempo-change)
                                 (display (format #f "{\"time\": ~a, \"tempo\": ~a}"
                                                  (car tempo-change) (cdr tempo-change)) port))
                               sorted-tempos)
                     (display "],\n" port)
                     (display "  \"lastBarTime\": " port)
                     (display (if (null? timing-list) 0 (apply max timing-list)) port)
                     (display "\n}" port)
                     (close-output-port port))))))))

         % Enhanced engraver for complex pieces
         #(define Detailed_timing_exporter
           (make-detailed-timing-exporter "detailed-timings.json"))