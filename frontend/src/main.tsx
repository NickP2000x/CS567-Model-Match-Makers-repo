import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { createMockExperimentService } from './services/mockExperiment';
import './styles.css';

const root = document.getElementById('root');

if (!root) {
  throw new Error('The application root is missing.');
}

const service = createMockExperimentService();

createRoot(root).render(
  <StrictMode>
    <App service={service} />
  </StrictMode>,
);
