import { preparationDefinition } from '../src/services/studyPreparation.ts';

export async function acknowledge(service, id) {
  await service.confirmPreparation(id, preparationDefinition[id].statements.map(statement => statement.id));
}

export async function startTask(service) {
  const id = service.getSnapshot().step;
  if (!service.getSnapshot().preparations[id]) await acknowledge(service, id);
  await service.beginTask();
}

export async function finishFeedback(service) {
  await service.submitFeedback({ interfaceComments: '', studyComments: '' });
}
