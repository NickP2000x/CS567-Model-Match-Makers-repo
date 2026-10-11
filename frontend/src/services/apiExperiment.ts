import type {
  CatalogItem, Checkpoint, Decision, ExperimentService, PreparationId, SequenceId, StudyState, TaskId,
} from './experiment.types.ts';

// Network adapter for the backend (#39). Screens use it exactly like the in-memory mock;
// routes and payloads follow docs/experiment-api-http-draft.md.

type ServerState = Omit<StudyState, 'pendingOperations' | 'error' | 'refreshRestartsDemo'> & { sessionId: string };
type SessionStorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export interface ApiExperimentOptions {
  baseUrl: string;
  fetch?: typeof fetch;
  // Defaults to sessionStorage, so a refresh resumes the same backend session.
  storage?: SessionStorageLike | null;
  // Development builds create development sessions (backend DEV_CONTROLS=true) instead of
  // consuming one of the twelve allocation slots.
  developmentSequence?: SequenceId;
}

export const SESSION_STORAGE_KEY = 'model-matchmakers-session';
const PLANNING_STEPS: readonly string[] = ['practice', 'task-1', 'task-2'];
// Requests overtaken by a deadline or a later checkpoint are not shown as screen errors (as in the mock).
const SUPERSEDED = new Set(['TASK_EXPIRED', 'STALE_OPERATION']);

export class ApiExperimentError extends Error {
  constructor(publicCode: string, message: string, state?: ServerState) {
    super(message);
    this.code = publicCode;
    this.state = state;
  }
  readonly code: string;
  readonly state: ServerState | undefined;
}

function freeze<T>(value: T): T {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}

function defaultStorage(): SessionStorageLike | null {
  try { return globalThis.sessionStorage ?? null; } catch { return null; }
}

