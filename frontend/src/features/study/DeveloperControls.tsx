import { useState } from 'react';
import type { SequenceId, StudyState } from '../../services/experiment.types';

const sequences: Record<SequenceId, string> = {
  1: 'A Automatic → B Override', 2: 'B Automatic → A Override',
  3: 'A Override → B Automatic', 4: 'B Override → A Automatic',
};

export function DeveloperControls({ state, pending, terminating, onReset, onTimeout }: {
  state: StudyState; pending: boolean; terminating: boolean;
  onReset: (sequence: SequenceId) => void; onTimeout: () => void;
}) {
  const [sequence, setSequence] = useState(state.sequenceId);
  const activeTask = state.step === 'task-1' || state.step === 'task-2' ? state.tasks[state.step] : null;
  return (
    <details className="developer-controls">
      <summary>Development controls — synthetic demo only</summary>
      <p>Current mock sequence: {state.sequenceId} — {sequences[state.sequenceId]}</p>
      <label htmlFor="demo-sequence">Sequence for next reset</label>
      <select id="demo-sequence" value={sequence} disabled={pending}
        onChange={event => setSequence(Number(event.target.value) as SequenceId)}>
        {([1, 2, 3, 4] as const).map(id => <option key={id} value={id}>{id}: {sequences[id]}</option>)}
      </select>
      <p className="field-help">Reset discards current in-memory work and returns to consent. This is not real random participant allocation.</p>
      <div className="actions">
        <button type="button" disabled={pending} onClick={() => onReset(sequence)}>Apply sequence and reset demo</button>
        <button type="button" className="secondary" disabled={!activeTask || activeTask.status !== 'active' || terminating}
          onClick={onTimeout}>Trigger timeout</button>
      </div>
    </details>
  );
}
