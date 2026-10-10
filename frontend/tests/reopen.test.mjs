import assert from 'node:assert/strict';
import test from 'node:test';
import { createMockExperimentService } from '../src/services/mockExperiment.ts';
import { surveyDimensions } from '../src/services/experiment.types.ts';
import { EXPERIMENTAL_TASK_MS } from '../src/services/taskTiming.ts';
import { acknowledge, startTask } from './study-helpers.mjs';

// Provisional "Back to Task" from the ratings page (mock service).

async function submittedTask1(clock) {
  const service = createMockExperimentService({ sequenceId: 1, now: () => clock.now });
  await service.recordConsent(true);
  await service.saveDemographics({ age: 25, gender: 'synthetic example', priorLlmUsage: 'weekly' });
  await acknowledge(service, 'before-start');
  await service.completeTutorial();
  await startTask(service);
  await service.finishTask();
  await startTask(service);
  await service.requestRecommendation();
  await service.updatePlan({ venue: 'A-venue-good', catering: null, supplies: [] });
  clock.now += 60_000;
  await service.finishTask();
  assert.equal(service.getSnapshot().step, 'tlx-1');
  return service;
}

test('back to task keeps work and the original deadline, and can repeat', async () => {
  const clock = { now: 1_000_000 };
  const service = await submittedTask1(clock);
  const before = service.getSnapshot().tasks['task-1'];
  await service.saveSurveyAnswers('task-1', { effort: 50 });
  clock.now += 5_000;
  await service.reopenTask('task-1');
  const task = service.getSnapshot().tasks['task-1'];
  assert.equal(service.getSnapshot().step, 'task-1');
  assert.equal(task.status, 'active');
  assert.equal(task.endedAt, null);
  assert.equal(task.deadline, before.deadline);
  assert.deepEqual(task.plan, before.plan);
  assert.deepEqual(task.decisions, before.decisions);
  assert.deepEqual(task.reopens, [{ endedAt: before.endedAt, reopenedAt: clock.now }]);
  await service.updatePlan({ venue: 'A-venue-good', catering: 'A-food-good', supplies: [] });
  await service.finishTask();
  assert.deepEqual(service.getSnapshot().tasks['task-1'].survey.answers, { effort: 50 });
  await service.reopenTask('task-1');
  assert.equal(service.getSnapshot().tasks['task-1'].reopens.length, 2);
});

test('cannot reopen after time runs out, after rating, after timeout, or for practice', async () => {
  const clock = { now: 1_000_000 };
  const late = await submittedTask1(clock);
  clock.now += EXPERIMENTAL_TASK_MS;
  await assert.rejects(late.reopenTask('task-1'), { code: 'TASK_EXPIRED' });
  assert.equal(late.getSnapshot().step, 'tlx-1');

  const rated = await submittedTask1({ now: 1_000_000 });
  await assert.rejects(rated.reopenTask('practice'), { code: 'INVALID_STEP' });
  await rated.saveSurveyAnswers('task-1', Object.fromEntries(surveyDimensions.map(key => [key, 50])));
  await rated.submitSurvey('task-1');
  await assert.rejects(rated.reopenTask('task-1'), { code: 'INVALID_STEP' });
  await startTask(rated);
  await rated.finishTask('timed-out');
  await assert.rejects(rated.reopenTask('task-2'), { code: 'INVALID_STEP' });
});
