import assert from 'node:assert/strict';
import test from 'node:test';
import { createMockExperimentService } from '../src/services/mockExperiment.ts';
import { surveyDimensions } from '../src/services/experiment.types.ts';
import { acknowledge, startTask } from './study-helpers.mjs';

async function demographics(service) {
  await service.recordConsent(true);
  await service.saveDemographics({ age: 25, gender: 'Invented example', priorLlmUsage: 'weekly' });
}

test('acknowledgements are explicit, validated, immutable, and do not create tasks/deadlines', async () => {
  let clock = 1000;
  const service = createMockExperimentService({ now: () => clock });
  await demographics(service);
  await assert.rejects(service.completeTutorial(), { code: 'INVALID_PREPARATION' });
  await assert.rejects(service.confirmPreparation('before-start', ['no-refresh']), { code: 'INVALID_PREPARATION' });
  assert.deepEqual(service.getSnapshot().preparations, {});
  await acknowledge(service, 'before-start');
  const before = service.getSnapshot().preparations['before-start'];
  assert.deepEqual(before.acknowledgedIds, ['no-refresh', 'synthetic-only']);
  clock += 1000;
  await acknowledge(service, 'before-start');
  assert.deepEqual(service.getSnapshot().preparations['before-start'], before);
  assert.throws(() => { before.acknowledgedIds.push('another'); }, TypeError);
  await service.completeTutorial();
  await assert.rejects(service.beginTask(), { code: 'INVALID_PREPARATION' });
  await acknowledge(service, 'practice');
  assert.deepEqual(service.getSnapshot().tasks, {});
  await service.beginTask(); await service.finishTask();
  await assert.rejects(service.beginTask(), { code: 'INVALID_PREPARATION' });
  await acknowledge(service, 'task-1');
  assert.equal(service.getSnapshot().tasks['task-1'], undefined);
  clock += 600000; // Spending time on preparation cannot consume or start task time.
  await service.beginTask();
  assert.equal(service.getSnapshot().tasks['task-1'].startedAt, clock);
  assert.equal(service.getSnapshot().tasks['task-1'].deadline, clock + 900000);
});

test('feedback is optional, separate from task scores, and only completes after both surveys', async () => {
  for (const answers of [{ interfaceComments: '', studyComments: '' },
    { interfaceComments: 'Invented usability comment', studyComments: 'Invented study suggestion' }]) {
    const service = createMockExperimentService();
    await assert.rejects(service.submitFeedback(answers), { code: 'INVALID_STEP' });
    await demographics(service); await acknowledge(service, 'before-start');
    await service.completeTutorial(); await startTask(service); await service.finishTask();
    for (const taskId of ['task-1', 'task-2']) {
      await startTask(service); await service.finishTask();
      await service.saveSurveyAnswers(taskId, Object.fromEntries(surveyDimensions.map(key => [key, 50])));
      await service.submitSurvey(taskId);
    }
    assert.equal(service.getSnapshot().step, 'feedback');
    const tasks = service.getSnapshot().tasks;
    await assert.rejects(service.submitFeedback({ interfaceComments: 123, studyComments: '' }), { code: 'INVALID_FEEDBACK' });
    assert.equal(service.getSnapshot().feedback, null);
    const results = await Promise.allSettled([service.submitFeedback(answers), service.submitFeedback(answers)]);
    assert.equal(results[0].status, 'fulfilled');
    assert.equal(results[1].status, 'rejected');
    assert.equal(service.getSnapshot().step, 'completion');
    assert.equal(service.getSnapshot().feedback.interfaceComments, answers.interfaceComments);
    assert.equal(service.getSnapshot().feedback.studyComments, answers.studyComments);
    assert.equal(service.getSnapshot().feedback.version, 'provisional-feedback-v1');
    assert.deepEqual(service.getSnapshot().tasks, tasks);
    assert.equal(service.getSnapshot().tasks['task-1'].survey.rawScore, 50);
    await service.reset(2);
    assert.deepEqual(service.getSnapshot().preparations, {});
    assert.equal(service.getSnapshot().feedback, null);
  }
});
