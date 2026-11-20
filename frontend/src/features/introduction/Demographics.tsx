import type { FormEvent } from 'react';
import type { StudyState } from '../../services/experiment.types';

type DemographicValues = NonNullable<StudyState['demographics']>;

interface DemographicsProps {
  values: StudyState['demographics'];
  pending: boolean;
  onSubmit: (values: DemographicValues) => void;
}

export function Demographics({ values, pending, onSubmit }: DemographicsProps) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSubmit({
      age: Number(data.get('age')),
      gender: String(data.get('gender') ?? '').trim(),
      priorLlmUsage: String(data.get('priorLlmUsage') ?? ''),
      prolificId: String(data.get('prolificId') ?? '').trim(),
    });
  }
  // Prolific adds PROLIFIC_PID to the study link; pre-fill it so participants need not type it.
  const linkedProlificId = new URLSearchParams(window.location.search).get('PROLIFIC_PID') ?? undefined;

  return (
    <>
      <p className="provisional-notice">
        Provisional questionnaire — wording, options, required fields, and
        eligibility rules are pending researcher approval.
      </p>
      <p id="demographics-help">
        All fields are required. Enter your real Prolific ID. For the other questions, invented answers
        are accepted while this questionnaire is provisional.
      </p>
      <form onSubmit={submit} aria-describedby="demographics-help">
        <fieldset disabled={pending}>
          <legend>Prolific ID and demographic responses</legend>
          <label htmlFor="prolific-id">Prolific ID</label>
          <input id="prolific-id" name="prolificId" type="text" required maxLength={64} pattern="[A-Za-z0-9]+"
            autoComplete="off" spellCheck={false} defaultValue={values?.prolificId ?? linkedProlificId}
            aria-describedby="prolific-id-help" />
          <p id="prolific-id-help" className="field-help">
            Your 24-character Prolific ID, shown in your Prolific account. It is filled in automatically if
            you came from Prolific. We use it only to confirm your participation and payment.
          </p>

          <label htmlFor="age">Age (synthetic example)</label>
          <input id="age" name="age" type="number" min="0" step="1" required
            defaultValue={values?.age} aria-describedby="age-help" />
          <p id="age-help" className="field-help">Use a nonnegative whole number. This is not a study eligibility check.</p>

          <label htmlFor="gender">Gender (synthetic example)</label>
          <input id="gender" name="gender" type="text" required defaultValue={values?.gender}
            aria-describedby="gender-help" />
          <p id="gender-help" className="field-help">Free text; an invented answer or “Prefer not to say” is accepted.</p>

          <label htmlFor="prior-llm-usage">Prior LLM usage (synthetic example)</label>
          <select id="prior-llm-usage" name="priorLlmUsage" required defaultValue={values?.priorLlmUsage ?? ''}>
            <option value="" disabled>Select an example response</option>
            <option value="never">Never</option>
            <option value="less-than-weekly">Less than weekly</option>
            <option value="weekly">Weekly</option>
            <option value="daily">Daily or more often</option>
            <option value="prefer-not-to-say">Prefer not to say</option>
          </select>
          <div className="actions"><button type="submit">Continue to tutorial</button></div>
        </fieldset>
      </form>
    </>
  );
}
