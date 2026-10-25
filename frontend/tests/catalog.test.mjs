import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { catalog, scenarios, feasiblePlans, alternativeFeasiblePlans } from '../src/mocks/scenarios.ts';
import { preparationDefinition } from '../src/services/studyPreparation.ts';
import { createMockExperimentService } from '../src/services/mockExperiment.ts';
import { acknowledge, startTask } from './study-helpers.mjs';

async function experimentalTask(scenarioId) {
  const service = createMockExperimentService({ sequenceId: scenarioId === 'B' ? 2 : 1 });
  await service.recordConsent(true);
  await service.saveDemographics({ age: 25, gender: 'Invented example', priorLlmUsage: 'weekly' });
  await acknowledge(service, 'before-start');
  await service.completeTutorial();
  await startTask(service);
  await service.finishTask();
  await startTask(service);
  return service;
}

test('expanded catalogs and preparation definitions match generated backend fixtures', () => {
  const fixture = name => JSON.parse(readFileSync(new URL(`../../backend/app/fixtures/${name}`, import.meta.url), 'utf8'));
  assert.deepEqual(fixture('catalog.json'), {
    version: 'catalog-v2', source: 'frontend/src/mocks/scenarios.ts', scenarios, items: catalog,
  });
  assert.deepEqual(fixture('reference-plans.json').plans, feasiblePlans);
  assert.deepEqual(fixture('reference-plans.json').alternatives, alternativeFeasiblePlans);
  assert.deepEqual(fixture('definitions.json').preparations, preparationDefinition);
});

test('A/B each have six options per category while practice stays at eight options', () => {
  assert.equal(new Set(catalog.map(item => item.id)).size, 44);
  assert.equal(catalog.filter(item => item.scenarioId === 'practice').length, 8);
  for (const id of ['A', 'B']) {
    for (const category of ['venue', 'catering', 'supplies']) {
      assert.equal(catalog.filter(item => item.scenarioId === id && item.category === category).length, 6);
    }
  }
  assert.equal(new Set(catalog.map(item => item.name)).size, catalog.length);
});

test('new options support distinct feasible plans, intended distractors, and cumulative budget checks', async () => {
  for (const id of ['A', 'B']) {
    const service = await experimentalTask(id);
    const task = () => service.getSnapshot().tasks['task-1'];
    const reference = feasiblePlans[id];
    const expectedCosts = id === 'A' ? [80000, 62500, 89000] : [120000, 102500, 129000];
    for (const [index, plan] of [reference, ...alternativeFeasiblePlans[id]].entries()) {
      await service.updatePlan(plan);
      assert.equal(task().totalCostCents, expectedCosts[index]);
      assert.deepEqual(task().constraints, { budget: true, capacity: true, dietary: true, accessibility: true });
    }
    for (const [plan, constraint] of [
      [{ ...reference, venue: `${id}-venue-near-capacity` }, 'capacity'],
      [{ ...reference, catering: `${id}-food-partial` }, 'dietary'],
      [{ ...reference, supplies: [`${id}-supplies-bundle`, `${id}-supplies-good`] }, 'budget'],
    ]) {
      await service.updatePlan(plan);
      assert.deepEqual(Object.entries(task().constraints).filter(([, met]) => !met).map(([key]) => key), [constraint]);
    }
    // Supplies remain optional, not an implicit equipment/completeness constraint.
    await service.updatePlan({ ...reference, supplies: [] });
    assert.ok(Object.values(task().constraints).every(Boolean));
    const plan = { ...reference, supplies: [`${id}-supplies-presentation`, `${id}-supplies-tableware`] };
    await service.updatePlan(plan);
    assert.equal(task().totalCostCents, id === 'A' ? 79000 : 119000);
    await service.updatePlan(plan);
    assert.deepEqual(task().plan.supplies, plan.supplies);
    assert.equal(task().totalCostCents, id === 'A' ? 79000 : 119000);
  }
});

test('new option search and inspection keep constraint facts out of summaries', async () => {
  for (const id of ['A', 'B']) {
    const service = await experimentalTask(id);
    const summaries = await service.searchCatalog(id);
    assert.equal(summaries.length, 18);
    for (const item of summaries) {
      assert.deepEqual(Object.keys(item).sort(), ['id', 'scenarioId', 'category', 'name', 'summary', 'priceCents'].sort());
      assert.doesNotMatch(`${item.name} ${item.summary}`, /\b(vegan|vegetarian|gluten|nut-free|wheelchair|stairs|step-free|capacity|servings|fails|insufficient)\b/i);
    }
    const chosen = alternativeFeasiblePlans[id][0];
    await service.updatePlan(chosen);
    const summary = summaries.find(item => item.id === `${id}-food-partial`);
    const found = await service.searchCatalog(id, summary.name.toUpperCase(), 'catering');
    assert.deepEqual(found.map(item => item.id), [summary.id]);
    const details = await service.inspectItem(summary.id);
    assert.equal(details.dietaryCoverage.length, 1);
    assert.match(details.details, /coverage is not provided/);
    assert.deepEqual(service.getSnapshot().tasks['task-1'].plan, chosen);
    assert.deepEqual(await service.searchCatalog(id, 'no such vendor'), []);
  }
});