export async function createApiExperimentService(options: ApiExperimentOptions): Promise<ExperimentService> {
  const base = options.baseUrl.replace(/\/+$/, '');
  const fetcher = options.fetch ?? globalThis.fetch.bind(globalThis);
  const storage = options.storage === undefined ? defaultStorage() : options.storage;
  const listeners = new Set<() => void>();

  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetcher(`${base}/api${path}`, {
        method,
        headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiExperimentError('NETWORK_ERROR', 'Could not reach the study server. Please try again.');
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const error = data?.error ?? { code: 'SERVER_ERROR', message: 'The study server returned an error.' };
      throw new ApiExperimentError(error.code, error.message, data?.state);
    }
    return data as T;
  }

  // Connect before the first render: resume the stored session, or create a new one.
  let initialState: ServerState | null = null;
  const storedId = storage?.getItem(SESSION_STORAGE_KEY);
  if (storedId) {
    try {
      initialState = await request<ServerState>('GET', `/sessions/${encodeURIComponent(storedId)}`);
    } catch (error) {
      if (!(error instanceof ApiExperimentError && error.code === 'SESSION_NOT_FOUND')) throw error;
      storage?.removeItem(SESSION_STORAGE_KEY);
    }
  }
  initialState ??= await request<ServerState>('POST', '/sessions',
    options.developmentSequence ? { sequenceId: options.developmentSequence } : {});

  let state: StudyState = freeze({ ...initialState, pendingOperations: 0, error: null, refreshRestartsDemo: false });
  storage?.setItem(SESSION_STORAGE_KEY, initialState.sessionId);

  const publish = (next: StudyState) => { state = freeze(next); listeners.forEach(listener => listener()); };
  function accept(server: ServerState) {
    storage?.setItem(SESSION_STORAGE_KEY, server.sessionId);
    publish({ ...server, pendingOperations: state.pendingOperations, error: null, refreshRestartsDemo: false });
  }
  const session = (path = '') => `/sessions/${encodeURIComponent(state.sessionId!)}${path}`;

  async function run<T>(operation: () => Promise<T>): Promise<T> {
    publish({ ...state, pendingOperations: state.pendingOperations + 1, error: null });
    try {
      return await operation();
    } catch (error) {
      const failure = error instanceof ApiExperimentError ? error
        : new ApiExperimentError('CLIENT_ERROR', 'The request could not be completed.');
      if (failure.state) accept(failure.state);
      if (!SUPERSEDED.has(failure.code)) publish({ ...state, error: { code: failure.code, message: failure.message } });
      throw failure;
    } finally {
      publish({ ...state, pendingOperations: state.pendingOperations - 1 });
    }
  }

  const mutate = (method: string, path: string, body?: unknown) =>
    run(async () => { accept(await request<ServerState>(method, session(path), body)); });

  function fail(code: string, message: string): Promise<never> {
    return run(async () => { throw new ApiExperimentError(code, message); });
  }

  // Capture the task and checkpoint when the call is made, so a reply that arrives after the
  // task or checkpoint moved on is rejected by the server instead of applied to the new one.
  function planning<T>(operation: (taskId: TaskId, checkpoint: Checkpoint) => Promise<T>): Promise<T> {
    const taskId = state.step as TaskId;
    const task = state.tasks[taskId];
    if (!PLANNING_STEPS.includes(state.step) || !task) return fail('NO_ACTIVE_TASK', 'Start an active planning task first.');
    return run(() => operation(taskId, task.checkpoint));
  }
  const planningMutation = (method: string, path: string, body: Record<string, unknown> = {}) =>
    planning(async (taskId, checkpoint) => {
      accept(await request<ServerState>(method, session(`/tasks/${taskId}${path}`), { ...body, checkpoint }));
    });

  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    reset: sequenceId => mutate('POST', '/reset', sequenceId ? { sequenceId } : {}),
    recordConsent: accepted => mutate('POST', '/consent', { accepted }),
    saveDemographics: values => mutate('POST', '/demographics', values),
    completeTutorial: () => mutate('POST', '/tutorial/complete'),
    confirmPreparation: (id: PreparationId, acknowledgedIds) => mutate('POST', `/preparations/${id}`, { acknowledgedIds }),
    getScenario: id => run(() => request('GET', `/scenarios/${encodeURIComponent(id)}`)),
    searchCatalog: (id, query = '', category) => {
      const params = new URLSearchParams({ query });
      if (category) params.set('category', category);
      return run(() => request('GET', `/scenarios/${encodeURIComponent(id)}/catalog?${params}`));
    },
    inspectItem: itemId => planning(async (taskId, checkpoint) => {
      const data = await request<{ item: CatalogItem; state: ServerState }>(
        'POST', session(`/tasks/${taskId}/inspect`), { itemId, checkpoint });
      accept(data.state);
      return data.item;
    }),
    beginTask: () => {
      if (!PLANNING_STEPS.includes(state.step)) return fail('INVALID_STEP', 'Reach a planning step first.');
      return mutate('POST', `/tasks/${state.step}/begin`);
    },
    updatePlan: plan => planningMutation('PUT', '/plan', { plan }),
    lockInitialChoice: model => planningMutation('POST', '/routing/initial', { model }),
    requestRecommendation: () => planning(async (taskId, checkpoint) => {
      accept(await request<ServerState>('POST', session(`/tasks/${taskId}/routing/recommendation`), { checkpoint }));
      return state.tasks[taskId]!.decisions[checkpoint] as Decision;
    }),
    confirmModel: model => planningMutation('POST', '/routing/confirm', { model }),
    sendMessage: text => planningMutation('POST', '/messages', { text }),
    advanceCheckpoint: () => planningMutation('POST', '/checkpoint/advance'),
    finishTask: (reason = 'submitted') => {
      if (!PLANNING_STEPS.includes(state.step)) return fail('NO_ACTIVE_TASK', 'Start an active planning task first.');
      return mutate('POST', `/tasks/${state.step}/finish`, { reason });
    },
    saveSurveyAnswers: (taskId, answers) => taskId === 'practice'
      ? fail('INVALID_SURVEY', 'Survey is unavailable for this task.')
      : mutate('PUT', `/surveys/${taskId}`, { answers }),
    submitSurvey: taskId => taskId === 'practice'
      ? fail('INCOMPLETE_SURVEY', 'Answer all six dimensions for the current task.')
      : mutate('POST', `/surveys/${taskId}/submit`),
    submitFeedback: answers => mutate('POST', '/feedback', answers),
  };
}
