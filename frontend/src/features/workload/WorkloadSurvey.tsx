import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { surveyDimensions } from '../../services/experiment.types';
import type { ExperimentService, SurveyAnswers, TaskId } from '../../services/experiment.types';
import { useExperiment } from '../../services/useExperiment';

interface SurveyProps {
  service: ExperimentService;
  taskId: Exclude<TaskId, 'practice'>;
  pending: boolean;
  perform: (operation: () => Promise<void>) => Promise<boolean>;
}

export function WorkloadSurvey({ service, taskId, pending: actionPending, perform }: SurveyProps) {
  const state = useExperiment(service);
  const task = state.tasks[taskId];
  const [draft, setDraft] = useState<{ taskId: TaskId; answers: SurveyAnswers } | null>(null);
  const attemptedDraft = useRef<typeof draft>(null);
  const [submitting, setSubmitting] = useState(false);
  const pending = actionPending || state.pendingOperations > 0;
  const available = !!task && task.status !== 'active' && !!task.survey.metadata
    && task.survey.submittedAt === null && state.step === (taskId === 'task-1' ? 'tlx-1' : 'tlx-2');

  useEffect(() => {
    if (!available || pending || !draft || draft.taskId !== taskId || attemptedDraft.current === draft) return;
    void perform(async () => {
      attemptedDraft.current = draft;
      await service.saveSurveyAnswers(taskId, draft.answers);
    });
  }, [available, pending, draft, taskId, perform, service]);

  if (!available || !task?.survey.metadata) {
    return <p>The workload survey is unavailable for this task.</p>;
  }

  const answers = draft?.taskId === taskId ? draft.answers : task.survey.answers;
  const metadata = task.survey.metadata;
  const points = Array.from({ length: (metadata.max - metadata.min) / metadata.increment + 1 },
    (_, index) => metadata.min + index * metadata.increment);

  function choose(dimension: typeof surveyDimensions[number], value: number) {
    setDraft(current => ({ taskId, answers: {
      ...(current?.taskId === taskId ? current.answers : task!.survey.answers), [dimension]: value,
    } }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void perform(async () => {
      setSubmitting(true);
      // Save the entire visible draft, including any selection retained after an
      // earlier failed save, before submitting. Raw scoring stays service-owned.
      try {
        await service.saveSurveyAnswers(taskId, answers);
        await service.submitSurvey(taskId);
      } finally { setSubmitting(false); }
    });
  }

  return (
    <section className="workload-survey" aria-label={`Workload ratings for Task ${taskId === 'task-1' ? '1' : '2'}`}>
      <p className="field-help">Provisional adapted NASA-TLX · Five labelled choices · Pending researcher approval</p>
      <p id="workload-help">Select one response for each question about the task you just completed.</p>
      <form onSubmit={submit} aria-describedby="workload-help">
        {surveyDimensions.map(dimension => {
          const item = metadata.items[dimension];
          return (
            <fieldset key={dimension} disabled={submitting} className="workload-question" aria-describedby={`${dimension}-question`}>
              <legend>{item.label}</legend>
              <p id={`${dimension}-question`}>{item.question}</p>
              {!item.labels && <div className="workload-anchors"><span>{item.leftAnchor}</span><span>{item.rightAnchor}</span></div>}
              <div className="workload-scale">
                <div className={`workload-points${item.labels ? ' labelled-points' : ''}`}
                  style={{ gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))` }}>
                  {points.map((value, index) => (
                    <label className="workload-option" key={value}>
                      <input type="radio" name={dimension} value={value} required
                        checked={answers[dimension] === value}
                        aria-label={`${item.label}: ${item.labels?.[index] ?? `${value} out of 100`}`}
                        onChange={() => choose(dimension, value)} />
                      {item.labels && <span>{item.labels[index]}</span>}
                    </label>
                  ))}
                </div>
              </div>
            </fieldset>
          );
        })}
        <button type="submit" disabled={pending || submitting}>Continue</button>
        <p role="status">{pending ? 'Saving workload responses…' : ''}</p>
      </form>
    </section>
  );
}
