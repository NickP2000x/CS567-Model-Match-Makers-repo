import assert from 'node:assert/strict';
import test from 'node:test';
import { createMockExperimentService } from '../src/services/mockExperiment.ts';
import { checkpoints, surveyDimensions } from '../src/services/experiment.types.ts';
import { feasiblePlans } from '../src/mocks/scenarios.ts';

const answers = Object.fromEntries(surveyDimensions.map(key => [key, 50]));
async function intro(service) {
  await service.recordConsent(true);
  await service.saveDemographics({ age: 25, gender: 'synthetic example', priorLlmUsage: 'occasional' });
  await service.completeTutorial();
  await service.beginTask();
}
async function practice(service) {
  await intro(service);
  await service.updatePlan(feasiblePlans.practice);
  await service.finishTask();
}

test('pending/error state is observable; failures do not bypass consent', async () => {
  const service = createMockExperimentService();
  const observed = [];
  const unsubscribe = service.subscribe(() => observed.push(service.getSnapshot().pendingOperations));
  await assert.rejects(service.completeTutorial(), { code: 'INVALID_STEP' });
  assert.equal(service.getSnapshot().step, 'consent');
  assert.equal(service.getSnapshot().error.code, 'INVALID_STEP');
  assert.ok(observed.includes(1));
  assert.equal(service.getSnapshot().pendingOperations, 0);
  await service.recordConsent(false);
  assert.equal(service.getSnapshot().step, 'consent');
  assert.equal(service.getSnapshot().error, null);
  assert.throws(() => { service.getSnapshot().step = 'completion'; }, TypeError);
  unsubscribe();
});

test('all catalogs have feasible plans and detail-only violations; summaries omit details', async () => {
  for (const scenarioId of ['practice', 'A', 'B']) {
    const service = createMockExperimentService({ sequenceId: scenarioId === 'B' ? 2 : 1 });
    await intro(service);
    if (scenarioId !== 'practice') { await service.finishTask(); await service.beginTask(); }
    const summaries = await service.searchCatalog(scenarioId, '', 'venue');
    assert.equal(summaries.length, 3);
    assert.equal('wheelchairAccessible' in summaries[0], false);
    assert.equal('details' in summaries[0], false);
    const hidden = await service.inspectItem(`${scenarioId}-venue-access`);
    assert.equal(hidden.wheelchairAccessible, false);
    await service.inspectItem(hidden.id);
    const id = scenarioId === 'practice' ? 'practice' : 'task-1';
    assert.deepEqual(service.getSnapshot().tasks[id].inspectedItems, [hidden.id]);
    await service.updatePlan(feasiblePlans[scenarioId]);
    assert.ok(Object.values(service.getSnapshot().tasks[id].constraints).every(Boolean));
    await service.updatePlan({ ...feasiblePlans[scenarioId], venue: hidden.id });
    assert.equal(service.getSnapshot().tasks[id].constraints.accessibility, false);
    await assert.rejects(service.updatePlan({ venue: 'unknown', catering: null, supplies: [] }), { code: 'INVALID_PLAN' });
    assert.equal(service.getSnapshot().tasks[id].plan.venue, hidden.id);
  }
});

