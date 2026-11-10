import assert from 'node:assert/strict';
import { mock, test } from 'node:test';
import { AGENT_ACTIVITY_LABEL, PHRASE_INTERVAL_MS, startPhraseRotation } from '../src/features/planning/phraseRotation.ts';
import { AGENT_STATUS_MESSAGES } from '../src/features/planning/agentStatusMessages.ts';
import { createMockExperimentService } from '../src/services/mockExperiment.ts';
import { acknowledge, startTask } from './study-helpers.mjs';

function withFakeTimers(run) {
  mock.timers.enable({ apis: ['setInterval'] });
  try { return run(); } finally { mock.timers.reset(); }
}

test('the editable phrase list exists and is plain text', () => {
  assert.ok(AGENT_STATUS_MESSAGES.length > 0);
  assert.ok(AGENT_STATUS_MESSAGES.every(phrase => typeof phrase === 'string' && phrase.trim()));
  assert.equal(PHRASE_INTERVAL_MS, 4000);
});

test('the first phrase shows immediately, then rotates every four seconds and wraps', () => withFakeTimers(() => {
  const shown = [];
  const stop = startPhraseRotation(['One', 'Two', 'Three'], phrase => shown.push(phrase));
  assert.deepEqual(shown, ['One']);
  mock.timers.tick(3999);
  assert.deepEqual(shown, ['One']);
  mock.timers.tick(1);
  mock.timers.tick(PHRASE_INTERVAL_MS * 2);
  assert.deepEqual(shown, ['One', 'Two', 'Three', 'One']);
  stop();
}));

test('each request starts from the first phrase and stop() ends all updates', () => withFakeTimers(() => {
  const first = [];
  const stopFirst = startPhraseRotation(['One', 'Two'], phrase => first.push(phrase));
  mock.timers.tick(PHRASE_INTERVAL_MS);
  stopFirst();
  mock.timers.tick(PHRASE_INTERVAL_MS * 5);
  assert.deepEqual(first, ['One', 'Two']);
  const second = [];
  const stopSecond = startPhraseRotation(['One', 'Two'], phrase => second.push(phrase));
  assert.deepEqual(second, ['One']);
  stopSecond();
  stopSecond();  // Safe to call twice (e.g. cleanup after a late response).
}));

test('a single phrase needs no timer and an empty list falls back to the stable label', () => {
  const calls = [];
  const timers = { setInterval: () => { calls.push('set'); return 1; }, clearInterval: () => calls.push('clear') };
  const single = [];
  startPhraseRotation(['Only one'], phrase => single.push(phrase), timers)();
  const empty = [];
  startPhraseRotation([], phrase => empty.push(phrase), timers)();
  assert.deepEqual(single, ['Only one']);
  assert.deepEqual(empty, [AGENT_ACTIVITY_LABEL]);
  assert.deepEqual(calls, []);
});

test('custom phrases are passed through unchanged, including markup-like text', () => {
  const shown = [];
  startPhraseRotation(['<b>Brewing coffee</b>…'], phrase => shown.push(phrase))();
  assert.deepEqual(shown, ['<b>Brewing coffee</b>…']);
});

test('sending a message stores only the participant and agent messages', async () => {
  const service = createMockExperimentService({ sequenceId: 1 });
  await service.recordConsent(true);
  await service.saveDemographics({ age: 25, gender: 'Invented example', priorLlmUsage: 'weekly' });
  await acknowledge(service, 'before-start');
  await service.completeTutorial();
  await startTask(service);
  await service.sendMessage('Which venue fits?');
  const texts = service.getSnapshot().tasks.practice.messages.map(message => message.text);
  assert.equal(texts.length, 2);
  assert.ok(texts.every(text => !AGENT_STATUS_MESSAGES.includes(text) && text !== AGENT_ACTIVITY_LABEL));
});
