import { useState, useEffect, useCallback } from 'react';

interface UseTypewriterOptions {
  texts: string[];
  typingSpeed?: number;
  deletingSpeed?: number;
  pauseDuration?: number;
  loop?: boolean;
}

export const useTypewriter = ({
  texts,
  typingSpeed = 50,
  deletingSpeed = 30,
  pauseDuration = 2000,
  loop = true
}: UseTypewriterOptions) => {
  const [displayText, setDisplayText] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isTyping, setIsTyping] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isStarted, setIsStarted] = useState(false);

  const startTyping = useCallback(() => {
    setIsStarted(true);
  }, []);

  const reset = useCallback(() => {
    setDisplayText('');
    setCurrentIndex(0);
    setIsTyping(true);
    setIsDeleting(false);
    setIsPaused(false);
    setIsStarted(false);
  }, []);

  useEffect(() => {
    if (!isStarted || texts.length === 0) return;

    const currentText = texts[currentIndex];

    if (isPaused) {
      const pauseTimer = setTimeout(() => {
        setIsPaused(false);
        setIsDeleting(true);
      }, pauseDuration);
      return () => clearTimeout(pauseTimer);
    }

    if (isTyping && !isDeleting) {
      if (displayText.length < currentText.length) {
        const timer = setTimeout(() => {
          setDisplayText(currentText.slice(0, displayText.length + 1));
        }, typingSpeed);
        return () => clearTimeout(timer);
      } else {
        setIsTyping(false);
        setIsPaused(true);
      }
    }

    if (isDeleting) {
      if (displayText.length > 0) {
        const timer = setTimeout(() => {
          setDisplayText(displayText.slice(0, -1));
        }, deletingSpeed);
        return () => clearTimeout(timer);
      } else {
        setIsDeleting(false);
        setIsTyping(true);
        if (loop || currentIndex < texts.length - 1) {
          setCurrentIndex((prev) => (prev + 1) % texts.length);
        }
      }
    }
  }, [
    displayText,
    currentIndex,
    isTyping,
    isDeleting,
    isPaused,
    isStarted,
    texts,
    typingSpeed,
    deletingSpeed,
    pauseDuration,
    loop
  ]);

  return {
    displayText,
    isTyping: isTyping && !isPaused,
    isDeleting,
    isPaused,
    currentIndex,
    startTyping,
    reset
  };
};

export default useTypewriter;
