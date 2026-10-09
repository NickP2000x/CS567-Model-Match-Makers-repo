import { catalog, scenarios } from '../mocks/scenarios.ts';
import { cannedResponse, recommendations } from '../mocks/responses.ts';
import { checkpoints, surveyDimensions } from './experiment.types.ts';
import type { Assignment, Decision, ExperimentService, Model, SequenceId, StudyState, Task, TaskId } from './experiment.types.ts';

const sequences: Record<SequenceId, [Assignment, Assignment]> = {
  1: [{ scenarioId: 'A', condition: 'automatic' }, { scenarioId: 'B', condition: 'override' }],
  2: [{ scenarioId: 'B', condition: 'automatic' }, { scenarioId: 'A', condition: 'override' }],
  3: [{ scenarioId: 'A', condition: 'override' }, { scenarioId: 'B', condition: 'automatic' }],
  4: [{ scenarioId: 'B', condition: 'override' }, { scenarioId: 'A', condition: 'automatic' }],
};
export class ExperimentError extends Error {
  constructor(publicCode: string, message: string) { super(message); this.code = publicCode; }
  readonly code: string;
}
function fail(code: string, message: string): never { throw new ExperimentError(code, message); }
function freeze<T>(value: T): T {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}
function initial(sequenceId: SequenceId): StudyState {
  if (!sequences[sequenceId]) fail('INVALID_SEQUENCE', 'Choose mock sequence 1–4.');
  return {
    participantId: `demo-sequence-${sequenceId}`, sequenceId, assignments: structuredClone(sequences[sequenceId]),
    step: 'consent', consent: null, demographics: null, tasks: {}, pendingOperations: 0, error: null,
    simulated: true, refreshRestartsDemo: true,
  };
}
function active(state: StudyState): Task {
  const task = state.tasks[state.step as TaskId];
  if (!task || task.status !== 'active') fail('NO_ACTIVE_TASK', 'Start an active planning task first.');
  return task;
}
function decision(task: Task): Decision { return task.decisions[task.checkpoint]!; }
function modelCheck(model: Model) {
  if (model !== 'small' && model !== 'large') fail('INVALID_MODEL', 'Choose small or large.');
}
function newDecision(task: Task, now: number): Decision {
  const practice = task.condition === 'practice';
  return { phase: practice ? 'committed' : task.condition === 'override' ? 'choose' : 'awaiting-recommendation',
    initialModel: null, recommendedModel: null, finalModel: practice ? 'small' : null, reason: null,
    shownAt: now, initialLockedAt: null, recommendationShownAt: null, finalCommittedAt: practice ? now : null };
}
function evaluate(task: Task) {
  const chosen = [task.plan.venue, task.plan.catering, ...task.plan.supplies].filter(Boolean);
  const items = catalog.filter(item => chosen.includes(item.id));
  const venue = items.find(item => item.category === 'venue');
  const food = items.find(item => item.category === 'catering');
  const r = scenarios.find(s => s.id === task.scenarioId)!.requirements;
  task.totalCostCents = items.reduce((sum, item) => sum + item.priceCents, 0);
  task.constraints = { budget: task.totalCostCents <= r.budgetCents,
    capacity: (venue?.capacity ?? 0) >= r.attendees,
    dietary: (food?.servings ?? 0) >= r.attendees && r.dietaryNeeds.every(need => food?.dietaryCoverage?.includes(need)),
    accessibility: !r.wheelchairRequired || venue?.wheelchairAccessible === true };
}

