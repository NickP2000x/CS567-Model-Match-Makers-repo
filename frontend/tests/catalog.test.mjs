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
    version: 'catalog-v4', source: 'frontend/src/mocks/scenarios.ts', scenarios, items: catalog,
  });
  assert.deepEqual(fixture('reference-plans.json').plans, feasiblePlans);
  assert.deepEqual(fixture('reference-plans.json').alternatives, alternativeFeasiblePlans);
  assert.deepEqual(fixture('definitions.json').preparations, preparationDefinition);
});

test('A/B each have 15 options per category while practice stays at eight options', () => {
  assert.equal(new Set(catalog.map(item => item.id)).size, 98);
  assert.equal(catalog.filter(item => item.scenarioId === 'practice').length, 8);
  for (const id of ['A', 'B']) {
    for (const category of ['venue', 'catering', 'supplies']) {
      assert.equal(catalog.filter(item => item.scenarioId === id && item.category === category).length, 15);
    }
  }
  assert.equal(new Set(catalog.map(item => item.name)).size, catalog.length);
});

test('catalog order is a fixed shuffle, not grouped by category or by original option order', () => {
  for (const id of ['A', 'B']) {
    const items = catalog.filter(item => item.scenarioId === id);
    assert.equal(new Set(items.slice(0, 12).map(item => item.category)).size, 3, 'categories are interleaved');
    const venues = items.filter(item => item.category === 'venue').map(item => item.id);
    assert.notDeepEqual(venues.slice(0, 3), [`${id}-venue-good`, `${id}-venue-capacity`, `${id}-venue-access`]);
    assert.ok(venues.filter(item => !/-\d\d$/.test(item)).some((_, index, legacy) => index > 0
      && venues.indexOf(legacy[index]) - venues.indexOf(legacy[index - 1]) > 1), 'original options are spread out');
  }
});

test('every venue has a fictional area in its details; summaries never reveal it', () => {
  const areaNames = ['Riverside', 'North Quarter', 'East Side', 'Old Town', 'Harbor Front', 'Hillside', 'Market District'];
  for (const item of catalog) {
    if (item.category !== 'venue') { assert.equal(item.areaId, undefined, item.id); continue; }
    assert.ok(item.areaId, item.id);
    assert.ok(areaNames.some(name => item.details.includes(`Located in ${name}.`)), item.id);
    assert.ok(!areaNames.some(name => item.summary.includes(name)), item.id);
  }
  for (const scenario of scenarios) {
    const venues = catalog.filter(item => item.scenarioId === scenario.id && item.category === 'venue');
    assert.equal(venues.filter(item => item.areaId !== scenario.requirements.area.id).length, scenario.id === 'practice' ? 0 : 3);
  }
});

test('the practice reference plan passes all six constraints', async () => {
  const service = createMockExperimentService({ sequenceId: 1 });
  await service.recordConsent(true);
  await service.saveDemographics({ age: 25, gender: 'Invented example', priorLlmUsage: 'weekly' });
  await acknowledge(service, 'before-start');
  await service.completeTutorial();
  await startTask(service);
  await service.updatePlan(feasiblePlans.practice);
  assert.deepEqual(service.getSnapshot().tasks.practice.constraints,
    { budget: true, capacity: true, dietary: true, accessibility: true, supplies: true, location: true });
});

test('generated options include feasible choices and detail-only distractors for each constraint', async () => {
  for (const id of ['A', 'B']) {
    const service = await experimentalTask(id);
    const task = () => service.getSnapshot().tasks['task-1'];
    const reference = feasiblePlans[id];
    const generated = catalog.filter(item => item.scenarioId === id && /-\d\d$/.test(item.id));
    assert.equal(generated.length, 27);
    const broken = new Set();
    for (const item of generated) {
      const plan = { ...reference, supplies: [...reference.supplies] };
      if (item.category === 'supplies') plan.supplies = [item.id];
      else plan[item.category === 'venue' ? 'venue' : 'catering'] = item.id;
      await service.updatePlan(plan);
      const failing = Object.entries(task().constraints).filter(([, met]) => !met).map(([key]) => key);
      assert.ok(failing.length <= 1, `${item.id} breaks ${failing}`);
      failing.forEach(key => broken.add(key));
    }
    assert.deepEqual([...broken].sort(), ['accessibility', 'capacity', 'dietary', 'location', 'supplies']);
  }
});

test('new options support distinct feasible plans, intended distractors, and cumulative budget checks', async () => {
  for (const id of ['A', 'B']) {
    const service = await experimentalTask(id);
    const task = () => service.getSnapshot().tasks['task-1'];
    const reference = feasiblePlans[id];
    const expectedCosts = id === 'A' ? [80000, 67500, 92500] : [120000, 106500, 131500];
    for (const [index, plan] of [reference, ...alternativeFeasiblePlans[id]].entries()) {
      await service.updatePlan(plan);
      assert.equal(task().totalCostCents, expectedCosts[index]);
      assert.deepEqual(task().constraints, { budget: true, capacity: true, dietary: true, accessibility: true, supplies: true, location: true });
    }
    for (const [plan, constraint] of [
      [{ ...reference, venue: `${id}-venue-near-capacity` }, 'capacity'],
      [{ ...reference, catering: `${id}-food-partial` }, 'dietary'],
      [{ ...reference, supplies: [`${id}-supplies-bundle`, `${id}-supplies-good`] }, 'budget'],
      [{ ...reference, supplies: [`${id}-supplies-stationery`] }, 'supplies'],
    ]) {
      await service.updatePlan(plan);
      assert.deepEqual(Object.entries(task().constraints).filter(([, met]) => !met).map(([key]) => key), [constraint]);
    }
    // Supplies are scored only by required items; with none selected, only that check fails.
    await service.updatePlan({ ...reference, supplies: [] });
    assert.deepEqual(Object.entries(task().constraints).filter(([, met]) => !met).map(([key]) => key), ['supplies']);
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
    assert.equal(summaries.length, 45);
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
