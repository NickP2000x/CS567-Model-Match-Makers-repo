import type { Checkpoint, Model } from '../services/experiment.types.ts';

export const recommendations: Record<Checkpoint, { model: Model; reason: string }> = {
  Venue: { model: 'small', reason: 'Simulated recommendation: start with a catalog comparison.' },
  Catering: { model: 'large', reason: 'Simulated recommendation: compare dietary coverage and servings.' },
  Supplies: { model: 'small', reason: 'Simulated recommendation: compare supplies and prices.' },
  'Final constraint check': { model: 'large', reason: 'Simulated recommendation: review all four constraints together.' },
};
export function cannedResponse(model: Model, checkpoint: Checkpoint): string {
  return model === 'small'
    ? `[Simulated small model] ${checkpoint}: inspect the catalog details before choosing.`
    : `[Simulated large model] ${checkpoint}: compare alternatives and review budget, capacity, dietary coverage, and wheelchair access.`;
}
