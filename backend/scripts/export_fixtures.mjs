// Regenerate backend fixtures from the frontend mock sources so both sides stay identical.
// Run from the repository root with Node 22.18+ (type stripping): node backend/scripts/export_fixtures.mjs
import { writeFileSync } from 'node:fs';

const scenarios = await import('../../frontend/src/mocks/scenarios.ts');
const responses = await import('../../frontend/src/mocks/responses.ts');
const workload = await import('../../frontend/src/services/workloadSurvey.ts');
const preparation = await import('../../frontend/src/services/studyPreparation.ts');

const write = (name, value) => writeFileSync(new URL(`../app/fixtures/${name}`, import.meta.url), `${JSON.stringify(value, null, 2)}\n`);

write('catalog.json', {
  version: 'catalog-v1', source: 'frontend/src/mocks/scenarios.ts',
  scenarios: scenarios.scenarios, items: scenarios.catalog,
});
write('reference-plans.json', {
  note: 'Researcher-only feasible reference plans. Never served by the API.',
  plans: scenarios.feasiblePlans,
});
write('definitions.json', {
  source: 'frontend/src/services/{workloadSurvey,studyPreparation}.ts and frontend/src/mocks/responses.ts',
  surveys: {
    current: workload.workloadSurveyDefinition.version,
    definitions: {
      [workload.workloadSurveyDefinitionV1.version]: workload.workloadSurveyDefinitionV1,
      [workload.workloadSurveyDefinition.version]: workload.workloadSurveyDefinition,
    },
  },
  preparations: preparation.preparationDefinition,
  feedback: preparation.feedbackDefinition,
  recommendations: responses.recommendations,
});
