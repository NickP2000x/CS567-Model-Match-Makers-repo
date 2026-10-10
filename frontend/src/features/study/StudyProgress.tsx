import type { StudyStep } from '../../services/experiment.types';

const phases = ['Introduction', 'Practice', 'Task 1', 'Ratings 1', 'Task 2', 'Ratings 2', 'Feedback', 'Finish'];
const phaseIndex: Record<StudyStep, number> = {
  consent: 0, demographics: 0, tutorial: 0, practice: 1, 'task-1': 2, 'tlx-1': 3,
  'task-2': 4, 'tlx-2': 5, feedback: 6, completion: 7,
};
export function StudyProgress({ step }: { step: StudyStep }) {
  return <ol className="study-progress" aria-label="Study progress">
    {phases.map((label, index) => <li key={label} aria-current={index === phaseIndex[step] ? 'step' : undefined}
      className={index === phaseIndex[step] ? 'current-phase' : undefined}>
      {index < phaseIndex[step] ? '✓ ' : ''}{label}
    </li>)}
  </ol>;
}