export function createMockExperimentService(options: { sequenceId?: SequenceId; now?: () => number } = {}): ExperimentService {
  const now = options.now ?? Date.now;
  let state = freeze(initial(options.sequenceId ?? 1));
  const listeners = new Set<() => void>();
  const publish = (next: StudyState) => { state = freeze(next); listeners.forEach(listener => listener()); };
  async function run<T>(operation: (draft: StudyState) => T): Promise<T> {
    publish({ ...state, pendingOperations: state.pendingOperations + 1, error: null });
    // Expose a real pending state without a network, timer, or provider dependency.
    await Promise.resolve();
    try {
      const draft = structuredClone(state);
      const result = operation(draft);
      publish(draft);
      return structuredClone(result);
    } catch (error) {
      const failure = error instanceof ExperimentError ? error : new ExperimentError('MOCK_ERROR', 'Mock operation failed.');
      publish({ ...state, error: { code: failure.code, message: failure.message } });
      throw failure;
    } finally { publish({ ...state, pendingOperations: state.pendingOperations - 1 }); }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    reset: sequenceId => run(draft => {
      const next = initial(sequenceId ?? draft.sequenceId);
      Object.assign(draft, next, { pendingOperations: draft.pendingOperations });
    }),
    recordConsent: accepted => run(draft => {
      if (draft.step !== 'consent') fail('INVALID_STEP', 'Consent is the first step.');
      draft.consent = accepted;
      if (accepted) draft.step = 'demographics';
    }),
    saveDemographics: values => run(draft => {
      if (draft.step !== 'demographics') fail('INVALID_STEP', 'Complete consent first.');
      if (!Number.isInteger(values.age) || values.age < 0 || !values.gender.trim() || !values.priorLlmUsage.trim())
        fail('INVALID_DEMOGRAPHICS', 'Enter synthetic age, gender, and prior LLM usage.');
      draft.demographics = { ...values }; draft.step = 'tutorial';
    }),
    completeTutorial: () => run(draft => {
      if (draft.step !== 'tutorial') fail('INVALID_STEP', 'Complete demographics first.');
      draft.step = 'practice';
    }),
    getScenario: id => run(() => scenarios.find(s => s.id === id) ?? fail('NOT_FOUND', 'Scenario not found.')),
    searchCatalog: (id, query = '', category) => run(() => {
      if (!scenarios.some(s => s.id === id)) fail('NOT_FOUND', 'Scenario not found.');
      return catalog.filter(item => item.scenarioId === id && (!category || item.category === category)
        && `${item.name} ${item.summary}`.toLowerCase().includes(query.toLowerCase()))
        .map(({ id, scenarioId, category, name, summary, priceCents }) => ({ id, scenarioId, category, name, summary, priceCents }));
    }),
    inspectItem: id => run(draft => {
      const task = active(draft);
      const item = catalog.find(item => item.id === id && item.scenarioId === task.scenarioId)
        ?? fail('NOT_FOUND', 'Item not found in this task.');
      if (!task.inspectedItems.includes(id)) task.inspectedItems.push(id);
      return item;
    }),
    beginTask: () => run(draft => {
      if (!['practice', 'task-1', 'task-2'].includes(draft.step)) fail('INVALID_STEP', 'Reach a planning step first.');
      const id = draft.step as TaskId;
      if (draft.tasks[id]) return; // Repeated visibility events do not restart deadlines.
      const assignment = id === 'practice' ? { scenarioId: 'practice' as const, condition: 'practice' as const }
        : draft.assignments[id === 'task-1' ? 0 : 1];
      const start = now();
      const task: Task = { id, ...assignment, excludedFromResults: id === 'practice', status: 'active',
        startedAt: start, deadline: id === 'practice' ? null : start + 15 * 60 * 1000, endedAt: null,
        checkpoint: 'Venue', decisions: {}, messages: [], inspectedItems: [],
        plan: { venue: null, catering: null, supplies: [] }, totalCostCents: 0,
        constraints: { budget: true, capacity: false, dietary: false, accessibility: false },
        survey: { answers: {}, submittedAt: null } };
      task.decisions.Venue = newDecision(task, start); draft.tasks[id] = task;
    }),
    updatePlan: plan => run(draft => {
      const task = active(draft);
      const entries = [['venue', plan.venue], ['catering', plan.catering], ...plan.supplies.map(id => ['supplies', id])];
      for (const [category, id] of entries) {
        if (id && !catalog.some(item => item.id === id && item.scenarioId === task.scenarioId && item.category === category))
          fail('INVALID_PLAN', 'Plan items must belong to the task and correct category.');
      }
      task.plan = { ...plan, supplies: [...new Set(plan.supplies)] }; evaluate(task);
    }),
    lockInitialChoice: model => run(draft => {
      modelCheck(model); const task = active(draft); const d = decision(task);
      if (task.condition !== 'override' || d.phase !== 'choose') fail('INVALID_ROUTING_PHASE', 'Initial choice is unavailable.');
      d.initialModel = model; d.initialLockedAt = now(); d.phase = 'locked';
    }),
    requestRecommendation: () => run(draft => {
      const task = active(draft); const d = decision(task);
      if (task.condition === 'practice' || (task.condition === 'override' && d.phase === 'choose'))
        fail('INVALID_ROUTING_PHASE', 'Lock the independent initial choice before revealing the recommendation.');
      if (!d.recommendedModel) {
        const recommendation = recommendations[task.checkpoint];
        d.recommendedModel = recommendation.model; d.reason = recommendation.reason; d.recommendationShownAt = now();
        d.phase = task.condition === 'automatic' ? 'committed' : 'recommended';
        if (task.condition === 'automatic') { d.finalModel = recommendation.model; d.finalCommittedAt = now(); }
      }
      return d;
    }),
    confirmModel: model => run(draft => {
      modelCheck(model); const task = active(draft); const d = decision(task);
      if (task.condition !== 'override' || d.phase !== 'recommended') fail('INVALID_ROUTING_PHASE', 'Model choice is unavailable or already fixed.');
      d.finalModel = model; d.finalCommittedAt = now(); d.phase = 'committed';
    }),
    sendMessage: text => run(draft => {
      const task = active(draft); const model = decision(task).finalModel;
      if (!model) fail('MODEL_REQUIRED', 'Complete routing before agent work.');
      if (!text.trim()) fail('EMPTY_MESSAGE', 'Enter a message.');
      const stamp = now(); const index = task.messages.length;
      task.messages.push({ id: `${task.id}-message-${index}`, role: 'user', text: text.trim(), checkpoint: task.checkpoint, model: null, createdAt: stamp, simulated: false },
        { id: `${task.id}-message-${index + 1}`, role: 'assistant', text: cannedResponse(model, task.checkpoint), checkpoint: task.checkpoint, model, createdAt: stamp, simulated: true });
    }),
    advanceCheckpoint: () => run(draft => {
      const task = active(draft);
      if (!decision(task).finalModel) fail('MODEL_REQUIRED', 'Complete routing before advancing.');
      const next = checkpoints[checkpoints.indexOf(task.checkpoint) + 1];
      if (!next) fail('FINAL_CHECKPOINT', 'Submit the current plan.');
      task.checkpoint = next; task.decisions[next] = newDecision(task, now());
    }),
    finishTask: (reason = 'submitted') => run(draft => {
      const task = active(draft); const end = now();
      task.status = task.deadline !== null && end >= task.deadline ? 'timed-out' : reason;
      task.endedAt = end; evaluate(task);
      draft.step = task.id === 'practice' ? 'task-1' : task.id === 'task-1' ? 'tlx-1' : 'tlx-2';
    }),
    saveSurveyAnswers: (id, answers) => run(draft => {
      const task = draft.tasks[id];
      if (!task || id === 'practice' || task.status === 'active' || task.survey.submittedAt !== null
        || draft.step !== (id === 'task-1' ? 'tlx-1' : 'tlx-2')) fail('INVALID_SURVEY', 'Survey is unavailable for this task.');
      for (const [key, value] of Object.entries(answers)) {
        if (!surveyDimensions.includes(key as typeof surveyDimensions[number]) || !Number.isFinite(value) || value < 0 || value > 100)
          fail('INVALID_SURVEY', 'Use provisional demo responses between 0 and 100.');
      }
      Object.assign(task.survey.answers, answers);
    }),
    submitSurvey: id => run(draft => {
      const task = draft.tasks[id];
      if (!task || id === 'practice' || draft.step !== (id === 'task-1' ? 'tlx-1' : 'tlx-2')
        || surveyDimensions.some(key => task.survey.answers[key] === undefined)) fail('INCOMPLETE_SURVEY', 'Answer all six dimensions for the current task.');
      task.survey.submittedAt = now(); draft.step = id === 'task-1' ? 'task-2' : 'completion';
    }),
  };
}
