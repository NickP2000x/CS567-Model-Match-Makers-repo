import { useState } from 'react';
import type { PreparationId } from '../../services/experiment.types';
import { preparationDefinition } from '../../services/studyPreparation';

export function Preparation({ id, pending, onContinue }: {
  id: PreparationId; pending: boolean; onContinue: (ids: string[]) => void;
}) {
  const [checked, setChecked] = useState<string[]>([]);
  const statements = preparationDefinition[id].statements;
  const button = id === 'before-start' ? 'Continue to instructions' : id === 'practice' ? 'Start practice' : `Start Task ${id === 'task-1' ? '1' : '2'}`;
  return (
    <>
      <p>{id === 'before-start' ? 'Read these reminders before the interface guide.'
        : id === 'practice' ? 'Try the interface before the two study tasks. No survey follows practice.'
          : 'A short workload survey follows this task. The timer starts when the requirements appear.'}</p>
      <form onSubmit={event => { event.preventDefault(); onContinue(checked); }}>
        <fieldset disabled={pending}>
          <legend className="visually-hidden">Required acknowledgements</legend>
          {statements.map(statement => (
            <label className="acknowledgement" key={statement.id}>
              <input type="checkbox" required checked={checked.includes(statement.id)}
                onChange={event => {
                  const selected = event.target.checked;
                  setChecked(current => selected ? [...current, statement.id] : current.filter(value => value !== statement.id));
                }} />
              {statement.text}
            </label>
          ))}
          <div className="actions"><button type="submit" disabled={checked.length !== statements.length}>{button}</button></div>
        </fieldset>
      </form>
    </>
  );
}
