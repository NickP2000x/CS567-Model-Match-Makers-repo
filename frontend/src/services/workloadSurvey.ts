import { surveyDimensions } from './experiment.types.ts';
import type { SurveyAnswers, SurveyMetadata } from './experiment.types.ts';

// Explicit provisional anchors, retained with each experimental task's answers.
export const workloadSurveyDefinition: SurveyMetadata = {
  version: 'provisional-nasa-tlx-21-v1', provisional: true, min: 0, max: 100, increment: 5,
  items: {
    mentalDemand: { label: 'Mental demand', question: 'How mentally demanding was the task?', leftAnchor: 'Very low', rightAnchor: 'Very high', orientation: 'higher-is-more-workload' },
    physicalDemand: { label: 'Physical demand', question: 'How physically demanding was the task?', leftAnchor: 'Very low', rightAnchor: 'Very high', orientation: 'higher-is-more-workload' },
    temporalDemand: { label: 'Temporal demand', question: 'How hurried or rushed did you feel?', leftAnchor: 'Very low', rightAnchor: 'Very high', orientation: 'higher-is-more-workload' },
    performance: { label: 'Performance', question: 'How successful were you in accomplishing the task?', leftAnchor: 'Perfect performance', rightAnchor: 'Failure', orientation: 'higher-is-more-workload' },
    effort: { label: 'Effort', question: 'How hard did you have to work to accomplish the task?', leftAnchor: 'Very low', rightAnchor: 'Very high', orientation: 'higher-is-more-workload' },
    frustration: { label: 'Frustration', question: 'How insecure, discouraged, irritated, stressed, or annoyed did you feel?', leftAnchor: 'Very low', rightAnchor: 'Very high', orientation: 'higher-is-more-workload' },
  },
};
Object.values(workloadSurveyDefinition.items).forEach(Object.freeze);
Object.freeze(workloadSurveyDefinition.items);
Object.freeze(workloadSurveyDefinition);

export function isSurveyResponse(value: number, metadata: SurveyMetadata): boolean {
  return Number.isFinite(value) && value >= metadata.min && value <= metadata.max
    && (value - metadata.min) % metadata.increment === 0;
}

export function calculateWorkloadMean(answers: SurveyAnswers, metadata: SurveyMetadata): number | null {
  let total = 0;
  for (const dimension of surveyDimensions) {
    const value = answers[dimension];
    if (value === undefined || !isSurveyResponse(value, metadata)) return null;
    const commonScale = 100 * (value - metadata.min) / (metadata.max - metadata.min);
    total += metadata.items[dimension].orientation === 'higher-is-more-workload' ? commonScale : 100 - commonScale;
  }
  return total / surveyDimensions.length;
}
