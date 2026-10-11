import assert from 'node:assert/strict';
import test from 'node:test';
import { createApiExperimentService, SESSION_STORAGE_KEY } from '../src/services/apiExperiment.ts';

// Offline checks of the network adapter (#39) with a scripted fetch; no backend needed.

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => { values.set(key, String(value)); },
    removeItem: key => { values.delete(key); },
  };
}

function serverState(overrides = {}) {
  return {
    sessionId: 's1', participantId: 'dev-s1', sequenceId: 1,
    assignments: [{ scenarioId: 'A', condition: 'automatic' }, { scenarioId: 'B', condition: 'override' }],
    step: 'consent', consent: null, demographics: null, tasks: {}, preparations: {}, feedback: null,
    simulated: true, ...overrides,
  };
}

function activeTask(checkpoint = 'Venue', decisions = {}) {
  return {
    id: 'task-1', scenarioId: 'A', condition: 'automatic', excludedFromResults: false, status: 'active',
    startedAt: 1, deadline: 900001, endedAt: null, checkpoint, decisions, messages: [], inspectedItems: [],
    plan: { venue: null, catering: null, supplies: [] }, totalCostCents: 0,
    constraints: { budget: true, capacity: false, dietary: false, accessibility: false },
    survey: { answers: {}, metadata: null, rawScore: null, submittedAt: null },
  };
}

// Responds to "METHOD /path" keys in order; records every request.
function scriptedFetch(responses) {
  const calls = [];
  const fetch = async (url, init = {}) => {
    const { pathname, search } = new URL(url);
    const key = `${init.method} ${pathname}`;
    calls.push({ key, search, body: init.body === undefined ? undefined : JSON.parse(init.body) });
    const queue = responses[key];
    if (!queue || queue.length === 0) throw new Error(`Unexpected request ${key}`);
    const next = queue.shift();
    if (next instanceof Error) throw next;
    const [status, body] = next;
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  };
  return { fetch, calls };
}

const base = { baseUrl: 'http://backend.test/' };

test('connects by creating a development session; a refresh resumes it', async () => {
  const storage = memoryStorage();
  const first = scriptedFetch({ 'POST /api/sessions': [[201, serverState()]] });
  const service = await createApiExperimentService({ ...base, fetch: first.fetch, storage, developmentSequence: 2 });
  assert.deepEqual(first.calls[0].body, { sequenceId: 2 });
  assert.equal(storage.getItem(SESSION_STORAGE_KEY), 's1');
  assert.equal(service.getSnapshot().step, 'consent');
  assert.equal(service.getSnapshot().refreshRestartsDemo, false);

  const resumed = scriptedFetch({ 'GET /api/sessions/s1': [[200, serverState({ step: 'tutorial' })]] });
  const again = await createApiExperimentService({ ...base, fetch: resumed.fetch, storage });
  assert.deepEqual(resumed.calls.map(call => call.key), ['GET /api/sessions/s1']);
  assert.equal(again.getSnapshot().step, 'tutorial');
});

test('a missing stored session is replaced; participant builds request allocation', async () => {
  const storage = memoryStorage({ [SESSION_STORAGE_KEY]: 'old' });
  const { fetch, calls } = scriptedFetch({
    'GET /api/sessions/old': [[404, { error: { code: 'SESSION_NOT_FOUND', message: 'Session not found.' } }]],
    'POST /api/sessions': [[201, serverState({ sessionId: 's2', participantId: 'P03' })]],
  });
  const service = await createApiExperimentService({ ...base, fetch, storage });
  assert.deepEqual(calls[1].body, {});
  assert.equal(service.getSnapshot().participantId, 'P03');
  assert.equal(storage.getItem(SESSION_STORAGE_KEY), 's2');
});

test('connection failures reject so the app can show the server error', async () => {
  const { fetch } = scriptedFetch({ 'POST /api/sessions': [new TypeError('fetch failed')] });
  await assert.rejects(createApiExperimentService({ ...base, fetch, storage: memoryStorage() }), { code: 'NETWORK_ERROR' });
  const full = scriptedFetch({ 'POST /api/sessions': [[409, { error: { code: 'ALLOCATION_FULL', message: 'All study slots are allocated.' } }]] });
  await assert.rejects(createApiExperimentService({ ...base, fetch: full.fetch, storage: memoryStorage() }),
    { code: 'ALLOCATION_FULL', message: 'All study slots are allocated.' });
});

test('planning requests name the task and checkpoint and return the committed decision', async () => {
  const decision = { phase: 'committed', initialModel: null, recommendedModel: 'large', finalModel: 'large',
    reason: 'Simulated recommendation.', shownAt: 1, initialLockedAt: null, recommendationShownAt: 2, finalCommittedAt: 2 };
  const before = serverState({ step: 'task-1', tasks: { 'task-1': activeTask('Catering', { Catering: { ...decision, phase: 'awaiting-recommendation' } }) } });
  const after = serverState({ step: 'task-1', tasks: { 'task-1': activeTask('Catering', { Catering: decision }) } });
  const { fetch, calls } = scriptedFetch({
    'POST /api/sessions': [[201, before]],
    'POST /api/sessions/s1/tasks/task-1/routing/recommendation': [[200, after]],
    'PUT /api/sessions/s1/tasks/task-1/plan': [[200, after]],
    'GET /api/scenarios/A/catalog': [[200, []]],
  });
  const service = await createApiExperimentService({ ...base, fetch, storage: memoryStorage() });
  assert.deepEqual(await service.requestRecommendation(), decision);
  assert.deepEqual(calls[1].body, { checkpoint: 'Catering' });
  await service.updatePlan({ venue: 'A-venue-good', catering: null, supplies: [] });
  assert.deepEqual(calls[2].body, { plan: { venue: 'A-venue-good', catering: null, supplies: [] }, checkpoint: 'Catering' });
  await service.searchCatalog('A', 'Hall', 'venue');
  assert.equal(calls[3].search, '?query=Hall&category=venue');
});

