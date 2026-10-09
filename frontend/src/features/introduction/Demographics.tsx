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
    });
  }

  return (
    <>
      <p className="provisional-notice">
        Provisional questionnaire — wording, options, required fields, and
        eligibility rules are pending researcher approval.
      </p>
      <p id="demographics-help">All fields are required for this demo. Enter invented answers, not your personal details.</p>
      <form onSubmit={submit} aria-describedby="demographics-help">
        <fieldset disabled={pending}>
          <legend>Example demographic responses</legend>
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
