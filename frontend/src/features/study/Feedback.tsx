import { useState } from 'react';
import type { FeedbackAnswers } from '../../services/experiment.types';
import { feedbackDefinition } from '../../services/studyPreparation';

export function Feedback({ pending, onFinish }: { pending: boolean; onFinish: (answers: FeedbackAnswers) => void }) {
  const [answers, setAnswers] = useState<FeedbackAnswers>({ interfaceComments: '', studyComments: '' });
  return <>
    <p>Optional — you may leave either box blank. Use invented information only.</p>
    <form onSubmit={event => { event.preventDefault(); onFinish(answers); }}>
      <fieldset disabled={pending}>
        <legend className="visually-hidden">Optional study feedback</legend>
        {(['interfaceComments', 'studyComments'] as const).map(key => <div key={key}>
          <label htmlFor={key}>{feedbackDefinition[key]}</label>
          <textarea id={key} rows={4} value={answers[key]} onChange={event => setAnswers(current => ({ ...current, [key]: event.target.value }))} />
        </div>)}
        <div className="actions"><button type="submit">Finish</button></div>
      </fieldset>
    </form>
  </>;
}
