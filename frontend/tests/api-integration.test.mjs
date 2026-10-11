import assert from 'node:assert/strict';
import test from 'node:test';
import { checkpoints, surveyDimensions } from '../src/services/experiment.types.ts';
import { createApiExperimentService } from '../src/services/apiExperiment.ts';
import { acknowledge, finishFeedback, startTask } from './study-helpers.mjs';

// Opt-in contract check against a running backend (mock mode, DEV_CONTROLS=true):
//   MM_API_URL=http://127.0.0.1:8000 bash scripts/frontend.sh test
const apiUrl = process.env.MM_API_URL;
const skip = apiUrl ? false : 'set MM_API_URL to a backend started with DEV_CONTROLS=true';

function memoryStorage() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => { values.set(key, value); }, removeItem: key => { values.delete(key); } };
}

async function connect(sequenceId, storage = memoryStorage()) {
  return { service: await createApiExperimentService({ baseUrl: apiUrl, storage, developmentSequence: sequenceId }), storage };
}

async function intro(service) {
  await service.recordConsent(true);
  await service.saveDemographics({ age: 25, gender: 'synthetic example', priorLlmUsage: 'weekly' });
  await acknowledge(service, 'before-start');
  await service.completeTutorial();
  await startTask(service);
}

async function route(service) {
  const state = service.getSnapshot();
  const task = state.tasks[state.step];
  if (task.condition === 'override') {
    await service.lockInitialChoice('large');
    const decision = await service.requestRecommendation();
    assert.equal(decision.phase, 'recommended');
    await service.confirmModel(decision.recommendedModel);
  } else {
    assert.equal((await service.requestRecommendation()).phase, 'committed');
  }
}

for (const sequenceId of [1, 2, 3, 4]) {
  test(`sequence ${sequenceId} runs consent to completion through the backend`, { skip }, async () => {
    const { service } = await connect(sequenceId);
    assert.equal(service.getSnapshot().sequenceId, sequenceId);
    await intro(service);
    const scenario = await service.getScenario('practice');
    assert.equal(scenario.requirements.attendees, 15);
    const summaries = await service.searchCatalog('practice', 'meadow');
    assert.equal(summaries.length, 1);
    assert.equal(summaries[0].capacity, undefined);
    const item = await service.inspectItem(summaries[0].id);
    assert.equal(item.capacity, 15);
    await service.updatePlan({ venue: summaries[0].id, catering: null, supplies: [] });
    await service.finishTask();
    assert.equal(service.getSnapshot().step, 'task-1');

    for (const [taskId, surveyStep] of [['task-1', 'tlx-1'], ['task-2', 'tlx-2']]) {
      await startTask(service);
      const task = service.getSnapshot().tasks[taskId];
      assert.equal(task.deadline - task.startedAt, 15 * 60 * 1000);
      for (const checkpoint of checkpoints) {
        await route(service);
        await service.sendMessage(`Help with ${checkpoint}`);
        if (checkpoint !== 'Final constraint check') await service.advanceCheckpoint();
      }
      await assert.rejects(service.advanceCheckpoint(), { code: 'FINAL_CHECKPOINT' });
      assert.equal(service.getSnapshot().tasks[taskId].messages.length, 8);
      await service.finishTask();
      assert.equal(service.getSnapshot().step, surveyStep);
      await service.saveSurveyAnswers(taskId, Object.fromEntries(surveyDimensions.map(key => [key, 50])));
      await service.submitSurvey(taskId);
      assert.equal(service.getSnapshot().tasks[taskId].survey.rawScore, 50);
    }
    await finishFeedback(service);
    assert.equal(service.getSnapshot().step, 'completion');
    assert.equal(service.getSnapshot().error, null);
  });
}

test('override concealment and errors come from the backend', { skip }, async () => {
  const { service } = await connect(3);
  await intro(service);
  await service.finishTask();
  await startTask(service);
  await assert.rejects(service.requestRecommendation(), { code: 'INVALID_ROUTING_PHASE' });
  assert.equal(service.getSnapshot().tasks['task-1'].decisions.Venue.recommendedModel, null);
  await assert.rejects(service.sendMessage('too early'), { code: 'MODEL_REQUIRED' });
  await assert.rejects(service.updatePlan({ venue: 'B-venue-good', catering: null, supplies: [] }), { code: 'INVALID_PLAN' });
});

test('a refresh resumes the same session and keeps the deadline', { skip }, async () => {
  const { service, storage } = await connect(2);
  await intro(service);
  await service.finishTask();
  await startTask(service);
  await route(service);
  const before = service.getSnapshot();
  const { service: resumed } = await connect(2, storage);
  const after = resumed.getSnapshot();
  assert.equal(after.sessionId, before.sessionId);
  assert.equal(after.tasks['task-1'].deadline, before.tasks['task-1'].deadline);
  assert.deepEqual(after.tasks['task-1'].decisions, before.tasks['task-1'].decisions);
  await resumed.beginTask(); // repeated requirements-visible event
  assert.equal(resumed.getSnapshot().tasks['task-1'].deadline, before.tasks['task-1'].deadline);
});
