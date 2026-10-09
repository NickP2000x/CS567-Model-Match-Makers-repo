import { useSyncExternalStore } from 'react';
import type { ExperimentService } from './experiment.types.ts';

// Pass a service instance created once at the app boundary; swap adapters later.
export function useExperiment(service: ExperimentService) {
  return useSyncExternalStore(service.subscribe, service.getSnapshot, service.getSnapshot);
}
