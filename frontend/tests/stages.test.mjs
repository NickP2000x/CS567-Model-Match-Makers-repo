import assert from 'node:assert/strict';
import test from 'node:test';
import { catalogMatches, stageCategory, stageComplete } from '../src/features/planning/stages.ts';

const none = { budget: true, capacity: false, dietary: false, accessibility: false, supplies: false, location: false };

test('a stage is complete only when its own constraints are met', () => {
  assert.equal(stageComplete('Venue', { ...none, capacity: true, accessibility: true }), false);
  assert.equal(stageComplete('Venue', { ...none, capacity: true, accessibility: true, location: true }), true);
  assert.equal(stageComplete('Catering', { ...none, dietary: true }), true);
  assert.equal(stageComplete('Supplies', { ...none, supplies: true }), true);
  const all = Object.fromEntries(Object.keys(none).map(key => [key, true]));
  assert.equal(stageComplete('Final constraint check', all), false);  // never auto-advances
  assert.deepEqual(['Venue', 'Catering', 'Supplies', 'Final constraint check'].map(stageCategory),
    ['venue', 'catering', 'supplies', null]);
});

test('catalog filtering matches names or summaries within a category', () => {
  const item = { id: 'v', scenarioId: 'A', category: 'venue', name: 'Willow Hall', summary: 'A bright room', priceCents: 1 };
  assert.equal(catalogMatches(item, '', ''), true);
  assert.equal(catalogMatches(item, ' BRIGHT ', 'venue'), true);
  assert.equal(catalogMatches(item, 'willow', 'catering'), false);
  assert.equal(catalogMatches(item, 'capacity', ''), false);  // details are not searched
});
