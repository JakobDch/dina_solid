import { useState, useEffect, useCallback } from 'react';

interface UseCounterOptions {
  end: number;
  start?: number;
  duration?: number;
  delay?: number;
  easing?: 'linear' | 'easeOut' | 'easeInOut';
}

export const useCounter = ({
  end,
  start = 0,
  duration = 2000,
  delay = 0,
  easing = 'easeOut'
}: UseCounterOptions) => {
  const [count, setCount] = useState(start);
  const [isStarted, setIsStarted] = useState(false);
  const [isComplete, setIsComplete] = useState(false);

  const easingFunctions = {
    linear: (t: number) => t,
    easeOut: (t: number) => 1 - Math.pow(1 - t, 3),
    easeInOut: (t: number) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
  };

  const startCounting = useCallback(() => {
    setIsStarted(true);
  }, []);

  const reset = useCallback(() => {
    setCount(start);
    setIsStarted(false);
    setIsComplete(false);
  }, [start]);

  useEffect(() => {
    if (!isStarted) return;

    const startTime = performance.now() + delay;
    let animationFrame: number;

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;

      if (elapsed < 0) {
        animationFrame = requestAnimationFrame(animate);
        return;
      }

      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = easingFunctions[easing](progress);
      const currentCount = Math.round(start + (end - start) * easedProgress);

      setCount(currentCount);

      if (progress < 1) {
        animationFrame = requestAnimationFrame(animate);
      } else {
        setIsComplete(true);
      }
    };

    animationFrame = requestAnimationFrame(animate);

    return () => {
      if (animationFrame) {
        cancelAnimationFrame(animationFrame);
      }
    };
  }, [isStarted, start, end, duration, delay, easing]);

  return {
    count,
    isComplete,
    startCounting,
    reset
  };
};

export default useCounter;
