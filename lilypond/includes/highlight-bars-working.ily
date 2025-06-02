% highlight-bars.ily
% Auto-highlight each measure with a cycling color.
% Includes special handling for pickup measures (\partial)
% Now accepts parameters for colors and color selection logic

#(define* (make-auto-measure-highlight-engraver
           #:optional
           (colors '("lightblue" "lightgreen" "lightyellow" "lightpink"))
           (color-index-fn #f))
   "Create an auto measure highlight engraver with customizable colors and indexing.
   
   Arguments:
   - colors: list of color strings (default: standard 4-color cycle)
   - color-index-fn: function that takes bar-number and returns color index
                     (default: simple modulo cycling)
   
   Usage examples:
   1. Default colors: (make-auto-measure-highlight-engraver)
   2. Custom colors: (make-auto-measure-highlight-engraver '(\"red\" \"blue\" \"green\"))
   3. Custom colors + indexing: (make-auto-measure-highlight-engraver 
                                  '(\"red\" \"blue\" \"green\")
                                  (lambda (bar) (if (even? bar) 0 1)))"

   (let ((default-color-index-fn (lambda (bar-num colors-list)
                                   (modulo bar-num (length colors-list)))))
     (lambda (context)
       (let ((last-bar -1)
             (color-list colors)
             (get-color-index (or color-index-fn default-color-index-fn)))
         (make-engraver
          ((process-music engraver)
           (let* ((raw-bar     (ly:context-property context 'currentBarNumber 0))
                  (pos         (ly:context-property context 'measurePosition (ly:make-moment 0)))
                  ;; Treat negative measure positions (pickup) as bar 0
                  (current-bar (if (negative? (ly:moment-main-numerator pos)) 0 raw-bar)))

             ;; Debug: print bar status
             ;; (display
             ;;   (format #f ">>> raw = ~a, moment = ~a, numerator = ~a~%"
             ;;           raw-bar pos (ly:moment-main-numerator pos)))
             ;; (display (format #f ">>> Tick: raw = ~a, effective = ~a, pos = ~a, last = ~a~%"
             ;;                  raw-bar current-bar pos last-bar))

             (when (> current-bar last-bar)
               ;; (newline)
               (let* ((color-idx (get-color-index current-bar color-list))
                      (color (list-ref color-list color-idx))
                      (start (ly:make-stream-event
                              (ly:make-event-class 'staff-highlight-event)
                              (list (cons 'span-direction START)
                                    (cons 'color color)
                                    (cons 'bar-number current-bar)))))
                 ;; (display (format #f ">>> Highlighting bar ~a with ~a" current-bar color))
                 (ly:broadcast (ly:context-event-source context) start))
               (set! last-bar current-bar)))))))))

% Convenience function for backward compatibility
Auto_measure_highlight_engraver = #(make-auto-measure-highlight-engraver)

% Example usage functions for common patterns:

#(define (make-alternating-highlight-engraver color1 color2)
   "Create engraver that alternates between two colors"
   (make-auto-measure-highlight-engraver
    (list color1 color2)))

#(define (make-conditional-highlight-engraver colors condition-fn)
   "Create engraver with colors chosen by a condition function.
   condition-fn should take bar-number and return color index"
   (make-auto-measure-highlight-engraver colors condition-fn))

#(define (make-grouping-highlight-engraver colors group-size)
   "Create engraver that groups measures (e.g., 4 bars per color)"
   (make-auto-measure-highlight-engraver
    colors
    (lambda (bar-num colors-list)
      (modulo (quotient bar-num group-size) (length colors-list)))))

% Keep the existing add-data-bar-to-highlight function unchanged
#(define (add-data-bar-to-highlight grob)
   (let* ((ev     (ly:grob-property grob 'cause))
          (clazz  (and ev (ly:event-property ev 'class)))
          (bar-num (and ev (ly:event-property ev 'bar-number))))
     ;; (display
     ;;  (format #f ">>>> event class: ~a, bar-num: ~a~%"
     ;;          clazz
     ;;          (if (number? bar-num) bar-num "NOT A NUMBER")))
     (when (and (list? clazz)
                (member 'staff-highlight-event clazz)
                (number? bar-num))
       (ly:grob-set-property! grob 'output-attributes
                              (list (cons "data-bar" (number->string bar-num)))))
     '()))