for (const sequenceId of [1, 2, 3, 4]) {
  test(`sequence ${sequenceId}: four checkpoints, both tasks/surveys, no practice survey`, async () => {
    let clock = 1000;
    const service = createMockExperimentService({ sequenceId, now: () => ++clock });
    await practice(service);
    assert.equal(service.getSnapshot().tasks.practice.excludedFromResults, true);
    assert.equal(service.getSnapshot().step, 'task-1');
    await assert.rejects(service.saveSurveyAnswers('practice', answers), { code: 'INVALID_SURVEY' });
    for (const id of ['task-1', 'task-2']) {
      await service.beginTask();
      const task = service.getSnapshot().tasks[id];
      const expected = service.getSnapshot().assignments[id === 'task-1' ? 0 : 1];
      assert.equal(task.scenarioId, expected.scenarioId);
      assert.equal(task.condition, expected.condition);
      assert.equal(task.deadline - task.startedAt, 900000);
      await service.beginTask();
      assert.equal(service.getSnapshot().tasks[id].deadline, task.deadline);
      await service.updatePlan(feasiblePlans[task.scenarioId]);
      for (const stage of checkpoints) {
        if (task.condition === 'override') {
          await assert.rejects(service.requestRecommendation(), { code: 'INVALID_ROUTING_PHASE' });
          assert.equal(service.getSnapshot().tasks[id].decisions[stage].recommendedModel, null);
          await service.lockInitialChoice('large');
        } else {
          await assert.rejects(service.lockInitialChoice('small'), { code: 'INVALID_ROUTING_PHASE' });
        }
        const recommendation = await service.requestRecommendation();
        assert.deepEqual(await service.requestRecommendation(), recommendation);
        if (task.condition === 'override') await service.confirmModel('small');
        await service.sendMessage('Help with this stage');
        await assert.rejects(service.confirmModel('large'), { code: 'INVALID_ROUTING_PHASE' });
        assert.equal(service.getSnapshot().tasks[id].messages.at(-1).simulated, true);
        if (stage !== checkpoints.at(-1)) await service.advanceCheckpoint();
      }
      await service.finishTask();
      assert.equal(service.getSnapshot().step, id === 'task-1' ? 'tlx-1' : 'tlx-2');
      await assert.rejects(service.submitSurvey(id), { code: 'INCOMPLETE_SURVEY' });
      await service.saveSurveyAnswers(id, { mentalDemand: 0 });
      await service.saveSurveyAnswers(id, answers);
      await service.submitSurvey(id);
      assert.equal(Object.keys(service.getSnapshot().tasks[id].survey.answers).length, 6);
    }
    assert.equal(service.getSnapshot().step, 'completion');
    await service.reset(2);
    assert.equal(service.getSnapshot().step, 'consent');
    assert.deepEqual(service.getSnapshot().tasks, {});
  });
}

test('override retains independent initial and final choices for keep/change paths', async () => {
  for (const initial of ['small', 'large']) for (const final of ['small', 'large']) {
    const service = createMockExperimentService({ sequenceId: 3 });
    await practice(service); await service.beginTask();
    await service.lockInitialChoice(initial); await service.requestRecommendation(); await service.confirmModel(final);
    const d = service.getSnapshot().tasks['task-1'].decisions.Venue;
    assert.equal(d.initialModel, initial); assert.equal(d.finalModel, final);
    assert.ok(d.initialLockedAt <= d.recommendationShownAt);
    assert.ok(d.recommendationShownAt <= d.finalCommittedAt);
  }
});

test('each scenario supports independent constraint violations and incomplete submission', async () => {
  for (const scenarioId of ['practice', 'A', 'B']) {
    const service = createMockExperimentService({ sequenceId: scenarioId === 'B' ? 2 : 1 });
    await intro(service);
    if (scenarioId !== 'practice') { await service.finishTask(); await service.beginTask(); }
    const id = scenarioId === 'practice' ? 'practice' : 'task-1';
    const reference = feasiblePlans[scenarioId];
    const variants = [
      ['capacity', { ...reference, venue: `${scenarioId}-venue-capacity` }],
      ['accessibility', { ...reference, venue: `${scenarioId}-venue-access` }],
      ['dietary', { ...reference, catering: `${scenarioId}-food-diet` }],
      ['dietary', { ...reference, catering: `${scenarioId}-food-servings` }],
      ['budget', { ...reference, supplies: [`${scenarioId}-supplies-cost`] }],
    ];
    for (const [failedConstraint, plan] of variants) {
      await service.updatePlan(plan);
      assert.deepEqual(service.getSnapshot().tasks[id].constraints,
        Object.fromEntries(['budget', 'capacity', 'dietary', 'accessibility'].map(key => [key, key !== failedConstraint])));
    }
    const scenario = await service.getScenario(scenarioId);
    const summaries = await service.searchCatalog(scenarioId);
    assert.ok(summaries.every(item => item.priceCents <= scenario.requirements.budgetCents));
    for (const item of summaries) {
      for (const detail of ['details', 'capacity', 'wheelchairAccessible', 'servings', 'dietaryCoverage']) {
        assert.equal(detail in item, false);
      }
    }
    await service.updatePlan({ venue: reference.venue, catering: null, supplies: [] });
    const before = service.getSnapshot().tasks[id];
    await service.finishTask();
    assert.equal(service.getSnapshot().tasks[id].status, 'submitted');
    assert.deepEqual(service.getSnapshot().tasks[id].plan, before.plan);
    assert.deepEqual(service.getSnapshot().tasks[id].constraints, before.constraints);
    assert.deepEqual(Object.keys(service.getSnapshot().tasks[id].decisions), ['Venue']);
    assert.equal(service.getSnapshot().tasks[id].decisions.Venue.recommendedModel, null);
    assert.equal(service.getSnapshot().step, id === 'practice' ? 'task-1' : 'tlx-1');
  }
});

