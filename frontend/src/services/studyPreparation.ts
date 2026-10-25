import type { PreparationId } from './experiment.types.ts';

export const preparationDefinition: Record<PreparationId, { version: string; statements: { id: string; text: string }[] }> = {
  'before-start': { version: 'provisional-before-start-v2', statements: [
    { id: 'no-refresh', text: 'I will avoid refreshing the page during the demonstration; unsent work may be lost.' },
    { id: 'synthetic-only', text: 'I will use invented information only.' },
  ] },
  practice: { version: 'provisional-practice-preparation-v1', statements: [
    { id: 'untimed', text: 'I understand that practice has no time limit.' },
    { id: 'excluded', text: 'I understand that practice does not count toward the study tasks.' },
  ] },
  'task-1': { version: 'provisional-task-preparation-v1', statements: [
    { id: 'time-limit', text: 'I understand that this task lasts up to 15 minutes.' },
    { id: 'no-refresh', text: 'I will not refresh the page.' },
    { id: 'submit-anytime', text: 'I can submit my current plan at any time.' },
  ] },
  'task-2': { version: 'provisional-task-preparation-v1', statements: [
    { id: 'time-limit', text: 'I understand that this task lasts up to 15 minutes.' },
    { id: 'no-refresh', text: 'I will not refresh the page.' },
    { id: 'submit-anytime', text: 'I can submit my current plan at any time.' },
  ] },
};

export const feedbackDefinition = {
  version: 'provisional-feedback-v1',
  interfaceComments: 'Was anything confusing or difficult about using the interface?',
  studyComments: 'Do you have any other comments or suggestions about the study?',
};
