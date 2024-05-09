(defun print_int (x)
  (progn
    (setq num_to_div 1)
    (while (+ (> (/ x num_to_div) 10) (= (/ x num_to_div) 10))
      (setq num_to_div (* num_to_div 10)))
    (if (= x 0)
      (print_char 48)
      (while (> x 0)
        (progn
          (print_char (+ 48 (/ x num_to_div)))
          (if (* (= (% x num_to_div) 0) (> num_to_div 1))
            (progn
              (while (> num_to_div 1)
                (progn
                  (print_char 48)
                  (setq num_to_div (/ num_to_div 10)))))
            (0))
          (setq x (% x num_to_div))
          (setq num_to_div (/ num_to_div 10)))))))