test('ended tasks reject duplicate termination and mutations without changing recorded work', async () => {
  const service = createMockExperimentService({ sequenceId: 3 });
  await practice(service); await service.beginTask();
  await service.lockInitialChoice('large');
  await service.updatePlan(feasiblePlans.A);
  await service.inspectItem('A-venue-good');
  await service.finishTask('timed-out');
  const ended = service.getSnapshot().tasks['task-1'];
  for (const operation of [
    () => service.finishTask(),
    () => service.updatePlan({ venue: null, catering: null, supplies: [] }),
    () => service.inspectItem('A-food-good'),
    () => service.requestRecommendation(),
    () => service.confirmModel('small'),
    () => service.sendMessage('Late message'),
    () => service.advanceCheckpoint(),
    () => service.beginTask(),
  ]) {
    await assert.rejects(operation());
    assert.deepEqual(service.getSnapshot().tasks['task-1'], ended);
  }
  assert.equal(ended.decisions.Venue.initialModel, 'large');
  assert.equal(ended.decisions.Venue.recommendedModel, null);
  assert.equal(ended.decisions.Venue.finalModel, null);
  assert.throws(() => { ended.plan.supplies.push('another-item'); }, TypeError);
  await assert.rejects(service.saveSurveyAnswers('task-1', { performance: 101 }), { code: 'INVALID_SURVEY' });
  assert.deepEqual(service.getSnapshot().tasks['task-1'].survey.answers, {});
  await assert.rejects(service.saveSurveyAnswers('task-2', answers), { code: 'INVALID_SURVEY' });
});

test('documented contract walkthroughs preserve automatic/override and submission/survey payloads', async () => {
  for (const sequenceId of [1, 3]) {
    const service = createMockExperimentService({ sequenceId });
    await intro(service); await service.finishTask(); await service.beginTask();
    if (sequenceId === 3) {
      await assert.rejects(service.requestRecommendation(), { code: 'INVALID_ROUTING_PHASE' });
      await service.lockInitialChoice('large');
    }
    const recommendation = await service.requestRecommendation();
    assert.equal(recommendation.recommendedModel, 'small');
    assert.equal(recommendation.initialModel, sequenceId === 3 ? 'large' : null);
    if (sequenceId === 3) await service.confirmModel('small');
    await service.sendMessage('Compare venue options');
    await service.updatePlan({ venue: 'A-venue-good', catering: null, supplies: [] });
    await service.finishTask();
    const task = service.getSnapshot().tasks['task-1'];
    assert.equal(task.totalCostCents, 30000);
    assert.deepEqual(task.constraints, { budget: true, capacity: true, dietary: false, accessibility: true });
    assert.equal(task.decisions.Venue.finalModel, 'small');
    assert.equal(task.messages.at(-1).model, 'small');
    const raw = { mentalDemand: 20, physicalDemand: 0, temporalDemand: 40, performance: 60, effort: 30, frustration: 10 };
    await service.saveSurveyAnswers('task-1', raw); await service.submitSurvey('task-1');
    assert.deepEqual(service.getSnapshot().tasks['task-1'].survey.answers, raw);
    assert.equal(service.getSnapshot().step, 'task-2');
    assert.equal(service.getSnapshot().tasks['task-2'], undefined);
    await assert.rejects(service.submitSurvey('task-1'), { code: 'INCOMPLETE_SURVEY' });
  }
});

test('expired incomplete task preserves work and rejects late updates; fresh instance resets', async () => {
  let clock = 100;
  const service = createMockExperimentService({ now: () => clock });
  await practice(service); await service.beginTask(); await service.requestRecommendation();
  await service.sendMessage('A partial plan');
  clock = service.getSnapshot().tasks['task-1'].deadline;
  const finish = service.finishTask();
  const late = service.sendMessage('Too late');
  await finish; await assert.rejects(late, { code: 'NO_ACTIVE_TASK' });
  assert.equal(service.getSnapshot().tasks['task-1'].status, 'timed-out');
  assert.equal(service.getSnapshot().tasks['task-1'].messages.length, 2);
  assert.equal(service.getSnapshot().step, 'tlx-1');
  assert.equal(createMockExperimentService().getSnapshot().step, 'consent');
});