test('errors are exposed and keep state; pending operations are observable', async () => {
  const { fetch } = scriptedFetch({
    'POST /api/sessions': [[201, serverState()]],
    'POST /api/sessions/s1/tutorial/complete': [[409, { error: { code: 'INVALID_STEP', message: 'Complete demographics first.' } }]],
    'POST /api/sessions/s1/consent': [[200, serverState({ step: 'demographics', consent: true })]],
  });
  const service = await createApiExperimentService({ ...base, fetch, storage: memoryStorage() });
  const pending = [];
  service.subscribe(() => pending.push(service.getSnapshot().pendingOperations));
  await assert.rejects(service.completeTutorial(), { code: 'INVALID_STEP', message: 'Complete demographics first.' });
  assert.equal(service.getSnapshot().step, 'consent');
  assert.deepEqual(service.getSnapshot().error, { code: 'INVALID_STEP', message: 'Complete demographics first.' });
  assert.ok(pending.includes(1));
  assert.equal(service.getSnapshot().pendingOperations, 0);
  await service.recordConsent(true);
  assert.equal(service.getSnapshot().step, 'demographics');
  assert.equal(service.getSnapshot().error, null);
  assert.throws(() => { service.getSnapshot().step = 'completion'; }, TypeError);
});

test('an expired task publishes the ended state without a screen error', async () => {
  const ended = serverState({ step: 'tlx-1', tasks: { 'task-1': { ...activeTask(), status: 'timed-out', endedAt: 900001 } } });
  const { fetch } = scriptedFetch({
    'POST /api/sessions': [[201, serverState({ step: 'task-1', tasks: { 'task-1': activeTask() } })]],
    'PUT /api/sessions/s1/tasks/task-1/plan': [[409, { error: { code: 'TASK_EXPIRED', message: 'The task deadline has passed.' }, state: ended }]],
  });
  const service = await createApiExperimentService({ ...base, fetch, storage: memoryStorage() });
  await assert.rejects(service.updatePlan({ venue: null, catering: null, supplies: [] }), { code: 'TASK_EXPIRED' });
  assert.equal(service.getSnapshot().step, 'tlx-1');
  assert.equal(service.getSnapshot().tasks['task-1'].status, 'timed-out');
  assert.equal(service.getSnapshot().error, null);
});

test('local guards reject impossible requests without calling the server', async () => {
  const { fetch, calls } = scriptedFetch({ 'POST /api/sessions': [[201, serverState()]] });
  const service = await createApiExperimentService({ ...base, fetch, storage: memoryStorage() });
  await assert.rejects(service.beginTask(), { code: 'INVALID_STEP' });
  await assert.rejects(service.updatePlan({ venue: null, catering: null, supplies: [] }), { code: 'NO_ACTIVE_TASK' });
  await assert.rejects(service.finishTask(), { code: 'NO_ACTIVE_TASK' });
  await assert.rejects(service.saveSurveyAnswers('practice', {}), { code: 'INVALID_SURVEY' });
  assert.equal(calls.length, 1);
  assert.equal(service.getSnapshot().pendingOperations, 0);
});

test('a server failure without a JSON body still reports a typed error', async () => {
  const fetch = async (url, init = {}) => init.method === 'POST' && new URL(url).pathname === '/api/sessions'
    ? new Response(JSON.stringify(serverState()), { status: 201 })
    : new Response('Internal Server Error', { status: 500 });
  const service = await createApiExperimentService({ ...base, fetch, storage: memoryStorage() });
  await assert.rejects(service.recordConsent(true), { code: 'SERVER_ERROR' });
  assert.equal(service.getSnapshot().step, 'consent');
});

test('development reset switches to the new session', async () => {
  const storage = memoryStorage();
  const { fetch, calls } = scriptedFetch({
    'POST /api/sessions': [[201, serverState()]],
    'POST /api/sessions/s1/reset': [[201, serverState({ sessionId: 's9', sequenceId: 4 })]],
    'POST /api/sessions/s9/consent': [[200, serverState({ sessionId: 's9', sequenceId: 4, step: 'demographics' })]],
  });
  const service = await createApiExperimentService({ ...base, fetch, storage, developmentSequence: 1 });
  await service.reset(4);
  assert.deepEqual(calls[1].body, { sequenceId: 4 });
  assert.equal(storage.getItem(SESSION_STORAGE_KEY), 's9');
  await service.recordConsent(true);
  assert.equal(calls[2].key, 'POST /api/sessions/s9/consent');
});
