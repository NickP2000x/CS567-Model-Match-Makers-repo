import { useEffect, useRef, useState } from 'react';
import { Consent } from './features/introduction/Consent';
import { Demographics } from './features/introduction/Demographics';
import { Tutorial } from './features/introduction/Tutorial';
import { Preparation } from './features/introduction/Preparation';
import { PlanningWorkspace } from './features/planning/PlanningWorkspace';
import { WorkloadSurvey } from './features/workload/WorkloadSurvey';
import { DeveloperControls } from './features/study/DeveloperControls';
import { StudyProgress } from './features/study/StudyProgress';
import { Feedback } from './features/study/Feedback';
import type { ExperimentService, StudyState, StudyStep, TaskId } from './services/experiment.types';
import { useExperiment } from './services/useExperiment';

function context(state: StudyState) {
  return JSON.stringify([state.participantId, state.step, state.consent, state.tasks[state.step as TaskId]?.checkpoint]);
}

const headings: Record<StudyStep, string> = {
  consent: 'Consent', demographics: 'About you', tutorial: 'Interface guide',
  practice: 'Practice', 'task-1': 'Task 1', 'tlx-1': 'Workload ratings — Task 1',
  'task-2': 'Task 2', 'tlx-2': 'Workload ratings — Task 2', feedback: 'Additional feedback', completion: 'Study demonstration complete',
};

export function App({ service }: { service: ExperimentService }) {
  const state = useExperiment(service);
  const title = useRef<HTMLHeadingElement>(null);
  const actionInFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const endingTask = useRef<TaskId | null>(null);
  const [terminating, setTerminating] = useState(false);
  const pending = busy || terminating || state.pendingOperations > 0;

  const planningStep = state.step === 'practice' || state.step === 'task-1' || state.step === 'task-2' ? state.step : null;
  const preparationId = state.step === 'tutorial' && !state.preparations['before-start'] ? 'before-start'
    : planningStep && !state.preparations[planningStep] ? planningStep : null;
  useEffect(() => { title.current?.focus(); }, [state.step, state.consent, preparationId]);

  async function perform(operation: () => Promise<void>) {
    const origin = context(state);
    if (actionInFlight.current || endingTask.current || service.getSnapshot().pendingOperations > 0
      || origin !== context(service.getSnapshot())) return false;
    actionInFlight.current = true;
    setBusy(true);
    setActionError(null);
    try {
      await operation();
      return true;
    } catch (error) {
      if (origin === context(service.getSnapshot())) {
        setActionError(error instanceof Error ? error.message : 'Could not continue. Please try again.');
      }
      return false;
    } finally {
      actionInFlight.current = false;
      setBusy(false);
    }
  }

  async function finishTask(taskId: TaskId, reason: 'submitted' | 'timed-out' = 'submitted') {
    const current = service.getSnapshot();
    if (endingTask.current || current.step !== taskId || current.tasks[taskId]?.status !== 'active') return false;
    // Timeout must be able to end a task even while a router/agent action is pending.
    endingTask.current = taskId;
    setTerminating(true);
    setActionError(null);
    try { await service.finishTask(reason); return true; }
    catch (error) {
      if (service.getSnapshot().step === taskId) setActionError(error instanceof Error ? error.message : 'Could not finish the task.');
      return false;
    } finally { endingTask.current = null; setTerminating(false); }
  }

  const heading = state.step === 'consent' && state.consent === false ? 'Demo declined'
    : preparationId === 'before-start' ? 'Before you start'
    : preparationId === 'practice' ? 'Ready for practice'
    : preparationId ? `Ready for Task ${preparationId === 'task-1' ? '1' : '2'}` : headings[state.step];
  const planning = planningStep !== null && preparationId === null;
  const surveyTask = state.step === 'tlx-1' ? 'task-1' : state.step === 'tlx-2' ? 'task-2' : null;

  return (
    <main className={planning ? 'planning-page' : undefined}>
      <p className="prototype-label">Provisional demonstration · Simulated AI · Use invented information</p>
      {state.step === 'consent' ? <>
        <h1>Model Matchmakers</h1><h2 id="screen-title" ref={title} tabIndex={-1}>{heading}</h2>
      </> : <>
        <StudyProgress step={state.step} />
        <h1 id="screen-title" ref={title} tabIndex={-1}>{heading}</h1>
      </>}
      <section aria-labelledby="screen-title" aria-busy={pending}>
        {actionError && <p role="alert" className="error-message">{actionError}</p>}
        {state.step === 'consent' && (
          <Consent declined={state.consent === false} pending={pending}
            onDecision={accepted => { void perform(() => service.recordConsent(accepted)); }} />
        )}
        {state.step === 'demographics' && (
          <Demographics values={state.demographics} pending={pending}
            onSubmit={values => { void perform(() => service.saveDemographics(values)); }} />
        )}
        {preparationId && <Preparation key={preparationId} id={preparationId} pending={pending}
          onContinue={ids => { void perform(() => service.confirmPreparation(preparationId, ids)); }} />}
        {state.step === 'tutorial' && preparationId === null && (
          <Tutorial pending={pending} onContinue={() => { void perform(() => service.completeTutorial()); }} />
        )}
        {planning && (
          <PlanningWorkspace key={state.step} service={service} taskId={state.step as TaskId}
            pending={pending} perform={perform} onFinish={finishTask} />
        )}
        {surveyTask && (
          <>
            <p role="status">{state.tasks[surveyTask]?.status === 'timed-out' ? 'Time is up. Your current work was preserved.' : 'Your current plan was submitted.'} Please rate the task you just completed.</p>
            <WorkloadSurvey key={surveyTask} service={service} taskId={surveyTask} pending={pending} perform={perform} />
          </>
        )}
        {state.step === 'feedback' && <Feedback pending={pending} onFinish={answers => { void perform(() => service.submitFeedback(answers)); }} />}
        {state.step === 'completion' && <p>Thank you. Both tasks, ratings, and optional feedback are complete. This demonstration is not approved for real participant data collection.</p>}
      </section>
      {import.meta.env.DEV && <DeveloperControls state={state} pending={pending} terminating={terminating}
        onReset={sequence => { void perform(() => service.reset(sequence)); }}
        onTimeout={() => {
          if (state.step === 'task-1' || state.step === 'task-2') void finishTask(state.step, 'timed-out');
        }} />}
      <p role="status" className="operation-status">{pending ? 'Updating the demonstration…' : ''}</p>
      <p className="field-help">{state.refreshRestartsDemo ? 'Refreshing restarts this demonstration.' : 'Refreshing resumes your current session.'}</p>
    </main>
  );
}
