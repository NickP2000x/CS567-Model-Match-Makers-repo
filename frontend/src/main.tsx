import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { ServerUnavailable } from './features/study/ServerUnavailable';
import { createApiExperimentService } from './services/apiExperiment';
import { createMockExperimentService } from './services/mockExperiment';
import type { ExperimentService } from './services/experiment.types';
import './styles.css';

const root = document.getElementById('root');

if (!root) {
  throw new Error('The application root is missing.');
}

// Mock and backend modes are explicit: the backend is used only when VITE_API_BASE_URL is set.
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

async function createService(): Promise<ExperimentService> {
  if (!apiBaseUrl) return createMockExperimentService();
  return createApiExperimentService({ baseUrl: apiBaseUrl, developmentSequence: import.meta.env.DEV ? 1 : undefined });
}

const app = createRoot(root);
createService().then(
  service => app.render(<StrictMode><App service={service} /></StrictMode>),
  (error: unknown) => app.render(
    <StrictMode>
      <ServerUnavailable serverUrl={apiBaseUrl ?? ''} detail={error instanceof Error ? error.message : String(error)} />
    </StrictMode>,
  ),
);
