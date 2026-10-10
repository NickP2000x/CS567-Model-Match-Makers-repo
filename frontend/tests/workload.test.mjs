import assert from 'node:assert/strict';
import test from 'node:test';
import { createMockExperimentService } from '../src/services/mockExperiment.ts';
import { surveyDimensions } from '../src/services/experiment.types.ts';
import { calculateWorkloadMean, workloadSurveyDefinition, workloadSurveyDefinitionV1 } from '../src/services/workloadSurvey.ts';
import { acknowledge, finishFeedback, startTask } from './study-helpers.mjs';

const uniform = value => Object.fromEntries(surveyDimensions.map(key => [key, value]));
const example = { mentalDemand: 25, physicalDemand: 0, temporalDemand: 50, performance: 75, effort: 25, frustration: 0 };
async function surveyReady(service) {
  await service.recordConsent(true);
  await service.saveDemographics({ age: 25, gender: 'Invented example', priorLlmUsage: 'weekly' });
  await acknowledge(service, 'before-start');
  await service.completeTutorial(); await startTask(service); await service.finishTask();
  await startTask(service); await service.finishTask();
}

test('known common-scale means respect explicit successful-to-unsuccessful performance labels', () => {
  assert.equal(calculateWorkloadMean(uniform(0), workloadSurveyDefinition), 0);
  assert.equal(calculateWorkloadMean(uniform(50), workloadSurveyDefinition), 50);
  assert.equal(calculateWorkloadMean(uniform(100), workloadSurveyDefinition), 100);
  assert.equal(calculateWorkloadMean(example, workloadSurveyDefinition), 175 / 6);
  assert.equal(workloadSurveyDefinition.items.performance.leftAnchor, 'Completely successful');
  assert.equal(workloadSurveyDefinition.items.performance.rightAnchor, 'Not successful');
  assert.equal(workloadSurveyDefinition.items.performance.orientation, 'higher-is-more-workload');
  assert.equal(example.performance, 75);
});

test('performance reversal follows changed anchors/metadata, not the dimension name', () => {
  const reversed = structuredClone(workloadSurveyDefinition);
  reversed.items.performance = { ...reversed.items.performance, leftAnchor: 'Not successful',
    rightAnchor: 'Completely successful', labels: [...reversed.items.performance.labels].reverse(), orientation: 'lower-is-more-workload' };
  assert.equal(calculateWorkloadMean(example, reversed), 125 / 6);
  assert.equal(example.performance, 75);
});

test('incomplete, nonfinite, out-of-range, and off-point answers have no score', () => {
  assert.equal(calculateWorkloadMean({}, workloadSurveyDefinition), null);
  assert.equal(calculateWorkloadMean({ mentalDemand: 0 }, workloadSurveyDefinition), null);
  for (const performance of [-5, 105, NaN, Infinity, 12, 2.5]) {
    assert.equal(calculateWorkloadMean({ ...example, performance }, workloadSurveyDefinition), null);
  }
});

test('partial survey state retains raw responses and a frozen wording/anchor version; failures are atomic', async () => {
  const service = createMockExperimentService();
  await surveyReady(service);
  const initial = service.getSnapshot().tasks['task-1'].survey;
  assert.deepEqual(initial.answers, {});
  assert.equal(initial.rawScore, null);
  assert.equal(initial.metadata.version, 'provisional-adapted-nasa-tlx-5-v2');
  assert.throws(() => { initial.metadata.items.performance.rightAnchor = 'Success'; }, TypeError);
  await service.saveSurveyAnswers('task-1', { mentalDemand: 0 });
  await assert.rejects(service.submitSurvey('task-1'), { code: 'INCOMPLETE_SURVEY' });
  await assert.rejects(service.saveSurveyAnswers('task-1', { mentalDemand: 50, performance: 12 }), { code: 'INVALID_SURVEY' });
  assert.deepEqual(service.getSnapshot().tasks['task-1'].survey.answers, { mentalDemand: 0 });
  assert.equal(service.getSnapshot().tasks['task-1'].survey.rawScore, null);
  assert.equal(service.getSnapshot().step, 'tlx-1');
  await assert.rejects(service.saveSurveyAnswers('practice', example), { code: 'INVALID_SURVEY' });
  assert.equal(service.getSnapshot().tasks.practice.survey.metadata, null);
  assert.equal(service.getSnapshot().tasks.practice.survey.rawScore, null);
});

test('both task surveys retain independent raw answers, oriented means, and duplicate protection', async () => {
  const service = createMockExperimentService();
  await surveyReady(service);
  await service.saveSurveyAnswers('task-1', example);
  await service.submitSurvey('task-1');
  const first = service.getSnapshot().tasks['task-1'].survey;
  assert.equal(first.rawScore, 175 / 6);
  assert.deepEqual(first.answers, example);
  assert.ok(first.submittedAt !== null);
  await assert.rejects(service.submitSurvey('task-1'), { code: 'INCOMPLETE_SURVEY' });
  await assert.rejects(service.saveSurveyAnswers('task-1', uniform(100)), { code: 'INVALID_SURVEY' });
  assert.deepEqual(service.getSnapshot().tasks['task-1'].survey, first);
  await startTask(service); await service.finishTask();
  const second = service.getSnapshot().tasks['task-2'].survey;
  assert.deepEqual(second.answers, {});
  assert.equal(second.rawScore, null);
  assert.deepEqual(second.metadata, first.metadata);
  await service.saveSurveyAnswers('task-2', uniform(0));
  await service.submitSurvey('task-2');
  assert.equal(service.getSnapshot().tasks['task-2'].survey.rawScore, 0);
  assert.deepEqual(service.getSnapshot().tasks['task-1'].survey, first);
  assert.equal(service.getSnapshot().step, 'feedback');
  await finishFeedback(service);
  assert.equal(service.getSnapshot().step, 'completion');
});

test('the earlier 21-point definition remains unchanged and scores its own raw positions', () => {
  assert.equal(workloadSurveyDefinitionV1.version, 'provisional-nasa-tlx-21-v1');
  assert.equal(workloadSurveyDefinitionV1.increment, 5);
  assert.equal(calculateWorkloadMean({ mentalDemand: 20, physicalDemand: 0, temporalDemand: 40, performance: 60, effort: 30, frustration: 10 }, workloadSurveyDefinitionV1), 160 / 6);
  assert.deepEqual(workloadSurveyDefinition.items.mentalDemand.labels, ['Very low', 'Low', 'Moderate', 'High', 'Very high']);
});
