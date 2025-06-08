% highlight-bars.ily
% Clean version - creates clean SVG rectangles with timing data attributes
% JavaScript handles visibility and styling

#(define (make-simple-highlight-engraver)
   "Create a simple engraver that adds clean highlight rectangles with timing data."
   
   (lambda (context)
     (let ((last-bar -1))
       (make-engraver
        ((process-music engraver)
         (let* ((raw-bar     (ly:context-property context 'currentBarNumber 0))
                (pos         (ly:context-property context 'measurePosition (ly:make-moment 0)))
                (current-bar (if (negative? (ly:moment-main-numerator pos)) 0 raw-bar)))

           (when (> current-bar last-bar)
             (let ((start (ly:make-stream-event
                          (ly:make-event-class 'staff-highlight-event)
                          (list (cons 'span-direction START)
                                (cons 'color "#e7dfd0")
                                (cons 'bar-number current-bar)))))
               (ly:broadcast (ly:context-event-source context) start))
             (set! last-bar current-bar))))))))

% Define the engraver instance
#(define Simple_highlight_engraver (make-simple-highlight-engraver))

% Bar timing collector - collects raw LilyPond timing data
#(define bar-timing-data '())

#(define (make-bar-timing-collector)
   "Create an engraver that collects raw LilyPond timing information."
   
   (lambda (context)
     (let ((last-bar -1))
       (make-engraver
        ((process-music engraver)
         (let* ((raw-bar     (ly:context-property context 'currentBarNumber 0))
                (pos         (ly:context-property context 'measurePosition (ly:make-moment 0)))
                (current-bar (if (negative? (ly:moment-main-numerator pos)) 0 raw-bar))
                (current-moment (ly:context-current-moment context)))

           ;; Record timing when starting a new bar
           (when (and (> current-bar last-bar)
                      (equal? pos (ly:make-moment 0)))
             (let ((moment-main (ly:moment-main current-moment))
                   (moment-grace (ly:moment-grace current-moment)))
               (set! bar-timing-data 
                     (cons (list current-bar moment-main moment-grace) bar-timing-data))
               (set! last-bar current-bar)))))
        
        ; ((finalize engraver)
        ; (let ((sorted-timings (sort bar-timing-data (lambda (a b) (< (car a) (car b))))))
        ;   (display (format #f "Collected LilyPond bar timings: ~a\n" sorted-timings))))
        ))))

% Define the timing collector instance
#(define Bar_timing_collector (make-bar-timing-collector))

% Clean function that adds only the data attributes we need
#(define (add-data-bar-to-highlight grob)
   (let* ((ev     (ly:grob-property grob 'cause))
          (clazz  (and ev (ly:event-property ev 'class)))
          (bar-num (and ev (ly:event-property ev 'bar-number))))
     (when (and (list? clazz)
                (member 'staff-highlight-event clazz)
                (number? bar-num))
       
       ;; Find timing data for this bar
       (let ((timing-entry (assoc bar-num bar-timing-data)))
         (let ((attributes (list (cons "data-bar" (number->string bar-num)))))
           
           ;; Add timing attributes if available
           (when timing-entry
             (let ((moment-main (cadr timing-entry))
                   (moment-grace (caddr timing-entry)))
               (set! attributes 
                     (append attributes
                             (list (cons "data-bar-moment-main" (number->string moment-main))
                                   (cons "data-bar-moment-grace" (number->string moment-grace)))))))
           
           ;; Set only the data attributes we want
           (ly:grob-set-property! grob 'output-attributes attributes))))
     '()))