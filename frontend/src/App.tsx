import { useEffect, useRef, useState } from 'react';
import { Consent } from './features/introduction/Consent';
import { Demographics } from './features/introduction/Demographics';
import { Tutorial } from './features/introduction/Tutorial';
import type { ExperimentService } from './services/experiment.types';
import { useExperiment } from './services/useExperiment';

export function App({ service }: { service: ExperimentService }) {
  const state = useExperiment(service);
  const title = useRef<HTMLHeadingElement>(null);
  const actionInFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const pending = busy || state.pendingOperations > 0;

  useEffect(() => { title.current?.focus(); }, [state.step, state.consent]);

  async function perform(operation: () => Promise<void>) {
    if (actionInFlight.current || service.getSnapshot().pendingOperations > 0) return;
    actionInFlight.current = true;
    setBusy(true);
    setActionError(null);
    try {
      await operation();
    } catch {
      // Expected service errors are exposed in the snapshot. Keep the screen/input.
      if (!service.getSnapshot().error) setActionError('Could not continue. Please try again.');
    } finally {
      actionInFlight.current = false;
      setBusy(false);
    }
  }

  const heading = state.step === 'consent' ? (state.consent === false ? 'Demo declined' : 'Provisional consent')
    : state.step === 'demographics' ? 'Synthetic demographics'
    : state.step === 'tutorial' ? 'How the planning task works' : 'Practice';
  const error = state.error?.message ?? actionError;

  return (
    <main>
      <p className="prototype-label">Frontend research prototype</p>
      <h1>Model Matchmakers</h1>
      <p className="demo-notice">
        Use synthetic information only. Router and agent behavior is simulated;
        this build is not ready for real participant data collection.
        Refreshing restarts the demonstration.
      </p>
      <section aria-labelledby="screen-title" aria-busy={pending}>
        <h2 id="screen-title" ref={title} tabIndex={-1}>{heading}</h2>
        {error && <p role="alert" className="error-message">{error}</p>}
        {state.step === 'consent' && (
          <Consent declined={state.consent === false} pending={pending}
            onDecision={accepted => { void perform(() => service.recordConsent(accepted)); }} />
        )}
        {state.step === 'demographics' && (
          <Demographics values={state.demographics} pending={pending}
            onSubmit={values => { void perform(() => service.saveDemographics(values)); }} />
        )}
        {state.step === 'tutorial' && (
          <Tutorial pending={pending} onContinue={() => { void perform(() => service.completeTutorial()); }} />
        )}
        {state.step === 'practice' && (
          <>
            <p>Your introduction is complete. Practice is the next step.</p>
            <p>The practice workspace is not available in this build yet.</p>
          </>
        )}
      </section>
      <p role="status" className="operation-status">{pending ? 'Saving your demo response…' : ''}</p>
    </main>
  );
}
