export type Model = 'small' | 'large';
export type Condition = 'automatic' | 'override';
export type SequenceId = 1 | 2 | 3 | 4;
export type ScenarioId = 'practice' | 'A' | 'B';
export type TaskId = 'practice' | 'task-1' | 'task-2';
export type Category = 'venue' | 'catering' | 'supplies';
export const checkpoints = ['Venue', 'Catering', 'Supplies', 'Final constraint check'] as const;
export type Checkpoint = (typeof checkpoints)[number];
export type StudyStep = 'consent' | 'demographics' | 'tutorial' | TaskId | 'tlx-1' | 'tlx-2' | 'feedback' | 'completion';
export type PreparationId = 'before-start' | TaskId;
export interface PreparationRecord {
  version: string; acknowledgedIds: string[]; statements: { id: string; text: string }[]; confirmedAt: number;
}
export interface FeedbackAnswers { interfaceComments: string; studyComments: string }
export const surveyDimensions = ['mentalDemand', 'physicalDemand', 'temporalDemand', 'performance', 'effort', 'frustration'] as const;
export type SurveyDimension = (typeof surveyDimensions)[number];
export type SurveyAnswers = Partial<Record<SurveyDimension, number>>;
export interface SurveyItemDefinition {
  label: string; question: string; leftAnchor: string; rightAnchor: string;
  orientation: 'higher-is-more-workload' | 'lower-is-more-workload';
  labels?: string[];
}
export interface SurveyMetadata {
  version: string; provisional: true; min: number; max: number; increment: number;
  items: Record<SurveyDimension, SurveyItemDefinition>;
}

export interface Assignment { scenarioId: 'A' | 'B'; condition: Condition }
export interface Scenario {
  id: ScenarioId;
  title: string;
  requirements: { budgetCents: number; attendees: number; dietaryNeeds: string[]; wheelchairRequired: boolean };
  provisional: true;
}
export interface CatalogSummary {
  id: string; scenarioId: ScenarioId; category: Category; name: string; summary: string; priceCents: number;
}
export interface CatalogItem extends CatalogSummary {
  details: string; capacity?: number; wheelchairAccessible?: boolean; servings?: number; dietaryCoverage?: string[];
}
export interface Plan { venue: string | null; catering: string | null; supplies: string[] }
export interface Constraints { budget: boolean; capacity: boolean; dietary: boolean; accessibility: boolean }
export interface Decision {
  phase: 'choose' | 'locked' | 'awaiting-recommendation' | 'recommended' | 'committed';
  initialModel: Model | null; recommendedModel: Model | null; finalModel: Model | null;
  reason: string | null; shownAt: number; initialLockedAt: number | null;
  recommendationShownAt: number | null; finalCommittedAt: number | null;
}
export interface Message {
  id: string; role: 'user' | 'assistant'; text: string; checkpoint: Checkpoint;
  model: Model | null; createdAt: number; simulated: boolean;
}
export interface Task {
  id: TaskId; scenarioId: ScenarioId; condition: Condition | 'practice'; excludedFromResults: boolean;
  status: 'active' | 'submitted' | 'timed-out'; startedAt: number; deadline: number | null; endedAt: number | null;
  checkpoint: Checkpoint; decisions: Partial<Record<Checkpoint, Decision>>;
  messages: Message[]; inspectedItems: string[]; plan: Plan; totalCostCents: number; constraints: Constraints;
  survey: { answers: SurveyAnswers; metadata: SurveyMetadata | null; rawScore: number | null; submittedAt: number | null };
}
export interface StudyState {
  participantId: string; sequenceId: SequenceId; assignments: [Assignment, Assignment]; step: StudyStep;
  consent: boolean | null; demographics: { age: number; gender: string; priorLlmUsage: string } | null;
  tasks: Partial<Record<TaskId, Task>>;
  preparations: Partial<Record<PreparationId, PreparationRecord>>;
  feedback: (FeedbackAnswers & { version: string; submittedAt: number }) | null;
  pendingOperations: number; error: { code: string; message: string } | null;
  // The in-memory mock is always simulated and restarts on refresh; the API adapter (#39)
  // resumes the backend session, whose agent is real when the backend runs real models.
  simulated: boolean; refreshRestartsDemo: boolean;
  sessionId?: string;
  // Backend only: false when recommendations come from RouteLLM (#37). Absent means simulated.
  routerSimulated?: boolean;
}
export interface ExperimentService {
  getSnapshot(): StudyState;
  subscribe(listener: () => void): () => void;
  reset(sequenceId?: SequenceId): Promise<void>;
  recordConsent(accepted: boolean): Promise<void>;
  saveDemographics(values: NonNullable<StudyState['demographics']>): Promise<void>;
  completeTutorial(): Promise<void>;
  confirmPreparation(id: PreparationId, acknowledgedIds: string[]): Promise<void>;
  getScenario(id: ScenarioId): Promise<Scenario>;
  searchCatalog(id: ScenarioId, query?: string, category?: Category): Promise<CatalogSummary[]>;
  inspectItem(id: string): Promise<CatalogItem>;
  beginTask(): Promise<void>;
  updatePlan(plan: Plan): Promise<void>;
  lockInitialChoice(model: Model): Promise<void>;
  requestRecommendation(): Promise<Decision>;
  confirmModel(model: Model): Promise<void>;
  sendMessage(text: string): Promise<void>;
  advanceCheckpoint(): Promise<void>;
  finishTask(reason?: 'submitted' | 'timed-out'): Promise<void>;
  saveSurveyAnswers(taskId: TaskId, answers: SurveyAnswers): Promise<void>;
  submitSurvey(taskId: TaskId): Promise<void>;
  submitFeedback(answers: FeedbackAnswers): Promise<void>;
}
