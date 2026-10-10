import assert from 'node:assert/strict';
import test from 'node:test';
import { createMockExperimentService } from '../src/services/mockExperiment.ts';
import { EXPERIMENTAL_TASK_MS, remainingSeconds } from '../src/services/taskTiming.ts';
import { acknowledge, startTask } from './study-helpers.mjs';

async function ready(service) {
  await service.recordConsent(true);
  await service.saveDemographics({ age: 25, gender: 'Invented example', priorLlmUsage: 'weekly' });
  await acknowledge(service, 'before-start');
  await service.completeTutorial(); await startTask(service); await service.finishTask();
  await startTask(service);
}

test('countdown derives from the absolute deadline and rounds up without negative values', () => {
  assert.equal(EXPERIMENTAL_TASK_MS, 900000);
  assert.equal(remainingSeconds(901000, 1000), 900);
  assert.equal(remainingSeconds(901000, 301000), 600);
  assert.equal(remainingSeconds(901000, 900999), 1);
  assert.equal(remainingSeconds(901000, 901000), 0);
  assert.equal(remainingSeconds(901000, 999000), 0);
});

test('late planning mutations expire the task before changing preserved work or routing', async () => {
  for (const operation of [
    service => service.updatePlan({ venue: 'A-venue-good', catering: null, supplies: [] }),
    service => service.inspectItem('A-venue-good'),
    service => service.requestRecommendation(),
    service => service.lockInitialChoice('small'),
    service => service.confirmModel('large'),
    service => service.sendMessage('Late response'),
    service => service.advanceCheckpoint(),
  ]) {
    let clock = 1000;
    const service = createMockExperimentService({ sequenceId: 3, now: () => clock });
    await ready(service);
    await service.lockInitialChoice('large');
    const before = service.getSnapshot().tasks['task-1'];
    clock = before.deadline + 5000;
    await assert.rejects(operation(service), { code: 'TASK_EXPIRED' });
    const ended = service.getSnapshot().tasks['task-1'];
    assert.equal(ended.status, 'timed-out');
    assert.equal(ended.endedAt, before.deadline);
    assert.deepEqual(ended.plan, before.plan);
    assert.deepEqual(ended.messages, before.messages);
    assert.deepEqual(ended.inspectedItems, before.inspectedItems);
    assert.deepEqual(ended.decisions, before.decisions);
    assert.equal(ended.decisions.Venue.initialModel, 'large');
    assert.equal(ended.decisions.Venue.recommendedModel, null);
    assert.equal(service.getSnapshot().step, 'tlx-1');
    assert.equal(service.getSnapshot().error, null);
  }
});

test('deadline/duplicate termination preserves a single end boundary and correct survey linkage', async () => {
  let clock = 500;
  const service = createMockExperimentService({ now: () => clock });
  await ready(service);
  const deadline = service.getSnapshot().tasks['task-1'].deadline;
  clock = deadline + 2000;
  const results = await Promise.allSettled([service.finishTask(), service.finishTask('timed-out')]);
  assert.equal(results[0].status, 'fulfilled');
  assert.equal(results[1].status, 'rejected');
  const ended = service.getSnapshot().tasks['task-1'];
  assert.equal(ended.endedAt, deadline);
  assert.equal(ended.status, 'timed-out');
  assert.equal(service.getSnapshot().step, 'tlx-1');
  assert.equal(service.getSnapshot().tasks['task-2'], undefined);
  assert.deepEqual(Object.keys(ended.decisions), ['Venue']);
  assert.equal(service.getSnapshot().pendingOperations, 0);
});

test('queued responses cannot cross an ended checkpoint or a reset session', async () => {
  const service = createMockExperimentService();
  await ready(service); await service.requestRecommendation();
  const old = service.getSnapshot().tasks['task-1'].decisions.Venue;
  const stageResults = await Promise.allSettled([service.advanceCheckpoint(), service.sendMessage('Old-stage response')]);
  assert.equal(stageResults[0].status, 'fulfilled');
  assert.equal(stageResults[1].status, 'rejected');
  assert.equal(stageResults[1].reason.code, 'STALE_OPERATION');
  assert.deepEqual(service.getSnapshot().tasks['task-1'].decisions.Venue, old);
  assert.deepEqual(service.getSnapshot().tasks['task-1'].messages, []);
  const resetResults = await Promise.allSettled([service.reset(4), service.updatePlan({ venue: null, catering: null, supplies: [] })]);
  assert.equal(resetResults[0].status, 'fulfilled');
  assert.equal(resetResults[1].status, 'rejected');
  assert.equal(resetResults[1].reason.code, 'STALE_OPERATION');
  assert.equal(service.getSnapshot().sequenceId, 4);
  assert.equal(service.getSnapshot().step, 'consent');
  assert.deepEqual(service.getSnapshot().tasks, {});
  assert.equal(service.getSnapshot().pendingOperations, 0);
  assert.equal(service.getSnapshot().error, null);
});
