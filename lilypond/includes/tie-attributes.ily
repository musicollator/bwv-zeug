%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% tie-attributes.ily
%
% LILYPOND INCLUDE FILE - Note Tie Relationship System
%
% PURPOSE:
% Adds data attributes to establish tie relationships in the SVG output. This
% enables interactive applications to highlight tied note sequences and
% understand musical connections.
%
% FEATURES:
% - Handles complex tie chains (start, end, both roles)
% - Adds data-tie-role, data-tie-to, and data-tie-from attributes
% - Works with middle notes that are both tie endings and beginnings
% - Uses internal location-based identification system
%
% ALGORITHM:
% 1. Extract source file location from note heads
% 2. Generate internal identifiers from location data
% 3. Determine tie role (start, end, both)
% 4. Add appropriate data attributes to SVG elements
%
% DATA ATTRIBUTES ADDED:
% - data-tie-role: "start", "end", or "both"
% - data-tie-to: Reference to target note identifier (for start/both)
% - data-tie-from: Reference to source note identifier (for end/both)
%
% USAGE:
% Include this file and add to your Voice context:
%   \layout {
%     \context {
%       \Voice
%       \consists \Tie_grob_engraver
%     }
%   }
%
% OUTPUT:
% SVG note elements with tie relationship data that can be processed
% by JavaScript for interactive highlighting and musical analysis.
%
% PART OF: BWV LilyPond Project - Shared include for all BWV scores
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

#(define (find-note-head-in-bound bound-obj)
   "Find a NoteHead grob within or associated with a bound object"
   (cond
    ((not (ly:grob? bound-obj)) #f)
    ((memq 'note-head-interface (ly:grob-interfaces bound-obj))
     bound-obj)
    ((memq 'note-column-interface (ly:grob-interfaces bound-obj))
     (let ((note-heads (ly:grob-object bound-obj 'note-heads)))
       (if (ly:grob-array? note-heads)
           (let ((heads-list (ly:grob-array->list note-heads)))
             (if (pair? heads-list)
                 (car heads-list)
                 #f))
           #f)))
    (else #f)))

#(define (safe-add-attribute attrs key value)
   "Add attribute to alist, replacing if it already exists"
   (let ((existing (assoc key attrs)))
     (if existing
         (acons key value (alist-delete key attrs))
         (acons key value attrs))))

#(define (extract-location-string origin)
   "Extract clean file:line:col string from LilyPond location object"
   (if origin
       (let ((location-str (format #f "~a" origin)))
         ;; Strip "#<location " prefix and ">" suffix
         ;; Input: "#<location test-main.ly:30:5>"
         ;; Output: "test-main.ly:30:5"
         (let ((prefix "#<location ")
               (suffix ">"))
           (if (and (> (string-length location-str) (+ (string-length prefix) (string-length suffix)))
                    (string=? (substring location-str 0 (string-length prefix)) prefix)
                    (string=? (substring location-str (- (string-length location-str) 1)) suffix))
               (substring location-str 
                         (string-length prefix)
                         (- (string-length location-str) 1))
               #f)))
       #f))

#(define (hex-hash location-str)
   "Generate a pure hex hash from location string"
   (if location-str
       (string-append "x" (string-upcase (substring (number->string (string-hash location-str) 16) 0 8)))
       #f))

#(define (get-note-origin note-head)
   "Get the source file origin from a note head's cause"
   (let ((cause (ly:grob-property note-head 'cause #f)))
     (when (and cause (ly:stream-event? cause))
       (ly:event-property cause 'origin #f))))

#(define (make-tie-grob-engraver)
   "Create an engraver with pure hex hash IDs"
   (lambda (context)
     (let ((processed-ties '()))
       
       (make-engraver
        (end-acknowledgers
         ((tie-interface engraver grob source-engraver)
          (let* ((left-bound (ly:spanner-bound grob LEFT))
                 (right-bound (ly:spanner-bound grob RIGHT)))
            
            (when (and left-bound right-bound
                       (ly:grob? left-bound)
                       (ly:grob? right-bound))
              (let ((left-note-head (find-note-head-in-bound left-bound))
                    (right-note-head (find-note-head-in-bound right-bound)))
                
                (when (and left-note-head right-note-head
                           (ly:grob? left-note-head)
                           (ly:grob? right-note-head))
                  
                  (let ((left-origin (get-note-origin left-note-head))
                        (right-origin (get-note-origin right-note-head)))
                    
                    (when (and left-origin right-origin)
                      (let ((left-location (extract-location-string left-origin))
                            (right-location (extract-location-string right-origin)))
                        
                        (when (and left-location right-location)
                          ; (format #t "Creating tie: ~a -> ~a~%" left-location right-location)
                          
                          (let ((left-id (hex-hash left-location))
                                (right-id (hex-hash right-location)))
                            
                            (when (and left-id right-id)
                              ;; Add attributes to left note head (check for existing role)
                              (let ((left-attrs (ly:grob-property left-note-head 'output-attributes '())))
                                (set! left-attrs (safe-add-attribute left-attrs "id" left-id))
                                (set! left-attrs (safe-add-attribute left-attrs "data-tie-role" 
                                                                   (if (assoc "data-tie-role" left-attrs) "both" "start")))
                                (set! left-attrs (safe-add-attribute left-attrs "data-tie-to" (string-append "#" right-id)))
                                (ly:grob-set-property! left-note-head 'output-attributes left-attrs))
                              
                              ;; Add attributes to right note head (check for existing role)
                              (let ((right-attrs (ly:grob-property right-note-head 'output-attributes '())))
                                (set! right-attrs (safe-add-attribute right-attrs "id" right-id))
                                (set! right-attrs (safe-add-attribute right-attrs "data-tie-role"
                                                                    (if (assoc "data-tie-role" right-attrs) "both" "end")))
                                (set! right-attrs (safe-add-attribute right-attrs "data-tie-from" (string-append "#" left-id)))
                                (ly:grob-set-property! right-note-head 'output-attributes right-attrs))
                              
                              (set! processed-ties (cons (list left-location right-location) processed-ties))))))))))))))))))
                              
Tie_grob_engraver = #(make-tie-grob-engraver)