import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import type { ExperimentService, Model, Task } from '../../services/experiment.types';

interface RoutingProps {
  task: Task;
  service: ExperimentService;
  pending: boolean;
  perform: (operation: () => Promise<void>) => Promise<boolean>;
  routerSimulated: boolean;
  agentSimulated: boolean;
}

// Mount a fresh panel per task/checkpoint. The service owns all recorded choices.
export function RoutingPanel({ task, service, pending, perform, routerSimulated, agentSimulated }: RoutingProps) {
  const decision = task.decisions[task.checkpoint]!;
  const [initialSelection, setInitialSelection] = useState<Model | null>(null);
  const [finalSelection, setFinalSelection] = useState<Model | null>(null);
  const [requestFailed, setRequestFailed] = useState(false);
  const requestInFlight = useRef(false);
  const recommendationTitle = useRef<HTMLHeadingElement>(null);
  const committedTitle = useRef<HTMLHeadingElement>(null);
  const needsRecommendation = task.status === 'active' && (
    (task.condition === 'automatic' && decision.phase === 'awaiting-recommendation')
    || (task.condition === 'override' && decision.phase === 'locked')
  );

  useEffect(() => {
    if (!needsRecommendation || pending || requestFailed || requestInFlight.current) return;
    requestInFlight.current = true;
    let attempted = false;
    void perform(async () => {
      const state = service.getSnapshot();
      const current = state.tasks[task.id];
      if (state.step !== task.id || current?.status !== 'active' || current.checkpoint !== task.checkpoint) return;
      attempted = true;
      await service.requestRecommendation();
    }).then(success => {
      // A guarded/skipped operation is not a failed request. The next idle render
      // can try again; a real failure requires an explicit retry, not a loop.
      if (attempted && !success) setRequestFailed(true);
    }).finally(() => { requestInFlight.current = false; });
  }, [needsRecommendation, pending, requestFailed, perform, service, task.id, task.checkpoint]);

  useEffect(() => {
    if (decision.phase === 'recommended') recommendationTitle.current?.focus();
    if (decision.phase === 'committed' && task.condition !== 'practice') committedTitle.current?.focus();
  }, [decision.phase, task.condition]);

  function lockInitial(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (initialSelection) void perform(() => service.lockInitialChoice(initialSelection));
  }

  function confirmFinal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (finalSelection) void perform(() => service.confirmModel(finalSelection));
  }

  if (task.condition === 'practice') {
    return (
      <div className="routing-status">
        <p>{agentSimulated ? 'Simulated small model' : 'Small model'} — fixed for this stage. Provisional practice treatment; no router recommendation.</p>
      </div>
    );
  }

  const recommendationVisible = decision.phase === 'recommended' || decision.phase === 'committed';
  const alternative = decision.initialModel === 'small' ? 'large' : 'small';
  return (
    <section className="routing-status" aria-labelledby="routing-title">
      <h4 id="routing-title">{task.condition === 'automatic' ? 'Automatic' : 'Override'} routing{routerSimulated ? ' — simulated' : ''}</h4>
      {task.condition === 'override' && decision.phase === 'choose' && (
        <form onSubmit={lockInitial}>
          <fieldset disabled={pending}>
            <legend>Choose your initial model independently</legend>
            <p>The router recommendation is hidden until you lock this choice.</p>
            {(['small', 'large'] as const).map(model => (
              <label className="model-option" key={model}>
                <input type="radio" name="initial-model" value={model} required
                  checked={initialSelection === model} onChange={() => setInitialSelection(model)} />
                {model === 'small' ? 'Small model' : 'Large model'}
              </label>
            ))}
            <button type="submit" disabled={!initialSelection}>Lock initial choice</button>
          </fieldset>
        </form>
      )}
      {task.condition === 'override' && decision.phase !== 'choose' && (
        <p>Your initial choice: <strong>{decision.initialModel}</strong> (locked)</p>
      )}
      {needsRecommendation && (
        requestFailed ? (
          <>
            <p>Recommendation unavailable. Your existing choices are retained.</p>
            <button type="button" disabled={pending} onClick={() => setRequestFailed(false)}>Retry recommendation</button>
          </>
        ) : <p role="status">Loading the {routerSimulated ? 'simulated ' : ''}recommendation…</p>
      )}
      {recommendationVisible && (
        <div className="recommendation-details">
          <h5 ref={recommendationTitle} tabIndex={-1}>{routerSimulated ? 'Simulated router recommendation' : 'Router recommendation'}</h5>
          <p>Recommended model: <strong>{decision.recommendedModel}</strong></p>
          {task.condition === 'override' && decision.initialModel === decision.recommendedModel && <p>Your choice matches the recommendation.</p>}
          <p>{decision.reason}</p>
          <p className="field-help">Provisional recommendation reason — pending researcher approval.</p>
        </div>
      )}
      {task.condition === 'override' && decision.phase === 'recommended' && (
        <form onSubmit={confirmFinal}>
          <fieldset disabled={pending}>
            <legend>Retain or change your initial choice</legend>
            <label className="model-option">
              <input type="radio" name="final-model" required checked={finalSelection === decision.initialModel}
                onChange={() => setFinalSelection(decision.initialModel!)} />
              Keep my choice: {decision.initialModel}{decision.initialModel === decision.recommendedModel ? ' (recommended)' : ''}
            </label>
            <label className="model-option">
              <input type="radio" name="final-model" required checked={finalSelection === alternative}
                onChange={() => setFinalSelection(alternative)} />
              {alternative === decision.recommendedModel ? `Use recommended model: ${alternative}` : `Change to ${alternative}`}
            </label>
            <button type="submit" disabled={!finalSelection}>Confirm final choice</button>
          </fieldset>
        </form>
      )}
      {decision.phase === 'committed' && (
        <div role="status">
          <h5 ref={committedTitle} tabIndex={-1}>Stage model: {agentSimulated ? 'simulated ' : ''}{decision.finalModel}</h5>
          <p>{task.condition === 'automatic' ? 'Applied automatically. ' : 'Final choice confirmed. '}The model is fixed until the next checkpoint.</p>
        </div>
      )}
    </section>
  );
}
