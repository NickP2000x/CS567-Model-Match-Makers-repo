import { useEffect, useRef, useState } from 'react';
import type { Task } from '../../services/experiment.types';
import { remainingSeconds } from '../../services/taskTiming';

export function TaskCountdown({ task, onTimeout }: { task: Task; onTimeout: () => Promise<boolean> }) {
  const [seconds, setSeconds] = useState(() => task.deadline === null ? 0 : remainingSeconds(task.deadline, Date.now()));
  const ending = useRef(false);

  useEffect(() => {
    if (task.deadline === null || task.status !== 'active') return;
    const deadline = task.deadline;
    function check() {
      const remaining = remainingSeconds(deadline, Date.now());
      setSeconds(remaining);
      if (remaining === 0 && !ending.current) {
        ending.current = true;
        void onTimeout().then(success => { if (!success) ending.current = false; });
      }
    }
    check();
    const interval = window.setInterval(check, 1000);
    window.addEventListener('focus', check);
    document.addEventListener('visibilitychange', check);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener('focus', check);
      document.removeEventListener('visibilitychange', check);
    };
  }, [task.id, task.deadline, task.status, onTimeout]);

  if (task.deadline === null) return <p className="time-remaining">Time: untimed practice</p>;
  return <p className="time-remaining" role="timer" aria-live="off" aria-label="Time remaining">
    Time remaining: {Math.floor(seconds / 60).toString().padStart(2, '0')}:{(seconds % 60).toString().padStart(2, '0')}
  </p>;
}
